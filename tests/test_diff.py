"""Tests for screenplay_studio.diff — draft snapshotting, activation, and
draft-to-draft diffing (structural + findings)."""

import io
import json
import os

import pytest

from screenplay_parser import parse_fountain, parse_screenplay
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator
from screenplay_studio import diff

import screenplay_studio.webapp_server as webapp_server


DRAFT2 = """Title: E2E Test Script
Author: Test

INT. STUDY - NIGHT

MARA unlocks a drawer and takes out an old REVOLVER, setting it on the desk.

MARA
Now I have to tell you the truth.

DEREK watches her, uneasy.

DEREK
Just don't do anything stupid.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table.

MARA
I promise I'll explain everything.

CUT TO:

INT. STUDY - NIGHT

The REVOLVER is still there, untouched.

MARA
Some things are better left alone.

CUT TO:

INT. GARAGE - DAY

Mara finds DEREK hiding behind the tool bench.

MARA
I thought you were gone.
"""


@pytest.fixture
def analyzed_manifest(tmp_path, sample_fountain, mock_server):
    m = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain)
    m.server_url = mock_server
    m.save()
    orch = Orchestrator(m)
    orch.run_parse()
    orch.run_analyze()
    return m


def _write_draft2(tmp_path, name="draft2.fountain"):
    p = tmp_path / name
    p.write_text(DRAFT2, encoding="utf-8")
    return str(p)


