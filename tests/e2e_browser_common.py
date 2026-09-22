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

# Windows consoles default to cp1252, so any check detail carrying a non-Latin-1
# glyph (✕ ≤ ≥ — the suites' own wording) crashes the PRINT, not the check:
# phase8/9/11 passed every assertion and still exited 1 on a UnicodeEncodeError.
# Make stdout/stderr UTF-8 once, here, for every suite that imports this module.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # non-reconfigurable stream (pytest capture)
        pass

# ---------------------------------------------------------------------------
# Loopback must never go through a proxy — and `requests` disagrees with `curl`
# about that.
#
# curl bypasses localhost automatically. `requests` does NOT: it honours
# HTTP_PROXY/HTTPS_PROXY for every host unless `no_proxy` says otherwise. In a
# sandboxed or instrumented environment those variables point at a local proxy,
# so every call this harness makes to the studio it just booted on 127.0.0.1
# goes out through it — and when that proxy refuses, the failure reads as
# "Max retries exceeded … ProxyError", which looks exactly like a product fault.
# Measured: the full gun_pen audit failed `pass2: force re-analysis accepted`
# with a ProxyError against 127.0.0.1:8517, a studio that was answering every
# other request fine.
#
# Every studio here is on loopback by construction, so bypass the proxy for
# loopback unconditionally. Set at import, before any suite makes a request.
# ---------------------------------------------------------------------------
for _var in ("NO_PROXY", "no_proxy"):
    _hosts = [h for h in os.environ.get(_var, "").split(",") if h.strip()]
    for _h in ("127.0.0.1", "localhost", "::1"):
        if _h not in _hosts:
            _hosts.append(_h)
    os.environ[_var] = ",".join(_hosts)

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


