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
    gets re-inlined into app.js, that testability is lost silently.

    SPEC 14.54 moved where app.js ENTERS the lane code: the render and loopList
    both call core's queueProjection (bind -> admit -> groupByLane), so the call
    sites are asserted by their exact code lines, not by a bare name a comment
    could satisfy."""
    core_path = os.path.join(ROOT, "screenplay_studio", "webapp", "core.js")
    with open(core_path, encoding="utf-8") as fh:
        core = fh.read()
    assert "function groupByLane(entries)" in core, (
        "groupByLane is missing from core.js. The grouping must stay there: it "
        "is the only reason the lane logic is verifiable without Playwright."
    )
    assert "function queueProjection(" in core, (
        "SPEC 14.54: the ordered projection (binding -> admission -> lanes) "
        "must live in core.js — app.js's render AND loopList both consume it, "
        "and core is the only home verifiable without a browser."
    )
    assert "const laneCut = queueProjection(items" in app_js, (
        "renderFixQueuePanel no longer calls queueProjection — the ledger is "
        "not lane-grouped through the shared projection."
    )
    assert "const proj = queueProjection(items" in app_js, (
        "loopList no longer calls queueProjection — the keyboard loop walks the "
        "report again instead of the ranked queue (the 14.53 divergence)."
    )
    # ...and app.js must not have grown its own copies.
    assert "function groupByLane" not in app_js, (
        "app.js defines its own groupByLane. Two implementations of the lane "
        "rule will drift, and only one of them is under test."
    )
    assert "function queueProjection" not in app_js, (
        "app.js defines its own queueProjection. Two implementations of the "
        "queue walk will drift, and only one of them is under test."
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


E2E_DOCK = os.path.join(ROOT, "tests", "e2e_browser_dock_sections.py")


def test_the_e2e_does_not_reach_for_the_retired_section_key() -> None:
    """Spec 14.20. `by-category` no longer exists in the DOM.

    A selector naming it cannot fail loudly in a Playwright run — a locator that
    matches nothing either trips an assertion or, worse, is used as a "vehicle"
    that silently stops testing anything. The 176/0 result the runner withdrew
    was a suite that ran against the wrong tree; this is the guard that would
    have made the retirement visible in CI instead.
    """
    with open(E2E_DOCK, encoding="utf-8") as fh:
        lines = fh.readlines()
    live = [
        (i + 1, ln.rstrip()) for i, ln in enumerate(lines)
        if "by-category" in ln and not ln.lstrip().startswith("#")
    ]
    # Comments may name it — they are the migration record. CODE may not, in any
    # form. An earlier version of this guard exempted lines containing
    # data-key="by-category", which is exactly the selector form it exists to
    # catch, so the mutation test passed against a vacuous guard.
    offenders = [(n, t.strip()) for n, t in live]
    assert not offenders, (
        "the e2e still references the retired by-category dock section at "
        f"{offenders}. It was removed at spec 14.20; the ledger moved INTO the "
        "Fix Queue. Re-point it at the queue, or at another live section if it "
        "is only a vehicle for the collapse contract."
    )


def test_the_queue_row_keeps_its_depth_and_gains_the_verbs(app_js: str) -> None:
    """Spec 14.25. The merge replaced the deep card with the Fix Queue's
    `.fix-row` and deleted four agreements from the first debate off the primary
    worklist: the evidence quote, who said so, the finding's own observation,
    and the verdict the accuracy meter counts.

    The ruling: depth is not negotiable, verbs are additive. The lane row is the
    deep card WITH the verb row on it. This guard is here because that
    regression passed every other check in this file."""
    lane = app_js[app_js.index("if (options.lanes) {"):]
    assert "findingNoteEl(f, index, {" in lane, (
        "the lane row is no longer a deep card. Evidence, attribution, the "
        "observation and the truth verdict stop being visible in the worklist, "
        "and the accuracy meter has no surface to count."
    )
    assert "deep: true" in lane, "the lane row is not built with deep anatomy"
    # SPEC 14.31: the lane row contributes TRIAGE only. The deep card already
    # renders Locate/Rewrite/Discuss; appending a second set is what duplicated
    # six buttons doing three jobs and broke the one-row action budget.
    assert "buildFixActions(item, disp, fi, true)" in lane, (
        "the lane row is not mounting its triage verbs. The card has no Dismiss "
        "and P1.10 puts that gesture in the queue, so losing it here means "
        "nothing can be triaged from the worklist."
    )
    assert 'row.querySelector(".finding-note-actions")' in lane, (
        "triage must mount INTO the card's own action row. Appending it as a "
        "second row below is what broke the pinned one-row budget."
    )
    # Each verb is constructed exactly ONCE in the shared helper. The deep card
    # builds its own copy; a second construction here is the duplication back.
    # Scoped to the helper's body — a count taken to end-of-file also counts the
    # unrelated pin popup, and the first draft of this assertion failed on a
    # build that was correct.
    helper = app_js[app_js.index("const buildFixActions"):]
    helper = helper[: helper.index("\n  const buildFixRow")]
    for verb in ('"Locate"', '"Rewrite"', '"Discuss"'):
        assert helper.count(verb) == 1, (
            f"{verb} is constructed {helper.count(verb)} times in the shared verb "
            "helper. It must be built once; the card renders its own and "
            "re-rendering it here is what made one finding look like four "
            "competing surfaces."
        )
    # ...and the shallow row must not have quietly become the only renderer.
    assert "buildFixRow(item)" in app_js, "the flat report-page path lost its row"


def _js_only(code: str) -> str:
    """Strip comments and string/template literals.

    Without this the callee scan reads prose ("they disagree(") and quoted
    selectors, which is how the first draft of this guard produced 35 nonsense
    names and failed on a build that was fine."""
    out, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if c == "/" and i + 1 < n and code[i + 1] == "/":
            while i < n and code[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and code[i + 1] == "*":
            i += 2
            while i + 1 < n and not (code[i] == "*" and code[i + 1] == "/"):
                i += 1
            i += 2
        elif c in "\"'`":
            quote = c
            i += 1
            while i < n and code[i] != quote:
                i += 2 if code[i] == "\\" else 1
            i += 1
            out.append(' "" ')
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _module_scope_names(code: str) -> set:
    """Every binding visible at module scope, including destructured imports.

    core.js is pulled in as a destructured const, so a plain `^const NAME =`
    regex misses `groupByLane` and `rankReasonText` and reports them as phantom
    callees."""
    names = set(re.findall(r"^(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)", code, re.M))
    for m in re.finditer(r"^(?:const|let|var)\s+([^=\n]+)=", code, re.M):
        for part in m.group(1).split(","):
            part = part.strip()
            name = part.split(":")[-1].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                names.add(name)
    return names


def test_the_queue_renders_no_function_scoped_dependency(app_js: str) -> None:
    """Spec 14.26. Catches TEMPORAL DEAD ZONE defects in the queue's render path.

    `isAddressed` was a `const` arrow declared inside the Context builder at line
    6694. `renderFixQueuePanel` called it at 4642 and is itself invoked at 6643,
    all inside that same builder. First use, then declaration, same tick: a
    ReferenceError that aborted the Evidence lens before a single `.dock-section`
    mounted. The anchored run saw 3 passed / 14 failed and zero sections.

    Neither `node --check` nor pytest evaluates a browser render path, so this
    walks the queue's body, collects the BARE identifiers it calls, and fails on
    any that is neither declared at module scope nor declared inside the
    function. A callee bound to a `const` in another builder is exactly the
    defect, and this is the only check in the repository that can see it."""
    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "core.js"),
              encoding="utf-8") as fh:
        core = fh.read()
    # core.js is loaded by a plain <script src="core.js"> tag, so its top-level
    # `function` declarations land on window and are visible from app.js as
    # bare globals. Without folding them in, groupByLane and rankReasonText read
    # as phantom callees.
    code = _js_only(app_js + "\n" + core)
    m = re.search(r"function renderFixQueuePanel\(([^)]*)\)\s*\{", code)
    assert m, "renderFixQueuePanel not found"
    start = code.index("{", m.start())
    depth, end = 0, None
    for i in range(start, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    assert end, "could not find the end of renderFixQueuePanel"
    body = code[start:end]

    module_scope = _module_scope_names(code)
    local = set(re.findall(r"\b(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)", body))
    for pm in re.finditer(r"\b(?:const|let|var)\s+([^=\n{]+)=", body):
        name = pm.group(1).split(",")[0].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            local.add(name)
    local |= {p.strip() for p in m.group(1).split(",") if re.fullmatch(r"[A-Za-z_$][\w$]*", p.strip())}

    BUILTIN = {
        "if", "for", "while", "switch", "catch", "return", "typeof", "await",
        "function", "Array", "Object", "String", "Number", "Boolean", "Math",
        "JSON", "Date", "Map", "Set", "Promise", "Error", "parseInt", "parseFloat",
        "isNaN", "encodeURIComponent", "decodeURIComponent", "require",
        "async", "fetch",
    }
    # only BARE calls - `x.foo(` is a method, and `x . foo(` is never a TDZ bug
    called = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", body))
    unresolved = sorted(called - module_scope - local - BUILTIN)
    assert not unresolved, (
        f"renderFixQueuePanel calls {unresolved}, which is not declared at module "
        "scope and not declared inside the function. If one of them is a `const` "
        "in some other builder, that is a TEMPORAL DEAD ZONE defect: this function "
        "is invoked before that declaration runs, so the lens throws and renders "
        "nothing. `isAddressed` did exactly this and it shipped."
    )


E2E_DOCK_2 = E2E_DOCK


def test_every_seed_that_writes_findings_also_writes_queue_items() -> None:
    """Spec 14.29. Roughly 36 anchored failures traced to one omission.

    A seed that replaces `state.findings` and calls `refreshAllFindingSurfaces`
    used to be enough, because the ledger read `report.findings`. After 14.20
    the queue renders from `state.fixQueue.items`, so a seed that writes only
    `state.findings` produces ZERO queue rows — not mis-ordered rows, absent
    ones. That is silent: the seed reports success and every downstream check
    reads zero.

    The fix for rows mis-binding to shifted indices was in app.js; this is the
    other half. An id-accurate join cannot conjure an item that was never
    written, so each seed must write its own items.

    Payloads are matched as WHOLE triple-quoted strings, not as a character
    window: a window version of this guard passed while a mutation deleted one
    seed's items block, because the window reached into the next seed and found
    that one's block instead."""
    with open(E2E_DOCK_2, encoding="utf-8") as fh:
        code = fh.read()
    payloads = code.split('\"\"\"')
    # odd indices are the JS payloads between the triple quotes
    seeds = [(i, p) for i, p in enumerate(payloads) if i % 2 == 1
             and re.search(r"state\.findings\s*=\s*\w+;", p)]
    assert len(seeds) >= 4, (
        f"expected at least 4 seeded payloads writing state.findings, found "
        f"{len(seeds)} - has the fixture moved?"
    )
    # Match on CODE, not on the file text: the block this guard is about opens
    # with a comment that NAMES state.fixQueue.items, so a text match was
    # satisfied by the comment alone. Deleting the assignment left the comment
    # and the guard passed - it took a second mutation to notice.
    missing = [i for i, payload in seeds
               if "state.fixQueue.items" not in _js_only(payload)]
    assert not missing, (
        f"seed payload(s) at quote-block index {missing} write state.findings "
        "but never write state.fixQueue.items. They render ZERO queue rows and "
        "every assertion downstream of them reads zero."
    )


