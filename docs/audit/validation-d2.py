# validation-d2: CORRECTED Phase D.
# Fixes the three probe bugs found by reading the code:
#   (1) report findings live at /report (evidence_quote + verification), NOT /edits
#   (2) the Sushruta lens adopts the FV consult chat -> .fv-msg, not .msg
#   (3) the FV composer is a <form>: a synthetic Enter does not submit it -> click submit
# Also adds a NO-EDIT CONTROL pass to test whether last_pass manufactures
# false Fixed/New under duplicate finding ids (list-length vs set-size).
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
vs1 = rep1.get("verification_summary") or {}
print("P1_COUNT", len(f1), "DISTINCT", len(set(ids1)), "VS", json.dumps(vs1))
for i, f in enumerate(f1):
    print("P1_ROW", i, ids1[i], f.get("category"), f.get("severity"),
          "q=" + ("Y" if f.get("evidence_quote") else "N"),
          "verif=" + str((f.get("verification") or {}).get("status")),
          "sc=" + str(f.get("scene_refs")), "|", (f.get("issue") or "")[:44])
check("P1 report has findings", len(f1) > 0, len(f1))
check("P1 verification_summary present", bool(vs1), vs1)
# GAP-3: compute_finding_id CAN collide (same category + same quote/issue) —
# gun_pen itself carries 9 rows / 7 distinct ids. Duplicates are ONE finding for
# arithmetic; the de-dup contract is asserted after the control pass below.
print("P1_ID_DUPES", len(ids1), "rows /", len(set(ids1)), "distinct")

# seed the last_pass snapshot (first GET -> honest null payload)
e1 = edits()
print("P1_LAST_PASS(first)", json.dumps(e1.get("last_pass")))

# ---------------- CONTROL: pass 2 with NO edits / NO intents ----------------
analyze()
rep2 = report()
ids2 = ids_of(rep2)
e2 = edits()
lp_ctrl = e2.get("last_pass")
print("CTRL_COUNT", len(ids2), "DISTINCT", len(set(ids2)))
print("CTRL_LAST_PASS", json.dumps(lp_ctrl))
# expected under correct (set-based) arithmetic with an unchanged report:
#   last_total=len(old), still_live=|set(old)&set(new)|, fixed=new=0
ctrl_still = len(set(ids1) & set(ids2))
ctrl_fixed_true = len(set(ids1) - set(ids2))
ctrl_new_true = len(set(ids2) - set(ids1))
check("CONTROL: no writer action -> report Fixed=0 (set-based truth)",
      (lp_ctrl or {}).get("fixed") == ctrl_fixed_true,
      f"server fixed={ (lp_ctrl or {}).get('fixed') } vs true={ctrl_fixed_true}")
check("CONTROL: no writer action -> report New=0 (set-based truth)",
      (lp_ctrl or {}).get("new") == ctrl_new_true,
      f"server new={ (lp_ctrl or {}).get('new') } vs true={ctrl_new_true}")
# GAP-3 de-dup contract: with duplicates present and ZERO writer action, a no-op
# re-analysis must report fixed=0/new=0 AND last_total as a DISTINCT count.
check("CONTROL: last_total counts DISTINCT ids (dup rows collapse to one finding)",
      (lp_ctrl or {}).get("last_total") == len(set(ids1)),
      f"last_total={(lp_ctrl or {}).get('last_total')} distinct={len(set(ids1))} rows={len(ids1)}")
check("CONTROL: duplicate rows cannot manufacture phantom progress",
      (lp_ctrl or {}).get("fixed") == 0 and (lp_ctrl or {}).get("new") == 0,
      f"fixed={(lp_ctrl or {}).get('fixed')} new={(lp_ctrl or {}).get('new')} for {len(ids1)} rows / {len(set(ids1))} distinct")
print("CTRL_ARITH server(still,fixed,new)=",
      (lp_ctrl or {}).get("still_live"), (lp_ctrl or {}).get("fixed"), (lp_ctrl or {}).get("new"),
      "| list-vs-set truth (still,fixed,new)=", ctrl_still, ctrl_fixed_true, ctrl_new_true,
      "| naive list math fixed/new=", len(ids1) - ctrl_still, len(ids2) - ctrl_still)

