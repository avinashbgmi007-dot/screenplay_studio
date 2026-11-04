"""Staged, validated report generations — one reading, published by one pointer.

Gap 3 measured: a run that produced NO usable output still overwrote the previous
good report (Markdown and findings both), so the writer's last reading was gone
and `/report` answered 400. Gap 4 measured the neighbouring failure: a run that
read one draft, while another draft became active, still published — its findings
appeared in the completed report of a draft it never saw.

Both are the same shape: **the report was written straight onto the live paths as
it was produced.** There was no moment at which "this reading is complete and it
is about this script" was decided, so there was nothing to refuse and nothing to
roll back to.

This module gives that moment a name:

* a run **stages** its whole artifact set into `report.generations/<id>/` —
  Markdown, findings, the exact document it read, and a manifest naming the
  digest and the run;
* **publication** is `publish_generation`, which re-reads the live draft, refuses
  if the digest moved, and only then copies the three live files into place and
  writes the pointer.

A failure before publication leaves the previous generation live and readable.
The staged directory is left behind (it is small, and a failed run's output is
evidence), so "what did the attempt produce" is answerable afterwards.
"""
from __future__ import annotations

import os
import shutil
import time

from .jsonio import atomic_write_json


def _stamp(man) -> dict:
    return {
        "digest": man.get("digest"),
        "title": man.get("title"),
        "scene_count": man.get("scene_count"),
        "run_at": man.get("run_at"),
    }


def new_generation_dir(m, digest: str, doc=None) -> str:
    """A fresh directory for this run's output, tagged with the digest it read.

    Named by time AND digest so two runs on the same script cannot collide, and
    so a directory can be traced back to a document without opening it. Never
    reuses an existing directory: a leftover from an earlier attempt is not this
    attempt's output and must not be published by accident.
    """
    root = m.report_generations_dir
    os.makedirs(root, exist_ok=True)
    safe = (digest or "unknown").replace(":", "-")
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{safe}-{os.getpid()}"
    path = os.path.join(root, name)
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(root, f"{name}-{n}")
    os.makedirs(path, exist_ok=True)
    return path


def stage_generation(result, gen_dir: str, m, digest: str, doc) -> dict:
    """Write this reading into `gen_dir` and return its manifest.

    Order matters: the artifacts are written first and the manifest LAST, so a
    manifest on disk means everything it names is already there. An interrupted
    run therefore leaves a directory with no manifest — visibly incomplete rather
    than a generation that claims to be whole.
    """
    from screenplay_analyzer.report import save_report

    md_path = os.path.join(gen_dir, "report.md")
    findings_path = os.path.join(gen_dir, "report.findings.json")
    snapshot_path = os.path.join(gen_dir, "report.snapshot.json")

    save_report(result, md_path, findings_path)

    # The report has to name the script it read, in the artifact itself: a
    # reader with only the file cannot otherwise check it against the draft on
    # screen, and the manifest is a separate document that could be copied away
    # from the pair it describes.
    import json
    with open(findings_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    stamp = {"digest": digest, "title": getattr(doc, "title", None),
             "scene_count": getattr(doc, "scene_count", None)}
    payload["snapshot"] = stamp
    atomic_write_json(findings_path, payload)

    # The exact document this reading is about, saved beside it (gaps 3/4).
    doc.save(snapshot_path)

    man = {
        **stamp,
        "run_at": time.time(),
        "markdown": "report.md",
        "findings": "report.findings.json",
        "snapshot": "report.snapshot.json",
        "model_used": getattr(result, "model_used", None),
    }
    atomic_write_json(os.path.join(gen_dir, "generation.json"), man)
    return man


def load_manifest(gen_dir: str) -> dict | None:
    """The generation's manifest, or None when the directory is not a complete
    generation. Damage raises: an unreadable manifest is not "no reading here"
    (the same distinction every other store in this package keeps)."""
    import json
    path = os.path.join(gen_dir, "generation.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f"the staged reading at {os.path.basename(gen_dir)} is "
                         f"unreadable ({e})") from e
    return data if isinstance(data, dict) else None


def publish_generation(m, gen_dir: str) -> dict:
    """Make a staged generation the live report — the one publication step.

    Compare-and-publish FIRST (gap 4): the live draft is re-read here, at the
    moment of publication, and the swap is refused if it no longer hashes to the
    digest this run read. A run that outlived its draft must not write its
    findings over a reading of a different script.

    Then the three live files are written and the pointer last. The pointer is
    what readers follow, so a crash between the file writes leaves the previous
    pointer in place — the desk keeps a whole reading, old or new, never a mix.
    """
    from screenplay_analyzer.report import document_digest

    man = load_manifest(gen_dir)
    if man is None:
        raise ValueError(f"no complete reading to publish at {os.path.basename(gen_dir)}")

    try:
        from .revision import load_working
        live_digest = document_digest(load_working(m))
    except Exception:                                        # noqa: BLE001
        live_digest = None
    if live_digest is not None and man.get("digest") != live_digest:
        raise ValueError(
            "the draft changed while this analysis was running, so its findings "
            "were not published — they describe a script that is no longer on "
            "screen. Run the analysis again.")

    for live, rel in ((m.report_md_path, man["markdown"]),
                      (m.report_findings_path, man["findings"]),
                      (m.report_snapshot_path, man["snapshot"])):
        src = os.path.join(gen_dir, rel)
        if os.path.exists(src):
            shutil.copy2(src, live)

    atomic_write_json(m.report_pointer_path, {
        "generation": os.path.basename(gen_dir),
        **_stamp(man),
        "published_at": time.time(),
    })
    return man


def current_generation(m) -> dict | None:
    """What is published right now, per the pointer, or None before any run."""
    import json
    path = m.report_pointer_path
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f"the published-reading pointer is unreadable ({e})") from e
