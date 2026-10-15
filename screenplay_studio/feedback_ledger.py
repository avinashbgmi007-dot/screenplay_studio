"""Gate 9 — the feedback ledger: the system of record for what the desk said.

Amendment 6 measured the fact this gate exists for. Across two real runs of the
same model on the same script, only 25 % of marked findings had their point
re-raised; 65 % were not re-raised at all — and no identity function fixes that,
because the judgment tier churns by nature (the deterministic tier re-raised
100 %). So "nothing lost" cannot mean *every mark survives*. It must mean *every
mark stays accounted for*: each run is recorded, and every prior thread is
reconciled against the new one.

The reconcile vocabulary is the design's, not this module's:

    same            the thread was re-raised and its content id survived
    maybe           a weak counterpart exists (same category, overlapping scene,
                    similar issue text) — a candidate, not a claim
    likely_resolved the writer marked it addressed (or dismissed it) and it did
                    NOT come back — the payoff the writer actually feels
    not_re_raised   it did not come back and the writer never marked it — the
                    honest "the model moved on" case, which is why a matcher can
                    never satisfy "nothing lost" and a ledger can
    new             a thread with no prior counterpart at all

A thread is keyed by the finding's content id (`revision.compute_finding_id`) —
the SAME identity the writer's marks and verdicts key on, so a thread is exactly
the thing the writer acted on, not a parallel notion of identity.

The ledger is a LOG, not a matcher. It records what each run delivered and
derives the reconciliation on read, so a better matcher later re-reads the same
history instead of needing a migration — the property Amendment 6 asks for when
it says the ledger "must not depend on one" matcher.

Store discipline is the house one, unchanged: its OWN file, the lock spans the
read, the write is atomic, and a damaged store is refused rather than
overwritten. A ledger write can never cost the writer their marks, verdicts or
report — it is a separate file for exactly that reason.
"""
import os
import time

# How similar two issue texts must be to call one a WEAK counterpart of the
# other. Deliberately not 1.0 and deliberately not low: the measured near-miss
# in Amendment 6 sat at 0.88 while genuine "different points" sat at 0.17-0.43,
# so anything in that wide gap separates them. 0.5 sits in the middle and errs
# toward `maybe` (a candidate the writer can dismiss) rather than toward a
# confident `same`.
MAYBE_SIMILARITY = 0.5


def ledger_path(m) -> str:
    return os.path.join(m.project_dir, "feedback_ledger.json")


def load_ledger(m) -> dict:
    """The recorded runs. Missing -> {"runs": []}; damaged -> StoreUnreadable.

    The default is a well-formed empty ledger, never a bare {}: a caller must be
    able to tell "no runs recorded yet" from "the store is unreadable", and only
    the second is damage.
    """
    from .jsonio import StoreUnreadable, load_json_store
    path = ledger_path(m)
    data = load_json_store(path, default={"runs": []})
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise StoreUnreadable(path, "expected an object with a 'runs' list")
    return data


def _threads_from_report(m, report: dict) -> list:
    """One thread per DISTINCT finding id — the same collapse `verdict_accuracy`
    uses, so the ledger's population is the delivered set the writer judges."""
    from .revision import annotate_report_scene_keys, compute_finding_id
    report = annotate_report_scene_keys(m, report)
    seen: dict = {}
    for f in report.get("findings") or []:
        if not isinstance(f, dict):
            continue
        fid = compute_finding_id(f)
        if fid in seen:
            continue
        seen[fid] = {
            "id": fid,
            "category": f.get("category"),
            "issue": f.get("issue"),
            "severity": f.get("severity"),
            "scene_key": f.get("scene_key"),
            "scene_refs": list(f.get("scene_refs") or []),
            "quote": f.get("evidence_quote"),
        }
    return list(seen.values())


def _signature(threads: list) -> str:
    """A stable fingerprint of a run's delivered set, so recording the SAME
    report twice (a re-run that produced identical output, or a double call)
    does not log two runs for one delivery."""
    import hashlib
    blob = "|".join(sorted(t["id"] for t in threads))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def record_run(m, report: dict) -> int:
    """Append this run's delivered set to the ledger; return the run number.

    Recording the same delivered set twice is a no-op — one delivery is one run,
    however many times the writer pressed the button. A damaged ledger raises
    (the caller decides; it must never be silently reset), but the caller is
    expected to treat that as a warning, not a failure: the report is already on
    disk and the ledger is the audit trail, not the deliverable.
    """
    from .jsonio import StoreUnreadable, load_json_store, lock_for, atomic_write_json
    path = ledger_path(m)
    threads = _threads_from_report(m, report)
    sig = _signature(threads)
    with lock_for(path):
        data = load_json_store(path, default={"runs": []})   # damaged -> raises
        if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
            raise StoreUnreadable(path, "expected an object with a 'runs' list")
        runs = data["runs"]
        if runs and runs[-1].get("signature") == sig:
            return len(runs)                                  # same delivery, one run
        runs.append({
            "run": len(runs) + 1,
            "at": time.time(),
            "model_used": report.get("model_used"),
            "signature": sig,
            "threads": threads,
        })
        atomic_write_json(path, {"runs": runs})
    return len(runs)


