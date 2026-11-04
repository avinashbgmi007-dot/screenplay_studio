"""Gap 113: served counts must distinguish "everything I hold" from "what the
desk shows by default".

The original filing said `/fixqueue` and `/findings/summary` report a count that
includes ungrounded rows "the desk hides by default", and that the strip, meter
and queue print that count. Reading the shipped client while fixing it, that
last part is **not true**, and it is worth pinning both halves:

  * the desk's mass strip prints `findingCounts()` — "N open of M findings" over
    the WHOLE script, with "· K shown by filter" beside it, so whole-script scope
    is labelled rather than implied;
  * the queue header prints `queueCounts()`, which DOES drop ungrounded rows and
    prints them as a separate "total".

So the defect is real but narrower than filed: the counts are honest as
whole-script totals, they merely arrived without the split, and `state.
findingsSummary` — the in-repo field that carries them — is written twice and
read nowhere in the shipped SPA. These tests pin the split the routes now ship
and the precedence it has to use.
"""

import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def client(tmp_path, sample_fountain):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _project_with(client, sample_fountain, findings, marks=None):
    """A real project whose analyze stage is complete and whose report holds
    exactly `findings`. Uploaded and parsed through the real routes."""
    with open(sample_fountain, "rb") as f:
        made = client.post("/api/projects",
                           data={"file": (f, "s.fountain"), "title": "Scope"})
    name = made.json["project"]
    m = webapp_server._load_manifest(name)
    m.mark_complete("analyze")
    os.makedirs(os.path.dirname(m.report_findings_path), exist_ok=True)
    with open(m.report_findings_path, "w", encoding="utf-8") as fh:
        json.dump({"findings": findings}, fh)
    if marks:
        from screenplay_studio.revision import finding_marks_path
        with open(finding_marks_path(m), "w", encoding="utf-8") as fh:
            json.dump(marks, fh)
    m.save()
    return name, m


GROUNDED = {"id": "a", "category": "dialogue", "severity": "high",
            "issue": "Grounded one", "evidence_quote": "line", "scene_refs": [1]}
UNGROUNDED = {"id": "b", "category": "dialogue", "severity": "low",
              "issue": "Ungrounded one", "evidence_quote": None,
              "scene_refs": [1], "ungrounded": True}


class TestTheCountsCarryTheSplit:
    def test_summary_reports_how_many_rows_are_hidden_by_default(self, client, sample_fountain):
        name, _ = _project_with(client, sample_fountain, [GROUNDED, UNGROUNDED])
        data = client.get(f"/api/projects/{name}/findings/summary").get_json()

        # the whole set is still the whole set — that count was never wrong
        assert data["total_count"] == 2
        assert data["open_count"] == 2
        # and now it says how much of that the writer can see
        assert data["ungrounded_count"] == 1
        assert data["ungrounded_hidden_count"] == 1
        assert data["open_visible_count"] == 1, (
            "open_count 2 with nothing hidden would tell a consumer the writer "
            "has two rows to work on when they can see one")

    def test_fixqueue_reports_the_same_split(self, client, sample_fountain):
        name, _ = _project_with(client, sample_fountain, [GROUNDED, UNGROUNDED])
        data = client.get(f"/api/projects/{name}/fixqueue").get_json()

        assert data["total_count"] == 2
        assert data["ungrounded_count"] == 1
        assert data["grounded_count"] == 1
        assert data["grounded_count"] + data["ungrounded_count"] == data["total_count"]

    def test_the_two_routes_agree_on_the_split(self, client, sample_fountain):
        """One arithmetic, two shapes — the drift this register keeps finding."""
        name, _ = _project_with(client, sample_fountain, [GROUNDED, UNGROUNDED])
        fq = client.get(f"/api/projects/{name}/fixqueue").get_json()
        sm = client.get(f"/api/projects/{name}/findings/summary").get_json()
        assert fq["ungrounded_count"] == sm["ungrounded_count"]


class TestThePrecedenceMatchesTheDesk:
    """An ungrounded row the writer has already marked is NOT hidden — their
    own disposition puts it back in front of them. `findingCounts`/`queueCounts`
    in app.js exempt addressed/deferred rows from the groundedness toggle, and
    the served split has to use the same rule or the two disagree again."""

    def test_a_writer_marked_ungrounded_row_is_not_counted_as_hidden(
            self, client, sample_fountain):
        from screenplay_studio.revision import compute_finding_id
        marked_id = compute_finding_id(UNGROUNDED)
        name, _ = _project_with(client, sample_fountain, [GROUNDED, UNGROUNDED],
                                marks={marked_id: "addressed"})
        data = client.get(f"/api/projects/{name}/findings/summary").get_json()

        assert data["ungrounded_count"] == 1, "the row is still ungrounded"
        assert data["ungrounded_hidden_count"] == 0, (
            "a row the writer already marked was reported as hidden from them")

    def test_a_deferred_ungrounded_row_is_not_counted_as_hidden(
            self, client, sample_fountain):
        from screenplay_studio.revision import compute_finding_id
        marked_id = compute_finding_id(UNGROUNDED)
        name, _ = _project_with(client, sample_fountain, [GROUNDED, UNGROUNDED],
                                marks={marked_id: "deferred"})
        data = client.get(f"/api/projects/{name}/findings/summary").get_json()
        assert data["ungrounded_hidden_count"] == 0


class TestTheShippedDeskAlreadyLabelsItsScope:
    """A static pin on the behaviour I verified by reading (and executing the
    extracted helpers): the desk does not print an unlabelled count."""

    def test_the_mass_strip_discloses_the_filtered_remainder(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "screenplay_studio", "webapp", "app.js"),
            encoding="utf-8").read()
        assert '" open of " + m.total + " findings"' in src
        assert "shown by filter" in src, (
            "the mass strip lost its scope disclosure — it would again read as "
            "a claim about the filtered board below it")

    def test_an_ungrounded_row_with_no_writer_mark_is_filtered_out(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "screenplay_studio", "webapp", "app.js"),
            encoding="utf-8").read()
        assert "f.ungrounded && !state.fixQueueShowUngrounded" in src
        assert 'd !== "addressed" && d !== "deferred"' in src, (
            "the desk stopped exempting writer-dispositioned rows from the "
            "groundedness toggle — the served precedence would now disagree")
