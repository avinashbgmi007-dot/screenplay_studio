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

    def test_hybrid_genre_combines_conventions(self):
        conv = conventions_for("romantic comedy")
        assert conv == GENRE_CONVENTIONS["comedy"] + GENRE_CONVENTIONS["romance"]

    def test_science_fiction_hybrid_combines_conventions(self):
        conv = conventions_for("Sci-Fi Thriller")
        assert conv == GENRE_CONVENTIONS["sci-fi"] + GENRE_CONVENTIONS["thriller"]

    def test_neo_noir_uses_mystery_and_thriller_conventions(self):
        conv = conventions_for("Neo-noir")
        assert conv == GENRE_CONVENTIONS["mystery"] + GENRE_CONVENTIONS["thriller"]

    def test_unknown_genre_has_no_conventions(self):
        assert conventions_for("weird experimental") == []

    def test_empty_genre_has_no_conventions(self):
        assert conventions_for("") == []

    def test_conventions_and_kb_share_hybrid_routing(self):
        from knowledge_base import KnowledgeBase
        from screenplay_analyzer.rules_context import RulesContext

        label = "Romantic Comedy"
        assert KnowledgeBase.resolve_genres(label) == ("comedy", "romance")
        rule_genres = {rule.genre for rule in RulesContext().rules_for_genre(label)}
        assert {"comedy", "romance"} <= rule_genres
        assert conventions_for(label) == (
            GENRE_CONVENTIONS["comedy"] + GENRE_CONVENTIONS["romance"]
        )

    def test_unknown_genre_skips_the_model_check(self):
        from screenplay_analyzer.genre import run_genre_check

        class UnexpectedClient:
            def chat_json(self, *args, **kwargs):
                raise AssertionError("unknown genre should not trigger a model call")

        assert run_genre_check(
            {"genre": "interpretive dance documentary"}, "overview", UnexpectedClient()
        ) == []


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
