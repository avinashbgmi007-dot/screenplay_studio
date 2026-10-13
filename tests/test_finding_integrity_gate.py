"""The finding integrity gate — the post-analysis pass that removes mechanically
FALSE findings and folds same-scene duplicate observations before delivery.

Three properties this file exists to pin, in order of importance:

1. **Nothing is lost.** `findings` + `withdrawals` is always the pre-gate list.
   This is the "nothing lost" law, made checkable rather than asserted — the
   whole reason the gate keeps a ledger instead of deleting.
2. **Precision over recall.** Every rule is narrow enough that a *real* finding
   cannot be read as a false one. The conservative cases below ("the subtext is
   missing", a name that contains the other name, a generic craft template) are
   as load-bearing as the firing cases: they are what stops the gate from
   costing the writer a true note.
3. **The counts describe what the writer receives.** The gate runs before the
   verification summary and the evidence depth, so those numbers cannot publish
   a total the delivered rows contradict.
"""
from __future__ import annotations

import copy
import os
from types import SimpleNamespace

import pytest

from screenplay_analyzer.finding_integrity import FindingIntegrityGate, gate_findings
from screenplay_analyzer.pipeline import AnalysisResult, analyze
from screenplay_analyzer.report import render_markdown, to_findings_json
from screenplay_parser import parse_fountain

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")


def _f(issue, category="dialogue", scenes=(1,), quote="", rule_id=None,
       severity="medium", **over):
    f = {"category": category, "issue": issue, "evidence_quote": quote,
         "scene_refs": list(scenes), "severity": severity, "rule_id": rule_id,
         "why_it_matters": ""}
    f.update(over)
    return f


# --------------------------------------------------------------------------
# the five classes, and the conservative case beside each
# --------------------------------------------------------------------------

def test_inverted_finding_is_rejected():
    """A clean bill of health filed as feedback is not a finding."""
    rows = [_f("No problem with the dialogue in this scene; it reads cleanly.")]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["reject"] == 1
    assert "ABSENCE of a defect" in res.of("reject")[0].reason


def test_missing_desirable_quality_is_NOT_rejected():
    """The precision test that matters: "the subtext is missing" is a *defect*,
    not a clean bill of health. A broader rule would withdraw a real finding —
    the exact error this gate must never make."""
    rows = [_f("The subtext is missing from the final exchange.")]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


def test_deterministic_name_variant_false_positive_is_rejected():
    rows = [_f("GUN_GUY and PEN_GUY appear to be inconsistent name variants of "
               "one character.",
               category="character", rule_id="name_variant_check")]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["reject"] == 1
    assert "edit distance" in res.of("reject")[0].reason


def test_name_containing_the_other_name_is_NOT_rejected():
    """RAJ is inside RAJESH — that is weak evidence they are one character, and
    the gate must not withdraw the finding on it."""
    rows = [_f("RAJ and RAJESH are inconsistent name variants of one character.",
               category="character", rule_id="name_variant_check")]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


def test_same_observation_twice_in_one_scene_is_merged():
    rows = [
        _f("Dialogue states the subtext outright.", category="dialogue",
           scenes=(2,), quote="I am your father."),
        _f("Dialogue states the subtext outright.", category="dialogue",
           scenes=(2,), quote="I am your father."),
    ]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["merge"] == 1
    assert res.summary["keep"] == 1
    # the survivor states what it absorbed
    assert res.findings[0].get("merged_from") == [1]


def test_cross_category_restatement_keeps_both_rows():
    """Two shelves are two pieces of work, and the shelf is information the
    writer would lose — so the gate must not fold them. Costs nothing on the
    measured payloads, where the same-category form removed the same 5 errors."""
    rows = [
        _f("Dialogue states the subtext outright.", category="dialogue",
           scenes=(2,), quote="I am your father."),
        _f("Dialogue states the subtext outright.", category="character",
           scenes=(2,), quote="I am your father."),
    ]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["keep"] == 2
    assert res.withdrawals == []


