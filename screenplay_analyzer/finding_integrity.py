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
    reject      — provably a non-finding (inverted, praise-as-finding, or a
                  deterministic rule firing on names that are not the same);
                  removed from the delivered set, preserved in the ledger
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

# "praise filed as a finding" — a compliment or neutral description with no
# defect claim (trial 11: "Dialogue contains multiple subtext layers" and
# "Dialogue reflects cultural context" filed as defects). Deliberately
# NARROW, same contract as ABSENCE above: the issue must carry a praise
# marker AND neither issue nor observation may carry a defect marker or a
# contrast turn (but/however/although...). A mixed note ("rich but
# unearned") is a real defect and is kept; only unalloyed praise is
# withdrawn. Quotes are never scanned — verbatim script text by design.
# Known cost: praise worded without these markers is not caught. That is the
# accepted side of the precision/recall trade this module declares.
PRAISE = re.compile(
    r"\bcontains\s+multiple\b"
    r"|\breflects?\b"
    r"|\brich\b|\beffective\b|\bcompelling\b|\bexcellent\b|\bnuanced\b"
    r"|\bimpressive\b|\bbeautiful\b|\bpowerful\b|\bwell[\s-]?crafted\b",
    re.I,
)
# a counter-signal: the sentence does flag a defect after all (superset of
# CONSEQUENCE, which only covers contrast turns)
DEFECT_MARK = re.compile(
    r"\b(but|however|although|yet|undercuts|weakens|fails|reduces|costs|"
    r"at the expense)\b"
    r"|\b(not|n't|never|no)\b"
    r"|\b(lack\w*|fail\w*|miss\w*|weak\w*|without|absent|inconsistent|"
    r"unclear|generic|static|poor|bad|flat|forced|abrupt|unearned|passive|"
    r"repetitive|redundant|vague|confus\w*|disrupt\w*|problem|flaw|defect)\b",
    re.I,
)

# "absolute absence, falsified by presence" — trial-10 #4 ("objects do
# not recur" while the pen recurs two scenes later). Same narrow
# contract as ABSENCE/PRAISE above: unhedged phrasing required, positive
# proof required, quotes never scanned.
ABSENCE_CLAIM = re.compile(
    r"\bdo(?:es)?\s+not\s+recur\b|\bnever\s+(referenced|mentioned|seen|reappear"
    r"s?|recur\w*|addressed)\b"
    r"|\bno\s+dialogue\b|\bnever\s+speaks?\b|\bno\s+action\s+lines?\b"
    r"|\bno\s+confrontation\b|\babsent\s+from\b",
    re.I,
)
HEDGE = re.compile(
    r"\b(appears?|seems?|may|might|arguably|suggests?|possibly|likely)\b",
    re.I,
)

# "these two names are the same character" — the deterministic name-variant rule
NAME_VARIANT = re.compile(
    r"\b(variant|spelling|spelled|two names|same character|inconsistent name|"
    r"name.{0,12}(vary|varies|inconsist)|character.{0,12}(name|named))\b", re.I)

# "identity verdict contradicted by explicit equation" — trial-10 #12's
# mirror. The pipeline demotes identity verdicts the text cannot settle;
# when the text DOES settle one — an explicit equation (X addressed as Y)
# beside a verdict that X is NOT Y — the verdict is provably false and is
# withdrawn, not demoted. Deliberately NARROW, same contract as the rules
# above: only a distinctness verdict beside sameness evidence fires. A
# sameness verdict ("is really Y", "same character") beside an equation is
# supported, not contradicted, so it is kept; dialogue co-presence (both
# parties speak) supports a distinctness verdict and is never a
# contradiction — only the equation branch of the pipeline's
# `_identity_proven` rule is mirrored here, never its co-presence branch.
# Quotes are never scanned — verbatim script text by design.
# Known cost: sameness verdicts falsified by co-presence are not caught.
# That is the accepted side of the precision/recall trade this module declares.
_IDENTITY_SAMENESS = re.compile(r"\bis\s+really\b|\bsame\s+character\b", re.I)
_IDENTITY_EQUATION_VERB = re.compile(r"\b(calls|addresses|greets|names)\b", re.I)


