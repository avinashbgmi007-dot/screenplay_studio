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
    lines = [
        "Possible story-mechanic cues (deterministic text scan only, not a judgment):",
        "Keep these as leads. They may be literal, metaphorical, ordinary dreams, or "
        "something else; do not dismiss a finding or another reading because of a cue.",
    ]
    for c in candidates:
        lines.append(f"- Scene {c['scene']}: '{c['line']}'")
    return "\n".join(lines)


def confirmed_twist_block(verdict: dict | None) -> str:
    """Compatibility name: render a model reading as provisional, never as fact.

    It deliberately does not replace the independent deterministic candidate
    block; downstream readers need both the cue and the alternative reading.
    """
    if not isinstance(verdict, dict) or verdict.get("twist") is not True:
        return ""
    coverage = verdict.get("coverage")
    if isinstance(coverage, dict):
        sent = coverage.get("characters_sent")
        total = coverage.get("script_characters")
        if coverage.get("scope") == "full_script":
            coverage_line = f"Probe coverage: full screenplay ({sent} characters provided)."
        else:
            coverage_line = (f"Probe coverage: only the first {sent} of {total} screenplay "
                             "characters; later text was not assessed.")
    else:
        coverage_line = "Probe coverage was not recorded; later text may be unassessed."
    scene = verdict.get("scene")
    location = f"Scene {scene}" if scene is not None else "scene location uncertain"
    return "\n".join([
        "Model-suggested reality-twist reading (not an established fact):",
        f"- {location}: '{verdict.get('line', '')}' "
        f"({verdict.get('kind', 'twist')}).",
        coverage_line,
        "Treat this as a question for the writer. Keep other readings and contrary "
        "findings live; the quotation does not prove what the story means.",
    ])


TWIST_PROMPT = (
    "You are offering one possible reading of a screenplay passage, not deciding "
    "what is factually true in the story.\n"
    "Reply with ONLY this JSON object, no other text: "
    '{"twist": true/false, "scene": N or null, '
    '"line": "exact verbatim text from the provided screenplay or empty", '
    '"kind": "dream/hallucination/flashback/none"}.\n'
    "A true value means only that a reality-twist reading seems plausible, not "
    "that it is established. An ordinary character dream, metaphor, hypothetical, "
    "unreliable memory, deliberate ambiguity, or the writer's explanation may "
    "support another reading. Cite exact text you actually see; if unsure, return "
    "false. Never tell later passes to distrust contrary findings."
)

TWIST_TEXT_BUDGET = 9000


def _scene_texts(doc) -> list[tuple[int | None, str]]:
    scenes = []
    for scene in doc.scenes or []:
        parts = []
        for element in scene.elements or []:
            text = getattr(element, "text", None) or (
                element.get("text") if isinstance(element, dict) else "")
            if text:
                parts.append(str(text))
        if parts:
            scenes.append((scene.scene_number, "\n".join(parts)))
    return scenes


def _prompt_text(doc, budget: int = TWIST_TEXT_BUDGET):
    """Return the sent prefix, its coverage, and which scene text it includes."""
    scenes = _scene_texts(doc)
    full_text = "\n".join(text for _, text in scenes)
    prompt_text = full_text[:budget]
    included = []
    cursor = 0
    for index, (scene_number, scene_text) in enumerate(scenes):
        if index:
            cursor += 1  # the newline between scenes in `full_text`
        if cursor >= len(prompt_text):
            break
        visible = prompt_text[cursor:cursor + len(scene_text)]
        if visible:
            included.append((scene_number, visible))
        cursor += len(scene_text)
    return prompt_text, len(full_text), included


def _full_text(doc, budget: int = TWIST_TEXT_BUDGET) -> str:
    """Compatibility helper retained for tests and callers of this private API."""
    return _prompt_text(doc, budget)[0]


