"""
Parser for Final Draft (.fdx) files.

.fdx is XML with explicit <Paragraph Type="..."> tags, so this is the most
reliable source format — no heuristic guessing required. Paragraph types
map directly onto our ElementType enum.
"""

import os
import re
import xml.etree.ElementTree as ET

from .models import Element, ElementType, ParseWarning, Scene, ScriptDocument
from .heuristics import normalize_character_name, parse_scene_heading

FDX_TYPE_MAP = {
    "Scene Heading": ElementType.SCENE_HEADING,
    "Action": ElementType.ACTION,
    "Character": ElementType.CHARACTER,
    "Dialogue": ElementType.DIALOGUE,
    "Parenthetical": ElementType.PARENTHETICAL,
    "Transition": ElementType.TRANSITION,
    "Shot": ElementType.SHOT,
    "General": ElementType.GENERAL,
}


def _split_styles(value: str | None) -> list[str]:
    """`Style` attribute -> style names. Final Draft composes with '+'
    ("Bold+Italic"); anything unrecognised is kept verbatim rather than dropped,
    so a style this build does not know about still makes the round trip."""
    if not value:
        return []
    return [part.strip() for part in value.split("+") if part.strip()]


def _paragraph_runs(paragraph_el: ET.Element) -> tuple[str, list[dict]]:
    """The paragraph's text and its emphasis, as (text, spans).

    Gap 22. This used to concatenate the runs and discard every `Style`
    attribute, so emphasis was destroyed at PARSE — before the model or the
    exporter could lose it. FDX carries emphasis natively (one styled `<Text>`
    run per stretch), so there was nothing in the format to blame.

    Offsets are computed against the concatenation and then SHIFTED by whatever
    `strip()` removes, because the returned text is the stripped one. Computed
    without the shift they point at the wrong characters, which shows up as
    emphasis landing a word early — a bug that looks like a parsing quirk rather
    than an off-by-N.
    """
    parts: list[tuple[str, list[str]]] = []
    for text_el in paragraph_el.findall("Text"):
        chunk = text_el.text or ""
        if chunk:
            parts.append((chunk, _split_styles(text_el.get("Style"))))

    joined = "".join(chunk for chunk, _ in parts)
    lead = len(joined) - len(joined.lstrip())
    text = joined.strip()

    spans: list[dict] = []
    cursor = 0
    for chunk, styles in parts:
        start, end = cursor, cursor + len(chunk)
        cursor = end
        if not styles:
            continue
        # shift into stripped coordinates and clamp to the kept range
        a = max(0, start - lead)
        b = min(len(text), end - lead)
        if b > a:
            spans.append({"start": a, "end": b, "styles": styles})
    return text, spans


def _paragraph_text(paragraph_el: ET.Element) -> str:
    """The paragraph's text. Kept for callers that only need the words."""
    return _paragraph_runs(paragraph_el)[0]


def parse_fdx(path: str) -> ScriptDocument:
    filename = os.path.basename(path)
    tree = ET.parse(path)
    root = tree.getroot()

    title = None
    author = None

    title_page = root.find("TitlePage")
    if title_page is not None:
        collected = []
        for paragraph_el in title_page.iter("Paragraph"):
            t = _paragraph_text(paragraph_el)
            if t:
                collected.append(t)
        if collected:
            title = collected[0]
            # naive author guess: a line that starts with "by <name>" and isn't
            # just the bare "Written by" / "By" label itself.
            for line in collected[1:5]:
                stripped = line.strip()
                lower = stripped.lower()
                if lower in ("by", "written by", "screenplay by", "story by"):
                    continue
                m = re.match(r"^(?:written\s+)?by\s+(.+)$", stripped, re.IGNORECASE)
                if m and m.group(1).strip():
                    author = m.group(1).strip()
                    break

    doc = ScriptDocument(title=title, author=author, source_format="fdx", source_filename=filename)
    doc.parse_confidence = "high"

    content = root.find("Content")
    if content is None:
        doc.warnings.append(ParseWarning(message="No <Content> element found in .fdx file — is this a valid Final Draft file?", severity="error"))
        return doc

    current_scene: Scene | None = None
    scene_num = 0
    pending_character: str | None = None

    for paragraph_el in content.findall("Paragraph"):
        ptype = paragraph_el.get("Type", "General")
        etype = FDX_TYPE_MAP.get(ptype, ElementType.GENERAL)
        text, spans = _paragraph_runs(paragraph_el)
        if not text:
            continue

        if etype == ElementType.SCENE_HEADING:
            scene_num += 1
            parsed = parse_scene_heading(text)
            current_scene = Scene(
                scene_number=scene_num,
                heading_raw=text,
                int_ext=parsed["int_ext"],
                location=parsed["location"],
                time_of_day=parsed["time_of_day"],
            )
            current_scene.elements.append(Element(type=etype, text=text, spans=spans))
            doc.scenes.append(current_scene)
            pending_character = None
            continue

        target = current_scene
        if target is None:
            # content before the first scene heading (rare, but handle gracefully)
            doc.front_matter.append(Element(type=etype, text=text, spans=spans))
            continue

        if etype == ElementType.CHARACTER:
            pending_character = normalize_character_name(text)
            target.elements.append(Element(type=etype, text=text, character=pending_character, spans=spans))
            if pending_character and pending_character not in target.characters_present:
                target.characters_present.append(pending_character)
        elif etype in (ElementType.DIALOGUE, ElementType.PARENTHETICAL):
            target.elements.append(Element(type=etype, text=text, character=pending_character, spans=spans))
        else:
            target.elements.append(Element(type=etype, text=text, spans=spans))
            if etype != ElementType.ACTION:
                pending_character = None

    for scene in doc.scenes:
        scene.characters_present.sort()

    if not doc.scenes:
        doc.warnings.append(ParseWarning(message="No scenes detected — file may be empty or use a non-standard structure.", severity="error"))
        doc.parse_confidence = "low"

    return doc
