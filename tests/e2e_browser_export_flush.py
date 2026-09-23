"""Browser e2e for the two behaviors that previously shipped without live proof:

A) The 📥 Report export button appears in the Feedback room once a report
   exists, points at /report/export, and actually downloads.
B) Closing the tab within the autosave debounce still persists the typed
   idea content (pagehide -> sendBeacon flush).

Self-hosted by default: boots its own demo studio on a free port with a
pre-seeded projects dir (via e2e_browser_common). For a shared sweep server,
set E2E_BASE *and* E2E_PROJECTS_DIR (the seeded project is written there).

Run:  python tests/e2e_browser_export_flush.py
Needs: pip install playwright && python -m playwright install chromium
"""
import http.server
import json
import os
import socket
import socketserver
import tempfile
import threading
import time
import urllib.request

from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, free_port, launch, start_studio

checks = Checks()


class FakeLlamaServer(socketserver.TCPServer):
    allow_reuse_addr = True


def ok(name, cond, extra=""):
    checks.ok(name, cond, extra)


def seed_project(projects_dir: str) -> None:
    """A minimal analyzed project, seeded straight onto disk (no model)."""
    d = os.path.join(projects_dir, "Seed_Export")
    os.makedirs(d, exist_ok=True)
    manifest = {
        "project_dir": d,
        "title": "Seed Export",
        "source_filename": "seed.fountain",
        "source_format": ".fountain",
        "created_at": time.time(),
        "updated_at": time.time(),
        "stages": {
            "parse": {"status": "complete"},
            "analyze": {"status": "complete"},
            "chat": {"status": "pending"},
        },
    }
    parsed = {"title": "Seed Export", "author": None, "source_format": "fountain",
              "source_filename": "seed.fountain", "scenes": [],
              "front_matter": [], "warnings": [], "parse_confidence": "high"}
    report = {"coverage": {"recommendation": "pass",
                           "logline": "A seed project for the export probe."},
              "findings": []}
    with open(os.path.join(d, "project.json"), "w") as f:
        json.dump(manifest, f)
    with open(os.path.join(d, "parsed.json"), "w") as f:
        json.dump(parsed, f)
    with open(os.path.join(d, "report.findings.json"), "w") as f:
        json.dump(report, f)

    # a damaged neighbor: torn manifest must stay on the shelf, flagged
    broken = os.path.join(projects_dir, "Broken_Show")
    os.makedirs(broken, exist_ok=True)
    with open(os.path.join(broken, "project.json"), "w") as f:
        f.write("{ torn")


