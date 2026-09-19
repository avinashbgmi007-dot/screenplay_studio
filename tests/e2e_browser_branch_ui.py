"""Branch UI gate -- the fork / switch controls in a real browser (M2 / C9).

The branch system shipped with a switcher and nothing to switch to: the fork
entry point had been removed "per the writer's preference", so the flagship
feature had no way to create a second branch. It was restored in
`app.js:renderBranches()` and the fork modal (orphaned in `index.html:722`)
was wired up -- but only the API was ever asserted (`test_webapp_api.py:306`
fork, `:326` switch). The UI path -- pill -> modal -> POST -> switch -- had no
test at all, which is the half that can silently rot.

This suite drives it the way a writer does. It deliberately forks WITHOUT
sending a message first: a fresh project has `state.currentSession === null`
(`app.js:1983`), and the fork button renders on `state.currentProject` alone,
so the null-session path is reachable and must not 404.

Run:  python tests/e2e_browser_branch_ui.py
"""
import os
import time

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, assert_no_js_errors, launch, start_studio

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("project") or title


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    page.locator(".project-item").filter(has_text=name.split("_")[0]).first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
    page.wait_for_timeout(600)


def reveal_bar(page):
    """The project bar is auto-hide chrome -- opacity 0 until the pointer is on
    it -- so an unattended click is intercepted. A writer reveals it by hovering;
    so do we (force=True skips the hover-actionability wait on the transparent
    box, which is the trap that made this flow look broken before)."""
    page.locator("#project-bar").hover(force=True)
    page.wait_for_timeout(300)


def wait_active(page, wrap, expected, timeout=6.0):
    """Poll until the active pill's text contains `expected`; return it."""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        active = wrap.locator(".branch-pill.active")
        last = active.first.inner_text().strip() if active.count() else ""
        if expected in last:
            return last
        page.wait_for_timeout(150)
    return last


def run(base):
    name = seed(base, "Branch UI Probe")
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, base, name)
        reveal_bar(page)

        wrap = page.locator("#branch-switcher")
        # --- the switcher renders, and offers a way to make a second branch ---
        check("branch switcher is present", wrap.count() == 1)
        check("a 'main' branch pill renders",
              wrap.locator(".branch-pill").filter(has_text="main").count() >= 1)
        fork = wrap.locator(".branch-pill.add")
        check("the fork button is offered (the M2 defect: a switcher with nothing to switch to)",
              fork.count() == 1, f"count={fork.count()}")

        # --- fork: open the modal, name it, create ---------------------------------
        # No message has been sent, so state.currentSession is null here on purpose.
        fork.first.click()
        page.wait_for_timeout(400)
        check("clicking fork opens #fork-modal (the z-index fix: a modal above app chrome)",
              page.locator("#fork-modal").is_visible())

        branch_name = "alt-%d" % (int(time.time()) % 100000)
        page.locator("#fork-name-input").fill(branch_name)
        page.locator("#fork-save").click()
        page.wait_for_timeout(1800)

        # The error banner is how a failed create surfaces (createFork -> showError).
        # Reading it names the cause instead of leaving "nothing happened".
        err_text = ""
        if page.locator("#error-banner").is_visible():
            err_text = page.locator("#error-banner-text").inner_text().strip()
        check("the fork reports no error", err_text == "", err_text)

        check("the fork modal closes after a successful create",
              not page.locator("#fork-modal").is_visible())
        names = wrap.locator(".branch-pill").all_inner_texts()
        check("the new branch pill appears in the switcher",
              any(branch_name in n for n in names), str(names))

        # --- merge-peek: the pill explains where the branch came from -------------
        alt_pill = wrap.locator(".branch-pill").filter(has_text=branch_name).first
        title = alt_pill.get_attribute("title") or ""
        check("merge-peek names the parent branch and the fork point",
              "forked from" in title and "main" in title, title)

        # --- switch to the fork, then back to main --------------------------------
        reveal_bar(page)
        alt_pill.click()
        got = wait_active(page, wrap, branch_name)
        check("switching moves the active pill to the fork", branch_name in got, got)

        reveal_bar(page)
        wrap.locator(".branch-pill").filter(has_text="main").first.click()
        got = wait_active(page, wrap, "main")
        check("switching back moves the active pill to main", "main" in got, got)

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
