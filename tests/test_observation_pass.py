"""
Gate 11 — the observation pass.

The integrity gate removed what was mechanically FALSE. What it could not touch
is the larger set that is mechanically UNCHECKABLE: findings with no evidence at
all, so no rule can score them. This pass grounds those — and the whole point of
its design is what it REFUSES to do:

  * it never trusts the model's own verdict (the grammar has no `grounded`
    field at all — the citation is re-verified against the script);
  * it never rewrites the writer-facing `issue`;
  * it never promotes a finding whose citation fails verification;
  * it never touches a finding the verifier already judged.

Every one of those refusals is pinned below, because each is the difference
between a grounding pass and a fabrication engine.
"""

import copy
import os

from screenplay_analyzer import grammar as grammar_mod
from screenplay_analyzer import pipeline
from screenplay_analyzer.observation_pass import (DEFAULT_LIMIT, ObservationPass,
                                                  needs_grounding,
                                                  observation_limit,
                                                  observation_pass_enabled)
from screenplay_parser import parse_fountain
from screenplay_parser.quotematch import find_scene_text


def _doc():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "pain_tenglish.fountain")
    return parse_fountain(path)


def _real_line(doc, scene_number=1):
    """A verbatim line from the parsed script, long enough to clear the
    verifier's 3-word floor. Read from the document rather than hardcoded, so
    re-cutting the fixture cannot silently turn a 'verified' case into a
    'fabricated' one."""
    text = find_scene_text(doc, scene_number) or ""
    for line in text.split("\n"):
        if len(line.split()) >= 4:
            return line.strip()
    raise AssertionError("the fixture has no usable line in scene 1")


class _Stub:
    """Returns a queued reply per call and counts the calls."""

    def __init__(self, replies=None, error=None):
        self.replies = list(replies or [])
        self.error = error
        self.calls = 0
        self.prompts = []

    def resolve_model(self):
        return "stub-model"

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        self.calls += 1
        self.prompts.append((system, user))
        if self.error:
            raise self.error
        if self.replies:
            return self.replies.pop(0)
        return {"observation": "", "quote": None, "search": ""}


def _ungrounded(issue="The theme is underdeveloped.", **kw):
    f = {"category": "theme", "severity": "low", "issue": issue, "scene_key": "scene-1",
         "scene_refs": [1], "evidence_quote": None,
         "verification": {"status": "no_quote", "matched_scene": None, "confidence": None}}
    f.update(kw)
    return f


# ---------------------------------------------------------------- the contract

def test_the_grammar_offers_no_way_for_the_model_to_certify_itself():
    """The load-bearing omission. If the model could return `grounded: true`,
    every other safety in this pass would be decoration — a confident
    fabrication would carry its own certificate."""
    g = grammar_mod.observation_grounding_grammar()
    for fragment in ("observation", "quote", "search"):
        assert fragment in g
    assert "grounded" not in g


def test_only_no_quote_findings_are_targets():
    assert needs_grounding(_ungrounded())
    # a verified finding has nothing to gain
    assert not needs_grounding(_ungrounded(verification={"status": "verified"}))
    # a rejected citation stays rejected: re-asking would erase the record that
    # the model's first citation was wrong
    assert not needs_grounding(_ungrounded(verification={"status": "not_found"}))
    assert not needs_grounding(_ungrounded(verification={"status": "scene_not_found"}))


# ---------------------------------------------------------------- grounding

def test_a_real_citation_grounds_the_finding():
    doc = _doc()
    line = _real_line(doc, 1)
    client = _Stub([{"observation": "Siddhu is told he cannot feel pain.",
                     "quote": line, "search": ""}])
    res = ObservationPass().run([_ungrounded()], client, doc)

    assert res.attempted == 1 and res.grounded == 1
    f = res.findings[0]
    assert f["evidence_quote"] == line
    assert f["verification"]["status"] == "verified"
    assert f["observation"].startswith("Siddhu")
    # the writer-facing sentence is the analyzer's, untouched
    assert f["issue"] == "The theme is underdeveloped."


def test_a_fabricated_citation_is_rejected_by_the_verifier():
    """The core safety property: the model proposes, `verify_finding` disposes."""
    doc = _doc()
    client = _Stub([{"observation": "A confident-sounding claim.",
                     "quote": "This line appears nowhere in the screenplay whatsoever.",
                     "search": ""}])
    res = ObservationPass().run([_ungrounded()], client, doc)

    assert res.attempted == 1 and res.grounded == 0
    f = res.findings[0]
    assert f.get("evidence_quote") is None, "a fabricated quote was adopted"
    assert f["verification"]["status"] == "no_quote"
    assert "observation" not in f, "an ungrounded observation was attached anyway"


def test_no_citation_at_all_leaves_the_finding_a_question():
    doc = _doc()
    res = ObservationPass().run([_ungrounded()], _Stub([{"observation": "o",
                                                         "quote": None}]), doc)
    assert res.grounded == 0
    assert res.findings[0]["evidence_quote"] is None


def test_a_grounded_finding_is_never_re_asked():
    doc = _doc()
    rows = [_ungrounded(verification={"status": "verified", "matched_scene": 1,
                                      "confidence": 1.0}),
            _ungrounded(issue="A quote that failed.",
                        verification={"status": "not_found", "confidence": 0.2})]
    client = _Stub([])
    res = ObservationPass().run(rows, client, doc)
    assert client.calls == 0, "the pass spent a model call on a non-target"
    assert res.attempted == 0
    assert res.findings == rows


