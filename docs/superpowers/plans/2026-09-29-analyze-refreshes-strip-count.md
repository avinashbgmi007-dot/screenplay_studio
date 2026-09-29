# Analyze Refreshes the Status-Strip Finding Count Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a finished analysis update the ⚡ status strip's "N/M fixed" count, so it stops showing the previous report's numbers.

**Architecture:** The count lives in `metrics.json` (`findings_open` / `findings_total`) and is served by `GET /api/projects/<name>/metrics`, which the client already re-fetches the moment an analysis finishes (`webapp/app.js:2826`). The only writer of that count today is the edit path (`apply` / `undo` / `redo` → `_record_findings_metrics`). Analysis records its own pass through `_record_pass`, which already loads the exact `finding_statuses` payload the helper needs — so the fix is one call inside `_record_pass`, reusing the existing single counting path. No new counter, no client change, no store-schema change.

**Tech Stack:** Python 3 (stdlib + Flask), pytest against `tests/mock_unified_server.py`; vanilla-JS SPA (untouched).

**Spec:** `docs/PRD.md` (loop instrumentation / IMPROVEMENT_AUDIT 1.3) and the item-2 production-readiness report delivered 2026-09-29 (defect #2). `docs/DATA_FORMATS.md:385` states the contract this plan preserves: *"the same one `metrics.json` and the client's `findingCounts()` use, so no surface owns a second counter."*

## Global Constraints

- **One counting path.** The open count is `still_present + unknown` and the total is `addressed + still_present + unknown` — the `finding_statuses` summary arithmetic already implemented in `webapp_server._record_findings_metrics` and `pass_history.append_pass`. Never write a second formula.
- **Best-effort instrumentation.** A metrics write must never turn a completed analysis into a 500 or into a re-run of the model (`_record_pass`'s existing contract, `webapp_server.py:1361-1370`).
- **Store writes go through `jsonio.atomic_write_json` + `lock_for(path)`** — already true of `metrics._modify`; do not add a raw write.
- **Nothing leaves the machine**; no new outbound URL, no change to `net_guard` or `_validate_server_url`.
- **No context-window arithmetic** anywhere in this plan: no ctx constants, no `--ctx-size` advice.
- **`studio_projects/` is real user data** — tests run against `tmp_path` only; never point `PROJECTS_DIR` at it.
- **Console copy is UTF-8 pinned**; no new print copy with assumed terminal encoding (the failure path uses `traceback.print_exc()`, already present).
- **No push.** `main` is 2 commits ahead of `origin/main`; this plan only commits locally, on the branch the owner names.
- **Tests are the gate:** `python -m pytest tests/` then `python -u tests/run_browser_suites.py` (the fleet, run in background).

## Line-number map (both trees)

The workspace is currently on branch **`qoder/update`** (`c89572e`). The audit rungs 17–18 are on **`main`** (`9c83cc7`), where the same code sits **22 lines later**. Both trees contain `_record_pass` and `_record_findings_metrics` unchanged, so the edit is identical; only the anchor lines differ.

| Symbol | `qoder/update` (c89572e) | `main` (9c83cc7) |
|---|---|---|
| `def _record_pass(m)` | `webapp_server.py:1359` | `webapp_server.py:1381` |
| its `record_analysis` + `_record_pass` call sites | `:1435`, `:1497` | `:1457`, `:1519` |
| `def _record_findings_metrics(m, statuses)` | `:1984-1994` | `:2006-2016` |
| its existing callers (apply/undo/redo) | `:1964`, `:1980`, `:2019` | `:1986`, `:2002`, `:2041` |
| `metrics.record_findings` / `summarize` | `metrics.py:66-88` | same |
| client strip that renders it | `webapp/app.js:696-717` | same |
| client re-fetch after analysis | `webapp/app.js:2826` | same |

## File Structure

| File | Responsibility in this change |
|---|---|
| `screenplay_studio/webapp_server.py` (`_record_pass`) | The one moment a fresh report exists: record the strip's count here, through the existing helper. |
| `tests/test_webapp_api.py` (`TestProjectLifecycle`) | HTTP-level proof that analyze writes the count, and that a re-analysis replaces a stale one. |
| `tests/test_metrics.py` | Unit proof that the no-report branch leaves the writer's count alone. |
| `docs/DATA_FORMATS.md:384` | The `metrics.json` contract line gains who writes it. |
| `NOTES.md` | Handoff line, per AGENTS.md. |

Not touched: `metrics.py`, `pass_history.py`, `revision.py`, anything under `webapp/`, `STATE_STORES.md` (its row 7 lists the store and its route, not the writers).

---

### Task 1: Analysis records the status-strip finding count

**Files:**
- Modify: `screenplay_studio/webapp_server.py:1359-1377` (`_record_pass`) — on `main`, `:1381-1399`
- Test: `tests/test_webapp_api.py` (add two methods to `class TestProjectLifecycle`, which opens at `:76`)
- Test: `tests/test_metrics.py` (add one module-level function)
- Docs: `docs/DATA_FORMATS.md:384`

**Interfaces:**
- Consumes: `finding_statuses(m) -> {"findings": [...], "summary": {"addressed", "still_present", "unknown"}, "checked_at"}` (`revision.py:930`); `_record_findings_metrics(m, statuses)` (`webapp_server.py:1984`); `metrics.summarize(m) -> {analysis_seconds, avg_reply_seconds, discussed, findings_open, findings_total, findings_fixed, findings_fixed_pct}` (`metrics.py:73`); route `GET /api/projects/<name>/metrics` (`webapp_server.py:2001`).
- Produces: nothing new. `metrics.json` keys are unchanged; the same two keys are now also written by the analyze and retry-failed routes.

- [ ] **Step 1: Write the failing HTTP test — analyze writes the count**

Append to `class TestProjectLifecycle` in `tests/test_webapp_api.py` (next to `test_analyze_full_flow`, `:101`):

```python
    def test_analyze_records_the_strip_finding_count(self, http_client):
        """Item 2 (production-readiness audit 2026-09-29): the status strip's
        `N/M fixed` was written only by apply/undo/redo, so a finished analysis
        kept showing the PREVIOUS report's numbers — measured on a real project
        as `0/29 fixed` against a 36-row report. Analyze stamps the pass, so it
        must stamp the count from the same payload."""
        import json
        import os

        project = _upload(http_client).get_json()["project"]
        resp = http_client.post(f"/api/projects/{project}/analyze")
        assert resp.status_code == 200

        report_path = os.path.join(webapp_server._project_dir(project),
                                   "report.findings.json")
        n = len(json.load(open(report_path, encoding="utf-8"))["findings"])
        assert n  # an empty fixture would pass every assertion below by accident

        m = http_client.get(f"/api/projects/{project}/metrics").get_json()
        assert m["findings_total"] == n
        # nothing has been edited since this report was written, so nothing can
        # be 'addressed' — every finding is still_present or unknown
        assert m["findings_open"] == n
        assert m["findings_fixed"] == 0
```

- [ ] **Step 2: Run it to verify it fails for the right reason**

```bash
python -m pytest tests/test_webapp_api.py::TestProjectLifecycle::test_analyze_records_the_strip_finding_count -v
```

Expected: FAIL with `KeyError: 'findings_total'`-shaped emptiness, concretely `assert None == 9` — the route returns `findings_total: None` because nothing wrote it. If it passes, stop: the fixture or the assertion is wrong, do not continue.

- [ ] **Step 3: Write the second failing test — a stale count is replaced**

Add directly after the test above. This is the reported symptom itself: the old number sitting there after a new analysis.

```python
    def test_reanalysis_replaces_a_stale_finding_count(self, http_client):
        """Seed the store with a previous report's numbers, then re-analyze with
        force. The strip must move to the new report, not keep the seeded pair."""
        import json
        import os
        from types import SimpleNamespace

        from screenplay_studio.metrics import record_findings

        project = _upload(http_client).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        report_path = os.path.join(webapp_server._project_dir(project),
                                   "report.findings.json")
        n = len(json.load(open(report_path, encoding="utf-8"))["findings"])

        # a different report's arithmetic: 5 open of 9
        record_findings(SimpleNamespace(project_dir=webapp_server._project_dir(project)),
                        5, 9)
        assert http_client.get(f"/api/projects/{project}/metrics").get_json()["findings_total"] == 9

        resp = http_client.post(f"/api/projects/{project}/analyze", json={"force": True})
        assert resp.status_code == 200
        m = http_client.get(f"/api/projects/{project}/metrics").get_json()
        assert m["findings_total"] == n != 9
        assert m["findings_open"] == n
```

If `n == 9` the mock report happens to match the seeded total, the last assertion proves nothing, and the test is not can-fail: change the seeded pair to `(6, 10)` instead and re-check. Record which you used in the commit message.

- [ ] **Step 4: Write the failing unit test for the no-report branch**

Append to `tests/test_metrics.py`. An analysis that did not complete must not zero the writer's existing count; `_record_pass` hands the helper an empty dict in that case, and the helper's `if total:` guard is what keeps the store alone.

```python
def test_a_run_without_a_complete_report_leaves_the_count_alone(tmp_path):
    """`_record_pass` passes `{}` when the analyze stage is not complete. The
    helper's `if total:` guard must keep a failed run from zeroing a count the
    writer earned on the last good report."""
    from types import SimpleNamespace

    from screenplay_studio.webapp_server import _record_findings_metrics

    m = FakeManifest(str(tmp_path))
    record_findings(m, open_count=4, total=7)
    _record_findings_metrics(m, {})
    assert load(m)["findings_total"] == 7
    _record_findings_metrics(m, {"summary": {"addressed": 0, "still_present": 0, "unknown": 0}})
    assert load(m)["findings_total"] == 7
```

- [ ] **Step 5: Run it to verify it fails only if the guard is gone**

```bash
python -m pytest tests/test_metrics.py::test_a_run_without_a_complete_report_leaves_the_count_alone -v
```

Expected: PASS immediately — it defends a branch of the call being added, not the call itself. That is allowed for a guard test, and Step 6's mutation proves it can fail. Do not skip Step 6.

- [ ] **Step 6: Prove the guard test can fail (mutation)**

Temporarily change `if total:` to `if True:` in `_record_findings_metrics` (`webapp_server.py:1991` / `main:2013`) and rerun:

```bash
python -m pytest tests/test_metrics.py::test_a_run_without_a_complete_report_leaves_the_count_alone -v
```

Expected: FAIL (`assert 0 == 7`). Restore `if total:` and confirm it passes again. Delete no other line, commit no part of this experiment.

- [ ] **Step 7: Implement the one call**

In `screenplay_studio/webapp_server.py`, `def _record_pass(m)` at `:1359` (`main:1381`), replace the body's `try` block. The whole function after the edit:

```python
def _record_pass(m) -> None:
    """spec §15.4: stamp the revision arc — and the status-strip finding count —
    with this pass's numbers.

    Best-effort on purpose. The analysis is finished and its report is on disk
    by the time this runs, so a history write that fails (a locked store, a full
    disk) must not answer a completed run with a 500 that pushes the writer into
    re-running the model. The failure is printed, not swallowed — the same
    discipline the `record_analysis` call directly above it applies.
    """
    try:
        from .pass_history import append_pass
        from .revision import finding_statuses
        statuses = (finding_statuses(m)
                    if m.stage("analyze").status == "complete" else {})
        # Item 2 (audit 2026-09-29): `metrics.findings_*` was written only by
        # apply/undo/redo, so a finished analysis left the PREVIOUS report's
        # numbers on the strip. This is the one moment the new report exists and
        # its statuses are already loaded, and `_record_findings_metrics` is the
        # single counting path -- reuse it rather than a second arithmetic.
        # Ahead of append_pass so a history failure cannot strand the count; the
        # helper's own best-effort try is what keeps a locked store off the 500
        # path. An incomplete analyze gives {}, whose total is 0, so the writer's
        # existing count survives a failed run untouched.
        _record_findings_metrics(m, statuses)
        failed = (m.stage("analyze").output_paths or {}).get("failed_categories") or []
        append_pass(m, statuses, failed)
    except Exception:
        traceback.print_exc()
```

`_record_findings_metrics` is defined later in the module (`:1984`); that is fine — it resolves at call time, and every request comes after import. Do not move the helper.

- [ ] **Step 8: Run the new tests to verify they pass**

```bash
python -m pytest tests/test_webapp_api.py::TestProjectLifecycle::test_analyze_records_the_strip_finding_count tests/test_webapp_api.py::TestProjectLifecycle::test_reanalysis_replaces_a_stale_finding_count tests/test_metrics.py -v
```

Expected: all PASS, output pristine (no stray tracebacks — a printed traceback here means the metrics write raised and was swallowed by the outer `except`, which is exactly the failure the tests must not hide).

- [ ] **Step 9: Verify the existing pass-history tests still describe the same numbers**

```bash
python -m pytest tests/test_pass_history.py tests/test_revision.py tests/test_route_smoke.py -v
```

Expected: all PASS. `tests/test_route_smoke.py:76` asserts the `/metrics` body carries `{"analysis_seconds", "discussed", "findings_total"}` — unchanged shape. `tests/test_store_fault_injection.py:125-134` covers the metrics store's fault contract — unchanged writer path.

- [ ] **Step 10: Update the store contract line**

In `docs/DATA_FORMATS.md:384`, name who writes the count so the next session does not re-derive it:

```markdown
- **metrics.json** — desk metrics. `{analysis_seconds, last_analysis_ts, reply_seconds (rolling ≤40), discussed, findings_open, findings_total}`. `findings_open`/`findings_total` are written by `_record_pass` (every completed or partial analysis, and the retry) and by apply/undo/redo, always through `_record_findings_metrics` — the `finding_statuses` summary arithmetic, so the strip and `pass_history.json` never disagree and no surface owns a second counter.
```

- [ ] **Step 11: Handoff note**

Add one entry to `NOTES.md` under the current R6 section, in its existing voice: analyze now refreshes the ⚡ count; the client already re-fetched it (`app.js:2826`), so the defect was purely that the server never wrote it at analyze; item 2's defects #1 (id collision) and #3 (copy resets the fixed/new guard) remain open and untouched.

- [ ] **Step 12: Commit**

```bash
git add screenplay_studio/webapp_server.py tests/test_webapp_api.py tests/test_metrics.py docs/DATA_FORMATS.md NOTES.md
git commit -m "$(cat <<'EOF'
R6 item-2 fix: a finished analysis refreshes the strip's finding count

metrics.findings_* was written only by apply/undo/redo, so after a re-run the
status strip kept the previous report's numbers (measured: 0/29 fixed against
a 36-row report). _record_pass already loads the statuses the count is derived
from, so it now feeds the same _record_findings_metrics path the edits use —
one arithmetic, no second counter.
EOF
)"
```

---

### Task 2: Close the gate on the final tree

**Files:** no source edits; this task exists because a change to the analyze route's writes can only be certified by the full gate, and the gate's own output is what gets reported.

**Interfaces:**
- Consumes: Task 1's committed tree.
- Produces: gate evidence (counts) for the report back to the owner; a `NOTES.md` amendment if the gate moves anything.

- [ ] **Step 1: Full pytest**

```bash
python -m pytest tests/ -q
```

Expected: same pass count as the baseline for this branch (main's last certified run: 1,912 passed / 3 pre-existing failures) plus the 3 new tests, no new failures. Record the two numbers; do not call it green from a partial run.

- [ ] **Step 2: Browser fleet, in background with unbuffered output**

```bash
python -u tests/run_browser_suites.py
```

Expected: every suite passes except the known skips (baseline on this repo: 57 pass / 1 skip / 1,488 checks; `dock_sections` 169/0). This fleet is what proves the client half — `refreshMetrics()` on the analysis-complete path (`app.js:2826`) now receives a non-null count. It never proved it before, because the server had nothing to send.

- [ ] **Step 3: If the fleet exposes a strip that shows nothing**

Do not change `app.js` to make a test pass. Read the failing check's assertion, then `GET /api/projects/<name>/metrics` for the same project in-process and compare against `report.findings.json` row count. Attribute the delta to a named transform before editing anything.

- [ ] **Step 4: Amend NOTES.md with the measured gate numbers, commit only if NOTES.md changed**

```bash
git add NOTES.md && git commit -m "R6 item-2 fix: gate numbers for the strip-count refresh"
```

- [ ] **Step 5: Report, and stop before pushing**

Tell the owner: the branch this landed on, the two gate counts, and that item 2's defects #1 and #3 are still open. No push, no branch move — his call.

---

## Out of scope (deliberately, so it is not mistaken for a miss)

- **A clean report of zero findings leaves the old count on screen.** `_record_findings_metrics`'s `if total:` guard behaves this way for all four of its callers today, edits included. Fixing it changes the edit paths, which are not part of this defect.
- **Whether "fixed" should mean cross-pass progress** rather than "of this report, how many my edits resolved" — a presentation decision, item 4 territory.
- **The id-collision defect (#1) and the copy-resets-the-guard defect (#3)** — untouched here on purpose; #1 needs the alias step for the 23 real projects, #3 needs a fingerprint that covers the whole report.
- **A browser test that pins the strip's label text.** `dock_sections` covers strip rendering generally; this change's client half already existed and was verified by reading `app.js:2826` in-session.

## Self-review record

- **Spec coverage:** the defect as reported ("the ⚡ strip shows 0/29 fixed from an old snapshot and doesn't refresh after a new analysis") is Task 1 Steps 1–8; the retry route shares `_record_pass`, so Task 1 Step 7 covers both call sites (`:1435`, `:1497`) with one edit; the contract doc moves with the code (Step 10); certification is Task 2.
- **Placeholders:** none — every step carries its code or its command and expected output.
- **Type consistency:** `record_findings(m, open_count, total)` is called positionally as `(m, open_count_value, total_value)` by `_record_findings_metrics` (`:1992`) and by keyword in `tests/test_metrics.py` — both match `metrics.py:66`. `summarize()` supplies `findings_fixed` / `findings_fixed_pct` derived, never stored (`metrics.py:85-87`), which is what the two HTTP tests assert.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-29-analyze-refreshes-strip-count.md`. Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, reviewed between tasks.
2. **Inline Execution** — I run the tasks in this session with checkpoints.

Also needed from the owner before any edit: which branch to land on (`main`, which holds audit rungs 17–18, or the currently checked-out `qoder/update`).
