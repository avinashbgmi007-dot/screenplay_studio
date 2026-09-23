"""Gate runner for the Playwright browser suites.

The ``tests/e2e_browser_*.py`` suites are standalone scripts, not pytest tests:
each one boots its own studio (or a static server), walks a real writer flow in
chromium, and prints a PASS/FAIL line per check. pytest never collected them
(they do not match ``test_*.py``) and nothing ran them automatically before
2026-09-20 — roughly 460 checks, entirely manual, while the shipped SPA
(``app.js``, ~9k lines) had no other behavioural coverage at all. This is that
missing gate.

Usage::

    python tests/run_browser_suites.py              # all runnable suites
    python tests/run_browser_suites.py phase6 smoke # by name substring
    python tests/run_browser_suites.py --strict     # include the known-broken
    E2E_BASE=http://127.0.0.1:8500 python tests/run_browser_suites.py

Exit code is nonzero if any suite fails or crashes.
"""
import argparse
import os
import re
import subprocess
import sys
import time

# Windows consoles default to cp1252: a suite name or reason carrying a non
# Latin-1 glyph would crash the PRINT, not the check (the same trap the suites'
# own harness documents). Make stdout/stderr UTF-8 once, here.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
HARNESS = "e2e_browser_common.py"
DEFAULT_TIMEOUT = 300

# Suites that drive a studio the operator is already running: they read E2E_BASE
# and never boot one, so a clean checkout dies with ERR_CONNECTION_REFUSED and
# prints "0 passed, 5 failed" — indistinguishable, at a glance, from a real
# regression. They are skipped LOUDLY unless E2E_BASE is set.
#
# `design_session` used to be listed here and did not belong: it was not gated on
# a live studio, it was IMPOSSIBLE to pass. Its console frames the SPA, and the
# SPA shipped `frame-ancestors 'none'`, so that cell was blank on every port and
# the suite could never have gone green. Pass 13 self-hosted the suite but pinned
# the block as a check, which documented the dead surface instead of fixing it;
# pass 14 relaxed the directive to 'self' (a foreign page still cannot frame the
# desk) and the suite now asserts the frame RENDERS. (passes 13-14)
#
# `gun_pen_audit` genuinely belongs: it runs a real analyze and needs a
# llama-server, which the gate does not have.
REQUIRES_LIVE_STUDIO = {
    "gun_pen_audit": "runs a real analyze — needs a llama-server, so E2E_BASE must point at a studio that has one",
}

# Known-red suites with their reason. Never silently skipped: every run prints
# them, because a skipped suite is dead coverage — and dead coverage is worse
# than none, since it looks like safety. Repair or delete them.
#
# EMPTY as of 2026-09-21: the last two entries (preview_next, preview_redesigns)
# were REPAIRED rather than tolerated. Both had been excluded as "crashes", which
# hid far more than a crash — preview_next died on its second of six worlds, so
# the other four were never exercised at all, and preview_redesigns was asserting
# a screen model (welcome/desk/cowrite/feedback, .edge-tab, .pane-pop) that no
# longer exists anywhere in the lab. Repairing them immediately surfaced four
# real defects: the desk composer bound to the wrong thread, the desk's findings
# verbs wired by only one of six worlds, the Workbench button sitting under the
# review bar in three worlds, and a gallery script dying on a null
# getElementById. Keep this dict empty; a new entry needs a reason AND an issue.
KNOWN_BROKEN = {}

_SUMMARY_RE = re.compile(r"^=== (\d+) passed, (\d+) failed ===", re.M)

# Every suite must boot the studio the product ships with: secure by default,
# capability token minted. `--no-token` (and the harness parameter that used to
# pass it) switches the control off, so a suite can go green while a write path
# that cannot carry the header is 403ing for real writers. The dictation upload
# and the pagehide idea flush were exactly that, and the whole fleet missed it.
# Checked on the source text because the flag also reaches argv at runtime.
_TOKEN_SWITCH_RE = re.compile(r"--no-token|\buse_token\b")


def _token_switch_off_suites():
    """Return [(suite, line-number, text)] for suites that disable the token."""
    offenders = []
    for filename in discover():
        path = os.path.join(TESTS_DIR, filename)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                if _TOKEN_SWITCH_RE.search(line):
                    offenders.append((_key(filename), lineno, line.strip()))
    return offenders


def _key(filename: str) -> str:
    return filename[len("e2e_browser_"):-len(".py")]


def discover():
    return [f for f in sorted(os.listdir(TESTS_DIR))
            if f.startswith("e2e_browser_") and f.endswith(".py") and f != HARNESS]


