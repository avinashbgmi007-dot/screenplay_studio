"""E2E for H1 secure-by-default: boot the studio with NO token flag and verify the
SPA (which reads the cookie and echoes the header) can create + chat, while a
blind server-side write with no token is 403. This asserts the DEFAULT posture --
previously the token required --require-token.

It also audits every WRITE the SPA can make from a real browser, not just the
ones that go through api(): the mic dictation and the pagehide idea flush were
built on raw fetch/sendBeacon, which cannot carry a header, so in hardened
posture they were a silent 403 the old api()-only test could not see.

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
import tempfile
import time
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
         "--port", str(port), "--projects-dir", projects, "--demo-model"],
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


# The mic needs a MediaRecorder that produces a non-empty blob; the fake audio
# device is not worth a launch-flag dependency when the only thing under test is
# the REQUEST (pattern borrowed from e2e_browser_ui_batch.py).
MIC_STUB = """
navigator.mediaDevices.getUserMedia = async () =>
  ({ getTracks: () => [{ stop: () => {} }] });
class FakeRecorder {
  constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm';
    FakeRecorder.instances.push(this); }
  start() { this.state = 'recording'; }
  stop() { this.state = 'inactive'; if (this.onstop) this.onstop(); }
}
FakeRecorder.instances = [];
window.MediaRecorder = FakeRecorder;
"""


def write_proofs(c, base):
    """Drive the two writes the SPA does NOT route through api(), and prove the
    server saw a capability token on each."""
    seen = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(
            viewport={"width": 1440, "height": 900},
            permissions=["microphone"]).new_page()
        page.add_init_script(MIC_STUB)
        page.on("request", lambda r: seen.append(
            (r.method, r.url, r.headers.get("x-studio-token"), r.post_data)))
        page.on("response", lambda r: seen.append(
            ("RESPONSE " + r.request.method, r.url,
             r.request.headers.get("x-studio-token"), str(r.status))))
        page.goto(base)
        page.wait_for_load_state("networkidle")

        def hit(fragment):
            return [s for s in seen if s[0].startswith("RESPONSE")
                    and fragment in s[1]]

        def request_for(fragment):
            return [s for s in seen if s[0] == "POST" and fragment in s[1]]

        # ---- B2: dictation ----
        # An idea canvas is the state where the composer and its mic are both on
        # screen (on a 1440px desk the room is parked off-canvas until opened).
        idea = page.evaluate(
            "async () => await api('/ideas', "
            "{method:'POST', body: JSON.stringify({title:'Flush Probe'})})")
        page.evaluate("async (id) => { await openIdea(id); }", idea["id"])
        page.wait_for_selector("#idea-content:visible", timeout=10000)
        mic = page.locator("div.mic-wrap:has(#idea-content) .mic-btn")
        mic.click()                      # start
        page.evaluate(
            "() => { const r = window.MediaRecorder.instances.at(-1);"
            " r.ondataavailable({ data: new Blob(['tone'], { type: 'audio/webm' }) }); }")
        mic.click()                      # stop -> recorder.onstop -> POST /api/stt
        page.wait_for_timeout(1500)
        posts = request_for("/api/stt")
        c.check("dictation really POSTed /api/stt", bool(posts),
                "no request seen" if not posts else "")
        if posts:
            c.check("dictation POST carries the capability token",
                    bool(posts[-1][2]), f"header={posts[-1][2]!r}")
        answers = hit("/api/stt")
        c.check("the server accepted the dictation POST (not 401/403)",
                bool(answers) and answers[-1][3] not in ("401", "403"),
                f"status={answers[-1][3] if answers else 'none'}")

        # ---- B3: the pagehide idea flush ----
        page.fill("#idea-content", "the brass key, untokened no more")
        page.wait_for_timeout(60)        # inside the 300ms autosave debounce
        page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
        page.wait_for_timeout(1200)
        flushed = [s for s in seen if "/content" in s[1]]
        c.check("pagehide flushed the pending idea save", bool(flushed),
                "no /content request seen")
        if flushed:
            c.check("the idea flush carries the capability token",
                    bool(flushed[-1][2]), f"header={flushed[-1][2]!r}")
            saved = page.evaluate(
                "async (id) => (await api('/ideas/' + encodeURIComponent(id))).content",
                idea["id"])
            c.check("the idea flush actually persisted the keystrokes",
                    "untokened no more" in (saved or ""), repr(saved[:60]))

        # ---- the tripwire: no NEW untokened write path in the SPA ----
        # A behaviour test can only prove the two writes it knows about. This
        # proves there are no others: the only raw fetch() allowed in app.js are
        # api() itself and the SSE turn (which sets the header by hand).
        src = open(os.path.join(REPO, "screenplay_studio", "webapp", "app.js"),
                   encoding="utf-8").read()
        raws = [ln.strip() for ln in src.splitlines()
                if "fetch(" in ln or "sendBeacon(" in ln]
        allowed = ("const resp = await fetch(API + path",
                   "const resp = await fetch(API + base")
        strays = [r for r in raws if not r.startswith(allowed)]
        c.check("no untokened write path left in the SPA", not strays,
                "; ".join(strays[:4]))
        browser.close()


def document_has_token(base, path):
    """Does GET <base><path> answer with the studio_token cookie?"""
    try:
        with urllib.request.urlopen(base + path, timeout=15) as r:
            return "studio_token=" in (r.headers.get("Set-Cookie") or "")
    except Exception:
        return False


def token_reaches_every_document(c, base):
    """The capability token is a page's LICENCE TO WRITE, so every served HTML
    document must hand it over — not just `/`. This was the hole: the labs are
    separate documents, never got the cookie, and all six design-lab worlds died
    on `missing or invalid capability token` the moment their dismiss POST was
    tried against the posture the product actually ships in."""
    for doc in ("/", "/index.html", "/design_session.html",
                "/preview-next/index.html", "/preview-next/report-first.html"):
        c.check(f"{doc} is served with the capability token",
                document_has_token(base, doc))
    # ...and only documents: a cookie on every font and stylesheet is noise.
    c.check("an asset response carries no token",
            not document_has_token(base, "/style.css"))
    # The tripwire: a page that was handed the cookie must be able to READ it —
    # an HttpOnly or path-scoped cookie would pass the header check above and
    # still leave the document unable to write. (That the write then succeeds is
    # preview_next's job: it drives a real dismissal and reload per world.)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(base + "/preview-next/report-first.html")
        page.wait_for_load_state("networkidle")
        tok = page.evaluate(
            "() => (document.cookie.match(/(?:^|;\\s*)studio_token=([^;]*)/) || [])[1] || ''")
        c.check("the lab document can read the token it was handed", bool(tok),
                f"len={len(tok)}")
        browser.close()


def main():
    c = Checks()
    base, proc, log, tmp = boot_hardened()
    try:
        c.check("blind no-token write blocked (403)", blind_delete(base, "Nope") == 403)
        token_reaches_every_document(c, base)
        write_proofs(c, base)
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
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
        log.close()
        tmp.cleanup()
    c.finish()


if __name__ == "__main__":
    main()
