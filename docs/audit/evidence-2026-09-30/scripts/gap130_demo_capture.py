#!/usr/bin/env python3
# ruff: noqa: E701, E702
import argparse
import hashlib
import json
import pathlib
import sys
import requests
from PIL import Image, PngImagePlugin
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))
from e2e_browser_common import start_studio, studio_headers  # noqa: E402

parser = argparse.ArgumentParser(description="Capture disclosed Gap 130 demo evidence")
parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("/tmp/gap130-candidates"))
OUT = parser.parse_args().out
OUT.mkdir(parents=True, exist_ok=True)
FIXTURE = ROOT / "tests/fixtures/pain_tenglish.fountain"
SCRIPT = """Title: Audit Loop Script
Author: Audit

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. HALLWAY - NIGHT

MARA walks to the door.

MARA
Some things are better left alone.

CUT TO:

EXT. STREET - DAWN

The city wakes. MARA lights a cigarette, hands shaking.

MARA
One more day. That's all I need.

CUT TO:

INT. OFFICE - DAY

The editor waits. MARA sits down slowly.

MARA
I finished it. Every page.
"""
SCRIPT_V2 = SCRIPT.replace("One more day. That's all I need.", "One more night. That is all I ask.")
MANIFEST = {}


def seed(base, title, content):
    r = requests.post(
        base + "/api/projects",
        files={"file": (title + ".fountain", content.encode(), "text/plain")},
        data={"title": title},
        headers=studio_headers(base),
        timeout=60,
    )
    assert r.status_code in (200, 201), r.text[:300]
    name = r.json()["project"]
    a = requests.post(
        f"{base}/api/projects/{name}/analyze", json={"force": True}, headers=studio_headers(base), timeout=300
    )
    assert a.status_code == 200, a.text[:300]
    report = requests.get(f"{base}/api/projects/{name}/report", headers=studio_headers(base), timeout=30).json()
    return name, report


def open_project(page, base, name):
    page.goto(base, wait_until="domcontentloaded")
    page.wait_for_selector("#shelf-trigger", timeout=20000)
    page.evaluate("(n) => openProject(n)", name)
    page.wait_for_selector("#manuscript-container .scene-page", timeout=25000)
    page.wait_for_function("(n) => state.currentProject === n && state.report && state.script", arg=name, timeout=20000)
    page.wait_for_timeout(400)


def open_dock(page):
    if not page.locator("#context-dock.open").count():
        page.locator("#right-edge-affordance").click()
        page.wait_for_selector("#context-dock.open", timeout=8000)
    page.wait_for_timeout(400)
    assert page.locator('.dock-lens[data-lens="evidence"]').is_visible()


def open_section(page, key):
    sec = page.locator(f'.dock-lens[data-lens="evidence"] .dock-section[data-key="{key}"]').first
    assert sec.count(), f"missing section {key}"
    if sec.get_attribute("data-open") != "true":
        sec.locator(".dock-section-head").click()
        page.wait_for_function(
            '(k) => document.querySelector(`.dock-lens[data-lens="evidence"] .dock-section[data-key="${k}"]`)?.dataset.open === "true"',
            arg=key,
            timeout=5000,
        )
    return sec


def watermark(page, title, detail):
    page.evaluate(
        """({title, detail}) => {
      document.getElementById('gap130-demo-watermark')?.remove();
      const w=document.createElement('aside'); w.id='gap130-demo-watermark';
      Object.assign(w.style,{position:'fixed',left:'56px',top:'8px',zIndex:'2147483647',
        padding:'8px 12px',background:'#6b2f00',color:'#fff4d6',border:'2px solid #ffd166',
        borderRadius:'6px',boxShadow:'0 2px 8px #0009',font:'700 13px/1.25 system-ui,sans-serif',
        maxWidth:'560px',pointerEvents:'none',letterSpacing:'.03em'});
      const a=document.createElement('div'); a.textContent=title; a.style.fontWeight='900';
      const b=document.createElement('div'); b.textContent=detail; b.style.fontWeight='600'; b.style.fontSize='11px';
      w.append(a,b); document.body.appendChild(w);
    }""",
        {"title": title, "detail": detail},
    )
    page.wait_for_timeout(150)


