"""
Gap 12: two findings can share an id while asserting OPPOSITE things, and then
one verdict covers both.

Reproduced first: two findings with the same category, quote and scene and
opposite `issue` text both computed `fyrjq3y`. The writer could mark one
"incorrect" and had no way to say the other was right.

The obvious fix -- fold the claim into `compute_finding_id` -- is WRONG, and the
suite said so immediately: three pre-existing tests assert that a quoted
finding's id SURVIVES the model re-wording its `issue`, because that is what
keeps a verdict attached across a re-analysis (the model rewords constantly).
Re-keying every finding on its prose would orphan every mark on every run --
a far worse defect than the collision it fixes.

So the fix is conditional. Ids are untouched; a store key is claim-scoped ONLY
for findings that actually collide in the current report; and a verdict stored
under the bare id before the collision appeared is shown as a QUESTION rather
than applied to both rows. These tests pin all four properties, including the
ones that must not change.
"""

from screenplay_studio import revision


A = {"category": "dialogue", "evidence_quote": "Light banchey!",
     "scene_key": "int house day", "scene_refs": [4],
     "issue": "The line is on-the-nose: Ravi says exactly what he feels."}
B = {"category": "dialogue", "evidence_quote": "Light banchey!",
     "scene_key": "int house day", "scene_refs": [4],
     "issue": "The joke undercuts the grief the scene just built."}
SOLO = {"category": "dialogue", "evidence_quote": "A different line entirely.",
        "scene_key": "int house day", "scene_refs": [4],
        "issue": "Whatever the model says this time."}


class TestTheCollisionIsReal:

    def test_opposite_claims_still_share_a_plain_id(self):
        # Not a defect by itself -- this is what makes verdicts survive a
        # re-analysis, and it is pinned by test_finding_verdict_channel.py.
        assert revision.compute_finding_id(A) == revision.compute_finding_id(B)

    def test_the_two_rows_get_distinct_store_keys(self):
        keys = revision.finding_store_keys([A, B])
        assert len(set(keys)) == 2, "colliding rows still share one verdict key"
        assert all(k.startswith(revision.compute_finding_id(A)) for k in keys), (
            "a claim-scoped key must extend the plain id, not replace it")


class TestNothingElseIsReKeyed:

    def test_a_report_with_no_collision_keeps_every_plain_id(self):
        keys = revision.finding_store_keys([SOLO])
        assert keys == [revision.compute_finding_id(SOLO)]

    def test_a_verdict_written_before_this_change_still_resolves(self):
        f = SOLO
        pid = revision.compute_finding_id(f)
        verdict, ambiguous = revision.resolve_verdict(f, {pid: "correct"})
        assert verdict == "correct" and ambiguous is None, (
            "an existing verdict stopped resolving -- every stored mark would "
            "disappear on upgrade")

    def test_the_id_itself_survives_a_reworded_issue(self):
        # The property the naive fix broke. Guarded here too, because this file
        # is where someone will next be tempted to touch compute_finding_id.
        reworded = dict(A, issue="Completely different words this time.")
        assert revision.compute_finding_id(reworded) == revision.compute_finding_id(A)


class TestEachRowCanBeJudgedSeparately:

    def test_a_scoped_verdict_resolves_to_its_own_row(self):
        keys = revision.finding_store_keys([A, B])
        verdicts = {keys[0]: "incorrect", keys[1]: "correct"}
        assert revision.resolve_verdict(A, verdicts, collides=True) == ("incorrect", None)
        assert revision.resolve_verdict(B, verdicts, collides=True) == ("correct", None)

    def test_judging_one_row_does_not_judge_the_other(self):
        keys = revision.finding_store_keys([A, B])
        verdicts = {keys[0]: "incorrect"}
        assert revision.resolve_verdict(A, verdicts, collides=True)[0] == "incorrect"
        assert revision.resolve_verdict(B, verdicts, collides=True)[0] is None, (
            "one row's verdict leaked onto the opposite claim -- the filed defect")

    def test_a_bare_verdict_on_a_collision_is_shown_as_a_question(self):
        # The writer judged something here before the split. We do not know
        # which row, so we neither apply it twice nor forget it.
        pid = revision.compute_finding_id(A)
        for row in (A, B):
            verdict, ambiguous = revision.resolve_verdict(row, {pid: "correct"},
                                                          collides=True)
            assert verdict is None, "an ambiguous verdict was applied to a row"
            assert ambiguous == {"finding_id": pid, "verdict": "correct"}, (
                "an ambiguous verdict was dropped instead of surfaced")

    def test_no_stored_verdict_means_no_ambiguity(self):
        assert revision.resolve_verdict(A, {}, collides=True) == (None, None)

    def test_a_damaged_verdict_value_is_ignored_on_the_scoped_path_too(self):
        keys = revision.finding_store_keys([A, B])
        assert revision.resolve_verdict(A, {keys[0]: "garbage"}, collides=True)[0] is None