# ---------------- BROWSER: Sushruta "why" (corrected) ----------------
verified = next(((i, f) for i, f in enumerate(f1)
                 if (f.get("verification") or {}).get("status") == "verified" and f.get("evidence_quote")), None)
verified_old_id = ids1[verified[0]] if verified else None
print("D_VERIFIED", verified[0] if verified else None,
      (verified[1].get("evidence_quote") or "")[:60] if verified else None,
      "old_id=", verified_old_id)

pw = sync_playwright().start()
b = pw.chromium.launch()
pg = b.new_page(viewport={"width": 1480, "height": 940})
pg.goto(base, timeout=20000)
pg.wait_for_timeout(1500)
pg.locator("#dash-grid .dash-card").first.click()
pg.wait_for_function("()=>(state.findings||[]).length>0", timeout=20000)
pg.wait_for_timeout(800)

def dump(tag, js):
    print(tag, json.dumps(pg.evaluate(js), ensure_ascii=False))

# Discuss on the first finding -> pins pendingQuote (Sameer handoff)
pg.evaluate("() => openDock()")
pg.wait_for_timeout(400)
pg.evaluate("() => setDockLens('evidence')")
pg.wait_for_timeout(700)
pg.evaluate("""() => { const b=[...document.querySelectorAll('.dock-lens[data-lens="evidence"] .finding-note button')].filter(x=>x.offsetParent&&/discuss/i.test(x.textContent))[0]; if(b) b.click(); }""")
pg.wait_for_timeout(1200)
dump("E1_SAMEER", """() => ({
  pendingQuote: (typeof pendingQuote!=='undefined'&&pendingQuote)?{scene:pendingQuote.scene_number,text:(pendingQuote.text||'').slice(0,60)}:null,
  composer:(document.querySelector('#input')||{}).value||null,
  quoteCard: (()=>{const q=document.querySelector('#quote-card');return q?{hidden:q.hidden,text:q.textContent.trim().slice(0,60)}:null})()
})""")

# switch to Sushruta lens and send a REAL "why" (form submit)
pg.evaluate("() => setDockLens('sushruta')")
pg.wait_for_timeout(900)
sent = pg.evaluate("""() => {
  const inp=document.getElementById('fv-consult-input');
  if(!inp) return 'no-input';
  inp.focus(); inp.value='Why was the dialogue finding flagged? What exactly is wrong in scene 1?';
  inp.dispatchEvent(new Event('input',{bubbles:true}));
  const btn=document.querySelector('#fv-consult-composer button[type=submit]');
  if(btn){ btn.click(); return 'submit-btn'; }
  return 'no-btn';
}""")
print("E2_SENT", sent)
try:
    pg.wait_for_function("()=>document.querySelectorAll('.dock-lens[data-lens=\"sushruta\"] .fv-msg.ai').length>0", timeout=25000)
except Exception as ex:
    print("E2_WAIT_FAIL", str(ex)[:120])
pg.wait_for_timeout(1200)
dump("E2_SUSH", """() => ({
  fvmsg: document.querySelectorAll('.dock-lens[data-lens="sushruta"] .fv-msg').length,
  ai: document.querySelectorAll('.dock-lens[data-lens="sushruta"] .fv-msg.ai').length,
  lastAi: (()=>{const n=[...document.querySelectorAll('.dock-lens[data-lens="sushruta"] .fv-msg.ai')].pop();return n?n.textContent.trim().slice(0,300):null})(),
  userTurn: (()=>{const n=[...document.querySelectorAll('.dock-lens[data-lens="sushruta"] .fv-msg.user')].pop();return n?n.textContent.trim().slice(0,160):null})(),
  // did the pinned quote ride into the consult turn? (sendFvMessage passes null)
  msgsContainQuote: (()=>{ try{const md=currentBranchData()||{};const all=(md.messages||[]).map(m=>m.content||'').join(' ');return all.includes('Pace drag')||all.includes('tell you everything');}catch(e){return 'err:'+e.message} })(),
  branchMsgCount: (()=>{try{return (currentBranchData()||{}).messages.length}catch(e){return -1}})()
})""")
pg.screenshot(path=os.path.join(SHOTS, "validation-22-sushruta-why.png"))

