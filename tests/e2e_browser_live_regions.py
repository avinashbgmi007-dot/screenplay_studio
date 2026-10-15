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
    (2026-09-30: showError stopped deferring its text into the next animation
    frame — reveal and words now land in the same task, the canonical
    role="alert" show-with-content pattern, which kills the one-frame
    visible-but-empty window CI could read. The mutation-order check survives
    unchanged; the repeat-error clear check below had to become a frame
    sampler, because the intermediate empty write it looked for WAS that
    one-frame window.)

R6-UX-5 added the third member of the family: the beat board and the compare
panes. Both are rebuilt with `innerHTML = ""` and both carried
`aria-live="polite"`, so one drag read out the entire corkboard and one click read
out the entire diff — the announcement buried the change it was meant to report.
They are covered here as a PAIR, because either half alone is a weak fence: the
absence check proves the noise is gone, and the positive check proves the delta
still arrives. Deleting only `aria-live` would leave a screen-reader user with a
silent board and pass half the suite.

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
  const board = document.getElementById('beatboard-board');
  const panes = document.getElementById('compare-panes');
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
    board_live: live(board),
    board_role: board && board.getAttribute('role'),
    panes_live: live(panes),
    panes_role: panes && panes.getAttribute('role'),
  };
}"""

# Records every mutation with its KIND and its position in the sequence.
#
# Two traps this shape avoids, both of which made the first version of this
# suite pass against the broken code (caught by the mutation harness):
#   * a MutationObserver callback fires AFTER the DOM has advanced, so
#     `getComputedStyle` at callback time cannot see the intermediate state.
#     Reading the inline style proves nothing — the ORDER of the records is the
#     evidence. (The reveal must be recorded before any text write; since
#     showError's 2026-09-30 sync write, reveal and text land in the same
#     task, and the order still holds.)
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

# The window sampler: rAF-loop records of (banner visible?, its text), taken
# every rendered frame for one second. The mutation log CANNOT see a same-task
# clear (callbacks read final state), but a FRAME can — this is what would
# catch a future deferral reintroducing the visible-but-empty window that
# server_url_guard read twice on CI on 2026-09-30.
SAMPLE_WINDOW_JS = """() => {
  const banner = document.getElementById('error-banner');
  const text = document.getElementById('error-banner-text');
  window.__bannerWin = [];
  const tick = () => {
    window.__bannerWin.push({
      visible: getComputedStyle(banner).display !== 'none',
      text: text.textContent,
    });
    if (window.__bannerWin.length < 60) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
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
            # R6-UX-5: the same trap, in the two full-redraw regions the round-3
            # fix did not reach. `renderBeatboard()` does `board.innerHTML = ""`
            # and re-appends every card on EVERY move, and `renderCompare()` does
            # the same to the panes — so each was an `aria-live="polite"` region
            # that read the entire board back for one drag, and the whole diff for
            # one click, burying the change the user was checking.
            for key, label in (("board", "the beat board"),
                               ("panes", "the compare panes")):
                check(f"{label} is NOT a live region (rebuilt card-for-card / "
                      f"pane-for-pane, so a live region there re-announces the "
                      f"whole view for one edit)",
                      markup[f"{key}_role"] in (None, "")
                      and markup[f"{key}_live"] in ("", None),
                      json.dumps({"role": markup[f"{key}_role"],
                                  "live": markup[f"{key}_live"]}))

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
            # showError's 2026-09-30 sync fix took the intermediate empty
            # write with it: that empty write was announce()'s clear-then-
            # rewrite diff signal, and it was EXACTLY the one-frame
            # visible-but-empty window the sync write exists to kill — a
            # sampler can no longer see it. A same-string textContent
            # replacement is still a real node replacement (a mutation record
            # appears either way), so the repeat still lands. What this suite
            # can no longer observe is AT's content-diff silence on the
            # identical repeat — which was never observable from the DOM
            # anyway (see the announce() comment in app.js on the same point).
            page.evaluate("(m) => showError(m)", ERROR_MSG)
            page.wait_for_timeout(500)
            log2 = page.evaluate("() => window.__bannerLog")
            repeats = [e for e in log2
                       if e["kind"] == "text" and (e.get("text") or "").strip() == ERROR_MSG]
            check("a repeated identical error is written to the banner again",
                  len(repeats) >= 2, f"message writes: {len(repeats)}")

            # ---------- no reader can see the banner visible with empty words -
            # The regression this suite's ancestor caught (reveal and write
            # racing across a frame boundary) is now impossible by
            # construction. This continuous sampler is what pins it: fire the
            # error, then demand every sample with the banner rendered carries
            # its text already — including the very first.
            page.reload()
            page.wait_for_load_state("networkidle")
            page.evaluate(SAMPLE_WINDOW_JS)
            page.evaluate("(m) => showError(m)", ERROR_MSG)
            page.wait_for_timeout(400)
            win = page.evaluate("() => window.__bannerWin")
            empty_visible = [s for s in win
                             if s["visible"] and not (s["text"] or "").strip()]
            check("every frame the banner is rendered, it already carries its "
                  "words (no visible-but-empty window)",
                  not empty_visible, json.dumps(empty_visible[:3]))
            check("...and the sampler really saw the banner rendered with its "
                  "text (it cannot pass on an empty window)",
                  any(s["visible"] and (s["text"] or "").strip() == ERROR_MSG
                      for s in win), json.dumps(win[-3:]))

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

            # ---------- R6-UX-5: the delta still has to be SPOKEN --------------
            # Taking `aria-live` off a redrawn region only stops the noise. The
            # pair of checks below is what keeps it honest: the announcement has
            # to arrive, and it has to be the ONE THING THAT CHANGED — a sentence
            # about the card that moved, not the board.
            loaded = page.evaluate("async () => { "
                                   "if (state.view === 'beatboard') state.view = 'cowrite'; "
                                   "await loadBeatboard(); announce(''); return bbOrder.slice(); }")
            page.wait_for_timeout(300)
            check("the beat board has scenes to move (precondition)",
                  isinstance(loaded, list) and len(loaded) >= 2, json.dumps(loaded))
            moved_scene = loaded[0]
            page.evaluate("() => bbMove(0, 1)")
            page.wait_for_timeout(400)
            spoken = page.evaluate("() => document.getElementById('a11y-status').textContent || ''")
            check("one keyboard move is announced",
                  str(moved_scene) in spoken and " 2" in spoken, json.dumps(spoken[:160]))
            check("...as the one card that changed, not the board it sits on",
                  0 < len(spoken) <= 120 and spoken.count("Scene") <= 2,
                  f"announced length: {len(spoken)}")

            page.evaluate("() => announce('')")
            page.wait_for_timeout(300)
            page.evaluate("""() => renderCompare({
              from: 'draft 1', to: 'active draft', common_scene_count: 2,
              scenes: [{scene_number: 1, heading: 'INT. DEPOT - NIGHT', rows: [
                {kind: 'changed', left: 'One line.', right: 'Another line.'}]}]})""")
            page.wait_for_timeout(400)
            spoken = page.evaluate("() => document.getElementById('a11y-status').textContent || ''")
            check("opening a comparison is announced as what is being compared",
                  "draft 1" in spoken and "active draft" in spoken, json.dumps(spoken[:160]))
            check("...in a sentence, not the diff text",
                  0 < len(spoken) <= 160 and "INT. DEPOT" not in spoken,
                  f"announced length: {len(spoken)}")

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
