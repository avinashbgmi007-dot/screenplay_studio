"""Finding integrity gate — the post-analysis pass that removes mechanically
FALSE findings and folds duplicates before delivery.

Why this exists
---------------
Measured against two real scripts (Pain_3, gun_pen; 61 findings), the error
rate was 12.8% / 13.6% — roughly 9x the 1.42% bar that "98.58% accurate"
implies. Every one of the 8 errors was *mechanical*, not a craft misjudgement:

    class            n   example
    duplicate        5   gun_pen #20 restates #14/#16 under a different category
    category         1   Pain3 #5 files a visual detail (cigar ash) as `dialogue`
    deterministic    1   GUN_GUY vs PEN_GUY flagged "one character" in a script
                         literally titled gun_pen (edit distance 2)
    inverted         1   a pass reporting the ABSENCE of a defect as a finding

None of these need a model to detect. The gate runs AFTER the analyzer and
BEFORE the verification summary, so every downstream count (the summary, the
evidence depth, the served JSON) describes the set the writer actually receives.

The three laws this module obeys
--------------------------------
1. **Flag, don't drop** (repo law). A finding is never removed in silence. Every
   removal lands in the withdrawal ledger with a machine-readable reason and the
   finding's full content, so `findings + withdrawals` is always the original
   list — the "nothing lost" law, made checkable.
2. **Precision over recall.** Wrongly withdrawing a *real* finding costs the
   writer a true note; missing a false one costs them a bad note. This repo has
   consistently chosen to keep the writer's information whole, so every rule
   here is deliberately narrow — it fires only on a signal that cannot be read
   the other way. When a rule would have to guess, it does not fire.
3. **Never promote an unverified finding to asserted.** The gate does not touch
   `verification` and does not rescue evidence into `evidence_quote`: doing so
   after pass 5 would let an unverified quote render as a confirmed citation.
   The product already badges anything that is not `verified` as unverified
   (`app.js`), so the gate adds no second register — it only removes falsehoods.

What the gate does NOT do
-------------------------
It does not reject "generic craft templates" (statements that could be said of
any script). Those are *unfalsifiable*, not *false* — they carry no truth value,
so they cannot be inaccurate, and the product already shows them as unverified.
Withdrawing them would lift the accuracy number by shrinking the denominator,
which is the exact failure mode this work set out to avoid. They are the
verifiability debt, and the fix for them is gate 11 (the analyzer emitting
observations), not deletion here.

Actions
-------
    keep        — delivered unchanged (the default; includes ungrounded findings,
                  which the app badges as unverified)
    reclassify  — delivered, with a corrected category (the observation may be
                  real; only its shelf was wrong)
    merge       — folded into an earlier finding that states what it absorbed;
                  the duplicate's full text is preserved in the ledger
    reject      — provably false (inverted, or a deterministic rule firing on
                  names that are not the same); removed from the delivered set,
                  preserved in the ledger
"""
from __future__ import annotations

import collections
import copy
import re
import unicodedata
from dataclasses import dataclass, field


# --------------------------------------------------------------------- helpers
def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def toks(s: str | None) -> set[str]:
    return {w for w in norm(s).split() if len(w) > 3}


def jaccard(a: str | None, b: str | None) -> float:
    A, B = toks(a), toks(b)
    if not (A | B):
        return 0.0
    return len(A & B) / len(A | B)


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def scenes_of(f: dict) -> set:
    return set(f.get("scene_refs") or [])


def vstatus(f: dict):
    v = f.get("verification")
    return v.get("status") if isinstance(v, dict) else v


def quote(f: dict) -> str:
    return (f.get("evidence_quote") or "").strip()


# -------------------------------------------------------------------- lexicons
# Tokens that betray a VISUAL claim (belongs to scene/action, not dialogue).
VISUAL = {"shot", "frame", "camera", "lighting", "closeup", "close", "ash",
          "cigar", "gesture", "visual", "image", "silhouette", "colour", "color",
          "shadow", "wide", "angle", "pan", "cut", "montage"}
# Tokens that betray a SPOKEN-line claim (belongs to dialogue).
SPOKEN = {"line", "says", "said", "spoken", "dialogue", "turn", "monologue",
          "voice", "voiceover", "speech", "exchange", "reply", "answers"}

