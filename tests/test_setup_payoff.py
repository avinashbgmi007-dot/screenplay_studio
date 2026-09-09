"""Tests for the end-of-pipeline setup/payoff ledger pass."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_analyzer.grammar import setup_payoff_ledger_grammar
from screenplay_analyzer.setup_payoff import run_setup_payoff_ledger, dangling_findings, _seed_candidates
from screenplay_parser.knowledge_graph import build_knowledge_graph

SAMPLE = """Title: Ledger Test
Author: T

INT. ROOM - NIGHT

MARA holds a small CIGAR, turning it over.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. HALL - DAY

The CIGAR sits on the table, untouched.

MARA
(scared)
The debt is coming.
"""


def _parse(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _kg(text=None):
    return build_knowledge_graph(_parse(text or SAMPLE))


class FakeClient:
    def __init__(self, ledger=None, raise_err=None):
        self._ledger = ledger or {"ledger": []}
        self._raise = raise_err

    def chat_json(self, system, user, grammar=None, max_tokens=0, temperature=0.0):
        if self._raise:
            raise self._raise
        return self._ledger


class StubRules:
    def prompt_fragment_for_category(self, category):
        return ""

    def prompt_fragment_for_rule(self, rule):
        return ""

    def fragment_for_pass(self, pass_name):
        return ""


def test_seed_candidates_from_kg():
    kg = _kg()
    seeds = _seed_candidates(kg)
    assert any("PROMISE" in s for s in seeds)          # "I'll tell you everything"
    assert any("CIGAR" in s.upper() for s in seeds)    # recurring object across 2 scenes


def test_ledger_cleans_and_sorts():
    client = FakeClient(ledger={"ledger": [
        {"setup": "The cigar", "kind": "object", "setup_scenes": [1, 2], "payoff_scenes": None,
         "status": "dangling", "note": "Never lit."},
        {"setup": "The debt", "kind": "theme", "setup_scenes": [2], "payoff_scenes": [3],
         "status": "paid", "note": "Paid off in the last beat."},
        {"setup": "", "kind": "other", "setup_scenes": [], "payoff_scenes": None,
         "status": "paid", "note": ""},                       # empty setup — dropped
        {"setup": "Bad status", "kind": "other", "setup_scenes": [1], "payoff_scenes": None,
         "status": "whoops", "note": ""},                     # unknown status -> dangling
    ]})
    entries, errors = run_setup_payoff_ledger("overview", _kg(), client, "", 3)
    assert errors == []
    assert len(entries) == 3
    # dangling sorts first; unknown status defaulted to dangling
    assert entries[0]["status"] == "dangling"
    assert entries[0]["setup"] == "The cigar"
    assert entries[0]["payoff_scenes"] is None
    assert entries[1]["status"] == "dangling" and entries[1]["setup"] == "Bad status"
    assert entries[2]["status"] == "paid"


def test_ledger_error_surfaces():
    class Boom(Exception):
        pass
    client = FakeClient(raise_err=Boom("model down"))
    entries, errors = run_setup_payoff_ledger("overview", _kg(), client, "", 3)
    assert entries == []
    assert len(errors) == 1 and "failed" in errors[0]


def test_dangling_findings_deduped():
    existing = [
        {"category": "plot_thread", "issue": 'Promise never fulfilled: "I\'ll tell you everything"',
         "why_it_matters": "Set up in scene 1, never delivered."},
    ]
    ledger = [
        {"setup": "I'll tell you everything", "kind": "promise", "setup_scenes": [1],
         "payoff_scenes": None, "status": "dangling", "note": "Never delivered."},
        {"setup": "The cigar", "kind": "object", "setup_scenes": [1, 2],
         "payoff_scenes": None, "status": "abandoned", "note": "Left on the table."},
        {"setup": "The debt", "kind": "theme", "setup_scenes": [2], "payoff_scenes": [3],
         "status": "paid", "note": "Landed."},
    ]
    findings = dangling_findings(ledger, existing)
    # the promise overlaps the existing plot_thread finding -> deduped away
    assert len(findings) == 1
    assert "cigar" in findings[0]["issue"].lower()
    assert findings[0]["category"] == "plot_thread"
    assert findings[0]["rule_id"] == "setup_payoff_general"
    assert findings[0]["scene_refs"] == [1, 2]


def test_grammar_covers_statuses():
    g = setup_payoff_ledger_grammar()
    for s in ("paid", "dangling", "abandoned", "red_herring"):
        assert f"\\\"{s}\\\"" in g


def test_pipeline_integration():
    from screenplay_analyzer import pipeline

    doc = _parse(SAMPLE)

    class PipelineClient:
        def resolve_model(self):
            return "mock"

        def chat_json(self, system, user, grammar=None, max_tokens=0, temperature=0.0, **kw):
            if "summaries" in grammar:
                return {"summaries": [{"scene_number": s, "summary": "Mara and the debt."} for s in (1, 2)]}
            if "ledger" in grammar:
                return {"ledger": [
                    {"setup": "The cigar", "kind": "object", "setup_scenes": [1, 2],
                     "payoff_scenes": None, "status": "dangling", "note": "Never used."},
                    {"setup": "The debt", "kind": "theme", "setup_scenes": [2],
                     "payoff_scenes": [2], "status": "paid", "note": "Lands."},
                ]}
            return {"findings": []}

    result = pipeline.analyze(doc, PipelineClient(), run_categories=("setup_payoff",))
    assert result.category_outcomes["setup_payoff"] == "ok"
    assert len(result.setup_payoff) == 2
    assert result.setup_payoff[0]["status"] == "dangling"  # sorted first
    # dangling entry folded into findings (plot_thread)
    assert any(f["category"] == "plot_thread" and "cigar" in f["issue"].lower() for f in result.findings)
    # report renders the section + carries the key in JSON
    from screenplay_analyzer.report import render_markdown, to_findings_json
    md = render_markdown(result)
    assert "## Setup / Payoff" in md
    assert "🚩 Dangling" in md
    j = to_findings_json(result)
    assert j["setup_payoff"] == result.setup_payoff
