"""BE-H1 e2e — the writer is TOLD when a model-server URL is refused.

`tests/test_server_url_guard.py` proves the *server* refuses a remote URL. This
proves the *desk* says so. A silent 400 would leave the writer clicking Save on
a modal that does nothing, which is its own bug — and the whole point of the
guard is that the writer understands why their script cannot go to that host.

Boots the real studio (demo craft model, loopback) and drives the actual
Settings modal:

  1. Test Connection with a remote URL -> refusal shown in the result line
  2. Save with a remote URL            -> error banner names the opt-in, the
                                          modal stays open, the config is intact
  3. both prefix-check bypasses        -> also refused
  4. the real loopback URL             -> still connects, so the guard is a
                                          filter and not a wall
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import Checks, assert_no_js_errors, launch, start_studio  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

# Non-routable by standard (RFC 5737 / RFC 2606): a regression cannot reach a
# real host from here.
REMOTE = "http://192.0.2.1:1"
REMOTE_NAME = "http://inference.example:1"
USERINFO_BYPASS = "http://127.0.0.1@192.0.2.1:1"
SUFFIX_BYPASS = "http://localhost.inference.example:1"

RESULT = "#test-connection-result"


def _config(page):
    return page.evaluate("fetch('/api/config').then(r => r.json())")


def _result_state(page):
    return (page.locator(RESULT).inner_text(),
            page.locator(RESULT).get_attribute("class") or "")


def run():
    checks = Checks()

    with start_studio() as studio:
        with sync_playwright() as p:
            browser, page, errors = launch(p)
            page.goto(studio.base_url, wait_until="networkidle")
            expect(page.locator("#welcome-view")).to_be_visible(timeout=10000)

            # The URL the desk is genuinely on — the control for every refusal
            # below, so "refused" cannot be confused with "nothing works".
            real_url = _config(page)["server_url"]
            checks.ok("studio is on a loopback server",
                      "127.0.0.1" in real_url or "localhost" in real_url, real_url)

            page.click("#settings-btn")
            expect(page.locator("#settings-modal")).to_be_visible(timeout=10000)

            # ---- 1. Test Connection refuses, and says why ----------------
            page.fill("#server-url-input", REMOTE_NAME)
            page.click("#test-connection-btn")
            expect(page.locator(RESULT)).to_contain_text("local", timeout=20000)
            text, cls = _result_state(page)
            checks.ok("Test Connection refuses a remote URL",
                      "fail" in cls, cls)
            checks.ok("the refusal names the opt-in",
                      "--allow-remote-server" in text, text[:120])

            # ---- 2. Save refuses and leaves the desk intact --------------
            page.fill("#server-url-input", REMOTE)
            page.click("#settings-save")
            expect(page.locator("#error-banner")).to_be_visible(timeout=20000)
            banner = page.locator("#error-banner-text").inner_text()
            checks.ok("Save surfaces the refusal in the error banner",
                      "Refusing" in banner, banner[:120])
            checks.ok("the banner names the opt-in",
                      "--allow-remote-server" in banner, banner[:120])
            checks.ok("the settings modal stays open after a refusal",
                      page.locator("#settings-modal").is_visible())
            checks.ok("the refused URL never reached the config",
                      _config(page)["server_url"] == real_url,
                      f"{_config(page)['server_url']} vs {real_url}")

            # ---- 3. the two prefix-check bypasses ------------------------
            for label, url in (("userinfo", USERINFO_BYPASS), ("suffix", SUFFIX_BYPASS)):
                page.fill("#server-url-input", url)
                page.click("#test-connection-btn")
                expect(page.locator(RESULT)).to_contain_text("local", timeout=20000)
                text, cls = _result_state(page)
                checks.ok(f"{label} bypass refused at the desk",
                          "local" in text.lower() and "fail" in cls, f"{text[:60]} | {cls}")
                checks.ok(f"{label} bypass left the config alone",
                          _config(page)["server_url"] == real_url)

            # ---- 4. the real loopback URL still works --------------------
            page.fill("#server-url-input", real_url)
            page.click("#test-connection-btn")
            page.wait_for_function(
                "() => { const el = document.querySelector('#test-connection-result');"
                " return el && /Connected/.test(el.textContent); }", timeout=30000)
            _, cls = _result_state(page)
            checks.ok("a loopback URL still connects (a filter, not a wall)",
                      "ok" in cls, cls)

            page.click("#settings-save")
            expect(page.locator("#settings-modal")).to_be_hidden(timeout=20000)
            checks.ok("saving the real URL still succeeds",
                      _config(page)["server_url"] == real_url)

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    run()
