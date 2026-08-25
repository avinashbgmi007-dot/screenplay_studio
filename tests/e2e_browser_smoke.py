"""SMOKE e2e — the whole desk boots and one chat turn streams, via Playwright.

SELF-CONTAINED like every e2e_browser_* suite now is (see e2e_browser_common):
it launches the real server as a subprocess with the built-in demo craft
model (--demo-model), on a free port with a throwaway projects dir, then
drives the actual UI end to end:

  1. open the studio            -> #welcome-view, status strip shows the demo
  2. demo model active          -> /api/config demo_model=true + "demo craft model" chip
  3. open the sample page       -> #sample-btn creates + opens the project
  4. summon Sameer              -> #gutter-sam opens the partner drawer
  5. send a chat turn           -> #input + #send-btn, SSE body captured
  6. VERIFY STREAMING           -> two independent proofs:
       a. UI-level: a MutationObserver records the pending bubble's text
          length at every DOM mutation; a streamed turn shows strictly
          growing lengths (>=2 distinct states).
       b. wire-level: every SSE frame is parsed; the concatenation of all
          {"token": ...} events must EQUAL the final {"done": ...} reply.
  7. VERIFY PERSISTENCE         -> GET /api/projects/<p>/chat/sessions/<s>
                                   after the turn: the stored assistant
                                   message equals the streamed concatenation,
                                   and the rendered bubble matches it too.

Run:  python tests/e2e_browser_smoke.py
Needs: playwright (+ chromium) installed; nothing else — no llama-server.
"""
import json
import sys

from playwright.sync_api import sync_playwright, expect

from e2e_browser_common import Checks, assert_no_js_errors, last_reply, launch, start_studio

STREAM_OBSERVER = """() => {
  const c = document.querySelector('#messages-scroll');
  window.__streamLog = [];
  const snap = () => {
    const bubbles = c.querySelectorAll('.msg.assistant .msg-bubble');
    const b = bubbles[bubbles.length - 1];
    if (!b) return;
    const sink = b.querySelector('.stream-text');
    window.__streamLog.push((sink ? sink.textContent : b.textContent).length);
  };
  new MutationObserver(snap).observe(c, {subtree: true, childList: true, characterData: true});
}"""


def parse_sse(body):
    """Split an SSE payload into ([token pieces], done_event, error_event)."""
    tokens, done_evt, error_evt = [], None, None
    for frame in body.split("\n\n"):
        line = next((ln for ln in frame.split("\n") if ln.startswith("data:")), None)
        if not line:
            continue
        try:
            evt = json.loads(line[len("data:"):].strip())
        except ValueError:
            continue
        if "token" in evt:
            tokens.append(evt["token"])
        elif evt.get("done"):
            done_evt = evt
        elif "error" in evt:
            error_evt = evt
    return tokens, done_evt, error_evt


def norm(text):
    """Whitespace-insensitive comparison form (rendered HTML reflows spaces)."""
    return " ".join(text.split())


