"""Browser e2e for the two behaviors that previously shipped without live proof:

A) The 📥 Report export button appears in the Feedback room once a report
   exists, points at /report/export, and actually downloads.
B) Closing the tab within the autosave debounce still persists the typed
   idea content (pagehide -> sendBeacon flush).

Self-hosted by default (spawns its own server on :8577). For a shared
sweep server, set E2E_BASE *and* E2E_PROJECTS_DIR (the seeded project is
written there).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

PORT = int(os.environ.get("E2E_PORT", "8577"))
BASE = f"http://127.0.0.1:{PORT}"

results = []


def ok(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{extra}]" if extra else ""))


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

    proc = None
    if external_base and external_projects:
        # shared-server mode: seed into ITS projects dir, spawn nothing
        global BASE
        BASE = external_base.rstrip("/")
        seed_project(external_projects)
    else:
        workdir = "/tmp/e2e_export_flush"
        subprocess.run(["rm", "-rf", workdir], check=True)
        os.makedirs(workdir + "/projects", exist_ok=True)
        seed_project(workdir + "/projects")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.getcwd()
        proc = subprocess.Popen(
            [sys.executable, "-m", "screenplay_studio.webapp_server",
             "--port", str(PORT), "--projects-dir", "./projects", "--demo-model"],
            cwd=workdir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/api/config", timeout=1)
                break
            except Exception:
                time.sleep(0.25)

        # sanity: the report endpoint serves the seeded analysis
        with urllib.request.urlopen(BASE + "/api/projects/Seed_Export/report",
                                    timeout=10) as r:
            body = json.loads(r.read())
        ok("seeded report served", "findings" in body)

        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 1440, "height": 900},
                                accept_downloads=True)
            page = ctx.new_page()
            js_errors = []
            page.on("pageerror", lambda e: js_errors.append(str(e)))
            page.goto(BASE, wait_until="networkidle")

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
            page.locator("#shelf-trigger").hover()
            page.wait_for_timeout(300)
            page.locator(".project-item", has_text="Seed Export").first.click()
            page.wait_for_timeout(800)
            ok("healthy project opens normally",
               page.locator("#project-title").inner_text().strip() == "Seed Export")
            page.locator("#room-feedback-btn").click()
            page.wait_for_timeout(600)

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

            # ---- B. pagehide flush of pending idea autosave ----
            page.locator("#room-cowrite-btn").click()
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
                    BASE + f"/api/ideas/{idea_url}", timeout=10) as r:
                saved = json.loads(r.read()).get("content") or ""
            ok("tab closed mid-debounce: last line persisted server-side",
               "Third line not yet saved." in saved,
               f"len={len(saved)}")

            ok("zero js errors", not js_errors, "; ".join(js_errors[:2]))
            b.close()
    finally:
        if proc is not None:
            proc.terminate()

    failed = [n for n, c in results if not c]
    print(f"\n=== {len(results) - len(failed)} passed, {len(failed)} failed ===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
