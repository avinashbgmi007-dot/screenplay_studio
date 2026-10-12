# Absence-Falsification Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Withdraw integrity-gate findings whose absolute absence claims are falsified by presence in the parsed document.

**Architecture:** One new `FindingIntegrityGate` method plus lexicons, following the existing `_inverted`/`_praise_filed` narrow-regex contract; `run()` gains an optional `doc` (default `None` preserves every existing caller); the pipeline passes its `doc` at the 8d call site.

**Tech Stack:** Python 3, stdlib `re` only, existing `screenplay_parser` models (`characters_present`, dialogue `Element.character`), `quotematch.find_scene_text`, setup-payoff `_content_terms`/`_terms_in_scenes` reused via lazy import.

## Global Constraints

- Narrow-rule contract: fire only on positive proof of presence; any doubt keeps the row.
- Quotes never scanned (verbatim script text).
- Withdrawals preserve the full row; findings + withdrawals always equals the pre-gate list.
- `ruff check` clean on touched files; full suite green before commit.
- No new dependencies, no prompt/grammar/report/UI changes.

---

### Task 1: Lexicons and the `_absence_falsified` method

**Files:**
- Modify: `screenplay_analyzer/finding_integrity.py` (lexicon block after `DEFECT_MARK`, circa line 160; new method after `_praise_filed`)
- Test: `tests/test_finding_integrity_gate.py` (append new test functions)

**Interfaces:**
- Consumes: `PRAISE`/`DEFECT_MARK` style module lexicons; `norm()` helper; lazy `from screenplay_analyzer.setup_payoff import _content_terms, _terms_in_scenes` and `from screenplay_parser.quotematch import find_scene_text` inside the method (codebase lazy-import convention — no module-load cross-package imports).
- Produces: `FindingIntegrityGate._absence_falsified(self, f: dict, doc) -> str | None` returning a reason string on falsification, `None` otherwise (including when `doc` is `None`). Task 2 wires it into `run()`.

- [ ] **Step 1: Write the failing test (non-recurrence fires)**

```python
def test_falsified_non_recurrence_is_rejected():
    """Trial-10 #4 shape: 'do not recur' while the object recurs."""
    from screenplay_parser import parse_fountain
    import os, tempfile
    text = ("Title: T\nAuthor: T\n\nINT. ROOM - NIGHT\n\n"
            "A gun lies on the floor here.\n\nCUT TO:\n\n"
            "INT. HALL - DAY\n\nHe picks up the gun again.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    rows = [_f("The gun does not recur or get referenced later.",
               category="dialogue", scenes=(1,),
               quote="A gun lies on the floor here.")]
    res = FindingIntegrityGate().run(rows, doc=doc)
    assert res.summary["reject"] == 1
    assert "falsified" in res.of("reject")[0].reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_finding_integrity_gate.py::test_falsified_non_recurrence_is_rejected -q -p no:cacheprovider`
Expected: FAIL with `TypeError` (run takes no `doc`) or `AttributeError` (`_absence_falsified` missing).

- [ ] **Step 3: Write minimal implementation (lexicons + method, no wiring)**

```python
# "absolute absence, falsified by presence" — trial-10 #4 ("objects do
# not recur" while the pen recurs two scenes later). Same narrow
# contract as ABSENCE/PRAISE above: unhedged phrasing required, positive
# proof required, quotes never scanned.
ABSENCE_CLAIM = re.compile(
    r"\bdo\s+not\s+recur\b|\bnever\s+(referenced|mentioned|seen|reappear"
    r"s?|recur\w*|addressed)\b"
    r"|\bno\s+dialogue\b|\bnever\s+speaks?\b|\bno\s+action\s+lines?\b"
    r"|\bno\s+confrontation\b|\babsent\s+from\b",
    re.I,
)
HEDGE = re.compile(
    r"\b(appears?|seems?|may|might|arguably|suggests?|possibly|likely)\b",
    re.I,
)
```

```python
    # -- 4c. absence claim falsified by presence ---------------------------
    def _absence_falsified(self, f: dict, doc) -> str | None:
        issue = f.get("issue") or ""
        if doc is None or not ABSENCE_CLAIM.search(issue):
            return None
        text = f"{issue} {f.get('observation') or ''}"
        if HEDGE.search(text) or DEFECT_MARK.search(text):
            return None
        return None  # Task 2 note: presence checks land here
```

Note: this step lands the gating skeleton only; the presence checks
arrive in Task 2. The test from Step 1 still fails (returns None).

- [ ] **Step 4: Run test to verify it still fails (skeleton returns None)**

Run: same pytest invocation as Step 2.
Expected: FAIL with `assert res.summary["reject"] == 1` (got keep).

- [ ] **Step 5: Commit the skeleton**

```bash
git add screenplay_analyzer/finding_integrity.py tests/test_finding_integrity_gate.py
git commit -m "feat(accuracy): absence-claim lexicons and check skeleton"
```

### Task 2: Presence checks, `run()` wiring, pipeline call site

**Files:**
- Modify: `screenplay_analyzer/finding_integrity.py` (`_absence_falsified` body, `run(self, findings, doc=None)` signature, loop wiring after the `_praise_filed` branch)
- Modify: `screenplay_analyzer/pipeline.py` (8d call site passes `doc=doc`)
- Test: `tests/test_finding_integrity_gate.py` (missing-lines, missing-beats, conservative siblings)

