"""Tests for screenplay_studio.revision — the revision loop backend.

Covers: working-copy lifecycle, line replacement matching (exact / fuzzy /
ambiguous / skip), model rewrite suggestions against the mock server, and
finding-resolution status (addressed / still_present / unknown).
"""

import json
import time

import pytest

from screenplay_parser import parse_fountain
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator
from screenplay_studio import revision
from screenplay_analyzer.llm_client import LlamaServerClient


@pytest.fixture
def manifest(tmp_path, sample_fountain, mock_server):
    m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
    m.server_url = mock_server
    m.save()
    Orchestrator(m).run_parse()
    return m


def _make_doc(sample_fountain):
    return parse_fountain(sample_fountain)


class TestWorkingCopy:
    def test_ensure_working_copies_parse(self, manifest):
        path = revision.ensure_working(manifest)
        assert path == revision.working_path(manifest)
        doc = revision.load_working(manifest)
        assert doc.scene_count == 3

    def test_has_edits_false_without_edits(self, manifest):
        revision.ensure_working(manifest)
        assert revision.has_edits(manifest) is False

    def test_reset_removes_working_copy(self, manifest):
        revision.ensure_working(manifest)
        revision.reset_working(manifest)
        assert not revision.has_edits(manifest)

    def test_working_copy_self_heals_after_reparse(self, manifest):
        # first view creates the working copy from the parse
        path = revision.ensure_working(manifest)
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
        # simulate a re-parse regenerating parsed.json (e.g. a parser fix)
        time.sleep(0.02)  # ensure a newer mtime
        Orchestrator(manifest).run_parse()
        path = revision.ensure_working(manifest)
        with open(path, "r", encoding="utf-8") as f:
            refreshed = f.read()
        assert refreshed == original  # same source -> same working copy

    def test_working_copy_preserved_when_edits_exist(self, manifest, sample_fountain):
        # a writer's applied edits must never be clobbered by a re-parse
        from screenplay_parser.models import ScriptDocument, Element, ElementType
        doc = revision.load_working(manifest)
        doc.scenes[0].elements.append(Element(type=ElementType.ACTION, text="Writers edit here."))
        revision.save_working(manifest, doc, record={"summary": "test edit"})
        with open(revision.working_path(manifest), "r", encoding="utf-8") as f:
            edited = f.read()
        assert "Writers edit here." in edited
        time.sleep(0.02)
        Orchestrator(manifest).run_parse()
        with open(revision.working_path(manifest), "r", encoding="utf-8") as f:
            after = f.read()
        assert "Writers edit here." in after


class TestApplyReplacements:
    def test_exact_match_applied(self, manifest):
        doc = revision.load_working(manifest)
        result = revision.apply_replacements(doc, 1, [
            {"old": "I'll tell you everything when this is over.", "new": "I'll tell you the truth."},
        ])
        assert len(result["applied"]) == 1
        assert result["skipped"] == []
        texts = [el.text for el in doc.scenes[0].elements]
        assert "I'll tell you the truth." in texts

    def test_fuzzy_match_applied(self, manifest):
        doc = revision.load_working(manifest)
        # slightly different wording — fuzzy match should still land
        result = revision.apply_replacements(doc, 1, [
            {"old": "I'll tell you everything when this is over", "new": "I'll tell you the truth."},
        ])
        assert len(result["applied"]) == 1

    def test_missing_line_skipped(self, manifest):
        doc = revision.load_working(manifest)
        result = revision.apply_replacements(doc, 1, [
            {"old": "This line does not exist anywhere.", "new": "x"},
        ])
        assert result["applied"] == []
        assert result["skipped"][0]["reason"] == "line not found in scene"

    def test_duplicate_line_ambiguous_skipped(self, manifest):
        doc = revision.load_working(manifest)
        # duplicate the dialogue line so exact matches are ambiguous
        scene = doc.scenes[0]
        for el in list(scene.elements):
            if el.type.value == "dialogue":
                from screenplay_parser.models import Element, ElementType
                scene.elements.append(Element(type=ElementType.DIALOGUE, text=el.text, character=el.character))
                break
        result = revision.apply_replacements(doc, 1, [
            {"old": "I'll tell you everything when this is over.", "new": "x"},
        ])
        assert result["applied"] == []
        assert "identical" in result["skipped"][0]["reason"]

    def test_multiline_old_skipped(self, manifest):
        doc = revision.load_working(manifest)
        result = revision.apply_replacements(doc, 1, [
            {"old": "line one\nline two", "new": "x"},
        ])
        assert result["skipped"][0]["reason"] == "old spans multiple lines"


