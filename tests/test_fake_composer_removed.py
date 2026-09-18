"""The fake Sameer composer is gone, and the craft questions reach the real one (H3).

The review's H3: *"A fake Sameer chat composer silently discards user input in a
product whose stated law is 'the UI never pretends'."* The finding was accurate, and
the reality was worse than the description.

The off-canvas `#sameer-panel` was not merely fake — it was **the destination of
every craft question in the command palette**. All seven of them ("Why doesn't my
dialogue land?", "Is my Act II sagging?", …) called `openSameerWith()`, which filled
`#sameer-ta`; its Send button then appended the text to its own thread and made **no
API call**. So the product's headline craft entry point discarded the writer's
question in silence, under a heading that said "Sameer".

The panel also shipped three hardcoded "messages" — prose about a stairwell and a
character named Mara, on whatever script the writer had actually opened.

Resolution: **deleted, not wired.** The Co-write room already has a real composer that
sends, so wiring a second one would duplicate it. `openSameerWith()` now pre-fills
that composer. Deleting a surface that lies is the honest fix; the UI never pretends.
"""

import io
import os
import re

import pytest

import screenplay_studio.webapp_server as ws


def _read(name):
    path = ws.__file__.replace("webapp_server.py", os.path.join("webapp", name))
    return io.open(path, encoding="utf-8").read()


@pytest.fixture(scope="module")
def html():
    return _read("index.html")


@pytest.fixture(scope="module")
def js():
    return _read("app.js")


@pytest.fixture(scope="module")
def css():
    return _read("style.css")


# --------------------------------------------------------------------------
# the fake surface is gone
# --------------------------------------------------------------------------

class TestTheFakeSurfaceIsGone:
    def test_the_panel_is_removed(self, html):
        assert 'id="sameer-panel"' not in html

    def test_its_fake_transcript_is_removed(self, html):
        """Hardcoded prose about a stairwell and a character named Mara, shown
        regardless of which script the writer opened."""
        assert "sp-thread" not in html
        assert "The stairwell scene sings" not in html
        assert "Mara exit line" not in html

    def test_its_echo_only_composer_is_removed(self, html):
        assert 'id="sameer-ta"' not in html
        assert 'id="sameer-send"' not in html
        assert "Send to Sameer" not in html

    def test_the_toggle_is_removed(self, js):
        assert "toggleSameerPanel" not in js
        assert "sameerPanelOpen" not in js

    def test_no_code_still_reaches_for_the_deleted_elements(self, js):
        """A stale `closest("#sameer-ta")` survived the HTML deletion and would
        have thrown on every selection-popup hit-test. Comments are stripped
        first: the note explaining the removal names the old ids on purpose."""
        code = "\n".join(
            line.split("//")[0] for line in js.splitlines()
        )
        for stale in ("#sameer-ta", "#sameer-send", "#sameer-panel", "#sameer-close",
                      "#sameer-thread"):
            assert stale not in code, f"{stale} is still referenced by live code"

    def test_the_style_is_removed(self, css):
        assert ".sameer-panel" not in css
        assert ".sp-composer" not in css
        assert ".sp-msg" not in css

    def test_a_note_explains_why_it_is_gone(self, html):
        """So the next reader does not re-add it as a 'missing' surface."""
        assert "H3" in html
        assert "no API call" in html.lower() or "NO API call" in html


# --------------------------------------------------------------------------
# the craft questions reach a composer that sends
# --------------------------------------------------------------------------

class TestTheCraftQuestionsReachTheRealComposer:
    def test_open_sameer_with_targets_the_real_composer(self, js):
        body = js[js.index("function openSameerWith("):]
        body = body[:body.index("\n}\n") + 3]
        assert '$("#input")' in body, "the craft question must land in the sending composer"
        assert "sameer-ta" not in body

    def test_it_still_opens_the_cowrite_room(self, js):
        body = js[js.index("function openSameerWith("):]
        body = body[:body.index("\n}\n") + 3]
        assert "openCowriteRoom()" in body

    def test_all_seven_craft_prompts_are_still_wired(self, js):
        """The palette entries must not have been dropped along with the panel."""
        assert js.count("openSameerWith(") >= 8  # 1 definition + 7 entries

    def test_the_real_composer_still_exists_and_sends(self, html, js):
        """The whole justification for deleting rather than wiring: the room
        already has a composer that reaches the API."""
        assert 'id="input"' in html
        assert 'id="send-btn"' in html
        assert 'id="composer"' in html
        assert "/chat/sessions/" in js and "messages/stream" in js


# --------------------------------------------------------------------------
# the harness note is no longer stale
# --------------------------------------------------------------------------

class TestTheHarnessNote:
    def test_it_no_longer_describes_a_panel_that_exists(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "e2e_browser_common.py")
        src = io.open(path, encoding="utf-8").read()
        assert "off-canvas #sameer-send panel button carries the" not in src, (
            "the harness still explains a workaround for a deleted element"
        )
        assert "exact=True still matters" in src
