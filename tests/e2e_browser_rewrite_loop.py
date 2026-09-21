"""P1.4 — the select-to-rewrite loop: a real inline diff with Apply / Stash / Reject.

What the item asked for: "his proposed passage edits render as inline diffs with
Apply/Stash/Reject, writing into working.json through the existing revision
machinery — converts 'want me to sketch a version?' into the product's core loop."

What was actually there: the proposal rendered as the WHOLE old line struck
through above the WHOLE new line in green, with a checkbox and one bulk "Apply
changes". That is a diff the writer has to read twice to find the two words that
moved, and there was no way to keep a proposal without taking it.

Two layers are asserted here, and they need different tools:

  * The DIFF ALGORITHM is a pure function, so it is tested directly in the page
    with crafted pairs and exact expected runs. The demo model's rewrite happens
    to share no words with the line it replaces, so driving the algorithm only
    through a real proposal could never exercise a partial mark — the case the
    whole feature exists for.
  * The LOOP is asserted end to end through the real modal: Stash lands in the
    existing stash store, Reject writes nothing, Apply writes the working copy.

Run:  python tests/e2e_browser_rewrite_loop.py
"""
import os
import sys

import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks, launch, seen_visible, start_studio

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")
checks = Checks()
check = checks.ok


# (old, new, expected runs) — exact, because the algorithm is deterministic and
# "roughly the right marks" is not a thing a writer can trust.
DIFF_CASES = [
    ("a b c d", "a b x d", [["same", "a b"], ["del", "c"], ["ins", "x"], ["same", "d"]]),
    ("one two three", "one three", [["same", "one"], ["del", "two"], ["same", "three"]]),
    ("the line lands quiet", "the line lands quiet",
     [["same", "the line lands quiet"]]),
    ("old only", "", [["del", "old only"]]),
    ("", "new only", [["ins", "new only"]]),
    ("cut the explainer line entirely", "cut the explainer",
     [["same", "cut the explainer"], ["del", "line entirely"]]),
]


