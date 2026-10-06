"""A chunk that exhausted its retry ladder and was rescued by splitting used to
be invisible at the run level.

`_with_chunk_backoff` (pipeline.py) catches a LlamaServerError, halves the chunk
and retries the halves. When the halves succeed, no error is recorded — so a run
could report `dialogue: "ok"` with an empty `errors` list while a call burned all
three attempts and threw its response body away. Measured on qwen3.6 / Pain_3:
two dialogue calls exhausted their ladders and the pass still read "ok".

The recovery is deliberately NOT an error. The scenes were analysed, so the pass
did not fail and must not be reported as failed — `category_outcomes` is what the
resume path keys on. But a split is not nothing either: it re-asks the scenes, and
the same input was measured to yield 8 findings unsplit vs 12 split. So it gets its
own channel, and these tests pin all three properties:

  * a rescued split is recorded as a RECOVERY, separately from errors;
  * a split never flips `category_outcomes` to "failed";
  * a terminal failure stays an error and is never mislabelled a recovery;
  * the note reaches `result.errors` — the surface the desk actually renders.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_analyzer import pipeline  # noqa: E402
from screenplay_analyzer.llm_client import LlamaServerError  # noqa: E402
from screenplay_parser import parse_fountain  # noqa: E402

SAMPLE = """INT. WORKSHOP - NIGHT

MARA (30) stands at the bench, a broken loom in her hands.

MARA
Fix it or bury it. Those are the two.

RAVI
Then we bury it.

INT. WORKSHOP - LATER

MARA welds the frame shut. Sparks. She does not look up.
"""


def _scenes(n):
    return [{"scene_number": i + 1} for i in range(n)]


def _parse(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 1. the unit: a split is a recovery, a terminal failure is an error
# ---------------------------------------------------------------------------

def test_a_rescued_split_is_recorded_as_a_recovery_not_an_error():
    """The exact shape the run-level silence came from: the whole chunk raises,
    the halves succeed."""
    def call(chunk):
        if len(chunk) > 1:
            raise LlamaServerError("reply hit the output limit")
        return [{"scene_number": chunk[0]["scene_number"]}]

    recoveries = []
    results, errors = pipeline._with_chunk_backoff(_scenes(2), call, recoveries=recoveries)

    assert errors == [], "a rescued split was reported as an error"
    assert len(results) == 2, "the halves did not both come back"
    assert len(recoveries) == 1, f"the split left no trace: {recoveries}"
    assert recoveries[0]["scenes"] == [1, 2]
    assert recoveries[0]["size"] == 2
    assert "output limit" in recoveries[0]["error"]


def test_a_terminal_failure_is_an_error_and_not_a_recovery():
    """A single scene that still fails is a genuine failure: it must stay an
    error, and it must not be dressed up as a recovery."""
    def call(chunk):
        raise LlamaServerError("server down regardless of size")

    recoveries = []
    results, errors = pipeline._with_chunk_backoff(_scenes(1), call, recoveries=recoveries)

    assert results == []
    assert len(errors) == 1 and "Scene 1" in errors[0]
    assert recoveries == [], "a terminal failure was mislabelled a recovery"


def test_the_accumulator_is_optional_so_existing_callers_are_unaffected():
    """`recoveries` defaults to None; a caller that does not want the ledger
    still gets the old two-tuple and the old behaviour."""
    def call(chunk):
        if len(chunk) > 1:
            raise LlamaServerError("boom")
        return [{"scene_number": chunk[0]["scene_number"]}]

    results, errors = pipeline._with_chunk_backoff(_scenes(2), call)
    assert errors == [] and len(results) == 2


def test_the_note_names_the_pass_and_the_scenes_and_says_it_is_not_a_skip():
    note = pipeline._chunk_recovery_note("Dialogue analysis", [{"scenes": [4, 5, 6], "size": 3}])
    assert note is not None
    assert "Dialogue analysis" in note
    assert "4\u20136" in note, f"the scenes are not named: {note}"
    assert "Nothing was skipped" in note, (
        "the note must not read as a failure — the scenes WERE analysed")
    assert pipeline._chunk_recovery_note("Dialogue analysis", []) is None


# ---------------------------------------------------------------------------
# 2. the wiring: analyze() must record it, and must not fail the pass
# ---------------------------------------------------------------------------

class FlakyDialogueClient:
    """Raises on the first call — forcing `_with_chunk_backoff` to split — and
    answers with valid JSON afterwards."""

    def __init__(self):
        self.calls = 0

    def resolve_model(self, requested=None):
        return "stub-model"

    def chat_json(self, system, user, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise LlamaServerError("reply hit the output limit")
        return {"findings": []}


def test_analyze_records_a_split_without_failing_the_pass(monkeypatch):
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "0")
    client = FlakyDialogueClient()
    doc = _parse(SAMPLE)

    result = pipeline.analyze(doc, client, run_categories=("dialogue",), progress_cb=None,
                              integrity_gate=False, observation_pass=False)

    assert client.calls > 1, "the chunk was never split, so this proved nothing"
    assert result.category_outcomes.get("dialogue") == "ok", (
        "a rescued split was reported as a failed pass")
    notes = [e for e in result.errors if "re-run in smaller pieces" in e]
    assert notes, f"the split stayed invisible at the run level: {result.errors}"
    assert "Dialogue analysis" in notes[0]


def test_a_clean_run_records_no_recovery_note(monkeypatch):
    """The note must be evidence, not decoration: nothing split, nothing said."""
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "0")

    class CleanClient:
        def resolve_model(self, requested=None):
            return "stub-model"

        def chat_json(self, system, user, **kwargs):
            return {"findings": []}

    doc = _parse(SAMPLE)
    result = pipeline.analyze(doc, CleanClient(), run_categories=("dialogue",),
                              progress_cb=None, integrity_gate=False, observation_pass=False)

    assert not [e for e in result.errors if "re-run in smaller pieces" in e], (
        f"a clean run claimed a split: {result.errors}")
