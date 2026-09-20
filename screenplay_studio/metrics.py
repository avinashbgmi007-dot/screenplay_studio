"""Quiet loop instrumentation (IMPROVEMENT_AUDIT 1.3): time-to-reply,
analysis duration, findings-per-fix, and the discussed count — persisted per
project as metrics.json and surfaced quietly in the status bar. This is
telemetry the WRITER can see, stored only on this machine; nothing leaves
the project directory.
"""

import os
import time

# keep only the last N reply timings (the strip shows a rolling average)
MAX_REPLY_SAMPLES = 40


def metrics_path(m) -> str:
    return os.path.join(m.project_dir, "metrics.json")


def load(m) -> dict:
    # Missing -> {} ; damaged -> StoreUnreadable. The A3 atomic write only fixed
    # half the A3 shape: `load` still read a torn file as {} — i.e. the writer's
    # stats silently reset, and the next record_* wrote over the torn file.
    from .jsonio import StoreUnreadable, load_json_store
    data = load_json_store(metrics_path(m), default={})
    if not isinstance(data, dict):
        raise StoreUnreadable(metrics_path(m),
                              f"expected an object, found {type(data).__name__}")
    return data


def _save(m, data: dict) -> None:
    """Atomic (A3, 2026-09-20): this used to be a raw non-atomic write, so a
    crash mid-write left a torn file that `load` then read back as {} — silently
    resetting the writer's stats on the next record_*."""
    from .jsonio import atomic_write_json
    atomic_write_json(metrics_path(m), data)


def _modify(m, apply) -> None:
    """Load-modify-write under the per-path lock: a racing request cannot
    clobber a stat it never saw (jsonio's documented contract)."""
    from .jsonio import lock_for
    with lock_for(metrics_path(m)):
        data = load(m)
        apply(data)
        _save(m, data)


def record_analysis(m, seconds: float) -> None:
    def apply(data):
        data["analysis_seconds"] = round(seconds, 1)
        data["last_analysis_ts"] = time.time()
    _modify(m, apply)


def record_reply(m, seconds: float, quoted: bool = False) -> None:
    def apply(data):
        times = data.setdefault("reply_seconds", [])
        times.append(round(seconds, 2))
        del times[:-MAX_REPLY_SAMPLES]
        if quoted:
            data["discussed"] = data.get("discussed", 0) + 1
    _modify(m, apply)


def record_findings(m, open_count: int, total: int) -> None:
    def apply(data):
        data["findings_open"] = open_count
        data["findings_total"] = total
    _modify(m, apply)


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