def main() -> None:
    external_base = os.environ.get("E2E_BASE")
    external_projects = os.environ.get("E2E_PROJECTS_DIR")

    tmp = None
    studio = None
    try:
        # Stand-in for the writer's llama-server, used by part C below.
        # Prefer its conventional :8080; when that's taken (a REAL
        # llama-server may be running!), take a free port instead and boot
        # OUR studio pointed at it, so real_server_url lands on the fake.
        fake_port = 8080
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", 8080))
        except OSError:
            fake_port = free_port()
        finally:
            probe.close()

        class FakeLlama(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                payload = json.dumps(
                    {"object": "list", "data": [{"id": "fake-qwen"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        fake = FakeLlamaServer(("127.0.0.1", fake_port), FakeLlama)
        threading.Thread(target=fake.serve_forever, daemon=True,
                         name="fake-llama").start()

        if external_base and external_projects:
            # shared-server mode: seed into ITS projects dir, spawn nothing
            base = external_base.rstrip("/")
            seed_project(external_projects)
        else:
            tmp = tempfile.TemporaryDirectory(prefix="studio_export_flush_")
            projects_dir = os.path.join(tmp.name, "projects")
            os.makedirs(projects_dir)
            seed_project(projects_dir)
            studio = start_studio(projects_dir=projects_dir,
                                  server_url=f"http://127.0.0.1:{fake_port}")
            base = studio.base_url

        # sanity: the report endpoint serves the seeded analysis
        with urllib.request.urlopen(base + "/api/projects/Seed_Export/report",
                                    timeout=10) as r:
            body = json.loads(r.read())
        ok("seeded report served", "findings" in body)

        with sync_playwright() as pw:
            browser, page, js_errors = launch(pw, accept_downloads=True)
            page.goto(base, wait_until="networkidle")

            # ---- A2 first, on a pristine welcome desk: corrupt project ----
            page.locator("#shelf-trigger").hover()
            page.wait_for_timeout(400)
            shelf_txt = page.locator("#shelf-section").inner_text()
            ok("corrupt project flagged on shelf", "unreadable" in shelf_txt)

            page.locator(".project-item", has_text="Broken_Show").first.click()
            page.wait_for_timeout(500)
            banner_visible = page.locator("#error-banner").evaluate(
                "el => getComputedStyle(el).display !== 'none'")
            desk_open = page.locator("#project-bar").evaluate(
                "el => getComputedStyle(el).display !== 'none'")
            ok("clicking flagged project errors instead of opening",
               banner_visible and not desk_open,
               f"banner={banner_visible} desk={desk_open}")

            # ---- A. export button lives in the Feedback room ----
            # The corrupt-project banner from the check above still covers
            # the top strip for its 10s life, and the project bar idle-fades
            # after 4s — dismiss the banner and wake the chrome first (the
            # same pattern the phase-14 journey uses before top-bar clicks).
            page.locator("#error-banner-dismiss").click()
            page.mouse.move(700, 20)
            page.wait_for_timeout(300)
            page.locator("#shelf-trigger").hover()
            page.wait_for_timeout(300)
            page.locator(".project-item", has_text="Seed Export").first.click()
            page.wait_for_timeout(800)
            ok("healthy project opens normally",
               page.locator("#project-title").inner_text().strip() == "Seed Export")
            # The Feedback DRAWER room is the surface that owns the toolbar's
            # export button (loadFeedbackPanels -> renderReportPanel shows
            # it). With a project open, #room-feedback-btn routes to the
            # full-screen Feedback View instead, so the drawer room is
            # reached the same way the text-popup's "Ask consultant" action
            # reaches it (app.js openFeedbackRoom — the established evaluate
            # nudge, same as ui_fixes uses for openDock).
            page.mouse.move(700, 20)
            page.evaluate("openFeedbackRoom()")
            page.wait_for_timeout(800)

            btn = page.locator("#report-export-btn")
            ok("export button visible with report", btn.is_visible())
            href = btn.get_attribute("href") or ""
            ok("export href targets /report/export",
               href.endswith("/Seed_Export/report/export"), href)
            ok("export carries download name",
               (btn.get_attribute("download") or "") == "Seed_Export-report.md")

            try:
                with page.expect_download(timeout=5000) as dl_info:
                    btn.click()
                dl = dl_info.value
                ok("clicking downloads the report",
                   dl.suggested_filename == "Seed_Export-report.md",
                   dl.suggested_filename)
            except Exception as e:
                ok("clicking downloads the report", False, str(e)[:80])

            # ---- C. status strip honesty: demo badge, then live re-attach ----
            # The drawer opened by openFeedbackRoom overlays the strip's
            # right side, and #status-model stays display:none until the
            # strip itself is hovered — close the drawer, hover the strip
            # first (its left edge), then the item.
            page.locator("#drawer-close").click()
            page.wait_for_timeout(400)

            # ---- C2. the affordance a writer actually opens: the overflow
            # menu is where every other export lives, and with a project open
            # the Feedback drawer is NOT reachable from the desk (the room
            # button routes to the dock), so the report has to be takeable
            # away from here too.
            page.locator("#overflow-toggle").click()
            page.wait_for_timeout(400)
            rep = page.locator("#export-report")
            offered = rep.is_visible()
            ok("the overflow menu offers the report export", offered)
            rhref = (rep.get_attribute("href") or "") if offered else ""
            ok("the overflow report export targets /report/export",
               rhref.endswith("/Seed_Export/report/export"), rhref)
            if offered and rhref:
                try:
                    with page.expect_download(timeout=5000) as dl_info:
                        rep.click()
                    ok("the overflow report export downloads",
                       dl_info.value.suggested_filename == "Seed_Export-report.md",
                       dl_info.value.suggested_filename)
                except Exception as e:
                    ok("the overflow report export downloads", False, str(e)[:80])
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            dot_cls = page.locator("#connection-dot").get_attribute("class") or ""
            ok("demo mode shows amber dot, not green", "demo" in dot_cls, dot_cls)
            ok("strip names the demo, not a fake model id",
               page.locator("#status-model-label").inner_text().strip() == "demo craft model")

            page.locator("#status-strip").hover(position={"x": 10, "y": 10})
            page.wait_for_timeout(200)
            page.locator("#status-model").hover()
            page.wait_for_timeout(300)
            card_txt = page.locator("#conn-card").inner_text()
            ok("hover card tells the truth about the demo",
               "Demo (built-in stand-in)" in card_txt, card_txt[:60].replace("\n", " | "))

            # the writer's llama-server is ALREADY up (the fake above) — the
            # studio just hasn't polled since it booted:
            page.evaluate("checkConnection()")
            page.wait_for_timeout(400)

            conn_txt = page.locator("#status-conn").inner_text()
            ok("real server noticed — switch offered",
               "click to switch" in conn_txt, conn_txt)

            page.locator("#status-conn").click()
            page.wait_for_timeout(1000)

            dot_cls = page.locator("#connection-dot").get_attribute("class") or ""
            ok("after switch: green dot", "ok" in dot_cls, dot_cls)
            ok("after switch: strip shows the real model id",
               "fake-qwen" in page.locator("#status-model-label").inner_text())
            cfg_now = page.evaluate(
                "async () => (await (await fetch('/api/config')).json()).demo_model")
            ok("server-side demo flag cleared", cfg_now is False)

            fake.shutdown()
            fake.server_close()

            # ---- B. pagehide flush of pending idea autosave ----
            # wake the chrome before the top-bar click (same pattern)
            page.mouse.move(700, 20)
            page.locator("#room-cowrite-btn").click()
            # The script room auto-collapses the shelf (wireframe contract: the
            # manuscript owns the room, no permanent left nav). Reopen it from
            # its edge tab before hovering a control that lives inside it.
            shelf_tab = page.locator("#sidebar-edge-tab")
            if shelf_tab.is_visible():
                shelf_tab.click()
                page.wait_for_timeout(350)
            page.locator("#ideas-trigger").hover()
            page.wait_for_timeout(300)
            page.locator("#new-idea-btn").click()
            page.wait_for_timeout(500)

            lines = "First line of genius.\nSecond line, mid-flight.\nThird line not yet saved."
            page.locator("#idea-content").click()
            page.keyboard.type(lines, delay=5)
            idea_url = page.evaluate("state.currentIdea.id")
            page.close()  # fires pagehide while the 300ms debounce is pending

            time.sleep(1.0)  # let the beacon land
            with urllib.request.urlopen(
                    base + f"/api/ideas/{idea_url}", timeout=10) as r:
                saved = json.loads(r.read()).get("content") or ""
            ok("tab closed mid-debounce: last line persisted server-side",
               "Third line not yet saved." in saved,
               f"len={len(saved)}")

            ok("zero js errors", not js_errors, "; ".join(js_errors[:2]))
            browser.close()
    finally:
        if studio is not None:
            studio.close()
        if tmp is not None:
            tmp.cleanup()

    checks.finish()


if __name__ == "__main__":
    main()
