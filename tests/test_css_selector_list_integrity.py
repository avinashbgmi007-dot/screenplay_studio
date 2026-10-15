"""Guards the CSS against losing a declaration to an adjacent edit.

**The defect this exists for (Track A, found 2026-10-15).** Section 3 deleted the
`.gutter` selector from two comma-separated selector lists. In both cases the edit
took the list's shared `{ display: none !important; }` block with it, leaving the
survivors dangling. A dangling list is *valid CSS*: the survivors simply merged
into whatever rule came next and inherited its declarations.

Two rules were destroyed this way and only one was caught:

1. The spotlight hide rule. Four selectors absorbed `padding-top: 26px` and
   **nothing hid under spotlight mode**. Caught by `e2e_browser_phase13`.
2. The `@media print` hide rule. ~25 chrome selectors absorbed
   `display: block !important` from `#manuscript-workspace`, so the sidebar,
   the toolbars, the modals and the project bar would all have **printed**.
   Caught by nobody — no suite renders print media.

**Why brace balance was not enough.** `style.css` still balanced (1451 open,
1451 close) and `app.js` still parsed with the whole spotlight rule destroyed.
Neither check looks at whether a selector kept its declaration, because losing
one does not unbalance anything.

**Why a generic parser cannot catch it either.** The broken spotlight rule was
syntactically valid:

    .spotlight-mode #diff-banner,
    .spotlight-mode #manuscript-container { padding-top: 26px; }

That is a well-formed rule. It is merely the wrong rule. So this module pins the
rules that carry product behaviour rather than trying to infer intent from
syntax. `test_no_selector_list_lost_its_declaration` is a cheap tripwire for the
mechanical shape; the two `test_*_rule_*` tests are the ones that would have
caught the actual regressions.

This is a source check. No browser is involved, so it runs on every pytest
invocation rather than in the slower browser fleet.
"""
import os
import re

import pytest

WEBAPP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "screenplay_studio", "webapp")
CSS_PATH = os.path.join(WEBAPP, "style.css")


@pytest.fixture(scope="module")
def css() -> str:
    with open(CSS_PATH, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def code(css: str) -> str:
    """The stylesheet with comments removed — what the parser actually sees."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule_body(text: str, selector_fragment: str) -> str:
    """Return the full rule (selector list + declarations) that declares
    `selector_fragment`, or '' if no rule does.

    Matches on the *whole* rule rather than one line so that a selector list
    which has lost its declaration block cannot be mistaken for a healthy one.
    """
    for match in re.finditer(r"(?P<sel>[^{}]+)\{(?P<decl>[^{}]*)\}", text):
        if selector_fragment in match.group("sel"):
            return match.group(0)
    return ""


def test_the_stylesheet_exists_and_parses_to_balanced_braces(code: str) -> None:
    assert code.count("{") == code.count("}"), (
        "style.css braces are unbalanced: "
        f"{code.count('{')} open vs {code.count('}')} close"
    )


def test_no_selector_list_lost_its_declaration(code: str) -> None:
    """No rule may end in a dangling comma.

    This is the cheap mechanical tripwire for the defect above. It does not
    catch the spotlight rule as it actually broke (that list had no trailing
    comma — it ran straight into the next selector), so the two targeted tests
    below are the real guards. What this one does catch is the literal shape
    the print rule ended up in if the edit lands one line later.
    """
    dangling = [
        stmt.strip()[-120:]
        for stmt in re.findall(r"[^{}]+\{", code)
        if stmt.strip()[:-1].rstrip().endswith(",")
    ]
    assert not dangling, (
        "selector list ends with a dangling comma, so its declaration block was "
        f"lost to the next rule: {dangling}"
    )


def test_spotlight_rule_still_hides_the_chrome(code: str) -> None:
    """Spotlight mode must hide the project bar, desk toolbar, draft bar,
    diff banner and partner drawer — and it must do it with a real
    declaration, not inherit one from a neighbouring rule.

    `.gutter` is absent by design (Track A section 3 deleted the element).
    """
    rule = _rule_body(code, ".spotlight-mode #project-bar")
    assert rule, (
        "no rule declares `.spotlight-mode #project-bar` — the spotlight hide "
        "rule was destroyed. Spotting nothing but the page means these four "
        "bars stay on screen."
    )
    assert "display: none !important" in rule, (
        "the spotlight hide rule has lost its `display: none !important` and "
        f"its selectors are inheriting from a neighbouring rule: {rule!r}"
    )
    for selector in ("#desk-toolbar", "#draft-bar", "#diff-banner", "#room-drawer"):
        assert f".spotlight-mode {selector}" in rule, (
            f"spotlight no longer hides {selector}: {rule!r}"
        )


def _print_block(code: str) -> str:
    """Return the contents of the `@media print` block.

    Scoping matters: `#sidebar` also appears in the base layout rule, so a
    search over the whole stylesheet finds the wrong one. The first version of
    this test did exactly that and failed against a correct stylesheet.
    """
    start = code.index("@media print")
    depth = 0
    for i in range(start, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[start + 1:i]
    raise AssertionError("@media print block is not closed")


def test_print_rule_hides_chrome_and_shows_only_the_manuscript(code: str) -> None:
    """Print media must hide the sidebar and the chrome, and show the
    manuscript workspace.

    These two are separate rules on purpose. When the section 3 edit merged
    them, the chrome list absorbed `display: block !important` and the whole
    sidebar, both toolbars, the modals and the project bar would have printed
    on top of the script. Nothing caught it: no suite renders print media.
    """
    printed = _print_block(code)
    hide = _rule_body(printed, "#sidebar")
    assert hide, "no print rule declares `#sidebar` — print chrome hiding is gone"
    assert "display: none !important" in hide, (
        f"the print hide rule has lost its declaration: {hide!r}"
    )
    for selector in ("#desk-toolbar", "#project-bar", "#status-strip",
                     "#context-dock", "#scene-index"):
        assert selector in hide, f"print no longer hides {selector}: {hide!r}"
    assert "#manuscript-workspace" not in hide, (
        "#manuscript-workspace is the thing print must SHOW. It is in the hide "
        f"list, so the manuscript itself would be hidden: {hide!r}"
    )

    show = _rule_body(printed, "#manuscript-workspace")
    assert show, "no print rule declares `#manuscript-workspace`"
    assert "display: block !important" in show, (
        f"the manuscript is not restored to `display: block` in print: {show!r}"
    )