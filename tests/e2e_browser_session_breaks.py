"""e2e_browser_session_breaks.py — two session-break survivals (P2/P4, audit W1/V3).

The studio mints its capability token PER PROCESS. A restart therefore means:
same URL, new token, every already-open tab's cookie is dead. Two contracts
guard the writer there, and no other suite exercised either end to end:

  * **Leg 1 — the studio is killed and restarted under a live tab.** The page
    never reloads; the first dead write must recover silently (re-fetch `/`
    with cache:no-store to re-mint the cookie, retry once if the licence
    actually moved) and land on the NEW server. And when recovery is truly
    impossible — server killed and NOT restarted — the writer must see a
    readable sentence, never the guard's internal "missing or invalid
    capability token" string and never a raw TypeError.
  * **Leg 2 — a destructive confirm() answered "Cancel".** `launch()`
    auto-accepts every dialog, so no existing suite ever exercises the decline
    path. Here the dialog is DISMISSED (the page's dialog handler is replaced,
    `launch()` itself untouched) and the store must come back byte-identical;
    then the SAME action accepted must really destroy the object — the
    can-fail witness that the decline test measures something.

This suite KILLS and RESTARTS its own server, so it always boots privately via
start_studio() (never open_studio/E2E_BASE — it must not touch a shared
studio). The relaunch mirrors start_studio's child exactly: same --port,
same --projects-dir, --demo-model + SCREENPLAY_STUDIO_DEMO_MODEL=1, output to a
drained LOG FILE (never an unread PIPE, see e2e_browser_common.py:424-427),
readiness polled on /api/config. Everything lives under a throwaway temp dir.

Controlled reversion (Leg 1 red witness): deleting the
`if (resp.status === 403 && !_retry)` block from _apiOnce in app.js turns
L1b/L1c/L1d red — the write never lands, the page's cookie stays dead, and the
guard's internal "missing or invalid capability token" string surfaces to the
writer verbatim.

Run:  python tests/e2e_browser_session_breaks.py
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
import e2e_browser_common as common  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    REPO_ROOT, Checks, assert_no_js_errors, clicked, filled, launch,
    seen_visible, start_studio, studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")
PROJ = "SessA"

RESTART_SENTENCE = "The studio restarted since this page was opened."
INTERNAL_TOKEN_STRING = "missing or invalid capability token"


# ---------- helpers -----------------------------------------------------------

def upload(base, title, path):
    with open(path, "rb") as f:
        r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["project"]


def notes_via_http(base, name):
    """GET the notes store over HTTP (reads need no token, but send it anyway)."""
    r = requests.get(f"{base}/api/projects/{name}/notes",
                     headers=studio_headers(base), timeout=30)
    assert r.status_code == 200, r.text
    return [n.get("text", "") for n in r.json()["notes"]]


def notes_store_bytes(projects_dir, name):
    with open(os.path.join(projects_dir, name, "notes.json"), "rb") as f:
        return f.read()


def page_cookie_token(page):
    m = re.search(r"studio_token=([^;]+)", page.evaluate("() => document.cookie"))
    return urllib.parse.unquote(m.group(1)) if m else None


def refetch_token(base):
    """The token the CURRENT process mints — drop the harness cache first, or
    studio_headers would keep replaying the dead one."""
    common._TOKEN_CACHE.pop(base.rstrip("/"), None)
    return common.studio_token(base)


def kill_studio(proc):
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=15)
    except Exception:
        proc.kill()
        proc.wait(timeout=15)


def relaunch_studio(port, projects_dir, timeout=60):
    """Restart the child on the SAME port + SAME projects dir (new process =>
    new token: that is the whole point). Mirrors start_studio's boot exactly;
    a bind failure (old socket in TIME_WAIT) is retried until the deadline."""
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ)
    env["SCREENPLAY_STUDIO_DEMO_MODEL"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [sys.executable, "-m", "screenplay_studio.webapp_server",
           "--port", str(port), "--projects-dir", projects_dir, "--demo-model"]
    # drained sink, never a PIPE — see e2e_browser_common.py:424-427
    log_path = os.path.join(os.path.dirname(os.path.abspath(projects_dir)),
                            "_studio_relaunch.log")
    log_file = open(log_path, "ab")
    deadline = time.time() + timeout
    last = "never polled"
    while time.time() < deadline:
        proc = subprocess.Popen(cmd, cwd=REPO_ROOT, env=env,
                                stdout=log_file, stderr=subprocess.STDOUT)
        while time.time() < deadline:
            if proc.poll() is not None:
                last = f"child exited early ({proc.returncode})"
                break  # likely the port is still held: retry below
            try:
                cfg = json.loads(urllib.request.urlopen(base + "/api/config",
                                                        timeout=3).read().decode())
                if cfg.get("demo_model"):
                    return proc, log_file
                last = "up but demo_model inactive"
            except Exception as e:
                last = str(e)
            time.sleep(0.4)
        time.sleep(0.6)
    log_file.close()
    raise RuntimeError(f"relaunch never became ready at {base}: {last}")


def wait_dead(base, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/api/config", timeout=2).read()
        except Exception:
            return True
        time.sleep(0.3)
    return False


def wait_note_stored(base, name, text, timeout=15):
    """Bounded poll: the note with `text` is visible to a fresh HTTP read."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if any(text in t for t in notes_via_http(base, name)):
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def ui_add_note(page, btn_index, text):
    """The cheapest real UI write: scene-head "✎ note" -> textarea -> Enter,
    which POSTs /notes through api(). False if the control was unreachable."""
    btn = page.locator("button.note-add").nth(btn_index)
    if not seen_visible(btn, timeout=8000):
        return False
    if not clicked(btn):
        return False
    editor = page.locator("textarea.note-editor").last
    if not seen_visible(editor, timeout=5000) or not filled(editor, None, text):
        return False
    try:
        editor.press("Enter", timeout=5000)
    except Exception:
        return False
    return True


