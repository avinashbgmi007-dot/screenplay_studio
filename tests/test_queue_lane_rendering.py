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
4. **The queue is the only place a finding is rendered.** Spec 14.20, ONE HOME.
   `renderFixQueuePanel` carries the lanes now, and the Tier 2 scene/script
   sections are pointers. This replaced the old "the by-category key survives"
   guard, which pinned the very section that duplicated the queue.

**Migrated at 14.20.** No assertion was dropped. Guards 4 and 9 were rewritten
because their subject genuinely moved; guards 1-3, 5-8 are untouched.
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


def test_the_queue_is_the_only_place_a_finding_is_rendered(app_js: str) -> None:
    """Spec 14.20, ONE HOME. Was: "the by-category dockSection key survives."

    It pinned the Tier 2 ledger, which is exactly the surface that duplicated
    the Fix Queue. The guard has to move with the architecture: the section is
    gone, and what must now hold is that the ledger does NOT come back and that
    nothing below the queue renders findings as cards."""
    assert 'dockSection("by-category"' not in app_js, (
        'the Tier 2 "by-category" ledger is back. It renders report["findings"], '
        "which is the same array the Fix Queue renders, so restoring it puts "
        "every finding on the page twice with two sets of verbs. ONE HOME."
    )
    # the lanes moved UP into the queue, they did not die
    assert "groupByLane" in app_js, "the lane grouping left app.js entirely"


def test_the_tier_two_sections_are_pointers_not_cards(app_js: str) -> None:
    """The scene and script-level sections keep their keys and their audit hook,
    and keep telling the writer how many findings are there and where they
    went. They must not render finding bodies."""
    for key in ('"scene-findings"', '"script-level"'):
        assert key in app_js, f"the {key} section key vanished; audits open it by key"
    assert 'classList.add("dock-section-scene-findings")' in app_js, (
        "the audit hook on the scene-findings section is gone"
    )
    # `findingNoteEl` is the deep card renderer. It must NOT appear inside the
    # two Tier 2 pointer sections any more - that is precisely what made each
    # finding render twice on one page.
    ptr = re.search(r"let sceneSection = null;.*?sceneSection = dockSection\(\s*\n?", app_js, re.S)
    tail = app_js[app_js.index("let sceneSection = null;"): app_js.index("let scriptSection = null;")]
    assert "findingNoteEl" not in tail, (
        "the scene-findings section is rendering finding cards again. It is a "
        "pointer now; a card here duplicates the queue."
    )
    tail2 = app_js[app_js.index("let scriptSection = null;"): app_js.index("scriptSection = dockSection")]
    assert "findingNoteEl" not in tail2, (
        "the script-level section is rendering finding cards again."
    )
    assert "dock-pointer-line" in app_js, (
        "the Tier 2 sections are no longer pointers - either they went missing "
        "or they went back to rendering finding cards beside the queue."
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

def test_the_ranked_queue_leads_the_default_open_surface(app_js: str) -> None:
    """Gate G5, checked structurally. Was: "the queue is appended before the
    detail cards" - true while two queues existed.

    Now there is one queue, so the structural fact worth pinning is that it is
    built in TIER 1, the tier that opens by default. Lanes landing back in Tier
    2 would put the ranking behind a collapsed disclosure again."""
    fq = re.search(r"const fqWrap = el\(\"div\", \"dock-section-fixqueue\"\);", app_js)
    assert fq, "the dock's fix-queue section wrapper is gone"
    call = app_js.find("renderFixQueuePanel(fqWrap, { lanes: true })")
    assert call != -1, (
        "the Tier 1 queue is no longer built with the lanes. Either { lanes: "
        "true } was dropped or the call moved, and either way the ranking is "
        "not on the surface that opens by default."
    )
    assert 'defaultOpen: true' in app_js[call: call + 300], (
        "the fix-queue dock section no longer opens by default; the ranked rows "
        "would sit behind a closed header, which is the original fold complaint."
    )
