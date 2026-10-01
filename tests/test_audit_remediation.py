"""The audit's P3 register, fixed and pinned (audit 2026-09-30, F-01..F-05),
plus the three findings query APIs Report 2 §6 proposed.

Each test names its finding. The P3 register was verified against the running
app before anything here was written; these tests keep the fixes from regressing
the same way the register kept the findings from drifting.
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import screenplay_studio.webapp_server as webapp_server  # noqa: E402


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Audit Remediation Test
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


def _upload(http_client):
    resp = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Audit Test"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    return resp.get_json()["project"]


def _project_with_draft(http_client):
    """The audit's F-01 repro: upload a project, then upload a DRAFT — which
    snapshots the original and auto-activates the new draft."""
    project = _upload(http_client)
    resp = http_client.post(
        f"/api/projects/{project}/drafts",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "draft2.fountain")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    body = resp.get_json()
    active = body.get("active_draft")
    assert active, f"draft upload should auto-activate; got {body}"
    return project, active


def _analyzed(http_client):
    project = _upload(http_client)
    http_client.post(f"/api/projects/{project}/analyze")
    return project


def _report_path(project):
    return os.path.join(webapp_server.PROJECTS_DIR, project, "report.findings.json")


def _fixqueue_items(http_client, project):
    return http_client.get(f"/api/projects/{project}/fixqueue").get_json()["items"]


# ---------------------------------------------------------------------------
# F-01: activating the already-active draft is a no-op, not "No snapshot"
# ---------------------------------------------------------------------------

class TestF01ActivateActiveDraft:
    def test_activate_active_answers_ok_not_no_snapshot(self, http_client):
        project, active = _project_with_draft(http_client)
        resp = http_client.post(f"/api/projects/{project}/drafts/activate",
                                json={"name": active})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert "error" not in (resp.get_json() or {})

    def test_activate_active_still_carries_the_manifest_summary(self, http_client):
        project, active = _project_with_draft(http_client)
        body = http_client.post(f"/api/projects/{project}/drafts/activate",
                                json={"name": active}).get_json()
        assert body and body.get("project") == project

    def test_activate_unknown_draft_still_answers_400(self, http_client):
        project = _upload(http_client)
        resp = http_client.post(f"/api/projects/{project}/drafts/activate",
                                json={"name": "no-such-draft"})
        assert resp.status_code == 400
        assert "No snapshot" in resp.get_json()["error"]

    def test_activate_with_no_name_still_answers_400(self, http_client):
        project = _upload(http_client)
        resp = http_client.post(f"/api/projects/{project}/drafts/activate", json={})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# F-02: a negative finding index answers the M4 JSON-400, never HTML 405
# ---------------------------------------------------------------------------

class TestF02NegativeFindingIndex:
    @pytest.mark.parametrize("index", [-1, -5])
    def test_negative_dismiss_answers_json_400(self, http_client, index):
        project = _upload(http_client)
        resp = http_client.post(f"/api/projects/{project}/findings/{index}/dismiss")
        assert resp.status_code == 400
        assert resp.content_type.startswith("application/json")
        assert "out of range" in resp.get_json()["error"]

    def test_negative_undismiss_answers_json_400(self, http_client):
        project = _upload(http_client)
        resp = http_client.post(f"/api/projects/{project}/findings/-1/undismiss")
        assert resp.status_code == 400
        assert resp.content_type.startswith("application/json")

    def test_too_large_index_still_answers_json_400(self, http_client):
        project = _upload(http_client)
        resp = http_client.post(f"/api/projects/{project}/findings/99/dismiss")
        assert resp.status_code == 400
        assert resp.content_type.startswith("application/json")


# ---------------------------------------------------------------------------
# F-03: nosniff + referrer policy ride every response, not just the SPA document
# ---------------------------------------------------------------------------

class TestF03GlobalNosniff:
    @pytest.mark.parametrize("path", ["/api/health", "/api/config", "/style.css",
                                      "/definitely-not-here", "/api/projects"])
    def test_nosniff_on_every_response(self, http_client, path):
        resp = http_client.get(path)
        assert resp.headers.get("X-Content-Type-Options") == "nosniff", path

    def test_referrer_policy_on_api_too(self, http_client):
        assert http_client.get("/api/health").headers.get("Referrer-Policy") == "no-referrer"

    def test_csp_still_scoped_to_the_spa_document(self, http_client):
        assert http_client.get("/").headers.get("Content-Security-Policy")
        assert not http_client.get("/api/health").headers.get("Content-Security-Policy")


# ---------------------------------------------------------------------------
# F-04: the shipped KB default honors its own soft ceiling
# ---------------------------------------------------------------------------

class TestF04KbBudgetDefault:
    def test_default_budget_equals_the_soft_ceiling(self):
        import screenplay_analyzer.rules_context as rc
        assert rc.KB_FRAGMENT_SOFT_WARN == 40000
        assert rc.KB_FRAGMENT_CHAR_BUDGET == rc.KB_FRAGMENT_SOFT_WARN, (
            "the shipped default must cap fragments at the soft ceiling "
            "without an env var (F-04)")
        from screenplay_analyzer import rules_context as pkg_rc
        assert pkg_rc.KB_FRAGMENT_CHAR_BUDGET == pkg_rc.KB_FRAGMENT_SOFT_WARN

    def test_oversized_default_fragment_now_states_the_omission(self):
        """The exact audit symptom: the character fragment rendered >65k chars
        with no budget set. Under the new default it keeps whole rules up to the
        ceiling and says what it shed."""
        from screenplay_analyzer.rules_context import (
            KB_OMISSION_MARKER, RulesContext)
        frag = RulesContext().fragment_for_pass("character")
        assert len(frag) <= 40000 + 400, f"fragment is {len(frag)} chars"
        assert KB_OMISSION_MARKER in frag

    def test_explicit_zero_budget_still_means_unlimited(self, monkeypatch):
        import screenplay_analyzer.rules_context as rc
        monkeypatch.setattr(rc, "KB_FRAGMENT_CHAR_BUDGET", 0)
        frag = rc.RulesContext().fragment_for_pass("character")
        assert rc.KB_OMISSION_MARKER not in frag

    def test_explicit_budget_wins_over_the_default(self, monkeypatch):
        import screenplay_analyzer.rules_context as rc
        monkeypatch.setattr(rc, "KB_FRAGMENT_CHAR_BUDGET", 5000)
        frag = rc.RulesContext().fragment_for_pass("character")
        assert len(frag) <= 6000


# ---------------------------------------------------------------------------
# F-05: the route map's totals are pinned to the source census
# ---------------------------------------------------------------------------

def _source_census():
    """The same census the map's header states: route decorators per module."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import re
    counts = {}
    for fname, appname in (("screenplay_studio/webapp_server.py", "app"),
                           ("screenplay_studio/demo_model.py", "demo_app")):
        src = open(os.path.join(base, fname), encoding="utf-8").read()
        counts[fname] = len(re.findall(r"@" + appname + r"\.route\(", src))
    return counts


