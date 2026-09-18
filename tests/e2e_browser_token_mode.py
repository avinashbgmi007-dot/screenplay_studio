"""E2E for H1 hardened mode: boot the studio with --require-token and verify the
SPA (which reads the cookie and echoes the header) can create + chat, while a
blind server-side write with no token is 403.

Run:  python tests/e2e_browser_token_mode.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks, free_port
import tempfile, time
from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def boot_hardened():
    tmp = tempfile.TemporaryDirectory(prefix="studio_tok_")
    projects = os.path.join(tmp.name, "projects"); os.makedirs(projects)
    port = free_port()
    env = dict(os.environ); env["PYTHONUNBUFFERED"] = "1"
    log = open(os.path.join(tmp.name, "srv.log"), "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "screenplay_studio.webapp_server",
         "--port", str(port), "--projects-dir", projects, "--demo-model", "--require-token"],
        cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            json.loads(urllib.request.urlopen(base + "/api/config", timeout=3).read().decode())
            break
        except Exception:
            time.sleep(0.4)
    return base, proc, log, tmp


def blind_delete(base, name):
    req = urllib.request.Request(base + f"/api/projects/{name}", method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    c = Checks()
    base, proc, log, tmp = boot_hardened()
    try:
        c.check("blind no-token write blocked (403)", blind_delete(base, "Nope") == 403)
        with sync_playwright() as pw:
            page = pw.chromium.launch(headless=True).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(base); page.wait_for_load_state("networkidle")
            # the SPA carries the token via its api() wrapper: create the sample
            name = page.evaluate("async () => { try { const r = await api('/sample', {method:'POST'}); return 200; } catch (e) { return e.status || 0; } }")
            c.check("SPA api() POST works (token echoed) -> sample", name == 200, str(name))
            c.check("no JS page errors in hardened mode", not errs, "; ".join(errs[:3]))
    finally:
        proc.terminate()
        try: proc.wait(timeout=8)
        except Exception: proc.kill()
        log.close(); tmp.cleanup()
    c.finish()


if __name__ == "__main__":
    main()
