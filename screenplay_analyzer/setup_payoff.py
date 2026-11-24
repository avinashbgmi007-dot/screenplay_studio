"""
Setup/Payoff ledger — the end-of-pipeline whole-script audit.

The Principles Engine judges each mechanically-flagged candidate from its
own mentions alone: "was THIS object significant, and was it paid off?" It
cannot see the arc. This pass is the complementary view and it runs LAST,
when the whole script's shape is available: the model gets the
scene-by-scene overview of the entire screenplay plus the mechanically
extracted candidate list, and produces a model-assessed ledger — for every setup it can see (seeded
candidates AND setups the extractor missed: thematic promises and single-scene
emphasis), with cited setup/payoff scenes and a proposed status. These
assessments remain proposals until a reader judges their narrative meaning.

This is deliberately a diagnosis-only output: the ledger says what's set up
and what never comes back. Proposing fixes stays in the conversational
layer, where the writer can ask for it.

Dangling entries are folded back into findings only while they still carry a
model-assigned dangling/abandoned status. Mechanical adjudication changes
unprovable verdicts to `unverified`, because absence of a later mention cannot
prove that a setup was forgotten. Those entries remain visible in the ledger
with the model's original assessment and the reason it could not be verified.
"""

from __future__ import annotations

import re

from . import prompts
from .grammar import setup_payoff_ledger_grammar
from .deterministic_utils import int_list
from .rules_context import severity_for as _severity_for

# Cap total ledger entries so a long script's overview + a greedy model can't
# blow the output budget or the grammar's patience.
MAX_LEDGER_ENTRIES = 12

# Time-pressure expressions: relative countdowns, clock-face countdown
# displays, and the words that announce them. A countdown buried in
# dialogue is neither a KG prop nor a promise-shaped line, so without these
# the ledger is never asked about it (trial-9 recall audit: the 'Inka 3
# mints / 00:00' beat reached neither findings nor ledger). Bare "clock" is
# deliberately NOT a keyword (trial 11: a wall clock mentioned as set
# dressing seeded noise) — "alarm"/"timer" stay, because a ringing alarm is
# a beat, while a clock on the wall usually is not.
_TIME_PATTERNS = [
    re.compile(r"[0-9]+[ ]*(?:mints?|minutes?|mins?|seconds?|secs?|hours?|hrs?)", re.I),
    re.compile(r"[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?(?![ ]*(?:AM|PM))", re.I),
    re.compile(r"(?:count[ ]?downs?|deadlines?|ticking|timers?|alarms?)", re.I),
]
MAX_TIME_SEEDS = 4

_STATUS_ORDER = {"dangling": 0, "abandoned": 1, "red_herring": 2, "paid": 3}


def _seed_candidates(kg, doc=None) -> list[str]:
    """Compact seed list of mechanically-flagged candidates — props and
    dialogue promises — with the scenes they appear in, straight from the
    knowledge graph (real text, no paraphrase). Time-pressure lines come
    from the document itself (see `_time_pressure_seeds`); `doc` may be
    None, in which case that family is skipped."""
    seeds = []
    for p in sorted(kg.prop_candidates, key=lambda c: -c.mention_count):
        scenes = ", ".join(f"S{s}" for s in p.scenes_mentioned)
        seeds.append(f'- OBJECT "{p.name}" — mentioned in scenes {scenes}')
    for p in kg.promise_candidates:
        text = (p.text or "").strip()[:120]
        seeds.append(f'- PROMISE (by {p.character}, scene {p.scene_number}): "{text}"')
    seeds.extend(_time_pressure_seeds(doc))
    return seeds


def _time_pressure_seeds(doc) -> list[str]:
    """One seed per scene containing a time-pressure line, capped. Candidate
    generation only — the model still judges whether the beat matters."""
    if doc is None:
        return []
    from screenplay_parser.quotematch import find_scene_text
    seeds = []
    for s in (doc.scenes or []):
        n = getattr(s, "scene_number", None)
        if not n:
            continue
        try:
            text = find_scene_text(doc, n)
        except Exception:
            continue
        if not text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if len(line.split()) < 3:
                continue
            if any(p.search(line) for p in _TIME_PATTERNS):
                seeds.append(f'- TIME-PRESSURE (scene {n}): "{line[:120]}"')
                break
        if len(seeds) >= MAX_TIME_SEEDS:
            break
    return seeds