class TestSnapshotAndUpload:
    def test_upload_new_draft_snapshots_and_reparses(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        src = _write_draft2(tmp_path)
        diff.upload_new_draft(m, src, "draft2.fountain")

        assert m.active_draft == "draft-1"
        assert m.drafts[0]["name"] == "draft-1"
        assert m.source_filename == "draft2.fountain"
        # original snapshot exists and holds the OLD script
        original_parsed = diff.draft_parsed_path(m, "original")
        assert os.path.exists(original_parsed)
        # parse stage was re-queued (needs re-run on the new source)
        assert m.stage("parse").status == "pending"

    def test_reparse_after_upload(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        doc = diff._baseline_doc(m, "active")
        assert doc.scene_count == 4  # draft 2 added a scene

    def test_activate_draft_restores_files(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        diff.activate_draft(m, "original")
        assert m.active_draft == "original"
        doc = diff._baseline_doc(m, "active")
        assert doc.scene_count == 3
        assert any("tell you everything" in e.text for s in doc.scenes for e in s.elements)

    def test_activate_unknown_draft_raises(self, analyzed_manifest):
        with pytest.raises(ValueError):
            diff.activate_draft(analyzed_manifest, "ghost")


# ---------- R6-BE-3: switching drafts must never cost the writer a script ----------
# The docstring above `activate_draft` promises "switching is never destructive".
# These two are that promise, as files on disk: the draft you switch TO must have
# its own source text back, and the draft you switch AWAY from must keep its text
# even when it never parsed (the preserve step used to be gated on
# `parse == complete`, and the delete was unconditional).
ORIG_LINE = "I'll tell you everything when this is over."
D2_LINE = "Now I have to tell you the truth."


class TestActivatePreservesSource:
    def _read(self, path):
        assert os.path.exists(path), f"{os.path.basename(path)} is not on disk"
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_activate_restores_the_drafts_own_source_text(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        assert D2_LINE in self._read(m.source_path)

        diff.activate_draft(m, "original")
        # The snapshot holds "source.fountain"; activation used to look for the
        # uploaded filename instead, find nothing, and leave the project with no
        # source file at all (parsed.json restored, so the UI looked fine).
        assert ORIG_LINE in self._read(m.source_path)
        assert m.source_format == ".fountain"

    def test_switching_from_an_unparsed_draft_keeps_its_text(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        # deliberately no re-parse: the writer switches before the parse ran

        diff.activate_draft(m, "original")
        assert ORIG_LINE in self._read(m.source_path)
        preserved = os.path.join(diff.draft_dir(m, "draft-1"), "source.fountain")
        assert D2_LINE in self._read(preserved), (
            "draft-2's only copy was deleted while its parse was still pending")

    def test_a_snapshot_missing_its_source_does_not_delete_the_active_one(
            self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        # A damaged/older snapshot: parsed.json present, source file not.
        os.remove(os.path.join(diff.draft_dir(m, "original"), "source.fountain"))

        diff.activate_draft(m, "original")
        # The old code deleted the active source up front and then had nothing to
        # put back. Keeping the current file is wrong about which draft is active,
        # but recoverable; deleting it was not.
        assert D2_LINE in self._read(m.source_path)

    def test_the_restored_source_actually_parses(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        diff.activate_draft(m, "original")
        # A fresh parse is what the writer's Re-parse button does, and what the
        # next analyze needs. (Calling Orchestrator.run_parse() here would be a
        # no-op check: activate_draft leaves `parse` complete, so it returns
        # before ever opening the file — the missing source stayed invisible.)
        doc = parse_screenplay(m.source_path)
        assert doc.scene_count == 3


class TestStructuralDiff:
    def test_scene_diff_detects_added_changed(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        result = diff.diff_drafts(m, "original", "active")
        scenes = result["scenes"]
        assert scenes["added_scenes"] == [4]
        # scene 1's dialogue changed -> listed as changed
        changed_nums = [c["scene_number"] for c in scenes["changed_scenes"]]
        assert 1 in changed_nums
        scene1 = next(c for c in scenes["changed_scenes"] if c["scene_number"] == 1)
        assert any("tell you" in (l["old"] or "") for l in scene1["changed_lines"])

    def test_findings_diff_marks_resolved(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        Orchestrator(m).run_analyze()  # re-analyze the new draft

        result = diff.diff_drafts(m, "original", "active")
        summary = result["findings"]["summary"]
        # the dialogue finding's quote was changed -> resolved
        assert summary["resolved"] >= 1
        # theme/character findings with identical issues carried over
        assert summary["carried"] >= 1


class TestManifestDraftsPersistence:
    def test_drafts_survive_reload(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        reloaded = ProjectManifest.load(m.project_dir)
        assert reloaded.active_draft == "draft-1"
        assert reloaded.drafts[0]["source_filename"] == "draft2.fountain"


# ---------- webapp API ----------

@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Diff Test Script
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


def _upload(http_client, data, filename="script.fountain", title="Diff Test"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(data), filename), "title": title},
        content_type="multipart/form-data",
    )


class TestDraftApi:
    def test_upload_draft_flow(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")

        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active_draft"] == "draft-1"
        assert len(data["drafts"]) == 1
        # parse re-queued because the source changed
        assert data["stages"]["parse"] == "complete"  # run_parse ran inside the endpoint
        assert data["stages"]["analyze"] == "pending"

    def test_diff_endpoint_after_draft(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )
        http_client.post(f"/api/projects/{project}/analyze")

        resp = http_client.get(f"/api/projects/{project}/diff?from=original&to=active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["findings"]["summary"]["resolved"] >= 1
        assert data["scenes"]["added_scenes"] == [3, 4]  # SAMPLE_SCRIPT has 2 scenes; DRAFT2 has 4

    def test_activate_draft_api(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )

        resp = http_client.post(f"/api/projects/{project}/drafts/activate", json={"name": "original"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active_draft"] == "original"

        script = http_client.get(f"/api/projects/{project}/script").get_json()
        texts = [e["text"] for s in script["scenes"] for e in s["elements"]]
        assert "I'll tell you everything when this is over." in texts

    def test_diff_requires_known_draft(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/diff?from=ghost&to=active")
        assert resp.status_code == 400


# ---------- gap 62: a draft name is a name, not a path ----------
# `draft_dir` used to join a request-supplied name onto `drafts/` verbatim, so
# activating `../../Other/drafts/v2` from one project read a DIFFERENT project's
# snapshot, copied it over this project's active source and report, and stored
# the traversal string as `active_draft`. `/diff` and `/compare` took the same
# names in query params and served the other project's text with a 200.
#
# These tests are the attack, run against the real routes, plus the flows that
# must keep working: the app's own names are `original` and `draft-N`.

TRAVERSAL_NAMES = [
    "../../Other/drafts/v2",
    "../Other/drafts/v2",
    "..",
    "/etc/passwd",
    "draft 1",
    "a/b",
    "drafts/v2",
]


class TestDraftNameContainment:
    def test_draft_dir_refuses_a_path(self, analyzed_manifest):
        for bad in TRAVERSAL_NAMES:
            with pytest.raises(ValueError):
                diff.draft_dir(analyzed_manifest, bad)

    def test_draft_dir_accepts_the_names_the_app_makes(self, analyzed_manifest):
        for good in ("original", "draft-1", "draft-2", "Draft_3"):
            assert diff.draft_dir(analyzed_manifest, good).endswith(os.sep + good)

    def _project_with_a_revision(self, http_client, title="Diff Test"):
        """Upload a second draft so the project has a `drafts/` directory.

        This matters: `drafts/..` only resolves if `drafts` exists, so a project
        that has never been revised cannot be traversed through. Every writer
        past their first revision is in the vulnerable state; this fixture is
        therefore the ordinary one, not a contrived one.
        """
        project = _upload(http_client, SAMPLE_SCRIPT, title=title).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )
        assert os.path.isdir(os.path.join(webapp_server.PROJECTS_DIR, project, "drafts"))
        return project

    def _poisoned_neighbour(self, http_client):
        """A DIFFERENT project carrying a real, loadable snapshot at drafts/v2.

        `snapshot_active` only writes `parsed.json` once the parse stage is
        complete, so the neighbour is parsed first — otherwise the traversal
        target does not exist and an assertion of 400 would pass for the wrong
        reason (the first version of this test did exactly that).
        """
        other = _upload(http_client, DRAFT2.encode(), title="Other Project").get_json()["project"]
        other_dir = os.path.join(webapp_server.PROJECTS_DIR, other)
        Orchestrator(ProjectManifest.load(other_dir)).run_parse()
        diff.snapshot_active(ProjectManifest.load(other_dir), "v2")
        assert os.path.exists(os.path.join(other_dir, "drafts", "v2", "parsed.json")), \
            "the traversal target must exist, or this test proves nothing"
        return other, other_dir

    def test_activation_of_a_cross_project_name_is_refused(self, http_client):
        project = self._project_with_a_revision(http_client)
        other, other_dir = self._poisoned_neighbour(http_client)

        this_dir = os.path.join(webapp_server.PROJECTS_DIR, project)
        before_source = open(os.path.join(this_dir, "source.fountain"), "rb").read()

        cross = f"../../{other}/drafts/v2"
        for bad in TRAVERSAL_NAMES + [cross]:
            resp = http_client.post(
                f"/api/projects/{project}/drafts/activate", json={"name": bad}
            )
            assert resp.status_code == 400, (bad, resp.status_code, resp.get_json())

        # Nothing was copied over this project, and the name was not recorded.
        assert open(os.path.join(this_dir, "source.fountain"), "rb").read() == before_source
        assert ProjectManifest.load(this_dir).active_draft != cross

    def test_diff_and_compare_do_not_serve_another_project(self, http_client):
        project = TestDraftNameContainment._project_with_a_revision(self, http_client)
        other, other_dir = TestDraftNameContainment._poisoned_neighbour(self, http_client)
        cross = f"../../{other}/drafts/v2"

        for route in ("diff", "compare"):
            for query in (f"?from={cross}&to=active", f"?from=original&to={cross}"):
                resp = http_client.get(f"/api/projects/{project}/{route}{query}")
                assert resp.status_code == 400, (route, query, resp.status_code)
                # DRAFT2's opening line — present only if another project's
                # script was served.
                assert "unlocks a drawer" not in resp.get_data(as_text=True).lower()

    def test_the_normal_switch_still_works(self, http_client):
        """The fix must not cost the writer the switch it protects."""
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )
        first = http_client.post(
            f"/api/projects/{project}/drafts/activate", json={"name": "original"}
        )
        assert first.status_code == 200
        assert first.get_json()["active_draft"] == "original"

        second = http_client.post(
            f"/api/projects/{project}/drafts/activate", json={"name": "draft-1"}
        )
        assert second.status_code == 200
        assert second.get_json()["active_draft"] == "draft-1"


# ---------- gap 1: a draft switch must not destroy the writer's revisions ----------
# The UI calls switching non-destructive — the tooltip literally says switching
# preserves the current draft. It did not: `_reset_derived_state` deleted
# working.json + edits.json + edits.redo.json on every switch, so applying an
# edit, switching away and switching back restored the ORIGINAL text with no
# undo log and no redo stack. These tests drive the real revision module.


class TestSwitchPreservesEdits:
    def _apply_one_edit(self, m):
        from screenplay_studio import revision
        doc = revision.load_working(m)
        scene = doc.scenes[0]
        old = next(e.text for e in scene.elements if e.text.strip())
        result = revision.apply_edit(m, scene.scene_number, [{"old": old, "new": old + " EDITED"}])
        assert len(result["applied"]) == 1
        return old

    def test_edits_survive_switching_away_and_back(self, analyzed_manifest, tmp_path):
        from screenplay_studio import revision
        m = analyzed_manifest
        marker = self._apply_one_edit(m)
        assert revision.has_edits(m)
        drafts_before = len(revision.load_working(m).scenes)

        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        diff.activate_draft(m, "original")

        # The edit is back in the text...
        texts = [e.text for s in revision.load_working(m).scenes for e in s.elements]
        assert any(t.endswith("EDITED") for t in texts), "the applied edit was destroyed by the switch"
        # ...and so is the undo history, so the writer can still take it back.
        assert revision.has_edits(m)
        undo = revision.undo_last_edit(m)
        assert len(undo["restored"]) == 1 and not undo["failed"]
        texts = [e.text for s in revision.load_working(m).scenes for e in s.elements]
        assert marker in texts, "undo after a switch did not restore the original line"

    def test_a_never_edited_draft_does_not_inherit_an_undo_stack(self, analyzed_manifest, tmp_path):
        """The other half: restoring must not hand draft-2 an undo entry for text
        it never had."""
        from screenplay_studio import revision
        m = analyzed_manifest
        self._apply_one_edit(m)
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        # draft-1 (the upload) has never been edited.
        assert not revision.has_edits(m), "a fresh upload must not inherit the previous draft's log"
        with pytest.raises(Exception):
            revision.undo_last_edit(m)

    def test_redo_is_preserved_when_it_belongs_to_the_draft(self, analyzed_manifest, tmp_path):
        from screenplay_studio import revision
        m = analyzed_manifest
        self._apply_one_edit(m)
        revision.undo_last_edit(m)          # puts the edit on the redo stack
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        diff.activate_draft(m, "original")
        # Undo state came back with the draft, so redo can still run.
        assert os.path.exists(revision.edits_redo_path(m)), "the redo stack was lost with the switch"


# ---------- gap 63: the whole per-snapshot bundle moves with the draft ----------
# Restoring only parsed.json + the report pair left parsed.kg.json bound to the
# outgoing draft, so /characters described a script the writer was no longer
# looking at. Measured before the fix: switch back to the original draft and its
# own cast was gone.


BETA_SCRIPT = b"""Title: Beta

INT: VAULT - NIGHT

BETA STRANGER waits in the dark.

BETA STRANGER
Nobody follows me here.
"""


class TestSwitchRestoresTheWholeBundle:
    def test_characters_follow_the_draft(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        before = http_client.get(f"/api/projects/{project}/characters").get_json()["characters"]
        assert before, "the original draft must have a cast to lose"

        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(BETA_SCRIPT), "beta.fountain")},
            content_type="multipart/form-data",
        )
        http_client.post(f"/api/projects/{project}/analyze")

        assert http_client.post(
            f"/api/projects/{project}/drafts/activate", json={"name": "original"}
        ).status_code == 200
        after = http_client.get(f"/api/projects/{project}/characters").get_json()["characters"]
        names = {c.get("name") for c in after}
        assert names == {c.get("name") for c in before}, (
            f"switching back showed {names}, not the original draft's cast")
        assert "BETA STRANGER" not in names

    def test_a_draft_without_a_report_does_not_inherit_one(self, http_client):
        """The other direction: a member the snapshot lacks is removed live, not
        left over from the draft the writer came from."""
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(BETA_SCRIPT), "beta.fountain")},
            content_type="multipart/form-data",
        )
        # draft-1 was never analyzed, so switching to it must not serve a report.
        body = http_client.post(
            f"/api/projects/{project}/drafts/activate", json={"name": "draft-1"}
        ).get_json()
        assert body["stages"]["analyze"] != "complete"
        summary = http_client.get(f"/api/projects/{project}/findings/summary").get_json()
        assert summary.get("total_count", 0) == 0


# ---------- gap 65: no draft switch while an analysis is running ----------
# An analysis keeps publishing into whatever the active draft becomes, so a
# switch mid-run writes one draft's findings into another's report. The switch
# is now refused with 409 while the per-project analysis lock is held.


class TestNoSwitchDuringAnalysis:
    def test_activate_is_refused_while_an_analysis_runs(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        lock = webapp_server._analyze_lock(project)
        assert lock.acquire(blocking=False)
        try:
            resp = http_client.post(
                f"/api/projects/{project}/drafts/activate", json={"name": "original"}
            )
            assert resp.status_code == 409
            assert "analysis is running" in resp.get_json()["error"].lower()
        finally:
            lock.release()

    def test_upload_is_refused_while_an_analysis_runs(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        lock = webapp_server._analyze_lock(project)
        assert lock.acquire(blocking=False)
        try:
            resp = http_client.post(
                f"/api/projects/{project}/drafts",
                data={"file": (io.BytesIO(BETA_SCRIPT), "beta.fountain")},
                content_type="multipart/form-data",
            )
            assert resp.status_code == 409
        finally:
            lock.release()

    def test_switching_works_again_once_the_run_ends(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        lock = webapp_server._analyze_lock(project)
        lock.acquire(blocking=False)
        lock.release()
        resp = http_client.post(
            f"/api/projects/{project}/drafts/activate", json={"name": "original"}
        )
        assert resp.status_code in (200, 400)  # 400 = nothing to switch back to yet
        assert resp.status_code != 409


# ---------- gap 64: a bad upload must not become the active draft ----------
# Measured before the fix: a non-screenplay .fdx returned 500 but had already
# replaced the active draft — parse `failed`, edits discarded, analysis reset,
# the previous good report still on disk while /report answered 400, and /script
# refusing "Project hasn't been parsed yet" even after switching back, because
# activation left the FAILED status in place.


NOT_A_SCREENPLAY = b"\x00\x01\x02 this is not an fdx \xff\xfe"


class TestABadUploadCannotBecomeTheActiveDraft:
    def test_a_broken_upload_is_refused_and_changes_nothing(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        before = http_client.get(f"/api/projects/{project}/script").get_json()

        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(NOT_A_SCREENPLAY), "broken.fdx")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400, "a file that cannot be parsed is a client error"
        assert "broken.fdx" in resp.get_json()["error"]

        # The draft the writer was on is still the draft they are on, and the
        # script still reads.
        after = http_client.get(f"/api/projects/{project}/script").get_json()
        assert after == before
        assert http_client.get(f"/api/projects/{project}/report").status_code == 200
        drafts = http_client.get(f"/api/projects/{project}/drafts").get_json()
        assert all(d["name"] != "draft-1" for d in drafts.get("drafts", []))
        assert drafts.get("active_draft") is None  # still the writer's original

    def test_a_rejected_upload_does_not_survive_on_disk(self, http_client, tmp_path):
        """The quarantine temp file is removed — a rejected upload must not leave
        a half-valid source lying beside the good one."""
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(NOT_A_SCREENPLAY), "broken.fdx")},
            content_type="multipart/form-data",
        )
        project_dir = os.path.join(webapp_server.PROJECTS_DIR, project)
        leftovers = [n for n in os.listdir(project_dir) if n.startswith("_draft_upload")]
        assert leftovers == []

    @pytest.mark.parametrize("filename,body", [
        ("bad.fdx", NOT_A_SCREENPLAY),
        ("bad.pdf", b"%PDF this is not a real pdf"),
    ])
    def test_every_format_has_a_rejection_path(self, http_client, filename, body):
        """The gate is format-generic, not fdx-specific.

        `.fdx` and `.pdf` are the two formats that really do reject garbage.
        `.fountain`, `.txt` and `.md` are flat text: an empty one parses as a
        zero-scene script and is ACCEPTED — measured, not assumed. That is a
        product decision older than this gap (a blank file is a valid blank
        screenplay), so it is recorded here instead of being asserted away; the
        property this gap needs is only that a REJECTED upload never lands.
        """
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(body), filename)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert filename in resp.get_json()["error"]
        assert http_client.get(f"/api/projects/{project}/script").status_code == 200


class TestAParseFailureAfterTheSwapIsUndone:
    def test_the_writer_is_put_back_on_the_draft_they_had(self, http_client, monkeypatch):
        """The gate makes this rare, not impossible: a parse can fail on the
        second read. When it does, `upload_new_draft` has already swapped the
        source, so the writer is stranded unless we put them back."""
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        before = http_client.get(f"/api/projects/{project}/script").get_json()

        real_run = Orchestrator.run_parse
        calls = {"n": 0}

        def _fail_the_new_draft(self, *a, **kw):
            calls["n"] += 1
            raise RuntimeError("simulated parse failure after the swap")

        monkeypatch.setattr(Orchestrator, "run_parse", _fail_the_new_draft)
        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(BETA_SCRIPT), "beta.fountain")},
            content_type="multipart/form-data",
        )
        monkeypatch.setattr(Orchestrator, "run_parse", real_run)
        assert calls["n"] == 1, "the failure must come from the swapped-in draft"

        assert resp.status_code == 500
        assert "back on" in resp.get_json()["error"]
        after = http_client.get(f"/api/projects/{project}/script").get_json()
        assert after == before, "the writer must be on the draft they started on"
        assert http_client.get(f"/api/projects/{project}/report").status_code == 200


class TestActivationRestoresTheParseStage:
    def test_switching_back_brings_the_parse_stage_with_it(self, http_client):
        """A restored parse must not inherit the FAILED status of a later
        attempt. Measured before the fix: `/script` refused a draft whose
        parsed.json was sitting right there."""
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(BETA_SCRIPT), "beta.fountain")},
            content_type="multipart/form-data",
        )
        # Make the live parse stage genuinely `failed` — the state a bad upload
        # used to leave behind. Without the fix, activation restored parsed.json
        # but kept this status, so `/script` refused a draft whose parse was
        # sitting right there on disk.
        from screenplay_studio.manifest import StageStatus
        m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, project))
        m.stages["parse"] = StageStatus(status="failed", error="a parse that failed")
        m.save()

        assert http_client.post(
            f"/api/projects/{project}/drafts/activate", json={"name": "original"}
        ).status_code == 200
        # `/drafts` carries no stage map — read the project endpoint, which does.
        stage = http_client.get(f"/api/projects/{project}").get_json()["stages"]["parse"]
        assert stage == "complete", (
            "the snapshot's parse was complete, so the restored draft is parsed")
        assert http_client.get(f"/api/projects/{project}/script").status_code == 200


