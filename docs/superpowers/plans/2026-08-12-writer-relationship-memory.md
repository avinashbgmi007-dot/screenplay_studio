# Writer Relationship Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sam learns how the writer likes to work — tone, directness, probing, pushback, topic gravity — across all projects, via per-turn rule signals plus an every-10-turns LLM refresh, with a visible editable "Sam's notes on you" panel.

**Architecture:** New pure-function module `screenplay_cowriter/memory.py` (signal extraction, confidence-gated dimensions, relationship card, refresh prompt/parse/merge) + a thin `WriterMemory` I/O wrapper. `context.py::build_system_prompt` gains two optional paragraphs (relationship card + cold-start line); `engine.py::CoWriterEngine` gains optional `memory=None` (absent = today's exact behavior) and observes each turn. The webapp wires memory by default (`PROJECTS_DIR/writer_profile.json`) with three new endpoints; the cowriter CLI/server get an optional `--memory-path`. Frontend adds a "Sam's notes on you" modal in the Co-write room's partner card.

**Tech Stack:** Python (stdlib only — json, re, threading, uuid, os, time), Flask (webapp), vanilla JS (no build step).

## Global Constraints

- Memory **informs tone, never content**; the card text forbids quoting the memory at the writer ("you always say…" is forbidden).
- **Behavior gate:** a dimension affects behavior only when `value` is a learnable pole AND `confidence >= 0.6` AND `pos + neg >= 3` (MIN_EVIDENCE). One signal must never gate anything.
- **No flip-flopping:** a dimension flips only when `neg > pos` (the opposite pole wins at confidence); after a flip confidence is recomputed and must still cross the gate.
- Refresh trigger: `total_turns_observed - turns_at_last_refresh >= 10`. Refresh is fire-and-forget (daemon thread); the writer's reply is never blocked.
- Cold start: profile empty → Sam neutral; one light optional opening question only on the very first turn of a fresh session with zero evidence.
- **Backward compatibility:** `CoWriterEngine(memory=None)` and `build_system_prompt(relationship_card=None, cold_start_line=None)` must be byte-identical to today; only the webapp wires memory by default; cowriter CLI/server expose `--memory-path` default off.
- Existing 328 tests must stay green (in-process mock llama-server, no real model).
- Profile lives at `PROJECTS_DIR/writer_profile.json` (webapp). Corrupt file → backed up to `.bak`, empty profile used, chat never breaks. All file I/O serialized by a **module-level** lock (instances are per-request).
- TDD: write the failing test, watch it fail, implement, watch it pass, commit.

---

### Task 1: `memory.py` — profile, signals, confidence gate (pure core)

**Files:**
- Create: `screenplay_cowriter/memory.py`
- Create: `tests/test_writer_memory.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces (used by Tasks 2–7):
  - `empty_profile() -> dict`
  - `extract_signals(user_text: str, turn_kind: str, was_pending: bool, previous_reply: str | None) -> dict`
  - `apply_signals(profile: dict, signals: dict) -> dict` (mutates + returns)
  - `confidence(pos: int, neg: int) -> float`
  - `dimension_gate(profile: dict) -> dict` — `{dim: {"value", "confidence"}}` for gated dims only
  - Constants: `BEHAVIOR_GATE = 0.6`, `MIN_EVIDENCE = 3`, `REFRESH_INTERVAL = 10`, `DIMENSION_POLES`, `NEUTRAL`, `TOPIC_CATEGORIES`, `TOPIC_KEYWORDS`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_writer_memory.py
import pytest
from screenplay_cowriter import memory as mem


def test_extract_tone_statement_direct():
    s = mem.extract_signals("just tell me straight what's wrong with scene 3", "idea", False, None)
    assert s["poles"].get("directness") == "direct"


def test_extract_tone_statement_short():
    s = mem.extract_signals("keep it short please", "idea", False, None)
    assert s["poles"].get("detail_level") == "short"


def test_extract_probe_engagement():
    s = mem.extract_signals("because the guilt is eating her", "idea", True, "So the idea is...?")
    assert s["probe_engagement"] == "engaged"
    s2 = mem.extract_signals("hmm", "idea", True, "So the idea is...?")
    assert s2["probe_engagement"] == "dismissed"


def test_extract_pushback():
    s = mem.extract_signals("no, cutting that line loses the subtext", "idea", False, None)
    assert s["pushback"] == "argued"
    s2 = mem.extract_signals("ok sure", "idea", False, None)
    assert s2["pushback"] == "accepted"


def test_extract_topics():
    s = mem.extract_signals("the protagonist's arc feels flat", "idea", False, None)
    assert "character" in s["topics"]


def test_single_signal_does_not_gate():
    p = mem.empty_profile()
    sig = {"poles": {"detail_level": "short"}, "topics": [], "probe_engagement": None, "pushback": None}
    mem.apply_signals(p, sig)
    assert "detail_level" not in mem.dimension_gate(p)


def test_three_consistent_signals_gate():
    p = mem.empty_profile()
    sig = {"poles": {"detail_level": "short"}, "topics": [], "probe_engagement": None, "pushback": None}
    for _ in range(3):
        mem.apply_signals(p, sig)
    assert mem.dimension_gate(p)["detail_level"]["value"] == "short"


def test_contradiction_flips_only_when_winning():
    p = mem.empty_profile()
    short = {"poles": {"detail_level": "short"}, "topics": [], "probe_engagement": None, "pushback": None}
    for _ in range(4):
        mem.apply_signals(p, short)
    assert mem.dimension_gate(p)["detail_level"]["value"] == "short"
    deep = {"poles": {"detail_level": "deep"}, "topics": [], "probe_engagement": None, "pushback": None}
    for _ in range(5):
        mem.apply_signals(p, deep)
    assert "detail_level" not in mem.dimension_gate(p)  # mid-flip uncertainty drops below gate
    for _ in range(2):
        mem.apply_signals(p, deep)
    assert mem.dimension_gate(p)["detail_level"]["value"] == "deep"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'screenplay_cowriter.memory'`

- [ ] **Step 3: Write minimal implementation** — create `screenplay_cowriter/memory.py` with:

```python
"""Writer relationship memory — Sam's gradually-learned sense of how the
writer likes to work, persisted writer-level (across all projects).

Spec: docs/superpowers/specs/2026-08-12-writer-relationship-memory-design.md

Two-tier inference:
  1. Per-turn rule signals (cheap, deterministic) accumulated into per-
     dimension pos/neg evidence with a confidence gate (nothing gates on a
     single signal; a dimension flips only when the opposite pole wins).
  2. A session refresh: one LLM call (fire-and-forget) that reads recent
     conversation and proposes profile updates, merged with strict rules.

The writer stays the editor: everything is visible via card_text() and
reversible via suppress().
"""

from __future__ import annotations

import re
import time
import uuid

BEHAVIOR_GATE = 0.6
MIN_EVIDENCE = 3           # a dimension needs this many signals before it can gate
REFRESH_INTERVAL = 10      # new observed turns between refreshes

# Neutral value per dimension (the "nothing set" state — never gates).
NEUTRAL = {"detail_level": "balanced", "directness": "balanced",
           "probe_appetite": "medium", "pushback_appetite": "medium"}

# Learnable poles per dimension.
DIMENSION_POLES = {
    "detail_level": ("short", "deep"),
    "directness": ("gentle", "direct"),
    "probe_appetite": ("low", "high"),
    "pushback_appetite": ("low", "high"),
}

TOPIC_CATEGORIES = ("character", "structure", "dialogue", "craft")
TOPIC_KEYWORDS = {
    "character": ["character", "protagonist", "antagonist", "motive", "arc",
                  "backstory", "hero", "villain"],
    "structure": ["structure", "act", "pacing", "plot", "climax", "midpoint",
                  "setup", "payoff", "ending"],
    "dialogue": ["dialogue", "monologue", "subtext", "banter"],
    "craft": ["description", "slugline", "parenthetical", "wryly", "formatting"],
}

# Explicit tone statements — regex, dimension, pole.
TONE_RULES = [
    (re.compile(r"\b(?:keep it short|be brief|concise|short answer|tl;?dr)\b", re.I), "detail_level", "short"),
    (re.compile(r"\b(?:go deeper|more detail|elaborate|expand on that|really dig in|in depth)\b", re.I), "detail_level", "deep"),
    (re.compile(r"\b(?:tell me straight|just say it|don'?t soften|be blunt|be direct|no sugar.?coating)\b", re.I), "directness", "direct"),
    (re.compile(r"\b(?:be gentle|ease me in|softly|carefully|kindly|gently)\b", re.I), "directness", "gentle"),
    (re.compile(r"\b(?:push back|argue with me|disagree with me|challenge me|fight me on)\b", re.I), "pushback_appetite", "high"),
]

PUSHBACK_ARGUE = re.compile(r"\b(?:i disagree|no,? |but |that won'?t work|that doesn'?t work|that loses|keep it anyway|actually no)\b", re.I)
PUSHBACK_AGREE = re.compile(r"\b(?:ok(?:ay)?|sure|fine|good point|makes sense|agree(?:d)?|sounds good|go with it)\b", re.I)
PROBE_REASON = re.compile(r"\b(?:because|since|the reason|my instinct|i feel|i think|the thing is)\b", re.I)


def empty_profile() -> dict:
    return {
        "version": 1,
        "dimensions": {dim: {"value": NEUTRAL[dim], "confidence": 0.5,
                             "evidence": {"pos": 0, "neg": 0},
                             "last_updated": time.time()} for dim in DIMENSION_POLES},
        "topic_gravity": {c: 0 for c in TOPIC_CATEGORIES},
        "observations": [],
        "meta": {"total_turns_observed": 0, "turns_at_last_refresh": 0,
                 "last_refresh": None, "refresh_count": 0},
    }


def confidence(pos: int, neg: int) -> float:
    """Laplace-smoothed: 0 evidence => 0.5; needs sustained evidence to cross the gate."""
    return (pos + 2.0) / (pos + neg + 4.0)


def extract_signals(user_text, turn_kind, was_pending, previous_reply=None):
    """Rule signals for one writer turn. Returns:
    {"poles": {dim: pole}, "topics": [cat...],
     "probe_engagement": "engaged"|"dismissed"|None, "pushback": "argued"|"accepted"|None}"""
    signals = {"poles": {}, "topics": [], "probe_engagement": None, "pushback": None}
    lowered = (user_text or "").strip()
    if not lowered:
        return signals
    for rx, dim, pole in TONE_RULES:
        if rx.search(lowered):
            signals["poles"][dim] = pole
    if was_pending:
        words = lowered.split()
        if len(words) <= 3:
            signals["probe_engagement"] = "dismissed"
        elif PROBE_REASON.search(lowered):
            signals["probe_engagement"] = "engaged"
        elif len(words) >= 6 and not lowered.rstrip().endswith("?"):
            signals["probe_engagement"] = "engaged"
        else:
            signals["probe_engagement"] = "dismissed"
    if PUSHBACK_ARGUE.search(lowered):
        signals["pushback"] = "argued"
    elif PUSHBACK_AGREE.search(lowered):
        signals["pushback"] = "accepted"
    for cat, kws in TOPIC_KEYWORDS.items():
        if any(kw in lowered.lower() for kw in kws):
            signals["topics"].append(cat)
    return signals


def _dim_state(profile, dim):
    d = profile["dimensions"].get(dim)
    if d is None:
        d = profile["dimensions"][dim] = {"value": NEUTRAL[dim], "confidence": 0.5,
                                          "evidence": {"pos": 0, "neg": 0}, "last_updated": time.time()}
    return d


def _bump(profile, dim, pole):
    d = _dim_state(profile, dim)
    if d["value"] not in DIMENSION_POLES[dim]:
        d["value"] = pole
    if d["value"] == pole:
        d["evidence"]["pos"] += 1
    else:
        d["evidence"]["neg"] += 1
    d["last_updated"] = time.time()
    d["confidence"] = round(confidence(d["evidence"]["pos"], d["evidence"]["neg"]), 2)
    if d["evidence"]["neg"] > d["evidence"]["pos"]:
        # flip: the opposite pole now leads — swap so pos means "for the value"
        d["value"] = DIMENSION_POLES[dim][1] if d["value"] == DIMENSION_POLES[dim][0] else DIMENSION_POLES[dim][0]
        d["evidence"]["pos"], d["evidence"]["neg"] = d["evidence"]["neg"], d["evidence"]["pos"]
    return d


def apply_signals(profile, signals):
    for dim, pole in signals.get("poles", {}).items():
        _bump(profile, dim, pole)
    if signals.get("probe_engagement") == "engaged":
        _bump(profile, "probe_appetite", "high")
    elif signals.get("probe_engagement") == "dismissed":
        _bump(profile, "probe_appetite", "low")
    if signals.get("pushback") == "argued":
        _bump(profile, "pushback_appetite", "high")
    elif signals.get("pushback") == "accepted":
        _bump(profile, "pushback_appetite", "low")
    for cat in signals.get("topics", []):
        profile["topic_gravity"][cat] = profile["topic_gravity"].get(cat, 0) + 1
    return profile


def dimension_gate(profile):
    """Dimensions that actually affect behavior: learnable pole, confidence >= gate,
    and at least MIN_EVIDENCE total signals."""
    gated = {}
    for dim, d in profile["dimensions"].items():
        if dim not in DIMENSION_POLES:
            continue
        ev = d["evidence"]
        if d["value"] in DIMENSION_POLES[dim] and d["confidence"] >= BEHAVIOR_GATE and (ev["pos"] + ev["neg"]) >= MIN_EVIDENCE:
            gated[dim] = {"value": d["value"], "confidence": d["confidence"]}
    return gated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/memory.py tests/test_writer_memory.py
git commit -m "feat: writer-memory pure core — signals, evidence, confidence gate"
```

---

### Task 2: `memory.py` — card, cold start, refresh prompt/parse/merge (pure)

**Files:**
- Modify: `screenplay_cowriter/memory.py` (append)
- Modify: `tests/test_writer_memory.py` (append)

**Interfaces:**
- Consumes: Task 1 constants + functions.
- Produces (used by Tasks 3–7):
  - `build_relationship_card(profile: dict) -> str | None`
  - `cold_start_line(profile: dict) -> str | None`
  - `refresh_prompt(recent_messages: list[dict]) -> str`
  - `parse_refresh_json(text: str) -> dict | None`
  - `merge_refresh(profile: dict, proposal: dict) -> dict`
  - `novel_observation(profile: dict, text: str) -> bool`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_writer_memory.py`)

```python
_SIG = {"poles": {}, "topics": [], "probe_engagement": None, "pushback": None}


def _signal(pole_map):
    s = dict(_SIG)
    s["poles"] = dict(pole_map)
    return s


def test_card_empty_profile():
    assert mem.build_relationship_card(mem.empty_profile()) is None


def test_card_gated_only_and_never_quotes_memory():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    card = mem.build_relationship_card(p)
    assert card and "ABOUT HOW YOU TWO WORK TOGETHER" in card
    assert "never content" in card
    assert "you always say" not in card


def test_card_excludes_suppressed_observation():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"directness": "direct"}))
    obs = next(o for o in p["observations"] if o["dimension"] == "directness")
    obs["suppressed"] = True
    card = mem.build_relationship_card(p)
    assert obs["text"] not in card


