"""Gap 43 — direct emotion was automatically declared missing subtext.

Measured before the fix, on a scene deliberately built as a twelve-years-delayed
confession (the silence held in the action line, the line as the release):

    severity=low
    "On-the-nose line for MIRA: 'I love you.' names the emotion outright —
     the subtext is missing, so the scene tells instead of shows."
    why="...the moment lands flat..."

The identical finding was produced for the same line with no dramatic framing at
all, and for a comic scene built entirely on the bluntness of "I hate this."
A regex matched, and three separate claims were printed as fact:

    "the subtext is missing"        — an absence claim
    "the scene tells instead of shows" — a craft verdict on the scene
    "the moment lands flat"         — a claim about the reader's experience

A regex knows none of these. It knows the line names an emotion.

The register was explicit about the remedy: "treat literal expression as an
optional observation or context-sensitive question, not proof of absent subtext
or poor writing" and "do not categorically ban useful directness". So the
finding stays. The verdict goes.
"""
from screenplay_analyzer.report import OBSERVATION_BADGE, _format_finding
from screenplay_analyzer.voice import run_subtext_analysis
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument


def _doc(*scenes):
    d = ScriptDocument(title="T", author=None, source_format="fountain",
                       source_filename="t.fountain")
    d.scenes = list(scenes)
    return d


def _scene(stage_lines=(), who="MIRA", line="I love you.", num=1):
    sc = Scene(scene_number=num, heading_raw="INT. KITCHEN - NIGHT", int_ext="INT",
               location="KITCHEN", time_of_day="NIGHT")
    sc.elements.append(Element(type=ElementType.SCENE_HEADING, text="INT. KITCHEN - NIGHT"))
    for t in stage_lines:
        sc.elements.append(Element(type=ElementType.ACTION, text=t))
    sc.elements.append(Element(type=ElementType.CHARACTER, text=who))
    sc.elements.append(Element(type=ElementType.DIALOGUE, text=line))
    return sc


CONFESSION = (
    "MIRA has held this for twelve years. She sets down the cup, and the "
    "silence between them is the whole marriage.",
)


# ---------------------------------------------------------------------------
# 1. The filed case: the words that asserted a verdict are gone
# ---------------------------------------------------------------------------

def test_the_finding_no_longer_says_the_subtext_is_missing():
    findings, _ = run_subtext_analysis(_doc(_scene(CONFESSION)))
    assert findings, "the observation should still be raised"
    blob = (findings[0]["issue"] + " " + findings[0]["why_it_matters"]).lower()
    assert "the subtext is missing" not in blob
    assert "tells instead of shows" not in blob


def test_the_finding_no_longer_says_the_moment_lands_flat():
    findings, _ = run_subtext_analysis(_doc(_scene(CONFESSION)))
    assert "lands flat" not in findings[0]["why_it_matters"].lower()


def test_the_finding_still_reports_what_was_actually_detected():
    """The observation must survive: the regex genuinely noticed something."""
    findings, _ = run_subtext_analysis(_doc(_scene(CONFESSION)))
    assert len(findings) == 1
    f = findings[0]
    assert 'I love you.' in f["issue"]
    assert "MIRA" in f["issue"]
    assert f["evidence_quote"] == "I love you."
    assert f["category"] == "subtext"


def test_directness_is_still_reported_not_banned():
    """The register's explicit warning: do not categorically ban useful
    directness. A blunt line must still produce an observation."""
    findings, _ = run_subtext_analysis(_doc(_scene((), who="MIRA", line="I hate this.")))
    assert len(findings) == 1


# ---------------------------------------------------------------------------
# 2. It is marked as an observation, in the data and in the report
# ---------------------------------------------------------------------------

def test_the_finding_is_flagged_as_an_observation():
    findings, _ = run_subtext_analysis(_doc(_scene(CONFESSION)))
    assert findings[0]["is_observation"] is True
    assert findings[0]["confidence"] == "observation"


