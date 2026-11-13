"""Small pure helpers split out of webapp_server.py.

Two jobs, both free of Flask and of this module's state:

* `_code_revision` / `_stale_code_warning` — the code-freshness pair. The desk
  boots once and loads modules once, so an analysis can silently run week-old
  code; these stamp the revision at boot and compare it later.
* `_strip_rewrite_noise` — trims the JSON artefacts the model leaks into
  rewritten lines.
"""
import os
import subprocess


def _code_revision(root=None):
    """The code this process analyzes with, as `"<short-hash>[+dirty]"`.

    A long-lived desk loads modules once at boot and never again, so an
    analysis can silently run week-old code (measured 2026-10-13: a re-run
    served pre-fix findings with no signal anywhere). Best-effort and
    never raising: no git, no checkout, or any error answers "unknown".
    """
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root,
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root,
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"
    if not head:
        return "unknown"
    return head + ("+dirty" if dirty else "")


def _stale_code_warning(boot_rev, now_rev):
    """None when the tree matches boot, else a plain-language warning.

    "unknown" on either side means "cannot tell" — warn too, because an
    unverifiable runner is no better than a stale one for this purpose.
    """
    if not boot_rev or not now_rev:
        return "Could not determine the server's code revision."
    if "unknown" in (boot_rev, now_rev):
        return ("Could not verify the server is running current code "
                "(revision unknown) — restart the desk before trusting "
                "this analysis to reflect the latest fixes.")
    if boot_rev != now_rev:
        return (f"Server code changed since boot (booted at {boot_rev}, tree "
                f"is now {now_rev}) — this analysis ran the booted code, "
                "not the current tree. Restart the desk and re-run.")
    return None


def _strip_rewrite_noise(line: str) -> str:
    """Remove JSON-emit artifacts the model leaks into copied lines. Two shapes:
    1. trailing punctuation/quote noise ('RAVI stops walking.",",' -> 'RAVI stops walking.')
    2. structural tokens emitted mid-string when the model breaks its own JSON
       ('RAVI stops walking.",", "new":' -> 'RAVI stops walking.')
    Cut at the first structural token sequence; strip trailing junk otherwise."""
    import re as _re
    # structural break: quote/comma/backslash run followed by a key like "new":
    m = _re.search(r'[",\\\s]*(new|old|note)"?\s*:\s*"?$', line)
    if m:
        line = line[:m.start()]
    # residual escape/punct tails at the very end
    return _re.sub(r'[",\'\\]+$', "", line.rstrip()).rstrip()