class TestF05RouteMapTotals:
    def test_map_totals_match_the_source_census(self):
        counts = _source_census()
        total = sum(counts.values())
        server = counts["screenplay_studio/webapp_server.py"]
        doc = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "docs", "API_ROUTE_MAP.md"), encoding="utf-8").read()
        assert f"**Totals:** {server} endpoints in `webapp_server.py` + 2 in `demo_model.py` = **{total}**" in doc, (
            f"docs/API_ROUTE_MAP.md totals drifted: source says {server}+2={total}")
        for marker in ("findings/summary", "findings/intent/batch", "`get_findings`"):
            assert marker in doc, f"route map lost {marker}"

    def test_census_is_what_the_audit_measured_plus_the_new_routes(self):
        counts = _source_census()
        # 91 (audit baseline) + analyze/cancel (R2) + library/backup (R7) = 93
        assert counts["screenplay_studio/webapp_server.py"] == 93, (
            "the count the route map pins moved: regenerate the map (its header "
            "says how) and update this pin together")


# ---------------------------------------------------------------------------
# New API: GET /findings/summary (Report 2 §6 #1)
# ---------------------------------------------------------------------------

class TestFindingsSummary:
    def test_counts_and_dawn_arithmetic(self, http_client):
        project = _analyzed(http_client)
        data = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        assert data["total_count"] >= 3
        total_live = data["total_count"] - data["dismissed_count"]
        assert data["open_count"] + data["done_count"] == total_live
        expected_dawn = round(100 * data["done_count"] / total_live) if total_live else 0
        assert data["dawn_pct"] == expected_dawn
        assert sum(data["by_severity"].values()) == data["total_count"]
        assert sum(data["by_category"].values()) == data["total_count"]
        assert set(data["by_status"]) == {"addressed", "still_present", "unknown"}
        assert data["acts"] and {"act", "name", "scene_count"} <= set(data["acts"][0])

    def test_writer_intent_moves_done_and_dawn(self, http_client):
        project = _analyzed(http_client)
        before = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        fid = _fixqueue_items(http_client, project)[0]["finding_id"]
        http_client.post(f"/api/projects/{project}/findings/intent",
                         json={"finding_id": fid, "intent": "addressed"})
        after = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        assert after["done_count"] == before["done_count"] + 1
        total = after["total_count"] - after["dismissed_count"]
        assert after["dawn_pct"] == round(100 * after["done_count"] / total)

    def test_dismissed_rows_leave_open_and_dawn_alone(self, http_client):
        project = _analyzed(http_client)
        item = _fixqueue_items(http_client, project)[0]
        http_client.post(f"/api/projects/{project}/findings/{item['index']}/dismiss",
                         json={"issue": item["issue"]})
        data = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        assert data["dismissed_count"] == 1
        assert data["open_count"] + data["done_count"] == data["total_count"] - 1

    def test_answers_the_report_contracts(self, http_client):
        project = _upload(http_client)
        assert http_client.get(f"/api/projects/{project}/findings/summary").status_code == 400
        analyzed = _analyzed(http_client)
        os.remove(_report_path(analyzed))
        resp = http_client.get(f"/api/projects/{analyzed}/findings/summary")
        assert resp.status_code == 404
        assert "Re-run" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# New API: GET /findings (Report 2 §6 #2)
