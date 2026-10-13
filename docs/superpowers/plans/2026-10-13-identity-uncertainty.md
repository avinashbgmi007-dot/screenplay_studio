# Identity-Uncertainty Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag and demote unhedged identity verdicts the script text cannot settle, in both assertion directions.

**Architecture:** A pure trigger/resolution helper plus `apply_identity_check(findings, doc)` in the pipeline finalize chain (the gate has no demote action); a contradiction rung in the integrity gate (proven falsehoods reject there); one Fix Queue chip beside the existing flags. All detection deterministic, quotes never scanned.

**Tech Stack:** Python 3, stdlib `re` only; `normalize_character_name` (already used by the continuity guard); `demote_severity` from `screenplay_analyzer.feedback_filter`; existing `row-flag` CSS pattern.

## Global Constraints

- Narrow-rule contract: fire only on positive trigger evidence; any doubt keeps the row.
- Quotes never scanned (verbatim script text).
- Flag-don't-drop for uncertainty (demote, delivered); withdraw only for proven contradiction (gate ledger).
- `ruff check` clean on touched files; full suite green before commit.
- No prompt, grammar, or report-schema changes.

---

### Task 1: Trigger patterns and name resolution

**Files:**
- Modify: `screenplay_analyzer/pipeline.py` (new module-level `_IDENTITY_PATTERNS`, `_HEDGE_PATTERNS`, `_identity_parties(f)` helper near the other finalize guards, circa line 940-975)
- Test: `tests/test_accuracy_guards.py` (append)

**Interfaces:**
- Consumes: nothing (pure function of the finding dict).
- Produces: `_identity_parties(f: dict) -> tuple[str, str] | None` — the two resolved names or None. Task 2 consumes it.

- [ ] **Step 1: Write the failing test**

```python
def test_identity_parties_from_observation():
    from screenplay_analyzer import pipeline as P
    f = {"category": "character",
         "issue": "Protagonist Identity Ambiguity: Raj's role is unclear because he does not appear to be the 'Pen Guy'.",
         "observation": "The character labeled 'PEN_GUY' is a distinct entity not named Raj.",
         "severity": "high", "scene_refs": [1, 2, 3]}
    assert P._identity_parties(f) == ("RAJ", "PEN GUY")


def test_identity_single_name_returns_none():
    from screenplay_analyzer import pipeline as P
    assert P._identity_parties({"issue": "Rahul never appears after scene 4."}) is None
    assert P._identity_parties({"issue": "He never speaks to her."}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider -k "identity_parties or identity_single"`
Expected: FAIL with `AttributeError` (no such name on the module).

- [ ] **Step 3: Write minimal implementation**

```python
_IDENTITY_PATTERNS = [
    re.compile(r"\bis\s+not\b", re.I),
    re.compile(r"\bis\s+really\b", re.I),
    re.compile(r"\bdistinct\s+entit\w*\b", re.I),
    re.compile(r"\bsame\s+character\b", re.I),
    re.compile(r"\bdoes\s+not\s+appear\s+to\s+be\b", re.I),
    re.compile(r"\bnever\s+appears\b", re.I),
    re.compile(r"\bdoes\s+not\s+appear\b", re.I),
    re.compile(r"\bno\b.{0,20}\bpresent\b", re.I),
    re.compile(r"\babsent\b", re.I),
]
_HEDGE_PATTERNS = [
    # Affirmative hedging only: "does NOT appear to be X" asserts absence
    # (the trial-10 #12 shape) and must not veto — the lookbehind excludes
    # the negated form.
    re.compile(r"(?<!not\s)\bappears\s+to\s+be\b", re.I),
    re.compile(r"\bmay\s+be\b", re.I),
    re.compile(r"\bpossibly\b", re.I),
    re.compile(r"\breads?\s+as\b", re.I),
]
_NAME_RE = re.compile(r"[A-Z][\w\-']*(?:\s+[A-Z][\w\-']*)*")


def _identity_parties(f: dict) -> tuple[str, str] | None:
    """Two normalized names bound by an unhedged identity assertion in
    issue+observation, else None. Quotes are evidence, never the claim —
    names resolve from issue/observation text only."""
    from screenplay_parser.heuristics import normalize_character_name
    text = f"{f.get('issue') or ''} {f.get('observation') or ''}"
    if not any(p.search(text) for p in _IDENTITY_PATTERNS):
        return None
    if any(p.search(text) for p in _HEDGE_PATTERNS):
        return None
    seen = []
    for m in _NAME_RE.finditer(text):
        # Title-case sentence starts ("Protagonist Identity Ambiguity")
        # are not names: real cue names run to two words max. Possessives
        # ("Raj's") strip to their owner before comparing.
        words = m.group(0).split()
        if len(words) > 2:
            continue
        name = normalize_character_name(
            re.sub(r"['\u2019][sS]$", "", m.group(0))).upper()
        if not name or name in {"THE", "AND", "SCENE"}:
            continue
        if name not in seen:
            seen.append(name)
    if len(seen) < 2:
        return None
    return seen[0], seen[1]
```