def test_cold_start_line_only_when_zero_evidence():
    p = mem.empty_profile()
    assert mem.cold_start_line(p)
    p["meta"]["total_turns_observed"] = 1
    assert mem.cold_start_line(p) is None


def test_refresh_prompt_shape():
    txt = mem.refresh_prompt([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    assert "RELATIONSHIP MEMORY REFRESH" in txt
    assert "user: hi" in txt and "assistant: hello" in txt


def test_parse_refresh_json():
    assert mem.parse_refresh_json(
        'Here you go: {"detail_level": {"value": "deep", "confidence": 0.8}}'
    ) == {"detail_level": {"value": "deep", "confidence": 0.8}}
    assert mem.parse_refresh_json('{"directness": {"value": "direct", "confidence": 0.7}}') == \
        {"directness": {"value": "direct", "confidence": 0.7}}
    assert mem.parse_refresh_json("no idea what happened") is None


def test_merge_refresh_higher_confidence_wins():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    mem.merge_refresh(p, {"detail_level": {"value": "deep", "confidence": 0.9}, "observations": []})
    assert p["dimensions"]["detail_level"]["value"] == "deep"


def test_merge_refresh_lower_confidence_loses():
    p = mem.empty_profile()
    for _ in range(3):
        mem.apply_signals(p, _signal({"detail_level": "short"}))
    mem.merge_refresh(p, {"detail_level": {"value": "deep", "confidence": 0.5}, "observations": []})
    assert p["dimensions"]["detail_level"]["value"] == "short"


def test_merge_refresh_observations_novel_only():
    p = mem.empty_profile()
    mem.merge_refresh(p, {"observations": [{"text": "You like short answers.", "dimension": "detail_level"}]})
    mem.merge_refresh(p, {"observations": [
        {"text": "You like short answers.", "dimension": "detail_level"},
        {"text": "You argue for lines.", "dimension": "pushback_appetite"},
    ]})
    texts = [o["text"] for o in p["observations"]]
    assert texts.count("You like short answers.") == 1
    assert "You argue for lines." in texts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 8 new tests FAIL (`AttributeError: module ... has no attribute 'build_relationship_card'` etc.)

- [ ] **Step 3: Implement** — append to `screenplay_cowriter/memory.py`:

```python
DIM_LABELS = {
    "detail_level": ("prefers short, tight answers", "likes to go deep and wander"),
    "directness": ("prefers gentle, eased-in notes", "wants the note straight, no softening"),
    "probe_appetite": ("dislikes being probed before answers", "engages well with probing questions"),
    "pushback_appetite": ("prefers Sam to defer", "enjoys Sam pushing back on choices"),
}

# Human-readable observations auto-created the moment a dimension first gates.
OBS_TEMPLATES = {
    ("detail_level", "short"): "You tend toward short, tight answers.",
    ("detail_level", "deep"): "You like to go deep and wander.",
    ("directness", "gentle"): "You like notes eased in gently.",
    ("directness", "direct"): "You want the note straight — no softening.",
    ("probe_appetite", "low"): "You'd rather skip the probing and get to it.",
    ("probe_appetite", "high"): "You engage well with probing questions.",
    ("pushback_appetite", "low"): "You tend to accept suggestions readily.",
    ("pushback_appetite", "high"): "You enjoy sparring over choices — you argue for what you believe.",
}

CARD_RULES = (
    " Adapt your tone accordingly. Rules: this informs TONE, never content. "
    "Never quote the memory to the writer (\"you always say…\" is forbidden). "
    "If the writer contradicts a remembered preference this turn, the current turn wins."
)


def _maybe_add_template_observation(profile, dim):
    """When a dimension first crosses the gate, record a human-readable observation."""
    d = profile["dimensions"][dim]
    if d["value"] not in DIMENSION_POLES[dim] or d["confidence"] < BEHAVIOR_GATE:
        return
    ev = d["evidence"]
    if (ev["pos"] + ev["neg"]) < MIN_EVIDENCE:
        return
    text = OBS_TEMPLATES.get((dim, d["value"]))
    if not text:
        return
    if any(o["text"] == text and not o["suppressed"] for o in profile["observations"]):
        return
    profile["observations"].append({
        "id": "obs_" + uuid.uuid4().hex[:8],
        "text": text,
        "dimension": dim,
        "confidence": d["confidence"],
        "source": "rules",
        "contradictions": 0,
        "suppressed": False,
        "created": time.time(),
        "updated": time.time(),
    })


def _note_contradictions(profile, signals):
    """An explicit tone statement against a gated preference counts as a
    contradiction on that dimension's observations; auto-suppress at 2+."""
    for dim, pole in signals.get("poles", {}).items():
        d = profile["dimensions"].get(dim)
        if not d or d["value"] not in DIMENSION_POLES[dim] or d["value"] == pole:
            continue
        if d["confidence"] < BEHAVIOR_GATE:
            continue
        for obs in profile["observations"]:
            if obs["dimension"] == dim and not obs["suppressed"]:
                obs["contradictions"] += 1
                if obs["contradictions"] >= 2:
                    obs["suppressed"] = True


def build_relationship_card(profile):
    gated = dimension_gate(profile)
    if not gated:
        return None
    phrases = []
    for dim, entry in sorted(gated.items()):
        idx = 0 if entry["value"] == DIMENSION_POLES[dim][0] else 1
        phrases.append(DIM_LABELS[dim][idx])
    topics = {k: v for k, v in profile.get("topic_gravity", {}).items() if v > 0}
    if topics and sum(topics.values()) >= 10:
        top = max(topics, key=topics.get)
        if topics[top] / sum(topics.values()) >= 0.4:
            phrases.append(f"keeps returning to {top}-level concerns")
    obs_lines = [o["text"] for o in profile.get("observations", [])
                 if not o["suppressed"] and o["confidence"] >= BEHAVIOR_GATE]
    card = ("ABOUT HOW YOU TWO WORK TOGETHER — what you've noticed about how this writer "
            "likes to work: " + "; ".join(phrases) + ".")
    if obs_lines:
        card += " Observations: " + " ".join(f"• {t}" for t in obs_lines[:3])
    return card + CARD_RULES


def cold_start_line(profile):
    if profile["meta"]["total_turns_observed"] > 0:
        return None
    if profile["observations"]:
        return None
    return ("A light opening question for a brand-new relationship (optional to answer): "
            "\"Before we dive in — what's the one thing you're trying to fix in this draft?\"")


def refresh_prompt(recent_messages):
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in recent_messages)
    return (
        "RELATIONSHIP MEMORY REFRESH — read the conversation below between a writer and "
        "their co-writer. Based ONLY on explicit evidence in it, what does this writer "
        "prefer? Output STRICT JSON object with keys detail_level, directness, "
        "probe_appetite, pushback_appetite — each {\"value\": "
        "\"short|deep|balanced|gentle|direct|low|high|medium|no_evidence\", "
        "\"confidence\": 0.0-1.0} — plus \"observations\": a list of 0-3 objects "
        "{\"text\": \"plain language, what the writer expects/accepts/argues about\", "
        "\"dimension\": \"detail_level|directness|probe_appetite|pushback_appetite|"
        "topic_gravity|general\"}. Do NOT invent. If unclear, use \"no_evidence\".\n\n"
        "CONVERSATION:\n" + transcript
    )


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.S)


def parse_refresh_json(text):
    if not text:
        return None
    m = _JSON_OBJ_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def novel_observation(profile, text):
    t = text.strip().lower()
    if not t:
        return False
    for obs in profile["observations"]:
        if obs["suppressed"]:
            continue
        o = obs["text"].strip().lower()
        if o == t or (len(t) > 20 and (o in t or t in o)):
            return False
    return True


def merge_refresh(profile, proposal):
    if not isinstance(proposal, dict):
        return profile
    for dim in DIMENSION_POLES:
        entry = proposal.get(dim)
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        conf = entry.get("confidence")
        if value in (None, "no_evidence") or not isinstance(conf, (int, float)):
            continue
        conf = max(0.0, min(1.0, conf))
        if value not in DIMENSION_POLES[dim] and value != NEUTRAL[dim]:
            continue
        cur = profile["dimensions"].get(dim)
        if cur is not None and conf <= cur["confidence"]:
            continue  # the refresh never overrides stronger existing evidence
        d = _dim_state(profile, dim)
        d["value"] = value
        d["confidence"] = round(conf, 2)
        d["evidence"] = {"pos": round(conf * 20), "neg": round((1 - conf) * 20)}
        d["last_updated"] = time.time()
    for obs in proposal.get("observations", [])[:3]:
        if not isinstance(obs, dict):
            continue
        text = (obs.get("text") or "").strip()
        if not text or not novel_observation(profile, text):
            continue
        profile["observations"].append({
            "id": "obs_" + uuid.uuid4().hex[:8],
            "text": text,
            "dimension": obs.get("dimension", "general"),
            "confidence": 0.6,
            "source": "refresh",
            "contradictions": 0,
            "suppressed": False,
            "created": time.time(),
            "updated": time.time(),
        })
    return profile
```

Add `import json` to the module's imports (top of `memory.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/memory.py tests/test_writer_memory.py
git commit -m "feat: writer-memory card, cold start, refresh prompt/parse/merge"
```

---

### Task 3: `WriterMemory` wrapper — I/O, locks, observe, suppress, refresh

**Files:**
- Modify: `screenplay_cowriter/memory.py` (append)
- Modify: `tests/test_writer_memory.py` (append)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces (used by Tasks 4–7):
  - `WriterMemory(path: str)`; `WriterMemory.load(path) -> WriterMemory` (tolerant); `.save()`
  - `.observe(user_text, turn_kind, was_pending, previous_reply=None)`
  - `.card_text() -> str | None`; `.cold_start_line() -> str | None`
  - `.refresh_due() -> bool`; `.maybe_refresh_async(client, recent_messages)`
  - `.refresh(client, recent_messages)` (synchronous — used by the webapp button)
  - `.suppress(obs_id: str) -> bool`; `.to_dict() -> dict`

- [ ] **Step 1: Write the failing tests** (append)

```python
class _FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []
    def chat(self, messages, **kw):
        self.calls.append(messages)
        return self.reply


def test_round_trip_and_observe(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(3):
        m.observe("keep it short please", "idea", False, None)
    m2 = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    assert m2.profile["meta"]["total_turns_observed"] == 3
    assert m2.card_text() is not None


def test_corrupt_file_backed_up(tmp_path):
    p = tmp_path / "writer_profile.json"
    p.write_text("{ not json", encoding="utf-8")
    m = mem.WriterMemory.load(str(p))
    assert m.profile["meta"]["total_turns_observed"] == 0
    assert (tmp_path / "writer_profile.json.bak").exists()


def test_suppress_persists(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(3):
        m.observe("just tell me straight what's wrong", "idea", False, None)
    obs = next(o for o in m.profile["observations"] if not o["suppressed"])
    assert m.suppress(obs["id"]) is True
    assert m.suppress(obs["id"]) is False  # already suppressed
    m2 = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    assert next(o for o in m2.profile["observations"] if o["id"] == obs["id"])["suppressed"] is True


def test_refresh_due_and_reset(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    assert not m.refresh_due()
    for _ in range(10):
        m.observe("hi there", "question", False, None)
    assert m.refresh_due()
    m._refresh_sync(_FakeClient('{"observations": []}'), [{"role": "user", "content": "hi"}])
    assert not m.refresh_due()


def test_refresh_sync_merges_proposal(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "writer_profile.json"))
    for _ in range(10):
        m.observe("hi there", "question", False, None)
    client = _FakeClient('{"detail_level": {"value": "deep", "confidence": 0.8}, '
                         '"observations": [{"text": "Likes deep answers.", "dimension": "detail_level"}]}')
    m._refresh_sync(client, [{"role": "user", "content": "hi"}])
    assert m.profile["dimensions"]["detail_level"]["value"] == "deep"
    assert m.profile["meta"]["refresh_count"] == 1
    assert len(client.calls) == 1
    assert "RELATIONSHIP MEMORY REFRESH" in client.calls[0][0]["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 5 new tests FAIL (`AttributeError: ... WriterMemory`)

- [ ] **Step 3: Implement** — append to `screenplay_cowriter/memory.py`:

```python
_FILE_LOCK = threading.RLock()  # module-level: instances are per-request, file I/O must serialize


class WriterMemory:
    def __init__(self, path, profile=None):
        self.path = path
        self.profile = profile if profile is not None else empty_profile()
        self._refresh_in_flight = False

    @classmethod
    def load(cls, path):
        with _FILE_LOCK:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        return cls(path, profile=data)
                except (ValueError, json.JSONDecodeError):
                    # corrupt: back it up, start fresh — chat must never break
                    try:
                        os.replace(path, path + ".bak")
                    except OSError:
                        pass
        return cls(path)

    def save(self):
        with _FILE_LOCK:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2, ensure_ascii=False)

    def to_dict(self):
        return self.profile

    def observe(self, user_text, turn_kind, was_pending, previous_reply=None):
        signals = extract_signals(user_text, turn_kind, was_pending, previous_reply)
        apply_signals(self.profile, signals)
        _note_contradictions(self.profile, signals)
        for dim in list(DIMENSION_POLES):
            _maybe_add_template_observation(self.profile, dim)
        self.profile["meta"]["total_turns_observed"] += 1
        self.save()

    def card_text(self):
        return build_relationship_card(self.profile)

    def cold_start_line(self):
        return cold_start_line(self.profile)

    def suppress(self, obs_id):
        for obs in self.profile["observations"]:
            if obs["id"] == obs_id:
                if obs["suppressed"]:
                    return False  # already forgotten
                obs["suppressed"] = True
                self.save()
                return True
        return False

    def refresh_due(self):
        meta = self.profile["meta"]
        return (meta["total_turns_observed"] - meta["turns_at_last_refresh"]) >= REFRESH_INTERVAL

    def maybe_refresh_async(self, client, recent_messages):
        """Fire-and-forget: never blocks the writer's reply. Double-checked so
        concurrent requests can't pile up refreshes (see _refresh_worker)."""
        if self._refresh_in_flight or not self.refresh_due():
            return
        self._refresh_in_flight = True
        t = threading.Thread(target=self._refresh_worker, args=(client, recent_messages), daemon=True)
        t.start()

    def _refresh_worker(self, client, recent_messages):
        try:
            with _FILE_LOCK:
                if not self.refresh_due():
                    return
            self._refresh_sync(client, recent_messages)
        finally:
            self._refresh_in_flight = False

    def refresh(self, client, recent_messages):
        """Synchronous refresh — used by the webapp's 'refresh now' button."""
        self._refresh_sync(client, recent_messages)

    def _refresh_sync(self, client, recent_messages):
        reply = client.chat([{"role": "user", "content": refresh_prompt(recent_messages)}])
        proposal = parse_refresh_json(reply)
        with _FILE_LOCK:
            if proposal:
                merge_refresh(self.profile, proposal)
            self.profile["meta"]["turns_at_last_refresh"] = self.profile["meta"]["total_turns_observed"]
            self.profile["meta"]["last_refresh"] = time.time()
            self.profile["meta"]["refresh_count"] += 1
            self.save()
```

Add `import json`, `import os`, `import threading` to the module imports (top of `memory.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 22 passed

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/memory.py tests/test_writer_memory.py
git commit -m "feat: WriterMemory wrapper — I/O, locks, observe, suppress, refresh"
```

---

### Task 4: Engine + context integration (card injection, cold start, observe)

**Files:**
- Modify: `screenplay_cowriter/context.py` (`build_system_prompt`, ~line 126)
- Modify: `screenplay_cowriter/engine.py` (`CoWriterEngine.__init__`, `send_message`)
- Modify: `tests/test_writer_memory.py` (append engine tests)

**Interfaces:**
- Consumes: Task 3 `WriterMemory`.
- Produces (used by Task 5–6):
  - `build_system_prompt(script_ctx, report_ctx, persona, mode, relationship_card=None, cold_start_line=None)`
  - `CoWriterEngine(client, script_ctx, report_ctx, history_window=16, store=None, memory=None)`
  - `send_message` calls `self.memory.observe(...)` each turn and `self.memory.maybe_refresh_async(self.client, recent)` after a successful turn.

- [ ] **Step 1: Write the failing tests** (append)

```python
def _make_engine(client, memory=None):
    from screenplay_cowriter.engine import CoWriterEngine
    from screenplay_cowriter.context import ScriptContext, ReportContext
    return CoWriterEngine(client, ScriptContext({}), ReportContext(None), memory=memory)


class _CapturingClient:
    def __init__(self, reply="Okay — here's my thought."):
        self.reply = reply
        self.prompts = []
    def chat(self, messages, **kw):
        self.prompts.append(next(m["content"] for m in messages if m["role"] == "system"))
        return self.reply


def test_memory_none_prompt_has_no_card():
    client = _CapturingClient()
    engine = _make_engine(client)  # no memory
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "what about scene 3?")
    assert "ABOUT HOW YOU TWO WORK TOGETHER" not in client.prompts[0]
    assert "LANGUAGE" in client.prompts[0]  # base content still present


def test_card_injected_when_gated(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "p.json"))
    for _ in range(3):
        m.observe("just tell me straight what's wrong", "idea", False, None)
    client = _CapturingClient()
    engine = _make_engine(client, memory=m)
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "what about scene 3?")
    assert "ABOUT HOW YOU TWO WORK TOGETHER" in client.prompts[0]


def test_cold_start_line_only_first_turn(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "p2.json"))
    client = _CapturingClient()
    engine = _make_engine(client, memory=m)
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "hi")
    assert "what's the one thing you're trying to fix" in client.prompts[0]
    engine.send_message(s, "hi again")
    assert "what's the one thing you're trying to fix" not in client.prompts[1]


def test_observe_called_each_turn(tmp_path):
    m = mem.WriterMemory.load(str(tmp_path / "p3.json"))
    client = _CapturingClient()
    engine = _make_engine(client, memory=m)
    s = mem_mod.Session.new(title="t")
    engine.send_message(s, "what do you think?")
    engine.send_message(s, "what about the ending?")
    assert m.profile["meta"]["total_turns_observed"] == 2
```

Add at the top of the test file: `from screenplay_cowriter import models as mem_mod`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 4 new tests FAIL — `TypeError: CoWriterEngine.__init__() got an unexpected keyword argument 'memory'`

- [ ] **Step 3a: Modify `context.py::build_system_prompt`**

Replace the `return (...)` block with:

```python
def build_system_prompt(script_ctx, report_ctx, persona, mode, relationship_card=None, cold_start_line=None):
    title = script_ctx.title or report_ctx.title or "this screenplay"
    prompt = (
        f"{persona_text(persona)}\n\n"
        f"{mode_text(mode)}\n\n"
        f"You're discussing the screenplay \"{title}\" with its writer. Here is the "
        f"standing analysis report for reference:\n\n{report_ctx.compact_summary()}\n\n"
        f"When specific scene text is relevant to the current question, it will be "
        f"provided below as additional context for this turn. If it isn't provided "
        f"and you need exact wording to answer precisely, say so rather than guessing "
        f"at exact lines from memory.\n\n{LANGUAGE_META_INSTRUCTION}"
    )
    if relationship_card:
        prompt += f"\n\n{relationship_card}"
    if cold_start_line:
        prompt += f"\n\n{cold_start_line}"
    return prompt
```

- [ ] **Step 3b: Modify `engine.py`**

`__init__` — add `memory=None` param and attribute:

```python
    def __init__(self, client, script_ctx, report_ctx, history_window=HISTORY_WINDOW, store=None, memory=None):
        self.client = client
        self.script_ctx = script_ctx
        self.report_ctx = report_ctx
        self.history_window = history_window
        self.store = store
        self.memory = memory
```

In `send_message`, immediately after the `was_pending` block (before `scene_refs = extract_scene_refs(user_text)`) add:

```python
        if self.memory is not None:
            # Capture the cold-start line BEFORE observe(): observe bumps
            # total_turns_observed, which would otherwise kill it on turn 1.
            cold_start_line = self.memory.cold_start_line() if not branch.messages else None
            prev_reply = branch.messages[-1].content if (was_pending and branch.messages) else None
            self.memory.observe(user_text, turn_kind, was_pending, prev_reply)
        else:
            cold_start_line = None
        relationship_card = self.memory.card_text() if self.memory is not None else None
```

In the **probe path**, change the `build_system_prompt(...)` call to:

```python
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
            ) + "\n\n" + PROBE_SYSTEM_PROMPT
```

In the **full-turn path**, change the `build_system_prompt(...)` call to:

```python
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
            )
```

After the `if self.store is not None: self.store.save(session)` line, add:

```python
        if self.memory is not None:
            recent = [m.to_dict() for m in branch.messages[-self.history_window:]]
            self.memory.maybe_refresh_async(self.client, recent)
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/test_writer_memory.py -q`
Expected: 26 passed

- [ ] **Step 5: Run the regression suites that exercise the engine with no memory**

Run: `python -m pytest tests/test_peer_guardrails.py tests/test_chat_language_meta.py tests/test_positive.py tests/test_negative.py tests/test_neutral_edge.py tests/test_stress.py tests/test_fix_batch.py -q`
Expected: all pass (proves `memory=None` is behavior-identical)

- [ ] **Step 6: Commit**

```bash
git add screenplay_cowriter/context.py screenplay_cowriter/engine.py tests/test_writer_memory.py
git commit -m "feat: engine+context integrate writer memory (observe, card, cold start)"
```

---

### Task 5: Cowriter CLI/server optional `--memory-path`

**Files:**
- Modify: `screenplay_cowriter/server.py` (add module global + argparse + engine construction)
- Modify: `screenplay_cowriter/cli.py` (chat command engine construction)

**Interfaces:**
- Consumes: Task 3 `WriterMemory`, Task 4 `CoWriterEngine(memory=...)`.
- Produces: `python -m screenplay_cowriter.server --memory-path <path>` and the CLI chat command accept an optional `--memory-path` (default off = today's behavior).

- [ ] **Step 1: Locate the engine construction sites**

Run: `grep -n "CoWriterEngine(" screenplay_cowriter/server.py screenplay_cowriter/cli.py`
Expected: one hit in `server.py` (`send_message` route) and one in `cli.py` (the `chat` command's loop).

- [ ] **Step 2: Modify `server.py`**

Add next to the existing `store: SessionStore = None` module global:

```python
memory_path: str = None  # optional writer relationship memory file (set in main())
```

In the `send_message` route, replace:

```python
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store)
```

with:

```python
    memory = None
    if memory_path:
        from .memory import WriterMemory
        memory = WriterMemory.load(memory_path)
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory)
```

In `main()`, add the argument and assignment:

```python
    parser.add_argument("--memory-path", default=None, help="Optional writer relationship memory file")
    ...
    global memory_path
    memory_path = args.memory_path
```

- [ ] **Step 3: Modify `cli.py`** (three precise edits):

Edit 1 — change `run_repl` (line 55) to accept and use a `memory` param:

```python
def run_repl(session: Session, store: SessionStore, client: LlamaServerClient, memory=None):
    script_ctx, report_ctx = _load_contexts(session)
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory)
```

Edit 2 — in `cmd_chat`, build the memory from the flag just before the `run_repl` call:

```python
    memory = None
    if args.memory_path:
        from .memory import WriterMemory
        memory = WriterMemory.load(args.memory_path)

    run_repl(session, store, client, memory=memory)
```

Edit 3 — add the argument to the `chat` subparser (after the existing `--sessions-dir` line):

```python
    p_chat.add_argument("--memory-path", default=None, help="Optional writer relationship memory file")
```

- [ ] **Step 4: Verify nothing regressed**

Run: `python -m pytest tests/test_webapp_api.py tests/test_fix_batch.py -q`
Expected: all pass (webapp and store paths untouched by the flag)

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/server.py screenplay_cowriter/cli.py
git commit -m "feat: optional --memory-path for cowriter CLI/server"
```

---

### Task 6: Webapp — wire memory + endpoints + mock marker

**Files:**
- Modify: `screenplay_studio/webapp_server.py` (`_load_session_and_engine` + 3 routes)
- Modify: `tests/mock_unified_server.py` (refresh marker)
- Modify: `tests/test_webapp_api.py` (3 new tests + isolation helper)

**Interfaces:**
- Consumes: Task 3 `WriterMemory`, Task 4 `CoWriterEngine(memory=...)`, Task 5 mock pattern.
- Produces:
  - `_load_session_and_engine` constructs the engine with `memory=WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))`.
  - `GET /api/writer-memory` → `{"profile": dict, "card": str | None}`
  - `POST /api/writer-memory/observations/<obs_id>/suppress` → `{"ok": true}` or 404
  - `POST /api/writer-memory/refresh` body `{"project", "session_id"}` → refreshed `{"profile", "card"}`

- [ ] **Step 1: Add the mock refresh marker** — in `tests/mock_unified_server.py`, inside `chat_completions()`, immediately after the request payload/messages are parsed and **before** the persona-marker detection, add:

```python
    if "RELATIONSHIP MEMORY REFRESH" in user:
        return _reply(json.dumps({
            "detail_level": {"value": "deep", "confidence": 0.8},
            "directness": {"value": "direct", "confidence": 0.7},
            "probe_appetite": {"value": "no_evidence", "confidence": 0.0},
            "pushback_appetite": {"value": "no_evidence", "confidence": 0.0},
            "observations": [{"text": "The writer likes to explore character motives at length.",
                              "dimension": "topic_gravity"}],
        }))
```

(The file already computes a `user` variable from the messages and imports `json` — confirm with `grep -n "json" tests/mock_unified_server.py`; add `import json` if absent.)

- [ ] **Step 2: Write the failing webapp tests** — append to `TestChatFlow` in `tests/test_webapp_api.py`:

```python
    def _reset_writer_memory(self):
        import os
        from screenplay_studio import webapp_server
        p = os.path.join(webapp_server.PROJECTS_DIR, "writer_profile.json")
        if os.path.exists(p):
            os.remove(p)

    def test_get_writer_memory(self, http_client):
        self._reset_writer_memory()
        resp = http_client.get("/api/writer-memory")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "profile" in data and "card" in data
        assert data["profile"]["meta"]["total_turns_observed"] == 0

    def test_suppress_observation_via_api(self, http_client):
        self._reset_writer_memory()
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        for _ in range(3):
            http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages",
                             json={"text": "just tell me straight, what's wrong with scene 1"})
        data = http_client.get("/api/writer-memory").get_json()
        obs = next(o for o in data["profile"]["observations"] if not o["suppressed"])
        resp = http_client.post(f"/api/writer-memory/observations/{obs['id']}/suppress")
        assert resp.status_code == 200
        data2 = http_client.get("/api/writer-memory").get_json()
        assert next(o for o in data2["profile"]["observations"] if o["id"] == obs["id"])["suppressed"] is True

    def test_suppress_unknown_observation_404(self, http_client):
        self._reset_writer_memory()
        resp = http_client.post("/api/writer-memory/observations/obs_nope/suppress")
        assert resp.status_code == 404

    def test_refresh_endpoint_merges_mock_proposal(self, http_client):
        self._reset_writer_memory()
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages", json={"text": "hello"})
        resp = http_client.post("/api/writer-memory/refresh",
                                json={"project": project, "session_id": sid})
        assert resp.status_code == 200
        profile = resp.get_json()["profile"]
        assert profile["dimensions"]["detail_level"]["value"] == "deep"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_webapp_api.py -k "writer_memory" -q`
Expected: FAIL — `404 Not Found` for `/api/writer-memory`

- [ ] **Step 4: Implement the webapp changes**

In `webapp_server.py`:

1. In `_load_session_and_engine`, replace the final engine construction:

```python
    memory = None
    try:
        mem_mod = _import_cowriter("memory")
        memory = mem_mod.WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))
    except Exception:
        memory = None  # never let memory wiring break the chat
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory)
    return session, engine, store
```

2. Add a helper + three routes near the other chat routes (after the `/settings` route):

```python
def _load_writer_memory():
    mem_mod = _import_cowriter("memory")
    return mem_mod.WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))


