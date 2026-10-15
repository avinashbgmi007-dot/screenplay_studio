"""e2e_browser_text_popup.py — every row the selection popup offers must DO something.

R6-UX-3 (round 6, 2026-09-26). `#text-popup` rendered SEVEN actions and the click
chain at app.js branched on FOUR. So "Rewrite passage" and "Locate finding" (the
two the revision context deliberately reveals) closed the menu and did nothing —
and "Add to logline", the one row the idea context reveals, had no handler
either. Nothing in the fleet drove this popup at all, so a 1,249-check green run
sat on top of it.

Each row is now judged the same way, per context:

1. the rows it OFFERS equal the rows that work there (the fence — a row added to
   index.html without a case here fails this suite by name), and
2. clicking each offered row changes something the writer can see.

Why the sets differ from the spec's original seven:
* `rewrite` / `locate` are GONE from the markup. The revision view's own queue
  (app.js `renderFixQueuePanel`) already carries "Locate" and "Rewrite" per
  finding, with the finding object in hand — the thing a text selection cannot
  supply, since `openRewriteModal` needs a scene + finding index and
  `locateFinding` needs the finding. A worse duplicate that silently no-ops is
  worse than no row.
* the idea context keeps only "Ask Sameer". It has no project, so "Stash this"
  hit the `state.currentProject` guard and did nothing and "Add margin note"
  parked text in a note form that cannot save; "Add to logline" pointed at
  `#idea-logline`, a field inside `#idea-structure-panel`, which is `display:
  none` until the writer presses "▸ Structure". The idea room already has its
  own selection surface for the one action that works there (`#idea-quote-float`
  → `askSamAboutSelection`).
* "Ask Consultant" was HALF alive, and this is a second R6-UX-1: it called
  `openFeedbackRoom()`, which sets `#cowrite-panel` — the only panel `#input`
  lives in — to `display: none`, and then typed the quote into that hidden
  composer. It now takes the route the product already uses to reach the doctor
  (`discussWithDoctor`): pin the quote, open the dock's Sushruta lens, seed and
  focus that lens's own composer.

Run:  python tests/e2e_browser_text_popup.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import studio_headers, Checks, launch, open_studio, assert_no_js_errors  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok

# The rows each context is allowed to offer. Anything else appearing is a row
# with no case below it; anything missing is a row that was dropped silently.
OFFERED = {
    "script": {"ask-sameer", "ask-consultant", "margin-note", "stash"},
    "revision": {"ask-sameer", "ask-consultant"},
    "idea": {"ask-sameer"},
}

# Make a REAL selection under `rootSel` and end it with a real mouseup, which is
# the only way the popup is reached (its mouseup listener owns the show).
SELECT = """
([rootSel]) => {
  const root = document.querySelector(rootSel);
  if (!root) return { error: 'no root: ' + rootSel };
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = null;
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.trim().length > 3) { node = walker.currentNode; break; }
  }
  if (!node) return { error: 'no text node under ' + rootSel };
  const range = document.createRange();
  range.selectNodeContents(node);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  const rect = range.getBoundingClientRect();
  root.dispatchEvent(new MouseEvent('mouseup', {
    bubbles: true, cancelable: true, clientX: rect.left + 2, clientY: rect.bottom - 2,
  }));
  const popup = document.getElementById('text-popup');
  return {
    text: sel.toString().trim(),
    shown: [...popup.querySelectorAll('.text-popup-item')]
      .filter((e) => e.style.display !== 'none').map((e) => e.dataset.action),
    visible: popup.style.display === 'block',
  };
}
"""

RESET = """() => {
  document.getElementById('input').value = '';
  document.getElementById('dock-note-input').value = '';
  const c = document.getElementById('fv-consult-input');
  if (c) c.value = '';
  window.getSelection().removeAllRanges();
}"""

# One read of everything a row is allowed to touch. `inputVisible` is here because
# R6-UX-1 was exactly this failure shape: text written into a composer the writer
# cannot see, and a check that passed anyway.
OBSERVE = """() => {
  const onScreen = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 20 && cs.visibility !== 'hidden' && cs.pointerEvents !== 'none';
  };
  const input = document.getElementById('input');
  const consult = document.getElementById('fv-consult-input');
  return {
    view: state.view,
    inIdea: !!state.inIdea,
    input: input.value,
    inputFocused: document.activeElement === input,
    inputVisible: onScreen(input),
    drawer: !!document.querySelector('#room-drawer.open'),
    dock: dockIsOpen(),
    consult: consult ? consult.value : null,
    consultFocused: !!consult && document.activeElement === consult,
    consultVisible: onScreen(consult),
    noteInput: document.getElementById('dock-note-input').value,
    popupClosed: document.getElementById('text-popup').style.display === 'none',
  };
}"""


def offer(page, root_sel):
    page.evaluate(RESET)
    page.wait_for_timeout(120)
    out = page.evaluate(SELECT, [root_sel])
    return out


def click_row(page, action):
    # A real click, so a row that is only *listed* but not on screen fails here
    # instead of quietly passing an evaluate-based one.
    page.locator(f'#text-popup [data-action="{action}"]').click()
    page.wait_for_timeout(500)


def stash_count(base, project):
    body = requests.get(f"{base}/api/projects/{project}/stash", timeout=30).json()
    return len(body["stash"])


def stash_count_until(base, project, want, timeout=8000):
    """Poll the SERVER until the Stash holds `want` cards; return the last count.

    The row's handler is one async POST, so reading the count straight after the
    click's 500ms settle is a race: measured 2026-10-02, the Windows CI runner
    reported "0 -> 0" while the identical commit passed on the parallel run.
    Waiting for the real round trip keeps the check honest — it still fails, by
    name, if the card never lands.
    """
    deadline = time.time() + timeout / 1000.0
    n = stash_count(base, project)
    while n != want and time.time() < deadline:
        time.sleep(0.25)
        n = stash_count(base, project)
    return n


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            with open(FIXTURE, "rb") as f:
                r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                                  files={"file": ("popup.fountain", f, "text/plain")},
                                  data={"title": "Text Popup"}, timeout=60)
            assert r.status_code in (200, 201), r.text
            project = r.json()["project"]
            page.evaluate("async (n) => { await openProject(n); }", project)
            page.wait_for_timeout(1500)

            # ---------- the dead rows are gone from the DOM, not just hidden ----
            gone = page.evaluate("""() => [...document.querySelectorAll('#text-popup [data-action]')]
                .map((e) => e.dataset.action)""")
            check("the popup's markup no longer offers the rows nothing handles",
                  not ({"rewrite", "locate", "add-logline"} & set(gone)), json.dumps(gone))

            # ---------- script context: the four actions that work -------------
            page.evaluate("() => closeRoomDrawer()")
            page.evaluate("() => closeDock()")
            page.wait_for_timeout(300)
            got = offer(page, "#manuscript-container")
            check("selecting a line on the desk offers exactly the working rows",
                  not got.get("error") and got["visible"]
                  and set(got["shown"]) == OFFERED["script"], json.dumps(got))

            click_row(page, "ask-sameer")
            o = page.evaluate(OBSERVE)
            check("Ask Sameer puts the quote in a composer the writer can SEE",
                  o["input"].startswith("/sameer") and o["drawer"]
                  and o["inputVisible"] and o["inputFocused"], json.dumps(o))
            check("...and closes the menu", o["popupClosed"], json.dumps(o))

            got = offer(page, "#manuscript-container")
            click_row(page, "ask-consultant")
            o = page.evaluate(OBSERVE)
            check("Ask Consultant opens the doctor's lens with a composer the writer can SEE",
                  got["text"][:60] in (o["consult"] or "") and o["dock"]
                  and o["consultVisible"] and o["consultFocused"],
                  json.dumps({"got": got, "o": o}))

            got = offer(page, "#manuscript-container")
            click_row(page, "margin-note")
            o = page.evaluate(OBSERVE)
            check("Add margin note opens the lens and carries the text",
                  o["dock"] and o["noteInput"] == got["text"][:200],
                  json.dumps({"got": got, "o": o}))

            before = stash_count(base, project)
            offer(page, "#manuscript-container")
            click_row(page, "stash")
            after = stash_count_until(base, project, before + 1)
            check("Stash this files a card in the Stash (server round trip)",
                  after == before + 1, f"{before} -> {after}")

            # ---------- revision context --------------------------------------
            page.evaluate("async () => { await openRevisionView(); }")
            page.wait_for_timeout(1200)
            got = offer(page, "#revision-script")
            check("in the revision view the popup offers only the two asks",
                  not got.get("error") and set(got["shown"]) == OFFERED["revision"],
                  json.dumps(got))
            offer(page, "#revision-script")
            click_row(page, "ask-sameer")
            o = page.evaluate(OBSERVE)
            check("...and both of them work — Ask Sameer from a revision page",
                  o["input"].startswith("/sameer") and o["inputVisible"], json.dumps(o))
            page.evaluate("() => closeRevisionView()")
            page.wait_for_timeout(600)

            # ---------- idea context -----------------------------------------
            idea = requests.post(f"{base}/api/ideas", headers=studio_headers(base),
                                 json={"title": "popup idea"}, timeout=30).json()
            page.evaluate("async (id) => { await openIdea(id); }", idea["id"])
            page.wait_for_timeout(1200)
            got = offer(page, "#idea-canvas")
            check("in the idea room the popup offers only what has no project to break it",
                  not got.get("error") and set(got["shown"]) == OFFERED["idea"],
                  json.dumps(got))
            click_row(page, "ask-sameer")
            o = page.evaluate(OBSERVE)
            check("Ask Sameer works in the idea room too",
                  o["inIdea"] and o["input"].startswith("/sameer") and o["drawer"],
                  json.dumps(o))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
