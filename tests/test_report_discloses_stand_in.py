"""Gap 88: a report must disclose the stand-in BY NATURE, from the run's record.

The demo model used to be disclosed only by name — "Analyzed with:
`demo-craft-model`" plus the stub's own `[demo]` prefixes. Both depend on either
the reader recognising a model id or the stub cooperating, and neither survives
the writer connecting a real server (that is gap 59's shape: disclosure follows
current global state instead of the run being described).

`model_used` is persisted with the report, so the record exists; these tests pin
that the renderer uses it.
"""

import os

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import model_is_stand_in, render_markdown
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument

STAND_IN = "demo-craft-model"
REAL = "qwen2.5-14b-instruct"


def _render(model_used, findings=None):
    doc = ScriptDocument(title="T", author=None, source_format="fountain",
                         source_filename="x.fountain")
    doc.scenes.append(Scene(
        scene_number=1, heading_raw="INT. ROOM - DAY",
        elements=[Element(type=ElementType.DIALOGUE, text="Hello there, friend.")]))
    return render_markdown(AnalysisResult(doc=doc, findings=findings or [],
                                          model_used=model_used))


class TestTheMarkdownStatesTheNature:
    def test_a_stand_in_report_says_so_in_words(self):
        md = _render(STAND_IN)
        assert "not a real analysis" in md.lower(), (
            "the exported report names the model id but never says what it is")
        assert "stand-in" in md.lower()
        assert "Do not use them to judge your screenplay" in md

    def test_a_real_report_carries_no_stand_in_warning(self):
        """A permanent banner trains the writer to ignore it."""
        md = _render(REAL)
        assert "not a real analysis" not in md.lower()
        assert "stand-in" not in md.lower()

    def test_the_disclosure_comes_from_the_run_not_the_stub_wording(self):
        """Findings that do NOT happen to prefix themselves still produce a
        disclosed report. This is the defect: disclosure via the model saying
        '[demo]' is the stub cooperating, not the renderer doing its job."""
        findings = [{"id": "f1", "category": "dialogue", "severity": "high",
                     "issue": "On the nose", "scene_refs": [1],
                     "evidence_quote": "Hello there, friend."}]
        md = _render(STAND_IN, findings=findings)
        assert "[demo]" not in md
        assert "not a real analysis" in md.lower()

    def test_the_disclosure_sits_above_what_the_writer_reads(self):
        """Position matters: a caveat after the findings is read too late."""
        md = _render(STAND_IN)
        assert md.lower().index("not a real analysis") < md.index("## Detailed Analysis")

    def test_the_disclosure_is_its_own_block_not_glued_to_the_next_line(self):
        md = _render(STAND_IN)
        assert "getting a real reading.\n" not in md  # no stray glued lines
        line = next(ln for ln in md.splitlines() if "not a real analysis" in ln.lower())
        assert line.startswith("> "), (
            "the disclosure must be a blockquote so it survives Markdown parsing "
            "as a distinct block")


class TestTheArchiveStaysTruthful:
    def test_model_is_stand_in_reads_the_record(self):
        assert model_is_stand_in(STAND_IN) is True
        assert model_is_stand_in(REAL) is False
        assert model_is_stand_in(None) is False
        assert model_is_stand_in("") is False

    def test_an_archived_demo_report_discloses_after_demo_mode_is_off(self, monkeypatch):
        """Gap 59's shape, pinned at the surface that leaves the app."""
        monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", False)
        assert webapp_server._report_banner(STAND_IN), (
            "an archived demo report lost its banner once the writer connected a "
            "real server — the export then reads as a real review")

    def test_a_real_report_is_not_bannered_just_because_demo_mode_is_on(self, monkeypatch):
        monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", True)
        assert webapp_server._report_banner(REAL) == "", (
            "a real reading was labelled canned because of a global setting")

    def test_unknown_provenance_falls_back_rather_than_claiming_a_real_reading(
            self, monkeypatch):
        monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", True)
        assert webapp_server._report_banner(None), (
            "with the run's model unknown the banner must stay conservative")


class TestTheHtmlExportCarriesIt:
    def test_the_blockquote_reaches_the_exported_html(self):
        md = _render(STAND_IN)
        html = webapp_server._md_to_html(md, webapp_server._report_banner(STAND_IN))
        assert 'class="report-disclosure"' in html
        assert "not a real analysis" in html
        assert "&gt; **This report" not in html, (
            "the renderer flattened the blockquote into a paragraph with a "
            "literal '>' — the warning degrades instead of rendering")

    def test_a_real_report_exports_without_the_banner(self):
        md = _render(REAL)
        html = webapp_server._md_to_html(md, webapp_server._report_banner(REAL))
        assert 'class="demo-banner"' not in html
