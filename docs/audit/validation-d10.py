# validation-d10: GAP-5 regression probe — the arrival strip stops implying
# writer-fix causality, and carries the working-copy truth instead.
#
# The structural claim (proved here against real behavior):
#   analysis reads m.parsed_path (the parse-of-record) while verification reads
#   working.json (the live draft) — so a writer's edit moves the DRAFT signal
#   but can never move the PASS numbers. The old copy ("Last pass … Fixed: N")
#   let the word "Fixed" borrow credit it cannot earn.
#
# Scenario (gun_pen, demo engine, end to end):
#   pass 1 -> seed snapshot -> the writer edits a cited line
#     (a) PASS truth: re-analysis still reads the original parse, so the pass
#         line reports 0 no-longer-flagged / 0 new even though the writer acted
#     (b) DRAFT truth: findings_status (working copy) flips that finding to
#         "addressed" — the signal the strip used to lack
#   BROWSER: the strip renders the scoped pass line + the reviewer chip + the
#            writer's own addressed clause; the word "Fixed" is gone from it.
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
f1 = rep1.get("findings") or []
ids1 = ids_of(rep1)
print("P1_COUNT", len(f1), "DISTINCT", len(set(ids1)))
check("P1 report has findings", len(f1) > 0, len(f1))
e1 = edits()   # seeds the snapshot: first GET -> honest null payload
print("P1_LAST_PASS(first)", json.dumps(e1.get("last_pass")))
check("P1 first pass has no arithmetic yet (honest null)", e1.get("last_pass") is None,
      e1.get("last_pass"))

# ---------------- the writer edits a cited line ----------------
verified = next(((i, f) for i, f in enumerate(f1)
                 if (f.get("verification") or {}).get("status") == "verified"
                 and f.get("evidence_quote")), None)
check("setup: a verified quote exists to edit (the drift candidate)", verified is not None,
      None if verified is None else verified[0])
assert verified is not None, "no verified quote — cannot exercise the writer-edit path"

v_idx, vf = verified
v_id = compute_finding_id(vf)
quote = vf.get("evidence_quote")
# the apply contract needs the SCENE the quote was verified against — that
# lives on verification.matched_scene (proven in d4), NOT on scene_refs
vscene = (vf.get("verification") or {}).get("matched_scene")
print("EDIT_TARGET", v_idx, v_id, "scene", vscene, "|", (quote or "")[:60])
check("setup: the verified finding carries a matched_scene for the apply call",
      vscene is not None, vscene)
assert vscene is not None, "verified finding has no matched_scene — cannot edit"

ap = requests.post(base + f"/api/projects/{NAME}/edits/apply",
                   json={"scene_number": vscene,
                         "replacements": [{"old": quote, "new": "MARA: It stays between us. (rewritten by the writer.)"}]},
                   timeout=60)
print("APPLY", ap.status_code, (ap.text or "")[:160])
check("setup: the writer's replacement actually applied (200)", ap.status_code == 200,
      ap.status_code)
fs = (ap.json() or {}).get("findings_status", {}) or {}
row = next((r for r in (fs.get("findings") or []) if r.get("finding_id") == v_id), None)
print("APPLY_STATUS", json.dumps(row))
check("DRAFT truth: the edit flips the finding to 'addressed' (working copy moved)",
      bool(row) and row.get("status") == "addressed", row)

# ---------------- PASS 2 (re-analysis, writer already acted) ----------------
analyze()
rep2 = report()
ids2 = ids_of(rep2)
e2 = edits()
lp = e2.get("last_pass") or {}
print("P2_LAST_PASS", json.dumps(lp))

# Structural claim: analysis read the ORIGINAL parse, so the edited finding's
# quote-keyed id survives the pass — the pass reports it as still live.
check("GAP-5 structural: re-analysis reads the parse, not the draft — the edited"
      " finding's id SURVIVES the pass (it stays 'still live')",
      v_id in set(ids2), f"v_id in new_ids={v_id in set(ids2)}")

old_set, new_set = set(ids1), set(ids2)
exp_still = len(old_set & new_set)
exp_fixed = len(old_set - new_set)
exp_new = len(new_set - old_set)
print("P2_EXPECT(set) still/fixed/new", exp_still, exp_fixed, exp_new)
check("GAP-5 structural: the pass numbers equal analyzer re-read drift only"
      " (server == set truth)",
      (lp.get("still_live"), lp.get("fixed"), lp.get("new")) == (exp_still, exp_fixed, exp_new),
      f"server={lp.get('still_live'), lp.get('fixed'), lp.get('new')} truth={exp_still, exp_fixed, exp_new}")
check("GAP-5 structural: a writer edit produced NO pass 'fixed' (the word can't"
      " mean writer progress)",
      lp.get("fixed") == 0, lp.get("fixed"))

# ---------------- BROWSER: the honest strip ----------------
pw = sync_playwright().start()
b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
errors = []
pg.on("pageerror", lambda e: errors.append(str(e)))
pg.goto(base, timeout=20000)
pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000)
pg.wait_for_timeout(800)
pg.evaluate("() => openDock()")
pg.wait_for_timeout(400)
pg.evaluate("() => setDockLens('evidence')")
pg.wait_for_timeout(1000)
dump = pg.evaluate("""() => ({
  strip: (document.querySelector('.dock-arrival-line')||{}).textContent||null,
  scope: (document.querySelector('.dock-arrival-scope')||{}).textContent||null,
  draft: (document.querySelector('.dock-arrival-draft')||{}).textContent||null,
  trust: (document.querySelector('.dock-trust')||{}).textContent||null,
  summary: (()=>{try{const s=findingStatusSummary();return s.addressed+'/'+(s.addressed+s.open)}catch(e){return 'err:'+e.message}})()
})""")
print("STRIP", json.dumps(dump, ensure_ascii=False))

expected = (f"Pass: {lp.get('last_total')} \u2192 {lp.get('still_live')} still live "
            f"\u00b7 {lp.get('fixed')} no longer flagged \u00b7 {lp.get('new')} new")
check("BROWSER: pass line byte-matches the (scoped) server payload",
      dump["strip"] == expected, f"browser={dump['strip']!r} expected={expected!r}")
check("BROWSER: the word 'Fixed' no longer appears in the pass line",
      "Fixed" not in (dump["strip"] or ""), dump["strip"])
check("BROWSER: scope chip says the numbers are from the last run, not the writer's edits",
      "not your edits" in (dump["scope"] or ""), dump["scope"])
check("BROWSER: the writer's own progress rides the strip (working-copy truth)",
      "addressed by you" in (dump["draft"] or ""), dump["draft"])
check("BROWSER: the draft clause agrees with the client's own status summary (N3)",
      bool(dump["draft"]) and dump["summary"].startswith(dump["draft"].split(" of ")[0]),
      f"clause={dump['draft']!r} summary={dump['summary']!r}")
check("BROWSER: the clause reports at least one addressed (the writer's edit counts)",
      bool(dump["draft"]) and not dump["draft"].startswith("0 of "), dump["draft"])
check("BROWSER: no JS errors on the strip path", not errors, errors[:2])
pg.screenshot(path=os.path.join(SHOTS, "validation-29-gap5-scoped-strip.png"))

b.close(); pw.stop()
try:
    st.proc.terminate()
except Exception:
    pass

print("\n===== SUMMARY =====")
passed = sum(1 for _, ok, _ in RESULTS if ok)
for name, ok, detail in RESULTS:
    if not ok:
        print("FAIL  " + name + "   [" + str(detail) + "]")
print(f"{passed}/{len(RESULTS)} checks passed")