@app.route("/api/writer-memory", methods=["GET"])
def get_writer_memory():
    try:
        mem = _load_writer_memory()
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    return jsonify({"profile": mem.to_dict(), "card": mem.card_text()})


@app.route("/api/writer-memory/observations/<obs_id>/suppress", methods=["POST"])
def suppress_writer_observation(obs_id):
    try:
        mem = _load_writer_memory()
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    if not mem.suppress(obs_id):
        return _error("Observation not found.", 404)
    return jsonify({"ok": True})


@app.route("/api/writer-memory/refresh", methods=["POST"])
def refresh_writer_memory():
    body = request.get_json() or {}
    project = body.get("project")
    session_id = body.get("session_id")
    if not project or not session_id:
        return _error("project and session_id are required.", 400)
    try:
        session, _, _ = _load_session_and_engine(project, session_id)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    try:
        mem = _load_writer_memory()
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    client = LlamaServerClient(base_url=session.server_url or CONFIG["server_url"],
                               model=session.model_id, timeout=CONFIG["timeout"])
    recent = [m.to_dict() for m in session.branch.messages[-16:]]
    mem.refresh(client, recent)
    return jsonify({"profile": mem.to_dict(), "card": mem.card_text()})
```

(`os` is already imported in `webapp_server.py`; `_error`, `LlamaServerClient`, `CONFIG`, `CowriterUnavailableError` already exist.)

- [ ] **Step 5: Run the webapp memory tests**

Run: `python -m pytest tests/test_webapp_api.py -k "writer_memory" -q`
Expected: 4 passed

- [ ] **Step 6: Run the full webapp suite (regression — memory now wired by default)**

Run: `python -m pytest tests/test_webapp_api.py -q`
Expected: all pass (the memory wiring is inert for existing tests: fresh profile ⇒ no card, no due refresh)

- [ ] **Step 7: Commit**

```bash
git add screenplay_studio/webapp_server.py tests/mock_unified_server.py tests/test_webapp_api.py
git commit -m "feat: webapp wires writer memory + GET/suppress/refresh endpoints"
```

---

### Task 7: Frontend — "Sam's notes on you" modal

**Files:**
- Modify: `screenplay_studio/webapp/index.html` (partner card + modal markup)
- Modify: `screenplay_studio/webapp/app.js` (open/load/render/suppress/refresh)
- Modify: `screenplay_studio/webapp/style.css` (panel styles)

**Interfaces:**
- Consumes: Task 6 endpoints `GET /api/writer-memory`, `POST /api/writer-memory/observations/<id>/suppress`, `POST /api/writer-memory/refresh`.
- Produces: the `#sam-notes-btn` in `#partner-card` opens `#sam-notes-modal` (reuses the existing `.modal-overlay`/`.modal` pattern from the settings modal), lists gated dimensions + observations, per-observation "forget", and a "Refresh now" button.

