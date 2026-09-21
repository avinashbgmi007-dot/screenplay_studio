"""Regression tests for the 2026-09-20 production-readiness audit (docs/audit/production_readiness_2026-09-20.md).

Covers the three behavior changes the audit found exploitable or lossy:

- B1: SessionStore session-id path traversal (`_path("..\\..\\evil")` used to
  escape sessions_dir; the webapp <sid> converter delivers backslashes).
- B2: webapp_demo bound 0.0.0.0 and bypassed main()'s token mint.
- A1: a corrupt/unreadable edits.json made has_edits() read False, letting
  ensure_working() overwrite the writer's only edited copy on re-parse.
"""
import importlib.util
import json
import os

import pytest

from screenplay_cowriter.store import SessionStore
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio import revision


# ---- B1: session-id path traversal is rejected --------------------------
class TestSessionIdGuard:
    def test_dotdot_backslash_rejected(self, tmp_path):
        store = SessionStore(str(tmp_path / "sessions"))
        with pytest.raises((ValueError, PermissionError)):
            store._path("..\\..\\evil")

    def test_dotdot_forward_rejected(self, tmp_path):
        store = SessionStore(str(tmp_path / "sessions"))
        with pytest.raises((ValueError, PermissionError)):
            store._path("../../evil")

    def test_valid_id_still_resolves_inside_dir(self, tmp_path):
        sdir = tmp_path / "sessions"
        store = SessionStore(str(sdir))
        p = store._path("abc123")
        assert os.path.abspath(p).startswith(os.path.abspath(str(sdir)))
        assert p.endswith(".json")

    def test_delete_of_traversal_id_does_not_touch_outside_file(self, tmp_path):
        outside = tmp_path / "victim.json"
        outside.write_text("{}", encoding="utf-8")
        store = SessionStore(str(tmp_path / "sessions"))
        with pytest.raises((ValueError, PermissionError)):
            store.delete("..\\..\\victim")  # must raise before reaching os.remove
        assert outside.exists()


# ---- B2: the demo launcher never binds 0.0.0.0 --------------------------
def test_webapp_demo_binds_loopback_not_all_interfaces():
    """B2: the demo launcher must not bind all interfaces. Assert no *actual*
    `app.run(host="0.0.0.0")` remains — mentions in comments/docstrings are
    allowed (they document the fix), a live bind call is not."""
    import re
    src = open("screenplay_studio/webapp_demo.py", encoding="utf-8").read()
    assert not re.search(r'run\s*\(\s*host\s*=\s*["\']0\.0\.0\.0', src), (
        "webapp_demo still makes a live app.run(host='0.0.0.0') bind")


# ---- A1: corrupt edits.json must NOT read as "no edits" -----------------
def test_has_edits_treats_corrupt_log_as_present_not_empty(tmp_path, sample_fountain):
    m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
    m.save()
    log_path = revision.edits_log_path(m)
    # simulate a crash-truncated edit log (the non-atomic write from A2)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write('[{"id": "abc123", "scene_number": 1, "old": "x", "new": "y"')
    assert revision.has_edits(m) is True, (
        "a corrupt edit log was read as 'no edits', which lets ensure_working() "
        "overwrite the writer's only edited copy on re-parse")


