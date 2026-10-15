# Ledger Precision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every kept setup-payoff verdict is mechanically checked against the script text, and true fold-in rows carry a real setup quote.

**Architecture:** A pure post-pass in `setup_payoff.py` (`adjudicate_ledger`) runs between the model call and the fold-in; quote extraction reuses the verifier's tested primitives; the pipeline hook is two lines; severity and dedup paths are untouched.

**Tech Stack:** Python 3 stdlib + pytest; `difflib` only where the verifier primitives do not reach.

## Global Constraints

- Asymmetric by design: text recurrence proves payoff (flip to paid), absence proves nothing (keep the model verdict). The checker exonerates but never convicts.
- Flag-don't-drop: no entry is ever removed; worst case keeps its model verdict plus flags.
- No cross-package imports at module load (lazy inside functions, per AGENTS.md).
- No new model calls. Full suite green after every task.

---

### Task 1: Adjudicate ledger verdicts against the text

**Files:**
- Modify: `screenplay_analyzer/setup_payoff.py` (new `adjudicate_ledger` + `STOPWORDS` reuse)
- Modify: `screenplay_analyzer/pipeline.py` (~line 1404, hook between the ledger run and the fold-in)
- Test: `tests/test_setup_payoff.py` (append)

**Interfaces:**
- Consumes: ledger entries `{setup, kind, setup_scenes, payoff_scenes, status, note}` + parsed `doc`.
- Produces: same entries plus `verified: bool` and `verify_note: str`; status flips dangling/abandoned to paid only on positive term recurrence, plus `setup_ungrounded: True` / `payoff_unproven: True` markers where due.

- [ ] **Step 1: Write the failing tests**

```python
def _doc_two_scenes():
    return _parse(
        "Title: T\nAuthor: T\n\n"
        "INT. ROOM - NIGHT\n\n"
        "MARA holds a small CIGAR, turning it over.\n\n"
        "CUT TO:\n\n"
        "INT. HALL - DAY\n\n"
        "The CIGAR sits on the table, untouched.\n")


def test_false_dangling_flips_to_paid_with_proof():
    from screenplay_analyzer.setup_payoff import adjudicate_ledger
    entries = adjudicate_ledger([{
        "setup": "The cigar", "kind": "object",
        "setup_scenes": [1], "payoff_scenes": None,
        "status": "dangling", "note": "Never lit."}], _doc_two_scenes())
    assert entries[0]["status"] == "paid"
    assert entries[0]["verified"] is True
    assert "2" in entries[0]["verify_note"]


def test_true_dangling_keeps_verdict():
    from screenplay_analyzer.setup_payoff import adjudicate_ledger
    entries = adjudicate_ledger([{
        "setup": "The moonstone amulet", "kind": "object",
        "setup_scenes": [1], "payoff_scenes": None,
        "status": "dangling", "note": "Never seen again."}], _doc_two_scenes())
    assert entries[0]["status"] == "dangling"
    assert entries[0]["verified"] is False


def test_setup_absent_from_setup_scenes_is_marked():
    from screenplay_analyzer.setup_payoff import adjudicate_ledger
    entries = adjudicate_ledger([{
        "setup": "The moonstone amulet", "kind": "object",
        "setup_scenes": [1], "payoff_scenes": None,
        "status": "paid", "note": "Lands."}], _doc_two_scenes())
    assert entries[0].get("setup_ungrounded") is True
    assert entries[0]["status"] == "paid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup_payoff.py -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'adjudicate_ledger'" (3 failures)

- [ ] **Step 3: Write minimal implementation**

In `screenplay_analyzer/setup_payoff.py`, append (imports of verifier
primitives are lazy, inside the function):

```python
def _content_terms(text: str) -> set:
    import re
    from screenplay_analyzer.verifier import _STOPWORDS
    return {w for w in re.sub(r"[^a-z0-9 ]", " ",
            str(text or "").lower()).split()
            if w not in _STOPWORDS}


def _terms_in_scenes(terms: set, doc, scenes: list) -> tuple[bool, int | None]:
    """True + first matching scene when a strict majority of terms lands in
    one cited scene (windowed fuzzy first, token overlap second)."""
    from screenplay_analyzer.verifier import (
        _normalize, _best_fuzzy_match, _token_overlap,
        FUZZY_MATCH_THRESHOLD,
    )
    from screenplay_parser.quotematch import find_scene_text
    for n in scenes or []:
        text = find_scene_text(doc, n)
        if not text:
            continue
        tnorm = _normalize(text)
        joined = " ".join(sorted(terms))
        if _best_fuzzy_match(_normalize(joined), tnorm) >= FUZZY_MATCH_THRESHOLD:
            return True, n
        if _token_overlap(" ".join(sorted(terms)), tnorm) >= 0.5:
            return True, n
    return False, None