def test_the_scene_chip_counts_the_scope_the_list_shows(app_js: str) -> None:
    """N3. The This-scene chip's number and the list printed beside it must be
    the same scope.

    `openFindingsOnScene` walked `state.findings`, which includes rows the queue
    HIDES behind the Kit A ungrounded toggle. The chip therefore printed a
    grounded count next to an unfiltered list: two numbers, both true, not
    agreeing. The fix counts `state.fixQueue.items` through the SAME exclusion
    rule as `queueCounts`, so there is one rule and three surfaces.

    SPEC 14.54: the clause itself now lives in its ONE helper
    (ungroundedRowVisible), read by this count, queueCounts, inFindingFilter and
    the keyboard loop. The guard follows it: the function must read the helper,
    and the helper must be where the toggle clause actually lives."""
    fn = app_js[app_js.index("function openFindingsOnScene"):]
    fn = fn[: fn.index("\n}\n")]
    assert "state.fixQueue.items" in fn, (
        "the scene chip's count no longer walks the queue's items, so it can "
        "disagree with the list beside it. That is the N3 violation."
    )
    assert "ungroundedRowVisible" in fn, (
        "the scene chip's count ignores the Kit A toggle, so a hidden ungrounded "
        "row is counted by the label and not shown in the list."
    )
    helper = app_js[app_js.index("function ungroundedRowVisible"):]
    helper = helper[: helper.index("\n}\n")]
    assert "fixQueueShowUngrounded" in helper, (
        "SPEC 14.54: the Kit A clause must live in its one helper; the surface "
        "above reads the helper, so a missing toggle check here silently reverts "
        "the count to the pre-fix spread."
    )
    # and it must not have gone back to reading state.findings directly
    assert "state.findings || []).forEach" not in fn, (
        "the chip counts findings, not queue rows, which is how the two scopes "
        "started disagreeing."
    )


