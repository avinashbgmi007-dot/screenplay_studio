"""Writer relationship memory tests — pure core, WriterMemory wrapper, engine integration.

Plan: docs/superpowers/plans/2026-08-12-writer-relationship-memory.md
"""

import pytest

from screenplay_cowriter import memory as mem
from screenplay_cowriter import models as mem_mod

_SIG = {"poles": {}, "topics": [], "probe_engagement": None, "pushback": None}


def _signal(pole_map):
    s = dict(_SIG)
    s["poles"] = dict(pole_map)
    return s


# ---------- Task 1: signals, evidence, confidence gate ----------


def test_extract_tone_statement_direct():
    s = mem.extract_signals("just tell me straight what's wrong with scene 3", "idea", False, None)
    assert s["poles"].get("directness") == "direct"


def test_extract_tone_statement_short():
    s = mem.extract_signals("keep it short please", "idea", False, None)
    assert s["poles"].get("detail_level") == "short"


def test_extract_probe_engagement():
    s = mem.extract_signals("because the guilt is eating her", "idea", True, "So the idea is...?")
    assert s["probe_engagement"] == "engaged"
    s2 = mem.extract_signals("hmm", "idea", True, "So the idea is...?")
    assert s2["probe_engagement"] == "dismissed"


def test_extract_pushback():
    s = mem.extract_signals("no, cutting that line loses the subtext", "idea", False, None)
    assert s["pushback"] == "argued"
    s2 = mem.extract_signals("ok sure", "idea", False, None)
    assert s2["pushback"] == "accepted"


def test_extract_topics():
    s = mem.extract_signals("the protagonist's arc feels flat", "idea", False, None)
    assert "character" in s["topics"]


def test_single_signal_does_not_gate():
    p = mem.empty_profile()
    mem.apply_signals(p, _signal({"detail_level": "short"}))
    assert "detail_level" not in mem.dimension_gate(p)


def test_three_consistent_signals_gate():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    assert mem.dimension_gate(p)["detail_level"]["value"] == "short"


def test_contradiction_flips_only_when_winning():
    p = mem.empty_profile()
    for _ in range(4):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    assert mem.dimension_gate(p)["detail_level"]["value"] == "short"
    for _ in range(5):
        mem.apply_signals(p, _signal({"detail_level": "deep"}))
    assert "detail_level" not in mem.dimension_gate(p)  # mid-flip uncertainty drops below gate
    for _ in range(2):
        mem.apply_signals(p, _signal({"detail_level": "deep"}))
    assert mem.dimension_gate(p)["detail_level"]["value"] == "deep"


# ---------- Task 2: card, cold start, refresh prompt/parse/merge ----------


def test_card_empty_profile():
    assert mem.build_relationship_card(mem.empty_profile()) is None


def test_card_gated_only_and_never_quotes_memory():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    card = mem.build_relationship_card(p)
    assert card and "ABOUT HOW YOU TWO WORK TOGETHER" in card
    assert "never content" in card
    # The rule text may contain "you always say…" as the forbidden example —
    # the real invariant is that learned observations never use that framing.
    assert all("you always say" not in o["text"] for o in p["observations"])


def test_card_excludes_suppressed_observation():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    obs = next(o for o in p["observations"] if o["dimension"] == "directness")
    obs["suppressed"] = True
    card = mem.build_relationship_card(p)
    assert obs["text"] not in card


def test_cold_start_line_only_when_zero_evidence():
    p = mem.empty_profile()
    assert mem.cold_start_line(p)
    p["meta"]["total_turns_observed"] = 1
    assert mem.cold_start_line(p) is None


