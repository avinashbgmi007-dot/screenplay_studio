"""P1.6 gate — the Evidence dock's sections REALLY collapse (plan §5).

The dock's own comment promised "sections stack vertically and collapse under one
header each" while every `.dock-section-title` was a plain div: nothing collapsed,
nothing persisted. This suite pins the contract that makes the sentence true:

  * every ledger section is `.dock-section[data-key][data-open="true|false"]`
  * its header is a real <button> carrying aria-expanded + a chevron
  * the default is CLOSED — and the three orientation surfaces (arrival strip,
    the ONE filter row, the current-scene strip) are NOT sections: they stay
    always visible, so they must have no `.dock-section` ancestor
  * clicking the head flips data-open, follows with aria-expanded, and really
    hides/shows the body (the cards inside are unreachable while closed)
  * the choice is written to prefs["dock_section_<key>"] and survives a reload
  * the height animation sits behind `prefers-reduced-motion: no-preference`:
    under `reduce` the body carries no transition at all

Run:  python tests/e2e_browser_dock_sections.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)
"""
import os

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, clicked, launch, note, open_studio

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok

PREFS_JS = "JSON.parse(localStorage.getItem('screenplay_studio.prefs.v1') || '{}')"


def seed_and_analyze(base, title):
    """Upload the fixture and run the demo-model analysis to completion.

    The title is a display hint — the server names the project (safe-id
    charset), so the returned name is always used (same contract as
    e2e_browser_phase6_evidence.py).
    """
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    name = r.json().get("project") or r.json().get("name") or title
    r2 = requests.post(f"{base}/api/projects/{name}/analyze",
                       json={"force": True}, timeout=300)
    assert r2.status_code in (200, 201), r2.text[:400]
    return name


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    row = page.locator(".project-item").filter(has_text=name.split("_")[0])
    if not row.count():
        row = page.locator(".project-item").filter(has_text=name.replace("_", " "))
    row.first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def open_dock(page):
    page.locator("#right-edge-affordance").click()
    page.wait_for_selector("#context-dock.open", timeout=5000)
    page.wait_for_timeout(450)  # the dock animates width 0 → 380px


def section_head_is_a_button(page):
    """Every header is a real <button type=button> whose aria-expanded matches
    its section's data-open — one attribute the CSS, the tests and the screen
    reader all read."""
    return page.evaluate(
        """() => {
             const hs = [...document.querySelectorAll(
               '.dock-lens[data-lens="evidence"] .dock-section-head')];
             return hs.length > 0 && hs.every((h) => h.tagName === "BUTTON"
               && h.type === "button"
               && h.getAttribute("aria-expanded")
                  === h.closest(".dock-section").getAttribute("data-open"));
           }""")


def transition_duration(page, selector):
    return page.evaluate(
        """(sel) => {
             const el = document.querySelector(sel);
             return el ? getComputedStyle(el).transitionDuration : "missing";
           }""", selector)


def seconds(value):
    """'0.18s' / '1e-06s' / '120ms' -> seconds (None when unparsable).

    The duration is compared numerically because the app has its own global
    reduced-motion clamp (`style.css`: `* { transition-duration: 0.001ms
    !important }`), so under `reduce` the computed value is 1e-06s, not 0s.
    """
    v = (value or "").split(",")[0].strip()
    try:
        if v.endswith("ms"):
            return float(v[:-2]) / 1000.0
        if v.endswith("s"):
            return float(v[:-1])
    except ValueError:
        return None
    return None



