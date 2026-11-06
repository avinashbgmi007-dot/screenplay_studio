"""Gap 47 — an empty category said "No significant findings" whatever happened.

The renderer emitted that one sentence for every empty category, so a pass that
crashed, a pass that could not apply to the script, a pass that was never
requested, and a pass that genuinely read the script clean all looked
identical. On a report a writer acts on, those are four different facts and the
difference decides what they do next.

The filed reproduction: an `AnalysisResult` with dialogue marked failed and an
error produced a Dialogue section reading "No significant findings", with the
global error printed elsewhere. That is measured in
`test_a_failed_category_never_reads_as_clean`.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import render_markdown, to_findings_json


def _doc():
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write("Title: T\n\nINT. ROOM - NIGHT\n\nMIRA\nHello there.\n")
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _section(result, title="Dialogue & Action"):
    md = render_markdown(result)
    assert f"### {title}" in md, f"section {title!r} missing from the report"
    return md.split(f"### {title}")[1].split("###")[0].strip()


def _result(outcomes, findings=None):
    r = AnalysisResult(doc=_doc())
    r.category_outcomes = dict(outcomes)
    r.findings = list(findings or [])
    return r


# ---------- the filed reproduction ----------

def test_a_failed_category_never_reads_as_clean():
    """Dialogue failed, an error is present, and the section must say so."""
    r = _result({"dialogue": "failed"})
    r.errors.append("Dialogue analysis failed: provider returned 500")
    body = _section(r)
    assert "No significant findings" not in body
    assert "failed" in body.lower()
    # the global error is still rendered somewhere
    assert "provider returned 500" in render_markdown(r)


def test_a_failed_category_is_told_to_re_run():
    """A writer needs to know the fix is re-running, not rewriting."""
    body = _section(_result({"dialogue": "failed"}))
    assert "re-run" in body.lower() or "rerun" in body.lower()


# ---------- the other states ----------

def test_a_clean_category_says_it_ran():
    """The one case where 'nothing here' IS the honest answer — and it must
    say the pass ran, so it is distinguishable from the three that did not."""
    body = _section(_result({"dialogue": "ok"}))
    assert "ran" in body.lower()
    assert "not a clean result" not in body.lower()
    assert "No significant findings" not in body


def test_a_skipped_pass_is_not_a_clean_result():
    body = _section(_result({"dialogue": "skipped"}))
    assert "nothing was measured" in body.lower()
    assert "not a clean result" not in body.lower(), "skipped is not a failure"
    assert "No significant findings" not in body


def test_an_unrecorded_category_is_not_a_clean_result():
    """No entry at all: not requested, or a report from before outcomes were
    recorded. Either way, absence of a record is not evidence of quality."""
    body = _section(_result({}))
    assert "not analyzed" in body.lower()
    assert "not a clean result" in body.lower()
    assert "No significant findings" not in body


def test_the_four_states_render_four_different_sentences():
    seen = {
        label: _section(_result(out))
        for label, out in (
            ("ok", {"dialogue": "ok"}),
            ("failed", {"dialogue": "failed"}),
            ("skipped", {"dialogue": "skipped"}),
            ("absent", {}),
        )
    }
    assert len(set(seen.values())) == 4, seen
    for label, body in seen.items():
        assert "No significant findings" not in body, label


def test_a_category_with_findings_still_renders_its_findings():
    """The outcome text must not displace real findings."""
    finding = {
        "category": "dialogue", "issue": "Line does no work",
        "why_it_matters": "It repeats the previous beat.",
        "severity": "low", "scene_refs": [1], "evidence_quote": None,
    }
    body = _section(_result({"dialogue": "ok"}, [finding]))
    assert "Line does no work" in body
    assert "Analyzed, no findings" not in body


# ---------- the whole vocabulary must be documented and used ----------

def test_pipeline_records_an_outcome_for_every_deterministic_pass():
    """A pass that can fail must be able to say it failed.

    Source-level check, because driving every pass to failure needs a model.
    The four deterministic/craft passes used to record nothing, which is
    exactly how they rendered as clean.
    """
    import inspect
    from screenplay_analyzer import pipeline
    src = inspect.getsource(pipeline)
    for key in ("voice", "subtext", "continuity", "pacing"):
        assert f'category_outcomes["{key}"] = "failed"' in src, key
        assert f'category_outcomes["{key}"] = "ok"' in src, key
    assert 'category_outcomes["pacing"] = "skipped"' in src


def test_json_carries_the_outcomes():
    """A JSON consumer must be able to tell clean from never-ran."""
    r = _result({"dialogue": "failed"})
    js = to_findings_json(r)
    assert js["category_outcomes"]["dialogue"] == "failed"


def test_no_old_report_claims_cleanliness_by_default():
    """A result object built without any outcomes (e.g. loaded from an old
    report) must not render ten confident clean bills of health."""
    md = render_markdown(_result({}))
    assert "No significant findings" not in md
    assert md.count("not a clean result") >= 5
