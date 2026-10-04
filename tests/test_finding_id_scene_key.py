"""The scene key in a finding's id, and what the upgrade does to stored marks.

HIGH-1 (NOTES.md "D1 + D2-a"): content alone was not a unique key. On
Pain_3 the demo dialogue finding repeats its issue at nine scenes, so 9 of 16
findings hashed to ONE id — one press of ✓ counted nine findings addressed, and
nine rows left the worklist together. The tie-breaker is the finding's scene,
named by its slugline (screenplay_parser/scenekey.py).

What this file pins, in the order the risk matters:

1. COMPATIBILITY — a finding with no scene key hashes to exactly the id the
   pre-scene-key build produced. If this breaks, every stored mark on a
   script-level finding silently stops matching, which is worse than the
   collision it fixes.
2. THE COLLISION ITSELF — nine same-words findings at nine scenes get nine ids;
   the same heading twice gets two, via the occurrence suffix.
3. THE SLUG — the normalisation that decides whether an id moves when the
   writer edits a heading (punctuation/case do not move it; words do).
4. THE MIGRATION POLICY — one stored id, one finding: carried (lossless). One
   stored id, several findings: held aside in finding_marks.ambiguous.json and
   NOT applied, because spreading one mark across nine findings is the exact
   overclaim the mark store exists to prevent. Idempotent, and a damaged store
   is never overwritten.
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from screenplay_parser.models import Scene, ScriptDocument  # noqa: E402
from screenplay_parser.scenekey import heading_slug, scene_key_map  # noqa: E402
from screenplay_studio.revision import (ambiguous_marks, compute_finding_id,  # noqa: E402
                                        finding_intents, legacy_id_candidates)

DEMO_ISSUE = "[demo] Sample dialogue finding — the built-in demo model is running, not a real analysis."


def _doc(*headings):
    return ScriptDocument(
        title="t", author=None, source_format="txt", source_filename="t.txt",
        scenes=[Scene(scene_number=i + 1, heading_raw=h) for i, h in enumerate(headings)],
    )


def _finding(scene, issue=DEMO_ISSUE, keys=None, with_key=True):
    f = {"category": "dialogue", "issue": issue, "severity": "low",
         "evidence_quote": None, "scene_refs": [scene]}
    if with_key:
        f["scene_key"] = (scene_key_map(keys) if keys is not None else {}).get(scene, "")
    return f


# ---------- 1. compatibility: no scene key == the old id, byte for byte ----------

def test_a_finding_without_a_scene_key_keeps_the_old_id():
    """The upgrade must be a no-op for anything the key cannot name: no quote
    and no scene (script-level), and every finding in a report written before
    the field existed."""
    for f in ({"category": "genre", "issue": "The genre reads thin."},
              {"category": "dialogue", "issue": DEMO_ISSUE, "scene_refs": []},
              {"category": "dialogue", "evidence_quote": "A line.", "scene_refs": [7]}):
        with_key = {**f, "scene_key": ""}
        assert compute_finding_id(f) == compute_finding_id(with_key)
    # and a stamped finding with no scene_refs is identical to an unstamped one
    assert compute_finding_id({"category": "genre", "issue": "x", "scene_key": "ANY"}) \
        != compute_finding_id({"category": "genre", "issue": "x"})


# ---------- 2. the collision, on the shape that actually collided ----------

def test_nine_same_words_findings_at_nine_scenes_get_nine_ids():
    """The measured HIGH-1 shape: one issue, nine scenes. Before the scene key
    all nine hashed together; the whole point is that they no longer do."""
    headings = ["INT. A - DAY", "INT. B - DAY", "INT. C - DAY", "INT. D - DAY",
                "INT. E - DAY", "INT. F - DAY", "INT. G - DAY", "INT. H - DAY",
                "INT. I - DAY"]
    doc = _doc(*headings)
    keys = scene_key_map(doc)
    ids = {compute_finding_id(_finding(n, keys=doc)) for n in range(1, 10)}
    assert len(ids) == 9, f"the collision is back: {len(ids)} distinct ids for 9 findings"
    # ...and the old key really did collide, so this test cannot pass by accident
    legacy = {compute_finding_id(_finding(n, with_key=False)) for n in range(1, 10)}
    assert len(legacy) == 1


def test_a_repeated_heading_is_disambiguated_by_occurrence_and_the_first_is_stable():
    """Two scenes share a slugline. The first keeps the bare slug, so appending
    a LATER duplicate can never rename the scene that came first — the residual
    hazard (inserting a duplicate before it) is documented in scenekey.py and
    is the price of not keying on ordinals."""
    doc = _doc("INT. SIDDHU'S HOUSE - NIGHT", "EXT. ROAD - DAY", "INT. SIDDHU'S HOUSE - NIGHT")
    keys = scene_key_map(doc)
    assert keys[1] == "INT SIDDHUS HOUSE NIGHT"
    assert keys[3] == "INT SIDDHUS HOUSE NIGHT#2"
    assert compute_finding_id(_finding(1, keys=doc)) != compute_finding_id(_finding(3, keys=doc))
    # a third scene with a NEW heading does not disturb either
    later = scene_key_map(_doc("INT. SIDDHU'S HOUSE - NIGHT", "EXT. ROAD - DAY",
                               "INT. SIDDHU'S HOUSE - NIGHT", "INT. KITCHEN - DAY"))
    assert later[1] == keys[1] and later[3] == keys[3]


# ---------- 3. the slug: which edits move an id, and which do not ----------

def test_punctuation_and_case_do_not_move_the_slug_but_words_do():
    """The slug is what an id keys on, so the test states the exact price the
    report discloses: a re-typed heading with the same words keeps the scene's
    key (and its marks); renaming the location does not."""
    assert heading_slug("INT. SIDDHU’S HOUSE - CONTINUOUS") == heading_slug("int siddhu's house continuous")
    assert heading_slug("INT.  HOUSE  -  NIGHT") == "INT HOUSE NIGHT"
    assert heading_slug("INT. HOUSE - NIGHT") != heading_slug("INT. HOUSE - MORNING")
    assert heading_slug("இNT. வீடு - இரவு")  # non-ASCII survives rather than collapsing


def test_a_heading_that_slugs_empty_gets_no_key():
    """An empty/garbage heading must not produce an empty-string key that looks
    like a real one: the finding keeps its old id, honestly."""
    keys = scene_key_map(_doc("...", "INT. HOUSE - DAY"))
    assert 1 not in keys
    assert keys[2] == "INT HOUSE DAY"


def test_a_heading_with_a_character_above_the_bmp_keeps_it():
    """The keep-list runs to U+10FFFF. Stopping at U+FFFF dropped every emoji
    and every CJK-extension character: an emoji-only heading slugged to ''
    (no key at all) and two headings that differed only by an emoji shared one
    slug. The rule is inside every stored id, so it is pinned before the first
    release — after it, changing it would move ids."""
    house, car = "INT. \U0001F3E0 - DAY", "INT. \U0001F697 - DAY"
    assert heading_slug(house) == "INT \U0001F3E0 DAY"
    assert heading_slug(house) != heading_slug(car)
    assert heading_slug("\U00020BB7") == "\U00020BB7"  # CJK extension B
    assert scene_key_map(_doc("\U0001F3E0"))[1] == "\U0001F3E0"  # not an empty slug
    # what was already kept is still kept, unchanged
    assert heading_slug("INT. \u0bb5\u0bc0\u0b9f\u0bc1 \u0b87\u0bb0\u0bb5\u0bc1") \
        == "INT \u0bb5\u0bc0\u0b9f\u0bc1 \u0b87\u0bb0\u0bb5\u0bc1"


def test_inserting_a_scene_moves_no_existing_key_and_scene_refs_never_key_the_id():
    """The contract the id was built around (test_revision's
    test_id_survives_scene_insert_shift): the writer inserts a scene and no
    mark orphans. Every ordinal after the insert shifts; the slugline keys — and
    so the ids — do not."""
    before = _doc("INT. A - DAY", "INT. B - DAY", "INT. C - DAY")
    after = _doc("INT. A - DAY", "INT. NEW - NIGHT", "INT. B - DAY", "INT. C - DAY")
    kb, ka = scene_key_map(before), scene_key_map(after)
    assert kb[2] == ka[3] == "INT B DAY"      # B: scene 2 -> scene 3, same key
    assert kb[3] == ka[4] == "INT C DAY"
    f_before, f_after = _finding(2, keys=before), _finding(3, keys=after)
    assert f_before["scene_refs"] != f_after["scene_refs"]
    assert compute_finding_id(f_before) == compute_finding_id(f_after)


# ---------- 4. the migration: carry what is unambiguous, hold the rest ----------

class _M:
    """A manifest stub: revision.py only needs project_dir + report_findings_path."""

    def __init__(self, tmp_path, findings):
        self.project_dir = str(tmp_path)
        self.report_findings_path = os.path.join(self.project_dir, "report.findings.json")

    def stage(self, _name):
        raise AssertionError("no stage gate on this path")


def _write_report(m, findings):
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        json.dump({"findings": findings}, f)


def test_one_stored_mark_one_finding_is_carried_losslessly(tmp_path):
    doc = _doc("INT. KID SIDDHU’S HOUSE - NIGHT", "INT. A RANDOM MALL - MORNING")
    keys = scene_key_map(doc)
    findings = [{"category": "continuity", "issue": "time flip", "evidence_quote": "INT. KID SIDDHU’S HOUSE - NIGHT",
                 "scene_refs": [1], "scene_key": keys[1]}]
    m = _M(tmp_path, findings)
    _write_report(m, findings)
    legacy = compute_finding_id({**findings[0], "scene_key": ""})
    current = compute_finding_id(findings[0])
    assert legacy != current
    with open(os.path.join(m.project_dir, "finding_marks.json"), "w", encoding="utf-8") as f:
        json.dump({legacy: "deferred"}, f)
    # the mark is carried, same intent, one new id — and the parse-of-record is
    # not even needed: the report already names the scene
    assert finding_intents(m) == {current: "deferred"}
    assert json.load(open(os.path.join(m.project_dir, "finding_marks.json"))) == {current: "deferred"}
    # idempotent: a second read changes nothing
    assert finding_intents(m) == {current: "deferred"}


def _save_path(m):
    return os.path.join(m.project_dir, "parsed.json")


def test_one_stored_mark_covering_nine_findings_is_held_aside_not_spread(tmp_path):
    """The collision itself. One mark, nine findings: the desk must not apply it
    to any of them (that invents a judgment) and must not drop it either."""
    headings = [f"INT. ROOM {i} - DAY" for i in range(1, 10)]
    doc = _doc(*headings)
    keys = scene_key_map(doc)
    findings = [{"category": "dialogue", "issue": DEMO_ISSUE, "evidence_quote": None,
                 "scene_refs": [i], "scene_key": keys[i]} for i in range(1, 10)]
    m = _M(tmp_path, findings)
    _write_report(m, findings)
    doc.save(_save_path(m))
    legacy = compute_finding_id({**findings[0], "scene_key": ""})
    with open(os.path.join(m.project_dir, "finding_marks.json"), "w", encoding="utf-8") as f:
        json.dump({legacy: "addressed"}, f)

    out = finding_intents(m)
    assert out == {}, "a collided mark must not be applied to any finding"
    held = ambiguous_marks(m)
    assert list(held) == [legacy]
    assert held[legacy]["intent"] == "addressed"
    assert held[legacy]["covered"] == 9
    assert len(held[legacy]["candidates"]) == 9
    # the active store no longer carries it, and the held copy is not a deletion
    assert json.load(open(os.path.join(m.project_dir, "finding_marks.json"))) == {}

    # a NEW mark on a resolved id still works beside it, and the held file keeps
    # its record through later marks
    from screenplay_studio.revision import set_finding_intent
    set_finding_intent(m, compute_finding_id(findings[3]), "deferred")
    assert finding_intents(m) == {compute_finding_id(findings[3]): "deferred"}
    assert list(ambiguous_marks(m)) == [legacy]


def test_a_mark_shared_with_a_finding_that_kept_its_id_is_held_aside_too(tmp_path):
    """One stored id covered a scene-keyed finding AND a script-level finding
    saying the same words. Only the first changes id. A carry that counted just
    the finding that moved would hand the mark to it alone and silently take it
    from the other — a guess about which one the writer meant. It is held
    aside like every other collision, and `covered` counts both."""
    doc = _doc("INT. HOUSE - DAY")
    keys = scene_key_map(doc)
    scened = {"category": "dialogue", "issue": DEMO_ISSUE, "evidence_quote": None,
              "scene_refs": [1], "scene_key": keys[1]}
    script_level = {"category": "dialogue", "issue": DEMO_ISSUE, "evidence_quote": None,
                    "scene_refs": []}
    findings = [scened, script_level]
    m = _M(tmp_path, findings)
    _write_report(m, findings)
    doc.save(_save_path(m))
    legacy = compute_finding_id(script_level)
    assert legacy == compute_finding_id({**scened, "scene_key": ""})
    assert compute_finding_id(scened) != legacy

    remap, _ = legacy_id_candidates(m)
    assert sorted(remap[legacy]) == sorted({compute_finding_id(scened), legacy}), \
        "the finding that kept the legacy id is a candidate too"

    with open(os.path.join(m.project_dir, "finding_marks.json"), "w", encoding="utf-8") as f:
        json.dump({legacy: "addressed"}, f)
    assert finding_intents(m) == {}, "the mark must not be handed to one of two findings"
    held = ambiguous_marks(m)
    assert held[legacy]["intent"] == "addressed" and held[legacy]["covered"] == 2


def test_a_migration_that_cannot_read_the_report_never_touches_the_store(tmp_path):
    m = _M(tmp_path, [])
    _write_report(m, [{"category": "dialogue", "issue": DEMO_ISSUE}])
    marks = {"fdeadbeef": "addressed"}
    with open(os.path.join(m.project_dir, "finding_marks.json"), "w", encoding="utf-8") as f:
        json.dump(marks, f)
    assert finding_intents(m) == marks
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        f.write("{ this is not json")
    assert finding_intents(m) == marks


def test_a_stamp_is_never_overwritten_by_a_later_merge():
    """`stamp_scene_keys` leaves an existing key alone: a finding carried
    forward from an earlier report keeps the id it was stored under."""
    from screenplay_parser.scenekey import stamp_scene_keys
    doc = _doc("INT. HOUSE - DAY")
    keys = scene_key_map(doc)
    f = {"category": "dialogue", "issue": "x", "scene_refs": [1], "scene_key": "OLD SLUG"}
    assert stamp_scene_keys([f], keys)[0]["scene_key"] == "OLD SLUG"
    bare = {"category": "dialogue", "issue": "x", "scene_refs": [1]}
    assert stamp_scene_keys([bare], keys)[0]["scene_key"] == "INT HOUSE DAY"
