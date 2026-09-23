"""Cross-language parity for the finding id — `core.js:computeFindingId` vs
`revision.py:compute_finding_id`.

Why this suite exists (2026-09-21 production-readiness audit, finding F4):
a finding's content-hash id is the KEY for the writer's marks
(`finding_marks.json`), their dismissals (`dismissed_findings.json`), ghost
detection, and the doctor's case file. It is computed on BOTH sides — the server
observes, the client displays — so the two implementations must agree exactly.

They did not. The JS walked UTF-16 code units (`charCodeAt(i)` over `s.length`)
while Python walked code points (`for ch in s`), so a surrogate pair hashed as
TWO values on one side and ONE on the other. ASCII and BMP text (accents,
punctuation) always agreed, which is why this survived: only a finding whose
quote or issue contained a non-BMP character (an emoji, an astral-plane symbol)
got a different id on each side, and every one of those keys silently stopped
matching.

Measured before the fix, against the real page and the real Python:

    emoji in quote             js=f1jd41v6  py=f17jmr79   DIVERGE
    emoji in issue, no quote   js=f4wk75j   py=fyvgmwq    DIVERGE
    astral math char           js=fioal4w   py=f10wp4rv   DIVERGE
    ascii / accented / empty   (agreed)

This suite calls the SHIPPED JS in a real page and the SHIPPED Python on the
same objects — nothing is transcribed, so a mismatch is a product defect rather
than a typo in the test. It also drives the id through the live API, because
"the two functions agree" is only interesting if the round trip works.

Run:  python tests/e2e_browser_finding_id_parity.py
"""
import json
import os
import sys
import urllib.request

# This suite is the only one that imports the product package: it has to call
# the SHIPPED Python, not a copy of it. Running a script puts only its own
# directory on sys.path, so the repo root goes on explicitly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                studio_headers)
from playwright.sync_api import sync_playwright  # noqa: E402
from screenplay_studio.revision import compute_finding_id  # noqa: E402

# Every vector is a finding as the analyzer would write it. The table is
# deliberately wide: the hash itself, the two normalisation tiers (quote vs
# issue), the 100-char slice boundary, and the whitespace folding that the two
# languages express very differently (`/\s+/g` + trim vs `.split()` + join).
VECTORS = [
    ("ascii quote", {"category": "dialogue", "evidence_quote": "I am angry."}),
    ("empty finding", {}),
    ("category missing", {"evidence_quote": "A line."}),
    ("bmp accents", {"category": "voice", "evidence_quote": "café naïve résumé"}),
    ("emoji in quote", {"category": "dialogue",
                        "evidence_quote": "She smiled 😀 and left."}),
    ("emoji in issue, no quote", {"category": "theme",
                                  "issue": "the theme 😀 is thin"}),
    ("astral in issue, no quote", {"category": "voice",
                                   "issue": "astral probe 𝕏 in the quote"}),
    ("astral math char", {"category": "voice", "evidence_quote": "𝕏 marks it"}),
    ("zwj family emoji", {"category": "voice",
                          "evidence_quote": "the family 👨‍👩‍👧‍👦 arrives"}),
    ("flag (regional pair)", {"category": "voice", "evidence_quote": "a 🇮🇳 flag"}),
    ("non-bmp category", {"category": "🎬", "evidence_quote": "A line."}),
    ("whitespace runs in issue", {"category": "structure",
                                  "issue": "  too   many \t tabs\nand a newline  "}),
    ("nbsp in issue", {"category": "voice", "issue": "a\u00a0nbsp here"}),
    ("uppercase issue", {"category": "structure", "issue": "THE THEME IS THIN"}),
    ("issue 100 chars", {"category": "structure", "issue": "y" * 100}),
    ("issue 101 chars (slice boundary)", {"category": "structure",
                                          "issue": "z" * 101}),
    ("issue 140 chars", {"category": "structure", "issue": "x" * 140}),
    ("quote wins over issue", {"category": "dialogue", "issue": "ignored",
                               "evidence_quote": "the quote wins"}),
    ("whitespace-only quote falls back", {"category": "dialogue",
                                          "evidence_quote": "   ",
                                          "issue": "fallback used"}),
]

