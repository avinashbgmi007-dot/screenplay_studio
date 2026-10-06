"""
observation_pass.py — gate 11: ground what the verifier could not.

The measured problem
--------------------
On two real scripts, 50–64 % of delivered findings carried NO evidence at all.
The script-level categories (theme / character / structure / scene_function)
reason from scene summaries, so their prompts force `evidence_quote: null`. A
finding with no evidence is unfalsifiable: the writer cannot check it, the
verifier cannot score it, and "98.58 % accurate" cannot be measured over it.
That set is the verifiability debt.

What this pass does
-------------------
For each finding the verifier left at `no_quote`, ask the model to restate the
note as a falsifiable OBSERVATION and to cite the line it rests on. Then — and
this is the part that matters — RE-VERIFY that citation against the script with
the SAME `verifier.verify_finding` every other pass uses, at the same 0.72
fuzzy threshold. The model's own opinion is never trusted: it is not even asked
for one (the grammar has no `grounded` field). A confident fabricated citation
is precisely the failure the verifier exists to catch, so accepting a model's
self-report would undo the check it is standing on.

A finding is grounded only when the citation SURVIVES verification. Otherwise
the finding is returned EXACTLY as it was — still `no_quote`, still flagged
unverified in the UI. Nothing is promoted on the model's say-so.

What this does NOT do
---------------------
- **It does not rewrite `issue`.** The writer-facing sentence stays the
  analyzer's; the pass ADDS a verified citation and the observation it rests
  on. Two fields, never a replacement.
- **It does not claim the citation SUPPORTS the claim** — only that the line
  exists in the script. Semantic support is the writer's judgment, which is
  what the verdict channel measures. This pass raises VERIFIABILITY (metric B),
  not truth (metric A).
- **It does not touch `not_found` or `verified` findings.** Retrying a citation
  the verifier already rejected would erase the record that the model's first
  one was wrong; a `verified` finding has nothing to gain.

A side effect worth naming: attaching a quote moves the finding's id from the
`issue` tier to the `quote` tier (`revision.compute_finding_id`). That makes the
id MORE stable across re-analyses, not less — a quote survives the model
re-wording the issue, which is exactly how an ungrounded finding's mark gets
orphaned today.

Measured — and a correction
---------------------------
The design prototype (docs/design/scene-first/grounding_pass.py) reported
"grounding 21% -> 66%". That number is NOT comparable to this pass: the
prototype counted the model's SELF-REPORTED `VERDICT: GROUNDED` line without
ever checking the citation against the script. Re-measured here, with every
citation re-verified by `verify_finding`, the honest yield on the two real
scripts is far lower:

    gun_pen  : 16 ungrounded ->  4 grounded  (25%)   coverage 24% -> 43%
    Pain_3   : 19 ungrounded ->  2 grounded  (11%)   coverage 43% -> 49%

The yield is noisy run-to-run (gun_pen grounded 2-7 across configs) because the
model's grammar-constrained generation degenerates into a truncated token loop
on roughly 2 calls in 5. Treat these as the honest range, not a precise figure.

The gap between the prototype's 66% and this ~10-25% is the whole point of the
pass's design: the prototype counted confident citations, and most confident
citations do not survive checking against the script. Roughly 40% of the targets
are ABSENCE claims ("no scene states an objective"), which have no line to cite
and correctly come back null — that share is irreducible by prompting and is why
this pass pays down the debt rather than clearing it.

Cost, honestly: ~40s per target on the 26B local model with retries, so a
full-limit run adds roughly 15 minutes to an analysis. That is the price of the
grounding; `SCREENPLAY_STUDIO_OBSERVATION_LIMIT` is the dial, and 0 or
`SCREENPLAY_STUDIO_OBSERVATION_PASS=0` stands the pass down entirely.

Cost
----
One model call per ungrounded finding, capped by `limit`, single-attempt. On by
default — it is the pass that pays the debt — with
`SCREENPLAY_STUDIO_OBSERVATION_PASS=0` as the field kill-switch and
`SCREENPLAY_STUDIO_OBSERVATION_LIMIT` as the cap.
"""
from __future__ import annotations