def _identity_eq_name_pat(name: str) -> str:
    """Regex matching a normalized cue name with flexible inner spacing."""
    return r"\s*".join(re.escape(w) for w in name.split())


def _identity_eq_type(e) -> str:
    t = getattr(e, "type", None)
    return str(getattr(t, "value", t) or "").lower()


def _identity_eq_names_in(text: str, *names: str) -> bool:
    normed = re.sub(r"\s+", " ", str(text or "").upper().replace("_", " "))
    return all(re.search(r"\b" + _identity_eq_name_pat(n) + r"\b", normed) for n in names)


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

    # -- 4b. praise filed as a finding --------------------------------------
    def _praise_filed(self, f: dict) -> str | None:
        issue = f.get("issue") or ""
        if not PRAISE.search(issue):
            return None
        text = f"{issue} {f.get('observation') or ''}"
        if DEFECT_MARK.search(text):
            return None
        return "praise filed as a finding — a compliment or neutral description with no defect claim"

    # -- 4c. absence claim falsified by presence ---------------------------
    def _absence_falsified(self, f: dict, doc) -> str | None:
        issue = f.get("issue") or ""
        if doc is None or not ABSENCE_CLAIM.search(issue):
            return None
        text = f"{issue} {f.get('observation') or ''}"
        if HEDGE.search(text) or CONSEQUENCE.search(text):
            return None
        refs = f.get("scene_refs") or []
        if not refs:
            return None
        scenes = getattr(doc, "scenes", None) or []
        valid = {s.scene_number for s in scenes}
        if any(r not in valid for r in refs):
            return None
        # Pronoun subjects carry no resolvable referent — never guess.
        if re.match(r"\s*(he|she|they)\b", issue, re.I):
            return None
        pronouns = {"he", "she", "they", "him", "her", "them"}

        # -- missing lines: X has a cue in the cited range -----------------
        if re.search(r"\bno\s+dialogue\b|\bnever\s+speaks?\b"
                     r"|\bno\s+action\s+lines?\b", issue, re.I):
            name = None
            m = re.search(r"(?i:\bno\s+dialogue\s+(?:lines?\s+)?for\s+)"
                          r"([A-Z][\w\-']*(?:\s+[A-Z][\w\-']*)*)", issue)
            if not m:
                m = re.search(r"(?i:\bno\s+action\s+lines?\s+for\s+)"
                              r"([A-Z][\w\-']*(?:\s+[A-Z][\w\-']*)*)", issue)
            if not m:
                m = re.search(r"\b([A-Z][\w\-']*(?:\s+[A-Z][\w\-']*)*)"
                              r"\s+(?i:never\s+speaks?)\b", issue)
            if m:
                name = m.group(1)
            if not name:
                return None
            first = name.strip().split()[0].lower() if name.strip() else ""
            if first in pronouns:
                return None
            want = norm(name)
            if not want:
                return None
            for r in sorted(refs):
                sc = next((s for s in scenes if s.scene_number == r), None)
                if sc is None:
                    continue
                present = {norm(c) for c in (sc.characters_present or [])}
                if want in present:
                    return f"absence claim falsified by presence in scene(s) {r}"
                for el in (sc.elements or []):
                    if getattr(el, "character", None) and norm(el.character) == want:
                        return f"absence claim falsified by presence in scene(s) {r}"
            return None

        # -- non-recurrence: object terms recur after the cited range ------
        if re.search(r"\bdo(?:es)?\s+not\s+recur\b|\bnever\s+(?:referenced|"
                     r"mentioned|seen|reappears?|recur\w*)\b", issue, re.I):
            from screenplay_analyzer.setup_payoff import _content_terms, _terms_in_scenes
            m = re.search(r"\bdo(?:es)?\s+not\s+recur\b|\bnever\s+(?:referenced|"
                          r"mentioned|seen|reappears?|recur\w*)\b", issue, re.I)
            before = issue[:m.start()] if m else issue
            # The named object, not the framing prose: "… (gun, newspaper,
            # pen) do not recur" carries framing words (chekhov/emphasis/
            # narrative/objects/given) that hold single-scene overlap below
            # the 0.5 floor even when the objects do recur. Prefer (a) the
            # parenthesized span immediately before the marker, else (b) a
            # quoted span in the issue, else (c) the full prefix as before.
            terms = None
            pm = re.search(r"\(([^()]+)\)\s*$", before)
            if pm:
                scoped = _content_terms(pm.group(1))
                if scoped:
                    terms = scoped
            if terms is None:
                qm = re.search(r'"([^"]+)"', issue)
                if qm:
                    scoped = _content_terms(qm.group(1))
                    if scoped:
                        terms = scoped
            if terms is None:
                terms = _content_terms(before)
            if not terms:
                return None
            if {t.lower() for t in terms} <= pronouns:
                return None
            max_ref = max(refs)
            later = sorted(s.scene_number for s in scenes if s.scene_number > max_ref)
            if not later:
                return None
            hit, at = _terms_in_scenes(terms, doc, later)
            if hit:
                return f"absence claim falsified by presence in scene(s) {at}"
            return None

        # -- missing beats: beat content lands in the cited range ----------
        if re.search(r"\bno\s+confrontation\b|\babsent\s+from\b"
                     r"|\bnever\s+addressed\b", issue, re.I):
            from screenplay_analyzer.setup_payoff import _content_terms, _terms_in_scenes
            m_af = re.search(r"\babsent\s+from\b", issue, re.I)
            if m_af:
                before_af = issue[:m_af.start()]
                before_clean = re.sub(r"\b(is|was|are|were)\s*$", "",
                                      before_af, flags=re.I).strip()
                m_name = re.search(r"([A-Z][\w\-']*(?:\s+[A-Z][\w\-']*)*)\s*$",
                                   before_clean)
                if m_name:
                    name = m_name.group(1)
                    first = name.strip().split()[0].lower() if name.strip() else ""
                    if first in pronouns:
                        return None
                    if first not in ("the", "a", "an", "this", "that",
                                     "these", "those", "it"):
                        want = norm(name)
                        if want:
                            for r in sorted(refs):
                                sc = next((s for s in scenes
                                           if s.scene_number == r), None)
                                if sc is None:
                                    continue
                                present = {norm(c) for c in
                                           (sc.characters_present or [])}
                                if want in present:
                                    return ("absence claim falsified by presence "
                                            f"in scene(s) {r}")
                                for el in (sc.elements or []):
                                    if getattr(el, "character", None) and \
                                            norm(el.character) == want:
                                        return ("absence claim falsified by presence "
                                                f"in scene(s) {r}")
                            return None
            m_beat = re.search(r"(?i:\bno\s+)(confrontation)\b", issue)
            if m_beat:
                beat_text = m_beat.group(1)
            else:
                m2 = re.search(r"\babsent\s+from\b|\bnever\s+addressed\b",
                               issue, re.I)
                beat_text = issue[:m2.start()] if m2 else issue
            terms = _content_terms(beat_text)
            if not terms:
                return None
            if {t.lower() for t in terms} <= pronouns:
                return None
            hit, at = _terms_in_scenes(terms, doc, sorted(refs))
            if hit:
                return f"absence claim falsified by presence in scene(s) {at}"
            return None
        return None

    # -- 4d. identity verdict contradicted by explicit equation -----------
    def _identity_contradicted(self, f: dict, doc) -> str | None:
        """A distinctness verdict ("X is not Y") beside an explicit equation
        (the text addressing X as Y) is provably false — withdraw it. The
        equation supports the OPPOSITE of the claim, which is what makes it
        a contradiction rather than support."""
        if doc is None:
            return None
        # Lazy: the pipeline never imports the gate at module load, so no cycle
        # (verified with `python -c "import screenplay_analyzer.finding_integrity"`).
        from .pipeline import _identity_parties
        from screenplay_parser.heuristics import normalize_character_name
        parties = _identity_parties(f)
        if parties is None:
            return None
        text = f"{f.get('issue') or ''} {f.get('observation') or ''}"
        if _IDENTITY_SAMENESS.search(text):
            # A sameness verdict beside an equation is supported, not
            # contradicted — any doubt keeps the row.
            return None
        refs = [r for r in (f.get("scene_refs") or []) if isinstance(r, int)]
        if not refs:
            return None
        scenes = {s.scene_number: s for s in (getattr(doc, "scenes", None) or [])}
        if any(r not in scenes for r in refs):
            return None
        a, b = parties
        for r in sorted(refs):
            for e in getattr(scenes[r], "elements", None) or []:
                t = _identity_eq_type(e)
                chn = normalize_character_name(str(getattr(e, "character", None) or "")).upper()
                etext = getattr(e, "text", None) or ""
                if t == "dialogue" and chn in (a, b):
                    other = b if chn == a else a
                    if _identity_eq_names_in(etext, other):
                        return ("identity verdict contradicted by explicit equation "
                                f"in scene(s) {r}")
                elif t == "action" and _IDENTITY_EQUATION_VERB.search(etext):
                    if _identity_eq_names_in(etext, a, b):
                        return ("identity verdict contradicted by explicit equation "
                                f"in scene(s) {r}")
                elif t == "parenthetical" and chn in (a, b):
                    other = b if chn == a else a
                    if re.search(r"\(\s*as\s+" + _identity_eq_name_pat(other) + r"\s*\)", etext, re.I):
                        return ("identity verdict contradicted by explicit equation "
                                f"in scene(s) {r}")
                elif t == "scene_heading":
                    for x, y in ((a, b), (b, a)):
                        xp, yp = _identity_eq_name_pat(x), _identity_eq_name_pat(y)
                        if re.search(xp + r"\s*=\s*" + yp, etext, re.I):
                            return ("identity verdict contradicted by explicit equation "
                                    f"in scene(s) {r}")
                        if re.search(xp + r"\s+as\s+" + yp, etext, re.I):
                            return ("identity verdict contradicted by explicit equation "
                                    f"in scene(s) {r}")
                        if re.search(xp + r"\s*-\s*as\s*-\s*" + yp, etext, re.I):
                            return ("identity verdict contradicted by explicit equation "
                                    f"in scene(s) {r}")
        return None

    # -- run ---------------------------------------------------------------
    def run(self, findings: list[dict], doc=None) -> GateResult:
        res = GateResult()
        merge_map = self._dedupe(findings)
        absorbed: dict[int, list[int]] = collections.defaultdict(list)
        for dup, keep in merge_map.items():
            absorbed[keep].append(dup)

        for i, original in enumerate(findings):
            f = copy.deepcopy(original)  # never mutate the caller's finding

            reason_bits: list[str] = []
            if (f.get("category") or "").lower() == "scene":
                # "scene" was never in FINDING_CATEGORIES (trial 5: an older
                # gate revision wrote it). Intake normalization, not a
                # verdict — the row is still judged on its merits below.
                f["category"] = "scene_function"
                reason_bits.append("intake category normalized: scene → scene_function")

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

            praise = self._praise_filed(f)
            if praise:
                res.decisions.append(Decision(i, "reject", praise, f))
                continue

            falsified = self._absence_falsified(f, doc)
            if falsified:
                res.decisions.append(Decision(i, "reject", falsified, f))
                continue

            fp = self._deterministic_fp(f)
            if fp:
                res.decisions.append(Decision(i, "reject", fp, f))
                continue

            if doc is not None:
                contra = self._identity_contradicted(f, doc)
                if contra:
                    res.decisions.append(Decision(i, "reject", contra, f))
                    continue

            reason_bits: list[str]
            if absorbed.get(i):
                f["merged_from"] = absorbed[i]
                reason_bits.append(f"absorbed duplicate(s) {absorbed[i]}")

            mismatch = self._category_mismatch(f)
            if mismatch:
                # reclassify rather than drop: the observation may be real,
                # only its category is wrong.
                f["_category_was"] = f.get("category")
                f["category"] = "scene_function" if "visual" in mismatch else "character"
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
