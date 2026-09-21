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


# --- the same class of bug, one level up: a harness must not write over evidence ---
#
# Top-level `impl-shots/` is EVIDENCE — the verdict tables in docs/ cite those
# exact filenames. `e2e_browser_gun_pen_audit.py` wrote its shots straight into
# it, so re-running the audit silently replaced a table's screenshots with
# post-fix images. FULL_FEEDBACK_AUDIT_VERDICTS.md filed that as "a small honesty
# bug of the same family this document exists to catch"; these tests hold the
# fix, which is the same shape as REL-M1: the default must be ignored scratch,
# and touching the versioned set must be a deliberate act.

AUDIT_MODULE = "e2e_browser_gun_pen_audit"


def _audit_shots(monkeypatch, *, promote: bool) -> str:
    """The audit's resolved SHOTS path, with AUDIT_PROMOTE forced either way.

    Reloaded because SHOTS is computed once at import — the point is to test the
    value the harness actually resolves, not a re-derivation of its formula.
    """
    import importlib

    if promote:
        monkeypatch.setenv("AUDIT_PROMOTE", "1")
    else:
        monkeypatch.delenv("AUDIT_PROMOTE", raising=False)
    module = importlib.import_module(AUDIT_MODULE)
    return importlib.reload(module).SHOTS


def _is_ignored(path: str) -> bool:
    """Ask git's RULES whether this path would be ignored.

    `--no-index` is load-bearing, not decoration. Plain `git check-ignore` treats
    a TRACKED file as not-ignored (the index wins), so a guard built on it can
    only notice an untracking that has ALREADY happened — it is blind to the
    .gitignore rule that causes it. `--no-index` asks the question actually
    meant: "would this path be ignored?".
    """
    proc = _git("check-ignore", "--no-index", "-q", path)
    return proc.returncode == 0


def test_the_audit_writes_to_ignored_scratch_by_default(monkeypatch):
    """A run must not write into the versioned evidence set.

    The invariant is not "SHOTS ends with runs/" (a path shape that could be
    renamed); it is that whatever the default is, git ignores it.
    """
    if not _in_work_tree():
        pytest.skip("no git work tree here — there is no index to inspect")

    shots = _audit_shots(monkeypatch, promote=False)
    rel = os.path.relpath(shots, ROOT).replace(os.sep, "/")
    assert rel != "impl-shots", (
        "the audit writes into the versioned evidence set by default — a run "
        "would silently replace the screenshots the verdict tables cite")
    assert _is_ignored(rel + "/probe.png"), (
        f"the audit's default output {rel}/ is NOT gitignored, so every run "
        f"dirties the tree with regenerated binaries")


def test_promote_is_the_only_way_into_the_versioned_set(monkeypatch):
    """The deliberate path must still reach the versioned set.

    Without this, `SHOTS` could be hard-coded to scratch and promotion would be
    silently impossible — the evidence set could never be refreshed.
    """
    shots = _audit_shots(monkeypatch, promote=True)
    rel = os.path.relpath(shots, ROOT).replace(os.sep, "/")
    assert rel == "impl-shots", f"AUDIT_PROMOTE=1 resolved to {rel!r}, not impl-shots/"


def test_the_versioned_evidence_set_is_still_tracked():
    """Guard the guard: the fix must not untrack the evidence itself.

    The tempting wrong fix is to add `impl-shots/` to .gitignore. That would
    stop the churn and silently drop the evidence the docs cite from the repo —
    a worse bug than the one being fixed.
    """
    if not _in_work_tree():
        pytest.skip("no git work tree here — there is no index to inspect")

    assert not _is_ignored("impl-shots/A-dialogue.png"), (
        "impl-shots/ is now ignored — the evidence the verdict tables cite has "
        "been silently untracked")
    assert _git("ls-files", "impl-shots").stdout.strip(), (
        "no impl-shots/ evidence is tracked any more")