# ---- A2: writer-owned stores must be written atomically (tmp + replace) ---
class TestAtomicWrites:
    """A2 (audit 2026-09-20): the crash-truncated edits.json that A1 now survives
    is still producible because these writer-owned stores use raw open(...,'w').
    The fix routes them through jsonio.atomic_write_json — a torn write can no
    longer reach the reader."""

    def test_edits_log_is_atomic(self, tmp_path, sample_fountain):
        import unittest.mock as mock
        from screenplay_studio import jsonio
        from screenplay_parser import parse_fountain
        m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
        m.save()
        parse_fountain(sample_fountain).save(m.parsed_path)  # parse, or save_working refuses
        revision.ensure_working(m)  # creates working.json
        with mock.patch.object(jsonio, "atomic_write_json",
                               wraps=jsonio.atomic_write_json) as spy:
            revision.save_working(m, revision.load_working(m),
                                  record={"scene_number": 1, "old": "a", "new": "b"})
        called_paths = [str(c.args[0]) for c in spy.call_args_list]
        assert any("edits" in p for p in called_paths), (
            f"edits.json was not written atomically; atomic_write_json saw {called_paths}")

    def test_writer_profile_save_is_atomic(self, tmp_path):
        import unittest.mock as mock
        from screenplay_studio import jsonio
        from screenplay_cowriter.memory import WriterMemory
        p = WriterMemory(str(tmp_path / "writer_profile.json"))
        with mock.patch.object(jsonio, "atomic_write_json",
                               wraps=jsonio.atomic_write_json) as spy:
            p.save()
        assert spy.called, "WriterMemory.save bypassed atomic_write_json"

    def test_working_copy_is_atomic(self, tmp_path, sample_fountain):
        """ScriptDocument.save is the single chokepoint for working.json/parsed.json —
        the writer's only edited copy must never be a torn write."""
        import unittest.mock as mock
        from screenplay_parser import parse_fountain
        from screenplay_studio import jsonio
        m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
        m.save()
        parse_fountain(sample_fountain).save(m.parsed_path)  # parse, or ensure_working refuses
        with mock.patch.object(jsonio, "atomic_write_json",
                               wraps=jsonio.atomic_write_json) as spy:
            revision.ensure_working(m)
        called_paths = [str(c.args[0]) for c in spy.call_args_list]
        assert any(p.endswith("working.json") for p in called_paths), (
            f"working.json was not written atomically; saw {called_paths}")


# ---- D: demo-mode findings are labelled, not fabricated as real notes ----
class TestDemoHonesty:
    """The canned fallback findings must not read as real analysis: each is
    tagged so the fix queue cannot pass it off as the doctor's note.

    Behavioural, not textual. The old check regexed demo_model.py's source for
    `"issue": "..."` literals, which proved a label STRING existed in the file —
    not that the model emits it. This drives the model's own dispatch (the same
    `_decide_reply` the demo server's /v1/chat/completions calls) with the
    trigger phrases the analyzer actually sends (screenplay_analyzer/prompts.py)
    and inspects the findings it really returns.
    """

    # (analyzer trigger phrase, user turn, the category that pass emits)
    _FINDING_PASSES = [
        ("on-the-nose dialogue",
         "Scene 1\nMARA: I'll tell you everything when this is over.", "dialogue"),
        ("theme and subtext", "Scene 1\nMARA: The rain again.", "theme"),
        ("character arcs", "Scene 1\nMARA: The rain again.", "character"),
        ("genre specialist checking whether", "Scene 1\nMARA: The rain again.", "genre"),
    ]

    @pytest.mark.parametrize("trigger,user,expected_category", _FINDING_PASSES)
    def test_every_finding_pass_labels_its_output_as_demo(
            self, trigger, user, expected_category):
        from screenplay_studio.demo_model import _decide_reply
        raw = _decide_reply([{"role": "system", "content": trigger},
                             {"role": "user", "content": user}])
        findings = json.loads(raw).get("findings") or []
        assert findings, f"the {trigger!r} pass emitted no finding to inspect"
        assert any(f.get("category") == expected_category for f in findings), (
            f"{trigger!r} emitted categories "
            f"{[f.get('category') for f in findings]}, expected {expected_category!r}")
        unlabelled = [f.get("issue") for f in findings
                      if "[demo]" not in (f.get("issue") or "")
                      and "demo model" not in (f.get("issue") or "").lower()]
        assert not unlabelled, (
            f"{trigger!r} emitted findings that could pass as a real analysis: {unlabelled}")


