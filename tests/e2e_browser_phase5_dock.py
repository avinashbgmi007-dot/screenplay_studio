"""Phase 5 gate — Context Dock shell (master plan §6).

Verifies the dock's structural contract on the live app:
  * right-edge invocation opens; the affordance hides while open
  * close button + Esc both close; focus returns to the invoking element
  * lens tabs switch (Evidence / Sameer / Sushruta) with aria-selected sync
  * open/close never re-renders or scrolls the manuscript (context preserved)
  * desktop: dock is an in-flow sibling, manuscript keeps >=50% width
  * tablet (<=1199px): dock becomes a fixed right overlay; manuscript full width
  * mobile (<=767px): dock becomes a bottom sheet, full width
  * legacy surfaces: #room-drawer, #feedback-panel live on; #feedback-view and
  #problem-board are RETIRED (P0.1/P0.2) — absence asserted in the suite

Run:  python tests/e2e_browser_phase5_dock.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)

Needs: pip install playwright && python -m playwright install chromium
"""
import os

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, launch, open_studio

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed_project(base):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": ("Rain Courier.fountain", f, "text/plain")},
                          data={"title": "Rain Courier"}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("name", "Rain Courier")


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    page.locator(".project-item", has_text=name).first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def run(base):
    name = seed_project(base)
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        open_project(page, base, name)

        # --- desktop geometry: in-flow sibling, page keeps the room ---------
        mc_box = page.locator("#manuscript-container").bounding_box()
        ws_box = page.locator(".manuscript-workspace-layout").bounding_box()
        check("desktop: manuscript >=50% of workspace width",
              mc_box and ws_box and mc_box["width"] / ws_box["width"] >= 0.5,
              f"mc={mc_box and round(mc_box['width'])} ws={ws_box and round(ws_box['width'])}")

        # --- right-edge invocation -------------------------------------------
        edge = page.locator("#right-edge-affordance")
        check("right-edge affordance visible when dock closed", edge.is_visible())
        edge.click()
        check("dock opens from the right edge", page.locator("#context-dock.open").is_visible())
        check("affordance hides while dock open", not edge.is_visible())

        # --- lens switching + aria sync ---------------------------------------
        page.click("#dock-tab-sameer")
        sameer_hidden = page.locator('.dock-lens[data-lens="sameer"]').get_attribute("hidden")
        evidence_hidden = page.locator('.dock-lens[data-lens="evidence"]').get_attribute("hidden")
        check("Sameer lens becomes active",
              sameer_hidden is None and evidence_hidden is not None,
              f"sameer hidden={sameer_hidden} evidence hidden={evidence_hidden}")
        check("aria-selected syncs with the active lens",
              page.locator("#dock-tab-sameer").get_attribute("aria-selected") == "true"
              and page.locator("#dock-tab-evidence").get_attribute("aria-selected") == "false")
        page.click("#dock-tab-sushruta")
        check("Sushruta lens becomes active",
              page.locator('.dock-lens[data-lens="sushruta"]').get_attribute("hidden") is None)

        # --- context preservation: no re-render, no scroll --------------------
        page.evaluate("document.getElementById('manuscript-container').scrollTop = 300")
        scroll_before = page.evaluate("document.getElementById('manuscript-container').scrollTop")
        page.click("#dock-tab-evidence")
        page.click("#dock-close")
        check("close button closes the dock", page.locator("#context-dock.open").count() == 0)
        scroll_after = page.evaluate("document.getElementById('manuscript-container').scrollTop")
        check("manuscript scroll position preserved across open/close",
              scroll_before == scroll_after, f"{scroll_before} -> {scroll_after}")
        check("affordance returns when dock closes", edge.is_visible())

        # --- Esc dismissal + focus restoration --------------------------------
        edge.click()
        dock_tab = page.locator("#dock-tab-evidence")
        check("opening the dock focuses its active lens tab",
              dock_tab.evaluate("el => el === document.activeElement"))
        page.keyboard.press("Escape")
        check("Esc closes the dock", page.locator("#context-dock.open").count() == 0)
        check("focus returns to the invoking element on Esc-close",
              edge.evaluate("el => el === document.activeElement"))

        # --- tablet: fixed overlay, manuscript keeps full width --------------
        page.set_viewport_size({"width": 1000, "height": 800})
        page.wait_for_timeout(350)
        edge.click()
        page.wait_for_timeout(350)
        pos = page.locator("#context-dock").evaluate("el => getComputedStyle(el).position")
        dock_box = page.locator("#context-dock").bounding_box()
        mc_box_t = page.locator("#manuscript-container").bounding_box()
        ws_box_t = page.locator(".manuscript-workspace-layout").bounding_box()
        check("tablet: dock detaches to a fixed overlay", pos == "fixed", f"position={pos}")
        # a FIXED overlay anchors to the viewport's right edge, not the
        # in-flow workspace's (that sits inside the scrollbar gutter)
        vp_width = page.evaluate("window.innerWidth")
        check("tablet: dock hugs the right edge",
              dock_box and abs((dock_box["x"] + dock_box["width"]) - vp_width) <= 2,
              f"dock right={dock_box and round(dock_box['x'] + dock_box['width'])} viewport={vp_width}")
        check("tablet: manuscript keeps ~full workspace width",
              mc_box_t and ws_box_t and mc_box_t["width"] / ws_box_t["width"] >= 0.9,
              f"mc={mc_box_t and round(mc_box_t['width'])} ws={ws_box_t and round(ws_box_t['width'])}")
        page.keyboard.press("Escape")

        # --- mobile: bottom sheet ---------------------------------------------
        page.set_viewport_size({"width": 480, "height": 800})
        page.wait_for_timeout(350)
        edge.click()
        page.wait_for_timeout(350)
        dock_box_m = page.locator("#context-dock").bounding_box()
        ws_box_m = page.locator(".manuscript-workspace-layout").bounding_box()
        check("mobile: dock spans the full width as a bottom sheet",
              dock_box_m and ws_box_m and abs(dock_box_m["width"] - ws_box_m["width"]) <= 2,
              f"dock={dock_box_m and round(dock_box_m['width'])} ws={ws_box_m and round(ws_box_m['width'])}")
        # a FIXED bottom sheet anchors to the viewport bottom; the workspace's
        # own bottom sits above the in-flow room panels/composer
        vp_h = page.evaluate("window.innerHeight")
        check("mobile: sheet anchored to the bottom",
              dock_box_m and abs((dock_box_m["y"] + dock_box_m["height"]) - vp_h) <= 2,
              f"sheet bottom={dock_box_m and round(dock_box_m['y'] + dock_box_m['height'])} viewport={vp_h}")
        page.keyboard.press("Escape")
        page.set_viewport_size({"width": 1440, "height": 900})

        # --- live legacy surfaces remain; the retired two stay retired --------
        # P0.1/P0.2: #feedback-view (dormant clone) and #problem-board were
        # deliberately deleted — absence is now the contract, not presence.
        for sel, label in [("#room-drawer", "room drawer"), ("#feedback-panel", "feedback panel")]:
            check(f"legacy surface intact: {label}", page.locator(sel).count() > 0)
        for sel, label in [("#feedback-view", "feedback view clone"),
                           ("#problem-board", "problem board")]:
            check(f"retired surface stays gone: {label}", page.locator(sel).count() == 0)

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


if __name__ == "__main__":
    with open_studio() as base:
        run(base)
    checks.finish()
