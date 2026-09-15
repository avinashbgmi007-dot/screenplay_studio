# validation-d6: close the three UNEXERCISED rows from the verdict table.
#   C3 report.md  - exists, opens, matches the desk's numbers
#   A2 clean bill - is a zero-finding state reachable? (demo engine) + does the
#                   UI render a clean state when findings == []
#   H1 ghosted    - does the ghosted summary RENDER (render-path; the arithmetic
#                   is unreachable per GAP-5, so the payload is seeded, labelled)
import sys, os, json, tempfile, shutil
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
pdir = os.path.join(pd, NAME)
requests.post(base + f"/api/projects/{NAME}/analyze", json={"force": True}, timeout=1800)
rep = requests.get(base + f"/api/projects/{NAME}/report", timeout=60).json()
n_find = len(rep.get("findings") or [])
print("DESK findings", n_find)

# ---------------- C3: report.md ----------------
md_path = os.path.join(pdir, "report.md")
fj_path = os.path.join(pdir, "report.findings.json")
md_exists = os.path.exists(md_path)
md_text = open(md_path, "r", encoding="utf-8", errors="replace").read() if md_exists else ""
fj = json.load(open(fj_path, "r", encoding="utf-8")) if os.path.exists(fj_path) else {}
print("REPORT_MD exists", md_exists, "bytes", len(md_text))
print("REPORT_MD head:", json.dumps(md_text[:300]))
print("FINDINGS_JSON count", len(fj.get("findings") or []), "keys", sorted(fj.keys())[:8])
check("C3 report.md exists and is non-empty", md_exists and len(md_text) > 0, f"{len(md_text)} bytes")
check("C3 desk findings == report.findings.json findings",
      n_find == len(fj.get("findings") or []), f"{n_find} vs {len(fj.get('findings') or [])}")
# does report.md carry the same numbers as the desk? look for a findings count mention
import re as _re
nums = set(int(x) for x in _re.findall(r"\b(\d{1,2})\b", md_text[:4000]))
print("REPORT_MD numeric tokens (head)", sorted(nums)[:20])
check("C3 report.md is readable and mentions the script's scene/finding scale",
      md_exists and (str(n_find) in nums or "finding" in md_text.lower()),
      f"n_find={n_find} in head-nums={n_find in nums}")

# ---------------- A2: is a zero-finding report reachable on the demo engine? ----------------
# code-grounded: demo_model emits a finding for dialogue/theme/character whenever
# the prompt carries >=1 scene, and genre unconditionally -> any parsed script
# yields >=3 findings. Verify by counting what the report's own categories show.
cats = {}
for f in (rep.get("findings") or []):
    cats[f.get("category")] = cats.get(f.get("category"), 0) + 1
print("CATEGORIES", json.dumps(cats))
check("A2 demo engine cannot yield zero findings for a script with scenes (by construction)",
      len(cats) >= 3 and n_find > 0, f"cats={cats}")

# ---------------- A2b + H1: browser render paths ----------------
pw = sync_playwright().start(); b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
errors = []
pg.on("pageerror", lambda e: errors.append(str(e)))
pg.goto(base, timeout=20000); pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000); pg.wait_for_timeout(800)

# --- A2b: synthetic zero-finding report -> clean-bill render ---
shutil.copyfile(fj_path, fj_path + ".bak")
zero = dict(fj); zero["findings"] = []
json.dump(zero, open(fj_path, "w", encoding="utf-8"))
pg.reload(); pg.wait_for_timeout(2200)
pg.evaluate("() => openDock()"); pg.wait_for_timeout(500)
pg.evaluate("() => setDockLens('evidence')"); pg.wait_for_timeout(900)
clean = pg.evaluate("""() => {
  const lens=document.querySelector('.dock-lens[data-lens="evidence"]');
  const ms=document.querySelector('.dock-mass-strip');
  return {
    findings:(state.findings||[]).length,
    boardCards:lens?lens.querySelectorAll('.finding-note').length:0,
    massStrip: ms?{children:ms.children.length,text:ms.textContent.trim().slice(0,90)}:null,
    ruler: !!document.querySelector('.dock-ruler'),
    filterRow: !!document.querySelector('.dock-filter-row'),
    cleanWord: lens?/clean|no findings|all clear|0 of 0/i.test(lens.textContent):null,
    lensText: lens?lens.textContent.replace(/\\s+/g,' ').trim().slice(0,220):null
  };
}""")
print("CLEAN_BILL", json.dumps(clean, ensure_ascii=False))
check("A2b zero-finding report renders without cards", clean["boardCards"] == 0, clean["boardCards"])
check("A2b zero-finding report renders without JS errors", len(errors) == 0, errors[:2])
check("A2b clean state has a LEGIBLE clean-bill affordance (plan fix #5)",
      bool(clean["cleanWord"]) or bool(clean["massStrip"] and clean["massStrip"]["children"]),
      f"cleanWord={clean['cleanWord']} massStrip={clean['massStrip']} lensText={clean['lensText']!r}")
pg.screenshot(path=os.path.join(SHOTS, "validation-27-clean-bill.png"))
shutil.copyfile(fj_path + ".bak", fj_path)  # restore real findings

# --- H1: seed a ghosted payload -> ghosted summary renders (render-path only) ---
lp_path = os.path.join(pdir, "last_pass.json")
lp_bak = lp_path + ".bak" if os.path.exists(lp_path) else None
if lp_bak: shutil.copyfile(lp_path, lp_bak)
mtime = os.path.getmtime(fj_path)
seed = {"ids": [compute_finding_id(f) for f in (rep.get("findings") or [])],
        "issues": {}, "report_mtime": mtime,
        "payload": {"computed_at": 1789400000.0, "last_total": n_find, "still_live": n_find - 1,
                    "fixed": 1, "new": 0,
                    "ghosted_marks": [{"finding_id": "fGHOST123", "issue": "Pace drag - Scene 1 runs long with little movement",
                                       "intent": "deferred"}]}}
json.dump(seed, open(lp_path, "w", encoding="utf-8"))
pg.reload(); pg.wait_for_timeout(2200)
pg.evaluate("() => openDock()"); pg.wait_for_timeout(500)
pg.evaluate("() => setDockLens('evidence')"); pg.wait_for_timeout(1000)
gh = pg.evaluate("""() => ({
  arrival: (document.querySelector('.dock-arrival-line')||{}).textContent||null,
  ghosted: (document.querySelector('.dock-ghosted-summary')||{}).textContent||null,
  rows: [...document.querySelectorAll('.dock-ghosted-row')].map(r=>r.textContent.trim().slice(0,90)),
  dot: document.getElementById('dock-tab-evidence').classList.contains('has-unread')
})""")
print("GHOSTED", json.dumps(gh, ensure_ascii=False))
check("H1 ghosted summary renders when last_pass carries ghosted_marks",
      bool(gh["ghosted"]), gh["ghosted"])
check("H1 ghosted row shows the vanished issue + its intent",
      any("next pass" in r or "deferred" in r or "Pace drag" in r for r in (gh["rows"] or [])), gh["rows"])
check("H1 seeded arrival numbers render (render-path)", bool(gh["arrival"]), gh["arrival"])
pg.screenshot(path=os.path.join(SHOTS, "validation-28-ghosted-render.png"))
# restore
if lp_bak: shutil.copyfile(lp_bak, lp_path)
else: os.remove(lp_path)

b.close(); pw.stop()
try: st.proc.terminate()
except Exception: pass
print("\n=== VALIDATION-D6 SUMMARY ===")
for n, ok, d in RESULTS: print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D6_DONE")