- [ ] **Step 1: Verify the existing modal pattern**

Run: `sed -n '248,270p' screenplay_studio/webapp/index.html`
Expected: the settings modal markup — `<div id="settings-modal" class="modal-overlay" style="display:none;">…</div>` with `.modal-label`, `.modal-hint`, `.modal-actions` classes. Copy this structure.

- [ ] **Step 2: Add markup to `index.html`**

In `#partner-card` (after the `#reset-partner-btn` button), add:

```html
          <button id="sam-notes-btn" class="btn-secondary btn-small" title="What Sam has noticed about how you work together" type="button">Sam's notes on you</button>
```

Immediately before the settings modal (`<!-- Settings modal -->`), add:

```html
<!-- Sam's notes on you modal -->
<div id="sam-notes-modal" class="modal-overlay" style="display:none;">
  <div class="modal">
    <h3 class="modal-label">📝 Sam's notes on you</h3>
    <p class="modal-hint">Inferred from how you've worked together — you stay the editor. Nothing here is final; forget anything that's wrong.</p>
    <div id="sam-notes-dimensions" class="sam-notes-dimensions"></div>
    <ul id="sam-notes-observations" class="sam-notes-observations"></ul>
    <p id="sam-notes-empty" class="modal-hint">Nothing yet — Sam is still getting to know you. It grows as you talk.</p>
    <div class="modal-actions">
      <button id="sam-notes-refresh" class="btn-secondary btn-small" type="button">Refresh now</button>
      <button id="sam-notes-close" class="btn-primary btn-small" type="button">Close</button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add JS to `app.js`**

Find the `resetToPartner` function definition and add after it:

```javascript
async function loadSamNotes() {
  const data = await api("/writer-memory");
  renderSamNotes(data);
}
function renderSamNotes(data) {
  const dims = $("#sam-notes-dimensions"), obsList = $("#sam-notes-observations"), empty = $("#sam-notes-empty");
  dims.innerHTML = "";
  obsList.innerHTML = "";
  const profile = data.profile || {};
  const gated = Object.entries(profile.dimensions || {}).filter(([, d]) => d && d.confidence >= 0.6 && d.value !== "balanced" && d.value !== "medium");
  gated.forEach(([name, d]) => {
    const chip = document.createElement("span");
    chip.className = "sam-notes-chip";
    chip.textContent = `${name.replace(/_/g, " ")}: ${d.value} (${Math.round(d.confidence * 100)}%)`;
    dims.appendChild(chip);
  });
  const observations = (profile.observations || []).filter((o) => !o.suppressed);
  observations.forEach((o) => {
    const li = document.createElement("li");
    li.className = "sam-notes-obs";
    const text = document.createElement("span");
    text.textContent = o.text;
    const forget = document.createElement("button");
    forget.className = "btn-secondary btn-small";
    forget.textContent = "forget this";
    forget.addEventListener("click", async () => {
      await api(`/writer-memory/observations/${encodeURIComponent(o.id)}/suppress`, { method: "POST" });
      loadSamNotes();
    });
    li.append(text, forget);
    obsList.appendChild(li);
  });
  empty.style.display = (!gated.length && !observations.length) ? "" : "none";
}
async function openSamNotes() {
  openModal("#sam-notes-modal");
  await loadSamNotes();
}
function closeSamNotes() {
  closeModal("#sam-notes-modal");
}
```

Wire the buttons in the init section (next to the existing `#reset-partner-btn` listener):