def run_setup_payoff_ledger(
    overview: str,
    kg,
    client,
    rules_fragment: str = "",
    total_scenes: int = 0,
    language: str = "eng",
    doc=None,
) -> tuple[list[dict], list[str]]:
    """One whole-script call producing the setup/payoff ledger.

    Returns (entries, errors). Before adjudication, entries have:
      {setup, kind, setup_scenes, payoff_scenes (list|None), status, note}
    status is one of paid | dangling | abandoned | red_herring. The later
    `adjudicate_ledger` pass may change an unprovable model status to
    `unverified`, preserving the original in `model_status`.

    `doc` is optional: when present its scenes contribute time-pressure
    seeds; without it that family is skipped (all existing callers keep
    working).
    """
    seeds = _seed_candidates(kg, doc)
    seed_block = chr(10).join(seeds) if seeds else (
        "(none mechanically flagged — judge from the overview alone)"
    )
    system, user = prompts.setup_payoff_ledger_prompt(
        overview, seed_block, rules_fragment, total_scenes, language=language
    )
    try:
        data = client.chat_json(
            system, user,
            grammar=setup_payoff_ledger_grammar(),
            max_tokens=2000,
            temperature=0.3,
        )
    except Exception as e:  # LlamaServerError and any client wrapper
        return [], [f"Setup/payoff ledger failed: {e}"]

    if not isinstance(data, dict):
        return [], ["Setup/payoff ledger returned a non-object."]
    entries = data.get("ledger")
    if not isinstance(entries, list):
        return [], ["Setup/payoff ledger missing the 'ledger' list."]

    cleaned = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        setup = (e.get("setup") or "").strip()
        if not setup:
            continue
        status = e.get("status")
        if status not in ("paid", "dangling", "abandoned", "red_herring"):
            status = "dangling"  # default: flag it, don't silently drop it
        cleaned.append({
            "setup": setup[:200],
            "kind": e.get("kind") or "other",
            "setup_scenes": int_list(e.get("setup_scenes")),
            "payoff_scenes": int_list(e.get("payoff_scenes")) or None,
            "status": status,
            "note": (e.get("note") or "").strip()[:400],
        })
    cleaned.sort(key=lambda e: _STATUS_ORDER.get(e["status"], 9))
    return cleaned[:MAX_LEDGER_ENTRIES], []


def _setup_quote(entry: dict, doc) -> str | None:
    """Best-matching setup-scene line for the entry's terms (windowed
    matcher, 0.72 floor shared with the verifier; token-overlap fallback
    mirrors _terms_in_scenes — a lone content term can never reach the
    fuzzy floor against a full line, but its presence still grounds the
    row). None when nothing qualifies — the row then keeps today's
    ungrounded path."""
    from screenplay_analyzer.verifier import (
        _normalize, _best_fuzzy_match, _token_overlap,
        FUZZY_MATCH_THRESHOLD,
    )
    from screenplay_parser.quotematch import find_scene_text
    terms = sorted(_content_terms(entry.get("setup")))
    if not terms or not doc:
        return None
    joined = _normalize(" ".join(terms))
    best, best_conf = None, 0.0
    for n in entry.get("setup_scenes") or []:
        text = find_scene_text(doc, n)
        if not text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if len(line.split()) < 3:
                continue
            lnorm = _normalize(line)
            conf = _best_fuzzy_match(joined, lnorm)
            if conf < FUZZY_MATCH_THRESHOLD and _token_overlap(joined, lnorm) < 0.5:
                continue
            if conf > best_conf:
                best, best_conf = line, conf
    return best


