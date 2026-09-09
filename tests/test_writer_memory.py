"""Writer relationship memory tests — pure core, WriterMemory wrapper, engine integration.

Plan: docs/superpowers/plans/2026-08-12-writer-relationship-memory.md
"""

import json
import os
import tempfile

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


def test_extract_support_style():
    gen = mem.extract_signals("give me three options for this scene", "directive", False)
    assert gen["poles"].get("support_style") == "generate"
    dis = mem.extract_signals("help me think this through", "question", False)
    assert dis["poles"].get("support_style") == "discuss"
    # unrelated turns produce no signal
    none_ = mem.extract_signals("that ending feels rushed", "idea", False)
    assert "support_style" not in none_["poles"]


def test_older_profile_missing_new_dimension_does_not_crash():
    # a profile saved before support_style existed has only the old dims;
    # applying signals must migrate it, not raise
    p = mem.empty_profile()
    del p["dimensions"]["support_style"]  # simulate a pre-support_style file
    mem.apply_signals(p, _signal({"support_style": "generate"}))
    assert p["dimensions"]["support_style"]["value"] == "generate"
    mem.apply_signals(p, {"poles": {}, "topics": [], "probe_engagement": None, "pushback": None})
    assert "support_style" in p["dimensions"]


def test_support_style_gates_after_evidence():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"support_style": "generate"}))
    g = mem.dimension_gate(p)
    assert g["support_style"]["value"] == "generate"
    assert "likes concrete options to react to" in mem.build_relationship_card(p)


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
    # the only learned belief was forgotten — no phrase, no bullet, no card
    assert mem.build_relationship_card(p) is None


def test_suppressed_belief_drops_phrase_and_gate():
    """Forgetting a belief stops it steering Sam's tone: the dimension drops
    out of the gate (so its card phrase disappears) until re-learned, while
    other remembered dimensions keep working."""
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    for _ in range(3):
        mem.apply_signals(p, _signal({"pushback_appetite": "high"}))
    assert "directness" in mem.dimension_gate(p)
    assert "pushback_appetite" in mem.dimension_gate(p)
    card = mem.build_relationship_card(p)
    assert "no softening" in card
    assert "pushing back" in card

    # the writer forgets the directness belief
    obs = next(o for o in p["observations"] if o["dimension"] == "directness")
    obs["suppressed"] = True

    assert "directness" not in mem.dimension_gate(p)
    assert "pushback_appetite" in mem.dimension_gate(p)
    card2 = mem.build_relationship_card(p)
    assert "no softening" not in card2
    assert "pushing back" in card2


def test_forgotten_belief_returns_after_learning():
    """Forgetting is reversible: fresh evidence re-learns the belief and the
    dimension steers Sam again (the old suppressed observation doesn't block
    the re-gate)."""
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    obs = next(o for o in p["observations"] if o["dimension"] == "directness")
    obs["suppressed"] = True
    assert "directness" not in mem.dimension_gate(p)

    mem.apply_signals(p, _signal({"directness": "direct"}))  # writer re-learns it
    assert "directness" in mem.dimension_gate(p)
    assert "no softening" in mem.build_relationship_card(p)
    active = [o for o in p["observations"] if o["dimension"] == "directness" and not o["suppressed"]]
    assert active  # a fresh observation exists alongside the forgotten one


def test_card_omits_refresh_observation_for_rejected_dimension():
    """A refresh note about a forgotten dimension must not leak the rejected
    belief back into the card (the phrase is gone AND its observations are)."""
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    for _ in range(3):
        mem.apply_signals(p, _signal({"pushback_appetite": "high"}))
    p["observations"].append({"dimension": "directness", "text": "Writer often asks for directness.",
                               "confidence": 0.6, "suppressed": False})
    obs = next(o for o in p["observations"] if o["dimension"] == "directness" and o["text"] == "You want the note straight — no softening.")
    obs["suppressed"] = True
    card = mem.build_relationship_card(p)
    assert "no softening" not in card
    assert "Writer often asks for directness" not in card
    assert "pushing back" in card  # the other dimension still speaks


def test_contradiction_auto_suppress_keeps_new_pole_phrase():
    """The writer arguing an old belief away auto-suppresses that observation
    (2 contradictions) — but the flipped NEW belief must still steer Sam."""
    p = mem.empty_profile()
    for _ in range(4):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    assert "detail_level" in mem.dimension_gate(p)
    for _ in range(5):
        mem.apply_signals(p, _signal({"detail_level": "deep"}))  # flips + auto-suppresses old obs
    for _ in range(2):
        mem.apply_signals(p, _signal({"detail_level": "deep"}))  # re-gates at deep
    assert mem.dimension_gate(p)["detail_level"]["value"] == "deep"
    card = mem.build_relationship_card(p)
    assert "go deep and wander" in card  # the new belief speaks, not the forgotten old one


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


