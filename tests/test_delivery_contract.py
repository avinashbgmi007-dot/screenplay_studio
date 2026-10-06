"""Gate 8 — the delivery contract: no report field is silently undelivered.

Law D says craft attribution is the product. A route that drops `rule_id` makes
the product unreadable *through that route*, and `/findings` dropped it — along
with `check_id`, `evidence_source` and `merged_rule_ids` — while the client
already carried renderers for two of them (`ruleChip`, `finding-check`). The
fields existed, the renderers existed, and the wire between them did not.

This file is the enforcement. It is VALUE-BASED on purpose: it takes a finding
carrying every field the *documented* schema emits, serves it through
`/findings`, and compares the keys that arrive against the keys that left. The
expected field set is read from `docs/DATA_FORMATS.md` rather than copied here,
so a new report field cannot ship without a delivery decision — the guard bites
in the direction that matters (a field on the report, missing from the wire).

`_fixqueue_items` is the shared builder behind both `/findings` and `/fixqueue`,
so a green `/findings` covers both routes.
"""
import json
import os
import re
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from screenplay_studio.manifest import ProjectManifest  # noqa: E402

_DOC = os.path.join(_ROOT, "docs", "DATA_FORMATS.md")


def documented_finding_fields() -> set:
    """The report finding keys `docs/DATA_FORMATS.md` declares.

    Read from the doc, not copied, because the whole point is to fail when the
    schema grows and the wire does not. Top-level finding keys sit at six spaces
    of indentation inside the `"findings": [` block; the nested objects
    (`verification`) sit deeper and are excluded.
    """
    text = open(_DOC, encoding="utf-8").read()
    block = text.split('"findings": [', 1)[1].split('\n  "setup_payoff"', 1)[0]
    return set(re.findall(r'^      "([a-z_]+)":', block, re.M))


def _full_finding() -> dict:
    """One finding carrying EVERY documented field, so the guard has something
    to compare against. Values are arbitrary; only the keys matter."""
    return {
        "category": "dialogue",
        "issue": "MARA states the subtext aloud instead of dramatizing it.",
        "why_it_matters": "Says the feeling rather than showing it.",
        "severity": "low",
        "scene_refs": [1],
        "evidence_quote": "I'll tell you everything when this is over.",
        "observation": "MARA announces the revelation aloud in scene 1.",
        "rule_id": "rule_on_the_nose",
        "check_id": None,
        "evidence_source": "pages",
        "merged_rule_ids": ["rule_x"],
        "merged_findings": [{"category": "dialogue", "issue": "absorbed", "severity": "medium",
                             "scene_refs": [1], "rule_id": "rule_y"}],
        "scene_key": "INT STUDY NIGHT#1",
        "verification": {"status": "verified", "matched_scene": 1,
                         "confidence": 0.95, "note": None},
    }


@pytest.fixture
def served(tmp_path, sample_fountain, monkeypatch):
    """A project the Flask test client can reach, whose report carries every
    documented finding field."""
    import screenplay_studio.webapp_server as webapp_server
    from screenplay_parser import parse_screenplay
    from screenplay_studio.revision import ensure_working

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server.app.config["TESTING"] = True
    m = ProjectManifest.create(str(root / "p1"), sample_fountain)
    m.save()
    # the row builder reads the parsed script (for scene headings/acts), so the
    # project must be parsed, not merely have a report file
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    ensure_working(m)
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        json.dump({"findings": [_full_finding()]}, f)
    m.mark_complete("analyze")
    return webapp_server.app.test_client(), m


# ---------- the guard ----------

def test_every_documented_finding_field_reaches_the_findings_row(served):
    """The load-bearing check: what the report carries, the row must deliver."""
    client, _m = served
    r = client.get("/api/projects/p1/findings")
    assert r.status_code == 200, r.data
    row = r.json["items"][0]
    missing = documented_finding_fields() - set(row)
    assert not missing, (
        f"/findings drops documented report field(s) {sorted(missing)}. Deliver "
        "them on the row, or record the omission as a deliberate internal field "
        "with a reason — Law D: craft attribution is the product.")


def test_the_documented_set_is_what_we_think_it_is():
    """A canary on the doc parse itself. If DATA_FORMATS.md's findings block is
    reshaped, the guard above could silently start comparing an empty set and
    pass forever — this fails loudly instead."""
    fields = documented_finding_fields()
    assert {"category", "issue", "severity", "rule_id", "check_id",
            "evidence_source", "merged_rule_ids", "observation",
            "scene_key", "verification"} <= fields, (
        f"the doc parse found {sorted(fields)} — the findings block was reshaped")


def test_the_guard_bites_when_a_field_is_dropped(served):
    """Falsifiability. A guard that cannot fail is decoration: prove it reports
    a dropped field by removing one from a real row."""
    import screenplay_studio.webapp_server as webapp_server

    _client, m = served
    items, _acts = webapp_server._fixqueue_items(m)
    row = items[0]
    assert "rule_id" in row, "the row no longer carries rule_id at all"
    row.pop("rule_id")
    assert documented_finding_fields() - set(row) == {"rule_id"}