```javascript
  $("#sam-notes-btn").addEventListener("click", () => { openModal("#sam-notes-modal"); loadSamNotes(); });
  $("#sam-notes-close").addEventListener("click", () => closeModal("#sam-notes-modal"));
  $("#sam-notes-refresh").addEventListener("click", async () => {
    if (!state.currentProject || !state.currentSession) return;
    await api("/writer-memory/refresh", {
      method: "POST",
      body: JSON.stringify({ project: state.currentProject, session_id: state.currentSession }),
    });
    loadSamNotes();
  });
```

The app already has `openModal`/`closeModal` helpers (used by the settings modal at app.js:145/2525) — reuse them; do NOT set `style.display` directly. The `api()` helper (app.js) auto-adds the `Content-Type: application/json` header when `body` is a JSON string, so no explicit `headers` argument is needed.

- [ ] **Step 4: Add CSS to `style.css`** — append after the partner-card block:

```css
/* Sam's notes on you */
.sam-notes-dimensions { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.sam-notes-chip {
  background: var(--bg-soft); border: 1px solid var(--border); border-radius: 999px;
  padding: 3px 10px; font-size: 12px; color: var(--text-soft);
}
.sam-notes-observations { list-style: none; padding: 0; margin: 0; }
.sam-notes-obs {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px;
}
```

