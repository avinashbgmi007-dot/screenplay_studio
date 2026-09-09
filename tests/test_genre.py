"""Tests for the genre-convention check (Feature: genre conventions)."""

import os

from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator
from screenplay_analyzer.genre import conventions_for, GENRE_CONVENTIONS


class TestConventionLookup:
    def test_exact_genre(self):
        assert conventions_for("thriller") == GENRE_CONVENTIONS["thriller"]

    def test_case_and_whitespace(self):
        conv = conventions_for("  Romance ")
        assert conv == GENRE_CONVENTIONS["romance"]

    def test_substring_genre(self):
        conv = conventions_for("romantic comedy")
        assert conv == GENRE_CONVENTIONS["comedy"]

    def test_unknown_genre_falls_back(self):
        conv = conventions_for("weird experimental")
        assert conv == GENRE_CONVENTIONS["drama"]

    def test_empty_genre_falls_back(self):
        assert conventions_for("") == GENRE_CONVENTIONS["drama"]


class TestGenreInPipeline:
    def test_analyze_includes_genre_findings(self, tmp_path, sample_fountain, mock_server):
        manifest = ProjectManifest.create(str(tmp_path / "g"), sample_fountain)
        manifest.server_url = mock_server
        manifest.save()
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()

        import json
        report = json.load(open(manifest.report_findings_path, encoding="utf-8"))
        categories = {f["category"] for f in report["findings"]}
        assert "genre" in categories

    def test_report_has_genre_section(self, tmp_path, sample_fountain, mock_server):
        manifest = ProjectManifest.create(str(tmp_path / "g2"), sample_fountain)
        manifest.server_url = mock_server
        manifest.save()
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()

        md = open(manifest.report_md_path, encoding="utf-8").read()
        assert "Genre Conventions" in md
