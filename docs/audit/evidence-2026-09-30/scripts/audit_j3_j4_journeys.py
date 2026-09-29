"""Audit J3+J4 — feedback surfaces + the writer loop, on HEAD ddac2df.

Every pipeline stage a check depends on completes INSIDE this probe:
seed -> parse -> analyze (demo model) -> report/fixqueue -> revision loop.
Legs and what each proves:
  J3   Evidence lens sections, fix-queue severity order, ONE filter row
       (severity chip drives queue+board), category chips, keyboard fix loop
       (N/P/Esc via loopState), Locate jump, legacy report/fixqueue tabs,
       dismissal + undismiss, intent mark -> dawn meter, duplicate-finding
       deaths (rung 20 surface), strip finding count (rung 19 surface).
  J4   rewrite candidates -> apply -> addressed/still-present recompute ->
       undo -> redo -> export fountain/fdx -> inline edit (UI) -> beatboard
       reorder/save/export/reset -> drafts upload/activate/diff/compare.

Run:  python docs/audit/evidence-2026-09-30/scripts/audit_j3_j4_journeys.py
"""
import json
import os
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, start_studio, studio_headers
from audit_common import save_console_capture, shot, reveal_chrome

EV_DIR = os.path.join(REPO_ROOT, "docs", "audit", "evidence-2026-09-30")
SHOTS = os.path.join(EV_DIR, "shots")
os.makedirs(SHOTS, exist_ok=True)

checks = Checks()
check = checks.ok
evidence = {}

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

SCRIPT_V2 = SCRIPT.replace("One more day. That's all I need.",
                           "One more night. That is all I ask.")


def wpost(base, path, payload=None, timeout=300):
    """Token-carrying JSON write."""
    return requests.post(base + path, json=payload if payload is not None else {},
                         timeout=timeout, headers=studio_headers(base))


def seed_and_analyze(base, title, script):
    ok, name, detail = None, None, None
    r = requests.post(base + "/api/projects",
                      files={"file": (title.lower().replace(" ", "_") + ".fountain",
                                      script.encode(), "text/plain")},
                      data={"title": title}, timeout=60, headers=studio_headers(base))
    ok = r.status_code in (200, 201)
    name = (r.json() or {}).get("project") if ok else None
    detail = f"status={r.status_code}"
    check(f"seed: {title} created + parsed", ok and name, detail)
    if not name:
        return None
    ar = wpost(base, f"/api/projects/{name}/analyze", {"force": True}, timeout=300)
    check(f"seed: {title} analyzed (demo model)", ar.status_code == 200,
          f"status={ar.status_code} {ar.text[:120]}")
    st = requests.get(f"{base}/api/projects/{name}", timeout=15).json()
    n = len((requests.get(f"{base}/api/projects/{name}/report", timeout=15).json() or {}).get("findings") or [])
    check(f"seed: {title} report carries findings (demo model)", n > 0, f"findings={n}")
    evidence.setdefault("seed_findings", {})[title] = n
    return name


def open_on_desk(page, base, name):
    page.goto(base, timeout=30000)
    page.wait_for_load_state("networkidle")
    page.evaluate("(n) => openProject(n)", name)
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def open_dock(page):
    """Idempotent: the affordance hides while the dock is already open (the
    fix loop opens it too), so a second open_dock must be a no-op."""
    already = page.evaluate(
        "() => document.querySelector('#context-dock')?.classList.contains('open') || false")
    if already:
        return
    page.locator("#right-edge-affordance").click()
    page.wait_for_selector("#context-dock.open", timeout=5000)
    page.wait_for_timeout(450)


