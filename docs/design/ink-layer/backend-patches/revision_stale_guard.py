"""revision.py — absolute stale-proposal protection for the apply path.

WHERE THIS GOES
    Paste the block below into `screenplay_studio/revision.py`, immediately
    above `def apply_edit(...)` (with `scene_text` already defined above it),
    then add ONE line inside the existing critical section of `apply_edit` —
    after the document has been read, before anything is written:

        with lock_for(...):                     # the existing critical section
            doc = load_working(m)               # the existing read
            _assert_proposal_is_fresh(doc, scene_number, replacements)   # ADD
            ...                                 # the existing replace + save

    Verification and mutation must be ONE critical section. A pre-check in the
    route would read outside this lock and race the very write it is meant to
    protect (BE-1) — which is why the guard lives here and not in webapp_server.
"""

STALE_PROPOSAL_MESSAGE = "Stale proposal: the text was modified manually."


class StaleProposalError(ValueError):
    """A proposal no longer matches the working copy it was cut from.

    Raised from inside `apply_edit`'s `lock_for('working.json')` section, before
    anything is written — the mutation is refused, never half-applied.

    Subclasses ValueError on purpose: every layer that already answers a
    ValueError with a 400 keeps working anywhere the stale contract is not
    named, so a route that forgets to catch this can never turn a stale
    proposal into a 500.
    """

    def __init__(self, message: str = STALE_PROPOSAL_MESSAGE):
        super().__init__(message)


def _still_holds(lines, wanted: bytes) -> bool:
    """Is `wanted` present, byte for byte, as one line or a consecutive run?

    Whole-value equality at every granularity — never containment. Containment
    was the first shape of this guard and it is wrong in the one way that
    matters: a writer who types "!" onto the end of the proposed line leaves the
    old text as an exact substring, so a substring test passes and the frame
    commits over a line the writer had just changed, dragging the stray "!" into
    the middle of the replacement ("…broken.!"). Exact equality of the whole
    value is the only comparison that can tell "the text still stands" from "the
    text was edited", which is the entire question this guard asks.

    The run window exists so a proposal spanning a line break (a dialogue
    exchange, an action paragraph the model copied across lines) is verified by
    the same rule rather than a looser one.
    """
    if wanted in lines:
        return True
    span = wanted.count(b"\n") + 1
    if span == 1 or span > len(lines):
        return False
    return any(b"\n".join(lines[i:i + span]) == wanted
               for i in range(len(lines) - span + 1))


def _assert_proposal_is_fresh(doc, scene_number: int, replacements) -> None:
    """Verify every proposal frame against the live working copy, verbatim.

    The rewrite route hands the SPA candidates cut from a snapshot of one
    scene, and the writer keeps editing for as long as the model takes to
    answer. By the time a candidate is accepted, the line it was cut from may
    have been retyped — applying it anyway would overwrite words the writer
    never saw, in a document whose whole promise is that edits are deliberate.
    So a frame is applied only while its `old` text still stands in the scene,
    byte for byte, at the instant the lock is held.

    Reads the scene through `scene_text`, the same serializer `/rewrite` echoed
    to the client, so the comparison is apples-to-apples with the snapshot the
    proposal was cut from rather than a second opinion about what the scene
    says. No strip, no case-fold, no Unicode normalisation anywhere: a
    whitespace difference IS the manual edit this guard exists to catch.

    Known, bounded limitation: a scene holding two byte-identical lines cannot
    say which one a frame targets (the payload carries text, not offsets), so a
    manual edit to the other copy of a duplicated line is not detected here.
    """
    lines = scene_text(doc, scene_number).encode("utf-8").split(b"\n")
    for rep in replacements:
        if not _still_holds(lines, rep["old"].encode("utf-8")):
            raise StaleProposalError()


def proposal_is_landable(doc, scene_number: int, old: str) -> bool:
    """True when `old` still stands in the scene verbatim.

    The producer's half of the same predicate: `/rewrite` shows a candidate only
    if this returns True, `_assert_proposal_is_fresh` refuses the rest, and both
    answer from `_still_holds` — so the desk can never offer a proposal the
    apply path will reject, and can never accept one the writer has outrun.
    """
    return _still_holds(scene_text(doc, scene_number).encode("utf-8").split(b"\n"),
                        old.encode("utf-8"))
