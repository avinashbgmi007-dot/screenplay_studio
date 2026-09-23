"""`pass_history.json` — every completed analysis, one entry each.

Spec §15.4: the arrival strip remembers ONE generation back (`last_pass.json`),
which is enough for "what changed since yesterday" and useless for the question
a writer actually asks after five rewrites: *is this converging?* This store
keeps the numbers the analyze path already computes — totals, still-open,
addressed, which categories failed — so the desk can draw the whole arc.

Append-only, boring, and locked like every other store here: the append is a
load-modify-write, so `lock_for` is held across the READ, not just the write.
Without that the CLI and the webapp appending in the same second each load the
pre-append list and rename over each other's file, and an entry vanishes from
the one record whose whole job is to never lose one.
"""
from __future__ import annotations

import os
import time


def path(m) -> str:
    return os.path.join(m.project_dir, "pass_history.json")


def load_passes(m) -> list[dict]:
    """Oldest first — which is file order, not a sort: an append can only happen
    under the store lock and it lands at the end of the list, so the file IS the
    chronology. (`ts` is when each pass was measured, so two passes in the same
    clock tick can tie; a sort would shuffle ties.)

    Missing store -> [] ; damaged store -> StoreUnreadable. Reading damage as
    "no history yet" is the destructive option: the next append would write a
    one-entry list over the writer's only copy of the arc.
    """
    from .jsonio import StoreUnreadable, load_json_store
    p = path(m)
    data = load_json_store(p, default=[])
    if not isinstance(data, list):
        raise StoreUnreadable(p, f"expected a list, found {type(data).__name__}")
    return [e for e in data if isinstance(e, dict) and "open" in e]


def append_pass(m, statuses, failed_categories=None) -> dict:
    """Record one analysis. `statuses` is the `revision.finding_statuses`
    payload, so `open` means what the ledger says it means (still present +
    not-yet-verifiable) and this module never invents a second counter.
    """
    summary = (statuses or {}).get("summary") or {}
    addressed = int(summary.get("addressed") or 0)
    open_count = int(summary.get("still_present") or 0) + int(summary.get("unknown") or 0)
    entry = {
        "ts": time.time(),
        "total": addressed + open_count,
        "open": open_count,
        "addressed": addressed,
        "failed_categories": list(failed_categories or []),
    }
    from .jsonio import atomic_write_json, lock_for
    p = path(m)
    os.makedirs(m.project_dir, exist_ok=True)
    with lock_for(p):
        passes = load_passes(m)
        passes.append(entry)  # chronological: the arc reads left to right
        atomic_write_json(p, passes)
    return entry
