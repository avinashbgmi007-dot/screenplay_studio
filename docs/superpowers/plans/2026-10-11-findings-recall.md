# Findings Recall (Accuracy Kit B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catch story mechanics the summary pipeline misses (dream reveals, paid-off threads) and measure recall with checked-in golden sets.

**Architecture:** Full-text overview for small scripts at the existing 2b site (`pipeline.py` ~line 1096); a deterministic reveal scan feeding script-level context through the existing `rules_fragment` parameter (`run_script_level_category`, `pipeline.py:701`); golden facts plus a deterministic local eval runner (no model judge, anchor-substring matching).

**Tech Stack:** Python 3 stdlib + pytest; real llama-server for the eval runner only (never CI-blocking).

## Global Constraints

- No cross-package imports at module load (lazy inside functions, per AGENTS.md).
- Local eval runner only; nothing here gates CI (real model required).
- Full suite green after every task.

---

### Task 1: Full-text overview for small scripts

**Files:**
- Modify: `screenplay_analyzer/pipeline.py` (~line 1096, 2b block)
- Test: `tests/test_recall.py` (new file)

**Interfaces:**
- Consumes: `doc` parsed text, `MAX_OVERVIEW_CHARS` (6000, `pipeline.py:400`).
- Produces: `script_level_overview` built from full text when it fits; `stats["script_level_source"] = "full_text"`; evidence stamps stay `EVIDENCE_FULL_TEXT` (existing bucket, no new taxonomy).

- [ ] **Step 1: Write the failing test**

```python
"""Kit B: small scripts are read whole, not summarized."""
from screenplay_analyzer import pipeline as P


class _El:
    def __init__(self, t):
        self.text = t


class _Scene:
    def __init__(self, n, texts):
        self.scene_number = n
        self.elements = [_El(t) for t in texts]


class _Doc:
    scene_count = 2
    scenes = [_Scene(1, ["INT. FLAT - DAY", "Raj wakes. It was a dream."]),
              _Scene(2, ["INT. FLAT - DAY", "He writes the article."])]


def test_small_script_overview_contains_full_text():
    stats = {}
    overview, source = P.build_script_level_source(_Doc(), "summary text", stats)
    assert source == "full_text"
    assert "It was a dream." in overview


def test_large_script_keeps_summary_path():
    big = _Doc()
    big.scenes = [_Scene(i, ["x" * 5000]) for i in range(1, 6)]
    stats = {}
    overview, source = P.build_script_level_source(big, "summary text", stats)
    assert source == "overview"
    assert overview == "summary text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recall.py -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'build_script_level_source'"

- [ ] **Step 3: Write minimal implementation**

Module level in `pipeline.py` (near `build_scene_overview_text`, ~line 524):

```python
def _scene_full_text(doc) -> str:
    """All parsed element texts in scene order (already exists as the
    per-scene helper — reuse it, do not add another)."""
    return _scene_full_text_joined(doc)


def build_script_level_source(doc, overview: str, stats: dict) -> tuple[str, str]:
    """Full text when it fits MAX_OVERVIEW_CHARS, else the summary path.
    Returns (overview_text, source_bucket). Records the choice in stats so
    the report can name what the passes actually read."""
    texts = []
    for s in doc.scenes or []:
        for e in s.elements or []:
            t = getattr(e, "text", None) or (e.get("text") if isinstance(e, dict) else "")
            if t:
                texts.append(str(t))
    full = "\n".join(texts)
    if full and len(full) <= MAX_OVERVIEW_CHARS:
        stats["script_level_source"] = "full_text"
        return full, EVIDENCE_FULL_TEXT
    stats["script_level_source"] = "overview"
    return overview, EVIDENCE_OVERVIEW
```

Call site (`pipeline.py` ~line 1096, replacing `script_level_overview = overview`):

```python
    script_level_overview, _sl_source = build_script_level_source(doc, overview, result.stats)
```

Then keep the checkpoint block as-is (it may still add checkpoints; when the
source is already full text the mixed bucket must NOT overwrite it — guard the
`script_level_source = ...` assignment at ~line 1114 to only apply when the
source is not already `EVIDENCE_FULL_TEXT`).

Note: `_scene_full_text` naming — the module already has a per-scene full-text
helper used by summaries (referenced in the summaries docstring path); reuse
that exact helper rather than adding a second joiner. Read its signature at
implementation time and call it per scene.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_recall.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/pipeline.py tests/test_recall.py
git commit -m "feat(recall): full-text overview for small scripts"
```