# ---- UI audit 2026-09-20: the ledger must open showing everything ----------
class TestFeedbackLedgerDefaults:
    """Defect #1 (docs/audit/ui_evidence_findings_2026-09-20.md): the dock's mass
    strip counts EVERY finding while the default filter showed only HIGH ones, so
    the room read "6 open of 6 findings" above "0 shown / 6 total". A writer whose
    script produced no highs saw an empty room that claimed six findings. The
    ledger now defaults to all severities; the chips narrow, the header stays true."""

    def test_default_filter_admits_every_severity(self):
        import re
        src = open("screenplay_studio/webapp/app.js", encoding="utf-8").read()
        m = re.search(r"findingFilter:\s*\{\s*severities:\s*\[([^\]]*)\]", src)
        assert m, "findingFilter default not found — did the state shape change?"
        declared = set(re.findall(r'"(\w+)"', m.group(1)))
        assert declared == {"high", "medium", "low"}, (
            f"the ledger default hides severities {sorted({'high','medium','low'} - declared)}; "
            "the dock header counts all findings, so a narrower default contradicts it")

    def test_the_mass_strip_labels_its_scope_when_the_filter_narrows(self):
        """The contradiction was never that one count was wrong — it was that a
        WHOLE-script total sat unlabelled above a FILTERED list. The strip must
        now print which scope it shows whenever the filter narrows it."""
        import re
        src = open("screenplay_studio/webapp/app.js", encoding="utf-8").read()
        assert "function findingCounts()" in src, "the scope counter is gone"
        assert re.search(r'dock-mass-total",\s*mText', src), (
            "the mass strip must print its scope via mText — a bare "
            "'N open of M findings' reads as a claim about the filtered board")
        assert "shown by filter" in src, "the narrow-scope label is missing"

    def test_the_fix_queue_reuses_the_one_filter_predicate(self):
        """Two copies of the severity/category test is how the strip and the
        queue drifted apart in the first place (N3: surfaces cannot disagree)."""
        import re
        src = open("screenplay_studio/webapp/app.js", encoding="utf-8").read()
        assert "function inFindingFilter(" in src, "the ONE filter predicate is gone"
        assert "const inFilter = inFindingFilter;" in src, (
            "the fix queue no longer reuses the shared predicate")
        assert not re.search(r"const inFilter = \(item\) =>", src), (
            "a second, local filter predicate came back")


# ---- R6: the manuscript margin points, it never covers the script ---------
class TestManuscriptMarginContract:
    """Defect #1 + #2 (docs/audit/ui_evidence_findings_2026-09-20.md): every
    per-scene finding card was absolutely positioned at right:-18px, so 196px of
    the 214px column lay ON the paper — measured overlap was 164px of text per
    card, i.e. action lines clipped mid-word — and each card carried the full
    judgment row (Rewrite/Discuss) on top of the board, the dock and the shadow
    copy, so one finding rendered as four competing surfaces.

    The margin now (a) cannot cover text by construction, and (b) is a PIN: it
    locates, the board/dock judge. These are the source contracts behind the
    live geometry checks in e2e_browser_phase13_legacy_cleanup.py."""

    def test_default_layout_is_in_flow_not_an_overlay(self):
        """In-flow is the safe default: an absolutely positioned margin can only
        be correct for the widths someone remembered to special-case."""
        import re
        css = open("screenplay_studio/webapp/style.css", encoding="utf-8").read()
        block = re.search(r"\.scene-notes\s*\{([^}]*)\}", css)
        assert block, ".scene-notes rule not found"
        assert "position: static" in block.group(1), (
            "the margin base rule must be in-flow — the gutter column is the "
            "opt-in, not the default")

    def test_the_gutter_column_is_gated_on_real_room(self):
        """The overlap survived a viewport media query because the dock takes
        380px WITHOUT changing the viewport: at 1440px the paper's gutter was
        already gone. The promotion must key off the container, and must not
        fire while the Problem Board's absolute overlay holds that gutter."""
        import re
        css = open("screenplay_studio/webapp/style.css", encoding="utf-8").read()
        assert "container: manuscript-column / inline-size" in css, (
            "#manuscript-container no longer establishes the container context")
        assert "@container manuscript-column" in css, (
            "the margin promotion must be a container query, not a media query")
        assert ":not(:has(#problem-board.visible:not(.pb-collapsed)))" in css, (
            "the gutter column must stand down while the board overlay is open")
        assert not re.search(r"\.scene-notes\s*\{[^}]*right:\s*-18px", css), (
            "the margin is pinned back over the paper")

    def test_margin_pins_are_read_only_pointers(self):
        """findingNoteEl's own comment has always said "margin pins stay
        read-only"; the code rendered Rewrite/Discuss on them anyway."""
        import re
        src = open("screenplay_studio/webapp/app.js", encoding="utf-8").read()
        assert "{ addressed, pin: true }" in src, (
            "renderScenePage no longer renders the margin as pins")
        gate = src.index("if (!opts.pin)")
        tail = src[gate:gate + 260]
        assert "appendChild(rewriteBtn)" in tail and "appendChild(discussBtn)" in tail, (
            "the judgment controls must be gated on !opts.pin")
        assert "appendChild(locateBtn)" not in tail, (
            "Locate is navigation and stays on the pin")


