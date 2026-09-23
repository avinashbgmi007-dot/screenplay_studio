"""WCAG 2.4.7 guard: no bare `outline: none` suppressors in the stylesheet.

Removing a focus ring without putting a visible affordance back is how
keyboard users lose their place. This sheet is allowed to suppress the ring
only in two situations:

  1. **The suppressor IS the focus rule and it replaces the ring** — the same
     declaration block carries a visible alternative (`box-shadow`, `border`
     or `background`). The ring is swapped, not deleted.
  2. **The selector is on the audited whitelist below** — containers and the
     writing surface, where a ring would be hostile.

Anything else must be paired with a `:focus` / `:focus-visible` rule for the
same selector that provides a visible alternative.

This replaces the dormant root-level `_r2_a11y_guard.py` (deleted
2026-09-21). That script failed twice over:

  * **Nothing ran it.** Not CI, not pytest, not the browser gate — despite
    `docs/design/R2_PRIMITIVES_SPEC.md` describing it as a "permanent gate".
  * **It could not fail.** Its third compensation branch read

        if re.search(re.escape(base), css) and ":focus-within" in css:

    but `base` IS the rule's own selector, so the first conjunct is always
    true and the branch collapses to `":focus-within" in css` — true, because
    this sheet contains 13 of them. Every suppressor was excused. Executed
    proof: injecting `.zz-injected-bare-suppressor { outline: none; }` still
    printed `clean — 18 outline:none sites, all compensated/whitelisted`.

`test_the_detector_can_fail` below is the standing proof that the replacement
does not repeat that mistake.
"""

from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_PATH = os.path.join(ROOT, "screenplay_studio", "webapp", "style.css")

# Audited 2026-09-12, re-confirmed 2026-09-21. Keyed on the selector exactly as
# written in the sheet. `test_whitelist_entries_still_exist` fails if an entry
# outlives the rule it describes, so this list cannot quietly stop being true.
WHITELIST = {
    "#main:focus":
        "the manuscript container — a ring around the whole page is hostile",
    ".idea-content":
        "the idea writing surface — word-processor caret exemption; a ring "
        "while typing prose would be actively hostile",
}

# Declarations that put a visible affordance back once the ring is gone.
VISIBLE_ALTERNATIVES = ("box-shadow", "border", "background", "outline-offset")

# `selector { body }` — enough for a flat stylesheet. At-rules (`@media`,
# `@supports`) wrap further nesting, but every `outline: none` in this sheet
# sits in a top-level rule; `test_the_parser_sees_the_real_sheet` pins that.
_RULE_RE = re.compile(r"([^\n{}]+)\{([^}]*)\}")
_PSEUDO_RE = re.compile(r":(focus-visible|focus-within|focus)$")


def _rules(css: str) -> list[tuple[str, str, int]]:
    """(selector, body, 1-based line) for every flat rule in the sheet."""
    out = []
    for m in _RULE_RE.finditer(css):
        sel = " ".join(m.group(1).split())
        if not sel or sel.startswith("@"):
            continue
        out.append((sel, m.group(2), css[: m.start()].count("\n") + 1))
    return out


def _parts(selector: str) -> list[tuple[str, str]]:
    """Split a comma group into (base, pseudo) pairs.

    `a:focus, b` -> [("a", ":focus"), ("b", "")]. Pseudo-elements like
    `::before` are left inside `base`; they never carry a focus state.
    """
    pairs = []
    for raw in selector.split(","):
        part = raw.strip()
        m = _PSEUDO_RE.search(part)
        if m:
            pairs.append((part[: m.start()].strip(), m.group(0)))
        else:
            pairs.append((part, ""))
    return pairs


def _has_visible_alternative(body: str) -> bool:
    """True if the block puts an affordance back after suppressing the ring.

    A bare `outline: none` alongside, say, `box-shadow: 0 0 0 2px accent`
    satisfies 2.4.7; the same declaration with nothing else does not.
    """
    return any(k in body for k in VISIBLE_ALTERNATIVES)


def _suppressors(css: str) -> list[tuple[int, str, str, str]]:
    """Every (line, base, pseudo, body) whose block suppresses the outline."""
    found = []
    for sel, body, line in _rules(css):
        if not re.search(r"outline\s*:\s*none", body):
            continue
        for base, pseudo in _parts(sel):
            found.append((line, base, pseudo, body))
    return found