Notes the implementer must honor: `import re` already exists at pipeline top (verify; add if missing). The hedge check runs on the same combined text so "appears to be X" vetoes even when another pattern matches. Pronouns never match `_NAME_RE` (lowercase), so pronoun-only text yields fewer than two names.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider -k "identity"`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/pipeline.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): identity-assertion trigger and name resolution"
```

### Task 2: Evidence ladder, `apply_identity_check`, pipeline wiring

**Files:**
- Modify: `screenplay_analyzer/pipeline.py` (`apply_identity_check(findings, doc)`, call after `apply_observation_check` in the 8g/8h area)
- Test: `tests/test_accuracy_guards.py` (append)

**Interfaces:**
- Consumes: Task 1's `_identity_parties(f)`; `demote_severity` from `screenplay_analyzer.feedback_filter` (same lazy import style as `apply_observation_check`); dialogue `Element.character` per scene; `find_scene_text(doc, n)` from `screenplay_parser.quotematch` (lazy import, codebase convention).
- Produces: flagged rows (`identity_uncertain: True`, one severity step down). Task 4 backtests them.

- [ ] **Step 1: Write the failing tests**

```python
def test_identity_uncertain_flagged_and_demoted():
    from screenplay_analyzer import pipeline as P
    rows = [{"category": "character",
             "issue": "Raj does not appear to be the Pen Guy.",
             "observation": "Pen Guy is a distinct entity not named Raj.",
             "severity": "high", "scene_refs": [2],
             "evidence_quote": "Nuvvu evaru ra?"}]
    P.apply_identity_check(rows, _TDoc())
    assert rows[0].get("identity_uncertain") is True
    assert rows[0]["severity"] == "medium"


def test_identity_with_dialogue_copresence_kept():
    """Both names speaking in one cited scene supports distinctness."""
    from screenplay_analyzer import pipeline as P
    rows = [{"category": "character",
             "issue": "Raj is not Pen Guy.",
             "observation": "Two speaking parts.",
             "severity": "medium", "scene_refs": [1],
             "evidence_quote": "Nuvvu evaru ra?"}]
    P.apply_identity_check(rows, _CopresentDoc())
    assert rows[0].get("identity_uncertain", False) is False
    assert rows[0]["severity"] == "medium"
```