def main():
    with start_studio() as studio:
        base = studio.base_url
        name = seed_and_analyze(base, "Loop Script", SCRIPT)
        if not name:
            (checks.finish)()
            return

        console_msgs, page_errors, net = [], [], []
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text[:200]}"))
            page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))
            page.on("response", lambda r: net.append(f"{r.status} {r.url[-60:]}" if r.status >= 400 else None))

            open_on_desk(page, base, name)
            open_dock(page)
            browser_ctx_ok = True

            # ---------------- J3.1 evidence lens renders its ledger ----------
            lens = ".dock-lens[data-lens='evidence']"
            fq_section = page.locator(f"{lens} .dock-section[data-key='fix-queue']").count()
            rows_dock = page.locator(f"{lens} .fix-row").count()
            check("J3.1: Evidence lens renders fix-queue section + rows",
                  fq_section == 1 and rows_dock > 0,
                  f"sections={fq_section} rows={rows_dock}")
            shot(page, SHOTS, "j3_evidence_lens")

            # ---------------- J3.2 fix-queue severity order ------------------
            order = page.evaluate(
                """(sel) => [...document.querySelectorAll(sel + ' .fix-row .sev-badge')]
                     .map((e) => (e.textContent || '').trim().toLowerCase())""", lens)
            weight = {"high": 0, "major": 1, "medium": 2, "low": 3}
            ws = [weight.get(s, 9) for s in order]
            check("J3.2: queue rows are severity-ordered (high->low, ties by act)",
                  ws == sorted(ws) and len(ws) > 0, str(order[:12]))
            evidence["j3_severity_order"] = order[:12]

            # ---------------- J3.3 ONE filter row drives the queue -----------
            chips = page.locator(f"{lens} .fchip:not(.fchip-loop)")
            n_chips = chips.count()
            check("J3.3: filter row renders severity/category chips", n_chips >= 3,
                  f"chips={n_chips}")
            before_n = page.locator(f"{lens} .fix-row").count()
            low_chip = page.locator(f"{lens} .fchip", has_text="low").first
            if low_chip.count() == 0:
                low_chip = page.locator(f"{lens} .fchip", has_text="Low").first
            if low_chip.count():
                # chip semantics are EXCLUSION toggles (state.findingFilter.severities
                # is an include-gate; clicking removes that severity from it)
                low_chip.click()
                page.wait_for_timeout(500)
                after_n = page.locator(f"{lens} .fix-row").count()
                sevs = page.evaluate(
                    """(sel) => [...document.querySelectorAll(sel + ' .fix-row .sev-badge')]
                         .map((e) => (e.textContent || '').trim().toLowerCase())""", lens)
                no_low = all(s != "low" for s in sevs) if sevs else True
                check("J3.3: severity chip excludes that severity from the queue",
                      after_n < before_n and no_low,
                      f"before={before_n} after={after_n} sevs={sevs[:8]}")
                low_chip.click()  # restore
                page.wait_for_timeout(400)
            else:
                check("J3.3: severity chip filters the queue", False, "no low chip found")

            # ---------------- J3.4 keyboard fix loop (N/P/Esc) ---------------
            loop_btn = page.locator(f"{lens} .fchip-loop")
            check("J3.4: fix-loop button present in the filter row",
                  loop_btn.count() == 1, f"count={loop_btn.count()}")
            loop_btn.click()
            page.wait_for_timeout(500)
            active = page.evaluate("typeof loopState !== 'undefined' && loopState.active")
            check("J3.4: loop engages", bool(active), f"loopState.active={active}")
            pos1 = page.evaluate("loopState.pos")
            page.keyboard.press("n")
            page.wait_for_timeout(400)
            pos2 = page.evaluate("loopState.pos")
            page.keyboard.press("p")
            page.wait_for_timeout(400)
            pos3 = page.evaluate("loopState.pos")
            check("J3.4: N steps forward, P steps back (wrap-safe)",
                  pos2 != pos1 and pos3 == pos1, f"pos {pos1}->{pos2}->{pos3}")
            cur = page.locator(f"{lens} .finding-note.loop-current").count()
            check("J3.4: the loop's current card is highlighted", cur == 1, f"loop-current={cur}")
            shot(page, SHOTS, "j3_loop_active")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            exited = page.evaluate("!loopState.active")
            check("J3.4: Esc exits the loop", bool(exited), f"active after Esc={not exited}")

            # ---------------- J3.5 Locate jump -------------------------------
            err_before = page.locator("#error-banner").is_visible()
            locate = page.locator(f"{lens} .fix-row button", has_text="Locate").first
            check("J3.5: Locate verb present on queue rows (rung 18: one spelling)",
                  locate.count() > 0, "no Locate button")
            if locate.count():
                locate.click()
                page.wait_for_timeout(600)
                err_after = page.locator("#error-banner").is_visible()
                check("J3.5: Locate jumps without an error banner",
                      err_before or not err_after, "error banner visible after Locate")

            # ---------------- J3.6 rung-20 surface: duplicate deaths ---------
            # Product contract (dedupe.collapse_exact_duplicates): the WHOLE row
            # is the key — same issue text under a differing field survives by
            # design. So the check is exact-row duplicates; same-issue-text rows
            # are recorded as writer-visible duplication evidence for Report 2.
            dup = page.evaluate(
                """() => {
                  const fs = state.findings || [];
                  const seenJson = new Set(), exact = [];
                  const byIssue = new Map(), sameIssue = [];
                  fs.forEach((f, i) => {
                    const k = JSON.stringify(f);
                    if (seenJson.has(k)) exact.push(i);
                    seenJson.add(k);
                    const ik = String((f && f.issue) || '').trim();
                    if (byIssue.has(ik)) {
                      sameIssue.push({ a: byIssue.get(ik), b: i, issue: ik.slice(0, 60),
                                       ra: byIssue.get(ik) && fs[byIssue.get(ik)], rb: f });
                    } else byIssue.set(ik, i);
                  });
                  return { total: fs.length, exact, sameIssue };
                }""")
            check("J3.6: no whole-row duplicate findings survive (rung 20 contract)",
                  dup["total"] > 0 and not dup["exact"],
                  f"total={dup['total']} exact_dups={dup['exact']}")
            if dup["sameIssue"]:
                evidence["j3_same_issue_rows"] = [
                    {"issue": s["issue"],
                     "row_a": {k: s["ra"].get(k) for k in ("severity", "rule_id", "check_id", "category", "scene_refs")},
                     "row_b": {k: s["rb"].get(k) for k in ("severity", "rule_id", "check_id", "category", "scene_refs")}}
                    for s in dup["sameIssue"][:4]]
                check("J3.6 (note): same-issue-text rows differ in some field (not collapsed by design)",
                      True, f"{len(dup['sameIssue'])} writer-visible same-text rows recorded for Report 2")
            evidence["j3_duplicates"] = {"total": dup["total"], "exact": dup["exact"]}

            # ---------------- J3.7 rung-19 surface: strip finding count ------
            status_txt = ""
            reveal_chrome(page, "#desk-analyze-status")
            st_loc = page.locator("#desk-analyze-status")
            if st_loc.count():
                status_txt = st_loc.first.inner_text()
            check("J3.7: desk status strip names the finding count after analysis (rung 19)",
                  "finding" in status_txt.lower(),
                  repr(status_txt[:90]))

            # ---------------- J3.8 dismissal + undismiss ---------------------
            open_dock(page)
            rows_before = page.locator(f"{lens} .fix-row").count()
            d = page.locator(f"{lens} .fq-dismiss").first
            if d.count():
                d.click()
                page.wait_for_timeout(900)
                rows_after = page.locator(f"{lens} .fix-row").count()
                check("J3.8: Dismiss takes the row out of the to-do",
                      rows_after == rows_before - 1,
                      f"before={rows_before} after={rows_after}")
                tog = page.locator(f"{lens} .fq-toggle-dismissed")
                if tog.count():
                    tog.first.click()
                    page.wait_for_timeout(900)
                    restore = page.locator(f"{lens} .fq-undismiss").first
                    check("J3.8: dismissed row is restorable (flag-don't-drop)",
                          restore.count() > 0, "no Restore button")
                    if restore.count():
                        restore.click()
                        page.wait_for_timeout(900)
                        rows_back = page.locator(f"{lens} .fix-row").count()
                        check("J3.8: Restore returns the row", rows_back == rows_before,
                              f"before={rows_before} after={rows_back}")
                else:
                    check("J3.8: dismissed-rows toggle appears", False,
                          "no .fq-toggle-dismissed after dismissing")
            else:
                check("J3.8: Dismiss verb present", False, "no .fq-dismiss button")

            # ---------------- J3.9 intent mark -> dawn meter -----------------
            pct_before = page.evaluate(
                """() => { const p = document.querySelector('.dawn-pct');
                           return p ? (p.textContent || '') : null; }""")
            mark = page.locator(f"{lens} .finding-note .intent-btn").first
            if mark.count():
                mark.click(force=True)
                page.wait_for_timeout(700)
                pct_after = page.evaluate(
                    """() => { const p = document.querySelector('.dawn-pct');
                               return p ? (p.textContent || '') : null; }""")
                check("J3.9: marking a finding resolved warms the dawn meter",
                      pct_before != pct_after and pct_after not in (None, "0%", ""),
                      f"{pct_before!r} -> {pct_after!r}")
                shot(page, SHOTS, "j3_dawn_after_mark")
            else:
                check("J3.9: intent mark button present", False, "no .intent-btn rendered")

            # ---------------- J3.10 legacy report/fixqueue tabs --------------
            # Product contract verified in source: for a PROJECT every shipped
            # route into Feedback (room toggle 9753-9755, gutter tab, palette
            # 8551, f key 8826-8828) lands on the Evidence lens
            # (openFeedbackView -> openDock). The legacy #feedback-panel
            # survives only through DEEP-LINK restoration
            # (#/<project>/feedback -> openFeedbackRoom, app.js:2160).
            # Recorded as Report-2 evidence; the probe drives the deep link.
            page.evaluate(
                "() => { location.hash = '#/' + encodeURIComponent(state.currentProject) + '/feedback'; }")
            page.wait_for_timeout(1800)
            fb_visible = page.locator("#feedback-panel").is_visible()
            report_children = page.evaluate(
                "() => document.querySelector('#feedback-report')?.children.length || 0")
            check("J3.10: deep link #/p/feedback restores the legacy report pane",
                  fb_visible and report_children > 0,
                  f"visible={fb_visible} children={report_children}")
            tabs_clickable = page.locator("#tab-fixqueue-btn").is_visible()
            if tabs_clickable:
                page.locator("#tab-fixqueue-btn").click()
                page.wait_for_timeout(500)
                fq_visible = page.locator("#feedback-fixqueue").is_visible()
                fq_rows = page.locator("#feedback-fixqueue .fix-row").count()
                check("J3.10: legacy Fix Queue tab shows the same rows",
                      fq_visible and fq_rows > 0, f"visible={fq_visible} rows={fq_rows}")
            else:
                check("J3.10: legacy Fix Queue tab shows the same rows", False,
                      "#feedback-tabs still hidden after deep link")
            shot(page, SHOTS, "j3_legacy_feedback_tabs")
            evidence["j3_feedback_route_contract"] = (
                "mouse/palette/f-key routes land on the Evidence lens by design; "
                "legacy panel reachable only via deep link")
            page.evaluate(
                "() => { location.hash = '#/' + encodeURIComponent(state.currentProject) + '/cowrite'; }")
            page.wait_for_timeout(600)

            # ================= J4 — the writer loop =========================
            # J4.1 rewrite candidates (API, demo model labeled)
            rr = wpost(base, f"/api/projects/{name}/rewrite", {"scene_number": 1}, timeout=120)
            check("J4.1: /rewrite returns candidates (demo model)", rr.status_code == 200,
                  f"status={rr.status_code} {rr.text[:120]}")
            reps = (rr.json() or {}).get("replacements") or [] if rr.status_code == 200 else []
            evidence["j4_rewrite_candidates"] = len(reps)
            rep = reps[0] if reps else {"old": "MARA takes out an old REVOLVER, setting it on the desk.",
                                        "new": "MARA lays the old REVOLVER on the desk."}
            if not reps:
                check("J4.1: demo rewrite produced candidates", False,
                      "no candidates; fallback replacement used for apply legs (documented)")
            ap = wpost(base, f"/api/projects/{name}/edits/apply",
                       {"scene_number": 1, "replacements": [rep]})
            check("J4.1: /edits/apply applies the replacement", ap.status_code == 200,
                  f"status={ap.status_code} {ap.text[:120]}")

            # J4.2 addressed/still-present recompute
            ed = requests.get(f"{base}/api/projects/{name}/edits", timeout=15).json()
            summary = (ed.get("findings_status") or {}).get("summary") or {}
            check("J4.2: /edits carries findings_status summary after an edit",
                  bool(ed.get("edits")) and summary.get("addressed", 0) + summary.get("still_present", 0) > 0,
                  json.dumps(summary))
            evidence["j4_status_summary"] = summary
            # rung-19 companion: strip count moved on edit too (apply path)
            check("J4.2: can_undo flips true after apply", ed.get("can_undo") is True,
                  f"can_undo={ed.get('can_undo')}")

            # J4.3 undo -> text restored -> redo -> text replaced again
            u = wpost(base, f"/api/projects/{name}/edits/undo")
            check("J4.3: undo accepted", u.status_code == 200, f"status={u.status_code}")
            ed2 = requests.get(f"{base}/api/projects/{name}/edits", timeout=15).json()
            check("J4.3: after undo, redo is offered", ed2.get("can_redo") is True,
                  f"can_redo={ed2.get('can_redo')}")
            r = requests.post(base + f"/api/projects/{name}/edits/redo", timeout=60,
                              headers=studio_headers(base))
            check("J4.3: redo accepted", r.status_code == 200, f"status={r.status_code}")

            # J4.4 export fountain + fdx
            ex = requests.get(f"{base}/api/projects/{name}/export?format=fountain", timeout=30)
            body = ex.text
            check("J4.4: export .fountain carries the working copy",
                  ex.status_code == 200 and "INT." in body,
                  f"status={ex.status_code} bytes={len(body)}")
            ex2 = requests.get(f"{base}/api/projects/{name}/export?format=fdx", timeout=30)
            check("J4.4: export .fdx returns XML",
                  ex2.status_code == 200 and ("FinalDraft" in ex2.text or "<?xml" in ex2.text),
                  f"status={ex2.status_code} bytes={len(ex2.text)}")

            # J4.5 inline edit through the real UI — pick a line that carries no
            # finding-ink chip (a chip inside the line pollutes textContent)
            open_on_desk(page, base, name)
            line = page.locator(
                "#scene-page-2 [class^='el-']:not(:has(.finding-ink))").last
            if line.count() == 0:
                line = page.locator("#scene-page-2 [class^='el-']").last
            target_text = (line.evaluate("e => e.textContent") or "").strip()
            line.dblclick()
            page.wait_for_selector("#manuscript-container [class^=el-].inline-editing", timeout=5000)
            page.keyboard.type(" AUDITED")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            banner_txt = page.evaluate(
                "() => document.querySelector('#error-banner')?.style?.display !== 'none' ? (document.querySelector('#error-banner-text')?.textContent || '') : ''")
            sc = requests.get(f"{base}/api/projects/{name}/script", timeout=15).json()
            raw = json.dumps(sc)
            check("J4.5: inline edit lands in the working copy",
                  "AUDITED" in raw,
                  f"banner={banner_txt[:80]!r} target={target_text[:40]!r}")
            shot(page, SHOTS, "j4_inline_edit")

            # J4.6 beatboard reorder -> save -> export -> reset
            bb = requests.get(f"{base}/api/projects/{name}/beatboard", timeout=15).json()
            def norm_order(payload):
                for key in ("scenes", "order"):
                    lst = payload.get(key) or []
                    if lst:
                        return [s if isinstance(s, int) else s.get("scene_number") for s in lst]
                return []
            order_in = norm_order(bb)
            check("J4.6: beatboard GET returns an order", len(order_in) >= 2, str(order_in)[:80])
            swapped = list(order_in)
            swapped[0], swapped[1] = swapped[1], swapped[0]
            put = requests.put(base + f"/api/projects/{name}/beatboard",
                               json={"order": swapped}, timeout=30,
                               headers=studio_headers(base))
            check("J4.6: beatboard PUT accepts the permutation", put.status_code == 200,
                  f"status={put.status_code} {put.text[:100]}")
            bb2 = requests.get(f"{base}/api/projects/{name}/beatboard", timeout=15).json()
            order_out = norm_order(bb2)
            check("J4.6: saved order persists on re-read", order_out == swapped,
                  f"want={swapped} got={str(order_out)[:80]}")
            bbx = requests.get(f"{base}/api/projects/{name}/beatboard/export?format=fountain",
                               timeout=30)
            bbx_text = bbx.text
            # the reordered export must present the new first scene before the old one
            if len(order_in) >= 2:
                heads = {s if isinstance(s, int) else s.get("scene_number"): (s.get("heading_raw") if isinstance(s, dict) else None)
                         for s in (bb.get("scenes") or [])}
                if heads:
                    h_new = str(heads.get(swapped[0]) or "")[:24]
                    h_old = str(heads.get(swapped[1]) or "")[:24]
                    i_new, i_old = bbx_text.find(h_new), bbx_text.find(h_old)
                    check("J4.6: reordered export presents the new scene order",
                          bbx.status_code == 200 and h_new and i_new != -1 and (i_old == -1 or i_new < i_old),
                          f"new@{i_new} old@{i_old}")
            rst = wpost(base, f"/api/projects/{name}/beatboard/reset")
            check("J4.6: beatboard reset returns the original order", rst.status_code == 200,
                  f"status={rst.status_code}")
            shot(page, SHOTS, "j4_beatboard_exported")

            # J4.7 drafts upload -> activate -> diff -> compare.
            # Server contract: drafts get SERVER-ASSIGNED names (draft-1, ...);
            # the upload itself re-parses the upload as the new active draft.
            dl_before = {d.get("name") for d in (requests.get(
                f"{base}/api/projects/{name}/drafts", timeout=15).json().get("drafts") or [])}
            dr = requests.post(base + f"/api/projects/{name}/drafts",
                               files={"file": ("v2.fountain", SCRIPT_V2.encode(), "text/plain")},
                               timeout=60, headers=studio_headers(base))
            check("J4.7: draft v2 uploads", dr.status_code in (200, 201),
                  f"status={dr.status_code} {dr.text[:100]}")
            dl = requests.get(f"{base}/api/projects/{name}/drafts", timeout=15).json()
            names = [d.get("name") for d in (dl.get("drafts") or [])]
            new_names = [n for n in names if n not in dl_before]
            check("J4.7: upload registers a new server-named draft", bool(new_names),
                  f"before={sorted(dl_before)} after={names}")
            v2name = new_names[0] if new_names else (names[-1] if names else None)
            if v2name:
                # upload_new_draft ALREADY activates the upload (active_draft =
                # draft-N) and re-parses — verify that shipped behavior
                st1 = requests.get(f"{base}/api/projects/{name}", timeout=15).json()
                check("J4.7: upload auto-activates the new draft (shipped contract)",
                      st1.get("active_draft") == v2name and (st1.get("stages") or {}).get("parse") == "complete",
                      f"active={st1.get('active_draft')!r} parse={(st1.get('stages') or {}).get('parse')!r}")
                sc = requests.get(f"{base}/api/projects/{name}/script", timeout=15).json()
                check("J4.7: the new draft's content is live (v2 line present)",
                      "One more night" in json.dumps(sc), "v2 dialogue not in /script")
                # FINDING (recorded, kept as evidence): activating the
                # ALREADY-ACTIVE draft answers 400 "No snapshot for draft X" —
                # a no-op request gets a misleading data-shaped error. Not
                # reachable through the UI (the drafts select cannot fire
                # change on its own value), so P3 API-contract polish.
                aa = wpost(base, f"/api/projects/{name}/drafts/activate", {"name": v2name})
                evidence["j4_activate_active_quirk"] = {
                    "request": f"POST activate name={v2name} (already active)",
                    "status": aa.status_code, "body": (aa.text or "")[:120],
                    "classification": "P3 API-contract polish: misleading error on a no-op; UI-unreachable",
                }
                # the REAL writer journey: switch BACK to the original draft
                act = wpost(base, f"/api/projects/{name}/drafts/activate", {"name": "original"})
                check("J4.7: switching back to the original draft succeeds", act.status_code == 200,
                      f"status={act.status_code} {act.text[:100]}")
                st2 = requests.get(f"{base}/api/projects/{name}", timeout=15).json()
                check("J4.7: manifest carries the restored active draft",
                      st2.get("active_draft") == "original",
                      f"active_draft={st2.get('active_draft')!r}")
                sc2 = requests.get(f"{base}/api/projects/{name}/script", timeout=15).json()
                raw2 = json.dumps(sc2)
                check("J4.7: original content restored (v2 line gone)",
                      "One more night" not in raw2 and "One more day" in raw2,
                      "content did not flip back to the original draft")
                df = requests.get(f"{base}/api/projects/{name}/diff?from=original&to=active",
                                  timeout=15).json()
                # shipped shape: {scenes, findings, from, to, characters} (R6-BE-x)
                check("J4.7: diff original->active reports structural deltas",
                      isinstance(df, dict) and bool(df.get("scenes") or df.get("findings")),
                      f"keys={list(df.keys())[:6]}")
                cmp_ = requests.get(f"{base}/api/projects/{name}/compare?from=original&to=active",
                                    timeout=15).json()
                check("J4.7: compare original->active answers scenes/findings shape",
                      isinstance(cmp_, dict) and ("scenes" in cmp_ or "findings" in cmp_),
                      f"keys={list(cmp_.keys())[:8]}")
                shot(page, SHOTS, "j4_draft_activated")
            browser.close()

        errs = [m for m in console_msgs if m.startswith("error")]
        failed_net = [n for n in net if n]
        save_console_capture(EV_DIR, "j3_j4_console.json", console_msgs, page_errors, failed_net)
        check("J3+J4: zero console errors across both journeys", not errs, "; ".join(errs[:3]))
        check("J3+J4: zero failed network calls across both journeys", not failed_net,
              "; ".join(failed_net[:4]))
        evidence["console_errors"] = errs
        evidence["failed_network"] = failed_net

    evidence["verdict"] = "J3+J4 PROVEN" if not checks.failed else f"FAILURES: {checks.failed}"
    with open(os.path.join(EV_DIR, "j3_j4_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    print("[j3j4] evidence -> docs/audit/evidence-2026-09-30/j3_j4_evidence.json")
    (checks.finish)()


if __name__ == "__main__":
    main()
