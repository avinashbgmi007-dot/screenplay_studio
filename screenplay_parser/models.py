"""
Core data model for parsed screenplays.

Every format-specific parser (fdx, txt, fountain, pdf) converges on this
same schema, so anything downstream (analyzer, co-writer, stats) never
needs to know what the source file format was.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json


class ElementType(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    DIALOGUE = "dialogue"
    PARENTHETICAL = "parenthetical"
    TRANSITION = "transition"
    SHOT = "shot"
    GENERAL = "general"  # title page / unclassified text


@dataclass
class Element:
    """A single formatted unit inside a scene, in original document order."""
    type: ElementType
    text: str
    character: Optional[str] = None  # populated for DIALOGUE / PARENTHETICAL elements
    line_start: Optional[int] = None  # source line number, if known (txt/fountain)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class Scene:
    scene_number: int  # 1-indexed sequential order in the script
    heading_raw: str  # e.g. "INT. COFFEE SHOP - DAY"
    int_ext: Optional[str] = None  # "INT" | "EXT" | "INT/EXT" | None
    location: Optional[str] = None  # e.g. "COFFEE SHOP"
    time_of_day: Optional[str] = None  # e.g. "DAY", "NIGHT", "CONTINUOUS"
    page_start: Optional[float] = None
    page_end: Optional[float] = None
    elements: list[Element] = field(default_factory=list)
    characters_present: list[str] = field(default_factory=list)  # derived, sorted

    def to_dict(self) -> dict:
        return {
            "scene_number": self.scene_number,
            "heading_raw": self.heading_raw,
            "int_ext": self.int_ext,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "characters_present": self.characters_present,
            "elements": [e.to_dict() for e in self.elements],
        }


@dataclass
class ParseWarning:
    message: str
    scene_number: Optional[int] = None
    severity: str = "info"  # "info" | "warning" | "error"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScriptDocument:
    title: Optional[str]
    author: Optional[str]
    source_format: str  # "fdx" | "pdf" | "txt" | "fountain" | "md"
    source_filename: str
    scenes: list[Scene] = field(default_factory=list)
    front_matter: list[Element] = field(default_factory=list)  # title page etc.
    warnings: list[ParseWarning] = field(default_factory=list)
    parse_confidence: str = "high"  # "high" | "medium" | "low" — set by format-specific parsers

    @property
    def all_characters(self) -> list[str]:
        seen = set()
        for scene in self.scenes:
            seen.update(scene.characters_present)
        return sorted(seen)

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    @property
    def estimated_page_count(self) -> Optional[float]:
        pages = [s.page_end for s in self.scenes if s.page_end is not None]
        return max(pages) if pages else None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "author": self.author,
            "source_format": self.source_format,
            "source_filename": self.source_filename,
            "parse_confidence": self.parse_confidence,
            "scene_count": self.scene_count,
            "estimated_page_count": self.estimated_page_count,
            "all_characters": self.all_characters,
            "front_matter": [e.to_dict() for e in self.front_matter],
            "scenes": [s.to_dict() for s in self.scenes],
            "warnings": [w.to_dict() for w in self.warnings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @staticmethod
    def from_dict(d: dict) -> "ScriptDocument":
        doc = ScriptDocument(
            title=d.get("title"),
            author=d.get("author"),
            source_format=d.get("source_format", "unknown"),
            source_filename=d.get("source_filename", ""),
            parse_confidence=d.get("parse_confidence", "high"),
        )
        doc.front_matter = [
            Element(type=ElementType(e["type"]), text=e["text"], character=e.get("character"), line_start=e.get("line_start"))
            for e in d.get("front_matter", [])
        ]
        doc.warnings = [
            ParseWarning(message=w["message"], scene_number=w.get("scene_number"), severity=w.get("severity", "info"))
            for w in d.get("warnings", [])
        ]
        for s in d.get("scenes", []):
            scene = Scene(
                scene_number=s["scene_number"],
                heading_raw=s["heading_raw"],
                int_ext=s.get("int_ext"),
                location=s.get("location"),
                time_of_day=s.get("time_of_day"),
                page_start=s.get("page_start"),
                page_end=s.get("page_end"),
                characters_present=s.get("characters_present", []),
            )
            scene.elements = [
                Element(type=ElementType(e["type"]), text=e["text"], character=e.get("character"), line_start=e.get("line_start"))
                for e in s.get("elements", [])
            ]
            doc.scenes.append(scene)
        return doc

    @staticmethod
    def load(path: str) -> "ScriptDocument":
        with open(path, "r", encoding="utf-8") as f:
            return ScriptDocument.from_dict(json.load(f))
