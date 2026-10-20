"""G5 fold gate: the first actionable finding must finish above 900px.

The subject is a fixed analyzed project, copied to a temp projects dir for
each run. The gate asserts the served revision, the correct first admitted
finding, the hidden ungrounded controls, font readiness, the 1440x900 default
worklist, scroll 0, and the card/component rectangles. DOM/geometry only.

Run: python tests/e2e_browser_g5_fold.py
"""
import json
import os
import shutil
import subprocess
import tempfile

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import (Checks, launch, open_dock_section,
                                start_studio)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "fixtures", "g5_fixed_project")

checks = Checks()
check = checks.ok


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


def prepare_projects_dir(tmp):
    shutil.copytree(FIXTURE, tmp, dirs_exist_ok=True)
    project = os.path.join(tmp, "G5_Fixed")
    manifest_path = os.path.join(project, "project.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["project_dir"] = project
    manifest["server_url"] = ""
    for stage in (manifest.get("stages") or {}).values():
        stage["output_paths"] = {}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    for root, _dirs, files in os.walk(project):
        for name in files:
            if name.endswith(".lock"):
                os.remove(os.path.join(root, name))


GEOM = """() => {
  const round = (n) => Math.round(n);
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: round(r.top), bottom: round(r.bottom),
             height: round(r.height), width: round(r.width) };
  };
  const all = [...document.querySelectorAll(
    '.dock-section-fixqueue .finding-note.queue-row')];
  const visible = all.filter((el) => el.getClientRects().length
    && el.getBoundingClientRect().height > 0);
  const first = visible[0] || null;
  const raw = (state.report && state.report.findings) || state.findings || [];
  const idx = first ? Number(first.dataset.findingIndex) : null;
  const f = idx != null ? (raw[idx] || {}) : {};
  const lens = document.querySelector('.dock-lens[data-lens="evidence"]');
  const body = document.querySelector('#context-dock .dock-body');
  const card = rect(first);
  const part = (sel) => rect(first ? first.querySelector(sel) : null);
  const chrome = lens ? [...lens.children].map((el) => {
    const r = el.getBoundingClientRect();
    return { cls: String(el.className || ''), top: round(r.top),
             bottom: round(r.bottom) };
  }).filter((x) => x.bottom > 0 && (!card || x.top < card.top)) : [];
  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    fonts: document.fonts.status,
    scroll: { window: window.scrollY,
              lens: lens ? lens.scrollTop : null,
              body: body ? body.scrollTop : null },
    rows: { total: all.length, visible: visible.length },
    first: card,
    finding: { index: idx, category: f.category, rule_id: f.rule_id,
               check_id: f.check_id, severity: f.severity,
               grounded: !f.ungrounded, verification: f.verification || null,
               quote: f.evidence_quote || null },
    ungrounded: {
      total: raw.filter((x) => x && x.ungrounded).length,
      visible: visible.filter((row) => {
        const g = raw[Number(row.dataset.findingIndex)];
        return g && g.ungrounded;
      }).length
    },
    parts: { top: part('.finding-note-top'), issue: part('.finding-note-text'),
             deep: part('.finding-deep'), why: part('.finding-deep-why'),
             observation: part('.finding-deep-observation'),
             quote: part('.finding-deep-quote'),
             flags: part('.finding-row-flags'),
             verdict: part('.finding-verdict-row'),
             actions: part('.finding-note-actions'),
             intent: part('.finding-intent-hint'),
             rank: part('.dock-rank-reason') },
    chromeAbove: chrome
  };
}"""


def run(base):
    served = (requests.get(f"{base}/api/health", timeout=15).json() or {}).get("code_rev")
    head = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    check("G5: served revision matches HEAD", served == head,
          f"served={served} head={head}")

    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, base, "G5_Fixed")
        page.evaluate("() => document.fonts.ready.then(() => document.fonts.status)")
        page.locator("#right-edge-affordance").click()
        page.wait_for_selector("#context-dock.open", timeout=5000)
        page.wait_for_timeout(450)
        check("G5: fix queue opens from its header",
              open_dock_section(page, "fix-queue"))
        page.wait_for_selector(
            ".dock-section-fixqueue .finding-note.queue-row", timeout=10000)
        page.wait_for_timeout(500)

        geom = page.evaluate(GEOM)
        print("G5 geometry:", json.dumps(geom, sort_keys=True), flush=True)

        ident = geom["finding"]
        check("G5: first admitted finding is index 0/continuity/timeline",
              ident["index"] == 0 and geom["rows"]["visible"] == 1
              and ident["category"] == "continuity"
              and ident["rule_id"] == "timeline_consistency"
              and ident["check_id"] == "unmarked_time_flip",
              json.dumps(ident, sort_keys=True))
        check("G5: first finding is grounded and verified",
              ident["grounded"]
              and (ident["verification"] or {}).get("status") == "verified"
              and float((ident["verification"] or {}).get("confidence") or 0) >= 0.99,
              json.dumps(ident, sort_keys=True))
        check("G5: hidden ungrounded controls stay hidden",
              geom["ungrounded"]["total"] == 6
              and geom["ungrounded"]["visible"] == 0,
              json.dumps(geom["ungrounded"], sort_keys=True))
        check("G5: default worklist, fonts ready, 1440x900, scroll 0",
              geom["viewport"] == {"w": 1440, "h": 900}
              and geom["fonts"] == "loaded"
              and geom["scroll"]["window"] == 0
              and geom["scroll"]["body"] == 0
              and geom["scroll"]["lens"] == 0,
              json.dumps({"viewport": geom["viewport"],
                          "fonts": geom["fonts"],
                          "scroll": geom["scroll"]}, sort_keys=True))
        first = geom["first"]
        check("G5: first card bottom < 900",
              bool(first) and first["bottom"] < 900,
              f"bottom={first['bottom'] if first else None} "
              f"top={first['top'] if first else None} "
              f"height={first['height'] if first else None} "
              f"parts={json.dumps(geom['parts'], sort_keys=True)}")
        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="g5_fixed_") as tmp:
        prepare_projects_dir(tmp)
        with start_studio(projects_dir=tmp) as studio:
            run(studio.base_url)