def test_refresh_prompt_shape():
    txt = mem.refresh_prompt([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    assert "RELATIONSHIP MEMORY REFRESH" in txt
    assert "user: hi" in txt and "assistant: hello" in txt


def test_parse_refresh_json():
    assert mem.parse_refresh_json(
        'Here you go: {"detail_level": {"value": "deep", "confidence": 0.8}}'
    ) == {"detail_level": {"value": "deep", "confidence": 0.8}}
    assert mem.parse_refresh_json('{"directness": {"value": "direct", "confidence": 0.7}}') == \
        {"directness": {"value": "direct", "confidence": 0.7}}
    assert mem.parse_refresh_json("no idea what happened") is None


def test_merge_refresh_higher_confidence_wins():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    mem.merge_refresh(p, {"detail_level": {"value": "deep", "confidence": 0.9}, "observations": []})
    assert p["dimensions"]["detail_level"]["value"] == "deep"


def test_merge_refresh_lower_confidence_loses():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    mem.merge_refresh(p, {"detail_level": {"value": "deep", "confidence": 0.5}, "observations": []})
    assert p["dimensions"]["detail_level"]["value"] == "short"


def test_merge_refresh_observations_novel_only():
    p = mem.empty_profile()
    mem.merge_refresh(p, {"observations": [{"text": "You like short answers.", "dimension": "detail_level"}]})
    mem.merge_refresh(p, {"observations": [
        {"text": "You like short answers.", "dimension": "detail_level"},
        {"text": "You argue for lines.", "dimension": "pushback_appetite"},
    ]})
    texts = [o["text"] for o in p["observations"]]
    assert texts.count("You like short answers.") == 1
    assert "You argue for lines." in texts


# ---------- Task 3: WriterMemory wrapper ----------


class _FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append(messages)
        return self.reply


def test_round_trip_and_observe(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(3):
        m.observe("keep it short please", "idea", False, None)
    m2 = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    assert m2.profile["meta"]["total_turns_observed"] == 3
    assert m2.card_text() is not None


def test_corrupt_file_backed_up(tmp_path):
    p = tmp_path / "writer_profile.json"
    p.write_text("{ not json", encoding="utf-8")
    m = mem.WriterMemory.load(str(p))
    assert m.profile["meta"]["total_turns_observed"] == 0
    assert (tmp_path / "writer_profile.json.bak").exists()


def test_suppress_persists(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(3):
        m.observe("just tell me straight what's wrong", "idea", False, None)
    obs = next(o for o in m.profile["observations"] if not o["suppressed"])
    assert m.suppress(obs["id"]) is True
    assert m.suppress(obs["id"]) is False  # already suppressed
    m2 = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    assert next(o for o in m2.profile["observations"] if o["id"] == obs["id"])["suppressed"] is True


def test_refresh_due_and_reset(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    assert not m.refresh_due()
    for _ in range(10):
        m.observe("hi there", "question", False, None)
    assert m.refresh_due()
    m._refresh_sync(_FakeClient('{"observations": []}'), [{"role": "user", "content": "hi"}])
    assert not m.refresh_due()


def test_refresh_sync_merges_proposal(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(10):
        m.observe("hi there", "question", False, None)
    client = _FakeClient('{"detail_level": {"value": "deep", "confidence": 0.8}, '
                         '"observations": [{"text": "Likes deep answers.", "dimension": "detail_level"}]}')
    m._refresh_sync(client, [{"role": "user", "content": "hi"}])
    assert m.profile["dimensions"]["detail_level"]["value"] == "deep"
    assert m.profile["meta"]["refresh_count"] == 1
    assert len(client.calls) == 1
    assert "RELATIONSHIP MEMORY REFRESH" in client.calls[0][0]["content"]


# ---------- Task 4: engine + context integration ----------


def _make_engine(client, memory=None):
    from screenplay_cowriter.engine import CoWriterEngine
    from screenplay_cowriter.context import ScriptContext, ReportContext
    return CoWriterEngine(client, ScriptContext({}), ReportContext(None), memory=memory)


class _CapturingClient:
    def __init__(self, reply="Okay — here's my thought."):
        self.reply = reply
        self.prompts = []

    def chat(self, messages, **kw):
        self.prompts.append(next(m["content"] for m in messages if m["role"] == "system"))
        return self.reply


def test_memory_none_prompt_has_no_card():
    client = _CapturingClient()
    engine = _make_engine(client)  # no memory
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "what about scene 3?")
    assert "ABOUT HOW YOU TWO WORK TOGETHER" not in client.prompts[0]
    assert "LANGUAGE" in client.prompts[0]  # base content still present


def test_card_injected_when_gated(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "p.json"))
    for _ in range(3):
        m.observe("just tell me straight what's wrong", "idea", False, None)
    client = _CapturingClient()
    engine = _make_engine(client, memory=m)
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "what about scene 3?")
    assert "ABOUT HOW YOU TWO WORK TOGETHER" in client.prompts[0]


def test_cold_start_line_only_first_turn(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "p2.json"))
    client = _CapturingClient()
    engine = _make_engine(client, memory=m)
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "hi")
    assert "what's the one thing you're trying to fix" in client.prompts[0]
    engine.send_message(s, "hi again")
    assert "what's the one thing you're trying to fix" not in client.prompts[1]


def test_observe_called_each_turn(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "p3.json"))
    client = _CapturingClient()
    engine = _make_engine(client, memory=m)
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "what do you think?")
    engine.send_message(s, "what about the ending?")
    assert m.profile["meta"]["total_turns_observed"] == 2
