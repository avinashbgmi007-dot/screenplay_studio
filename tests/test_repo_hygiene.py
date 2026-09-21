"""Repo-hygiene guard: local scratch must never be tracked (REL-M1).

`.gitignore` set out to ignore root-level scratch and then enumerated
extensions:

    # Scratch artifacts at repo root
    /_*.png
    /_*.log
    /_*.json
    /_*.txt

`/_*.py` and `/_*.xml` were never added, so five scratch files were tracked at
the repo root — `_gen_wf.py`, `_wf_gen.py`, `_r2_a11y_guard.py`,
`_r3_palette_probe.py` and `_p12_junit.xml`. Two of those turned out to be more
than clutter: `_r2_a11y_guard.py` was a WCAG guard nothing ran *and* could not
fail, and `_r3_palette_probe.py` was a browser probe nothing ran *and* crashed.

The fix is one extension-agnostic rule, `/_*`. These tests hold it in place:

  1. `test_no_scratch_files_are_tracked_at_repo_root` — the real invariant,
     asked of git's index rather than of a glob.
  2. `test_gitignore_rule_is_extension_agnostic` — no git needed. Asserts the
     rule covers every extension that has leaked, plus a bare extensionless
     name, so the *class* stays closed rather than today's five files.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITIGNORE = os.path.join(ROOT, ".gitignore")

# Every shape that has leaked or could plausibly leak. The list is deliberately
# representative, not exhaustive: the rule under test is extension-agnostic, so
# covering these is evidence it covers the class.
SCRATCH_NAMES = [
    "_probe.py", "_capture.py", "_junit.xml", "_report.json",
    "_out.txt", "_run.log", "_shot.png", "_no_extension",
]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _in_work_tree() -> bool:
    try:
        return _git("rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except OSError:
        return False


def _ignore_patterns() -> list[str]:
    with open(GITIGNORE, encoding="utf-8") as f:
        return [
            ln.strip() for ln in f
            if ln.strip() and not ln.strip().startswith("#")
        ]


def test_no_scratch_files_are_tracked_at_repo_root():
    """REL-M1: nothing matching root `_*` may be in the index.

    Asked of git rather than of a glob, so it catches a file that was
    force-added despite the ignore rule.
    """
    if not _in_work_tree():
        pytest.skip("no git work tree here — there is no index to inspect")

    tracked = _git("ls-files").stdout.splitlines()
    offenders = [
        p for p in tracked
        if p.startswith("_") and "/" not in p
    ]
    assert not offenders, (
        "scratch files are tracked at the repo root: "
        f"{offenders} — root `_*` is local scratch. If one of these is a real "
        "deliverable, it belongs in tests/ or a package, not at the root.")


def test_gitignore_rule_is_extension_agnostic():
    """The rule must cover the class, not a list that can fall behind.

    The original defect was an enumerated extension list missing two entries.
    A representative name of each shape must match some pattern.
    """
    patterns = _ignore_patterns()
    assert patterns, ".gitignore has no patterns at all"

    def ignored(name: str) -> bool:
        for pat in patterns:
            # gitignore: a leading `/` anchors to the repo root; `*` does not
            # cross `/`. At root level both reduce to a plain fnmatch.
            p = pat[1:] if pat.startswith("/") else pat
            if p.endswith("/"):
                continue  # directory-only rule; these names are files
            if fnmatch.fnmatch(name, p):
                return True
        return False

    uncovered = [n for n in SCRATCH_NAMES if not ignored(n)]
    assert not uncovered, (
        f".gitignore does not ignore {uncovered} at the repo root — the "
        f"scratch rule has gone back to enumerating shapes and will fall "
        f"behind again (this is exactly how REL-M1 happened)")


def test_the_hygiene_rule_is_not_vacuous():
    """Guard the guard: the matcher must reject a name that is NOT scratch.

    Without this, an `ignored()` that returned True for everything would
    satisfy the test above while ignoring the whole repository.
    """
    patterns = _ignore_patterns()

    def ignored(name: str) -> bool:
        for pat in patterns:
            p = pat[1:] if pat.startswith("/") else pat
            if p.endswith("/"):
                continue
            if fnmatch.fnmatch(name, p):
                return True
        return False

    for real in ("AGENTS.md", "pyproject.toml", "requirements.txt", "setup.py"):
        assert not ignored(real), (
            f"{real!r} matches a root ignore pattern — the scratch rule is too "
            f"broad and would silently untrack a real repo file")
