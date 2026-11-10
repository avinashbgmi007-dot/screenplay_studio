"""Structural guardrails for the writing-partner voice.

All functions here are pure (no model calls) so they're unit-testable
without a server. The engine (engine.py) calls them around each chat turn.
"""

import re

_QUESTION_START = re.compile(
    r"^(who|what|why|how|does|can|should|is|are|would|could|do|did)\b", re.I
)
_DIRECTIVE_START = re.compile(
    r"^(rewrite|fix|change|try|add|cut|move|remove|make|let'?s|let\s+us|write|imagine|explain)\b",
    re.I,
)
_REASONING = re.compile(
    r"\b(because|since|so that|the reason|my instinct|i feel like|the thing is)\b", re.I
)

# ---------------------------------------------------------------------------
# Gap 98: classification keyed on the FIRST TOKEN and a trailing "?", so a
# writer who said what they wanted was treated as a writer with a raw idea and
# then interrogated ("why do you think so?"). Measured on the real functions:
#
#   "Let the silence sit."                      -> idea -> probed
#   "I want the audience to feel compulsion."   -> idea -> probed
#   "I cut the line."                           -> idea -> probed
#   "The ending should feel earned."            -> idea -> probed
#
# Those are decisions, not undeveloped thoughts. Probing them is the failure the
# brief rules out. Two new kinds carry the distinction, and each has a
# BEHAVIOUR, not just a label — a kind nothing reads is a comment.

# "Let the silence sit." but not "let's" / "let us" (those are directives).
_INTENT_START = re.compile(
    r"^(?:"
    r"let\s+(?!'s\b|us\b|s\b)"
    r"|keep\b|allow\b|hold\b|leave\b|preserve\b|stet\b"
    r"|i'd\s+like|i\s+would\s+like"
    # Contractions sit directly after the pronoun, so `i\s+` never matched them:
    # "I've decided" was classified a bare idea until this branch existed.
    r"|i'(?:ve|m)\s+(?:decided|cut|kept|moved|added|changed|removed|rewritten|trying)"
    r"|i\s+(?:have|am)\s+(?:decided|cut|kept|moved|added|changed|removed|rewritten|trying)"
    r"|i\s+(?:want|need|decided|intend|prefer|cut|kept|moved|added|changed|removed|wrote"
    r"|'m\s+trying|am\s+trying)\b"
    r")", re.I)

# A statement that names the EFFECT the writer wants: "The ending should feel
# earned." / "This must read as a betrayal." That is an intention, stated.
#
# Deliberately NOT every "should": "Mara should die at the end" is a plot idea
# offered for development, and two pre-existing tests pin it as probeable —
# correctly, because a story decision is exactly what a co-writer should help
# think through. The boundary is effect-vs-event: how the work should FEEL is
# the writer's intention; what should HAPPEN is the writer's idea.
_INTENT_STATEMENT = re.compile(
    r"\b(?:should|must|needs?\s+to|has\s+to|ought\s+to)\s+"
    r"(?:feel|read|play|land|sound|look|come\s+across|track|sit)\b", re.I)

# Modal + FIRST PERSON = the writer proposing something about their own script,
# not asking a fact about the world. Narrow on purpose: "Can the mother appear
# earlier?" stays a question, because that one IS asking for a judgment.
_REQUEST_START = re.compile(
    r"^(can|could|would|will|should|may|might)\s+(we|i|you)\b", re.I)

# A second-person modal can be a courteous command or a request for information,
# not only a proposal. Keep these lists deliberately small: unknown forms retain
# the existing generic request behavior instead of being guessed as an edit.
_POLITE_INFORMATION_START = re.compile(
    r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?"
    r"(?:explain|tell|describe|clarify|summarize|remind)\b", re.I)
_POLITE_DIRECTIVE_START = re.compile(
    r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?"
    r"(?:rewrite|revise|tighten|trim|shorten|expand|fix|change|try|add|cut|"
    r"move|remove|make|write|draft|replace|polish|rework)\b", re.I)

# `since` can be causal (`... since the audience knows`) or temporal
# (`Since the funeral, ...`). Exempt only a leading, comma-terminated clause
# with an explicit time/event noun; do not pretend to parse arbitrary prose.
_TEMPORAL_SINCE_PREFIX = re.compile(
    r"^\s*since\s+(?:(?:the|last|this)\s+)?"
    r"(?:funeral|wedding|accident|night|morning|afternoon|evening|day|week|"
    r"month|year|summer|winter|spring|autumn|fall|childhood|birth|then)"
    r"\b[^,.;!?]*,\s*", re.I)

PROBE_SYSTEM_PROMPT = (
    "You are Sameer, the writer's co-writing partner. The writer just shared an idea with "
    "you. This turn has ONE job: let them feel heard — reflect their idea back in your "
    "own words, naturally, like you're turning it over with them — then ask one genuine "
    "question about what's driving it (\"why do you think so?\" or a real question in your "
    "voice). Don't jump to suggestions, alternatives, fixes, or judgments yet — they "
    "didn't ask for any. One question, and make it sound like you, not a form."
)


