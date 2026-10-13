"""Deterministic reveal-mechanic scan (accuracy kit B).

Twist mechanics live in single action lines a summary drops ("it was a
dream"). This scan finds candidate lines so script-level passes can account
for them. Lexical only — no model call, never fails a run.
"""

from __future__ import annotations

import re

REVEAL_PATTERNS = [
    re.compile(r"\bit was (all )?a dream\b", re.I),
    re.compile(r"\bdreamt\b|\bdreaming\b", re.I),
    re.compile(r"\bwok[ee] (up )?to\b.{0,20}\bdream", re.I),
    re.compile(r"\bkalaa\b", re.I),
    re.compile(r"\bjust a dream\b|\bonly a dream\b", re.I),
    re.compile(r"\bdead .{0,20}\balive\b", re.I),
]


def scan_reveals(doc) -> list:
    """Return [{scene, line, match}] for reveal-candidate lines, in order."""
    found = []
    for s in doc.scenes or []:
        for e in s.elements or []:
            text = getattr(e, "text", None) or (e.get("text") if isinstance(e, dict) else "")
            if not text:
                continue
            for p in REVEAL_PATTERNS:
                m = p.search(str(text))
                if m:
                    found.append({"scene": s.scene_number, "line": str(text)[:160],
                                  "match": m.group(0)})
                    break
    return found


def reveal_context_block(candidates: list) -> str:
    if not candidates:
        return ""
    lines = ["Candidate story mechanics (deterministic scan — verify against the text,",
             "do not assume; if a finding contradicts one, the finding is suspect):"]
    for c in candidates:
        lines.append(f"- Scene {c['scene']}: '{c['line']}'")
    return "\n".join(lines)


def confirmed_twist_block(verdict: dict | None) -> str:
    """Confirmed-twist context: stronger than candidates (a direct probe
    answered), so it replaces — never stacks with — the candidate block."""
    if not isinstance(verdict, dict) or verdict.get("twist") is not True:
        return ""
    return ("\n".join([
        "CONFIRMED story mechanic (probed directly — treat as established",
        "unless the text before you contradicts it):",
        f"- Scene {verdict.get('scene')}: '{verdict.get('line', '')}' "
        f"({verdict.get('kind', 'twist')}).",
        "Findings that treat these events as literal waking-plot are suspect.",
    ]))


TWIST_PROMPT = (
    "You are checking a short screenplay for reality-twist mechanics.\n"
    "Reply with ONLY this JSON object, no other text: "
    '{"twist": true/false, "scene": N or null, '
    '"line": "verbatim line or empty", "kind": "dream/hallucination/flashback/none"}.\n'
    "A twist exists ONLY if the text states or clearly implies part of the "
    "story was unreal. Do NOT infer one from theme."
)

TWIST_TEXT_BUDGET = 9000


def _full_text(doc, budget: int = TWIST_TEXT_BUDGET) -> str:
    parts = []
    for s in doc.scenes or []:
        for e in s.elements or []:
            text = getattr(e, "text", None) or (e.get("text") if isinstance(e, dict) else "")
            if text:
                parts.append(str(text))
    return "\n".join(parts)[:budget]


def parse_twist_verdict(reply) -> dict | None:
    """A confirmed twist dict, else None. Accepts a parsed object or raw
    text (first {...} block). Negatives, missing keys, and garbage all
    yield None — an unconfirmed twist changes nothing downstream."""
    import json
    import re
    data = None
    if isinstance(reply, dict):
        data = reply
    elif isinstance(reply, str):
        m = re.search(r"\{[^{}]*\}", reply, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except (ValueError, TypeError):
                return None
    if not isinstance(data, dict):
        return None
    if data.get("twist") is not True:
        return None
    # Scene may be null: the model confirmed the mechanic but hedged on
    # location (measured 7/8 live probes). The caller already drops
    # out-of-range ints to None, so accepting null here changes nothing
    # downstream — it only stops destroying true confirmations. The
    # semantic bar (twist:true + known kind + non-empty line) is unchanged.
    if data.get("scene") is not None and not isinstance(data.get("scene"), int):
        return None
    if not data.get("line"):
        return None
    if data.get("kind") not in ("dream", "hallucination", "flashback"):
        return None
    return {"twist": True, "scene": data["scene"],
            "line": str(data["line"])[:200], "kind": data["kind"]}


def confirm_twist(doc, client, system_prompt: str = TWIST_PROMPT) -> dict | None:
    """One candidate-gated model call answering whether the script contains
    a reality twist. None unless confirmed — negatives, parse failures, and
    model errors all leave the run exactly as it was. A cited scene number
    outside the script is dropped to None (the detection stands; the false
    precision does not — trial acceptance caught scene 4 of 3)."""
    if not scan_reveals(doc):
        return None
    text = _full_text(doc)
    if not text.strip():
        return None
    try:
        reply = client.chat_json(system_prompt, text,
                                 max_tokens=800, temperature=0.2)
    except Exception:
        return None
    verdict = parse_twist_verdict(reply)
    if verdict is None:
        return None
    real = {s.scene_number for s in doc.scenes or []}
    if verdict.get("scene") not in real:
        verdict["scene"] = None
    return verdict
