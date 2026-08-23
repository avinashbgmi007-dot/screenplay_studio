"""Browser-level e2e for the UI batch: sidebar flyouts, the translate
language picker, and local dictation (stubbed recorder + intercepted STT).

Flow mirrors a writer's evening: land on the desk -> browse the collapsed
shelves -> open an idea from the flyout -> summon Sameer mid-page -> ask ->
hover the globe for Telugu -> dictate a follow-up with the mic.
"""
import re
import sys

import requests
from playwright.sync_api import sync_playwright, expect

BASE = __import__("os").environ.get("E2E_BASE", "http://localhost:8500")
PAGE = (
    "Flyout Probe\n\n"
    "A night courier in Mumbai discovers her delivery bag swaps whatever is "
    "inside with an object from the recipient's greatest regret.\n"
    "She keeps one swapped item: a brass key nobody has claimed.\n"
)

PASS = 0


def ok(name, cond=True):
    global PASS
    if not cond:
        print(f"FAIL {name}")
        sys.exit(1)
    PASS += 1
    print(f"PASS {name}")


def main():
    api = requests.Session()
    # seed an idea + conversation over HTTP (the browser then navigates via UI)
    iid = api.post(f"{BASE}/api/ideas", json={"title": "Flyout Probe"}).json()["id"]
    # sweep leftovers from earlier aborted runs so counts are deterministic
    for old in api.get(f"{BASE}/api/ideas").json():
        if old["title"] == "Flyout Probe" and old["id"] != iid:
            api.delete(f"{BASE}/api/ideas/{old['id']}")
    n_ideas = len(api.get(f"{BASE}/api/ideas").json())
    api.post(f"{BASE}/api/ideas/{iid}/content", json={"content": PAGE})
    sid = api.post(f"{BASE}/api/ideas/{iid}/chat/start").json()["session_id"]
    r = api.post(f"{BASE}/api/ideas/{iid}/chat/sessions/{sid}/messages",
                 json={"text": "what about the brass key?"})
    assert r.ok, r.text

    errors = []
    mic_stub = """
    window.__mic_chunks = [];
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

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(mic_stub)
        page.route("**/api/stt", lambda route: route.fulfill(
            json={"text": "dictated brass key line", "language": "en", "engine": "stub"}))
        page.goto(BASE, wait_until="networkidle")

        # ---- sidebar flyouts ----
        ideas_section = page.locator("#ideas-section")
        expect(page.locator("#idea-list")).to_be_hidden()
        ok("flyouts collapsed on load")
        page.locator("#ideas-trigger").hover()
        expect(ideas_section).to_have_class(re.compile("open"))
        ok("hover opens the Ideas flyout")
        badge = page.locator("#idea-count").inner_text().strip()
        ok("count badge shows items", badge == str(n_ideas))

        # open the idea from inside the flyout (click-through navigation)
        page.locator("#idea-list .idea-item", has_text="Flyout Probe").first.click()
        expect(page.locator("#idea-content")).to_be_visible()
        val = page.locator("#idea-content").input_value()
        assert "brass key" in val, val[:120]
        ok("flyout item click opens the idea")

        # typing still lands after mic reparenting
        page.locator("#idea-content").focus()
        page.keyboard.press("End")
        page.keyboard.type(" /sameer what does the key unlock?")
        page.wait_for_timeout(600)  # summon debounce + save flush
        composer = page.locator("#input")
        expect(composer).to_be_visible()
        deadline = 0
        while "key" not in composer.input_value() and deadline < 40:
            page.wait_for_timeout(100); deadline += 1
        assert "key" in composer.input_value(), composer.input_value()
        ok("/sameer summons from the flyout-opened idea")

        composer.press("Enter")
        # assistant bubbles render straight into .msg-bubble (no .msg-text wrapper)
        page.wait_for_selector(".msg.assistant:not(.msg-pending)", timeout=20000)
        ok("Sameer replies in the summoned room")
        page.wait_for_timeout(700)   # let the reply stream settle (a human reads first)

        # ---- translate language picker ----
        globe = page.locator(".msg.assistant .translate-btn").last
        globe.hover()
        expect(page.locator(".lang-menu").last).to_be_visible()
        n_items = page.locator(".lang-menu .lang-menu-item").count()
        ok("globe hover shows language menu", n_items == 5)
        page.eval_on_selector(
            ".lang-menu .lang-menu-item >> nth=1",
            "el => el.click()")  # Telugu
        panel_label = page.wait_for_function(
            """() => {
              const panels = [...document.querySelectorAll('.msg-translation')];
              const last = panels[panels.length - 1];
              return last && !last.hidden ? last.querySelector('.msg-translation-label')?.textContent : null;
            }""", timeout=15000)
        assert "\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41" in panel_label.json_value(), panel_label.json_value()
        ok("Telugu target renders a labeled inline panel")
        # not persisted: reload wipes it (display-only contract)
        n_before = page.locator(".msg-translation").count()

        # ---- dictation (stubbed recorder + intercepted STT) ----
        mic = page.locator("div.mic-wrap:has(#input) .mic-btn")
        expect(mic).to_be_visible()
        mic.click()
        expect(mic).to_have_class(re.compile("recording"))
        ok("mic click starts recording state")
        page.evaluate(
            "() => { const r = window.MediaRecorder.instances.at(-1);" 
            " r.ondataavailable({ data: new Blob(['hello'], { type: 'audio/webm' }) }); }")
        mic.click()  # stop -> upload -> insert at caret
        deadline = 0
        while "dictated brass key line" not in composer.input_value() and deadline < 50:
            page.wait_for_timeout(100); deadline += 1
        assert "dictated brass key line" in composer.input_value(), composer.input_value()
        ok("transcribed text lands at the caret")

        # right-click picks the speech language (remembered)
        mic.click(button="right")
        expect(page.locator(".mic-lang-menu").last).to_be_visible()
        page.eval_on_selector(".mic-lang-menu .mic-lang-item >> nth=1",
                              "el => el.click()")
        lang = page.evaluate("() => localStorage.getItem('studio-stt-lang')")
        ok("speech language remembered", lang == "en")

        ok("no JS errors during the whole flow", len(errors) == 0)
        del n_before
        browser.close()

    # cleanup the probe idea
    api.delete(f"{BASE}/api/ideas/{iid}")
    print(f"\n=== {PASS}/{PASS} browser checks green ===")


if __name__ == "__main__":
    main()
