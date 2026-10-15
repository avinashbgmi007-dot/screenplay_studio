"""Source guards for Track B section 7 — the lane-grouped findings ledger.

These are **source** checks, not browser checks. They run on every pytest
invocation and they cover the four §7 invariants that can be established from
the markup alone. The rendered behaviours — G5's fold position, G6's rank
reason being *readable*, G7's headers being above the fold — need a browser and
are the runner's; this file exists so the things a browser would catch third are
already caught first.

**What each one protects.**

1. **Category chips left the filter row.** §7 moves them into the lanes. If they
   come back, the filter row spends its width on a taxonomy the queue already
   shows, and G4's "chip count <= 6" quietly regresses.
2. **The lane headers still set the filter.** Removing the chips without giving
   the filter a second door would strand `findingFilter.category`: the field
   would be set by nothing, and pressing a header could not widen the view.
3. **`findingPassesFilter` is still the only lane-bearing predicate.** §1.4 trap
   2: a second predicate is how GAP-1 comes back — the page and the ledger
   disagreeing, 15 cards against 9 rows.
4. **The "by-category" dockSection key survives.** It is the hook
   `e2e_browser_dock_sections.py` opens the section by. Renaming it to
   "by-lane" for tidiness would silently unhook the whole suite.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "screenplay_studio", "webapp", "app.js")


@pytest.fixture(scope="module")
def app_js() -> str:
    with open(APP_JS, encoding="utf-8") as fh:
        return fh.read()


def test_the_source_read_is_not_trivially_empty(app_js: str) -> None:
    """Guard the guard. An APP_JS that failed to read would make every assertion
    below pass or fail for the wrong reason."""
    assert len(app_js) > 100_000, f"app.js looks truncated: {len(app_js)} chars"
    assert "function buildDockLens" in app_js or "findingPassesFilter" in app_js


def test_category_count_chips_left_the_filter_row(app_js: str) -> None:
    """The filter row no longer builds category count-chips."""
    assert "catCounts" not in app_js, (
        "the category count-chip loop is back in the filter row. Track B "
        "section 7 moved those chips into the lanes; their counts now ride the "
        "lane's own category header."
    )


def test_the_lane_headers_still_drive_the_category_filter(app_js: str) -> None:
    """Removing the chips must not have removed the filter's only door."""
    m = re.search(
        r"state\.findingFilter\.category = active \? null : cat", app_js)
    assert m, (
        "nothing sets state.findingFilter.category any more. The lane category "
        "headers are the replacement door and they must still set exactly the "
        "field the filter-row chips set."
    )


def test_no_second_predicate_grew_a_lane_check(app_js: str) -> None:
    """§1.4 trap 2. `inFindingFilter` and `findingPassesFilter` are two existing
    predicates with overlapping clauses — a pre-existing duplication this work
    does not touch. What must never happen is either growing a LANE clause,
    which would fork admission and bring GAP-1 back."""
    for name in ("findingPassesFilter", "inFindingFilter"):
        start = app_js.find(f"function {name}(")
        assert start != -1, f"{name} vanished — re-check section 1.4 trap 2"
        body = app_js[start:start + 2000]
        body = body.split("\n}")[0]
        assert "findingLane(" not in body, (
            f"{name} now calls findingLane. A lane check inside a PREDICATE "
            "decides admission, and admission has exactly one predicate "
            "(spec 1.4 trap 2). Lanes are presentational: groupByLane filters "
            "nothing, it is handed rows the predicate already admitted."
        )


def test_the_by_category_section_hook_survives(app_js: str) -> None:
    """G8. The dock section key is the harness hook, not a name."""
    assert 'dockSection("by-category"' in app_js, (
        'the ledger section key changed. e2e_browser_dock_sections.py opens '
        'this section by the literal "by-category" in 21 places; renaming it '
        "for tidiness silently unhooks the suite."
    )


def test_every_queue_row_prints_its_rank_reason(app_js: str) -> None:
    """G6. Spec 1.5: a row that cannot print its own reason is not ranked."""
    assert 'el("div", "dock-rank-reason", rankReasonText(f))' in app_js, (
        "the ledger no longer appends a rank-reason to each row. Gate G6 "
        "requires every queue row to render it."
    )


def test_lane_grouping_is_pure_and_centralised(app_js: str) -> None:
    """The grouping lives in core.js so it is testable without a browser. If it
    gets re-inlined into app.js, that testability is lost silently."""
    core_path = os.path.join(ROOT, "screenplay_studio", "webapp", "core.js")
    with open(core_path, encoding="utf-8") as fh:
        core = fh.read()
    assert "function groupByLane(entries)" in core, (
        "groupByLane is missing from core.js. The grouping must stay there: it "
        "is the only reason the lane logic is verifiable without Playwright."
    )
    assert "groupByLane(" in app_js, (
        "app.js no longer calls groupByLane — the ledger is not lane-grouped."
    )
    # ...and app.js must not have grown its own copy.
    assert "function groupByLane" not in app_js, (
        "app.js defines its own groupByLane. Two implementations of the lane "
        "rule will drift, and only one of them is under test."
    )


def test_severity_is_still_an_attribute_not_an_ordering(app_js: str) -> None:
    """§7 keeps severity displayed and drops it as the sort key. The old
    `SEV_RANK` ordering table must be gone from the ledger; the severity CHIP
    row and the severity attributes must remain, because the filter still uses
    them and DESIGN.md's rim/mass/label language is verified in use."""
    assert "const SEV_RANK = { high: 0, medium: 1, low: 2 };" not in app_js, (
        "the ledger's SEV_RANK ordering is back. Craft impact replaces severity "
        "as the sort key (section 7); severity stays an attribute and a filter."
    )
    assert "findingFilter.severities" in app_js, (
        "the severity filter disappeared. Section 7 keeps severity chips; it "
        "only stops severity being the ORDER."
    )