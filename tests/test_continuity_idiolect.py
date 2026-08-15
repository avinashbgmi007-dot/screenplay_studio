"""Tests for the new analysis passes: deterministic continuity (time-flip,
character-name variants), idiolect consistency, and Tenglish promise
extraction in the knowledge graph."""

import os
import tempfile

from screenplay_parser import parse_fountain
from screenplay_parser.knowledge_graph import build_knowledge_graph, TELUGU_PROMISE_RE
from screenplay_analyzer.continuity import run_continuity_analysis
from screenplay_analyzer.voice import run_idiolect_analysis


def _parse(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _rules(doc, rule_id):
    findings, _ = run_continuity_analysis(doc)
    return [f for f in findings if f.get("rule_id") == rule_id]


# ---- continuity: unmarked time flips ----

FLIP = """Title: Flip
Author: T

INT. ROOM - NIGHT

AARAV
Goodnight.

CUT TO:

INT. KITCHEN - DAY

AARAV pours coffee.
"""

MARKED_FLIP = """Title: MarkedFlip
Author: T

INT. ROOM - NIGHT

AARAV
Goodnight.

CUT TO:

INT. KITCHEN - DAY - LATER

AARAV pours coffee.
"""

CONTINUOUS_OK = """Title: Continuous
Author: T

INT. ROOM - NIGHT

AARAV
Goodnight.

CUT TO:

INT. KITCHEN - CONTINUOUS

AARAV pours coffee.
"""


def test_unmarked_time_flip_flagged():
    doc = _parse(FLIP)
    findings = _rules(doc, "unmarked_time_flip")
    assert len(findings) == 1
    assert findings[0]["category"] == "continuity"
    assert findings[0]["severity"] == "low"


def test_time_flip_cleared_by_marker():
    doc = _parse(MARKED_FLIP)
    assert _rules(doc, "unmarked_time_flip") == []


def test_continuous_clears_boundary():
    doc = _parse(CONTINUOUS_OK)
    assert _rules(doc, "unmarked_time_flip") == []


# ---- continuity: character name variants ----

VARIANT = """Title: Variants
Author: T

INT. ROOM - NIGHT

SIDDHARTH
I will find you.

CUT TO:

INT. HALL - NIGHT

SIDDHART
No you won't.
"""

SHARED_SCENE = """Title: Shared
Author: T

INT. ROOM - NIGHT

SIDDHARTH
I will find you.

SIDDHU
Then come.

CUT TO:

INT. HALL - NIGHT

SIDDHARTH
Ready?
"""


def test_character_name_variant_flagged():
    doc = _parse(VARIANT)
    findings = _rules(doc, "character_name_variant")
    assert len(findings) == 1
    assert "SIDDHARTH" in findings[0]["issue"] and "SIDDHART" in findings[0]["issue"]


def test_name_variant_sharing_scene_not_flagged():
    # If they ever appear together, they're deliberately different characters.
    doc = _parse(SHARED_SCENE)
    assert _rules(doc, "character_name_variant") == []


# ---- idiolect consistency ----

SHIFT = """Title: Shift
Author: T

INT. ROOM - NIGHT

AARAV
No.

MEERA
Okay.

AARAV
Why.

MEERA
Fine.

AARAV
Go.

AARAV
Stop.

CUT TO:

INT. KITCHEN - DAY

AARAV
I have been thinking about the way the light falls across this
kitchen every morning and what it says about the life we were
supposed to be living together and I do not know where to begin.

MEERA
And I have spent the whole year practicing the speech I would
give you if you ever actually stayed still long enough to hear
it, but now that you are here the words have all gone quiet.

AARAV
The silence between us has a shape of its own now, familiar and
heavy, and I carry it with me the way you used to carry your
coffee cup everywhere in this house.

AARAV
And I keep returning to that same question every evening, the
one about whether we were ever really going to leave this town,
and I still do not have an answer that sounds like the truth.
"""

STABLE = """Title: Stable
Author: T

INT. ROOM - NIGHT

AARAV
I think we should talk.

MEERA
I think we should too.

AARAV
I have been holding this for a while.

MEERA
I have been holding mine as well.

AARAV
It is heavier than I thought.

MEERA
Mine is heavier than I thought.

CUT TO:

INT. KITCHEN - DAY

AARAV
I want to say it plainly.

MEERA
I want to hear it plainly.

AARAV
I am afraid of how it sounds.

MEERA
I am afraid of how it lands.
"""


def test_idiolect_shift_flagged():
    doc = _parse(SHIFT)
    findings, _ = run_idiolect_analysis(doc)
    voice_breaks = [f for f in findings if f.get("rule_id") == "idiolect_consistency"]
    # AARAV (3 short lines then 3 long lines) must be flagged; the check needs
    # >= 6 lines so only characters with both halves sampled qualify.
    assert any("AARAV" in f["issue"] for f in voice_breaks)


def test_idiolect_consistent_not_flagged():
    doc = _parse(STABLE)
    findings, _ = run_idiolect_analysis(doc)
    assert [f for f in findings if f.get("rule_id") == "idiolect_consistency"] == []


# ---- Tenglish promise extraction ----

TENGLISH_PROMISE = """Title: Tenglish
Author: T

INT. HOSPITAL - NIGHT

DOCTOR
Hypoalgesia antaaru.

RISHI
Enti?

DOCTOR
Dhaa cheptha.

RISHI
Nammuko ra, inka jaragadu.

CUT TO:

INT. PARK - MAGIC HOUR

RISHI
Oka roju anni marchipotha.
"""


def test_tenglish_promise_extracted():
    doc = _parse(TENGLISH_PROMISE)
    kg = build_knowledge_graph(doc)
    texts = [c.text for c in kg.promise_candidates]
    assert any("Dhaa cheptha" in t for t in texts)
    assert any("Nammuko" in t for t in texts)
    assert any("Oka roju" in t for t in texts)


def test_telugu_promise_re_matches_known_forms():
    for phrase in ("Dhaa cheptha", "Nammuko", "Oka roju anni jarugutundi", "Pratijna chestaanu"):
        assert TELUGU_PROMISE_RE.search(phrase), phrase
    # ordinary narration must not match
    assert not TELUGU_PROMISE_RE.search("Vadu kurchunadu")
