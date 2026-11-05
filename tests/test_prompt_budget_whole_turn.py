"""Gap 30 — the declared prompt budget bounded one segment of the turn, not the turn.

Measured before the fix, on a script with three long scenes and
`prompt_budget=2048`:

    system message   29,971 chars
    whole payload    30,369 chars

The budget *was* enforced — on `build_system_prompt` alone, whose result was
then handed to `_assemble_messages`, which appended, with no budget argument at
all: the scene block (62,484 chars for three scenes), the quote, the few-shot
examples, the trait reminder, the post-history reminder and the history window.
So the number that claimed to protect the turn protected about a sixth of it.

The register asked for three things, and this file tests all three:

  * a budget that covers the WHOLE payload — system, scenes, quote, history,
    and room reserved for the reply;
  * requested context preserved by measured windowing, with omissions
    DISCLOSED to the writer rather than silently dropped;
  * a clear failure when the irreducible minimum cannot fit.

Everything here is arithmetic over the real assembly code. No model, no server.
"""
import warnings

import pytest

from screenplay_cowriter.context import (
    PROMPT_CHAR_BUDGET,
    PROMPT_REPLY_RESERVE_CHARS,
    PromptBudgetUnreachable,
    ReportContext,
    ScriptContext,
    build_scene_context_block,
    build_system_prompt,
    reply_reserve,
    room_for_scenes,
    split_over_budget,
    window_scene_text,
)
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session

LONG_LINE = "The rain keeps falling on the empty street outside."
REPLY = "A reply from the stand-in client."


class _Client:
    """Captures the payload instead of sending it."""

    def __init__(self):
        self.messages = []

    def chat(self, messages, **kw):
        self.messages = messages
        return REPLY

    def chat_stream(self, messages, on_token=None, **kw):
        self.messages = messages
        if on_token:
            on_token(REPLY)
        return REPLY


def _script(n_scenes=3, repeats=400):
    scenes = []
    for i in range(1, n_scenes + 1):
        text = " ".join([LONG_LINE] * repeats)
        scenes.append({
            "scene_number": i, "heading_raw": f"INT. ROOM {i} - DAY",
            "text": text, "page_start": float(i), "page_end": float(i) + 1,
            "characters": ["RISHI"],
            "elements": [{"type": "ACTION", "text": text}],
        })
    return {"title": "Big", "scenes": scenes, "characters": ["RISHI"]}


def _payload(n_scenes=3, repeats=400, budget=None, text="What's wrong with scene 3?"):
    client = _Client()
    engine = CoWriterEngine(client, ScriptContext(_script(n_scenes, repeats)),
                            ReportContext(None), prompt_budget=budget)
    engine.send_message(Session.new(title="t"), text)
    return client.messages


def _chars(messages):
    return sum(len(m.get("content") or "") for m in messages)


# ---------------------------------------------------------------------------
# 1. The filed reproduction: a small budget must actually bound the payload
# ---------------------------------------------------------------------------

def test_a_2048_budget_no_longer_produces_a_30000_char_payload():
    """The filed number. Before: 30,369 chars sent against a 2,048 budget.

    The turn is now REFUSED rather than sent oversized: 2,048 cannot hold the
    persona, the guards and the standing report, and sending it anyway is the
    silent truncation the budget exists to prevent. Either outcome is correct;
    what is not correct is a 30,369-char send.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(PromptBudgetUnreachable) as exc:
            _payload(budget=2048)
    assert "2048" in str(exc.value) or "budget" in str(exc.value)


@pytest.mark.parametrize("budget", [12000, 20000, 26000, 40000])
def test_a_feasible_budget_bounds_the_whole_payload(budget):
    """The regression itself: whatever is sent, the SUM of every message fits.

    Before the fix this was the test that would have caught the gap — the
    payload was 30,369 against 2,048 and nothing noticed.
    """
    msgs = _payload(budget=budget)
    total = _chars(msgs)
    assert total <= budget, f"sent {total} chars against a {budget} budget"
    system = [m for m in msgs if m["role"] == "system"]
    assert len(system) == 1, "the single-system contract (H7a) must survive"
    assert len(system[0]["content"]) <= budget


def test_the_reply_is_reserved_out_of_the_budget():
    """A budget that the prompt fills leaves no room for the answer."""
    assert reply_reserve() == min(PROMPT_REPLY_RESERVE_CHARS, PROMPT_CHAR_BUDGET // 4)

    msgs = _payload(budget=20000)
    total = _chars(msgs)
    assert total <= 20000 - reply_reserve(), (
        f"sent {total}; the reserve of {reply_reserve()} was not held back")


def test_no_budget_still_means_unlimited():
    """The CLI's contract, unchanged: `None` sends the full context."""
    msgs = _payload(budget=None)
    assert _chars(msgs) > 20000, "an unlimited turn should not be trimmed"


# ---------------------------------------------------------------------------
# 2. Requested context survives by windowing, and the loss is disclosed
# ---------------------------------------------------------------------------

