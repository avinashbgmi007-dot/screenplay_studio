# validation-d7: GAP-3 regression probe — the arrival strip must not lie.
# Scenario (gun_pen pathology, end to end):
#   pass 1: upload gun_pen.pdf -> analyze -> seed last_pass snapshot
#   pass 2: re-analyze with NO writer action (no edits, no intents)
#           -> /edits last_pass must report fixed=0, new=0 (distinct-identity truth)
#   browser: the arrival strip's PASS LINE must byte-match
#           "Pass: N -> N still live . 0 no longer flagged . 0 new" and the
#           ghosted summary must be ABSENT (no writer marks exist to ghost).
#   (GAP-5 later rescoped this copy: the pass numbers compare analysis passes,
#   never writer edits — word "Fixed" retired, scope chip added, and the
#   writer's own progress rides the draft clause.)
# Before the fix: 9 findings / 7 distinct ids -> "Fixed: 2 . New: 2" manufactured
# out of duplicate rows. After: honest zeros.
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
    print(("PASS  " if cond else "FAIL  ") + name + ("" if not cond else "   [" + str(detail) + "]"))

tmp = tempfile.TemporaryDirectory()
pd = os.path.join(tmp.name, "projects")
os.makedirs(pd)
st = start_studio(projects_dir=pd)
base = st.base_url

with open(PDF, "rb") as f:
    requests.post(base + "/api/projects", files={"file": ("gun_pen.pdf", f, "application/pdf")},
                  data={"title": "Gun Pen"}, timeout=300)
projects = requests.get(base + "/api/projects", timeout=30).json()
plist = projects if isinstance(projects, list) else (projects.get("projects") or [])
NAME = (plist[0].get("project") if plist and isinstance(plist[0], dict) else "Gun_Pen")
print("PROJECT", NAME)

def api(path):
    return requests.get(base + f"/api/projects/{NAME}" + path, timeout=60)

def analyze():
    return requests.post(base + f"/api/projects/{NAME}/analyze", json={"force": True}, timeout=1800)

def report():
    return api("/report").json()

def edits():
    return api("/edits").json()

def ids_of(rep):
    return [compute_finding_id(f) for f in (rep.get("findings") or [])]

# ---------------- PASS 1 ----------------
analyze()
rep1 = report()
ids1 = ids_of(rep1)
print("P1_COUNT", len(ids1), "DISTINCT", len(set(ids1)))

# seed the snapshot (first GET -> honest null payload)
e1 = edits()
print("P1_LAST_PASS(first)", json.dumps(e1.get("last_pass")))

# ---------------- PASS 2: NO WRITER ACTION ----------------
analyze()
rep2 = report()
ids2 = ids_of(rep2)
e2 = edits()
lp = e2.get("last_pass")
print("P2_COUNT", len(ids2), "DISTINCT", len(set(ids2)))
print("P2_LAST_PASS", json.dumps(lp))

distinct = len(set(ids2))
check("P2: last_pass payload present (second pass arithmetic)", lp is not None, lp)
if lp:
    check("P2: last_total == distinct id count (not raw rows)",
          lp.get("last_total") == distinct,
          f"last_total={lp.get('last_total')} distinct={distinct} rows={len(ids2)}")
    check("P2: still_live == distinct (unchanged report)",
          lp.get("still_live") == distinct,
          f"still_live={lp.get('still_live')} distinct={distinct}")
    check("GAP-3 REGRESSION: no writer action -> fixed == 0",
          lp.get("fixed") == 0, f"fixed={lp.get('fixed')}")
    check("GAP-3 REGRESSION: no writer action -> new == 0",
          lp.get("new") == 0, f"new={lp.get('new')}")
    check("GAP-3: no intents set -> ghosted_marks empty",
          not (lp.get("ghosted_marks") or []),
          lp.get("ghosted_marks"))

# ---------------- BROWSER: arrival strip exactness ----------------
pw = sync_playwright().start()
b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
pg.goto(base, timeout=20000)
pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000)
pg.wait_for_timeout(800)
pg.evaluate("() => openDock()")
pg.wait_for_timeout(400)
pg.evaluate("() => setDockLens('evidence')")
pg.wait_for_timeout(1000)
strip = pg.evaluate("""() => ({
  strip:(document.querySelector('.dock-arrival-line')||{}).textContent||null,
  scope:(document.querySelector('.dock-arrival-scope')||{}).textContent||null,
  draft:(document.querySelector('.dock-arrival-draft')||{}).textContent||null,
  ghosted:(document.querySelector('.dock-ghosted-summary')||{}).textContent||null
})""")
print("STRIP", json.dumps(strip, ensure_ascii=False))
if lp:
    expected = (f"Pass: {lp.get('last_total')} \u2192 {lp.get('still_live')} still live "
                f"\u00b7 {lp.get('fixed')} no longer flagged \u00b7 {lp.get('new')} new")
    check("BROWSER: arrival strip string == server payload (exact)",
          strip["strip"] == expected,
          f"browser={strip['strip']!r} expected={expected!r}")
    check("BROWSER: strip shows honest zeros (0 no longer flagged . 0 new)",
          "0 no longer flagged" in (strip["strip"] or "") and "0 new" in (strip["strip"] or ""),
          strip["strip"])
    # GAP-5: the pass numbers are scoped on-screen, and the writer's own
    # working-copy progress rides beside them (the signal the strip lacked).
    check("BROWSER: GAP-5 scope chip says the numbers are not writer edits",
          "not your edits" in (strip["scope"] or ""), strip["scope"])
    check("BROWSER: GAP-5 draft clause carries the working-copy progress",
          "addressed by you" in (strip["draft"] or ""), strip["draft"])
check("BROWSER: no ghosted summary (no writer marks exist)",
      not strip["ghosted"], strip["ghosted"])
pg.screenshot(path=os.path.join(SHOTS, "validation-24-gap3-arrival-zero.png"))

b.close(); pw.stop()
try:
    st.proc.terminate()
except Exception:
    pass

print("\n=== VALIDATION-D7 SUMMARY ===")
for n, ok, d in RESULTS:
    print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D7_DONE")