def _jaccard(a, b) -> float:
    from screenplay_analyzer.finding_integrity import jaccard
    return jaccard(a, b)


def _weak_counterpart(prev: dict, cur_threads: list, used: set):
    """The best not-yet-claimed thread in `cur_threads` that could be the same
    point as `prev`, or None. Same category is required — a dialogue note and a
    structure note are not two views of one point — and either the scenes
    overlap or neither names a scene. Returns (thread, similarity)."""
    best = None
    p_scenes = set(prev.get("scene_refs") or [])
    for c in cur_threads:
        if c["id"] in used or c.get("category") != prev.get("category"):
            continue
        c_scenes = set(c.get("scene_refs") or [])
        if p_scenes and c_scenes and not (p_scenes & c_scenes):
            continue
        sim = _jaccard(prev.get("issue"), c.get("issue"))
        if sim >= MAYBE_SIMILARITY and (best is None or sim > best[1]):
            best = (c, sim)
    return best


def reconcile(prev_threads: list, cur_threads: list,
              addressed_ids=(), dismissed_ids=()) -> dict:
    """Classify every thread across two consecutive runs.

    Returns the five buckets plus counts. Every prior thread lands in exactly
    one of same / maybe / likely_resolved / not_re_raised, and every current
    thread lands in exactly one of same / maybe / new — so the buckets are a
    partition, and "nothing lost" is checkable as `len(prev) == same+maybe+
    resolved+not_re_raised` rather than asserted.
    """
    addressed = set(addressed_ids or ())
    dismissed = set(dismissed_ids or ())
    cur_by_id = {t["id"]: t for t in cur_threads}
    out = {"same": [], "maybe": [], "likely_resolved": [],
           "not_re_raised": [], "new": []}
    used: set = set()
    for p in prev_threads:
        if p["id"] in cur_by_id:
            out["same"].append({"prev": p, "cur": cur_by_id[p["id"]]})
            used.add(p["id"])
            continue
        weak = _weak_counterpart(p, cur_threads, used)
        if weak is not None:
            thread, sim = weak
            out["maybe"].append({"prev": p, "cur": thread, "similarity": round(sim, 2)})
            used.add(thread["id"])
            continue
        if p["id"] in addressed or p["id"] in dismissed:
            out["likely_resolved"].append(p)
        else:
            out["not_re_raised"].append(p)
    for c in cur_threads:
        if c["id"] not in used:
            out["new"].append(c)
    out["counts"] = {k: len(v) for k, v in out.items() if k != "counts"}
    out["prev_total"] = len(prev_threads)
    out["cur_total"] = len(cur_threads)
    return out


def ledger_view(m) -> dict:
    """What the desk reads: the last two runs reconciled, plus the run count.

    One run -> no reconciliation yet (there is nothing to compare against), and
    the view says so instead of inventing a comparison against nothing.
    """
    runs = load_ledger(m).get("runs") or []
    if not runs:
        return {"runs": 0, "reconcile": None, "latest": None, "previous": None}
    latest = runs[-1]
    if len(runs) < 2:
        return {"runs": len(runs), "reconcile": None,
                "latest": _summary(latest), "previous": None}
    from .revision import finding_intents, dismissed_finding_ids
    try:
        intents = finding_intents(m)
    except Exception:
        intents = {}
    try:
        dismissed = dismissed_finding_ids(m)
    except Exception:
        dismissed = set()
    addressed = [k for k, v in (intents or {}).items() if v == "addressed"]
    prev = runs[-2]
    rec = reconcile(prev.get("threads") or [], latest.get("threads") or [],
                    addressed_ids=addressed, dismissed_ids=dismissed)
    return {"runs": len(runs), "reconcile": rec,
            "latest": _summary(latest), "previous": _summary(prev)}


def _summary(run: dict) -> dict:
    return {"run": run.get("run"), "at": run.get("at"),
            "model_used": run.get("model_used"),
            "threads": len(run.get("threads") or [])}