# "the defect is absent" — a clean bill of health filed as feedback, not a
# finding. Deliberately NARROW. An earlier, broader form matched a bare
# "(is|are) (not )?(absent|missing|lacking)", which reads the same way as the
# perfectly valid defect "the subtext is missing" — withdrawing that would cost
# the writer a true note. The rule now requires the absent thing to BE a defect
# (problem/issue/flaw/weakness/defect), which cannot be read the other way.
# Known cost: a finding phrased as "a technique is absent" is not caught. That
# is the accepted side of the precision/recall trade this module declares.
ABSENCE = re.compile(
    r"\bno\s+(problem|issue|concern|flaw|weakness|defect)\b"
    r"|\b(is|are|was|were)\s+not\s+an\s+issue\b"
    r"|\b(works?|reads?|plays?)\s+(well|fine|cleanly|smoothly)\b"
    r"|\bsucceeds\s+at\b"
    r"|\b(is|are)\s+(present\s+and\s+effective|well[\s-]?handled|effectively\s+handled)\b"
    r"|\b(problem|issue|flaw|weakness|defect)s?\s+(is|are|was|were)\s+"
    r"(absent|missing|lacking|not\s+present)\b",
    re.I,
)
# a counter-signal: the sentence does flag a consequence after all
CONSEQUENCE = re.compile(r"\b(but|however|although|yet|undercuts|weakens|"
                         r"fails|reduces|costs|at the expense)\b", re.I)

# "these two names are the same character" — the deterministic name-variant rule
NAME_VARIANT = re.compile(
    r"\b(variant|spelling|spelled|two names|same character|inconsistent name|"
    r"name.{0,12}(vary|varies|inconsist)|character.{0,12}(name|named))\b", re.I)


# ---------------------------------------------------------------------- result
@dataclass
class Decision:
    orig: int
    action: str          # keep | reclassify | merge | reject
    reason: str
    finding: dict

    @property
    def withdrawn(self) -> bool:
        return self.action in ("merge", "reject")


@dataclass
class GateResult:
    decisions: list[Decision] = field(default_factory=list)

    def of(self, action: str) -> list[Decision]:
        return [d for d in self.decisions if d.action == action]

    @property
    def kept(self) -> list[Decision]:
        """Everything the writer still receives (as a finding)."""
        return [d for d in self.decisions if not d.withdrawn]

    @property
    def withdrawals(self) -> list[Decision]:
        """Everything removed from the delivered set — kept in the ledger."""
        return [d for d in self.decisions if d.withdrawn]

    @property
    def findings(self) -> list[dict]:
        return [d.finding for d in self.kept]

    @property
    def ledger(self) -> list[dict]:
        """The withdrawal ledger: {index, action, reason, finding} per removal.
        Carries the finding's FULL content, so nothing is lost by removing it
        from the delivered set."""
        return [{"index": d.orig, "action": d.action, "reason": d.reason,
                 "finding": d.finding} for d in self.withdrawals]

    @property
    def summary(self) -> collections.Counter:
        return collections.Counter(d.action for d in self.decisions)

    @property
    def accounted_for(self) -> bool:
        """The 'nothing lost' invariant: delivered + ledger == original."""
        return len(self.kept) + len(self.withdrawals) == len(self.decisions)


