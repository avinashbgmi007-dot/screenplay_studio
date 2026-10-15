# Findings Guardrails (Accuracy Kit A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demote (never delete) weak findings so the Fix Queue default view holds only grounded notes.

**Architecture:** All Python rules land in the finalize chain in `pipeline.py::analyze` (after step 8e ~line 1451, before `verification_summary` ~line 1453, so counts describe delivered rows); language patterns extend the existing `feedback_filter.py`; the desk filter extends the ONE predicate `inFindingFilter` (`app.js:7610`) with a dismissed-style toggle.

**Tech Stack:** Python 3 stdlib + pytest; vanilla JS with `node --test tests/js/`; Playwright e2e for the desk filter.

## Global Constraints

- No cross-package imports at module load (lazy inside functions, per AGENTS.md).
- Flag-don't-drop: no task deletes a finding; demotion only.
- Console output UTF-8; repo test command `python -m pytest tests/`.
- Full suite green after every task.

---

### Task 1: Evidence floor in finalize (8f)

**Files:**
- Modify: `screenplay_analyzer/pipeline.py:1451-1453` (insert 8f block)
- Test: `tests/test_accuracy_guards.py` (new file)

**Interfaces:**
- Consumes: `result.findings` rows with `evidence_quote` / `observation` keys (set by passes + `observation_pass.py`).
- Produces: rows gain `ungrounded: True` + forced `severity: "low"` when both missing; everything else untouched.

- [ ] **Step 1: Write the failing test**

```python
"""Kit A guardrails: weak findings are demoted, never deleted."""
from screenplay_analyzer.pipeline import AnalysisResult


def _result_with(*rows):
    # Plain dataclass, no validation on construct — doc=None is fine for
    # tests that only touch findings (mirrors test_generation_timeout.py).
    r = AnalysisResult(doc=None)
    r.findings = [dict(f) for f in rows]
    return r


def test_quoteless_observationless_row_is_flagged_not_dropped():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "scene_function", "issue": "Scene 21 provides a neat resolution.",
         "severity": "medium", "scene_refs": [21],
         "evidence_quote": None, "observation": None},
        {"category": "dialogue", "issue": "On-the-nose line.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "Who cares!", "observation": None},
    )
    P.apply_evidence_floor(r)
    assert len(r.findings) == 2, "flag-don't-drop: demote, never delete"
    assert r.findings[0].get("ungrounded") is True
    assert r.findings[0]["severity"] == "low"
    assert r.findings[1].get("ungrounded", False) is False
    assert r.findings[1]["severity"] == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'apply_evidence_floor'"

- [ ] **Step 3: Write minimal implementation**

In `screenplay_analyzer/pipeline.py`, after the 8e observation-pass block ends (line ~1451, `result.errors.append(f"Observation pass skipped: {e}")` branch close) and before `result.verification = verification_summary(result.findings)` (~line 1453), insert:

```python
    # 8f. evidence floor (accuracy kit A): a finding with neither a quote
    # nor an observation is demoted, never deleted — flag-don't-drop holds,
    # but the Fix Queue default view must not present it as a grounded note.
    apply_evidence_floor(result.findings)
```

Module level (near `evidence_depth`, ~line 874):

```python
def apply_evidence_floor(findings: list) -> None:
    """Demote ungrounded rows in place: severity forced low plus
    `ungrounded: True`. Rows with a quote or an observation are untouched."""
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        if not f.get("evidence_quote") and not f.get("observation"):
            f["ungrounded"] = True
            f["severity"] = "low"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/pipeline.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): evidence floor demotes ungrounded findings"
```

### Task 2: Refutation adjudication

**Files:**
- Modify: `screenplay_analyzer/feedback_filter.py` (new patterns + `is_refuted`), `screenplay_analyzer/pipeline.py` (call in 8f)
- Test: `tests/test_accuracy_guards.py` (append)

**Interfaces:**
- Consumes: finding `issue` + `observation` strings.
- Produces: `contested: True` + one-step severity demotion (high→medium→low) when the observation rebuts the note.

- [ ] **Step 1: Write the failing test**

```python
def test_refuting_observation_demotes_one_step():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "character", "issue": "Supporting character lacks motivation.",
         "severity": "high", "scene_refs": [3],
         "evidence_quote": "Who asked you?",
         "observation": "The note claims no motivation; however, the script explicitly shows a direct confrontation."},
    )
    P.apply_evidence_floor(r)
    assert r.findings[0].get("contested") is True
    assert r.findings[0]["severity"] == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: FAIL on missing `contested`

