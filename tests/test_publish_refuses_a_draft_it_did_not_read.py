"""A run must not publish a reading of a script that is no longer on screen.

Gap 65, filed grade A: an analysis already running can publish findings for the
draft it started on after the writer has switched drafts. Gap 4 built the
compare-and-publish guard most of the way; this file pins the part that was
still open, which is the part that matters most because it is the part that
fails silently.

The hole was an inverted conditional in `publish_generation`:

    try:
        live_digest = document_digest(load_working(m))
    except Exception:
        live_digest = None
    if live_digest is not None and man.get("digest") != live_digest:
        raise ValueError(...)

When the live draft could not be read the check was SKIPPED and the run
published anyway. "I could not verify the draft" was treated as "the draft is
fine" — and an unreadable working copy is exactly the state a concurrent writer
or an interrupted cycle produces, so the guard evaporated precisely when the
project was least healthy.

The invariant asserted here: **publication happens only when the draft has been
read and it matches what the run analysed.** Unverifiable is a refusal, and the
refusal says which of the two happened so the writer is not sent looking for a
draft switch that never occurred.
"""

from __future__ import annotations

import json
import os

import pytest

from screenplay_parser import parse_screenplay
from screenplay_studio import report_generation, revision
from screenplay_studio.manifest import ProjectManifest
from screenplay_analyzer.report import document_digest

DRAFT_A = b"""Title: Draft A
Author: Test

INT. ROOM - DAY

MARA speaks the OLD line.
"""

DRAFT_B = b"""Title: Draft B
Author: Test

INT. KITCHEN - NIGHT

TOM speaks the NEW line.
"""


def _result(quote, doc):
    """A real AnalysisResult, not a hand-rolled stub.

    `save_report` reads a dozen fields off it, and a fake that drifts from the
    real dataclass fails for reasons that have nothing to do with publishing.
    """
    from screenplay_analyzer.pipeline import AnalysisResult
    return AnalysisResult(
        doc=doc,
        findings=[{"id": "f1", "category": "dialogue", "quote": quote,
                   "issue": "flat", "scene_number": 1}])


def _project(tmp_path, script=DRAFT_A):
    src = tmp_path / "a.fountain"
    src.write_bytes(script)
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="Publish")
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    revision.ensure_working(m)
    return m


def _stage(m, gen_dir, digest, doc, quote):
    report_generation.stage_generation(_result(quote, doc), gen_dir, m, digest, doc)
    return gen_dir


def _switch_draft(m, tmp_path, script=DRAFT_B):
    """Replace the script the way an upload does: new parse, new working copy.

    Re-read from disk first, because that is what the switch route does — the
    running analysis is holding its own older manifest object.
    """
    fresh = ProjectManifest.load(m.project_dir)
    src = tmp_path / "b.fountain"
    src.write_bytes(script)
    parse_screenplay(str(src)).save(fresh.parsed_path)
    revision.reset_working(fresh)
    fresh.save()


def test_a_reading_of_the_previous_draft_is_refused(tmp_path):
    """The filed defect: publish after the script on screen changed."""
    m = _project(tmp_path)
    run_doc = revision.load_working(m)
    run_digest = document_digest(run_doc)
    gen = _stage(m, report_generation.new_generation_dir(m, run_digest),
                 run_digest, run_doc, "MARA speaks the OLD line.")

    _switch_draft(m, tmp_path)

    with pytest.raises(ValueError) as exc:
        report_generation.publish_generation(m, gen)
    assert "draft changed" in str(exc.value).lower()

    # and nothing from the refused run reached the live paths
    assert not os.path.exists(m.report_md_path), \
        "a refused publication still wrote the live report"


def test_an_unreadable_draft_is_refused_not_waved_through(tmp_path, monkeypatch):
    """The fail-open: 'cannot verify' must not mean 'verified'.

    Damage the stored document so `load_working` raises, then publish. Before
    the fix the digest came back None, the comparison was skipped, and the
    findings were published over whatever was on the desk.
    """
    m = _project(tmp_path)
    run_doc = revision.load_working(m)
    run_digest = document_digest(run_doc)
    gen = _stage(m, report_generation.new_generation_dir(m, run_digest),
                 run_digest, run_doc, "MARA speaks the OLD line.")

    with open(revision.working_path(m), "w", encoding="utf-8") as f:
        f.write("{ this is not a script")

    with pytest.raises(ValueError) as exc:
        report_generation.publish_generation(m, gen)
    message = str(exc.value).lower()
    assert "could not" in message or "unreadable" in message, (
        f"an unreadable draft must be refused with its own reason, not a "
        f"draft-switch story: {exc.value!r}")
    assert not os.path.exists(m.report_md_path), \
        "a run published while the draft could not be verified"


