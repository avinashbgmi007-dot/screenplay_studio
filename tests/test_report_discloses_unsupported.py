"""Gap 87: the report a writer exports must say when a note is unsupported.

The analyse pipeline demotes a finding with no quote and no observation to low
severity and marks it `ungrounded`. The desk honours that (such rows hide behind
a toggle); the exported Markdown did not, so the same sentence read as a plain
finding in the artefact that travels and as a hidden guess in the dock.

Scope note, stated because the original finding is easy to over-read: the demo
stand-in produced the invented detail ("the revolver"), so nothing here is a
claim about real-model fabrication. This is about disclosure and classification.
"""

import os

import pytest

from screenplay_analyzer.pipeline import AnalysisResult, apply_evidence_floor
from screenplay_analyzer.report import render_markdown
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument

SCRIPT_LINE = "Hello there, friend."


def _doc(text=SCRIPT_LINE):
    d = ScriptDocument(title="T", author=None, source_format="fountain",
                       source_filename="x.fountain")
    d.scenes.append(Scene(
        scene_number=1, heading_raw="INT. ROOM - DAY",
        elements=[Element(type=ElementType.DIALOGUE, text=text)]))
    return d


def _render(findings, doc=None):
    apply_evidence_floor(findings)   # the real pass, not a hand-set flag
    return render_markdown(AnalysisResult(doc=doc or _doc(), findings=findings))


INVENTED = {"id": "f1", "category": "plot_thread", "severity": "medium",
            "issue": "Setup left dangling: 'The revolver'", "scene_refs": [1, 2],
            "evidence_quote": None}
QUOTED = {"id": "f2", "category": "dialogue", "severity": "high",
          "issue": "On the nose", "scene_refs": [1], "evidence_quote": SCRIPT_LINE}


class TestTheExportedReportMarksIt:
    def test_the_invented_detail_is_marked_unsupported(self):
        md = _render([INVENTED, QUOTED])
        line = next(ln for ln in md.splitlines() if "revolver" in ln.lower())
        assert "unsupported" in line.lower(), (
            f"the unsupported row reads as a plain finding in the export: {line!r}")

    def test_a_quoted_finding_is_not_marked_unsupported(self):
        """The mark has to distinguish, not decorate everything — or it becomes
        noise and stops carrying information."""
        md = _render([INVENTED, QUOTED])
        line = next(ln for ln in md.splitlines() if "On the nose" in ln)
        assert "unsupported" not in line.lower()

    def test_the_count_is_stated_where_the_list_is_printed(self):
        md = _render([INVENTED, QUOTED])
        assert "1 of 2 notes below are **unsupported**" in md, (
            "the report does not say how much of what follows rests on nothing "
            "the writer can check")

    def test_no_such_line_when_everything_is_grounded(self):
        md = _render([dict(QUOTED)])
        assert "unsupported" not in md.lower(), (
            "a fully grounded report carries an unsupported banner anyway")

    def test_every_finding_still_renders(self):
        """Disclosure, not silent dropping: the writer must be able to see the
        row and judge it. Hiding it in the export would be the opposite lie."""
        md = _render([INVENTED, QUOTED])
        assert "revolver" in md.lower()
        assert "On the nose" in md


class TestMissingFromTheScriptIsItsOwnClass:
    """The register asks for "names something absent from the script" to be a
    verifiable defect class rather than a low-severity opinion. The machinery
    already exists: `_setup_quote` searches the setup scenes' actual lines and
    returns None when nothing matches, which is exactly the classification. It
    was simply never surfaced as a statement about the script."""

    @staticmethod
    def _ledger(setup):
        return [{"setup": setup, "kind": "prop", "setup_scenes": [1],
                 "payoff_scenes": [], "status": "dangling", "note": ""}]

    def test_a_setup_the_script_never_mentions_is_ungrounded(self):
        from screenplay_analyzer.setup_payoff import dangling_findings

        doc = _doc("He puts the ticket in his pocket.")
        findings = dangling_findings(self._ledger("the revolver"), [], doc=doc)
        apply_evidence_floor(findings)
        assert findings and findings[0]["ungrounded"] is True, (
            "a setup naming a prop the script never mentions was treated as "
            "grounded")

    def test_a_setup_the_script_does_mention_is_grounded(self):
        """The other direction, or the check above proves nothing: a term that
        IS on the page must not be flagged."""
        from screenplay_analyzer.setup_payoff import dangling_findings

        doc = _doc("He puts the ticket in his pocket.")
        findings = dangling_findings(self._ledger("the ticket"), [], doc=doc)
        apply_evidence_floor(findings)
        assert findings and findings[0].get("ungrounded") is not True
        assert findings[0].get("evidence_quote"), (
            "a grounded setup should carry the line it rests on into the report")

    def test_the_absent_prop_is_marked_in_the_rendered_report(self):
        from screenplay_analyzer.setup_payoff import dangling_findings

        doc = _doc("He puts the ticket in his pocket.")
        findings = dangling_findings(self._ledger("the revolver"), [], doc=doc)
        md = _render(findings, doc=doc)
        line = next(ln for ln in md.splitlines() if "revolver" in ln.lower())
        assert "unsupported" in line.lower()
