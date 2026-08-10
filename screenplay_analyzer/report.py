"""
Assembles the human-readable .md report and the machine-readable findings
JSON (same content, structured — this is what Piece 3 loads to discuss
specific findings without re-parsing markdown) from an AnalysisResult.
"""

import json

from .pipeline import AnalysisResult

VERIFICATION_BADGE = {
    "verified": "",
    "not_found": " ⚠️ *unverified — quote not confirmed in cited scene(s)*",
    "no_quote": "",
    "scene_not_found": " ⚠️ *unverified — cited scene number doesn't exist*",
}

CATEGORY_TITLES = {
    "theme": "Theme & Subtext",
    "character": "Character Arcs & Consistency",
    "structure": "Structure & Pacing",
    "dialogue": "Dialogue & Action",
    "scene_function": "Scene Functionality",
    "plot_thread": "Plot Economy (Setups, Payoffs & Chekhov's Gun)",
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

    # --- Analysis categories ---
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

    # --- Analytics ---
    st = result.stats
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
        if v.get("not_found", 0) > 0:
            lines.append(
                "\n*Unverified findings are kept in the report above (marked ⚠️) rather than "
                "silently dropped — the underlying observation may still be valid even where "
                "the model's exact quote couldn't be confirmed.*"
            )
        lines.append("")

    return "\n".join(lines)


def to_findings_json(result: AnalysisResult) -> dict:
    """Machine-readable version for Piece 3 to load and reference by scene/finding."""
    return {
        "title": result.doc.title,
        "source_filename": result.doc.source_filename,
        "model_used": result.model_used,
        "coverage": result.coverage,
        "findings": result.findings,
        "formatting_findings": result.formatting_findings,
        "stats": result.stats,
        "verification_summary": result.verification,
        "errors": result.errors,
    }


def save_report(result: AnalysisResult, md_path: str, json_path: str) -> None:
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(result))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(to_findings_json(result), f, indent=2, ensure_ascii=False)
