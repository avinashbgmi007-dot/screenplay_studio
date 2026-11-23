"""Human-reviewed scorecard for one or more runs on a short screenplay.

This is evaluation tooling, not a CI quality gate. It keeps three different
questions separate: could the quote be located, does the evidence support the
claim, and is the note true about the writer's script? It also reports the
analyzer's own quote-verification statuses separately from human location
judgments. A located quote is never counted as proof of claim support.

Usage:
  python tests/eval_short_script.py eval-manifest.json

Manifest example:
  {"script_id":"short-a","page_count":12.5,"runs":[
    {"run_id":"baseline-1","report":"r1/report.findings.json","judgments":"r1/judgments.json"},
    {"run_id":"baseline-2","report":"r2/report.findings.json","judgments":"r2/judgments.json"}]}

Each judgments JSON contains a `judgments` array. `finding_index` is the
1-based position in that run's `findings` array. `reviewer_role` is `writer`
or `independent`. Labels are `truth` (correct / partial / wrong),
`quote_location` (located_in_cited_scene / wrong_scene / not_found /
not_applicable / unclear), and `claim_support` (supports /
partially_supports / does_not_support / unclear). Missing labels remain
unjudged. `unclear` is reported but excluded from the corresponding decisive
denominator. Reports at 30 pages or longer are refused; this scorecard does
not validate feature-length behavior. No writer outcomes are inferred or
fabricated by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MAX_SHORT_SCRIPT_PAGES = 30.0
TRUTH_LABELS = frozenset({"correct", "partial", "wrong"})
QUOTE_LOCATION_LABELS = frozenset({
    "located_in_cited_scene", "wrong_scene", "not_found", "not_applicable", "unclear",
})
CLAIM_SUPPORT_LABELS = frozenset({
    "supports", "partially_supports", "does_not_support", "unclear",
})
REVIEWER_ROLES = frozenset({"writer", "independent"})
MACHINE_VERIFICATION_STATUSES = frozenset({
    "verified", "not_found", "no_quote", "scene_not_found",
})


def _rate(numerator: int, denominator: int) -> float | None:
    return round(100.0 * numerator / denominator, 1) if denominator else None


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(value or "").lower())).strip()


def _finding_signature(finding: dict[str, Any]) -> str:
    """Stable cross-run key, preferring the product ID and otherwise lexical.

    The fallback intentionally measures text-and-scene churn, not semantic
    identity. Wording changes can count as churn; reviewers should interpret
    it as a repeatability signal, not as a correctness score.
    """
    for key in ("finding_id", "id"):
        value = finding.get(key)
        if value is not None and str(value).strip():
            return f"id:{str(value).strip()}"
    refs = finding.get("scene_refs") or []
    canonical = "|".join((
        str(finding.get("category") or "").strip().lower(),
        ",".join(str(x) for x in sorted(refs, key=str)),
        _norm(finding.get("issue")),
    ))
    return "text:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _load_json(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _counter(labels: list[str], allowed: frozenset[str]) -> dict[str, int]:
    counts = Counter(label for label in labels if label in allowed)
    return {label: counts.get(label, 0) for label in sorted(allowed)}


def _review_metrics(findings: list[dict[str, Any]], judgments: list[dict[str, Any]], role: str) -> dict[str, Any]:
    rows = [row for row in judgments if row.get("reviewer_role") == role]
    truth_counts = _counter([str(row.get("truth") or "") for row in rows], TRUTH_LABELS)
    truth_n = sum(truth_counts.values())
    support_counts = _counter([str(row.get("claim_support") or "") for row in rows], CLAIM_SUPPORT_LABELS)
    support_n = sum(support_counts[x] for x in ("supports", "partially_supports", "does_not_support"))
    location_counts = _counter([str(row.get("quote_location") or "") for row in rows], QUOTE_LOCATION_LABELS)
    location_n = sum(location_counts[x] for x in ("located_in_cited_scene", "wrong_scene", "not_found"))
    unsupported_high = sum(
        1 for row in rows
        if row.get("claim_support") == "does_not_support"
        and str(findings[row["finding_index"] - 1].get("severity") or "").lower() == "high"
    )
    judged_indexes = {
        row["finding_index"] for row in rows
        if any(row.get(field) is not None
               for field in ("truth", "claim_support", "quote_location"))
    }
    return {
        "findings_with_any_judgment": len(judged_indexes),
        "findings_without_any_judgment": max(0, len(findings) - len(judged_indexes)),
        "truth": {
            "counts": truth_counts,
            "judged": truth_n,
            "not_wrong_rate_pct": _rate(truth_counts["correct"] + truth_counts["partial"], truth_n),
            "strict_correct_rate_pct": _rate(truth_counts["correct"], truth_n),
        },
        "claim_support": {
            "counts": support_counts,
            "rated_excluding_unclear": support_n,
            "strict_support_rate_pct": _rate(support_counts["supports"], support_n),
            "support_or_partial_rate_pct": _rate(
                support_counts["supports"] + support_counts["partially_supports"], support_n),
        },
        "quote_location": {
            "counts": location_counts,
            "rated_excluding_unclear_and_not_applicable": location_n,
            "located_in_cited_scene_rate_pct": _rate(
                location_counts["located_in_cited_scene"], location_n),
        },
        "high_severity_claims_judged_not_supported": unsupported_high,
    }


def evaluate_run(run_id: str, report: dict[str, Any], annotation: dict[str, Any]) -> dict[str, Any]:
    findings = report.get("findings")
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        raise ValueError(f"run {run_id}: report.findings must be a list of objects")
    judgments = annotation.get("judgments")
    if not isinstance(judgments, list) or not all(isinstance(row, dict) for row in judgments):
        raise ValueError(f"run {run_id}: judgments must be a list of objects")

    seen: set[tuple[int, str]] = set()
    for row in judgments:
        index = row.get("finding_index")
        role = row.get("reviewer_role")
        if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= len(findings):
            raise ValueError(f"run {run_id}: finding_index must be 1..{len(findings)}")
        if not isinstance(role, str) or role not in REVIEWER_ROLES:
            raise ValueError(f"run {run_id}: reviewer_role must be one of {sorted(REVIEWER_ROLES)}")
        pair = (index, role)
        if pair in seen:
            raise ValueError(f"run {run_id}: duplicate judgment for finding {index} by {role}")
        seen.add(pair)
        for field, allowed in (("truth", TRUTH_LABELS),
                               ("quote_location", QUOTE_LOCATION_LABELS),
                               ("claim_support", CLAIM_SUPPORT_LABELS)):
            value = row.get(field)
            if value is not None and (not isinstance(value, str) or value not in allowed):
                raise ValueError(f"run {run_id}: invalid {field} label {value!r}")

    machine_statuses = []
    for finding in findings:
        verification = finding.get("verification")
        status = verification.get("status") if isinstance(verification, dict) else None
        machine_statuses.append(
            status if isinstance(status, str) and status in MACHINE_VERIFICATION_STATUSES
            else "unknown"
        )
    machine_counts = Counter(machine_statuses)
    keys = [_finding_signature(finding) for finding in findings]
    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    runtime = stats.get("runtime_minutes")
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or not math.isfinite(runtime):
        runtime = None
    recoveries = report.get("recoveries") or []
    errors = report.get("errors") or []

    return {
        "run_id": run_id,
        "model_used": report.get("model_used"),
        "findings": len(findings),
        "runtime_minutes": runtime,
        "recovery_notes": len(recoveries) if isinstance(recoveries, list) else None,
        "errors": len(errors) if isinstance(errors, list) else None,
        "machine_quote_verification_statuses": {
            label: machine_counts.get(label, 0)
            for label in sorted(MACHINE_VERIFICATION_STATUSES | {"unknown"})
        },
        "reviewers": {
            role: _review_metrics(findings, judgments, role)
            for role in sorted(REVIEWER_ROLES)
        },
        "_finding_keys": keys,
    }


def _churn(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    # Multisets preserve repeated findings instead of collapsing duplicate rows.
    from collections import Counter
    before = Counter(previous["_finding_keys"])
    after = Counter(current["_finding_keys"])
    added = sum((after - before).values())
    removed = sum((before - after).values())
    union = sum((before | after).values())
    return {
        "from_run": previous["run_id"],
        "to_run": current["run_id"],
        "findings_added": added,
        "findings_missing_from_next_run": removed,
        "text_and_scene_churn_pct": round(100.0 * (added + removed) / union, 1) if union else 0.0,
    }


def evaluate_manifest(manifest: dict[str, Any], base_dir: str | Path = ".") -> dict[str, Any]:
    script_id = str(manifest.get("script_id") or "").strip()
    pages = manifest.get("page_count")
    if not script_id:
        raise ValueError("manifest.script_id is required")
    if isinstance(pages, bool) or not isinstance(pages, (int, float)) or not math.isfinite(pages):
        raise ValueError("manifest.page_count must be a finite number")
    if pages <= 0 or pages >= MAX_SHORT_SCRIPT_PAGES:
        raise ValueError(f"page_count must be greater than 0 and under {MAX_SHORT_SCRIPT_PAGES:g}")
    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("manifest.runs must contain at least one run")

    base = Path(base_dir)
    results = []
    seen_run_ids: set[str] = set()
    for entry in runs:
        if not isinstance(entry, dict):
            raise ValueError("each manifest.runs entry must be an object")
        run_id = str(entry.get("run_id") or "").strip()
        report_path = entry.get("report")
        judgment_path = entry.get("judgments")
        if not run_id or not isinstance(report_path, str) or not isinstance(judgment_path, str):
            raise ValueError("each run needs run_id, report, and judgments paths")
        if run_id in seen_run_ids:
            raise ValueError(f"duplicate run_id: {run_id}")
        seen_run_ids.add(run_id)
        results.append(evaluate_run(
            run_id,
            _load_json(base / report_path),
            _load_json(base / judgment_path),
        ))

    public_runs = [{k: v for k, v in run.items() if not k.startswith("_")} for run in results]
    return {
        "scope": "short screenplay under 30 pages; not a feature-length claim",
        "script_id": script_id,
        "page_count": pages,
        "runs": public_runs,
        "run_to_run_churn": [_churn(a, b) for a, b in zip(results, results[1:])],
        "interpretation": {
            "quote_verification": "machine status only; it measures quote location, not claim support",
            "claim_support": "reviewer judgment; reported separately from truth and quote location",
            "truth": "writer judgments; partial counts in not-wrong but not strict correctness",
            "churn": "text-and-scene identity comparison; wording changes can count as churn",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="JSON manifest listing short-script runs and judgments")
    args = parser.parse_args(argv)
    try:
        manifest_path = Path(args.manifest)
        result = evaluate_manifest(_load_json(manifest_path), manifest_path.parent)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"evaluation input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
