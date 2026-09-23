"""P2.17 gate — /quickcheck: the deterministic rules answer an edit at once.

spec §15.3: a writer who breaks a line should not have to re-run a twelve-pass
analysis to be told. Continuity + formatting are pure functions of the text and
answer in milliseconds with no model — so they run again on every edit, on the
WORKING copy, and say so: the section is labelled a live check and is
provisional, because two rule passes are not the ledger.

The legs therefore pin three things the feature can get wrong independently:

  * it answers WITHOUT an analysis (the report is still absent, the stage still
    pending — the desk is unanalysed here, on purpose);
  * it reads the current text, not the parse (undo makes the flagged row go
    away, so the rows track the working copy in both directions);
  * it is not counted (findingCounts() stays 0 while rows are on screen — the
    ONE counting path never sees `state.lint`).

Run:  python tests/e2e_browser_quickcheck.py   (boots its own studio;
      set E2E_BASE to reuse an already-running one)
"""
import time

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, clicked, launch, note, open_studio

checks = Checks()
check = checks.ok

SCRIPT = """Title: Quickcheck Script
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. HALLWAY - NIGHT

MARA walks to the door.

MARA
Some things are better left alone.
"""

# 11 words x 8 = 88: over formatting_check's 60-word action ceiling.
LONG_ACTION = "MARA studies the revolver on the desk for a long moment. " * 8

KEY = 'livecheck'
SEC = f'.dock-lens[data-lens="evidence"] .dock-section[data-key="{KEY}"]'


def seed(base, title="Quickcheck Script"):
    r = requests.post(f"{base}/api/projects",
                      files={"file": ("quickcheck.fountain", SCRIPT.encode(), "text/plain")},
                      data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("project") or title


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.evaluate("(n) => openProject(n)", name)
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
    page.locator("#right-edge-affordance").click()
    page.wait_for_selector("#context-dock.open", timeout=5000)
    page.wait_for_timeout(450)


def rows(page):
    return page.evaluate(
        """(sel) => [...document.querySelectorAll(sel + ' .dock-lint-row')]
             .map((e) => e.textContent)""", SEC)


def edit_first_action_line(page):
    """Double-click the page's first action line, replace it, press Enter —
    the inline-edit path a writer actually uses."""
    line = page.locator("#manuscript-container .el-action").first
    line.dblclick()
    page.wait_for_selector("#manuscript-container .el-action.inline-editing", timeout=5000)
    page.keyboard.press("Control+a")
    page.keyboard.type(LONG_ACTION)
    page.keyboard.press("Enter")


def wait_for_lint(page, timeout=15000):
    """Poll until the live check has answered. The request is fire-and-forget
    from the edit, so the section appearing IS the completion signal."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if page.evaluate("(s) => !!document.querySelector(s)", SEC):
            return True
        page.wait_for_timeout(150)
    return False


def run(base):
    name = seed(base)
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, base, name)

        # --- 1. nothing is claimed before the text changes --------------------
        check("no live check before an edit",
              not page.evaluate("(s) => !!document.querySelector(s)", SEC))
        check("the desk really is unanalysed here",
              page.evaluate("() => !state.report && !(state.findings || []).length"))

        # --- 2. an edit answers without an analysis ---------------------------
        edit_first_action_line(page)
        seen = wait_for_lint(page)
        if not seen:
            note("the live check never mounted", "the legs below fail by name")
        got = rows(page)
        check("the live check mounts after an inline edit, with no analysis run",
              seen and len(got) >= 1, f"{len(got)} rows")
        check("it names the rule it actually fired",
              any("long_action_block" in r for r in got), " | ".join(got[:3])[:160])
        s = requests.get(f"{base}/api/projects/{name}", timeout=15).json()
        check("still no report, still no analyse stage",
              s.get("stages", {}).get("analyze") == "pending",
              str(s.get("stages", {}).get("analyze")))

        # --- 3. it is labelled provisional, not ledger ------------------------
        title = page.evaluate(
            """(s) => { const h = document.querySelector(s + ' .dock-section-head');
                        return h ? h.textContent.replace(/\\s+/g, ' ').trim() : null }""", SEC) or ""
        low = title.lower()
        check("the header says live check", "live check" in low, title[:90])
        check("the header says the full pass is still pending",
              "provisional" in low or "pending" in low, title[:90])

        # --- 4. the ONE counting path never sees it ---------------------------
        counts = page.evaluate("() => { const c = findingCounts();"
                               "return { total: c.total, shown: c.shown, open: c.open }; }")
        check("live-check rows are not findings (findingCounts stays empty)",
              counts == {"total": 0, "shown": 0, "open": 0}, str(counts))
        check("state.findings untouched by the lint layer",
              page.evaluate("() => (state.findings || []).length") == 0)

        # --- 5. it tracks the WORKING copy: undo un-flags ---------------------
        # Both halves on purpose: the section must still answer (the check
        # re-ran) with the flagged row gone. Asserting only the absence would
        # make leg 2 vacuous — zero rows would satisfy both.
        page.evaluate("() => undoEdit()")
        page.wait_for_timeout(1500)
        after = rows(page)
        check("undo re-answers: the live check is still mounted",
              len(after) >= 1, f"{len(after)} rows")
        check("and the flagged row is gone — it reads the current text",
              not any("long_action_block" in r for r in after),
              " | ".join(after[:3])[:160])

        # --- 6. the section collapses and persists like every other ----------
        head = page.locator(SEC + " .dock-section-head")
        if head.count():
            clicked(head.first)
            check("the live check collapses under its own header",
                  page.evaluate("(s) => document.querySelector(s).dataset.open", SEC) == "false")
            prefs = page.evaluate("() => JSON.parse("
                                  "localStorage.getItem('screenplay_studio.prefs.v1') || '{}')")
            check("the collapse persists (prefs)",
                  prefs.get(f"dock_section_{KEY}") is False, str(prefs.get(f"dock_section_{KEY}")))
            page.evaluate("(k) => setDockSectionOpen("
                          "document.querySelector(`.dock-section[data-key='${k}']`), true)", KEY)

        # --- 7. server text is rendered, never interpreted --------------------
        page.evaluate("""() => { state.lint = { findings: [{ rule: 'x', severity: 'low',
            scene_refs: [], message: '<img src=x onerror=alert(1)>marker-text</img>' }],
            errors: [], ok: true }; renderDockEvidence(); }""")
        inj = page.evaluate("""() => ({
            imgs: document.querySelectorAll('.dock-lint-row img').length,
            text: [...document.querySelectorAll('.dock-lint-row')]
                    .map((e) => e.textContent).join(' ') })""")
        check("a lint row escapes what the script put in it",
              inj["imgs"] == 0 and "marker-text" in inj["text"], str(inj["imgs"]))

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as studio_base:
        run(studio_base)
