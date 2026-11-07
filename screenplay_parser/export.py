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

import json
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

# Gap 79: an export used to be indistinguishable from an original. A script
# reconstructed from a PDF parse went out looking exactly like the writer's own
# Fountain file, so a collaborator receiving it had no way to know the layout had
# been approximated, or which file it came from at all. The mark below travels
# WITH the artifact, because an artifact outlives the session that made it.
PROVENANCE_MARKER = "screenplay-studio-provenance"


def build_provenance(doc: ScriptDocument, extra: dict = None) -> dict:
    """What this artifact must say about its own origin.

    Everything here is read off the document — nothing is remembered or passed
    around by the caller — so the provenance cannot drift from the text it sits
    beside. `extra` may add facts only the caller knows (which project, when the
    parse ran); a None value means "not recorded" and is dropped rather than
    rendered as a blank.
    """
    src = (doc.source_format or "").strip().lower().lstrip(".")
    prov = {
        "generator": "screenplay-studio",
        "source_file": doc.source_filename or None,
        "source_format": src or None,
        # A PDF is never the writer's file — it is a reading of one. Saying
        # "reconstructed" is a factual claim about the parse, not a hedge.
        "reconstructed": src == "pdf",
        "parse_confidence": doc.parse_confidence,
        "parse_warnings": len(doc.warnings or []),
        "scenes": len(doc.scenes),
    }
    if extra:
        prov.update({k: v for k, v in extra.items() if v is not None})
    return prov


def provenance_sentence(prov: dict) -> str:
    """The human half. A machine-readable block nobody can read is not
    disclosure — it is a receipt filed in a drawer."""
    name = prov.get("source_file") or "an unrecorded file"
    ext = (prov.get("source_format") or "unknown").upper()
    if prov.get("reconstructed"):
        return (f"Reconstructed by screenplay-studio from a parse of {name} ({ext}). "
                f"This is not the writer's original file: layout, emphasis and page "
                f"breaks are approximations of what the parse could read.")
    conf = prov.get("parse_confidence") or "unrecorded"
    return (f"Exported by screenplay-studio from {name} ({ext}), parse confidence {conf}.")


def _resolve_provenance(doc: ScriptDocument, provenance):
    if provenance is False:
        return None
    return build_provenance(doc, provenance if isinstance(provenance, dict) else None)


_DIALOGUE_BLOCK_TYPES = frozenset((
    ElementType.CHARACTER, ElementType.PARENTHETICAL, ElementType.DIALOGUE,
))

# What may CONTINUE a dialogue block without a blank line in between: a
# parenthetical or more dialogue. A CHARACTER cue is deliberately NOT here —
# it always begins a NEW block, and gluing it onto the previous speaker's
# dialogue line is gap 21: "AJAY / Hello. / VENU / Hi." exported as
#
#     AJAY
#     Hello.
#     VENU
#     Hi.
#
# re-parses as ONE speech by AJAY, because without the separating blank the
# parser sees VENU and Hi. as further dialogue lines of the same block. Every
# line was then attributed to AJAY, which corrupts dialogue attribution on
# re-import. The blank is what marks the block boundary for a text parser, so
# it has to be emitted before every character cue.
_DIALOGUE_CONTINUATION = frozenset((
    ElementType.PARENTHETICAL, ElementType.DIALOGUE,
))


def _append_blank_after(out: list[str], elements: list, i: int) -> None:
    """A blank line closes the current block. Dialogue blocks (character cue ->
    parentheticals -> dialogue lines) stay glued together; a new character cue
    and every non-dialogue element are preceded by a blank. Emitting a blank
    inside a dialogue block would make the re-parse classify the dialogue line
    as action; omitting it before a new cue would make the re-parse attribute
    the next speaker's lines to the previous one (gap 21).

    The next element is found by SKIPPING text-less elements, because callers
    `continue` past those without emitting anything — judging by `elements[i+1]`
    regardless let an empty element in between suppress the blank and glue two
    speeches together again.
    """
    if elements[i].type in _DIALOGUE_BLOCK_TYPES:
        nxt = None
        for j in range(i + 1, len(elements)):
            if elements[j].text:
                nxt = elements[j].type
                break
        if nxt in _DIALOGUE_CONTINUATION:
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


def to_fountain(doc: ScriptDocument, provenance=None) -> str:
    """
    Fountain export. Layout conventions (blank-line-delimited blocks, forced
    '>' for transitions) match what the parser's state machine expects, so
    re-parsing the export reproduces the same structure on the happy path.
    """
    out: list[str] = []
    prov = _resolve_provenance(doc, provenance)
    if prov is not None:
        # Fountain's boneyard. `_strip_boneyard` removes it on re-import, so the
        # note is visible in the file a writer opens and invisible to the parser
        # that reads it back — disclosure without contamination.
        out.append("/* " + PROVENANCE_MARKER)
        out.append(provenance_sentence(prov))
        out.append(json.dumps(prov, ensure_ascii=False, sort_keys=True))
        out.append("*/")
        out.append("")
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


