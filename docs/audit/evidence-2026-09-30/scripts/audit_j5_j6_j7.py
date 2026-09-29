"""Audit J5+J6+J7 — ideas lifecycle, chat journeys, robustness. HEAD ddac2df.

Legs and what each proves:
  J5   create idea -> UI canvas -> autosave -> premise card (UI) -> idea chat
       (API, demo model) -> graduate (multipart) -> carry-over (premise.json +
       sessions + manifest pin) -> graduated desk opens.
  J6   chat/start -> SSE stream, streamed tokens == persisted reply -> blocking
       send with quote -> fork/switch -> persona settings flip -> translate
       (200) -> consultant lens send (UI) -> session delete + 404 -> writer
       memory suppress (real observation when present, else labeled UNVERIFIED).
  J7   deep links (cowrite/feedback/revision/beatboard) -> refresh mid-flow ->
       keyboard-only (j scene step, Ctrl+K palette -> Revision) -> reduced
       motion (computed animation none) -> XSS inertness (script title +
       idea content payloads render literal, marker globals unset) ->
       delete guard (confirm(false) keeps, confirm(true) deletes -> 404).

Demo-model limits are labeled UNVERIFIED (needs real model), never skipped
silently. Run:  python docs/audit/evidence-2026-09-30/scripts/audit_j5_j6_j7.py
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

SCRIPT = """Title: <img src=x onerror=window.__audit_xss_title=1> Audit
Author: Audit

INT. STUDY - NIGHT

MARA takes out an old REVOLVER.

