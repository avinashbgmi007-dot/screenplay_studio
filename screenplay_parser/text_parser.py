"""
Parser for plain-text (.txt) and Fountain (.fountain / screenplay-flavored .md)
screenplays.

Fountain has explicit "forced" syntax (leading '.', '@', '>', '#', '=') which
we honor when present. Everything else — for both formats — goes through the
same blank-line-delimited state machine: a dialogue block stays "open"
(subsequent non-blank lines are attributed to the current speaker) until a
blank line closes it, which mirrors how screenplays are actually formatted
and avoids needing column/indentation data (which plain .txt doesn't have).

Because this relies on formatting conventions rather than explicit tags,
output is marked parse_confidence="medium" — good enough to work with, but
callers should treat ambiguous character-attribution edge cases as fixable
via manual review rather than ground truth.
"""

import os
import re

from .models import Element, ElementType, ParseWarning, Scene, ScriptDocument
from .heuristics import (
    looks_like_character_cue,
    looks_like_parenthetical,
    looks_like_scene_heading,
    looks_like_shot,
    looks_like_time_marker,
    looks_like_transition,
    normalize_character_name,
    parse_scene_heading,
)

BONEYARD_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
TITLE_PAGE_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 ]{0,30}):\s*(.*)$")


def _strip_boneyard(text: str) -> str:
    return BONEYARD_RE.sub("", text)


def _extract_title_page(lines: list[str]) -> tuple[dict, int]:
    """
    Fountain title pages are 'Key: value' pairs at the very top of the file,
    ending at the first blank line. Returns (fields, index_of_first_content_line).
    If the file doesn't start with recognizable key:value pairs, returns ({}, 0).
    """
    fields: dict[str, str] = {}
    i = 0
    current_key = None
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            break
        m = TITLE_PAGE_KEY_RE.match(line)
        if m:
            current_key = m.group(1).strip().lower()
            fields[current_key] = m.group(2).strip()
        elif current_key and line.startswith((" ", "\t")):
            fields[current_key] += " " + line.strip()
        else:
            if i == 0:
                return {}, 0  # first line isn't key:value — not a title page at all
            break
        i += 1
    return fields, i


