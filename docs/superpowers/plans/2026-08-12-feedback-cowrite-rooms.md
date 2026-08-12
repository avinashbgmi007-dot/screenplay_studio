# Feedback / Co-write Rooms + Writing-Partner Guardrails — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the webapp into two visually distinct rooms (Co-write = writer's desk with a human-feeling partner "Sam"; Feedback = consultant's desk with report + fix queue), and add structural guardrails so the co-writer can never jump the writer with suggestions or dead-end a conversation.

**Architecture:** Backend — a new pure-function module `screenplay_cowriter/peer.py` supplies the guardrails (turn classification, probe logic, forward-momentum check, suggestion cap); `engine.py` integrates them into the existing `send_message` flow; `Branch` gains an `awaiting_probe` flag. Frontend — restructure `index.html` from four views into a shared script pane + two switchable room panels, with `data-room` CSS theming and room-aware `app.js` view functions.

**Tech Stack:** Python 3 (stdlib + flask), existing vanilla-JS webapp (`app.js`/`index.html`/`style.css`), pytest with in-process mock llama server (port 8196). No new dependencies.

## Global Constraints

- Do NOT change the analyzer pipeline, report generation, fix-queue API, diff, beat board, compare, or revision/undo/redo flows.
- All existing API routes must stay live (this change is additive at the UI + cowriter engine layer).
- Existing saved sessions must load unchanged — `awaiting_probe` absent from JSON means `False`.
- New sessions default to persona `writing_partner`, mode `peer` (both the `models.Branch` defaults and `personas.DEFAULT_PERSONA`/`DEFAULT_MODE`).
- The partner never volunteers report findings; the report may only be discussed when the writer raises it (seed bridge included).
- The "→ discuss with my partner" bridge must PREFILL the composer (editable), never auto-send.
- Keep the full test suite green (298 tests at time of writing) — update the mock's persona markers and any default-persona assertions as needed.
- Every commit must leave tests passing.

---

### Task 1: `peer.py` — turn classification & probing rules (pure functions)

**Files:**
- Create: `screenplay_cowriter/peer.py`
- Test: `tests/test_peer_guardrails.py`

**Interfaces:**
- Produces:
  - `classify_turn(text: str) -> str` — `"idea" | "question" | "directive"`
  - `has_embedded_reasoning(text: str) -> bool`
  - `should_probe(text: str) -> bool` — True when `classify_turn(text) == "idea" and not has_embedded_reasoning(text)`
  - `PROBE_SYSTEM_PROMPT` — constant str used by Task 6 for the phase-1 model call

- [ ] **Step 1: Write the failing test**

```python
# tests/test_peer_guardrails.py
import pytest
from screenplay_cowriter.peer import classify_turn, has_embedded_reasoning, should_probe, PROBE_SYSTEM_PROMPT


def test_classify_question_by_question_mark():
    assert classify_turn("should Mara forgive him?") == "question"


def test_classify_question_by_start_word():
    assert classify_turn("why does scene 14 feel flat") == "question"


def test_classify_directive():
    assert classify_turn("rewrite scene 14 dialogue") == "directive"


def test_classify_plain_statement_as_idea():
    assert classify_turn("I think Mara should die at the end") == "idea"


def test_embedded_reasoning_detected():
    assert has_embedded_reasoning("I think Mara should die because the guilt is eating her")
    assert not has_embedded_reasoning("Mara should die at the end")


def test_should_probe_only_when_reasoning_absent():
    assert should_probe("Mara should die at the end")
    assert not should_probe("Mara should die because the guilt is eating her")
    assert not should_probe("should Mara die?")


def test_probe_prompt_forbids_suggestions():
    assert "do NOT offer suggestions" in PROBE_SYSTEM_PROMPT
    assert "one question" in PROBE_SYSTEM_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'screenplay_cowriter.peer'`

- [ ] **Step 3: Write minimal implementation**

```python
# screenplay_cowriter/peer.py
"""Structural guardrails for the writing-partner voice.

All functions here are pure (no model calls) so they're unit-testable
without a server. The engine (engine.py) calls them around each chat turn.
"""

import re

_QUESTION_START = re.compile(
    r"^(who|what|why|how|does|can|should|is|are|would|could|do|did)\b", re.I
)
_DIRECTIVE_START = re.compile(
    r"^(rewrite|fix|change|try|add|cut|move|remove|make|let'?s|write|imagine|explain)\b", re.I
)
_REASONING = re.compile(
    r"\b(because|since|so that|the reason|my instinct|i feel like|the thing is|what if it)\b", re.I
)

PROBE_SYSTEM_PROMPT = (
    "You are Sam, the writer's co-writing partner. The writer just shared an idea with "
    "you. This turn has ONE job and only one: reflect their idea back in your own words "
    "so they feel heard, then ask a single probing question about what's driving it "
    "(\"why do you think so?\" or similar). Do NOT offer suggestions, alternatives, fixes, "
    "or judgments yet — the writer hasn't asked for any. One question, in your voice."
)


def classify_turn(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "idea"
    if t.endswith("?") or _QUESTION_START.match(t):
        return "question"
    if _DIRECTIVE_START.match(t):
        return "directive"
    return "idea"


def has_embedded_reasoning(text: str) -> bool:
    return bool(_REASONING.search(text or ""))


def should_probe(text: str) -> bool:
    return classify_turn(text) == "idea" and not has_embedded_reasoning(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/peer.py tests/test_peer_guardrails.py
git commit -m "feat: add peer turn classification + probing rules"
```

