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


def _paragraph_text(paragraph_el: ET.Element) -> str:
    """Concatenate all <Text> runs inside a <Paragraph> (FDX splits styled text into runs)."""
    parts = []
    for text_el in paragraph_el.findall("Text"):
        if text_el.text:
            parts.append(text_el.text)
    return "".join(parts).strip()


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
        text = _paragraph_text(paragraph_el)
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
            current_scene.elements.append(Element(type=etype, text=text))
            doc.scenes.append(current_scene)
            pending_character = None
            continue

        target = current_scene
        if target is None:
            # content before the first scene heading (rare, but handle gracefully)
            doc.front_matter.append(Element(type=etype, text=text))
            continue

        if etype == ElementType.CHARACTER:
            pending_character = normalize_character_name(text)
            target.elements.append(Element(type=etype, text=text, character=pending_character))
            if pending_character and pending_character not in target.characters_present:
                target.characters_present.append(pending_character)
        elif etype in (ElementType.DIALOGUE, ElementType.PARENTHETICAL):
            target.elements.append(Element(type=etype, text=text, character=pending_character))
        else:
            target.elements.append(Element(type=etype, text=text))
            if etype != ElementType.ACTION:
                pending_character = None

    for scene in doc.scenes:
        scene.characters_present.sort()

    if not doc.scenes:
        doc.warnings.append(ParseWarning(message="No scenes detected — file may be empty or use a non-standard structure.", severity="error"))
        doc.parse_confidence = "low"

    return doc
