"""Static contract guards for the SPA — two claims the source makes about itself.

Both come from the 2026-09-21 audit's frontend section, and both were wrong in a
way a reader could not see without measuring:

**FE-M2** — `state.view`'s declaration comment said `// "chat" | "script"` while
`openViewByName()` accepted nine names. The comment had drifted; nobody noticed
because a comment cannot fail. The comment now declares the union in a form this
module can read, and the test below asserts it against the source — so the next
drift is a red test rather than a lie.

**FE-M3** — the audit reported undo/redo as "unreachable by mouse ... and
undiscoverable", `✅ code-verified`. The observation is true; the classification is
not. `index.html:206-208` documents the hiding as deliberate, and that comment
predates the audit by eleven days (`f648506`, 2026-09-10). The real defect was
elsewhere: `app.js` told the writer "Undo is in the script toolbar" — pointing at
the one control the code deliberately never renders.

So these tests do NOT assert the buttons are visible. They pin the *decision*:

  * the controls are hidden, and nothing can reveal them (checked across every
    reveal mechanism the SPA actually uses, and across the stylesheet);
  * the reason travels with the code, so a future reader meets the intent before
    the diff;
  * no user-facing copy names a LOCATION for undo/redo, because that is the claim
    the product cannot keep while the controls stay hidden;
  * the copy names the KEYBOARD instead — which is the actual contract
    (`app.js:8627` binds Ctrl/⌘ Z to `undoEdit()` in the views that have edits).

**Why there is no browser check for the hiding.** An inline `display:none` is
defeated only by an `!important` rule. The stylesheet's 19 `display:...!important`
declarations were enumerated: 13 are inside `@media print` (they hide, they do not
show) and the six outside it target `.gutter`, `.script-level-notes`,
`.finding-summary` and `#cowrite-panel` — none of them these controls. The only
rule naming `#undo-btn`/`#redo-btn` is `style.css:3572`, inside `@media print`. So
the computed value is determined by the markup and a browser adds nothing.
`tests/test_spa_contract.py` therefore stays a source check: fast, and it runs on
every pytest invocation rather than in the slower browser fleet.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(ROOT, "screenplay_studio", "webapp")
INDEX = os.path.join(WEBAPP, "index.html")
APPJS = os.path.join(WEBAPP, "app.js")
STYLECSS = os.path.join(WEBAPP, "style.css")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# FE-M2 — the view-name union
# ---------------------------------------------------------------------------

# The else-branch of `openViewByName` is the writing desk. It is a real accepted
# name but it is never *compared*, so it is declared in the comment without
# appearing as a `view === "..."` literal. Naming it here is the honest way to
# say "the union has one member the comparison cannot show".
DEFAULT_VIEW = "cowrite"


def _declared_view_union(src: str) -> set:
    """The union the declaration comment claims `openViewByName` accepts.

    Read from the single `// VIEWS:` line rather than from the surrounding prose.
    The first version of this extractor scraped every `|`-separated token out of
    the whole comment block and got a union that was missing `compare` and `fv` —
    because the joined lines put a `//` in front of one token and the em-dash
    sentence swallowed another. Prose is not a data format; the declaration line
    is, and a guard should read the thing that was written to be read.
    """
    lines = src.split("\n")
    idx = None
    for i, line in enumerate(lines):
        if re.match(r'\s*view:\s*"chat",\s*$', line):
            idx = i
            break
    assert idx is not None, (
        "could not find the `view: \"chat\",` declaration in app.js — the guard's "
        "anchor moved, so this test is now checking nothing"
    )

    block = []
    j = idx - 1
    while j >= 0 and lines[j].strip().startswith("//"):
        block.append(lines[j])
        j -= 1
    block.reverse()
    comment = "\n".join(block)

    m = re.search(r"//\s*VIEWS:\s*(.+)", comment)
    assert m, (
        "the `// VIEWS:` declaration line is gone from the comment above "
        "`view: \"chat\",`. It is the machine-readable half of the contract; "
        "without it this guard cannot tell drift from a rewrite."
    )
    names = {tok.strip() for tok in m.group(1).split("|")}
    bad = {n for n in names if not re.fullmatch(r"[a-z_]+", n)}
    assert not bad, f"unparseable token(s) on the VIEWS line: {sorted(bad)}"
    return names


def _source_view_names(src: str) -> set:
    """Every literal `openViewByName` actually compares `view` against."""
    start = src.find("async function openViewByName(")
    assert start != -1, "openViewByName is gone — update this guard"
    end = src.find("\n}", start)
    assert end != -1, "could not find the end of openViewByName"
    body = src[start:end]
    return set(re.findall(r'view\s*===\s*"([a-z_]+)"', body))


def test_the_view_union_comment_matches_the_source():
    """FE-M2. The comment is a claim; this makes it a checked one."""
    src = _read(APPJS)
    declared = _declared_view_union(src)
    compared = _source_view_names(src)

    # Non-vacuity: both sides must have been read. A regex that silently matched
    # nothing would make the equality below pass while guarding nothing.
    assert len(compared) >= 6, (
        f"only {len(compared)} compared view names found — the extraction broke"
    )
    assert declared, "the declaration comment yielded no names"

    expected = compared | {DEFAULT_VIEW}
    assert declared == expected, (
        "the `state.view` declaration comment and openViewByName() disagree.\n"
        f"  comment declares : {sorted(declared)}\n"
        f"  source accepts   : {sorted(expected)}\n"
        f"  comment-only     : {sorted(declared - expected)}\n"
        f"  source-only      : {sorted(expected - declared)}"
    )


def test_the_view_union_guard_can_fail():
    """The guard above is only worth having if a drift turns it red.

    This feeds the extractors a source whose comment omits a live name and
    asserts the disagreement is detected — so the equality in the test above is
    known to be reachable, not vacuous by construction.
    """
    src = _read(APPJS)
    drifted = src.replace(
        "VIEWS: premise | cowrite | feedback | compare | revision | beatboard",
        "VIEWS: premise | cowrite | feedback | revision | beatboard",
        1,
    )
    assert drifted != src, "the drift fixture no longer matches the VIEWS line"

    declared = _declared_view_union(drifted)
    compared = _source_view_names(drifted)
    assert declared != compared | {DEFAULT_VIEW}, (
        "a comment missing a live view name still compared equal — the guard is "
        "vacuous"
    )
    assert "compare" in (compared - declared)


# ---------------------------------------------------------------------------
# FE-M3 — the deliberately hidden controls, and the copy that must match them
# ---------------------------------------------------------------------------

# The controls with no visible surface, by design. Declared, not computed: see
# the module docstring for why a computed set is unsound here.
HIDDEN_BY_DESIGN = ("undo-btn", "redo-btn")

# The control that carries the SAME inline `display:none` and IS revealed, used
# to prove the reveal-detection below actually works.
REVEALED_CONTRAST = "reset-edits-btn"

# Location nouns. Copy that sends the writer to a *place* is the defect: the
# place does not exist on screen.
LOCATION_NOUNS = re.compile(r"\b(toolbar|menu|dropdown|button)\b", re.IGNORECASE)
UNDO_REDO = re.compile(r"\b(undo|redo)\b", re.IGNORECASE)
KEYBOARD = re.compile(r"Ctrl/⌘ Z|Ctrl\+Z|⌘Z")


def _inline_hidden_ids(html: str) -> set:
    """Ids of elements carrying an inline `display:none`."""
    hidden = set()
    for tag in re.findall(r"<[a-zA-Z][^>]*>", html):
        m_id = re.search(r'\bid="([^"]+)"', tag)
        m_st = re.search(r'\bstyle="([^"]*)"', tag)
        if m_id and m_st and re.search(r"display\s*:\s*none", m_st.group(1)):
            hidden.add(m_id.group(1))
    return hidden


def _reveal_targets(js: str) -> set:
    """Ids some JS path can make visible.

    Every mechanism the SPA uses to change visibility, not just `.style.display`:
    the first version of this helper checked only that one and reported 20
    controls as "permanently hidden" when the true answer is 2, because modals are
    revealed by class toggles and `.hidden`. An unsound detector is worse than
    none, so the mechanisms are enumerated explicitly.
    """
    targets = set()
    targets |= set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)\s*\.style\.display', js))
    targets |= set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)\s*\.hidden\s*=', js))
    targets |= set(re.findall(r'getElementById\("([A-Za-z0-9_-]+)"\)\s*\.hidden\s*=', js))
    # classList toggles: `$("#x").classList.add/remove/toggle(...)`
    targets |= set(re.findall(
        r'\$\("#([A-Za-z0-9_-]+)"\)\s*\.classList\s*\.\s*(?:add|remove|toggle)', js))
    # the modal helpers take a selector
    targets |= set(re.findall(r'(?:open|close)Modal\("#([A-Za-z0-9_-]+)"', js))
    return targets


def _css_display_selectors(css: str) -> set:
    """Ids a stylesheet rule outside `@media print` gives a `display` to.

    Only outside print matters: a print rule can hide a control but never show
    one on screen.
    """
    lines = css.split("\n")
    starts = [i for i, l in enumerate(lines) if re.match(r"\s*@media\s+print", l)]
    ranges = []
    for s in starts:
        e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("}")),
                 len(lines) - 1)
        ranges.append((s, e))

    def in_print(n):
        return any(s < n <= e for s, e in ranges)

    found = set()
    for i, line in enumerate(lines):
        if "display" not in line or in_print(i):
            continue
        for sel in re.findall(r"#([A-Za-z0-9_-]+)", line):
            found.add(sel)
    return found


@pytest.mark.parametrize("control", HIDDEN_BY_DESIGN)
def test_the_deliberately_hidden_controls_are_still_hidden(control):
    """FE-M3, the decision half: hidden, and nothing can reveal them."""
    html, js, css = _read(INDEX), _read(APPJS), _read(STYLECSS)

    assert control in _inline_hidden_ids(html), (
        f"#{control} no longer carries an inline display:none. If it was made "
        f"visible on purpose, delete this test and the comment at "
        f"index.html:206-208 together — but make it a decision, not a drift."
    )
    assert control not in _reveal_targets(js), (
        f"#{control} is now revealed by app.js. The hiding was documented as "
        f"deliberate; if that changed, the copy that names Ctrl/⌘ Z and this "
        f"guard both need to change with it."
    )
    assert control not in _css_display_selectors(css), (
        f"#{control} is given a display by a stylesheet rule outside @media "
        f"print, which would defeat the inline style"
    )


def test_the_hidden_control_detector_can_see_a_revealed_control():
    """Non-vacuity for the test above.

    `#reset-edits-btn` carries the same inline `display:none` and IS revealed
    (`app.js` sets its `.style.display` from `hasEdits`). If the detector cannot
    see that, then "not revealed" above proves nothing about undo/redo — it just
    means the regex is broken.
    """
    html, js = _read(INDEX), _read(APPJS)
    assert REVEALED_CONTRAST in _inline_hidden_ids(html), (
        "the contrast control is no longer inline-hidden, so it no longer tests "
        "the subtraction"
    )
    assert REVEALED_CONTRAST in _reveal_targets(js), (
        "the reveal detector missed a control that IS revealed — so it would also "
        "miss nothing and report undo/redo as hidden for the wrong reason"
    )


def test_the_reason_for_hiding_travels_with_the_code():
    """The intent has to be readable where the markup is, or the next reader
    re-opens FE-M3 as a bug — which is exactly what the audit did."""
    html = _read(INDEX)
    assert "no visible surface on purpose" in html, (
        "the comment explaining why undo/redo are hidden is gone. Without it the "
        "hidden buttons read as an oversight (the 2026-09-21 audit read them that "
        "way) and get 'fixed' by someone who has not seen the keyboard contract."
    )


def _js_literals(src: str) -> list:
    """String literals in a JS source, with comments and code skipped.

    A plain regex over the file is unsound here and the first version of this
    scan proved it: it matched from the apostrophe in a prose comment
    ("the writer's line ... another's") to the next apostrophe hundreds of lines
    away, and reported whole blocks of code as one "string literal". The result
    was a list of offenders that were not copy at all.

    So this walks the source once, tracking whether it is inside a line comment,
    a block comment or a quoted string, and collects only the last. Escapes are
    honoured. Template literals are collected whole (the `${...}` parts come
    along, which is what we want for a copy check).
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if c in "\"'`":
            quote = c
            i += 1
            buf = []
            while i < n and src[i] != quote:
                if src[i] == "\\" and i + 1 < n:
                    buf.append(src[i + 1])
                    i += 2
                    continue
                buf.append(src[i])
                i += 1
            i += 1
            out.append("".join(buf))
            continue
        i += 1
    return out


