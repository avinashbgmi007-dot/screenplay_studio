"""E2E-4 (audit 2026-09-24) — the SPA's fetch -> SSE -> render loop, over a real transport.

The audit's finding: *"the browser gate only ever exercises the demo model"*, and it
called this "the largest single coverage asymmetry in the gate".

Why the gate could not see it: `e2e_browser_common.start_studio()` forces
`SCREENPLAY_STUDIO_DEMO_MODEL=1` and passes `--demo-model`, and the demo craft model runs
**in-process**. So no suite had ever put an HTTP model transport under the chat pane at
all. pytest does cover the pipeline against `tests/mock_unified_server.py` — but that is a
different transport (`requests`, non-streaming) and a different code path from the SPA's
`fetch(/messages/stream)` -> SSE -> render loop. A regression in the *browser's* handling
of a real model's streaming would have been invisible.

This suite boots the studio with `demo_model=False` against the mock llama-server, so a
turn really travels:

    SPA fetch -> studio /messages/stream -> HTTP -> mock -> SSE frames -> studio -> SPA render

Two things had to exist first, and both are the finding's real content:

  * the mock answered only in the **non-streaming** shape, so it had no SSE to give a
    client that asked for it (`_answer_in_the_shape_that_was_asked_for`);
  * `start_studio` had no way to boot without the demo model.

The checks are written so this cannot pass by accidentally testing the demo path again:
the demo flag must be **false**, the studio's server_url must be the mock, the reply must
carry the mock's marker, and the mock must have seen a `stream: true` request.

Run:  python tests/e2e_browser_real_transport.py
"""
import json
import os
import sys
import threading

import requests
from flask import request
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from e2e_browser_common import (Checks, assert_no_js_errors, free_port, launch,
                                start_studio, studio_headers)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_unified_server as mock  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok

# Every chat completion the mock was asked for. Recorded here rather than in the
# mock itself so the mock stays a plain stand-in for llama-server.
SEEN: list = []


@mock.app.before_request
def _record_chat_completions():
    if request.path == "/v1/chat/completions":
        SEEN.append(request.get_json(silent=True) or {})


def start_mock():
    """The mock llama-server on its own port, in this process."""
    port = free_port()
    server = make_server("127.0.0.1", port, mock.app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


def seed(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=120)
    assert r.status_code in (200, 201), r.text
    return r.json().get("project") or title


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    page.locator(".project-item").filter(has_text=name.split("_")[0]).first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def run():
    server, mock_base = start_mock()
    try:
        with start_studio(server_url=mock_base, demo_model=False) as studio:
            base = studio.base_url

            # ---- preconditions: this is a REAL-transport boot -----------------
            # Each of these can fail, and each failure would otherwise let the
            # suite pass while testing the demo model all over again.
            cfg = studio.get_json("/api/config")
            check("the demo model is OUT of the path",
                  cfg.get("demo_model") is False,
                  f"demo_model={cfg.get('demo_model')!r} — the suite would be "
                  f"testing the in-process demo model, not a transport")

            health = studio.get_json("/api/health")
            check("the studio is pointed at the mock server",
                  health.get("server_url") == mock_base,
                  f"{health.get('server_url')!r} != {mock_base!r}")

            name = seed(base, "Real Transport Probe")
            check("the project seeded", bool(name), name)

            before = len(SEEN)
            with sync_playwright() as p:
                browser, page, errors = launch(p)
                open_project(page, base, name)

                # ---- the Sameer room, then one streamed turn ------------------
                page.locator("#right-edge-affordance").click()
                page.wait_for_timeout(450)
                page.locator("#dock-tab-sameer").click()
                page.wait_for_timeout(450)

                slot = page.locator('.dock-lens[data-lens="sameer"] .dock-chat-slot')
                check("the composer is reachable (precondition)",
                      slot.locator("#input").count() == 1)

                slot.locator("#input").fill("What do you make of the brass key?")
                slot.locator("#send-btn").click()
                page.wait_for_selector('.dock-lens[data-lens="sameer"] .msg.user',
                                       timeout=15000)
                check("the writer's own message renders",
                      page.locator('.dock-lens[data-lens="sameer"] .msg.user').count() >= 1)

                # The reply must finish STREAMING, not just appear: `:not(.msg-pending)`
                # is the SPA's own signal that the SSE stream closed.
                settled = True
                try:
                    page.wait_for_selector(
                        '.dock-lens[data-lens="sameer"] .msg.assistant:not(.msg-pending)',
                        timeout=20000)
                except Exception:
                    settled = False
                check("the assistant reply finished streaming", settled)

                reply = ""
                try:
                    reply = page.locator(
                        '.dock-lens[data-lens="sameer"] .msg.assistant .msg-bubble'
                    ).last.inner_text(timeout=8000).strip()
                except Exception:
                    pass

                # ---- the transport is what actually answered -----------------
                check("the reply is not empty (SSE frames were parsed and rendered)",
                      bool(reply), f"reply={reply[:120]!r}")
                check("the reply carries the mock's marker, so it came over HTTP",
                      "[mock chat reply]" in reply, reply[:200])
                check("the persona travelled in the real prompt",
                      "persona=writing_partner" in reply, reply[:200])

                sent = SEEN[before:]
                check("the mock received the turn",
                      len(sent) >= 1, f"{len(sent)} completion(s) seen")
                check("the mock was asked to STREAM, so the SSE path is what ran",
                      any(b.get("stream") is True for b in sent),
                      json.dumps([{"stream": b.get("stream")} for b in sent]))
                check("the real system prompt reached the model",
                      any("co-writing partner" in json.dumps(b.get("messages") or []).lower()
                          or "sameer" in json.dumps(b.get("messages") or []).lower()
                          for b in sent),
                      "no cowriter system prompt in the request bodies")

                assert_no_js_errors(checks, errors)
                browser.close()
    finally:
        server.shutdown()

    checks.finish()


if __name__ == "__main__":
    run()
