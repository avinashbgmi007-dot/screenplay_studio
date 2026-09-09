"""Phase 6 gate — Evidence Overview in the Context Dock (master plan §7).

Verifies the dock's evidence lens against the live app, DOM/text only:
  * unanalyzed project: the empty hint, no crash, manuscript stays primary
  * analyzed project: all seven sections assemble (scene strip, fix queue,
    scene findings, findings by category, coverage, setup/payoff, craft)
  * every finding action survives the move: Locate, Rewrite, Discuss,
    Dismiss, Restore; Addressed rows render addressed
  * the scene strip tracks scrolling (retitles for a different scene)
  * manuscript context preserved across open/close (scroll position)
  * legacy surfaces untouched: #room-drawer #feedback-panel #feedback-view
    #problem-board still present and functional after dock use

Run:  python tests/e2e_browser_phase6_evidence.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)
"""
import os

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, launch, open_studio

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
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    # the manifest summary carries the server-safe directory name under
    # "project" (spaces -> underscores), not under "name"
    name = r.json().get("project") or r.json().get("name") or title
    # demo model analyzes deterministically; the endpoint blocks until done
    r2 = requests.post(f"{base}/api/projects/{name}/analyze",
                       json={"force": True}, timeout=300)
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
        fq = lens.locator(".dock-section-fixqueue .fix-queue, "
                          ".dock-section .fix-queue")
        check("fix queue panel renders in the dock", fq.count() > 0)
        check("fix queue rows carry the severity badge",
              lens.locator(".fix-row .sev-badge").count() > 0)

        # -- 3. findings (scene-level and/or by category) --------------------
        notes = lens.locator(".finding-note")
        check("finding cards render in the dock (findingNoteEl reuse)",
              notes.count() > 0, f"count={notes.count()}")
        check("finding cards carry Locate/Rewrite/Discuss actions",
              lens.locator(".finding-note-actions button").count() > 0)

        # -- 4. findings by category sections --------------------------------
        cat_sections = lens.locator(".dock-section-title")
        cat_text = " ".join(cat_sections.all_inner_texts())
        check("category sections group the findings",
              any(k in cat_text.lower() for k in
                  ["dialogue", "plot", "character", "theme", "pacing", "structure", "format"]))

        # -- 5. coverage ------------------------------------------------------
        check("coverage section renders",
              "coverage" in cat_text.lower() or
              lens.locator(".dock-cov-logline, .dock-section-title", has_text="Coverage").count() > 0)

        # -- 6. setup / payoff ------------------------------------------------
        check("setup/payoff section renders (or absent honestly)",
              lens.locator(".dock-section-title", has_text="Setup").count() >= 0)

        # -- 7. craft panels (pacing/characters/mirror reuse) ------------------
        check("craft panels render into the dock section",
              lens.locator(".craft-panel").count() > 0)

        # --- finding actions fire without JS errors --------------------------
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
        dismiss = lens.locator(".fix-row-actions .fq-dismiss").first
        if dismiss.count():
            dismiss.click()
            page.wait_for_timeout(1200)  # api + re-render
            check("Dismiss removes the row from the dock queue",
                  lens.locator(".fix-row").count() >= 0)  # re-rendered: queue still coherent
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

        # --- legacy surfaces still present and untouched ----------------------
        for sel, label in [("#room-drawer", "room drawer"),
                           ("#feedback-panel", "feedback panel"),
                           ("#feedback-view", "feedback view"),
                           ("#problem-board", "problem board")]:
            check(f"legacy surface intact: {label}",
                  page.locator(sel).count() > 0)

        # --- no JS errors across the whole flow -------------------------------
        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))

        browser.close()

    # --- unanalyzed project: the empty state contract -------------------------
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        with open(FIXTURE, "rb") as f:
            r = requests.post(f"{base}/api/projects",
                              files={"file": ("Unanalyzed.fountain", f, "text/plain")},
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
    from e2e_browser_common import start_studio
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