def to_txt(doc: ScriptDocument, provenance=None) -> str:
    """Plain-text export — same layout as Fountain without forced syntax.

    Gap 79 deliberate limit: no provenance block here, and the reason is
    narrower than it first looks. Measured: a boneyard-prepended .txt re-imports
    with the scene count unchanged (6 -> 6) and the marker nowhere in scene
    text — but all four note lines land in `front_matter` as ACTION elements.
    So it corrupts no structure; it prints four bogus action paragraphs at the
    top of the writer's screenplay. Refused on that basis, and `/export` reports
    `X-Provenance-Embedded: none` so the absence is stated, not assumed.
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
            if not el.text or el.type == ElementType.SCENE_HEADING:
                continue
            if el.type == ElementType.PARENTHETICAL:
                out.append(f"({el.text})" if not el.text.startswith("(") else el.text)
            else:
                out.append(el.text)
            _append_blank_after(out, elements, i)

    return "\n".join(out).rstrip() + "\n"


def _runs_for(text: str, spans) -> list[tuple[str, str | None]]:
    """Split `text` into (chunk, style_or_None) runs for FDX.

    Spans are half-open ranges of style names; overlapping spans compose, so a
    character covered by Bold and Italic is emitted as one `Bold+Italic` run.
    Adjacent runs with the same style are merged, which keeps a round trip
    stable (export -> parse -> export is identical rather than sprouting a new
    run on every save).

    Tolerant by design: a span past the end is clamped, an inverted span is
    ignored, and text with no spans returns one unstyled run. This is called
    while writing the writer's export, so corrupt emphasis must degrade to plain
    text rather than take the export down.
    """
    if not text:
        return []
    per_char: list[set[str]] = [set() for _ in text]
    for span in spans or []:
        try:
            start = max(0, int(span.get("start", 0)))
            end = min(len(text), int(span.get("end", 0)))
        except (TypeError, ValueError, AttributeError):
            continue
        styles = [str(st) for st in (span.get("styles") or []) if st]
        if end <= start or not styles:
            continue
        for i in range(start, end):
            per_char[i].update(styles)

    runs: list[tuple[str, str | None]] = []
    for ch, styles in zip(text, per_char):
        style = "+".join(sorted(styles)) if styles else None
        if runs and runs[-1][1] == style:
            runs[-1] = (runs[-1][0] + ch, style)
        else:
            runs.append((ch, style))
    return runs


def to_fdx(doc: ScriptDocument, provenance=None) -> str:
    """
    Final Draft XML export. Paragraph types map 1:1 onto the parser's
    ElementType, so an fdx -> parse -> export -> parse round trip is exact.
    """
    root = ET.Element("FinalDraft", DocumentType="Script", Template="No", Version="1")
    prov = _resolve_provenance(doc, provenance)
    if prov is not None:
        # An XML comment directly under <FinalDraft>. `parse_fdx` reads only
        # TitlePage and Content, and ElementTree discards comments by default,
        # so Final Draft and our own re-import both ignore it. A real <Element>
        # would risk the first, and a title-page paragraph would print the note
        # on the writer's page — both were rejected for that reason.
        root.insert(0, ET.Comment(
            f" {PROVENANCE_MARKER} {provenance_sentence(prov)} "
            f"{json.dumps(prov, ensure_ascii=False, sort_keys=True)} "))

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

    def add_paragraph(etype: ElementType, text: str, number: str | None = None,
                      spans=None):
        """One <Paragraph>, split into styled <Text> runs where emphasis exists.

        Gap 22. This used to write a single plain <Text>, so any emphasis the
        document carried was dropped on the way out — with the format blamed.
        FDX expects the split: a run per stretch, `Style="Bold+Italic"` where
        styles compose.

        Unstyled text still emits exactly one run with no Style attribute, so a
        document without emphasis exports byte-for-byte as it did before.
        """
        p = ET.SubElement(content, "Paragraph", Type=FDX_TYPE_NAMES.get(etype, "General"))
        if number:
            p.set("Number", number)
        for chunk, style in _runs_for(text, spans):
            text_el = ET.SubElement(p, "Text")
            if style:
                text_el.set("Style", style)
            text_el.text = chunk

    for el in doc.front_matter:
        if el.text:
            add_paragraph(el.type, el.text, spans=el.spans)

    for scene in doc.scenes:
        add_paragraph(ElementType.SCENE_HEADING, scene.heading_raw, str(scene.scene_number))
        for el in scene.elements:
            if el.type == ElementType.SCENE_HEADING:
                continue  # heading already emitted
            if el.text:
                add_paragraph(el.type, el.text, spans=el.spans)

    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return body.decode("utf-8")


def export(doc: ScriptDocument, fmt: str, provenance=None) -> str:
    """Dispatch: 'fountain' | 'fdx' | 'txt' -> text content of the export.

    `provenance` is an optional dict of caller-known facts, or False to suppress
    the block entirely (format-conformance fixtures only — every writer-facing
    route embeds it).
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported export format '{fmt}'. Supported: {list(SUPPORTED_FORMATS)}")
    if fmt == "fountain":
        return to_fountain(doc, provenance=provenance)
    if fmt == "fdx":
        return to_fdx(doc, provenance=provenance)
    return to_txt(doc, provenance=provenance)


def export_to_path(doc: ScriptDocument, fmt: str, path: str, provenance=None) -> str:
    """Export and write to disk. Returns the export text."""
    text = export(doc, fmt, provenance=provenance)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text
