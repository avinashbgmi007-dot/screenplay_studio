"""Webapp tests for the prioritized fix queue (severity x act ordering)."""

import io
import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Fix Queue Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table.

MARA
I promise I'll explain everything.
"""


def _analyzed_project(http_client):
    resp = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Fix Queue Test"},
        content_type="multipart/form-data",
    )
    project = resp.get_json()["project"]
    http_client.post(f"/api/projects/{project}/analyze")
    return project


class TestFixQueue:
    def test_empty_before_analysis(self, http_client):
        resp = http_client.post(
            "/api/projects",
            data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Fix Queue Test"},
            content_type="multipart/form-data",
        )
        project = resp.get_json()["project"]
        data = http_client.get(f"/api/projects/{project}/fixqueue").get_json()
        assert data["items"] == []

    def test_items_sorted_by_severity_then_act(self, http_client):
        project = _analyzed_project(http_client)
        resp = http_client.get(f"/api/projects/{project}/fixqueue")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["items"]) >= 3
        assert data["acts"]

        weights = {"high": 0, "medium": 1, "low": 2}
        seq = [weights.get(i["severity"], 3) for i in data["items"]]
        assert seq == sorted(seq), "severity ordering violated"

    def test_items_carry_act_and_status(self, http_client):
        project = _analyzed_project(http_client)
        data = http_client.get(f"/api/projects/{project}/fixqueue").get_json()
        item = data["items"][0]
        assert item["act"] in (1, 2, 3, None)
        assert item["status"] in ("addressed", "still_present", "unknown")
        assert "issue" in item and "scene_heading" in item

    def test_items_carry_evidence_and_verification(self, http_client):
        """§7: a queue row is a to-do over a real finding, so it has to say how
        well that finding's own evidence held up. Both fields exist in the report
        and the allowlist was dropping them on the floor."""
        project = _analyzed_project(http_client)
        items = http_client.get(
            f"/api/projects/{project}/fixqueue").get_json()["items"]
        assert items
        for item in items:
            assert "evidence_quote" in item
            assert "verification" in item

        # Carried, not invented: whatever the row shows must be the report's own
        # text and the verifier's own vocabulary.
        with open(os.path.join(webapp_server.PROJECTS_DIR, project,
                               "report.findings.json"), encoding="utf-8") as f:
            report = json.load(f)
        report_quotes = {fl.get("evidence_quote") for fl in report["findings"]
                         if fl.get("evidence_quote")}
        assert report_quotes, "the mock report carries no quotes to hand over"
        quoted = [i for i in items if i["evidence_quote"]]
        assert quoted, "no queue row arrived with its evidence quote"
        for item in quoted:
            assert item["evidence_quote"] in report_quotes
        for item in items:
            if item["verification"]:
                assert item["verification"]["status"] in (
                    "verified", "not_found", "no_quote", "scene_not_found")
        assert any(i["verification"] for i in items), \
            "verification never crossed the allowlist"

    @pytest.mark.parametrize("endpoint", ["fixqueue", "findings"])
    def test_both_routes_preserve_reason_flags_with_false_and_missing_controls(self, http_client, endpoint):
        """The deep card reads the report, but flat/query consumers need the
        same identity reason too. A selector fix cannot repair a wire omission.
        Exercise real report loading/sanitization and both public envelopes.
        """
        project = _analyzed_project(http_client)
        path = os.path.join(webapp_server.PROJECTS_DIR, project, "report.findings.json")
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        original = report["findings"][0]
        flags = ("contested", "identity_uncertain", "ungrounded")
        controls = []
        for label, value in (("set", True), ("clear", False), ("absent", None)):
            row = dict(original)
            row["issue"] = f"{original['issue']} [flag transport {label}]"
            for flag in flags:
                row.pop(flag, None)
                if value is not None:
                    row[flag] = value
            controls.append(row)
        report["findings"] = controls
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f)

        response = http_client.get(f"/api/projects/{project}/{endpoint}")
        assert response.status_code == 200
        payload = response.get_json()
        by_issue = {row["issue"]: row for row in payload["items"]}
        assert set(by_issue) == {row["issue"] for row in controls}
        for source in controls:
            served = by_issue[source["issue"]]
            for flag in flags:
                assert flag in served, f"/{endpoint} drops {flag} from the finding"
                assert served[flag] is bool(source.get(flag)), (endpoint, flag, source, served)
        # The routes deliberately have different envelopes; this is field
        # carriage through the existing shared assembler, not their unification.
        if endpoint == "fixqueue":
            assert payload["acts"]
            assert payload["total_count"] == len(controls)
        else:
            assert payload["count"] == len(controls)