class TestRewriteScene:
    def test_rewrite_proposes_replacements(self, manifest, mock_server):
        client = LlamaServerClient(base_url=mock_server)
        doc = revision.load_working(manifest)
        result = revision.rewrite_scene(client, doc, 1, finding_text="Dialogue is on the nose.")
        assert isinstance(result["replacements"], list)
        assert result["replacements"][0]["old"] == "I'll tell you everything when this is over."
        assert result["note"]

    def test_rewrite_does_not_apply(self, manifest, mock_server):
        client = LlamaServerClient(base_url=mock_server)
        doc = revision.load_working(manifest)
        revision.rewrite_scene(client, doc, 1)
        texts = [el.text for el in doc.scenes[0].elements]
        assert not any("[fixed]" in t for t in texts)


def _analyzed_manifest(tmp_path, sample_fountain, mock_server):
    m = ProjectManifest.create(str(tmp_path / "ana"), sample_fountain)
    m.server_url = mock_server
    m.save()
    orch = Orchestrator(m)
    orch.run_parse()
    orch.run_analyze()
    return m


class TestFindingStatuses:
    def _analyzed_manifest(self, tmp_path, sample_fountain, mock_server):
        return _analyzed_manifest(tmp_path, sample_fountain, mock_server)

    def test_addressed_when_quote_edited_out(self, tmp_path, sample_fountain, mock_server):
        m = self._analyzed_manifest(tmp_path, sample_fountain, mock_server)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        dialogue = [f for f in report["findings"] if f["category"] == "dialogue"]
        assert dialogue and dialogue[0]["evidence_quote"]  # mock provides a quote

        doc = revision.load_working(m)
        result = revision.apply_replacements(doc, 1, [
            {"old": dialogue[0]["evidence_quote"], "new": "I changed the line entirely now."},
        ])
        assert len(result["applied"]) == 1
        revision.save_working(m, doc, record={"scene_number": 1, "applied": result["applied"], "skipped": []})

        statuses = revision.finding_statuses(m)
        dialogue_idx = report["findings"].index(dialogue[0])
        by_index = {s["index"]: s for s in statuses["findings"]}
        assert by_index[dialogue_idx]["status"] == "addressed"
        assert statuses["summary"]["addressed"] >= 1

    def test_still_present_when_quote_untouched(self, tmp_path, sample_fountain, mock_server):
        m = self._analyzed_manifest(tmp_path, sample_fountain, mock_server)
        statuses = revision.finding_statuses(m)
        dialogue = [s for s in statuses["findings"] if s["category"] == "dialogue"]
        assert dialogue[0]["status"] == "still_present"

    def test_unknown_for_quote_less_findings(self, tmp_path, sample_fountain, mock_server):
        m = self._analyzed_manifest(tmp_path, sample_fountain, mock_server)
        statuses = revision.finding_statuses(m)
        unknown = [s for s in statuses["findings"] if s["status"] == "unknown"]
        # theme/character findings in the mock have evidence_quote=None
        assert any(s["category"] == "theme" for s in unknown)

    def test_statuses_empty_when_no_report(self, manifest):
        statuses = revision.finding_statuses(manifest)
        assert statuses["findings"] == []


# ---------- content-hash finding identity (R1-b, GO 1) ----------

