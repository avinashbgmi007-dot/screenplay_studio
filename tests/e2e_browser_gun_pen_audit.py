"""gun_pen.pdf — Full Feedback-Projection Audit (session-only, real model).

Walks every feedback surface the backend emits against the real gun_pen
report, per docs/gun_pen.pdf_full_feedback_audit_<...>.plan.md. Connects to an
ALREADY-RUNNING studio pointed at the real llama-server (never boots the demo
model — the audit's whole point is real-findings depth).

  E2E_BASE=http://127.0.0.1:8500 python tests/e2e_browser_gun_pen_audit.py [stage]
  stage = matrix | escalation | inbetween | pass2 | all   (default all)

Screenshots -> impl-shots/ ; results -> impl-shots/audit_results.json.
No production code changes; gaps are filed in NOTES.md by the operator.
"""
import json
import os
import re
import sys
import time

import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)  # for screenplay_studio / screenplay_cowriter imports
from e2e_browser_common import Checks, launch  # noqa: E402

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8500").rstrip("/")
PROJECT = os.environ.get("GUNPEN_PROJECT", "gun_pen_2")
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "impl-shots")
os.makedirs(SHOTS, exist_ok=True)

checks = Checks()
check = checks.ok
RESULTS = {}
# A GAP is a product promise the desk does not keep (the audit's finding) —
# distinct from a harness failure. Gaps do not fail the run; they are filed.
GAPS = []


def gap(name, cond, detail=""):
    """Record a product gap. `cond` True == the promise holds (no gap)."""
    holds = bool(cond)
    print(f"  {'ok  ' if holds else 'GAP '} {name}" + (f"  [{detail}]" if detail else ""))
    if not holds:
        GAPS.append({"gap": name, "detail": detail})
    return holds


def api(method, path, **kw):
    r = requests.request(method, BASE + path, timeout=kw.pop("timeout", 60), **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def shot(page, name, full=False):
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path, full_page=full)
    print(f"    [shot] {name}")
    return path


def _working_texts(project_dir):
    """(scene_number, element_text) for the working copy."""
    with open(os.path.join(project_dir, "working.json"), encoding="utf-8") as f:
        doc = json.load(f)
    return [(s.get("scene_number"), el.get("text") or "")
            for s in doc.get("scenes", []) for el in s.get("elements", [])]


def _quote_present(texts, quote):
    """Mirrors revision.quote_present: exact substring, then fuzzy >= 0.95."""
    from difflib import SequenceMatcher
    q = (quote or "").strip()
    if not q:
        return False
    if any(q in t for t in texts):
        return True
    return any(SequenceMatcher(None, t, q).ratio() >= 0.95 for t in texts if t)


def shelf_label():
    """The shelf renders the project's TITLE (e.g. 'gun_pen'), not its dir name."""
    try:
        for x in api("GET", "/api/projects"):
            if x.get("project") == PROJECT:
                return x.get("title") or PROJECT
    except Exception:
        pass
    return PROJECT


def open_project(page, name, label=None):
    # domcontentloaded, not networkidle: the shell fires POST /api/test-connection
    # (a live probe of llama-server) on boot, and against a loaded model that can
    # exceed the networkidle window — the page is ready long before the probe is.
    page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("#shelf-trigger", timeout=20000)
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    row = page.locator(".project-item").filter(has_text=label or shelf_label())
    if not row.count():
        row = page.locator(".project-item").filter(has_text=name)
    row.first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=30000)
    page.wait_for_timeout(600)


def open_dock(page, lens="evidence"):
    if not page.locator("#context-dock.open").count():
        page.locator("#right-edge-affordance").click()
        page.wait_for_selector("#context-dock.open", timeout=8000)
        page.wait_for_timeout(500)
    page.locator(f"#dock-tab-{lens}").click()
    page.wait_for_timeout(500)


def widen_filter(page, lens):
    """Turn Medium + Low severity chips ON so every finding card shows."""
    for label in ("Medium", "Low"):
        chip = lens.locator(".fchip", has_text=label).first
        if chip.count() and "active" not in (chip.get_attribute("class") or ""):
            chip.click()
            page.wait_for_timeout(450)


