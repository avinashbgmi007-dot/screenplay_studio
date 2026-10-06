"""E2E gate — the feedback ledger, in a real browser, against a real server.

Gate 9 exists for the fact Amendment 6 measured: across two real runs of the same
model on the same script, 65 % of the writer's marks had no counterpart. So
"nothing lost" cannot mean every note COMES BACK — it must mean every note stays
ACCOUNTED FOR. The Python suite proves the reconcile arithmetic and the store
discipline; the route test proves the JSON. Neither proves the WRITER can see it,
and an accounting nobody can read is not an accounting. This suite drives the
whole path for real:

    feedback_ledger.json on disk
      -> GET /feedback/ledger (loads the store, derives the reconcile on read)
      -> client state.feedbackLedger
      -> the "Feedback across runs" dock section, its buckets and its note

It does NOT seed the client. The ledger is written to the project directory and
the page reloaded, so every hop above is exercised — a client-side seed would
pass even if the route silently failed.

What it pins, in the order the risk matters:

1. ONE RUN -> NO SECTION. There is nothing to reconcile against a single run, and
   inventing a comparison against nothing is the failure mode the gate exists to
   avoid. The surface is a fact about the history, not a permanent empty header.
2. TWO RUNS -> THE SECTION, naming both run numbers and the run count.
3. THE BUCKETS RENDER with their counts: same / maybe / likely_resolved /
   not_re_raised / new.
4. `not_re_raised` IS VISIBLE — the honest "the model moved on" case, which is
   the whole reason a ledger is needed instead of a matcher. This is the one
   bucket a matcher-only design would silently lose.
5. `likely_resolved` REQUIRES A MARK — a note the writer marked addressed that
   did not come back, the payoff the writer actually feels.
6. THE NOTE says nothing is lost and names feedback_ledger.json.

Run:  python tests/e2e_browser_feedback_ledger.py   (boots its own demo studio;
      E2E_BASE is refused — the on-disk injection needs a studio we started)
"""
import json
import os
import sys
import tempfile

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import (Checks, launch, open_dock_section,  # noqa: E402
                                start_studio, studio_headers)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def _thread(tid, category, issue, scenes, quote=None):
    return {"id": tid, "category": category, "issue": issue, "severity": "medium",
            "scene_key": None, "scene_refs": list(scenes), "quote": quote}


# Run 1 (previous). Four threads, each chosen so it lands in exactly one bucket:
#   t_same      -> re-raised with the SAME id            -> same
#   t_resolved  -> gone, and the writer marked it        -> likely_resolved
#   t_gone      -> gone, never marked                    -> not_re_raised
#   t_maybe     -> a weak counterpart exists in run 2    -> maybe
RUN1 = [
    _thread("t_same", "dialogue", "MARA states the subtext aloud in the opening exchange", [1],
            quote="I am your sister."),
    _thread("t_resolved", "structure", "Act two sags in the middle and loses momentum", [5]),
    _thread("t_gone", "theme", "The theme is never stated anywhere in the script", [2]),
    _thread("t_maybe", "voice", "The voice drifts in the third act", [9]),
]

# Run 2 (latest). Three threads:
#   t_same     -> unchanged            -> same
#   t_maybe2   -> near-identical voice note, same scene -> maybe
#   t_new      -> no prior counterpart -> new
RUN2 = [
    _thread("t_same", "dialogue", "MARA states the subtext aloud in the opening exchange", [1],
            quote="I am your sister."),
    _thread("t_maybe2", "voice", "The voice drifts in the third act slightly", [9]),
    _thread("t_new", "pacing", "A brand new note about the chase sequence", [7]),
]

# The mark that turns a vanished thread into `likely_resolved` rather than
# `not_re_raised`. Keyed on the ledger's own thread id — the id the writer acted
# on. The legacy-id migration only remaps ids derived from the report, so an
# id it does not recognise passes through untouched.
MARKED_ADDRESSED = "t_resolved"


def project_paths(projects_dir):
    """The one project's directory, derived not assumed (the server names it)."""
    for d in sorted(os.listdir(projects_dir)):
        p = os.path.join(projects_dir, d, "report.findings.json")
        if os.path.isfile(p):
            return os.path.dirname(p)
    raise AssertionError(f"no report.findings.json under {projects_dir}")