def test_the_queue_is_the_only_surface_that_opts_into_the_collapse(app_js: str) -> None:
    """Spec 14.38. The intent cluster collapses on the queue row only.

    Off everywhere else on purpose: the report page and margin pins keep the
    flat row, because only the queue stacks its Dismiss on top of the card's
    controls and only the queue overflows the measured budget."""
    assert app_js.count("collapseIntents: true") == 1, (
        "exactly one call site opts into the collapsed intent cluster. More than "
        "one means a surface that keeps its own budget was changed too; zero "
        "means the nine-control row is back."
    )
    assert 'const intentCluster = opts.collapseIntents' not in app_js, (
        "the intent cluster must be a hoisted `let`, not a const inside the deep "
        "block: the disclosure that wraps it is built after that block closes."
    )
    # The gate itself, not just the call-site count. Counting call sites passes
    # even when the wrap is unconditional, which is the mutation this missed
    # first: the collapse silently became global and every other surface lost
    # its flat row.
    assert "if (opts.collapseIntents && intentCluster !== actions)" in app_js, (
        "the disclosure is no longer gated on opts.collapseIntents, so the "
        "collapse applies to every surface. The report page and margin pins keep "
        "the flat row on purpose; only the queue overflows its budget."
    )


def test_the_disclosure_is_a_flex_item_not_a_block(app_js: str) -> None:
    """Spec 14.42, the geometry lesson.

    The first collapse attempt set `display: inline-block` on the disclosure and
    it changed nothing, because `.finding-note-actions` is `display: flex` and a
    flex child's `display` is blockified whatever it says. The disclosure was
    already a flex ITEM in the row; the row wrapped on WIDTH, not layout mode.

    So the budget fix is the label, not the display mode, and the CSS pins the
    flex behaviour rather than pretending a `display` declaration is load-bearing."""
    css_path = os.path.join(ROOT, "screenplay_studio", "webapp", "style.css")
    with open(css_path, encoding="utf-8") as fh:
        css = fh.read()
    assert ".dock-section .finding-note-actions { flex-wrap: wrap" in css, (
        "the actions row no longer wraps; the pin-rewrap check measures that same "
        "second row, so the rule and the gate have drifted apart."
    )
    block = css[css.index(".finding-intent-disclosure {"):]
    block = block[: block.index("}")]
    assert "flex: 0 0 auto" in block, (
        "the disclosure is not pinned as a non-shrinking flex item, so it can be "
        "squeezed and the row wraps for a reason that is not the label length."
    )
    # the visible word is short enough to fit; the full phrase lives in the name
    assert 'el("summary", "", "marks")' in app_js, (
        'the disclosure label is long again ("marks & tools" cost ~90px of a '
        "322px budget and put the fifth item on a second row)."
    )
    assert 'setAttribute("aria-label", "Marks and tools")' in app_js, (
        "shortening the visible label must not remove the full phrase from the "
        "accessible name; P1.10 wants the gesture learnable, and a screen reader "
        "user gets only the name."
    )
