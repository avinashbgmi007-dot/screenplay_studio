"""Quiet loop instrumentation (IMPROVEMENT_AUDIT 1.3): time-to-reply,
analysis duration, findings-per-fix, and the discussed count — persisted per
project as metrics.json and surfaced quietly in the status bar. This is
telemetry the WRITER can see, stored only on this machine; nothing leaves
the project directory.
"""

import json
import os
import time

# keep only the last N reply timings (the strip shows a rolling average)
MAX_REPLY_SAMPLES = 40


def metrics_path(m) -> str:
    return os.path.join(m.project_dir, "metrics.json")


def load(m) -> dict:
    try:
        with open(metrics_path(m), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(m, data: dict) -> None:
    with open(metrics_path(m), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_analysis(m, seconds: float) -> None:
    data = load(m)
    data["analysis_seconds"] = round(seconds, 1)
    data["last_analysis_ts"] = time.time()
    _save(m, data)


def record_reply(m, seconds: float, quoted: bool = False) -> None:
    data = load(m)
    times = data.setdefault("reply_seconds", [])
    times.append(round(seconds, 2))
    del times[:-MAX_REPLY_SAMPLES]
    if quoted:
        data["discussed"] = data.get("discussed", 0) + 1
    _save(m, data)


def record_findings(m, open_count: int, total: int) -> None:
    data = load(m)
    data["findings_open"] = open_count
    data["findings_total"] = total
    _save(m, data)


def summarize(m) -> dict:
    """The compact view the status strip reads: rolling averages + counts."""
    data = load(m)
    times = data.get("reply_seconds", [])
    out = {
        "analysis_seconds": data.get("analysis_seconds"),
        "avg_reply_seconds": round(sum(times) / len(times), 1) if times else None,
        "discussed": data.get("discussed", 0),
        "findings_open": data.get("findings_open"),
        "findings_total": data.get("findings_total"),
    }
    # findings-per-fix: how much of the last report is already resolved
    if out["findings_open"] is not None and out["findings_total"]:
        out["findings_fixed"] = out["findings_total"] - out["findings_open"]
        out["findings_fixed_pct"] = round(100 * out["findings_fixed"] / out["findings_total"])
    return out