def test_a_reading_of_the_current_draft_still_publishes(tmp_path):
    """The guard must not become a wall: the ordinary case still works."""
    m = _project(tmp_path)
    run_doc = revision.load_working(m)
    run_digest = document_digest(run_doc)
    gen = _stage(m, report_generation.new_generation_dir(m, run_digest),
                 run_digest, run_doc, "MARA speaks the OLD line.")

    report_generation.publish_generation(m, gen)

    assert os.path.exists(m.report_md_path)
    pointer = report_generation.current_generation(m)
    assert pointer["digest"] == run_digest
    with open(m.report_findings_path, "r", encoding="utf-8") as f:
        assert json.load(f)["snapshot"]["digest"] == run_digest


def test_the_refusal_names_the_draft_the_run_actually_read(tmp_path):
    """A writer told 'the draft changed' should be able to tell WHICH one."""
    m = _project(tmp_path)
    run_doc = revision.load_working(m)
    run_digest = document_digest(run_doc)
    gen = _stage(m, report_generation.new_generation_dir(m, run_digest),
                 run_digest, run_doc, "MARA speaks the OLD line.")
    _switch_draft(m, tmp_path)

    try:
        report_generation.publish_generation(m, gen)
    except ValueError as e:
        assert "again" in str(e).lower(), (
            "the refusal must say what to do next, not only what went wrong")
    else:
        pytest.fail("publication was allowed after the draft changed")


def test_the_previous_reading_survives_a_refused_run(tmp_path):
    """Gap 3's promise, re-asserted under gap 65's condition: a refused run
    must leave the last good reading exactly where it was."""
    m = _project(tmp_path)
    first_doc = revision.load_working(m)
    first_digest = document_digest(first_doc)
    first_gen = _stage(m, report_generation.new_generation_dir(m, first_digest),
                       first_digest, first_doc, "MARA speaks the OLD line.")
    report_generation.publish_generation(m, first_gen)
    good_pointer = report_generation.current_generation(m)

    _switch_draft(m, tmp_path)

    # a second run staged from the OLD digest publishes nothing
    with pytest.raises(ValueError):
        report_generation.publish_generation(m, first_gen)

    assert report_generation.current_generation(m) == good_pointer, (
        "the pointer moved on behalf of a refused run")


# ---------------------------------------------------------------------------
# a run publishes only what it staged
# ---------------------------------------------------------------------------

def test_a_missing_artifact_refuses_instead_of_moving_the_pointer(tmp_path):
    """An incomplete generation must not become the live reading.

    The old shape skipped a missing artifact and still wrote the pointer, so
    `/report` followed a pointer to a generation whose files were never copied.
    """
    m = _project(tmp_path)
    doc = revision.load_working(m)
    digest = document_digest(doc)
    gen = _stage(m, report_generation.new_generation_dir(m, digest),
                 digest, doc, "MARA speaks the OLD line.")
    os.unlink(os.path.join(gen, "report.md"))

    with pytest.raises(ValueError) as exc:
        report_generation.publish_generation(m, gen)
    assert "missing" in str(exc.value).lower()
    assert report_generation.current_generation(m) is None, \
        "the pointer moved on behalf of a generation that was never copied"


def test_a_manifest_naming_a_file_outside_its_folder_is_refused(tmp_path):
    """A reading can only publish files it staged.

    The live paths were derived from the manifest's relative names while the
    sources were joined to the generation directory, so a name escaping that
    directory would have copied an unrelated project file into the report.
    """
    m = _project(tmp_path)
    doc = revision.load_working(m)
    digest = document_digest(doc)
    gen = _stage(m, report_generation.new_generation_dir(m, digest),
                 digest, doc, "MARA speaks the OLD line.")

    manifest_path = os.path.join(gen, "generation.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        man = json.load(f)
    man["markdown"] = os.path.join("..", "..", "parsed.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(man, f)

    with pytest.raises(ValueError) as exc:
        report_generation.publish_generation(m, gen)
    assert "outside its own folder" in str(exc.value)
    assert not os.path.exists(m.report_md_path)
