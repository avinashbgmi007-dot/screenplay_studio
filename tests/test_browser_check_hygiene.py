"""UX-5 — a browser check must carry a condition.

`Checks.ok` used to be `def ok(self, name, cond=True, detail="")`. Eight calls in
`e2e_browser_ui_batch.py` passed a name and nothing else, so they verified
nothing while still counting as passes: 8 of the fleet's 1,235 checks were
decoration. The audit found those eight; the default is what let them exist.

This guards the whole fleet against the shape returning, at both ends:

  * the CAUSE — `cond` has no default, so a marker-only call is a `TypeError` at
    the moment it is written rather than a silent pass. (`export_flush` has
    always declared its own `ok(name, cond, extra="")` this way.)
  * the SYMPTOM — no suite passes a literal `True`/`None` as the condition.

A literal `False` is deliberately NOT flagged: `ok("x", False, detail)` is the
fleet's established "record a failure with a reason" idiom, used inside `except`
blocks and precondition-failure branches (33 sites). A rule that flagged it would
be wrong 33 times, and a guard that cries wolf gets deleted.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from e2e_browser_common import Checks  # noqa: E402

TESTS_DIR = pathlib.Path(__file__).parent
CHECK_NAMES = ("ok", "check")


def _scan():
    """[(file, line, condition-node)] for every ok/check call in the fleet."""
    found = []
    suites = sorted(TESTS_DIR.glob("e2e_browser_*.py"))
    for path in suites:
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:  # a broken suite is a different failure
            pytest.fail(f"{path.name} does not parse: {exc}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else fn.id if isinstance(fn, ast.Name) else None)
            if name not in CHECK_NAMES:
                continue
            kwargs = {k.arg: k.value for k in node.keywords}
            cond = node.args[1] if len(node.args) >= 2 else kwargs.get("cond")
            found.append((path.name, node.lineno, cond))
    return suites, found


def test_the_helper_has_no_default_condition():
    """The cause. With a default, `ok("name")` silently passes and the reported
    check total is inflated by decoration."""
    params = inspect.signature(Checks.ok).parameters
    assert "cond" in params, "the helper was renamed; this guard needs re-pointing"
    assert params["cond"].default is inspect.Parameter.empty, (
        "Checks.ok's `cond` has a default again — a marker-only call would now "
        "pass silently. A check with no condition to assert should be deleted, "
        "not defaulted to True."
    )


def test_no_suite_passes_a_literal_condition():
    suites, calls = _scan()

    # Non-vacuity. A glob that matched nothing, or a helper that got renamed,
    # would make the assertion below pass while guarding nothing at all.
    assert len(suites) >= 40, f"only {len(suites)} suites found — the scan is broken"
    assert len(calls) >= 500, f"only {len(calls)} ok/check calls found — the scan is broken"

    markers = [
        f"{name}:{lineno}"
        for name, lineno, cond in calls
        if isinstance(cond, ast.Constant) and (cond.value is True or cond.value is None)
    ]
    assert not markers, (
        "these checks pass a literal condition, so they assert nothing while "
        f"counting as passes — fold in the real condition or delete the marker: "
        f"{markers}"
    )


def test_no_suite_omits_the_condition():
    """The `TypeError` the signature change produces, caught statically so the
    failure names the call site instead of surfacing as a suite crash."""
    _, calls = _scan()
    missing = [f"{name}:{lineno}" for name, lineno, cond in calls if cond is None]
    assert not missing, (
        "these checks pass no condition at all (and would raise TypeError): "
        f"{missing}"
    )