# ---------------------------------------------------------------- invariants

def test_the_pass_never_mutates_its_input():
    doc = _doc()
    rows = [_ungrounded()]
    before = copy.deepcopy(rows)
    ObservationPass().run(rows, _Stub([{"observation": "o",
                                        "quote": _real_line(doc, 1)}]), doc)
    assert rows == before, "the pass mutated the caller's findings"


def test_the_limit_caps_the_model_calls():
    doc = _doc()
    rows = [_ungrounded(issue=f"note {i}") for i in range(5)]
    client = _Stub([{"observation": "o", "quote": None} for _ in range(5)])
    res = ObservationPass(limit=2).run(rows, client, doc)
    assert client.calls == 2 and res.attempted == 2


def test_a_model_error_is_recorded_and_never_fails_the_run():
    doc = _doc()
    res = ObservationPass().run([_ungrounded()], _Stub(error=RuntimeError("boom")), doc)
    assert res.attempted == 1 and res.grounded == 0
    assert res.errors and "boom" in res.errors[0]
    assert res.findings[0]["verification"]["status"] == "no_quote"


def test_the_summary_accounts_for_every_attempt():
    doc = _doc()
    rows = [_ungrounded(), _ungrounded(issue="second note")]
    res = ObservationPass().run(rows, _Stub([{"observation": "o", "quote": None},
                                             {"observation": "o", "quote": None}]), doc)
    assert res.summary() == {"attempted": 2, "grounded": 0, "ungrounded": 2}


# ---------------------------------------------------------------- the id claim

def test_grounding_moves_the_id_into_the_stable_quote_tier():
    """The documented side effect, pinned — and it is an IMPROVEMENT: a quoted
    finding's id survives the model re-wording the issue on the next analysis,
    which is exactly how an ungrounded finding's mark gets orphaned today."""
    from screenplay_studio.revision import compute_finding_id

    doc = _doc()
    line = _real_line(doc, 1)
    row = _ungrounded()
    before = compute_finding_id(row)

    res = ObservationPass().run([row], _Stub([{"observation": "o", "quote": line}]), doc)
    after = compute_finding_id(res.findings[0])
    assert after != before, "grounding did not move the id off the issue tier"

    reworded = dict(res.findings[0])
    reworded["issue"] = "Completely different words this time."
    assert compute_finding_id(reworded) == after, \
        "the grounded id is not stable under a re-worded issue"


# ---------------------------------------------------------------- env switches

def test_env_switches(monkeypatch):
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "0")
    assert not observation_pass_enabled()
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "1")
    assert observation_pass_enabled()
    monkeypatch.delenv("SCREENPLAY_STUDIO_OBSERVATION_PASS")
    assert observation_pass_enabled(), "the pass must be on by default"

    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_LIMIT", "7")
    assert observation_limit() == 7
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_LIMIT", "0")
    assert observation_limit() == 0
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_LIMIT", "garbage")
    assert observation_limit() == DEFAULT_LIMIT


# ---------------------------------------------------------------- in the pipeline

class _PipelineStub:
    """Crafted findings from every analysis pass, a real citation from the
    observation pass — told apart by the system prompt, so the pipeline's own
    routing is exercised rather than mocked away."""

    def __init__(self, line):
        self.line = line
        self.obs_calls = 0

    def resolve_model(self):
        return "stub-model"

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        # Keyed on the pass's own opening line, NOT on the word "falsifiable":
        # gate 11 full added that word to the CATEGORY prompts too (the
        # observation contract), so a keyword that appears in both prompts can
        # no longer tell the two calls apart. This marker is unique to the pass.
        if "grounding a note in a screenplay" in system:
            self.obs_calls += 1
            return {"observation": "The doctor explains the condition in one speech.",
                    "quote": self.line, "search": ""}
        return {"findings": [{
            "category": "dialogue", "severity": "low", "scene_refs": [1],
            "issue": "The doctor's explanation of the condition runs as one speech.",
            "why_it_matters": "It withholds the reaction shot the scene needs.",
            "evidence_quote": None, "rule_id": None}]}


def test_the_pipeline_runs_the_pass_and_discloses_it(monkeypatch):
    # conftest turns the pass off for the suite (it is model-backed and every
    # mocked finding is a target); this is the one test that must have it ON.
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "1")
    doc = _doc()
    client = _PipelineStub(_real_line(doc, 1))
    res = pipeline.analyze(doc, client, run_categories=("dialogue",))

    assert client.obs_calls > 0, "the pipeline never invoked the observation pass"
    assert res.findings, "the stub produced no findings"
    grounded = [f for f in res.findings if f.get("observation")]
    assert grounded, "nothing was grounded"
    assert all(f["verification"]["status"] == "verified" for f in grounded)
    assert res.stats.get("observation_pass", {}).get("grounded") == len(grounded)


def test_the_pipeline_can_turn_the_pass_off(monkeypatch):
    # the env says ON, so it is the `observation_pass=False` PARAM that must be
    # what stops the call — otherwise this test would pass on conftest's default.
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "1")
    doc = _doc()
    client = _PipelineStub(_real_line(doc, 1))
    res = pipeline.analyze(doc, client, run_categories=("dialogue",),
                           observation_pass=False)
    assert client.obs_calls == 0
    assert not any(f.get("observation") for f in res.findings)
    assert "observation_pass" not in (res.stats or {})