# ---------------------------------------------------------------------------

class TestFindingsQuery:
    def test_rows_match_fixqueue(self, http_client):
        project = _analyzed(http_client)
        fq = _fixqueue_items(http_client, project)
        fq_items = http_client.get(f"/api/projects/{project}/findings").get_json()["items"]
        assert [(i["index"], i["finding_id"]) for i in fq] == \
               [(i["index"], i["finding_id"]) for i in fq_items]

    def test_filters(self, http_client):
        project = _analyzed(http_client)
        all_items = http_client.get(f"/api/projects/{project}/findings").get_json()["items"]
        scene = next(i for i in all_items if i["scene_refs"])["scene_refs"][0]
        by_scene = http_client.get(f"/api/projects/{project}/findings?scene={scene}").get_json()
        assert by_scene["items"] and all(scene in i["scene_refs"] for i in by_scene["items"])
        sev = http_client.get(f"/api/projects/{project}/findings?severity=high").get_json()
        assert all(i["severity"] == "high" for i in sev["items"])
        cat = http_client.get(
            f"/api/projects/{project}/findings?category={all_items[0]['category']}").get_json()
        assert all(i["category"] == all_items[0]["category"] for i in cat["items"])

    def test_group_by_issue_text_preserves_scene_refs(self, http_client):
        """The Report 2 §4.3 measured case: one byte-identical note across two
        scenes renders once, with the scene union carried — nothing lost."""
        project = _analyzed(http_client)
        with open(_report_path(project), encoding="utf-8") as f:
            report = json.load(f)
        first = report["findings"][0]
        dup = dict(first)
        dup["scene_refs"] = [2]
        report["findings"].append(dup)
        with open(_report_path(project), "w", encoding="utf-8") as f:
            json.dump(report, f)
        groups = http_client.get(
            f"/api/projects/{project}/findings?group_by=issue-text").get_json()["groups"]
        g = next(g for g in groups if g["issue"] == first.get("issue"))
        assert g["count"] == 2
        expected_refs = sorted({s for fl in report["findings"]
                                if fl.get("issue") == first.get("issue")
                                for s in (fl.get("scene_refs") or [])})
        assert sorted(g["scene_refs"]) == expected_refs
        assert len(g["members"]) == 2
        # The rows grouped are the report's own rows: same content identity
        # (category + quote), different scenes — exactly the rung-20 case the
        # chip must carry.
        assert g["members"][0]["finding_id"] == g["members"][1]["finding_id"]
        assert sorted({s for m in g["members"] for s in (m["scene_refs"] or [])}) == sorted(expected_refs)

    def test_dismissal_triage_applies(self, http_client):
        project = _analyzed(http_client)
        item = _fixqueue_items(http_client, project)[0]
        http_client.post(f"/api/projects/{project}/findings/{item['index']}/dismiss",
                         json={"issue": item["issue"]})
        data = http_client.get(f"/api/projects/{project}/findings").get_json()
        assert all(i["index"] != item["index"] for i in data["items"])
        kept = http_client.get(
            f"/api/projects/{project}/findings?include_dismissed=1").get_json()
        assert any(i["index"] == item["index"] for i in kept["items"])


