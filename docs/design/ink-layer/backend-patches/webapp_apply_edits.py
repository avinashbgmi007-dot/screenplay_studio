"""webapp_server.py — hardened `apply_edits`.

WHERE THIS GOES
    Block A+B replace the existing `/api/projects/<name>/edits/apply` route: the
    constant + `_require_explicit_frames` sit immediately above the route (beside
    `_strip_rewrite_noise`), and the route itself is a whole-body replacement.

    Block C is a ONE-LINE change to the `/rewrite` loop directly above it, and
    it belongs with the rest: the staleness guard now requires `old` to match
    whole lines, so a frame the model mangled (`_strip_rewrite_noise` truncating
    a copied line at a structural token) would be shown to the writer and then
    refused as "modified manually" — a lie about a model artifact. The producer
    filters those out where the cause is known.

    The staleness verdict is NOT decided here: it is decided inside the working
    copy's own lock (see revision_stale_guard.py), and the only thing this route
    does with it is answer the contract's exact JSON.
"""

# Mandated frame contract: every entry of `replacements` must be an object
# carrying string 'old' and string 'new'. Shape-only, deliberately — deciding
# whether the text still MATCHES is the working copy's business and happens
# under its lock, never here, where a read would race the write it is meant to
# protect (BE-1).
_EXPLICIT_FRAMES_ERROR = "replacements require string fields 'old' and 'new'"


def _require_explicit_frames(replacements: list):
    """Return None when every frame is well-formed, else the 400 response.

    Absorbs the L5 guard (a bare string used to reach `rep.get()` and answer a
    500 carrying the traceback): the shape is now checked in one place, and the
    refusal is one of exactly two bodies — the array-level message, or the
    mandated frame message.
    """
    for rep in replacements:
        if not isinstance(rep, dict):
            return _error(_EXPLICIT_FRAMES_ERROR, 400)
        if not isinstance(rep.get("old"), str) or not isinstance(rep.get("new"), str):
            return _error(_EXPLICIT_FRAMES_ERROR, 400)
    return None


@app.route("/api/projects/<name>/edits/apply", methods=["POST"])
def apply_edits(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    body = request.get_json() or {}
    try:
        scene_number = int(body.get("scene_number"))
    except (TypeError, ValueError):
        return _error("scene_number is required.")
    replacements = body.get("replacements")
    if not isinstance(replacements, list) or not replacements:
        return _error("replacements list is required.")
    refusal = _require_explicit_frames(replacements)
    if refusal is not None:
        return refusal

    # BE-1: ONE call, because the load, the staleness verification and the
    # write must be one critical section. `apply_edit` holds
    # `lock_for(working.json)` across all three; do not reintroduce a
    # caller-side load or a pre-check here. The verification guard
    # (revision._assert_proposal_is_fresh) runs INSIDE that section, so no
    # writer can slip between "the text still matches" and "the text was
    # replaced".
    from .revision import apply_edit, finding_statuses, StaleProposalError, STALE_PROPOSAL_MESSAGE
    try:
        result = apply_edit(m, scene_number, replacements)
    except StaleProposalError:
        # The transaction is refused, whole: the writer typed into one of the
        # proposed lines while the rewrite was in flight. `stale: true` is what
        # lets the SPA offer "regenerate against the current text" instead of
        # showing a generic failure — reloading the proposal is the fix, and
        # retrying the same payload will refuse again, correctly.
        return jsonify({"error": STALE_PROPOSAL_MESSAGE, "stale": True}), 400
    statuses = finding_statuses(m) if m.stage("analyze").status == "complete" else {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}
    _record_findings_metrics(m, statuses)
    return jsonify({**result, "findings_status": statuses})


# ── Block C · one-line change in /rewrite ────────────────────────────────────
#
# In the existing `rewrite_scene_endpoint` loop:
#
#     from .revision import load_working, rewrite_scene, scene_text, proposal_is_landable
#     ...
#     replacements = []
#     for r in result.get("replacements", []):
#         old = (r.get("old") or "").strip()
#         new = (r.get("new") or "").strip()
#         old = _strip_rewrite_noise(old)
#         new = _strip_rewrite_noise(new)
#         if old and new and old != new and proposal_is_landable(doc, scene_number, old):
#             replacements.append({"old": old, "new": new})
#
# One added import name and one added condition. A candidate whose text no
# longer stands in the scene — because the model's copied line was truncated,
# or because the writer already typed over it while the model was thinking — is
# not shown as a proposal at all; `/rewrite` re-reads `doc` on the next request,
# so the regenerated set is taken from the current text.
