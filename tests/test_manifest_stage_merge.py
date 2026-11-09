"""Gap 74/75: separately loaded manifests merge a stage at field/key granularity."""

import json

from screenplay_studio import jsonio
from screenplay_studio.manifest import ProjectManifest


def _project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "source.fountain"
    source.write_text("INT. ROOM - DAY\n\nA person waits.\n", encoding="utf-8")
    return ProjectManifest.create(str(root), str(source), title="Stage merge")


def test_different_scalar_fields_in_one_stage_survive_separate_saves(tmp_path):
    initial = _project(tmp_path)
    first = ProjectManifest.load(initial.project_dir)
    second = ProjectManifest.load(initial.project_dir)

    first.stage("analyze").status = "complete"
    first.save()
    second.stage("analyze").error = "diagnostic from peer"
    second.save()

    stage = ProjectManifest.load(initial.project_dir).stage("analyze")
    assert stage.status == "complete"
    assert stage.error == "diagnostic from peer"


def test_disjoint_output_path_keys_survive_separate_saves(tmp_path):
    initial = _project(tmp_path)
    first = ProjectManifest.load(initial.project_dir)
    second = ProjectManifest.load(initial.project_dir)

    first.stage("analyze").output_paths["category_a"] = "a.json"
    first.save()
    second.stage("analyze").output_paths["category_b"] = "b.json"
    second.save()

    paths = ProjectManifest.load(initial.project_dir).stage("analyze").output_paths
    assert paths == {"category_a": "a.json", "category_b": "b.json"}


def test_same_output_path_key_uses_last_successful_save(tmp_path):
    initial = _project(tmp_path)
    initial.stage("analyze").output_paths["report"] = "old.json"
    initial.save()
    first = ProjectManifest.load(initial.project_dir)
    second = ProjectManifest.load(initial.project_dir)

    first.stage("analyze").output_paths["report"] = "first.json"
    first.save()
    second.stage("analyze").output_paths["report"] = "second.json"
    second.save()

    assert ProjectManifest.load(initial.project_dir).stage("analyze").output_paths == {
        "report": "second.json"
    }


def test_output_path_deletion_removes_unchanged_baseline_value(tmp_path):
    initial = _project(tmp_path)
    initial.stage("analyze").output_paths["stale"] = "old.json"
    initial.save()
    writer = ProjectManifest.load(initial.project_dir)

    writer.stage("analyze").output_paths.pop("stale")
    writer.save()

    assert "stale" not in ProjectManifest.load(initial.project_dir).stage(
        "analyze").output_paths


def test_stale_deletion_does_not_erase_a_peers_newer_value(tmp_path):
    initial = _project(tmp_path)
    initial.stage("analyze").output_paths["report"] = "old.json"
    initial.save()
    stale = ProjectManifest.load(initial.project_dir)
    peer = ProjectManifest.load(initial.project_dir)

    peer.stage("analyze").output_paths["report"] = "new.json"
    peer.save()
    stale.stage("analyze").output_paths.pop("report")
    stale.save()

    assert ProjectManifest.load(initial.project_dir).stage("analyze").output_paths == {
        "report": "new.json"
    }


def test_synthesized_missing_stage_is_baseline_not_an_implicit_reset(tmp_path):
    initial = _project(tmp_path)
    path = initial.manifest_path
    with open(path, encoding="utf-8") as stream:
        raw = json.load(stream)
    raw["stages"].pop("analyze")
    jsonio.atomic_write_json(path, raw)

    stale = ProjectManifest.load(initial.project_dir)
    peer = ProjectManifest.load(initial.project_dir)
    peer.stage("analyze").status = "complete"
    peer.save()
    stale.title = "A title edited from the old manifest"
    stale.save()

    assert ProjectManifest.load(initial.project_dir).stage("analyze").status == "complete"
