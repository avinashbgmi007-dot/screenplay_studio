"""One-off UI evidence capture for the Feedback Room brainstorm.

Boots the real studio (demo model), seeds + analyzes the sample project, and
screenshots the surfaces the writer actually sees, so the redesign is grounded
in what ships today — not the spec. Run once, then delete.
"""
import os
import sys
import time

sys.path.insert(0, "tests")
import playwright.sync_api as pw_sync
from e2e_browser_common import launch, open_studio

OUT = os.path.join("impl-shots", "ui_audit")
os.makedirs(OUT, exist_ok=True)


def shot(page, name):
    page.wait_for_timeout(400)
    path = os.path.join(OUT, name + ".png")
    page.screenshot(path=path, full_page=False)
    print("  ", path)


def main():
    with open_studio() as base:
        with pw_sync.sync_playwright() as p:
            browser, page, errors = launch(p)

            page.goto(base, wait_until="networkidle")
            shot(page, "01_welcome")

            # seed + analyze the sample (server-side, trusted local tool)
            page.evaluate(
                "async () => { await fetch('/api/sample', {method:'POST'});"
                " await fetch('/api/projects/The_Late_Hour/analyze', {method:'POST'}); return 1; }")
            page.goto(base, wait_until="networkidle")
            page.wait_for_timeout(800)

            # open the project via the real affordance on the desk card
            page.click("text=Open desk", timeout=8000)
            page.wait_for_timeout(1500)
            shot(page, "03_desk_script")

            # feedback room (Evidence lens) via the f shortcut
            page.keyboard.press("f")
            page.wait_for_timeout(1000)
            shot(page, "05_feedback_room")

            # power-user path: the keyboard fix loop
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            shot(page, "06_desk_back")

            # idea room: create an idea, land on its canvas
            page.evaluate(
                "async () => { const r = await fetch('/api/ideas', {method:'POST',"
                " headers:{'Content-Type':'application/json'}, body:'{\"title\":\"Idea audit\"}'});"
                " const j = await r.json(); return j.id; }")
            page.wait_for_timeout(800)
            shot(page, "07_idea_canvas")

            print("JS errors:", errors[:5] if errors else "none")
            browser.close()


if __name__ == "__main__":
    main()