def test_a_long_scene_is_windows_into_the_turn_rather_than_dropped():
    """Three 20k-char scenes, 20,000-char budget: the writer asked about scene
    3, so scene text must be present — just not all of it."""
    msgs = _payload(budget=20000)
    system = [m for m in msgs if m["role"] == "system"][0]["content"]
    assert "SCENE TEXT" in system, "the requested scene was dropped entirely"


def test_a_trimmed_scene_says_that_it_was_trimmed():
    """A scene that simply stops lets the model reason about an ending that is
    not there. The cut is marked, and the model is told the middle is missing."""
    text = "\n".join(f"line {i} of the scene" for i in range(500))
    piece, trimmed = window_scene_text(text, 2000)
    assert trimmed is True
    assert len(piece) <= 2000, len(piece)
    assert "middle is not shown" in piece
    # Both ends survive: a writer asking about the END of a scene needs it.
    assert piece.startswith("line 0")
    assert piece.rstrip().endswith("line 499 of the scene")


def test_a_scene_that_fits_is_returned_byte_identical():
    text = "INT. ROOM - DAY\n\nA short scene."
    piece, trimmed = window_scene_text(text, 1000)
    assert trimmed is False
    assert piece == text


def test_the_scene_block_honours_the_budget_it_is_given():
    """The block had NO budget parameter before this gap."""
    sc = ScriptContext(_script(3, 400))
    block = build_scene_context_block(sc, [1, 2, 3], budget=5000)
    assert block is not None
    assert len(block) <= 5000, f"block is {len(block)} chars against a 5000 budget"


def test_each_scene_gets_an_equal_share_so_one_long_scene_cannot_starve_the_rest():
    sc = ScriptContext({"scenes": [
        {"scene_number": 1, "heading_raw": "INT. A - DAY", "text": "x " * 8000},
        {"scene_number": 2, "heading_raw": "INT. B - DAY", "text": "y " * 100},
        {"scene_number": 3, "heading_raw": "INT. C - DAY", "text": "z " * 100},
    ]})
    block = build_scene_context_block(sc, [1, 2, 3], budget=3000)
    assert "INT. B" in block and "INT. C" in block, "the short scenes were starved"
    assert block.count("---") == 2, "all three scenes should still be represented"


def test_scenes_that_cannot_be_shown_at_all_are_named_to_the_model():
    """Silence would let the model answer about a scene it was never given."""
    sc = ScriptContext(_script(3, 400))
    block = build_scene_context_block(sc, [1, 2, 3], budget=1)
    assert block is not None, "the omission itself must still be sent"
    assert "NOT SHOWN" in block.replace("SCENES NOT SHOWN", "NOT SHOWN")


def test_a_scene_missing_from_the_script_is_not_blamed_on_the_budget():
    """A false disclosure: "no room in the context" for a scene that is not in
    the script at all. The writer would be told to narrow a question that
    narrowing cannot answer. My first version conflated the two."""
    sc = ScriptContext({"scenes": [{"scene_number": 1, "heading_raw": "INT. A - DAY",
                                    "text": "A short scene."}]})
    block = build_scene_context_block(sc, [3])
    assert block is not None
    assert "NOT IN THE SCRIPT" in block
    assert "no room" not in block, "a missing scene was reported as a budget cut"


def test_split_over_budget_reports_a_shortfall_instead_of_returning_nothing():
    shares, shortfall = split_over_budget([1, 2, 3], 0)
    assert shares == [0, 0, 0]
    assert shortfall == 3
    shares, shortfall = split_over_budget([1, 2, 3], 900)
    assert shares == [300, 300, 300]
    assert shortfall == 0


def test_room_for_scenes_is_derived_from_what_is_actually_in_the_turn():
    """My first version gave the block a fixed half of the budget, which wasted
    room on a small base prompt and over-allocated on a large one."""
    small = room_for_scenes(20000, base_chars=2000, margin=0)
    large = room_for_scenes(20000, base_chars=15000, margin=0)
    assert small == 20000 - reply_reserve() - 2000
    assert large == 20000 - reply_reserve() - 15000
    assert small > large
    assert room_for_scenes(0, 1000) == 0, "no budget means no cap, not zero room"
    assert room_for_scenes(1000, 99999) == 0, "a negative room must clamp at 0"


# ---------------------------------------------------------------------------
# 3. A required minimum that cannot fit fails clearly
# ---------------------------------------------------------------------------

