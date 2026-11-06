"""
Setup/Payoff ledger — the end-of-pipeline whole-script audit.

The Principles Engine judges each mechanically-flagged candidate from its
own mentions alone: "was THIS object/promise significant, and was it paid
off?" It cannot see the arc. This pass is the complementary view and it runs
LAST, when the whole script's shape is available: the model gets the
scene-by-scene overview of the entire screenplay plus the mechanically
extracted candidate list, and produces a ledger — for every setup it can see
(seeded candidates AND setups the extractor missed: thematic promises,
single-scene emphasis that never pays), where it was set up, where (if
anywhere) it was paid off, and an honest status: paid / dangling / abandoned
/ red herring.

This is deliberately a diagnosis-only output: the ledger says what's set up
and what never comes back. Proposing fixes stays in the conversational
layer, where the writer can ask for it.

Dangling entries are folded back into the findings (category plot_thread,
rule setup_payoff_general) so they land in the Fix Queue — deduped against
the Principles Engine's per-candidate findings so the same promise isn't
reported twice.
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
    re.compile(r"\b\d+\s*(?:mints?|minutes?|mins?|seconds?|secs?|hours?|hrs?)\b", re.I),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),
    re.compile(r"\b(?:count\s?downs?|deadlines?|ticking|timers?|alarms?)\b", re.I),
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
        seeds.append(f"- OBJECT \"{p.name}\" — mentioned in scenes {scenes}")
    for p in kg.promise_candidates:
        text = (p.text or "").strip()[:120]
        seeds.append(f"- PROMISE (by {p.character}, scene {p.scene_number}): \"{text}\"")
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
                seeds.append(f"- TIME-PRESSURE (scene {n}): \"{line[:120]}\"")
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

    Returns (entries, errors). entries is a list of:
      {setup, kind, setup_scenes, payoff_scenes (list|None), status, note}
    status is one of paid | dangling | abandoned | red_herring.

    `doc` is optional: when present its scenes contribute time-pressure
    seeds; without it that family is skipped (all existing callers keep
    working).
    """
    seeds = _seed_candidates(kg, doc)
    seed_block = "\n".join(seeds) if seeds else (
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
    """Fold dangling/abandoned ledger entries into findings for the Fix Queue,
    deduped against existing plot_thread findings (e.g. the Principles
    Engine's 'Promise never fulfilled' for the same candidate).

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
        if e.get("status") not in ("dangling", "abandoned"):
            continue
        setup = (e.get("setup") or "").strip()
        haystack = " ".join(existing_texts)
        if setup and setup.lower()[:40] in haystack:
            continue  # already reported by the Principles Engine
        label = "Setup left dangling" if e.get("status") == "dangling" else "Setup abandoned"
        quote = _setup_quote(e, doc) if doc is not None else None
        # Gap 54: "Do not count an unresolved relationship or intentionally open
        # ending as a defect merely because closure is absent." The statuses can
        # express a deliberate choice (`red_herring` is one), but the note is
        # free prose and the reader of a finding needs to know a strand may be
        # open on purpose. So the finding says it, and a candidate location from
        # `adjudicate_ledger` is surfaced as evidence to check rather than
        # silently absorbed into a verdict.
        why = (e.get("note") or "Set up on the page, never paid off.").strip()
        why += (" An unresolved strand can be deliberate — the story may end with "
                "it open on purpose. If it is, this note is wrong and the strand "
                "is fine.")
        candidates = e.get("payoff_candidates") or []
        if candidates:
            why += (" The setup's words reappear in scene "
                    f"{', '.join(str(n) for n in candidates)} — worth reading that "
                    "scene, though matching words are not a payoff.")
        findings.append({
            "category": "plot_thread",
            "rule_id": "setup_payoff_general",
            "issue": f'{label}: "{setup}"',
            "why_it_matters": why,
            "severity": _severity_for(rules_ctx, "setup_payoff_general"),
            "scene_refs": e.get("setup_scenes") or [],
            "evidence_quote": quote,
            "payoff_candidates": candidates,
            "is_observation": True,
            "confidence": "observation",
        })
    return findings


def _content_terms(text: str) -> set:
    import re
    from screenplay_analyzer.verifier import _STOPWORDS
    # Ledger setups are model prose ("Rishi's promise to drop something
    # (Scene 10)"), not script text: scene refs, role words, and digits
    # would sink every match, so they are stopwords here, not content.
    META = {"scene", "scenes", "sc", "setup", "payoff", "promise",
            "stated", "mentioned", "described"}
    return {w for w in re.sub(r"[^a-z0-9 ]", " ",
            str(text or "").lower()).split()
            if w not in _STOPWORDS and w not in META
            and not w.isdigit() and len(w) > 1}


def _terms_in_scenes(terms: set, doc, scenes: list) -> tuple[bool, int | None]:
    """True + first matching scene when the terms land in one cited scene
    (windowed fuzzy first, token overlap second). Majority is by overlap
    share (see `_token_overlap`), not a strict count — setup strings are
    short and scenes are long. Underscores become spaces on the haystack
    side: script cues read `X_COMPANY`/`GUN_GUY` while setups say
    `X Company`/`gun guy`, and the shared normaliser keeps `_` (pinned by
    verifier/status-engine contract tests — do not change it there)."""
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
    return False, None


def adjudicate_ledger(entries: list, doc) -> list:
    """Mechanical re-read of every model verdict.

    Gap 54. The rule this used to state was "recurrence proves payoff (flip +
    note), absence proves nothing". The asymmetry was half right: absence really
    does prove nothing. Recurrence proves nothing either. It proves that the
    setup's vocabulary appears again, which is a *location to look at*, not a
    dramatic resolution — and the two are not the same thing.

    Measured on the register's own fixture: a ledger entry saying a silver key
    opens the vault, and a second scene where the key hangs on a hook while the
    vault stays locked. The words recur, so the entry flipped `dangling` ->
    `paid`, dropped a payoff scene onto it, and set `verified: true`, which
    suppressed the dangling finding entirely. The vault is still locked.

    Now:
      * recurrence records CANDIDATE locations (`payoff_candidates`) and leaves
        the model's status alone;
      * `verified` is only ever set by checking a payoff the entry already
        claims — this pass never manufactures one;
      * an entry the model called dangling stays dangling, with the candidate
        scene recorded and uncertainty stated, so the writer can see both the
        claim and the contradictory evidence;
      * absence still proves nothing (a scene may pay off a setup in words the
        setup never used), so nothing is downgraded for lack of a match.
    """
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        terms = _content_terms(e.get("setup"))
        setup_ok, setup_at = _terms_in_scenes(
            terms, doc, e.get("setup_scenes") or [])
        if terms and not setup_ok:
            e["setup_ungrounded"] = True
            e["verified"] = False
            e["verify_note"] = "setup terms not found in the cited setup scenes"
            continue
        if e.get("status") == "paid":
            # Chronological sanity, same rule as the dangling branch: a cited
            # payoff scene at or before the setup is confusion, not a payoff
            # (trial rerun: sc17 setup "paid" via a sc4 mention). Such scenes
            # are dropped from the check, never trusted.
            setup_after = max(e.get("setup_scenes") or [0])
            cited = [n for n in (e.get("payoff_scenes") or []) if n > setup_after] \
                if e.get("setup_scenes") else (e.get("payoff_scenes") or [])
            ok, at = _terms_in_scenes(terms, doc, cited)
            e["verified"] = bool(ok)
            e["verify_note"] = (
                f"payoff terms recur in scene {at}" if ok
                else "payoff scenes carry no matching terms (kept: absence proves nothing)")
            if not ok:
                e["payoff_unproven"] = True
        elif e.get("status") in ("dangling", "abandoned"):
            # Narrative order only: a payoff must come AFTER its setup. Any
            # earlier recurrence is backstory or coincidence, never a payoff
            # (trial rerun: sc17 setup "paid" via a sc4 mention).
            setup_after = max(e.get("setup_scenes") or [0])
            if e.get("setup_scenes"):
                later = [s.scene_number for s in (doc.scenes or [])
                         if s.scene_number > setup_after]
            else:
                later = [s.scene_number for s in (doc.scenes or [])]
            ok, at = _terms_in_scenes(terms, doc, later)
            if ok:
                # Gap 54: a candidate, not a verdict. The scene's words match;
                # whether it RESOLVES the setup is a judgement about content
                # that a token overlap cannot make. The status stays as the
                # model wrote it and `verified` stays False — this pass has not
                # verified anything, it has found somewhere to look.
                e["payoff_candidates"] = [at]
                e.setdefault("payoff_scenes", e.get("payoff_scenes") or [])
                e["verified"] = False
                e["verify_note"] = (
                    f"setup terms reappear in scene {at}, which is a place to look, "
                    f"not a payoff — the entry stays {e.get('status')}")
            else:
                e["verified"] = False
                e["verify_note"] = "no later recurrence found (kept: absence proves nothing)"
        else:
            e["verified"] = False
            e["verify_note"] = "status outside the adjudicated set, kept as written"
    return entries
