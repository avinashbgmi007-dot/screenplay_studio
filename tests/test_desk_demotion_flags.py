"""All four demotion flags must reach the desk, not just two of them.

The analyzer has four ways of saying "read this row with care", all under the
same demote-never-drop contract:

* `ungrounded`         — no quote and no checkable observation (apply_evidence_floor)
* `contested`          — its own observation argues against it (demote_contested)
* `summary_only`       — a scene note with no citation (apply_scene_quote_rule)
* `identity_uncertain` — an identity verdict the pages cannot settle (apply_identity_check)

`_fixqueue_items` delivered the first two and dropped the last two. The damage
was not symmetric: `/fixqueue` hides `ungrounded` rows by default, so a
`summary_only` row — usually grounded enough to escape that filter — was the one
on screen with no marker, reading like a cited defect. And `identity_uncertain`
was worse than missing: `app.js` already had `if (item.identity_uncertain)`,
so the `identity?` chip was dead code.

The flags below are set by the analyzer's own guard functions and written by the
production `save_report` path, then served through the real routes — so this
file breaks if a demotion stops recording itself or the row builder stops
delivering it.
"""

import json
import os
import types

import pytest

import screenplay_studio.webapp_server as webapp_server

DEMOTION_FLAGS = ("ungrounded", "contested", "summary_only", "identity_uncertain")


class _Doc:
    title = "Desk Flag Test"
    source_filename = "desk_flags.txt"
    author = None
    source_format = "txt"
    scene_count = 1
    estimated_page_count = 1.0
    parse_confidence = "high"
    all_characters = ["RAJ", "PEN GUY"]
    scenes = [types.SimpleNamespace(
        scene_number=2, heading_raw="INT. FLAT - NIGHT", elements=[], characters_present=["RAJ"]
    )]


def _flagged_findings():
    from screenplay_analyzer import pipeline as P
    from screenplay_analyzer.pipeline import AnalysisResult

    result = AnalysisResult(doc=_Doc())
    result.findings = [
        {"category": "dialogue", "issue": "marker-a on-the-nose line.",
         "severity": "high", "scene_refs": [2], "evidence_quote": None,
         "observation": None, "verification": {"status": "no_quote"}},
        {"category": "character", "issue": "marker-b lacks motivation.",
         "severity": "high", "scene_refs": [2], "evidence_quote": "Who asked you?",
         "observation": "The note claims no motivation; however, the script "
                        "explicitly shows a direct confrontation."},
        {"category": "scene_function", "issue": "marker-c provides a neat resolution.",
         "severity": "medium", "scene_refs": [2], "evidence_quote": None,
         "observation": "The scene resolves in one beat."},
        {"category": "character", "issue": "Raj is not the Pen Guy (marker-d).",
         "severity": "high", "scene_refs": [2], "evidence_quote": "Who asked you?",
         "observation": "Pen Guy is a distinct entity not named Raj."},
        {"category": "structure", "issue": "marker-e act two turns too late.",
         "severity": "medium", "scene_refs": [2], "evidence_quote": "Who asked you?",
         "observation": "The turn happens after the midpoint.",
         "verification": {"status": "verified"}},
    ]
    P.apply_evidence_floor(result)
    P.apply_scene_quote_rule(result.findings)
    P.apply_identity_check(result.findings, _Doc())
    return result


@pytest.fixture
def desk(tmp_path, sample_fountain, monkeypatch):
    from screenplay_analyzer.report import save_report
    from screenplay_parser import parse_screenplay
    from screenplay_studio.manifest import ProjectManifest
    from screenplay_studio.revision import ensure_working

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server.app.config["TESTING"] = True
    m = ProjectManifest.create(str(root / "p1"), sample_fountain)
    m.save()
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    ensure_working(m)
    save_report(_flagged_findings(), str(m.report_md_path), str(m.report_findings_path))
    m.mark_complete("analyze")
    return webapp_server.app.test_client()


def _rows_by_marker(client):
    items = client.get("/api/projects/p1/fixqueue").get_json()["items"]
    return {marker: item for item in items
            for marker in ("marker-a", "marker-b", "marker-c", "marker-d", "marker-e")
            if marker in (item.get("issue") or "")}


class TestAllFourFlagsReachTheDesk:
    def test_every_demotion_flag_survives_the_route(self, desk):
        rows = _rows_by_marker(desk)
        assert len(rows) == 5, f"the queue lost rows: {sorted(rows)}"

        expected = {
            "marker-a": {"ungrounded"},
            "marker-b": {"contested"},
            "marker-c": {"summary_only"},
            "marker-d": {"identity_uncertain"},
            "marker-e": set(),
        }
        for marker, flags in expected.items():
            row = rows[marker]
            for flag in DEMOTION_FLAGS:
                assert flag in row, f"{marker} arrived without `{flag}` on its row"
                assert isinstance(row[flag], bool), (
                    f"{marker}.{flag} is {type(row[flag]).__name__}, not bool")
            got = {f for f in DEMOTION_FLAGS if row[f]}
            assert got == flags, (
                f"{marker} carried {sorted(got)} — the report says {sorted(flags)}")

        # The leak itself: the two flags that escape the ungrounded filter must
        # not be folded into it, or the row would have been hidden anyway.
        assert rows["marker-c"]["summary_only"] and not rows["marker-c"]["ungrounded"]
        assert rows["marker-d"]["identity_uncertain"] and not rows["marker-d"]["ungrounded"]