### Task 2: Reveal retrieval scan

**Files:**
- Create: `screenplay_analyzer/reveal_scan.py`
- Modify: `screenplay_analyzer/pipeline.py` (AnalysisResult field ~line 240, hook after summaries ~line 1090, context thread at script-level call ~line 1160)
- Test: `tests/test_recall.py` (append)

**Interfaces:**
- Consumes: parsed `doc` scenes/elements.
- Produces: `result.reveal_candidates` list of `{scene, line, match}`; appended context block in `rules_fragment`.

- [ ] **Step 1: Write the failing test**

```python
def test_dream_reveal_detected():
    from screenplay_analyzer.reveal_scan import scan_reveals

    class _E(dict):
        pass

    doc = _Doc()
    found = scan_reveals(doc)
    assert any("dream" in f["match"].lower() for f in found), \
        "the gunpen acceptance case: 'It was a dream.' must surface"
    assert found[0]["scene"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recall.py -q -p no:cacheprovider`
Expected: FAIL with "No module named 'screenplay_analyzer.reveal_scan'"

- [ ] **Step 3: Write minimal implementation**

New file `screenplay_analyzer/reveal_scan.py`:

```python
"""Deterministic reveal-mechanic scan (accuracy kit B).

Twist mechanics live in single action lines a summary drops ("it was a
dream"). This scan finds candidate lines so script-level passes can account
for them. Lexical only — no model call, never fails a run.
"""

from __future__ import annotations

import re

REVEAL_PATTERNS = [
    re.compile(r"\bit was (all )?a dream\b", re.I),
    re.compile(r"\bdreamt\b|\bdreaming\b", re.I),
    re.compile(r"\bwok[ee] (up )?to\b.{0,20}\bdream", re.I),
    re.compile(r"\bkalaa\b", re.I),
    re.compile(r"\bjust a dream\b|\bonly a dream\b", re.I),
    re.compile(r"\bdead .{0,20}\balive\b", re.I),
]


def scan_reveals(doc) -> list:
    """Return [{scene, line, match}] for reveal-candidate lines, in order."""
    found = []
    for s in doc.scenes or []:
        for e in s.elements or []:
            text = getattr(e, "text", None) or (e.get("text") if isinstance(e, dict) else "")
            if not text:
                continue
            for p in REVEAL_PATTERNS:
                m = p.search(str(text))
                if m:
                    found.append({"scene": s.scene_number, "line": str(text)[:160],
                                  "match": m.group(0)})
                    break
    return found


def reveal_context_block(candidates: list) -> str:
    if not candidates:
        return ""
    lines = ["Candidate story mechanics (deterministic scan — verify against the text,",
             "do not assume; if a finding contradicts one, the finding is suspect):"]
    for c in candidates:
        lines.append(f"- Scene {c['scene']}: '{c['line']}'")
    return "\n".join(lines)
```

Pipeline wiring: `AnalysisResult` gains `reveal_candidates: list = field(default_factory=list)`
(field block ~line 240); after the summaries stage (~line 1090, where `overview`
is set) add:

```python
    from .reveal_scan import scan_reveals
    result.reveal_candidates = scan_reveals(doc)
```

At the script-level call site (~line 1160,
`run_script_level_category(fn, client, rules_fragment, ...)`), append:

```python
    from .reveal_scan import reveal_context_block
    _reveal_block = reveal_context_block(result.reveal_candidates)
    if _reveal_block:
        rules_fragment = (rules_fragment + "\n\n" + _reveal_block) if rules_fragment else _reveal_block
```

