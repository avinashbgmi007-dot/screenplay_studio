# stage_pain3_session.py — PRE-STAGE the felt-validation session on Pain_3.
#
# This is NOT the felt gate and NOT a probe. It is the staging for one:
# it puts a real full-length script into the live desk, runs the FIRST pass,
# and leaves the desk COLD — no snapshot, so no arrival strip yet. The writer
# then does the felt work (marks, edits, the SECOND pass) on their own screen.
# The snapshot is self-seeding: the writer's first page load records pass 1's
# ids with a null payload (strip blank, honest first pass); their pass 2 diffs
# against it and THE STRIP APPEARS — which is the felt moment (checklist step
# 3). Pre-seeding it here would destroy that moment, so we deliberately don't.
#
# Why pre-stage: pass 1 on a full-length script is dead time for the writer.
# Why stop before pass 2: the arrival strip's first appearance IS the data.
#
# Idempotent: re-running reuses the staged project, re-runs pass 1, and
# re-colds the desk (removes any snapshot a prior run left behind).
#
#   python docs/audit/stage_pain3_session.py            # prep + report
#   python docs/audit/stage_pain3_session.py --shots    # also baseline shots
#
# ENGINE CAVEAT (must be stated to the writer): the built-in demo engine is
# deterministic but SHALLOW — it emits low/medium severities only, never
# "high". Pain_3 therefore yields ZERO high findings, and the desk's default
# filter is highs-only, so a fresh board opens EMPTY. That is an engine
# artifact, not a product finding: widen the filter (Medium + Low) to see the
# real 17. Any felt judgement about "highs-only ink amount" is demo-limited.

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter

REPO = r"E:\screenplay-studio_1_verdent"
sys.path.insert(0, os.path.join(REPO, "tests"))
sys.path.insert(0, REPO)

from e2e_browser_common import start_studio          # noqa: E402
from screenplay_studio.revision import compute_finding_id  # noqa: E402

PDF = r"C:\Users\Avinash-Pro\Downloads\Pain_3_updated_FULL.pdf"
PROJECTS_DIR = os.path.join(REPO, "studio_projects")
TITLE = "Pain 3"
NAME = "Pain_3"          # safe_name(sanitised title) — the desk's dir name
SHOTS_DIR = os.path.join(REPO, "docs", "audit")


