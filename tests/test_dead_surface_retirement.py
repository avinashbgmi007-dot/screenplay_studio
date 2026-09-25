"""Retired-and-dead surface guards (re-audit 2026-09-24).

Two findings were closed by REMOVING something rather than by adding
behaviour, and a removal is only durable if the next person cannot quietly
re-add it:

  * **L8 — the resizable script pane.** The divider was already inert
    (`style.css` pins `#script-pane` with `flex: 1 1 auto !important`, "the
    retired divider code must never squeeze the page back into a 70/30 split"):
    a measured 240px drag moved nothing while writing a `pane-width-v2` pref
    nothing honoured, and it stayed a mouse-only `role="separator"` on screen in
    the idea room. The audit's suggested fix (tabindex + arrow keys) would have
    added a keyboard path to a control that cannot move anything, so the element,
    its wiring, its pref and its CSS are gone.
  * **L7 — the second escape helper.** `_fvEscape` was a hand-rolled clone of
    core.js's canonical `escapeHtml`, and app.js already routes every other
    `innerHTML` sink through the canonical one.

Both are source-level pins on purpose: they cost nothing, they run everywhere,
and they fail at the moment the dead surface comes back.
"""

from __future__ import annotations

import os

WEBAPP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "screenplay_studio", "webapp")


def _read(name: str) -> str:
    with open(os.path.join(WEBAPP, name), "r", encoding="utf-8") as f:
        return f.read()


def _code_only(text: str) -> str:
    """Drop comments — prose may NAME a retired thing to explain its absence.

    The pins below are about live code: a mention inside a comment is the
    documentation of the retirement, not a re-introduction of it.

    LIMITATION, stated because it matters for a pin: this is a scanner, not a
    parser — a `//` inside a string literal (a URL, say) reads as a line comment
    and the rest of that line is dropped. The pins below name identifiers that no
    string literal in these files contains, and a false PASS can only come from a
    reference written AFTER such a `//` on the same line.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        two, four = text[i:i + 2], text[i:i + 4]
        if text.startswith("<!--", i):
            end = text.find("-->", i)
            i = n if end < 0 else end + 3
        elif two == "/*":
            end = text.find("*/", i)
            i = n if end < 0 else end + 2
        elif two == "//":
            end = text.find("\n", i)
            i = n if end < 0 else end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def test_the_retired_pane_divider_cannot_come_back():
    """No markup, no wiring, no pref, no CSS — the affordance was a no-op."""
    html, js, css = _code_only(_read("index.html")), _code_only(_read("app.js")), _code_only(_read("style.css"))
    assert "pane-divider" not in html, (
        "the retired divider is back in index.html — it is not connected to the "
        "layout (#script-pane is pinned full-width) and a mouse-only "
        'role="separator" is an a11y violation either way')
    assert "pane-divider" not in js, "app.js wires #pane-divider again"
    assert "pane-width-v2" not in js, (
        "the dead pane-width pref is written again (nothing reads it)")
    assert ".pane-divider" not in css, "the .pane-divider CSS is back"


def test_the_canonical_escape_helper_is_the_only_one():
    """`_fvEscape` was a second implementation of escapeHtml — drift waiting."""
    assert "_fvEscape" not in _code_only(_read("app.js")), (
        "a second escape helper is back; route the sink through core.js's "
        "escapeHtml (AGENTS.md: one canonical escape at the render boundary)")