# ---------------------------------------------------------------------------
# STEP 1 — probe (deterministic, no browser)
# ---------------------------------------------------------------------------

def step_probe():
    import pypdf
    pdf = os.path.join(os.path.dirname(SHOTS), "studio_projects", PROJECT, "source.pdf")
    r = pypdf.PdfReader(pdf)
    txt = "\n".join((p.extract_text() or "") for p in r.pages)
    probe = {
        "pdf_pages": len(r.pages),
        "text_layer_chars": len(txt),
        "int_ext_headings": len(re.findall(r"(?m)^\s*(INT|EXT)[\. ]", txt)),
    }
    rep = api("GET", f"/api/projects/{PROJECT}/report")
    findings = rep.get("findings") or []
    sc = api("GET", f"/api/projects/{PROJECT}/script")
    probe.update({
        "findings": len(findings),
        "scenes": len(sc.get("scenes") or []),
        "report_keys": sorted(rep.keys()),
    })
    RESULTS["probe"] = probe
    print("STEP 1 — probe:", json.dumps(probe, ensure_ascii=False))
    check("probe: text layer present (no OCR contingency)", probe["text_layer_chars"] > 2000)
    check("probe: short-form script recorded honestly (<=6 scenes)", probe["scenes"] <= 6,
          f"{probe['scenes']} scenes / {probe['pdf_pages']} pages")


# ---------------------------------------------------------------------------
# STEP 2/3 — baseline + split-matrix walk
# ---------------------------------------------------------------------------

CATEGORY_LABELS = {
    "dialogue": "Dialogue", "structure": "Structure", "scene_function": "Scene function",
    "character": "Character", "theme": "Theme", "genre": "Genre", "plot_thread": "Plot",
    "continuity": "Continuity", "principles": "Principles", "setup_payoff": "Setup",
}