# ------------------------------------------------------------------- the gate
class FindingIntegrityGate:
    """Deterministic, model-free, and conservative. Runs on a copy of every
    finding and never mutates its input."""

    def __init__(self, dup_issue_sim: float = 0.70, dup_concept_sim: float = 0.55):
        self.dup_issue_sim = dup_issue_sim
        self.dup_concept_sim = dup_concept_sim

    # -- 1. duplicates -----------------------------------------------------
    def _dedupe(self, findings: list[dict]) -> dict[int, int]:
        """Return {duplicate_index: kept_index}.

        Only findings in the SAME scene are candidates, and only when they state
        the SAME observation — measured as near-identical issue text. Two
        deliberate narrowings, both measured against the real payloads:

        - **A shared quote is not sufficient.** `dedupe.collapse_exact_duplicates`
          established the product rule: one quoted line flagged under two
          different craft rules is TWO notes about one line, and must stay two
          rows. So the quote cannot be the warrant — the issue text must agree.
          (An earlier form of this rule merged on quote equality alone and would
          have silently violated that rule.)
        - **The category must agree.** A restatement under a different shelf is
          usually a different piece of work, and the shelf is information the
          writer would lose. Restricting to one category costs nothing on the
          measured payloads — it removed exactly the same 5 false findings as the
          cross-category form — while removing the risk of folding two shelves
          into one. Same-category restatements are also the ones the rule-linked
          dedup above cannot see, because it works through rule edges, not text.
        """
        merge: dict[int, int] = {}
        for j in range(len(findings)):
            if j in merge:
                continue
            b = findings[j]
            for i in range(j):
                a = findings[i]
                if not (scenes_of(a) & scenes_of(b)):
                    continue
                if a.get("category") != b.get("category"):
                    continue
                sim = jaccard(a.get("issue"), b.get("issue"))
                # (a) near-identical issue text — the same observation twice
                if sim >= self.dup_issue_sim:
                    merge[j] = i
                    break
                # (b) both ungrounded: a looser bar, because neither carries a
                #     quote to corroborate it and the shared concept is the only
                #     signal there is
                if not quote(a) and not quote(b) and sim >= self.dup_concept_sim:
                    merge[j] = i
                    break
        return merge

    # -- 2. category mismatch ---------------------------------------------
    def _category_mismatch(self, f: dict) -> str | None:
        cat = (f.get("category") or "").lower()
        issue = norm(f.get("issue"))
        if cat == "dialogue":
            has_visual = bool(toks(f.get("issue")) & VISUAL)
            has_spoken = bool(toks(f.get("issue")) & SPOKEN)
            if has_visual and not has_spoken:
                return "claim is about a visual/scene detail, not a spoken line"
        if cat == "genre":
            if re.search(r"\barc\b|\bwant\b.*\bneed\b|\blie\b|\bghost\b|\bwound\b", issue):
                return "claim is a character-arc note, not a genre convention"
        return None

    # -- 3. deterministic false positive ----------------------------------
    def _deterministic_fp(self, f: dict) -> str | None:
        rid = (f.get("rule_id") or "").lower()
        blob = f"{rid} {f.get('issue') or ''}"
        if not NAME_VARIANT.search(blob):
            return None
        names = re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", f.get("issue") or "")
        names = [n for n in dict.fromkeys(names) if n not in {"THE", "AND"}]
        if len(names) < 2:
            return None
        best = None
        for x in range(len(names)):
            for y in range(x + 1, len(names)):
                a, b = names[x], names[y]
                d = edit_distance(a, b)
                sub = a in b or b in a
                if best is None or d < best[0]:
                    best = (d, a, b, sub)
        if best and best[0] >= 2 and not best[3]:
            d, a, b, _ = best
            return (f"name-variant rule fired on {a} vs {b} (edit distance {d}); "
                    f"neither name contains the other — no evidence they are one character")
        return None

    # -- 4. inverted finding ----------------------------------------------
    def _inverted(self, f: dict) -> str | None:
        issue = f.get("issue") or ""
        if ABSENCE.search(issue) and not CONSEQUENCE.search(issue):
            return "reports the ABSENCE of a defect — a clean bill of health filed as a finding"
        return None

    # -- run ---------------------------------------------------------------
    def run(self, findings: list[dict]) -> GateResult:
        res = GateResult()
        merge_map = self._dedupe(findings)
        absorbed: dict[int, list[int]] = collections.defaultdict(list)
        for dup, keep in merge_map.items():
            absorbed[keep].append(dup)

        for i, original in enumerate(findings):
            f = copy.deepcopy(original)  # never mutate the caller's finding

            if i in merge_map:
                res.decisions.append(Decision(
                    i, "merge",
                    f"duplicate of #{merge_map[i]} (same scene, same evidence/observation)",
                    f))
                continue

            inv = self._inverted(f)
            if inv:
                res.decisions.append(Decision(i, "reject", inv, f))
                continue

            fp = self._deterministic_fp(f)
            if fp:
                res.decisions.append(Decision(i, "reject", fp, f))
                continue

            reason_bits: list[str] = []
            if absorbed.get(i):
                f["merged_from"] = absorbed[i]
                reason_bits.append(f"absorbed duplicate(s) {absorbed[i]}")

            mismatch = self._category_mismatch(f)
            if mismatch:
                # reclassify rather than drop: the observation may be real,
                # only its category is wrong.
                f["_category_was"] = f.get("category")
                f["category"] = "scene" if "visual" in mismatch else "character"
                reason_bits.append(f"category corrected: {mismatch}")
                res.decisions.append(Decision(i, "reclassify", "; ".join(reason_bits), f))
                continue

            res.decisions.append(Decision(i, "keep", "; ".join(reason_bits) or "clean", f))

        return res


# ----------------------------------------------------------------- convenience
def gate_findings(findings: list[dict], gate: FindingIntegrityGate | None = None):
    """Run the gate and return `(delivered, ledger)` — the two halves of the
    original list, in a form the pipeline can store without any further work.

    `delivered + [e["finding"] for e in ledger]` is always the original list,
    which is the 'nothing lost' invariant the pipeline test pins.
    """
    result = (gate or FindingIntegrityGate()).run(findings)
    return result.findings, result.ledger