def test_one_quoted_line_under_two_rules_keeps_both_rows():
    """The repo's established rule (`dedupe.collapse_exact_duplicates`): two notes
    about one quoted line are two pieces of work. A shared quote is NOT on its own
    a warrant to merge — an earlier form of this rule would have violated it."""
    rows = [
        _f("Dialogue is redundant and explains the action shown.",
           category="dialogue", scenes=(3,), quote="RAHUL Light banchey!"),
        _f("Character voice is indistinguishable and lacks markers.",
           category="dialogue", scenes=(3,), quote="RAHUL Light banchey!"),
    ]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["keep"] == 2
    assert res.withdrawals == []


def test_duplicate_in_a_different_scene_is_NOT_merged():
    """Two findings that point at different pages are two pieces of work."""
    rows = [
        _f("Dialogue states the subtext outright.", scenes=(2,), quote="I am your father."),
        _f("Dialogue states the subtext outright.", scenes=(9,), quote="I am your father."),
    ]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["keep"] == 2


def test_visual_claim_filed_as_dialogue_is_reclassified():
    rows = [_f("The ash falls from the cigar in a slow shot.", category="dialogue")]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["reclassify"] == 1
    d = res.of("reclassify")[0]
    assert d.finding["category"] == "scene_function"
    assert d.finding["_category_was"] == "dialogue"


def test_spoken_claim_in_dialogue_is_NOT_reclassified():
    rows = [_f("The line says the same thing twice in the dialogue.",
               category="dialogue")]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


def test_praise_filed_as_finding_is_rejected():
    """Trial-11 live rows: neutral/positive descriptions filed as defects."""
    rows = [
        _f("Dialogue contains multiple subtext layers.",
           category="dialogue", scenes=(5,),
           quote="Ajay doesnt look at his father",
           over={"observation": "The script contains exactly two instances of dialogue."}),
        _f("Dialogue reflects cultural context.",
           category="dialogue", scenes=(5,),
           quote="Alantide kotha book koni ichesthe?",
           over={"observation": "The character named 'RAM' is only listed as a speaker once."}),
    ]
    res = FindingIntegrityGate().run(rows)
    assert res.summary["reject"] == 2
    assert all("praise" in d.reason for d in res.of("reject"))
    # nothing lost: the ledger carries both rows whole
    assert res.accounted_for


def test_mixed_praise_with_contrast_is_NOT_rejected():
    """Precision sibling: 'rich but unearned' is a real defect — the
    contrast turn exempts it."""
    rows = [_f("The theme is rich but unearned by the plot.",
               over={"observation": "Stated in voiceover, never tested."})]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


def test_praise_with_defect_marker_is_NOT_rejected():
    """Precision sibling: any defect marker in issue or observation keeps
    the row, even beside a praise word."""
    rows = [
        _f("The pacing is effective without payoff in act three.",
           over={"observation": "Moves well, lands nowhere."}),
        _f("Strong opening, weak midpoint.",
           over={"observation": "The midpoint sags."}),
    ]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 2


def test_praise_in_quote_does_not_fire():
    """Quotes are verbatim script text and are never scanned."""
    rows = [_f("The line states the plan outright with no subtext.",
               quote="What a beautiful plan, perfectly effective.")]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


def test_gate_never_emits_a_category_outside_the_taxonomy():
    """Trial-5 regression: the gate reclassified a visual dialogue claim to
    category "scene", which is not in FINDING_CATEGORIES — a label the
    grammar can never produce and the report map never names. Reclassified
    rows must land inside the taxonomy (visual claims → scene_function)."""
    from screenplay_analyzer.grammar import FINDING_CATEGORIES
    rows = [
        _f("The ash falls from the cigar in a slow shot.", category="dialogue"),
        _f("The theme is not clearly defined as a cause-and-effect statement."),
        _f("A clean note about the opening image.", category="scene"),
    ]
    res = FindingIntegrityGate().run(rows)
    delivered, _ = gate_findings(rows)
    for f in delivered:
        assert f["category"] in FINDING_CATEGORIES, f["category"]


def test_generic_craft_template_is_NOT_withdrawn():
    """Deliberate: a template is *unfalsifiable*, not *false*. It carries no
    truth value, so withdrawing it would lift the accuracy number by shrinking
    the denominator — the failure mode this work set out to avoid. The product
    already badges it unverified."""
    rows = [_f("The theme is not clearly defined as a cause-and-effect statement.")]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