def _get(base, path, timeout=120):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(base, path, payload=None, timeout=1800):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", action="store_true",
                    help="also capture baseline screenshots of each surface")
    args = ap.parse_args()

    if not os.path.exists(PDF):
        print("MISSING SCRIPT:", PDF)
        return 2
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    project_dir = os.path.join(PROJECTS_DIR, NAME)

    # ---- boot a private prep server on the live desk dir ----
    st = start_studio(projects_dir=PROJECTS_DIR)
    base = st.base_url
    print("prep server:", base)

    try:
        # ---- 1. create the project (idempotent) ----
        existing = _get(base, "/api/projects")
        plist = existing if isinstance(existing, list) else (existing.get("projects") or [])
        have = {p.get("project") for p in plist if isinstance(p, dict)}
        if NAME in have:
            print(f"[1/4] project '{NAME}' already staged — reusing")
        else:
            import requests
            with open(PDF, "rb") as f:
                r = requests.post(base + "/api/projects",
                                  files={"file": ("Pain_3_updated_FULL.pdf", f,
                                                  "application/pdf")},
                                  data={"title": TITLE}, timeout=900)
            if r.status_code >= 300:
                print("UPLOAD FAILED", r.status_code, (r.text or "")[:200])
                return 1
            print(f"[1/4] uploaded + parsed -> {r.json().get('project')}")

        # ---- 2. first pass (idempotent: force re-run keeps the report fresh) ----
        # analyze returns _manifest_summary(m): model_id + failed_categories +
        # stages ride the manifest, NOT a bespoke result object. Surface an
        # analyze failure loudly instead of reporting a phantom "complete".
        try:
            res = _post(base, f"/api/projects/{NAME}/analyze", {"force": True})
        except urllib.error.HTTPError as ex:
            print(f"[2/4] ANALYZE FAILED {ex.code}: {(ex.read() or b'').decode()[:300]}")
            return 1
        stages_now = res.get("stages") or {}
        print(f"[2/4] pass 1 → analyze stage={stages_now.get('analyze')} "
              f"(model={res.get('model_id')}, "
              f"failed_categories={res.get('failed_categories')})")
        if stages_now.get("analyze") != "complete":
            print(f"[2/4] ABORT: analyze stage is {stages_now.get('analyze')!r}, "
                  f"errors={res.get('errors')}")
            return 1

        report = _get(base, f"/api/projects/{NAME}/report")
        findings = report.get("findings") or []
        ids = [compute_finding_id(f) for f in findings]
        distinct = sorted(set(ids))
        sev = Counter((f.get("severity") or "?").lower() for f in findings)
        cat = Counter((f.get("category") or "?") for f in findings)
        vs = report.get("verification_summary") or {}

        # ---- 3. leave the desk COLD (no snapshot) ----
        # The snapshot is self-seeding: the writer's first page load calls
        # GET /edits, which (no file yet) records THIS generation's ids with a
        # null payload and shows no strip — honest first pass. Their own pass 2
        # then diffs against it, and THE STRIP APPEARS. That appearance is the
        # felt moment (checklist step 3), so we must NOT pre-seed it. If a
        # prior run (or its --shots page load) already wrote one, remove it.
        # (path mirrors revision.last_pass_path: <project_dir>/last_pass.json)
        snap_file = os.path.join(project_dir, "last_pass.json")
        if os.path.exists(snap_file):
            os.remove(snap_file)

        # ---- 4. verify the cold contract, then re-cold it ----
        e = _get(base, f"/api/projects/{NAME}/edits")
        first_lp = e.get("last_pass")
        cold_ok = first_lp is None
        if os.path.exists(snap_file):     # that GET re-seeded it — ditch it again
            os.remove(snap_file)
        print(f"[3/4] cold contract: first /edits after a pass returns "
              f"last_pass={first_lp!r} ({'OK honest blank' if cold_ok else 'UNEXPECTED'})")
        print(f"[4/4] desk left COLD: last_pass.json present = "
              f"{os.path.exists(snap_file)} (the writer's pass 2 makes the first strip)")

        print("\n================ STAGED STATE ================")
        print(f"  desk project   : {NAME}  ({PROJECTS_DIR})")
        print(f"  script         : Pain_3_updated_FULL.pdf "
              f"({os.path.getsize(PDF)//1024} KB, full length)")
        print(f"  findings       : {len(findings)} rows / {len(distinct)} distinct ids")
        print(f"  severity mix   : {dict(sev)}")
        print(f"  categories     : {dict(cat)}")
        print(f"  quote trust    : {vs.get('verified', 0)} of "
              f"{sum(vs.values()) or 0} verified")
        print(f"  report.md      : {os.path.exists(os.path.join(project_dir, 'report.md'))}")
        print(f"  snapshot       : {os.path.exists(snap_file)}  "
              f"(COLD = no strip until the writer's own pass 2)")

        hi = sev.get("high", 0)
        if hi == 0:
            print("\n  !! EMPTY-BOARD CAVEAT: 0 high findings on this script, and the")
            print("     desk filter defaults to highs-only. The writer must widen the")
            print("     filter (Medium + Low chips) on arrival or the board reads empty.")
            print("     Engine artifact (the demo craft model emits low/medium only) —")
            print("     NOT a product finding. With a real model, expect highs.")
            print(f"     Widen to see: {len(distinct)} distinct findings.")

        # ---- optional baseline shots ----
        if args.shots:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1480, "height": 940})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(base, timeout=20000)
            pg.wait_for_timeout(1600)
            pg.screenshot(path=os.path.join(SHOTS_DIR, "pain3-session-00-dashboard.png"))
            # target Pain_3 by NAME — the shelf sorts by title, so `.first`
            # would open "A courier story…", not ours.
            opened = pg.evaluate(
                """async (n) => { await openProject(n); return state.currentProject; }""",
                NAME)
            print("  opened project:", opened)
            pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=25000)
            pg.wait_for_timeout(1200)
            pg.screenshot(path=os.path.join(SHOTS_DIR, "pain3-session-01-manuscript.png"))
            pg.evaluate("() => openDock('evidence')")
            pg.wait_for_timeout(800)
            # widen the filter through the REAL chips (High/Medium/Low) — a
            # direct rerender() call is impossible (it is a local const inside
            # buildFindingFilterRow); the buttons re-render for us.
            for label in ("Medium", "Low"):
                try:
                    pg.locator(".dock-filter-row .fchip",
                                has_text=label).first.click(timeout=4000)
                    pg.wait_for_timeout(350)
                except Exception as ex:
                    print(f"  filter chip '{label}' not clicked:", str(ex)[:90])
            pg.wait_for_timeout(700)
            board = pg.evaluate("""() => {
              const lens=document.querySelector('.dock-lens[data-lens="evidence"]');
              const secs=[...lens.querySelectorAll('.dock-section')].map(s=>({
                t:((s.querySelector('.dock-section-title')||{}).textContent||'').slice(0,22),
                n:s.querySelectorAll('.finding-note').length})).filter(s=>s.n>0);
              return {
                reportRows: (state.findings||[]).length,
                distinctIds: (new Set(state.findingIds||[])).size,
                filter: (state.findingFilter.severities||[]).join('+'),
                currentScene: (typeof currentManuscriptScene==='function')?currentManuscriptScene():null,
                boardNotes: lens.querySelectorAll('.finding-note').length,
                pageInk: document.querySelectorAll('.finding-ink').length,
                quotedForInk: (state.findings||[]).filter(f=>(f.evidence_quote||'').trim().length>=2).length,
                sections: secs,
                hasLoopBtn: !!document.querySelector('.fchip-loop'),
                hasMassStrip: !!document.querySelector('.dock-mass-strip'),
                hasRuler: !!document.querySelector('.dock-ruler'),
                hasArrival: !!document.querySelector('.dock-arrival-strip')
              };
            }""")
            print("\n  baseline board (filter widened):", json.dumps(board, indent=2))
            pg.screenshot(path=os.path.join(SHOTS_DIR, "pain3-session-02-board-widened.png"))
            # the fix loop engaged (startLoop opens the dock + arms card 1)
            try:
                pg.evaluate("() => startLoop()")
                pg.wait_for_timeout(900)
                pg.screenshot(path=os.path.join(SHOTS_DIR, "pain3-session-03-loop.png"))
                looped = pg.evaluate("""() => ({
                  bar: !!document.getElementById('loop-bar'),
                  current: document.querySelectorAll('.finding-note.loop-current').length})""")
                print("  loop engaged:", json.dumps(looped))
            except Exception as ex:
                print("  loop shot skipped:", str(ex)[:100])
            print("  js errors during shots:", errs[:2] if errs else "none")
            b.close(); pw.stop()
            # the --shots page load called GET /edits, which re-seeded the
            # snapshot — re-cold the desk so the writer's pass 2 still makes
            # the first strip.
            if os.path.exists(snap_file):
                os.remove(snap_file)
                print("  desk re-cold after shots: last_pass.json removed")

        print("\n=============================================")
        print("NEXT (the writer's own screen — do NOT automate):")
        print("  1. launch the desk on 8500 (command in the run card)")
        print("  2. widen the filter · press the fix loop · mark 2-3 · edit 1 line")
        print("  3. run the SECOND pass → the arrival strip appears → answer the")
        print("     checklist at docs/REAL_WRITER_VALIDATION.md per surface")
        print("     (step 3 IS the strip's first appearance: it stays blank until now)")
    finally:
        st.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())