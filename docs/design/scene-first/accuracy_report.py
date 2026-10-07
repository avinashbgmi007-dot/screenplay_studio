#!/usr/bin/env python3
"""
accuracy_report.py — the unified two-metric accuracy report.

The decision this implements (2026-10-05)
----------------------------------------
98.58% is measured TWO ways, and both matter. They are not alternatives; they
cover different populations and answer different questions.

  METRIC A — WRITER-AGREEMENT  (the HEADLINE; covers ALL feedback)
      precision = correct / (correct + wrong), over every item DELIVERED to the
      writer — findings *and* prompts. Supplied by the writer through the
      verdict channel (correct / wrong / partial). A prompt counts: answering
      "was this a real problem?" is a verdict.
      This is the number the user asked for: "the end user-writer would be
      waiting on to fix things".

  METRIC B — FACTUAL CORRECTNESS  (the INTERNAL GATE; observations only)
      error_rate = wrong / judged, over the ASSERTED tier — the items where a
      verified quote IS the subject of the claim. This is what the pipeline can
      guarantee with no writer in the loop.

Why both, and why neither substitutes for the other
---------------------------------------------------
    perfect observations the writer ignores  ->  B = 100%, A = 0%
    agreeable opinions                       ->  A high,  B unmeasurable
Only A proves the writer trusts the output; only B proves the output is
checkable. The product must clear both.

What this instrument adds over accuracy_meter.py
------------------------------------------------
accuracy_meter.py scores the RAW report. This runs the integrity gate FIRST and
reports the metric on what the gate would actually deliver — so it can answer
the operational question: *how much of the 98.58% is bought by the gate alone,
before any model or prompt change?*

Inputs
------
    --report    report.findings.json
    --verdicts  verdicts.json   { "<index>": {"label": "correct|partial|wrong"} }

Exit code is 0 always; the report is the output, not a pass/fail gate.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from finding_integrity import FindingIntegrityGate, score as gate_score  # noqa: E402

TARGET = 0.9858
TARGET_ERR = 1.0 - TARGET          # 1.42 %


def pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.1f}%" if d else "—"


def _lab(verdicts: dict[int, dict], i: int) -> str:
    return (verdicts.get(i) or {}).get("label", "unjudged")


def agreement(indices, verdicts) -> dict:
    """Metric A over a set of finding indices.

    THREE readings of the same tally, because the choice of denominator is the
    whole game. `precision` (correct / (correct+wrong)) EXCLUDES the ambiguous
    middle and is therefore gameable — a writer who marks everything `partial`
    scores undefined-or-high. It is reported for continuity with the earlier
    instrument, but it is NOT the headline.

    The headline is `strict` = correct / ALL delivered. Nothing is excluded: a
    finding the writer cannot fully endorse is not agreement. `partial` is then
    the single most diagnostic number in the product — it is the ambiguous
    middle that the observation contract (gate 11) exists to eliminate.
    """
    c = sum(1 for i in indices if _lab(verdicts, i) == "correct")
    w = sum(1 for i in indices if _lab(verdicts, i) == "wrong")
    p = sum(1 for i in indices if _lab(verdicts, i) == "partial")
    ruled = c + w
    n = c + p + w
    return {
        "n": len(indices), "correct": c, "partial": p, "wrong": w,
        "ruled": ruled, "all_ruled": n,
        # -- gameable: excludes the ambiguous middle
        "precision": (c / ruled) if ruled else None,
        # -- HEADLINE: ungameable; nothing excluded
        "strict": (c / n) if n else None,
        # -- weighted: a partial is worth half
        "weighted": ((c + 0.5 * p) / n) if n else None,
        # -- lenient: "not wrong". A true-but-unverifiable observation is still
        #    valid feedback, so this is the accuracy reading that separates
        #    ACCURACY (is it true?) from VERIFIABILITY (can we check it?).
        "lenient": ((c + p) / n) if n else None,
        # to clear the bar under the STRICT reading, allowed wrong+partial:
        "wrong_allowed": int(n * TARGET_ERR),
        "wrong_excess": (w + p) - int(n * TARGET_ERR),
    }


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

    # ---- run the integrity gate (deterministic, model-free)
    gate = FindingIntegrityGate()
    res = gate.run(findings)
    gs = gate_score(res, verdicts)

    # ---- populations
    all_idx = list(range(len(findings)))
    delivered_idx = [d.orig for d in res.decisions if d.action in ("keep", "reclassify", "demote")]
    asserted_idx = [d.orig for d in res.decisions if d.action in ("keep", "reclassify")]
    prompt_idx = [d.orig for d in res.decisions if d.action == "demote"]

    A_before = agreement(all_idx, verdicts)            # raw report
    A_after = agreement(delivered_idx, verdicts)       # what the gate delivers
    B_asserted = agreement(asserted_idx, verdicts)     # the internal gate

    # per-category, post-gate
    by_cat: dict[str, list[int]] = collections.defaultdict(list)
    for i in delivered_idx:
        by_cat[findings[i].get("category") or "?"].append(i)

    if args.json:
        print(json.dumps({
            "label": args.label,
            "gate": dict(res.summary),
            "metric_a_writer_agreement": {
                "before_gate": A_before, "after_gate": A_after,
            },
            "metric_b_factual_correctness": B_asserted,
            "target": TARGET,
        }, indent=1, default=str))
        return 0

    W = 78
    print(f"\n{'=' * W}")
    print(f"TWO-METRIC ACCURACY REPORT — {args.label}")
    print(f"{'=' * W}")
    print(f"  report: {len(findings)} findings  ->  gate  ->  "
          f"{len(asserted_idx)} findings · {len(prompt_idx)} prompts · "
          f"{gs['merged']} merged · {gs['rejected']} withdrawn")
    print(f"  gate: {dict(res.summary)}")
    print(f"  withdrawn by verdict: wrong={gs['removed_wrong']} partial={gs['removed_partial']} "
          f"correct={gs['removed_correct']}  "
          f"{'(no false positives)' if gs['removed_correct'] == 0 else '<-- FALSE POSITIVES'}")

    # ---------------- METRIC A ----------------
    print()
    print(f"  ── METRIC A · WRITER-AGREEMENT   (HEADLINE — covers ALL feedback) ──")
    print(f"     four readings of the SAME tally. Which one is '98.58%' is a product decision,")
    print(f"     not a technical one — and it is settled by the two-axis verdict channel.")
    print(f"     {'':26}{'strict':>8}{'weighted':>10}{'lenient':>9}{'excl-part':>11}")
    for name, a in (("raw report (before gate)", A_before), ("delivered (after gate)", A_after)):
        print(f"     {name:26}{pct(a['correct'], a['all_ruled']):>8}"
              f"{pct(int(a['correct'] + 0.5 * a['partial']), a['all_ruled']):>10}"
              f"{pct(a['correct'] + a['partial'], a['all_ruled']):>9}"
              f"{pct(a['correct'], a['ruled']):>11}")
    d = A_after
    print(f"       strict     = correct / all          (partial + wrong count against)")
    print(f"       weighted   = (correct + ½·partial) / all")
    print(f"       lenient    = not-wrong / all         (the ACCURACY reading; partial is 'true but unverifiable')")
    print(f"       excl-part  = correct / (correct+wrong)  <-- GAMEABLE: ignores the middle")
    if d["strict"] is not None and d["strict"] < TARGET:
        print(f"     -> strict bar needs at most {d['wrong_allowed']} non-correct item(s) at this size; "
              f"you have {d['wrong'] + d['partial']}.")
    print(f"     -> the ambiguous middle ('partial') is {pct(d['partial'], d['all_ruled'])} of everything "
          f"delivered. THAT is the gap, and it is what gate 11 exists to close.")

    # ---------------- METRIC B ----------------
    print()
    print(f"  ── METRIC B · FACTUAL CORRECTNESS  (INTERNAL GATE — observations only) ──")
    b = B_asserted
    err = (b["wrong"] / b["all_ruled"]) if b["all_ruled"] else 0.0
    print(f"     asserted tier (grounded findings): {b['n']}  ruled {b['all_ruled']}")
    print(f"     correct / partial / wrong : {b['correct']} / {b['partial']} / {b['wrong']}")
    print(f"     ERROR RATE (wrong / all asserted) : {pct(b['wrong'], b['all_ruled']):>7}   "
          f"target <= {100*TARGET_ERR:.2f}%   {'PASS' if err <= TARGET_ERR else 'FAIL'}")
    print(f"     non-correct (wrong+partial)       : {pct(b['wrong'] + b['partial'], b['all_ruled']):>7}   "
          f"(the strict view of the asserted tier)")
    print(f"     coverage delivered : {pct(len(delivered_idx), len(findings))}  "
          f"(silent drops = {gs['silent_drops']})")

    # ---------------- per category ----------------
    print()
    print(f"  ── METRIC A BY CATEGORY (post-gate, the 'all categories' requirement) ──")
    print(f"     {'category':16}{'n':>4}{'corr':>6}{'part':>6}{'wrong':>7}{'STRICT':>9}{'gap':>8}")
    for c in sorted(by_cat, key=lambda k: -len(by_cat[k])):
        a = agreement(by_cat[c], verdicts)
        s = a["strict"]
        gap = f"{100*(TARGET-s):+.1f}" if s is not None else "—"
        print(f"     {c:16}{a['n']:>4}{a['correct']:>6}{a['partial']:>6}{a['wrong']:>7}"
              f"{pct(a['correct'], a['all_ruled']):>9}{gap:>8}")

    # ---------------- the two together ----------------
    print()
    print(f"  ── BOTH METRICS, ONE LINE ──")
    print(f"     A (writer-agreement, ALL feedback, strict) : {pct(A_after['correct'], A_after['all_ruled'])}"
          f"   target {100*TARGET:.2f}%")
    print(f"     B (factual correctness, asserted tier)     : {pct(b['correct'], b['all_ruled'])}"
          f"   target {100*TARGET:.2f}%")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