def adjudicate_ledger(entries: list, doc) -> list:
    """Mechanical re-read of every model verdict (accuracy follow-up).
    Asymmetric: recurrence proves payoff (flip + note), absence proves
    nothing (keep + mark). Mutates entries in place, returns them."""
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        terms = _content_terms(e.get("setup"))
        setup_ok, setup_at = _terms_in_scenes(
            terms, doc, e.get("setup_scenes") or [])
        if terms and not setup_ok:
            e["setup_ungrounded"] = True
            e["verified"] = False
            e["verify_note"] = "setup terms not found in the cited setup scenes"
            continue
        if e.get("status") == "paid":
            ok, at = _terms_in_scenes(terms, doc, e.get("payoff_scenes") or [])
            e["verified"] = bool(ok)
            e["verify_note"] = (
                f"payoff terms recur in scene {at}" if ok
                else "payoff scenes carry no matching terms (kept: absence proves nothing)")
            if not ok:
                e["payoff_unproven"] = True
        elif e.get("status") in ("dangling", "abandoned"):
            later = [s.scene_number for s in (doc.scenes or [])
                     if s.scene_number not in (e.get("setup_scenes") or [])]
            ok, at = _terms_in_scenes(terms, doc, later)
            if ok:
                e["status"] = "paid"
                e["payoff_scenes"] = [at]
                e["verified"] = True
                e["verify_note"] = f"setup terms recur in scene {at} — paid, not {e.get('status')}"
            else:
                e["verified"] = False
                e["verify_note"] = "no later recurrence found (kept: absence proves nothing)"
        else:
            e["verified"] = False
            e["verify_note"] = "status outside the adjudicated set, kept as written"
    return entries
