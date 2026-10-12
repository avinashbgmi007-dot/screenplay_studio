"""Local recall eval: golden facts vs a real-model report. Real model required;
never CI. Usage: python tests/eval_recall.py <project-dir> <golden-json>

A fact hits when ANY of its anchors matches ANY finding's issue +
observation + evidence_quote. Matching is lexical only: exact substring
first, token-overlap (>= 0.5, the same floor the verifier uses) second, so
a golden worded differently from the report still hits when it shares
content words. This still understates recall — a correct finding phrased
with none of the golden's words scores a MISS (trial 5: the sc16
silence note exists, the "silence" keyword does not). Do not gate trials
on this number; goldens should list each fact's acceptable surface forms.
"""
import json
import re
import sys

TOKEN_OVERLAP_FLOOR = 0.5


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(text or "").lower())).strip()


def _tokens(text: str) -> set:
    return set(_norm(text).split())


def _overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


# Minimal stopwords for the overlap fallback (inline: this script must stay
# import-free — run as `python tests/eval_recall.py`, it cannot see the
# analyzer packages). Without these, glue words carry false hits (trial 9:
# "money within the parcel" hit on {"the", "within"}).
_OVERLAP_STOPWORDS = frozenset({
    "the", "and", "with", "from", "that", "this", "for", "are", "was",
    "were", "has", "have", "had", "but", "not", "you", "your", "his",
    "her", "its", "our", "their", "she", "him", "them", "they", "who",
    "what", "when", "into", "over", "such", "than", "then", "there",
})


def _content_tokens(text: str) -> set:
    """Anchor tokens that carry meaning: alphabetic, longer than 2 chars,
    not glue words. Without this floor the overlap fallback fires on scraps — trial 9: the
    anchor "3 mints" hit a report containing no "mints" anywhere, on the
    token "3" alone."""
    return {w for w in _norm(text).split()
            if w.isalpha() and len(w) > 2 and w not in _OVERLAP_STOPWORDS}


def _anchor_hit(anchor: str, texts: list[str]) -> tuple[bool, str]:
    """(hit, method) — "exact" for substring, "overlap" for shared content
    words at the floor, else (False, ""). Overlap needs at least two
    content tokens in the anchor; anything shorter is exact-only."""
    anem = _norm(anchor)
    if not anem:
        return False, ""
    for t in texts:
        if anem in t:
            return True, "exact"
    atok = _content_tokens(anchor)
    if len(atok) < 2:
        return False, ""
    for t in texts:
        if _overlap(atok, _content_tokens(t)) >= TOKEN_OVERLAP_FLOOR:
            return True, "overlap"
    return False, ""


def _search_texts(report: dict) -> list[str]:
    """Finding prose plus the twist channel: a confirmed twist reaches the
    writer through twist_verdict/reveal_candidates, not through a finding
    (trial 8: no finding says "dream", the verdict does) — recall that
    ignores it measures wording luck, not what the report delivers."""
    texts = [_norm(f"{f.get('issue', '')} {f.get('observation', '')} {f.get('evidence_quote', '')}")
             for f in report.get("findings", [])]
    tv = report.get("twist_verdict") or {}
    if isinstance(tv, dict):
        texts.append(_norm(f"{tv.get('kind', '')} {tv.get('line', '')}"))
        if tv.get("twist"):
            texts.append("twist confirmed")
    for c in report.get("reveal_candidates") or []:
        if isinstance(c, dict):
            texts.append(_norm(str(c.get("line", ""))))
        else:
            texts.append(_norm(str(c)))
    return texts


def hit_rate(report_path, golden_path):
    report = json.load(open(report_path, encoding="utf-8"))
    goldens = json.load(open(golden_path, encoding="utf-8"))
    texts = _search_texts(report)
    rows = []
    for fact in goldens["facts"]:
        hit = False
        for a in fact["anchors"]:
            hit, _ = _anchor_hit(a, texts)
            if hit:
                break
        rows.append((fact["id"], hit))
    return rows


def _selftest():
    import os
    import tempfile
    tmp = tempfile.mkdtemp()
    rep = os.path.join(tmp, "report.findings.json")
    json.dump({"findings": [
        {"issue": "The countdown pays at 00:00.", "observation": "", "evidence_quote": ""},
        {"issue": "The clock keeps ticking loudly.", "observation": "", "evidence_quote": ""},
    ],
        "twist_verdict": {"twist": True, "kind": "dream", "line": "He wakes up."}}, open(rep, "w", encoding="utf-8"))
    gold = os.path.join(tmp, "gold.json")
    json.dump({"facts": [{"id": "a", "anchors": ["00:00"]},
                         {"id": "b", "anchors": ["never-mentioned-xyz"]},
                         {"id": "c", "anchors": ["ticking clock"]},
                         {"id": "d", "anchors": ["dream"]}]},
              open(gold, "w", encoding="utf-8"))
    rows = hit_rate(rep, gold)
    assert rows == [("a", True), ("b", False), ("c", True), ("d", True)], rows
    print("selftest OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        _selftest()
        sys.exit(0)
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        print("Usage: python tests/eval_recall.py <project-dir> <golden-json>", file=sys.stderr)
        sys.exit(2)
    report = json.load(open(sys.argv[1] + "/report.findings.json", encoding="utf-8"))
    goldens = json.load(open(sys.argv[2], encoding="utf-8"))
    texts = _search_texts(report)
    hits = 0
    for fact in goldens["facts"]:
        matched = ""
        method = ""
        for a in fact["anchors"]:
            hit, method = _anchor_hit(a, texts)
            if hit:
                matched = a
                break
        if matched:
            hits += 1
            print(f"HIT  {fact['id']}  [{method}] {matched[:60]}")
        else:
            print(f"MISS {fact['id']}")
    print(f"{hits}/{len(goldens['facts'])} facts hit")
    sys.exit(0 if hits == len(goldens["facts"]) else 1)