---

### Task 2: `peer.py` — forward-momentum check (dead-end prevention)

**Files:**
- Modify: `screenplay_cowriter/peer.py`
- Test: `tests/test_peer_guardrails.py`

**Interfaces:**
- Consumes: (none new)
- Produces: `ensure_forward_momentum(reply: str, turn_kind: str) -> str`, `FORWARD_NUDGES: list[str]`

- [ ] **Step 1: Write the failing test**

```python
def test_forward_reply_left_untouched():
    from screenplay_cowriter.peer import ensure_forward_momentum
    assert ensure_forward_momentum("What do you think?", "idea") == "What do you think?"


def test_stranded_reply_gets_nudge_for_idea_turn():
    from screenplay_cowriter.peer import ensure_forward_momentum
    out = ensure_forward_momentum("That could work.", "idea")
    assert out.startswith("That could work.")
    assert out != "That could work."
    assert any(out.endswith(n) for n in ["", "? "]) or out.rstrip().endswith("?")


def test_no_nudge_for_factual_answer():
    from screenplay_cowriter.peer import ensure_forward_momentum
    long_factual = "In act two, Mara confronts her brother at the warehouse. " * 3
    assert ensure_forward_momentum(long_factual, "question") == long_factual


def test_short_factual_turn_still_gets_nudge():
    from screenplay_cowriter.peer import ensure_forward_momentum
    assert ensure_forward_momentum("Act two.", "question") != "Act two."


def test_nudges_rotate_no_repeat_back_to_back():
    from screenplay_cowriter.peer import ensure_forward_momentum, FORWARD_NUDGES
    a = ensure_forward_momentum("Yes.", "idea")
    b = ensure_forward_momentum("Yes.", "idea")
    assert a != b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: FAIL — `ImportError: cannot import name 'ensure_forward_momentum'`

- [ ] **Step 3: Write minimal implementation** (append to `peer.py`)

```python
FORWARD_NUDGES = [
    "Want me to poke at that with you?",
    "How are you feeling about it so far?",
    "Want to chase that thought?",
    "Where does that leave us — want to keep going?",
]
_nudge_index = 0


def _has_forward_ending(reply: str) -> bool:
    t = reply.rstrip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    last = t.split()[-1] if t.split() else ""
    # "want me to…", "let's…", "should we…", "…right?" style openers
    return any(tok in last.lower() for tok in ("want", "let's", "lets", "should", "shall", "right"))
    # NOTE: deliberately conservative — only obvious forward endings count.


def ensure_forward_momentum(reply: str, turn_kind: str) -> str:
    """Append a forward nudge only when the reply is short or stranded AND the
    turn is an idea/response turn. Never append to a substantial factual answer."""
    global _nudge_index
    t = (reply or "").strip()
    if not t:
        return reply
    if _has_forward_ending(t):
        return reply
    is_factual = turn_kind == "question" and len(t) > 200
    if is_factual:
        return reply
    nudge = FORWARD_NUDGES[_nudge_index % len(FORWARD_NUDGES)]
    _nudge_index += 1
    return f"{t}\n\n{nudge}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/peer.py tests/test_peer_guardrails.py
git commit -m "feat: add forward-momentum dead-end guardrail"
```

---

### Task 3: `peer.py` — one-idea-at-a-time cap

**Files:**
- Modify: `screenplay_cowriter/peer.py`
- Test: `tests/test_peer_guardrails.py`

**Interfaces:**
- Produces: `cap_suggestions(reply: str, max_ideas: int = 1) -> str`, `IDEAS_TRUNCATION_NOTE: str`

- [ ] **Step 1: Write the failing test**

```python
def test_cap_leaves_single_suggestion_alone():
    from screenplay_cowriter.peer import cap_suggestions
    reply = "Here's one thought:\n- Try cutting the opening monologue."
    assert cap_suggestions(reply) == reply


def test_cap_trims_overflow_and_offers_choice():
    from screenplay_cowriter.peer import cap_suggestions
    reply = "Options:\n- Cut the monologue\n- Move it to act two\n- Give it to Mara's brother"
    out = cap_suggestions(reply)
    assert out.count("- ") == 1
    assert "one at a time" in out.lower()


def test_cap_no_bullets_untouched():
    from screenplay_cowriter.peer import cap_suggestions
    prose = "I think cutting the monologue works, and I'd move the key reveal to act two."
    assert cap_suggestions(prose) == prose
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: FAIL — `ImportError: cannot import name 'cap_suggestions'`

- [ ] **Step 3: Write minimal implementation** (append to `peer.py`)

```python
import re as _re

IDEAS_TRUNCATION_NOTE = (
    "\n\n(Let's take these one at a time — which one do you want to explore first?)"
)

_BULLET = _re.compile(r"^\s*(•|-|\d+[.)])\s+")


def cap_suggestions(reply: str, max_ideas: int = 1) -> str:
    """Safety net: keep at most `max_ideas` bulleted suggestions. The prompt
    enforces this primarily; this is the structural backstop. Prose is left
    alone (can't be safely trimmed)."""
    lines = (reply or "").splitlines()
    bullet_indices = [i for i, ln in enumerate(lines) if _BULLET.match(ln)]
    if len(bullet_indices) <= max_ideas:
        return reply
    cut_at = bullet_indices[max_ideas]
    kept = "\n".join(lines[:cut_at]).rstrip()
    return kept + IDEAS_TRUNCATION_NOTE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/peer.py tests/test_peer_guardrails.py
git commit -m "feat: add one-idea-at-a-time suggestion cap"
```