def dom_snapshot(page):
    """Raw truth from the page: sentinel, error banner, visible text, state."""
    return page.evaluate("""() => ({
        noReload: window.__noReload,
        bannerShown: getComputedStyle(document.getElementById('error-banner')).display !== 'none',
        bannerText: document.getElementById('error-banner-text').textContent,
        bodyText: document.body.innerText,
        stateText: JSON.stringify(state),
    })""")


# ---------- suite ---------------------------------------------------------------

checks = Checks()
check = checks.ok


def main():
    # Deliberately NOT open_studio(): this suite kills and restarts its server,
    # so it must own the process even when E2E_BASE is set.
    studio = start_studio()
    base = studio.base_url
    port = int(base.rsplit(":", 1)[1])
    projects_dir = studio.projects_dir
    procs = []
    try:
        upload(base, PROJ, FIXTURE)
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")
            page.evaluate("async (n) => { await openProject(n); }", PROJ)
            check("the desk opened with the scene note controls (precondition)",
                  seen_visible(page.locator("button.note-add").first, timeout=10000))

            # ---- Leg 1: one successful UI write under the ORIGINAL token ----
            ok = ui_add_note(page, 0, "note saved before the restart")
            landed_before = ok and wait_note_stored(base, PROJ, "before the restart", timeout=10)
            check("write #1 (the control under test) stored over HTTP first",
                  landed_before, f"ui_ok={ok}")
            old_token = common.studio_token(base)
            check("the studio boots with a minted token (precondition)", bool(old_token))

            # sentinel BEFORE the kill: proves the tab is never reloaded/navigated
            page.evaluate("() => { window.__noReload = 1; }")

            # ---- kill and restart: same port, same dir, NEW process ----
            kill_studio(studio._proc)
            check("the studio really died (precondition)", wait_dead(base))
            proc2, _log2 = relaunch_studio(port, projects_dir)
            procs.append(proc2)
            new_token = refetch_token(base)
            check("the restart minted a DIFFERENT token (the scenario is real)",
                  bool(new_token) and new_token != old_token,
                  json.dumps({"old": bool(old_token), "new": bool(new_token),
                              "same": new_token == old_token}))

            # ---- second write from the SAME tab, nothing touched ----
            ok2 = ui_add_note(page, 1, "note saved after the restart")
            check("the after-restart write control was usable (precondition)", ok2)
            # Poll to ONE verdict: the write lands, or an error banner appears —
            # sampling every 0.3s, because the banner auto-hides after 10s and
            # a single late read would miss the failure it is meant to catch.
            landed_after, snap, bad_banner = False, {}, ""
            deadline = time.time() + 15
            while time.time() < deadline:
                snap = dom_snapshot(page)
                if snap["bannerShown"] and snap["bannerText"]:
                    bad_banner = snap["bannerText"]
                    break
                try:
                    landed_after = any("after the restart" in t
                                       for t in notes_via_http(base, PROJ))
                except Exception:
                    landed_after = False
                if landed_after:
                    break
                time.sleep(0.3)
            check("L1a the tab was never reloaded or navigated",
                  snap.get("noReload") == 1, json.dumps(snap.get("noReload")))
            check("L1b the restart write landed on the NEW server's store",
                  landed_after and "after the restart" in
                  notes_store_bytes(projects_dir, PROJ).decode("utf-8", "replace"),
                  f"http_seen={landed_after}")
            surfaced = (bad_banner
                        or RESTART_SENTENCE in snap.get("bodyText", "")
                        or RESTART_SENTENCE in snap.get("stateText", "")
                        or INTERNAL_TOKEN_STRING in snap.get("bodyText", "")
                        or INTERNAL_TOKEN_STRING in snap.get("stateText", ""))
            check("L1c no writer-facing error surfaced for the recovered write",
                  not surfaced,
                  json.dumps({"banner": bad_banner[:120],
                              "restarted_in_dom": RESTART_SENTENCE in snap.get("bodyText", ""),
                              "internal_in_dom": INTERNAL_TOKEN_STRING in snap.get("bodyText", "")}))
            check("L1d the page's cookie now equals the NEW server's token",
                  page_cookie_token(page) == new_token,
                  json.dumps({"cookie": (page_cookie_token(page) or "")[:8] + "…",
                              "want": new_token[:8] + "…"}))

            # ---- honest failure: killed and NOT restarted ----
            kill_studio(proc2)
            procs.remove(proc2)
            check("the studio died again (precondition)", wait_dead(base))
            page.evaluate("() => { hideError(); return true; }")
            ok3 = ui_add_note(page, 2, "note the dead server never got")
            # Chromium's fetch against the just-killed server needs ~2s (it
            # dies on a reused keep-alive socket) — poll the banner, bounded.
            fail = {"shown": False, "text": "", "body": ""}
            deadline = time.time() + 12
            while time.time() < deadline:
                fail = page.evaluate("""() => ({
                    shown: getComputedStyle(document.getElementById('error-banner')).display !== 'none',
                    text: document.getElementById('error-banner-text').textContent,
                    body: document.body.innerText,
                })""")
                if fail["shown"] and fail["text"]:
                    break
                page.wait_for_timeout(400)
            msg = fail.get("text", "")
            check("a write against a dead server was attempted through the UI",
                  ok3, "note control unreachable while dead")
            check("the writer sees a readable sentence, not the internal token string "
                  "and not a raw TypeError",
                  fail.get("shown") and "Couldn't save note" in msg
                  and INTERNAL_TOKEN_STRING not in msg and "TypeError" not in msg
                  and INTERNAL_TOKEN_STRING not in fail.get("body", ""),
                  json.dumps(msg[:160]))
            # nothing reached any server: the store still has exactly the two notes
            check("the failed write stored nothing",
                  "never got" not in notes_store_bytes(projects_dir, PROJ).decode("utf-8", "replace"))

            # ---- restore the studio for Leg 2 ----
            proc3, _log3 = relaunch_studio(port, projects_dir)
            procs.append(proc3)
            refetch_token(base)

            # ---- Leg 2: destructive confirm() answered "Cancel" ----
            # launch() auto-accepts every dialog and Python's Page has no
            # remove_all_listeners, so Leg 2 runs in its OWN context with a
            # controllable dialog handler (launch() itself untouched). Fresh
            # context = fresh licence too: the goto below re-mints the cookie.
            KILL_TEXT = "note that may or may not survive a confirm()"
            r = requests.post(f"{base}/api/projects/{PROJ}/notes",
                              headers=studio_headers(base), timeout=30,
                              json={"scene_number": 1, "text": KILL_TEXT})
            assert r.status_code == 201, r.text
            note_id = r.json()["id"]

            dialog_mode = {"accept": False}
            seen_dialogs = []

            def _dialog(d):
                seen_dialogs.append(d.message)
                if dialog_mode["accept"]:
                    d.accept()
                else:
                    d.dismiss()

            errors2 = []
            page2 = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
            page2.on("pageerror", lambda e: errors2.append(str(e)))
            page2.on("dialog", _dialog)
            page2.goto(base)
            page2.wait_for_load_state("networkidle")
            page2.evaluate("async (n) => { await openProject(n); }", PROJ)
            # the seeded note must be ON SCREEN with its confirm-gated delete
            wrap = page2.locator(f'.note-mine[data-note-id="{note_id}"]')
            present = seen_visible(wrap, timeout=8000)
            del_btn = wrap.locator('button[title="Delete this note"]')
            check("the seeded note renders with its confirm-gated delete (precondition)",
                  present and seen_visible(del_btn.first, timeout=4000), note_id)

            before = notes_store_bytes(projects_dir, PROJ)
            clicked(del_btn.first)
            page2.wait_for_timeout(1000)
            after_decline = notes_store_bytes(projects_dir, PROJ)
            check("L2 the confirm() gate actually fired",
                  any("Delete this margin note" in m for m in seen_dialogs),
                  json.dumps(seen_dialogs))
            check("L2 declining the dialog leaves notes.json byte-identical",
                  after_decline == before,
                  f"{len(before)} vs {len(after_decline)} bytes")
            check("L2 the note is still on screen after Cancel",
                  page2.locator(f'.note-mine[data-note-id="{note_id}"]').count() == 1
                  and KILL_TEXT in page2.evaluate(
                      "([id]) => { const e = document.querySelector(`.note-mine[data-note-id='${id}']`);"
                      "  return e ? e.textContent : ''; }", [note_id]))
            check("L2 declining surfaced no error",
                  not page2.evaluate("() => getComputedStyle("
                                     "document.getElementById('error-banner')).display !== 'none'"))

            # can-fail witness: ACCEPTING the same dialog really destroys it
            dialog_mode["accept"] = True
            clicked(del_btn.first)
            gone_store = False
            gone_dom = False
            deadline = time.time() + 10
            while time.time() < deadline and not (gone_store and gone_dom):
                gone_store = note_id not in notes_store_bytes(
                    projects_dir, PROJ).decode("utf-8", "replace")
                gone_dom = page2.locator(f'.note-mine[data-note-id="{note_id}"]').count() == 0
                time.sleep(0.3)
            check("L2 witness: accepting DOES delete the note from the store",
                  gone_store, note_id)
            check("L2 witness: accepting DOES remove it from the desk",
                  gone_dom)

            assert_no_js_errors(checks, errors, "no JS page errors (Leg 1 tab)")
            assert_no_js_errors(checks, errors2, "no JS page errors (Leg 2 tab)")
            browser.close()
    finally:
        for p in procs:
            kill_studio(p)
        studio.close()

    checks.finish()


if __name__ == "__main__":
    main()
