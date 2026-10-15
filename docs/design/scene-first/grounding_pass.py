#!/usr/bin/env python3
"""
grounding_pass.py — the second layer of the accuracy contract.

The integrity gate (finding_integrity.py) proves the mechanical errors are
removable, but it also exposes the real gap: on two real scripts, 50-64% of
findings carry NO evidence, so no rule can score them. "All findings at 98.58%"
is unreachable while half the set is ungrounded.

This pass takes the ungrounded findings and tries to GROUND each one:

    positive grounding  — find the line(s) the claim is about, and cite them
    negative grounding  — for an absence claim ("no scene states an objective"),
                          record the search that establishes the absence

Output per finding: grounded (with evidence) | not_grounded (-> stays a question)

Run:  python grounding_pass.py --report ... --parsed ... --server http://127.0.0.1:8080
      [--only-demoted --limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request

sys.path.insert(0, ".")
try:
    from finding_integrity import FindingIntegrityGate, quote, vstatus  # noqa: E402
except Exception:  # pragma: no cover
    from docs.design.scene_first.finding_integrity import (  # type: ignore
        FindingIntegrityGate, quote, vstatus)


# --------------------------------------------------------------- script text
def script_text(parsed: dict, scenes: list[int] | None, max_chars: int = 60000) -> str:
    """Render the script (or the named scenes) as plain text for the model."""
    out = []
    for sc in parsed.get("scenes", []):
        n = sc.get("scene_number")
        if scenes and n not in scenes:
            continue
        out.append(f"--- SCENE {n}: {sc.get('heading_raw', '')} ---")
        for el in sc.get("elements", []):
            t = (el.get("text") or "").strip()
            if not t:
                continue
            typ = el.get("type") or ""
            if typ == "character":
                out.append(f"\n{t.upper()}")
            elif typ == "dialogue":
                out.append(t)
            else:
                out.append(t)
    text = "\n".join(out)
    return text[:max_chars]


# --------------------------------------------------------------- model call
def ask(server: str, system: str, user: str, timeout: int = 180) -> str:
    body = json.dumps({
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.0,
        "max_tokens": 700,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{server.rstrip('/')}/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"].strip()


SYSTEM = (
    "You are a script analyst verifying a claim against a screenplay. You are "
    "adversarial about evidence: you only ground a claim you can point to. "
    "Reply in EXACTLY this format, nothing else:\n"
    "VERDICT: GROUNDED | NOT_GROUNDED\n"
    "EVIDENCE: <the exact line(s) quoted from the script, or, for a claim about "
    "an ABSENCE, the search you performed and what it established, e.g. "
    "'searched all scenes for a stated objective: none found'>\n"
    "WHY: <one sentence: does the evidence actually support the claim?>"
)

USER_TMPL = (
    "CLAIM (category: {cat}, severity: {sev}):\n{issue}\n\n"
    "THE SCRIPT:\n{script}\n\n"
    "Ground this claim: find the exact line(s) that support it, or establish the "
    "absence it asserts. If neither is possible, answer NOT_GROUNDED."
)


def parse_reply(txt: str) -> dict:
    v = re.search(r"VERDICT:\s*(GROUNDED|NOT_GROUNDED)", txt, re.I)
    e = re.search(r"EVIDENCE:\s*(.+?)(?=\nWHY:|\Z)", txt, re.I | re.S)
    w = re.search(r"WHY:\s*(.+)", txt, re.I | re.S)
    return {
        "verdict": (v.group(1).upper() if v else "NOT_GROUNDED"),
        "evidence": (e.group(1).strip() if e else ""),
        "why": (w.group(1).strip() if w else ""),
        "raw": txt,
    }


# --------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--label", default="report")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--all", action="store_true", help="ground every finding, not just demoted")
    args = ap.parse_args()

    report = json.load(open(args.report, encoding="utf-8"))
    parsed = json.load(open(args.parsed, encoding="utf-8"))
    verdicts = {int(k): v for k, v in json.load(open(args.verdicts, encoding="utf-8")).items()}
    findings = report.get("findings", [])

    gate = FindingIntegrityGate()
    res = gate.run(findings)

    if args.all:
        targets = [d for d in res.decisions if d.action != "merge"]
    else:
        targets = [d for d in res.decisions if d.action == "demote"]

    print(f"\n{'=' * 78}")
    print(f"GROUNDING PASS — {args.label}")
    print(f"{'=' * 78}")
    print(f"  gate demoted {len(targets)} ungrounded findings; grounding up to {args.limit}")
    print()

    full_script = script_text(parsed, None)
    grounded = not_grounded = 0
    results = []
    for d in targets[: args.limit]:
        f = d.finding
        sc = f.get("scene_refs") or []
        # absence/global claims need the whole script; scene-scoped ones do not
        script = script_text(parsed, sc) if sc else full_script
        user = USER_TMPL.format(cat=f.get("category"), sev=f.get("severity"),
                                issue=f.get("issue") or "", script=script)
        t0 = time.time()
        try:
            reply = ask(args.server, SYSTEM, user)
            pr = parse_reply(reply)
        except Exception as exc:
            pr = {"verdict": "ERROR", "evidence": "", "why": str(exc), "raw": ""}
        dt = time.time() - t0
        lab = (verdicts.get(d.orig) or {}).get("label", "?")
        if pr["verdict"] == "GROUNDED":
            grounded += 1
        else:
            not_grounded += 1
        results.append({"index": d.orig, "label": lab, "issue": f.get("issue"),
                        "grounding": pr, "seconds": round(dt, 1)})
        mark = "OK " if pr["verdict"] == "GROUNDED" else "—  "
        print(f"  [{d.orig:>2}] {mark} verdict={lab:8} {dt:5.1f}s  {(f.get('issue') or '')[:58]}")
        print(f"       -> {pr['verdict']}: {pr['evidence'][:150]}")
        print(f"       why: {pr['why'][:150]}")

    n = len(results)
    print()
    print(f"  GROUNDED     : {grounded}/{n}  ({100 * grounded // max(n, 1)}% of the ungrounded set)")
    print(f"  NOT GROUNDED : {not_grounded}/{n}  -> stay questions")
    # of the grounded, how many were 'partial' (were they the real, just-uncited ones?)
    g_partial = sum(1 for r in results if r["grounding"]["verdict"] == "GROUNDED" and r["label"] == "partial")
    print(f"  of the grounded, previously 'partial' : {g_partial}")
    out = args.report.replace("report.findings.json", "_grounding.json")
    json.dump(results, open(out, "w", encoding="utf-8"), indent=1)
    print(f"  written: {out}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