EMOJI_ISSUE = "emoji probe 😀 in the quote"
ASTRAL_ISSUE = "astral probe 𝕏 in the quote"


def finding(issue, scene=1, category="dialogue", severity="high",
            evidence_quote=""):
    return {
        "category": category,
        "severity": severity,
        "issue": issue,
        "description": issue,
        "evidence_quote": evidence_quote,
        "scene_refs": [scene],
        "scene": scene,
        "rule_id": None,
        "check_id": None,
    }


def post(base, path, body=None):
    req = urllib.request.Request(
        base + path, data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json", **studio_headers(base)},
        method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode() or "{}")


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def run(base, projects_dir, headers):
    checks = Checks()

    # ---- a real project with a real report ---------------------------------
    sample = post(base, "/api/sample")
    name = sample.get("project")
    checks.ok("sample project created", bool(name), f"got {name!r}")
    post(base, f"/api/projects/{name}/analyze")

    report_path = os.path.join(projects_dir, name, "report.findings.json")
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    baseline = len(report.get("findings") or [])
    checks.ok("demo analysis produced findings", baseline > 0, f"{baseline}")

    # Keep the exact objects we plant: the client-side recomputation below must
    # use the SAME finding, not a reconstruction. (Category is part of the hash
    # key, so a rebuilt dict that defaults the category produces a different id
    # and would look like a product defect.)
    planted = {
        "emoji": finding(EMOJI_ISSUE, scene=1),
        "astral": finding(ASTRAL_ISSUE, scene=2, category="voice"),
    }
    report["findings"] = ((report.get("findings") or [])
                          + list(planted.values())
                          + [finding("plain control finding", scene=3, severity="low")])
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.wait_for_function("() => typeof computeFindingId === 'function'")

        # ---- 1. the two implementations agree, live ------------------------
        diverged = []
        for label, vector in VECTORS:
            js = page.evaluate("(f) => computeFindingId(f)", vector)
            py = compute_finding_id(vector)
            if js != py:
                diverged.append(f"{label}: js={js} py={py}")
        checks.ok(f"all {len(VECTORS)} id vectors agree across JS and Python",
                  not diverged, "; ".join(diverged[:4]))

        # ---- 2. the API hands the client the SAME id it computes -----------
        # /fixqueue is where the server publishes its own `compute_finding_id`
        # for each finding, so this is the parity check on the real contract
        # rather than on two functions in isolation.
        queue = get(base, f"/api/projects/{name}/fixqueue")
        items = queue.get("items") or []
        by_issue = {i.get("issue"): i for i in items}

        for label, vector in planted.items():
            item = by_issue.get(vector["issue"])
            if item is None:
                checks.ok(f"{label} finding reached /fixqueue", False,
                          f"issues seen: {sorted(by_issue)[:4]}")
                continue
            server_id = item.get("finding_id")
            client_id = page.evaluate("(f) => computeFindingId(f)", vector)
            checks.ok(f"{label}: server and client publish the same id",
                      server_id == client_id,
                      f"server={server_id} client={client_id}")

        # ---- 3. the round trip: the client's key is the server's key ------
        # The client marks a finding by POSTing the id IT computed. The server
        # must then be able to read that mark back using the id IT computes —
        # which only holds if the two agree.
        emoji_finding = planted["emoji"]
        client_id = page.evaluate("(f) => computeFindingId(f)", emoji_finding)
        post(base, f"/api/projects/{name}/findings/intent",
             {"finding_id": client_id, "intent": "deferred"})

        marks_path = os.path.join(projects_dir, name, "finding_marks.json")
        with open(marks_path, encoding="utf-8") as f:
            marks = json.load(f)
        checks.ok("the mark the client wrote is keyed by the id the server computes",
                  marks.get(client_id) == "deferred", json.dumps(marks)[:160])
        checks.ok("no orphan key: the client id IS the server id",
                  compute_finding_id(emoji_finding) == client_id,
                  "the two implementations disagree — marks for this finding "
                  "would be written under one id and read under another")

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    from e2e_browser_common import start_studio
    with start_studio() as studio:
        run(studio.base_url, studio.projects_dir, {})
