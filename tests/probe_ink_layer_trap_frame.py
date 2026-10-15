"""The Ink Layer's trap frame, in chromium, driven with a REAL refusal from the desk.

PR #6 left one check open: the prototype's refusal state (`row[data-cast="stale"]`,
the sentence kept in the fold) was wired to an error the desk never raised, so it
could only ever be seen through the offline `#drift` seam. `feature/stale-proposal-guard`
raises that error. This probe runs the two halves against each other, live:

  REAL   the live adapter's `/rewrite` (the producer filter runs on the desk)
  REAL   a refused `POST /edits/apply`, captured as the error object the live
         adapter itself throws — 400 `{"stale": true}` — and classified by the
         page's own `classifyApplyError`
  REAL   the gesture (`n` → `Enter` fold → `j` cast → `Enter` keep) and the DOM
         state it leaves behind, in chromium, against the real page

  CUT BY HAND  the take. The demo model skips slug lines on purpose (`demo_model.py`:
  "Skip anything that looks like a slug line ... so the demo always moves visible
  text") while every finding on both loaded projects anchors to a scene heading, so
  no model-produced take can land on a wet row on these projects. The take's `old`
  is therefore the wet row's own text, handed to the page through the adapter seam
  the prototype's own suite documents (`window.InkLayer.source`), and the refusal
  that comes back is the desk's, not a stub.

Run:  STUDIO_TOKEN=… python tests/probe_ink_layer_trap_frame.py   (desk up on :8501)
"""
import json
import os
import sys

import requests
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8501").rstrip("/")
PROJECT = os.environ.get("PROBE_PROJECT", "Pain_3")
SCENE = int(os.environ.get("PROBE_SCENE", "1"))
TOKEN = os.environ["STUDIO_TOKEN"]
PAGE = f"{BASE}/preview-ink-layer/index.html?project={PROJECT}"
SHOTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "impl-shots", "runs", "latest"))

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))


