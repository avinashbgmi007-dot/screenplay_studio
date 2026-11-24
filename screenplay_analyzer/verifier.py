"""Conservative evidence verification for model-generated screenplay claims."""

from screenplay_parser.models import ScriptDocument
from screenplay_parser.quotematch import (
    find_scene_text as _scene_full_text,
    normalize_text as _normalize,
    windowed_similarity as _best_fuzzy_match,
)

FUZZY_MATCH_THRESHOLD = 0.72


def _normalize_scene_refs(scene_refs):
    """Normalize only clear numeric scene citations; report malformed refs."""
    if scene_refs is None:
        return [], []
    values = scene_refs if isinstance(scene_refs, (list, tuple)) else [scene_refs]
    normalized, invalid = [], []
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            normalized.append(value)
            continue
        if isinstance(value, str):
            raw = value.strip()
            if raw.isdecimal() and int(raw) > 0:
                normalized.append(int(raw))
                continue
            prefix = "scene "
            if raw[:len(prefix)].casefold() == prefix and raw[len(prefix):].strip().isdecimal():
                number = int(raw[len(prefix):].strip())
                if number > 0:
                    normalized.append(number)
                    continue
        invalid.append(value)
    return list(dict.fromkeys(normalized)), invalid


def _invalid_ref_result(finding, invalid_scene_refs):
    finding["verification"] = {
        "status": "invalid_scene_ref",
        "matched_scene": None,
        "confidence": None,
        "note": f"Malformed scene reference(s) were not normalized: {invalid_scene_refs!r}.",
    }
    return finding


def verify_finding(finding: dict, doc: ScriptDocument) -> dict:
    """Attach quote and scene-citation verification to a finding."""
    quote = finding.get("evidence_quote")
    raw_scene_refs = finding.get("scene_refs") or []
    scene_refs, invalid_scene_refs = _normalize_scene_refs(raw_scene_refs)
    if invalid_scene_refs:
        return _invalid_ref_result(finding, invalid_scene_refs)

    def quoteless():
        if scene_refs:
            existing = {s.scene_number for s in doc.scenes}
            if all(scene_num not in existing for scene_num in scene_refs):
                finding["verification"] = {
                    "status": "scene_not_found", "matched_scene": None,
                    "confidence": None,
                }
                return finding
        finding["verification"] = {
            "status": "no_quote", "matched_scene": None, "confidence": None,
        }
        return finding

    if not quote or not quote.strip():
        return quoteless()
    quote_norm = _normalize(quote)
    if len(quote_norm.split()) < 3:
        return quoteless()

    best_scene, best_conf = None, 0.0
    for scene_num in scene_refs:
        scene_text = _scene_full_text(doc, scene_num)
        if scene_text is None:
            continue
        scene_norm = _normalize(scene_text)
        if quote_norm in scene_norm:
            finding["verification"] = {
                "status": "verified", "matched_scene": scene_num,
                "confidence": 1.0,
            }
            return finding
        ratio = _best_fuzzy_match(quote_norm, scene_norm)
        if ratio > best_conf:
            best_conf, best_scene = ratio, scene_num

    if scene_refs and all(_scene_full_text(doc, n) is None for n in scene_refs):
        finding["verification"] = {
            "status": "scene_not_found", "matched_scene": None,
            "confidence": None,
        }
        return finding
    if best_conf >= FUZZY_MATCH_THRESHOLD:
        finding["verification"] = {
            "status": "verified", "matched_scene": best_scene,
            "confidence": round(best_conf, 2),
        }
        return finding

    # A real quote under a different scene number is corrected visibly.
    for scene in doc.scenes:
        scene_norm = _normalize(" ".join(e.text for e in scene.elements))
        if quote_norm in scene_norm:
            finding["verification"] = {
                "status": "verified", "matched_scene": scene.scene_number,
                "confidence": 1.0,
                "note": f"Quote found in Scene {scene.scene_number}, not the cited scene(s) {scene_refs} — corrected.",
            }
            return finding
    finding["verification"] = {
        "status": "not_found", "matched_scene": None,
        "confidence": round(best_conf, 2),
    }
    return finding


