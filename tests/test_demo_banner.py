"""A demo-model report says so, on the report (Wave 2 / §5 item 8, §7 item 10).

When no llama-server is reachable the studio falls back to a rule-based craft
model. That is an honest workflow demo — but until now the ONLY thing that said so
was an amber dot and a hover card on the desk, while the report itself read like a
professional review and the partner card said "Sameer — AI writing partner".

The product's stated law is that the UI never pretends. So the disclosure has to
live on the surfaces a writer actually reads, and on the artifact that leaves the
app: an exported HTML report outlives the status strip that would have explained it.
"""

import re

import pytest

import screenplay_studio.webapp_server as ws


MD = "# Report\n\nSome findings.\n"


@pytest.fixture
def demo(monkeypatch):
    """Drive the module's demo flag without booting a demo server."""
    def _set(active):
        monkeypatch.setattr(ws, "_DEMO_MODEL_ACTIVE", active)
    return _set


# --------------------------------------------------------------------------
# the exported report carries the disclosure
# --------------------------------------------------------------------------

class TestExportedReportBanner:
    # The class NAME appears in the <style> block whether or not the banner
    # renders, so the assertions below key on the banner's own text. (Keying on
    # "demo-banner" made two of these tests pass/fail for the wrong reason.)
    MARK = "Built-in stand-in model."

    def test_a_real_model_report_carries_no_banner(self, demo):
        """A permanent banner would train the writer to ignore it."""
        demo(False)
        assert ws._report_banner() == ""
        assert self.MARK not in ws._md_to_html(MD, ws._report_banner())

    def test_a_demo_report_carries_the_banner(self, demo):
        demo(True)
        assert ws._report_banner() == ws.DEMO_REPORT_BANNER

    def test_the_banner_lands_at_the_top_of_the_exported_document(self, demo):
        demo(True)
        html = ws._md_to_html(MD, ws._report_banner())
        body_at = html.index("<body>")
        banner_at = html.index(self.MARK)
        content_at = html.index("<h1>")
        assert body_at < banner_at < content_at, (
            "the disclosure must be read before the findings, not after them"
        )

    def test_the_banner_says_what_it_is_and_how_to_fix_it(self, demo):
        """Naming the problem without naming the remedy is just a disclaimer."""
        demo(True)
        banner = ws.DEMO_REPORT_BANNER
        assert "stand-in" in banner.lower()
        assert "llama-server" in banner, "the writer needs the way out"
        assert "canned" in banner.lower(), "say plainly that the findings are not real"

    def test_the_export_styles_the_banner(self, demo):
        demo(True)
        html = ws._md_to_html(MD, ws._report_banner())
        assert ".demo-banner" in html, "an unstyled banner would render as a bare div"

    def test_an_empty_banner_leaves_the_document_unchanged(self):
        """The default path (real model) must be byte-identical to before."""
        assert ws._md_to_html(MD) == ws._md_to_html(MD, "")
        assert "<body><h1>" in ws._md_to_html(MD)

    def test_the_export_route_uses_the_helper(self):
        """Guards against the route drifting back to its own inline decision."""
        src = open(ws.__file__, encoding="utf-8").read()
        assert "_md_to_html(md, _report_banner())" in src


# --------------------------------------------------------------------------
# the banner obeys the colour discipline the phase-12 work established
# --------------------------------------------------------------------------

class TestBannerColourDiscipline:
    """The demo banner is an amber-family surface, which is exactly where the
    phase-12 pass found three hardcoded ambers — including a dawn-theme rule that
    had hardcoded the NIGHT amber and so overrode its own token. Pin the token."""

    def _rule(self):
        css = open(ws.__file__.replace("webapp_server.py", "webapp/style.css"),
                   encoding="utf-8").read()
        match = re.search(r"\.demo-banner\s*\{(.*?)\}", css, re.S)
        assert match, "the .demo-banner rule is missing"
        return match.group(1)

    def test_it_uses_the_severity_token(self):
        assert "var(--sev-mid)" in self._rule()

    def test_it_hardcodes_no_amber(self):
        rule = self._rule()
        assert "232, 162, 79" not in rule, "the night amber literal is back"
        assert "#e8a24f" not in rule.lower()
        assert "#8a5a14" not in rule.lower(), "the dawn amber literal is back"

    def test_it_uses_type_and_space_tokens(self):
        rule = self._rule()
        assert "var(--fs-" in rule and "var(--sp-" in rule


# --------------------------------------------------------------------------
# the in-app surfaces
# --------------------------------------------------------------------------

class TestInAppDisclosure:
    """The two in-app surfaces are HTML/JS, so these assert the wiring exists and
    that the demo check is not duplicated by hand — the browser suite covers the
    rendered result."""

    def _app_js(self):
        return open(ws.__file__.replace("webapp_server.py", "webapp/app.js"),
                    encoding="utf-8").read()

    def _index_html(self):
        return open(ws.__file__.replace("webapp_server.py", "webapp/index.html"),
                    encoding="utf-8").read()

    def test_the_partner_card_is_labelled_through_one_helper(self):
        js = self._app_js()
        assert "function partnerLabel(" in js
        # every hardcoded partner name must go through it, or the two call sites
        # drift and one of them starts pretending again
        hardcoded = re.findall(r'\.partner-name"\)\.textContent = ("[^"]*")', js)
        assert hardcoded == [], f"a partner name bypasses partnerLabel: {hardcoded}"
        assert js.count("partnerLabel(") >= 3  # 1 definition + 2 call sites

    def test_the_report_banner_exists_and_is_off_by_default(self):
        html = self._index_html()
        assert "data-demo-banner" in html
        assert re.search(r'data-demo-banner[^>]*hidden', html), (
            "the banner must start hidden — it is revealed by config, not by layout"
        )

    def test_the_banner_sits_outside_the_flex_header(self):
        """`.feedback-header` is a flex row; a banner inside it would become a
        flex item and push the toolbar sideways."""
        html = self._index_html()
        header_at = html.index('class="feedback-header"')
        banner_at = html.index('data-demo-banner')
        assert banner_at < header_at

    def test_the_project_report_surface_carries_a_banner_too(self):
        """A PROJECT renders its report in the dock; #feedback-panel is the
        legacy/idea-room surface and is display:none for a project. Verified in a
        browser: with only the panel banner, a demo project showed no disclosure
        at all — the panel was never visible."""
        html = self._index_html()
        dock_at = html.index('id="context-dock"')
        assert html.count("data-demo-banner") >= 2, (
            "one banner for the idea room, one for the project's dock"
        )
        assert html.index("data-demo-banner", dock_at) > dock_at, (
            "the dock's banner must live inside the dock"
        )

    def test_the_dock_banner_is_outside_the_rendered_lens(self):
        """renderDockEvidence() replaces the lens contents, so a banner inside
        #dock-lens-evidence would be wiped on the first render."""
        html = self._index_html()
        banner_at = html.index("data-demo-banner", html.index('id="context-dock"'))
        lens_at = html.index('id="dock-lens-evidence"')
        assert banner_at < lens_at, "the dock banner must sit outside the lens body"

    def test_the_disclosure_is_applied_when_config_loads(self):
        js = self._app_js()
        assert "function applyDemoDisclosure(" in js
        assert 'querySelectorAll("[data-demo-banner]")' in js, (
            "every banner surface must be toggled from one place"
        )
        # both the initial load and a settings save can change demo state
        assert js.count("applyDemoDisclosure()") >= 3  # 1 definition + 2 call sites
