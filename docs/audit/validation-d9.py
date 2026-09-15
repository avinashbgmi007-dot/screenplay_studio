# validation-d9: GAP-4 regression probe — the consult turn carries the finding.
# Scenario (gun_pen, demo engine, end to end):
#   1. open the Evidence board, widen the filter so cards render (T2: the
#      default highs-only view is honestly empty on this script)
#   2. click the escalation gesture on a deep card (the doctor button) —
#      it must pin the finding's quote, flip the dock to the Sushruta lens
#      and seed the "why" question
#   3. submit the consult composer
#   4. assert the turn rode the quote: stored on the user message (client
#      state AND server session JSON), the writer's own turn RENDERS in the
#      doctor's column (the audit's failed check), the quote chip shows,
#      and the doctor's reply lands tagged to the consultant persona.
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
pg.wait_for_timeout(900)

# widen the filter so cards render (T2 contract: default is highs-only)
pg.evaluate("""() => {
  const c = [...document.querySelectorAll('.dock-lens[data-lens="evidence"] .fchip')]
    .find(x => x.textContent.trim().startsWith('Low') && !x.classList.contains('fchip-loop'));
  if (c && !c.classList.contains('active')) c.click();
}""")
pg.wait_for_timeout(900)
cards = pg.locator('.dock-lens[data-lens="evidence"] .finding-note').count()
check("setup: board cards render after widening the filter", cards > 0, cards)

# ---------------- the escalation gesture ----------------
why = pg.evaluate("""() => {
  const btns = [...document.querySelectorAll('.dock-lens[data-lens="evidence"] .finding-note-actions .intent-btn')]
    .filter(b => (b.title || '').includes('Ask Dr. Sushruta'));
  if (!btns.length) return 'missing';
  btns[0].click();
  return 'clicked';
}""")
check("escalation: the doctor button exists on deep cards", why == "clicked", why)
pg.wait_for_timeout(900)

state_after = pg.evaluate("""() => ({
  lens: (typeof dockLens !== 'undefined') ? dockLens : null,
  pendingQuote: (typeof pendingQuote !== 'undefined' && pendingQuote)
    ? {scene: pendingQuote.scene_number, text: (pendingQuote.text||'').slice(0,60)} : null,
  composer: (document.getElementById('fv-consult-input')||{}).value || null,
  sushVisible: (()=>{const l=document.querySelector('.dock-lens[data-lens="sushruta"]');return !!(l&&l.offsetParent);})()
})""")
print("AFTER_CLICK", json.dumps(state_after, ensure_ascii=False))
check("escalation: dock flipped to the Sushruta lens", state_after["sushVisible"] is True, state_after["sushVisible"])
check("escalation: the finding's quote is pinned", state_after["pendingQuote"] is not None, state_after["pendingQuote"])
check("escalation: the why-question is seeded in the doctor's composer",
      bool(state_after["composer"]) and "flagged" in (state_after["composer"] or "").lower(),
      state_after["composer"])

# ---------------- send the consult turn ----------------
pg.evaluate("""() => {
  const btn = document.querySelector('.dock-lens[data-lens="sushruta"] #fv-consult-composer button[type=submit]')
           || document.querySelector('#fv-consult-composer button[type=submit]');
  if (btn) btn.click();
}""")
try:
    pg.wait_for_function(
        "()=>document.querySelectorAll('.dock-lens[data-lens=\"sushruta\"] .fv-msg.ai').length>0",
        timeout=30000)
except Exception as ex:
    print("WAIT_FAIL", str(ex)[:120])
pg.wait_for_timeout(1200)

turn = pg.evaluate("""() => {
  const msgs = (currentBranchData()||{}).messages || [];
  const lastUser = [...msgs].reverse().find(m => m.role === 'user');
  const lastAi = [...msgs].reverse().find(m => m.role === 'assistant');
  const lens = document.querySelector('.dock-lens[data-lens="sushruta"]');
  return {
    userPartner: lastUser ? lastUser.partner : null,
    userQuote: lastUser && lastUser.quote ? lastUser.quote.text.slice(0,60) : null,
    userQuoteScene: lastUser && lastUser.quote ? lastUser.quote.scene_number : null,
    aiPartner: lastAi ? lastAi.partner : null,
    aiText: lastAi ? (lastAi.content||'').slice(0,120) : null,
    renderedUser: lens ? lens.querySelectorAll('.fv-msg.user').length : -1,
    renderedAi: lens ? lens.querySelectorAll('.fv-msg.ai').length : -1,
    quoteChip: lens ? lens.querySelectorAll('.fv-msg-quote').length : -1,
    session: (typeof state !== 'undefined') ? state.currentSession : null
  };
}""")
print("TURN", json.dumps(turn, ensure_ascii=False))
check("consult turn: the quote rode into the turn (stored on the user message)",
      bool(turn["userQuote"]), turn["userQuote"])
check("consult turn: the turn is tagged to the consultant persona",
      turn["userPartner"] == "script_consultant" and turn["aiPartner"] == "script_consultant",
      f"user={turn['userPartner']} ai={turn['aiPartner']}")
check("consult column: the writer's own turn RENDERS (the audit's failed check)",
      turn["renderedUser"] >= 1, turn["renderedUser"])
check("consult column: the doctor's reply renders", turn["renderedAi"] >= 1, turn["renderedAi"])
check("consult column: the quote chip shows what the question was about",
      turn["quoteChip"] >= 1, turn["quoteChip"])

# ---------------- server truth ----------------
if turn["session"]:
    sess = requests.get(base + f"/api/projects/{NAME}/chat/sessions/{turn['session']}", timeout=30).json()
    branches = sess.get("branches") or {}
    cur = sess.get("current_branch") or "main"
    msgs = (branches.get(cur) or {}).get("messages") or []
    stored_user = [m for m in msgs if m.get("role") == "user"][-1] if msgs else {}
    stored_ai = [m for m in msgs if m.get("role") == "assistant"][-1] if msgs else {}
    print("STORED_USER", json.dumps({k: stored_user.get(k) for k in ("role","partner","quote")}, ensure_ascii=False)[:220])
    check("server truth: stored user message carries quote + partner",
          bool(stored_user.get("quote")) and stored_user.get("partner") == "script_consultant",
          f"quote={bool(stored_user.get('quote'))} partner={stored_user.get('partner')}")
    check("server truth: stored reply is tagged to the consultant",
          stored_ai.get("partner") == "script_consultant", stored_ai.get("partner"))

check("no JS errors during the escalation", len(errors) == 0, "; ".join(errors[:2]))
pg.screenshot(path=os.path.join(SHOTS, "validation-26-gap4-consult-context.png"))

b.close(); pw.stop()
try:
    st.proc.terminate()
except Exception:
    pass

print("\n=== VALIDATION-D9 SUMMARY ===")
for n, ok, d in RESULTS:
    print(("PASS  " if ok else "FAIL  ") + n + ("" if ok else "   [" + str(d) + "]"))
print(f"=== {sum(1 for _,o,_ in RESULTS if o)} passed, {sum(1 for _,o,_ in RESULTS if not o)} failed ===")
print("VALIDATION_D9_DONE")