# --------------------------------------------------------------------------
# the invariants
# --------------------------------------------------------------------------

def test_gate_never_mutates_its_input():
    rows = [_f("No problem here."),
            _f("The ash falls from the cigar in a slow shot."),
            _f("Dialogue states the subtext outright.", scenes=(2,), quote="I am your father."),
            _f("Dialogue states the subtext outright.", scenes=(2,), quote="I am your father.",
               severity="low")]
    before = copy.deepcopy(rows)
    FindingIntegrityGate().run(rows)
    assert rows == before, "the gate mutated the caller's findings"


def test_nothing_is_lost_delivered_plus_ledger_is_the_original():
    rows = [_f("No problem here."),
            _f("The ash falls from the cigar in a slow shot."),
            _f("Dialogue states the subtext outright.", scenes=(2,), quote="I am your father."),
            _f("Dialogue states the subtext outright.", scenes=(2,), quote="I am your father.",
               severity="low"),
            _f("A clean note about the opening image.", category="scene")]
    res = FindingIntegrityGate().run(rows)
    assert res.accounted_for
    assert len(res.kept) + len(res.withdrawals) == len(rows)
    # and the ledger carries the finding's FULL content, not a reference
    for entry in res.ledger:
        assert entry["finding"]
        assert entry["action"] in ("merge", "reject")
        assert entry["reason"].strip()


def test_every_decision_carries_a_reason():
    rows = [_f("No problem here."),
            _f("The ash falls from the cigar in a slow shot."),
            _f("A clean note about the opening image.", category="scene")]
    res = FindingIntegrityGate().run(rows)
    assert all(d.reason.strip() for d in res.decisions)


def test_convenience_returns_the_two_halves():
    rows = [_f("No problem here."), _f("A clean note.", category="scene")]
    delivered, ledger = gate_findings(rows)
    assert len(delivered) + len(ledger) == len(rows)


# --------------------------------------------------------------------------
# in the pipeline
# --------------------------------------------------------------------------

class _StubClient:
    """Returns the same crafted payload for every pass, so the gate's effect is
    isolated from anything the model would decide."""

    INVERTED = _f("No problem with the exposition in this scene; it is well handled.",
                  scenes=(1,))
    DUP_A = _f("Dialogue states the subtext outright.", scenes=(2,),
               quote="I am your father.")
    # differs only in severity, so it survives `collapse_exact_duplicates` (which
    # keys on the whole row) and reaches the gate as a near-duplicate
    DUP_B = _f("Dialogue states the subtext outright.", scenes=(2,),
               quote="I am your father.", severity="low")
    CLEAN = _f("The opening image repeats the previous scene heading verbatim.",
               category="continuity", scenes=(1,),
               quote="INT. KID SIDDHU'S HOUSE - NIGHT")

    def resolve_model(self):
        return "stub-model"

    def chat_json(self, *args, **kwargs):
        return {"findings": [self.INVERTED, self.DUP_A, self.DUP_B, self.CLEAN]}


def _doc():
    return parse_fountain(FIXTURE)


def test_pipeline_withdrawals_plus_findings_equals_the_ungated_list():
    """The end-to-end 'nothing lost' proof: turning the gate on removes rows
    from `findings` but accounts for every one of them in `withdrawals`."""
    on = analyze(_doc(), _StubClient(), run_categories=("dialogue",))
    off = analyze(_doc(), _StubClient(), run_categories=("dialogue",),
                  integrity_gate=False)

    assert off.withdrawals == [], "the gate ran when it was told not to"
    assert len(on.findings) + len(on.withdrawals) == len(off.findings), (
        "the gate lost a finding: findings + withdrawals must be the ungated list")
    assert on.withdrawals, "the crafted false findings did not trigger the gate"
    assert all(w["reason"].strip() for w in on.withdrawals)


def test_env_kill_switch_stands_the_gate_down(monkeypatch):
    monkeypatch.setenv("SCREENPLAY_STUDIO_INTEGRITY_GATE", "0")
    result = analyze(_doc(), _StubClient(), run_categories=("dialogue",))
    assert result.withdrawals == []


