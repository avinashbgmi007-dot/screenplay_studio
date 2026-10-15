"""e2e_browser_stale_socket_recovery.py — the BELOW-HTTP half of restart recovery.

The capability token is minted per server process, so a studio restart kills
every open tab's writes. `session_breaks` covers that end to end with a real
kill — but on Linux CI its first-recovery legs (L1b/L1c/L1d) flaked twice on
2026-09-30 while passing locally every time. The mechanism: the FIRST fetch a
tab attempts against the new process can land on a keep-alive socket the old
process held open, and Chromium discovers the dead socket BELOW HTTP —
TypeError "Failed to fetch", no request sent, so no 403 ever comes back and a
403-only recovery can never fire. (Windows closes sockets with an instant RST,
evicting the dead pooled connection immediately — hence local Windows runs
passed while Linux CI flaked.) Recovery now ALSO triggers on the network-level
TypeError itself: re-mint via the document, retry while the studio answers,
and fail with a readable sentence when it is truly unreachable.

A real kill reproduces the poisoned-socket death only by luck, so a kill-based
suite cannot pin the fix. This suite reproduces it DETERMINISTICALLY by
intercepting the page's fetch: while armed, /api/ requests reject with the
exact TypeError the browser throws for a dead pooled socket. Leg A arms ONCE
(server alive underneath) and asserts the restart contract: re-mint, retry,
write lands on the real store, nothing surfaces to the writer. Leg B keeps
every /api/ attempt dying below HTTP and asserts the failure is the readable
"not reachable" sentence — never the raw TypeError, never the guard's internal
token string — and that the attempts are bounded, not a spin.

Run:  python tests/e2e_browser_stale_socket_recovery.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import (  # noqa: E402
    Checks, assert_no_js_errors, clicked, filled, launch, seen_visible,
    start_studio, studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")
PROJ = "SockRec"
INTERNAL_TOKEN_STRING = "missing or invalid capability token"
DEAD_SENTENCE = "The studio is not reachable right now."

# mode 1 = kill exactly ONE /api/ request, then pass through (the poisoned-
# socket scenario: the first attempt dies, the recovery's retry must find the
# net healthy and land). mode 2 = kill every /api/ request (the studio is
# unreachable through the socket layer). The wrapper installs ONCE and stays
# for the whole suite; legs only move the mode, so counters never race an
# uninstall.
PATCH_FETCH = """() => {
  if (window.__net) { window.__net.mode = 0; return true; }
  const real = window.fetch.bind(window);
  window.__net = { mode: 0, blocked: 0, docFetched: 0, retried: 0 };
  window.fetch = (input, init) => {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const isApi = url.includes("/api/");
    const n = window.__net;
    if (isApi && n.mode) {
      if (n.mode === 1) n.mode = 0; // kill exactly one request
      n.blocked++;
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    if (isApi) n.retried++;
    if (!isApi && url.endsWith("/")) n.docFetched++;
    return real(input, init);
  };
  return true;
}"""

ARM_ONCE = "() => { window.__net.mode = 1; return true; }"
ARM_HOLD = "() => { window.__net.mode = 2; return true; }"
DISARM = """() => {
  const n = window.__net;
  n.mode = 0;
  const out = { blocked: n.blocked, docFetched: n.docFetched, retried: n.retried };
  n.blocked = 0; n.docFetched = 0; n.retried = 0;
  return out;
}"""


def notes_via_http(base, name):
    import requests
    r = requests.get(f"{base}/api/projects/{name}/notes",
                     headers=studio_headers(base), timeout=30)
    assert r.status_code == 200, r.text
    return [n.get("text", "") for n in r.json()["notes"]]


def wait_note_stored(base, name, text, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if any(text in t for t in notes_via_http(base, name)):
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def ui_add_note(page, btn_index, text):
    """The real UI write path: scene-head note button -> textarea -> Enter,
    through the same hardened wrappers session_breaks uses."""
    btn = page.locator("button.note-add").nth(btn_index)
    if not seen_visible(btn, timeout=8000) or not clicked(btn):
        return False
    editor = page.locator("textarea.note-editor").last
    if not seen_visible(editor, timeout=5000) or not filled(editor, None, text):
        return False
    try:
        editor.press("Enter", timeout=5000)
    except Exception:
        return False
    return True


def banner_state(page):
    return page.evaluate("""() => ({
        shown: getComputedStyle(document.getElementById('error-banner')).display !== 'none',
        text: document.getElementById('error-banner-text').textContent,
        body: document.body.innerText,
    })""")


def main():
    checks = Checks()
    check = checks.ok
    studio = start_studio()
    base = studio.base_url
    try:
        import requests
        with open(FIXTURE, "rb") as f:
            r = requests.post(f"{base}/api/projects",
                              headers=studio_headers(base), files={
                "file": (f"{PROJ}.fountain", f, "text/plain")},
                data={"title": PROJ}, timeout=60)
        assert r.status_code in (200, 201), r.text

        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")
            page.evaluate("async (n) => { await openProject(n); }", PROJ)
            check("the desk opened with scene note controls (precondition)",
                  seen_visible(page.locator("button.note-add").first, timeout=10000))

            # ---- Leg A: the first write dies BELOW HTTP — exactly what the
            # first fetch onto a restarted process's poisoned pooled socket
            # produces. One arm, server alive underneath: recovery must re-mint
            # via the document, retry, land the write, surface nothing.
            page.evaluate(PATCH_FETCH)
            page.evaluate(ARM_ONCE)
            ok = ui_add_note(page, 0, "recovered from a below-HTTP death")
            check("the blocked write control was usable (precondition)", ok)
            # The recovery cascade is ASYNC: Enter resolves before the retry
            # does, so wait for the landing FIRST, then read the counters.
            landed = wait_note_stored(base, PROJ, "below-HTTP death", timeout=10)
            net = page.evaluate(DISARM)
            check("A the write landed on the real server's store", landed)
            check("A the first /api/ attempt died below HTTP (scenario is real)",
                  net.get("blocked") == 1, json.dumps(net))
            check("A recovery re-minted via the document",
                  net.get("docFetched", 0) >= 1, json.dumps(net))
            check("A the write was retried after the re-mint",
                  net.get("retried", 0) >= 1, json.dumps(net))
            bad = banner_state(page)
            check("A nothing surfaced to the writer (no banner)",
                  not (bad["shown"] and bad["text"]), json.dumps(bad["text"][:120]))
            check("A no internal token string and no raw TypeError in the DOM",
                  INTERNAL_TOKEN_STRING not in bad["body"] and "TypeError" not in bad["body"])

            # ---- Leg B: EVERY /api/ attempt dies below HTTP (the socket layer
            # is hostile while the server itself stays up). The failure must be
            # the readable sentence, never the raw TypeError, never the guard's
            # internal string — and the attempts must be bounded, not a spin.
            page.evaluate("() => { hideError(); return true; }")
            page.evaluate(ARM_HOLD)
            ok2 = ui_add_note(page, 1, "never lands while the net is down")
            check("the dead-write control was usable (precondition)", ok2)
            # The block STAYS ARMED until the failure has surfaced: every
            # attempt in the bounded recovery cascade must die below HTTP.
            deadline = time.time() + 10
            fail = {"shown": False, "text": "", "body": ""}
            while time.time() < deadline:
                fail = banner_state(page)
                if fail["shown"] and fail["text"]:
                    break
                page.wait_for_timeout(150)
            net2 = page.evaluate(DISARM)
            check("B the readable not-reachable sentence surfaced",
                  fail["shown"] and DEAD_SENTENCE in fail["text"],
                  json.dumps(fail["text"][:160]))
            check("B no internal token string and no raw TypeError anywhere",
                  INTERNAL_TOKEN_STRING not in fail["text"]
                  and "TypeError" not in fail["text"]
                  and INTERNAL_TOKEN_STRING not in fail["body"])
            check("B the attempts were bounded, not a spin",
                  2 <= net2.get("blocked", 0) <= 16, json.dumps(net2))
            check("B the failed write stored nothing",
                  wait_note_stored(base, PROJ, "net is down", timeout=1) is False)

            assert_no_js_errors(checks, errors, "no JS page errors")
            browser.close()
    finally:
        studio.close()
    checks.finish()


if __name__ == "__main__":
    main()
