"""Gap 56 — the advertised opt-out was ignored by the import path.

`SCREENPLAY_STUDIO_DEMO_MODEL=0` was read through `_env_flag`, which collapses
the variable to a bool. That made "off" and "unset" indistinguishable, so the
startup fallback could not tell a writer who had refused the demo from one who
never mentioned it. Measured in a fresh process with the variable set to 0 and
no reachable server: the startup printed

    "set SCREENPLAY_STUDIO_DEMO_MODEL=0 to disable this fallback."
    "DEMO MODEL active (in-process) — no real llama-server needed."

on consecutive lines, and `_DEMO_MODEL_ACTIVE` was True. The normal entry point
behaved differently because `_undo_demo_fallback` clears the flag the re-check
depends on, so `flask run` and `main()` disagreed about the same configuration.

The tests below drive the decision in fresh subprocesses, because the code under
test runs at IMPORT time.
"""

import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PROBE = (
    "import screenplay_studio.webapp_server as ws;"
    "print('ACTIVE=', ws._DEMO_MODEL_ACTIVE);"
    "print('SERVER=', ws.CONFIG['server_url'])"
)


def _import(env_extra):
    """Import the server in a fresh process with a dead server and given env."""
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)          # not our pytest, their boot
    env["SCREENPLAY_STUDIO_DEMO_MODEL"] = ""
    env.update(env_extra)
    return subprocess.run([sys.executable, "-c", _PROBE], capture_output=True,
                          text=True, env=env, cwd=REPO, timeout=180)


def _active(p):
    for line in p.stdout.splitlines():
        if line.startswith("ACTIVE="):
            return line.split("=", 1)[1].strip() == "True"
    raise AssertionError(f"probe produced no state; stdout={p.stdout!r} stderr={p.stderr[-800:]!r}")


# ---------- the filed reproduction ----------

def test_opt_out_is_honoured_at_import():
    """The filed case: variable 0, server dead, demo must NOT start."""
    p = _import({"SCREENPLAY_STUDIO_DEMO_MODEL": "0"})
    assert _active(p) is False, (
        "the opt-out was ignored at import — this is the reported defect; "
        f"stdout={p.stdout!r}")


def test_opt_out_does_not_announce_a_demo_it_then_starts():
    """Self-contradiction is the tell. The message advertising the opt-out and
    the demo banner must never both appear."""
    p = _import({"SCREENPLAY_STUDIO_DEMO_MODEL": "0"})
    assert "DEMO MODEL active" not in p.stdout
    assert "DISABLED" in p.stdout, "the desk must say why it has no model"


def test_opt_out_states_the_unavailable_consequence():
    """'No model' is a state the operator has to be told about, not inferred."""
    p = _import({"SCREENPLAY_STUDIO_DEMO_MODEL": "0"})
    out = p.stdout.lower()
    assert "unreachable" in out
    assert "fail" in out, "the operator must know analyses will not run"


@pytest.mark.parametrize("value", ["0", "false", "off", "no", "FALSE", " 0 "])
def test_every_spelling_of_off_is_an_opt_out(value):
    p = _import({"SCREENPLAY_STUDIO_DEMO_MODEL": value})
    assert _active(p) is False, f"{value!r} did not opt out; stdout={p.stdout!r}"


# ---------- the fallback still works when nobody opted out ----------

def test_unset_still_falls_back():
    """The conveniences must survive: this is what most launches do."""
    p = _import({})
    assert _active(p) is True, f"the fallback should still run; stdout={p.stdout!r}"
    assert "DEMO MODEL active" in p.stdout


def test_explicit_on_is_explicit_demo_not_fallback():
    p = _import({"SCREENPLAY_STUDIO_DEMO_MODEL": "1"})
    assert _active(p) is True


# ---------- the three states, at the unit level ----------

def test_the_setting_reads_three_states(monkeypatch):
    from screenplay_studio import webapp_server as ws
    monkeypatch.delenv("SCREENPLAY_STUDIO_DEMO_MODEL", raising=False)
    assert ws._demo_setting() == "unset"
    monkeypatch.setenv("SCREENPLAY_STUDIO_DEMO_MODEL", "0")
    assert ws._demo_setting() == "off"
    monkeypatch.setenv("SCREENPLAY_STUDIO_DEMO_MODEL", "1")
    assert ws._demo_setting() == "on"


def test_off_and_unset_are_distinguishable():
    """The whole defect in one assertion: `_env_flag` cannot express this."""
    from screenplay_studio import webapp_server as ws
    import os as _os
    saved = _os.environ.get("SCREENPLAY_STUDIO_DEMO_MODEL")
    try:
        _os.environ["SCREENPLAY_STUDIO_DEMO_MODEL"] = "0"
        assert ws._env_flag("SCREENPLAY_STUDIO_DEMO_MODEL") is False
        assert ws._demo_setting() == "off"
        del _os.environ["SCREENPLAY_STUDIO_DEMO_MODEL"]
        assert ws._env_flag("SCREENPLAY_STUDIO_DEMO_MODEL") is False   # same bool!
        assert ws._demo_setting() == "unset"                            # different state
    finally:
        if saved is None:
            _os.environ.pop("SCREENPLAY_STUDIO_DEMO_MODEL", None)
        else:
            _os.environ["SCREENPLAY_STUDIO_DEMO_MODEL"] = saved


def test_the_recheck_undoes_a_demo_when_the_writer_opted_out(monkeypatch):
    """main()'s re-check must also enforce the opt-out — the second half of the
    filed report, where the two startup paths disagreed."""
    from screenplay_studio import webapp_server as ws
    saved = (ws._DEMO_MODEL_ACTIVE, ws._DEMO_URL, ws._DEMO_FALLBACK_AUTO)
    saved_url = ws.CONFIG["server_url"]
    try:
        ws._use_demo_model(auto=True)                     # what import did
        assert ws._DEMO_MODEL_ACTIVE is True
        monkeypatch.setenv("SCREENPLAY_STUDIO_DEMO_MODEL", "0")
        monkeypatch.setattr(ws, "_server_reachable", lambda url: False)
        ws._recheck_fallback_after_args()
        assert ws._DEMO_MODEL_ACTIVE is False, "the opt-out must win over a leftover demo"
    finally:
        (ws._DEMO_MODEL_ACTIVE, ws._DEMO_URL, ws._DEMO_FALLBACK_AUTO) = saved
        ws.CONFIG["server_url"] = saved_url


def test_one_env_reader_and_one_pytest_check():
    """Source pin: the two startup paths must not re-implement the rule.

    The defect was two paths deciding the same question with different code.
    """
    import inspect
    from screenplay_studio import webapp_server as ws
    src = inspect.getsource(ws)
    assert src.count("def _demo_setting") == 1
    assert src.count("def _running_under_pytest") == 1
    # the raw env var may only be read inside _demo_setting
    assert src.count('os.environ.get("SCREENPLAY_STUDIO_DEMO_MODEL"') == 1
    assert src.count('_env_flag("SCREENPLAY_STUDIO_DEMO_MODEL")') == 0