def seed_and_analyze(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    name = r.json().get("project") or r.json().get("name") or title
    r2 = requests.post(f"{base}/api/projects/{name}/analyze", headers=studio_headers(base),
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
    page.wait_for_timeout(450)


SECTION_JS = """() => {
  const sec = document.querySelector(
    '.dock-lens[data-lens="evidence"] .dock-section[data-key="feedback-ledger"]');
  if (!sec) return null;
  const heads = [...sec.querySelectorAll('.dock-ledger-head')].map((n) => n.textContent);
  const rows = [...sec.querySelectorAll('.dock-ledger-row')].map((r) => ({
    cls: r.className,
    issue: (r.querySelector('.dock-ledger-issue') || {}).textContent || '',
    sim: (r.querySelector('.dock-ledger-sim') || {}).textContent || '',
  }));
  return {
    title: (sec.querySelector('.dock-section-title') || {}).textContent || '',
    open: sec.getAttribute('data-open'),
    heads,
    rows,
    note: (sec.querySelector('.dock-ledger-note') || {}).textContent || '',
  };
}"""


def write_ledger(proj_dir, runs):
    with open(os.path.join(proj_dir, "feedback_ledger.json"), "w", encoding="utf-8") as f:
        json.dump({"runs": runs}, f)


def run(base, projects_dir):
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        name = seed_and_analyze(base, "Ledger fixture")
        open_project(page, base, name)
        open_dock(page)
        proj = project_paths(projects_dir)

        # --- 1. one run: nothing to reconcile, so no section ---
        write_ledger(proj, [{"run": 1, "at": 1.0, "model_used": "demo",
                             "signature": "s1", "threads": RUN1}])
        served = requests.get(f"{base}/api/projects/{name}/feedback/ledger",
                              headers=studio_headers(base), timeout=15).json()
        check("one run -> the route reports no reconcile (nothing to compare against)",
              served.get("reconcile") is None and served.get("runs") == 1, str(served.get("runs")))
        page.reload()
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
        page.wait_for_timeout(700)
        open_dock(page)
        page.evaluate("() => setEvidenceTier(2)")
        page.wait_for_timeout(600)
        check("one run renders NO ledger section (no invented comparison)",
              page.evaluate(SECTION_JS) is None, "section present with a single run")

        # --- 2. two runs + the mark: the section appears ---
        write_ledger(proj, [
            {"run": 1, "at": 1.0, "model_used": "demo", "signature": "s1", "threads": RUN1},
            {"run": 2, "at": 2.0, "model_used": "demo", "signature": "s2", "threads": RUN2},
        ])
        with open(os.path.join(proj, "finding_marks.json"), "w", encoding="utf-8") as f:
            json.dump({MARKED_ADDRESSED: "addressed"}, f)

        served = requests.get(f"{base}/api/projects/{name}/feedback/ledger",
                              headers=studio_headers(base), timeout=15).json()
        rc = served.get("reconcile") or {}
        check("two runs -> the route reconciles them", bool(rc), str(served.get("runs")))
        counts = rc.get("counts") or {}
        check("the buckets partition the prior run (nothing lost)",
              counts.get("same", 0) + counts.get("maybe", 0)
              + counts.get("likely_resolved", 0) + counts.get("not_re_raised", 0)
              == rc.get("prev_total") == 4,
              str({**counts, "prev_total": rc.get("prev_total")}))
        check("the marked-and-gone note is `likely_resolved`, the unmarked one is not",
              counts.get("likely_resolved") == 1 and counts.get("not_re_raised") == 1,
              str(counts))

        # --- 3-6. reload so the CLIENT fetches it, then read the DOM ---
        page.reload()
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
        page.wait_for_timeout(700)
        open_dock(page)
        # The ledger sits at the lens foot inside the collapsed "Context"
        # disclosure, so summon Tier 2 the way the writer does — that OPENS
        # Context and makes the nested header a real click target.
        page.evaluate("() => setEvidenceTier(2)")
        page.wait_for_timeout(600)

        sec = page.evaluate(SECTION_JS)
        check("the Feedback-across-runs section exists in the Evidence lens",
              sec is not None, str(sec))
        check("its header names both runs and the run count",
              sec and "run 2 vs run 1" in sec["title"] and "2 runs recorded" in sec["title"],
              str(sec and sec["title"]))
        check("the count is legible in the header while the section is CLOSED",
              sec and sec["open"] == "false", str(sec and sec["open"]))

        # A REAL click on the header — the same control a writer presses.
        opened = open_dock_section(page, "feedback-ledger")
        page.wait_for_timeout(350)
        sec = page.evaluate(SECTION_JS)
        check("clicking its header opens it for real", opened and sec["open"] == "true",
              f"opened={opened} state={sec and sec['open']}")

        heads = (sec or {}).get("heads") or []
        joined = " | ".join(heads)
        check("the same bucket renders with its count", "1 returned" in joined, joined)
        check("the maybe bucket renders with its count", "1 possibly the same point" in joined, joined)
        check("the likely_resolved bucket renders (the payoff the writer feels)",
              "1 you marked" in joined, joined)
        check("the not_re_raised bucket renders — the honest 'the model moved on' case",
              "1 did not come back (you had not marked them)" in joined, joined)
        check("the new bucket renders with its count", "1 new this run" in joined, joined)

        rows = (sec or {}).get("rows") or []
        check("the vanished, unmarked note is LISTED, not dropped",
              any("never stated" in r["issue"] for r in rows),
              str([r["issue"][:40] for r in rows]))
        check("a maybe row shows its similarity, so a candidate reads as a candidate",
              any("similar" in r["sim"] for r in rows),
              str([r["sim"] for r in rows]))
        check("the note says nothing is lost and names the file",
              "Nothing is lost" in (sec or {}).get("note", "")
              and "feedback_ledger.json" in (sec or {}).get("note", ""),
              str((sec or {}).get("note")))

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        print("E2E_BASE is set: this suite must boot its own studio to write the "
              "ledger to disk. Unset E2E_BASE and re-run.")
        sys.exit(2)
    with tempfile.TemporaryDirectory(prefix="feedback_ledger_e2e_") as tmp:
        projects = os.path.join(tmp, "projects")
        os.makedirs(projects, exist_ok=True)
        with start_studio(projects_dir=projects) as studio:
            run(studio.base_url, studio.projects_dir)