def test_json_report_carries_the_ledger():
    result = analyze(_doc(), _StubClient(), run_categories=("dialogue",))
    payload = to_findings_json(result)
    assert "withdrawals" in payload
    assert payload["withdrawals"] == result.withdrawals


def test_markdown_discloses_what_left_the_delivered_set():
    result = analyze(_doc(), _StubClient(), run_categories=("dialogue",))
    assert result.withdrawals, "need withdrawals to test the disclosure"
    md = render_markdown(result)
    assert "Integrity gate:" in md
    assert "Nothing was deleted" in md


def test_markdown_stays_silent_when_nothing_was_withdrawn():
    result = AnalysisResult(doc=_doc())
    assert "Integrity gate:" not in render_markdown(result)


def test_falsified_non_recurrence_is_rejected():
    """Trial-10 #4 shape: 'do not recur' while the object recurs."""
    from screenplay_parser import parse_fountain
    import os
    import tempfile
    text = ("Title: T\nAuthor: T\n\nINT. ROOM - NIGHT\n\n"
            "A gun lies on the floor here.\n\nCUT TO:\n\n"
            "INT. HALL - DAY\n\nHe picks up the gun again.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    rows = [_f("The gun does not recur or get referenced later.",
               category="dialogue", scenes=(1,),
               quote="A gun lies on the floor here.")]
    res = FindingIntegrityGate().run(rows, doc=doc)
    assert res.summary["reject"] == 1
    assert "falsified" in res.of("reject")[0].reason


def test_falsified_missing_lines_is_rejected():
    """'No dialogue for Raj' while Raj has a cue in range."""
    from screenplay_parser import parse_fountain
    import os
    import tempfile
    text = ("Title: T\nAuthor: T\n\nINT. ROOM - NIGHT\n\n"
            "RAJ\nI am staying right here.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    rows = [_f("There is no dialogue for Raj in this scene.",
               category="dialogue", scenes=(1,))]
    res = FindingIntegrityGate().run(rows, doc=doc)
    assert res.summary["reject"] == 1


def test_hedged_absence_is_NOT_rejected():
    """A careful model is never punished for hedging."""
    rows = [_f("The gun appears to never recur after this scene.",
               category="dialogue", scenes=(1,))]
    res = FindingIntegrityGate().run(rows)
    assert res.withdrawals == []
    assert res.summary["keep"] == 1


def test_falsified_parenthesized_object_list_is_rejected():
    """Spec-implementation gap: framing prose around the named object must
    not sink the recurrence check — terms come from the parenthesized span
    immediately before the marker, not the full prefix."""
    from screenplay_parser import parse_fountain
    import os
    import tempfile
    text = ("Title: T\nAuthor: T\n\nINT. ROOM - NIGHT\n\n"
            "A gun and a newspaper and a pen lie here.\n\nCUT TO:\n\n"
            "INT. HALL - DAY\n\nHe picks up the gun and the newspaper "
            "and the pen again.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    rows = [_f("Chekhov's Gun: Objects given narrative emphasis "
               "(gun, newspaper, pen) do not recur or get referenced later.",
               category="plot_thread", scenes=(1,),
               quote="A gun and a newspaper and a pen lie here.")]
    res = FindingIntegrityGate().run(rows, doc=doc)
    assert res.summary["reject"] == 1
    assert "falsified" in res.of("reject")[0].reason


class _EqDoc:
    """Minimal stub: one scene where RAJ's cue names PEN GUY — an
    explicit equation settling the identity the verdict denies."""

    def __init__(self):
        self.scenes = [SimpleNamespace(
            scene_number=2,
            characters_present=["RAJ", "PEN GUY"],
            elements=[SimpleNamespace(type="dialogue", character="RAJ",
                                       text="Pen Guy, come here.")])]


def test_identity_claim_contradicted_by_equation_is_rejected():
    """Claim 'X is not Y' beside text addressing X as Y is provably
    false — withdraw, don't demote."""
    rows = [_f("Raj is not Pen Guy.", category="character", scenes=(2,),
               quote="Nuvvu evaru ra?",
               over={"observation": "Pen Guy answers when Raj calls him by name."})]
    res = FindingIntegrityGate().run(rows, doc=_EqDoc())
    assert res.summary["reject"] == 1
    assert "contradict" in res.of("reject")[0].reason