# ---- A3: a damaged premise card is reported, never silently emptied -------
class TestPremiseStoreIntegrity:
    """A3 (2026-09-20): premise.json was the last writer-owned store still
    written with a raw open(...,'w') — the same shape A2 fixed elsewhere — and
    BOTH of its readers collapsed every error into "no premise card". A
    crash-truncated file therefore erased the writer's title / logline / premise
    / open-questions from the UI permanently, with no error and no backup.
    It is now atomic, and UNREADABLE is distinct from MISSING."""

    @pytest.fixture
    def client(self, tmp_path):
        import screenplay_studio.webapp_server as webapp_server
        webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
        os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
        webapp_server.app.config["TESTING"] = True
        return webapp_server.app.test_client()

    def _make_project(self, sample_fountain, raw_card):
        import screenplay_studio.webapp_server as webapp_server
        d = os.path.join(webapp_server.PROJECTS_DIR, "Embers")
        os.makedirs(d, exist_ok=True)
        m = ProjectManifest.create(d, sample_fountain)
        m.save()
        with open(os.path.join(d, "premise.json"), "w", encoding="utf-8") as f:
            f.write(raw_card)
        return "Embers"

    def test_premise_writers_are_atomic(self):
        import re
        for path in ("screenplay_studio/ideas.py", "screenplay_studio/webapp_server.py"):
            src = open(path, encoding="utf-8").read()
            assert not re.search(r'"premise\.json"\)?\s*,\s*"w"', src), (
                f"{path} still writes premise.json with a raw open(..., 'w')")

    def test_unreadable_premise_is_reported_not_presented_as_absent(
            self, client, sample_fountain):
        name = self._make_project(sample_fountain, '{"title": "Embers", "logline": "A ga')
        data = client.get(f"/api/projects/{name}").get_json()
        assert data.get("premise_error"), (
            "a torn premise.json was reported as 'no premise card'")
        assert "premise" not in data, "a damaged card must not be served as a card"

    def test_unreadable_premise_is_never_silently_overwritten(
            self, client, sample_fountain, tmp_path):
        raw = '{"title": "Embers", "logline": "A ga'
        name = self._make_project(sample_fountain, raw)
        r = client.post(f"/api/projects/{name}/premise",
                        json={"card": {"logline": "a NEW logline"}})
        assert r.status_code == 409, (
            f"a write over a damaged card must be refused, got {r.status_code}")
        import screenplay_studio.webapp_server as webapp_server
        with open(os.path.join(webapp_server.PROJECTS_DIR, name, "premise.json"),
                  encoding="utf-8") as f:
            assert f.read() == raw, "the damaged card was overwritten despite the refusal"


# ---- B1: CI must actually run the browser suites -------------------------
def test_ci_runs_the_browser_suite_gate():
    """B1 (2026-09-20): ~460 browser checks existed and NOTHING ran them — the
    SPA (app.js, ~9k lines) had no automated coverage in CI beyond 7 assertions
    on core.js. If this job is deleted, or the runner stops being invoked, that
    regression comes straight back and looks like a green build."""
    src = open(".github/workflows/ci.yml", encoding="utf-8").read()
    assert "tests/run_browser_suites.py" in src, (
        "ci.yml no longer runs the browser suite gate — the e2e_browser_* suites "
        "are back to being manual-only")
    assert "playwright install" in src, "the browser job can't run without chromium"
    # Assert the DIRECTIVE, not the bare word: ci.yml legitimately *mentions*
    # ubuntu-latest in a comment explaining why it is avoided (same trap the B2
    # bind test documents).
    import re
    assert not re.search(r"runs-on:\s*ubuntu-latest", src), (
        "an unpinned runner is back — the 24.04 -> 26.04 migration breaks it silently")