**Interfaces:**
- Consumes: Task 1's `_absence_falsified(self, f, doc)` signature and lexicons; `doc.scenes` with `.scene_number`, `Scene.characters_present`, dialogue `Element.character`; `find_scene_text(doc, n)` returning `str | None`.
- Produces: working end-to-end withdrawal; reason format `absence claim falsified by presence in scene(s) N`. Task 3 backtests it.

- [ ] **Step 1: Write the failing tests (missing lines + hedged keep)**

```python
def test_falsified_missing_lines_is_rejected():
    """'No dialogue for Raj' while Raj has a cue in range."""
    from screenplay_parser import parse_fountain
    import os, tempfile
    text = ("Title: T\nAuthor: T\n\nINT. ROOM - NIGHT\n\n"
            "RAJ\nI am staying right here.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    rows = [_f("There is no dialogue for Raj in this scene.",
               category="dialogue", scenes=(1,))]
    res = FindingIntegrityGate().run(rows, doc=doc)
    assert res.summary["reject"] == 1


def test_hedged_absence_is_NOT_rejected():
    """A careful model is never punished for hedging."""
    rows = [_f("The gun appears to never recur after this scene.",
               category="dialogue", scenes=(1,))]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_finding_integrity_gate.py -q -p no:cacheprovider -k "falsified_missing or hedged_absence"`
Expected: FAIL on the first (skeleton returns None); PASS on the second.

- [ ] **Step 3: Implement presence checks and wiring**

Replace the `return None  # Task 2 note` line with the three checks (non-recurrence via lazy-imported `_content_terms`/`_terms_in_scenes` over scenes after the max cited ref; missing lines via normalized name match against `characters_present` plus dialogue-element `.character` in cited range; missing beats via term search in cited range). Out-of-range refs and pronoun subjects (`he/she/they`) return `None`. On a hit return `f"absence claim falsified by presence in scene(s) {at}"`.

Wire into `run()`:

```python
    def run(self, findings: list[dict], doc=None) -> GateResult:
```

and after the `_praise_filed` branch:

```python
            falsified = self._absence_falsified(f, doc)
            if falsified:
                res.decisions.append(Decision(i, "reject", falsified, f))
                continue
```

Pipeline 8d call site: `gate_res = FindingIntegrityGate().run(result.findings, doc=doc)`.

- [ ] **Step 4: Run the gate tests green**

Run: `python -m pytest tests/test_finding_integrity_gate.py -q -p no:cacheprovider`
Expected: all PASS (25 existing + new).

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/finding_integrity.py screenplay_analyzer/pipeline.py tests/test_finding_integrity_gate.py
git commit -m "feat(accuracy): withdraw absence claims falsified by presence"
```

### Task 3: 19-report backtest, full suite, map, notes, commit

**Files:**
- Modify: `docs/CODEBASE_MAP.md` (finding_integrity row: add absence-falsification)
- Modify: `NOTES.md` (append trial verdict entry)
- Test: no new test files (backtest is a procedure, recorded in NOTES)

**Interfaces:**
- Consumes: Tasks 1–2 (working check); 19 stored reports under `C:\Users\Avinash-Pro\AppData\Local\Temp\opencode\e2e_range\accuracy*\*\report.findings.json` with parsed docs beside them where available (accuracy8/10/11 have `parsed.json`; reports without a stored doc are skipped, never reconstructed).
- Produces: a merged, committed, green tree.

- [ ] **Step 1: Run the backtest procedure**

```bash
python -c "import sys,glob,json; sys.path.insert(0,r'E:\screen_play_astra'); from screenplay_parser.models import ScriptDocument; from screenplay_analyzer.finding_integrity import FindingIntegrityGate; g=FindingIntegrityGate(); print([(p.split('e2e_range')[-1],[(i,(f.get('issue') or '')[:70]) for i,f in enumerate(json.load(open(p,encoding='utf-8'))['findings']) if (lambda d: g._absence_falsified(f,d) if d else None)(__import__('os').path.exists(p.replace('report.findings.json','parsed.json')) and ScriptDocument.load(p.replace('report.findings.json','parsed.json')) or None)]) for p in sorted(glob.glob(r'C:\Users\Avinash-Pro\AppData\Local\Temp\opencode\e2e_range\accuracy*\*\report.findings.json'))])"
```

Expected: fires only on #4-shaped rows. Any firing on a finding scored solid in NOTES audits BLOCKS this task: narrow the regexes (Task 1) and re-run before proceeding.

- [ ] **Step 2: Run ruff and the full suite**

Run: `python -m ruff check screenplay_analyzer/finding_integrity.py screenplay_analyzer/pipeline.py tests/test_finding_integrity_gate.py`
Expected: All checks passed.

Run: `python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/e2e_browser_readiness_gate.py`
Expected: all passed (baseline 2217), 3 skipped.

- [ ] **Step 3: Update map and notes, commit**

`docs/CODEBASE_MAP.md` finding_integrity row: append absence-falsification to the method list. `NOTES.md`: append the backtest outcome (firing rows, solid-hit count, suite tally).

```bash
git add docs/CODEBASE_MAP.md NOTES.md
git commit -m "docs: absence-falsification backtest outcome"
```
