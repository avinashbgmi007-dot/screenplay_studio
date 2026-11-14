"""Trust-state leak in writer_library: past theme issues must carry demotion flags."""

import os

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_cowriter.writer_library import build_library, library_digest_text
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import save_report


class _Doc:
    title = "Library Trust Test"
    source_filename = "library_trust.txt"
    author = None
    source_format = "txt"
    scene_count = 1
    estimated_page_count = 1.0
    parse_confidence = "high"
    all_characters = ["RAJ", "PEN GUY"]
    scenes = []


def _real_report(tmp_path):
    proj = tmp_path / "Proj"
    proj.mkdir(exist_ok=True)
    result = AnalysisResult(doc=_Doc())
    result.findings = [
        {"category": "theme", "issue": "marker-u past theme ungrounded.",
         "why_it_matters": "x", "severity": "high", "scene_refs": [1],
         "evidence_quote": None, "observation": None,
         "verification": {"status": "no_quote"}},
        {"category": "theme", "issue": "marker-c past theme contested.",
         "why_it_matters": "x", "severity": "high", "scene_refs": [1],
         "evidence_quote": "Who asked you?",
         "observation": "The note claims X; however, the script shows Y."},
        {"category": "theme", "issue": "marker-s past theme summary.",
         "why_it_matters": "x", "severity": "medium", "scene_refs": [1],
         "evidence_quote": None, "summary_only": True},
        {"category": "theme", "issue": "marker-i past theme identity.",
         "why_it_matters": "x", "severity": "medium", "scene_refs": [1],
         "evidence_quote": "Who asked you?",
         "identity_uncertain": True},
        {"category": "theme", "issue": "marker-n past theme clean.",
         "why_it_matters": "x", "severity": "medium", "scene_refs": [1],
         "evidence_quote": "Who asked you?",
         "observation": "The turn happens after the midpoint.",
         "verification": {"status": "verified"}},
    ]
    from screenplay_analyzer import pipeline as P
    P.apply_evidence_floor(result)
    import json as _json
    parsed = {"title": _Doc.title, "source_format": "txt", "scene_count": 1,
              "all_characters": _Doc.all_characters, "scenes": []}
    with open(proj / "parsed.json", "w", encoding="utf-8") as f:
        _json.dump(parsed, f)
    json_path = proj / "report.findings.json"
    save_report(result, str(proj / "report.md"), str(json_path))
    return json_path


def test_ungrounded_theme_carries_marker(tmp_path):
    _real_report(tmp_path)
    lib = build_library(str(tmp_path))
    themes = lib[0]["themes"]
    ungrounded = [t for t in themes if "marker-u" in t][0]
    assert "UNGROUNDED" in ungrounded
    assert "NO QUOTE" in ungrounded


def test_contested_theme_carries_marker(tmp_path):
    _real_report(tmp_path)
    lib = build_library(str(tmp_path))
    themes = lib[0]["themes"]
    contested = [t for t in themes if "marker-c" in t][0]
    assert "CONTESTED" in contested


def test_summary_only_theme_carries_marker(tmp_path):
    _real_report(tmp_path)
    lib = build_library(str(tmp_path))
    themes = lib[0]["themes"]
    summary = [t for t in themes if "marker-s" in t][0]
    assert "SUMMARY ONLY" in summary


def test_identity_uncertain_theme_carries_marker(tmp_path):
    _real_report(tmp_path)
    lib = build_library(str(tmp_path))
    themes = lib[0]["themes"]
    ident = [t for t in themes if "marker-i" in t][0]
    assert "IDENTITY UNCERTAIN" in ident


def test_clean_theme_renders_without_marker(tmp_path):
    proj = tmp_path / "Proj"
    proj.mkdir(exist_ok=True)
    result = AnalysisResult(doc=_Doc())
    result.findings = [
        {"category": "theme", "issue": "marker-n past theme clean.", "severity": "medium",
         "scene_refs": [1], "evidence_quote": "Who asked you?",
         "observation": "The turn happens after the midpoint.",
         "verification": {"status": "verified"}},
    ]
    import json as _json
    parsed = {"title": _Doc.title, "source_format": "txt", "scene_count": 1,
              "all_characters": _Doc.all_characters, "scenes": []}
    with open(proj / "parsed.json", "w", encoding="utf-8") as f:
        _json.dump(parsed, f)
    json_path = proj / "report.findings.json"
    save_report(result, str(proj / "report.md"), str(json_path))
    lib = build_library(str(tmp_path))
    themes = lib[0]["themes"]
    clean = [t for t in themes if "marker-n" in t][0]
    assert "[" not in clean


def test_markers_reach_digest_text(tmp_path):
    _real_report(tmp_path)
    text = library_digest_text(build_library(str(tmp_path)))
    for marker in ("UNGROUNDED", "CONTESTED", "SUMMARY ONLY", "IDENTITY UNCERTAIN"):
        assert marker in text, f"{marker} did not reach the digest"
    assert "TRUST MARKERS" in text


def test_clean_shelf_no_legend(tmp_path):
    proj = tmp_path / "Proj"
    proj.mkdir(exist_ok=True)
    result = AnalysisResult(doc=_Doc())
    result.findings = [
        {"category": "theme", "issue": "clean theme one.", "severity": "low",
         "scene_refs": [1], "evidence_quote": "q", "observation": "o",
         "verification": {"status": "verified"}},
    ]
    import json as _json
    parsed = {"title": _Doc.title, "source_format": "txt", "scene_count": 1,
              "all_characters": _Doc.all_characters, "scenes": []}
    with open(proj / "parsed.json", "w", encoding="utf-8") as f:
        _json.dump(parsed, f)
    json_path = proj / "report.findings.json"
    save_report(result, str(proj / "report.md"), str(json_path))
    text = library_digest_text(build_library(str(tmp_path)))
    assert "TRUST MARKERS" not in text