def test_a_damaged_stage_record_refuses_the_switch_without_moving(tmp_path, monkeypatch, mock_server):
    """Damage is not absence (the fault-injection contract, applied to this
    store): a truncated stage record must refuse the activation BEFORE the
    writer is moved, not apologise afterwards."""
    webapp_server.PROJECTS_DIR = str(tmp_path / "proj_api")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    client = webapp_server.app.test_client()

    project = _upload(client, SAMPLE_SCRIPT).get_json()["project"]
    client.post(f"/api/projects/{project}/analyze")
    client.post(
        f"/api/projects/{project}/drafts",
        data={"file": (io.BytesIO(BETA_SCRIPT), "beta.fountain")},
        content_type="multipart/form-data",
    )
    sidecar = diff.snapshot_stage_path(
        diff.draft_dir(ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, project)),
                       "original"))
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write('{"parse": "comp')  # crash-truncated

    before = client.get(f"/api/projects/{project}/script").get_json()
    resp = client.post(f"/api/projects/{project}/drafts/activate", json={"name": "original"})
    assert resp.status_code == 400
    assert "unreadable" in resp.get_json()["error"]
    assert client.get(f"/api/projects/{project}/script").get_json() == before
    active = client.get(f"/api/projects/{project}/drafts").get_json()["active_draft"]
    assert active == "draft-1", "a refused switch must not move the writer"