def seed_and_analyze(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    name = r.json().get("project") or r.json().get("name") or title
    r2 = requests.post(f"{base}/api/projects/{name}/analyze",
                       json={"force": True}, timeout=300)
    assert r2.status_code in (200, 201), r2.text[:400]
    return name


def run(base):
    name = seed_and_analyze(base, "Rewrite Loop")
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        page.goto(base)
        page.wait_for_load_state("networkidle")

        # ---------------- 1. the diff algorithm, directly ----------------
        # `typeof` guards, so a missing wordDiff is a GRADED failure with a
        # readable detail rather than an uncaught evaluate error that aborts the
        # whole suite. That matters for the mutation check: a crash is RED but
        # tells you nothing about which assertions the fix carries.
        def _diff(old, new):
            got = page.evaluate(
                "([o, n]) => (typeof wordDiff === 'function')"
                " ? wordDiff(o, n).map(r => [r.kind, r.text]) : '__MISSING__'",
                [old, new])
            return got

        for old, new, expected in DIFF_CASES:
            got = _diff(old, new)
            check(f"diff: {old[:22]!r} -> {new[:22]!r} marks exactly the change",
                  got == expected, f"got={got} want={expected}")

        # The LCS invariant, on every case: replaying the runs must rebuild both
        # sides. This is what makes the marks trustworthy rather than decorative.
        for old, new, _ in DIFF_CASES:
            ok = page.evaluate(
                """([o, n]) => {
                     if (typeof wordDiff !== 'function') return false;
                     const runs = wordDiff(o, n) || [];
                     const pick = (kinds) => runs.filter(r => kinds.includes(r.kind))
                                                 .map(r => r.text).join(' ');
                     const norm = (s) => s.trim().replace(/\\s+/g, ' ');
                     return norm(pick(['same', 'ins'])) === norm(n) &&
                            norm(pick(['same', 'del'])) === norm(o);
                   }""", [old, new])
            check(f"diff: runs rebuild both sides ({old[:18]!r})", ok)

        # A pair too long to mark word by word must say so, not allocate a table
        # nobody reads — renderInlineDiff falls back to the whole-line form.
        huge = " ".join(f"w{i}" for i in range(500))
        check("diff: an over-long pair refuses to diff",
              page.evaluate(
                  "(s) => (typeof wordDiff === 'function') ? wordDiff(s, s + ' x') === null"
                  " : '__MISSING__'", huge) is True)
        check("diff: the over-long pair falls back to the whole-line form",
              page.evaluate(
                  "(rep) => (typeof renderInlineDiff === 'function')"
                  " ? renderInlineDiff(rep).className : '__MISSING__'",
                  {"old": huge, "new": huge + " x"}) == "rewrite-candidate-pair")
        check("diff: a normal pair renders as a word diff",
              page.evaluate(
                  "(rep) => (typeof renderInlineDiff === 'function')"
                  " ? renderInlineDiff(rep).className : '__MISSING__'",
                  {"old": "a b c", "new": "a b d"}) == "rewrite-diff")

        # ---------------- 2. the loop, through the real modal ----------------
        # Wrapped, so a missing element is a graded failure rather than a
        # 30-second Playwright timeout that aborts the suite mid-run.
        try:
            _run_loop(page, base, name)
        except Exception as e:  # noqa: BLE001 — a probe reports, it does not crash
            check("loop: the rewrite loop ran end to end", False, f"{type(e).__name__}: {e}"[:160])

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


def _run_loop(page, base, name):
    page.evaluate("(n) => openProject(n)", name)
    page.wait_for_timeout(900)
    page.evaluate("() => openScriptView()")
    page.wait_for_timeout(900)

    note = page.locator("#manuscript-container .finding-note").first
    note.locator("button", has_text="Rewrite").click()
    # "the rewrite modal OPENS FROM THE FINDING CARD" — assert it opened AND is
    # armed (its generate control exists), so an empty modal shell cannot pass.
    # The throwing wait proved only visibility; `check(name, True)` proved
    # nothing, and a failure was a crash rather than a named check.
    modal_ok = seen_visible(page, "#rewrite-modal", timeout=8000)
    # is_visible, not count()>0: PRESENCE is satisfied by a hidden button, so an
    # empty modal shell would still pass. This is the half of the claim the
    # throwing wait never covered.
    armed = page.locator("#rewrite-generate").is_visible()
    check("loop: the rewrite modal opens from the finding card", modal_ok and armed,
          f"modalVisible={modal_ok} generateVisible={armed}")

    page.locator("#rewrite-generate").click()
    page.wait_for_selector("#rewrite-candidates .rewrite-candidate", timeout=30000)
    cand = page.locator("#rewrite-candidates .rewrite-candidate")
    check("loop: the model proposes a targeted change", cand.count() > 0,
          f"candidates={cand.count()}")

    scene_title = page.locator("#rewrite-scene-title").inner_text()
    scene_number = int("".join(ch for ch in scene_title if ch.isdigit()) or 0)

    # The proposal is rendered as a diff, not as two whole lines.
    check("loop: the proposal renders as a word-level diff",
          page.locator("#rewrite-candidates .rewrite-diff").count() > 0)
    check("loop: the old whole-line strikethrough is gone",
          page.locator("#rewrite-candidates .rewrite-old").count() == 0)

    # Per-proposal actions exist, and the bulk contract the phase14 journey
    # asserts on is untouched.
    check("loop: each proposal offers Apply / Stash / Reject",
          cand.first.locator(".rewrite-candidate-actions .rc-apply").count() == 1
          and cand.first.locator(".rewrite-candidate-actions .rc-stash").count() == 1
          and cand.first.locator(".rewrite-candidate-actions .rc-reject").count() == 1)
    check("loop: the bulk Apply button survives",
          page.locator("#rewrite-apply").is_visible())

    # ---- STASH: parks the proposal in the existing stash store ----
    before = requests.get(f"{base}/api/projects/{name}/stash", timeout=30).json()
    n_before = len(before.get("stash") or [])
    page.locator("#rewrite-candidates .rewrite-candidate").first \
        .locator(".rc-stash").click()
    page.wait_for_timeout(1200)
    after = requests.get(f"{base}/api/projects/{name}/stash", timeout=30).json()
    stash = after.get("stash") or []
    check("stash: the proposal lands in the project's stash",
          len(stash) == n_before + 1, f"{n_before} -> {len(stash)}")
    if stash:
        check("stash: it carries the scene it came from",
              stash[0].get("scene_number") == scene_number,
              f"entry={stash[0].get('scene_number')} scene={scene_number}")
        check("stash: it carries the proposed wording",
              "[demo]" in (stash[0].get("text") or ""),
              stash[0].get("text", "")[:60])
    check("stash: the row is marked stashed, not removed",
          page.locator("#rewrite-candidates .rewrite-candidate-stashed").count() == 1)
    # Parking is not deciding: the writer stashed it in order to decide
    # later, so Apply and Reject must still be there. (Getting this backwards
    # made Stash a one-way door, which the first run of this suite caught.)
    stashed_row = page.locator("#rewrite-candidates .rewrite-candidate-stashed").first
    check("stash: Apply and Reject survive the stash",
          stashed_row.locator(".rc-apply").count() == 1
          and stashed_row.locator(".rc-reject").count() == 1)
    check("stash: the Stash button itself is spent",
          stashed_row.locator(".rc-stash").is_disabled())
    check("stash: stashing writes nothing to the script",
          page.locator("#manuscript-container", has_text="[demo] The line lands quieter").count() == 0)

    # ---- REJECT: drops the proposal, writes nothing ----
    n_rows = page.locator("#rewrite-candidates .rewrite-candidate").count()
    page.locator("#rewrite-candidates .rewrite-candidate").first \
        .locator(".rc-reject").click()
    page.wait_for_timeout(500)
    check("reject: the proposal leaves the list",
          page.locator("#rewrite-candidates .rewrite-candidate").count() == n_rows - 1)
    check("reject: rejecting everything hides the bulk Apply",
          page.locator("#rewrite-apply").is_hidden())
    check("reject: the status line says nothing was changed",
          "nothing was changed" in page.locator("#rewrite-status").inner_text())
    check("reject: rejecting writes nothing to the script",
          page.locator("#manuscript-container", has_text="[demo] The line lands quieter").count() == 0)

    # ---- APPLY: writes the working copy ----
    page.locator("#rewrite-generate").click()
    page.wait_for_selector("#rewrite-candidates .rewrite-candidate", timeout=30000)
    page.locator("#rewrite-candidates .rewrite-candidate").first \
        .locator(".rc-apply").click()
    page.wait_for_timeout(2500)
    check("apply: the proposed line reaches the manuscript",
          page.locator("#manuscript-container", has_text="[demo] The line lands quieter").count() > 0)
    check("apply: the row is marked applied",
          page.locator("#rewrite-candidates .rewrite-candidate-applied").count() == 1)

    # undo still unwinds it — the loop rides the EXISTING revision machinery
    page.keyboard.press("Control+z")
    page.wait_for_timeout(1800)
    gone = page.evaluate(
        "() => ![...document.querySelectorAll('#manuscript-container [class^=el-]')]"
        ".some(el => el.textContent.includes('[demo] The line lands quieter'))")
    check("apply: Ctrl+Z unwinds it through the existing undo stack", gone)


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
