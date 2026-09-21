"""E2E — the Settings modal is ONE form for two places a model can live.

`tests/test_connection_modes.py` proves the server side: the mode is not a
permission, the opt-in is a launch decision, and a saved token becomes a real
`Authorization: Bearer …` on the wire. This proves the DESK side — that the
writer can actually reach both setups through the same form, and that the form
tells the truth about which one is available.

Boots the real studio twice, because the two halves are genuinely different
states of the same product:

  A. a studio started WITHOUT the opt-in — the local path, and the honest
     disabled state of the remote option;
  B. a studio started WITH `--allow-remote-server` — the remote path, the shared
     fields, and the one thing that must never happen: the token coming back to
     the browser.

Suite B deliberately saves a `.example` host (RFC 2606, never resolves) so the
post-save connection probe fails instantly instead of hanging on a timeout.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import Checks, assert_no_js_errors, launch, start_studio  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

# Reserved TLD — guaranteed never to resolve, so the probe fails immediately.
REMOTE = "http://inference.example:1/v1"
TOKEN = "sk-e2e-0123456789abcdef"


def _config(page):
    return page.evaluate("fetch('/api/config').then(r => r.json())")


def _open_settings(page, base):
    page.goto(base, wait_until="networkidle")
    expect(page.locator("#welcome-view")).to_be_visible(timeout=15000)
    page.click("#settings-btn")
    expect(page.locator("#settings-modal")).to_be_visible(timeout=10000)


def _local_half(checks):
    """A studio with no remote opt-in: local works, remote is honestly closed."""
    with start_studio() as studio:
        with sync_playwright() as p:
            browser, page, errors = launch(p)
            _open_settings(page, studio.base_url)

            cfg = _config(page)
            checks.ok("the desk reports its mode and the opt-in state",
                      cfg["connection_mode"] == "local" and cfg["allow_remote"] is False,
                      f"mode={cfg.get('connection_mode')} allow_remote={cfg.get('allow_remote')}")
            checks.ok("no token is set on a fresh local desk",
                      cfg["api_key_set"] is False)
            checks.ok("the raw token is not a field in the config response",
                      "api_key" not in cfg, str(sorted(cfg.keys()))[:140])

            # ---- the form itself ----------------------------------------
            checks.ok("Local is the selected mode",
                      page.get_attribute("#mode-local", "aria-checked") == "true")
            checks.ok("Remote is offered but DISABLED while the opt-in is off",
                      page.locator("#mode-remote").is_disabled(),
                      "a mode the server refuses must not look selectable")
            hint = page.inner_text("#mode-hint")
            checks.ok("the hint names the launch flag that would enable it",
                      "--allow-remote-server" in hint, hint[:140])
            checks.ok("the URL field is labelled for a local server",
                      "llama-server" in page.inner_text("#server-url-label"))

            # The token field is SHARED and stays visible: a local llama-server
            # can legitimately require one (--api-key), and hiding the field
            # would make that setup unreachable while a stored token kept being
            # sent anyway.
            checks.ok("the token field is present in local mode too",
                      page.locator("#api-key-input").is_visible())
            checks.ok("the local token hint explains when one is needed",
                      "--api-key" in page.inner_text("#api-key-hint"),
                      page.inner_text("#api-key-hint")[:120])

            # ---- local actually still works -----------------------------
            real_url = cfg["server_url"]
            page.fill("#server-url-input", real_url)
            page.click("#test-connection-btn")
            page.wait_for_function(
                "() => { const el = document.querySelector('#test-connection-result');"
                " return el && /Connected/.test(el.textContent); }", timeout=30000)
            cls = page.locator("#test-connection-result").get_attribute("class") or ""
            checks.ok("Test Connection reports the mode it connected in",
                      "ok" in cls and "(local)" in page.inner_text("#test-connection-result"),
                      page.inner_text("#test-connection-result")[:100])

            page.fill("#model-input", "my-local-model")
            page.click("#settings-save")
            expect(page.locator("#settings-modal")).to_be_hidden(timeout=20000)
            checks.ok("the model name round-trips through save",
                      _config(page)["model"] == "my-local-model",
                      str(_config(page).get("model")))

            # reopening shows what was saved, not a blank form
            page.click("#settings-btn")
            expect(page.locator("#settings-modal")).to_be_visible(timeout=10000)
            checks.ok("reopening the form shows the saved model",
                      page.input_value("#model-input") == "my-local-model")
            checks.ok("reopening the form is still Local",
                      page.get_attribute("#mode-local", "aria-checked") == "true")
            checks.ok("reopening the form does not leak the token into the field",
                      page.input_value("#api-key-input") == "",
                      "the field must never be populated from the server")

            assert_no_js_errors(checks, errors)
            browser.close()


def _remote_half(checks):
    """A studio started WITH the opt-in: the remote path is genuinely usable."""
    env = {"SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER": "1"}
    with start_studio(env_extra=env) as studio:
        with sync_playwright() as p:
            browser, page, errors = launch(p)
            _open_settings(page, studio.base_url)

            cfg = _config(page)
            checks.ok("the opt-in is reported to the desk",
                      cfg["allow_remote"] is True, str(cfg.get("allow_remote")))
            checks.ok("Remote is selectable once the studio was launched with the flag",
                      not page.locator("#mode-remote").is_disabled())

            # ---- switching modes keeps the shared fields -----------------
            page.fill("#model-input", "shared-model")
            page.fill("#timeout-input", "900")
            page.click("#mode-remote")
            checks.ok("Remote becomes the selected mode",
                      page.get_attribute("#mode-remote", "aria-checked") == "true")
            checks.ok("the URL field is relabelled for an API base URL",
                      "API" in page.inner_text("#server-url-label"),
                      page.inner_text("#server-url-label"))
            checks.ok("the placeholder shows the /v1 shape",
                      "/v1" in (page.get_attribute("#server-url-input", "placeholder") or ""))
            checks.ok("the remote hint warns that the script leaves the machine",
                      "leaves this machine" in page.inner_text("#mode-hint"),
                      page.inner_text("#mode-hint")[:140])
            # the shared inputs survived the mode switch — the whole point of
            # "one form, two modes"
            checks.ok("the shared fields keep their values across a mode switch",
                      page.input_value("#model-input") == "shared-model"
                      and page.input_value("#timeout-input") == "900",
                      f"model={page.input_value('#model-input')!r} "
                      f"timeout={page.input_value('#timeout-input')!r}")

            # ---- save a real remote setup -------------------------------
            page.fill("#server-url-input", REMOTE)
            page.fill("#api-key-input", TOKEN)
            page.click("#settings-save")
            expect(page.locator("#settings-modal")).to_be_hidden(timeout=20000)

            cfg = _config(page)
            checks.ok("the remote endpoint is saved", cfg["server_url"] == REMOTE,
                      str(cfg.get("server_url")))
            checks.ok("the mode is now derived as remote", cfg["connection_mode"] == "remote",
                      str(cfg.get("connection_mode")))
            checks.ok("the desk reports a token is set", cfg["api_key_set"] is True)
            checks.ok("the token is NOT returned to the browser",
                      TOKEN not in str(cfg), "the secret came back in /api/config")

            # ---- and back to local fills the local info in --------------
            page.click("#settings-btn")
            expect(page.locator("#settings-modal")).to_be_visible(timeout=10000)
            checks.ok("reopening shows the remote mode and a saved-token placeholder",
                      page.get_attribute("#mode-remote", "aria-checked") == "true"
                      and "saved" in (page.get_attribute("#api-key-input", "placeholder") or ""),
                      page.get_attribute("#api-key-input", "placeholder") or "")

            page.click("#mode-local")
            page.click("#settings-save")
            expect(page.locator("#settings-modal")).to_be_hidden(timeout=20000)
            cfg = _config(page)
            checks.ok("switching to Local restores the localhost URL",
                      cfg["server_url"] == "http://localhost:8080", str(cfg.get("server_url")))
            checks.ok("switching to Local clears the remote token",
                      cfg["api_key_set"] is False,
                      "a remote credential must not be left pointed at localhost")
            checks.ok("the mode reads local again", cfg["connection_mode"] == "local")

            assert_no_js_errors(checks, errors)
            browser.close()


def run():
    checks = Checks()
    _local_half(checks)
    _remote_half(checks)
    checks.finish()


if __name__ == "__main__":
    run()