# ---------------- IN-BETWEEN: intents + quote-visible edit ----------------
addressed, deferred = [], None
if len(ids1) >= 3:
    add_i, def_i = 1, 0
    if verified:
        def_i = verified[0]           # put the intent on the finding whose id will DRIFT
    for idx, intent in ((add_i, "addressed"), (min(add_i + 1, len(ids1) - 1), "addressed")):
        if idx != def_i:
            r = requests.post(base + f"/api/projects/{NAME}/findings/intent",
                              json={"finding_id": ids1[idx], "intent": intent}, timeout=30)
            print("INTENT", idx, ids1[idx], intent, r.status_code)
    r = requests.post(base + f"/api/projects/{NAME}/findings/intent",
                      json={"finding_id": ids1[def_i], "intent": "deferred"}, timeout=30)
    print("INTENT", def_i, ids1[def_i], "deferred", r.status_code)
    deferred = ids1[def_i]

if verified:
    idx, vf = verified
    quote = vf.get("evidence_quote")
    # CONTRACT: a verified finding carries EMPTY scene_refs -> use
    # verification.matched_scene (the d3-proven contract). With scene_refs the
    # POST 400s ("scene_number is required") and the drift checks below pass
    # VACUOUSLY (nothing was edited).
    scene = (vf.get("verification") or {}).get("matched_scene")
    if quote and scene is not None:
        # rewrite the quoted line WITHOUT the trigger phrase.
        # GAP-5 NOTE: this does NOT re-key the finding — analysis reads the
        # parse-of-record, so the id survives (asserted as STRUCTURAL below).
        # What DOES move is the working-copy truth: the apply response's
        # findings_status flips the finding to "addressed" (the signal the
        # arrival strip now carries in its draft clause).
        newline = "MARA: Then it stays between us. (rewritten by the writer.)"
        app = requests.post(base + f"/api/projects/{NAME}/edits/apply",
                            json={"scene_number": scene,
                                  "replacements": [{"old": quote, "new": newline}]}, timeout=60)
        print("E4_APPLY", app.status_code, (app.text or "")[:200])
        check("IN-BETWEEN: the quote-visible edit actually applied (not a silent 400)",
              app.status_code == 200, f"{app.status_code} {(app.text or '')[:120]}")
        _row = next((r for r in ((app.json() or {}).get("findings_status", {}).get("findings") or [])
                     if r.get("finding_id") == verified_old_id), None)
        print("GAP5_EDIT_STATUS", verified_old_id, _row)
        check("GAP-5: the writer's edit reads 'addressed' from the working copy "
              "(the truth the pass line structurally cannot carry)",
              bool(_row) and _row.get("status") == "addressed", _row)
    else:
        print("E4_SKIP", "no verified quote / no matched_scene", bool(quote), scene)

# seed snapshot for this generation, then pass 3
edits()
analyze()
rep3 = report()
ids3 = ids_of(rep3)
e3 = edits()
lp = e3.get("last_pass")
intents = e3.get("finding_intents") or {}
print("P3_COUNT", len(ids3), "DISTINCT", len(set(ids3)))
print("P3_LAST_PASS", json.dumps(lp))
print("P3_INTENTS", json.dumps(intents))
print("P3_VS", json.dumps(rep3.get("verification_summary") or {}))

# expected in-between truth (set-based)
old_set, new_set = set(ids2), set(ids3)
exp_still = len(old_set & new_set)
exp_fixed = len(old_set - new_set)
exp_new = len(new_set - old_set)
exp_ghosted = sorted(g for g in (old_set - new_set) if intents.get(g))
print("P3_EXPECT (set) still/fixed/new", exp_still, exp_fixed, exp_new,
      "ghosted", exp_ghosted)
check("IN-BETWEEN: writer intent persisted to disk (finding_intents non-empty)",
      bool(intents), intents)
check("IN-BETWEEN: deferred intent recorded",
      any(v == "deferred" for v in intents.values()), intents)
