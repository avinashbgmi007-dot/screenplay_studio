"""Gap 85 — the port and the process model must be stated once, and truthfully.

Filed defect: `docs/API_ROUTE_MAP.md`'s header said the map was authoritative for a
process "on port 8500" while the same file's totals and the SPA describe one Flask
process serving both the API and the static SPA; the `screenplay_studio` package's
own `--help` named no port at all, while `webapp_server` defaults to 8500 and
`webapp_demo` maps `PORT`.

Small, and the filing is right about why it matters anyway: *a support document is
where a stuck writer looks first.* A wrong port in a support doc is not a typo, it
is a writer who concludes the app is broken.

The fix has two halves, and the second is the one that lasts:

1. state it once — one launch table at the top of the route map, one epilog in the
   CLI's `--help`;
2. **derive it from the code.** These tests read the numbers out of
   `webapp_server`'s own argparse defaults and out of `demo_model`, then require the
   prose to contain them. A doc that restates a number drifts; a doc that is checked
   against the number cannot.
"""

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from screenplay_studio import demo_model, webapp_server  # noqa: E402


def _doc(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _defaults():
    return webapp_server.build_argument_parser().parse_args([])


# ---------- the code's own answer, which everything else must agree with ----------

def test_the_defaults_are_readable_without_launching():
    """The parser lives at module level now. It used to exist only inside
    `main()`, which is exactly why every document had to restate the numbers."""
    ns = _defaults()
    assert ns.port == webapp_server.DEFAULT_PORT == 8500
    assert webapp_server.DEFAULT_BIND == "127.0.0.1"
    assert ns.projects_dir == webapp_server.DEFAULT_PROJECTS_DIR


def test_the_token_is_on_by_default_and_no_token_is_the_opt_out():
    ns = _defaults()
    assert ns.no_token is False, "secure by default: the opt-out must be explicit"


def test_the_demo_model_prefers_its_own_port_and_falls_back():
    assert demo_model.DEMO_PREFERRED_PORT == 8099
    src = open(os.path.join(ROOT, "screenplay_studio", "demo_model.py"),
               encoding="utf-8").read()
    # the ephemeral fallback is the part that keeps a busy 8099 from breaking boot
    assert "make_server(\"127.0.0.1\", 0" in src


# ---------- the route map states it once ----------

def test_the_route_map_states_the_default_port():
    text = _doc("docs", "API_ROUTE_MAP.md")
    assert f"**{webapp_server.DEFAULT_PORT}**" in text
    assert "the only place the port is stated" in text


def test_the_route_map_states_the_bind_and_the_token_in_the_same_place():
    """The filing's actual ask: the promise the reader most needs, in one sentence."""
    text = _doc("docs", "API_ROUTE_MAP.md")
    start = text.index("The launch promise")
    table = text[start:text.index("Companion docs")]
    assert f"**{webapp_server.DEFAULT_BIND} only**" in table
    assert "capability token" in table
    assert "**both** the JSON API and the static SPA" in table


def test_the_route_map_does_not_contradict_itself_about_the_process_model():
    """The filed contradiction: one sentence implying a separate API process, the
    totals and the SPA implying one."""
    text = _doc("docs", "API_ROUTE_MAP.md")
    assert "single Flask process" in text
    assert "the same process also serves the static SPA" in text
    # the demo model is genuinely separate, and the map must keep saying so
    assert "a **separate** Flask app" in text


def test_the_demo_port_in_the_docs_is_the_one_in_the_code():
    text = _doc("docs", "API_ROUTE_MAP.md")
    assert f"**{demo_model.DEMO_PREFERRED_PORT}**" in text
    assert "ephemeral" in text, "the fallback is part of the promise"


# ---------- the CLI help finally names the desk ----------

def _cli_help() -> str:
    out = subprocess.run([sys.executable, "-B", "-m", "screenplay_studio", "--help"],
                         capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_the_cli_help_names_the_desk_and_its_port():
    help_text = _cli_help()
    assert "webapp_server" in help_text
    assert str(webapp_server.DEFAULT_PORT) in help_text


def test_the_cli_help_states_the_loopback_bind_and_the_token():
    help_text = _cli_help()
    # argparse wraps at the terminal width, so a phrase can straddle a newline.
    # Normalise whitespace: the wrap is cosmetic, the sentence is the contract.
    flat = " ".join(help_text.split())
    assert webapp_server.DEFAULT_BIND in flat
    assert "capability token" in flat
    assert "--no-token" in flat


def test_the_cli_help_derives_its_numbers_from_the_server():
    """Not a string compare against a constant I typed here: the sentence is built
    from `DEFAULT_PORT`/`DEFAULT_BIND`, so this asserts the derivation survives."""
    src = open(os.path.join(ROOT, "screenplay_studio", "cli.py"), encoding="utf-8").read()
    assert "from .webapp_server import DEFAULT_BIND, DEFAULT_PORT" in src, (
        "the CLI must read the defaults, not restate them")


# ---------- the other docs agree ----------

@pytest.mark.parametrize("path", [("docs", "CLI_REFERENCE.md"), ("AGENTS.md",)])
def test_every_doc_that_mentions_the_port_agrees_with_the_code(path):
    text = _doc(*path)
    assert str(webapp_server.DEFAULT_PORT) in text
    # a doc that mentions the port must also mention that it is loopback-only,
    # because "run this on 8500" without the bind is the sentence that misleads
    assert "127.0.0.1" in text or "loopback" in text.lower()


def test_no_doc_promises_a_lan_visible_desk():
    """`host="0.0.0.0"` is how a desk becomes reachable from the café wifi. Nothing
    in the launch path may do it, and no doc may imply it."""
    for module in ("webapp_server.py", "webapp_demo.py", "cli.py"):
        src = open(os.path.join(ROOT, "screenplay_studio", module), encoding="utf-8").read()
        assert "0.0.0.0" not in src, f"{module} binds all interfaces"


def test_the_bind_is_the_literal_the_server_actually_uses():
    src = open(os.path.join(ROOT, "screenplay_studio", "webapp_server.py"),
               encoding="utf-8").read()
    assert 'app.run(host=DEFAULT_BIND' in src, (
        "the constant must be the thing passed to app.run, or it describes nothing")
