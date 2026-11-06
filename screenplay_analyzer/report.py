"""
Assembles the human-readable .md report and the machine-readable findings
JSON (same content, structured — this is what Piece 3 loads to discuss
specific findings without re-parsing markdown) from an AnalysisResult.
"""

import json
import os
import tempfile

from .pipeline import AnalysisResult
from .verifier import verification_rate


def _atomic_write_text(path: str, text: str) -> None:
    """Write `text` to `path` via a temp file + os.replace, so a crash or kill
    mid-write leaves the PREVIOUS file intact instead of a torn or empty one
    (M5b). The report is the product's core artifact; `open(path, "w")` is
    truncate-then-write, which is exactly the window that loses it.

    Local to Piece 2 on purpose: the packages stay standalone (no import of
    screenplay_studio.jsonio, whose helper this mirrors)."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-report-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

VERIFICATION_BADGE = {
    "verified": "",
    "not_found": " ⚠️ *unverified — quote not confirmed in cited scene(s)*",
    "no_quote": "",
    "scene_not_found": " ⚠️ *unverified — cited scene number doesn't exist*",
}

# Gap 87: the analyse pipeline demotes a finding with no quote and no
# observation to low severity and marks it `ungrounded` (pipeline
# .apply_evidence_floor). The desk honours that — such rows are hidden behind a
# toggle in the fix queue. The exported Markdown did NOT: it carried neither the
# flag nor the verification status, so the same unsupported sentence read as a
# plain "[LOW] Scene 1, Scene 2 — Setup left dangling: 'The revolver'" in the
# report a writer exports or sends to a producer, and as a hidden guess in the
# dock. The report is the artefact that travels; it has to say so itself.
UNGROUNDED_BADGE = (" ⚠️ *unsupported — this note cites no quote or observation "
                    "from your script*")

# Gap 43: a deterministic check can notice a line and cannot judge a scene. Such
# findings are marked with a badge that says so in the one place the writer
# reads, so an observation is never mistaken for a note on the writing.
OBSERVATION_BADGE = (" ◆ *observation — a pattern, not a verdict; whether it works "
                     "depends on the scene, which is your call*")

# Gap 88: the built-in stand-in used to be disclosed only BY NAME — its model id
# appeared in "Analyzed with" and its own findings happened to say "[demo] ...".
# Both are the stub cooperating with us. A report should say what produced it
# from the RUN'S OWN RECORD, so that an archive still tells the truth after the
# demo setting is switched off (gap 59) and so a change of wording inside the
# stub cannot quietly remove the disclosure.
DEMO_MODEL_IDS = frozenset({"demo-craft-model"})


def model_is_stand_in(model_used: str | None) -> bool:
    """Was this report produced by the built-in stand-in?

    Derived from the persisted `model_used`, never from the current process's
    demo setting: what matters is what ran, not what is configured now.
    """
    return (model_used or "").strip().lower() in DEMO_MODEL_IDS

CATEGORY_TITLES = {
    "theme": "Theme & Subtext",
    "character": "Character Arcs & Consistency",
    "structure": "Structure & Pacing",
    "scene_function": "Scene Functionality",
    # Deterministic craft passes — these categories were previously missing
    # here, so their findings existed in report.findings.json and the Fix
    # Queue but silently never rendered in the markdown/HTML report.
    "continuity": "Continuity",
    "voice": "Voice & Idiolect",
    "subtext": "Subtext",
    "dialogue": "Dialogue & Action",
    "plot_thread": "Plot Economy (Setups, Payoffs & Chekhov's Gun)",
    "genre": "Genre Conventions",
}


# Gap 47: an empty category used to say "No significant findings" whatever had
# happened. Three very different situations shared one sentence:
#
#   ok       the pass ran, found nothing            -> a clean result
#   failed   the pass errored                       -> NOT a clean result
#   skipped  the pass could not apply to this text  -> NOT a clean result
#
# and a fourth, worse one: the category was never attempted (not requested, or
# a prerequisite was missing) and so appears in no `category_outcomes` entry at
# all. A writer reading "No significant findings" under Dialogue cannot tell
# whether the dialogue is clean or the dialogue pass crashed, and the honest
# answer changes what they do next.
_OUTCOME_TEXT = {
    "failed": ("**This pass failed — the section below is not a clean result.** "
               "Check the run errors, then re-run analysis before treating "
               "\"{title}\" as cleared."),
    "skipped": ("*Not applicable to this script, so nothing was measured here. "
                "This says nothing either way about \"{title}\"*"),
    "pending": ("*This pass did not finish, so nothing here was assessed.*"),
}


def _empty_category_line(cat: str, outcomes: dict) -> str:
    """What an empty category means, given what the pass actually did."""
    title = CATEGORY_TITLES.get(cat, cat)
    outcome = outcomes.get(cat)
    if outcome in _OUTCOME_TEXT:
        return _OUTCOME_TEXT[outcome].format(title=title)
    if outcome == "ok":
        return ("*Analyzed, no findings.* The pass ran on this script and raised "
                "nothing in this category.")
    if outcome is None:
        # No record at all: either an older report, or a category that was not
        # requested. Neither is evidence of quality, so it may not read as one.
        return ("*Not analyzed in this run, so there is no assessment here — "
                "this is not a clean result.*")
    return f"*No findings recorded (pass outcome: {outcome}).*"


def _findings_by_category(findings: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for f in findings:
        grouped.setdefault(f.get("category", "other"), []).append(f)
    return grouped


def _format_finding(f: dict) -> str:
    scene_refs = f.get("scene_refs") or []
    scene_str = ", ".join(f"Scene {n}" for n in scene_refs) if scene_refs else "General"
    severity = f.get("severity", "medium").upper()
    verification = f.get("verification", {})
    badge = VERIFICATION_BADGE.get(verification.get("status"), "")

    note = verification.get("note")
    issue = f.get("issue", "").strip()
    why = f.get("why_it_matters", "").strip()

    if f.get("ungrounded"):
        badge += UNGROUNDED_BADGE
    if f.get("is_observation"):
        badge += OBSERVATION_BADGE
    lines = [f"**[{severity}] {scene_str}** — {issue}{badge}"]
    if why:
        lines.append(f"  - *Why it matters:* {why}")
    if note:
        lines.append(f"  - *{note}*")
    quote = f.get("evidence_quote")
    if quote and verification.get("status") == "verified":
        lines.append(f"  - Evidence: \"{quote}\"")
    return "\n".join(lines)


def render_markdown(result: AnalysisResult) -> str:
    doc = result.doc
    lines = []
    title = doc.title or doc.source_filename
    lines.append(f"# Script Doctor Report: {title}")
    if doc.author:
        lines.append(f"*by {doc.author}*")
    lines.append("")
    lines.append(f"**Parsed from:** `{doc.source_filename}` ({doc.source_format}, parse confidence: {doc.parse_confidence})")
    if result.model_used:
        lines.append(f"**Analyzed with:** `{result.model_used}`")
    else:
        # Gap 59: a legacy result carries no model record. Saying nothing lets
        # the reader assume the default (or whatever is configured now); saying
        # "unknown" is the only true statement, and it is what the HTML export's
        # banner says too, so the two artifacts agree.
        lines.append("**Analyzed with:** *not recorded* — this result does not say "
                     "which model produced it, so its provenance is unknown.")
    if model_is_stand_in(result.model_used):
        # Its own line, above everything the writer is about to read, because
        # the whole report's standing changes: this is a demo of the machinery,
        # not a reading of their script. Rendered from the run's record, so an
        # exported copy stays honest after the demo setting is turned off.
        lines.append("")
        lines.append(
            "> ⚠️ **This report was produced by the built-in demo model, not a "
            "real analysis.** The studio's analysis engine ran end to end, but "
            "the findings, coverage and craft notes below came from a stand-in "
            "model that reads the script only superficially. Do not use them to "
            "judge your screenplay. Run the analysis against your configured "
            "model to get a real reading.")
        lines.append("")
    lines.append(f"**Scenes:** {doc.scene_count} | **Characters:** {len(doc.all_characters)}")
    if doc.estimated_page_count:
        lines.append(f"**Estimated pages:** {doc.estimated_page_count}")
    lines.append("")

    if result.errors:
        lines.append("## ⚠️ Analysis Warnings")
        for e in result.errors:
            lines.append(f"- {e}")
        lines.append("")

    if result.notices:
        # M2: recoveries get their own voice, distinct from warnings — the
        # writer should know a pass wobbled and landed, not that something
        # is wrong with their script.
        lines.append("## ℹ️ Run Notes")
        for n in result.notices:
            lines.append(f"- {n}")
        lines.append("")
    # A caveat, not a warning — see `AnalysisResult.recoveries`. Rendered apart
    # from the warning block on purpose: nothing failed, and a report that shouts
    # "warning" at a split trains the writer to ignore the block that does mean it.
    if getattr(result, "recoveries", None):
        lines.append("## Notes on this run")
        for n in result.recoveries:
            lines.append(f"- {n}")
        lines.append("")

    # --- Coverage ---
    if result.coverage:
        cov = result.coverage
        rec = (cov.get("recommendation") or "").upper()
        lines.append("## Coverage")
        lines.append(f"**Recommendation: {rec}**")
        lines.append("")
        lines.append(f"**Logline:** {cov.get('logline', '')}")
        lines.append(f"**Genre:** {cov.get('genre', '')}  |  **Tone:** {cov.get('tone', '')}")
        lines.append("")
        lines.append("**Synopsis:**")
        lines.append(cov.get("one_page_synopsis", ""))
        lines.append("")
        if cov.get("strengths"):
            lines.append("**Strengths:**")
            for s in cov["strengths"]:
                lines.append(f"- {s}")
            lines.append("")
        if cov.get("weaknesses"):
            lines.append("**Weaknesses:**")
            for w in cov["weaknesses"]:
                lines.append(f"- {w}")
            lines.append("")
        if cov.get("comparable_films"):
            lines.append(f"**Comparable films:** {', '.join(cov['comparable_films'])}")
            lines.append("")

    # --- Logline test ---
    if result.logline_test:
        lt = result.logline_test
        lines.append("## Logline Test")
        signal = (lt.get("signal") or "").upper()
        lines.append(f"**Signal: {signal}** — {lt.get('logline', '')}")
        lines.append("")
        if lt.get("what_works"):
            lines.append(f"**What works:** {lt['what_works']}")
        if lt.get("what_muddles"):
            lines.append(f"**What muddles it:** {lt['what_muddles']}")
        if lt.get("missing"):
            lines.append(f"**What a clean logline needs that's missing:** {lt['missing']}")
        if lt.get("tightened"):
            lines.append(f"**Tightened example (your premise intact):** {lt['tightened']}")
        lines.append("")

    # --- Character-perception read ---
    if result.character_reads:
        lines.append("## How the Characters Read")
        lines.append(
            "*An impartial first-time reader's impression of each main character "
            "— what they actually come across as, vs. what the script appears "
            "to intend.*"
        )
        lines.append("")
        for r in result.character_reads:
            name = r.get("character", "?")
            lines.append(f"### {name}")
            lines.append(f"**Reads as:** {r.get('how_reads', '')}")
            lines.append(f"**Apparent intent:** {r.get('apparent_intent', '')}")
            lines.append(f"**The gap:** {r.get('gap', '')}")
            v = r.get("verification", {})
            badge = VERIFICATION_BADGE.get(v.get("status"), "")
            quote = r.get("evidence_quote")
            if quote and v.get("status") == "verified":
                lines.append(f"- Evidence: \"{quote}\"")
            elif quote:
                lines.append(f"- Evidence (unverified): \"{quote}\"{badge}")
            lines.append("")

    # --- Analysis categories ---
    grouped = _findings_by_category(result.findings)
    lines.append("## Detailed Analysis")
    # Gap 87: state the unsupported count where the list is printed, so a writer
    # scanning the report knows how much of what follows rests on nothing they
    # can check. Every finding is still rendered — this quotes the proportion
    # rather than quietly dropping rows from the export.
    unsupported = [f for f in result.findings if isinstance(f, dict) and f.get("ungrounded")]
    if unsupported:
        lines.append(
            f"*{len(unsupported)} of {len(result.findings)} notes below are "
            f"**unsupported**: they cite no quote or observation from your script. "
            f"They are marked ⚠️ in place, are held to low severity, and are "
            f"hidden by default in the Fix Queue. Treat them as questions, not "
            f"findings.*")
        lines.append("")
    outcomes = dict(getattr(result, "category_outcomes", None) or {})
    for cat, cat_title in CATEGORY_TITLES.items():
        cat_findings = grouped.get(cat, [])
        lines.append(f"### {cat_title}")
        if cat_findings:
            for f in cat_findings:
                lines.append(_format_finding(f))
        else:
            lines.append(_empty_category_line(cat, outcomes))
        lines.append("")

    # --- Setup / Payoff ledger (end-of-pipeline whole-script audit) ---
    if result.setup_payoff:
        lines.append("## Setup / Payoff")
        lines.append(
            "*The final whole-script audit: what the story set up and whether it "
            "ever came back — paid, still dangling, abandoned, or a deliberate "
            "red herring. Dangling/abandoned entries also appear in the Plot "
            "Economy findings above so they can be worked in the Fix Queue.*"
        )
        lines.append("")
        STATUS_LABEL = {
            "paid": "✅ Paid off", "dangling": "🚩 Dangling",
            "abandoned": "🪦 Abandoned", "red_herring": "🪄 Red herring",
        }
        for e in result.setup_payoff:
            setup_scenes = e.get("setup_scenes") or []
            setup_str = ", ".join(f"Scene {n}" for n in setup_scenes) if setup_scenes else "General"
            payoff = e.get("payoff_scenes")
            if payoff:
                payoff_str = ", ".join(f"Scene {n}" for n in payoff)
            else:
                payoff_str = "never"
            kind = e.get("kind") or "other"
            lines.append(f"**{STATUS_LABEL.get(e.get('status'), e.get('status', ''))}** — {e.get('setup', '')} "
                        f"({kind}; set up in {setup_str}; payoff: {payoff_str})")
            note = (e.get("note") or "").strip()
            if note:
                lines.append(f"  - {note}")
            lines.append("")

    # --- Story mechanics (deterministic reveal scan) ---
    if getattr(result, "reveal_candidates", None):
        lines.append("## Story mechanics worth a second look")
        lines.append(
            "*Single lines that may flip the story's meaning (a dream, a "
            "waking, a death undone). Found by text scan, not judgment — "
            "check them against the pages before believing any finding that "
            "contradicts one.*"
        )
        lines.append("")
        for c in result.reveal_candidates:
            lines.append(f"- Scene {c.get('scene')}: '{c.get('line', '')}'")
        lines.append("")

    # --- Confirmed twist (candidate-gated probe call) ---
    twist = getattr(result, "twist_verdict", None)
    if isinstance(twist, dict) and twist.get("twist") is True:
        lines.append("## Confirmed twist — read everything after it twice")
        lines.append(
            f"A direct probe confirmed a {twist.get('kind', 'twist')} in "
            f"Scene {twist.get('scene')}: '{twist.get('line', '')}'. Findings "
            "that treat those events as literal waking-plot are suspect."
        )
        lines.append("")

    # --- Pacing (deterministic per-scene pace index) ---
    if result.pacing:
        # Gap 45: this block used to promise "where the script drags" and to
        # score scenes out of 100 as if the number measured drag. It measures a
        # RANK among this script's own scenes, from two counts, and it cannot
        # see dramatic movement at all. Said here so a writer reading the table
        # does not take the ordering for a judgement.
        lines.append("## Pacing — relative text density")
        lines.append("*Per-scene rank by counted words and the action/dialogue "
                     "split. This is a shape, not a verdict: a dialogue-driven "
                     "climax and a deliberately quiet scene both rank here.*")
        lines.append("")
        drags = [r for r in result.pacing if r.get("drag")]
        if drags:
            lines.append("**Slowest scenes (rank among this script's scenes):** " + ", ".join(
                f"Scene {r['scene_number']} "
                f"({r.get('pace_rank')}/{len([x for x in result.pacing if x.get('pace_score') is not None])})"
                for r in drags) + "")
        else:
            # "the script keeps its momentum" was a claim about the writing that
            # a word count cannot make.
            lines.append("*No scene stands out from its neighbours by this measure.*")
        lines.append("")

    # --- Character dials (model-scored trait poles) ---
    if result.character_dials:
        lines.append("## Character Dials")
        lines.append("*How each main character reads on the page, 1–10 per trait pole. "
                     "Diagnosis only — the dial shows the page, not the intent.*")
        lines.append("")
        for d in result.character_dials:
            lines.append(f"**{d.get('character', '')}**")
            for t in d.get("traits") or []:
                refs = t.get("scene_refs") or []
                ref_str = f" (scenes {', '.join(str(n) for n in refs)})" if refs else ""
                note = (t.get("note") or "").strip()
                note_str = f" — {note}" if note else ""
                lines.append(f"- {t.get('trait', '')}: **{t.get('score')}/10**{ref_str}{note_str}")
            lines.append("")

    # --- Formatting (deterministic) ---
    lines.append("### Formatting & Industry Standards")
    if not result.formatting_findings:
        lines.append("*No formatting issues detected.*")
    else:
        for f in result.formatting_findings:
            scene_refs = f.get("scene_refs") or []
            scene_str = ", ".join(f"Scene {n}" for n in scene_refs) if scene_refs else "General"
            lines.append(f"**[{f.get('severity', 'low').upper()}] {scene_str}** — {f.get('message', '')}")
    lines.append("")

    # --- Acts ---
    st = result.stats
    acts = st.get("acts") or []
    if acts:
        lines.append("## Structure at a Glance")
        lines.append("### Acts")
        for a in acts:
            pages = f"pp. {a['page_start']}–{a['page_end']}" if a["page_start"] else ""
            if not a["scene_numbers"]:
                lines.append(f"**{a['name']}** (no scenes in this range)")
                continue
            lines.append(f"**{a['name']}** ({a['scene_count']} scenes, {pages}): Scenes {a['scene_numbers'][0]}–{a['scene_numbers'][-1]}")
        lines.append("")
        pacing = st.get("pacing") or {}
        segments = pacing.get("segments", [])
        if segments:
            lines.append("### Pacing (dialogue vs action words per segment)")
            lines.append("| Pages | Dialogue | Action | Scenes |")
            lines.append("|---|---|---|---|")
            for seg in segments:
                # Gap 27: a segment holding part of a scene that crosses its
                # boundary gets an ESTIMATED share of that scene's words, and
                # the row says so. Printing a split number as if it were
                # counted would be the same claim-to-precision this row had
                # wrong when it charged the whole scene to one side.
                mark = " ~" if seg.get("spans_boundary") else ""
                lines.append(
                    f"| {seg['page_start']}–{seg['page_end']} | "
                    f"{seg['dialogue_words']}{mark} | {seg['action_words']}{mark} | "
                    f"{seg['scene_count']} |")
            if pacing.get("weighted"):
                lines.append("")
                lines.append("~ includes part of a scene that crosses this segment's "
                             "boundary — those words are split by page span, so the "
                             "figure is an estimate, not a count.")
            lines.append("")
        arcs = st.get("character_arc") or []
        if arcs:
            lines.append("### Character Presence")
            lines.append("| Character | First scene | Last scene | Scenes | Dialogue lines |")
            lines.append("|---|---|---|---|---|")
            for c in arcs[:12]:
                lines.append(f"| {c['character']} | {c['first_scene']} | {c['last_scene']} | {c['scene_count']} | {c['dialogue_lines']} |")
            lines.append("")

    # --- Analytics ---
    lines.append("## Analytics")
    if st.get("character_stats", {}).get("characters"):
        lines.append("### Character Dialogue Share")
        lines.append("| Character | Lines | Words | Scenes | Share |")
        lines.append("|---|---|---|---|---|")
        for c in st["character_stats"]["characters"]:
            lines.append(
                f"| {c['character']} | {c['dialogue_lines']} | {c['dialogue_words']} | "
                f"{c['scenes_present']} | {c['dialogue_share_pct']}% |"
            )
        lines.append("")
    dar = st.get("dialogue_action_ratio", {})
    if dar.get("dialogue_pct") is not None:
        lines.append(f"**Dialogue/Action balance:** {dar['dialogue_pct']}% dialogue / {dar['action_pct']}% action")
        lines.append("")
    loc = st.get("location_usage", {})
    if loc.get("usage"):
        lines.append(f"**Unique locations:** {loc['unique_locations']}")
        lines.append("")
    tod = st.get("int_ext_and_time_breakdown", {})
    if tod.get("night_scene_pct") is not None:
        lines.append(f"**Night scenes:** {tod['night_scene_pct']}% of the script")
        lines.append("")

    # --- Verification summary ---
    v = result.verification
    if v:
        total = sum(v.values())
        lines.append("## Evidence Verification")
        lines.append(
            f"Of {total} model-generated findings: **{v.get('verified', 0)} had citations verified "
            f"against the actual script text**, **{v.get('not_found', 0)} had citations that could not "
            f"be confirmed**, and {v.get('no_quote', 0)} were cited by scene number only (no quote — "
            f"expected for theme/character/structure/scene-function findings, which reason from scene "
            f"summaries rather than full text)."
        )
        if v.get("scene_not_found", 0):
            lines.append(
                f"\n**{v.get('scene_not_found', 0)} findings cite scenes that do not exist in the "
                "script** (⚠️ flagged in place). Quote-less findings cite scene numbers — those "
                "numbers are checked too, and a citation that cannot exist reads as unverified, "
                "not as quietly fine."
            )
        # The one number a writer can act on: of the findings whose citation a
        # machine CAN judge (they carry a quotable line), how many held up.
        # Deliberately absent when nothing was quote-checkable — a percentage
        # over nothing is a lie (verifier.verification_rate owns the rule).
        rate = verification_rate(v)
        if rate["quote_bearing"]:
            lines.append(
                f"\n**Quote-verified rate: {rate['verified_pct_of_quoted']}%** "
                f"({v.get('verified', 0)} of {rate['quote_bearing']} findings that cite quotable "
                "text; summary-reasoned findings cite scene numbers and are excluded)."
            )
        # Evidence depth (§5 item 4): the paragraph above describes the ceiling in
        # prose; this states its SIZE. A count is what makes an invisible
        # false-negative risk visible — "reason from scene summaries" is a caveat,
        # "18 of 30 came from a summary" is a scope.
        depth = (result.stats or {}).get("evidence_depth") or {}
        if depth.get("total"):
            mixed = depth.get("overview_and_checkpoints", 0)
            scenes = ((result.stats or {}).get("checkpoint_coverage") or {}).get("scenes") or []
            line = (
                f"\n**Evidence depth:** of {depth['total']} findings, "
                f"**{depth.get('full_text', 0)} came from the full script text** and "
                f"**{depth.get('overview', 0)} from scene summaries**"
            )
            if mixed:
                # §5 item 2: these passes read the summaries AND the raw pages of a
                # bounded set of key scenes. Named, because "we read some of your
                # pages" is a scope the writer is entitled to see — and the scene
                # numbers are the difference between a claim and a check.
                where = f" (scenes {', '.join(str(n) for n in scenes)})" if scenes else ""
                line += (f", and **{mixed} from scene summaries plus the raw pages of the "
                         f"key scenes{where}**")
            line += (
                " — a description of the script rather than the script itself. Treat the "
                "summary-derived groups as a second opinion on structure, not as a reading "
                "of your pages."
            )
            lines.append(line)
            if depth.get("unknown"):
                # Never fold an unattributed pass into either side: a pass that
                # forgot to declare its source must not read as full-text.
                lines.append(
                    f"\n*{depth['unknown']} finding(s) could not be attributed to a pass — "
                    f"reported here rather than counted as either.*"
                )
        if v.get("not_found", 0) > 0:
            lines.append(
                "\n*Unverified findings are kept in the report above (marked ⚠️) rather than "
                "silently dropped — the underlying observation may still be valid even where "
                "the model's exact quote couldn't be confirmed.*"
            )
        if result.withdrawals:
            # The integrity gate removed these from the delivered set — a
            # mechanically false finding, or a duplicate folded into another.
            # Counted in the human report too, not only the JSON ledger, so
            # "nothing lost" is visible to the writer and not just checkable by
            # a test.
            n_rej = sum(1 for w in result.withdrawals if w.get("action") == "reject")
            n_mrg = sum(1 for w in result.withdrawals if w.get("action") == "merge")
            bits = []
            if n_rej:
                bits.append(f"{n_rej} withdrawn as mechanically false")
            if n_mrg:
                bits.append(f"{n_mrg} folded into a duplicate")
            lines.append(
                f"\n**Integrity gate:** {len(result.withdrawals)} finding(s) left the delivered "
                f"set ({'; '.join(bits)}). Nothing was deleted — each is kept with its reason "
                "and full text in `report.findings.json` under `withdrawals`."
            )
        lines.append("")

    return "\n".join(lines)


def _observation_coverage(findings: list) -> dict:
    """Gate 11: the share of the delivered set carrying a checkable observation.

    A quote makes a finding citable; an observation makes it FALSIFIABLE — the
    contract (Law V″) is that every finding reduces to one. Reported beside the
    quote rate because they answer different questions: "can I find the line?"
    versus "can I check the claim?" `None` until at least one finding exists — a
    percentage over nothing is a lie (the same rule `verification_rate` owns).
    """
    total = len(findings or [])
    bearing = sum(1 for f in (findings or [])
                  if isinstance(f, dict) and (f.get("observation") or "").strip())
    return {"observation_bearing": bearing,
            "observation_pct": round(100.0 * bearing / total, 1) if total else None}


def document_digest(doc) -> str:
    """A stable fingerprint of the EXACT document a run read (gap 2).

    The digest is taken over the parsed text, not over the file bytes: the same
    screenplay saved by a newer `save()` (an added field, a re-ordered key) must
    still be recognisably the same reading, while any change the writer or the
    parser makes to the words must change it. Findings hang off this digest, so
    "which script was this note about" is answerable from the report alone.

    Deliberately excludes `source_filename` and `warnings`: renaming a file does
    not change the screenplay, and parser warnings are advice about the parse,
    not content.
    """
    import hashlib
    import json as _json
    payload = {
        "title": getattr(doc, "title", None),
        "scenes": [
            {"heading": getattr(s, "heading_raw", None),
             "elements": [[getattr(e.type, "value", str(e.type)), e.text]
                          for e in s.elements]}
            for s in doc.scenes
        ],
    }
    blob = _json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()[:32]


def to_findings_json(result: AnalysisResult) -> dict:
    """Machine-readable version for Piece 3 to load and reference by scene/finding."""
    # HIGH-1: every finding carries the slugline key of its scene, because the
    # writer's marks are keyed by the finding's content-hash id and content
    # alone collided (9 of 16 rows on Pain_3 shared one id). Stamped here, at
    # the one place a report is written, so the artifact is self-describing:
    # the desk, the fix queue and the client all read the same field instead of
    # each re-deriving a scene key (screenplay_parser/scenekey.py).
    from screenplay_parser.scenekey import scene_key_map, stamp_scene_keys
    return {
        # Gap 2: WHICH script this report is about, in the artifact itself. A
        # report that does not say which draft it read cannot be checked against
        # the draft on screen, and the desk would have to trust a manifest entry
        # that the next upload overwrites.
        "snapshot": {
            "digest": document_digest(result.doc),
            "title": result.doc.title,
            "scene_count": result.doc.scene_count,
        },
        "title": result.doc.title,
        "source_filename": result.doc.source_filename,
        "model_used": result.model_used,
        "coverage": result.coverage,
        "character_reads": result.character_reads,
        "logline_test": result.logline_test,
        "setup_payoff": result.setup_payoff,
        # Recall kit B2: deterministic reveal candidates. Serialized (not just
        # threaded into prompts) so the desk, the eval runner, and any reader
        # can see what the scan found — an unserialized scan is a silent one.
        "reveal_candidates": list(getattr(result, "reveal_candidates", None) or []),
        # Twist confirmation verdict (candidate-gated probe call). None unless
        # confirmed — served so the desk and eval can see the verdict.
        "twist_verdict": getattr(result, "twist_verdict", None),
        "character_dials": result.character_dials,
        "pacing": result.pacing,
        "findings": stamp_scene_keys(result.findings, scene_key_map(result.doc)),
        "formatting_findings": result.formatting_findings,
        "stats": result.stats,
        # The integrity gate's ledger: findings removed from the delivered set
        # (mechanically false, or folded duplicates), each with its reason and
        # full content. Served so "nothing lost" is checkable rather than
        # asserted — `findings` + `withdrawals` is the pre-gate list. Empty when
        # the gate is off. See screenplay_analyzer/finding_integrity.py.
        "withdrawals": result.withdrawals,
        # Counts by verification status plus the derived quote-verified rate
        # (verifier.verification_rate). Served as-is by /report, so the
        # writer's "how correct is this feedback" question has a computed
        # answer instead of a vibe.
        "verification_summary": {
            **(result.verification or {}),
            **verification_rate(result.verification),
            # Gate 11: the share of the delivered set carrying a checkable
            # observation. A quote makes a finding citable; an observation makes
            # it falsifiable, and the contract is that every finding reduces to
            # one. Reported beside the quote rate because they answer different
            # questions: "can I find the line?" versus "can I check the claim?"
            **_observation_coverage(result.findings),
        },
        "errors": result.errors,
        "notices": result.notices,
        # Caveats, not errors: a pass whose chunk had to be split mid-run. Kept
        # out of `errors` because that list is the orchestrator's partial-failure
        # signal and the desk's failure banner — a split means the pass succeeded
        # in smaller pieces, so dressing it as a failure is a false alarm. Its own
        # key so the writer can be told the finding set is path-dependent without
        # being told the run is broken.
        "recoveries": result.recoveries,
        # Gap 47: per-category outcome, so a JSON consumer can tell "read
        # clean" from "never ran". The markdown report reads the same dict.
        "category_outcomes": dict(getattr(result, "category_outcomes", None) or {}),
    }


def save_report(result: AnalysisResult, md_path: str, json_path: str) -> None:
    # Both writes go through a temp file + os.replace (M5b): a failure partway
    # through must never leave a truncated report.md or an unparseable
    # report.findings.json behind — the previous good report survives instead.
    _atomic_write_text(md_path, render_markdown(result))
    _atomic_write_text(json_path, json.dumps(to_findings_json(result), indent=2,
                                            ensure_ascii=False))
