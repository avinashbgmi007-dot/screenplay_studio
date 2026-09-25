"""e2e_browser_beatboard_drag.py — the Beat Board's reorder contract, dragged.

H3 (re-audit 2026-09-24). `bindBeatboardDrag`'s `dragover` handler called
`renderBeatboard()` on the first crossing, and that opens with
`board.innerHTML = ""` — so the FIRST crossing destroyed the drag SOURCE node,
mid-gesture. Two failures at once:

  * a native drag whose source is detached is cancelled by the browser (the drag
    ghost vanishes, no further dragover/drop arrives, dragend fires on the
    detached node), and
  * the rebuilt cards are wired by a FRESH closure whose `dragNum` starts null,
    so every later dragover bails on `dragNum != null` and nothing reorders.

The writer's experience: one grab moves a card exactly one slot, ever — and that
single crossing had already spliced `bbOrder` and set `bbDirty`, so they also
inherit a partial reorder they never completed (offered up as "Save order").

The old coverage could not see it: phase10 drags a card ONCE (the only hop that
worked) with synthetic DragEvents, and synthetic events do not abort on source
removal. These probes drive the same synthetic events but assert the two things
that actually broke — the node must SURVIVE the drag, and the board must NOT
rebuild while the gesture is live — plus the multi-hop outcome and the keyboard
path's focus (M4: the ↑/↓ buttons re-render the board, which used to drop focus
to <body> on every hop).

Run:  python tests/e2e_browser_beatboard_drag.py
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


# One gesture, two crossings, with a live lookup for the second target (the node
# that exists at that moment — which is exactly what a real drag hits).
DRAG_PROBE = r"""
() => {
  const board = document.getElementById('beatboard-board');
  const nums = () => [...board.querySelectorAll('.bb-card')].map((c) => Number(c.dataset.num));
  const live = (n) => board.querySelector('.bb-card[data-num="' + n + '"]');
  const order0 = nums();
  if (order0.length < 4) return {ok: false, why: 'need at least 4 cards', order0};
  const srcNum = order0[0], firstOver = order0[1], secondOver = order0[2];

  const src = live(srcNum);
  window.__bbSrc = src;
  const realRender = window.renderBeatboard;
  let renders = 0;
  window.renderBeatboard = function () { renders += 1; return realRender.apply(this, arguments); };
  const dt = () => new DataTransfer();
  const ev = (type) => new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt()});

  src.dispatchEvent(ev('dragstart'));
  live(firstOver).dispatchEvent(ev('dragover'));
  const afterHop1 = nums();
  const rendersAfterHop1 = renders;
  live(secondOver).dispatchEvent(ev('dragover'));
  const afterHop2 = nums();
  const rendersDuringDrag = renders;
  // the contract is that the source survives the GESTURE — the repaint that
  // follows dragend is allowed to rebuild the board (the gesture is over)
  const srcSurvivesMidDrag = !!window.__bbSrc && window.__bbSrc.isConnected;
  src.dispatchEvent(ev('dragend'));
  window.renderBeatboard = realRender;

  const afterDragend = nums();
  const labels = [...board.querySelectorAll('.bb-card')].map((c) => c.querySelector('.bb-card-pos').textContent);
  const finalIdx = afterDragend.indexOf(srcNum);
  return {
    ok: true, srcNum, order0, afterHop1, afterHop2, afterDragend,
    srcSurvivesMidDrag,
    srcSurvivesAfterDragend: !!window.__bbSrc && window.__bbSrc.isConnected,
    rendersAfterHop1, rendersDuringDrag, rendersAfterDragend: renders,
    slotsMoved: finalIdx - order0.indexOf(srcNum),
    posLabel: labels[finalIdx],
    expectPosLabel: String(finalIdx + 1).padStart(2, '0'),
    dirty: document.getElementById('bb-save-btn').classList.contains('dirty'),
  };
}
"""


def seed_project(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["project"]


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            name = seed_project(base, "BB Drag")
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_timeout(1500)
            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(1200)

            drag = page.evaluate(DRAG_PROBE)
            check("beat board has enough cards to reorder (precondition)",
                  drag.get("ok"), json.dumps(drag))
            if drag.get("ok"):
                order0 = drag["order0"]
                check("reordering never rebuilds the board while the drag is live",
                      drag["rendersDuringDrag"] == 0,
                      f"renderBeatboard ran {drag['rendersDuringDrag']}x mid-drag "
                      f"(after hop 1: {drag['rendersAfterHop1']}x) — the innerHTML wipe "
                      "destroys the drag source")
                check("the dragged card node survives the whole gesture",
                      drag["srcSurvivesMidDrag"],
                      "the drag source was detached mid-drag (innerHTML = '') — a native "
                      "drag is cancelled and no drop can land")
                check("one grab carries the card across BOTH crossings",
                      drag["afterHop2"][:3] == [order0[1], order0[2], order0[0]],
                      f"{order0} -> after hop1 {drag['afterHop1']} -> after hop2 {drag['afterHop2']}")
                check("the card ends two slots along (one gesture, two slots)",
                      drag["slotsMoved"] == 2, json.dumps(drag["afterDragend"]))
                check("position labels repaint once the gesture ends",
                      drag["posLabel"] == drag["expectPosLabel"],
                      f"label {drag['posLabel']} != {drag['expectPosLabel']} at the card's slot")
                check("the gesture marks the order dirty (save contract)", drag["dirty"],
                      json.dumps(drag))
                check("exactly one repaint for the whole gesture",
                      drag["rendersAfterDragend"] == 1,
                      f"renders={drag['rendersAfterDragend']}")

            # ---------- the keyboard path: the move buttons must keep focus ----
            page.evaluate("() => closeBeatboardView()")
            page.wait_for_timeout(400)
            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(1200)
            before = page.evaluate(
                "() => [...document.querySelectorAll('#beatboard-board .bb-card')].map((c) => Number(c.dataset.num))")
            page.locator("#beatboard-board .bb-card").nth(1).locator(".bb-move").nth(1).focus()
            page.keyboard.press("Enter")             # down on the second card
            page.wait_for_timeout(400)
            focus = page.evaluate("""() => ({
                inBoard: !!document.activeElement.closest('#beatboard-board'),
                isMove: document.activeElement.classList.contains('bb-move'),
                tag: document.activeElement.tagName,
                after: [...document.querySelectorAll('#beatboard-board .bb-card')].map((c) => Number(c.dataset.num)),
            })""")
            check("keyboard move reorders the card",
                  focus["after"][:3] == [before[0], before[2], before[1]],
                  f"{before} -> {focus['after']}")
            check("focus stays on the move control after the re-render (reorder is repeatable)",
                  focus["inBoard"] and focus["isMove"],
                  f"focus landed on <{focus['tag']}> — a keyboard user must re-Tab through "
                  "the whole board for every slot")

            # a second Enter must move it again, not require a fresh Tab walk
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)
            twice = page.evaluate(
                "() => ({order: [...document.querySelectorAll('#beatboard-board .bb-card')].map((c) => Number(c.dataset.num)), "
                "focused: document.activeElement.classList.contains('bb-move')})")
            check("a second Enter moves it again without re-finding the button",
                  twice["order"][:4] == [before[0], before[2], before[3], before[1]] and twice["focused"],
                  json.dumps(twice))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()