# GAP-5: analysis reads the parse-of-record (orchestrator.py loads m.parsed_path),
# so a quote-visible EDIT does NOT re-key the finding — the id SURVIVES. This is
# exactly why the strip's pass numbers cannot mean writer progress (and why the
# strip now says so + carries the working-copy draft clause instead). Assert the
# true structural fact; a same-pass re-analyze still has to be honest about it.
check("STRUCTURAL (GAP-5): the quoted finding's id SURVIVES a writer edit "
      "(analysis reads the parse, not the working copy)",
      bool(verified_old_id) and verified_old_id in new_set,
      f"old_id={verified_old_id} in_new={verified_old_id in new_set if verified_old_id else None}")
check("STRUCTURAL (GAP-5): the quoted finding's id SURVIVES a writer edit "
      "(analysis reads the parse, not the working copy)",
      bool(verified_old_id) and verified_old_id in new_set,
      f"old_id={verified_old_id} in_new={verified_old_id in new_set if verified_old_id else None}")
check("ARRIVAL: server still_live == set-truth",
      (lp or {}).get("still_live") == exp_still,
      f"server={(lp or {}).get('still_live')} truth={exp_still}")
check("ARRIVAL: server fixed == set-truth",
      (lp or {}).get("fixed") == exp_fixed,
      f"server={(lp or {}).get('fixed')} truth={exp_fixed}")
check("ARRIVAL: server new == set-truth",
      (lp or {}).get("new") == exp_new,
      f"server={(lp or {}).get('new')} truth={exp_new}")
check("ARRIVAL: ghosted marks come from REAL intents on vanished ids",
      sorted(g.get("finding_id") for g in ((lp or {}).get("ghosted_marks") or [])) == exp_ghosted,
      (lp or {}).get("ghosted_marks"))

# ---------------- BROWSER: arrival strip exactness ----------------
pg.reload()
pg.wait_for_timeout(2500)
dot = pg.evaluate("() => document.getElementById('dock-tab-evidence').classList.contains('has-unread')")
print("E5_DOT", dot)
pg.evaluate("() => openDock()")
pg.wait_for_timeout(600)
pg.evaluate("() => setDockLens('evidence')")
pg.wait_for_timeout(1000)
strip = pg.evaluate("""() => ({
  strip:(document.querySelector('.dock-arrival-line')||{}).textContent||null,
  scope:(document.querySelector('.dock-arrival-scope')||{}).textContent||null,
  draft:(document.querySelector('.dock-arrival-draft')||{}).textContent||null,
  ghosted:(document.querySelector('.dock-ghosted-summary')||{}).textContent||null,
  trust:(document.querySelector('.dock-trust')||{}).textContent||null,
  dot: document.getElementById('dock-tab-evidence').classList.contains('has-unread')
})""")
print("E5_STRIP", json.dumps(strip, ensure_ascii=False))
# GAP-5: the pass line is scoped ("from the last run, not your edits") and the
# draft clause carries the working-copy truth the strip previously lacked.
expected = (f"Pass: {(lp or {}).get('last_total')} \u2192 {(lp or {}).get('still_live')} still live "
            f"\u00b7 {(lp or {}).get('fixed')} no longer flagged \u00b7 {(lp or {}).get('new')} new")
check("ARRIVAL: browser strip string == server payload (exact)",
      strip["strip"] == expected, f"browser={strip['strip']!r} expected={expected!r}")
check("ARRIVAL: scope chip says the pass numbers are not writer edits",
      "not your edits" in (strip["scope"] or ""), strip["scope"])
check("ARRIVAL: unread dot present on fresh load after a new pass", dot is True, dot)
check("ARRIVAL: unread dot cleared once Evidence lens opened", strip["dot"] is False, strip["dot"])
# GAP-5: ghosted marks need a vanished id that carries an intent — unreachable
# while analysis reads the parse (ids survive). Assert the honest ABSENCE; the
# render path itself is covered by d6's seeded payload (H1).
check("ARRIVAL: no ghosted summary — nothing vanished to ghost (GAP-5: ids survive)",
      not strip["ghosted"], strip["ghosted"])
check("ARRIVAL: the draft clause carries the writer's working-copy progress",
      "addressed by you" in (strip["draft"] or ""), strip["draft"])
pg.screenshot(path=os.path.join(SHOTS, "validation-23-arrival-strip.png"))

b.close(); pw.stop()
try:
    st.proc.terminate()
except Exception:
    pass

print("\n=== VALIDATION-D2 SUMMARY ===")
for n, ok, d in RESULTS:
    print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D2_DONE")