`_TDoc` already exists in this file (used by the gloss tests — a doc whose scene 1 carries the fixture text). `_CopresentDoc` is new in this step: copy the `_TDoc` helper in-file and add dialogue elements with `.character` set to two distinct names in scene 1 (mirror how `test_voice_subtext.py` builds dialogue elements, or plain `types.SimpleNamespace(character=..., text=...)` if the check only reads those two attributes — check what the implementation reads before choosing).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider -k "identity_uncertain or copresence"`
Expected: FAIL with `AttributeError` (no `apply_identity_check`, no `_CopresentDoc` yet — write the helper in this step too, the function is what must fail).

- [ ] **Step 3: Write minimal implementation**

```python
def apply_identity_check(findings: list, doc) -> None:
    """Flag identity verdicts the text cannot settle (trial-10 #12):
    `identity_uncertain: True` plus one severity step down. Demote, never
    drop — uncertainty is not falsehood. Explicit equations and dialogue
    co-presence keep the row; everything else verifiable is out of scope
    for this check (pronouns, ref-less rows, missing docs)."""
    from .feedback_filter import demote_severity
    from .deterministic_utils import dialogue_lines_by_character  # only if needed; else read elements directly
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        parties = _identity_parties(f)
        if parties is None or doc is None:
            continue
        refs = [r for r in (f.get("scene_refs") or []) if isinstance(r, int)]
        if not refs:
            continue
        scenes = {s.scene_number: s for s in (doc.scenes or [])}
        if any(r not in scenes for r in refs):
            continue
        if _identity_proven(f, parties, [scenes[r] for r in sorted(refs)]):
            continue
        f["identity_uncertain"] = True
        demote_severity(f)
```

`_identity_proven(f, parties, scenes)` helper (same file): True when (a) an explicit equation element exists — a DIALOGUE element whose `.character` normalizes to one party and whose text names the other, or an ACTION element matching `calls|addresses|greets|names`, or a parenthetical `(as Y)` attached to X's cue/line, or a heading containing an `X=Y`/`X-AS-Y` form; or (b) both parties carry DIALOGUE elements (`.character` normalized) in one cited scene. Anything else returns False. Wire the call in `analyze()` directly after `apply_observation_check(result.findings, doc)` with a `# 8h`-style comment matching neighbors.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: PASS (whole file green).

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/pipeline.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): identity-uncertainty flag and demote"
```

### Task 3: Contradiction rung in the integrity gate

**Files:**
- Modify: `screenplay_analyzer/finding_integrity.py` (new `_identity_contradicted` beside `_praise_filed`, wired before the mismatch branch — contradictions reject; ordering: after `_deterministic_fp`, before `_category_mismatch`)
- Test: `tests/test_finding_integrity_gate.py` (append)

**Interfaces:**
- Consumes: Task 1's name/equation element definitions (same equation rule, opposite polarity); gate `Decision(i, "reject", reason, f)`; gate `run(findings, doc=None)` already accepts doc (absence work) — skip (no doc) when `doc is None`.
- Produces: withdrawn rows with reason `identity verdict contradicted by explicit equation in scene(s) N`.

- [ ] **Step 1: Write the failing test**

```python
def test_identity_claim_contradicted_by_equation_is_rejected():
    """Claim 'X is not Y' beside text addressing X as Y is provably
    false — withdraw, don't demote."""
    rows = [_f("Raj is not Pen Guy.", category="character", scenes=(2,),
               quote="Nuvvu evaru ra?",
               over={"observation": "Pen Guy answers when Raj calls him by name."})]
    res = FindingIntegrityGate().run(rows, doc=_EqDoc())
    assert res.summary["reject"] == 1
    assert "contradict" in res.of("reject")[0].reason
```

`_EqDoc` is new in this step: minimal stub with one scene (scene_number 2) whose elements include a DIALOGUE element with `.character == "RAJ"` and text naming PEN_GUY (reuse the `_f`/`_El` stub style already in this file — check its top helpers first; mirror them).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_finding_integrity_gate.py -q -p no:cacheprovider -k "contradicted"`
Expected: FAIL (no such method/branch).

- [ ] **Step 3: Write minimal implementation**