def classify_turn(text: str) -> str:
    """'idea' | 'question' | 'directive' | 'intent' | 'request'

    - idea: a thought offered for development — the ONLY kind that gets probed
    - question: a fact/world question — answer first, then at most one follow-up
    - directive: an instruction (imperative) — 'rewrite', 'fix', 'try', ...
    - intent: the writer said what they want or what they did — never probed
    - request: a modal first-person proposal — engaged with, never nudged

    Order matters. `request` is checked before the trailing-"?" catch, because
    "Could I lose the last beat?" is a proposal that happens to end in a
    question mark; `question` before `intent`, so "Should the mother appear
    earlier?" is not read as a decision; and `directive` before `intent`, so
    "Let's cut the scene" is an instruction while "Let the silence sit." is the
    writer's intention.
    """
    t = (text or "").strip()
    if not t:
        return "idea"
    if _POLITE_INFORMATION_START.match(t):
        return "question"
    if _POLITE_DIRECTIVE_START.match(t):
        return "directive"
    if _REQUEST_START.match(t):
        return "request"
    if t.endswith("?") or _QUESTION_START.match(t):
        return "question"
    if _DIRECTIVE_START.match(t):
        return "directive"
    if _INTENT_START.match(t) or _INTENT_STATEMENT.search(t):
        return "intent"
    return "idea"


# What the reply must do first, per turn kind. Pure, so the contract is testable
# without a model call — the engine used to build this inline, which meant the
# only way to know what a writer would be told was to read the prompt.
_OPENING_CONTRACTS = {
    "question": (
        "\n\nANSWER FIRST: the writer asked a direct question. Open with "
        "the actual answer to THAT question -- no preamble, no redirect. "
        "After the answer, at most one short follow-up."
    ),
    "request": (
        "\n\nREQUEST FIRST: the writer proposed something about their own "
        "script. Engage with the proposal as a collaborator would -- what it "
        "would cost, what it would buy, what it would need -- and answer the "
        "yes/no they are actually asking. Do not interrogate them about why "
        "they asked, and do not treat it as a fact question about the world."
    ),
    "intent": (
        "\n\nTHE WRITER HAS DECIDED: they told you what they want or what "
        "they did. Take it as given. Do not ask what is driving it -- they "
        "already said. Build on it, name what it would change, or say what it "
        "risks; do not re-open the decision."
    ),
}


def opening_contract(turn_kind: str) -> str:
    """The lead-the-reply instruction for a turn kind ("" for idea/directive)."""
    return _OPENING_CONTRACTS.get(turn_kind, "")


def has_embedded_reasoning(text: str) -> bool:
    """True when the writer gave their own reasoning ('because', 'since', 'my
    instinct', ...) — a real co-writer doesn't interrogate a thought the writer
    has already justified.

    A small, comma-terminated temporal `Since <event/time>, ...` opener is
    removed first: that fact can be scene context rather than a reason for a
    later idea. Other `since` uses retain the original broad behavior.
    """
    remaining = _TEMPORAL_SINCE_PREFIX.sub("", text or "", count=1)
    return bool(_REASONING.search(remaining))


def should_probe(text: str) -> bool:
    """Probe only when the writer shares an idea WITHOUT embedded reasoning.

    Gap 98: this is now the whole of the rule, because `intent` and `request`
    are no longer classified as `idea`. The brief says Sameer must not
    interrogate a writer who has already said what they want or asked
    something — so the classification carries that, and this predicate stops
    needing a growing list of exceptions.
    """
    return classify_turn(text) == "idea" and not has_embedded_reasoning(text)


FORWARD_NUDGES = [
    "Want me to run with this and see where it goes?",
    "Where do you feel like taking it from here?",
    "Want me to sketch a version so we can react to something real?",
    "What's your instinct on the next move?",
]

# Which personas may close a turn by offering to move the work forward.
#
# The nudge is a COLLABORATOR's move: it offers to act. It used to be appended
# to every persona's short reply, which meant the Doctor's diagnosis ended
# with "Want me to run with this and see where it goes?" — contradicting his
# own voice check ("verdict first... diagnosis is your job; fixes are Sameer's
# department") and offering the other desk's service. The evaluators and the
# reactor do not offer to act either: they deliver a read and stop.
#
# Every persona is classified explicitly, and tests/test_cowriter_personas.py
# fails if a new one is added without a decision.
NUDGE_PERSONAS = frozenset({"writing_partner", "premise_doctor", "dev_exec", "teacher"})
NO_NUDGE_PERSONAS = frozenset({"script_consultant", "producer", "audience", "genre_specialist"})

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


def ensure_forward_momentum(reply: str, turn_kind: str, persona: str | None = None) -> str:
    """Append a forward nudge only when the reply is SHORT and doesn't already
    end forward. A substantial reply (a complete answer, a developed thought)
    is never stranded — real humans end on a period; the goal is the writer
    never feels left hanging, not that every message interrogates them.

    A DIRECT QUESTION from the writer never gets a nudge: they asked, we
    answered -- tacking "want me to run with this?" onto an answer reads as
    evasive. Questions get clean answers.

    `persona` gates it to the collaborators (`NUDGE_PERSONAS`); an unknown or
    absent persona gets no nudge, because the nudge is a character decision,
    not a house style.
    """
    global _nudge_index
    t = (reply or "").strip()
    if not t:
        return reply
    if persona not in NUDGE_PERSONAS:
        return reply
    if turn_kind in ("question", "request"):
        # Both are the writer asking US something. Tacking "want me to run with
        # this?" onto the answer reads as evasive — and gap 98 added `request`
        # to this rule because a modal proposal is still a request for an answer.
        return reply
    # The nudge list is English. Appending an English question to a reply the
    # language mirror just kept in Telugu or Hindi is the ENGINE breaking the
    # register it promised to keep — and because this is deterministic it would
    # happen on every short reply, not occasionally. Until the nudges exist per
    # register (a product decision, and one that needs a real model to
    # validate), a non-Latin reply ends without one: an honest short answer
    # beats a two-language one.
    try:
        from .language_mirror import reply_is_non_latin
        if reply_is_non_latin(t):
            return reply
    except Exception:
        pass  # the gate is an enhancement — never break a turn over it
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
