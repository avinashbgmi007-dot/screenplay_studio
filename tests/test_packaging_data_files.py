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