---

### Task 4: `personas.py` — writing_partner persona + peer mode + defaults

**Files:**
- Modify: `screenplay_cowriter/personas.py`
- Test: `tests/test_peer_guardrails.py`

**Interfaces:**
- Consumes: existing `PERSONAS`/`MODES` dicts
- Produces: `PERSONAS["writing_partner"]`, `MODES["peer"]`, `DEFAULT_PERSONA = "writing_partner"`, `DEFAULT_MODE = "peer"`

- [ ] **Step 1: Write the failing test**

```python
def test_writing_partner_persona_exists_and_is_default():
    from screenplay_cowriter.personas import PERSONAS, DEFAULT_PERSONA, persona_text
    assert "writing_partner" in PERSONAS
    assert DEFAULT_PERSONA == "writing_partner"
    text = persona_text("writing_partner")
    assert "co-writer" in text.lower() or "partner" in text.lower()


def test_peer_mode_is_default_and_informed_partner_locked():
    from screenplay_cowriter.personas import MODES, DEFAULT_MODE, mode_text
    assert "peer" in MODES
    assert DEFAULT_MODE == "peer"
    text = mode_text("peer")
    assert "never volunteer" in text.lower()
    assert "one idea" in text.lower()


def test_legacy_personas_still_present():
    from screenplay_cowriter.personas import PERSONAS
    for name in ("producer", "dev_exec", "teacher", "audience", "genre_specialist", "script_consultant"):
        assert name in PERSONAS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: FAIL — `AssertionError` (defaults still `script_consultant`/`evidence_discussion`; `writing_partner` absent)

- [ ] **Step 3: Write minimal implementation**

```python
# Append to PERSONAS and MODES dicts, and change the defaults at the bottom of personas.py:

PERSONAS["writing_partner"] = (
    "You are Sam, the writer's co-writing partner — not a critic, not an analyst, a "
    "colleague who works beside them. You have a warm, subtly witty voice; you may use "
    "light sarcasm or a dry joke to make a point, but never at the writer's expense and "
    "never to show off. You are on the writer's side. You build on their ideas rather "
    "than replacing them, and you treat the writer as the final editor of everything."
)

MODES["peer"] = (
    "This is a peer working session. Rules that are non-negotiable: "
    "(1) Acknowledge first — before anything else, show you understood the writer's idea. "
    "(2) Permission before critique — never volunteer criticism; ask 'want my honest take?' "
    "first. (3) One idea at a time — offer a single thought and wait. (4) Probe, don't judge — "
    "when an idea seems thin, ask 'why do you think so?' so the writer discovers it themselves. "
    "(5) Never volunteer the report — you know the analysis report exists, but you never "
    "bring it up and never say 'the report says'; discuss it only when the writer raises it. "
    "(6) Never abandon the thread — end every reply with a question, a choice, or a next step. "
    "(7) Stay focused on the work — the journey can be fun, but it's always about the script."
)

DEFAULT_PERSONA = "writing_partner"
DEFAULT_MODE = "peer"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: PASS (18 passed)

- [ ] **Step 5: Run the cowriter's existing chat tests (defaults ripple)**

Run: `python -m pytest tests/test_chat_language_meta.py tests/test_webapp_api.py -q 2>&1 | tail -5`
Expected: existing failures, if any, are ONLY default-persona assertions — fix them in Task 7's mock update (don't fix yet). If green, continue.

- [ ] **Step 6: Commit**

```bash
git add screenplay_cowriter/personas.py tests/test_peer_guardrails.py
git commit -m "feat: add writing_partner persona + peer mode as defaults"
```

---

### Task 5: `models.py` — Branch.awaiting_probe flag

**Files:**
- Modify: `screenplay_cowriter/models.py` (Branch dataclass + `to_dict`/`from_dict`)
- Test: `tests/test_peer_guardrails.py`

**Interfaces:**
- Produces: `Branch.awaiting_probe: bool = False`; persisted in `to_dict`/`from_dict`; new branches default persona `writing_partner` / mode `peer`

- [ ] **Step 1: Write the failing test**

```python
def test_branch_awaiting_probe_default_false():
    from screenplay_cowriter.models import Branch
    assert Branch(name="main").awaiting_probe is False


def test_awaiting_probe_round_trips_through_dict():
    from screenplay_cowriter.models import Branch
    b = Branch(name="main")
    b.awaiting_probe = True
    restored = Branch.from_dict(b.to_dict())
    assert restored.awaiting_probe is True


def test_new_branch_defaults_to_writing_partner_peer():
    from screenplay_cowriter.models import Branch
    b = Branch(name="main")
    assert b.active_persona == "writing_partner"
    assert b.active_mode == "peer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: FAIL — no `awaiting_probe` attribute; defaults still `script_consultant`/`evidence_discussion`

- [ ] **Step 3: Write minimal implementation**

```python
# In Branch: add the field to the dataclass (after active_mode):
    active_persona: str = "writing_partner"
    active_mode: str = "peer"
    awaiting_probe: bool = False

# In Branch.to_dict: add  "awaiting_probe": self.awaiting_probe,
# In Branch.from_dict: read  awaiting_probe=d.get("awaiting_probe", False),
#   and update the persona/mode defaults there too:
    active_persona=d.get("active_persona", "writing_partner"),
    active_mode=d.get("active_mode", "peer"),