class TestFindingIdentity:
    def test_id_stable_for_same_content(self):
        f = {"category": "character", "evidence_quote": "I'll tell you everything when this is over.", "severity": "high", "scene_refs": [1]}
        assert revision.compute_finding_id(f) == revision.compute_finding_id(dict(f))

    def test_id_survives_rescoring(self):
        # severity is a judgment about a note, not its identity
        f = {"category": "character", "evidence_quote": "I'll tell you everything when this is over.", "severity": "high"}
        g = {"category": "character", "evidence_quote": "I'll tell you everything when this is over.", "severity": "medium"}
        assert revision.compute_finding_id(f) == revision.compute_finding_id(g)

    def test_id_survives_scene_insert_shift(self):
        # scene_refs ride as data — renumbering must not orphan marks
        f = {"category": "character", "evidence_quote": "I'll tell you everything when this is over.", "scene_refs": [1]}
        g = {"category": "character", "evidence_quote": "I'll tell you everything when this is over.", "scene_refs": [3]}
        assert revision.compute_finding_id(f) == revision.compute_finding_id(g)

    def test_id_differs_across_category_or_quote(self):
        f = {"category": "character", "evidence_quote": "one"}
        g = {"category": "dialogue", "evidence_quote": "one"}
        h = {"category": "character", "evidence_quote": "two"}
        assert revision.compute_finding_id(f) != revision.compute_finding_id(g)
        assert revision.compute_finding_id(f) != revision.compute_finding_id(h)

    def test_no_quote_tier_deterministic(self):
        f = {"category": "theme", "issue": "The  theme  states   itself once."}
        g = {"category": "theme", "issue": "the theme states itself once."}
        assert revision.compute_finding_id(f) == revision.compute_finding_id(g)

    def test_statuses_carry_ids(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        statuses = revision.finding_statuses(m)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        for s, f in zip(statuses["findings"], report["findings"]):
            assert s["finding_id"] == revision.compute_finding_id(f)

    def test_dismiss_sticks_by_id_through_regenerated_report(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        f = report["findings"][0]
        fid = revision.compute_finding_id(f)
        revision.dismiss_finding(m, 0, f.get("issue") or "", fid)
        # the report regenerates: same content, NEW position (re-scoring reordered)
        moved = dict(f, severity="low")
        report2 = {"findings": [report["findings"][1], moved] + report["findings"][2:]}
        json.dump(report2, open(m.report_findings_path, "w", encoding="utf-8"))
        # legacy lookup is position-bound: the same content at a NEW index no
        # longer matches the writer's (index, issue) mark...
        new_issue = report2["findings"][0].get("issue") or ""
        assert (0, new_issue) not in revision.dismissed_issues(m)
        # ...but the id lookup DOES match — the writer's mark survives
        assert fid in revision.dismissed_finding_ids(m)

    def test_undismiss_by_id_and_legacy_index(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        f = report["findings"][0]
        fid = revision.compute_finding_id(f)
        revision.dismiss_finding(m, 0, f.get("issue") or "", fid)
        revision.undismiss_finding(m, 0, fid)
        assert fid not in revision.dismissed_finding_ids(m)
        # legacy entry (no id) still removed by index
        revision.dismiss_finding(m, 1, "legacy")
        revision.undismiss_finding(m, 1)
        data = json.load(open(m.project_dir + "/dismissed_findings.json", encoding="utf-8"))
        assert all(d.get("index") != 1 for d in data)


# ---------- writer intent + last-pass scorekeeping (GO 2) ----------

class TestFindingIntents:
    def test_set_get_clear_roundtrip(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        revision.set_finding_intent(m, "fabc123", "deferred")
        assert revision.finding_intents(m) == {"fabc123": "deferred"}
        revision.set_finding_intent(m, "fabc123", "addressed")
        assert revision.finding_intents(m) == {"fabc123": "addressed"}
        revision.set_finding_intent(m, "fabc123", None)
        assert revision.finding_intents(m) == {}

    def test_intents_survive_report_regeneration(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        revision.set_finding_intent(m, "fabc123", "deferred")
        # the report regenerates (re-scored, renumbered) — the id key holds
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        report["findings"][0]["severity"] = "low"
        json.dump(report, open(m.report_findings_path, "w", encoding="utf-8"))
        assert revision.finding_intents(m) == {"fabc123": "deferred"}

    def test_intents_missing_file_is_empty(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        assert revision.finding_intents(m) == {}


class TestLastPass:
    def test_first_pass_returns_none(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        assert revision.last_pass_snapshot(m) is None

    def test_second_pass_arithmetic(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        old = report["findings"]
        assert revision.last_pass_snapshot(m) is None  # snapshot seeds, no arithmetic yet
        # second pass: keep findings 0 and 2 as-is, drop finding 1 (fixed),
        # add one brand-new finding (re-scored finding 0 keeps its id = still live)
        kept = [old[0], old[2]]
        fresh = dict(old[1], issue="A brand new observation entirely.", evidence_quote=None)
        report["findings"] = kept + [fresh]
        json.dump(report, open(m.report_findings_path, "w", encoding="utf-8"))
        lp = revision.last_pass_snapshot(m)
        assert lp is not None
        assert lp["last_total"] == len(old)
        assert lp["still_live"] == 2
        assert lp["fixed"] == len(old) - 2  # everything seeded but not kept
        assert lp["new"] == 1

    def test_idempotent_reads(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        report["findings"] = report["findings"][:1]
        json.dump(report, open(m.report_findings_path, "w", encoding="utf-8"))
        first = revision.last_pass_snapshot(m)
        second = revision.last_pass_snapshot(m)  # same mtime — served from the guard
        assert first == second

    def test_ghosted_marks_report_writer_intent(self, tmp_path, sample_fountain, mock_server):
        m = _analyzed_manifest(tmp_path, sample_fountain, mock_server)
        report = json.load(open(m.report_findings_path, encoding="utf-8"))
        revision.last_pass_snapshot(m)  # seed: this pass has been seen
        gone = report["findings"][0]
        gid = revision.compute_finding_id(gone)
        revision.set_finding_intent(m, gid, "addressed")
        report["findings"] = report["findings"][1:]  # the marked finding transformed away
        json.dump(report, open(m.report_findings_path, "w", encoding="utf-8"))
        lp = revision.last_pass_snapshot(m)
        assert lp["fixed"] >= 1  # the marked finding is among the transformed
        assert any(g["finding_id"] == gid and g["intent"] == "addressed" for g in lp["ghosted_marks"])