def verify_findings(findings: list[dict], doc: ScriptDocument) -> list[dict]:
    return [verify_finding(f, doc) for f in findings]


def _norm_name(text: str) -> str:
    return " ".join(str(text or "").upper().replace("_", " ").split())


def _quoted_fragments(text: str) -> list[str]:
    """Extract simple single- or double-quoted spans without altering the text."""
    fragments = []
    start = None
    delimiter = None
    for index, char in enumerate(text):
        if delimiter is None and char in ("'", '"'):
            if char == "'" and index > 0 and text[index - 1].isalnum():
                continue
            delimiter, start = char, index + 1
        elif delimiter == char:
            if char == "'" and index + 1 < len(text) and text[index + 1].isalnum():
                continue
            fragments.append(text[start:index])
            delimiter, start = None, None
    return fragments


def verify_observation(finding: dict, doc) -> bool | None:
    """Check whether an observation is supported by its cited scene text.

    Returns True (supported), False (contradicted), or None (not checkable).
    Malformed and missing scene citations are never converted into support.
    """
    if not isinstance(finding, dict):
        return None
    observation = finding.get("observation") or ""
    if not observation.strip():
        return None
    scene_refs, invalid_scene_refs = _normalize_scene_refs(finding.get("scene_refs") or [])
    if invalid_scene_refs or not scene_refs:
        return None
    cited = [s for s in (doc.scenes or [])
             if getattr(s, "scene_number", None) in scene_refs]
    if not cited:
        return None

    cited_tokens = []
    for scene in cited:
        text = _scene_full_text(doc, scene.scene_number) or ""
        cited_tokens.append(set(_normalize(text).split()))
    known = {_norm_name(name) for name in (getattr(doc, "all_characters", None) or [])}
    obs_tokens = set(_normalize(observation).split())
    for name in known:
        name_tokens = set(_normalize(name).split())
        if name_tokens and name_tokens <= obs_tokens:
            if not any(name_tokens <= tokens for tokens in cited_tokens):
                return False

    for fragment in _quoted_fragments(observation):
        if len(fragment.split()) < 3:
            continue
        frag_norm = _normalize(fragment)
        supported = any(
            _best_fuzzy_match(frag_norm, _normalize(_scene_full_text(doc, s.scene_number) or ""))
            >= FUZZY_MATCH_THRESHOLD
            for s in cited
        )
        if not supported:
            supported = any(
                _token_overlap(frag_norm, _normalize(_scene_full_text(doc, s.scene_number) or ""))
                >= 0.5
                for s in cited
            )
        if not supported:
            whole = _normalize(" ".join(
                _scene_full_text(doc, scene.scene_number) or "" for scene in doc.scenes or []))
            if (_best_fuzzy_match(frag_norm, whole) < FUZZY_MATCH_THRESHOLD
                    and _token_overlap(frag_norm, whole) < 0.5):
                return False
    return True


_STOPWORDS = frozenset(
    "is are was were be been being the a an of to in on and or very so as at "
    "by for with from that this it its it s".split())


def _token_overlap(frag_norm: str, haystack_norm: str) -> float:
    """Share of fragment content words present in the comparison text."""
    words = [word for word in frag_norm.split() if word not in _STOPWORDS]
    if not words:
        return 0.0
    hay = set(haystack_norm.split())
    return sum(1 for word in words if word in hay) / len(words)


def verification_summary(findings: list[dict]) -> dict:
    counts = {"verified": 0, "not_found": 0, "no_quote": 0,
              "scene_not_found": 0, "invalid_scene_ref": 0}
    for finding in findings:
        status = finding.get("verification", {}).get("status", "no_quote")
        counts[status] = counts.get(status, 0) + 1
    return counts


def verification_rate(counts: dict) -> dict:
    """Return the verifiable-quote percentage, excluding uncheckable findings."""
    counts = counts or {}
    quote_bearing = counts.get("verified", 0) + counts.get("not_found", 0)
    return {
        "quote_bearing": quote_bearing,
        "verified_pct_of_quoted": (
            round(100.0 * counts.get("verified", 0) / quote_bearing, 1)
            if quote_bearing else None),
    }
