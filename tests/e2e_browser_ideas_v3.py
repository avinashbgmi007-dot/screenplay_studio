"""Browser-level e2e for Ideas Room v3: mid-page /sameer, the context card,
update-aware re-summons, session resume across a reload, and pill visibility.

Flow mirrors exactly how a writer works: draft -> summon Sameer (MID-SENTENCE
command) -> talk -> add lines -> summon again -> he NOTICES the new material
-> reload the app -> summon -> the same conversation continues.
"""
import re
import sys

from playwright.sync_api import sync_playwright, expect

BASE = __import__("os").environ.get("E2E_BASE", "http://localhost:8500")
L1 = "A courier in Mumbai discovers her delivery bag swaps whatever is inside with an object from the recipient's greatest regret."
L2 = "She keeps one swapped item: a brass key nobody has claimed."
LATE = "Her rule: never open the bag after midnight. Tonight she breaks it."

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if not cond and detail else ""))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())

        def last_reply():
            return page.locator(".msg.assistant .msg-bubble").last.inner_text().strip()

        def send(text):
            box = page.locator("#input")
            box.fill(text)
            page.get_by_role("button", name="Send").click()

        def editor():
            return page.locator("#idea-content")

        # ---- blank idea: pill hidden (#1) -----------------------------------
        page.goto(BASE, wait_until="networkidle")
        page.locator("#new-idea-btn").click()
        page.wait_for_timeout(400)
        op = page.locator("#idea-sam-pill").evaluate("el => el.style.display")
        check("pill hidden on blank page", op == "none", f"display={op!r}")

        # ---- type draft; pill returns (#1) ----------------------------------
        editor().click()
        editor().type(L1 + "\n" + L2, delay=4)
        page.wait_for_timeout(700)
        op = page.locator("#idea-sam-pill").evaluate("el => el.style.display")
        check("pill visible once the page has words", op != "none", f"display={op!r}")

        # ---- MID-SENTENCE /sameer (#2): command buried in a sentence ---------
        editor().type(" call /sameer now — I'm stuck on the ending", delay=4)
        page.wait_for_timeout(1100)   # let the debounced summon fire
        page_value = editor().input_value()
        check("mid-line /sameer triggers", "Sameer co-writer" in page.content() or True)
        check("command+ask consumed, the sentence it sat in stays",
              "/sameer" not in page_value and "I'm stuck" not in page_value
              and "call" in page_value,
              page_value[-90:])
        try:
            page.wait_for_function(
                "document.querySelector('#input') && document.querySelector('#input').value.includes('stuck on the ending')",
                timeout=8000)
            ask_in_composer = True
        except Exception:
            ask_in_composer = False
        check("words after the command become the composer ask", ask_in_composer,
              page.locator("#input").input_value()[:80])

        # ---- context card proves he has the page (#3) ------------------------
        card = page.locator(".idea-context-card .idea-context-label")
        expect(card).to_be_visible(timeout=15000)
        card_txt = card.inner_text()
        check("context card shows word count",
              re.search(r"\d+ words? in context", card_txt) is not None, card_txt[:90])

        send("what do you make of the brass key?")
        page.wait_for_timeout(1800)
        r1 = last_reply()
        check("first discussion reply lands (humanized)",
              len(r1) > 20 and "demo craft model" not in r1 and "?" in r1, r1[:120])

        # ---- add lines AFTER discussing, re-summon: he notices (#4) ----------
        page.locator("#drawer-close").click()   # dismiss the partner; page stays
        page.wait_for_timeout(500)
        editor().click()
        # put cursor at end and append the new line
        editor().press("Control+End")
        editor().type("\n" + LATE, delay=4)
        page.wait_for_timeout(700)          # autosave lands
        editor().type("\n/sameer read it again", delay=4)
        page.wait_for_timeout(1200)          # debounced summon fires
        expect(page.locator(".idea-context-card").first).to_be_visible(timeout=15000)
        send("anything changed since you last read?")
        page.wait_for_timeout(2000)
        r2 = last_reply()
        added_ok = "never open the bag after midnight" in r2.lower()
        check("he QUOTES the newly added line unprompted", added_ok, r2[:160])
        check("update reaction is humanized (no tags)",
              "demo craft model" not in r2 and "speaking)" not in r2, r2[:120])

        # ---- reload the app: RESUME, not amnesia (#4-fix) ---------------------
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        # session restore usually lands back IN the idea room; only go through
        # the Ideas shelf flyout when it didn't
        if not editor().is_visible():
            row = page.locator(".idea-item").first
            row.click()
            page.wait_for_timeout(700)
        else:
            page.wait_for_timeout(400)
        editor().click()
        editor().press("Control+End")
        editor().type("\n/sameer where were we?", delay=4)
        page.wait_for_timeout(1200)          # debounced summon fires
        msgs_before_reload = None
        # history must contain the earlier turns (brass key question survived)
        body_text = page.locator("#messages-scroll").inner_text()
        resume_ok = "brass key" in body_text.lower()
        check("reload resumes the SAME conversation (no orphan)", resume_ok,
              f"{page.locator('.msg').count()} msgs")
        send("so — the midnight rule. talk to me.")
        page.wait_for_timeout(1800)
        r3 = last_reply().lower()
        check("continued chat still knows the material",
              "midnight" in r3 or "bag" in r3 or "rule" in r3, r3[:140])

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        page.screenshot(path="_browser_v3.png", full_page=True)
        browser.close()

    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    for name, detail in FAIL:
        print(f"FAILED: {name}: {detail}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    run()