# ---------------------------------------------------------------------------
# New API: POST /findings/intent/batch (Report 2 §6 #3)
# ---------------------------------------------------------------------------

class TestIntentBatch:
    def test_roundtrip(self, http_client):
        project = _analyzed(http_client)
        items = _fixqueue_items(http_client, project)[:2]
        marks = {i["finding_id"]: "addressed" for i in items}
        marks[items[1]["finding_id"]] = "deferred"
        resp = http_client.post(f"/api/projects/{project}/findings/intent/batch",
                                json={"intents": marks})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        stored = http_client.get(f"/api/projects/{project}/edits").get_json()["finding_intents"]
        assert stored == marks

    def test_batch_clearing_and_mixed_results(self, http_client):
        project = _analyzed(http_client)
        fid = _fixqueue_items(http_client, project)[0]["finding_id"]
        http_client.post(f"/api/projects/{project}/findings/intent/batch",
                         json={"intents": {fid: "addressed"}})
        # One batch that clears a real mark AND carries a bad id: the good one
        # applies, the bad one is reported, and the answer is 207 partial.
        resp = http_client.post(f"/api/projects/{project}/findings/intent/batch",
                                json={"intents": {fid: None, "": "addressed"}})
        body = resp.get_json()
        assert resp.status_code == 207
        assert fid in body["applied"]
        assert any(f["finding_id"] == "" for f in body["failed"])
        stored = http_client.get(f"/api/projects/{project}/edits").get_json()["finding_intents"]
        assert fid not in stored  # null cleared the mark

    def test_rejects_bad_bodies(self, http_client):
        project = _analyzed(http_client)
        assert http_client.post(f"/api/projects/{project}/findings/intent/batch",
                                json={}).status_code == 400
        assert http_client.post(f"/api/projects/{project}/findings/intent/batch",
                                json={"intents": {}}).status_code == 400
        resp = http_client.post(f"/api/projects/{project}/findings/intent/batch",
                                json={"intents": {"": "addressed"}})
        assert resp.status_code == 207
        assert resp.get_json()["failed"]

    def test_batch_writes_the_same_store_as_the_single_route(self, http_client):
        """The batch is N of the single write — same store, same keying."""
        project = _analyzed(http_client)
        items = _fixqueue_items(http_client, project)
        marks = {i["finding_id"]: ("deferred" if idx % 2 else "addressed")
                 for idx, i in enumerate(items)}
        http_client.post(f"/api/projects/{project}/findings/intent/batch",
                         json={"intents": marks})
        assert http_client.get(f"/api/projects/{project}/edits").get_json()["finding_intents"] == marks