- [ ] **Step 3: Write minimal implementation**

In `screenplay_analyzer/feedback_filter.py`, append:

```python
# --- patterns where the observation rebuts the note (accuracy kit A) ---
_CONTRADICTION_PATTERNS = [
    re.compile(r"\bhowever\b", re.I),
    re.compile(r"\bactually\b.{0,30}\b(not|no)\b", re.I),
    re.compile(r"\bcontradicts?\b", re.I),
    re.compile(r"\bno evidence\b", re.I),
    re.compile(r"\bclaims?\b.{0,30}\b(but|yet)\b", re.I),
]

_SEVERITY_LADDER = ("low", "medium", "high")


def is_refuted(finding: dict) -> bool:
    """True when the finding's own observation rebuts its note. Checks the
    observation only — the issue is the claim under test, never the judge."""
    if not isinstance(finding, dict):
        return False
    return _matches_any(str(finding.get("observation") or ""), _CONTRADICTION_PATTERNS)


def demote_contested(finding: dict) -> None:
    sev = str(finding.get("severity") or "low").lower()
    if sev in _SEVERITY_LADDER[1:]:
        finding["severity"] = _SEVERITY_LADDER[_SEVERITY_LADDER.index(sev) - 1]
    finding["contested"] = True
```

In `apply_evidence_floor`, after the ungrounded branch, add:

```python
        from .feedback_filter import is_refuted, demote_contested
        if not f.get("ungrounded") and is_refuted(f):
            demote_contested(f)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accuracy_guards.py tests/test_feedback_filter.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/feedback_filter.py screenplay_analyzer/pipeline.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): refuting observations demote one step"
```

### Task 3: Short-form framework skip

**Files:**
- Modify: `screenplay_analyzer/pipeline.py` (markers + gate in 8f)
- Test: `tests/test_accuracy_guards.py` (append)

**Interfaces:**
- Consumes: `doc.estimated_page_count`, finding `category`/`issue`.
- Produces: `form_mismatch: True` + forced low severity for framework demands on shorts.

**Note (deviation from spec §A3, verified 2026-10-11):** model findings carry
`check_id: None`, so gating cannot key on check ids. It keys on category plus
marker phrases instead, and demotes rather than skips (flag-don't-drop).

- [ ] **Step 1: Write the failing test**

```python
SHORT_SCRIPT_PAGES = 6.0


def test_framework_demand_on_short_demoted_with_marker():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "structure", "issue": "No midpoint shift from reaction to action.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "INT. SAME APARTMENT - LATE EVENING", "observation": None},
    )
    P.apply_short_form_gate(r.findings, page_count=SHORT_SCRIPT_PAGES)
    assert r.findings[0].get("form_mismatch") is True
    assert r.findings[0]["severity"] == "low"


def test_long_script_untouched():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "structure", "issue": "No midpoint shift from reaction to action.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "INT. SAME APARTMENT - LATE EVENING", "observation": None},
    )
    P.apply_short_form_gate(r.findings, page_count=28.0)
    assert r.findings[0].get("form_mismatch", False) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'apply_short_form_gate'"

- [ ] **Step 3: Write minimal implementation**

Module level in `pipeline.py`:

```python
SHORT_FORM_PAGE_LIMIT = 15.0
SHORT_FORM_SKIP_MARKERS = frozenset({
    "three-act", "three act", "midpoint", "mid-point", "second act",
    "act two", "climax", "second half",
})
SHORT_FORM_SKIP_CATEGORIES = frozenset({"structure", "genre"})


def apply_short_form_gate(findings: list, page_count) -> None:
    """Demote framework demands a short cannot meet (demote, never drop).
    Model findings carry no check_id, so this keys on category plus marker
    phrases in the issue text."""
    try:
        pages = float(page_count or 0)
    except (TypeError, ValueError):
        return
    if pages <= 0 or pages >= SHORT_FORM_PAGE_LIMIT:
        return
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        if str(f.get("category") or "") not in SHORT_FORM_SKIP_CATEGORIES:
            continue
        if any(m in str(f.get("issue") or "").lower() for m in SHORT_FORM_SKIP_MARKERS):
            f["form_mismatch"] = True
            f["severity"] = "low"
```

Call it in 8f right after `apply_evidence_floor(result.findings)`:

```python
    apply_short_form_gate(result.findings, getattr(doc, "estimated_page_count", None))
```

(Spec deviation recorded: check-id keying replaced — model rows have `check_id: None`, verified on both trial reports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/pipeline.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): short-form framework demands demoted"
```

### Task 4: Language-consistency extension

**Files:**
- Modify: `screenplay_analyzer/feedback_filter.py` (new patterns)
- Test: `tests/test_accuracy_guards.py` (append; existing `tests/test_feedback_filter.py` must stay green)

**Interfaces:**
- Consumes: finding issue + why_it_matters via existing `is_non_writing_feedback`.
- Produces: trial items shaped like "untranslated foreign language obscures meaning" now match and are filtered.

- [ ] **Step 1: Write the failing test**

```python
def test_untranslated_barrier_finding_is_filtered():
    from screenplay_analyzer.feedback_filter import is_non_writing_feedback
    assert is_non_writing_feedback({
        "issue": "Dialogue relies on untranslated foreign language that obscures meaning.",
        "why_it_matters": "The audience cannot follow the stakes without translation.",
    }) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: FAIL (False is not True)

- [ ] **Step 3: Write minimal implementation**

Append to `_SUBTITLE_PATTERNS` in `feedback_filter.py`:

```python
    re.compile(r"untranslated", re.I),
    re.compile(r"(obscures|blocks|barrier to) (meaning|understanding)", re.I),
    re.compile(r"mix(es|ed|ing) languages without", re.I),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accuracy_guards.py tests/test_feedback_filter.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/feedback_filter.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): filter untranslated-barrier meta-findings"