import copy
import dataclasses
import os

from screenplay_parser.quotematch import find_scene_text

from .grammar import observation_grounding_grammar
from .verifier import verify_finding

DEFAULT_LIMIT = 24

# The script text sent for one finding. A finding citing scenes gets those
# scenes; a whole-script claim gets the whole script. Capped so a 180-page
# screenplay cannot fill the context window by itself — the same reason
# pipeline.MAX_SCENE_CHARS exists for the other passes.
MAX_SCRIPT_CHARS = 24000

# The wording below is not a first draft — it was chosen by A/B measurement.
# Asking for "the line ... one line or two" grounded 25% of gun_pen's ungrounded
# findings; asking for "a SHORT distinctive phrase of about 4 to 12 words"
# grounded 43%. A shorter target is simply easier to reproduce verbatim, and a
# verbatim phrase is the only thing the verifier can accept. temperature=0 was
# measured too and was WORSE (18%) — the degenerate token loops this model falls
# into are suppressed by sampling, not encouraged by it. Do not "tidy" this copy
# without re-running the A/B (C:/tmp/ss_probe/probe_g11_ab.py).
SYSTEM = (
    "You are a script analyst grounding a note in a screenplay. A note is only "
    "checkable if a reader can point at the line it rests on.\n\n"
    "Return an OBSERVATION — a falsifiable statement about what is ON THE PAGE "
    "(a scene number, a count, who speaks, a repeated element, or the ABSENCE of "
    "a named thing). Not an evaluation.\n\n"
    "Return a `quote`: a SHORT distinctive phrase of about 4 to 12 words, copied "
    "word-for-word from the SCRIPT TEXT below. Copy it; do not retype it from "
    "memory, do not paraphrase, do not add or drop words. Choose the single most "
    "distinctive phrase a reader could search for.\n\n"
    "If the note is about an ABSENCE, or you cannot find a phrase you are certain "
    "is verbatim, set quote to null and record what you searched for in `search`. "
    "A wrong citation is worse than none — it will be checked against the script."
)

USER_TMPL = (
    "THE NOTE (category: {cat}, severity: {sev}):\n{issue}\n\n"
    "THE SCRIPT TEXT:\n{script}\n\n"
    "State the observation, then give the short verbatim phrase."
)


def observation_pass_enabled() -> bool:
    """The env kill-switch. `SCREENPLAY_STUDIO_OBSERVATION_PASS=0` stands the
    pass down without a code change — the same shape as the integrity gate's
    `SCREENPLAY_STUDIO_INTEGRITY_GATE=0`, and for the same reason: a pass that
    costs one model call per finding must be disableable in the field."""
    return os.environ.get("SCREENPLAY_STUDIO_OBSERVATION_PASS", "").strip().lower() \
        not in ("0", "false", "no", "off")


def observation_limit() -> int:
    """How many findings to attempt, from `SCREENPLAY_STUDIO_OBSERVATION_LIMIT`.
    A malformed or absent value falls back to DEFAULT_LIMIT; `0` disables the
    pass's work without touching the enable switch."""
    raw = os.environ.get("SCREENPLAY_STUDIO_OBSERVATION_LIMIT", "").strip()
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def needs_grounding(finding: dict) -> bool:
    """A finding is a target only when the verifier found NO quote to check.

    `not_found` is excluded on purpose (see the module docstring): the model
    already offered a citation and it did not verify. `scene_not_found` is a
    citation that points at scenes which do not exist — a different defect,
    fixed by the analyzer, not by re-asking.
    """
    return (finding.get("verification") or {}).get("status") == "no_quote"


