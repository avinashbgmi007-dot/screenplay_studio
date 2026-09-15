# validation-d4: close the last rows with CORRECT call contracts.
#   (1) findingDisposition(f, INDEX) -- d3 called it with one arg (probe artifact)
#   (2) writer-fix signal: a quote-visible edit -> findings_status observed "addressed"
#   (3) intent marks excluded from the open count (N3 one-counting contract)
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
def check(n, c, d=""):
    RESULTS.append((n, bool(c), d)); print(("PASS  " if c else "FAIL  ") + n + ("" if c else "   [" + str(d) + "]"))

tmp = tempfile.TemporaryDirectory(); pd = os.path.join(tmp.name, "projects"); os.makedirs(pd)
st = start_studio(projects_dir=pd); base = st.base_url
with open(PDF, "rb") as f:
    requests.post(base + "/api/projects", files={"file": ("gun_pen.pdf", f, "application/pdf")},
                  data={"title": "Gun Pen"}, timeout=300)
NAME = "Gun_Pen"
def api(p): return requests.get(base + f"/api/projects/{NAME}" + p, timeout=60)
requests.post(base + f"/api/projects/{NAME}/analyze", json={"force": True}, timeout=1800)
r1 = api("/report").json(); f1 = r1.get("findings") or []
ids1 = [compute_finding_id(f) for f in f1]
v = next(((i, f) for i, f in enumerate(f1)
          if (f.get("verification") or {}).get("status") == "verified" and f.get("evidence_quote")), None)
vid = ids1[v[0]] if v else None
vscene = (v[1].get("verification") or {}).get("matched_scene") if v else None
quote = v[1].get("evidence_quote") if v else None
print("VERIFIED idx", v[0], "id", vid, "matched_scene", vscene)

# mark 2 addressed + 1 deferred (one on the quoted finding)
requests.post(base + f"/api/projects/{NAME}/findings/intent", json={"finding_id": ids1[1], "intent": "addressed"}, timeout=30)
requests.post(base + f"/api/projects/{NAME}/findings/intent", json={"finding_id": ids1[2], "intent": "addressed"}, timeout=30)
requests.post(base + f"/api/projects/{NAME}/findings/intent", json={"finding_id": vid, "intent": "deferred"}, timeout=30)

pw = sync_playwright().start(); b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
pg.goto(base, timeout=20000); pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000); pg.wait_for_timeout(800)

# (1) dispositions WITH the index (correct contract)
d1 = pg.evaluate("""() => ({
  marks: Object.keys(state.findingMarks||{}).length,
  disp: (state.findings||[]).map((f,i)=>{try{return findingDisposition(f,i)}catch(e){return 'err:'+e.message}}),
  openCount: (state.findings||[]).filter((f,i)=>{try{return findingOpen(f,i)}catch(e){return true}}).length,
  total: (state.findings||[]).length
})""")
print("DISP_BEFORE", json.dumps(d1))
check("intent marks exclude findings from the OPEN count (N3)",
      d1["openCount"] < d1["total"] and ("deferred" in d1["disp"] or "addressed" in d1["disp"]), d1)
check("deferred disposition surfaces for the marked finding",
      "deferred" in (d1["disp"] or []), d1["disp"])

# (2) writer-fix signal: edit the quoted line -> observed 'addressed'
if v:
    ap = requests.post(base + f"/api/projects/{NAME}/edits/apply",
                       json={"scene_number": vscene,
                             "replacements": [{"old": quote, "new": "MARA: It stays between us. (rewritten.)"}]},
                       timeout=60)
    fs = (ap.json() or {}).get("findings_status", {}).get("findings", [])
    row = next((r for r in fs if r.get("finding_id") == vid), None)
    print("APPLY_STATUS", json.dumps(row))
    check("writer-fix signal: quote-visible edit -> observed 'addressed'",
          bool(row) and row.get("status") == "addressed", row)
pg.reload(); pg.wait_for_timeout(2500)
d2 = pg.evaluate("""() => ({
  disp: (state.findings||[]).map((f,i)=>{try{return findingDisposition(f,i)}catch(e){return 'err'}}),
  openCount: (state.findings||[]).filter((f,i)=>{try{return findingOpen(f,i)}catch(e){return true}}).length
})""")
print("DISP_AFTER", json.dumps(d2))
check("observed 'addressed' surfaces after reload",
      "addressed" in (d2["disp"] or []), d2["disp"])
pg.screenshot(path=os.path.join(SHOTS, "validation-25-dispositions.png"))
b.close(); pw.stop()
try: st.proc.terminate()
except Exception: pass
print("\n=== VALIDATION-D4 SUMMARY ===")
for n, ok, d in RESULTS: print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D4_DONE")