```

Pipeline hook (`pipeline.py`, after the `run_setup_payoff_ledger` return at
~line 1404, before the `dangling_findings` fold-in at ~line 1410):

```python
            from .setup_payoff import adjudicate_ledger
            ledger = adjudicate_ledger(ledger, doc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_payoff.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/setup_payoff.py screenplay_analyzer/pipeline.py tests/test_setup_payoff.py
git commit -m "feat(ledger): adjudicate verdicts against script text"
```

### Task 2: Setup-quote extraction for fold-in rows

**Files:**
- Modify: `screenplay_analyzer/setup_payoff.py` (`dangling_findings` gains optional `doc=None`; quote lookup)
- Test: `tests/test_setup_payoff.py` (append)

**Interfaces:**
- Consumes: ledger entry + `doc` (optional; None preserves old behavior exactly).
- Produces: fold-in finding's `evidence_quote` set to the best-matching setup-scene line, else None (row falls back to the ungrounded path as today).

- [ ] **Step 1: Write the failing test**

```python
def test_fold_in_rows_carry_the_setup_line():
    from screenplay_analyzer.setup_payoff import dangling_findings
    doc = _doc_two_scenes()
    ledger = [{"setup": "The cigar", "kind": "object",
               "setup_scenes": [1], "payoff_scenes": None,
               "status": "dangling", "note": "Never lit."}]
    findings = dangling_findings(ledger, [], doc=doc)
    assert len(findings) == 1
    assert findings[0]["evidence_quote"] is not None
    assert "cigar" in findings[0]["evidence_quote"].lower()


def test_fold_in_without_doc_keeps_old_shape():
    from screenplay_analyzer.setup_payoff import dangling_findings
    ledger = [{"setup": "The cigar", "kind": "object",
               "setup_scenes": [1], "payoff_scenes": None,
               "status": "dangling", "note": "Never lit."}]
    findings = dangling_findings(ledger, [])
    assert findings[0]["evidence_quote"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup_payoff.py -q -p no:cacheprovider`
Expected: FAIL (unexpected `doc` keyword, then missing quote)

- [ ] **Step 3: Write minimal implementation**

Change signature to `def dangling_findings(ledger, existing_plot_thread,
rules_ctx=None, doc=None):` and, when building each finding, add:

```python
        quote = _setup_quote(e, doc) if doc is not None else None
```

with module-level:

```python
def _setup_quote(entry: dict, doc) -> str | None:
    """Best-matching setup-scene line for the entry's terms (windowed
    matcher, 0.72 floor shared with the verifier). None when nothing
    reaches the floor — the row then keeps today's ungrounded path."""
    from screenplay_analyzer.verifier import (
        _normalize, _best_fuzzy_match, FUZZY_MATCH_THRESHOLD,
    )
    from screenplay_parser.quotematch import find_scene_text
    terms = sorted(_content_terms(entry.get("setup")))
    if not terms or not doc:
        return None
    best, best_conf = None, 0.0
    for n in entry.get("setup_scenes") or []:
        text = find_scene_text(doc, n)
        if not text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if len(line.split()) < 3:
                continue
            conf = _best_fuzzy_match(_normalize(" ".join(terms)),
                                     _normalize(line))
            if conf > best_conf:
                best, best_conf = line, conf
    return best if best_conf >= FUZZY_MATCH_THRESHOLD else None
```

Finding construction gains `"evidence_quote": quote,`.

Pipeline call site (`pipeline.py`, the `dangling_findings` fold-in at ~line
1410) gains `doc=doc`:

```python
            all_findings.extend(_tag_evidence(dangling_findings(ledger, existing_plot, rules_ctx=rules_ctx, doc=doc), EVIDENCE_OVERVIEW))
```

(`doc` is the analyze scope; the `test_evidence_depth.py` source pin on this
call is updated in Task 3.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_payoff.py tests/test_rules_grounding.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/setup_payoff.py tests/test_setup_payoff.py
git commit -m "feat(ledger): fold-in rows carry the setup line"
```

### Task 3: Serve the new fields, update the source pin

**Files:**
- Modify: `tests/test_evidence_depth.py` (source pin at the `dangling_findings` call site)
- Test: the pin itself plus a JSON-shape test

**Interfaces:**
- Consumes: `to_findings_json` output (passes `setup_payoff` whole — new keys flow free, assert it).
- Produces: updated pin text; no product code changes (verify first — if keys flow, this task is tests-only).

- [ ] **Step 1: Write the failing test**

```python
def test_ledger_verified_fields_reach_json():
    from screenplay_analyzer.report import to_findings_json
    from screenplay_analyzer.pipeline import AnalysisResult
    r = AnalysisResult(doc=_parse(SAMPLE))
    r.setup_payoff = [{"setup": "The cigar", "kind": "object",
                       "setup_scenes": [1], "payoff_scenes": [2],
                       "status": "paid", "note": "Lands.",
                       "verified": True, "verify_note": "terms recur in scene 2"}]
    assert to_findings_json(r)["setup_payoff"][0]["verified"] is True
```

(Helper `_parse`/SAMPLE already exist in `test_setup_payoff.py`; put this
test there, not in a new file.)

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `python -m pytest tests/test_setup_payoff.py -q -p no:cacheprovider`
Expected: PASS on first run (keys flow free — this test exists to pin that)

- [ ] **Step 3: Update the source pin**

In `tests/test_evidence_depth.py`, the assertion on the `dangling_findings`
call text must name the new call shape (`doc=doc` added at the pipeline
fold-in site). Update the expected substring to match, keeping the test's
intent (the fold-in still tags `EVIDENCE_OVERVIEW`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_payoff.py tests/test_evidence_depth.py tests/test_rules_grounding.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_setup_payoff.py tests/test_evidence_depth.py
git commit -m "test(ledger): pin verified fields served, update call-site pin"
```

### Task 4: Trial acceptance on both scripts

**Files:** none (measurement only).

- [ ] **Step 1: Re-run golden ledger evals on fresh real-model reports**

Run: `python tests/eval_recall.py <gunpen-project> tests/fixtures/recall_goldens/gunpen.json` and the pain3 pair after full real-model analyzes.
Expected: golden ledger facts (comic, debt, tea, job, countdown) correct; record hit tables in NOTES.md.
- [ ] **Step 2: Assert zero high-severity ungrounded ledger rows**

Run a findings scan: no `plot_thread` row with `rule_id == "setup_payoff_general"`, severity high, and `ungrounded` true without `setup_quote`.
- [ ] **Step 3: Full suite green**

Run: `python -m pytest tests/ -q -p no:cacheprovider`
Expected: PASS, no new failures.
- [ ] **Step 4: Commit the NOTES entry**

```bash
git add NOTES.md
git commit -m "docs: ledger precision acceptance numbers"
```