# ---------- gap 61: concurrent uploads must not share a staging file ----------
# Measured before the fix: the staging path was `_draft_upload.<ext>` — ONE name
# per project — so two uploads wrote each other's bytes and the loser's cleanup
# removed the winner's file mid-swap. With only the parse gate in place, the
# second upload died 400 and neither draft was recorded.


class TestConcurrentUploadsKeepTheirOwnFiles:
    def test_two_uploads_do_not_share_a_staging_file(self, http_client, monkeypatch):
        """Forced interleave at the seam the entry names: one upload pauses after
        saving its staging file while the other runs to completion."""
        import threading
        import time as _time

        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        resp = {"": None}
        real = webapp_server._validate_draft_upload

        def pause_for_A(path, filename):
            if filename.startswith("A"):
                _time.sleep(0.4)  # let B finish while A's staging file exists
            return real(path, filename)

        monkeypatch.setattr(webapp_server, "_validate_draft_upload", pause_for_A)
        out = {}

        def upload(tag, body):
            client = webapp_server.app.test_client()
            r = client.post(f"/api/projects/{project}/drafts",
                            data={"file": (io.BytesIO(body), f"{tag}.fountain")},
                            content_type="multipart/form-data")
            out[tag] = r.status_code

        a = threading.Thread(target=upload, args=("A", b"Title: A\n\nINT. ROOM - NIGHT\n\nALPHA only.\n"))
        a.start()
        _time.sleep(0.1)
        b = threading.Thread(target=upload, args=("B", b"Title: B\n\nINT. ROOM - NIGHT\n\nBETA only.\n"))
        b.start()
        a.join()
        b.join()

        assert out == {"A": 200, "B": 200}, f"an upload was lost: {out}"
        m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, project))
        assert len(m.drafts) == 2, f"both uploads must be recorded, got {m.drafts}"
        src = open(m.source_path, encoding="utf-8").read()
        # The active source holds the LAST writer's text, and the manifest names
        # that same file — the two must never disagree.
        if m.source_filename.startswith("A"):
            assert "ALPHA only." in src and "BETA only." not in src
        else:
            assert "BETA only." in src and "ALPHA only." not in src
        project_dir = os.path.join(webapp_server.PROJECTS_DIR, project)
        leftovers = [n for n in os.listdir(project_dir)
                     if n.startswith("_draft_upload") or n.endswith(".incoming")]
        assert leftovers == [], f"staging litter left behind: {leftovers}"
