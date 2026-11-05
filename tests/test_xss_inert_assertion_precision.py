"""Gap 17 (XSS leg) — the inert assertion was over-broad, and it said so twice.

The browser suite's dashboard leg asserted `"<img" not in sc["html"]`, meaning
"no <img> tag was created". `renderDashboard` sets
`card.title = \\`Open "${p.title}" on the desk\\`` — a payload in the title lands
in a QUOTED ATTRIBUTE and serializes literally, so the raw-html substring found
`<img` while the same scan reported `handlers == 0 and exec == 0`: an inert DOM.
The suite failed twice on its own over-broad check, not on a vulnerability.

The register's recommendation was "retain the structural probe and improve test
precision". This file pins the improved check itself, which is testable without
a browser because it is a pure function over the serialized HTML the leg already
collects. The browser run still needs a Chromium binary (see the note at the
bottom), but the precision fix is no longer unverified.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from e2e_browser_xss_inert import has_raw_tag, markup_outside_attributes  # noqa: E402

# The exact shapes the suite plants.
PAY_TAG = '<img src=x onerror="window.__XSS_DASH=2">'
PAY_ATTR = 'complete" onclick="window.__XSS_DASH=1'


# ---------------------------------------------------------------------------
# The false positive this fixed
# ---------------------------------------------------------------------------

def test_a_payload_in_a_quoted_title_is_not_a_raw_tag():
    """The measured case: `renderDashboard` builds
    `title="Open &quot;<img src=x onerror=...>&quot; on the desk"`."""
    html = ('<div class="dash-card" title="Open &quot;' + PAY_TAG +
            '&quot; on the desk"><span class="dash-card-title">xss probe</span></div>')

    assert "<img" in html, "precondition: the old substring check WOULD have matched"
    assert has_raw_tag(html, "img") is False, (
        "a payload inside a quoted attribute is text, not a tag — the over-broad "
        "check is what failed, not the escaping")


def test_the_old_substring_check_would_have_failed_that_markup():
    """Pins the regression in the check itself, so a future edit cannot quietly
    restore `"<img" not in html`."""
    html = '<div title="Open &quot;<img src=x>&quot;">ok</div>'
    assert ("<img" in html) is True          # the old assertion fails here
    assert has_raw_tag(html, "img") is False  # the precise one does not


# ---------------------------------------------------------------------------
# ...and it must still catch a real one
# ---------------------------------------------------------------------------

def test_a_real_tag_outside_an_attribute_is_still_caught():
    """The property the assertion exists for. Loosening it into vacuity would be
    worse than the false positive."""
    html = '<div class="card"><img src=x onerror="window.__XSS=1"></div>'
    assert has_raw_tag(html, "img") is True


def test_a_real_tag_after_a_quoted_attribute_is_still_caught():
    """The realistic escaping failure: the payload breaks out of the attribute
    and becomes a sibling node."""
    html = ('<div title="Open &quot;x&quot; on the desk">'
            '<img src=x onerror="window.__XSS=1"></div>')
    assert has_raw_tag(html, "img") is True


def test_a_single_quoted_attribute_is_handled():
    """Serialized HTML uses double quotes, but the scan must not assume it —
    a hand-built fixture or an innerHTML round trip can produce single ones."""
    assert has_raw_tag("<div title='a <b>'>text</div>", "b") is False
    assert has_raw_tag("<div title='x'><img src=x></div>", "img") is True


def test_script_and_iframe_are_covered_too():
    for tag in ("script", "iframe", "object", "embed"):
        assert has_raw_tag(f'<div title="a &quot;<{tag}>&quot;">t</div>', tag) is False
        assert has_raw_tag(f"<div>{tag and '<'}{tag} src=x>t</div>", tag) is True


def test_escaped_markup_in_text_is_not_a_tag():
    """What a correctly-escaped sink produces: `&lt;img` is text, and `&` is not
    a quote, so the scan must not treat it as one either."""
    html = '<div class="fix-row">&lt;img src=x onerror=alert(1)&gt;</div>'
    assert "&lt;img" in html
    assert has_raw_tag(html, "img") is False


def test_the_scan_removes_quoted_values_and_keeps_everything_else():
    """`markup_outside_attributes` strips quoted spans and nothing else: markup
    structure survives, so `has_raw_tag` cannot be fooled by content it dropped.
    (My first version of this test asserted the input was unchanged for markup
    that plainly contains a quoted value — the helper was right and I was not.)"""
    html = '<a href="/p?q=1">text</a>'
    assert markup_outside_attributes(html) == '<a href=>text</a>'

    html2 = '<a href="/p">text</a><b title="z">y</b>'
    stripped = markup_outside_attributes(html2)
    assert '"/p"' not in stripped and '"z"' not in stripped
    assert "<a href=" in stripped and ">text</a>" in stripped and "<b title=" in stripped


def test_markup_with_no_quotes_is_returned_unchanged():
    html = "<div><span>plain text</span></div>"
    assert markup_outside_attributes(html) == html


def test_empty_and_null_input_are_safe():
    assert has_raw_tag("", "img") is False
    assert has_raw_tag(None, "img") is False
    assert markup_outside_attributes("") == ""


@pytest.mark.parametrize("payload", [PAY_TAG, PAY_ATTR])
def test_both_planted_payloads_are_inert_when_escaped(payload):
    """Both shapes the suite plants, in the position `renderDashboard` puts them
    (an escaped attribute value), must read as inert."""
    escaped = payload.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    html = f'<div class="dash-card" title="Open &quot;{escaped}&quot; on the desk"></div>'
    assert has_raw_tag(html, "img") is False
    assert "<img" not in markup_outside_attributes(html)


# ---------------------------------------------------------------------------
# Why this file is not a browser run
# ---------------------------------------------------------------------------

def test_browser_binaries_are_named_as_the_missing_dependency():
    """Honesty about what was NOT verified.

    `tests/e2e_browser_*.py` are not in pytest's default collection: they need a
    Chromium binary. In this environment the download is blocked (the Playwright
    CDN is not reachable), so the suite was not run end to end. The precision fix
    above is verified; the browser pass is not, and this test exists so that gap
    is recorded in code rather than only in a commit message.
    """
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright not installed — browser legs not runnable here")
    # Even with the module, the binary may be absent; that is the case here.
    from pathlib import Path
    cache = Path.home() / ".cache" / "ms-playwright"
    if not cache.is_dir() or not any(cache.iterdir()):
        pytest.skip("no Chromium binary — browser legs not runnable here")
