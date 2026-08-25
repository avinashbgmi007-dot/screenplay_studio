"""Shared scaffolding for the tests/e2e_browser_*.py Playwright suites.

Every browser suite used to hand-roll the same three things: PASS/FAIL
bookkeeping, a chromium page wired with pageerror/dialog traps, and (in one
script only) its own studio server. This module owns all three so a suite
reads as pure scenario.

Studio connection modes:
  * E2E_BASE set in the env -> talk to that ALREADY-RUNNING studio (the
    shared-sweep convention; nothing is spawned).
  * otherwise (default)     -> start_studio() boots a PRIVATE server on a
    free port with a throwaway projects dir and the built-in demo craft
    model — no llama-server required.

Run any suite with:   python tests/e2e_browser_<name>.py
Needs: pip install playwright && python -m playwright install chromium
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- check bookkeeping -----------------------------------------------

class Checks:
    """Collect named checks; finish() prints the summary and exits nonzero
    on failure. fail_fast=True bails on the first failed check (the old
    e2e_browser_ui_batch contract)."""

    def __init__(self, fail_fast=False):
        self.passed = []
        self.failed = []
        self.fail_fast = fail_fast

    def ok(self, name, cond=True, detail=""):
        cond = bool(cond)
        (self.passed if cond else self.failed).append((name, detail))
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"  [{detail}]" if not cond and detail else ""))
        if not cond and self.fail_fast:
            print(f"\n=== failing fast after {len(self.passed)} passed ===")
            sys.exit(1)

    # friendlier alias used by most suites
    check = ok

    def finish(self):
        print(f"\n=== {len(self.passed)} passed, {len(self.failed)} failed ===")
        for name, detail in self.failed:
            print(f"FAILED: {name}: {detail}")
        sys.exit(1 if self.failed else 0)


# ---------- studio boot ------------------------------------------------------

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Studio:
    """A booted webapp_server subprocess. Use as a context manager."""

    def __init__(self, base_url, proc, projects_dir, log_path):
        self.base_url = base_url
        self._proc = proc
        self.projects_dir = projects_dir
        self.log_path = log_path
        self._log_file = None

    def get_json(self, path):
        """GET <base><path> and parse the JSON body."""
        with urllib.request.urlopen(self.base_url + path, timeout=15) as r:
            return json.loads(r.read().decode())

    def tail_log(self, n=2000):
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()[-n:]
        except OSError:
            return ""

    def close(self):
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
        tmp = getattr(self, "_tmp", None)
        if tmp is not None:
            try:
                tmp.cleanup()
            except OSError:
                pass  # best-effort; a leaked temp dir beats a broken run

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def start_studio(projects_dir=None, env_extra=None, timeout=60, server_url=None):
    """Boot the real webapp server with the in-process demo craft model.

    projects_dir: existing dir to serve from (seed it BEFORE calling), or
                  None for a throwaway temp dir removed on close().
    server_url:   where the "writer's real llama-server" supposedly lives
                  (drives the status-strip switch-back flow). Passed via
                  --server with the demo ENV TRIGGER OFF, so main() applies
                  it BEFORE demo activation pins real_server_url.
    Returns a Studio; call .close() (or use `with`) or the child lingers.
    """
    tmp = None
    if projects_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="studio_e2e_")
        # the SERVED dir is nested one level down so the child's log file can
        # sit beside it — never inside it, where suites would see it as a
        # (broken) shelf entry
        projects_dir = os.path.join(tmp.name, "projects")
        os.makedirs(projects_dir)
    port = free_port()
    env = dict(os.environ)
    env.update(env_extra or {})
    # env + flag parity: the env var activates the demo at import time (and
    # skips the "is :8080 up?" probe), the flag keeps it explicit.
    env["SCREENPLAY_STUDIO_DEMO_MODEL"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [sys.executable, "-m", "screenplay_studio.webapp_server",
           "--port", str(port), "--projects-dir", projects_dir, "--demo-model"]
    if server_url:
        # Drive --server through main() instead: both import-time demo paths
        # (env trigger and the :8080-unreachable fallback) would lock
        # real_server_url to the :8080 DEFAULT before args are parsed. With
        # both suppressed, main() sets server_url first and demo activation
        # then records it as the writer's real server. PYTEST_CURRENT_TEST
        # reuses the app's own deterministic-startup escape hatch.
        env.pop("SCREENPLAY_STUDIO_DEMO_MODEL", None)
        env.setdefault("PYTEST_CURRENT_TEST", "e2e_browser_common boot")
        cmd += ["--server", server_url]
    # Child output MUST go to a drained sink, not an unread PIPE: werkzeug's
    # per-request access log silently fills the OS pipe buffer mid-suite and
    # wedges every server thread on its next log write.
    log_path = os.path.join(os.path.dirname(os.path.abspath(projects_dir)),
                            "_studio_server.log")
    log_file = open(log_path, "ab")
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, env=env,
                            stdout=log_file, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    studio = Studio(base, proc, projects_dir, log_path)
    studio._log_file = log_file
    studio._tmp = tmp
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        if proc.poll() is not None:
            out = studio.tail_log()
            studio.close()
            if tmp:
                tmp.cleanup()
            raise RuntimeError(f"studio exited early ({proc.returncode}):\n{out}")
        try:
            cfg = json.loads(urllib.request.urlopen(base + "/api/config",
                                                    timeout=3).read().decode())
            if cfg.get("demo_model"):
                return studio
            last_err = "server is up but demo_model is not active"
        except Exception as e:
            last_err = str(e)
        time.sleep(0.4)
    studio.close()
    if tmp:
        tmp.cleanup()
    raise RuntimeError(f"studio never became ready at {base}: {last_err}")


class _ManagedStudio:
    """`with open_studio() as base:` — E2E_BASE wins, else boot privately."""

    def __init__(self):
        self.studio = None
        self._tmp = None

    def __enter__(self):
        external = os.environ.get("E2E_BASE")
        if external:
            return external.rstrip("/")
        self.studio = start_studio()
        return self.studio.base_url

    def __exit__(self, *exc):
        if self.studio:
            self.studio.close()


def open_studio():
    return _ManagedStudio()


# ---------- browser + page ----------------------------------------------------

def launch(pw, launch_args=None, **context_kwargs):
    """Headless chromium + a 1440x900 page wired with the standard traps.

    Returns (browser, page, errors) where errors collects uncaught JS
    exceptions; dialogs are auto-accepted. Extra kwargs go to new_context()
    (e.g. permissions=["microphone"]).
    """
    browser = pw.chromium.launch(args=launch_args or [])
    page = browser.new_context(viewport={"width": 1440, "height": 900},
                               **context_kwargs).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    return browser, page, errors


def assert_no_js_errors(checks, errors, name="no JS page errors"):
    checks.ok(name, len(errors) == 0, "; ".join(errors[:3]))


# ---------- chat helpers -------------------------------------------------------

def last_reply(page):
    """Text of the most recent finished assistant bubble."""
    return page.locator(".msg.assistant .msg-bubble").last.inner_text().strip()


def send_chat(page, text):
    """Type into the Sameer composer and hit Send."""
    box = page.locator("#input")
    box.fill(text)
    page.get_by_role("button", name="Send").click()
