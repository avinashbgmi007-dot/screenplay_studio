"""A chunk that exhausted its retry ladder and was rescued by splitting used to
be invisible at the run level.

`_with_chunk_backoff` (pipeline.py) catches a LlamaServerError, halves the chunk
and retries the halves. When the halves succeed, no error is recorded — so a run
could report `dialogue: "ok"` with an empty `errors` list while a call burned all
three attempts and threw its response body away. Measured on qwen3.6 / Pain_3:
two dialogue calls exhausted their ladders and the pass still read "ok".

The first fix recorded the split in `result.errors`. That was wrong: `errors`
feeds the orchestrator's partial-failure path (`orchestrator.py:169-176`) and the
desk's failure banner (`app.js:7221`), so a healthy run got dressed as a broken
one — the banner literally said "passes reported a problem". The notes now go to
`AnalysisResult.recoveries`, a caveat channel of its own.

These tests pin the whole contract:

  * a rescued split is recorded as a RECOVERY, and never as an error;
  * a split never flips `category_outcomes` to "failed";
  * a terminal failure stays an error and is never mislabelled a recovery;
  * the note reaches `result.recoveries` — and NOT `result.errors`;
  * **a record is written only after the halves return**, and `recovered` is
    False when a half still failed — the note must not claim "nothing was
    skipped" over a scene that was never analysed;
  * **the cause is read off the error**, never assumed — `LlamaServerError`
    covers a timeout and a refused connection too, and neither is an output
    limit;
  * the report surfaces carry it (`render_markdown`, `to_findings_json`).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_analyzer import pipeline  # noqa: E402
from screenplay_analyzer.llm_client import LlamaServerError  # noqa: E402
from screenplay_analyzer.report import render_markdown, to_findings_json  # noqa: E402
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

TRUNCATED = "reply could not be parsed. finish_reason='length' completion_tokens=3000"


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
            raise LlamaServerError(TRUNCATED)
        return [{"scene_number": chunk[0]["scene_number"]}]

    recoveries = []
    results, errors = pipeline._with_chunk_backoff(_scenes(2), call, recoveries=recoveries)

    assert errors == [], "a rescued split was reported as an error"
    assert len(results) == 2, "the halves did not both come back"
    assert len(recoveries) == 1, f"the split left no trace: {recoveries}"
    assert recoveries[0]["scenes"] == [1, 2]
    assert recoveries[0]["size"] == 2
    assert recoveries[0]["cause"] == "output_limit"
    assert recoveries[0]["recovered"] is True, (
        "every scene came back, so this split recovered in full")


def test_a_half_that_still_failed_is_recorded_as_not_recovered():
    """The record must describe what HAPPENED, not what was attempted. Scene 1
    is never analysed here, so `recovered` must be False — and the note must not
    claim nothing was skipped."""
    def call(chunk):
        if len(chunk) > 1 or chunk[0]["scene_number"] == 1:
            raise LlamaServerError(TRUNCATED)
        return [{"scene_number": chunk[0]["scene_number"]}]

    recoveries = []
    results, errors = pipeline._with_chunk_backoff(_scenes(2), call, recoveries=recoveries)

    assert len(errors) == 1 and "Scene 1" in errors[0]
    assert len(recoveries) == 1
    assert recoveries[0]["recovered"] is False, (
        "a half that never came back was reported as a full recovery")

    note = pipeline._chunk_recovery_note("Dialogue analysis", recoveries)
    assert note is not None
    assert "Nothing was skipped" not in note, (
        "the note claimed a clean recovery over a scene that was never analysed")
    assert "could not be analysed in full" in note, note
    assert "1 of those" in note, note


def test_the_cause_is_read_off_the_error_and_a_timeout_is_not_an_output_limit():
    """`LlamaServerError` covers a truncation, a timeout, a refused connection
    and a malformed reply alike. Only the truncated one carries a diagnosis."""
    def call(chunk):
        if len(chunk) > 1:
            raise LlamaServerError("Could not reach llama-server: connection refused")
        return [{"scene_number": chunk[0]["scene_number"]}]

    recoveries = []
    pipeline._with_chunk_backoff(_scenes(2), call, recoveries=recoveries)

    assert recoveries[0]["cause"] == "call_failed", (
        "a connection failure was mislabelled as the model's output limit")
    note = pipeline._chunk_recovery_note("Dialogue analysis", recoveries)
    assert "output limit" not in note, f"the note invented a cause: {note}"
    assert "a model call failed" in note, note


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
    note = pipeline._chunk_recovery_note("Dialogue analysis", [
        {"scenes": [4, 5, 6], "size": 3, "cause": "output_limit", "recovered": True}])
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
            raise LlamaServerError(TRUNCATED)
        return {"findings": []}


def test_analyze_records_a_split_in_recoveries_and_never_in_errors(monkeypatch):
    """The banner/orchestrator half of the contract: `errors` must stay clean,
    or a healthy run renders as a broken one."""
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "0")
    client = FlakyDialogueClient()
    doc = _parse(SAMPLE)

    result = pipeline.analyze(doc, client, run_categories=("dialogue",), progress_cb=None,
                              integrity_gate=False, observation_pass=False)

    assert client.calls > 1, "the chunk was never split, so this proved nothing"
    assert result.category_outcomes.get("dialogue") == "ok", (
        "a rescued split was reported as a failed pass")
    notes = [n for n in result.recoveries if "re-run in smaller pieces" in n]
    assert notes, f"the split stayed invisible at the run level: {result.recoveries}"
    assert "Dialogue analysis" in notes[0]
    assert not [e for e in result.errors if "re-run in smaller pieces" in e], (
        "the caveat leaked into `errors`, which drives the failure banner and the "
        f"orchestrator's partial-failure path: {result.errors}")


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

    assert not [n for n in result.recoveries if "re-run in smaller pieces" in n], (
        f"a clean run claimed a split: {result.recoveries}")
    assert result.errors == []


# ---------------------------------------------------------------------------
# 3. the report surfaces
# ---------------------------------------------------------------------------

def test_the_report_json_carries_recoveries_as_its_own_key():
    """Delivered next to `errors`, never inside it — the two mean different
    things and the desk renders `errors` as a failure."""
    result = pipeline.AnalysisResult(doc=_parse(SAMPLE))
    result.recoveries.append("Dialogue analysis: a model call failed on 1 chunk(s).")
    payload = to_findings_json(result)
    assert payload["recoveries"] == result.recoveries
    assert payload["errors"] == [], "a caveat must not appear in `errors`"


def test_the_markdown_report_renders_notes_apart_from_the_warning_block():
    result = pipeline.AnalysisResult(doc=_parse(SAMPLE))
    result.errors.append("Dialogue analysis failed: boom")
    result.recoveries.append("Dialogue analysis: a model call failed on 1 chunk(s).")
    md = render_markdown(result)
    assert "## Notes on this run" in md
    assert "re-run in smaller pieces" not in md  # the note text is the caller's
    notes_at = md.index("## Notes on this run")
    assert md.index("Dialogue analysis: a model call failed") > notes_at