def test_gated_dimensions_method_suppression_aware(tmp_path):
    """The wrapper exposes the same suppression-aware gate the webapp renders
    chips from — forgetting a belief removes it from gated_dimensions."""
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(3):
        m.observe("just tell me straight what's wrong", "idea", False, None)
    assert "directness" in m.gated_dimensions()
    obs = next(o for o in m.profile["observations"] if o["dimension"] == "directness")
    m.suppress(obs["id"])
    assert "directness" not in m.gated_dimensions()
    # the only learned belief is gone — Sam has no read on the writer until
    # he learns something new (the panel shows the "still getting to know
    # you" state, which is the honest thing to show)
    assert m.card_text() is None


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


# ---------- two-scope memory (global writer patterns vs project content) ----------


def _profile_with_obs(obs):
    p = mem.empty_profile()
    for i, (text, scope) in enumerate(obs):
        p["observations"].append({
            "id": f"obs_{i}", "text": text, "dimension": "general",
            "confidence": 0.7, "source": "refresh", "contradictions": 0,
            "suppressed": False, "created": 1.0, "updated": 1.0, "scope": scope,
        })
    # gate one dimension so build_relationship_card actually builds a card
    for _ in range(mem.MIN_EVIDENCE):
        mem._bump(p, "detail_level", "short")
    return p


def test_card_text_filters_other_project_observations():
    p = _profile_with_obs([
        ("prefers short, tight answers", "global"),
        ("asks about Rishi without context", "project:Pain_3_updated_FULL"),
        ("likes talking premises through", "idea:xyz"),
    ])
    card = mem.build_relationship_card(p, scope="project:Pain_3_updated_FULL")
    assert "prefers short, tight answers" in card
    assert "asks about Rishi" in card            # its own project sees it
    assert "likes talking premises through" not in card  # other idea stays out
    # another project never sees Pain's script-scoped note
    other = mem.build_relationship_card(p, scope="project:Other")
    assert "Rishi" not in other
    assert "prefers short, tight answers" in other


def test_card_text_no_scope_is_global_only():
    p = _profile_with_obs([
        ("prefers short, tight answers", "global"),
        ("asks about Rishi without context", "project:Pain_3_updated_FULL"),
    ])
    card = mem.build_relationship_card(p)  # no scope context (welcome screen etc.)
    assert "prefers short, tight answers" in card
    assert "Rishi" not in card


def test_merge_refresh_scopes_entity_mentions(tmp_path):
    p = mem.empty_profile()
    mem.set_refresh_context("project:Pain_3_updated_FULL", ["RISHI"])
    mem.merge_refresh(p, {
        "detail_level": {"value": "no_evidence", "confidence": 0.0},
        "observations": [
            {"text": "The user asks a single question about a character named Rishi without context", "dimension": "general"},
            {"text": "prefers short, tight answers", "dimension": "detail_level"},
        ],
    })
    scopes = {o["text"]: o.get("scope") for o in p["observations"]}
    assert scopes["The user asks a single question about a character named Rishi without context"] == "project:Pain_3_updated_FULL"
    assert scopes["prefers short, tight answers"] == "global"
    mem.set_refresh_context()  # reset for other tests


def test_refresh_prompt_forbids_script_facts():
    prompt = mem.refresh_prompt([{"role": "user", "content": "hi"}])
    assert "NEVER record facts about the script" in prompt
    assert "character names" in prompt


def test_migrate_v2_tags_script_specific_observation():
    p = mem.empty_profile()
    p["version"] = 1
    p["observations"] = [
        {"id": "a", "text": "asks about a character named Rishi", "dimension": "general",
         "confidence": 0.6, "suppressed": False},
        {"id": "b", "text": "prefers short answers", "dimension": "detail_level",
         "confidence": 0.6, "suppressed": False},
    ]
    changed = mem._migrate_v2(p, {"RISHI": "Pain_3_updated_FULL", "DOCTOR": "Pain_3_updated_FULL"})
    assert changed
    by_id = {o["id"]: o["scope"] for o in p["observations"]}
    assert by_id["a"] == "project:Pain_3_updated_FULL"
    assert by_id["b"] == "global"
    assert p["version"] == 2


def test_migrate_v2_idempotent():
    p = mem.empty_profile()
    p["observations"].append({"id": "a", "text": "x", "dimension": "general",
                              "confidence": 0.6, "suppressed": False, "scope": "global"})
    assert mem._migrate_v2(p, None) is False  # nothing to do


def test_entity_scope_map_resolves_relative_projects_dir():
    # Regression: the caller passes dirname(dirname(profile_path)) which can be
    # a relative path that collapses (./studio_projects -> "."); the map must
    # still find the projects or every observation stays global.
    tmp = tempfile.mkdtemp(dir=os.getcwd())  # same drive so relpath works
    try:
        proj = os.path.join(tmp, "Pain_X")
        os.makedirs(proj)
        with open(os.path.join(proj, "parsed.json"), "w", encoding="utf-8") as f:
            json.dump({"all_characters": ["RISHI", "DOCTOR"]}, f)
        rel = os.path.relpath(tmp)  # simulate the relative collapse
        mapping = mem._entity_scope_map(rel)
        assert mapping.get("RISHI") == "Pain_X"
        assert mapping.get("DOCTOR") == "Pain_X"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
