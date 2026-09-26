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

# ---- the three shapes round 6 found living inside a GREEN fleet --------------
# R6-E2E-1 proved the gap concretely: an export check written
#     code == 200 and "INT." in text or "EXT." in text or len(text) > 200
# binds as `(200 and "INT.") or "EXT." or len>200`, so a 500 error page passed
# it — and it sat in a fleet that ran 1,249 checks and printed PASS. The rules
# above (literal True / no condition) could not see it, because the vacuity is
# in the SHAPE of the expression, not a bare constant. These three cover that
# class; each is proven on a synthetic snippet below, so a rule that stops
# firing on real code is caught rather than assumed.

_OPS = (ast.And, ast.Or)


def _is_check(node):
    fn = node.func
    name = (fn.attr if isinstance(fn, ast.Attribute)
            else fn.id if isinstance(fn, ast.Name) else None)
    return name in CHECK_NAMES


def _cond(node):
    kwargs = {k.arg: k.value for k in node.keywords}
    return node.args[1] if len(node.args) >= 2 else kwargs.get("cond")


def _wrapped(lines, node):
    """Was THIS operand written inside its own parentheses?

    The AST throws parens away, so `a and b or c` and `a and (b or c)` are
    indistinguishable as trees — and only one of them means what its author
    thought. This reads the source back, which is the whole point of the rule.
    """
    before = lines[node.lineno - 1][:node.col_offset].rstrip()
    after = lines[node.end_lineno - 1][node.end_col_offset:node.end_col_offset + 2]
    return before.endswith("(") and after.lstrip().startswith(")")


def _vacuous_sites(src, tree):
    """[(line, why)] for check conditions that cannot evaluate to False."""
    lines = src.splitlines()
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_check(node)):
            continue
        cond = _cond(node)
        if cond is None:
            continue
        for sub in ast.walk(cond):
            if isinstance(sub, ast.BoolOp):
                for v in sub.values:
                    if isinstance(v, ast.Constant) and v.value in (True, None):
                        hits.append((node.lineno, "a literal in an or/and chain"))
                    elif (isinstance(v, ast.BoolOp)
                          and type(v.op) is not type(sub.op)
                          and not _wrapped(lines, v)):
                        hits.append((node.lineno, "and/or mixed without parentheses"))
            # `len(x) >= 0` and `x.count() >= 0` are true for every value a
            # length can hold. That is the idiom R6-E2E-3 found guarding a
            # dismiss that did nothing.
            elif (isinstance(sub, ast.Compare) and len(sub.ops) == 1
                    and isinstance(sub.left, ast.Call)
                    and isinstance(sub.comparators[0], ast.Constant)):
                fn = sub.left.func
                called = (fn.id if isinstance(fn, ast.Name)
                          else getattr(fn, "attr", ""))
                op, rhs = sub.ops[0], sub.comparators[0].value
                never_false = ((isinstance(op, ast.GtE) and rhs == 0)
                               or (isinstance(op, ast.Gt) and rhs == -1))
                if called in ("len", "count") and never_false:
                    hits.append((node.lineno, "a length compared against 0"))
        if isinstance(cond, ast.Constant) and cond.value in (True, None):
            hits.append((node.lineno, "a literal condition"))
    return sorted(set(hits))


@pytest.mark.parametrize("snippet, reason", [
    # exactly what shipped in R6-E2E-1
    ('check("export works", code == 200 and "INT." in t or "EXT." in t)', "and/or"),
    ('check("dismiss worked", rows.count() >= 0)', "length"),
    ('check("decoration", True)', "literal"),
])
def test_each_rule_fires_on_the_shape_it_exists_to_catch(snippet, reason):
    """A guard that cannot fire is the same defect it polices. Prove each one red
    before trusting it green, and prove it STAYS green on the parenthesised form
    so the rule filters instead of bullying."""
    tree = ast.parse(snippet)
    hits = _vacuous_sites(snippet, tree)
    assert hits, f"{snippet!r} is the defect this rule was written for"
    assert reason in " ".join(w for _, w in hits)


def test_the_parenthesised_form_is_clean():
    good = ('check("export works",\n'
            '      (code == 200 and ("INT." in t or "EXT." in t) and len(t) > 200))')
    assert not _vacuous_sites(good, ast.parse(good))


def test_no_suite_uses_a_condition_that_cannot_fail():
    suites = sorted(TESTS_DIR.glob("e2e_browser_*.py"))
    assert len(suites) >= 40, f"only {len(suites)} suites found — the scan is broken"
    offenders = []
    for path in suites:
        src = path.read_text(encoding="utf-8", errors="replace")
        offenders += [f"{path.name}:{line} ({why})"
                      for line, why in _vacuous_sites(src, ast.parse(src))]
    assert not offenders, (
        "these checks cannot evaluate to False, so they count as passes while "
        f"asserting nothing: {offenders}"
    )