def save(page, filename, title, detail, full=False, seeded=False):
    watermark(page, title, detail)
    path = OUT / filename
    page.screenshot(path=str(path), full_page=full)
    # Preserve the visible overlay and add machine-readable provenance.
    im = Image.open(path)
    info = PngImagePlugin.PngInfo()
    for k, v in im.info.items():
        if isinstance(v, str):
            info.add_text(k, v)
    info.add_text("Gap130-Demo-Provenance", detail)
    info.add_text("Gap130-Capture-Label", title)
    im.save(path, pnginfo=info, optimize=True)
    MANIFEST[filename] = {
        "label": title,
        "provenance": detail,
        "seeded_ui_state": seeded,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": im.size,
        "bytes": path.stat().st_size,
    }
    print("CAPTURE", filename, im.size, MANIFEST[filename]["sha256"], detail)


with start_studio(timeout=60) as studio:
    base = studio.base_url
    # Built-in demo model run on a checked-in Fountain fixture for real, disclosed
    # demo coverage and character-dial payloads.
    pain_name, pain_report = seed(base, "Demo Evidence Fixture", FIXTURE.read_text())
    print(
        "DEMO FIXTURE",
        pain_name,
        "findings",
        len(pain_report.get("findings") or []),
        "dials",
        len(pain_report.get("character_dials") or []),
        "coverage",
        bool(pain_report.get("coverage")),
    )
    assert pain_report.get("character_dials") and pain_report.get("coverage")
    # The reproducible J4 audit journey uses its explicit four-scene fixture.
    loop_name, loop_report = seed(base, "Loop Script", SCRIPT)
    assert loop_report.get("findings")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # A-scene_function: real app renderer, browser-only synthetic finding.
        # It is explicitly disclosed in both the watermark and PNG metadata.
        open_project(page, base, pain_name)
        open_dock(page)
        injected = page.evaluate("""() => {
          const f={category:'scene_function',issue:'[DEMO UI SAMPLE] Scene 2 needs an active choice to turn its setting into a dramatic obstacle.',why_it_matters:'This seeded example demonstrates the Scene function category card; it is not an analyzer verdict.',severity:'medium',scene_refs:[2],evidence_quote:null,rule_id:null};
          state.report.findings.push(f); state.findings.push(f); renderDockEvidence();
          return {reportFindings:state.report.findings.length,stateFindings:state.findings.length};
        }""")
        assert injected["reportFindings"] == injected["stateFindings"]
        page.locator(".dock-tier-btn").filter(has_text="Context").click()
        page.wait_for_timeout(350)
        open_section(page, "by-category")
        cat = page.locator(".dock-cat-group").filter(has_text="Scene function").first
        assert cat.count() and "[DEMO UI SAMPLE]" in cat.inner_text(), "scene-function sample card not rendered"
        page.locator("#context-dock .dock-body").evaluate("(e)=>e.scrollTop=e.scrollHeight")
        page.wait_for_timeout(250)
        cat.locator(".finding-note").last.evaluate('(e)=>e.scrollIntoView({block:"center",inline:"nearest"})')
        page.wait_for_timeout(200)
        card = cat.locator(".finding-note").last
        rect = card.evaluate("(e)=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom}}")
        assert card.is_visible() and rect["top"] >= 70 and rect["bottom"] <= 850, f"scene-function card clipped: {rect}"
        save(
            page,
            "A-scene_function.png",
            "DEMO UI FIXTURE · SCENE FUNCTION",
            "Synthetic browser-only example; not model output and not original Gun-Pen material.",
            seeded=True,
        )

        # B-character-dials: actual built-in demo model payload, not hand-drawn.
        open_project(page, base, pain_name)
        open_dock(page)
        page.locator(".dock-tier-btn").filter(has_text="Context").click()
        page.wait_for_timeout(350)
        sec = open_section(page, "dials")
        sec.scroll_into_view_if_needed()
        page.wait_for_timeout(250)
        dial_rows = sec.locator(".dial-row")
        assert dial_rows.count() >= 2 and dial_rows.first.is_visible(), f"dials missing/count={dial_rows.count()}"
        assert "MARA" in sec.inner_text().upper()
        save(
            page,
            "B-character-dials.png",
            "DEMO · CHARACTER DIALS",
            "Built-in demo craft model on tests/fixtures/pain_tenglish.fountain; not original Gun-Pen material.",
        )

        # B-coverage: actual demo model coverage, framed by the matching section.
        open_project(page, base, pain_name)
        open_dock(page)
        page.locator(".dock-tier-btn").filter(has_text="Context").click()
        page.wait_for_timeout(350)
        cov = open_section(page, "coverage")
        cov.scroll_into_view_if_needed()
        page.wait_for_timeout(250)
        cov_text = cov.inner_text()
        assert cov.locator(".dock-cov-logline").count() and cov.locator(".dock-cov-frame").count()
        assert "A demo logline." in cov_text and "DRAMA" in cov_text.upper()
        save(
            page,
            "B-coverage.png",
            "DEMO · WRITING COVERAGE",
            "Built-in demo craft model coverage on tests/fixtures/pain_tenglish.fountain; not original Gun-Pen material.",
        )

        # A02 full Evidence lens: expand the real evidence disclosure tree and
        # assert all the named payloads before a full-page capture. A tall viewport
        # exposes the scroll-contained dock without altering its production CSS.
        page.set_viewport_size({"width": 1440, "height": 2600})
        open_project(page, base, pain_name)
        open_dock(page)
        page.locator(".dock-tier-btn").filter(has_text="Context").click()
        page.wait_for_timeout(350)
        for _ in range(5):
            sections = page.locator('.dock-lens[data-lens="evidence"] .dock-section')
            collapsed = []
            for i in range(sections.count()):
                s = sections.nth(i)
                if s.get_attribute("data-open") != "true":
                    collapsed.append(s)
            if not collapsed:
                break
            for s in collapsed:
                try:
                    s.locator(".dock-section-head").click(timeout=3000)
                except Exception:
                    pass
            page.wait_for_timeout(180)
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        assert lens.locator(".dock-cov-logline").count() and lens.locator(".dial-row").count()
        assert lens.locator('.dock-section[data-key="by-category"]').count()
        assert lens.locator('.dock-section[data-key="coverage"]').get_attribute("data-open") == "true"
        assert lens.locator('.dock-section[data-key="dials"]').get_attribute("data-open") == "true"
        page.evaluate(
            """() => { const b=document.querySelector('#context-dock .dock-body'); const c=document.querySelector('.dock-lens[data-lens=\"evidence\"] .dock-section[data-key=\"coverage\"]'); if(b && c){const br=b.getBoundingClientRect(), cr=c.getBoundingClientRect(); b.scrollTop += cr.top-br.top-120;} }"""
        )
        page.wait_for_timeout(250)
        save(
            page,
            "A02-evidence-lens-full.png",
            "DEMO · EVIDENCE LENS OVERVIEW",
            "Built-in demo model on tests/fixtures/pain_tenglish.fountain; disclosure sections expanded for audit; not original Gun-Pen material.",
            full=True,
        )
        page.set_viewport_size({"width": 1440, "height": 900})

        # J4 inline edit: real keyboard/pointer editor path; API confirms save.
        open_project(page, base, loop_name)
        page.locator("#manuscript-container").focus()
        page.keyboard.press("s")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_selector("#manuscript-container [class^=el-].inline-editing", timeout=5000)
        page.keyboard.press("Control+a")
        page.keyboard.type("MARA walks to the door. AUDITED")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1400)
        exported = requests.get(f"{base}/api/projects/{loop_name}/export?format=fountain", timeout=20)
        assert exported.status_code == 200 and "AUDITED" in exported.text, (
            "inline edit did not persist to Fountain export"
        )
        assert "AUDITED" in page.locator("#manuscript-container").inner_text(), (
            "edited text not visible in the manuscript"
        )
        save(
            page,
            "j4_inline_edit.png",
            "DEMO · INLINE EDIT SAVED",
            "Built-in demo model; Loop Script audit fixture; AUDITED text confirmed in persisted working copy.",
        )

        # J4 Beat Board: reorder via API as the audit does, verify UI order and
        # fountain export sequence, then capture the actual reordered board.
        bb = requests.get(f"{base}/api/projects/{loop_name}/beatboard", timeout=20).json()
        original = bb.get("order") or [s.get("scene_number") for s in bb.get("scenes") or []]
        assert len(original) >= 2, bb
        order = list(original)
        order[0], order[1] = order[1], order[0]
        put = requests.put(
            f"{base}/api/projects/{loop_name}/beatboard",
            json={"order": order},
            headers=studio_headers(base),
            timeout=20,
        )
        assert put.status_code == 200, put.text[:200]
        saved = requests.get(f"{base}/api/projects/{loop_name}/beatboard", timeout=20).json()
        order2 = saved.get("order") or [s.get("scene_number") for s in saved.get("scenes") or []]
        assert order2 == order, (order, order2)
        export = requests.get(f"{base}/api/projects/{loop_name}/beatboard/export?format=fountain", timeout=20)
        assert export.status_code == 200
        heads = {s.get("scene_number"): s.get("heading_raw") for s in (bb.get("cards") or []) if isinstance(s, dict)}
        if not heads:
            heads = {
                s.get("scene_number"): s.get("heading_raw") for s in (saved.get("cards") or []) if isinstance(s, dict)
            }
        hfirst = str(heads.get(order[0]) or "")[:24]
        hsecond = str(heads.get(order[1]) or "")[:24]
        assert (
            hfirst
            and export.text.find(hfirst) != -1
            and (export.text.find(hsecond) == -1 or export.text.find(hfirst) < export.text.find(hsecond))
        ), (hfirst, hsecond)
        page.evaluate("() => openBeatboardView()")
        page.wait_for_selector("#beatboard-view", timeout=8000)
        page.wait_for_selector("#beatboard-board .bb-card", timeout=8000)
        page.wait_for_function(
            '(o) => JSON.stringify([...document.querySelectorAll("#beatboard-board .bb-card")].map(c=>Number(c.dataset.num))) === JSON.stringify(o)',
            arg=order,
            timeout=10000,
        )
        assert page.locator("#bb-export").is_visible()
        save(
            page,
            "j4_beatboard_exported.png",
            "DEMO · BEAT BOARD REORDERED",
            f"Built-in demo model; Loop Script fixture; board order {order} verified and Fountain export sequence checked.",
        )

        # J4 draft upload auto-activates; reopen the writer desk and verify the
        # actual active draft text in the rendered manuscript before capture.
        dr = requests.post(
            f"{base}/api/projects/{loop_name}/drafts",
            files={"file": ("v2.fountain", SCRIPT_V2.encode(), "text/plain")},
            headers=studio_headers(base),
            timeout=60,
        )
        assert dr.status_code in (200, 201), dr.text[:200]
        drafts = requests.get(f"{base}/api/projects/{loop_name}/drafts", timeout=20).json()
        newnames = [d.get("name") for d in drafts.get("drafts", []) if d.get("name") != "original"]
        assert newnames, newnames
        v2 = newnames[-1]
        assert drafts.get("active_draft") == v2, drafts
        script = requests.get(f"{base}/api/projects/{loop_name}/script", timeout=20).json()
        assert "One more night. That is all I ask." in json.dumps(script)
        page.evaluate(
            """async () => { openCowriteRoom(); await loadScriptData(); renderManuscript(document.getElementById('manuscript-container')); }"""
        )
        page.wait_for_function(
            '(n) => state.drafts?.active_draft === n && state.script && JSON.stringify(state.script).includes("One more night")',
            arg=v2,
            timeout=15000,
        )
        assert page.evaluate("state.drafts.active_draft") == v2
        assert "One more night. That is all I ask." in page.locator("#manuscript-container").inner_text()
        save(
            page,
            "j4_draft_activated.png",
            "DEMO · DRAFT V2 ACTIVE",
            f"Built-in demo model; Loop Script fixture; {v2} active and v2 dialogue verified in rendered manuscript.",
        )

        browser.close()
        assert not errors, errors

manifest = {
    "captures": MANIFEST,
    "browser": {"playwright": "1.63.0", "chromium": "153.0.8010.0", "web_security_overrides": False},
    "fixture": "tests/fixtures/pain_tenglish.fountain",
    "synthetic_data_notice": "A-scene_function includes one browser-only seeded UI sample, explicitly watermarked and not part of the server report.",
}
(OUT / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("MANIFEST", OUT / "capture-manifest.json")