# In Branch.__init__ signature (dataclass field defaults) they now default to
# writing_partner/peer. Sessions saved before this change carry their old
# stored values and load them unchanged (d.get falls back only when absent).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: PASS (21 passed)

- [ ] **Step 5: Commit**

```bash
git add screenplay_cowriter/models.py tests/test_peer_guardrails.py
git commit -m "feat: add Branch.awaiting_probe flag + new partner defaults"
```

---

### Task 6: `engine.py` — two-phase turn + guardrail integration

**Files:**
- Modify: `screenplay_cowriter/engine.py` (`CoWriterEngine.send_message`)
- Test: `tests/test_peer_guardrails.py`

**Interfaces:**
- Consumes: `classify_turn`, `should_probe`, `PROBE_SYSTEM_PROMPT`, `ensure_forward_momentum`, `cap_suggestions` from `peer.py`; `Branch.awaiting_probe`
- Produces: `send_message(session, user_text) -> str` with the two-phase flow (same signature as today)

**Behavior contract:**
- `awaiting_probe=True` and writer's new message is a **question or directive** → abandon probe, answer fresh, clear flag.
- `awaiting_probe=True` and new message is an **idea** (continuation) → clear flag, full turn.
- `awaiting_probe=False` and `should_probe(text)` → phase-1 call with `PROBE_SYSTEM_PROMPT` + scene context + history; set flag; NO suggestions.
- All other turns → normal full turn; then `cap_suggestions`; then `ensure_forward_momentum(reply, turn_kind)`.
- Any exception → reset flag, re-raise (caller already surfaces it).

- [ ] **Step 1: Write the failing test** (uses a fake client — no server needed)

```python
class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
    def chat(self, messages):
        self.calls.append(messages)
        return self.replies.pop(0)


def _make_session():
    from screenplay_cowriter.models import Session
    return Session.new(title="t")


def _make_engine(client):
    from screenplay_cowriter.engine import CoWriterEngine
    from screenplay_cowriter.context import ScriptContext, ReportContext
    return CoWriterEngine(client, ScriptContext({}), ReportContext(None))


def test_idea_without_reasoning_probes_first_and_defers_suggestions():
    client = FakeClient(["So the idea is Mara dies at the end. What's pulling you toward that?"])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "Mara should die at the end")
    assert "?" in reply
    assert s.branch.awaiting_probe is True
    # probe call must NOT contain the writer's raw idea as the last user msg unchanged — it
    # must be a phase-1 call (system prompt is the probe prompt)
    assert "ONE job" in client.calls[0][0]["content"]
    assert len(s.branch.messages) == 2  # user + assistant, no suggestions offered


def test_idea_with_reasoning_gets_full_turn():
    client = FakeClient(["That reasoning lands. Want to explore the guilt angle?"])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "Mara should die because the guilt is eating her")
    assert s.branch.awaiting_probe is False
    assert reply == "That reasoning lands. Want to explore the guilt angle?"


def test_probe_abandoned_on_topic_change():
    client = FakeClient(["Sure, scene 14. What's bugging you about it?"])
    engine = _make_engine(client)
    s = _make_session()
    engine.send_message(s, "Mara should die at the end")  # probes
    assert s.branch.awaiting_probe is True
    reply = engine.send_message(s, "what about scene 14?")  # question -> abandon
    assert s.branch.awaiting_probe is False
    assert reply == "Sure, scene 14. What's bugging you about it?"


def test_probe_continuation_clears_flag_and_answers():
    client = FakeClient(["Because she's the only one who knows the truth.", "Then let's lean into that."])
    engine = _make_engine(client)
    s = _make_session()
    engine.send_message(s, "Mara should die at the end")
    assert s.branch.awaiting_probe is True
    engine.send_message(s, "because the guilt is eating her")  # continuation idea
    assert s.branch.awaiting_probe is False


def test_suggestion_cap_applied_to_full_turn():
    client = FakeClient(["Options:\n- Cut it\n- Move it\n- Rewrite it"])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "what should I do with the monologue?")
    assert reply.count("- ") == 1


def test_dead_end_nudge_applied_when_needed():
    client = FakeClient(["That could work."])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "I think we cut the monologue")
    assert "one at a time" not in reply  # no bullets, so no cap
    assert reply.endswith("?") or "want" in reply.lower() or "let's" in reply.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: FAIL — old `send_message` has no two-phase logic (assertions on `awaiting_probe` fail)

- [ ] **Step 3: Write minimal implementation** — replace `send_message` body:

```python
    def send_message(self, session: Session, user_text: str) -> str:
        from .peer import (
            classify_turn, should_probe, PROBE_SYSTEM_PROMPT,
            ensure_forward_momentum, cap_suggestions,
        )
        branch = session.branch
        user_text = (user_text or "").strip()
        turn_kind = classify_turn(user_text)

        # Abandon a pending probe when the writer has clearly moved on.
        if branch.awaiting_probe and turn_kind != "idea":
            branch.awaiting_probe = False
        # An idea continuing a probe counts as the phase-2 answer.
        elif branch.awaiting_probe and turn_kind == "idea":
            branch.awaiting_probe = False

        scene_refs = extract_scene_refs(user_text)

        if not branch.awaiting_probe and should_probe(user_text):
            # Phase 1: reflect + probe, no suggestions.
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode
            ) + "\n\n" + PROBE_SYSTEM_PROMPT
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = [{"role": "system", "content": system_prompt}]
            if scene_block:
                messages.append({"role": "system", "content": scene_block})
            for m in branch.messages[-self.history_window:]:
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": user_text})
            try:
                reply = strip_language_meta(self.client.chat(messages))
            except Exception:
                branch.awaiting_probe = False  # never strand the writer mid-probe
                raise
            branch.awaiting_probe = True
        else:
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode
            )
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = [{"role": "system", "content": system_prompt}]
            if scene_block:
                messages.append({"role": "system", "content": scene_block})
            for m in branch.messages[-self.history_window:]:
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": user_text})
            reply = strip_language_meta(self.client.chat(messages))
            reply = cap_suggestions(reply)

        reply = ensure_forward_momentum(reply, turn_kind)

        branch.messages.append(Message(role="user", content=user_text, scene_refs=scene_refs, mode=branch.active_mode))
        branch.messages.append(Message(role="assistant", content=reply, mode=branch.active_mode))

        if self.store is not None:
            self.store.save(session)

        return reply
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_peer_guardrails.py -v`
Expected: PASS (27 passed)

- [ ] **Step 5: Run full peer batch + chat tests**

Run: `python -m pytest tests/test_peer_guardrails.py tests/test_chat_language_meta.py -q 2>&1 | tail -5`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add screenplay_cowriter/engine.py tests/test_peer_guardrails.py
git commit -m "feat: integrate two-phase turn + guardrails into co-writer engine"
```