def run():
    checks = Checks()

    with start_studio() as studio:
        with sync_playwright() as p:
            browser, page, errors = launch(p)
            BASE = studio.base_url

            # ---- 1. the studio opens --------------------------------
            page.goto(BASE, wait_until="networkidle")
            checks.ok("app loads", page.title() == "Script Doctor Studio", page.title())
            expect(page.locator("#welcome-view")).to_be_visible(timeout=10000)
            checks.ok("welcome desk shown", True)

            # ---- 2. the demo model is live --------------------------
            cfg = page.evaluate("fetch('/api/config').then(r => r.json())")
            checks.ok("demo model reported by API", cfg.get("demo_model") is True, str(cfg))
            expect(page.locator("#status-model-label")).to_have_text(
                "demo craft model", timeout=15000)
            dot_cls = page.locator("#connection-dot").get_attribute("class") or ""
            checks.ok("status strip shows the demo chip", "demo" in dot_cls, dot_cls)

            # ---- 3. lay the sample page on the desk -----------------
            page.locator("#sample-btn").click()
            expect(page.locator("#project-title")).not_to_have_text("—", timeout=20000)
            checks.ok("sample project opened",
                      page.locator(".workspace").is_visible()
                      and page.locator("#composer").count() == 1)

            # project view closes the partner drawer by design — summon Sameer
            page.locator("#gutter-sam").click()
            drawer_cls = ""
            for _ in range(20):
                drawer_cls = page.locator("#room-drawer").get_attribute("class") or ""
                if "open" in drawer_cls:
                    break
                page.wait_for_timeout(100)
            checks.ok("partner drawer summoned", "open" in drawer_cls, drawer_cls)
            expect(page.locator("#input")).to_be_visible()

            # ---- 4+5. instrument streaming, send a chat turn --------
            # MutationObserver on the messages container: log the live
            # assistant bubble's text length at every DOM mutation batch.
            # A streamed turn produces many distinct lengths; a
            # whole-reply-at-once turn would produce exactly one.
            page.evaluate(STREAM_OBSERVER)

            # capture the raw SSE body so the wire contract can be checked
            with page.expect_response(
                    lambda r: r.request.method == "POST" and "/messages/stream" in r.url,
                    timeout=30000) as ri:
                page.locator("#input").fill("Give me your honest take on scene 1.")
                page.locator("#send-btn").click()

            # user's own message echoes into the transcript
            expect(page.locator(".msg.user").last).to_be_visible(timeout=10000)
            checks.ok("user message rendered", True)

            # the turn finishes when Send re-enables (finishTurn)
            expect(page.locator("#send-btn")).to_be_enabled(timeout=45000)

            # final rendered reply replaces the pending bubble (assistant
            # bubbles render via innerHTML — .msg-text is user-only)
            reply = last_reply(page)
            checks.ok("assistant reply landed", len(reply) > 40, reply[:120])
            checks.ok("reply is a real answer (no error copy)",
                      "Couldn't get a reply" not in reply, reply[:120])

            # ---- 6a. THE POINT: it streamed in the UI ---------------
            log = page.evaluate("window.__streamLog || []")
            distinct = sorted(set(log))
            checks.ok(f"turn streamed progressively ({len(distinct)} distinct render sizes)",
                      len(distinct) >= 2 and max(log) > min(log), f"sizes={distinct[:12]}")

            # ---- 6b+7. wire truth: tokens == final == persisted -----
            sse_body = ri.value.text()
            tokens, done_evt, error_evt = parse_sse(sse_body)
            checks.ok("no error event on the stream", error_evt is None, str(error_evt))
            checks.ok(f"reply arrived as {len(tokens)} streamed tokens",
                      len(tokens) >= 4, f"n={len(tokens)} first={tokens[:3]}")
            concatenated = "".join(tokens)
            final_reply = (done_evt or {}).get("reply")
            checks.ok("concatenation of streamed tokens == the final 'done' reply",
                      final_reply is not None and concatenated == final_reply,
                      f"streamed={len(concatenated)}ch done={final_reply and len(final_reply)}ch")

            proj, sid = page.evaluate("[state.currentProject, state.currentSession]")
            session = studio.get_json(f"/api/projects/{proj}/chat/sessions/{sid}")
            messages = session["branches"][session["current_branch"]]["messages"]
            assistant = [m for m in messages if m["role"] == "assistant"]
            stored = assistant[-1]["content"] if assistant else None
            checks.ok("persisted history ends with this assistant turn",
                      bool(assistant), f"{len(messages)} messages")
            checks.ok("persisted reply == the streamed concatenation",
                      stored == concatenated,
                      f"stored={stored and len(stored)}ch streamed={len(concatenated)}ch")
            checks.ok("rendered bubble matches what was kept",
                      norm(reply) == norm(stored or ""),
                      f"ui={norm(reply)[:80]!r} stored={norm(stored or '')[:80]!r}")

            banner_hidden = not page.locator("#error-banner").is_visible()
            checks.ok("no error banner", banner_hidden)
            assert_no_js_errors(checks, errors)

            page.screenshot(path="_browser_smoke.png", full_page=True)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    run()
