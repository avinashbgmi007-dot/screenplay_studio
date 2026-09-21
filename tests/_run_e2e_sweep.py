import os
import subprocess
import sys
import glob
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "tests", "_e2e_sweep_results.txt")
# LAB-ONLY suites: they boot their own static server against the design gallery
# (webapp/preview-next/, preview-r4/) or require a hand-started studio on :8500.
# They are not shipped-app surface, so a non-zero exit there is not a product
# failure — reported separately rather than counted as a gate failure.
LAB_ONLY = {
    # lab console; self-hosts since pass 13 (it used to need a studio on :8500,
    # but it frames the SPA and the SPA sends frame-ancestors 'none', so no port
    # could ever have made it pass)
    "e2e_browser_design_session.py",
    "e2e_browser_preview_next.py",         # design gallery (preview-next/)
    "e2e_browser_preview_redesigns.py",    # design gallery (preview-*)
}
suites = sorted(glob.glob(os.path.join(REPO, "tests", "e2e_browser_*.py")))
suites = [s for s in suites if not s.endswith("_common.py")]
lines = []
total_pass = total_fail = 0
for s in suites:
    name = os.path.basename(s)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, s], cwd=REPO, capture_output=True, text=True, timeout=900)
        out = (p.stdout or "")
        tail = "\n".join(out.strip().splitlines()[-2:])
        err = (p.stderr or "").strip().splitlines()
        status = "OK " if p.returncode == 0 else "FAIL"
        if p.returncode != 0 and name in LAB_ONLY:
            status = "LAB"
        # parse "N passed, M failed"
        import re as _re
        m = _re.search(r"(\d+) passed, (\d+) failed", out)
        if m:
            total_pass += int(m.group(1)); total_fail += int(m.group(2))
        lines.append(f"{status} {name} ({time.time()-t0:.0f}s, rc={p.returncode})\n   {tail}")
        if p.returncode != 0 and err:
            lines.append("   STDERR: " + "\n   ".join(err[-5:]))
    except subprocess.TimeoutExpired:
        lines.append(f"TIMEOUT {name}")
    except Exception as e:
        lines.append(f"ERROR {name}: {e}")
summary = f"\n==== TOTAL: {total_pass} checks passed, {total_fail} failed across {len(suites)} suites ====\n"
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + summary)
print("\n".join(lines))
print(summary)
print("WROTE", OUT)