def dangling_findings(ledger: list[dict], existing_plot_thread: list[dict],
                      rules_ctx=None, doc=None) -> list[dict]:
    """Fold adjudicated dangling/abandoned ledger entries into findings for
    the Fix Queue, deduped against existing plot_thread findings (e.g. the
    Principles Engine's 'Promise never fulfilled' for the same candidate).

    Entries marked unverified by adjudication are deliberately not promoted
    into findings: quote-checking the setup cannot prove the absence of a
    later payoff. Raw legacy entries without a `verified` field retain the
    previous behavior for callers that do not run adjudication.

    `rules_ctx` is optional: when present, the finding takes the cited rule's
    curated severity instead of a flat default, so this pass and the
    Principles Engine grade the same defect the same way."""
    existing_texts = []
    for f in existing_plot_thread:
        issue = (f.get("issue") or "").lower()
        why = (f.get("why_it_matters") or "").lower()
        existing_texts.append(issue + " " + why)

    findings = []
    for e in ledger:
        if e.get("status") not in ("dangling", "abandoned") or e.get("verified") is False:
            continue
        setup = (e.get("setup") or "").strip()
        haystack = " ".join(existing_texts)
        if setup and setup.lower()[:40] in haystack:
            continue  # already reported by the Principles Engine
        label = "Setup left dangling" if e.get("status") == "dangling" else "Setup abandoned"
        scenes = e.get("setup_scenes") or []
        if not scenes and doc is not None:
            terms = _content_terms(setup)
            ok, at = _terms_in_scenes(terms, doc,
                                      [s.scene_number for s in (doc.scenes or [])])
            if ok and at is not None:
                scenes = [at]
                e["setup_scenes"] = scenes
        quote = _setup_quote(e, doc) if doc is not None else None
        findings.append({
            "category": "plot_thread",
            "rule_id": "setup_payoff_general",
            "issue": f'{label}: "{setup}"',
            "why_it_matters": e.get("note") or "Set up on the page, never paid off.",
            "severity": _severity_for(rules_ctx, "setup_payoff_general"),
            "scene_refs": scenes,
            "evidence_quote": quote,
        })
    return findings


def _content_terms(text: str) -> set:
    import re
    from screenplay_analyzer.verifier import _STOPWORDS
    META = {"scene", "scenes", "sc", "setup", "payoff", "promise",
            "stated", "mentioned", "described"}
    return {w for w in re.sub(r"[^a-z0-9 ]", " ",
            str(text or "").lower()).split()
            if w not in _STOPWORDS and w not in META
            and not w.isdigit() and len(w) > 1}