```

### Task 5: Absence ban plus caps

**Files:**
- Modify: `screenplay_analyzer/pipeline.py` (8f additions)
- Test: `tests/test_accuracy_guards.py` (append)

**Interfaces:**
- Consumes: finding issue text, category, scene_refs, doc page count.
- Produces: absence rows dropped pre-delivery (they are non-findings, not writer notes — the one exception to demote-only, matching the existing step-8 filter precedent); over-cap rows demoted to low with `capped: True`.

- [ ] **Step 1: Write the failing test**

```python
def test_absence_rows_dropped_and_caps_demote():
    from screenplay_analyzer import pipeline as P
    rows = [
        {"category": "dialogue", "issue": "N/A - No dialogue present to evaluate.",
         "severity": "low", "scene_refs": [5],
         "evidence_quote": None, "observation": "Scene 5 has no dialogue."},
    ]
    rows += [
        {"category": "character", "issue": f"Protagonist lacks trait {i}.",
         "severity": "high", "scene_refs": [1],
         "evidence_quote": "He enters.", "observation": "Enters quietly."}
        for i in range(9)
    ]
    P.apply_absence_and_caps(rows, page_count=6.0)
    assert not [f for f in rows if (f.get("issue") or "").strip().lower().startswith("n/a")], \
        "absence is not a finding"
    kept = [f for f in rows if f.get("category") == "character"]
    assert sum(1 for f in kept if f.get("capped")) >= 3, "same-anchor pileup demoted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'apply_absence_and_caps'"

- [ ] **Step 3: Write minimal implementation**

```python
_ABSENCE_RE = None  # compiled lazily to keep module import light
CATEGORY_CAPS_SHORT = {"character": 6, "dialogue": 8, "scene_function": 6}
CATEGORY_CAPS_LONG = {"character": 12, "dialogue": 20, "scene_function": 14}


def apply_absence_and_caps(findings: list, page_count) -> None:
    """Drop absence rows (non-findings, same precedent as step-8 filter);
    demote same-anchor pileups past the per-category cap. Mutates in place."""
    import re
    kept = [f for f in (findings or [])
            if isinstance(f, dict)
            and not re.match(r"\s*n/a\b", str(f.get("issue") or ""), re.I)]
    findings[:] = kept
    try:
        short = float(page_count or 0) < SHORT_FORM_PAGE_LIMIT
    except (TypeError, ValueError):
        short = False
    caps = CATEGORY_CAPS_SHORT if short else CATEGORY_CAPS_LONG
    seen_anchors: dict = {}
    for f in findings:
        key = (str(f.get("category") or ""),
               tuple(f.get("scene_refs") or []))
        seen_anchors[key] = seen_anchors.get(key, 0) + 1
        cap = caps.get(str(f.get("category") or ""))
        if cap is not None and seen_anchors[key] > cap:
            f["capped"] = True
            f["severity"] = "low"
```

