# validation-d3: finish the in-between legs the d2 probe could not reach.
#   * target the quote-visible edit via verification.matched_scene (the verified
#     finding carries EMPTY scene_refs -> d2's scene lookup was null -> 400)
#   * assert the STRUCTURAL GAP-5 fact: a writer edit does NOT re-key the finding
#     (analysis reads the parse-of-record), so ghosted_marks stays empty — the
#     ghosted RENDER path is covered by d6's seeded payload (H1) instead
#   * re-confirm the arithmetic is honest on a real duplicate-id report
import sys, os, json, tempfile
sys.path.insert(0, r"E:\screenplay-studio_1_verdent\tests")
sys.path.insert(0, r"E:\screenplay-studio_1_verdent")
import requests
from e2e_browser_common import start_studio
from playwright.sync_api import sync_playwright
from screenplay_studio.revision import compute_finding_id

SHOTS = r"C:\Users\Avinash-Pro\Downloads\GLM_5_3_SCRIPT_DOCTOR_HANDOFF\03_design_exploration\round-2-maximal\impl-shots"
PDF = r"C:\Users\Avinash-Pro\Downloads\gun_pen.pdf"

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   [" + str(detail) + "]"))

tmp = tempfile.TemporaryDirectory()
pd = os.path.join(tmp.name, "projects"); os.makedirs(pd)
st = start_studio(projects_dir=pd); base = st.base_url
with open(PDF, "rb") as f:
    requests.post(base + "/api/projects", files={"file": ("gun_pen.pdf", f, "application/pdf")},
                  data={"title": "Gun Pen"}, timeout=300)
NAME = "Gun_Pen"
def api(p): return requests.get(base + f"/api/projects/{NAME}" + p, timeout=60)
def analyze(): return requests.post(base + f"/api/projects/{NAME}/analyze", json={"force": True}, timeout=1800)
def rep(): return api("/report").json()
def ed(): return api("/edits").json()
def ids_of(r): return [compute_finding_id(f) for f in (r.get("findings") or [])]

# pass 1 + seed
analyze()
r1 = rep(); f1 = r1.get("findings") or []; ids1 = ids_of(r1)
print("P1", len(f1), "distinct", len(set(ids1)))
v = next(((i, f) for i, f in enumerate(f1)
          if (f.get("verification") or {}).get("status") == "verified" and f.get("evidence_quote")), None)
vid = ids1[v[0]] if v else None
vscene = (v[1].get("verification") or {}).get("matched_scene") if v else None
print("VERIFIED idx", v[0] if v else None, "id", vid, "quote", (v[1].get("evidence_quote") or "")[:50],
      "scene_refs", v[1].get("scene_refs"), "matched_scene", vscene)
check("verified finding locatable via verification.matched_scene", vscene is not None, vscene)
ed()  # seed snapshot (pass1 ids)

# intents: 2 addressed + 1 deferred, on findings OTHER than the one we edit.
# (GAP-5: the edited finding reads observed "addressed" from the working copy,
#  and observed status outranks a writer intent in findingDisposition — so a
#  deferred mark on the edit target would be masked. Park it on a survivor.)
marks = {}
_def_i = next((i for i in range(len(ids1)) if i not in (1, 2) and (not v or i != v[0])), None)
for idx, intent in ((1, "addressed"), (2, "addressed")):
    fid = ids1[idx]
    marks[fid] = intent
    requests.post(base + f"/api/projects/{NAME}/findings/intent",
                  json={"finding_id": fid, "intent": intent}, timeout=30)
if _def_i is not None:
    marks[ids1[_def_i]] = "deferred"
    requests.post(base + f"/api/projects/{NAME}/findings/intent",
                  json={"finding_id": ids1[_def_i], "intent": "deferred"}, timeout=30)
print("MARKS", json.dumps(marks), "deferred_idx", _def_i)

# quote-visible edit: rewrite the cited line WITHOUT the trigger -> id drift
if v:
    quote = v[1].get("evidence_quote")
    ap = requests.post(base + f"/api/projects/{NAME}/edits/apply",
                       json={"scene_number": vscene,
                             "replacements": [{"old": quote, "new": "MARA: It stays between us. (rewritten.)"}]},
                       timeout=60)
    print("APPLY", ap.status_code, (ap.text or "")[:160])