def _terms_in_scenes(terms: set, doc, scenes: list) -> tuple[bool, int | None]:
    """True + first matching scene when the terms land in one cited scene.

    Term matching is candidate generation only. It cannot determine whether
    a later appearance fulfills a promise, closes a thread, or pays off an
    object setup.
    """
    from screenplay_analyzer.verifier import (
        _normalize, _best_fuzzy_match, _token_overlap,
        FUZZY_MATCH_THRESHOLD,
    )
    from screenplay_parser.quotematch import find_scene_text
    for n in scenes or []:
        text = find_scene_text(doc, n)
        if not text:
            continue
        tnorm = _normalize(text).replace("_", " ")
        joined = " ".join(sorted(terms))
        if _best_fuzzy_match(_normalize(joined), tnorm) >= FUZZY_MATCH_THRESHOLD:
            return True, n
        if _token_overlap(" ".join(sorted(terms)), tnorm) >= 0.5:
            return True, n
        if terms:
            norm_terms = [_normalize(t) for t in terms]
            hits = sum(1 for nt in norm_terms if nt and nt in tnorm)
            if hits >= max(1, (len(norm_terms) + 1) // 2):
                return True, n
    return False, None


def _mark_unverified(entry: dict) -> None:
    """Keep the source model assessment separate from mechanical evidence."""
    if "model_status" not in entry:
        entry["model_status"] = entry.get("status")
    if "model_note" not in entry:
        entry["model_note"] = entry.get("note") or ""
    if "model_setup_scenes" not in entry:
        entry["model_setup_scenes"] = list(entry.get("setup_scenes") or [])
    if "model_payoff_scenes" not in entry:
        entry["model_payoff_scenes"] = list(entry.get("payoff_scenes") or []) or None
    entry["status"] = "unverified"
    entry["verified"] = False


def adjudicate_ledger(entries: list, doc) -> list:
    """Record textual matches without treating recurrence as narrative payoff.

    This pass can locate terms and cite candidate recurrence scenes. It cannot
    determine whether a later appearance fulfills a promise, closes a thread,
    or makes an earlier object meaningful. Nor can failure to find terms prove
    that a setup was abandoned. All model statuses therefore remain auditable
    proposals, not mechanically verified conclusions. Reprocessing is
    idempotent: source fields are captured once and derived fields are replaced.
    """
    scene_numbers = [s.scene_number for s in (doc.scenes or [])]
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        _mark_unverified(e)
        terms = _content_terms(e.get("setup"))
        model_setup = list(e.get("model_setup_scenes") or [])
        model_payoff = list(e.get("model_payoff_scenes") or [])
        e["candidate_setup_scenes"] = []
        e["candidate_recurrence_scenes"] = []
        e.pop("setup_ungrounded", None)
        e.pop("payoff_unproven", None)
        e.pop("setup_citation_missing", None)
        e.pop("payoff_citation_before_setup", None)
        # Preserve model-cited scenes separately; never expose them as
        # confirmed payoff locations to existing readers.
        e["payoff_scenes"] = None

        if terms:
            search_setup_scenes = model_setup or scene_numbers
            for scene_num in search_setup_scenes:
                ok, _ = _terms_in_scenes(terms, doc, [scene_num])
                if ok:
                    e["candidate_setup_scenes"].append(scene_num)
            if not model_setup:
                e["setup_citation_missing"] = True
                if not e["candidate_setup_scenes"]:
                    for scene_num in scene_numbers:
                        ok, _ = _terms_in_scenes(terms, doc, [scene_num])
                        if ok:
                            e["candidate_setup_scenes"].append(scene_num)
            elif not e["candidate_setup_scenes"]:
                e["setup_ungrounded"] = True
                for scene_num in scene_numbers:
                    ok, _ = _terms_in_scenes(terms, doc, [scene_num])
                    if ok:
                        e["candidate_setup_scenes"].append(scene_num)

            if not e["candidate_setup_scenes"]:
                e["setup_ungrounded"] = True
            elif not model_setup:
                e["candidate_setup_scenes"] = e["candidate_setup_scenes"][:1]

            if e["candidate_setup_scenes"]:
                setup_after = max(e["candidate_setup_scenes"])
            else:
                numeric_refs = [n for n in model_setup if isinstance(n, int) and not isinstance(n, bool)]
                setup_after = max(numeric_refs) if numeric_refs else 0
            later_scenes = [n for n in scene_numbers if n > setup_after]
            for scene_num in later_scenes:
                ok, _ = _terms_in_scenes(terms, doc, [scene_num])
                if ok:
                    e["candidate_recurrence_scenes"].append(scene_num)

            if model_payoff and any(
                isinstance(n, int) and not isinstance(n, bool) and n <= setup_after
                for n in model_payoff
            ):
                e["payoff_citation_before_setup"] = True

        if e.get("setup_ungrounded"):
            reason = "the cited setup location was not grounded; the payoff assessment remains a model proposal"
        elif e.get("candidate_recurrence_scenes"):
            scenes = ", ".join(str(n) for n in e["candidate_recurrence_scenes"])
            reason = (
                f"setup terms also recur in scene(s) {scenes}; this is a candidate recurrence, "
                "not confirmation of narrative payoff"
            )
        else:
            reason = (
                "no later textual recurrence was located; absence of terms or a payoff citation "
                "cannot establish that the setup is dangling or abandoned"
            )
        if e.get("payoff_citation_before_setup"):
            reason += "; at least one model-cited payoff scene is at or before the setup"
        if not terms:
            reason = "the setup has no checkable content terms; the payoff assessment remains unverified"
        e["verify_note"] = reason
        e["status"] = "unverified"
        e["verified"] = False
    return entries