def parse_text(path: str, source_format: str = "txt") -> ScriptDocument:
    filename = os.path.basename(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    if source_format == "fountain":
        raw = _strip_boneyard(raw)

    lines = raw.split("\n")

    title = None
    author = None
    start_idx = 0

    if source_format in ("fountain", "md"):
        fields, start_idx = _extract_title_page(lines)
        title = fields.get("title")
        author = fields.get("author") or fields.get("credit")

    return _parse_lines(lines, source_format, filename, title=title, author=author, start_idx=start_idx)


def _parse_lines(
    lines: list[str],
    source_format: str,
    filename: str,
    title: str = None,
    author: str = None,
    start_idx: int = 0,
    page_of_line: dict = None,
    line_layout: dict = None,
) -> ScriptDocument:
    """
    Core classifier shared by the .txt/.fountain path and the PDF path (which
    reconstructs synthetic lines — with blank lines inserted at detected
    paragraph breaks — from layout-aware text extraction, then feeds them
    through this same state machine so classification logic isn't duplicated).
    """
    doc = ScriptDocument(title=title, author=author, source_format=source_format, source_filename=filename)
    doc.parse_confidence = "medium"

    current_scene: Scene | None = None
    scene_num = 0
    pending_character: str | None = None
    dialogue_open = False
    paren_open = False  # a multi-line parenthetical is in progress (first line opened it)

    def add_scene(heading_text: str):
        nonlocal current_scene, scene_num, pending_character, dialogue_open, paren_open
        scene_num += 1
        parsed = parse_scene_heading(heading_text)
        page = page_of_line.get(idx) if page_of_line else None
        current_scene = Scene(
            scene_number=scene_num,
            heading_raw=heading_text.strip(),
            int_ext=parsed["int_ext"],
            location=parsed["location"],
            time_of_day=parsed["time_of_day"],
            page_start=page,
            page_end=page,
        )
        current_scene.elements.append(Element(type=ElementType.SCENE_HEADING, text=heading_text.strip(), line_start=idx))
        doc.scenes.append(current_scene)
        pending_character = None
        dialogue_open = False
        paren_open = False

    def add_element(etype: ElementType, text: str, character: str | None = None):
        target = current_scene
        el = Element(type=etype, text=text.strip(), character=character, line_start=idx)
        if target is None:
            doc.front_matter.append(el)
            return
        target.elements.append(el)
        if page_of_line and idx in page_of_line:
            target.page_end = page_of_line[idx]
        if character and character not in target.characters_present:
            target.characters_present.append(character)

    def classify_fresh(idx: int, stripped: str, layout: str | None):
        """Classify a line that is NOT dialogue continuation: character cue or
        action. Used both for lines seen with no dialogue open and for lines
        that *close* an open dialogue block (PDF layout says the block ended)."""
        nonlocal pending_character, dialogue_open, paren_open
        # caseless scripts (Devanagari/Hindi, Tamil) have no uppercase, so the
        # cue test needs the next non-blank line for context — a short
        # native-script line is only a speaker if followed by content.
        nxt = ""
        nxt2 = ""
        for j in range(idx + 1, len(lines)):
            if lines[j].strip():
                nxt = lines[j].strip()
                for k in range(j + 1, len(lines)):
                    if lines[k].strip():
                        nxt2 = lines[k].strip()
                        break
                break
        is_cue = looks_like_character_cue(stripped, nxt, nxt2)
        if not is_cue and layout == "center":
            # A centered short all-caps line at the classic character-cue
            # position is a cue even if the bare text heuristic is unsure —
            # column position is strong evidence on its own.
            is_cue = looks_like_character_cue(stripped)
        if is_cue:
            pending_character = normalize_character_name(stripped)
            add_element(ElementType.CHARACTER, stripped, character=pending_character)
            dialogue_open = True
            paren_open = False
        else:
            add_element(ElementType.ACTION, stripped)
            paren_open = False

    skip: set[int] = set()  # line indices absorbed into a merged multi-line transition
    for idx in range(start_idx, len(lines)):
        if idx in skip:
            continue
        line = lines[idx]
        stripped = line.strip()
        layout = line_layout.get(idx) if line_layout else None

        if not stripped:
            dialogue_open = False
            pending_character = None
            paren_open = False
            continue

        # ---- Fountain forced syntax ----
        if source_format in ("fountain", "md"):
            if stripped.startswith("..") is False and stripped.startswith(".") and len(stripped) > 1:
                add_scene(stripped[1:].strip())
                continue
            if stripped.startswith("@"):
                pending_character = normalize_character_name(stripped[1:].strip())
                add_element(ElementType.CHARACTER, stripped[1:].strip(), character=pending_character)
                dialogue_open = True
                paren_open = False
                continue
            if stripped.startswith(">") and not stripped.endswith("<"):
                add_element(ElementType.TRANSITION, stripped[1:].strip())
                pending_character = None
                dialogue_open = False
                paren_open = False
                continue
            if stripped.startswith("#") or stripped.startswith("="):
                continue  # section header / synopsis — metadata, not screenplay content
            if stripped.startswith("~"):
                # lyric line — attribute to current speaker as dialogue if one is open
                if dialogue_open and pending_character:
                    add_element(ElementType.DIALOGUE, stripped[1:].strip(), character=pending_character)
                else:
                    add_element(ElementType.ACTION, stripped[1:].strip())
                continue

        # ---- shared heuristic classification ----
        if looks_like_scene_heading(stripped):
            add_scene(stripped)
        elif looks_like_transition(stripped) or layout == "right":
            # Custom transitions often wrap over several right-aligned lines
            # ("MATCH CUT / TO:(EYES OF / RAHUL)") — absorb the whole run into
            # one transition element instead of three orphan fragments.
            text = stripped
            j = idx + 1
            while j < len(lines) and lines[j].strip() and (line_layout or {}).get(j) == "right":
                text += " " + lines[j].strip()
                skip.add(j)
                j += 1
            add_element(ElementType.TRANSITION, text)
            pending_character = None
            dialogue_open = False
            paren_open = False
        elif looks_like_time_marker(stripped):
            # "2 MONTHS LATER" / "TWO YEARS EARLIER" — beat markers, not action
            add_element(ElementType.TRANSITION, stripped)
            pending_character = None
            dialogue_open = False
            paren_open = False
        elif looks_like_shot(stripped):
            add_element(ElementType.SHOT, stripped)
        elif dialogue_open and pending_character and (paren_open or looks_like_parenthetical(stripped) or stripped.startswith("(")):
            # parenthetical — including the opening line of a multi-line one
            # ("(as he takes a deep" ... "breath)") which doesn't match the
            # complete-parenthetical regex on its own
            add_element(ElementType.PARENTHETICAL, stripped, character=pending_character)
            paren_open = not stripped.rstrip().endswith(")")
        elif dialogue_open and pending_character and layout in ("left", "center"):
            # PDFs carry no blank line between a dialogue block and the action
            # that follows it, so the open-dialogue state would otherwise
            # swallow the action (and any new character cue) as dialogue.
            # Column position resolves it: action resumes at the left margin,
            # a new cue sits centered. Close the block and reclassify fresh.
            dialogue_open = False
            pending_character = None
            classify_fresh(idx, stripped, layout)
        elif dialogue_open and pending_character:
            add_element(ElementType.DIALOGUE, stripped, character=pending_character)
        elif current_scene is not None:
            classify_fresh(idx, stripped, layout)
        else:
            add_element(ElementType.ACTION, stripped)
            pending_character = None
            dialogue_open = False
            paren_open = False

    for scene in doc.scenes:
        scene.characters_present.sort()

    if not doc.scenes:
        doc.warnings.append(ParseWarning(
            message="No scene headings detected. File may not be in standard screenplay format, "
                    "or scene headings don't start with INT./EXT./EST.",
            severity="error",
        ))
        doc.parse_confidence = "low"
    else:
        # sanity check: flag scenes with no dialogue AND no action as likely mis-parses
        empty_scenes = [s.scene_number for s in doc.scenes if len(s.elements) <= 1]
        if empty_scenes:
            doc.warnings.append(ParseWarning(
                message=f"{len(empty_scenes)} scene(s) contain only a heading with no content — "
                        f"possible parsing gap. Scene numbers: {empty_scenes[:10]}",
                severity="warning",
            ))

    return doc


def parse_fountain(path: str) -> ScriptDocument:
    return parse_text(path, source_format="fountain")


def parse_txt(path: str) -> ScriptDocument:
    return parse_text(path, source_format="txt")


def parse_md(path: str) -> ScriptDocument:
    # Fountain-flavored markdown screenplay — same rules as fountain.
    return parse_text(path, source_format="md")
