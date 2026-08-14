"""Writer relationship memory — Sam's gradually-learned sense of how the
writer likes to work, persisted writer-level (across all projects).

Spec: docs/superpowers/specs/2026-08-12-writer-relationship-memory-design.md
Plan: docs/superpowers/plans/2026-08-12-writer-relationship-memory.md

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

import json
import os
import re
import threading
import time
import uuid

BEHAVIOR_GATE = 0.6
MIN_EVIDENCE = 3           # a dimension needs this many signals before it can gate
REFRESH_INTERVAL = 10      # new observed turns between refreshes

# Neutral value per dimension (the "nothing set" state — never gates).
NEUTRAL = {"detail_level": "balanced", "directness": "balanced",
           "probe_appetite": "medium", "pushback_appetite": "medium",
           "support_style": "balanced"}

# Learnable poles per dimension. support_style captures HOW the writer wants
# Sam to work beside them: concrete options to react to (generate) vs. a
# thinking partner to talk it through with (discuss).
DIMENSION_POLES = {
    "detail_level": ("short", "deep"),
    "directness": ("gentle", "direct"),
    "probe_appetite": ("low", "high"),
    "pushback_appetite": ("low", "high"),
    "support_style": ("generate", "discuss"),
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
    (re.compile(r"\b(?:give me|gimme|offer(?: me)?|come up with|sketch|draft|throw out)\b", re.I), "support_style", "generate"),
    (re.compile(r"\b(?:what do you think|which one|help me think|your take|weigh in|talk it through|let'?s discuss)\b", re.I), "support_style", "discuss"),
]

PUSHBACK_ARGUE = re.compile(r"\b(?:i disagree\b|no,|but |that won'?t work\b|that doesn'?t work\b|that loses\b|keep it anyway\b|actually no\b)", re.I)
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
    # Observation lifecycle lives here (not in observe/save): a dimension that
    # crosses the gate gains a human-readable observation, and explicit tone
    # statements against a gated preference count as contradictions.
    _note_contradictions(profile, signals)
    for dim in list(DIMENSION_POLES):
        _maybe_add_template_observation(profile, dim)
    return profile


def _current_belief_rejected(profile, dim):
    """Has the writer rejected the dimension's CURRENT belief?

    'Forget this' suppresses the human-readable observation for the belief;
    that rejection must stop the belief from steering Sam's tone until it is
    re-learned. Keyed to the template of the *current* value so that
    contradiction auto-suppression of an OLD pole's observation (the writer
    argued the old belief away and the dimension flipped) does NOT silence
    the new belief — the dimension has moved on.
    """
    value = profile["dimensions"][dim]["value"]
    template = OBS_TEMPLATES.get((dim, value))
    if template is None:
        return False
    # Observations are appended in time order: the belief counts as rejected
    # only if its LATEST observation is suppressed. If the writer re-learns
    # the belief, a fresh (non-suppressed) observation is appended and the
    # old forgotten one no longer silences the gate.
    matching = [o for o in profile.get("observations", [])
                if o.get("dimension") == dim and o.get("text") == template]
    return bool(matching) and matching[-1].get("suppressed")


def dimension_gate(profile):
    """Dimensions that actually affect behavior: learnable pole, confidence >= gate,
    at least MIN_EVIDENCE total signals, and a belief the writer hasn't rejected
    (a suppressed template observation for the current value)."""
    gated = {}
    for dim, d in profile["dimensions"].items():
        if dim not in DIMENSION_POLES:
            continue
        ev = d["evidence"]
        if d["value"] in DIMENSION_POLES[dim] and d["confidence"] >= BEHAVIOR_GATE and (ev["pos"] + ev["neg"]) >= MIN_EVIDENCE:
            if _current_belief_rejected(profile, dim):
                continue
            gated[dim] = {"value": d["value"], "confidence": d["confidence"]}
    return gated


DIM_LABELS = {
    "detail_level": ("prefers short, tight answers", "likes to go deep and wander"),
    "directness": ("prefers gentle, eased-in notes", "wants the note straight, no softening"),
    "probe_appetite": ("dislikes being probed before answers", "engages well with probing questions"),
    "pushback_appetite": ("prefers Sam to defer", "enjoys Sam pushing back on choices"),
    "support_style": ("likes concrete options to react to", "prefers talking it through before committing"),
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
    ("support_style", "generate"): "You like concrete options to react to.",
    ("support_style", "discuss"): "You prefer talking things through before committing.",
}

CARD_RULES = (
    " Adapt your tone accordingly. Rules: this informs TONE, never content. "
    "Never quote the memory to the writer (\"you always say…\" is forbidden). "
    "If the writer contradicts a remembered preference this turn, the current turn wins."
)


def _maybe_add_template_observation(profile, dim):
    """When a dimension first crosses the gate, record a human-readable observation."""
    # _dim_state creates the entry for dimensions missing from an older stored
    # profile (adding a learnable dimension must never crash an existing file)
    d = _dim_state(profile, dim)
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
    if topics and sum(topics.values()) >= 6:
        top = max(topics, key=topics.get)
        if topics[top] / sum(topics.values()) >= 0.35:
            phrases.append(f"keeps returning to {top}-level concerns")
    # Only observations for dimensions Sam actually acts on (or free-standing
    # general notes) reach the card — a refresh note about a dimension whose
    # belief the writer forgot must not sneak the rejected belief back in.
    active_dims = set(gated) | {"general", "topic_gravity"}
    obs_lines = [o["text"] for o in profile.get("observations", [])
                 if not o["suppressed"] and o["confidence"] >= BEHAVIOR_GATE
                 and o.get("dimension") in active_dims]
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
    return ("This is a brand-new working relationship — you've never worked together before, "
            "so a natural, human opener fits (only if it fits the moment, never forced): "
            "\"Before we dive in — what's the one thing you're trying to fix in this draft?\"")


def refresh_prompt(recent_messages):
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in recent_messages)
    return (
        "RELATIONSHIP MEMORY REFRESH — read the conversation below between a writer and "
        "their co-writer. Based ONLY on explicit evidence in it, what does this writer "
        "prefer? Output STRICT JSON object with keys detail_level, directness, "
        "probe_appetite, pushback_appetite, support_style — each {\"value\": "
        "\"short|deep|balanced|gentle|direct|low|high|medium|generate|discuss|no_evidence\", "
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
        self.profile["meta"]["total_turns_observed"] += 1
        self.save()

    def card_text(self):
        return build_relationship_card(self.profile)

    def gated_dimensions(self):
        """The dimensions currently steering behavior (suppression-aware) —
        what the webapp's notes panel renders as chips, so the UI never
        shows a chip for a belief the writer has forgotten."""
        return dimension_gate(self.profile)

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
            if not self.refresh_due():
                return
            self._refresh_sync(client, recent_messages)
        finally:
            self._refresh_in_flight = False

    def refresh(self, client, recent_messages):
        """Synchronous refresh — used by the webapp's 'refresh now' button.
        force=True so a user-initiated refresh always runs, even when not due."""
        self._refresh_sync(client, recent_messages, force=True)

    def _refresh_sync(self, client, recent_messages, force=False):
        reply = client.chat([{"role": "user", "content": refresh_prompt(recent_messages)}])
        proposal = parse_refresh_json(reply)
        with _FILE_LOCK:
            # Re-check under the lock AFTER the (slow) model call: a concurrent
            # request may have refreshed while we were talking. Benign either
            # way, but this closes the double-refresh window for real.
            if not force and not self.refresh_due():
                return
            if proposal:
                merge_refresh(self.profile, proposal)
            self.profile["meta"]["turns_at_last_refresh"] = self.profile["meta"]["total_turns_observed"]
            self.profile["meta"]["last_refresh"] = time.time()
            self.profile["meta"]["refresh_count"] += 1
            self.save()
