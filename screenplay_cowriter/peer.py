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
    r"\b(because|since|so that|the reason|my instinct|i feel like|the thing is)\b", re.I
)

PROBE_SYSTEM_PROMPT = (
    "You are Sam, the writer's co-writing partner. The writer just shared an idea with "
    "you. This turn has ONE job: let them feel heard — reflect their idea back in your "
    "own words, naturally, like you're turning it over with them — then ask one genuine "
    "question about what's driving it (\"why do you think so?\" or a real question in your "
    "voice). Don't jump to suggestions, alternatives, fixes, or judgments yet — they "
    "didn't ask for any. One question, and make it sound like you, not a form."
)


def classify_turn(text: str) -> str:
    """'idea' | 'question' | 'directive'
    - idea: a statement sharing a thought
    - question: ends with ? or starts with who/what/why/how/does/can/should/...
    - directive: an instruction (imperative) — 'rewrite', 'fix', 'try', ...
    """
    t = (text or "").strip()
    if not t:
        return "idea"
    if t.endswith("?") or _QUESTION_START.match(t):
        return "question"
    if _DIRECTIVE_START.match(t):
        return "directive"
    return "idea"


def has_embedded_reasoning(text: str) -> bool:
    """True when the writer gave their own reasoning ('because', 'since', 'my
    instinct', ...) — a real co-writer doesn't interrogate a thought the writer
    has already justified."""
    return bool(_REASONING.search(text or ""))


def should_probe(text: str) -> bool:
    """Probe only when the writer shares an idea WITHOUT embedded reasoning."""
    return classify_turn(text) == "idea" and not has_embedded_reasoning(text)


FORWARD_NUDGES = [
    "Want me to run with this and see where it goes?",
    "Where do you feel like taking it from here?",
    "Want me to sketch a version so we can react to something real?",
    "What's your instinct on the next move?",
]
_nudge_index = 0


def _has_forward_ending(reply: str) -> bool:
    t = reply.rstrip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    last = t.split()[-1] if t.split() else ""
    # openers that carry a forward nudge even without a question mark
    return any(tok in last.lower() for tok in ("want", "let's", "lets", "should", "shall", "right"))


STRANDED_THRESHOLD = 120  # chars: replies at/above this are substantial, never nudged


def ensure_forward_momentum(reply: str, turn_kind: str) -> str:
    """Append a forward nudge only when the reply is SHORT and doesn't already
    end forward. A substantial reply (a complete answer, a developed thought)
    is never stranded — real humans end on a period; the goal is the writer
    never feels left hanging, not that every message interrogates them.
    `turn_kind` is accepted for interface stability / future use."""
    global _nudge_index
    t = (reply or "").strip()
    if not t:
        return reply
    if _has_forward_ending(t):
        return reply
    if len(t) >= STRANDED_THRESHOLD:
        return reply
    nudge = FORWARD_NUDGES[_nudge_index % len(FORWARD_NUDGES)]
    _nudge_index += 1
    return f"{t}\n\n{nudge}"


IDEAS_TRUNCATION_NOTE = (
    "\n\n(Let's take these one at a time — which one do you want to explore first?)"
)

_BULLET = re.compile(r"^\s*(•|-|\d+[.)])\s+")


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
