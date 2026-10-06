"""Gate 11 (full) — the observation contract in the analyzer itself.

Gate 11's first half shipped as a PASS (`observation_pass.py`): it grounds
findings the verifier had already left unquoted. That treats a symptom. The
binding half is Law V″ — a finding IS an observation, a falsifiable claim about
what is on the page, with the craft evaluation attached as an EVALUATION. An
opinion with nothing under it cannot be checked, and no amount of post-hoc
grounding fixes a schema that never asked for the claim in the first place.

This file pins the analyzer-side contract:

1. THE SCHEMA ASKS — the findings grammar has an `observation` key, and it comes
   BEFORE `issue`. Order is the contract: the model states the claim, then its
   reading of it. A schema that asks for the judgment first gets judgments.
2. THE PROMPT ASKS — both citation instructions (full-text and summary-tier)
   carry the observation instruction, because a summary-tier finding is exactly
   the one most likely to be an unevidenced evaluation.
3. NULLABLE ON PURPOSE — the field is `(string | null)`. A model that cannot
   state a checkable claim must be able to say so; forcing a string would
   manufacture exactly the confident-but-empty observation this gate exists to
   expose. Normalization folds "", "null" and whitespace to None so "did the
   model state one?" is a single honest test downstream.
4. MEASURED — the report discloses the coverage (`observation_bearing` /
   `observation_pct`) beside the quote rate, because "can I find the line?" and
   "can I check the claim?" are different questions.
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from screenplay_analyzer import prompts  # noqa: E402
from screenplay_analyzer.grammar import findings_grammar  # noqa: E402
from screenplay_analyzer.pipeline import _normalize_findings  # noqa: E402
from screenplay_analyzer.report import _observation_coverage  # noqa: E402


# ---------- 1. the schema asks ----------

def test_the_findings_grammar_has_an_observation_key():
    g = findings_grammar()
    assert '"\\"observation\\""' in g, "the findings grammar does not ask for an observation"


def test_the_grammar_asks_for_the_observation_before_the_judgment():
    """Order is the contract. A schema that asks for `issue` first gets
    judgments, and the observation becomes an afterthought the model skips."""
    g = findings_grammar()
    assert g.index('"\\"observation\\""') < g.index('"\\"issue\\""'), (
        "the grammar asks for the judgment before the claim")


def test_the_observation_field_is_nullable():
    """Forcing a string would manufacture a confident-but-empty observation —
    the exact failure this gate exists to expose."""
    g = findings_grammar()
    obs_rule = g.split('"\\"observation\\""', 1)[1].split('"\\"issue\\""', 1)[0]
    assert '"null"' in obs_rule, f"observation is not nullable: {obs_rule!r}"


# ---------- 2. the prompt asks ----------

def test_both_citation_instructions_carry_the_observation_instruction():
    for name in ("CITATION_INSTRUCTION", "CITATION_INSTRUCTION_SUMMARY"):
        text = getattr(prompts, name)
        assert text.startswith(prompts.OBSERVATION_INSTRUCTION), (
            f"{name} does not open with the observation instruction")


def test_the_instruction_names_the_two_things_that_matter():
    """An observation is falsifiable AND about the page. The instruction has to
    say both, or the model writes an opinion and calls it an observation."""
    low = prompts.OBSERVATION_INSTRUCTION.lower()
    assert "falsifiable" in low and "on the page" in low
    assert "null" in low, "the instruction must license a null rather than an invention"


# ---------- 3. normalization ----------

def test_normalize_keeps_a_real_observation():
    out = _normalize_findings([{"category": "theme", "issue": "x",
                                "observation": "The word 'home' is never spoken."}], "theme")
    assert out[0]["observation"] == "The word 'home' is never spoken."


@pytest.mark.parametrize("raw", [None, "", "   ", "null", "None"])
def test_normalize_folds_an_empty_observation_to_none(raw):
    """The grammar lets a model write the literal string "null". Downstream the
    question is only ever 'did the model state one?', so that has to be one
    value, not four."""
    out = _normalize_findings([{"category": "theme", "issue": "x",
                                "observation": raw}], "theme")
    assert out[0]["observation"] is None


def test_normalize_supplies_the_key_when_a_model_omits_it():
    """The mock and demo models return findings with no `observation` at all —
    the key must exist and be None, not be missing."""
    out = _normalize_findings([{"category": "theme", "issue": "x"}], "theme")
    assert "observation" in out[0] and out[0]["observation"] is None


# ---------- 4. measured ----------

def test_observation_coverage_arithmetic():
    findings = [{"observation": "a claim"}, {"observation": None},
                {"observation": "  "}, {"observation": "another"}]
    cov = _observation_coverage(findings)
    assert cov["observation_bearing"] == 2
    assert cov["observation_pct"] == 50.0


def test_observation_coverage_is_none_over_nothing():
    """A percentage over nothing is a lie — the same rule verification_rate
    owns."""
    cov = _observation_coverage([])
    assert cov["observation_pct"] is None and cov["observation_bearing"] == 0


def test_the_report_discloses_the_coverage(sample_fountain):
    """The contract has to be readable from the artifact, not only from the
    code: the writer's 'how checkable is this?' question gets a computed
    answer."""
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer.report import to_findings_json
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay(sample_fountain)
    r = AnalysisResult(doc=doc, findings=[
        {"category": "theme", "issue": "x", "observation": "A claim.",
         "severity": "low", "scene_refs": [], "evidence_quote": None},
        {"category": "theme", "issue": "y", "observation": None,
         "severity": "low", "scene_refs": [], "evidence_quote": None},
    ])
    vs = to_findings_json(r)["verification_summary"]
    assert vs["observation_bearing"] == 1 and vs["observation_pct"] == 50.0
