"""UI evidence capture - walks every shipped surface and screenshots it.

Boots the real studio (demo model), seeds an analyzed project + an idea, then
walks the desk / feedback dock / full-screen tools / reading modes / themes /
palette / idea room, plus narrow viewports. Defensive: each step is isolated so
one failure never kills the walk; the log says which steps landed.

    python tests/_ui_capture.py            # all steps
    python tests/_ui_capture.py dock       # only steps whose name contains a term

Shots land in impl-shots/ui_audit/ (gitignored - regenerate on demand).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playwright.sync_api as pw_sync
from e2e_browser_common import launch, open_studio

OUT = os.path.join("impl-shots", "ui_audit")
ONLY = sys.argv[1:]
log = []


def shot(page, name):
    page.wait_for_timeout(450)
    page.screenshot(path=os.path.join(OUT, name + ".png"))
    log.append("ok   " + name)
    print("   ", name)


def go(page, name, fn):
    """Run one capture step; never let it kill the walk."""
    if ONLY and not any(t in name for t in ONLY):
        return
    try:
        fn()
    except Exception as e:
        log.append("FAIL " + name + ": " + type(e).__name__ + ": " + str(e)[:90])
        print("    !! " + name + ": " + type(e).__name__ + ": " + str(e)[:90])
        try:
            shot(page, name + "_FAILED")
        except Exception:
            pass


def composer(page):
    return page.locator("#composer-input, .composer textarea, .composer input, textarea").first


def open_desk(page, base):
    """Seed the sample via the API, then open it on the desk."""
    page.evaluate(
        "async () => { await fetch(String.fromCharCode(47) + "
        "String.fromCharCode(97,112,105,47,115,97,109,112,108,101)); }")
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(700)
    page.click("text=Open desk >> visible=true", timeout=15000)
    page.wait_for_timeout(1600)


def reset_home(page, base):
    """Return to the landing/desk home using the app own affordance (never
    clear storage - that hides the desk cards and strands the walk)."""
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(600)
    hb = page.locator("#home-btn >> visible=true")
    if hb.count():
        hb.first.click(timeout=4000)
        page.wait_for_timeout(900)


def ensure_desk(page):
    """Keyboard shortcuts + desk toolbar only exist on the desk; make sure we are there."""
    if page.locator("#desk-analyze-btn >> visible=true").count() == 0 and        page.locator("#overflow-toggle >> visible=true").count() == 0:
        raise RuntimeError("not on the desk — toolbar controls absent")


def tail(page, errors, log):
    print("\nJS errors:", errors[:5] if errors else "none")
    print("\n--- step log ---")
    for line in log:
        print(line)

def main():
    os.makedirs(OUT, exist_ok=True)
    with open_studio() as base:
        with pw_sync.sync_playwright() as p:
            browser, page, errors = launch(p)

            page.goto(base, wait_until="networkidle")
            go(page, "01_welcome_empty", lambda: shot(page, "01_welcome_empty"))

            def landing_unanalyzed():
                page.evaluate("async () => { await fetch(`/api/sample`); }")
                reset_home(page, base)
                shot(page, "02_landing_unanalyzed")
            go(page, "02_landing_unanalyzed", landing_unanalyzed)

            def idea_blank():
                page.click("#idea-btn", timeout=6000)
                page.wait_for_timeout(1400)
                shot(page, "03_idea_blank")
            go(page, "03_idea_blank", idea_blank)

            def idea_typed():
                ed = page.locator("#idea-canvas, #idea-editor, [contenteditable=true]").first
                ed.click(timeout=5000)
                ed.type("A locksmith who can open anything except the one door "
                        "she needs. A monsoon city.", delay=8)
                page.wait_for_timeout(1200)
                shot(page, "04_idea_typed")
            go(page, "04_idea_typed", idea_typed)

            def idea_chat():
                page.keyboard.press("c")
                page.wait_for_timeout(700)
                c = composer(page)
                c.click(timeout=5000)
                c.fill("what is the weakest part of this idea?")
                c.press("Enter")
                page.wait_for_timeout(4500)
                shot(page, "05_idea_chat_sameer")
            go(page, "05_idea_chat_sameer", idea_chat)

            # ---- fresh context: the app persists its last view, and the idea
            # room has no home button, so a new context is the clean reset.
            new_page = browser.new_context(
                viewport={"width": 1440, "height": 900}).new_page()
            new_page.on("pageerror", lambda e: errors.append(str(e)))
            new_page.on("dialog", lambda d: d.accept())
            try:
                page.context.close()
            except Exception:
                pass
            page = new_page

            def desk_no_analysis():
                reset_home(page, base)
                page.click("text=Open desk >> visible=true", timeout=15000)
                page.wait_for_timeout(1400)
                shot(page, "06_desk_no_analysis")
            go(page, "06_desk_no_analysis", desk_no_analysis)

            def analysis_progress():
                page.click("#desk-analyze-btn", timeout=6000)
                page.wait_for_timeout(1600)
                shot(page, "07_analysis_progress")
            go(page, "07_analysis_progress", analysis_progress)
            # ---- analyzed project: desk + board + dock ------------------
            def analyzed_desk():
                page.evaluate("async () => { await fetch(`/api/sample`); }")
                page.evaluate("async () => { await fetch(`/api/projects/The_Late_Hour/analyze`); }")
                reset_home(page, base)
                page.click("text=Open desk >> visible=true", timeout=15000)
                page.wait_for_timeout(1800)
                shot(page, "08_desk_board_ink")
            go(page, "08_desk_board_ink", analyzed_desk)
            go(page, "08_desk_board_ink", lambda: shot(page, "08_desk_board_ink"))

            def craft_shelf():
                ensure_desk(page)
                page.keyboard.press("a")
                page.wait_for_timeout(900)
                shot(page, "09_craft_shelf")
            go(page, "09_craft_shelf", craft_shelf)

            def dock_evidence():
                page.keyboard.press("f")
                page.wait_for_timeout(1200)
                shot(page, "10_dock_evidence")
            go(page, "10_dock_evidence", dock_evidence)

            def dock_filter():
                page.click("text=Medium >> visible=true", timeout=8000)
                page.wait_for_timeout(900)
                shot(page, "11_dock_filter_medium")
            go(page, "11_dock_filter_medium", dock_filter)

            def dock_sameer():
                page.click("text=Sameer >> visible=true", timeout=8000)
                page.wait_for_timeout(900)
                shot(page, "12_dock_sameer")
            go(page, "12_dock_sameer", dock_sameer)

            def dock_sushruta():
                page.click("text=Sushruta >> visible=true", timeout=8000)
                page.wait_for_timeout(700)
                c = composer(page)
                c.click(timeout=5000)
                c.fill("why was the dialogue flagged?")
                c.press("Enter")
                page.wait_for_timeout(5000)
                shot(page, "13_dock_sushruta_turn")
            go(page, "13_dock_sushruta_turn", dock_sushruta)

            def dock_stash():
                page.click("text=Stash >> visible=true", timeout=8000)
                page.wait_for_timeout(900)
                shot(page, "14_dock_stash_notes")
            go(page, "14_dock_stash_notes", dock_stash)

            def fix_loop():
                page.keyboard.press("f")
                page.wait_for_timeout(900)
                page.click("text=fix loop >> visible=true", timeout=8000)
                page.wait_for_timeout(900)
                shot(page, "15_fix_loop")
            go(page, "15_fix_loop", fix_loop)
            # ---- full-screen tools --------------------------------------
            def beat_board():
                ensure_desk(page)
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.keyboard.press("b")
                page.wait_for_timeout(1200)
                shot(page, "16_beat_board")
            go(page, "16_beat_board", beat_board)

            def revision_view():
                ensure_desk(page)
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.keyboard.press("v")
                page.wait_for_timeout(1200)
                shot(page, "17_revision_view")
            go(page, "17_revision_view", revision_view)

            def compare_view():
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.keyboard.press("d")
                page.wait_for_timeout(1200)
                shot(page, "18_compare")
            go(page, "18_compare", compare_view)

            # ---- reading modes ------------------------------------------
            def focus_mode():
                ensure_desk(page)
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.click("#focus-btn", timeout=5000)
                page.wait_for_timeout(1000)
                shot(page, "19_focus_mode")
            go(page, "19_focus_mode", focus_mode)

            def reader_mode():
                ensure_desk(page)
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.click("#overflow-toggle", timeout=5000)
                page.wait_for_timeout(400)
                page.click("#reader-btn", timeout=5000)
                page.wait_for_timeout(1100)
                shot(page, "20_reader")
            go(page, "20_reader", reader_mode)

            def river_read():
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.click("#overflow-toggle", timeout=5000)
                page.wait_for_timeout(400)
                page.click("#flow-btn", timeout=5000)
                page.wait_for_timeout(1200)
                shot(page, "21_river_read")
            go(page, "21_river_read", river_read)

            def spotlight():
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.keyboard.press("z")
                page.wait_for_timeout(1000)
                shot(page, "22_spotlight")
            go(page, "22_spotlight", spotlight)
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            # ---- palette + settings -------------------------------------
            def palette():
                page.keyboard.press("Control+k")
                page.wait_for_timeout(800)
                shot(page, "23_palette")
            go(page, "23_palette", palette)
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            def settings():
                page.click("#settings-btn", timeout=5000)
                page.wait_for_timeout(1000)
                shot(page, "24_settings")
            go(page, "24_settings", settings)
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            # ---- dawn (light register) ----------------------------------
            def dawn():
                page.click("#dawn-btn", timeout=5000)
                page.wait_for_timeout(1100)
                shot(page, "25_dawn")
            go(page, "25_dawn", dawn)

            def dawn_feedback():
                page.keyboard.press("f")
                page.wait_for_timeout(1100)
                shot(page, "26_dawn_feedback")
            go(page, "26_dawn_feedback", dawn_feedback)

            def back_to_night():
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                page.click("#dawn-btn", timeout=5000)
                page.wait_for_timeout(800)
            go(page, "27_back_to_night", back_to_night)

            # ---- narrow viewport (responsive) ---------------------------
            def narrow():
                page.set_viewport_size({"width": 900, "height": 800})
                page.wait_for_timeout(1000)
                shot(page, "28_narrow_900")
            go(page, "28_narrow_900", narrow)

            def narrow_feedback():
                page.keyboard.press("f")
                page.wait_for_timeout(1000)
                shot(page, "29_narrow_feedback")
            go(page, "29_narrow_feedback", narrow_feedback)

            def narrow_600():
                page.set_viewport_size({"width": 600, "height": 800})
                page.wait_for_timeout(1000)
                shot(page, "30_narrow_600")
                page.set_viewport_size({"width": 1440, "height": 900})
                page.wait_for_timeout(600)
            go(page, "30_narrow_600", narrow_600)

            tail(page, errors, log)
            browser.close()


if __name__ == "__main__":
    main()