def _is_bare(base: str, pseudo: str, body: str, css: str) -> bool:
    """True when this suppressor has no compensating focus affordance."""
    # 1. the audited whitelist wins outright — it is a reviewed exception, and
    #    `#main:focus` is a focus rule that suppresses the ring with nothing put
    #    back, deliberately. (`#manuscript-container` is not on the list: it no
    #    longer suppresses anything — it declares a `:focus-visible` ring.)
    if f"{base}{pseudo}" in WHITELIST:
        return False
    # 2. the suppressor is itself a focus rule that swaps the ring
    if pseudo in (":focus", ":focus-visible"):
        return not _has_visible_alternative(body)
    # 3. a focus rule for the same selector that puts an affordance back
    for sel, other_body, _ in _rules(css):
        if not _has_visible_alternative(other_body):
            continue
        for other_base, other_pseudo in _parts(sel):
            if other_base != base:
                continue
            if other_pseudo in (":focus", ":focus-visible", ":focus-within"):
                return False
    return True


def _bare_sites(css: str) -> list[tuple[int, str]]:
    return [
        (line, f"{base}{pseudo}")
        for line, base, pseudo, body in _suppressors(css)
        if _is_bare(base, pseudo, body, css)
    ]


def _sheet() -> str:
    with open(CSS_PATH, encoding="utf-8") as f:
        return f.read()


# ---------- the gate ---------------------------------------------------------

def test_no_bare_outline_suppressors():
    """The real check: every `outline: none` in the sheet is compensated."""
    bare = _bare_sites(_sheet())
    assert not bare, (
        "bare `outline: none` suppressors found — a keyboard user cannot see "
        "where they are (WCAG 2.4.7). Replace the ring with a visible "
        "alternative (box-shadow / border / background) or justify the "
        "selector on the WHITELIST in this file:\n"
        + "\n".join(f"  style.css L{line}: {sel}" for line, sel in bare))


def test_the_parser_sees_the_real_sheet():
    """Guard the guard: a parser that finds nothing would pass vacuously.

    The old script's failure was a branch that could not fail. A silent
    parse failure is the same trap one layer down, so the count is pinned.
    """
    css = _sheet()
    sites = _suppressors(css)
    assert len(sites) >= 15, (
        f"only {len(sites)} outline-suppressing rules parsed out of "
        f"{len(_rules(css))} rules — the parser has drifted from the sheet's "
        f"shape, which would make test_no_bare_outline_suppressors vacuous")
    assert "outline" in css, "style.css is not the file this test expects"


def test_whitelist_entries_still_exist():
    """A whitelist entry with no matching rule is stale — it excuses nothing.

    Same anti-staleness rule the route-coverage registry uses: a declaration
    that no longer describes reality is worse than no declaration, because it
    reads as reviewed.
    """
    selectors = {f"{base}{pseudo}" for _, base, pseudo, _ in _suppressors(_sheet())}
    stale = sorted(set(WHITELIST) - selectors)
    assert not stale, (
        f"WHITELIST entries match no `outline: none` rule: {stale} — remove "
        f"them, or the list stops describing the sheet")


def test_the_detector_can_fail():
    """The standing proof this guard is not the vacuous one it replaces.

    Inject a suppressor on a fresh selector with no focus affordance anywhere
    and assert the detector flags it. This is the exact input the deleted
    `_r2_a11y_guard.py` reported as `clean`.
    """
    injected = (
        _sheet()
        + "\n.zz-injected-bare-suppressor { outline: none; }\n"
    )
    bare = _bare_sites(injected)
    assert any(sel == ".zz-injected-bare-suppressor" for _, sel in bare), (
        "the detector failed to flag a deliberately injected bare suppressor "
        "— this guard cannot fail, which is the defect it exists to fix")
    # and the real sheet stays clean, so the injection is the only difference
    assert not _bare_sites(_sheet()), "the real sheet must stay clean"


def test_compensated_suppressors_are_not_flagged():
    """The inverse: a suppressor WITH a visible alternative must pass.

    Without this, `_is_bare` could return True unconditionally and both the
    gate and the injection test would still be satisfied.
    """
    css = (
        ".zz-compensated:focus { outline: none; box-shadow: 0 0 0 2px #7e6bff; }"
    )
    assert not _bare_sites(css), "a ring swapped for a box-shadow is compliant"
    # and the same selector without the alternative IS bare
    assert _bare_sites(".zz-compensated:focus { outline: none; }")