def _script_text(doc, scenes) -> str:
    """The text to show the model: the cited scenes, or the whole script."""
    nums = [n for n in (scenes or []) if isinstance(n, int)]
    if nums:
        parts = [t for t in (find_scene_text(doc, n) for n in nums) if t]
        if parts:
            return "\n\n".join(parts)[:MAX_SCRIPT_CHARS]
    parts = []
    for scene in doc.scenes:
        text = find_scene_text(doc, scene.scene_number)
        if text:
            parts.append(f"--- SCENE {scene.scene_number}: {scene.heading_raw} ---\n{text}")
    return "\n\n".join(parts)[:MAX_SCRIPT_CHARS]


def _str_field(reply, key: str) -> str:
    if not isinstance(reply, dict):
        return ""
    value = reply.get(key)
    return value.strip() if isinstance(value, str) else ""


@dataclasses.dataclass
class ObservationResult:
    findings: list[dict]
    attempted: int = 0
    grounded: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)

    @property
    def ungrounded(self) -> int:
        return self.attempted - self.grounded

    def summary(self) -> dict:
        """The disclosure the report carries: how many were tried, how many
        came back with a citation that survived the verifier. The rest stay
        flagged unverified in the UI — no silent promotion."""
        return {"attempted": self.attempted, "grounded": self.grounded,
                "ungrounded": self.ungrounded}


class ObservationPass:
    """Deterministic in its accounting, model-backed in its one call per target.
    Never mutates its input — every finding is deep-copied first, the same
    discipline the integrity gate holds to."""

    def __init__(self, limit: int = DEFAULT_LIMIT, grammar: str | None = None):
        self.limit = limit
        self.grammar = grammar if grammar is not None else observation_grounding_grammar()

    def run(self, findings: list[dict], client, doc, on_progress=None) -> ObservationResult:
        out = [copy.deepcopy(f) for f in findings]
        res = ObservationResult(findings=out)
        targets = [i for i, f in enumerate(out) if isinstance(f, dict) and needs_grounding(f)]
        budget = min(max(0, self.limit), len(targets))
        for n, i in enumerate(targets[:budget], start=1):
            if on_progress:
                on_progress("observation", "running",
                            f"Grounding finding {n} of {budget}")
            res.attempted += 1
            f = out[i]
            try:
                # Keep the client's retries (measured, not assumed). This model's
                # grammar-constrained generation degenerates into a token loop
                # (truncated JSON) on roughly 2 calls in 5, and a fresh sample
                # usually clears it — dropping to retries=0 cut gun_pen's
                # grounding from 7/16 to 2/16. Retrying is the difference between
                # a pass that grounds and one that mostly reports failure, so it
                # is worth the extra generations. max_tokens=500 for headroom:
                # these scripts are Telugu-English and a verbatim Telugu quote
                # costs far more tokens than its character count suggests, so
                # 300 truncated mid-JSON.
                reply = client.chat_json(
                    SYSTEM,
                    USER_TMPL.format(cat=f.get("category"), sev=f.get("severity"),
                                     issue=f.get("issue") or "",
                                     script=_script_text(doc, f.get("scene_refs"))),
                    grammar=self.grammar, max_tokens=500)
            except Exception as e:
                # One finding that cannot be rewritten must never fail the run,
                # and must never be silently dropped from the count either.
                res.errors.append(f"Observation pass: finding {i} not grounded ({e})")
                continue

            quote = _str_field(reply, "quote")
            if not quote:
                continue  # the model found no citable line — the finding stays a question

            # Verify the citation against the script BEFORE adopting it. The
            # model's reply is a proposal; `verify_finding` is the judge.
            candidate = copy.deepcopy(f)
            candidate["evidence_quote"] = quote
            verify_finding(candidate, doc)
            if (candidate.get("verification") or {}).get("status") != "verified":
                continue

            f["evidence_quote"] = quote
            f["verification"] = candidate["verification"]
            observation = _str_field(reply, "observation")
            if observation:
                f["observation"] = observation
            res.grounded += 1
        return res
