"""Audit Phase 3 — cross-run the repo's own suites against the pulled HEAD.

Browser suites boot their own private studio (demo model, capability token);
pytest suites run against tmp dirs. Each suite's exit code + output tail is
recorded as evidence. This runner itself changes no product code.

Run:  python docs/audit/evidence-2026-09-30/scripts/audit_phase3_suites.py
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
EV_DIR = os.path.join(REPO_ROOT, "docs", "audit", "evidence-2026-09-30")
os.makedirs(EV_DIR, exist_ok=True)

# Browser suites (self-contained: boot their own studio on a free port)
BROWSER = ["e2e_browser_smoke.py", "e2e_browser_quickcheck.py",
           "e2e_browser_phase6_evidence.py", "e2e_browser_phase8_lifecycle.py"]
# pytest suites (API/behavior contracts, tmp dirs)
PYTEST = ["tests/test_fixqueue.py", "tests/test_production_readiness.py",
          "tests/test_webapp_api.py", "tests/test_negative.py"]

results = {"suites": [], "started": "phase3"}
for name in BROWSER:
    path = os.path.join(REPO_ROOT, "tests", name)
    p = subprocess.run([sys.executable, path], capture_output=True, text=True,
                       timeout=900, cwd=REPO_ROOT)
    tail = (p.stdout or "")[-1500:]
    passed = p.returncode == 0
    results["suites"].append({
        "suite": name, "kind": "browser", "exit": p.returncode, "ok": passed,
        "tail": tail,
    })
    print(f"[{'PASS' if passed else 'FAIL'}] {name} (exit {p.returncode})")
    if not passed:
        print(tail[-600:])

for spec in PYTEST:
    p = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", spec],
                       capture_output=True, text=True, timeout=900, cwd=REPO_ROOT)
    tail = (p.stdout or "")[-1500:]
    passed = p.returncode == 0
    results["suites"].append({
        "suite": spec, "kind": "pytest", "exit": p.returncode, "ok": passed,
        "tail": tail,
    })
    print(f"[{'PASS' if passed else 'FAIL'}] {spec} (exit {p.returncode})")
    if not passed:
        print(tail[-600:])

greens = sum(1 for s in results["suites"] if s["ok"])
results["verdict"] = f"{greens}/{len(results['suites'])} suites green on HEAD ddac2df"
with open(os.path.join(EV_DIR, "phase3_suites_evidence.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"[phase3] {results['verdict']}")
print("[phase3] evidence -> docs/audit/evidence-2026-09-30/phase3_suites_evidence.json")