# Playwright's driver can die between suites — "Connection closed while reading
# from the driver" / "Connection.init" — before a single check has run. That is a
# harness fault, not a product one: measured, `phase14_signoff_journey` ERRORed in
# a gate run and then passed **47/47 when run alone**. A red gate for this reason
# costs an operator a real investigation, so it gets ONE retry.
#
# Narrow on purpose. Only a failure that matches these markers AND produced no
# check summary is retried, so a genuine failure is never retried away — and the
# retry is REPORTED in the detail, so a retried pass can never be mistaken for a
# first-time pass.
_DRIVER_INIT_MARKERS = (
    "Connection closed while reading from the driver",
    "Connection.init",
)


def _looks_like_driver_init_failure(out: str) -> bool:
    return any(marker in out for marker in _DRIVER_INIT_MARKERS)


def _attempt(path: str, timeout: int):
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, path], cwd=REPO_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"exceeded {timeout}s", time.time() - started, ""
    elapsed = time.time() - started
    out = (proc.stdout or "") + (proc.stderr or "")
    hits = _SUMMARY_RE.findall(out)
    if not hits:
        tail = "\n".join([line for line in out.strip().splitlines()[-6:] if line.strip()])
        return "ERROR", tail or f"no summary; exit {proc.returncode}", elapsed, out
    passed, failed = (int(x) for x in hits[-1])
    if failed or proc.returncode != 0:
        fails = [line for line in out.splitlines() if line.startswith("FAILED")]
        detail = f"{passed} passed, {failed} failed"
        if fails:
            detail += " | " + " ; ".join(fails[:3])
        return "FAIL", detail, elapsed, out
    return "PASS", f"{passed} passed", elapsed, out


def run_one(filename: str, timeout: int):
    """Returns (status, detail, seconds). status in PASS / FAIL / ERROR / TIMEOUT."""
    path = os.path.join(TESTS_DIR, filename)
    status, detail, elapsed, out = _attempt(path, timeout)
    if status == "ERROR" and _looks_like_driver_init_failure(out):
        status, detail, again, _ = _attempt(path, timeout)
        elapsed += again
        detail = (f"{detail} (after one Playwright driver-init retry)" if status == "PASS"
                  else f"{detail} (retried once after a driver-init failure)")
    return status, detail, elapsed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", nargs="*", help="suite name substrings (default: all)")
    ap.add_argument("--strict", action="store_true",
                    help="also run the known-broken suites (chase work)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"per-suite timeout in seconds (default {DEFAULT_TIMEOUT})")
    args = ap.parse_args()

    live = bool(os.environ.get("E2E_BASE"))
    suites = discover()
    if args.names:
        suites = [f for f in suites if any(n in f for n in args.names)]
    if not suites:
        print("no suites matched")
        return 1

    offenders = [o for o in _token_switch_off_suites()
                 if f"e2e_browser_{o[0]}.py" in suites]
    if offenders:
        print("GATE FAILED — a suite boots the studio with the capability token "
              "switched off, so its green says nothing about the shipped, "
              "secure-by-default product:")
        for key, lineno, text in offenders:
            print(f"  e2e_browser_{key}.py:{lineno}: {text}")
        print("Remove the switch and carry the token instead "
              "(studio_headers(base), or studio.write/post/delete).")
        return 1

    rows, failed = [], 0
    print("=== browser suite gate ===")
    if not live:
        print("(no E2E_BASE set — suites boot their own private studio)")
    for filename in suites:
        key = _key(filename)
        if key in REQUIRES_LIVE_STUDIO and not live:
            rows.append(("SKIP", key, REQUIRES_LIVE_STUDIO[key], 0.0))
            continue
        if key in KNOWN_BROKEN and not args.strict:
            rows.append(("BROKEN", key, KNOWN_BROKEN[key], 0.0))
            continue
        status, detail, secs = run_one(filename, args.timeout)
        rows.append((status, key, detail, secs))
        print(f"  {status:<7} {key:<28} {detail}  ({secs:.0f}s)", flush=True)
        if status in ("FAIL", "ERROR", "TIMEOUT"):
            failed += 1

    print("\n=== summary ===")
    for status, key, detail, _ in rows:
        print(f"{status:<7} {key:<28} {detail}")
    passed = sum(1 for r in rows if r[0] == "PASS")
    skipped = sum(1 for r in rows if r[0] == "SKIP")
    broken = sum(1 for r in rows if r[0] == "BROKEN")
    print(f"\n{len(rows)} suites: {passed} passed, {failed} failed, "
          f"{skipped} skipped, {broken} known-broken")
    if failed:
        print("GATE FAILED — a browser suite regressed.")
        return 1
    if broken and not args.strict:
        print("Note: known-broken suites above are NOT covered right now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