def _exact_quote_scene(line: str, included_scenes: list[tuple[int | None, str]],
                       scene_hint: int | None = None):
    """Find the exact quote among the text actually sent to the probe."""
    needle = " ".join(str(line or "").split())
    if not needle:
        return None, False
    matched = {
        scene_number for scene_number, text in included_scenes
        if needle in " ".join(text.split())
    }
    if not matched:
        return None, False
    if len(matched) == 1:
        return next(iter(matched)), True
    # Keep the model's location only when the exact quotation verifies there.
    if scene_hint in matched:
        return scene_hint, True
    return None, True


def _citation_has_reveal_support(line: str, scene: int | None,
                                 candidates: list[dict],
                                 included_scenes: list[tuple[int | None, str]]) -> bool:
    """Require a textual link to a scan candidate or an explicit cue.

    Exact-source verification alone would still let an unrelated, real line
    become the basis of a dream/twist reading. This is a conservative relevance
    check, not proof that the words mean the story is unreal.
    """
    citation = " ".join(str(line or "").split()).casefold()
    for candidate in candidates:
        candidate_scene = candidate.get("scene")
        if scene is not None and candidate_scene != scene:
            continue
        visible_text = next((text for number, text in included_scenes
                             if number == candidate_scene), "")
        visible_norm = " ".join(visible_text.split()).casefold()
        candidate_line = " ".join(str(candidate.get("line", "")).split()).casefold()
        if (candidate_line and candidate_line in visible_norm
                and (citation in candidate_line or candidate_line in citation)):
            return True
    if any(pattern.search(line or "") for pattern in REVEAL_PATTERNS):
        return True
    return bool(re.search(r"\bwake[sd]?\b|\bwaking\b|\bwoke\b", line or "", re.I))


def parse_twist_verdict(reply) -> dict | None:
    """Parse a positive model reading; this alone does not ground or prove it.

    Accepts a parsed object or raw text (first {...} block). Negatives, missing
    keys, and garbage yield None. `confirm_twist` separately verifies the exact
    citation in the text that was actually sent to the model.
    """
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
    # Scene may be null; the caller derives location from the exact quote
    # rather than trusting this model-supplied number.
    if data.get("scene") is not None and (
            not isinstance(data.get("scene"), int) or isinstance(data.get("scene"), bool)):
        return None
    line = data.get("line")
    if not isinstance(line, str) or not line.strip() or len(line) > 200:
        return None
    if data.get("kind") not in ("dream", "hallucination", "flashback"):
        return None
    return {"twist": True, "scene": data["scene"],
            "line": line, "kind": data["kind"]}


def confirm_twist(doc, client, system_prompt: str = TWIST_PROMPT) -> dict | None:
    """Return a grounded model interpretation, never a confirmed story fact.

    The exact quote must occur in the actual text sent to the probe. A bad or
    absent citation drops this interpretation; it is never replaced with a
    different deterministic candidate. `coverage` distinguishes full-script
    input from the bounded prefix, and `scene` is derived from the cited text,
    not trusted from the model's scene number.
    """
    candidates = scan_reveals(doc)
    if not candidates:
        return None
    text, full_length, included_scenes = _prompt_text(doc)
    if not text.strip():
        return None
    coverage = {
        "scope": "full_script" if len(text) == full_length else "prefix",
        "characters_sent": len(text),
        "script_characters": full_length,
    }
    scope_note = (
        "The full screenplay is provided below."
        if coverage["scope"] == "full_script"
        else (f"Only the first {len(text)} of {full_length} screenplay characters "
              "are provided; later text has not been assessed.")
    )
    try:
        reply = client.chat_json(system_prompt, f"{scope_note}\n\n{text}",
                                 max_tokens=800, temperature=0.2)
    except Exception:
        return None
    interpretation = parse_twist_verdict(reply)
    if interpretation is None:
        return None
    scene, grounded = _exact_quote_scene(
        interpretation["line"], included_scenes, interpretation.get("scene"))
    if not grounded or not _citation_has_reveal_support(
            interpretation["line"], scene, candidates, included_scenes):
        return None
    return {
        **interpretation,
        "scene": scene,
        "status": "interpretation",
        "coverage": coverage,
    }
