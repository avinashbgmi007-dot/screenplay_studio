"""Verify the ledger-default fix: open the desk with the dock's Evidence lens and
screenshot it. Minimal on purpose — the full walk's navigation is still fragile."""
import os
import sys

sys.path.insert(0, "tests")
import playwright.sync_api as pw_sync
from e2e_browser_common import launch, open_studio

OUT = os.path.join("impl-shots", "ui_audit")
os.makedirs(OUT, exist_ok=True)

with open_studio() as base:
    with pw_sync.sync_playwright() as p:
        browser, page, errors = launch(p)
        page.goto(base, wait_until="networkidle")
        page.evaluate("async () => { await fetch('/api/sample'); }")
        page.evaluate("async () => { await fetch('/api/projects/The_Late_Hour/analyze'); }")
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(900)
        page.click("text=Open desk >> visible=true", timeout=15000)
        page.wait_for_timeout(1800)
        page.screenshot(path=os.path.join(OUT, "verify_A_desk.png"))
        page.keyboard.press("f")
        page.wait_for_timeout(1400)
        page.screenshot(path=os.path.join(OUT, "verify_B_dock.png"))
        print("JS errors:", errors[:3] if errors else "none")
        browser.close()
