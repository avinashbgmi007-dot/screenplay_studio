"""
screenplay_parser — Piece 1 of the Script Doctor & Co-Writer Studio.

No model dependency. Converts .fdx / .pdf / .txt / .fountain / .md
screenplays into a single structured JSON schema (see models.ScriptDocument)
that Piece 2 (Analyzer) and Piece 3 (Co-writer) both consume.

Quick use:
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay("my_script.fdx")
    doc.save("my_script.json")
"""

import os

from .models import Element, ElementType, ParseWarning, Scene, ScriptDocument
from .fdx_parser import parse_fdx
from .text_parser import parse_txt, parse_fountain, parse_md
from .pdf_parser import parse_pdf
from .knowledge_graph import build_knowledge_graph, KnowledgeGraph

__all__ = [
    "Element", "ElementType", "ParseWarning", "Scene", "ScriptDocument",
    "parse_screenplay", "parse_fdx", "parse_txt", "parse_fountain", "parse_md", "parse_pdf",
    "build_knowledge_graph", "KnowledgeGraph",
]

_EXT_DISPATCH = {
    ".fdx": parse_fdx,
    ".pdf": parse_pdf,
    ".txt": parse_txt,
    ".fountain": parse_fountain,
    ".md": parse_md,
}


def parse_screenplay(path: str) -> ScriptDocument:
    """Auto-detect format from file extension and parse."""
    ext = os.path.splitext(path)[1].lower()
    parser_fn = _EXT_DISPATCH.get(ext)
    if parser_fn is None:
        raise ValueError(
            f"Unsupported screenplay format '{ext}'. Supported: {sorted(_EXT_DISPATCH.keys())}"
        )
    return parser_fn(path)
