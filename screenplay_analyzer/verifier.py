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

import re
from difflib import SequenceMatcher

from screenplay_parser.models import ScriptDocument

FUZZY_MATCH_THRESHOLD = 0.72


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _scene_full_text(doc: ScriptDocument, scene_number: int) -> str | None:
    for scene in doc.scenes:
        if scene.scene_number == scene_number:
            return "\n".join(e.text for e in scene.elements)
    return None


def _best_fuzzy_match(quote_norm: str, haystack_norm: str) -> float:
    """
    Sliding-window fuzzy match: compares the quote against windows of the
    haystack roughly its own size, rather than the whole scene at once
    (SequenceMatcher on very different-length strings underestimates
    similarity for a short quote inside a long scene).
    """
    words = haystack_norm.split()
    qwords = quote_norm.split()
    if not qwords:
        return 0.0
    window = max(len(qwords), 3)
    best = 0.0
    step = max(1, window // 2)
    for i in range(0, max(1, len(words) - window + 1), step):
        chunk = " ".join(words[i:i + window + 2])
        ratio = SequenceMatcher(None, quote_norm, chunk).ratio()
        best = max(best, ratio)
    if not words:
        return 0.0
    return best


def verify_finding(finding: dict, doc: ScriptDocument) -> dict:
    """
    Mutates and returns the finding dict with a `verification` block:
      {status: "verified" | "not_found" | "no_quote" | "scene_not_found",
       matched_scene: int | null, confidence: float}
    """
    quote = finding.get("evidence_quote")
    scene_refs = finding.get("scene_refs") or []

    if not quote or not quote.strip():
        finding["verification"] = {"status": "no_quote", "matched_scene": None, "confidence": None}
        return finding

    quote_norm = _normalize(quote)
    if len(quote_norm.split()) < 3:
        # too short to meaningfully verify (also too short to be useful evidence)
        finding["verification"] = {"status": "no_quote", "matched_scene": None, "confidence": None}
        return finding

    best_status = "not_found"
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


def verification_summary(findings: list[dict]) -> dict:
    counts = {"verified": 0, "not_found": 0, "no_quote": 0, "scene_not_found": 0}
    for f in findings:
        status = f.get("verification", {}).get("status", "no_quote")
        counts[status] = counts.get(status, 0) + 1
    return counts