def main():
    os.makedirs(SHOTS, exist_ok=True)
    console, applies = [], []

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
        pg.on("response", lambda r: applies.append(r.status) if "/edits/apply" in r.url else None)
        pg.goto(PAGE, wait_until="load")
        pg.wait_for_function("() => window.InkLayer?.state?.rows?.length > 0", timeout=90000)
        pg.wait_for_timeout(1000)

        # ---- 1. the live half: the page is on the desk, not the demo ---------
        boot = pg.evaluate("""() => {
            const S = window.InkLayer.state;
            return { name: S.source?.name || String(S.source).slice(0, 40),
                     rows: S.rows.length, wet: S.rows.filter(r => r.wet).length,
                     wetRow: (() => { const i = S.rows.findIndex(r => r.wet);
                        const r = S.rows[i]; return { i, text: r.text,
                        scene: r.scene?.scene_number, cast: r.el.dataset.cast }; })() };
        }""")
        print(f"\n  adapter={boot['name']!r} rows={boot['rows']} wet={boot['wet']}")
        print(f"  first wet row {boot['wetRow']['i']}: {boot['wetRow']['text']!r}")
        check("the page is driving the REAL desk adapter", boot["name"] == "live", boot["name"])

        # ---- 2. the producer filter, on the real route -----------------------
        prod = pg.evaluate("""async (scene) => {
            const core = await import('/preview-ink-layer/core.js');
            const payload = await window.InkLayer.state.source.rewrite('%(p)s', { scene_number: scene });
            const n = core.normalizeRewrite(payload);
            return { frames: (payload.replacements || []).length, takes: n.takes.length,
                     old: (n.takes[0]?.oldText || '').slice(0, 45),
                     cands: n.takes[0]?.candidates?.length ?? 0 };
        }""" % {"p": PROJECT}, SCENE)
        print(f"  live /rewrite scene {SCENE}: {json.dumps(prod)}")
        check("the real route still offers a usable take (the filter is not over-broad)",
              prod["frames"] >= 1 and prod["takes"] >= 1, json.dumps(prod))

        # ---- 3. the refusal, from the real route ----------------------------
        refused = pg.evaluate("""async () => {
            const core = await import('/preview-ink-layer/core.js');
            try {
                await window.InkLayer.state.source.apply('%(p)s', { scene_number: %(s)d,
                    replacements: [{ old: 'ZZZ-NOT-IN-THE-SCENE-AT-ALL', new: 'x' }] });
                return { unexpected: true };
            } catch (e) {
                return { status: e.status, stale: e.stale, body: e.body,
                         verdict: core.classifyApplyError(e) };
            }
        }""" % {"p": PROJECT, "s": SCENE})
        print(f"  live refusal: status={refused.get('status')} stale={refused.get('stale')} "
              f"verdict={json.dumps(refused.get('verdict'))[:90]}")
        check("the desk refuses a stale frame with 400 + stale:true",
              refused.get("status") == 400 and refused.get("stale") is True,
              json.dumps(refused)[:160])
        check("the page's own classifier reads the REAL body as the stale state",
              (refused.get("verdict") or {}).get("kind") == "stale",
              json.dumps(refused.get("verdict"))[:160])

        # ---- 4. the gesture, with that real refusal delivered ----------------
        # The seam is the prototype's own (`source` is exposed for its suite), and
        # what it throws is the error object the live adapter itself produced above
        # — same status, same body, same flag.
        pg.evaluate("""(refused) => {
            const S = window.InkLayer.state;
            const live = S.source;
            const i = S.rows.findIndex(r => r.wet);
            const text = S.rows[i].text;
            S.source = {
                name: 'live',
                script: (p) => live.script(p),
                findings: (p, o) => live.findings(p, o),
                summary: (p) => live.summary(p),
                rewrite: async () => ({ scene_number: S.rows[i].scene.scene_number,
                                        note: 'probe — a frame cut from the line itself',
                                        replacements: [{ old: text, new: text + ' — quieter.' }] }),
                apply: async () => { const e = new Error(refused.body.error);
                    e.status = refused.status; e.body = refused.body; e.stale = refused.stale;
                    throw e; },
                ping: () => live.ping(), undo: (p) => live.undo(p),
            };
        }""", refused)

        pg.keyboard.press("n")            # wet.next: walk to the first inked line
        pg.wait_for_timeout(600)
        pg.keyboard.press("Enter")        # fold.toggle: a fold that is open is asking to be rewritten
        pg.wait_for_timeout(600)
        pg.keyboard.press("j")            # cast.begin.next
        pg.wait_for_timeout(2000)
        mid = pg.evaluate("""() => { const S = window.InkLayer.state; const c = S.casting;
            return { i: S.focus, cast: S.rows[S.focus]?.el?.dataset.cast,
                     n: c?.candidates?.length ?? 0, target: c?.frame?.target ?? null,
                     ann: document.getElementById('annunciator').textContent }; }""")
        print(f"\n  j → cast={mid['cast']!r} candidates={mid['n']} "
              f"target={(mid['target'] or '')[:40]!r}")
        print(f"      annunciator: {mid['ann'][:130]!r}")
        check("the cast began on the wet row and got its take",
              mid["n"] > 0 and mid["cast"] == "active", json.dumps(mid)[:160])

        pg.keyboard.press("Enter")        # cast.apply — the trap frame's ⏎ keep
        pg.wait_for_timeout(2000)
        after = pg.evaluate("""() => { const S = window.InkLayer.state; const row = S.rows[S.focus];
            const voidEl = row?.fold?.querySelector('.cast-void');
            return { cast: row?.el?.dataset.cast,
                     delta: row?.el?.dataset.delta,
                     voidText: voidEl?.textContent || '',
                     ann: document.getElementById('annunciator').textContent,
                     lineText: row?.el?.textContent || '' }; }""")
        print(f"\n  ⏎ → data-cast={after['cast']!r} data-delta={after['delta']!r}")
        print(f"      fold: {after['voidText'][:150]!r}")
        print(f"      annunciator: {after['ann'][:150]!r}")
        check('the row is marked data-cast="stale" — the trap frame, in production',
              after["cast"] == "stale", str(after["cast"]))
        check("the refusal is printed in the fold, not unwound",
              "Stale proposal" in after["voidText"], after["voidText"][:160])
        check("the writer's own line is still the line (nothing was written)",
              after["lineText"].strip() == boot["wetRow"]["text"].strip(),
              repr(after["lineText"][:60]))
        pg.screenshot(path=os.path.join(SHOTS, "trap-frame-live.png"))
        # This probe ASKS for a 400 on purpose, so the browser's own "Failed to
        # load resource: … 400" line is expected and is not a script error. Every
        # other console error still fails the run.
        unexpected = [m for m in console if "400" not in m]
        check("no JS page errors beyond the refusal this probe asks for",
              not unexpected, "; ".join(unexpected)[:200])
        b.close()

    print(f"\n  /edits/apply responses seen: "
          f"{applies or 'none — the refusal rides the adapter error, as the page reads it'}")
    print(f"\n=== {sum(1 for _, ok, _ in checks if ok)} passed, "
          f"{sum(1 for _, ok, _ in checks if not ok)} failed ===")
    for name, ok, detail in checks:
        if not ok:
            print(f"FAILED: {name}: {detail}")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
