"""gun_pen.pdf — Full Feedback-Projection Audit (session-only, real model).

Walks every feedback surface the backend emits against the real gun_pen
report, per docs/gun_pen.pdf_full_feedback_audit_<...>.plan.md. Connects to an
ALREADY-RUNNING studio pointed at the real llama-server (never boots the demo
model — the audit's whole point is real-findings depth).

  E2E_BASE=http://127.0.0.1:8500 python tests/e2e_browser_gun_pen_audit.py [stage]
  stage = matrix | escalation | inbetween | pass2 | all   (default all)

Screenshots and results land in gitignored scratch:
`impl-shots/runs/latest/` (audit_results.json included). Set AUDIT_PROMOTE=1 to
write into the versioned `impl-shots/` instead — see the note at SHOTS below for
why that is a deliberate act and not the default.
No production code changes; gaps are filed in NOTES.md by the operator.

P1.6: the Evidence ledger's sections are collapsed by default, and a closed body
is hidden (not painted, not in the a11y tree, not part of innerText). Every stage
below that inspects or clicks INSIDE a section opens the sections first
(open_dock_section_holding) — the writer's own move.
"""
import json
import os
import re
import sys
import time

import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)  # for screenplay_studio / screenplay_cowriter imports
from e2e_browser_common import (Checks, launch, note,  # noqa: E402
                                open_dock_section_holding, studio_headers)

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8500").rstrip("/")
PROJECT = os.environ.get("GUNPEN_PROJECT", "gun_pen_2")
# Where this run writes. Top-level `impl-shots/` is EVIDENCE: the verdict tables
# in docs/ cite those exact filenames, and a run used to write straight over them
# — so a table's screenshots were silently swapped for post-fix images, which
# FULL_FEEDBACK_AUDIT_VERDICTS.md filed as "a small honesty bug of the same family
# this document exists to catch". A run now lands in gitignored scratch, and
# refreshing the versioned set is the explicit act AUDIT_PROMOTE=1.
#
# The scratch path is deliberately STABLE ("latest") rather than timestamped:
# stages are separate processes that accumulate through audit_results.json, so a
# per-run directory would make a later stage silently start from nothing.
PROMOTE = os.environ.get("AUDIT_PROMOTE") == "1"
SHOTS = (os.path.join(_REPO_ROOT, "impl-shots") if PROMOTE
         else os.path.join(_REPO_ROOT, "impl-shots", "runs", "latest"))
os.makedirs(SHOTS, exist_ok=True)

checks = Checks()
check = checks.ok
RESULTS = {}
# A GAP is a product promise the desk does not keep (the audit's finding) —
# distinct from a harness failure. Gaps do not fail the run; they are filed.
GAPS = []
# which stage is running — stamped on every gap so a re-run can RETIRE the gaps
# that stage no longer produces (a plain merge accumulates stale findings forever)
CURRENT_STAGE = {"name": None}


def gap(name, cond, detail=""):
    """Record a product gap. `cond` True == the promise holds (no gap)."""
    holds = bool(cond)
    print(f"  {'ok  ' if holds else 'GAP '} {name}" + (f"  [{detail}]" if detail else ""))
    if not holds:
        GAPS.append({"gap": name, "detail": detail, "stage": CURRENT_STAGE["name"]})
    return holds


def api(method, path, **kw):
    headers = dict(kw.pop("headers", None) or {})
    headers.update(studio_headers(BASE))  # no-op unless the studio is token-protected
    r = requests.request(method, BASE + path, timeout=kw.pop("timeout", 60),
                         headers=headers, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def shot(page, name, full=False):
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path, full_page=full)
    print(f"    [shot] {name}")
    return path


def _working_texts(project_dir):
    """(scene_number, element_text) for the working copy."""
    with open(os.path.join(project_dir, "working.json"), encoding="utf-8") as f:
        doc = json.load(f)
    return [(s.get("scene_number"), el.get("text") or "")
            for s in doc.get("scenes", []) for el in s.get("elements", [])]


def _quote_present(texts, quote):
    """Mirrors revision.quote_present: exact substring, then fuzzy >= 0.95."""
    from difflib import SequenceMatcher
    q = (quote or "").strip()
    if not q:
        return False
    if any(q in t for t in texts):
        return True
    return any(SequenceMatcher(None, t, q).ratio() >= 0.95 for t in texts if t)


def shelf_label():
    """The shelf renders the project's TITLE (e.g. 'gun_pen'), not its dir name."""
    try:
        for x in api("GET", "/api/projects"):
            if x.get("project") == PROJECT:
                return x.get("title") or PROJECT
    except Exception:
        pass
    return PROJECT


def open_project(page, name, label=None):
    # domcontentloaded, not networkidle: the shell fires POST /api/test-connection
    # (a live probe of llama-server) on boot, and against a loaded model that can
    # exceed the networkidle window — the page is ready long before the probe is.
    page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("#shelf-trigger", timeout=20000)
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    row = page.locator(".project-item").filter(has_text=label or shelf_label())
    if not row.count():
        row = page.locator(".project-item").filter(has_text=name)
    row.first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=30000)
    page.wait_for_timeout(600)


def open_dock(page, lens="evidence"):
    if not page.locator("#context-dock.open").count():
        page.locator("#right-edge-affordance").click()
        page.wait_for_selector("#context-dock.open", timeout=8000)
        page.wait_for_timeout(500)
    page.locator(f"#dock-tab-{lens}").click()
    page.wait_for_timeout(500)


def widen_filter(page, lens):
    """Turn Medium + Low severity chips ON so every finding card shows.

    Returns the labels it actually toggled. `aria-pressed` is the app's own
    statement of the filter state, so that is what is read — a click that
    silently no-ops is otherwise invisible, and the check that follows
    (`wide >= default`) passes for `x >= x`.
    """
    toggled = []
    for label in ("Medium", "Low"):
        chip = lens.locator(".fchip", has_text=label).first
        if not chip.count():
            continue
        if chip.get_attribute("aria-pressed") == "true":
            continue
        chip.click()
        page.wait_for_timeout(450)
        toggled.append(label)
    return toggled


# ---------------------------------------------------------------------------
# STEP 1 — probe (deterministic, no browser)
# ---------------------------------------------------------------------------

