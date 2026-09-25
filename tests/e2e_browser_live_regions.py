"""e2e_browser_live_regions.py — errors and replies must reach a screen reader.

UX-1 (round-3 audit 2026-09-25): `#error-banner` and `#messages-scroll` were not
live regions, so an error and every chat reply were silent to assistive tech
(WCAG 4.1.3 Status Messages, AA). `#a11y-status` existed for exactly this and
carried only the manuscript-load count. No test anywhere asserted a live region,
which is why it went unnoticed for three rounds.

Two things this suite is careful about, because both are easy to get wrong and
both would make it worthless:

  * **`#messages-scroll` must NOT become a live region.** `renderMessages()`
    rebuilds it with `innerHTML = ""`, so a live region there would re-announce
    the entire conversation on every re-render — the same trap the manuscript
    region's own comment in index.html records. There is a check for the absence,
    not just for the presence of the fix.
  * **"Rendered" is the load-bearing half of an announcement.** A `role="alert"`
    region that is `display:none` is not in the accessibility tree, so writing
    its text there is announced to nobody. This suite observes the actual
    mutation sequence with a MutationObserver and asserts the text never became
    non-empty while the banner was hidden — a check that fails against the
    original `showError`, which wrote the text first and revealed second.

Run:  python tests/e2e_browser_live_regions.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    Checks,
    assert_no_js_errors,
    launch,
    open_studio,
    send_chat,
    studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

ERROR_MSG = "Live-region probe: the disk is full."

MARKUP_JS = """() => {
  const a11y = document.getElementById('a11y-status');
  const banner = document.getElementById('error-banner');
  const scroller = document.getElementById('messages-scroll');
  const live = (el) => el ? (el.getAttribute('aria-live') || '') : 'MISSING';
  return {
    a11y_role: a11y && a11y.getAttribute('role'),
    a11y_live: live(a11y),
    a11y_rendered: a11y ? getComputedStyle(a11y).display : null,
    banner_role: banner && banner.getAttribute('role'),
    banner_aria_live: live(banner),
    scroller_role: scroller && scroller.getAttribute('role'),
    scroller_live: live(scroller),
    scroller_rendered: scroller ? getComputedStyle(scroller).display : null,
  };
}"""

# Records every mutation with its KIND and its position in the sequence.
#
# Two traps this shape avoids, both of which made the first version of this
# suite pass against the broken code (caught by the mutation harness):
#   * a MutationObserver callback fires AFTER the DOM has advanced, so
#     `getComputedStyle` at callback time cannot see the intermediate state.
#     Reading the inline style proves nothing — the ORDER of the records is the
#     evidence. (The reveal must be recorded before any text write.)
#   * logging the text on EVERY mutation makes a style change look like a text
#     change, so a "was it written twice?" count silently counted style writes.
#     Only `kind === 'text'` entries may be counted as writes.
ARM_BANNER_JS = """() => {
  const banner = document.getElementById('error-banner');
  const text = document.getElementById('error-banner-text');
  window.__bannerLog = [];
  const record = (mutations) => {
    for (const mu of mutations) {
      const isText = mu.target === text || (text.contains && text.contains(mu.target));
      window.__bannerLog.push({
        kind: isText ? 'text' : 'style',
        text: text.textContent,
        display: getComputedStyle(banner).display,
      });
    }
  };
  const mo = new MutationObserver(record);
  mo.observe(banner, { attributes: true, attributeFilter: ['style'] });
  mo.observe(text, { childList: true, characterData: true, subtree: true });
  return true;
}"""


def _wait_for(page, condition, ms=10000):
    try:
        page.wait_for_function(condition, timeout=ms)
        return True
    except Exception:
        return False


def main():
    checks = Checks()
    check = checks.ok

    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            # ---------- the regions themselves --------------------------------
            markup = page.evaluate(MARKUP_JS)
            check("#a11y-status is an always-present live region",
                  markup["a11y_role"] == "status" and markup["a11y_live"] == "polite"
                  and markup["a11y_rendered"] != "none",
                  json.dumps({k: markup[k] for k in
                              ("a11y_role", "a11y_live", "a11y_rendered")}))
            check("the error banner is an alert",
                  markup["banner_role"] == "alert", json.dumps(markup["banner_role"]))
            check("the message list is NOT a live region (it is rebuilt wholesale, "
                  "so a live region there would re-announce the whole conversation)",
                  markup["scroller_role"] in (None, "") and markup["scroller_live"] in ("", None),
                  json.dumps({"role": markup["scroller_role"], "live": markup["scroller_live"]}))

            # ---------- an error is announced where it can be heard -----------
            page.evaluate(ARM_BANNER_JS)
            page.evaluate("(m) => showError(m)", ERROR_MSG)
            page.wait_for_timeout(500)
            log = page.evaluate("() => window.__bannerLog")
            first_style = next((i for i, e in enumerate(log) if e["kind"] == "style"), None)
            first_text = next((i for i, e in enumerate(log)
                               if e["kind"] == "text" and (e.get("text") or "").strip()), None)
            check("the error text reaches the banner at all",
                  first_text is not None, json.dumps(log[-4:]))
            check("...and the reveal is recorded BEFORE any text is written "
                  "(a role=alert that is display:none announces to nobody)",
                  first_style is not None and first_text is not None
                  and first_style < first_text,
                  json.dumps({"first_style_record": first_style,
                              "first_text_record": first_text,
                              "sequence": log[:4]}))

            # ---------- the SAME error again is still a change ----------------
            # Note what is and is not observable here. `textContent = sameString`
            # REPLACES the text node unconditionally, so a DOM record appears
            # whether or not the line was cleared first — counting message writes
            # alone therefore proves nothing about the clear. What the clear DOES
            # leave behind is an intermediate empty write, and that is the part
            # that makes the re-write a text CHANGE for a screen reader that
            # diffs content instead of re-reading the node.
            page.evaluate("(m) => showError(m)", ERROR_MSG)
            page.wait_for_timeout(500)
            log2 = page.evaluate("() => window.__bannerLog")
            repeats = [e for e in log2
                       if e["kind"] == "text" and (e.get("text") or "").strip() == ERROR_MSG]
            clears = [e for e in log2
                      if e["kind"] == "text" and not (e.get("text") or "").strip()]
            check("a repeated identical error is written to the banner again",
                  len(repeats) >= 2, f"message writes: {len(repeats)}")
            check("...and the line is CLEARED first, so the re-write is a text "
                  "change rather than a same-string replacement",
                  len(clears) >= 1, f"empty-text writes: {len(clears)}")

            page.evaluate("() => hideError()")

            # ---------- the status line has one writer, not a last-write race --
            page.evaluate("() => { announce('first'); announce('second'); }")
            page.wait_for_timeout(400)
            latest = page.evaluate("() => document.getElementById('a11y-status').textContent")
            check("a stale announcement cannot clobber a newer one",
                  latest == "second", json.dumps(latest))

            # ---------- a reply is announced ----------------------------------
            seeded = requests.post(f"{base}/api/sample",
                                   headers=studio_headers(base), timeout=60)
            assert seeded.status_code in (200, 201), seeded.text
            project = seeded.json()["project"]
            page.evaluate("async (p) => { await openProject(p); }", project)
            opened = _wait_for(page, "() => state.script && state.script.scenes")
            check("a project is open (precondition)", opened)

            page.evaluate("() => { if (typeof openRoomDrawer === 'function') openRoomDrawer(); }")
            drawer = _wait_for(page, "() => document.querySelector('#room-drawer.open')", 8000)
            check("the room drawer opens (precondition)", drawer,
                  "the composer is display:none without it, so no turn can be sent")

            # Clear the line first: otherwise a leftover "second" would make the
            # reply check pass for the wrong reason.
            page.evaluate("() => announce('')")
            page.wait_for_timeout(300)

            sent = send_chat(page, "One line of notes on the opening scene, please.")
            check("the chat turn was sent (precondition)", sent)
            replied = _wait_for(
                page,
                "() => (document.getElementById('a11y-status').textContent || '')"
                ".startsWith('Studio replied')",
                90000)
            spoken_reply = page.evaluate(
                "() => document.getElementById('a11y-status').textContent || ''")
            check("a completed chat reply is announced", replied, json.dumps(spoken_reply[:160]))
            check("...as a bounded excerpt, not the whole reply",
                  replied and 0 < len(spoken_reply) <= 300,
                  f"announced length: {len(spoken_reply)}")

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
