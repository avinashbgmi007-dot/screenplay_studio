"""Audit boot probe — 2026-09-30. Boots the studio EXACTLY as shipped
(capability token, demo model, throwaway projects dir) using the repo's own
harness, verifies the boot contract, and writes evidence:

  docs/audit/evidence-2026-09-30/shots/boot_welcome_1440x900.png
  docs/audit/evidence-2026-09-30/boot_evidence.json

Run:  python docs/audit/evidence-2026-09-30/scripts/audit_boot_probe.py
"""
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, start_studio

EV_DIR = os.path.join(REPO_ROOT, "docs", "audit", "evidence-2026-09-30")
SHOTS = os.path.join(EV_DIR, "shots")
os.makedirs(SHOTS, exist_ok=True)

checks = Checks()
check = checks.ok
evidence = {}

PLACEHOLDER_STAMPS = {"hx1b397", "ht4"}  # the literal ?v= values shipped in index.html


def main():
    with start_studio() as studio:
        base = studio.base_url
        evidence["base"] = base
        print(f"[boot] studio at {base}")

        # -- 1. health -------------------------------------------------------
        try:
            h = studio.get_json("/api/health")
            check("boot: /api/health answers", isinstance(h, dict), json.dumps(h)[:200])
            evidence["health"] = h
        except Exception as e:
            check("boot: /api/health answers", False, repr(e))

        # -- 2. SPA serves ---------------------------------------------------
        r = requests.get(base + "/", timeout=15)
        check("boot: GET / serves 200", r.status_code == 200, f"status={r.status_code}")
        html = r.text
        check("boot: SPA is Script Doctor Studio", "Script Doctor Studio" in html, "title missing")

        # -- 3. capability token minted (secure by default) -------------------
        tok = studio.token or ""
        check("boot: capability token minted via Set-Cookie", bool(tok),
              f"token_len={len(tok)}")
        evidence["token_len"] = len(tok)
        # a write without the token must be refused
        r403 = requests.post(base + "/api/config", json={}, timeout=15)
        check("boot: write without token -> 403", r403.status_code == 403,
              f"status={r403.status_code}")

        # -- 4. cache-bust stamps rewritten to content hashes -----------------
        import re
        stamps = dict(re.findall(r'(style\.css|tungsten\.css|app\.js|core\.js)\?v=([a-z0-9]+)', html))
        evidence["stamps"] = stamps
        check("boot: all four assets carry ?v= stamps", len(stamps) >= 4, str(stamps))
        bad = {k: v for k, v in stamps.items() if v in PLACEHOLDER_STAMPS}
        check("boot: stamps are content hashes (not the on-disk placeholders)",
              not bad, f"placeholders leaked: {bad}")

        # -- 5. security headers on / and /api/health -------------------------
        # HTTP header names are case-insensitive; compare lowered.
        def lower_h(rs):
            return {k.lower(): v for k, v in rs.headers.items()}
        hdrs = lower_h(r)
        interesting = ("content-security-policy", "x-content-type-options",
                       "referrer-policy", "permissions-policy")
        root_h = {k: hdrs.get(k) for k in interesting if hdrs.get(k)}
        evidence["security_headers_root"] = root_h
        # The shipped contract: CSP frame-ancestors 'self' (NOT X-Frame-Options,
        # which is deliberately absent — test_spa_security_headers.py pins this).
        csp = root_h.get("content-security-policy", "")
        check("boot: nosniff on /", hdrs.get("x-content-type-options", "").lower() == "nosniff",
              str(sorted(hdrs)))
        check("boot: CSP frame-ancestors 'self' on /", "frame-ancestors 'self'" in csp,
              csp[:160])
        check("boot: referrer-policy on /", bool(root_h.get("referrer-policy")),
              str(sorted(hdrs)))
        rh = requests.get(base + "/api/health", timeout=15)
        api_hdrs = lower_h(rh)
        evidence["security_headers_api"] = {k: api_hdrs.get(k) for k in interesting if api_hdrs.get(k)}
        check("boot: /api/health answers without a token (GET exempt)",
              rh.status_code == 200, f"status={rh.status_code}")

        # -- 6. demo-model disclosure truthfulness ----------------------------
        try:
            rc = studio.get_json("/api/real-server-check")
            evidence["real_server_check"] = rc
            check("boot: real-server-check reports the demo model honestly",
                  isinstance(rc, dict) and (rc.get("is_real") in (False, None) or rc.get("demo") is True),
                  json.dumps(rc)[:200])
        except Exception as e:
            check("boot: real-server-check reachable", False, repr(e))

        # -- 7. browser boot: console must be clean, welcome view paints ------
        console_msgs, page_errors = [], []
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text[:200]}"))
            page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))
            page.goto(base, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(800)

            welcome_visible = page.locator("#welcome-view").is_visible()
            check("boot: welcome view paints", welcome_visible, "no #welcome-view")
            shot = os.path.join(SHOTS, "boot_welcome_1440x900.png")
            page.screenshot(path=shot, full_page=False)
            evidence["boot_screenshot"] = os.path.relpath(shot, REPO_ROOT)

            # the four self-hosted fonts must actually load (no external requests)
            ext = page.evaluate(
                "performance.getEntriesByType('resource')"
                ".filter(e => !e.name.startsWith(location.origin)).map(e => e.name)")
            check("boot: zero external requests on first paint", not ext, str(ext[:5]))
            evidence["external_requests"] = ext
            browser.close()

        errors = [m for m in console_msgs if m.startswith("error")]
        evidence["console_errors"] = errors
        evidence["page_errors"] = page_errors
        check("boot: zero console errors", not errors, "; ".join(errors[:3]))
        check("boot: zero page errors (uncaught exceptions)", not page_errors,
              "; ".join(page_errors[:3]))

    evidence["verdict"] = "BOOT PROVEN" if not checks.failed else f"BOOT FAILURES: {checks.failed}"
    with open(os.path.join(EV_DIR, "boot_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    print(f"[boot] evidence -> {os.path.relpath(os.path.join(EV_DIR, 'boot_evidence.json'), REPO_ROOT)}")
    (checks.finish)()  # exits (0) on success — must run AFTER the evidence write


if __name__ == "__main__":
    main()