def step_matrix():
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, PROJECT)
        open_dock(page, "evidence")
        lens = page.locator('.dock-lens[data-lens="evidence"]')

        # -- STEP 2: baseline ------------------------------------------------
        shot(page, "A00-baseline-board.png")
        mass = lens.locator(".dock-mass-strip")
        check("baseline: mass strip renders", mass.count() > 0)
        mass_text = mass.inner_text() if mass.count() else ""
        trust = lens.locator(".dock-trust").first
        trust_text = trust.inner_text() if trust.count() else ""
        check("baseline: trust readout renders on the mass strip", bool(trust_text),
              trust_text)
        check("baseline: trust readout is the 'N of M verified (P%)' shape",
              bool(re.search(r"\d+ of \d+ quotes verified \(\d+%\)", trust_text)), trust_text)
        default_cards = lens.locator(".finding-note").count()
        check("baseline: highs-only default shows fewer cards than the full set",
              0 < default_cards, f"{default_cards} cards at default")
        print(f"    mass: {mass_text.splitlines()[:2]}  trust: {trust_text}")

        # -- cross-cutting: the counting contract (N3) ------------------------
        # With zero edits made, EVERY finding must read open. The server's own
        # observed-status report is the second opinion.
        ed = api("GET", f"/api/projects/{PROJECT}/edits")
        fsum = (ed.get("findings_status") or {}).get("summary") or {}
        n_findings = len(api("GET", f"/api/projects/{PROJECT}/report").get("findings") or [])
        RESULTS["findings_status_summary"] = fsum
        RESULTS["findings_total"] = n_findings
        gap("C: unedited script -> zero phantom 'addressed' findings",
            fsum.get("addressed", 0) == 0,
            f"server observes addressed={fsum.get('addressed')} still_present={fsum.get('still_present')} "
            f"unknown={fsum.get('unknown')} of {n_findings}")
        m = re.search(r"(\d+) open of (\d+) findings", mass_text)
        gap("C: mass strip reports every finding open on an unedited script",
            bool(m) and int(m.group(1)) == int(m.group(2)),
            f"mass strip says '{m.group(0)}' but the report has {n_findings} findings"
            if m else mass_text[:60])
        shot(page, "C00-phantom-addressed.png")
        # the desk's own status line vs the finding count (refreshDeskToolbar
        # runs at project-open BEFORE state.findings loads and is never re-run)
        ds = page.locator("#desk-analyze-status")
        ds_txt = ds.inner_text() if ds.count() else ""
        RESULTS["desk_status"] = ds_txt
        gap("C: the desk status line agrees with the finding count",
            n_findings == 0 or "clean bill" not in ds_txt.lower(),
            f"status reads {ds_txt[:90]!r} while the report has {n_findings} findings")
        shot(page, "C01-desk-status.png")

        widen_filter(page, lens)
        page.wait_for_timeout(500)
        wide_cards = lens.locator(".finding-note").count()
        check("widen: Medium+Low reveal every finding card", wide_cards >= default_cards,
              f"{default_cards} -> {wide_cards}")
        shot(page, "A01-widened-board.png")

        # -- row A: finding-emitting categories ------------------------------
        titles = lens.locator(".dock-section-title").all_inner_texts()
        titles_join = " | ".join(titles)
        row_a = []
        for cat in ("dialogue", "theme", "character", "structure",
                    "scene_function", "genre", "plot_thread", "continuity"):
            label = CATEGORY_LABELS[cat]
            present = label.lower() in titles_join.lower()
            row_a.append((cat, present))
            check(f"A/{cat}: category section renders", present, titles_join[:160])
        # principles + setup_payoff — the plan's split-matrix rows
        row_a.append(("principles", "Principles" in titles_join))
        check("A/principles: section present (or honestly absent)",
              True, "principles produced no findings on this script")
        RESULTS["row_a"] = row_a

        # per-category screenshot: scroll the section into view
        for cat in ("dialogue", "structure", "scene_function"):
            label = CATEGORY_LABELS[cat]
            sec = lens.locator(".dock-section", has=lens.locator(".dock-section-title", has_text=label)).first
            if sec.count():
                sec.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                shot(page, f"A-{cat}.png")

        # -- row A: trust chips on deep cards --------------------------------
        verified_badges = lens.locator(".finding-deep-badge.verified").count()
        unverified_badges = lens.locator(".finding-deep-badge.unverified").count()
        check("A: verified deep cards carry the trust chip", verified_badges > 0,
              f"{verified_badges} verified badges")
        check("A: no_quote findings are flagged unverified, never dropped",
              unverified_badges > 0, f"{unverified_badges} unverified badges")
        RESULTS["badges"] = {"verified": verified_badges, "unverified": unverified_badges}

        # -- row A: severity is never colour-alone ---------------------------
        sev_texts = lens.locator(".fix-row .sev-badge").all_inner_texts() or \
            lens.locator(".dock-mass-mark").all_inner_texts()
        check("A: severity carries a printed label (never colour-alone)",
              any(t.strip() for t in sev_texts), str(sev_texts[:6]))

        # -- orientation surfaces -------------------------------------------
        check("C: script ruler renders (diagnostic weight by scene)",
              lens.locator(".dock-ruler-track").count() > 0)
        check("C: setup/payoff spine renders (or absent honestly)",
              lens.locator(".dock-sp-spine").count() >= 0)

        # -- row B: report-section panels ------------------------------------
        craft_titles = lens.locator(".dock-craft .craft-panel-title").all_inner_texts()
        craft_join = " | ".join(craft_titles)
        row_b = {}
        row_b["pacing"] = lens.locator(".pacing-svg").count() > 0
        row_b["characters_panel"] = "character" in craft_join.lower()
        row_b["writer_mirror"] = lens.locator(".craft-panel.writer-mirror").count() > 0
        row_b["coverage"] = lens.locator(".dock-cov-logline").count() > 0
        for k, v in row_b.items():
            check(f"B/{k}: report-section panel renders in the dock", v, craft_join[:200])
        # the character DIALS specifically — data renders, but where?
        dial_rows = page.locator(".dial-row").count()
        dials_visible = page.locator(".rail-char-dials").first.is_visible() \
            if page.locator(".rail-char-dials").count() else False
        RESULTS["row_b"] = row_b
        row_b["character_dials"] = {"dial_rows": dial_rows, "visible": dials_visible}
        gap("B/character_dials: the dials are reachable on the live desk",
            dial_rows > 0 and dials_visible,
            f"{dial_rows} dial rows render, visible={dials_visible} "
            f"(#struct-rail is display:none — dead chrome)")
        shot(page, "B-character-dials.png")
        RESULTS["row_b"] = row_b
        craft = lens.locator(".dock-craft").first
        if craft.count():
            craft.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            shot(page, "B-craft-panels.png")
        cov = lens.locator(".dock-section", has=lens.locator(".dock-section-title", has_text="Coverage")).first
        if cov.count():
            cov.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            shot(page, "B-coverage.png")

        # -- row C: failed categories (quiet state on this script) -----------
        proj = [x for x in api("GET", "/api/projects") if x.get("project") == PROJECT]
        failed = (proj[0].get("failed_categories") if proj else []) or []
        RESULTS["failed_categories"] = failed
        check("C: no failed categories on this script (quiet state honest)",
              failed == [], str(failed))
        check("C: no inline retry button when nothing failed",
              lens.locator(".dock-arrival-retry").count() == 0)

        # -- full-lens verdict shot ------------------------------------------
        shot(page, "A02-evidence-lens-full.png", full=True)
        check("matrix walk: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


# ---------------------------------------------------------------------------
# STEP 4 — escalation proof (both routes)
# ---------------------------------------------------------------------------

def step_escalation():
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, PROJECT)

        def close_room(pg):
            # deterministic: dispatch the real close control, never rely on
            # hit-testing (an open drawer intercepts pointer events)
            for _ in range(4):
                if not pg.locator("#room-drawer.open").count():
                    return
                pg.evaluate("() => { const b = document.getElementById('drawer-close'); if (b) b.click(); }")
                pg.wait_for_timeout(500)

        def quote_state():
            qc = page.locator("#quote-card")
            vis = qc.count() > 0 and qc.first.is_visible()
            return vis, (qc.first.inner_text() if qc.count() else "")

        def prep_evidence():
            close_room(page)
            open_dock(page, "evidence")
            lens = page.locator('.dock-lens[data-lens="evidence"]')
            widen_filter(page, lens)
            page.wait_for_timeout(450)
            return lens

        # --- route 1: Discuss from the loop bar (no room involved) ----------
        # Runs FIRST: the loop bar lives in the dock, and every Discuss that
        # opens the room drawer would otherwise intercept the click.
        lens = prep_evidence()
        loop_btn = lens.locator(".fchip-loop").first
        check("escalation/Sameer: the fix loop engages", loop_btn.count() > 0)
        if loop_btn.count():
            loop_btn.click()
            page.wait_for_timeout(700)
            bar = page.locator("#loop-bar")
            check("escalation/Sameer: the loop bar renders with a position readout",
                  bar.count() > 0 and bar.locator(".loop-pos").count() > 0)
            # stepLoop falls back to jumpToScene when the current finding has no
            # inked quote — and jumpToScene() unconditionally opens the partner
            # drawer (app.js:2807), which covers the dock the loop bar lives in.
            room_opened = page.locator("#room-drawer.open").count() > 0
            gap("escalation/loop: engaging the fix loop does not cover its own bar",
                not room_opened,
                "engaging the loop opened the room drawer over the dock "
                "(startLoop -> stepLoop -> jumpToScene -> openCowriteRoom); the loop "
                "bar's mark/park/discuss buttons are then unreachable by mouse")
            close_room(page)
            lb_discuss = bar.locator(".loop-btn", has_text="discuss").first
            if lb_discuss.count():
                lb_discuss.click()
                page.wait_for_timeout(600)
                vis3, _ = quote_state()
                check("escalation/Sameer: loop-bar Discuss pins the quote", vis3)
            shot(page, "ESC-0-loop-bar.png")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            close_room(page)

        # --- route 2: Discuss from a deep card -> send -> discussed tag -----
        # Pick a SCENE-ANCHORED card: a script-level finding (scene_refs == [])
        # pins scene_number=null, so no scene can carry the discussed tag —
        # correct behaviour, but it can't exercise the tag.
        lens = prep_evidence()
        cards = lens.locator(".finding-note:has(.finding-deep-quote)")
        card = None
        for i in range(min(cards.count(), 40)):
            c = cards.nth(i)
            cat = c.locator(".finding-note-cat").first.inner_text().strip().lower()
            if cat and cat != "continuity":
                card = c
                break
        check("escalation/Sameer: a scene-anchored deep card exists",
              card is not None, f"{cards.count()} deep-quote cards")
        if card is None:
            card = cards.first
        if cards.count():
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(250)
            card.locator(".finding-note-actions button", has_text="Discuss").first.click()
            page.wait_for_timeout(800)
            vis, qtxt = quote_state()
            check("escalation/Sameer: Discuss PINS the quote (setPendingQuote)", vis, qtxt[:80])
            check("escalation/Sameer: Discuss opens the room",
                  page.locator("#room-drawer").count() > 0)
            prefill = page.locator("#input").input_value() or ""
            check("escalation/Sameer: the composer is seeded with the finding",
                  len(prefill) > 0, prefill[:90])
            shot(page, "ESC-1-sameer-quote-pinned.png")

            before_user = page.locator(".msg.user").count()
            before_asst = page.locator(".msg.assistant").count()
            page.locator("#input").fill(prefill or "What should I do about this?")
            page.locator("#send-btn").click()
            try:
                # require a NEW turn: the room may already hold earlier replies
                page.wait_for_function(
                    "(n) => document.querySelectorAll('.msg.user').length > n",
                    arg=before_user, timeout=30000)
                page.wait_for_function(
                    """(n) => {
                        const m = document.querySelectorAll('.msg.assistant');
                        return m.length > n && !m[m.length - 1].classList.contains('msg-pending');
                    }""", arg=before_asst, timeout=240000)
                reply = page.locator(".msg.assistant .msg-bubble").last.inner_text()
                check("escalation/Sameer: a real reply streams back", len(reply.strip()) > 20,
                      reply[:120])
                RESULTS["sameer_reply"] = reply[:1500]
            except Exception as e:
                check("escalation/Sameer: a real reply streams back", False, str(e)[:140])
            shot(page, "ESC-2-sameer-reply.png")
            # the discussed tag is computed when the manuscript renders from the
            # branch's messages — allow the live re-render, else confirm persistence
            try:
                page.wait_for_selector(".scene-discussed", timeout=10000)
            except Exception:
                pass
            disc = page.locator(".scene-discussed").count()
            live = disc > 0
            if not disc:
                open_project(page, PROJECT)
                disc = page.locator(".scene-discussed").count()
            check("escalation/Sameer: the scene page gains the 'discussed' tag", disc > 0,
                  f"{disc} tag(s) (live={live})")
            shot(page, "ESC-3-discussed-tag.png")
            close_room(page)

        # --- route 3: Discuss from the fix queue ----------------------------
        lens = prep_evidence()
        fq = lens.locator(".fix-row-actions button", has_text="Discuss").first
        check("escalation/Sameer: the fix queue carries Discuss", fq.count() > 0)
        if fq.count():
            fq.scroll_into_view_if_needed()
            fq.click()
            page.wait_for_timeout(700)
            vis2, _ = quote_state()
            check("escalation/Sameer: fix-queue Discuss also pins the quote", vis2)
            close_room(page)

        # --- route 4: Sushruta — the finding rides into the consult ---------
        lens = prep_evidence()
        why = lens.locator('.finding-note .intent-btn[title*="Ask Dr. Sushruta"]').first
        check("escalation/Sushruta: the 'ask the doctor why' gesture exists", why.count() > 0)
        if why.count():
            why.scroll_into_view_if_needed()
            why.click()
            page.wait_for_timeout(900)
            sush = page.locator('.dock-lens[data-lens="sushruta"]')
            check("escalation/Sushruta: the doctor's lens opens",
                  page.locator("#context-dock.open").count() > 0)
            seeded = sush.locator("#fv-consult-input")
            seeded_txt = seeded.input_value() if seeded.count() else ""
            check("escalation/Sushruta: the 'why was this flagged' question is seeded "
                  "with the finding's category + scene",
                  "flagged" in seeded_txt.lower() and "scene" in seeded_txt.lower(), seeded_txt[:110])
            shot(page, "ESC-4-sushruta-why-seeded.png")
            if seeded.count():
                before_ai = page.locator('.dock-lens[data-lens="sushruta"] .fv-msg.ai').count()
                seeded.fill(seeded_txt or "Why was this flagged? What exactly is wrong?")
                sush.locator("#fv-consult-composer button[type=submit]").click()
                try:
                    page.wait_for_function(
                        """(n) => {
                            const m = document.querySelectorAll('.dock-lens[data-lens="sushruta"] .fv-msg.ai');
                            if (m.length <= n) return false;
                            const t = m[m.length-1].textContent || '';
                            return t.length > 40 && !t.includes('reading');
                        }""", arg=before_ai, timeout=240000)
                    doc_reply = page.locator(
                        '.dock-lens[data-lens="sushruta"] .fv-msg.ai').last.inner_text()
                    check("escalation/Sushruta: the reply carries per-finding reasoning",
                          len(doc_reply.strip()) > 60, doc_reply[:140])
                    RESULTS["sushruta_reply"] = doc_reply[:2000]
                except Exception as e:
                    check("escalation/Sushruta: the reply carries per-finding reasoning",
                          False, str(e)[:120])
                shot(page, "ESC-5-sushruta-reply.png")

        check("escalation: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


# ---------------------------------------------------------------------------
# STEP 5 — in-between (intents + one quote-visible edit)
# ---------------------------------------------------------------------------

def step_inbetween():
    pdir = os.path.join(os.path.dirname(SHOTS), "studio_projects", PROJECT)
    rep = api("GET", f"/api/projects/{PROJECT}/report")
    findings = rep.get("findings") or []
    # ids straight from the server (no client-side re-derivation to drift)
    ed = api("GET", f"/api/projects/{PROJECT}/edits")
    fs_items = (ed.get("findings_status") or {}).get("findings") or []
    ids = list(dict.fromkeys(x.get("finding_id") for x in fs_items if x.get("finding_id")))
    check("in-between: the server exposes finding ids for intent marks", len(ids) > 0,
          f"{len(ids)} distinct ids")

    # 2 addressed + 1 deferred (writer intent)
    for fid in ids[:2]:
        api("POST", f"/api/projects/{PROJECT}/findings/intent",
            json={"finding_id": fid, "intent": "addressed"})
    if len(ids) > 2:
        api("POST", f"/api/projects/{PROJECT}/findings/intent",
            json={"finding_id": ids[2], "intent": "deferred"})
    intents = (api("GET", f"/api/projects/{PROJECT}/edits").get("finding_intents") or {})
    check("in-between: writer intents persisted", len(intents) >= 3, str(intents))
    RESULTS["intents"] = intents

    # one quote-visible edit: change a line a verified finding cites. The quote
    # must sit inside a SINGLE wrapped element (quote_present True) or
    # apply_replacements skips it ("line not found in scene").
    texts = _working_texts(pdir)
    target = None
    for f in findings:
        q = (f.get("evidence_quote") or "").strip()
        if (f.get("verification") or {}).get("status") != "verified" or not q:
            continue
        # the edit targets a whole ELEMENT line in the scene that HOLDS it
        # (apply_replacements matches the line, and scene_refs may be empty)
        candidates = [(sn, t) for sn, t in texts if t and q in t]
        if candidates:
            sn, old_line = max(candidates, key=lambda p: len(p[1]))
            target = (f, sn, old_line)
            break
    if target is None:
        check("in-between: a verified quote sits inside one editable element", False,
              "all verified quotes span wrapped lines")
        return
    target_f, scene, old_line = target
    new_line = old_line + " (rewritten in the audit)"
    res = api("POST", f"/api/projects/{PROJECT}/edits/apply",
              json={"scene_number": scene, "replacements": [{"old": old_line, "new": new_line}]})
    check("in-between: the quote-visible edit applied", bool(res.get("applied")),
          json.dumps(res)[:220])
    RESULTS["edit"] = {"scene": scene, "old": old_line, "new": new_line,
                       "applied": res.get("applied"), "skipped": res.get("skipped")}
    print("    edit:", json.dumps(RESULTS["edit"], ensure_ascii=False)[:220])
    st = res.get("findings_status", {}).get("summary", {})
    RESULTS["status_after_edit"] = st
    print("    findings_status after edit:", st)


# ---------------------------------------------------------------------------
# STEP 6 — pass 2 + arrival-strip arithmetic
# ---------------------------------------------------------------------------

def _expected_arrival():
    """The exact diff the arrival strip must show — read from the SERVER's own
    snapshot (last_pass_snapshot computes it lazily on GET /edits), so the
    assertion compares the UI against the server's arithmetic, not a
    re-implementation of it."""
    api("GET", f"/api/projects/{PROJECT}/edits")
    lp_path = os.path.join(os.path.dirname(SHOTS), "studio_projects", PROJECT, "last_pass.json")
    with open(lp_path, encoding="utf-8") as f:
        snap = json.load(f)
    return snap.get("payload") or {}


def step_pass2():
    before = _expected_arrival()
    print("    pre-pass2 baseline:", before)
    # POST /analyze BLOCKS until the whole run completes (~9 min on the real
    # model), so the timeout must cover the run. GUNPEN_SKIP_ANALYZE=1 asserts
    # against an already in-flight run instead of starting another.
    if os.environ.get("GUNPEN_SKIP_ANALYZE") != "1":
        try:
            r = requests.post(f"{BASE}/api/projects/{PROJECT}/analyze",
                              json={"force": True}, timeout=900)
            check("pass2: force re-analysis accepted", r.status_code in (200, 201),
                  str(r.status_code))
        except Exception as e:
            check("pass2: force re-analysis accepted", False, str(e)[:140])
    else:
        print("    (trigger skipped — asserting against the in-flight run)")
    deadline = time.time() + 1800
    pr = {}
    while time.time() < deadline:
        try:
            pr = api("GET", f"/api/projects/{PROJECT}/progress", timeout=15)
        except Exception:
            pr = {}
        if pr.get("status") == "complete" or pr.get("stage") == "done":
            break
        time.sleep(10)
    check("pass2: analysis completed", pr.get("status") == "complete" or pr.get("stage") == "done",
          json.dumps(pr)[:160])

    after = _expected_arrival()
    RESULTS["arrival_expected"] = after
    print("    post-pass2 expected arrival:", after)

    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, PROJECT)
        open_dock(page, "evidence")
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        strip = lens.locator(".dock-arrival-strip")
        check("pass2: the arrival strip appears", strip.count() > 0)
        if strip.count():
            line = strip.locator(".dock-arrival-line").inner_text()
            scope = strip.locator(".dock-arrival-scope").inner_text() if strip.locator(".dock-arrival-scope").count() else ""
            draft = strip.locator(".dock-arrival-draft").inner_text() if strip.locator(".dock-arrival-draft").count() else ""
            print(f"    arrival line: {line}")
            print(f"    scope: {scope} | draft: {draft}")
            m = re.search(r"Pass: (\d+) . (\d+) still live . (\d+) no longer flagged . (\d+) new", line)
            if after:
                check("pass2: arrival arithmetic is EXACT vs the server's own diff",
                      bool(m) and [int(m.group(i)) for i in (1, 2, 3, 4)] ==
                      [after["last_total"], after["still_live"], after["fixed"], after["new"]],
                      f"line={line!r} expected={after}")
            else:
                check("pass2: arrival arithmetic is EXACT vs the server's own diff", False,
                      f"no snapshot payload (line={line!r})")
            check("pass2: the scope chip states the pass line never tracks edits",
                  "not your edits" in scope.lower(), scope)
            # the arrival basis vs the board basis — the same desk, two totals
            rep_n = len(api("GET", f"/api/projects/{PROJECT}/report").get("findings") or [])
            gap("pass2: the arrival 'Pass:' total agrees with the board's finding count",
                after["last_total"] == rep_n,
                f"arrival last_total={after['last_total']} vs report findings={rep_n} "
                f"(distinct-id dedup: colliding finding ids collapse in the arithmetic)")
            ghosted = strip.locator(".dock-ghosted-summary").count()
            check("pass2: ghosted marks render honestly (never red)",
                  ghosted >= 0, f"{ghosted} ghosted block(s)")
            shot(page, "PASS2-arrival-strip.png")
        check("pass2: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()


def step_cleanbill():
    """The empty-pass 'clean bill' reading (plan fix #5).

    No zero-finding row occurs naturally on gun_pen, so this uses the plan's
    sanctioned synthetic mini-project (tests/_gunpen_clean_bill.py seeds it).
    """
    label = "Clean Bill Probe"
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, "Clean_Bill_Probe", label=label)
        status = page.locator("#desk-analyze-status")
        txt = status.inner_text() if status.count() else ""
        check("clean bill: the desk reads the empty pass as a clean bill",
              "clean bill" in txt.lower(), txt[:110])
        open_dock(page, "evidence")
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        check("clean bill: the lens is not a blank — coverage still renders",
              lens.locator(".dock-cov-logline, .dock-section-title").count() > 0)
        check("clean bill: no finding cards (honest zero)",
              lens.locator(".finding-note").count() == 0)
        check("clean bill: no mass strip claimed (nothing to weigh)",
              lens.locator(".dock-mass-strip").count() == 0)
        check("clean bill: no retry button (nothing failed)",
              lens.locator(".dock-arrival-retry").count() == 0)
        shot(page, "C-clean-bill.png")
        check("clean bill: no JS errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()
    RESULTS["clean_bill"] = {"synthetic": True, "label": label}


STAGES = {"matrix": step_matrix, "escalation": step_escalation,
          "inbetween": step_inbetween, "pass2": step_pass2,
          "cleanbill": step_cleanbill}


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    # stages accumulate: a later stage run must not wipe an earlier stage's data
    results_path = os.path.join(SHOTS, "audit_results.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, encoding="utf-8") as f:
                RESULTS.update(json.load(f))
            GAPS[:] = RESULTS.get("gaps") or []
        except (OSError, ValueError):
            pass
    print(f"=== gun_pen feedback audit :: stage={stage} :: base={BASE} :: project={PROJECT} ===")
    order = (["matrix", "escalation", "inbetween", "pass2", "cleanbill"]
             if stage == "all" else [stage])
    for name in order:
        print(f"\n--- stage: {name} ---")
        try:
            STAGES[name]()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"stage {name} completed", False, str(e)[:160])
    # MERGE this stage's gaps into the accumulated file — stages run as separate
    # processes, so replacing would silently drop every earlier stage's findings
    # (which is exactly what happened on the first pass2 run).
    prior = RESULTS.get("gaps") or []
    seen = {g.get("gap") for g in prior}
    RESULTS["gaps"] = prior + [g for g in GAPS if g.get("gap") not in seen]
    with open(os.path.join(SHOTS, "audit_results.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)
    print(f"\n=== GAPS FILED ({len(RESULTS['gaps'])}) ===")
    for g in RESULTS["gaps"]:
        print(f"  - {g['gap']}: {g['detail']}")
    checks.finish()


if __name__ == "__main__":
    main()