def seen_visible(target, selector=None, timeout=8000):
    """Bounded poll: True if the target becomes visible within `timeout`.

    Never raises. This is the T1c shape. A throwing `wait_for_selector` followed
    by `check(name, True)` does enforce the guarantee — but it reports a failure
    as a CRASH, and a crash aborts the run and masks every later check (pass 9:
    that is how four of six preview worlds hid behind one). Poll, then assert:

        ok = seen_visible(page, "#idea-content")
        check("idea: blank page opens", ok and blank, f"visible={ok} blank={blank}")

    `target` is a Page (pass `selector`) or a Locator — the latter for a
    `.last` / `.first` target, which a bare selector cannot express:

        ok = seen_visible(page.locator(".msg.user").last, timeout=10000)
    """
    try:
        if selector is None:
            target.wait_for(state="visible", timeout=timeout)
        else:
            target.wait_for_selector(selector, state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def clicked(target, selector=None, timeout=4000):
    """Bounded click: True if the click landed, False if it never could.

    Never raises. Same reasoning as `seen_visible`: once a precondition has
    failed, an unguarded `locator(...).click()` waits out its timeout and RAISES
    — aborting the run and masking every later check (pass 9). A click that could
    not happen is a fact to assert, not a crash.

        if not clicked(page, "#rewrite-generate"):
            check("inline edit: the rewrite section was exercised", False, "...")
    """
    try:
        if selector is None:
            target.click(timeout=timeout)
        else:
            target.locator(selector).click(timeout=timeout)
        return True
    except Exception:
        return False


def note(label, value=""):
    """Print a diagnostic that is deliberately NOT a check.

    `check(name, True, detail)` is worse than a no-op: it inflates the passed
    count, and `Checks.ok` prints `detail` only on FAILURE — so on a green run
    the payload is invisible *and* nothing was asserted. Diagnostics belong in
    stdout, where they are actually readable, not in the count.
    """
    print(f"  NOTE  {label}" + (f"  [{value}]" if value else ""))


# ---------- evidence-dock helpers (P1.6 collapsible sections) ----------------
# P1.6 put every section of the Evidence ledger behind a real header button with
# its body collapsed by DEFAULT, and a closed body is genuinely hidden: not
# painted, not in the tab order, not in the accessibility tree, and not part of
# `innerText` (Playwright's inner_text()/all_inner_texts() return "" for a
# hidden subtree; text_content() still sees it). A suite that wants to CLICK or
# READ inside a section therefore does what the writer does first — open it.
# Both helpers are bounded and never raise, like clicked()/seen_visible().

def open_dock_section(page, key, timeout=4000):
    """Open the Evidence dock's section `key`; True if it ends up open.

    No-op (True) when the section is already open; False when there is no such
    section or the header could not be clicked.
    """
    sec = page.locator(f'.dock-lens[data-lens="evidence"] .dock-section[data-key="{key}"]')
    if not sec.count():
        return False
    if sec.first.get_attribute("data-open") == "true":
        return True
    if not clicked(sec.first.locator(".dock-section-head"), timeout=timeout):
        return False
    return sec.first.get_attribute("data-open") == "true"


def open_dock_section_holding(page, inner_selector, timeout=4000):
    """Open every collapsed section that holds a match for `inner_selector`.

    Callers ask by CONTENT, not by key, because the same card renders in
    different sections depending on the scene and the ONE filter (this-scene >
    fix queue > by category). Returns how many sections it opened.
    """
    idx = page.evaluate(
        """(sel) => {
             const lens = document.querySelector('.dock-lens[data-lens="evidence"]');
             if (!lens) return [];
             return [...lens.querySelectorAll('.dock-section')]
               .map((s, i) => ({ i, has: !!s.querySelector(sel),
                                 open: s.getAttribute('data-open') }))
               .filter((x) => x.has && x.open !== 'true').map((x) => x.i);
           }""", inner_selector)
    opened = 0
    for i in idx:
        sec = page.locator('.dock-lens[data-lens="evidence"] .dock-section').nth(i)
        if clicked(sec.locator(".dock-section-head"), timeout=timeout):
            opened += 1
    return opened


# ---------- studio boot ------------------------------------------------------

# Chromium refuses to NAVIGATE to a list of ports it considers unsafe for the web
# (`net/base/port_util.cc`). `free_port` below picks a random free port, and when
# it lands on one of these the suite dies with
#
#     Page.goto: net::ERR_UNSAFE_PORT at http://127.0.0.1:2049/
#
# which reads exactly like a broken product and is really an unlucky draw.
# Measured: the `smoke` suite failed the whole 34-suite gate that way, on port
# 2049. The overlap with the ephemeral range is small but real — 2049, 3659, 4045,
# 5060, 6000, 6566, 6697, 10080 and the 6665-6669 block all sit in or near it.
_CHROMIUM_BLOCKED_PORTS = frozenset({
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79,
    87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137,
    139, 143, 161, 179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531, 532,
    540, 548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723,
    2049, 3659, 4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697,
    10080,
})


def free_port():
    """A free port Chromium will actually navigate to.

    The port must be free AND not on Chromium's blocked list — a plain
    `bind(("127.0.0.1", 0))` satisfies only the first, and the second failure
    mode looks like a product bug rather than a harness accident.
    """
    for _ in range(50):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        finally:
            s.close()
        if port not in _CHROMIUM_BLOCKED_PORTS:
            return port
    raise RuntimeError("no Chromium-safe free port found in 50 attempts")


_TOKEN_CACHE = {}


def studio_token(base):
    """The capability token the studio set as a SameSite=Strict cookie on `/`.

    Returns None when the server runs with --no-token (the self-booted harness
    default). Cached per base URL; best-effort -- any failure reads as no token.
    """
    base = base.rstrip("/")
    if base in _TOKEN_CACHE:
        return _TOKEN_CACHE[base]
    tok = None
    try:
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            sc = r.headers.get("Set-Cookie", "")
        import re as _re
        m = _re.search(r"studio_token=([^;]*)", sc)
        tok = m.group(1) if m else None
    except Exception:
        tok = None
    _TOKEN_CACHE[base] = tok
    return tok


def studio_headers(base):
    """Headers a direct (non-browser) client needs to write to `base`.

    Empty when the studio has no token; X-Studio-Token otherwise. This lets a
    suite run against a secure-by-default LIVE studio (E2E_BASE) without the
    operator having to pass --no-token. The browser flows get the token as a
    cookie automatically.
    """
    tok = studio_token(base)
    return {"X-Studio-Token": tok} if tok else {}


class Studio:
    """A booted webapp_server subprocess. Use as a context manager."""

    def __init__(self, base_url, proc, projects_dir, log_path):
        self.base_url = base_url
        self._proc = proc
        self.projects_dir = projects_dir
        self.log_path = log_path
        self._log_file = None
        self.token = None  # H1: capability token read from /'s Set-Cookie

    def _fetch_token(self):
        try:
            with urllib.request.urlopen(self.base_url + "/", timeout=15) as r:
                sc = r.headers.get("Set-Cookie", "")
        except Exception:
            return None
        import re as _re
        m = _re.search(r"studio_token=([^;]*)", sc)
        return m.group(1) if m else None

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


def start_studio(projects_dir=None, env_extra=None, timeout=60, server_url=None,
                 use_token=False):
    """Boot the real webapp server with the in-process demo craft model.

    projects_dir: existing dir to serve from (seed it BEFORE calling), or
                  None for a throwaway temp dir removed on close().
    server_url:   where the "writer's real llama-server" supposedly lives
                  (drives the status-strip switch-back flow). Passed via
                  --server with the demo ENV TRIGGER OFF, so main() applies
                  it BEFORE demo activation pins real_server_url.
    use_token:    boot SECURE-BY-DEFAULT (main() mints a capability token and
                  `/` sets it as a SameSite=Strict cookie) instead of the
                  harness's usual --no-token opt-out. Suites that seed through
                  direct server-side requests then need studio_headers() on
                  every write; suites that only drive the browser get the
                  cookie for free. Default False keeps every existing suite's
                  behaviour unchanged.
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
    # --no-token: the harness is a trusted local tool and seeds projects with
    # direct server-side requests, which the secure-by-default capability token
    # would 403. The harness opts out explicitly (it used to rely on the token
    # being off globally). The hardened path stays covered by
    # e2e_browser_token_mode.py, test_capability_token.py, and any suite that
    # asks for use_token=True.
    cmd = [sys.executable, "-m", "screenplay_studio.webapp_server",
           "--port", str(port), "--projects-dir", projects_dir, "--demo-model"]
    if not use_token:
        cmd.append("--no-token")
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
                studio.token = studio._fetch_token()  # H1
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
    """Text of the most recent finished assistant bubble, or "" if there is none.

    Bounded and never raises. After a failed send there IS no assistant bubble, and
    `.last.inner_text()` on a missing locator waits out its timeout and RAISES —
    aborting the run and masking every later check. An absent reply is a fact for
    the reply checks to assert, not a crash (mutation-verified: with the
    drawer-open class removed, this raised and killed the suite before its summary).
    """
    try:
        return page.locator(".msg.assistant .msg-bubble").last.inner_text(
            timeout=8000).strip()
    except Exception:
        return ""


def filled(target, selector, text, timeout=8000):
    """Bounded fill: True if the text landed, False if the field was unreachable.

    Same reasoning as `clicked`: an unreachable field is a precondition failure to
    assert by name, not a `fill()` timeout that aborts the run.
    """
    try:
        if selector is None:
            target.fill(text, timeout=timeout)
        else:
            target.locator(selector).fill(text, timeout=timeout)
        return True
    except Exception:
        return False


def send_chat(page, text):
    """Type into the Sameer composer and hit Send. Returns True if the turn was
    sent, False if the composer was never usable.

    BOUNDED and never raises. A hidden composer means an earlier precondition
    failed (e.g. the room drawer never opened, so the pane carrying #input is
    display:none) — and an unguarded `fill()` waits out its timeout and RAISES,
    aborting the run and masking every later check. Mutation-verified: with the
    drawer-open class removed, the old body died in `fill()` and the named
    failure above it never printed (pass 9's lesson, re-proved).

    exact=True still matters even though the off-canvas #sameer-send panel is gone
    (H3): the composer's own button is named exactly "Send", and any future control
    whose accessible name merely CONTAINS "Send" would make a substring match
    resolve to two buttons, which strict mode refuses.
    """
    try:
        page.locator("#input").fill(text, timeout=8000)
        page.get_by_role("button", name="Send", exact=True).click(timeout=8000)
        return True
    except Exception:
        return False
