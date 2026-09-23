"""#25 gate — the in-place line edit is reachable without a mouse.

The manuscript's inline editor (double-click a line, type, Enter) was wired to
one gesture only. WCAG 2.1.1 is not satisfied by "there is a keyboard shortcut
somewhere" when the thing it replaces is a pointer-only affordance, and it is
not satisfied by making nine hundred script lines into nine hundred tab stops
either — that trades one barrier for a worse one.

So the contract pinned here is a ROVING one, the same shape the app already
uses for its big sets of similar items:

  * the manuscript is ONE tab stop: `s` focuses the region, no line carries
    tabindex="0";
  * ArrowDown / ArrowUp walk a focus cursor line by line through the inked
    lines (`[class^=el-]` — the same selector markCurrentLine reads);
  * Enter opens the line you are on in place, and the save/undo path underneath
    is the double-click's path, not a parallel one;
  * Escape still abandons without writing;
  * after a save the cursor is back on the manuscript, because a keyboard
    writer who has to reach for the mouse to edit the NEXT line has not been
    given a keyboard path.

Run:  python tests/e2e_browser_keyboard_edit.py   (boots its own studio;
      set E2E_BASE to reuse an already-running one)
"""
import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import studio_headers, Checks, assert_no_js_errors, launch, open_studio

checks = Checks()
check = checks.ok

SCRIPT = """Title: Keyboard Edit Script
Author: Test

INT. ARCHIVE - NIGHT

SAMIR runs a finger along the ledger rows, counting them twice.

SAMIR
Nobody has opened this book in years.

INT. ARCHIVE - CORRIDOR - CONTINUOUS

SAMIR stops at the far door and listens.

SAMIR
Something is still running behind it.
"""

NEW_TEXT = "Samir signs the ledger and slides it across the desk."


def seed(base):
    r = requests.post(f"{base}/api/projects",
                      headers=studio_headers(base),
                      files={"file": ("keyboard_edit.fountain", SCRIPT.encode(), "text/plain")},
                      data={"title": "Keyboard Edit Script"}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("project") or "Keyboard Edit Script"


def fountain(base, name):
    r = requests.get(f"{base}/api/projects/{name}/export",
                     params={"format": "fountain"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.text


def focused(page):
    return page.evaluate("""() => {
        const a = document.activeElement;
        if (!a) return null;
        const box = a.getBoundingClientRect();
        const st = getComputedStyle(a);
        return {
          text: (a.textContent || '').trim().slice(0, 40),
          inManuscript: !!a.closest('#manuscript-container'),
          isLine: /^el-/.test((a.className || '').trim()),
          editing: a.isContentEditable,
          outlineStyle: st.outlineStyle,
          outlineWidth: parseFloat(st.outlineWidth) || 0,
          top: Math.round(box.top),
        };
    }""")


def open_editor(page, timeout=4000):
    """True if the keypress put a line into edit mode. A no-op must report as a
    failed check, not abort the run halfway through the legs."""
    try:
        page.wait_for_selector("#manuscript-container [class^=el-].inline-editing",
                               timeout=timeout)
        return True
    except Exception:
        return False


def run(base):
    name = seed(base)
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(base)
        page.wait_for_load_state("networkidle")
        page.evaluate("(n) => openProject(n)", name)
        page.wait_for_selector("#manuscript-container [class^=el-]", timeout=30000)

        # --- 1. the region is one tab stop, not nine hundred -----------------
        zero_stops = page.evaluate("""() => document.querySelectorAll(
            '#manuscript-container [tabindex="0"]').length""")
        check("no manuscript line is its own tab stop",
              zero_stops == 0, f"{zero_stops} lines carry tabindex=0")
        # ... and the region itself is: `s` is a shortcut, not a discovery path.
        # A keyboard writer meeting this app for the first time finds the page
        # with Tab, so Tab has to land somewhere that can then be walked.
        tab_stop = page.evaluate("() => document.getElementById('manuscript-container').tabIndex")
        check("Tab reaches the manuscript region", tab_stop == 0, f"tabIndex={tab_stop}")

        # --- 2. `s` then the arrows walk the page ----------------------------
        page.keyboard.press("s")
        check("s focuses the manuscript region",
              page.evaluate("() => document.activeElement.id === 'manuscript-container'"))
        page.keyboard.press("ArrowDown")
        first = focused(page)
        check("ArrowDown puts the focus cursor on a line",
              first and first["inManuscript"] and first["isLine"], str(first))
        check("the focused line shows a focus ring",
              bool(first["isLine"]) and first["outlineStyle"] != "none"
              and first["outlineWidth"] > 0, str(first))

        page.keyboard.press("ArrowDown")
        second = focused(page)
        check("ArrowDown walks to the NEXT line, not a fixed one",
              second["isLine"] and second["text"] != first["text"]
              and second["top"] > first["top"], f"{first} -> {second}")
        page.keyboard.press("ArrowUp")
        back = focused(page)
        check("ArrowUp walks back to the line you came from",
              back["text"] == first["text"], f"{second['text']} -> {back['text']}")

        # --- 3. Enter edits in place and saves ------------------------------
        page.keyboard.press("Enter")
        check("Enter opened the line in place", open_editor(page))
        page.keyboard.press("Control+a")
        page.keyboard.type(NEW_TEXT)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
        saved = fountain(base, name)
        check("a keyboard-only writer changed the script on disk",
              NEW_TEXT.lower() in saved.lower(),
              "the typed line is not in the Fountain export")

        # --- 4. ... and Escape still writes nothing -------------------------
        before = fountain(base, name)
        page.evaluate("""() => {
            const ls = [...document.querySelectorAll('#manuscript-container [class^=el-]')];
            (ls.find((l) => l.textContent.trim().startsWith('SAMIR')) || ls[0]).focus();
        }""")
        page.keyboard.press("Enter")
        check("Escape leg: the line opened", open_editor(page))
        page.keyboard.press("Control+a")
        page.keyboard.type("THIS TEXT MUST NOT SURVIVE ESCAPE")
        page.keyboard.press("Escape")
        page.wait_for_timeout(1200)
        now = fountain(base, name)
        check("Escape cancels without writing",
              now == before and "MUST NOT SURVIVE" not in now,
              "the cancelled text reached the export")

        # --- 5. the cursor survives the re-render ---------------------------
        page.evaluate("() => document.getElementById('manuscript-container').focus()")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")
        landed = focused(page)
        page.keyboard.press("Enter")
        check("Save leg: the line opened", open_editor(page))
        page.keyboard.press("Control+a")
        page.keyboard.type("A second keyboard edit, to keep walking.")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
        after = focused(page)
        check("after a save the focus cursor is back on a manuscript line",
              after["inManuscript"] and after["isLine"] and after["text"] != landed["text"],
              str(after))

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as studio_base:
        run(studio_base)
