"""Task 20 (spec §11 width budget): the manuscript never falls below half the
window, whatever the right-hand zone is doing — including when a persona is
open beside it.

The plan asks for the measurement at the desk's worst gesture: a finding card's
🩺 escalation, which opens Dr. Sushruta WITH the finding pinned. Two things must
survive it: the paper keeps >= 50% of the viewport, and the quote that rode into
the consult is actually visible atop the chat (a pinned finding the writer can't
see is a claim, not a feature).

Run:  python tests/e2e_browser_width_budget.py
"""
import json
import os
import re
import sys
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                open_dock_section_holding, start_studio,
                                studio_headers)
from playwright.sync_api import sync_playwright  # noqa: E402

LENSES = ("evidence", "notes", "sameer", "sushruta")
DOCTOR_BTN = 'button[title^="Ask Dr. Sushruta"]'


def post(base, path, body=None, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode() or "{}")


def get(base, path, headers=None):
    req = urllib.request.Request(base + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def norm(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


MEASURE = """() => {
  const r = (sel) => { const n = document.querySelector(sel);
                       return n ? n.getBoundingClientRect().width : 0; };
  const dock = document.querySelector('#context-dock');
  // The pin must be on the surface the writer is LOOKING AT. A rect-width check
  // anywhere in the document passes for the card parked in the closed room
  // drawer, which is not a feature the writer can see.
  const lens = document.querySelector('#context-dock .dock-lens:not([hidden])');
  const card = lens ? [...lens.querySelectorAll('.quote-card')]
                       .find((e) => !e.hidden && e.getBoundingClientRect().width > 0)
                    : null;
  const q = card ? card.querySelector('.quote-card-text') : null;
  return {
    vw: window.innerWidth,
    ms: r('#manuscript-container'),
    dock: r('#context-dock'),
    dockOpen: !!(dock && dock.classList.contains('open')),
    quote: q ? q.textContent.trim() : null,
    quoteVisible: !!q,
  };
}"""


def wait_dock_open(page):
    """Measure a settled dock, never a mid-transition one: `#context-dock`
    animates width/min-width over 0.25s and the ledger render can starve those
    frames, so a fixed timeout reads 1px and proves nothing."""
    page.wait_for_function(
        """() => {
          const d = document.querySelector('#context-dock');
          if (!d || !d.classList.contains('open')) return false;
          return d.getBoundingClientRect().width >= Math.min(380, innerWidth * 0.86) - 1;
        }""", timeout=15000)


def sweep(checks, page, name):
    """Every right-zone state, measured at the desk's own width budget."""
    for lens in LENSES:
        page.evaluate("(l) => openDock(l)", lens)
        wait_dock_open(page)
        m = page.evaluate(MEASURE)
        checks.ok(f"{name}: manuscript >= 50% with the {lens} lens open",
                  m["ms"] >= m["vw"] * 0.5,
                  f"ms={m['ms']:.0f} vw={m['vw']} dock={m['dock']:.0f}")


def escalate(checks, page, quotes, name):
    """The plan's Step 1 gesture: 🩺 from a finding card, then measure."""
    page.evaluate("() => openDock('evidence')")
    wait_dock_open(page)
    # the ledger's sections start collapsed (P1.6): a mounted-but-closed card is
    # in the DOM and unclickable, so open the one holding it before reaching in.
    open_dock_section_holding(page, DOCTOR_BTN)
    page.wait_for_timeout(250)
    btn = page.locator(f'.dock-lens[data-lens="evidence"] {DOCTOR_BTN}').first
    checks.ok(f"{name}: a finding card offers the escalation", btn.count() == 1,
              f"count={btn.count()}")
    if not btn.count():
        return
    btn.click()
    page.wait_for_timeout(600)
    m = page.evaluate(MEASURE)
    checks.ok(f"{name}: the consult keeps the manuscript >= 50%",
              m["ms"] >= m["vw"] * 0.5,
              f"ms={m['ms']:.0f} vw={m['vw']} dock={m['dock']:.0f}")
    checks.ok(f"{name}: the dock really moved to the doctor",
              m["dockOpen"] and m["dock"] > 0, f"dock={m['dock']:.0f}")
    checks.ok(f"{name}: the pinned quote is visible atop the chat",
              bool(m["quoteVisible"] and m["quote"]),
              f"quote={m['quote']!r}")
    if m["quote"]:
        shown = norm(m["quote"].rstrip("\u2026 "))
        # whatever the composer pins must be a finding's own evidence, never
        # something the client invented
        checks.ok(f"{name}: the pinned quote is the finding's evidence text",
                  any(c[:len(shown)] == shown for c in quotes if shown),
                  f"shown={shown[:60]!r}")


def _quotes(base, name):
    report = get(base, f"/api/projects/{name}/report")
    out = []
    for f in report.get("findings") or []:
        out.append(norm(f.get("evidence_quote") or f.get("issue") or ""))
    return [q for q in out if q]


def run(base, projects_dir, headers):
    checks = Checks()
    name = post(base, "/api/sample", headers=headers).get("project")
    checks.ok("sample project created", bool(name), f"got {name!r}")
    if not name:
        checks.finish()
        return
    post(base, f"/api/projects/{name}/analyze", headers=headers)
    quotes = _quotes(base, name)
    checks.ok("the analyzed report has evidence to pin", len(quotes) > 0,
              f"{len(quotes)} quotes")

    with sync_playwright() as pw:
        # 1200 is the tightest in-flow case: below it the dock stops competing
        # for the row (overlay / bottom sheet), so the paper cannot gain relief.
        for width in (1200, 1440, 1920):
            browser, page, errors = launch(pw)
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(base)
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_function("() => !!(state.report && state.report.findings)",
                                   timeout=30000)
            tag = f"{width}px"
            sweep(checks, page, tag)
            escalate(checks, page, quotes, tag)
            assert_no_js_errors(checks, errors, f"no JS errors at {tag}")
            browser.close()

    checks.finish()


if __name__ == "__main__":
    import tempfile
    with start_studio(projects_dir=tempfile.mkdtemp(prefix="width_budget_")) as studio:
        run(studio.base_url, studio.projects_dir, studio_headers(studio.base_url))