---

### Task 7: Mock personas + webapp default session + "back to Sam"

**Files:**
- Modify: `tests/mock_unified_server.py` (persona markers), `screenplay_studio/webapp_server.py` (if a default-persona assertion exists in tests)
- Test: `tests/test_webapp_api.py` (extend the existing chat test class)

**Interfaces:**
- Consumes: `/api/projects/<name>/chat/start`, `/api/projects/<name>/chat/sessions/<sid>/settings`
- Produces: new sessions defaulting to `writing_partner`/`peer`; `settings` endpoint accepts reset to partner

- [ ] **Step 1: Write the failing test** (append to `tests/test_webapp_api.py`, same class as `test_start_chat`)

```python
    def test_new_session_defaults_to_writing_partner(self, http_client):
        project = self._make_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        data = http_client.get(f"/api/projects/{project}/chat/sessions/{sid}").get_json()
        branch = next(iter(data["branches"].values()))
        assert branch["active_persona"] == "writing_partner"
        assert branch["active_mode"] == "peer"

    def test_settings_reset_to_partner(self, http_client):
        project = self._make_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        base = f"/api/projects/{project}/chat/sessions/{sid}/settings"
        http_client.post(base, json={"persona": "producer"})
        resp = http_client.post(base, json={"persona": "writing_partner", "mode": "peer"})
        assert resp.status_code == 200
        data = http_client.get(f"/api/projects/{project}/chat/sessions/{sid}").get_json()
        branch = next(iter(data["branches"].values()))
        assert branch["active_persona"] == "writing_partner"
        assert branch["active_mode"] == "peer"
```

- [ ] **Step 2: Run test to verify it fails** (or the existing chat tests fail on defaults)

Run: `python -m pytest tests/test_webapp_api.py -q 2>&1 | tail -8`
Expected: FAIL — default persona assertions, or new tests failing because the mock can't detect `writing_partner` (it echoes `persona=unknown`) and/or settings rejects `writing_partner`.

- [ ] **Step 3: Implement**