def run(base):
    name = seed_and_analyze(base, "Ledger Collapse")
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, base, name)
        open_dock(page)
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        # the ledger assembles from the report — bounded wait, so a missing
        # section reports as a NAMED failure instead of crashing the run
        try:
            page.wait_for_selector('.dock-lens[data-lens="evidence"] .dock-section[data-key]',
                                   timeout=20000)
        except Exception:
            note("the ledger rendered no collapsible section (data-key)",
                 "the checks below fail by name")

        # --- 1. the section contract ----------------------------------------
        n_secs = lens.locator(".dock-section").count()
        keyed = lens.locator(".dock-section[data-key]")
        n_keyed = keyed.count()
        check("the ledger renders its collapsible sections",
              n_keyed >= 5, f"{n_keyed} keyed of {n_secs} .dock-section")
        check("every .dock-section IS a collapsible section (data-key on all)",
              n_secs == n_keyed and n_keyed > 0, f"{n_keyed}/{n_secs} keyed")
        keys = [keyed.nth(i).get_attribute("data-key") for i in range(n_keyed)]
        note("section keys", ", ".join(k or "?" for k in keys))
        states = [keyed.nth(i).get_attribute("data-open") for i in range(n_keyed)]
        check("every section declares data-open true|false",
              bool(states) and all(v in ("true", "false") for v in states), str(states))
        check("every section starts CLOSED (P1.6 default)",
              bool(states) and all(v == "false" for v in states), str(states))
        for key in ("fix-queue", "by-category", "coverage"):
            check(f"the plan's section set includes {key!r}", key in keys, str(keys))
        check("the fix-queue section keeps its hook class",
              lens.locator(".dock-section-fixqueue").count() == 1,
              lens.locator(".dock-section-fixqueue").count())

        check("every header is a real <button> with aria-expanded",
              section_head_is_a_button(page))
        chevrons = lens.locator(".dock-section .dock-section-head .dock-section-chevron")
        check("every header carries a chevron",
              n_keyed > 0 and chevrons.count() == n_keyed,
              f"{chevrons.count()} chevrons for {n_keyed} sections")
        check("every craft panel lives inside a collapsible section",
              page.evaluate(
                  """() => {
                       const ps = [...document.querySelectorAll(
                         '.dock-lens[data-lens="evidence"] .craft-panel')];
                       return ps.length > 0 && ps.every((p) => {
                         const s = p.closest(".dock-section");
                         return s && s.getAttribute("data-key");
                       });
                     }"""))

        # --- 2. the orientation surfaces are NOT sections --------------------
        check("the ONE filter row stays outside the collapsibles",
              page.evaluate(
                  """() => { const r = document.querySelector(".dock-filter-row");
                       return !!r && r.offsetParent !== null && !r.closest(".dock-section"); }"""))
        check("the current-scene strip stays outside the collapsibles",
              page.evaluate(
                  """() => { const s = document.querySelector(".dock-evidence-scene");
                       return !!s && !s.closest(".dock-section"); }""")
              and lens.locator(".dock-evidence-scene").is_visible())

        # --- 3. by-category: closed → open, for real -------------------------
        sec = lens.locator('.dock-section[data-key="by-category"]')
        check("the by-category section exists exactly once", sec.count() == 1, sec.count())
        if not sec.count():
            check("the collapse contract was exercised", False,
                  "no by-category section to open (the checks above failed first)")
            check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
            browser.close()
            checks.finish()
        head = sec.locator(".dock-section-head")
        body = sec.locator(".dock-section-body")
        card = sec.locator(".finding-note").first
        check("it starts data-open=false", sec.get_attribute("data-open") == "false",
              sec.get_attribute("data-open"))
        check("its body is hidden while closed",
              body.count() == 1 and not body.is_visible())
        check("the cards inside are unreachable while closed",
              card.count() > 0 and not card.is_visible(),
              f"cards={card.count()}")
        check("clicking the head opens the section",
              clicked(head) and sec.get_attribute("data-open") == "true",
              sec.get_attribute("data-open"))
        page.wait_for_timeout(350)  # the body's height animation settles
        check("aria-expanded follows data-open",
              head.get_attribute("aria-expanded") == "true",
              head.get_attribute("aria-expanded"))
        check("the body is actually shown", body.is_visible())
        check("and so are the cards inside it", card.count() > 0 and card.is_visible())

        stored = page.evaluate(f"() => ({PREFS_JS})['dock_section_by-category']")
        check("the open state is written to prefs[dock_section_<key>]",
              stored is True, repr(stored))

        # --- 4. the choice survives a reload ---------------------------------
        page.reload()
        page.wait_for_load_state("networkidle")
        # the session picks the project back up; if this build lands on the desk
        # instead, reopen it by hand — the PREF is what is under test
        try:
            page.wait_for_selector("#manuscript-container .scene-page", timeout=8000)
        except Exception:
            note("reload landed on the desk", "reopening the project by hand")
            open_project(page, base, name)
        open_dock(page)
        page.wait_for_selector('.dock-lens[data-lens="evidence"] .dock-section[data-key]',
                               timeout=20000)
        sec = lens.locator('.dock-section[data-key="by-category"]')
        check("the open state survives page.reload()",
              sec.count() == 1 and sec.get_attribute("data-open") == "true",
              sec.get_attribute("data-open") if sec.count() else "no section")
        check("the body is open again after the reload (not just the attribute)",
              sec.count() == 1 and sec.locator(".dock-section-body").is_visible())
        keyed = lens.locator(".dock-section[data-key]")
        others = [
            keyed.nth(i).get_attribute("data-open")
            for i in range(keyed.count())
            if keyed.nth(i).get_attribute("data-key") != "by-category"
        ]
        check("the sections the writer never opened are still closed",
              all(v == "false" for v in others), str(others))

        # --- 5. closing persists too -----------------------------------------
        check("clicking again closes it",
              clicked(sec.locator(".dock-section-head"))
              and sec.get_attribute("data-open") == "false")
        page.wait_for_timeout(350)
        check("its body is hidden again", not sec.locator(".dock-section-body").is_visible())
        check("the closed state is written back to prefs too",
              page.evaluate(f"() => ({PREFS_JS})['dock_section_by-category']") is False,
              page.evaluate(f"() => ({PREFS_JS})['dock_section_by-category']"))

        # --- 6. motion: the height animation is opt-in -----------------------
        body_sel = '.dock-section[data-key="by-category"] .dock-section-body'
        page.emulate_media(reduced_motion="reduce")
        reduced = transition_duration(page, body_sel)
        check("under prefers-reduced-motion: reduce the body has no height animation",
              (seconds(reduced) is not None and seconds(reduced) < 0.01), reduced)
        page.emulate_media(reduced_motion="no-preference")
        animated = transition_duration(page, body_sel)
        check("with motion allowed the collapse animates (height transition present)",
              (seconds(animated) is not None and seconds(animated) >= 0.1), animated)

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as studio_base:
        run(studio_base)
