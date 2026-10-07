#!/usr/bin/env python3
"""
observation_rewrite.py — the gate-11 feasibility experiment.

The question this answers
-------------------------
Amendment 9 says "all findings at 98.58 %" requires the analyzer to emit
OBSERVATIONS, not evaluations. But that is a claim about what the model *can*
do, and it has not been tested. This experiment tests it:

  Take each ungrounded finding. Ask the model to (a) restate it as a falsifiable
  OBSERVATION about the text, and (b) ground that observation — a cited line, or
  a search establishing the absence. If the model cannot, say so.

  If the rewrite makes the finding groundable, gate 11 is the fix.
  If it does not, the product must ship two registers and the 98.58 % bar
  attaches to the observation register only.

This is the cheapest experiment that decides the plan. No tracked files.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request

sys.path.insert(0, ".")
from finding_integrity import FindingIntegrityGate  # noqa: E402
from grounding_pass import script_text  # noqa: E402


def ask(server: str, system: str, user: str, timeout: int = 240) -> str:
    body = json.dumps({
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.0, "max_tokens": 800, "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{server.rstrip('/')}/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


SYSTEM = (
    "You convert a screenwriting note into an OBSERVATION. An observation is a "
    "falsifiable claim about what is on the page — something a reader could check "
    "by pointing at the script. An evaluation ('the dialogue is too long') is NOT "
    "an observation; it is an opinion. Your job is to state the observation the "
    "evaluation rests on, then ground it.\n\n"
    "Reply in EXACTLY this format, nothing else:\n"
    "OBSERVATION: <a falsifiable claim about the text — include the measurable, "
    "e.g. word/line count, a scene number, a repeated element, or the absence of a "
    "named thing>\n"
    "EVIDENCE: <the exact line(s) quoted, OR the search performed and what it "
    "established, e.g. 'searched scenes 1-22 for a stated objective: none found'>\n"
    "GROUNDED: yes | no\n"
    "EVALUATION: <the craft judgment this supports, one sentence — labelled as "
    "an interpretation, not a fact>\n"
    "If the note cannot be reduced to a falsifiable observation, set GROUNDED: no "
    "and say why in EVIDENCE."
)

USER_TMPL = (
    "THE NOTE (category: {cat}, severity: {sev}):\n{issue}\n\n"
    "THE SCRIPT:\n{script}\n\n"
    "State the observation this note rests on, and ground it."
)


def parse(txt: str) -> dict:
    def grab(key, nxt):
        m = re.search(rf"{key}:\s*(.+?)(?=\n(?:{nxt}):|\Z)", txt, re.I | re.S)
        return m.group(1).strip() if m else ""
    g = re.search(r"GROUNDED:\s*(yes|no)", txt, re.I)
    return {
        "observation": grab("OBSERVATION", "EVIDENCE"),
        "evidence": grab("EVIDENCE", "GROUNDED"),
        "grounded": bool(g and g.group(1).lower() == "yes"),
        "evaluation": grab("EVALUATION", "ZZZ"),
        "raw": txt,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--label", default="report")
    ap.add_argument("--limit", type=int, default=6)
    args = ap.parse_args()

    report = json.load(open(args.report, encoding="utf-8"))
    parsed = json.load(open(args.parsed, encoding="utf-8"))
    findings = report.get("findings", [])
    verdicts = {int(k): v for k, v in json.load(open(args.verdicts, encoding="utf-8")).items()}

    res = FindingIntegrityGate().run(findings)
    demoted = [d for d in res.decisions if d.action == "demote"]
    full = script_text(parsed, None)

    print(f"\n{'=' * 78}")
    print(f"OBSERVATION REWRITE (gate-11 feasibility) — {args.label}")
    print(f"{'=' * 78}")
    print(f"  {len(demoted)} ungrounded findings; rewriting up to {args.limit}")
    print(f"  baseline: the plain grounding pass grounded 21 % of this set (3/14)")
    print()

    out, ok = [], 0
    for d in demoted[: args.limit]:
        f = d.finding
        sc = f.get("scene_refs") or []
        script = script_text(parsed, sc) if sc else full
        user = USER_TMPL.format(cat=f.get("category"), sev=f.get("severity"),
                                issue=f.get("issue") or "", script=script)
        t0 = time.time()
        try:
            pr = parse(ask(args.server, SYSTEM, user))
        except Exception as exc:
            pr = {"observation": "", "evidence": str(exc), "grounded": False,
                  "evaluation": "", "raw": ""}
        dt = time.time() - t0
        if pr["grounded"]:
            ok += 1
        lab = (verdicts.get(d.orig) or {}).get("label", "?")
        out.append({"index": d.orig, "label": lab, "original": f.get("issue"),
                    "rewrite": pr, "seconds": round(dt, 1)})
        print(f"  [{d.orig:>2}] {'OK ' if pr['grounded'] else '—  '} verdict={lab:8} {dt:5.1f}s")
        print(f"       note  : {(f.get('issue') or '')[:96]}")
        print(f"       obs   : {pr['observation'][:150]}")
        print(f"       evid  : {pr['evidence'][:150]}")
        print()

    n = len(out)
    print(f"  GROUNDED AFTER REWRITE : {ok}/{n}  ({100 * ok // max(n, 1)} %)")
    print(f"  vs baseline plain grounding : 21 %")
    p = args.report.replace("report.findings.json", "_rewrite.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print(f"  written: {p}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