def step_probe():
    import pypdf
    pdf = os.path.join(os.path.dirname(SHOTS), "studio_projects", PROJECT, "source.pdf")
    r = pypdf.PdfReader(pdf)
    txt = "\n".join((p.extract_text() or "") for p in r.pages)
    probe = {
        "pdf_pages": len(r.pages),
        "text_layer_chars": len(txt),
        "int_ext_headings": len(re.findall(r"(?m)^\s*(INT|EXT)[\. ]", txt)),
    }
    rep = api("GET", f"/api/projects/{PROJECT}/report")
    findings = rep.get("findings") or []
    sc = api("GET", f"/api/projects/{PROJECT}/script")
    probe.update({
        "findings": len(findings),
        "scenes": len(sc.get("scenes") or []),
        "report_keys": sorted(rep.keys()),
    })
    RESULTS["probe"] = probe
    print("STEP 1 — probe:", json.dumps(probe, ensure_ascii=False))
    check("probe: text layer present (no OCR contingency)", probe["text_layer_chars"] > 2000)
    check("probe: short-form script recorded honestly (<=6 scenes)", probe["scenes"] <= 6,
          f"{probe['scenes']} scenes / {probe['pdf_pages']} pages")


# ---------------------------------------------------------------------------
# STEP 2/3 — baseline + split-matrix walk
# ---------------------------------------------------------------------------

CATEGORY_LABELS = {
    # must match app.js CATEGORY_LABELS verbatim, or a label mismatch reads as a
    # missing category (plot_thread renders as "Plot economy", not "Plot")
    "dialogue": "Dialogue", "structure": "Structure", "scene_function": "Scene function",
    "character": "Character", "theme": "Theme", "genre": "Genre",
    "plot_thread": "Plot economy",
    "continuity": "Continuity", "principles": "Principles", "setup_payoff": "Setup",
}