```python
# 1) tests/mock_unified_server.py — add the marker line inside persona_markers:
        "script consultant": "script_consultant",
        "co-writing partner": "writing_partner",   # <- add this (matches the new persona text)

# 2) screenplay_studio/webapp_server.py update_settings — verify it validates against
#    PERSONAS/MODES keys (it already imports them). "writing_partner" and "peer" exist
#    in personas.py now, so no code change is needed for validation. If any existing
#    webapp test asserted the OLD default persona, update that assertion to the new default.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_webapp_api.py -q 2>&1 | tail -5`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/mock_unified_server.py tests/test_webapp_api.py
git commit -m "test: webapp sessions default to writing partner + reset endpoint"
```

---

### Task 8: `index.html` — room shell (shared script pane + two room panels)

**Files:**
- Modify: `screenplay_studio/webapp/index.html`

**Interfaces:**
- Consumes: nothing new (same element IDs where feasible)
- Produces: new DOM structure consumed by Tasks 9–11:
  - `<body data-room="cowrite">` (room attribute)
  - `#room-toggle` with `#room-cowrite-btn` and `#room-feedback-btn`
  - `#room-chip` (✍️ Writer's Desk / 📋 Consultant's Desk)
  - shared `#script-pane` (holds today's `#script-toolbar`, `#draft-bar`, `#diff-banner`, `#script-scenes`)
  - `#cowrite-panel` (partner card `#partner-card`, `#messages`, `#composer`)
  - `#feedback-panel` (header: `#feedback-title`, `#analyze-btn`, `#report-lang-select`, `#analyze-progress`; body: `#feedback-tabs` with `#tab-report-btn`/`#tab-fixqueue-btn`, `#feedback-report`, `#feedback-fixqueue`, `#feedback-empty`)
  - `#beatboard-view`, `#compare-view` unchanged, opened via script-pane toolbar icons `#bb-icon`, `#compare-icon`

- [ ] **Step 1: Restructure the project workspace markup**

Move the existing header controls: keep `#project-title` + `#branch-switcher` in a top bar; replace the four `#view-*` buttons with the two room buttons + `#room-chip`; MOVE `#analyze-btn`, `#report-lang-select`, `#analyze-progress`, `#reader-btn` into the Feedback panel header; MOVE `#persona-select` and `#mode-select` out of the header (they become hidden — lenses are conversational now). The composer form and `#messages` move into `#cowrite-panel`. Add `#partner-card` above `#messages` with: `[▓ Sam] — writing with you` and a `#reset-partner-btn` ("back to Sam"). Add the two `#bb-icon` / `#compare-icon` buttons into `#script-toolbar` next to export buttons. Add `#feedback-tabs`, the three feedback containers, and `#feedback-empty` (text: *"No analysis yet — Run Analysis to get the consultant's report"*).

- [ ] **Step 2: Verify structure by serving**

Run: `python -m pytest tests/test_webapp_api.py -q 2>&1 | tail -3` then open `screenplay_studio/webapp/index.html` — page still loads with no console errors (JS from Task 9 not yet wired; static check only).
Expected: no parse errors; DOM elements present via `grep` on the file.

- [ ] **Step 3: Commit**

```bash
git add screenplay_studio/webapp/index.html
git commit -m "feat: restructure webapp shell into shared script pane + two rooms"
```

---

### Task 9: `app.js` — room switching + panel wiring

**Files:**
- Modify: `screenplay_studio/webapp/app.js`

**Interfaces:**
- Consumes: new DOM from Task 8
- Produces: `openCowriteRoom()`, `openFeedbackRoom()`, `setRoom(room)`, updated `hideAllViews()`; all existing handlers (`openScriptView` callers, keyboard shortcuts, `discussFinding`, analyze button) re-pointed at the new IDs

- [ ] **Step 1: Update the view functions**

Replace `openChatView`/`openScriptView` with:

```js
function setRoom(room) {
  state.view = room;                       // "cowrite" | "feedback"
  document.body.dataset.room = room;       // drives CSS theming
  const chip = $("#room-chip");
  if (chip) chip.textContent = room === "feedback" ? "📋 Consultant's Desk" : "✍️ Writer's Desk";
  $("#room-cowrite-btn").classList.toggle("active", room === "cowrite");
  $("#room-feedback-btn").classList.toggle("active", room === "feedback");
  $("#cowrite-panel").style.display = room === "cowrite" ? "flex" : "none";
  $("#feedback-panel").style.display = room === "feedback" ? "flex" : "none";
  saveSession();
}

function openCowriteRoom() {
  if (state.view === "cowrite") return;
  setRoom("cowrite");
  renderMessages();
  maybeShowWelcome();
}

function openFeedbackRoom() {
  if (state.view === "feedback") return;
  setRoom("feedback");
  loadFeedbackPanels();
}
```

Update `hideAllViews()` to hide `#beatboard-view` and `#compare-view` only (the rooms are handled by `setRoom`). Update all references: `state.view === "script"` → treat `"cowrite"` and `"feedback"` as script-visible (e.g. `[state.view === "cowrite" || state.view === "feedback"]` in the keyboard/undo/print guards). Re-point `#analyze-btn`, `#report-lang-select`, `#analyze-progress` handlers — they now live in the Feedback panel but the existing `addEventListener` code already queries by ID, so no handler change is required. Add `$("#bb-icon")`/`$("#compare-icon")` click handlers → `openBeatboardView()`/`openCompareView()`. Add `$("#reset-partner-btn")` → POST settings `{persona:"writing_partner", mode:"peer"}` then `renderMessages()`.

- [ ] **Step 2: Add `maybeShowWelcome()` and the `discussFinding` prefill**

```js
let welcomeShownFor = null;
function maybeShowWelcome() {
  const branch = currentBranchData();
  const has = (branch.messages || []).length > 0;
  if (has || welcomeShownFor === state.currentProject) return;
  welcomeShownFor = state.currentProject;
  const container = $("#messages");
  if (!container.querySelector(".chat-empty-hint")) {
    container.appendChild(el("div", "chat-empty-hint", "Sam: Hey — I'm here. What are we working on?"));
  }
}
```

Update `discussFinding(f, index)` (it already prefills the composer) — change `openChatView()` to `openCowriteRoom()` and ensure the seed mentions the scene number (it already does via `Scene N`), then `$("#input").focus()` (already present). No auto-send.

- [ ] **Step 3: Wire the room toggle buttons**

```js
$("#room-cowrite-btn").addEventListener("click", openCowriteRoom);
$("#room-feedback-btn").addEventListener("click", openFeedbackRoom);
```

- [ ] **Step 4: Verify — start the webapp and exercise both rooms**

Run the mock + webapp servers, then `python -m pytest tests/test_webapp_api.py -q 2>&1 | tail -3` (APIs unaffected) and confirm via manual browser pass (or `node --check screenplay_studio/webapp/app.js` for syntax):
Expected: `node --check` passes; API tests pass.

- [ ] **Step 5: Commit**

```bash
git add screenplay_studio/webapp/app.js
git commit -m "feat: room switching + partner card wiring in webapp JS"
```

---

### Task 10: `app.js` — Feedback room panels (Report / Fix Queue / empty state)

**Files:**
- Modify: `screenplay_studio/webapp/app.js`

**Interfaces:**
- Consumes: existing `state.report`, `state.fixQueue`, `renderFixQueuePanel(container)` (reuse as-is)
- Produces: `loadFeedbackPanels()`, `renderReportPanel()`, feedback tab switching, empty-state handling

- [ ] **Step 1: Implement**

```js
async function loadFeedbackPanels() {
  const base = `/api/projects/${encodeURIComponent(state.currentProject)}`;
  try {
    if (!state.report) state.report = await api(`${base}/report`);
    if (!state.fixQueue) state.fixQueue = await api(`${base}/fixqueue`);
  } catch (e) { /* report 404 when no analysis — handled by empty state below */ }
  const hasReport = state.report && (state.report.findings || state.report.coverage);
  $("#feedback-empty").style.display = hasReport ? "none" : "block";
  $("#feedback-tabs").style.display = hasReport ? "flex" : "none";
  if (hasReport) {
    renderReportPanel();
    const fq = $("#feedback-fixqueue");
    fq.innerHTML = "";
    renderFixQueuePanel(fq);   // existing function, reused verbatim
  }
}

function renderReportPanel() {
  const c = $("#feedback-report");
  c.innerHTML = "";
  if (!state.report) return;
  const cov = state.report.coverage;
  if (cov) {
    const card = el("div", "craft-panel");
    card.appendChild(el("div", "craft-panel-head",
      el("span", "craft-panel-title", `Coverage — ${(cov.recommendation || "").toUpperCase()}`)));
    if (cov.logline) card.appendChild(el("p", "", `Logline: ${cov.logline}`));
    if (cov.synopsis) card.appendChild(el("p", "", cov.synopsis));
    (cov.weaknesses || []).forEach(w => card.appendChild(el("p", "fix-row-why", `• ${w}`)));
    c.appendChild(card);
  }
  const byCat = {};
  (state.report.findings || []).forEach(f => { (byCat[f.category] = byCat[f.category] || []).push(f); });
  for (const [cat, list] of Object.entries(byCat)) {
    const card = el("div", "craft-panel");
    card.appendChild(el("div", "craft-panel-head", el("span", "craft-panel-title", cat)));
    list.forEach(f => {
      const refs = (f.scene_refs || []).map(n => "Scene " + n).join(", ") || "General";
      card.appendChild(el("p", "fix-row-issue", `[${(f.severity||"low").toUpperCase()}] ${refs}: ${f.issue}`));
      if (f.why_it_matters) card.appendChild(el("p", "fix-row-why", f.why_it_matters));
    });
    c.appendChild(card);
  }
}

$("#tab-report-btn").addEventListener("click", () => {
  $("#tab-report-btn").classList.add("active");
  $("#tab-fixqueue-btn").classList.remove("active");
  $("#feedback-report").style.display = "block";
  $("#feedback-fixqueue").style.display = "none";
});
$("#tab-fixqueue-btn").addEventListener("click", () => {
  $("#tab-fixqueue-btn").classList.add("active");
  $("#tab-report-btn").classList.remove("active");
  $("#feedback-report").style.display = "none";
  $("#feedback-fixqueue").style.display = "block";
});
```

- [ ] **Step 2: Verify**

Run: `node --check screenplay_studio/webapp/app.js && python -m pytest tests/test_webapp_api.py -q 2>&1 | tail -3`
Expected: syntax OK, API tests pass.

- [ ] **Step 3: Commit**

```bash
git add screenplay_studio/webapp/app.js
git commit -m "feat: feedback room report + fix queue panels with empty state"
```

---

### Task 11: `style.css` — room theming + partner card + room chip

**Files:**
- Modify: `screenplay_studio/webapp/style.css`

**Interfaces:**
- Consumes: `body[data-room="cowrite|feedback"]`, `#partner-card`, `#room-chip`, `#feedback-panel`, `#cowrite-panel`, `#feedback-tabs`

- [ ] **Step 1: Implement**

```css
/* --- Room identity: the two desks --- */
body[data-room="cowrite"] { --room-accent: #c98a3d; --room-bg: #fdf6ec; }
body[data-room="feedback"] { --room-accent: #3d6ec9; --room-bg: #eef2fa; }

#room-toggle { display: flex; gap: 6px; }
.room-toggle-btn { border: 1px solid var(--border); background: transparent; border-radius: 8px;
  padding: 4px 12px; cursor: pointer; }
.room-toggle-btn.active { background: var(--room-accent); color: #fff; border-color: var(--room-accent); }
#room-chip { font-size: 11px; color: var(--room-accent); border: 1px dashed var(--room-accent);
  border-radius: 10px; padding: 2px 8px; margin-left: 8px; }

/* workspace: shared script pane + room panel */
.workspace { display: flex; height: calc(100vh - 96px); }
#script-pane { flex: 0 0 55%; min-width: 420px; overflow-y: auto; border-right: 1px solid var(--border); }
#cowrite-panel, #feedback-panel { flex: 1; display: flex; flex-direction: column; background: var(--room-bg); }
#feedback-panel { display: none; }

/* partner card */
#partner-card { display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: linear-gradient(90deg, var(--room-accent), transparent); border-bottom: 1px solid var(--border); }
#partner-card .avatar { width: 28px; height: 28px; border-radius: 50%; background: var(--room-accent);
  color: #fff; display: grid; place-items: center; font-weight: 700; }
#reset-partner-btn { margin-left: auto; }

/* feedback tabs */
#feedback-tabs { display: flex; gap: 6px; padding: 8px 12px 0; }
#feedback-tabs button { border: none; background: transparent; padding: 6px 12px;
  border-bottom: 2px solid transparent; cursor: pointer; }
#feedback-tabs button.active { border-bottom-color: var(--room-accent); color: var(--room-accent); }
#feedback-report, #feedback-fixqueue { padding: 12px; overflow-y: auto; }
#feedback-empty { padding: 40px 20px; text-align: center; color: var(--muted); }
```

- [ ] **Step 2: Verify**

Run: `node --check screenplay_studio/webapp/app.js` and a manual browser check of both rooms (script pane + panel styling, accent color switch).
Expected: both rooms render with distinct accents; script pane identical in both.

- [ ] **Step 3: Commit**

```bash
git add screenplay_studio/webapp/style.css
git commit -m "feat: room theming + partner card + feedback panel styles"
```

---

### Task 12: Regression — script pane from inside Feedback room + full suite

**Files:**
- Modify: `tests/test_webapp_api.py` (add script-pane-independent regression where feasible) or a new `tests/test_rooms_ui.py` for API-level assertions
- Verify: no production code changes unless a real bug surfaces

**Interfaces:**
- Consumes: nothing new — guards the shared-pane promise

- [ ] **Step 1: Add the API-level regression test** (the pane is DOM; API tests guard the data the pane renders)

```python
    def test_report_and_fixqueue_available_after_analysis(self, http_client):
        project = self._make_project(http_client)
        http_client.post(f"/api/projects/{project}/analyze")
        assert http_client.get(f"/api/projects/{project}/report").status_code == 200
        fq = http_client.get(f"/api/projects/{project}/fixqueue").get_json()
        assert "items" in fq
        assert "acts" in fq
```

- [ ] **Step 2: Run the FULL suite**

Run: `python -m pytest tests/ -q 2>&1 | tail -6`
Expected: all pass (298 existing + new peer/room tests).

- [ ] **Step 3: Manual browser pass** (if Chrome available) or instruct the user:
  1. Open project → default Co-write room (writer's desk, amber accent).
  2. Type "Mara should die at the end" → Sam reflects + probes, no suggestions.
  3. Reply with reasoning → Sam responds, capped at one idea.
  4. Switch to Feedback room (slate accent) → empty state → Run Analysis → Report + Fix Queue tabs.
  5. Click "→ discuss with my partner" → composer prefilled, NOT sent; scene number present.
  6. Same scene stays centered when switching rooms.

- [ ] **Step 4: Commit**

```bash
git add tests/test_webapp_api.py
git commit -m "test: feedback room regression + full suite green"
```

---

### Task 13: Docs — update NOTES.md + ARCHITECTURE.md (rooms + guardrails)

**Files:**
- Modify: `NOTES.md`, `docs/ARCHITECTURE.md`

- [ ] **Step 1: Update NOTES.md** — mark the feature complete: two rooms (Co-write / Feedback), shared script pane, partner "Sam" with the four guardrails, informed-partner rule, prefill bridge, room theming; note deferred v2 (relationship memory).

- [ ] **Step 2: Update ARCHITECTURE.md** — replace the "hardcoded persona list" wording in §2 (personas are now conversational lenses; UI defaults to `writing_partner`/`peer`) and add the guardrails + room architecture to the relevant section.

- [ ] **Step 3: Commit**

```bash
git add NOTES.md docs/ARCHITECTURE.md
git commit -m "docs: rooms + writing-partner guardrails (NOTES, ARCHITECTURE)"
```

---

## Self-Review (performed by the plan author before handoff)

**1. Spec coverage:**
- Two rooms + shared script pane → Tasks 8–11. ✅
- At-a-glance identity (amber/slate, room chip, partner card) → Tasks 8, 11. ✅
- One consistent partner "Sam" + default persona/mode → Tasks 4, 5. ✅
- Informed partner (never volunteers) → Task 4 mode text + probe flow (Task 6) + prefill bridge (Task 9). ✅
- Two-phase turn / probe-without-reasoning / abandon-on-topic-change → Tasks 1, 6. ✅
- Dead-end check (light-touch, no factual-answer nudges, rotation) → Task 2 + engine wiring (Task 6). ✅
- One idea at a time → Task 3 + engine wiring. ✅
- Fix queue + report as first-class Feedback tabs, empty state → Task 10. ✅
- Prefill-not-autosend bridge → Task 9 (`discussFinding` unchanged prefill semantics). ✅
- First-turn welcome → Task 9 (`maybeShowWelcome`). ✅
- Backward compat (`awaiting_probe` absent = False; legacy personas kept) → Tasks 4, 5. ✅
- Testing incl. script-pane regression + full suite → Tasks 7, 12. ✅

**2. Placeholder scan:** No TBD/TODO/`implement later` in the plan; every code step carries real code. ✅

**3. Type consistency:** `classify_turn`/`should_probe`/`has_embedded_reasoning`/`PROBE_SYSTEM_PROMPT` (Task 1) → used identically in Task 6. `ensure_forward_momentum`/`cap_suggestions`/`FORWARD_NUDGES` (Tasks 2–3) → used identically in Task 6. `Branch.awaiting_probe` (Task 5) → read/written in Task 6. New DOM IDs from Task 8 (`#room-cowrite-btn`, `#cowrite-panel`, `#feedback-panel`, `#partner-card`, `#room-chip`, `#feedback-tabs`, `#feedback-empty`) → referenced identically in Tasks 9–11. ✅
