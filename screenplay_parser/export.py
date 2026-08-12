"""
Deterministic screenplay export — the return half of the writer's loop.

Parsing turns .fdx/.fountain/.txt/.pdf into the structured ScriptDocument;
export turns the ScriptDocument (possibly after revision edits) back into
a screenplay the writer can open in Final Draft / Highland / WriterSolo.
No model dependency, same design rule as the rest of Piece 1.

Supported targets:
    fountain — plain-text Fountain (title page + blank-line-delimited blocks)
    fdx      — Final Draft XML (paragraph types map 1:1 onto our ElementType)
    txt      — plain screenplay text (same layout as Fountain, no forced syntax)

Round-trip: for .fdx the mapping is exact (type tags are preserved). For
text formats the state machine reclassifies on re-parse, so a handful of
heuristic-dependent edge cases (e.g. action text that reads like a
character cue) are the documented lossy boundary.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .models import ElementType, ScriptDocument

# Reverse of screenplay_parser.fdx_parser.FDX_TYPE_MAP
FDX_TYPE_NAMES = {
    ElementType.SCENE_HEADING: "Scene Heading",
    ElementType.ACTION: "Action",
    ElementType.CHARACTER: "Character",
    ElementType.DIALOGUE: "Dialogue",
    ElementType.PARENTHETICAL: "Parenthetical",
    ElementType.TRANSITION: "Transition",
    ElementType.SHOT: "Shot",
    ElementType.GENERAL: "General",
}

SUPPORTED_FORMATS = ("fountain", "fdx", "txt")


_DIALOGUE_BLOCK_TYPES = frozenset((
    ElementType.CHARACTER, ElementType.PARENTHETICAL, ElementType.DIALOGUE,
))


def _append_blank_after(out: list[str], elements: list, i: int) -> None:
    """A blank line closes the current block. Dialogue blocks (character cue ->
    parentheticals -> dialogue lines) stay glued together; every other element
    is followed by a blank. Emitting a blank inside a dialogue block would make
    the re-parse classify the dialogue line as action."""
    el = elements[i]
    if el.type in _DIALOGUE_BLOCK_TYPES:
        nxt = elements[i + 1].type if i + 1 < len(elements) else None
        if nxt in _DIALOGUE_BLOCK_TYPES:
            return  # continuation of the same dialogue block
    out.append("")


def _title_page_lines(doc: ScriptDocument) -> list[str]:
    """Title-page key/value pairs for text formats (Fountain convention)."""
    lines = []
    if doc.title:
        lines.append(f"Title: {doc.title}")
    if doc.author:
        lines.append(f"Author: {doc.author}")
    if lines:
        lines.append("")
    return lines


def to_fountain(doc: ScriptDocument) -> str:
    """
    Fountain export. Layout conventions (blank-line-delimited blocks, forced
    '>' for transitions) match what the parser's state machine expects, so
    re-parsing the export reproduces the same structure on the happy path.
    """
    out: list[str] = []
    out.extend(_title_page_lines(doc))

    for el in doc.front_matter:
        if el.text:
            out.append(el.text)
            out.append("")
    if doc.front_matter:
        out.append("")

    for scene in doc.scenes:
        out.append(scene.heading_raw)
        out.append("")
        elements = scene.elements
        for i, el in enumerate(elements):
            if not el.text:
                continue
            if el.type == ElementType.SCENE_HEADING:
                continue  # heading already emitted
            if el.type == ElementType.CHARACTER:
                out.append(el.text)
            elif el.type == ElementType.PARENTHETICAL:
                out.append(f"({el.text})" if not el.text.startswith("(") else el.text)
            elif el.type == ElementType.TRANSITION:
                out.append(f"> {el.text}")
            else:
                out.append(el.text)
            _append_blank_after(out, elements, i)

    return "\n".join(out).rstrip() + "\n"


def to_txt(doc: ScriptDocument) -> str:
    """Plain-text export — same layout as Fountain without forced syntax."""
    out: list[str] = []
    out.extend(_title_page_lines(doc))
    for el in doc.front_matter:
        if el.text:
            out.append(el.text)
            out.append("")
    if doc.front_matter:
        out.append("")

    for scene in doc.scenes:
        out.append(scene.heading_raw)
        out.append("")
        elements = scene.elements
        for i, el in enumerate(elements):
            if not el.text or el.type == ElementType.SCENE_HEADING:
                continue
            if el.type == ElementType.PARENTHETICAL:
                out.append(f"({el.text})" if not el.text.startswith("(") else el.text)
            else:
                out.append(el.text)
            _append_blank_after(out, elements, i)

    return "\n".join(out).rstrip() + "\n"


def to_fdx(doc: ScriptDocument) -> str:
    """
    Final Draft XML export. Paragraph types map 1:1 onto the parser's
    ElementType, so an fdx -> parse -> export -> parse round trip is exact.
    """
    root = ET.Element("FinalDraft", DocumentType="Script", Template="No", Version="1")

    # TitlePage mirrors what the .fdx parser reads back (first paragraph = title,
    # a 'by <name>' line = author), so title/author survive the round trip.
    if doc.title or doc.author:
        title_page = ET.SubElement(root, "TitlePage")
        if doc.title:
            tp_p = ET.SubElement(title_page, "Paragraph", Type="General")
            tp_text = ET.SubElement(tp_p, "Text")
            tp_text.text = doc.title
        if doc.author:
            tp_p = ET.SubElement(title_page, "Paragraph", Type="General")
            tp_text = ET.SubElement(tp_p, "Text")
            tp_text.text = f"by {doc.author}"

    content = ET.SubElement(root, "Content")

    def add_paragraph(etype: ElementType, text: str, number: str | None = None):
        p = ET.SubElement(content, "Paragraph", Type=FDX_TYPE_NAMES.get(etype, "General"))
        if number:
            p.set("Number", number)
        text_el = ET.SubElement(p, "Text")
        text_el.text = text

    for el in doc.front_matter:
        if el.text:
            add_paragraph(el.type, el.text)

    for scene in doc.scenes:
        add_paragraph(ElementType.SCENE_HEADING, scene.heading_raw, str(scene.scene_number))
        for el in scene.elements:
            if el.type == ElementType.SCENE_HEADING:
                continue  # heading already emitted
            if el.text:
                add_paragraph(el.type, el.text)

    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return body.decode("utf-8")


def export(doc: ScriptDocument, fmt: str) -> str:
    """Dispatch: 'fountain' | 'fdx' | 'txt' -> text content of the export."""
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported export format '{fmt}'. Supported: {list(SUPPORTED_FORMATS)}")
    if fmt == "fountain":
        return to_fountain(doc)
    if fmt == "fdx":
        return to_fdx(doc)
    return to_txt(doc)


def export_to_path(doc: ScriptDocument, fmt: str, path: str) -> str:
    """Export and write to disk. Returns the export text."""
    text = export(doc, fmt)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text