Verify the variable names (`--bg-soft`, `--border`, `--text-soft`) exist: `grep -n -- "--bg-soft\|--border\|--text-soft" screenplay_studio/webapp/style.css | head -3`. If they differ, use the actual names found.

- [ ] **Step 5: Validate JS + HTML**

Run: `node --check screenplay_studio/webapp/app.js && echo JS_OK`
Run: `grep -n "sam-notes" screenplay_studio/webapp/index.html screenplay_studio/webapp/app.js | head`
Expected: `JS_OK` and all three IDs (`sam-notes-btn`, `sam-notes-modal`, `sam-notes-refresh`) present in both files.

- [ ] **Step 6: Commit**

```bash
git add screenplay_studio/webapp/index.html screenplay_studio/webapp/app.js screenplay_studio/webapp/style.css
git commit -m "feat: Sam's notes on you modal (view, forget, refresh)"
```

---

### Task 8: Docs + full suite + review

**Files:**
- Modify: `NOTES.md` (Completed entry + Current State + deferred list)
- Modify: `docs/ARCHITECTURE.md` (memory module, endpoints, writer_profile.json)
- Modify: `docs/DATA_FORMATS.md` (`writer_profile.json` section)

- [ ] **Step 1: Update `NOTES.md`** — add a `2026-08-12 — Writer relationship memory (v2)` entry to Completed: writer-level `writer_profile.json` (studio_projects/), `screenplay_cowriter/memory.py` (rules + refresh), 0.6 confidence gate with MIN_EVIDENCE=3, card injection via `build_system_prompt(relationship_card=...)`, cold-start line, `--memory-path` for cowriter CLI/server, webapp `GET/POST /api/writer-memory*` endpoints, "Sam's notes on you" modal. Update Current State (new test count) and remove the "Deferred (v2): relationship memory" line.

- [ ] **Step 2: Update `docs/ARCHITECTURE.md`** — add `memory.py` to the cowriter module tree and the three endpoints to the webapp endpoint table; note the writer-level profile path and the `memory=` engine param.

- [ ] **Step 3: Update `docs/DATA_FORMATS.md`** — add a `writer_profile.json` subsection under the studio layout describing the schema in the spec §5 (dimensions with pos/neg evidence, observations, meta).

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: 328 existing + 26 `test_writer_memory.py` + 4 new webapp tests, all passing.

- [ ] **Step 5: Code review + fix** — dispatch `code-reviewer-deepseek-flash` over the full batch (memory.py logic, engine integration, webapp endpoints, modal wiring). Fix anything real it finds, re-run the suite, and commit the fixes.

- [ ] **Step 6: Commit docs**

```bash
git add NOTES.md docs/ARCHITECTURE.md docs/DATA_FORMATS.md
git commit -m "docs: writer relationship memory (NOTES, ARCHITECTURE, DATA_FORMATS)"
```
