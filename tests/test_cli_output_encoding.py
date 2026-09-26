"""CLI output encoding is a contract, not a coincidence (R6-UX-6 round-off).

Every user-facing CLI line is written for a human terminal, and this repo's own
prose is full of characters that a legacy code page cannot encode: the em dash in
`screenplay_studio/cli.py:108` ("Project state saved at '...' — fix the issue and
rerun"), the arrow at `:236`, the em dash in the `resume` help text at `:196`, and
the branch listing in `screenplay_cowriter/cli.py:165`. Nothing in the repo ever
stated what encoding those bytes are supposed to arrive in, so the answer was
"whatever the launching console's code page says" — measured on this machine:

    $ PYTHONIOENCODING=ascii python -m screenplay_studio --help
    ...
      File ".../argparse.py", line 2756, in _print_message
        file.write(message)
    UnicodeEncodeError: 'ascii' codec can't encode character '\u2014' ...

The command that exists to tell you what the commands do dies on its own help
text. Same shape on the writer-facing failure path: the sentence that is supposed
to say "fix the issue and rerun" becomes a traceback, and on a code page that
*can* encode the dash but is not UTF-8 (cp1252 here) the bytes land as `\\x97`, so
anything downstream that decodes the redirect as UTF-8 gets mojibake.

Fixed at the one place all four share and nowhere else: each package's
`__main__.py`, which only runs for `python -m <pkg>`. Not inside `main()`, so a
test that calls `cli.main()` never mutates the pytest process's own streams.

The original narrowing ("Windows mangles the CLI") was wrong: `PYTHONIOENCODING`
does not need to be set by the launcher, and the terminal is not broken. What was
missing was a contract, which is what these two checks pin.
"""

import os
import subprocess
import sys

import pytest

PACKAGES = ["screenplay_parser", "screenplay_analyzer", "screenplay_cowriter",
            "screenplay_studio"]

# A code page that cannot encode any of the characters this product prints.
HOSTILE = "ascii"

# Run a package's real `__main__.py` (so the guard under test executes), with its
# `main()` replaced by a probe that reports what the streams ended up as.
PROBE = (
    "import runpy, sys;"
    "import {pkg}.cli as c;"
    "c.main = lambda: print('ENC=' + sys.stdout.encoding + ',' + sys.stderr.encoding);"
    "runpy.run_module({pkg!r}, run_name='__main__')"
)


def _env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = HOSTILE
    env.pop("PYTEST_CURRENT_TEST", None)
    return env


@pytest.mark.parametrize("pkg", PACKAGES)
def test_launching_a_cli_leaves_utf_8_streams(pkg):
    """The contract: whatever the console claims, the CLI writes UTF-8."""
    proc = subprocess.run([sys.executable, "-u", "-c", PROBE.format(pkg=pkg)],
                          capture_output=True, text=True, encoding="utf-8",
                          env=_env(), timeout=120, cwd=os.getcwd())
    assert proc.returncode == 0, proc.stderr[-500:]
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("ENC=")), None)
    assert line is not None, f"the probe never ran: {proc.stdout!r} {proc.stderr[-300:]}"
    out, err = line[4:].split(",")
    assert (out, err) == ("utf-8", "utf-8"), (
        f"python -m {pkg} left the streams as {out}/{err}; a non-ASCII message "
        f"from that CLI will raise or mojibake on a legacy code page")


def test_the_help_text_that_started_this_reaches_the_terminal():
    """The writer-facing case, end to end, on the shipped command.

    `screenplay_studio/cli.py:196` advertises the `resume` subcommand with an em
    dash, so `--help` is a guaranteed non-ASCII output path with no setup, no
    model and no side effects. Before the guard this returned exit 0 with a
    traceback where the help should have been.
    """
    proc = subprocess.run([sys.executable, "-u", "-m", "screenplay_studio", "--help"],
                          capture_output=True, text=True, encoding="utf-8",
                          env=_env(), timeout=120, cwd=os.getcwd())
    assert "UnicodeEncodeError" not in proc.stderr, proc.stderr[-500:]
    assert "—" in proc.stdout, (
        f"--help never reached the terminal: rc={proc.returncode} "
        f"out={proc.stdout[:200]!r} err={proc.stderr[:300]!r}")
    assert proc.returncode == 0


def test_the_desk_itself_starts_on_such_a_console():
    """The same defect on the surface the writer actually uses, found by measuring.

    This was not in the round's findings — the audit's line was about the CLIs.
    `webapp_server` prints at IMPORT time (the startup demo-fallback notice at
    `:4270`), so on an ASCII stream the module raises before argparse ever runs:
    `python -m screenplay_studio.webapp_server --help` printed a traceback ending
    in `UnicodeEncodeError: ... position 50` and the desk never started. Hence
    the guard there is at the top of the module, not in a `__main__` block.
    """
    proc = subprocess.run(
        [sys.executable, "-u", "-m", "screenplay_studio.webapp_server", "--help"],
        capture_output=True, text=True, encoding="utf-8",
        env=_env(), timeout=120, cwd=os.getcwd())
    assert "UnicodeEncodeError" not in proc.stderr, proc.stderr[-600:]
    assert "usage" in proc.stdout.lower(), (
        f"the webapp never printed its usage: rc={proc.returncode} "
        f"out={proc.stdout[:200]!r} err={proc.stderr[:300]!r}")
