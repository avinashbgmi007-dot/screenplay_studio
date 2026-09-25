"""Packaging guard: the wheel and sdist must ship the app's data files.

`pip install .` used to produce a wheel containing ONLY `.py` files. Two
consequences, both silent:

  * `knowledge_base/` shipped without `index.json`, `schema.json` or any of the
    26 `rules/*.json` — so `KnowledgeBase()` loaded zero rules and every report
    quietly lost its "grounded in rule X" claim (`_kb_rule_ids()` returned an
    empty frozenset, so real rule ids were re-filed as check ids).
  * `screenplay_studio/webapp/` was absent entirely — so `GET /` 404'd. The
    frontend is a no-build-step SPA: those files *are* the artifact.

The cause was a bare `[tool.setuptools] packages` list with no `package-data`
and no `MANIFEST.in`. These tests fail if that ever happens again.

Three layers, deliberately:

  1. `test_declared_package_data_covers_every_shippable_asset` — fast, no build.
     Evaluates the declared globs against the real tree, so a *new* asset file
     (or a new nesting depth) that no pattern matches is a failure, without
     anyone having to remember to update a list.
  2. `test_wheel_*` — builds a real wheel and asserts its contents by name.
  3. `test_sdist_*` — the same for the source distribution, which is the other
     path `pip install` can take.

PNGs are asserted *absent*: the repo carries 69 tracked screenshots of UI
evidence, and none of them are needed to run the app.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(ROOT, "pyproject.toml")

# Extensions that must travel with the package for the app to work at all.
# PNG is deliberately NOT here — see the module docstring.
SHIPPABLE_EXTENSIONS = (".json", ".md", ".html", ".js", ".css", ".woff2")

# Assets the app cannot start without. Named explicitly so a rename or an
# accidental removal is a loud failure instead of a quiet shrink.
REQUIRED_ASSETS = (
    "knowledge_base/index.json",
    "knowledge_base/schema.json",
    "knowledge_base/rules/action.json",
    "knowledge_base/rules/structure_pacing.json",
    "screenplay_studio/webapp/index.html",
    "screenplay_studio/webapp/app.js",
    "screenplay_studio/webapp/core.js",
    "screenplay_studio/webapp/style.css",
    "screenplay_studio/webapp/tungsten.css",
)

# Tracked scratch that sits *inside* a package directory but is read by no code
# (`grep -rn 'graph_output.json|graph.json' --include='*.py'` finds nothing).
# A broad `*.json` package-data pattern would ship it, so it is excluded from
# the shipping patterns on purpose — and asserted absent from the wheel.
# Keyed by repo-relative path -> why it is not shipped. A stale entry fails the
# guard below, so this table cannot rot.
EXCLUDED_FROM_SHIPPING = {
    "screenplay_parser/graph_output.json": "orphaned graphify scratch; no code reads it",
    "screenplay_analyzer/graph.json": "orphaned graphify scratch; no code reads it",
}


# --------------------------------------------------------------------------
# Layer 1 — declared config vs. the real tree (no build, runs everywhere)
# --------------------------------------------------------------------------


def _load_pyproject() -> dict:
    if tomllib is None:  # pragma: no cover - Python 3.10
        pytest.skip("tomllib requires Python 3.11+; pyproject parsing skipped")
    with open(PYPROJECT, "rb") as fh:
        return tomllib.load(fh)


def _declared_package_data() -> tuple[list[str], dict]:
    cfg = _load_pyproject()
    st = cfg["tool"]["setuptools"]
    return st["packages"], st.get("package-data", {})


def _matched_paths() -> set[str]:
    """Repo-relative paths matched by the declared package-data globs.

    Uses the same mechanism setuptools does (`glob` with `recursive=True`), so
    the check reflects what the build will actually collect.
    """
    packages, patterns = _declared_package_data()
    matched: set[str] = set()
    for pkg in packages:
        pkg_dir = os.path.join(ROOT, pkg)
        if not os.path.isdir(pkg_dir):
            continue
        for pattern in patterns.get(pkg, []):
            for hit in glob.glob(os.path.join(pkg_dir, pattern), recursive=True):
                if os.path.isfile(hit):
                    matched.add(os.path.relpath(hit, ROOT).replace(os.sep, "/"))
    return matched


def test_package_data_is_declared_and_enabled():
    """The two settings whose absence caused R1 must both be present."""
    cfg = _load_pyproject()
    st = cfg["tool"]["setuptools"]
    assert st.get("include-package-data") is True, (
        "include-package-data must be true or MANIFEST.in is ignored by the wheel build"
    )
    assert st.get("package-data"), (
        "no [tool.setuptools.package-data]: the wheel would ship zero data files"
    )


def test_declared_package_data_covers_every_shippable_asset():
    """Every shippable file on disk must be matched by a declared glob.

    This is the drift guard: add `webapp/icons/foo.svg` and this fails until the
    pattern list knows about it, rather than the wheel silently omitting it.
    """
    packages, _ = _declared_package_data()
    matched = _matched_paths()

    on_disk: set[str] = set()
    for pkg in packages:
        pkg_dir = os.path.join(ROOT, pkg)
        if not os.path.isdir(pkg_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(pkg_dir):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in filenames:
                if filename.endswith(SHIPPABLE_EXTENSIONS):
                    rel = os.path.relpath(os.path.join(dirpath, filename), ROOT)
                    on_disk.add(rel.replace(os.sep, "/"))

    # The exclusion table must not rot: every entry has to exist on disk.
    stale = [p for p in EXCLUDED_FROM_SHIPPING if p not in on_disk]
    assert not stale, (
        "EXCLUDED_FROM_SHIPPING names files that no longer exist — delete the "
        f"entries: {stale}"
    )

    unmatched = sorted(on_disk - matched - set(EXCLUDED_FROM_SHIPPING))
    assert not unmatched, (
        "these files ship with the app but no [tool.setuptools.package-data] "
        "pattern matches them, so the wheel will omit them:\n  "
        + "\n  ".join(unmatched)
    )


def test_declared_patterns_cover_the_required_assets():
    """The named must-haves are matched by the declared globs."""
    matched = _matched_paths()
    missing = [rel for rel in REQUIRED_ASSETS if rel not in matched]
    assert not missing, f"required assets not covered by package-data: {missing}"



# --------------------------------------------------------------------------
# Layer 2/3 — build the real artifacts and assert what is inside
# --------------------------------------------------------------------------


def _purge_build_state() -> None:
    """Delete build artifacts before building.

    This is not hygiene, it is correctness of the TEST. setuptools keeps a
    `build/lib` staging tree and an `egg-info/SOURCES.txt` manifest between
    runs, and reuses both. Left in place, a regression in `package-data` is
    masked: the wheel is rebuilt from files staged by an earlier, working
    build, and every assertion below passes for the wrong reason.

    Verified by mutation — reverting the fix (removing `package-data` *and*
    MANIFEST.in) turns these tests red only when this purge runs first.

    Scoped to `build/` and `*.egg-info/`, which are pure intermediates that
    setuptools regenerates. `dist/` is deliberately NOT touched: a developer may
    keep a built release artifact there, and nothing here reads it.
    """
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    for entry in os.listdir(ROOT):
        if entry.endswith(".egg-info"):
            shutil.rmtree(os.path.join(ROOT, entry), ignore_errors=True)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)


def _build_wheel(out) -> subprocess.CompletedProcess:
    """Build a wheel, preferring no build isolation.

    `--no-build-isolation` is tried first because `setuptools>=68` is declared in
    the `ci` extra, so CI and dev environments already have the backend — and it
    avoids a network fetch inside the test suite. If that fails (a bare
    environment with no backend installed), retry letting pip provision it, so
    the guard degrades to "slower" rather than to "skipped".
    """
    base = [sys.executable, "-m", "pip", "wheel", ROOT, "--no-deps",
            "--no-cache-dir", "-w", str(out)]
    proc = _run(base + ["--no-build-isolation"])
    if proc.returncode != 0:
        proc = _run(base)
    return proc


@pytest.fixture(scope="module")
def wheel_path(tmp_path_factory):
    """Build a wheel once for the module. Skips if the build cannot run here."""
    out = tmp_path_factory.mktemp("wheelout")
    _purge_build_state()
    proc = _build_wheel(out)
    if proc.returncode != 0:
        pytest.skip("wheel build unavailable in this environment: "
                    + (proc.stderr or proc.stdout or "")[-400:])
    wheels = sorted(out.glob("*.whl"))
    assert wheels, "pip reported success but produced no wheel"
    return wheels[0]


@pytest.fixture(scope="module")
def sdist_path(tmp_path_factory):
    """Build an sdist once for the module. Skips if the build cannot run here."""
    out = tmp_path_factory.mktemp("sdistout")
    _purge_build_state()
    script = (
        "import setuptools.build_meta as b; "
        f"print(b.build_sdist({str(out)!r}))"
    )
    proc = _run([sys.executable, "-c", script])
    if proc.returncode != 0:
        pytest.skip("sdist build unavailable in this environment: "
                    + (proc.stderr or proc.stdout or "")[-400:])
    tarballs = sorted(out.glob("*.tar.gz"))
    assert tarballs, "sdist build reported success but produced no archive"
    return tarballs[0]


def _wheel_names(wheel) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        return zf.namelist()


def _sdist_names(sdist) -> list[str]:
    import tarfile

    with tarfile.open(sdist) as tf:
        return tf.getnames()


def test_wheel_ships_the_knowledge_base(wheel_path):
    names = _wheel_names(wheel_path)
    on_disk = glob.glob(os.path.join(ROOT, "knowledge_base", "rules", "*.json"))
    rules = [n for n in names if n.startswith("knowledge_base/rules/") and n.endswith(".json")]
    assert len(rules) == len(on_disk), (
        f"wheel carries {len(rules)} rule files, the source tree has {len(on_disk)}"
    )
    assert len(rules) >= 26, "the craft knowledge base is the analyzer's grounding — it must ship whole"
    for rel in ("knowledge_base/index.json", "knowledge_base/schema.json"):
        assert rel in names, f"{rel} missing from the wheel"


def test_wheel_ships_the_spa(wheel_path):
    names = _wheel_names(wheel_path)
    for rel in ("screenplay_studio/webapp/index.html",
                "screenplay_studio/webapp/app.js",
                "screenplay_studio/webapp/core.js",
                "screenplay_studio/webapp/style.css",
                "screenplay_studio/webapp/tungsten.css"):
        assert rel in names, f"{rel} missing from the wheel — GET / would 404"
    fonts = [n for n in names if n.startswith("screenplay_studio/webapp/fonts/")]
    assert len(fonts) >= 10, f"only {len(fonts)} fonts shipped; the SPA references all 14"


def test_wheel_excludes_evidence_screenshots(wheel_path):
    """69 tracked PNGs are UI evidence, not app assets."""
    pngs = [n for n in _wheel_names(wheel_path) if n.lower().endswith(".png")]
    assert not pngs, f"screenshots must not ship in the wheel, found {len(pngs)}: {pngs[:5]}"


def test_wheel_excludes_orphaned_graph_scratch(wheel_path):
    """`graph_output.json` / `graph.json` sit inside packages but no code reads them."""
    basenames = tuple(os.path.basename(p) for p in EXCLUDED_FROM_SHIPPING)
    names = _wheel_names(wheel_path)
    strays = [n for n in names if n.endswith(basenames)]
    assert not strays, f"orphaned scratch artifacts shipped: {strays}"


def test_sdist_ships_the_data_files(sdist_path):
    """MANIFEST.in exists so `pip install <sdist>` builds a working app too."""
    names = _sdist_names(sdist_path)
    normalised = [n.replace(os.sep, "/") for n in names]
    assert any(n.endswith("knowledge_base/index.json") for n in normalised), \
        "sdist is missing knowledge_base/index.json"
    assert any("/knowledge_base/rules/" in n and n.endswith(".json") for n in normalised), \
        "sdist is missing the craft rule files"
    assert any(n.endswith("screenplay_studio/webapp/app.js") for n in normalised), \
        "sdist is missing the SPA"
    assert not any(n.lower().endswith(".png") for n in normalised), \
        "sdist should not carry the evidence screenshots"


# --------------------------------------------------------------------------
# Layer 4 — install the wheel and SERVE from it (E2E-2, audit 2026-09-24)
#
# Layers 2/3 assert archive MEMBERSHIP. Membership is a proxy, and the repo's own
# recorded standard is the opposite — "verify by installing the wheel and serving
# from it, never by reasoning". A membership check cannot catch a loader that
# resolves its assets relative to the CURRENT WORKING DIRECTORY: that passes from
# a source checkout and fails the moment the package is installed. Nor can it
# catch a wheel that carries a file the runtime cannot read.
#
# Both loaders that matter were verified package-relative on 2026-09-24
# (`knowledge_base.py` and `webapp_server.py` each derive their directory from
# `os.path.abspath(__file__)`), so there is no bug today. This is the guard that
# would have caught one.
#
# Everything below runs with `cwd` set to a NEUTRAL directory and the repo root
# ABSENT from sys.path — that is what makes it an install test rather than a
# source-tree test wearing a hat.
# --------------------------------------------------------------------------

# The shipped KB's rule count, cross-checked against the source tree in Layer 2
# rather than pinned here, so a legitimate KB expansion does not turn this red.
# The rule count is NOT pinned here — it is cross-checked against the source tree
# in `test_installed_wheel_loads_the_whole_knowledge_base`, so a legitimate KB
# expansion does not turn this red, while a wheel that ships fewer rules than the
# tree does. The floor is the documented minimum from the module docstring.
INSTALLED_MIN_RULE_FILES = 26


def _source_rule_count() -> int:
    """How many rules the SOURCE tree loads — the number the install must match."""
    from knowledge_base import KnowledgeBase

    return len(KnowledgeBase().all())


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 60.0) -> bool:
    import socket
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


@pytest.fixture(scope="module")
def installed_wheel(wheel_path, tmp_path_factory):
    """`pip install --target` the built wheel into an isolated directory.

    `--no-index --no-deps` keeps this offline and free of resolution surprises:
    the wheel is local and the runtime deps are already in this environment.
    """
    target = tmp_path_factory.mktemp("installed")
    proc = _run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-index",
                 "--target", str(target), str(wheel_path)])
    if proc.returncode != 0:
        pytest.skip("pip install of the built wheel failed in this environment: "
                    + (proc.stderr or proc.stdout or "")[-400:])
    return target


@pytest.fixture(scope="module")
def neutral_cwd(tmp_path_factory):
    """A directory with nothing importable in it, so a cwd-relative loader cannot
    accidentally succeed."""
    return tmp_path_factory.mktemp("neutral")


def _installed_env(target, neutral_cwd) -> dict:
    env = dict(os.environ)
    # The repo root is deliberately NOT on the path — only the install target.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(target), env.get("PYTHONPATH", "")) if p)
    env["SCREENPLAY_STUDIO_DEMO_MODEL"] = "1"
    # A production-like boot: the child must not think it is inside a test run.
    env.pop("PYTEST_CURRENT_TEST", None)
    return env


def test_installed_wheel_loads_the_whole_knowledge_base(installed_wheel, neutral_cwd):
    """The silent-degradation failure mode: a wheel whose KB loads ZERO rules
    makes every report lose its "grounded in rule X" attribution with no error
    anywhere. Counting the rules from the INSTALLED package is the only way to
    know the install is not hollow."""
    script = (
        "import os, knowledge_base\n"
        "kb = knowledge_base.KnowledgeBase()\n"
        "print(os.path.dirname(os.path.abspath(knowledge_base.__file__)))\n"
        "print(len(kb.all()))\n"
    )
    proc = subprocess.run([sys.executable, "-c", script],
                          cwd=str(neutral_cwd),
                          env=_installed_env(installed_wheel, neutral_cwd),
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, (proc.stderr or proc.stdout)[-800:]
    where, count = proc.stdout.strip().splitlines()[-2:]
    assert str(installed_wheel) in where, (
        f"the test imported the wrong knowledge_base: {where}")
    expected = _source_rule_count()
    assert int(count) == expected, (
        f"the installed wheel loaded {count} craft rules, the source tree loads "
        f"{expected} — the wheel is not shipping the knowledge base whole")
    assert expected >= INSTALLED_MIN_RULE_FILES, (
        "the knowledge base lost files in the SOURCE tree, which is a different "
        "problem from packaging")


def test_installed_wheel_serves_the_spa(installed_wheel, neutral_cwd):
    """`GET /` from an installed wheel.

    This is what turns "the SPA is in the archive" into "the SPA is served" —
    the difference the writer actually experiences. It is also the check that
    would have caught the original R1 defect, where a `pip install` produced a
    wheel with no frontend at all and `GET /` 404'd silently.
    """
    import urllib.request

    port = _free_port()
    log_path = neutral_cwd / "serve.log"
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "screenplay_studio.webapp_server",
             "--port", str(port), "--projects-dir", str(neutral_cwd / "proj")],
            cwd=str(neutral_cwd),
            env=_installed_env(installed_wheel, neutral_cwd),
            stdout=log, stderr=subprocess.STDOUT)
        try:
            assert _wait_for_port(port), (
                "the installed app never came up on 127.0.0.1:\n"
                + log_path.read_text(encoding="utf-8", errors="replace")[-2000:])
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=20) as r:
                assert r.status == 200, f"GET / answered {r.status} from the installed wheel"
                body = r.read().decode("utf-8", "replace")
            assert "app.js" in body, (
                "GET / answered 200 but the body is not the SPA document")
            # The SPA's own assets must resolve from the install too — index.html
            # alone would be a page that renders nothing.
            for asset in ("/app.js", "/core.js", "/style.css", "/tungsten.css"):
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{asset}", timeout=20) as r:
                    assert r.status == 200, f"{asset} answered {r.status} from the installed wheel"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=15)
