"""Browser walk for the Design Lab (v5): six IA prototypes on REAL data.

Every world: boots the studio, seeds The_Late_Hour from the bundled sample
and runs a REAL demo-model analysis, then walks that world's IA landing +
the shared tri-pane contract (script center, feedback LEFT, Sameer RIGHT,
independent toggles + both-at-once master), real chat round-trip, real
dismiss persistence, growing composer, zero JS errors.

Self-hosted by default (demo craft model, throwaway projects dir); set
E2E_BASE to sweep an already-running studio.

Run:  python tests/e2e_browser_preview_next.py
Needs: pip install playwright && python -m playwright install chromium
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import (Checks, assert_no_js_errors, launch, open_studio,
                                studio_headers)
from playwright.sync_api import sync_playwright

WORLDS = ["report-first", "chat-first", "canvas-first", "stream-first", "inspector-first", "command-first"]


def seed_project(base):
    """Upload the bundled sample and run a REAL demo-model analysis, so every
    world loads live data on a fresh throwaway projects dir."""
    def post(path, body=None, timeout=30):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body or {}).encode(),
            headers={"Content-Type": "application/json", **studio_headers(base)},
            method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())

    def get(path, timeout=30):
        return json.loads(urllib.request.urlopen(base + path, timeout=timeout).read().decode())

    post("/api/sample")
    for _ in range(10):
        shelf = get("/api/preview/projects")
        if any(p["name"] == "The_Late_Hour" for p in shelf["projects"]):
            break
        time.sleep(0.5)
    post("/api/projects/The_Late_Hour/analyze")
    # the real signal: the shelf reports findings present
    for _ in range(360):
        try:
            shelf = get("/api/preview/projects")
            p = next((p for p in shelf["projects"] if p["name"] == "The_Late_Hour"), None)
            if p and p["has_findings"]:
                return "complete"
        except Exception:
            pass
        time.sleep(0.5)
    return "timeout"


def walk_world(checks, page, errors, base, w):
    tag = w
    page.goto(f"{base}/preview-next/{w}.html")
    page.wait_for_timeout(1800)

    # every world: live real data + project switcher + the IA landing view
    checks.check(f"{tag}: live data loaded", "live" in page.locator("[data-lab-live]").inner_text())
    checks.check(f"{tag}: real project title", "Late Hour" in page.locator("[data-lab-title]").inner_text())
    checks.check(f"{tag}: project switcher has shelf",
                 page.locator("[data-lab-switcher] option").count() >= 1)
    checks.check(f"{tag}: IA landing view renders",
                 page.locator("[data-ia-landing]").first.is_visible())

    # findings surface (where this world's IA puts them)
    checks.check(f"{tag}: real findings render",
                 page.locator("[data-finding]").count() >= 1)

    # the shared tri-pane desk: reveal it if the world's IA hides it on landing
    desk = page.locator("[data-desk]")
    if not desk.is_visible():
        # VISIBLE first: a world may declare several openers (canvas-first puts
        # data-open-desk on its scene cards too), and a hidden one must never be
        # the click target. Bounded and guarded so an unwired opener reports as
        # a failed check rather than a click timeout that aborts the whole run.
        try:
            page.locator("[data-open-desk]").locator("visible=true").first.click(timeout=5000)
            page.wait_for_timeout(400)
        except Exception:
            pass
    desk_open = desk.is_visible()
    checks.check(f"{tag}: desk reachable + both-open",
                 desk_open
                 and page.locator('[data-desk][data-desk-state="both-open"]').count() == 1)
    if not desk_open:
        # Everything below lives inside the desk. Say so once, by name, and move
        # on to the next world: aborting here is what used to hide five worlds
        # behind the first broken one.
        checks.check(f"{tag}: rest of the world exercised", False,
                     "the desk never opened — pane toggles, composer and findings skipped")
        return
    checks.check(f"{tag}: real script pages in center",
                 page.locator("[data-scene]").count() >= 3)

    # pane toggles + master
    page.locator("[data-pane-left-toggle]").first.click()
    checks.check(f"{tag}: left toggle", page.locator('[data-desk][data-desk-state="right-only"]').count() == 1)
    page.locator("[data-pane-left-toggle]").first.click()
    checks.check(f"{tag}: left reopens", page.locator('[data-desk][data-desk-state="both-open"]').count() == 1)
    page.locator("[data-panes-master]").first.click()
    checks.check(f"{tag}: master folds both", page.locator('[data-desk][data-desk-state="none-open"]').count() == 1)
    page.locator("[data-panes-master]").first.click()
    checks.check(f"{tag}: master restores", page.locator('[data-desk][data-desk-state="both-open"]').count() == 1)

    # REAL Sameer turn through the preview endpoint (demo model).
    # VISIBLE: chat-first ships its own composer inside [data-ia-landing], which
    # showDesk() hides — so there are two, and `.first` picked the hidden one,
    # giving bounding_box() == None.
    box = page.locator("[data-lab-composer-input]").locator("visible=true").first
    before = box.bounding_box()["height"]
    box.fill("In one sentence: what is this script's biggest problem?")
    page.locator("[data-lab-composer-send]").locator("visible=true").first.click()
    # #lab-thread is the DESK's thread (injected by _lab.js). The old selector
    # led with `#desk-thread`, which exists nowhere, so it fell through to a bare
    # `[data-lab-thread] .lab-sam` — matching the world's own (hidden) landing
    # thread first and waiting on it forever.
    try:
        page.wait_for_selector("#lab-thread .lab-sam", timeout=45000)
        replied = True
    except Exception:
        replied = False
    checks.check(f"{tag}: composer grows", box.bounding_box()["height"] > before + 5)
    thread_text = page.locator("#lab-thread").inner_text()
    checks.check(f"{tag}: REAL Sameer reply arrived",
                 replied and len(thread_text.strip()) > 40
                 and "couldn't be reached" not in thread_text[-300:])

    # real dismiss persistence (reload the page — dismissal survives)
    dismiss_btn = page.locator('[data-verb="dismiss"]').locator("visible=true").first
    if dismiss_btn.count():
        dismiss_btn.click()
        page.wait_for_timeout(800)
        page.reload()
        page.wait_for_timeout(1800)
        # A reload restores the world's LANDING state, and every world mounts the
        # desk folded (mountDesk(true)), so the desk has to be revealed again
        # before its findings surface — where the restore verb lives — is
        # visible. report-first only ever passed this because its landing IS the
        # report, so the verb happened to be on screen already.
        if not page.locator("[data-desk]").is_visible():
            page.locator("[data-open-desk]").locator("visible=true").first.click()
            page.wait_for_timeout(500)
        restore = page.locator('[data-verb="undismiss"]').locator("visible=true").first
        checks.check(f"{tag}: dismiss persists across reload", restore.count() >= 1)
        if restore.count():
            restore.click()
            page.wait_for_timeout(800)

    assert_no_js_errors(checks, errors, f"{tag}: zero JS errors")


if __name__ == "__main__":
    checks = Checks()
    with open_studio() as base, sync_playwright() as pw:
        browser, page, errors = launch(pw)
        stage = seed_project(base)
        checks.check("seed: real analysis completed on The_Late_Hour", stage == "complete",
                     f"stage={stage}")
        page.goto(f"{base}/preview-next/index.html")
        checks.check("gallery: design lab door with six IAs",
                     page.locator("a.card[href*='.html']").count() == 6)
        for w in WORLDS:
            walk_world(checks, page, errors, base, w)
        browser.close()
    checks.finish()
