"""e2e_browser_modal_guards.py — the keyboard belongs to the dialog while a
dialog is open, and one Escape press spends one rung.

Re-audit 2026-09-24, findings H4 + M5 + M6 + M7 + L8 + L9:

  * **H4** — after the modal-Esc branch, `bindGlobalShortcuts` bailed only for
    typing targets. With a dialog open and focus on a non-typing control (any
    button), `c/f/a/b/d/v/z/?` all fired BEHIND the dialog, and `s` called
    `getManuscriptContainer().focus()`, pulling focus out of the dialog and
    silently defeating the Tab trap.
  * **M5** — the backdrop click wrote `overlay.style.display = "none"` directly
    instead of going through `closeModal()`, so focus was never restored and the
    writer was dumped at <body> (the spec's "modals restore focus on close").
  * **M6** — a standalone document Escape listener closed sidebar flyouts on ANY
    Escape, so with a pinned flyout plus the dock open one press spent two rungs.
  * **M7** — a file dropped anywhere but #dropzone navigated the tab to the file
    (the SPA unloads mid-session): nothing cancelled the page-level default.
  * **L8** — `#pane-divider` is `role="separator"` but mouse-only: no tabindex,
    no arrow keys, no aria-valuenow, and the width it sets is persisted.
  * **L9** — `#palette-modal`'s dialog is the one overlay without `aria-modal`.

Run:  python tests/e2e_browser_modal_guards.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import studio_headers, Checks, launch, open_studio, assert_no_js_errors  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed_project(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["project"]


# A Files drag and a text drag on the same document, one per assertion.
DROP_PROBE = """
() => {
  const fileDt = new DataTransfer();
  fileDt.items.add(new File(['hi'], 'late.fountain', {type: 'text/plain'}));
  const fileOver = new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: fileDt});
  const fileDrop = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: fileDt});
  const overCancelled = !document.body.dispatchEvent(fileOver);
  const dropCancelled = !document.body.dispatchEvent(fileDrop);

  const note = document.querySelector('#dock-note-input');
  const textDt = new DataTransfer();
  textDt.setData('text/plain', 'a line of the script');
  const textOver = new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: textDt});
  const textCancelled = note ? !note.dispatchEvent(textOver) : null;
  return {
    fileTypes: [...fileDt.types],
    overCancelled, dropCancelled,
    textFieldFound: !!note, textCancelled,
  };
}
"""


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            name = seed_project(base, "Modal Guards")
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_timeout(1500)

            # ---------- H4: a dialog owns the keyboard ----------------------
            # the desk collapses the sidebar (manuscript first); Settings lives in
            # its footer, so expand it the way a writer would
            page.evaluate("() => toggleSidebar(false)")
            page.wait_for_timeout(400)

            def stray_key(key):
                """Press one key with a dialog open and focus on a NON-typing
                control, report what the app did behind the dialog, restore.

                Each key is probed from a FRESH dialog: otherwise the first stray
                letter poisons the state the next probe is measured in — pressing
                'b' mounts the Beat Board, which then hides the desk (and the
                script pane) that the later probes read. Focus must be on a
                button, not the field openModal() parks focus in, because an
                input is a typing target the cascade already bails on.
                """
                page.locator("#settings-btn").click()
                page.wait_for_timeout(350)
                page.evaluate("() => document.getElementById('settings-cancel').focus()")
                page.keyboard.press(key)
                page.wait_for_timeout(350)
                out = page.evaluate("""() => ({
                    view: state.view,
                    board: document.getElementById('beatboard-view').style.display,
                    modalOpen: document.getElementById('settings-modal').style.display,
                    focusInModal: !!(document.activeElement && document.activeElement.closest('#settings-modal')),
                    active: document.activeElement.id || document.activeElement.tagName,
                    spotlight: document.body.classList.contains('spotlight-mode'),
                })""")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                if page.evaluate("() => state.view") == "beatboard":
                    page.evaluate("() => closeBeatboardView()")
                    page.wait_for_timeout(400)
                return out

            check("settings dialog parks focus on a control inside itself (precondition)",
                  page.evaluate("() => !!document.getElementById('settings-cancel')"))
            b_state = stray_key("b")
            check("'b' does not mount the Beat Board behind an open dialog",
                  b_state["view"] != "beatboard" and b_state["board"] != "flex"
                  and b_state["modalOpen"] == "flex", json.dumps(b_state))
            s_state = stray_key("s")
            check("'s' cannot pull focus out of an open dialog (the Tab trap holds)",
                  s_state["focusInModal"] and s_state["active"] == "settings-cancel"
                  and s_state["modalOpen"] == "flex", json.dumps(s_state))
            z_state = stray_key("z")
            check("'z' does not toggle spotlight behind an open dialog",
                  not z_state["spotlight"], json.dumps(z_state))
            check("Esc still closes the dialog (the branch above the guard)",
                  page.evaluate("() => document.getElementById('settings-modal').style.display") == "none")
            check("the desk is back after the stray-key probes (isolation)",
                  page.evaluate("() => state.view") != "beatboard")

            # ---------- M5: the backdrop click is a close, focus restored ----
            page.evaluate("() => toggleSidebar(false)")
            page.wait_for_timeout(300)
            page.locator("#settings-btn").click()
            page.wait_for_timeout(400)
            inside = page.evaluate("""() => ({
                active: document.activeElement.id || document.activeElement.tagName,
                inModal: !!(document.activeElement && document.activeElement.closest('#settings-modal')),
            })""")
            check("settings dialog parks focus inside itself on open (precondition)",
                  inside["inModal"], json.dumps(inside))
            page.locator("#settings-modal").click(position={"x": 6, "y": 6})
            page.wait_for_timeout(400)
            m5 = page.evaluate("""() => ({
                closed: document.getElementById('settings-modal').style.display === 'none',
                active: document.activeElement.id || document.activeElement.tagName,
                visible: !!(document.activeElement && document.activeElement.offsetParent),
            })""")
            check("clicking the backdrop closes the dialog", m5["closed"], json.dumps(m5))
            check("...and focus returns to the (visible) control that opened it",
                  m5["active"] == "settings-btn" and m5["visible"], json.dumps(m5))
            # ---------- M6: one Escape spends one rung ----------------------
            page.locator("#ideas-trigger").click()      # pins a sidebar flyout open
            page.wait_for_timeout(500)
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(500)
            # the focus location IS the probe: openDock() parks focus on a dock
            # control, and a typing target makes the cascade bail — then the
            # standalone flyout listener would spend the press alone and the
            # "one rung" outcome would be an accident, not the fix
            page.evaluate("() => document.getElementById('settings-btn').focus()")
            rungs_before = page.evaluate("""() => ({
                flyout: !!document.querySelector('.sidebar-section.open'),
                dock: dockIsOpen(),
                typingTarget: isTypingTarget(document.activeElement),
            })""")
            check("pinned flyout + dock are both open, focus outside a field (precondition)",
                  rungs_before["flyout"] and rungs_before["dock"]
                  and not rungs_before["typingTarget"], json.dumps(rungs_before))
            # Ask the press which rung-spending function it called: the defect is
            # literally "one press called both", and counting calls is exact where
            # reading two booleans afterwards is not.
            page.evaluate("""() => {
              window.__escCalls = [];
              const wrap = (name) => { const orig = window[name];
                window[name] = function () { window.__escCalls.push(name); return orig.apply(this, arguments); }; };
              wrap('closeDock');
              wrap('closeSidebarFlyouts');
            }""")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            rungs_after = page.evaluate("""() => ({
                flyout: !!document.querySelector('.sidebar-section.open'),
                dock: dockIsOpen(),
                spent: window.__escCalls.filter((c) => c === 'closeDock' || c === 'closeSidebarFlyouts'),
            })""")
            check("one Escape spends exactly ONE rung",
                  len(rungs_after["spent"]) == 1, json.dumps(rungs_after))
            check("...and the rung it spends is the dock, leaving the sidebar flyout",
                  rungs_after["spent"] == ["closeDock"]
                  and rungs_before["dock"] and not rungs_after["dock"]
                  and rungs_after["flyout"], json.dumps(rungs_after))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            check("the next Escape spends the flyout's rung",
                  not page.evaluate("() => !!document.querySelector('.sidebar-section.open')")
                  and not page.evaluate("() => dockIsOpen()"))

            # ---------- M7: a stray file drop must not unload the app --------
            page.evaluate("() => openDock('notes')")
            page.wait_for_timeout(500)
            drop = page.evaluate(DROP_PROBE)
            check("the probe drags real Files and lands on a real text field",
                  "Files" in (drop["fileTypes"] or []) and drop["textFieldFound"], json.dumps(drop))
            check("a file dragged over the page never reaches the browser default",
                  drop["overCancelled"], json.dumps(drop))
            check("a file DROPPED on the page never navigates the tab away",
                  drop["dropCancelled"], json.dumps(drop))
            check("...while a TEXT drag into a field is still left alone (pasting by drag works)",
                  drop["textCancelled"] is False, json.dumps(drop))

            # ---------- L8: the pane divider is a keyboard control -----------
            # The divider was ONLY visible in the idea room (the desk's layout is
            # full width by design), and it was measured as a NO-OP: a 240px mouse
            # drag set `#script-pane`'s inline flex and moved nothing, because
            # style.css pins `flex: 1 1 auto !important` ("the retired divider code
            # must never squeeze the page back into a 70/30 split") — while the
            # drag still wrote a `pane-width-v2` pref nothing honoured and left a
            # mouse-only `role="separator"` on screen. So L8's fix is a RETIREMENT,
            # not a tabindex: a keyboard path for a control that cannot move
            # anything is worse than no control at all.
            acts = requests.get(f"{base}/api/ideas", headers=studio_headers(base), timeout=30).json()
            ideas = acts if isinstance(acts, list) else acts.get("ideas", [])
            if ideas:
                page.evaluate("async (id) => { await openIdea(id); }", ideas[0]["id"])
            else:
                page.evaluate("() => createIdea()")
            page.wait_for_timeout(1600)
            idea = page.evaluate("""() => {
                const sp = document.getElementById('script-pane');
                const desk = document.querySelector('.desk');
                const dead = [...document.querySelectorAll('[role="separator"]')]
                    .filter((el) => getComputedStyle(el).cursor === 'col-resize');
                return {
                    dividerGone: !document.getElementById('pane-divider'),
                    deadResizers: dead.length,
                    paneW: Math.round(sp.getBoundingClientRect().width),
                    deskW: Math.round(desk.getBoundingClientRect().width),
                    leftoverPref: localStorage.getItem('pane-width-v2'),
                };
            }""")
            check("the retired pane divider is gone from the DOM",
                  idea["dividerGone"], json.dumps(idea))
            check("no dead col-resize affordance is left on screen",
                  idea["deadResizers"] == 0, json.dumps(idea))
            check("the idea page still fills the room it was always drawn at",
                  idea["paneW"] >= idea["deskW"] - 8, json.dumps(idea))

            # ---------- L9: the palette's dialog is declared modal -----------
            page.keyboard.press("Control+k")
            page.wait_for_timeout(500)
            pal = page.evaluate("""() => {
                const inner = document.querySelector('#palette-modal .modal[role="dialog"]');
                return {found: !!inner, ariaModal: inner && inner.getAttribute('aria-modal')};
            }""")
            check("the command palette's dialog is marked aria-modal",
                  pal["found"] and pal["ariaModal"] == "true", json.dumps(pal))
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

            # ---------- M11: the dock's Escape return point is the LAST opener --
            # The L8 probe leaves the desk for the idea page, where there is no
            # dock to focus into, so come back to a real project first. The openers
            # are two controls the desk always paints: settings-btn and
            # ideas-trigger live behind #overflow-toggle at this width, and focus()
            # on a display:none control silently does nothing — which is a fixture
            # bug, not a finding.
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_function("() => !document.body.classList.contains('idea-mode')",
                                   timeout=15000)
            # openDock() used to capture the opener only when the dock was closed
            # (`if (!dockIsOpen())`), so a lens switch — which re-enters openDock
            # with the dock already open — kept the FIRST opener. Escape then
            # jumped back to a control the writer stopped using several clicks ago.
            page.evaluate("() => closeDock()")
            page.wait_for_timeout(200)
            page.evaluate("() => { document.getElementById('home-btn').focus(); }")
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(400)
            focus_in_dock = page.evaluate(
                "() => !!document.activeElement.closest('#context-dock')")
            check("openDock parks focus inside the dock (precondition)",
                  focus_in_dock, json.dumps(focus_in_dock))
            page.evaluate("() => document.getElementById('focus-btn').focus()")
            page.evaluate("() => openDock('notes')")
            page.wait_for_timeout(400)
            page.evaluate("() => closeDock()")
            page.wait_for_timeout(300)
            back = page.evaluate(
                "() => document.activeElement.id || document.activeElement.tagName")
            check("Escape/close returns to the control the writer last used, not the first",
                  back == "focus-btn", back)
            # and the other half: focus already INSIDE the dock must not become the
            # return point, or closing hands focus to a tab that is hidden a moment
            # later. openDock() parks focus on the lens tab (`#dock-tab-<lens>`),
            # so after the probe above the focus is already there.
            page.evaluate("() => document.getElementById('home-btn').focus()")
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(400)
            page.evaluate("() => openDock('notes')")
            page.wait_for_timeout(400)
            page.evaluate("() => closeDock()")
            page.wait_for_timeout(300)
            kept = page.evaluate(
                "() => document.activeElement.id || document.activeElement.tagName")
            check("a lens switch from inside the dock keeps the opener as the return point",
                  kept == "home-btn", kept)
            # third half: an opener detached by a re-render used to leave focus on
            # <body>, so the next Tab restarted at the top of the document.
            page.evaluate("""() => {
                const s = document.createElement('span');
                s.id = '__detached_opener'; s.tabIndex = -1;
                s.textContent = 'x';
                document.getElementById('main').appendChild(s);
                s.focus();
            }""")
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(400)
            page.evaluate("() => document.getElementById('__detached_opener').remove()")
            page.evaluate("() => closeDock()")
            page.wait_for_timeout(300)
            fell = page.evaluate("""() => ({
                active: document.activeElement.id || document.activeElement.tagName,
                body: document.activeElement === document.body,
            })""")
            check("a detached opener falls back to the dock's own affordance, not <body>",
                  fell["active"] == "right-edge-affordance" and not fell["body"],
                  json.dumps(fell))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()


