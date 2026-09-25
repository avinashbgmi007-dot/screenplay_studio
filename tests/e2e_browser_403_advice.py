"""e2e_browser_403_advice.py — the writer gets the RIGHT advice for a 403.

BE-4 (round-3 audit 2026-09-25). Both guards answer **403**, and they need
different advice: a stale capability token is fixed by reloading, while a Host the
desk does not answer to is **not** — the reload re-sends the same Host and gets the
same 403. The SPA told the writer to reload either way, which is confidently wrong
for the second case. The server now marks the Host branch (`host_rejected`) and
`_tokenError` branches on it.

**Why the bodies are injected rather than produced over the wire.** Chromium
refuses to send a foreign `Host` at all — `new_context(extra_http_headers={"Host":
...})` fails the navigation with `net::ERR_INVALID_ARGUMENT` (measured). That is a
real and reassuring fact about the threat model — a page cannot FORGE the header,
which is exactly why the attack needed the attacker's hostname to resolve to
127.0.0.1 (rebinding) — but it means a browser cannot reach the host-rejection
branch. So this suite fetches the bodies the SERVER actually produced (`requests`
can set the header) and injects exactly those into the page's transport. The copy
is real and the bodies are real; only the last hop is simulated, and it cannot be
anything else.

Run:  python tests/e2e_browser_403_advice.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    Checks,
    assert_no_js_errors,
    launch,
    open_studio,
    studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

# Stubs the transport for the next /api/ call and reports what `api()` threw.
# Everything that is not /api/ passes through, so the token-mint GET and any
# other real traffic behave normally.
PROBE = """async (a) => {
  const real = window.fetch;
  window.fetch = async (url, opts) => {
    if (String(url).indexOf('/api/') !== -1) {
      return new Response(a.body, {status: a.status,
                                   headers: {'Content-Type': 'application/json'}});
    }
    return real(url, opts);
  };
  try {
    await api('/projects');
    return {threw: false};
  } catch (e) {
    return {threw: true, message: e.message, status: e.status,
            hostRejected: !!e.hostRejected, tokenStale: !!e.tokenStale};
  } finally {
    window.fetch = real;
  }
}"""


def main():
    checks = Checks()
    check = checks.ok

    with open_studio() as base:
        # ---- the REAL bodies, from the real server -------------------------
        host_resp = requests.get(f"{base}/api/projects",
                                 headers={"Host": "evil.attacker.com"}, timeout=30)
        check("the server refuses a foreign Host (precondition)",
              host_resp.status_code == 403, f"HTTP {host_resp.status_code}")
        host_body = host_resp.text
        check("...and marks it as a host refusal (precondition)",
              host_resp.json().get("host_rejected") is True, host_body[:160])

        token_resp = requests.post(f"{base}/api/projects/whatever/analyze",
                                   headers={"X-Studio-Token": "definitely-wrong"},
                                   timeout=30)
        check("the server refuses a bad capability token (precondition)",
              token_resp.status_code == 403, f"HTTP {token_resp.status_code}")
        token_body = token_resp.text
        check("...and does NOT mark it as a host refusal (precondition)",
              not token_resp.json().get("host_rejected"), token_body[:160])

        # ---- what the SPA tells the writer ---------------------------------
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            host = page.evaluate(PROBE, {"status": 403, "body": host_body})
            check("a host refusal throws, and is marked as one",
                  host.get("threw") and host.get("hostRejected"), json.dumps(host))
            check("...and the advice names the loopback address to use instead",
                  "127.0.0.1" in (host.get("message") or ""),
                  json.dumps(host.get("message")))
            check("...and does NOT tell the writer to reload "
                  "(reloading re-sends the same Host)",
                  "reload" not in (host.get("message") or "").lower(),
                  json.dumps(host.get("message")))

            token = page.evaluate(PROBE, {"status": 403, "body": token_body})
            check("a stale token still throws, marked as stale",
                  token.get("threw") and token.get("tokenStale"), json.dumps(token))
            check("...and still gets the reload advice, which is right for it",
                  "reload" in (token.get("message") or "").lower(),
                  json.dumps(token.get("message")))

            check("the two 403s do not share a message — the marker is what "
                  "separates them",
                  bool(host.get("message")) and host["message"] != token.get("message"),
                  json.dumps({"host": host.get("message"),
                              "token": token.get("message")}))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
