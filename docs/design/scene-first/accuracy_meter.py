#!/usr/bin/env python3
"""
accuracy_meter.py — the instrument for the "98.58% precision" target.

Why this exists
---------------
The product asserts a quality bar it cannot currently measure. There is no
ground-truth channel: the writer's vocabulary is `addressed | deferred |
dismissed` (revision.py:75,101), and "dismissed" means *hide it*, not *it is
wrong*. So this file defines the metric and computes it from two inputs:

    --report   report.findings.json   (what the engine produced)
    --verdicts verdicts.json          (what a reader judged each finding to be)

The metric (the contract this file enforces)
--------------------------------------------
    precision      = correct / shown
    error_rate     = (wrong) / shown            <-- the 98.58% metric
    actionable     = (correct) / shown          <-- informational

    98.58% precision  ==  error_rate <= 0.0142  ==  at most 1 wrong in ~70.
    On a 39-finding report that is 0.55 wrong findings allowed: effectively zero.

The instrument also reports the two structural ceilings no UI can lift:
    evidence_coverage  = verified quotes / shown   (machine-checkable share)
    duplicate_rate     = auto-detected dupes / shown (a mechanical defect class)

Verdicts file shape
-------------------
    { "<finding index>": {"label": "correct|partial|wrong", "note": "..."}, ... }
A missing index is treated as `unjudged` and excluded from the rate, so a
partial labelling run is still honest about its denominator.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata


# ---------------------------------------------------------------- helpers
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


def vstatus(f: dict):
    v = f.get("verification")
    if isinstance(v, dict):
        return v.get("status")
    return v


def scenes_of(f: dict) -> set[int]:
    return set(f.get("scene_refs") or [])


# ---------------------------------------------------------------- dupes
def find_duplicates(findings: list[dict], sim: float = 0.80) -> list[tuple[int, int]]:
    """Same category AND (same scene overlap) AND issue text nearly identical,
    OR identical normalised quote within overlapping scenes. Returns index pairs."""
    dupes = []
    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            a, b = findings[i], findings[j]
            if a.get("category") != b.get("category"):
                continue
            if not (scenes_of(a) & scenes_of(b)):
                continue
            qi, qj = norm(a.get("evidence_quote")), norm(b.get("evidence_quote"))
            if qi and qi == qj:
                dupes.append((i, j))
                continue
            if jaccard(a.get("issue"), b.get("issue")) >= sim:
                dupes.append((i, j))
    return dupes


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--label", default="report")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report = json.load(open(args.report, encoding="utf-8"))
    findings = report.get("findings", [])
    verdicts = {int(k): v for k, v in json.load(open(args.verdicts, encoding="utf-8")).items()}

    dupes = find_duplicates(findings)
    dup_idx = {i for pair in dupes for i in pair[1:]}  # keep the first of each pair

    # ---- per-category tally
    by_cat: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    overall = collections.Counter()
    evidence = collections.Counter()

    for i, f in enumerate(findings):
        cat = f.get("category") or "?"
        lab = (verdicts.get(i) or {}).get("label", "unjudged")
        st = vstatus(f)
        by_cat[cat][lab] += 1
        by_cat[cat]["n"] += 1
        overall[lab] += 1
        overall["n"] += 1
        if st == "verified":
            by_cat[cat]["verified"] += 1
            evidence["verified"] += 1
        if (f.get("evidence_quote") or "").strip():
            by_cat[cat]["quoted"] += 1
            evidence["quoted"] += 1
        if i in dup_idx:
            by_cat[cat]["dup"] += 1
            evidence["dup"] += 1

    judged = overall["correct"] + overall["partial"] + overall["wrong"]
    denom = judged or 1

    def pct(n: int, d: int) -> str:
        return f"{100.0 * n / d:.1f}%" if d else "—"

    if args.json:
        print(json.dumps({
            "label": args.label,
            "shown": overall["n"],
            "judged": judged,
            "correct": overall["correct"],
            "partial": overall["partial"],
            "wrong": overall["wrong"],
            "error_rate": overall["wrong"] / denom,
            "precision_correct_only": overall["correct"] / denom,
            "evidence_coverage": evidence["verified"] / (overall["n"] or 1),
            "duplicate_rate": evidence["dup"] / (overall["n"] or 1),
            "by_category": {c: dict(v) for c, v in by_cat.items()},
        }, indent=1))
        return 0

    print(f"\n{'=' * 74}")
    print(f"ACCURACY METER — {args.label}")
    print(f"{'=' * 74}")
    print(f"  shown            : {overall['n']}")
    print(f"  judged           : {judged}  (unjudged excluded from rates)")
    print(f"  correct / partial / wrong : {overall['correct']} / {overall['partial']} / {overall['wrong']}")
    print()
    print(f"  ERROR RATE       : {pct(overall['wrong'], denom)}   <-- the 98.58% metric (target <= 1.42%)")
    print(f"  precision (strict, correct only) : {pct(overall['correct'], denom)}")
    print(f"  precision (lenient, correct+partial) : {pct(overall['correct'] + overall['partial'], denom)}")
    band_lo = overall["correct"] / denom
    band_hi = (overall["correct"] + overall["partial"]) / denom
    print(f"  PRECISION BAND   : {pct(overall['correct'], denom)} .. {pct(overall['correct'] + overall['partial'], denom)}"
          f"   (the {overall['partial']} 'partial' findings decide it — {pct(overall['partial'], denom)} of the report)")
    print(f"  error band       : {pct(overall['wrong'] + overall['partial'], denom)} .. {pct(overall['wrong'], denom)}"
          f"   (if a strict writer calls every 'partial' wrong)")
    print()
    print(f"  evidence coverage (verified quote) : {pct(evidence['verified'], overall['n'])}")
    print(f"  duplicate rate (auto-detected)     : {pct(evidence['dup'], overall['n'])}")

    # --- the asserted tier: a verified quote that IS the subject of the claim.
    # Mechanical proxy: verification.status == verified AND the quote is not a
    # scene heading AND the category is a line-level one (the claim is about a
    # line of the script, not about the whole scene/script).
    LINE_LEVEL = {"dialogue", "character"}
    asserted = [(i, f) for i, f in enumerate(findings)
                if vstatus(f) == "verified"
                and (f.get("evidence_quote") or "").strip()
                and (f.get("category") or "") in LINE_LEVEL]
    ac = sum(1 for i, _ in asserted if (verdicts.get(i) or {}).get("label") == "correct")
    aw = sum(1 for i, _ in asserted if (verdicts.get(i) or {}).get("label") == "wrong")
    ap = len(asserted) - ac - aw
    print()
    print(f"  ASSERTED TIER (verified quote that is the claim's subject)")
    print(f"    n = {len(asserted)} ({pct(len(asserted), overall['n'])} of the report)"
          f"  correct/wrong/partial = {ac}/{aw}/{ap}")
    print(f"    ASSERTED PRECISION = {pct(ac, len(asserted) or 1)}   <-- the number the 98.58% target can attach to")
    print(f"    OBSERVED TIER      = {pct(overall['n'] - len(asserted), overall['n'])} of findings, presented for writer judgment, not asserted")
    print()
    print(f"  {'category':16}{'n':>4}{'corr':>6}{'part':>6}{'wrong':>7}{'dup':>5}{'verif':>7}{'err%':>8}")
    for c in sorted(by_cat, key=lambda k: -by_cat[k]["n"]):
        v = by_cat[c]
        d = (v["correct"] + v["partial"] + v["wrong"]) or 1
        print(f"  {c:16}{v['n']:>4}{v['correct']:>6}{v['partial']:>6}{v['wrong']:>7}"
              f"{v['dup']:>5}{v['verified']:>7}{pct(v['wrong'], d):>8}")
    if dupes:
        print(f"\n  duplicate pairs (kept-first): {[(i, j) for i, j in dupes]}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
