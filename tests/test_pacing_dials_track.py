"""Tests for the pacing pass, character dials pass, and the character-track
route (the clickable per-character layer)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_parser.knowledge_graph import build_knowledge_graph
from screenplay_analyzer.pacing import per_scene_pace, drag_findings, DRAG_THRESHOLD
from screenplay_analyzer.dials import run_character_dials
from screenplay_analyzer.grammar import character_dials_grammar


SAMPLE = """Title: Track Test
Author: T

INT. ROOM - NIGHT

MARA holds a small CIGAR, turning it over.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. HALL - DAY

The CIGAR sits on the table, untouched.

MARA
(scared)
The debt is coming.
"""


def _parse(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


class FakeClient:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def chat_json(self, system, user, grammar=None, **kw):
        self.calls.append((system, user))
        return self._data


# ---------- pacing (deterministic) ----------

def test_pace_index_reports_all_scenes():
    doc = _parse(SAMPLE)
    rows = per_scene_pace(doc)
    assert rows, "pacing must produce a row per scene"
    assert all(0 <= r["pace_score"] <= 100 for r in rows)
    for r in rows:
        assert r["scene_number"] >= 1
        assert r["words"] > 0
        assert r["action_share"] >= 0 and r["action_share"] <= 1


def test_pace_drag_flagging_never_exceeds_cap():
    # A long, dialogue-heavy scene should rank as a drag; the cap holds.
    text = "Title: Drag Test\nAuthor: T\n\n"
    for s in range(1, 12):
        text += f"INT. ROOM {s} - NIGHT\n\n"
        text += "MARA walks slowly across the room and sits down.\n\n" * 4
        text += "MARA\nI keep talking and talking and talking.\n\n" * 6
    doc = _parse(text)
    rows = per_scene_pace(doc)
    assert sum(1 for r in rows if r["drag"]) <= 4
    for r in rows:
        if r["drag"]:
            assert r["pace_score"] >= DRAG_THRESHOLD


def test_drag_findings_are_structured():
    doc = _parse(SAMPLE)
    rows = per_scene_pace(doc)
    findings = drag_findings(rows)
    for f in findings:
        assert f["category"] == "structure"
        assert f["rule_id"] == "pacing_drag"
        assert f["severity"] == "medium"
        assert isinstance(f["scene_refs"], list) and f["scene_refs"]


# ---------- character dials (model pass) ----------

def test_dials_parse_scores_and_refs():
    client = FakeClient({"dials": [
        {"character": "MARA", "traits": [
            {"trait": "proactive", "score": 8, "scene_refs": [1, 2], "note": "Drives the plan."},
        ]},
    ]})
    out = run_character_dials(None, "MARA drives the story.", client, ["MARA", "RAVI"], language="eng")
    assert len(out) == 1
    d = out[0]
    assert d["character"] == "MARA"
    assert d["traits"][0]["score"] == 8
    assert d["traits"][0]["scene_refs"] == [1, 2]


def test_dials_clamp_scores_and_skip_bad_rows():
    client = FakeClient({"dials": [
        {"character": "MARA", "traits": [
            {"trait": "proactive", "score": 99, "scene_refs": [1], "note": ""},
            {"trait": "", "score": 3, "scene_refs": [], "note": ""},
        ]},
        {"character": "", "traits": []},
    ]})
    out = run_character_dials(None, "overview", client, ["MARA"], language="eng")
    assert len(out) == 1
    assert out[0]["traits"][0]["score"] == 10  # clamped


def test_dials_respect_cast_cap():
    cast = [f"CHAR{i}" for i in range(20)]
    client = FakeClient({"dials": []})
    run_character_dials(None, "overview", client, cast, language="eng")
    # The prompt names at most MAX_DIAL_CHARACTERS characters
    from screenplay_analyzer.dials import MAX_DIAL_CHARACTERS
    last_user = client.calls[-1][1]
    assert last_user.count("CHAR") <= MAX_DIAL_CHARACTERS


def test_dials_grammar_renders():
    g = character_dials_grammar()
    assert "dials" in g and "score" in g


def test_report_json_carries_pacing_and_dials(tmp_path):
    # Regression: to_findings_json must serialize the new surfaces — the
    # webapp renders pacing/dials from report.findings.json, so a drop here
    # means the charts silently vanish.
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer.report import to_findings_json

    doc = _parse(SAMPLE)
    result = AnalysisResult(doc=doc)
    result.pacing = per_scene_pace(doc)
    result.character_dials = [{"character": "MARA", "traits": [{"trait": "warm", "score": 6, "scene_refs": [1], "note": ""}]}]
    j = to_findings_json(result)
    assert j["pacing"] and j["pacing"][0]["scene_number"] >= 1
    assert j["character_dials"] and j["character_dials"][0]["character"] == "MARA"


# ---------- character track (route assembly) ----------

def test_character_track_assembles_from_kg_and_report(tmp_path):
    from screenplay_studio.character_track import build_character_tracks

    doc = _parse(SAMPLE)
    kg_path = tmp_path / "parsed.kg.json"
    kg = build_knowledge_graph(doc)
    kg.save(str(kg_path))

    report = {
        "character_dials": [
            {"character": "MARA", "traits": [{"trait": "proactive", "score": 8, "scene_refs": [1], "note": "Drives."}]},
        ],
        "character_reads": [
            {"character": "MARA", "how_reads": "Resolute and guarded.", "apparent_intent": "Get answers.", "gap": "Minimal."},
        ],
    }
    tracks = build_character_tracks(str(kg_path), report)
    assert tracks, "a parsed script must yield tracks"
    mara = next(t for t in tracks if t["name"] == "MARA")
    assert mara["scene_count"] >= 1
    assert mara["dialogue_lines"] >= 1
    assert mara["dials"], "dials from the report must ride in"
    assert mara["reads"]["how_reads"] == "Resolute and guarded."
    # ranked by importance: main first
    assert tracks[0]["importance"] in ("main", "supporting", "bit")


def test_character_track_ranks_main_first_and_tolerates_missing_report(tmp_path):
    from screenplay_studio.character_track import build_character_tracks

    doc = _parse(SAMPLE)
    kg_path = tmp_path / "parsed.kg.json"
    build_knowledge_graph(doc).save(str(kg_path))

    tracks = build_character_tracks(str(kg_path), None)
    assert tracks
    # no report => no dials, no reads, but presence/interactions still there
    for t in tracks:
        assert "dials" in t and "reads" in t and "interactions" in t


def test_character_track_tolerates_missing_kg(tmp_path):
    from screenplay_studio.character_track import build_character_tracks
    assert build_character_tracks(str(tmp_path / "nope.json"), None) == []


@pytest.fixture
def http_client(tmp_path, sample_fountain):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "proj")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = "http://localhost:8196"
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    from screenplay_studio.manifest import ProjectManifest
    m = ProjectManifest.create(os.path.join(webapp_server.PROJECTS_DIR, "p1"), sample_fountain)
    m.save()
    return webapp_server.app.test_client()


def test_characters_route(http_client, tmp_path):
    resp = http_client.get("/api/projects/p1/characters")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "characters" in data
