"""
Evidence verification.

The single biggest trust problem with LLM-generated script coverage is
confident, specific-sounding citations that don't actually check out —
"Scene 14" when it means Scene 12, or a quote that was never in the script.
This module catches that mechanically rather than trusting the model.

Policy: a finding with an unverifiable quote is NOT discarded (the
underlying observation may still be correct even if the model misquoted or
paraphrased the evidence) — it's downgraded and flagged so the report is
honest about what's confirmed vs. what's the model's unverified claim. This
matches the "flag, don't silently drop" approach — silently discarding
findings would hide real issues just because the model's memory of exact
wording was imperfect.
"""

from screenplay_parser.models import ScriptDocument
from screenplay_parser.quotematch import (
    find_scene_text as _scene_full_text,
    normalize_text as _normalize,
    windowed_similarity as _best_fuzzy_match,
)

# Verification is LENIENT on purpose: a model paraphrases a real line, and
# calling a real quote fabricated is the expensive error here.
FUZZY_MATCH_THRESHOLD = 0.72

# _normalize, _scene_full_text and _best_fuzzy_match are ALIASES, not wrappers.
# The primitives live in screenplay_parser.quotematch so that the studio's
# status engine (revision.quote_present) shares them: the two engines used to
# normalise and build the haystack differently, so a quote spanning a line wrap
# or mixing straight and curly quotes read as `verified` to the analyzer and
# `gone` to the status engine — which made the desk report unedited findings as
# "addressed by you". The private names survive because
# screenplay_cowriter.reply_transforms imports them.
#
# The THRESHOLD is deliberately NOT shared. Change detection asks a different
# question ("did the writer change this line?") and must be strict; see
# revision.QUOTE_CHANGE_THRESHOLD.


def verify_finding(finding: dict, doc: ScriptDocument) -> dict:
    """
    Mutates and returns the finding dict with a `verification` block:
      {status: "verified" | "not_found" | "no_quote" | "scene_not_found",
       matched_scene: int | null, confidence: float}
    """
    quote = finding.get("evidence_quote")
    scene_refs = finding.get("scene_refs") or []

    def _quoteless() -> dict:
        # A quote-less finding cites SCENE NUMBERS instead (theme/character/
        # structure/scene_function reason from summaries, so prompts force
        # evidence_quote to null). Those numbers are the finding's only
        # citation, and they are checkable: if EVERY cited scene is missing
        # from the parsed script, the citation cannot exist — same honesty
        # rule as a fabricated quote, same flag, never a silent pass. One
        # existing scene keeps the finding as no_quote: the citation may be
        # right even where another cited scene is not.
        if scene_refs:
            existing = {s.scene_number for s in doc.scenes}
            if all(s not in existing for s in scene_refs):
                finding["verification"] = {"status": "scene_not_found", "matched_scene": None, "confidence": None}
                return finding
        finding["verification"] = {"status": "no_quote", "matched_scene": None, "confidence": None}
        return finding

    if not quote or not quote.strip():
        return _quoteless()

    quote_norm = _normalize(quote)
    if len(quote_norm.split()) < 3:
        # too short to meaningfully verify (also too short to be useful evidence)
        return _quoteless()

    best_scene = None
    best_conf = 0.0

    for scene_num in scene_refs:
        scene_text = _scene_full_text(doc, scene_num)
        if scene_text is None:
            continue
        scene_norm = _normalize(scene_text)

        if quote_norm in scene_norm:
            finding["verification"] = {"status": "verified", "matched_scene": scene_num, "confidence": 1.0}
            return finding

        ratio = _best_fuzzy_match(quote_norm, scene_norm)
        if ratio > best_conf:
            best_conf = ratio
            best_scene = scene_num

    if scene_refs and all(_scene_full_text(doc, s) is None for s in scene_refs):
        finding["verification"] = {"status": "scene_not_found", "matched_scene": None, "confidence": None}
        return finding

    if best_conf >= FUZZY_MATCH_THRESHOLD:
        finding["verification"] = {"status": "verified", "matched_scene": best_scene, "confidence": round(best_conf, 2)}
    else:
        # last resort: check if the quote appears ANYWHERE in the script under a
        # different scene number — catches the classic "right quote, wrong scene
        # number" hallucination and lets the report correct it instead of just
        # rejecting it.
        for scene in doc.scenes:
            scene_norm = _normalize("\n".join(e.text for e in scene.elements))
            if quote_norm in scene_norm:
                finding["verification"] = {
                    "status": "verified",
                    "matched_scene": scene.scene_number,
                    "confidence": 1.0,
                    "note": f"Quote found in Scene {scene.scene_number}, not the cited scene(s) {scene_refs} — corrected.",
                }
                return finding
        finding["verification"] = {"status": "not_found", "matched_scene": None, "confidence": round(best_conf, 2)}

    return finding


def verify_findings(findings: list[dict], doc: ScriptDocument) -> list[dict]:
    return [verify_finding(f, doc) for f in findings]