(Read the exact call-site lines at implementation time; the shape above matches
`run_script_level_category(prompt_fn, client, rules_fragment, *args, ...)` at
`pipeline.py:701`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_recall.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add screenplay_analyzer/reveal_scan.py screenplay_analyzer/pipeline.py tests/test_recall.py
git commit -m "feat(recall): deterministic reveal scan into script-level context"
```

### Task 3: Golden recall sets plus local eval runner

**Files:**
- Create: `tests/fixtures/recall_goldens/gunpen.json`, `tests/fixtures/recall_goldens/pain3.json`, `tests/eval_recall.py`
- Test: the runner asserts per-fact hits (it IS the test; plus a unit test that anchor matching works on a synthetic report)

**Interfaces:**
- Consumes: a project dir with `report.findings.json`; golden JSON `{facts: [{id, anchors: [...]}, ...]}`.
- Produces: stdout hit-rate table + nonzero exit when any fact misses (local use only, never CI).

- [ ] **Step 1: Write the golden files and the failing runner test**

`tests/fixtures/recall_goldens/gunpen.json`:

```json
{"script": "gun_pen (6pp/3sc Tenglish short)",
 "facts": [
  {"id": "dream-reveal", "anchors": ["dream", "kalaa"]},
  {"id": "countdown-paid", "anchors": ["00:00", "3 mints", "countdown"]},
  {"id": "jam-turn", "anchors": ["jam"]},
  {"id": "pen-article-chain", "anchors": ["Local Gangs", "article"]},
  {"id": "journalist-rhyme", "anchors": ["journalist", "RAJ"]}
 ]}
```

`tests/fixtures/recall_goldens/pain3.json`:

```json
{"script": "Pain_3_updated_FULL (28pp/22sc)",
 "facts": [
  {"id": "debt-payoff", "anchors": ["amount", "money", "parcel"]},
  {"id": "comic-payoff", "anchors": ["comic", "bye", "wave"]},
  {"id": "deadline-outcome", "anchors": ["Rendu rojul", "two days", "deadline"]},
  {"id": "job-resolution", "anchors": ["X COMPANY", "shortlist", "job"]},
  {"id": "silence-facts", "anchors": ["Doesnt know what to do"]}
 ]}
```

`tests/eval_recall.py` (deterministic anchor matching — a fact hits when ANY
anchor appears in ANY finding's issue/observation/quote, case-insensitive):

```python
"""Local recall eval: golden facts vs a real-model report. Real model required;
never CI. Usage: python tests/eval_recall.py <project-dir> <golden-json>"""
import json
import sys


def hit_rate(report_path, golden_path):
    report = json.load(open(report_path, encoding="utf-8"))
    goldens = json.load(open(golden_path, encoding="utf-8"))
    texts = [f"{f.get('issue', '')} {f.get('observation', '')} {f.get('evidence_quote', '')}".lower()
             for f in report.get("findings", [])]
    rows = []
    for fact in goldens["facts"]:
        hit = any(a.lower() in t for a in fact["anchors"] for t in texts)
        rows.append((fact["id"], hit))
    return rows


if __name__ == "__main__":
    rows = hit_rate(sys.argv[1] + "/report.findings.json", sys.argv[2])
    for fid, hit in rows:
        print(("HIT  " if hit else "MISS ") + fid)
    print(f"{sum(1 for _, h in rows if h)}/{len(rows)} facts hit")
    sys.exit(0 if all(h for _, h in rows) else 1)
```

Unit test in `tests/test_recall.py`:

```python
def test_eval_runner_counts_hits(tmp_path):
    import json as J
    from tests.eval_recall import hit_rate  # local import: eval-only helper
```

(No: `tests/` is not a package import path — the runner is exec'd, not
imported. Instead the runner self-tests: `python tests/eval_recall.py --selftest`
builds a synthetic report in tmp and asserts 1/2. Implement `--selftest` in the
runner rather than a pytest import.)

Runner `--selftest` block:

```python
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        import tempfile, os
        tmp = tempfile.mkdtemp()
        rep = os.path.join(tmp, "report.findings.json")
        json.dump({"findings": [{"issue": "The countdown pays at 00:00.",
                                 "observation": "", "evidence_quote": ""}]}, open(rep, "w"))
        gold = os.path.join(tmp, "gold.json")
        json.dump({"facts": [{"id": "a", "anchors": ["00:00"]},
                             {"id": "b", "anchors": ["never-mentioned-xyz"]}]},
                  open(gold, "w"))
        rows = hit_rate(rep, gold)
        assert rows == [("a", True), ("b", False)], rows
        print("selftest OK")
        sys.exit(0)
```

- [ ] **Step 2: Run selftest to verify it passes, runner to verify current misses**

Run: `python tests/eval_recall.py --selftest`
Expected: selftest OK
Run: `python tests/eval_recall.py <gunpen-project-dir> tests/fixtures/recall_goldens/gunpen.json`
Expected: nonzero exit with named MISSES (baseline: dream/countdown miss)

- [ ] **Step 3: Commit**

```bash
git add tests/eval_recall.py tests/fixtures/recall_goldens/gunpen.json tests/fixtures/recall_goldens/pain3.json tests/test_recall.py
git commit -m "feat(recall): golden recall sets plus local eval runner"
```
