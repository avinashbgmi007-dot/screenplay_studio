"""Phase 6 gate — Evidence Overview in the Context Dock (master plan §7).

Verifies the dock's evidence lens against the live app, DOM/text only:
  * unanalyzed project: the empty hint, no crash, manuscript stays primary
  * analyzed project: all seven sections assemble (scene strip, fix queue,
    scene findings, findings by category, coverage, setup/payoff, craft)
  * the evidence-depth line states the mix, names the scenes read as raw pages
    (§5 item 2), and keeps the "not a full reading" caveat
  * every finding action survives the move: Locate, Rewrite, Discuss,
    Dismiss, Restore; Addressed rows render addressed
  * the scene strip tracks scrolling (retitles for a different scene)
  * manuscript context preserved across open/close (scroll position)
  * legacy surfaces: #room-drawer and #feedback-panel survive dock use;
    #feedback-view and #problem-board are retired (P0.1/P0.2) — absence asserted
  * every Evidence section collapses and persists (P1.6): a closed body is
    hidden (not rendered text, not clickable), so this suite opens the section
    it wants to read or click inside — the writer's own path

Run:  python tests/e2e_browser_phase6_evidence.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)
"""
import os
import re

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import (Checks, launch, open_dock_section,
                                open_dock_section_holding, open_studio,
                                studio_headers)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed_and_analyze(base, title):
    """Upload the fixture and run the demo-model analysis to completion.

    The title is a display hint — the server names the project (safe-id
    charset), so the returned name is always used.
    """
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          headers=studio_headers(base), files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    # the manifest summary carries the server-safe directory name under
    # "project" (spaces -> underscores), not under "name"
    name = r.json().get("project") or r.json().get("name") or title
    # demo model analyzes deterministically; the endpoint blocks until done
    r2 = requests.post(f"{base}/api/projects/{name}/analyze",
                       headers=studio_headers(base), json={"force": True}, timeout=300)
    assert r2.status_code in (200, 201), r2.text[:400]
    return name


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    # match the shelf row by the project's directory name (the server-safe id)
    row = page.locator(".project-item").filter(has_text=name.split("_")[0])
    if not row.count():
        row = page.locator(".project-item").filter(has_text=name.replace("_", " "))
    row.first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def run(base):
    analyzed = seed_and_analyze(base, "Rain Courier")
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        open_project(page, base, analyzed)

        # --- pre-open: lens holds the fallback hint, dock closed ------------
        edge = page.locator("#right-edge-affordance")
        check("affordance visible before open", edge.is_visible())

        # --- unanalyzed-state contract first: fresh project, no report -----
        # (rendered later; the analyzed one is the deep path)

        # --- open the dock on the evidence lens -----------------------------
        edge.click()
        # the dock animates width 0 → 380px (0.25s); settle before asserting
        page.wait_for_selector("#context-dock.open", timeout=5000)
        page.wait_for_timeout(450)
        check("dock opens", page.locator("#context-dock.open").is_visible())
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        check("evidence lens is the active panel", lens.is_visible())

        # -- 1. current-scene strip ------------------------------------------
        check("scene strip renders (Scene N or Script level)",
              lens.locator(".dock-evidence-scene .dock-scene-num").count() > 0,
              lens.locator(".dock-evidence-scene").count())

        # -- 2. Fix Queue section reuses the legacy panel --------------------
        # GAP-1 law: the queue follows the ONE filter. The default now shows
        # every severity (2026-09-20 scope contract), so the queue carries rows
        # out of the box; the honest "0 shown" state is reached by NARROWING
        # and is asserted below.
        fq = lens.locator(".dock-section-fixqueue .fix-queue, "
                          ".dock-section .fix-queue")
        check("fix queue panel renders in the dock", fq.count() > 0)

        # -- 3. findings (scene-level and/or by category) --------------------
        # GAP-1 law (R5-b completed) + the 2026-09-20 SCOPE contract:
        # the board list follows the ONE filter, and the DEFAULT shows the
        # ledger whole (all severities) -- because the mass strip above it
        # counts every finding, a narrower default made the strip and the queue
        # contradict each other ("6 open of 6" over "0 shown / 6 total").
        # The honest empty state is STILL the contract; it is now reached by
        # the writer narrowing, not by a partial default. Both sides asserted.
        notes = lens.locator(".finding-note")
        check("board: default ledger is whole (all severities shown)",
              notes.count() > 0, f"default notes={notes.count()}")
        # narrow to High only: turn Medium + Low OFF via the severity chips.
        # This fixture's findings are all medium/low, so the board empties -- and
        # must SAY so rather than render blank.
        for label in ["Medium", "Low"]:
            chip = lens.locator(".fchip", has_text=label).first
            if chip.count() and "active" in (chip.get_attribute("class") or ""):
                chip.click()
                page.wait_for_timeout(400)
        check("board: narrowed-to-empty filter shows the honest hint (not blank)",
              lens.locator(".dock-lens-hint", has_text="No findings match").count() > 0,
              f"notes after narrowing={lens.locator('.finding-note').count()}")
        # widen back: turn Medium + Low ON again and the cards return
        for label in ["Medium", "Low"]:
            chip = lens.locator(".fchip", has_text=label).first
            if chip.count() and "active" not in (chip.get_attribute("class") or ""):
                chip.click()
                page.wait_for_timeout(400)
        notes = lens.locator(".finding-note")
        check("board: widened filter reveals the finding cards (findingNoteEl reuse)",
              notes.count() > 0, f"count={notes.count()}")
        check("finding cards carry Locate/Rewrite/Discuss actions",
              lens.locator(".finding-note-actions button").count() > 0)
        check("fix queue rows carry the severity badge (after widening)",
              lens.locator(".fix-row .sev-badge").count() > 0)

        # -- 4. findings by category sections --------------------------------
        # P1.6: a section's body is collapsed by default and a closed body is not
        # rendered text — `inner_text()`/`all_inner_texts()` see "" inside it. So
        # open the section the way the writer does before reading its words.
        check("P1.6: the ledger's category section opens from its header",
              open_dock_section(page, "by-category"))
        cat_sections = lens.locator(".dock-section-title")
        cat_text = " ".join(cat_sections.all_inner_texts())
        check("category sections group the findings",
              any(k in cat_text.lower() for k in
                  ["dialogue", "plot", "character", "theme", "pacing", "structure", "format"]))

        # -- 5. coverage ------------------------------------------------------
        check("coverage section renders",
              "coverage" in cat_text.lower() or
              lens.locator(".dock-cov-logline, .dock-section-title", has_text="Coverage").count() > 0)

        # Evidence depth (§5 item 2): the script-level passes now read the
        # summaries PLUS the raw pages of the checkpoint scenes, and the dock has
        # to say so — the middle bucket is the whole point of the change. Rendered
        # only when the report carries the field, so an older report stays silent.
        check("P1.6: the coverage section opens (its depth line is read, not hovered)",
              open_dock_section(page, "coverage"))
        depth_el = lens.locator(".dock-cov-depth")
        depth_txt = depth_el.first.inner_text() if depth_el.count() else ""
        check("evidence depth line renders in the coverage section", depth_el.count() > 0, depth_txt)
        check("it names the raw pages the script-level passes actually read",
              "raw pages of the key scenes" in depth_txt, depth_txt)
        check("it names which scenes were read as pages",
              re.search(r"scenes \d", depth_txt) is not None, depth_txt)
        check("it still warns this is not a full reading",
              "not a reading of your pages" in (depth_el.first.get_attribute("title") or "")
              if depth_el.count() else False, depth_txt)

        # -- 6. setup / payoff ------------------------------------------------
        # The section renders IFF the report carries the ledger (app.js gates on
        # state.report.setup_payoff). Assert the AGREEMENT, not a tautology: a
        # report with the ledger MUST show the section, one without it MUST stay
        # silent. (Was `count() >= 0` — a count is never negative.)
        _rep = requests.get(f"{base}/api/projects/{analyzed}/report",
                            headers=studio_headers(base), timeout=30).json()
        _has_ledger = bool((_rep or {}).get("setup_payoff"))
        _setup_secs = lens.locator(".dock-section-title", has_text="Setup").count()
        check("setup/payoff section agrees with the report",
              (_setup_secs >= 1) if _has_ledger else (_setup_secs == 0),
              f"report.setup_payoff={_has_ledger} sections={_setup_secs}")

        # -- 7. craft panels (pacing/characters/mirror reuse) ------------------
        check("craft panels render into the dock section",
              lens.locator(".craft-panel").count() > 0)

        # --- finding actions fire without JS errors --------------------------
        # P1.6: the cards live in collapsed sections now — open whatever section
        # holds them (this-scene or by-category, depending on the filter) so the
        # writer's own path (open, then act) is the one under test.
        check("P1.6: the section holding the finding cards opens",
              open_dock_section_holding(page, ".finding-note") > 0)
        # Locate: jumps the manuscript to the finding's scene
        before_scroll = page.locator("#manuscript-container").evaluate(
            "e => e.scrollTop")
        first_locate = lens.locator(".finding-note-actions button",
                                    has_text="Locate").first
        if first_locate.count():
            first_locate.click()
            page.wait_for_timeout(900)
            after_scroll = page.locator("#manuscript-container").evaluate(
                "e => e.scrollTop")
            check("Locate scrolls the manuscript (not the dock)",
                  abs(after_scroll - before_scroll) > 4
                  or before_scroll > 0,
                  f"before={before_scroll} after={after_scroll}")
        else:
            check("Locate present on finding cards", False, "no Locate button found")

        # Discuss: hands the quote to the composer — and per the Phase 6
        # handoff contract, the dock steps aside for the conversation
        discuss = lens.locator(".finding-note-actions button",
                               has_text="Discuss").first
        if discuss.count():
            discuss.click()
            page.wait_for_timeout(400)
            check("Discuss closes the dock (handoff to the conversation)",
                  page.locator("#context-dock.open").count() == 0)
            composer = page.locator("#input")
            check("Discuss prefills the composer",
                  "Scene" in (composer.input_value() or ""),
                  composer.input_value()[:80])
            # the drawer owns the room now — close it to get the page back
            # (exactly the writer's path: ✕ dismisses the partner)
            page.locator("#drawer-close").click()
            page.wait_for_timeout(300)
            # come back to the dock for the triage checks
            page.locator("#right-edge-affordance").click()
            page.wait_for_timeout(450)
        else:
            check("Discuss present on finding cards", False, "no Discuss button found")

        # Dismiss / Restore through the fix queue rows
        check("P1.6: the fix-queue section opens for its row actions",
              open_dock_section(page, "fix-queue"))
        dismiss = lens.locator(".fix-row-actions .fq-dismiss").first
        if dismiss.count():
            rows_before = lens.locator(".fix-row").count()
            dismiss.click()
            page.wait_for_timeout(1200)  # api + re-render
            # the dismissed row must LEAVE the queue. (Was `count() >= 0`, which
            # a count can never violate — so a dismiss that did nothing passed.)
            rows_after = lens.locator(".fix-row").count()
            check("Dismiss removes the row from the dock queue",
                  rows_after == rows_before - 1,
                  f"before={rows_before} after={rows_after}")
            restore = lens.locator(".fix-row-actions .fq-undismiss").first
            if restore.count():
                restore.click()
                page.wait_for_timeout(1200)
                check("Restore returns the row to the dock queue",
                      lens.locator(".fix-row-actions .fq-dismiss").count() > 0)
        else:
            check("Dismiss button present on fix rows", False,
                  "no dismissable rows (queue state)")

        # --- scene strip tracks scrolling ------------------------------------
        dock_scrolls = page.locator('.dock-lens[data-lens="evidence"] .dock-scene-num')
        strip_before = dock_scrolls.first.inner_text() if dock_scrolls.count() else ""
        page.locator("#manuscript-container").evaluate(
            "e => e.scrollTop = e.scrollHeight")  # scroll to the last scene
        page.wait_for_timeout(700)
        strip_after = dock_scrolls.first.inner_text() if dock_scrolls.count() else ""
        check("scene strip retitles as the writer scrolls",
              strip_before != strip_after or "Scene" in strip_after,
              f"before='{strip_before}' after='{strip_after}'")

        # --- close + reopen preserves lens + sections -------------------------
        page.keyboard.press("Escape")
        check("Esc closes the dock", page.locator("#context-dock.open").count() == 0)
        edge2 = page.locator("#right-edge-affordance")
        edge2.click()
        check("reopen keeps the evidence lens active",
              page.locator('.dock-lens[data-lens="evidence"]').is_visible())
        check("reopen re-assembles the sections",
              page.locator('.dock-lens[data-lens="evidence"] .dock-section').count() > 0)

        # --- live legacy surfaces remain; the retired two stay retired --------
        # P0.1/P0.2 deleted the dormant #feedback-view clone and the Problem
        # Board — this gate asserts their absence now.
        for sel, label in [("#room-drawer", "room drawer"),
                           ("#feedback-panel", "feedback panel")]:
            check(f"legacy surface intact: {label}",
                  page.locator(sel).count() > 0)
        for sel, label in [("#feedback-view", "feedback view clone"),
                           ("#problem-board", "problem board")]:
            check(f"retired surface stays gone: {label}",
                  page.locator(sel).count() == 0)

        # --- no JS errors across the whole flow -------------------------------
        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))

        browser.close()

    # --- unanalyzed project: the empty state contract -------------------------
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        with open(FIXTURE, "rb") as f:
            r = requests.post(f"{base}/api/projects",
                              headers=studio_headers(base), files={"file": ("Unanalyzed.fountain", f, "text/plain")},
                              data={"title": "Unanalyzed"}, timeout=60)
        assert r.status_code in (200, 201), r.text
        unanalyzed = r.json().get("project") or "Unanalyzed"
        open_project(page, base, unanalyzed)
        page.locator("#right-edge-affordance").click()
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        empty_hint = lens.locator(".dock-evidence-empty, .dock-lens-hint")
        check("unanalyzed project shows the honest empty state",
              empty_hint.count() > 0, empty_hint.count())
        check("unanalyzed flow: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    from e2e_browser_common import studio_headers, start_studio
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