def _norm_name(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", str(text or "").upper().replace("_", " ")).strip()


def verify_observation(finding: dict, doc) -> bool | None:
    """Check an observation's CONTENT against the script text — quotes are
    verified elsewhere, but the prose around them can still invent (a
    confrontation a character never attends, a line never spoken).

    Returns True (supported), False (contradicted), or None (nothing to
    check: no observation, no cited scenes). Deliberately lenient like the
    quote check: only a positive contradiction fails. A lone mismatch never
    deletes the finding — callers demote and flag.
    """
    import re
    if not isinstance(finding, dict):
        return None
    observation = finding.get("observation") or ""
    if not observation.strip():
        return None
    scene_refs = finding.get("scene_refs") or []
    if not scene_refs:
        return None

    cited = [s for s in (doc.scenes or [])
             if getattr(s, "scene_number", None) in scene_refs]
    if not cited:
        return None
    # Presence means named IN THE SCENE TEXT, not in characters_present:
    # parse attribution gaps (a present-but-cueless character) must never
    # punish a true observation (trial rerun: Senior drives sc18 yet the
    # present list is empty). Token-subset per scene, all name words.
    cited_tokens = []
    for s in cited:
        text = _scene_full_text(doc, s.scene_number) or ""
        cited_tokens.append(set(_normalize(text).split()))
    known = {_norm_name(c) for c in (getattr(doc, "all_characters", None) or [])}

    obs_norm = _norm_name(observation)
    for name in known:
        if not name:
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", obs_norm):
            # Lowercase: cited tokens come from _normalize (lowercase), names
            # from _norm_name (upper) — compare in one case.
            if not any(set(name.lower().split()) <= toks for toks in cited_tokens):
                return False

    for frag in re.findall(r"(?<!\w)\"([^\"]+)\"|(?<!\w)'([^']+)'", observation):
        text = (frag[0] or frag[1]).strip()
        if len(text.split()) < 3:
            continue
        frag_norm = _normalize(text)
        supported = any(
            _best_fuzzy_match(frag_norm, _normalize(_scene_full_text(doc, s.scene_number) or "")) >= FUZZY_MATCH_THRESHOLD
            for s in cited
        )
        if not supported:
            # Gloss leniency (same generosity as quote verification): an
            # observation often restates a line in other words ("feeling is
            # very high" for a Tenglish V.O.). If most content words land in
            # the cited scenes, the fragment is grounded even when unfuzzy.
            supported = any(
                _token_overlap(frag_norm, _normalize(_scene_full_text(doc, s.scene_number) or "")) >= 0.5
                for s in cited
            )
        if not supported:
            whole = _normalize("\n".join(
                _scene_full_text(doc, s.scene_number) or "" for s in (doc.scenes or [])))
            if _best_fuzzy_match(frag_norm, whole) < FUZZY_MATCH_THRESHOLD \
                    and _token_overlap(frag_norm, whole) < 0.5:
                return False
    return True


_STOPWORDS = frozenset(
    "is are was were be been being the a an of to in on and or very so as at "
    "by for with from that this it its it s".split())


def _token_overlap(frag_norm: str, haystack_norm: str) -> float:
    """Share of the fragment's content words present in the haystack. Catches
    gloss-paraphrases fuzzy matching rejects, without blessing inventions
    (a fabricated line shares almost no content words with the scene)."""
    words = [w for w in frag_norm.split() if w not in _STOPWORDS]
    if not words:
        return 0.0
    hay = set(haystack_norm.split())
    return sum(1 for w in words if w in hay) / len(words)


def verification_summary(findings: list[dict]) -> dict:
    counts = {"verified": 0, "not_found": 0, "no_quote": 0, "scene_not_found": 0}
    for f in findings:
        status = f.get("verification", {}).get("status", "no_quote")
        counts[status] = counts.get(status, 0) + 1
    return counts


def verification_rate(counts: dict) -> dict:
    """The derived accuracy number over `verification_summary` counts.

    Quote-bearing findings are the ones a mechanical check ran a verdict on:
    `verified`, `not_found`, and `scene_not_found`. A `scene_not_found` row is
    a citation that pointed at scenes which do not exist — the verifier ran,
    and the citation failed, so it belongs in the denominator. Excluding a
    failure from a denominator RAISES the rate; that is what flattering one
    means. The earlier version of this docstring argued the opposite, and the
    code followed it, which is how the desk reported 100% verified when half
    the citations had failed.

    `no_quote` is the one exclusion, and it is not a judgement about quality:
    those findings cite scene numbers instead of quotable lines, so there is
    nothing for the check to act on.

    None until at least one finding carries a checkable citation — a
    percentage over an EMPTY denominator is a lie. A denominator where every
    check failed is not empty, and 0% is true and actionable."""
    counts = counts or {}
    quote_bearing = (counts.get("verified", 0) + counts.get("not_found", 0)
                     + counts.get("scene_not_found", 0))
    return {
        "quote_bearing": quote_bearing,
        "verified_pct_of_quoted": (
            round(100.0 * counts.get("verified", 0) / quote_bearing, 1)
            if quote_bearing else None),
    }
