"""M5b — report writes must be atomic.

`save_report` used plain `open(path, "w")`, i.e. truncate-then-write. A crash or
kill in that window (disk full, OOM, an interrupted run) left a torn or empty
`report.findings.json` / `report.md` — the product's core artifact — and the
report route then 500s on the unparseable JSON. The repo's contract is
temp-file + os.replace (jsonio's atomic_write_json); Piece 2 stays standalone,
so it carries its own tiny helper rather than importing screenplay_studio.
"""
from __future__ import annotations

import json
import os

import pytest

from screenplay_analyzer import report as report_mod
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_parser.models import ScriptDocument


def _result():
    return AnalysisResult(doc=ScriptDocument(title="T", author=None,
                                             source_format="fountain",
                                             source_filename="t.fountain"))


def _paths(tmp_path):
    return (str(tmp_path / "report.md"), str(tmp_path / "report.findings.json"))


def test_md_write_failure_leaves_the_previous_file_untouched(tmp_path, monkeypatch):
    md, js = _paths(tmp_path)
    with open(md, "w", encoding="utf-8") as f:
        f.write("PREVIOUS GOOD MD")
    with open(js, "w", encoding="utf-8") as f:
        f.write('{"findings": []}')

    def boom(_result):
        raise RuntimeError("disk full")

    monkeypatch.setattr(report_mod, "render_markdown", boom)
    with pytest.raises(RuntimeError):
        report_mod.save_report(_result(), md, js)

    # not truncated, not half-written — the previous report is still intact
    with open(md, encoding="utf-8") as f:
        assert f.read() == "PREVIOUS GOOD MD"


def test_json_write_failure_leaves_the_previous_file_untouched(tmp_path, monkeypatch):
    md, js = _paths(tmp_path)
    with open(md, "w", encoding="utf-8") as f:
        f.write("PREVIOUS GOOD MD")
    with open(js, "w", encoding="utf-8") as f:
        f.write('{"findings": [{"issue": "keep me"}]}')

    def boom(_result):
        raise RuntimeError("disk full")

    monkeypatch.setattr(report_mod, "to_findings_json", boom)
    with pytest.raises(RuntimeError):
        report_mod.save_report(_result(), md, js)

    with open(js, encoding="utf-8") as f:
        assert json.load(f) == {"findings": [{"issue": "keep me"}]}


def test_a_failed_replace_never_leaves_a_torn_target(tmp_path, monkeypatch):
    """The strongest form: the swap itself fails after the temp file is fully
    written. The target must still be the previous file, never a partial one."""
    md, js = _paths(tmp_path)
    with open(js, "w", encoding="utf-8") as f:
        f.write('{"findings": [{"issue": "keep me"}]}')

    def no_replace(src, dst):
        raise OSError("sharing violation")

    monkeypatch.setattr(report_mod.os, "replace", no_replace)
    with pytest.raises(OSError):
        report_mod.save_report(_result(), md, js)

    with open(js, encoding="utf-8") as f:
        assert json.load(f) == {"findings": [{"issue": "keep me"}]}
    # and the temp file was cleaned up, not left littering the project dir
    leftovers = [p for p in os.listdir(tmp_path) if p.startswith(".tmp-report-")]
    assert not leftovers, f"temp file left behind: {leftovers}"


def test_successful_save_writes_both_files(tmp_path):
    md, js = _paths(tmp_path)
    report_mod.save_report(_result(), md, js)
    assert "findings" in json.load(open(js, encoding="utf-8"))
    assert open(md, encoding="utf-8").read()