def test_an_unreachable_budget_refuses_the_turn_with_the_numbers_in_it():
    """Before: a RuntimeWarning went to the server log and the turn was sent
    oversized. A warning is not protection."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(PromptBudgetUnreachable) as exc:
            _payload(budget=3000)
    message = str(exc.value)
    assert "budget" in message
    assert "larger window" in message or "Raise" in message


def test_the_refusal_happens_before_anything_is_sent():
    """A turn must not half-send: the client is never called."""
    client = _Client()
    engine = CoWriterEngine(client, ScriptContext(_script(1, 10)), ReportContext(None),
                            prompt_budget=2048)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(PromptBudgetUnreachable):
            engine.send_message(Session.new(title="t"), "hello")
    assert client.messages == [], "the payload reached the client anyway"


def test_the_raising_renderer_is_only_a_warning():
    """`build_system_prompt` is a RENDERER: callers legitimately ask it what it
    can build under an impossible budget (the shed-ladder tests do). It warns;
    the refusal belongs where the payload is assembled. I first put the raise
    here and broke four tests that were doing exactly that."""
    with pytest.warns(RuntimeWarning, match="unreachable"):
        build_system_prompt(ScriptContext(_script(1, 10)), ReportContext(None),
                            "writing_partner", "peer", budget=1000)


# ---------------------------------------------------------------------------
# 4. The labelled blocks are still labelled
# ---------------------------------------------------------------------------

def test_a_trimmed_turn_still_carries_the_trim_note():
    from screenplay_cowriter.context import PROMPT_TRIM_NOTE

    library = "PAST WORK — " + ("a scene from another script. " * 700)
    client = _Client()
    engine = CoWriterEngine(client, ScriptContext(_script(1, 10)), ReportContext(None),
                            writer_library_text=library, prompt_budget=26000)
    engine.send_message(Session.new(title="t"), "hello")
    system = client.messages[0]["content"]
    assert PROMPT_TRIM_NOTE in system, "the writer is not told the context was cut"
    assert library not in system


def test_a_short_turn_is_untouched():
    """The ordinary turn must be byte-identical to before the budget existed —
    this gap only changes what happens when the budget BINDS."""
    msgs = _payload(n_scenes=1, repeats=5, budget=40000)
    system = msgs[0]["content"]
    assert "CONTEXT TRIMMED" not in system
    assert "NOT SHOWN" not in system


# ---------------------------------------------------------------------------
# 5. The two fixes that only bite when the base prompt is near the budget
#
# Both of these were found by the revert matrix, not by writing tests first:
# reverting them changed NO test outcome, which meant they were unpinned.
# ---------------------------------------------------------------------------

def _big_report(n=40):
    return ReportContext({
        "coverage": {"recommendation": "consider", "logline": "L", "genre": "G",
                     "tone": "T", "strengths": ["s"], "weaknesses": ["w"]},
        "findings": [
            {"category": "structure", "severity": ["high", "medium", "low"][i % 3],
             "issue": f"Issue number {i}", "why_it_matters": f"Rationale number {i}",
             "scene_refs": [i + 1]}
            for i in range(n)
        ],
    })


def test_a_scene_block_is_sized_against_the_room_the_system_prompt_left():
    """Reverting the in-assembly sizing (so the scene block keeps whatever cap
    the caller guessed) must break this. The caller cannot know the examples or
    the tail notes, so it must not be the one deciding."""
    client = _Client()
    engine = CoWriterEngine(client, ScriptContext(_script(3, 400)), _big_report(),
                            prompt_budget=24000)
    engine.send_message(Session.new(title="t"), "What's wrong with scene 3?")
    system = client.messages[0]["content"]
    assert len(system) <= 24000 - reply_reserve(), (
        f"system message is {len(system)} chars; the caller-sized scene block "
        f"overshot the room the base prompt left")


def test_the_base_prompt_is_trimmed_for_the_suffixes_that_follow_it(monkeypatch):
    """Reverting `_base_prompt_budget` must break this.

    Measured behaviour of the bug: an 11,589-char budget produced a 14,253-char
    turn, because the base prompt was trimmed to the FULL budget and then the
    probe/language/answer-first notes were appended to it. The turn is not
    merely over-long — the renderer was told to fit a limit that was already
    spent by the time its output was used.

    Asserts the contract directly: the budget handed to the renderer must leave
    room for what this engine appends after it. A purely end-to-end assertion
    does NOT catch the revert when the base prompt is far below the budget and
    nothing is trimmed at all — which is why my first version of this test
    passed with the fix reverted.
    """
    import screenplay_cowriter.engine as engine_mod

    seen = {}
    real = engine_mod.build_system_prompt

    def spy(*a, **kw):
        seen.update(kw)
        text = real(*a, **kw)
        seen["_out"] = text
        return text

    monkeypatch.setattr(engine_mod, "build_system_prompt", spy)

    budget = 40000
    client = _Client()
    engine = CoWriterEngine(client, ScriptContext(_script(1, 10)), _big_report(),
                            prompt_budget=budget)
    engine.send_message(Session.new(title="t"), "hello")

    handed = seen["budget"]
    # The engine appends the language note and the answer-first note after the
    # renderer returns; those are the chars that must be held back. Measured at
    # ~490 chars. With the revert the renderer gets the whole 40,000 and the
    # turn overshoots by exactly their length.
    assert budget - handed >= 200, (
        f"the renderer was handed {handed} of a {budget} budget, leaving nothing "
        f"for the {len(seen['_out']) and ''}text the engine appends after it")
    assert _chars(client.messages) <= budget, "the turn itself must still fit"


def _payload_with_big_report(budget):
    client = _Client()
    engine = CoWriterEngine(client, ScriptContext(_script(1, 10)), _big_report(),
                            prompt_budget=budget)
    engine.send_message(Session.new(title="t"), "hello")
    return client.messages