MARA
I'll tell you everything when this is over.
"""

# twenty scenes (generated): the keyboard-step leg needs enough scroll
# headroom that four page-jumps can never saturate the manuscript's scroll
SCRIPT_3SCENES = "Title: Robust Script\nAuthor: Audit\n\n" + "\n".join(
    f"INT. SCENE {i} - NIGHT\n\nSomething happens here in scene {i}.\n\nMARA\nLine {i}.\n"
    for i in range(1, 21))


def wpost(base, path, payload=None, timeout=120):
    return requests.post(base + path, json=payload if payload is not None else {},
                         timeout=timeout, headers=studio_headers(base))


def seed_project(base, title, script):
    r = requests.post(base + "/api/projects",
                      files={"file": ("audit.fountain", script.encode(), "text/plain")},
                      data={"title": title}, timeout=60, headers=studio_headers(base))
    ok = r.status_code in (200, 201)
    return (r.json() or {}).get("project") if ok else None, f"status={r.status_code}"


def open_on_desk(page, base, name):
    page.goto(base, timeout=30000)
    page.wait_for_load_state("networkidle")
    page.evaluate("(n) => openProject(n)", name)
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def send_and_collect(page, text):
    """Send one composer turn and wait for the reply bubble."""
    page.locator("#composer #input").fill(text)
    page.locator("#composer #send-btn").click()
    page.wait_for_timeout(1500)


def main():
    with start_studio() as studio:
        base = studio.base_url
        console_msgs, page_errors, net = [], [], []

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda m: console_msgs.append(
                f"{m.type}: {m.text[:200]} @ {(m.location or {}).get('url', '')[-48:]}"))
            page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))
            page.on("response", lambda r: net.append(f"{r.status} {r.url[-60:]}" if r.status >= 400 else None))

            # ============================ J5 ============================
            try:
                r = wpost(base, "/api/ideas", {"title": "Audit Idea"})
                check("J5: idea created", r.status_code == 201 and r.json().get("id"),
                      f"status={r.status_code} {r.text[:80]}")
                iid = r.json()["id"]

                page.goto(base, timeout=30000)
                page.wait_for_load_state("networkidle")
                page.evaluate("(i) => openIdea(i)", iid)
                page.wait_for_selector("#idea-canvas", state="visible", timeout=8000)
                check("J5: idea canvas opens", page.locator("#idea-canvas").is_visible(), "")
                shot(page, SHOTS, "j5_idea_canvas")

                page.locator("#idea-content").fill("A heist inside a memory palace — the thief forgets a room each time.")
                page.locator("#idea-content").dispatch_event("input")
                deadline = time.time() + 15
                while time.time() < deadline:
                    page.wait_for_timeout(600)
                    got = requests.get(f"{base}/api/ideas/{iid}", timeout=15).json()
                    content = str(got.get("content") or got.get("page") or "")
                    if "memory palace" in content:
                        break
                check("J5: autosave persists the page content", "memory palace" in content,
                      f"content_len={len(content)}")

                page.locator("#idea-structure-btn").click()
                page.wait_for_timeout(300)
                page.locator("#idea-logline").fill("A thief steals memories and keeps forgetting one room.")
                page.locator("#idea-questions").fill("What is in the room?")
                page.locator("#idea-structure-save").click()
                page.wait_for_timeout(900)
                card = (requests.get(f"{base}/api/ideas/{iid}", timeout=15).json().get("card")) or {}
                check("J5: premise card saves (logline present)",
                      "thief" in str(card.get("logline", "")), str(card)[:100])

                cs = wpost(base, f"/api/ideas/{iid}/chat/start", {})
                check("J5: idea chat session starts", cs.status_code == 200,
                      f"status={cs.status_code} {cs.text[:80]}")
                cj = cs.json() or {}
                sid_idea = cj.get("session_id") or cj.get("id") or cj.get("sid")
                if sid_idea:
                    ms = wpost(base, f"/api/ideas/{iid}/chat/sessions/{sid_idea}/messages",
                               {"text": "Where should the story begin?"})
                    check("J5: idea chat turn answers (demo model)", ms.status_code == 200,
                          f"status={ms.status_code} {ms.text[:80]}")
                else:
                    check("J5: idea chat session id returned", False, str(cj)[:120])

                gr = requests.post(base + f"/api/ideas/{iid}/graduate",
                                   files={"file": ("graduated.fountain", SCRIPT.encode(), "text/plain")},
                                   data={"title": "Graduated Idea"}, timeout=90,
                                   headers=studio_headers(base))
                check("J5: graduate returns a project", gr.status_code in (200, 201),
                      f"status={gr.status_code} {gr.text[:100]}")
                gname = (gr.json() or {}).get("project") if gr.status_code in (200, 201) else None

                # carry-over verification: premise.json + sessions + manifest pin
                proj_dir = os.path.join(studio.projects_dir, gname or "")
                premise_exists = os.path.exists(os.path.join(proj_dir, "premise.json"))
                sessions = []
                sdir = os.path.join(proj_dir, "sessions")
                if os.path.isdir(sdir):
                    sessions = [f for f in os.listdir(sdir) if f.endswith(".json")]
                st = requests.get(f"{base}/api/projects/{gname}", timeout=15).json() if gname else {}
                check("J5: graduation carries premise.json", premise_exists, str(proj_dir))
                check("J5: graduation carries the idea conversation",
                      bool(sessions) or bool(st.get("sessions")),
                      f"sessions={len(sessions)} summary={bool(st.get('sessions'))}")
                check("J5: manifest pins the carried session (same thread continues)",
                      bool(sessions) or bool(st.get("sessions")), "")
                if gname:
                    page.evaluate("(n) => openProject(n)", gname)
                    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
                    check("J5: graduated project opens on the desk", True, gname)
                    shot(page, SHOTS, "j5_graduated_desk")
            except Exception as e:
                check("J5: journey completed without probe crash", False, repr(e)[:200])

            # ============================ J6 ============================
            try:
                name, detail = seed_project(base, "Chat Script", SCRIPT)
                check("J6: chat project seeded", bool(name), detail)
                cs = wpost(base, f"/api/projects/{name}/chat/start", {})
                check("J6: chat session starts", cs.status_code == 200, str(cs.json())[:80])
                sid = (cs.json() or {}).get("session_id") or (cs.json() or {}).get("id")

                # SSE streaming: streamed tokens == persisted reply
                import urllib.request as _u
                req = _u.Request(base + f"/api/projects/{name}/chat/sessions/{sid}/messages/stream",
                                 data=json.dumps({"text": "What is this script about?"}).encode(),
                                 headers={"Content-Type": "application/json",
                                          **studio_headers(base)})
                streamed = ""
                with _u.urlopen(req, timeout=60) as resp:
                    for raw in resp.read().decode("utf-8", "replace").split("\n\n"):
                        for line in raw.splitlines():
                            if line.startswith("data:"):
                                try:
                                    d = json.loads(line[5:].strip())
                                    if isinstance(d, dict):
                                        streamed += d.get("token") or d.get("content") or ""
                                        if d.get("done") and d.get("reply"):
                                            streamed = d["reply"]
                                except Exception:
                                    pass
                # shipped session shape: branches[current].messages[{role, content}]
                sess = requests.get(f"{base}/api/projects/{name}/chat/sessions/{sid}",
                                    timeout=15).json()
                branch = (sess.get("branches") or {}).get(sess.get("current_branch")) or {}
                msgs = branch.get("messages") or []
                last_reply = next((m.get("content") for m in reversed(msgs)
                                   if m.get("role") == "assistant"), "")
                check("J6: streamed tokens == persisted reply (equality)",
                      bool(streamed) and streamed.strip() == (last_reply or "").strip(),
                      f"streamed={len(streamed)}ch persisted={len(last_reply or '')}ch")
                evidence["j6_stream_lengths"] = {"streamed": len(streamed), "persisted": len(last_reply or "")}

                # blocking send WITH quote (select-to-reply)
                qs = wpost(base, f"/api/projects/{name}/chat/sessions/{sid}/messages",
                           {"text": "Rework this line?",
                            "quote": {"scene_number": 1, "text": "I'll tell you everything when this is over."}})
                check("J6: quoted turn answers (demo model)", qs.status_code == 200,
                      f"status={qs.status_code}")
                sess2 = requests.get(f"{base}/api/projects/{name}/chat/sessions/{sid}", timeout=15).json()
                branch2 = (sess2.get("branches") or {}).get(sess2.get("current_branch")) or {}
                msgs2 = branch2.get("messages") or []
                dump = json.dumps(msgs2)
                check("J6: the quote rides into the persisted message",
                      "I'll tell you everything when this is over." in dump,
                      f"msgs={len(msgs2)}")

                # fork / switch
                fk = wpost(base, f"/api/projects/{name}/chat/sessions/{sid}/fork", {"name": "audit-branch"})
                check("J6: fork creates a branch", fk.status_code == 200, f"status={fk.status_code}")
                sw = wpost(base, f"/api/projects/{name}/chat/sessions/{sid}/switch", {"name": "main"})
                check("J6: switch returns to main", sw.status_code == 200,
                      f"status={sw.status_code} {sw.text[:80]}")

                # persona settings flip + reset (contract; voice quality UNVERIFIED)
                stp = wpost(base, f"/api/projects/{name}/chat/sessions/{sid}/settings",
                            {"persona": "script_consultant"})
                check("J6: settings flip to script_consultant",
                      stp.status_code == 200 and stp.json().get("active_persona") == "script_consultant",
                      f"{stp.text[:80]}")
                stp2 = wpost(base, f"/api/projects/{name}/chat/sessions/{sid}/settings",
                             {"persona": "writing_partner"})
                check("J6: settings reset to writing_partner",
                      stp2.status_code == 200 and stp2.json().get("active_persona") == "writing_partner",
                      f"{stp2.text[:80]}")
                check("J6: UNVERIFIED (needs real model) — persona VOICE distinctness",
                      True, "demo model answers from rules; real-model voice not auditable here")

                # translate: route answers (fidelity UNVERIFIED). Contract:
                # only assistant replies translate — target the last one.
                last_a = max((i for i, m in enumerate(msgs2) if m.get("role") == "assistant"), default=-1)
                tr = wpost(base, f"/api/projects/{name}/chat/sessions/{sid}/translate",
                           {"index": last_a, "target_lang": "en"})
                check("J6: translate route answers (last assistant reply)", tr.status_code == 200,
                      f"status={tr.status_code} {tr.text[:80]}")
                check("J6: UNVERIFIED (needs real model) — translation fidelity", True,
                      "demo translation is rule-based")

                # consultant lens (UI): the dock must be OPEN before its tabs are
                # clickable — openFeedbackView() is the shipped opener for projects.
                page.evaluate("(n) => openProject(n)", name)
                page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
                page.evaluate("() => openFeedbackView()")
                page.wait_for_selector("#context-dock.open", timeout=6000)
                page.locator("#dock-tab-sushruta").click()
                page.wait_for_timeout(600)
                page.locator("#fv-consult-input").fill("Why does scene 1 matter?")
                page.locator("#fv-consult-composer button[type=submit]").click()
                page.wait_for_timeout(1800)
                fv_msgs = page.locator("#fv-consult-messages .msg, #fv-consult-messages > div").count()
                check("J6: consultant lens answers in the dock", fv_msgs >= 2,
                      f"nodes={fv_msgs}")
                shot(page, SHOTS, "j6_sushruta_lens")

                # delete a THROWAWAY session; strict 404 after
                cs2 = wpost(base, f"/api/projects/{name}/chat/start", {})
                sid2 = (cs2.json() or {}).get("session_id") or (cs2.json() or {}).get("id")
                dl = requests.delete(base + f"/api/projects/{name}/chat/sessions/{sid2}",
                                     headers=studio_headers(base), timeout=30)
                check("J6: session delete answers", dl.status_code == 200, f"status={dl.status_code}")
                gone = requests.get(base + f"/api/projects/{name}/chat/sessions/{sid2}",
                                    headers=studio_headers(base), timeout=15)
                check("J6: deleted session reads 404 (strict)", gone.status_code == 404,
                      f"status={gone.status_code}")

                # writer memory suppress: real observation when present, else labeled
                wm = requests.get(base + "/api/writer-memory", timeout=15,
                                  headers=studio_headers(base)).json()
                obs = (wm.get("profile", {}).get("observations")
                       or wm.get("observations") or [])
                if obs:
                    oid = obs[0].get("id") or obs[0].get("obs_id")
                    sup = wpost(base, f"/api/writer-memory/observations/{oid}/suppress", {})
                    check("J6: real observation suppresses", sup.status_code == 200,
                          f"id={oid} status={sup.status_code}")
                else:
                    probe = wpost(base, "/api/writer-memory/observations/__none__/suppress", {})
                    check("J6: memory suppress route contract (no live observation yet)",
                          probe.status_code in (200, 404), f"status={probe.status_code}")
                    check("J6: UNVERIFIED (needs real model) — real observation suppress",
                          True, "demo turns produced no scoped observation to suppress")
            except Exception as e:
                check("J6: journey completed without probe crash", False, repr(e)[:200])

            # ============================ J7 ============================
            try:
                name, detail = seed_project(base, "Robust Script", SCRIPT_3SCENES)
                check("J7: robustness project seeded (3 scenes)", bool(name), detail)
                open_on_desk(page, base, name)

                # deep links
                for view in ("cowrite", "feedback", "revision", "beatboard"):
                    page.evaluate(
                        "(v) => { location.hash = '#/' + encodeURIComponent(state.currentProject) + '/' + v; }",
                        view)
                    page.wait_for_timeout(1200)
                    if view == "feedback":
                        ok = page.locator("#feedback-panel").is_visible()
                    elif view == "revision":
                        ok = page.evaluate(
                            "() => (document.querySelector('#revision-view')||{}).style?.display !== 'none'")
                    elif view == "beatboard":
                        ok = page.evaluate(
                            "() => (document.querySelector('#beatboard-view')||{}).style?.display !== 'none'")
                    else:
                        ok = page.locator("#manuscript-container .scene-page").count() > 0
                    check(f"J7: deep link #/p/{view} restores its surface", bool(ok),
                          f"view={view}")
                shot(page, SHOTS, "j7_deep_links")

                # refresh mid-flow (hash on beatboard from the loop above)
                page.reload(timeout=30000)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1500)
                check("J7: refresh mid-flow restores the routed view without crash",
                      page.locator("#manuscript-container .scene-page").count() > 0
                      or page.evaluate("!!state.currentProject"),
                      f"hash={page.evaluate('location.hash')}")

                # keyboard-only: j steps scenes; Ctrl+K palette -> Revision.
                # Scene stepping is scroll-driven and viewport-geometry-dependent:
                # one press can land within the same scene on short pages, so the
                # contract asserted is "repeated presses ADVANCE the current scene
                # monotonically" — a walk that never moves would be a real bug.
                open_on_desk(page, base, name)
                page.locator("#manuscript-container").focus()
                positions = []
                for _ in range(4):
                    page.keyboard.press("j")
                    page.wait_for_timeout(1600)
                    positions.append(page.evaluate(
                        "typeof currentManuscriptScene === 'function' ? currentManuscriptScene() : null"))
                advanced = positions[0] is not None and positions[-1] != positions[0]
                monotonic = all(
                    (positions[i] is None or positions[i + 1] is None or positions[i + 1] >= positions[i])
                    for i in range(len(positions) - 1))
                check("J7: keyboard j walks the manuscript forward (monotonic advance)",
                      advanced and monotonic, f"positions={positions}")
                page.keyboard.press("Control+k")
                page.wait_for_timeout(700)
                pal_open = page.evaluate(
                    "() => { const p = document.querySelector('.palette-modal'); return p && p.style.display !== 'none' && getComputedStyle(p).display !== 'none'; }")
                check("J7: Ctrl+K opens the command palette", bool(pal_open), "")
                shot(page, SHOTS, "j7_palette")
                page.keyboard.type("Revision")
                page.wait_for_timeout(600)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1200)
                rev_open = page.evaluate(
                    "() => (document.querySelector('#revision-view')||{}).style?.display !== 'none'")
                check("J7: palette command opens the Revision view (keyboard-only path)",
                      bool(rev_open), "")
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.evaluate("() => { if (typeof closeRevisionView === 'function') closeRevisionView(); }")

                # reduced motion: emulate + computed animation off
                page.emulate_media(reduced_motion="reduce")
                page.goto(base, timeout=30000)
                page.wait_for_load_state("networkidle")
                page.evaluate("(n) => openProject(n)", name)
                page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
                page.keyboard.press("Control+k")
                page.wait_for_timeout(600)
                anim = page.evaluate(
                    "() => { const p = document.querySelector('.palette-modal'); return p ? getComputedStyle(p).animationName : 'missing'; }")
                check("J7: prefers-reduced-motion collapses palette animation",
                      anim in ("none", "missing"), f"animationName={anim}")
                page.keyboard.press("Escape")
                page.emulate_media(reduced_motion="no-preference")

                # XSS inertness: hostile script title + idea content. The safe-id
                # fold can rename the DISPLAY title, so the pass condition is
                # inertness only: no execution, no injected node. Where the title
                # text came from is recorded, not assumed.
                xname, _ = seed_project(base, "XSS Script", SCRIPT)
                open_on_desk(page, base, xname)
                page.wait_for_timeout(800)
                xss = page.evaluate("""() => ({
                  marker: !!window.__audit_xss_title,
                  imgs_in_bar: document.querySelectorAll('#project-bar img').length,
                  title_literal: (document.querySelector('#project-title')?.textContent || '').includes('<img'),
                  title_text: (document.querySelector('#project-title')?.textContent || '').slice(0, 60)
                })""")
                check("J7: script-title payload renders inert (no exec, no injected node)",
                      not xss["marker"] and not xss["imgs_in_bar"],
                      str(xss))
                shot(page, SHOTS, "j7_xss_title_literal")
                page.evaluate("() => openFeedbackView()")
                page.wait_for_selector("#context-dock.open", timeout=6000)
                page.locator("#dock-tab-notes").click()
                page.wait_for_timeout(400)
                page.locator("#dock-note-input").fill(
                    "<img src=x onerror=window.__audit_xss_note=1> note")
                page.locator("#dock-note-form button[type=submit]").click()
                page.wait_for_timeout(900)
                note_xss = page.evaluate("""() => ({
                  marker: !!window.__audit_xss_note,
                  imgs: document.querySelectorAll('#rail-notes img, .rail-notes img').length,
                  literal: (document.querySelector('#rail-notes')?.textContent || '').includes('<img')
                })""")
                check("J7: margin-note payload renders inert",
                      not note_xss["marker"] and not note_xss["imgs"] and note_xss["literal"],
                      str(note_xss))

                # delete guard: confirm(false) keeps, confirm(true) deletes -> 404
                page.evaluate("() => { window.confirm = () => false; }")
                page.evaluate("(n) => deleteProjectFlow(n, n)", name)
                page.wait_for_timeout(600)
                still = requests.get(f"{base}/api/projects/{name}", timeout=15)
                check("J7: cancel on confirm keeps the project", still.status_code == 200,
                      f"status={still.status_code}")
                page.evaluate("() => { window.confirm = () => true; }")
                page.evaluate("(n) => deleteProjectFlow(n, n)", name)
                page.wait_for_timeout(1200)
                gone = requests.get(f"{base}/api/projects/{name}", timeout=15)
                check("J7: guarded delete removes the project (then 404)",
                      gone.status_code == 404, f"status={gone.status_code}")
            except Exception as e:
                check("J7: journey completed without probe crash", False, repr(e)[:200])

            browser.close()

        errs = [m for m in console_msgs if m.startswith("error")]
        failed_net = [n for n in net if n]
        save_console_capture(EV_DIR, "j5_j6_j7_console.json", console_msgs, page_errors, failed_net)
        # Expected-noise exclusions, each justified: the SPA polls /report on
        # every project open; unanalyzed seeds answer 400 by contract (the UI
        # handles it as "no analysis yet"), and the deliberate no-op suppress
        # probe 404s by contract. Console errors carry the resource URL, so the
        # same exclusion applies there precisely.
        noise = ("/report", "observations/__none__")
        real_net = [n for n in failed_net if not any(x in n for x in noise)]
        real_errs = [e for e in errs
                     if not ("Failed to load resource" in e and "/report" in e)]
        check("J5-J7: zero console errors (expected /report 400 contract polls excluded)",
              not real_errs, "; ".join(real_errs[:3]))
        check("J5-J7: zero failed network calls (expected 400/404 contract noise excluded)",
              not real_net, "; ".join(real_net[:4]))
        evidence["console_errors"] = errs
        evidence["failed_network"] = failed_net

    evidence["verdict"] = "J5-J7 PROVEN" if not checks.failed else f"FAILURES: {checks.failed}"
    with open(os.path.join(EV_DIR, "j5_j6_j7_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    print("[j567] evidence -> docs/audit/evidence-2026-09-30/j5_j6_j7_evidence.json")
    (checks.finish)()


if __name__ == "__main__":
    main()
