"""The feedback trust bundle (2026-10-01): verification must be honest, aggregated
and served.

Three contracts this file pins:

  * **A quote-less finding still cites SOMETHING.** Script-level categories
    (theme/character/structure/scene_function) cite scene numbers because their
    prompts force `evidence_quote` to null — and until now those numbers were
    never checked, so a hallucinated citation sailed through with no badge.
    All-missing refs now read `scene_not_found` (the same flag a fabricated
    quote gets); one existing scene keeps `no_quote`.
  * **Correctness is a number, not a vibe.** `verification_rate` derives the
    quote-verified percentage from the counts, and refuses to emit one when
    nothing was checkable — a percentage over nothing is a lie.
  * **The served report describes the rows it serves.** The summary block is
    recomputed from the FILTERED findings at serve time, so the serve-time
    filter and the aggregate can never disagree, and pre-block reports gain
    the block on read with no re-analysis.
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from screenplay_analyzer.verifier import (  # noqa: E402
    verify_finding,
    verification_rate,
    verification_summary,
)
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument  # noqa: E402
from screenplay_studio import pass_history  # noqa: E402


def _doc(scene_numbers=(1,)):
    doc = ScriptDocument(
        title="T", author=None, source_format="fountain", source_filename="x.fountain",
    )
    for n in scene_numbers:
        scene = Scene(scene_number=n, heading_raw=f"INT. ROOM {n} - NIGHT")
        scene.elements.append(
            Element(type=ElementType.DIALOGUE, text="I am here now friend.", character="A"))
        doc.scenes.append(scene)
    return doc


# ---------------------------------------------------------------------------
# Part A: the citation a quote-less finding makes is checked
# ---------------------------------------------------------------------------

class TestQuotelessCitationsAreChecked:
    def test_all_cited_scenes_missing_is_flagged(self):
        out = verify_finding({"scene_refs": [7, 9], "evidence_quote": None}, _doc())
        assert out["verification"]["status"] == "scene_not_found"

    def test_one_existing_scene_keeps_no_quote(self):
        # A finding may cite scene 9 wrongly and scene 1 rightly; one real
        # citation keeps it no_quote — the flag is for citations that cannot
        # exist at all, not for sloppy ones.
        out = verify_finding({"scene_refs": [1, 9], "evidence_quote": None}, _doc())
        assert out["verification"]["status"] == "no_quote"

    def test_no_refs_at_all_stays_no_quote(self):
        out = verify_finding({"scene_refs": [], "evidence_quote": None}, _doc())
        assert out["verification"]["status"] == "no_quote"

    def test_a_short_bogus_quote_with_bogus_refs_is_flagged_not_no_quote(self):
        # Below the 3-word floor the quote can never verify, but the REFS are
        # still checkable — and here they are fabricated too.
        out = verify_finding({"scene_refs": [7], "evidence_quote": "hi"}, _doc())
        assert out["verification"]["status"] == "scene_not_found"

    def test_the_quote_bearing_path_is_untouched(self):
        doc = _doc()
        out = verify_finding(
            {"scene_refs": [1], "evidence_quote": "I am here now friend."}, doc)
        assert out["verification"] == {
            "status": "verified", "matched_scene": 1, "confidence": 1.0}


# ---------------------------------------------------------------------------
# Part B: the rate rule
# ---------------------------------------------------------------------------

class TestVerificationRateRule:
    def test_the_rate_counts_only_checkable_findings(self):
        counts = verification_summary([
            {"verification": {"status": "verified"}},
            {"verification": {"status": "verified"}},
            {"verification": {"status": "not_found"}},
            {"verification": {"status": "no_quote"}},          # excluded
            {"verification": {"status": "scene_not_found"}},   # a FAILURE, not a denominator
        ])
        rate = verification_rate(counts)
        assert rate["quote_bearing"] == 3
        assert rate["verified_pct_of_quoted"] == 66.7

    def test_no_checkable_finding_means_no_percentage(self):
        rate = verification_rate({"no_quote": 5, "scene_not_found": 1})
        assert rate["quote_bearing"] == 0
        assert rate["verified_pct_of_quoted"] is None

    def test_empty_and_none_input_do_not_crash(self):
        assert verification_rate({})["verified_pct_of_quoted"] is None
        assert verification_rate(None)["quote_bearing"] == 0


# ---------------------------------------------------------------------------
# Part B: the served surfaces
# ---------------------------------------------------------------------------

@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(client):
    import io
    return client.post(
        "/api/projects",
        data={"file": (io.BytesIO(
            b"Title: Trust\n\nINT. STUDY - NIGHT\n\nMARA\nThe gun is gone.\n"),
            "trust.fountain"), "title": "Trust"},
        content_type="multipart/form-data",
    )


class TestTheServedReportCarriesTheSummary:
    def test_a_served_report_has_the_block_and_it_is_consistent(self, http_client):
        project = _upload(http_client).get_json()["project"]
        assert http_client.post(f"/api/projects/{project}/analyze").status_code == 200

        rep = http_client.get(f"/api/projects/{project}/report").get_json()
        vs = rep.get("verification_summary")
        assert isinstance(vs, dict) and "verified" in vs
        # internal consistency: the rate's denominator is exactly the two
        # statuses a mechanical check can judge
        assert vs["quote_bearing"] == vs["verified"] + vs["not_found"]
        rows = rep["findings"]
        assert sum(vs[k] for k in ("verified", "not_found", "no_quote", "scene_not_found")) \
            == len(rows), "the block must describe the rows it is served with"
        if vs["quote_bearing"]:
            expected = round(100.0 * vs["verified"] / vs["quote_bearing"], 1)
            assert vs["verified_pct_of_quoted"] == expected

    def test_a_pre_block_report_gains_the_block_on_read(self, http_client):
        # Simulate a report written before the block existed: strip it from the
        # stored JSON. The serve-time recomputation must restore it — no
        # re-analysis for old projects.
        project = _upload(http_client).get_json()["project"]
        assert http_client.post(f"/api/projects/{project}/analyze").status_code == 200
        import screenplay_studio.webapp_server as webapp_server
        path = os.path.join(webapp_server.PROJECTS_DIR, project,
                            "report.findings.json")
        stored = json.load(open(path, encoding="utf-8"))
        stored.pop("verification_summary", None)
        json.dump(stored, open(path, "w", encoding="utf-8"))

        rep = http_client.get(f"/api/projects/{project}/report").get_json()
        vs = rep.get("verification_summary")
        assert isinstance(vs, dict) and "verified" in vs
        assert sum(vs[k] for k in ("verified", "not_found", "no_quote", "scene_not_found")) \
            == len(rep["findings"])

    def test_the_findings_summary_answers_the_correctness_question(self, http_client):
        project = _upload(http_client).get_json()["project"]
        assert http_client.post(f"/api/projects/{project}/analyze").status_code == 200
        s = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        assert isinstance(s.get("verification"), dict) and "verified" in s["verification"]

    def test_the_report_served_matches_the_summary_endpoint(self, http_client):
        project = _upload(http_client).get_json()["project"]
        assert http_client.post(f"/api/projects/{project}/analyze").status_code == 200
        rep = http_client.get(f"/api/projects/{project}/report").get_json()
        s = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        assert rep["verification_summary"]["verified"] == s["verification"]["verified"]


# ---------------------------------------------------------------------------
# Part B: the pass arc remembers correctness
# ---------------------------------------------------------------------------

class TestPassHistoryVerificationCounts:
    def test_an_entry_with_the_block_carries_it(self, tmp_path):
        m = SimpleNamespace(project_dir=str(tmp_path))
        block = {"verified": 4, "not_found": 1, "no_quote": 6, "scene_not_found": 0,
                 "quote_bearing": 5, "verified_pct_of_quoted": 80.0}
        entry = pass_history.append_pass(m, {"findings": [], "summary": {}},
                                         verification_counts=block)
        assert entry["verification_counts"] == block
        loaded = pass_history.load_passes(m)
        assert loaded[-1]["verification_counts"] == block

    def test_an_entry_without_the_block_keeps_the_documented_shape(self, tmp_path):
        m = SimpleNamespace(project_dir=str(tmp_path))
        entry = pass_history.append_pass(m, {"findings": [], "summary": {}})
        assert set(entry) == {"ts", "total", "open", "addressed", "failed_categories"}
        assert "verification_counts" not in pass_history.load_passes(m)[-1]

    def test_a_pre_field_entry_reads_unchanged(self, tmp_path):
        # The exact back-compat claim: an entry written before the field
        # existed (no key at all) loads as it always did.
        m = SimpleNamespace(project_dir=str(tmp_path))
        pass_history.append_pass(m, {"findings": [], "summary": {}})
        old = pass_history.load_passes(m)[0]
        old.pop("verification_counts", None)
        from screenplay_studio.jsonio import atomic_write_json
        atomic_write_json(pass_history.path(m), [old])
        assert pass_history.load_passes(m)[0] == old

    def test_a_damaged_block_is_stripped_not_poisoned(self, tmp_path):
        m = SimpleNamespace(project_dir=str(tmp_path))
        pass_history.append_pass(m, {"findings": [], "summary": {}})
        from screenplay_studio.jsonio import atomic_write_json
        entry = pass_history.load_passes(m)[0]
        entry["verification_counts"] = "garbage"
        atomic_write_json(pass_history.path(m), [entry])
        loaded = pass_history.load_passes(m)[0]
        assert "verification_counts" not in loaded
        assert loaded["open"] == 0  # the rest of the entry survives