def step_matrix():
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, PROJECT)
        open_dock(page, "evidence")
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        # P1.6: every Evidence section is collapsed by default and a closed body
        # is hidden (not painted, not in the a11y tree, and NOT part of
        # innerText — `all_inner_texts()` sees "" inside it). This audit exists
        # to inspect what each panel RENDERS, so it opens them all first — the
        # writer's own move, once per section.
        _opened = open_dock_section_holding(page, ".dock-section-body")
        note("P1.6: dock sections opened for the audit", f"{_opened} section(s)")

        # -- STEP 2: baseline ------------------------------------------------
        shot(page, "A00-baseline-board.png")
        mass = lens.locator(".dock-mass-strip")
        check("baseline: mass strip renders", mass.count() > 0)
        mass_text = mass.inner_text() if mass.count() else ""
        trust = lens.locator(".dock-trust").first
        trust_text = trust.inner_text() if trust.count() else ""
        check("baseline: trust readout renders on the mass strip", bool(trust_text),
              trust_text)
        check("baseline: trust readout is the 'N of M verified (P%)' shape",
              bool(re.search(r"\d+ of \d+ quotes verified \(\d+%\)", trust_text)), trust_text)
        default_cards = lens.locator(".finding-note").count()
        check("baseline: highs-only default shows fewer cards than the full set",
              0 < default_cards, f"{default_cards} cards at default")
        print(f"    mass: {mass_text.splitlines()[:2]}  trust: {trust_text}")

        # -- cross-cutting: the counting contract (N3) ------------------------
        # With zero edits made, EVERY finding must read open. The server's own
        # observed-status report is the second opinion.
        ed = api("GET", f"/api/projects/{PROJECT}/edits")
        fsum = (ed.get("findings_status") or {}).get("summary") or {}
        n_findings = len(api("GET", f"/api/projects/{PROJECT}/report").get("findings") or [])
        RESULTS["findings_status_summary"] = fsum
        RESULTS["findings_total"] = n_findings
        gap("C: unedited script -> zero phantom 'addressed' findings",
            fsum.get("addressed", 0) == 0,
            f"server observes addressed={fsum.get('addressed')} still_present={fsum.get('still_present')} "
            f"unknown={fsum.get('unknown')} of {n_findings}")
        # What does the counting contract say is open? Asked of the app, because
        # "open" is decided by the writer's MARKS (`findingDisposition`) while
        # the server's `findings_status` above counts EDITS. Two different
        # stores — and conflating them is exactly what made the next check file
        # a false gap: it demanded open == total on the grounds that the script
        # was unedited, when an unedited script can still carry marks.
        # Measured: "29 open of 31" with 2 findings marked addressed. Correct.
        open_count = page.evaluate(
            """() => ((state.report && state.report.findings) || [])
                       .filter((f, i) => findingDisposition(f, i) === 'open').length""")
        m = re.search(r"(\d+) open of (\d+) findings", mass_text)
        # Two claims, and only the first is independent of the app's own
        # arithmetic: the total must be the report's finding count, and the open
        # count must agree with the contract the strip is built from.
        gap("C: the mass strip's counts agree with the report and the counting contract",
            bool(m) and int(m.group(2)) == n_findings and int(m.group(1)) == open_count,
            f"mass strip says '{m.group(0)}' but the report has {n_findings} findings "
            f"and the contract reports {open_count} open (the difference is the writer's "
            f"marks, not their edits)"
            if m else mass_text[:60])
        shot(page, "C00-phantom-addressed.png")
        # the desk's own status line vs the finding count (refreshDeskToolbar
        # runs at project-open BEFORE state.findings loads and is never re-run)
        ds = page.locator("#desk-analyze-status")
        ds_txt = ds.inner_text() if ds.count() else ""
        RESULTS["desk_status"] = ds_txt
        gap("C: the desk status line agrees with the finding count",
            n_findings == 0 or "clean bill" not in ds_txt.lower(),
            f"status reads {ds_txt[:90]!r} while the report has {n_findings} findings")
        shot(page, "C01-desk-status.png")

        widened = widen_filter(page, lens)
        page.wait_for_timeout(500)
        wide_cards = lens.locator(".finding-note").count()
        check("widen: Medium+Low reveal every finding card", wide_cards >= default_cards,
              f"{default_cards} -> {wide_cards}")
        if not widened:
            # Said out loud rather than passing quietly: on a project whose
            # default filter already admits every severity, the click above is a
            # no-op and this check is satisfied by `x >= x`. That is not a
            # failure — it is a check that did not get to do its job, which is
            # worth seeing in the output.
            note("widen: the default filter already admitted Medium+Low",
                 "the widen was a no-op, so 'wide >= default' asserted nothing here")
        shot(page, "A01-widened-board.png")

        # -- row A: finding-emitting categories ------------------------------
        titles = lens.locator(".dock-section-title").all_inner_texts()
        titles_join = " | ".join(titles)
        # Which categories SHOULD have a section? The ones the ACTIVE FILTER
        # ADMITS — asked of the app, not assumed, because the dock's section list
        # is dynamic (`app.js` groups `state.report.findings` through
        # `findingPassesFilter`) and a category whose only finding the writer has
        # marked `addressed`, or left `deferred` while that toggle is off, is
        # CORRECTLY absent.
        #
        # Measured: requiring a section for every emitted category filed a false
        # PRODUCT gap for `continuity` — its one finding is `addressed`
        # (id f1atq8x7, from the writer's own marks), so the board is right to
        # hide it, and the strip's "29 open of 31" is right for the same reason
        # (31 - 2 addressed). What this row is for is the RENDER: an admitted
        # finding whose category gets no section is a finding the writer cannot
        # see. The filter itself has its own checks.
        admitted = page.evaluate(
            """() => {
                 const fs = (state.report && state.report.findings) || [];
                 const out = {};
                 fs.forEach((f, i) => {
                   if (findingPassesFilter(f, i)) {
                     const c = f.category || 'other';
                     out[c] = (out[c] || 0) + 1;
                   }
                 });
                 return out;
               }""")
        row_a = []
        for cat in ("dialogue", "theme", "character", "structure",
                    "scene_function", "genre", "plot_thread", "continuity"):
            label = CATEGORY_LABELS[cat]
            if cat not in admitted:
                row_a.append((cat, None))
                note(f"A/{cat}: no section expected",
                     "the filter admits no finding in this category "
                     "(every one is marked addressed/dismissed, or deferred with that toggle off)")
                continue
            present = label.lower() in titles_join.lower()
            row_a.append((cat, present))
            # A category the report emits AND the filter admits, but the board
            # does not render, is a PRODUCT gap (the finding never reaches the
            # writer), not a harness failure — so it is filed, not counted
            # against the run.
            gap(f"A/{cat}: the category section reaches the board", present,
                f"{label!r} absent from: {titles_join[:140]} "
                f"({admitted[cat]} admitted finding(s) would go unseen)")
        # principles + setup_payoff — the plan's split-matrix rows
        row_a.append(("principles", "Principles" in titles_join))
        # The row above already records the truth. `check(name, True, "principles
        # produced no findings on this script")` asserted nothing and its detail
        # was never printed (Checks.ok prints detail on FAILURE only), so it was
        # an invisible no-op that inflated the passed count.
        note("A/principles: section present (or honestly absent)",
             f"Principles in titles={row_a[-1][1]}")
        RESULTS["row_a"] = row_a

        # per-category screenshot: scroll the section into view.
        # NOTE the `has=` locator must be PAGE-rooted, not lens-rooted: Playwright
        # re-roots `has` against each candidate, so a lens-scoped inner locator
        # resolves to `.dock-section >> .dock-lens >> .dock-section-title` and
        # matches nothing (this silently produced zero shots on the first run).
        for cat in ("dialogue", "structure", "scene_function"):
            label = CATEGORY_LABELS[cat]
            sec = lens.locator(".dock-section",
                               has=page.locator(".dock-section-title", has_text=label)).first
            if sec.count():
                sec.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                shot(page, f"A-{cat}.png")
            else:
                # not a separate gap — the missing section is already filed above
                # as "A/<cat>: the category section reaches the board"
                print(f"    [no shot] {cat}: no section to photograph")

        # -- row A: the margin ink layer (the 'where is the flaw' answer) -----
        # Ink anchors require an OPEN finding that CARRIES a quote and names a
        # scene. A quoted finding hidden as "addressed" (GAP-6) therefore loses
        # its pin, and a script-level finding (scene_refs []) never had one.
        ink_pins = page.locator(".finding-ink").count()
        inkable = page.evaluate(
            """() => (state.findings||[]).filter((f,i) =>
                   findingOpen(f,i) && (f.evidence_quote||'').trim() && (f.scene_refs||[]).length
               ).length"""
        )
        quoted_total = page.evaluate(
            """() => (state.findings||[]).filter(f => (f.evidence_quote||'').trim()).length"""
        )
        RESULTS["ink"] = {"pins": ink_pins, "inkable": inkable, "quoted": quoted_total}
        gap("A/ink: the manuscript carries margin ink for its quoted findings",
            ink_pins > 0,
            f"{ink_pins} pins rendered; {inkable} of {quoted_total} quoted findings are "
            f"both open and scene-anchored")

        # -- row A: trust chips on deep cards --------------------------------
        verified_badges = lens.locator(".finding-deep-badge.verified").count()
        unverified_badges = lens.locator(".finding-deep-badge.unverified").count()
        check("A: verified deep cards carry the trust chip", verified_badges > 0,
              f"{verified_badges} verified badges")
        check("A: no_quote findings are flagged unverified, never dropped",
              unverified_badges > 0, f"{unverified_badges} unverified badges")
        RESULTS["badges"] = {"verified": verified_badges, "unverified": unverified_badges}

        # -- row A: severity is never colour-alone ---------------------------
        sev_texts = lens.locator(".fix-row .sev-badge").all_inner_texts() or \
            lens.locator(".dock-mass-mark").all_inner_texts()
        check("A: severity carries a printed label (never colour-alone)",
              any(t.strip() for t in sev_texts), str(sev_texts[:6]))

        # -- orientation surfaces -------------------------------------------
        check("C: script ruler renders (diagnostic weight by scene)",
              lens.locator(".dock-ruler-track").count() > 0)
        # A census, not an invariant: the spine may legitimately be absent, so
        # `count() >= 0` was a tautology dressed as a render check. The count is
        # the payload — print it.
        note("C: setup/payoff spine",
             f"{lens.locator('.dock-sp-spine').count()} spine element(s)")

        # -- row B: report-section panels ------------------------------------
        craft_titles = lens.locator(".dock-craft .craft-panel-title").all_inner_texts()
        craft_join = " | ".join(craft_titles)
        row_b = {}
        row_b["pacing"] = lens.locator(".pacing-svg").count() > 0
        row_b["characters_panel"] = "character" in craft_join.lower()
        row_b["writer_mirror"] = lens.locator(".craft-panel.writer-mirror").count() > 0
        row_b["coverage"] = lens.locator(".dock-cov-logline").count() > 0
        for k, v in row_b.items():
            check(f"B/{k}: report-section panel renders in the dock", v, craft_join[:200])
        # the character DIALS specifically — they must render INSIDE the live dock.
        # The previous assertion pinned `.rail-char-dials` visibility, i.e. the DEAD
        # #struct-rail: re-homing the dials into the dock could never satisfy it, because
        # the class it looked for only ever existed in the dead chrome. Pinning the dock
        # is strictly stronger than "some node carrying the rail class is visible".
        dial_rows = page.locator(".dial-row").count()
        dock_dials = lens.locator(".dial-row")
        dock_n = dock_dials.count()
        dials_visible = dock_n > 0 and dock_dials.first.is_visible()
        RESULTS["row_b"] = row_b
        row_b["character_dials"] = {"dial_rows": dial_rows, "dock_dials": dock_n,
                                    "visible": dials_visible}
        gap("B/character_dials: the dials are reachable on the live desk",
            dial_rows > 0 and dials_visible,
            f"{dial_rows} dial rows render, {dock_n} of them in the dock, "
            f"visible={dials_visible} (the dials rendered only into the dead #struct-rail)")
        shot(page, "B-character-dials.png")
        RESULTS["row_b"] = row_b
        craft = lens.locator(".dock-craft").first
        if craft.count():
            craft.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            shot(page, "B-craft-panels.png")
        cov = lens.locator(".dock-section",
                           has=page.locator(".dock-section-title", has_text="Coverage")).first
        if cov.count():
            cov.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            shot(page, "B-coverage.png")

        # -- row C: failed categories (quiet state on this script) -----------
        proj = [x for x in api("GET", "/api/projects") if x.get("project") == PROJECT]
        failed = (proj[0].get("failed_categories") if proj else []) or []
        RESULTS["failed_categories"] = failed
        check("C: no failed categories on this script (quiet state honest)",
              failed == [], str(failed))
        check("C: no failure banner when nothing failed or errored (quiet state)",
              lens.locator(".failure-banner").count() == 0)

        # -- full-lens verdict shot ------------------------------------------
        shot(page, "A02-evidence-lens-full.png", full=True)
        check("matrix walk: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


# ---------------------------------------------------------------------------
# STEP 4 — escalation proof (both routes)
# ---------------------------------------------------------------------------

def step_escalation():
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, PROJECT)

        def close_room(pg):
            # deterministic: dispatch the real close control, never rely on
            # hit-testing (an open drawer intercepts pointer events)
            for _ in range(4):
                if not pg.locator("#room-drawer.open").count():
                    return
                pg.evaluate("() => { const b = document.getElementById('drawer-close'); if (b) b.click(); }")
                pg.wait_for_timeout(500)

        def quote_state():
            qc = page.locator("#quote-card")
            vis = qc.count() > 0 and qc.first.is_visible()
            return vis, (qc.first.inner_text() if qc.count() else "")

        def prep_evidence():
            close_room(page)
            open_dock(page, "evidence")
            lens = page.locator('.dock-lens[data-lens="evidence"]')
            # P1.6: the escalation routes click INSIDE dock sections (cards, queue
            # rows) — open them first, as the writer must, or the click has no
            # reachable target.
            open_dock_section_holding(page, ".dock-section-body")
            widen_filter(page, lens)
            page.wait_for_timeout(450)
            return lens

        # --- route 1: Discuss from the loop bar (no room involved) ----------
        # Runs FIRST: the loop bar lives in the dock, and every Discuss that
        # opens the room drawer would otherwise intercept the click.
        lens = prep_evidence()
        loop_btn = lens.locator(".fchip-loop").first
        check("escalation/Sameer: the fix loop engages", loop_btn.count() > 0)
        if loop_btn.count():
            loop_btn.click()
            page.wait_for_timeout(700)
            bar = page.locator("#loop-bar")
            check("escalation/Sameer: the loop bar renders with a position readout",
                  bar.count() > 0 and bar.locator(".loop-pos").count() > 0)
            # stepLoop falls back to jumpToScene when the current finding has no
            # inked quote — and jumpToScene() unconditionally opens the partner
            # drawer (app.js:2807), which covers the dock the loop bar lives in.
            room_opened = page.locator("#room-drawer.open").count() > 0
            gap("escalation/loop: engaging the fix loop does not cover its own bar",
                not room_opened,
                "engaging the loop opened the room drawer over the dock "
                "(startLoop -> stepLoop -> jumpToScene -> openCowriteRoom); the loop "
                "bar's mark/park/discuss buttons are then unreachable by mouse")
            close_room(page)
            lb_discuss = bar.locator(".loop-btn", has_text="discuss").first
            if lb_discuss.count():
                lb_discuss.click()
                page.wait_for_timeout(600)
                vis3, _ = quote_state()
                check("escalation/Sameer: loop-bar Discuss pins the quote", vis3)
            shot(page, "ESC-0-loop-bar.png")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            close_room(page)

        # --- route 2: Discuss from a deep card -> send -> discussed tag -----
        # Pick a SCENE-ANCHORED card: a script-level finding (scene_refs == [])
        # pins scene_number=null, so no scene can carry the discussed tag —
        # correct behaviour, but it can't exercise the tag.
        lens = prep_evidence()
        cards = lens.locator(".finding-note:has(.finding-deep-quote)")
        card = None
        for i in range(min(cards.count(), 40)):
            c = cards.nth(i)
            cat = c.locator(".finding-note-cat").first.inner_text().strip().lower()
            if cat and cat != "continuity":
                card = c
                break
        check("escalation/Sameer: a scene-anchored deep card exists",
              card is not None, f"{cards.count()} deep-quote cards")
        if card is None:
            card = cards.first
        if cards.count():
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(250)
            card.locator(".finding-note-actions button", has_text="Discuss").first.click()
            page.wait_for_timeout(800)
            vis, qtxt = quote_state()
            check("escalation/Sameer: Discuss PINS the quote (setPendingQuote)", vis, qtxt[:80])
            check("escalation/Sameer: Discuss opens the room",
                  page.locator("#room-drawer").count() > 0)
            prefill = page.locator("#input").input_value() or ""
            check("escalation/Sameer: the composer is seeded with the finding",
                  len(prefill) > 0, prefill[:90])
            shot(page, "ESC-1-sameer-quote-pinned.png")

            before_user = page.locator(".msg.user").count()
            before_asst = page.locator(".msg.assistant").count()
            page.locator("#input").fill(prefill or "What should I do about this?")
            page.locator("#send-btn").click()
            try:
                # require a NEW turn: the room may already hold earlier replies
                page.wait_for_function(
                    "(n) => document.querySelectorAll('.msg.user').length > n",
                    arg=before_user, timeout=30000)
                page.wait_for_function(
                    """(n) => {
                        const m = document.querySelectorAll('.msg.assistant');
                        return m.length > n && !m[m.length - 1].classList.contains('msg-pending');
                    }""", arg=before_asst, timeout=240000)
                reply = page.locator(".msg.assistant .msg-bubble").last.inner_text()
                check("escalation/Sameer: a real reply streams back", len(reply.strip()) > 20,
                      reply[:120])
                RESULTS["sameer_reply"] = reply[:1500]
            except Exception as e:
                check("escalation/Sameer: a real reply streams back", False, str(e)[:140])
            shot(page, "ESC-2-sameer-reply.png")
            # the discussed tag is computed when the manuscript renders from the
            # branch's messages — allow the live re-render, else confirm persistence
            try:
                page.wait_for_selector(".scene-discussed", timeout=10000)
            except Exception:
                pass
            disc = page.locator(".scene-discussed").count()
            live = disc > 0
            if not disc:
                open_project(page, PROJECT)
                disc = page.locator(".scene-discussed").count()
            check("escalation/Sameer: the scene page gains the 'discussed' tag", disc > 0,
                  f"{disc} tag(s) (live={live})")
            shot(page, "ESC-3-discussed-tag.png")
            close_room(page)

        # --- route 3: Discuss from the fix queue ----------------------------
        lens = prep_evidence()
        fq = lens.locator(".fix-row-actions button", has_text="Discuss").first
        check("escalation/Sameer: the fix queue carries Discuss", fq.count() > 0)
        if fq.count():
            fq.scroll_into_view_if_needed()
            fq.click()
            page.wait_for_timeout(700)
            vis2, _ = quote_state()
            check("escalation/Sameer: fix-queue Discuss also pins the quote", vis2)
            close_room(page)

        # --- route 4: Sushruta — the finding rides into the consult ---------
        lens = prep_evidence()
        why = lens.locator('.finding-note .intent-btn[title*="Ask Dr. Sushruta"]').first
        check("escalation/Sushruta: the 'ask the doctor why' gesture exists", why.count() > 0)
        if why.count():
            why.scroll_into_view_if_needed()
            why.click()
            page.wait_for_timeout(900)
            sush = page.locator('.dock-lens[data-lens="sushruta"]')
            check("escalation/Sushruta: the doctor's lens opens",
                  page.locator("#context-dock.open").count() > 0)
            seeded = sush.locator("#fv-consult-input")
            seeded_txt = seeded.input_value() if seeded.count() else ""
            check("escalation/Sushruta: the 'why was this flagged' question is seeded "
                  "with the finding's category + scene",
                  "flagged" in seeded_txt.lower() and "scene" in seeded_txt.lower(), seeded_txt[:110])
            shot(page, "ESC-4-sushruta-why-seeded.png")
            if seeded.count():
                before_ai = page.locator('.dock-lens[data-lens="sushruta"] .fv-msg.ai').count()
                seeded.fill(seeded_txt or "Why was this flagged? What exactly is wrong?")
                sush.locator("#fv-consult-composer button[type=submit]").click()
                try:
                    page.wait_for_function(
                        """(n) => {
                            const m = document.querySelectorAll('.dock-lens[data-lens="sushruta"] .fv-msg.ai');
                            if (m.length <= n) return false;
                            const t = m[m.length-1].textContent || '';
                            return t.length > 40 && !t.includes('reading');
                        }""", arg=before_ai, timeout=240000)
                    doc_reply = page.locator(
                        '.dock-lens[data-lens="sushruta"] .fv-msg.ai').last.inner_text()
                    check("escalation/Sushruta: the reply carries per-finding reasoning",
                          len(doc_reply.strip()) > 60, doc_reply[:140])
                    RESULTS["sushruta_reply"] = doc_reply[:2000]
                except Exception as e:
                    check("escalation/Sushruta: the reply carries per-finding reasoning",
                          False, str(e)[:120])
                shot(page, "ESC-5-sushruta-reply.png")

        check("escalation: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


# ---------------------------------------------------------------------------
# STEP 5 — in-between (intents + one quote-visible edit)
# ---------------------------------------------------------------------------

def step_inbetween():
    pdir = os.path.join(os.path.dirname(SHOTS), "studio_projects", PROJECT)
    rep = api("GET", f"/api/projects/{PROJECT}/report")
    findings = rep.get("findings") or []
    # ids straight from the server (no client-side re-derivation to drift)
    ed = api("GET", f"/api/projects/{PROJECT}/edits")
    fs_items = (ed.get("findings_status") or {}).get("findings") or []
    ids = list(dict.fromkeys(x.get("finding_id") for x in fs_items if x.get("finding_id")))
    check("in-between: the server exposes finding ids for intent marks", len(ids) > 0,
          f"{len(ids)} distinct ids")

    # 2 addressed + 1 deferred (writer intent)
    for fid in ids[:2]:
        api("POST", f"/api/projects/{PROJECT}/findings/intent",
            json={"finding_id": fid, "intent": "addressed"})
    if len(ids) > 2:
        api("POST", f"/api/projects/{PROJECT}/findings/intent",
            json={"finding_id": ids[2], "intent": "deferred"})
    intents = (api("GET", f"/api/projects/{PROJECT}/edits").get("finding_intents") or {})
    check("in-between: writer intents persisted", len(intents) >= 3, str(intents))
    RESULTS["intents"] = intents

    # one quote-visible edit: change a line a verified finding cites. The quote
    # must sit inside a SINGLE wrapped element (quote_present True) or
    # apply_replacements skips it ("line not found in scene").
    texts = _working_texts(pdir)
    target = None
    for f in findings:
        q = (f.get("evidence_quote") or "").strip()
        if (f.get("verification") or {}).get("status") != "verified" or not q:
            continue
        # the edit targets a whole ELEMENT line in the scene that HOLDS it
        # (apply_replacements matches the line, and scene_refs may be empty)
        candidates = [(sn, t) for sn, t in texts if t and q in t]
        if candidates:
            sn, old_line = max(candidates, key=lambda p: len(p[1]))
            target = (f, sn, old_line)
            break
    if target is None:
        check("in-between: a verified quote sits inside one editable element", False,
              "all verified quotes span wrapped lines")
        return
    target_f, scene, old_line = target
    new_line = old_line + " (rewritten in the audit)"
    res = api("POST", f"/api/projects/{PROJECT}/edits/apply",
              json={"scene_number": scene, "replacements": [{"old": old_line, "new": new_line}]})
    check("in-between: the quote-visible edit applied", bool(res.get("applied")),
          json.dumps(res)[:220])
    RESULTS["edit"] = {"scene": scene, "old": old_line, "new": new_line,
                       "applied": res.get("applied"), "skipped": res.get("skipped")}
    print("    edit:", json.dumps(RESULTS["edit"], ensure_ascii=False)[:220])
    st = res.get("findings_status", {}).get("summary", {})
    RESULTS["status_after_edit"] = st
    print("    findings_status after edit:", st)


# ---------------------------------------------------------------------------
# STEP 6 — pass 2 + arrival-strip arithmetic
# ---------------------------------------------------------------------------

def _expected_arrival():
    """The exact diff the arrival strip must show — read from the SERVER's own
    snapshot (last_pass_snapshot computes it lazily on GET /edits), so the
    assertion compares the UI against the server's arithmetic, not a
    re-implementation of it."""
    api("GET", f"/api/projects/{PROJECT}/edits")
    lp_path = os.path.join(os.path.dirname(SHOTS), "studio_projects", PROJECT, "last_pass.json")
    with open(lp_path, encoding="utf-8") as f:
        snap = json.load(f)
    return snap.get("payload") or {}


def _progress():
    """The project's progress.json, or {} when it cannot be read."""
    try:
        return api("GET", f"/api/projects/{PROJECT}/progress", timeout=15)
    except Exception:
        return {}


# A run that starts must say so quickly: the pipeline writes its first heartbeat
# at the top of stage 1, long before the model is asked anything. Silence past
# this means the run never began — a different failure from a slow model.
FIRST_BEAT_S = 300
# ...and once it IS running, a gap this long with no new heartbeat is a stall,
# not thinking. The whole script analyses in ~9-16 min on the 35B model.
STALL_S = 1200


def _start_analysis_and_wait():
    """Force a re-analysis and wait for THAT run to land. Returns True on success.

    Three traps, all measured against a 35B model (pass 14). Together they made
    this stage report three FALSE failures and one FALSE product gap, so they are
    worth the space:

    1. `POST /analyze` BLOCKS for the whole run, and on a real model a run can
       exceed any timeout we pick (measured: **15 min 38 s** for this 6-scene
       script on `qwen3.6-35b`, against a 900 s client timeout). A client-side
       read timeout therefore means **the run is still going**, not that it
       failed — the old code recorded it as a product failure and moved on.

    2. The completion poll exited on `status == "complete" or stage == "done"`,
       which the PREVIOUS run's `progress.json` still satisfies on disk, because
       nothing clears it between runs. So a run that never started would be
       declared complete instantly. It is anchored to a timestamp now: only a
       completion NEWER than the run we triggered counts.

    3. **The completion flag and the snapshot are written ~1 s apart.**
       `progress.json` says `done` at 21:12:08 and `last_pass.json` is refreshed
       at 21:12:09. So reading the expected snapshot the moment the flag flips
       returns the PREVIOUS pass's numbers while the browser — a second later —
       reads the new ones. Measured exactly that: expected `last_total=22` vs the
       strip's `27`, reported as an arithmetic mismatch and a product gap when
       nothing was wrong. `step_pass2` therefore waits for a NEW `computed_at`
       too; see `_wait_for_new_snapshot`.

    Returning False makes the caller fail the stage and SKIP the derived
    assertions, rather than emit product findings computed against a baseline
    that was never verified.
    """
    before_ts = _progress().get("ts") or 0
    started = os.environ.get("GUNPEN_SKIP_ANALYZE") == "1"
    if started:
        print("    (trigger skipped — asserting against the in-flight run)")
    else:
        try:
            r = requests.post(f"{BASE}/api/projects/{PROJECT}/analyze",
                              json={"force": True}, timeout=3600,
                              headers=studio_headers(BASE))
            if r.status_code in (200, 201):
                # "Accepted" must be MEASURED, not assumed from the status-code
                # branch we happen to be in (this check used to be `check(name,
                # True)` — unfailable). The blocking handler answers 200 with
                # this project's manifest summary; a 200 whose body is an error
                # envelope, another project's summary, or non-JSON (a proxy
                # page) is the server NOT confirming the forced run.
                try:
                    ack = r.json()
                except ValueError:
                    ack = None
                accepted = (isinstance(ack, dict)
                            and ack.get("project") == PROJECT
                            and not ack.get("error"))
                check("pass2: force re-analysis accepted", accepted,
                      f"HTTP {r.status_code} but body is not this project's "
                      "manifest summary: "
                      + (json.dumps(ack)[:140] if isinstance(ack, dict)
                         else repr(getattr(r, "text", "")[:140])))
                if not accepted:
                    return False
                started = True
            else:
                # NOT accepted -> return WITHOUT waiting. Trap 4, and the one
                # this function learned the hard way: a wait loop whose trigger
                # failed does not "wait for completion", it MANUFACTURES a
                # timeout — and a timeout is indistinguishable from a slow
                # model, so the real error stays hidden for the whole budget.
                # Measured: a sandbox-blocked os.remove() inside the handler
                # dropped the connection, this check recorded the failure, and
                # the stage then sat in time.sleep(10) for 20 minutes with
                # nothing to tell it apart from a 35B model thinking.
                check("pass2: force re-analysis accepted", False,
                      f"HTTP {r.status_code}: {r.text[:120]}")
                return False
        except requests.exceptions.ReadTimeout:
            # Expected on a real model: the run outlived the client. Not a
            # failure — the wait below is the actual gate.
            started = True
            note("pass2: the analyze call outlived the client timeout",
                 "the run is still going; waiting for its progress stamp")
        except Exception as e:
            # A dropped connection lands here too (RemoteDisconnected is a
            # ConnectionError, not a ReadTimeout), and it is NOT a reason to
            # wait: nothing was accepted.
            check("pass2: force re-analysis accepted", False, str(e)[:140])
            return False

    if not started:
        return False

    # Bounded in BOTH directions: an accepted trigger must produce a heartbeat
    # quickly, and a running one must not go quiet. "Still working" and "never
    # started" are different failures and now say so differently.
    deadline = time.time() + 3600
    first_beat_by = time.time() + FIRST_BEAT_S
    last_ts, last_change = before_ts, time.time()
    pr = {}
    while time.time() < deadline:
        pr = _progress()
        ts = pr.get("ts") or 0
        if ts > last_ts:
            last_ts, last_change = ts, time.time()
        # A NEW completion only: `ts` strictly after the run we started.
        if ts > before_ts and (pr.get("status") == "complete"
                               or pr.get("stage") == "done"):
            # The heartbeat flipping is only half the promise (the check used
            # to be `check(name, True)` — it merely echoed the loop condition
            # it sat under). A completed analysis must ALSO leave a non-empty
            # report behind, or the arrival strip below counts a pass that
            # produced nothing. Measure the LIVE report from the server.
            try:
                rep = api("GET", f"/api/projects/{PROJECT}/report", timeout=60)
                n_findings = len(rep.get("findings") or [])
                rep_err = ""
            except Exception as e:
                n_findings, rep_err = -1, str(e)[:120]
            completed = n_findings > 0
            check("pass2: analysis completed", completed,
                  f"progress says {pr.get('status')}/{pr.get('stage')} at "
                  f"ts={ts} (new vs {before_ts}), but the live report carries "
                  f"{n_findings} findings {rep_err}".strip())
            return completed
        if last_ts <= before_ts and time.time() > first_beat_by:
            check("pass2: analysis completed", False,
                  f"no heartbeat within {FIRST_BEAT_S}s of an accepted trigger — "
                  "the run never started")
            return False
        if last_ts > before_ts and time.time() - last_change > STALL_S:
            check("pass2: analysis completed", False,
                  f"progress went silent for {STALL_S}s "
                  f"(stage={pr.get('stage')} status={pr.get('status')})")
            return False
        time.sleep(10)
    check("pass2: analysis completed", False,
          f"no NEW completion within the deadline (progress={json.dumps(pr)[:160]})")
    return False


def _wait_for_new_snapshot(before, deadline_s=180):
    """Wait until last_pass.json carries a NEW computed_at. Returns the snapshot.

    Trap 3 in `_start_analysis_and_wait`: `progress.json` flips to `done` about a
    second before the arrival snapshot is rewritten, so reading the snapshot the
    instant the flag flips yields the PREVIOUS pass's numbers and makes the
    strip look wrong by exactly one pass. Anchored on `computed_at`, the same way
    the completion wait is anchored on `ts`.
    """
    before_at = before.get("computed_at")
    deadline = time.time() + deadline_s
    snap = before
    while time.time() < deadline:
        snap = _expected_arrival()
        if snap.get("computed_at") != before_at:
            return snap
        time.sleep(5)
    return snap


def step_pass2():
    before = _expected_arrival()
    print("    pre-pass2 baseline:", before)
    if not _start_analysis_and_wait():
        # Fail the stage and STOP. Everything below compares the arrival strip
        # against a snapshot, so running it on a baseline that was never
        # verified produces confident product findings about a run that had not
        # finished — which is precisely what happened before this guard existed
        # (measured: 3 FAILs and 1 GAP, all false, from reading the desk
        # mid-flight).
        print("    !! the re-analysis did not land — skipping the arrival assertions")
        return

    after = _wait_for_new_snapshot(before)
    if after.get("computed_at") == before.get("computed_at"):
        check("pass2: the new pass wrote a fresh arrival snapshot", False,
              f"computed_at unchanged ({after.get('computed_at')}) — the strip would "
              "be compared against the previous pass")
        return
    # "Fresh" is more than "computed_at differs" (which the branch above just
    # echoed; the check used to be `check(name, True)` — unfailable). The
    # snapshot must be STRICTLY NEWER and carry the exact arithmetic fields the
    # arrival checks below read by name — a pass that wrote a partial or
    # backwards-dated snapshot must fail here, not NPE further down.
    required = ("computed_at", "last_total", "prev_total",
                "still_live", "fixed", "new")
    missing = [k for k in required if after.get(k) is None]
    newer = ((after.get("computed_at") or 0)
             > (before.get("computed_at") or 0))
    fresh = newer and not missing
    check("pass2: the new pass wrote a fresh arrival snapshot", fresh,
          f"computed_at {before.get('computed_at')!r} -> "
          f"{after.get('computed_at')!r} (strictly newer={newer}); "
          f"missing fields={missing}")
    if not fresh:
        return
    RESULTS["arrival_expected"] = after
    print("    post-pass2 expected arrival:", after)

    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, PROJECT)

        # -- the unread-dot lifecycle (plan step 6) --------------------------
        # The dot is scheduled only when the client sees a last_pass computed_at
        # it has not seen before AND the dock is closed. open_project() already
        # waits past the 700ms peek timer, so the dot is expected to be present
        # by the time we look; what matters is that it IS there on a fresh load
        # and that opening the lens clears it.
        tab = page.locator("#dock-tab-evidence")
        page.wait_for_timeout(300)
        dot_present = "has-unread" in (tab.get_attribute("class") or "")
        dock_closed = page.locator("#context-dock.open").count() == 0
        check("pass2: the unread dot is present on a fresh load after a new pass",
              dot_present and dock_closed,
              f"has-unread={dot_present} dock closed={dock_closed}")

        open_dock(page, "evidence")
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        page.wait_for_timeout(400)
        cleared = "has-unread" not in (tab.get_attribute("class") or "")
        check("pass2: opening the Evidence lens clears the unread dot", cleared)

        strip = lens.locator(".dock-arrival-strip")
        check("pass2: the arrival strip appears", strip.count() > 0)
        if strip.count():
            line = strip.locator(".dock-arrival-line").inner_text()
            scope = strip.locator(".dock-arrival-scope").inner_text() if strip.locator(".dock-arrival-scope").count() else ""
            draft = strip.locator(".dock-arrival-draft").inner_text() if strip.locator(".dock-arrival-draft").count() else ""
            print(f"    arrival line: {line}")
            print(f"    scope: {scope} | draft: {draft}")
            m = re.search(r"Pass: (\d+) . (\d+) still live . (\d+) no longer flagged . (\d+) new", line)
            if after:
                check("pass2: arrival arithmetic is EXACT vs the server's own diff",
                      bool(m) and [int(m.group(i)) for i in (1, 2, 3, 4)] ==
                      [after["last_total"], after["still_live"], after["fixed"], after["new"]],
                      f"line={line!r} expected={after}")
            else:
                check("pass2: arrival arithmetic is EXACT vs the server's own diff", False,
                      f"no snapshot payload (line={line!r})")
            check("pass2: the scope chip states the pass line never tracks edits",
                  "not your edits" in scope.lower(), scope)
            # the arrival basis vs the board basis — the same desk, two totals
            rep_n = len(api("GET", f"/api/projects/{PROJECT}/report").get("findings") or [])
            # This stage forces a re-analysis WITHOUT a re-parse, so the script is
            # byte-identical to the last pass and there is no delta to draw: the
            # headline must then be the report the BOARD is counting. Measured:
            # one script, two runs, 36 findings then 22 — a "Pass: 36" over a
            # 22-row board is the UI pretending, which is what this now pins.
            # On a genuinely moved script the headline is the PREVIOUS pass's
            # total and need not match, so the assertion is scoped to this case.
            gap("pass2: on an unchanged script the arrival 'Pass:' total equals the board's finding count",
                after.get("same_input") is True and after["last_total"] == rep_n,
                f"same_input={after.get('same_input')} arrival last_total={after['last_total']} "
                f"vs report findings={rep_n}")
            ghosted = strip.locator(".dock-ghosted-summary").count()
            # app.js states the contract at its render site: "ghosted: the
            # writer's marks that transformed — muted, expandable, never red" —
            # and it renders the block only `if (ghosted.length)`. So `>= 0`
            # asserted neither half: it is true when there are zero ghosted
            # marks, which is precisely when nothing renders at all. Assert the
            # COLOUR, which is the actual claim.
            #
            # The danger token is resolved THROUGH the browser so both sides are
            # in the same `rgb()` form — comparing `getComputedStyle().color`
            # against the raw `--danger` string would differ by format alone and
            # be vacuous again.
            if ghosted:
                gcol = strip.locator(".dock-ghosted-summary").first.evaluate(
                    "el => getComputedStyle(el).color")
                dcol = page.evaluate(
                    """() => {
                      const probe = document.createElement('span');
                      probe.style.color = 'var(--danger)';
                      document.body.appendChild(probe);
                      const c = getComputedStyle(probe).color;
                      probe.remove();
                      return c;
                    }""")
                check("pass2: ghosted marks render honestly (never red)",
                      bool(dcol) and gcol != dcol,
                      f"ghosted={ghosted} colour={gcol} danger={dcol}")
            else:
                note("pass2: ghosted marks not rendered",
                     "no moved marks on this run — 'never red' was NOT exercised")
            # GAP-7: a force re-analysis with no re-parse reads the SAME script,
            # so every id that moved is the model re-wording its own sentence (the
            # no-quote tier hashes model prose). The arithmetic must not dress that
            # as progress: fixed/new are 0 and the churn is disclosed on the strip.
            # This is the gate for a bug that had no filed check before.
            rw = strip.locator(".dock-arrival-rewrite")
            rw_txt = rw.inner_text() if rw.count() else ""
            # Match the WHOLE clause, not just the number: "0" is in almost any
            # sentence, so a substring test would pass vacuously on a re-run where
            # nothing moved (measured: rewritten=0 after a same-report recompute).
            # This fails if the strip drops either the churn count or the
            # previous pass's total, which is what makes the disclosure readable.
            rw_expect = (f"{after.get('rewritten', 0)} of the last pass's {after['prev_total']}"
                         if after.get("prev_total") is not None
                         else f"{after.get('rewritten', 0)} findings reworded")
            check("pass2: an unchanged script is disclosed, not reported as progress",
                  after.get("same_input") is True and after.get("fixed") == 0
                  and after.get("new") == 0 and rw.count() > 0
                  and rw_expect in rw_txt,
                  f"same_input={after.get('same_input')} fixed={after.get('fixed')} "
                  f"new={after.get('new')} rewritten={after.get('rewritten')} "
                  f"clause={rw_txt[:60]!r}")
            shot(page, "PASS2-arrival-strip.png")
        check("pass2: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


def step_cleanbill():
    """The empty-pass 'clean bill' reading (plan fix #5).

    No zero-finding row occurs naturally on gun_pen, so this uses the plan's
    sanctioned synthetic mini-project (tests/_gunpen_clean_bill.py seeds it).
    """
    label = "Clean Bill Probe"
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, "Clean_Bill_Probe", label=label)
        status = page.locator("#desk-analyze-status")
        txt = status.inner_text() if status.count() else ""
        check("clean bill: the desk reads the empty pass as a clean bill",
              "clean bill" in txt.lower(), txt[:110])
        open_dock(page, "evidence")
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        check("clean bill: the lens is not a blank — coverage still renders",
              lens.locator(".dock-cov-logline, .dock-section-title").count() > 0)
        check("clean bill: no finding cards (honest zero)",
              lens.locator(".finding-note").count() == 0)
        check("clean bill: no mass strip claimed (nothing to weigh)",
              lens.locator(".dock-mass-strip").count() == 0)
        check("clean bill: no failure banner (nothing failed, nothing errored)",
              lens.locator(".failure-banner").count() == 0)
        shot(page, "C-clean-bill.png")
        check("clean bill: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()
    RESULTS["clean_bill"] = {"synthetic": True, "label": label}


STAGES = {"matrix": step_matrix, "escalation": step_escalation,
          "inbetween": step_inbetween, "pass2": step_pass2,
          "cleanbill": step_cleanbill}


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    # stages accumulate: a later stage run must not wipe an earlier stage's data
    results_path = os.path.join(SHOTS, "audit_results.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, encoding="utf-8") as f:
                RESULTS.update(json.load(f))
        except (OSError, ValueError):
            pass
    print(f"=== gun_pen feedback audit :: stage={stage} :: base={BASE} :: project={PROJECT} ===")
    rel = os.path.relpath(SHOTS, _REPO_ROOT).replace(os.sep, "/")
    if PROMOTE:
        print(f"    AUDIT_PROMOTE=1 — writing to the VERSIONED set {rel}/ "
              f"(this REPLACES evidence the docs cite)")
    else:
        print(f"    output -> {rel}/ (scratch; AUDIT_PROMOTE=1 to refresh impl-shots/)")
    order = (["matrix", "escalation", "inbetween", "pass2", "cleanbill"]
             if stage == "all" else [stage])
    for name in order:
        print(f"\n--- stage: {name} ---")
        CURRENT_STAGE["name"] = name
        try:
            STAGES[name]()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"stage {name} completed", False, str(e)[:160])
    # RETIRE-and-replace per stage: drop the prior gaps belonging to the stages
    # that just ran, then add this run's. A plain merge would keep a gap forever
    # after the condition stopped failing (a stale entry survived a fix on the
    # first attempt at this), and replacing wholesale would drop the other
    # stages' findings (stages run as separate processes).
    ran = set(order)
    kept = [g for g in (RESULTS.get("gaps") or []) if g.get("stage") not in ran]
    RESULTS["gaps"] = kept + GAPS
    with open(os.path.join(SHOTS, "audit_results.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)
    print(f"\n=== GAPS FILED ({len(RESULTS['gaps'])}) ===")
    for g in RESULTS["gaps"]:
        print(f"  - {g['gap']}: {g['detail']}")
    checks.finish()


if __name__ == "__main__":
    main()