def test_ci_pins_its_linter_to_the_version_the_repo_uses():
    """R7 (2026-09-21): the lint job ran `pip install ruff` — unpinned.

    That is the same class of hole the `runs-on` guard above covers: a floating
    tool means a new release can fail a green build with no code change, and the
    CI gate can silently disagree with the developer's own `ruff check .`. The
    version lives in three places (ci.yml, the `dev` extra, the `ci` extra), so
    this asserts all three agree rather than trusting them to.
    """
    import re
    ci = open(".github/workflows/ci.yml", encoding="utf-8").read()
    m = re.search(r'pip install "ruff==([0-9][^"]*)"', ci)
    assert m, (
        "ci.yml no longer pins ruff — `pip install ruff` floats, so a new ruff "
        "release can break the lint gate with no code change")
    ci_version = m.group(1)

    pyproject = open("pyproject.toml", encoding="utf-8").read()
    pinned = re.findall(r'"ruff==([0-9][^"]*)"', pyproject)
    assert pinned, "pyproject no longer pins ruff in its dev/ci extras"
    assert len(set(pinned)) == 1, f"the extras disagree with each other: {pinned}"
    assert pinned[0] == ci_version, (
        f"ci.yml pins ruff=={ci_version} but pyproject pins ruff=={pinned[0]} — "
        f"the CI gate and the local toolchain would lint with different rules")
    assert "ruff>=" not in pyproject, (
        "a floating `ruff>=` is back in pyproject; the pin is the point")


def test_every_ci_job_declares_a_timeout():
    """R9 (2026-09-21): a GitHub job with no `timeout-minutes` inherits the
    platform default of **360 minutes**, so one hung suite can burn six hours of
    CI before anything notices. All four jobs do declare one today — which is
    exactly why nothing was watching it.

    The per-job timeouts are also what makes the "is the budget big enough?"
    question answerable at all. Measured 2026-09-21: the browser gate is
    **303 s (5.05 min) for 28 suites**, sequential, against a 45-minute budget —
    roughly 9x headroom, so the audit's "125-minute worst case" reads as a sum of
    per-suite worst-case waits, not an expected runtime.

    This asserts the DECLARATION, not a duration: it cannot know how fast a
    runner is, but it can refuse a job that is unbounded.
    """
    import re
    src = open(".github/workflows/ci.yml", encoding="utf-8").read()
    assert "\njobs:" in src, "ci.yml no longer has a jobs: block"
    body = src.split("\njobs:", 1)[1]
    # job ids sit at two-space indent, their keys at four
    starts = [m.start() for m in re.finditer(r"^  ([A-Za-z][\w-]*):[ \t]*$", body, re.M)]
    assert starts, "no jobs parsed out of ci.yml — the file's shape changed"
    jobs = []
    for i, at in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(body)
        block = body[at:end]
        name = re.match(r"^  ([A-Za-z][\w-]*)", block).group(1)
        jobs.append((name, block))
    assert len(jobs) >= 4, f"expected the four CI jobs, parsed {[n for n, _ in jobs]}"
    unbounded = [n for n, block in jobs if "timeout-minutes:" not in block]
    assert not unbounded, (
        f"CI job(s) {unbounded} declare no timeout-minutes — a hang there runs to "
        f"the 360-minute platform default")


# ---- R7b: dependencies are pinned, and CI actually installs from the lock ----
LOCKFILE = "requirements.lock.txt"

# Deliberately unpinned, each with a reason. Keeping this list SHORT is the
# point: a lock with a long exception list is not a lock. Every entry must name
# a dependency that is genuinely not installed in the environment the lock was
# derived from — otherwise the honest move is to pin it.
_LOCK_EXCEPTIONS = {
    "faster-whisper": "opt-in `stt` extra: never installed by default, so there "
                      "is no measured version to record",
    "pytest-cov": "`ci` extra: CI installs it but no development environment has, "
                  "so any pin would be invented rather than measured",
    "importlib-metadata": 'gated by `python_version < "3.10"`; correctly absent',
    "exceptiongroup": 'gated by `python_version < "3.11"`; correctly absent',
    "tomli": 'gated by `python_version < "3.11"`; correctly absent',
    "backports-asyncio-runner": 'gated by `python_version < "3.11"`; correctly absent',
}


def _canon(name):
    import re
    return re.sub(r"[-_.]+", "-", name).lower()


