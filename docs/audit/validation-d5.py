# validation-d5: re-verify GAP-1 (the ONE filter is PARTIAL).
# Claim: severity/category filter drives ink + loop + chips, but NOT the board
# list -> page and board disagree (N3 violation).
import sys, os, json, tempfile
sys.path.insert(0, r"E:\screenplay-studio_1_verdent\tests")
sys.path.insert(0, r"E:\screenplay-studio_1_verdent")
import requests
from e2e_browser_common import start_studio
from playwright.sync_api import sync_playwright

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
requests.post(base + "/api/projects/Gun_Pen/analyze", json={"force": True}, timeout=1800)

pw = sync_playwright().start(); b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
pg.goto(base, timeout=20000); pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000); pg.wait_for_timeout(800)
pg.evaluate("() => openDock()"); pg.wait_for_timeout(400)
pg.evaluate("() => setDockLens('evidence')"); pg.wait_for_timeout(1000)

MEASURE = """() => ({
  filter: JSON.parse(JSON.stringify(state.findingFilter)),
  boardCards: document.querySelectorAll('.dock-lens[data-lens="evidence"] .finding-note').length,
  boardSevs: [...document.querySelectorAll('.dock-lens[data-lens="evidence"] .finding-note')].map(n=>{
     const m=(n.className.match(/sev-(high|medium|low)|finding-note-(high|medium|low)/)||[])[0]; return m||n.className.slice(0,40)}),
  ink: document.querySelectorAll('.finding-ink').length,
  chips: [...document.querySelectorAll('.dock-filter-row button.fchip')].map(c=>c.textContent.trim()+(c.classList.contains('active')?'*':'')),
  fixRows: document.querySelectorAll('.dock-section-fixqueue .fix-row, .dock-section-fixqueue .craft-row').length
})"""
before = pg.evaluate(MEASURE)
print("BEFORE", json.dumps(before, ensure_ascii=False))

# default is ALREADY highs-only; turn Low ON so the filter change is observable
pg.evaluate("""() => {
  const btns=[...document.querySelectorAll('.dock-filter-row button.fchip')];
  const b=btns.find(x=>x.textContent.trim()==='Low' && !x.classList.contains('active'));
  if(b) b.click();
}""")
pg.wait_for_timeout(1200)
after = pg.evaluate(MEASURE)
print("AFTER ", json.dumps(after, ensure_ascii=False))

print("DELTA board", before["boardCards"], "->", after["boardCards"], "| ink", before["ink"], "->", after["ink"])
check("filter change is observable (Low toggled ON)", "low" in after["filter"]["severities"],
      after["filter"]["severities"])
check("filter DID change ink (ink follows the filter)", after["ink"] != before["ink"],
      f"{before['ink']} -> {after['ink']}")
check("filter DID change the board list (N3: page and board agree)",
      after["boardCards"] != before["boardCards"],
      f"board {before['boardCards']} -> {after['boardCards']}  <-- GAP-1 if unchanged")
check("no low/medium cards remain on the board under highs-only",
      all(("high" in s) for s in before["boardSevs"]) if before["boardCards"] else True,
      before["boardSevs"][:12])
pg.screenshot(path=os.path.join(SHOTS, "validation-26-filter-board.png"))
b.close(); pw.stop()
try: st.proc.terminate()
except Exception: pass
print("\n=== VALIDATION-D5 SUMMARY ===")
for n, ok, d in RESULTS: print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D5_DONE")