Call in 8f after the short-form gate. Caps initial values from trial counts
(gunpen character 10 on 6pp); tuned by the trial re-run in Task 7.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_accuracy_guards.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/pipeline.py tests/test_accuracy_guards.py
git commit -m "feat(accuracy): absence ban plus per-category caps"
```

### Task 6: Desk hides ungrounded by default

**Files:**
- Modify: `screenplay_studio/webapp_server.py` (`_fixqueue_items` allowlist ~line 2570), `screenplay_studio/webapp/app.js` (`inFindingFilter` ~line 7610 + dismissed-style toggle near ~line 4401)
- Test: `tests/e2e_browser_ungrounded_filter.py` (new browser suite)

**Interfaces:**
- Consumes: fixqueue rows carrying `ungrounded`; `state.fixQueueShowUngrounded` (default false).
- Produces: default queue hides ungrounded; toggle shows them; counts via the same `queueCounts` path.

- [ ] **Step 1: Write the failing test**

New file `tests/e2e_browser_ungrounded_filter.py`, following the
`tests/e2e_browser_delivery_contract.py` plant pattern (boot demo studio via
`tests/e2e_browser_common.py`, plant one finding row with `ungrounded: True`
into the analyzed report, open the Evidence Fix Queue lens):

```python
"""Ungrounded rows hide by default and return behind an explicit toggle."""
# (harness imports mirror e2e_browser_delivery_contract.py)
CHECKS = []


def check(name, cond, detail=""):
    assert cond, f"{name}: {detail}"
    CHECKS.append(name)
```

Suite body: plant row → open Fix Queue → assert row absent and header counts
exclude it → enable the ungrounded toggle → assert row present → done. (Exact
plant helper names taken from `e2e_browser_common.py`: `start_studio`,
`open_dock_section`, `Checks.ok` — read that file's current helpers when
implementing; the delivery-contract suite is the template.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/e2e_browser_ungrounded_filter.py`
Expected: FAIL (no toggle; row shown)

- [ ] **Step 3: Write minimal implementation**

Server (`webapp_server.py::_fixqueue_items`, after `"observation": f.get("observation"),` ~line 2609):

```python
            # Accuracy kit A: the desk default-hides ungrounded rows, so the
            # flag must ride the row like evidence_quote does.
            "ungrounded": bool(f.get("ungrounded")),
            "contested": bool(f.get("contested")),
```

Client (`app.js::inFindingFilter`, after the scene clause ~line 7619):

```js
  if (f && f.ungrounded && !state.fixQueueShowUngrounded) return false;
```

Plus a toggle mirroring the dismissed toggle (`app.js` ~line 4401-4412):
state flag default false, button label `Show ungrounded (N)`, same
`reloadFixQueue` + `renderManuscript` refresh.

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/e2e_browser_ungrounded_filter.py` then `node --test tests/js/`
Expected: suite PASS, JS green

- [ ] **Step 5: Commit**

```bash
git add screenplay_studio/webapp_server.py screenplay_studio/webapp/app.js tests/e2e_browser_ungrounded_filter.py
git commit -m "feat(accuracy): fix queue default-hides ungrounded rows"
```

### Task 7: Trial re-run acceptance

**Files:** none (measurement only; values feed cap tuning in Task 5 if needed).

- [ ] **Step 1: Re-run both trial reports through the new finalize**

Run: `python -m pytest tests/ -q -p no:cacheprovider` (full suite must stay green)
- [ ] **Step 2: Assert acceptance numbers on a live re-analyze of the gunpen fixture**

Run a real-model analyze of `tests/fixtures/pain_tenglish.fountain` (small, fast)
and assert: zero high-severity ungrounded findings; zero `contested` rows whose
observation does not contain a contradiction marker.
- [ ] **Step 3: Record numbers in NOTES.md** (counts only, no code)
- [ ] **Step 4: Commit the NOTES entry**

```bash
git add NOTES.md
git commit -m "docs: accuracy-kit-A acceptance numbers"
```
