"""Gap 54 — a setup's word recurrence was treated as proof of payoff.

The filed reproduction: a two-scene script promises a silver key will open a
vault; later the key hangs unused while the vault stays locked. Because the
setup's words recur in that second scene, `adjudicate_ledger` flipped a
`dangling` verdict to `paid`, attached the scene as a payoff, set
`verified: true` — and `dangling_findings` then raised nothing. The vault is
still locked.

The module's own docstring stated the rule: "recurrence proves payoff (flip +
note), absence proves nothing". The asymmetry was half right. Absence really
does prove nothing — a scene can pay a setup off in words the setup never used.
Recurrence proves nothing either: it proves the vocabulary reappears, which is a
place to look, not a dramatic resolution.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_analyzer.setup_payoff import adjudicate_ledger, dangling_findings

KEY_UNUSED = """Title: T

INT. HALL - DAY

Lord Vale promises Mira the silver key opens the vault.

INT. VAULT - NIGHT

The silver key hangs on a hook. The vault stays locked.
"""

KEY_USED = """Title: T

INT. HALL - DAY

Lord Vale promises Mira the silver key opens the vault.

INT. VAULT - NIGHT

Mira turns the silver key and the vault opens.
"""

KEY_ABSENT = """Title: T

INT. HALL - DAY

Lord Vale promises Mira the silver key opens the vault.

INT. ROAD - DAY

Mira walks. Rain.
"""

ENTRY = {"setup": "the silver key opens the vault", "kind": "prop",
         "setup_scenes": [1], "payoff_scenes": [], "status": "dangling"}


def _doc(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _adjudicate(text, entry=None):
    return adjudicate_ledger([dict(entry or ENTRY)], _doc(text))[0]


# ---------- the filed reproduction ----------

def test_recurrence_does_not_flip_dangling_to_paid():
    e = _adjudicate(KEY_UNUSED)
    assert e["status"] == "dangling", (
        "the key hangs unused and the vault stays locked; matching words are "
        f"not a payoff (note was: {e.get('verify_note')!r})")


def test_recurrence_does_not_set_verified():
    """`verified` must mean this pass checked something, not that words matched."""
    e = _adjudicate(KEY_UNUSED)
    assert e.get("verified") is False


def test_recurrence_is_recorded_as_a_candidate_scene():
    """It is still useful information — just not a verdict."""
    e = _adjudicate(KEY_UNUSED)
    assert e.get("payoff_candidates") == [2]


def test_the_candidate_is_not_written_into_payoff_scenes():
    """A payoff scene is a claim. This pass has not established one."""
    e = _adjudicate(KEY_UNUSED)
    assert not e.get("payoff_scenes")


def test_the_dangling_finding_survives():
    """This is the consequence the entry names: the flip suppresses the finding."""
    e = _adjudicate(KEY_UNUSED)
    findings = dangling_findings([e], [], doc=_doc(KEY_UNUSED))
    assert len(findings) == 1
    assert "silver key" in findings[0]["issue"]


def test_the_note_says_what_was_and_was_not_established():
    e = _adjudicate(KEY_UNUSED)
    note = e["verify_note"].lower()
    assert "scene 2" in note
    assert "not a payoff" in note
    assert e["status"] in note, "the note should say the status did not change"


# ---------- a real payoff still verifies ----------

def test_a_claimed_payoff_that_really_recurs_is_still_verified():
    """The fix must not make the pass useless — it checks claims, it just does
    not invent them."""
    e = _adjudicate(KEY_USED, {**ENTRY, "status": "paid", "payoff_scenes": [2]})
    assert e["status"] == "paid"
    assert e["verified"] is True
    assert "scene 2" in e["verify_note"]


def test_a_claimed_payoff_with_no_matching_terms_is_flagged_not_trusted():
    e = _adjudicate(KEY_ABSENT, {**ENTRY, "status": "paid", "payoff_scenes": [2]})
    assert e["verified"] is False
    assert e.get("payoff_unproven") is True


def test_a_payoff_cited_before_its_setup_is_not_trusted():
    """Backstory or coincidence, never a payoff (the existing chronological rule)."""
    text = """Title: T

INT. VAULT - NIGHT

The silver key opens the vault.

INT. HALL - DAY

Lord Vale promises Mira the silver key opens the vault.
"""
    e = _adjudicate(text, {**ENTRY, "status": "paid", "payoff_scenes": [1]})
    assert e["verified"] is False


# ---------- absence still proves nothing ----------

def test_no_recurrence_keeps_the_status_and_flags_nothing():
    e = _adjudicate(KEY_ABSENT)
    assert e["status"] == "dangling"
    assert e["verified"] is False
    assert "absence proves nothing" in e["verify_note"]


def test_no_recurrence_does_not_downgrade_a_paid_verdict():
    """The mirror: a payoff the terms cannot locate is not proof it is missing."""
    e = _adjudicate(KEY_ABSENT, {**ENTRY, "status": "paid", "payoff_scenes": []})
    assert e["status"] == "paid"
    assert e.get("payoff_unproven") is True, "flagged as unproven, not rewritten"


# ---------- deliberately open strands ----------

def test_an_unresolved_strand_is_reported_as_possibly_deliberate():
    """'Do not count an intentionally open ending as a defect merely because
    closure is absent.' The finding must say so."""
    e = _adjudicate(KEY_ABSENT)
    f = dangling_findings([e], [], doc=_doc(KEY_ABSENT))[0]
    why = f["why_it_matters"].lower()
    assert "deliberate" in why or "on purpose" in why
    assert f["is_observation"] is True
    assert f["confidence"] == "observation"


def test_a_writer_note_is_preserved_in_the_finding():
    note = "Intentionally open — the vault is never opened."
    e = _adjudicate(KEY_ABSENT, {**ENTRY, "note": note})
    f = dangling_findings([e], [], doc=_doc(KEY_ABSENT))[0]
    assert note in f["why_it_matters"]


def test_a_red_herring_is_never_turned_into_a_finding():
    """`red_herring` is the status for a deliberately planted strand."""
    e = _adjudicate(KEY_ABSENT, {**ENTRY, "status": "red_herring"})
    assert dangling_findings([e], [], doc=_doc(KEY_ABSENT)) == []


def test_the_finding_points_at_the_candidate_scene_too():
    e = _adjudicate(KEY_UNUSED)
    f = dangling_findings([e], [], doc=_doc(KEY_UNUSED))[0]
    assert f["payoff_candidates"] == [2]
    assert "scene 2" in f["why_it_matters"]


# ---------- the setup itself still has to be real ----------

def test_an_ungrounded_setup_is_still_marked_ungrounded():
    e = _adjudicate(KEY_ABSENT, {**ENTRY, "setup": "a golden crown appears",
                                 "setup_scenes": [1]})
    assert e["setup_ungrounded"] is True
    assert e["verified"] is False