New method `_identity_contradicted(self, f, doc)` returning a reason string or None: resolve parties with the Task-1 rule (import it: `from .pipeline import _identity_parties` — lazy, inside the method; pipeline never imports the gate at module load, so no cycle — verify with `python -c "import screenplay_analyzer.finding_integrity"`), then check the explicit-equation rule against the verdict polarity (equation supports the OPPOSITE of the claim). Wire into `run()` after the `_deterministic_fp` branch, guarded by `doc is not None` (pipeline always passes doc; direct callers without one keep current behavior).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_finding_integrity_gate.py -q -p no:cacheprovider`
Expected: PASS (whole file green).

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/finding_integrity.py tests/test_finding_integrity_gate.py
git commit -m "feat(accuracy): reject identity verdicts contradicted by text"
```

### Task 4: Display chip, backtest, suite, map, notes, commit

**Files:**
- Modify: `screenplay_studio/webapp/app.js` (rowFlags area circa line 4483: `identity_uncertain` chip mirroring the contested block, text `identity?`, title `The script does not settle this identity verdict — read the observation before acting on it`)
- Modify: `screenplay_studio/webapp/style.css` (`.row-flag-identity` beside `.row-flag-contested`, circa line 1932; same chip geometry, distinct but non-alarm color — mirror the contested declaration, do not invent new tokens)
- Modify: `docs/CODEBASE_MAP.md` (pipeline row: append `apply_identity_check`; finding_integrity row: append contradiction rung)
- Modify: `NOTES.md` (append backtest outcome entry)
- Test: no new test files (backtest procedure below + suite)

**Interfaces:**
- Consumes: Tasks 1–3 (working check, wired gate + pipeline + chip).
- Produces: merged, committed, green tree.

**Deviation from the spec, recorded:** the spec's §2 says "and in deep-card flag space." There is no deep-card flag surface — contested/ungrounded render only in Fix Queue rows (app.js:4483). Creating one expands scope; this task ships Fix Queue parity only.

- [ ] **Step 1: Run the backtest procedure**

```bash
python -c "import sys,glob,json; sys.path.insert(0,r'E:\screen_play_astra'); from screenplay_parser.models import ScriptDocument; from screenplay_analyzer import pipeline as P; print([(p.split('e2e_range')[-1],[(i,(f.get('issue') or '')[:70]) for i,f in enumerate(json.load(open(p,encoding='utf-8'))['findings']) if (lambda d: (P.apply_identity_check([f], d), f.get('identity_uncertain'))[1] if d else None)(__import__('os').path.exists(p.replace('report.findings.json','parsed.json')) and ScriptDocument.load(p.replace('report.findings.json','parsed.json')) or None)]) for p in sorted(glob.glob(r'C:\Users\Avinash-Pro\AppData\Local\Temp\opencode\e2e_range\accuracy*\*\report.findings.json'))])"
```

Expected: fires only on trial-10 #12 shapes. Any firing on a finding scored SOLID in NOTES.md audits BLOCKS this task: narrow the Task-1 patterns and re-run before proceeding. (Note: `apply_identity_check` mutates a one-row list in place — the printed flag read is the verdict; the throwaway list is discarded.)

- [ ] **Step 2: Run ruff, node check, and the full suite**

Run: `python -m ruff check screenplay_analyzer/pipeline.py screenplay_analyzer/finding_integrity.py screenplay_studio/webapp/app.js tests/test_accuracy_guards.py tests/test_finding_integrity_gate.py`
Expected: All checks passed.

Run: `node --check screenplay_studio/webapp/app.js`
Expected: no output (clean parse).

Run: `python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/e2e_browser_readiness_gate.py`
Expected: all passed, 3 skipped.

- [ ] **Step 3: Update map and notes, commit**

`docs/CODEBASE_MAP.md` pipeline row: append `apply_identity_check`. finding_integrity row: append contradiction rung. `NOTES.md`: append the backtest outcome (firing rows, solid-hit count, suite tally) to the trial-11 section end.

```bash
git add docs/CODEBASE_MAP.md NOTES.md screenplay_studio/webapp/app.js screenplay_studio/webapp/style.css
git commit -m "feat(accuracy): identity-uncertainty flag display and backtest"
```
