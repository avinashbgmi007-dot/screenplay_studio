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
    mid-write leaves the PREVIOUS file intact instead of a torn or empty one.
    """
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
    "invalid_scene_ref": " ⚠️ *unverified — malformed scene citation*",
}

CATEGORY_TITLES = {
    "theme": "Theme & Subtext",
    "character": "Character Arcs & Consistency",
    "structure": "Structure & Pacing",
    "scene_function": "Scene Functionality",
    "continuity": "Continuity",
    "voice": "Voice & Idiolect",
    "subtext": "Subtext",
    "dialogue": "Dialogue & Action",
    "plot_thread": "Plot Economy (Setups, Payoffs & Chekhov's Gun)",
    "genre": "Genre Conventions",
}


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
        lines.append("## ℹ️ Run Notes")
        for n in result.notices:
            lines.append(f"- {n}")
        lines.append("")
    if getattr(result, "recoveries", None):
        lines.append("## Notes on this run")
        for n in result.recoveries:
            lines.append(f"- {n}")
        lines.append("")

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

    if result.character_reads:
        lines.append("## How the Characters Read")
        lines.append("*An impartial first-time reader's impression of each main character — what they actually come across as, vs. what the script appears to intend.*")
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

    grouped = _findings_by_category(result.findings)
    lines.append("## Detailed Analysis")
    for cat, cat_title in CATEGORY_TITLES.items():
        cat_findings = grouped.get(cat, [])
        lines.append(f"### {cat_title}")
        if not cat_findings:
            lines.append("*No significant findings.*")
        else:
            for f in cat_findings:
                lines.append(_format_finding(f))
        lines.append("")

    if result.setup_payoff:
        lines.append("## Setup / Payoff")
        lines.append("*Model assessments are proposals, not verified conclusions. A later match of setup terms is shown only as a candidate recurrence; it does not establish narrative payoff. Missing terms or citations cannot establish that a setup was abandoned.*")
        lines.append("")
        STATUS_LABEL = {
            "paid": "paid off", "dangling": "dangling",
            "abandoned": "abandoned", "red_herring": "red herring",
            "unverified": "unverified",
        }
        for e in result.setup_payoff:
            setup_scenes = e.get("setup_scenes") or []
            setup_str = ", ".join(f"Scene {n}" for n in setup_scenes) if setup_scenes else "not cited"
            model_status = e.get("model_status") or e.get("status") or "unverified"
            model_payoff = e.get("model_payoff_scenes")
            if model_payoff is None:
                model_payoff = e.get("payoff_scenes")
            if model_payoff:
                payoff_str = "model-cited " + ", ".join(f"Scene {n}" for n in model_payoff) + " (not verified)"
            else:
                payoff_str = "no payoff location verified"
            candidates = e.get("candidate_recurrence_scenes") or []
            if candidates:
                payoff_str += "; terms recur in " + ", ".join(f"Scene {n}" for n in candidates) + " (candidate only)"
            kind = e.get("kind") or "other"
            lines.append(f"**Model assessment (unverified): {STATUS_LABEL.get(model_status, model_status)}** — {e.get('setup', '')} "
                        f"({kind}; set up in {setup_str}; {payoff_str})")
            note = (e.get("model_note") if "model_note" in e else e.get("note")) or ""
            note = note.strip()
            if note:
                lines.append(f"  - Model note (unverified): {note}")
            verify_note = (e.get("verify_note") or "").strip()
            if verify_note:
                lines.append(f"  - Mechanical check: {verify_note}")
            lines.append("")

    if getattr(result, "reveal_candidates", None):
        lines.append("## Story mechanics worth a second look")
        lines.append("*Single lines that may flip the story's meaning (a dream, a waking, a death undone). Found by text scan, not judgment — check them against the pages before believing any finding that contradicts one.*")
        lines.append("")
        for c in result.reveal_candidates:
            lines.append(f"- Scene {c.get('scene')}: '{c.get('line', '')}'")
        lines.append("")

    twist = getattr(result, "twist_verdict", None)
    if isinstance(twist, dict) and twist.get("twist") is True:
        lines.append("## Confirmed twist — read everything after it twice")
        lines.append(f"A direct probe confirmed a {twist.get('kind', 'twist')} in Scene {twist.get('scene')}: '{twist.get('line', '')}'. Findings that treat those events as literal waking-plot are suspect.")
        lines.append("")

    if result.pacing:
        lines.append("## Pacing — where the script drags")
        lines.append("*Per-scene pace index (density × movement share). Scenes at or above the drag threshold run long with little on-page movement.*")
        lines.append("")
        drags = [r for r in result.pacing if r.get("drag")]
        if drags:
            lines.append("**Pace drags:** " + ", ".join(f"Scene {r['scene_number']} ({r['pace_score']:.0f}/100)" for r in drags))
        else:
            lines.append("*No pace drags detected — the script keeps its momentum.*")
        lines.append("")

    if result.character_dials:
        lines.append("## Character Dials")
        lines.append("*How each main character reads on the page, 1–10 per trait pole. Diagnosis only — the dial shows the page, not the intent.*")
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

    lines.append("### Formatting & Industry Standards")
    if not result.formatting_findings:
        lines.append("*No formatting issues detected.*")
    else:
        for f in result.formatting_findings:
            scene_refs = f.get("scene_refs") or []
            scene_str = ", ".join(f"Scene {n}" for n in scene_refs) if scene_refs else "General"
            lines.append(f"**[{f.get('severity', 'low').upper()}] {scene_str}** — {f.get('message', '')}")
    lines.append("")

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
                lines.append(f"| {seg['page_start']}–{seg['page_end']} | {seg['dialogue_words']} | {seg['action_words']} | {seg['scene_count']} |")
            lines.append("")
        arcs = st.get("character_arc") or []
        if arcs:
            lines.append("### Character Presence")
            lines.append("| Character | First scene | Last scene | Scenes | Dialogue lines |")
            lines.append("|---|---|---|---|---|")
            for c in arcs[:12]:
                lines.append(f"| {c['character']} | {c['first_scene']} | {c['last_scene']} | {c['scene_count']} | {c['dialogue_lines']} |")
            lines.append("")

    lines.append("## Analytics")
    if st.get("character_stats", {}).get("characters"):
        lines.append("### Character Dialogue Share")
        lines.append("| Character | Lines | Words | Scenes | Share |")
        lines.append("|---|---|---|---|---|")
        for c in st["character_stats"]["characters"]:
            lines.append(f"| {c['character']} | {c['dialogue_lines']} | {c['dialogue_words']} | {c['scenes_present']} | {c['dialogue_share_pct']}% |")
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

    v = result.verification
    if v:
        total = sum(v.values())
        lines.append("## Evidence Verification")
        lines.append(f"Of {total} model-generated findings: **{v.get('verified', 0)} had citations verified against the actual script text**, **{v.get('not_found', 0)} had citations that could not be confirmed**, and {v.get('no_quote', 0)} were cited by scene number only (no quote — expected for theme/character/structure/scene-function findings, which reason from scene summaries rather than full text).")
        if v.get("scene_not_found", 0):
            lines.append(f"\n**{v.get('scene_not_found', 0)} findings cite scenes that do not exist in the script** (⚠️ flagged in place). Quote-less findings cite scene numbers — those numbers are checked too, and a citation that cannot exist reads as unverified, not as quietly fine.")
        if v.get("invalid_scene_ref", 0):
            lines.append(f"\n**{v.get('invalid_scene_ref', 0)} finding(s) have malformed scene citations** that were left unnormalized and flagged in place.")
        rate = verification_rate(v)
        if rate["quote_bearing"]:
            lines.append(f"\n**Quote-verified rate: {rate['verified_pct_of_quoted']}%** ({v.get('verified', 0)} of {rate['quote_bearing']} findings that cite quotable text; summary-reasoned findings cite scene numbers and are excluded).")
        depth = (result.stats or {}).get("evidence_depth") or {}
        if depth.get("total"):
            mixed = depth.get("overview_and_checkpoints", 0)
            scenes = ((result.stats or {}).get("checkpoint_coverage") or {}).get("scenes") or []
            line = f"\n**Evidence depth:** of {depth['total']} findings, **{depth.get('full_text', 0)} came from the full script text** and **{depth.get('overview', 0)} from scene summaries**"
            if mixed:
                where = f" (scenes {', '.join(str(n) for n in scenes)})" if scenes else ""
                line += f", and **{mixed} from scene summaries plus the raw pages of the key scenes{where}**"
            line += " — a description of the script rather than the script itself. Treat the summary-derived groups as a second opinion on structure, not as a reading of your pages."
            lines.append(line)
            if depth.get("unknown"):
                lines.append(f"\n*{depth['unknown']} finding(s) could not be attributed to a pass — reported here rather than counted as either.*")
        if v.get("not_found", 0) > 0:
            lines.append("\n*Unverified findings are kept in the report above (marked ⚠️) rather than silently dropped — the underlying observation may still be valid even where the model's exact quote couldn't be confirmed.*")
        if result.withdrawals:
            n_rej = sum(1 for w in result.withdrawals if w.get("action") == "reject")
            n_mrg = sum(1 for w in result.withdrawals if w.get("action") == "merge")
            bits = []
            if n_rej:
                bits.append(f"{n_rej} withdrawn as mechanically false")
            if n_mrg:
                bits.append(f"{n_mrg} folded into a duplicate")
            lines.append(f"\n**Integrity gate:** {len(result.withdrawals)} finding(s) left the delivered set ({'; '.join(bits)}). Nothing was deleted — each is kept with its reason and full text in `report.findings.json` under `withdrawals`.")
        lines.append("")

    return "\n".join(lines)


def _observation_coverage(findings: list) -> dict:
    total = len(findings or [])
    bearing = sum(1 for f in (findings or [])
                  if isinstance(f, dict) and (f.get("observation") or "").strip())
    return {"observation_bearing": bearing,
            "observation_pct": round(100.0 * bearing / total, 1) if total else None}


def to_findings_json(result: AnalysisResult) -> dict:
    from screenplay_parser.scenekey import scene_key_map, stamp_scene_keys
    return {
        "title": result.doc.title,
        "source_filename": result.doc.source_filename,
        "model_used": result.model_used,
        "coverage": result.coverage,
        "character_reads": result.character_reads,
        "logline_test": result.logline_test,
        "setup_payoff": result.setup_payoff,
        "reveal_candidates": list(getattr(result, "reveal_candidates", None) or []),
        "twist_verdict": getattr(result, "twist_verdict", None),
        "character_dials": result.character_dials,
        "pacing": result.pacing,
        "findings": stamp_scene_keys(result.findings, scene_key_map(result.doc)),
        "formatting_findings": result.formatting_findings,
        "stats": result.stats,
        "withdrawals": result.withdrawals,
        "verification_summary": {
            **(result.verification or {}),
            **verification_rate(result.verification),
            **_observation_coverage(result.findings),
        },
        "errors": result.errors,
        "notices": result.notices,
        "recoveries": result.recoveries,
    }


def save_report(result: AnalysisResult, md_path: str, json_path: str) -> None:
    _atomic_write_text(md_path, render_markdown(result))
    _atomic_write_text(json_path, json.dumps(to_findings_json(result), indent=2,
                                            ensure_ascii=False))