# pass 2
analyze()
r2 = rep(); ids2 = ids_of(r2); e2 = ed(); lp = e2.get("last_pass")
print("P2", len(ids2), "distinct", len(set(ids2)))
print("LAST_PASS", json.dumps(lp))
print("INTENTS", json.dumps(e2.get("finding_intents") or {}))
print("VS2", json.dumps(r2.get("verification_summary") or {}))
old_set, new_set = set(ids1), set(ids2)
exp_still, exp_fixed, exp_new = len(old_set & new_set), len(old_set - new_set), len(new_set - old_set)
exp_ghost = sorted(g for g in (old_set - new_set) if marks.get(g))
print("EXPECT set-truth still/fixed/new", exp_still, exp_fixed, exp_new, "ghosted", exp_ghost)
# GAP-5: a quote-visible edit does NOT re-key the finding (analysis reads the
# parse-of-record) — the id SURVIVES. The probe asserts the true structural fact
# instead; that is precisely why the strip's pass numbers can never mean writer
# progress, which is the whole reason GAP-5 exists.
check("STRUCTURAL (GAP-5): the cited finding's id SURVIVES the quote edit "
      "(analysis reads the parse, not the working copy)",
      bool(vid) and vid in new_set, f"vid={vid} in_new={vid in new_set if vid else None}")
check("STRUCTURAL (GAP-5): a survivor can never become a ghosted mark "
      "(ghosted needs a vanished id + an intent)",
      not (lp or {}).get("ghosted_marks"), (lp or {}).get("ghosted_marks"))
check("ghosted_marks == real intents on vanished ids",
      sorted(g.get("finding_id") for g in ((lp or {}).get("ghosted_marks") or [])) == exp_ghost,
      (lp or {}).get("ghosted_marks"))
check("ghosted entry carries its intent (deferred)",
      all(g.get("intent") == "deferred" for g in ((lp or {}).get("ghosted_marks") or [])),
      (lp or {}).get("ghosted_marks"))
# arithmetic exactness against set-truth
check("still_live == set-truth", (lp or {}).get("still_live") == exp_still,
      f"{(lp or {}).get('still_live')} vs {exp_still}")
check("fixed == set-truth", (lp or {}).get("fixed") == exp_fixed,
      f"{(lp or {}).get('fixed')} vs {exp_fixed}")
check("new == set-truth", (lp or {}).get("new") == exp_new,
      f"{(lp or {}).get('new')} vs {exp_new}")

# browser: arrival strip + ghosted summary + open-count contract
pw = sync_playwright().start(); b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
pg.goto(base, timeout=20000); pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000); pg.wait_for_timeout(800)
pg.evaluate("() => openDock()"); pg.wait_for_timeout(400)
pg.evaluate("() => setDockLens('evidence')"); pg.wait_for_timeout(1000)
dump = pg.evaluate("""() => ({
  strip:(document.querySelector('.dock-arrival-line')||{}).textContent||null,
  scope:(document.querySelector('.dock-arrival-scope')||{}).textContent||null,
  draft:(document.querySelector('.dock-arrival-draft')||{}).textContent||null,
  ghosted:(document.querySelector('.dock-ghosted-summary')||{}).textContent||null,
  ghostedHTML:(()=>{const g=document.querySelector('.dock-ghosted-summary');return g?g.outerHTML.slice(0,300):null})(),
  trust:(document.querySelector('.dock-trust')||{}).textContent||null,
  marks:Object.keys(state.findingMarks||{}).length,
  dispositions:(state.findings||[]).map((f,i)=>{try{return (typeof findingDisposition==='function')?findingDisposition(f,i):null}catch(e){return 'err'}})
})""")
print("STRIP", json.dumps(dump, ensure_ascii=False))
# GAP-5: scoped pass line + the working-copy draft clause (same contract as d7/d10).
exp = (f"Pass: {(lp or {}).get('last_total')} \u2192 {(lp or {}).get('still_live')} still live "
       f"\u00b7 {(lp or {}).get('fixed')} no longer flagged \u00b7 {(lp or {}).get('new')} new")
check("browser strip == server payload (exact)", dump["strip"] == exp, f"{dump['strip']!r} vs {exp!r}")
check("scope chip says the pass numbers are not writer edits",
      "not your edits" in (dump["scope"] or ""), dump["scope"])
# GAP-5: no id vanished, so there is nothing to ghost — assert the honest
# absence (d6's seeded H1 covers the render path itself).
check("no ghosted summary — nothing vanished to ghost (GAP-5: ids survive)",
      not dump["ghosted"], dump["ghosted"])
check("deferred finding excluded from open counts (disposition)",
      any(d == "deferred" for d in (dump["dispositions"] or [])), dump["dispositions"])
pg.screenshot(path=os.path.join(SHOTS, "validation-24-drift-ghosted.png"))
b.close(); pw.stop()
try: st.proc.terminate()
except Exception: pass

print("\n=== VALIDATION-D3 SUMMARY ===")
for n, ok, d in RESULTS:
    print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D3_DONE")