# ---------------------------------------------------------------- over HTTP
# The desk cannot infer a collision from the store: it depends on which findings
# the CURRENT report contains. So the server serves the per-row store keys on
# the edits fetch it already makes, and the desk asks with those.

import pytest  # noqa: E402

from screenplay_studio.manifest import ProjectManifest  # noqa: E402


@pytest.fixture
def colliding(tmp_path, sample_fountain, monkeypatch):
    import json as _json

    import screenplay_studio.webapp_server as webapp_server

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server.app.config["TESTING"] = True
    m = ProjectManifest.create(str(root / "p1"), sample_fountain)
    m.save()
    with open(m.report_findings_path, "w", encoding="utf-8") as fh:
        _json.dump({"findings": [A, B]}, fh)
    m.mark_complete("analyze")
    return webapp_server.app.test_client(), m


class TestTheDeskIsGivenDistinctKeys:

    def test_the_edits_fetch_serves_one_key_per_colliding_row(self, colliding):
        client, _m = colliding
        body = client.get("/api/projects/p1/findings/verdicts").get_json()
        keys = body.get("finding_claim_keys")
        assert keys and len(keys) == 2, "the collision was not disclosed to the desk"
        assert len(set(keys)) == 2, "both rows were given the same key -- the defect"
        assert body.get("ambiguous_verdicts") == {}

    def test_a_single_row_report_serves_its_plain_id(self, tmp_path, sample_fountain,
                                                     monkeypatch):
        import json as _json

        import screenplay_studio.webapp_server as webapp_server

        root = tmp_path / "projects2"
        root.mkdir()
        monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
        webapp_server.app.config["TESTING"] = True
        m = ProjectManifest.create(str(root / "p2"), sample_fountain)
        m.save()
        with open(m.report_findings_path, "w", encoding="utf-8") as fh:
            _json.dump({"findings": [SOLO]}, fh)
        m.mark_complete("analyze")
        client = webapp_server.app.test_client()
        body = client.get("/api/projects/p2/findings/verdicts").get_json()
        assert body["finding_claim_keys"] == [revision.compute_finding_id(SOLO)]

    def test_a_verdict_can_be_recorded_against_one_colliding_row(self, colliding):
        client, m = colliding
        keys = client.get("/api/projects/p1/findings/verdicts").get_json()["finding_claim_keys"]
        r = client.post("/api/projects/p1/findings/verdict",
                        json={"finding_id": keys[1], "verdict": "incorrect"})
        assert r.status_code in (200, 204), r.get_data(as_text=True)
        stored = revision.finding_verdicts(m)
        verdict, _amb = revision.resolve_verdict(A, stored, collides=True)
        assert verdict is None, "the verdict leaked onto the opposite claim"
        verdict_b, _amb = revision.resolve_verdict(B, stored, collides=True)
        assert verdict_b == "incorrect"

    def test_a_legacy_bare_verdict_is_served_as_ambiguous(self, colliding):
        client, m = colliding
        pid = revision.compute_finding_id(A)
        revision.set_finding_verdict(m, pid, "correct")
        body = client.get("/api/projects/p1/findings/verdicts").get_json()
        assert body["ambiguous_verdicts"] == {pid: "correct"}, (
            "a verdict whose target is unknowable was silently applied or lost")
