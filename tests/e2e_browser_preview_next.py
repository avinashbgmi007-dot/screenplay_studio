"""Browser walk for the six preview-next worlds, R1 rebuild (tri-pane desk edition).

Every world: full journey (shelf -> upload -> desk), the tri-pane pane-state machine
(both-open default; left/right toggles; master both-at-once), feedback lifecycle via
the review bar, cross-room bridges (Locate -> script surface with flash; Discuss ->
pre-filled quote), chips tuck/restore, growing composer, zero JS errors.

Self-hosted by default (demo craft model, throwaway projects dir); set E2E_BASE to
sweep an already-running studio.

Run:  python tests/e2e_browser_preview_next.py
Needs: pip install playwright && python -m playwright install chromium
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio
from playwright.sync_api import sync_playwright

WORLDS = ["ledger", "midnight", "screening", "quarterly", "terminal", "studio-wall"]

# per-world params: shelf opener, finding surface, desk container, its state attribute, pane/macro controls
P = {
    "ledger": dict(
        opener='.enclosure[data-open]',
        desk="#file-desk", attr="data-desk-state",
        left='[data-pane-left-toggle]', right='[data-pane-right-toggle]', master='[data-panes-master]',
        finding='.cnote[data-finding="1"]', pages=".page", nav='#tabs [data-go="{go}"]',
    ),
    "midnight": dict(
        opener='#in-tray[data-open]',
        desk="#workbench", attr="data-desk-state",
        left='[data-pane-left-toggle]', right='[data-pane-right-toggle]', master='[data-panes-master]',
        finding='.case-note[data-finding="1"]', pages=".page", nav='#pv [data-go="{go}"]',
    ),
    "screening": dict(
        opener='.canister[data-open]',
        desk="#bench-desk", attr="data-desk-state",
        left='[data-pane-left-toggle]', right='[data-pane-right-toggle]', master='[data-panes-master]',
        finding='.clipnote[data-finding="1"]', pages=".frame", nav='#pv [data-go="{go}"]',
    ),
    "quarterly": dict(
        opener='.issue-row[data-open]',
        desk="#spread", attr="data-desk-state",
        left='[data-pane-left-toggle]', right='[data-pane-right-toggle]', master='[data-panes-master]',
        finding='.cc-item[data-finding="1"]', pages=".sheet", nav='#pv [data-go="{go}"]',
    ),
    "terminal": dict(
        opener='.tape[data-open]',
        desk="#session", attr="data-desk-state",
        left='[data-pane-left-toggle]', right='[data-pane-right-toggle]', master='[data-panes-master]',
        finding='.lintline[data-finding="1"]', pages=".scenebuf", nav='#tmux .wins [data-go="{go}"]',
    ),
    "studio-wall": dict(
        opener='[data-intake]',
        desk=None, attr=None,   # free-pan wall: pane states are body classes, checked separately
        left='#hinges [data-pane-left-toggle2]', right='#hinges [data-pane-right-toggle2]',
        master='#hinges [data-panes-master2]',
        finding='.cardpin[data-finding="1"]', pages=".sheet", nav='#pv [data-jump="{go}"]',
    ),
}


def walk_world(checks, page, errors, w):
    cfg = P[w]
    tag = w
    page.goto(f"{base}/preview-next/{w}.html")

    # per-world pre-steps (Midnight's shelf only exists after the lamp is lit)
    if w == "midnight":
        page.locator("#cord").click()

    # journey: shelf first paint -> upload moment -> desk
    shelf_check = {
        "ledger": lambda: page.locator("#cover.on").count() == 1,
        "midnight": lambda: page.locator("#in-tray").is_visible(),  # needs the lamp first
        "screening": lambda: page.locator("#vault.on").count() == 1,
        "quarterly": lambda: page.locator("#backissues.on").count() == 1,
        "terminal": lambda: page.locator("#motd.on").count() == 1,
        "studio-wall": lambda: page.locator("#door .poster").is_visible(),
    }[w]()
    checks.check(f"{tag}: shelf first paint", shelf_check)
    page.locator(cfg["opener"]).first.click()
    upload_check = {
        "ledger": lambda: page.locator("#tray.on").count() == 1,
        "midnight": lambda: page.locator("#stamp-overlay.on").count() == 1,
        "screening": lambda: page.locator("#bench.on").count() == 1,
        "quarterly": lambda: page.locator("#intake.on").count() == 1,
        "terminal": lambda: page.locator("#intake.on").count() == 1,
        "studio-wall": lambda: page.locator("#intake.on").count() == 1,
    }[w]()
    checks.check(f"{tag}: upload moment shows", upload_check)
    page.locator("#submit-btn").click()
    page.wait_for_timeout(1200)
    checks.check(f"{tag}: all {4} script surfaces render", page.locator(cfg["pages"]).count() == 4)

    # tri-pane machine (Studio Wall asserts body classes; others the desk-state attribute)
    if w == "studio-wall":
        checks.check(f"{tag}: default = both regions pinned",
                     page.evaluate("!document.body.classList.contains('board-folded') && !document.body.classList.contains('sam-folded')"))
        page.locator(cfg["left"]).click()
        checks.check(f"{tag}: left folded", page.evaluate("document.body.classList.contains('board-folded')"))
        page.locator(cfg["left"]).click()
        checks.check(f"{tag}: left re-pinned", page.evaluate("!document.body.classList.contains('board-folded')"))
        page.locator(cfg["right"]).click()
        checks.check(f"{tag}: right folded", page.evaluate("document.body.classList.contains('sam-folded')"))
        page.locator(cfg["master"]).click()
        checks.check(f"{tag}: master folds both",
                     page.evaluate("document.body.classList.contains('board-folded') && document.body.classList.contains('sam-folded')"))
        page.locator(cfg["master"]).click()
        checks.check(f"{tag}: master pins both back",
                     page.evaluate("!document.body.classList.contains('board-folded') && !document.body.classList.contains('sam-folded')"))
    else:
        def state():
            return page.locator(f'{cfg["desk"]}[{cfg["attr"]}]').get_attribute(cfg["attr"])
        checks.check(f"{tag}: desk lands both-open", state() == "both-open")
        page.locator(cfg["left"]).click()
        checks.check(f"{tag}: left toggle closes left", state() in ("right-only", "none-open"))
        page.locator(cfg["left"]).click()
        checks.check(f"{tag}: left toggle reopens", state() in ("both-open", "left-only"))
        page.locator(cfg["right"]).click()
        checks.check(f"{tag}: right toggle closes right", state() in ("left-only", "none-open"))
        page.locator(cfg["master"]).click()
        checks.check(f"{tag}: master folds everything", state() == "none-open")
        page.locator(cfg["master"]).click()
        checks.check(f"{tag}: master restores", state() == "both-open")

    # bridges: locate -> script surface + flash; discuss -> pre-filled quote
    # (navigate to where this world's findings live first)
    bridge_nav = {"ledger": "feedback", "midnight": "feedback", "screening": "feedback",
                  "quarterly": "feedback", "terminal": "desk"}
    if w != "studio-wall":
        page.locator(cfg["nav"].format(go=bridge_nav[w])).click()
        page.wait_for_timeout(300)
    else:
        page.locator('#hinges [data-jump="board"]').click()
        page.wait_for_timeout(400)
    page.locator(f'{cfg["finding"]} [data-act="locate"]').first.click()
    checks.check(f"{tag}: Locate lands on the script surface", page.locator(".flash-target").count() == 1)
    if w != "studio-wall":
        page.locator(cfg["nav"].format(go=bridge_nav[w])).click()
        page.wait_for_timeout(300)
    else:
        page.locator('#hinges [data-jump="board"]').click()
        page.wait_for_timeout(400)
    page.locator(f'{cfg["finding"]} [data-act="discuss"]').first.click()
    checks.check(f"{tag}: Discuss pre-fills the quote",
                 page.locator("#in-quote").is_visible()
                 and len(page.locator("#in-quote-text").inner_text().strip()) > 20)
    page.keyboard.press("Escape")
    checks.check(f"{tag}: Esc dismisses the quote", not page.locator("#in-quote").is_visible())

    # feedback lifecycle via review bar (Terminal renders it in the session's verdict pane)
    if w == "terminal":
        page.locator('#tmux [data-go="desk"]').click()
        page.wait_for_timeout(200)
        for st in ("empty", "running", "complete"):
            page.locator(f'#pv [data-fb="{st}"]').click()
            checks.check(f"{tag}: feedback {st} renders",
                         page.locator(f'#lint-body [data-state="{st}"]').is_visible())
        page.locator('#pv [data-fb="complete"]').click()
    else:
        page.locator('#pv [data-go="feedback"]').click()
        for st in ("empty", "running", "complete"):
            page.locator(f'#pv [data-fb="{st}"]').click()
            checks.check(f"{tag}: feedback {st} renders", page.locator(f'[data-state="{st}"]').first.is_visible())
        page.locator('#pv [data-fb="complete"]').click()

    # composer grows
    page.locator(cfg["nav"].format(go="desk")).click() if w != "studio-wall" else page.locator('#hinges [data-jump="sam"]').click()
    box = page.locator("#input")
    before = box.bounding_box()["height"]
    box.fill("line one\nline two\nline three")
    checks.check(f"{tag}: composer grows multi-line",
                 box.bounding_box()["height"] > before + 10)

    assert_no_js_errors(checks, errors, f"{tag}: zero JS errors")


def walk_idea_room(checks, page, errors):
    # chips tuck/restore is uniform: every world keeps the idea textarea + .chips
    for w in WORLDS:
        page.goto(f"{base}/preview-next/{w}.html")
        opener = '#pv [data-go="idea"]'
        page.locator(opener).first.click()
        ta = page.locator("#idea-content").first
        chips = page.locator(".chips").first
        ta.fill("a bird wakes when she sings")
        checks.check(f"{w}: chips tuck away on input",
                     "tucked" in (chips.get_attribute("class") or ""))
        ta.fill("")
        checks.check(f"{w}: chips restore on clear",
                     "tucked" not in (chips.get_attribute("class") or ""))
        errors.clear()
        checks.check(f"{w}: no JS errors in idea room", len(errors) == 0, "; ".join(errors[:3]))


if __name__ == "__main__":
    checks = Checks()
    with open_studio() as base, sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(f"{base}/preview-next/index.html")
        checks.check("gallery serves with six world links",
                     page.locator("a.card[href*='.html']").count() == 6)
        for w in WORLDS:
            walk_world(checks, page, errors, w)
        walk_idea_room(checks, page, errors)
        browser.close()
    checks.finish()