def test_the_report_shows_the_observation_badge():
    findings, _ = run_subtext_analysis(_doc(_scene(CONFESSION)))
    rendered = _format_finding(findings[0])
    assert OBSERVATION_BADGE.strip() in rendered
    assert "not a verdict" in rendered
    assert "your call" in rendered


def test_the_badge_is_not_attached_to_ordinary_findings():
    """A badge on everything is a badge on nothing."""
    plain = {"issue": "Pacing sags", "why_it_matters": "w", "severity": "medium",
             "scene_refs": [1], "verification": {"status": "verified"}}
    assert OBSERVATION_BADGE.strip() not in _format_finding(plain)


def test_every_deterministic_subtext_finding_carries_the_flag():
    """Not just the filed wording — the flag is a property of the check."""
    for line in ("I love you.", "I'm so angry.", "I hate this.", "I feel lonely."):
        findings, _ = run_subtext_analysis(_doc(_scene((), line=line)))
        assert findings and all(f["is_observation"] for f in findings), line


# ---------------------------------------------------------------------------
# 3. The context sensitivity the register asked for
# ---------------------------------------------------------------------------

def test_a_staged_moment_is_told_that_it_looks_deliberate():
    """A writer who has built twelve years of withholding around the line should
    not be told it is an accident."""
    findings, _ = run_subtext_analysis(_doc(_scene(CONFESSION)))
    why = findings[0]["why_it_matters"].lower()
    assert "looks deliberate" in why
    assert "held this" in why or "twelve years" in why


def test_an_unstaged_line_gets_the_neutral_wording():
    findings, _ = run_subtext_analysis(_doc(_scene((), line="I'm so angry.")))
    why = findings[0]["why_it_matters"].lower()
    assert "looks deliberate" not in why
    assert "your call" in why or "writer's call" in why


def test_the_observation_always_leaves_the_judgement_with_the_writer():
    """Whatever the context, the finding must not close the question."""
    for stage in (CONFESSION, (), ("A quiet room.",), ("He finally admits it.",)):
        findings, _ = run_subtext_analysis(_doc(_scene(stage)))
        why = findings[0]["why_it_matters"].lower()
        assert "call" in why or "observation" in why, why


def test_a_comic_beat_is_not_declared_bad_writing():
    """The register's comic control. Bluntness is the joke; the finding must not
    grade it."""
    comic = ("A clown suit. A birthday cake. He is furious about the cake, and "
             "the audience already laughed.")
    findings, _ = run_subtext_analysis(_doc(_scene(comic, line="I hate this.")))
    blob = (findings[0]["issue"] + " " + findings[0]["why_it_matters"]).lower()
    for banned in ("poor writing", "bad writing", "flat"):
        assert banned not in blob


# ---------------------------------------------------------------------------
# 4. Nothing else regressed
# ---------------------------------------------------------------------------

def test_a_scene_with_no_direct_emotion_produces_nothing():
    findings, errors = run_subtext_analysis(_doc(_scene((), line="The kettle is boiling.")))
    assert findings == []
    assert errors == []


def test_a_line_without_a_character_cue_is_ignored():
    """The check is about a character naming their own feeling; an orphan line
    has no one to attribute it to."""
    sc = Scene(scene_number=1, heading_raw="INT. A - DAY", int_ext="INT",
               location="A", time_of_day="DAY")
    sc.elements.append(Element(type=ElementType.DIALOGUE, text="I love you."))
    findings, _ = run_subtext_analysis(_doc(sc))
    assert findings == []


def test_each_scene_gets_its_own_finding():
    a = _scene((), who="MIRA", line="I love you.", num=1)
    b = _scene((), who="VENU", line="I hate this.", num=2)
    findings, _ = run_subtext_analysis(_doc(a, b))
    assert len(findings) == 2
    assert [f["scene_refs"] for f in findings] == [[1], [2]]