def _lock_pins():
    """name -> version for every non-comment line of the lock."""
    pins = {}
    with open(LOCKFILE, encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if not line:
                continue
            name, _, version = line.partition("==")
            pins[_canon(name.strip())] = version.strip()
    return pins


def _declared_requirements():
    """name -> specifier, from requirements.txt + pyproject's dependencies/extras."""
    import re
    declared = {}
    with open("requirements.txt", encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if not line:
                continue
            name = re.split(r"[<>=!~\[;]", line)[0].strip()
            declared[_canon(name)] = line[len(name):].strip()
    with open("pyproject.toml", encoding="utf-8") as f:
        for line in f:
            for m in re.finditer(r'"([A-Za-z0-9_.\-]+)\s*([<>=!~][^"]*)"',
                                 line.split("#")[0]):
                declared.setdefault(_canon(m.group(1)), m.group(2))
    return declared


def test_the_lockfile_is_a_lock_and_not_a_wish_list():
    """Every line must be an exact `==` pin. A `>=` in a lock file is a floor
    wearing a lock's clothes: it re-opens exactly the drift the file exists to
    close."""
    import re
    offenders = []
    with open(LOCKFILE, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            body = line.split("#")[0].strip()
            if not body:
                continue
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+==[^\s,;]+", body):
                offenders.append(f"line {n}: {body!r}")
    assert not offenders, (
        f"{LOCKFILE} has non-exact entries, so it is not a lock: {offenders}")


def test_every_declared_dependency_is_pinned_or_explained():
    """A dependency nobody pinned is a dependency that can change under a green
    build. Each miss must be on the documented exception list, with a reason."""
    pins = _lock_pins()
    missing = sorted(n for n in _declared_requirements()
                     if n not in pins and n not in _LOCK_EXCEPTIONS)
    assert not missing, (
        f"declared but not pinned in {LOCKFILE}: {missing}. Either pin them "
        f"(regenerate, do not retype) or add them to _LOCK_EXCEPTIONS with a "
        f"reason — an unexplained gap is how the lock silently stops being one.")
    stale = sorted(n for n in _LOCK_EXCEPTIONS if n in pins)
    assert not stale, (
        f"{stale} are pinned in {LOCKFILE} but still listed as exceptions; the "
        f"exception list has drifted out of date")


def test_no_pin_is_older_than_the_floor_it_has_to_satisfy():
    """The lock and the declarations must agree. Pinning below a declared floor
    would make CI install a version the project explicitly rejects — a lock that
    contradicts its own requirements is worse than no lock, because it looks
    authoritative."""
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    pins = _lock_pins()
    violations = []
    for name, spec in sorted(_declared_requirements().items()):
        if not spec or name not in pins:
            continue
        if Version(pins[name]) not in SpecifierSet(spec):
            violations.append(f"{name}: locked {pins[name]} but declared {spec!r}")
    assert not violations, (
        "the lock contradicts the declared requirements:\n  " + "\n  ".join(violations))


def test_the_lockfile_has_no_duplicate_entries():
    """Two pins for one package is a file that says two different things."""
    import re
    seen, dupes = set(), []
    with open(LOCKFILE, encoding="utf-8") as f:
        for line in f:
            body = line.split("#")[0].strip()
            if not body:
                continue
            name = _canon(body.split("==")[0].strip())
            if name in seen:
                dupes.append(name)
            seen.add(name)
    assert not dupes, f"duplicate entries in {LOCKFILE}: {sorted(set(dupes))}"


def test_ci_installs_from_the_lockfile():
    """The anti-decoration check. A lock file nothing installs from changes no
    version on any machine — it just looks like reproducibility. Wherever CI
    installs the full environment, the lock must be applied as a constraint."""
    import re
    src = open(".github/workflows/ci.yml", encoding="utf-8").read()
    installs = re.findall(r"^\s*run:\s*pip install .*$", src, re.M)
    assert installs, "no `pip install` steps parsed out of ci.yml"
    unconstrained = [line.strip() for line in installs
                     if ".[ci]" in line and "-c requirements.lock.txt" not in line]
    assert not unconstrained, (
        f"CI installs the full environment without the lock: {unconstrained}. "
        f"The declared `>=` floors mean CI and a developer can then resolve "
        f"different versions of the same dependency.")


def test_browser_gate_runner_never_silently_drops_a_suite():
    """Every suite the runner cannot execute must be a NAMED entry with a reason.
    A silently skipped suite is dead coverage, and dead coverage is worse than
    none because it looks like safety."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import run_browser_suites as rbs
    assert rbs.HARNESS == "e2e_browser_common.py", "the shared harness is not a suite"
    for key, reason in {**rbs.REQUIRES_LIVE_STUDIO, **rbs.KNOWN_BROKEN}.items():
        assert reason, f"{key} is excluded without a stated reason"
    for passing in ("smoke", "phase6_evidence", "phase14_signoff_journey",
                    "layout_audit", "rewrite_loop",
                    # repaired 2026-09-21 — these two were excluded as "crashes"
                    # for long enough that preview_next's other four worlds were
                    # never exercised. Re-adding either to KNOWN_BROKEN would
                    # silence real coverage, so pin them as runnable.
                    "preview_next", "preview_redesigns"):
        assert passing not in rbs.REQUIRES_LIVE_STUDIO, f"{passing} is runnable"
        assert passing not in rbs.KNOWN_BROKEN, f"{passing} is runnable"


# ---- B4: the "never off the machine" STT guard must not be prefix-bypassable --
class TestWhisperUrlGuard:
    """The external whisper engine is the one place dictation audio could leave
    this machine. Its guard was `url.startswith(("http://localhost",
    "http://127.0.0.1"))`, which both "http://127.0.0.1@evil.com" (userinfo: the
    authority ends at the @) and "http://localhost.evil.com" (suffix) satisfy
    while resolving to a REMOTE host."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1@evil.com",   # userinfo bypass
        "http://localhost.evil.com",   # suffix bypass
        "https://evil.example.com",
        "http://10.0.0.5:8080",
    ])
    def test_remote_looking_urls_are_refused(self, url):
        from screenplay_studio import stt
        with pytest.raises(stt.STTUnavailableError):
            stt._assert_local_whisper(url)

    @pytest.mark.parametrize("url", [
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://[::1]:8081",
    ])
    def test_genuinely_local_urls_are_accepted(self, url):
        from screenplay_studio import stt
        stt._assert_local_whisper(url)  # must not raise


class TestRetryPermissionBudget:
    """test_store_save_serializes_concurrent_writers + test_save_rename_race_never_tears_json
    intermittently surface WinError 32/33 under load: a reader (test_client.get) or AV
    holds the file while os.replace fires. retry_permission's 3 attempts at
    50/100/150ms total ~0.3s can expire before the holder releases. Widening the
    budget (more attempts, jittered, capped) makes the atomic-write guarantee hold
    under realistic load without masking a genuine denial (still fails fast on
    non-transient PermissionError)."""

    def test_default_budget_is_wide_enough_for_concurrent_hammer(self):
        import inspect
        from screenplay_studio import jsonio
        sig = inspect.signature(jsonio.retry_permission)
        assert sig.parameters["attempts"].default >= 6, (
            f"retry_permission default attempts={sig.parameters['attempts'].default} "
            "is too tight for the concurrent save/rename hammer (needs >=6)")

    def test_genuine_denial_still_raises_bounded_not_swallowed(self):
        """2026-09-20 decision: EVERY PermissionError is retried for the bounded
        window (so AV-hold hammers stay green), but a genuine denial must still
        RAISE — bounded, never swallowed, never infinite."""
        import time
        import pytest as _pytest
        from screenplay_studio import jsonio
        calls = {"n": 0}

        def denied():
            calls["n"] += 1
            raise PermissionError(13, "Access is denied")
        t0 = time.monotonic()
        with _pytest.raises(PermissionError):
            jsonio.retry_permission(denied, attempts=3)
        elapsed = time.monotonic() - t0
        assert calls["n"] == 3, f"a transient-eligible error must be retried all {calls['n']} times"
        assert elapsed < 3.0, f"retries must be bounded (~1s), took {elapsed:.2f}s"

    def test_non_permission_errors_are_not_retried(self):
        import pytest as _pytest
        from screenplay_studio import jsonio
        calls = {"n": 0}

        def boom():
            calls["n"] += 1
            raise ValueError("not a lock error")
        with _pytest.raises(ValueError):
            jsonio.retry_permission(boom)
        assert calls["n"] == 1, "a non-PermissionError must fail immediately, no retry"