# ---- R6-E2E-2: the `if`-guarded block with no `else` -------------------------
# The fourth shape the fleet's own hygiene test could not see. When every check in
# a suite sits inside `if <fixture precondition>:` and that guard has no `else`, a
# rename or a changed fixture deletes the ASSERTION without failing anything: the
# suite records nothing, prints PASS, and the product law it guarded — "the script
# pane never drops below 50%" — stops being tested in silence.
# `e2e_browser_dock_sections.py:596-605` is the correct local shape (an `else`
# that records a failing check), so this is a known pattern that never got applied
# elsewhere.
#
# A ratchet, not a clean rule: 53 raw sites when this was written, 25 once the
# guards that already pair with a hoisted precondition check are excluded (see
# _preceded_by_precondition_check — that shape cannot silence anything).
# Converting a real one costs a fixture judgement per site, so the ceiling may
# only FALL and nothing new may enter. layout_audit's 13 were the worst cluster
# and are now 0: the suite seeds its own desk, so the "<50% manuscript" law and
# the fix-loop contract are asserted again (25 checks -> 37, run twice). Largest
# survivor is gun_pen_audit, which SKIPs outright without a live llama-server —
# unrun, and named as such, rather than silently empty.
IF_GUARD_CEILING = 23


def _preceded_by_precondition_check(guard, prevs):
    """True when a statement just above the guard already records a failing check
    for the SAME condition — `check("control present", x.count() > 0)` followed by
    `if x.count(): click…`. That shape cannot silence anything: the precondition
    went red a line earlier, and the guard only avoids aborting the suite on a
    click that would throw. Not the defect."""
    test = ast.unparse(guard.test)
    # `if not found:` is the same precondition as a preceding
    # `check("...", found)` — the bail-out branch, not the silent branch.
    positives = {test, test[4:] if test.startswith("not ") else f"not {test}"}
    for stmt in prevs:
        for call in ast.walk(stmt):
            if not (isinstance(call, ast.Call) and _is_check(call)):
                continue
            cond = _cond(call)
            if cond is None:
                continue
            cond_src = ast.unparse(cond)
            if any(p in cond_src for p in positives):
                return True
    return False


def _if_guarded_sites():
    hits = []
    for path in sorted(TESTS_DIR.glob("e2e_browser_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))

        def visit(block):
            for i, stmt in enumerate(block):
                if (isinstance(stmt, ast.If) and not stmt.orelse
                        and any(_is_check(c) for c in ast.walk(stmt)
                                if isinstance(c, ast.Call))
                        and not _preceded_by_precondition_check(
                            stmt, block[max(0, i - 3):i])):
                    hits.append(f"{path.name}:{stmt.lineno}")
                for attr in ("body", "orelse", "finalbody"):
                    sub = getattr(stmt, attr, None)
                    if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                        visit(sub)

        visit(tree.body)
    return hits


def test_if_guarded_checks_do_not_grow():
    sites = _if_guarded_sites()
    assert len(sites) <= IF_GUARD_CEILING, (
        f"{len(sites)} checks sit inside an `if` with no `else` (ceiling "
        f"{IF_GUARD_CEILING}). When the guard is false the suite records nothing "
        "and still prints PASS. Give the guard an "
        "`else: check(..., False, 'guard not reached')` like "
        f"dock_sections.py:596-605, or lower the ceiling honestly: {sites}"
    )


def test_the_ratchet_is_not_a_free_pass():
    """A ceiling above zero is only trustworthy if the scanner still sees the
    shape it counts — and if the queue it describes is real. Proves the scan is
    wired to the AST rather than returning a constant."""
    sites = _if_guarded_sites()
    assert len(sites) == IF_GUARD_CEILING, (
        f"the queue moved to {len(sites)}; update IF_GUARD_CEILING in the same "
        "commit so the direction (down) stays visible in the diff"
    )
    # layout_audit carried 13 of these (the "<50% manuscript" law and the whole
    # fix-loop contract behind `if cards.count() > 0:`, with no project seeded).
    # Guard the repair: none of its guards may come back.
    assert not [s for s in sites if s.startswith("e2e_browser_layout_audit.py:")]
    sample = (
        'def t():\n'
        '    if widths:\n'
        '        check("the pane never drops below 50%", ok)\n')
    tree = ast.parse(sample)
    guarded = [n for n in ast.walk(tree)
               if isinstance(n, ast.If) and not n.orelse
               and any(_is_check(c) for c in ast.walk(n) if isinstance(c, ast.Call))]
    assert len(guarded) == 1