def test_the_literal_scanner_does_not_read_comments():
    """Non-vacuity for the copy rule below, and a regression test for the way
    this scan was first written.

    Comments in this file's subject matter mention undo constantly ("rides the
    existing apply/undo path"). If the scanner reads them, the copy rule either
    fires on prose or is satisfied by prose — in both cases it stops measuring
    the product.
    """
    src = '// the writer\'s undo path\nconst a = "keep me";\n/* redo this */\n'
    got = _js_literals(src)
    assert got == ["keep me"], f"scanner returned {got}"
    # and it must still see real copy that mentions the word
    assert _js_literals('x = "Undo is here";') == ["Undo is here"]


def test_no_user_facing_copy_names_a_location_for_undo_or_redo():
    """FE-M3, the defect half — and the part the audit missed.

    The product may not tell the writer to look in a place for undo/redo, because
    there is no such place on screen. `app.js` said "Undo is in the script
    toolbar" while the toolbar's Undo button is `display:none`.
    """
    js = _read(APPJS)
    literals = _js_literals(js)

    # Non-vacuity: the scan must have found real copy to inspect.
    mentioning = [s for s in literals if UNDO_REDO.search(s)]
    assert len(mentioning) >= 3, (
        f"only {len(mentioning)} string literals mention undo/redo — the scan "
        f"broke, and an empty scan passes the rule below for the wrong reason"
    )

    offenders = [s for s in mentioning if LOCATION_NOUNS.search(s)]
    assert not offenders, (
        "user-facing copy sends the writer to a LOCATION for undo/redo, but the "
        "controls are display:none by design so no such location exists on "
        f"screen:\n  " + "\n  ".join(repr(s) for s in offenders)
    )

    # The rule above is satisfied by DELETING the hint, which would be a
    # regression dressed as a pass. So the confirmation that follows an applied
    # rewrite must still tell the writer HOW to undo — by naming the keyboard,
    # which is the actual contract (`app.js:8627` binds Ctrl/⌘ Z to undoEdit).
    confirmations = [s for s in literals if "Applied to the working copy" in s]
    assert confirmations, (
        "the post-apply confirmation is gone. It is the only place the writer is "
        "told how to reverse an applied rewrite; losing it is not a fix for the "
        "copy having named the wrong thing."
    )
    assert any(KEYBOARD.search(s) for s in confirmations), (
        "the post-apply confirmation no longer names the keyboard. The undo/redo "
        f"buttons are display:none by design, so the hint must name Ctrl/⌘ Z:\n  "
        + "\n  ".join(repr(s) for s in confirmations)
    )
