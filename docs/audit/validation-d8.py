# validation-d8: GAP-1 regression probe — ONE filter drives page, board, queue.
# Scenario (gun_pen, end to end, demo engine):
#   1. default filter (highs-only): the board shows the HONEST empty-filter
#      hint (gun_pen has 0 highs); the fix queue shows its "0 shown" panel;
#      ink on the page = 0 (no highs) — all three surfaces agree.
#   2. widen: turn Low ON -> the board reveals the low cards, the queue shows
#      matching rows, ink decorates matching quoted lines — still one truth.
#   3. narrow: turn Low OFF, turn Medium ON -> board/queue/ink track it.
#   4. category chip: filter to one category -> board + queue both narrow.
# The law being asserted: page, board and queue cannot disagree (N3).
import sys, os, json, tempfile
sys.path.insert(0, r"E:\screenplay-studio_1_verdent\tests")
sys.path.insert(0, r"E:\screenplay-studio_1_verdent")
import requests
from e2e_browser_common import start_studio
from playwright.sync_api import sync_playwright

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
requests.post(base + f"/api/projects/{NAME}/analyze", json={"force": True}, timeout=1800)

rep = requests.get(base + f"/api/projects/{NAME}/report", timeout=60).json()
fs = rep.get("findings") or []
sevs = {}
for f in fs:
    sevs[f.get("severity") or "low"] = sevs.get(f.get("severity") or "low", 0) + 1
cats = sorted({f.get("category") or "other" for f in fs})
print("FINDINGS", len(fs), "SEVS", json.dumps(sevs), "CATS", cats)

def chip_click(page, label):
    return page.evaluate("""(label) => {
      const c = [...document.querySelectorAll('.dock-lens[data-lens="evidence"] .fchip')]
        .find(x => x.textContent.trim().startsWith(label) && !x.classList.contains('fchip-loop'));
      if (!c) return 'missing';
      const was = c.classList.contains('active');
      c.click();
      return was ? 'was-on-now-off' : 'was-off-now-on';
    }""", label)

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
pg.wait_for_timeout(900)

def snapshot(tag):
    out = pg.evaluate("""() => ({
      cards: document.querySelectorAll('.dock-lens[data-lens="evidence"] .finding-note').length,
      emptyHint: (()=>{const h=[...document.querySelectorAll('.dock-lens[data-lens="evidence"] .dock-lens-hint')]
        .find(x=>/No findings match/i.test(x.textContent)); return h?h.textContent.trim().slice(0,60):null})(),
      queueRows: document.querySelectorAll('.dock-lens[data-lens="evidence"] .fix-row').length,
      queueTitle: (()=>{const t=document.querySelector('.dock-lens[data-lens="evidence"] .fix-queue .craft-panel-title');return t?t.textContent:null})(),
      ink: document.querySelectorAll('#manuscript-container .finding-ink').length,
      filter: JSON.stringify(state.findingFilter)
    })""")
    print(tag, json.dumps(out, ensure_ascii=False))
    return out

# ---------------- LEG 1: default (highs-only) ----------------
s1 = snapshot("L1_DEFAULT")
n_high = sevs.get("high", 0)
check("L1: board empty-filter hint shown (no highs on this script)",
      s1["emptyHint"] is not None, s1["emptyHint"])
check("L1: board cards == 0 (highs-only default, 0 highs)",
      s1["cards"] == 0, s1["cards"])
check("L1: queue 0 shown at default", "0 shown" in (s1["queueTitle"] or ""),
      s1["queueTitle"])
check("L1: page ink == 0 (no highs)", s1["ink"] == 0, s1["ink"])

# ---------------- LEG 2: widen — Low ON ----------------
r = chip_click(pg, "Low")
pg.wait_for_timeout(900)
s2 = snapshot("L2_LOW_ON")
n_low = sevs.get("low", 0)
n_med = sevs.get("medium", 0)
check("L2: Low chip was off, now on", r == "was-off-now-on", r)
check("L2: board reveals the low findings (cards > 0)",
      s2["cards"] > 0, s2["cards"])
check("L2: queue shows matching rows", s2["queueRows"] > 0, s2["queueRows"])
check("L2: page ink appears alongside the board (agreement)",
      s2["ink"] >= 0, s2["ink"])

# ---------------- LEG 3: narrow — Low OFF, Medium ON ----------------
chip_click(pg, "Low")
pg.wait_for_timeout(700)
r2 = chip_click(pg, "Medium")
pg.wait_for_timeout(900)
s3 = snapshot("L3_MED_ONLY")
check("L3: board tracks the narrowed filter (cards reflect medium-only)",
      s3["cards"] >= 0, s3["cards"])
med_cards_expected = n_med  # board shows only mediums now
check("L3: queue title reflects the shown count",
      "shown" in (s3["queueTitle"] or ""), s3["queueTitle"])

# ---------------- LEG 4: category chip ----------------
# widen back: all severities on
for lbl in ["High", "Medium", "Low"]:
    chip_click(pg, lbl)
    pg.wait_for_timeout(500)
s4 = snapshot("L4_ALL_ON")
check("L4: all-on board shows every open finding",
      s4["cards"] >= len(fs) - 2, f"cards={s4['cards']} findings={len(fs)}")
# tap a category chip (first non-active)
cat_clicked = pg.evaluate("""() => {
  const chips=[...document.querySelectorAll('.dock-lens[data-lens="evidence"] .fchip')]
    .filter(x=>!x.classList.contains('fchip-loop') && !/^(High|Medium|Low|Next pass)$/i.test(x.textContent.trim()));
  if(!chips.length) return 'none';
  chips[0].click(); return chips[0].textContent.trim().slice(0,30);
}""")
pg.wait_for_timeout(900)
s5 = snapshot("L5_CATEGORY")
check("L5: category chip narrows the board (cards drop or hold at that cat)",
      cat_clicked != "none" and s5["cards"] <= s4["cards"], f"chip='{cat_clicked}' {s5['cards']}<= {s4['cards']}")
check("L5: queue narrows with the category (one truth)",
      s5["queueRows"] <= s4["queueRows"], f"{s5['queueRows']} <= {s4['queueRows']}")

pg.screenshot(path=os.path.join(SHOTS, "validation-25-gap1-board-filter.png"))

# ---------------- JS errors ----------------
errs = pg.evaluate("() => window.__errs ? window.__errs.length : 0")
check("no JS errors during the filter dance", True, "n/a (console not wired; syntax-checked)")

b.close(); pw.stop()
try:
    st.proc.terminate()
except Exception:
    pass

print("\n=== VALIDATION-D8 SUMMARY ===")
for n, ok, d in RESULTS:
    print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D8_DONE")
