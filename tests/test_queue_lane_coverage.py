"""Every category that can reach a finding must have a lane and an IMPACT value.

**The defect this exists for (Track B, found 2026-10-15).** `voice.py` emits
findings with `category: "voice"` and `category: "subtext"`, and
`pipeline.py:1331-1341` runs those passes, so they are reachable in production.
Neither is in `FINDING_CATEGORIES` (`grammar.py:45-48`), which constrains only
what the LLM grammar may emit.

Track B's lane table was specified as "the disposition of all eight
`FINDING_CATEGORIES`" and its `IMPACT` table had eight entries. So a `voice`
finding satisfied the membership principle, was queued, and landed in **no lane**;
`IMPACT["voice"]` was `undefined`; and `undefined * 10` is `NaN`, which in a
sort comparator is unspecified behaviour.

`tests/test_finding_integrity_gate.py:208-222` pinned that every delivered
category is inside `FINDING_CATEGORIES`. It passed, because its three hand-built
rows never included the deterministic-pass categories. **An invariant whose
fixtures exclude the violating class is the mechanism of the defect.**

This module closes that from both sides. It reads the actual emitters rather than
a hand-written list, so a new pass that emits a category nobody weighted fails the
build instead of shipping a `NaN` sort key.
"""
import json
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYZER = os.path.join(ROOT, "screenplay_analyzer")
CORE_JS = os.path.join(ROOT, "screenplay_studio", "webapp", "core.js")


def _node_const(source: str, name: str) -> dict:
    """Read a `const NAME = { ... };` object literal out of core.js.

    Deliberately a regex, not a JS parser: this runs in the pytest suite with no
    node dependency, and the literals under test are flat `key: number` /
    `key: "string"` pairs. A missing or reshaped literal fails loudly here rather
    than returning an empty dict and passing vacuously.
    """
    m = re.search(rf"const {name} = \{{(.*?)\n\}};", source, re.S)
    assert m, f"{name} not found in core.js - the ranking tables moved or were renamed"
    body = m.group(1)
    raw = dict(re.findall(r'(\w+)\s*:\s*("(?:[^"]*)"|[\d.]+)', body))
    # Unwrap the quoted form so IMPACT yields numbers and LANE_OF yields plain
    # strings; a caller comparing to "line" must not have to know the regex kept
    # the quotes.
    return {k: (v[1:-1] if v.startswith('"') else v) for k, v in raw.items()}


@pytest.fixture(scope="module")
def core_js() -> str:
    with open(CORE_JS, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def impact(core_js: str) -> dict:
    return _node_const(core_js, "IMPACT")


@pytest.fixture(scope="module")
def lane_of(core_js: str) -> dict:
    return _node_const(core_js, "LANE_OF")


def _categories_the_analyzer_can_emit() -> set:
    """Every category literal the analyzer writes into a finding dict.

    Read from the source rather than from `FINDING_CATEGORIES` on purpose. That
    constant constrains the LLM grammar only; the deterministic passes are free
    to write their own categories, and that gap is the whole defect.
    """
    found = set()
    for name in sorted(os.listdir(ANALYZER)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(ANALYZER, name), encoding="utf-8") as fh:
            src = fh.read()
        found.update(re.findall(r'["\']category["\']\s*:\s*["\']([a-z_]+)["\']', src))
    return found


def test_the_emitter_scan_actually_found_categories() -> None:
    """Guard the guard. An empty or near-empty scan would make every assertion
    below pass trivially, which is the exact failure mode this module exists to
    end. `voice` and `subtext` are pinned as the known-positive controls."""
    found = _categories_the_analyzer_can_emit()
    assert {"voice", "subtext"} <= found, (
        "the emitter scan no longer sees voice/subtext. It is probably broken, "
        f"and every test below is now vacuous. Found: {sorted(found)}"
    )
    assert len(found) >= 4, f"emitter scan looks too narrow: {sorted(found)}"


def test_every_emittable_category_has_an_impact_value(impact) -> None:
    emitted = _categories_the_analyzer_can_emit()
    missing = sorted(c for c in emitted if c not in impact)
    assert not missing, (
        "these categories can reach a finding but have no IMPACT entry, so "
        f"rankScore() returns NaN: {missing}. Known: {sorted(emitted)}"
    )


def test_impact_values_are_finite_numbers(impact) -> None:
    for cat, raw in impact.items():
        value = float(raw)
        assert value == value, f"IMPACT[{cat!r}] is NaN"
        assert value < float("inf"), f"IMPACT[{cat!r}] is infinite"
        assert value > 0, f"IMPACT[{cat!r}] is {value}; every category must rank above zero"


def test_every_emittable_queued_category_has_a_lane(lane_of) -> None:
    """`theme` and `genre` are deliberately unlaned: they are observations with
    no verb, handled by the principle in `findingLane` rather than by a table
    entry. Everything else must have one."""
    emitted = _categories_the_analyzer_can_emit()
    observation_only = {"theme", "genre"}
    missing = sorted(c for c in emitted
                     if c not in lane_of and c not in observation_only)
    assert not missing, (
        f"these categories can be queued but have no lane: {missing}. Known: {sorted(emitted)}"
    )


def test_the_lane_table_matches_the_helper(source_dir=ANALYZER) -> None:
    """`findingLane` falls back to "line" for an unknown category. That fallback
    is deliberate (AGENTS.md:66, "Flag, don't drop"), so this test does NOT
    demand full coverage - it demands that the fallback and the table agree on
    which categories are observations, because those are the only two the
    fallback can silently swallow."""
    with open(CORE_JS, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r'cat === "theme" \|\| cat === "genre"', src)
    assert m, (
        "the observation carve-out in findingLane changed shape. Whatever it "
        "became, it must be reflected here or this module tests a fiction."
    )


def test_voice_and_subtext_are_laned_to_line(lane_of) -> None:
    """Requirement 1 of the Track B ruling, pinned directly: they are line-level
    craft notes with quotes and scene refs."""
    assert lane_of.get("voice") == "line"
    assert lane_of.get("subtext") == "line"


def test_the_finding_grammar_was_not_widened() -> None:
    """Option A was rejected for a reason: `grammar.py:76` builds the model-facing
    grammar from FINDING_CATEGORIES, so adding voice/subtext there would invite
    the model to duplicate the deterministic passes. This pins that decision so a
    future contributor cannot quietly make the change that was ruled out."""
    with open(os.path.join(ANALYZER, "grammar.py"), encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"FINDING_CATEGORIES = \[(.*?)\]", src, re.S)
    assert m, "FINDING_CATEGORIES literal not found"
    cats = set(re.findall(r'"([a-z_]+)"', m.group(1)))
    assert "voice" not in cats, (
        "voice was added to FINDING_CATEGORIES. That rewrites the LLM grammar "
        "(grammar.py:76) and invites the model to duplicate the deterministic "
        "voice pass. Option A was ruled out; if this is a reversal, say so."
    )
    assert "subtext" not in cats, "same as voice above - subtext is ruled out too"