"""
Prompt templates. Two tiers, matching the hierarchical approach discussed:

- Scene-level ("dialogue" category): needs actual line-level text to judge
  on-the-nose dialogue, exposition dumps, and overwritten action — run in
  small scene chunks against full scene text.
- Script-level (theme / character / structure / scene_function): needs
  cross-script context but not full text everywhere — run once each
  against compact scene summaries, so the model can hold the whole
  script's shape in context without blowing the window on raw dialogue.

Every prompt instructs the model to ground findings in an exact quote and
scene number, since verifier.py depends on that to check the work.
"""

CITATION_INSTRUCTION = (
    "For every finding, split your observation into two fields: 'issue' (a short, "
    "specific label of what's wrong — one sentence) and 'why_it_matters' (the causal "
    "explanation — why this is actually a problem for the story, not just that it "
    "exists). Include the scene number(s) it applies to in scene_refs, and in "
    "evidence_quote include a short EXACT quote (word-for-word, under 15 words) "
    "copied directly from that scene's text that supports the finding. "
    "If a finding isn't tied to specific quotable text, set evidence_quote to null. "
    "Never paraphrase inside evidence_quote — it must be verbatim or it will be rejected. "
    "If a specific named principle below grounds this finding, set rule_id to that "
    "principle's id; otherwise set rule_id to null. "
    "Diagnosis only — do not propose fixes or suggest how to resolve the issue; "
    "that happens in a separate conversation, not in this report."
)

# Script-level categories (theme/character/structure/scene_function) only ever see
# compact scene SUMMARIES below, never the screenplay's actual dialogue/action text —
# so asking them for a verbatim quote from the original script would be asking them
# to fabricate one. Their citation mechanism is the scene number, not a quote.
CITATION_INSTRUCTION_SUMMARY = (
    "For every finding, split your observation into two fields: 'issue' (a short, "
    "specific label of what's wrong — one sentence) and 'why_it_matters' (the causal "
    "explanation — why this is actually a problem for the story, not just that it "
    "exists). Include the specific scene number(s) it applies to in scene_refs — that "
    "is your citation, and it's what lets someone go verify the finding directly. You "
    "are working from scene SUMMARIES below, not the original screenplay text, so you "
    "have not seen the actual dialogue/action lines — always set evidence_quote to "
    "null. Do not invent a quote. If a specific named principle below grounds this "
    "finding, set rule_id to that principle's id; otherwise set rule_id to null. "
    "Diagnosis only — do not propose fixes or suggest how to resolve the issue; "
    "that happens in a separate conversation, not in this report."
)

CONFIDENCE_TIER_INSTRUCTION = (
    "Each principle below is tagged with a confidence_tier. For 'high' or 'medium' "
    "tier principles, state findings directly. For 'low' tier principles, phrase the "
    "finding as a genuine open question for the writer rather than an assertion of "
    "fact — these are judgment calls even a human script consultant would frame as "
    "'worth considering', not verdicts."
)


def scene_summary_prompt(scenes_chunk: list[dict]) -> tuple[str, str]:
    system = (
        "You are a script analyst assistant. Summarize each screenplay scene in 1-2 "
        "plain sentences: what happens, who's involved, and its narrative purpose. "
        "Be concise and factual — no evaluation, just what happens. "
        "Respond only with JSON matching the required schema."
    )
    parts = []
    for s in scenes_chunk:
        parts.append(
            f"Scene {s['scene_number']} — {s['heading_raw']}\n"
            f"Characters: {', '.join(s['characters_present']) or 'none'}\n"
            f"{s['full_text']}\n"
        )
    user = "Summarize each of these scenes:\n\n" + "\n---\n".join(parts)
    return system, user


def dialogue_analysis_prompt(scenes_chunk: list[dict], rules_fragment: str = "", chekhov_fragment: str = "") -> tuple[str, str]:
    system = (
        "You are a professional script doctor reviewing dialogue and action lines. "
        "For the scenes below, identify specific issues.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        "Additionally, watch for objects/details given STRONG narrative emphasis "
        "within a single scene (camera lingers on it, a character reacts strongly, "
        "dialogue calls explicit attention to it) — even if you only see it in one "
        "scene here. This is the single-scene half of Chekhov's Gun detection: a "
        "cross-scene tracker already catches objects that recur; it structurally "
        "cannot catch something given enormous weight in just one scene. Be "
        "conservative — most objects mentioned in a scene are just set dressing, "
        "not a planted setup. Only flag if the emphasis is genuinely strong. Use "
        "category \"plot_thread\" and rule_id \"chekhovs_gun\" for these.\n\n"
        f"{chekhov_fragment}\n\n"
        "Only flag genuine issues — don't manufacture findings if the writing is fine. "
        f"{CITATION_INSTRUCTION} Use category \"dialogue\" for dialogue/action findings. "
        "Respond only with JSON matching the required schema."
    )
    parts = []
    for s in scenes_chunk:
        parts.append(f"Scene {s['scene_number']} — {s['heading_raw']}\n{s['full_text']}\n")
    user = "Review these scenes:\n\n" + "\n---\n".join(parts)
    return system, user


def theme_analysis_prompt(scene_overview: str, title: str, rules_fragment: str = "") -> tuple[str, str]:
    system = (
        "You are a professional script doctor analyzing theme and subtext across an "
        "entire screenplay.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"theme\" for all findings. "
        "Respond only with JSON matching the required schema."
    )
    user = f"Screenplay: {title or '(untitled)'}\n\nScene-by-scene overview:\n\n{scene_overview}"
    return system, user


def character_analysis_prompt(scene_overview: str, title: str, characters: list[str], rules_fragment: str = "") -> tuple[str, str]:
    system = (
        "You are a professional script doctor analyzing character arcs across an "
        "entire screenplay. Focus on the characters with the most scene presence — "
        "don't force findings for minor characters.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"character\" for all findings. "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay: {title or '(untitled)'}\n"
        f"Characters: {', '.join(characters)}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def structure_analysis_prompt(scene_overview: str, title: str, total_scenes: int, estimated_pages, rules_fragment: str = "") -> tuple[str, str]:
    page_note = f"~{estimated_pages} pages" if estimated_pages else "page count unknown"
    system = (
        "You are a professional script doctor analyzing structure and pacing.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"structure\" for all findings. "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay: {title or '(untitled)'} — {total_scenes} scenes, {page_note}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def scene_function_prompt(scene_overview: str, title: str, rules_fragment: str = "") -> tuple[str, str]:
    system = (
        "You are a professional script doctor evaluating whether each scene earns "
        "its place. Be conservative: only flag a scene if you're genuinely confident "
        "it isn't pulling weight.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"scene_function\" for all findings. "
        "Respond only with JSON matching the required schema."
    )
    user = f"Screenplay: {title or '(untitled)'}\n\nScene-by-scene overview:\n\n{scene_overview}"
    return system, user


def principle_judgment_prompt(
    candidate_kind: str,
    candidate_name: str,
    mention_contexts: list[dict],
    rule_fragment: str,
    total_scenes: int,
) -> tuple[str, str]:
    """
    candidate_kind: "recurring_object" | "dialogue_promise"
    mention_contexts: list of {"scene": int, "text": str} — where this candidate
        was mentioned, straight from Piece 1's knowledge graph (real text, not
        a paraphrase, so the model is judging the actual script).
    """
    system = (
        "You are a script doctor applying a specific, named dramatic-economy "
        "principle to a candidate the screenplay parser flagged mechanically. "
        "The parser found the pattern; your job is the judgment call the parser "
        "can't make: was this actually given deliberate narrative weight (not "
        "just incidental description), and if so, was it paid off by the end of "
        "the script?\n\n"
        f"{rule_fragment}\n\n"
        "Be conservative on 'significant' — most recurring objects/lines are NOT "
        "meaningful setups, just ordinary continuity (a character's car, a "
        "recurring location). Only mark significant=true if the mentions show "
        "genuine narrative emphasis (visual focus, a character reacting strongly, "
        "dialogue calling attention to it). Your job here is diagnosis only — "
        "explain in 'reasoning' what the emphasis was and, if unresolved, why "
        "that matters. Do NOT propose how to fix it; that's a separate "
        "conversation the writer has if and when they want it. "
        "Respond only with JSON matching the required schema."
    )
    contexts_text = "\n".join(f"Scene {c['scene']}: {c['text']}" for c in mention_contexts)
    kind_label = "a recurring object/detail" if candidate_kind == "recurring_object" else "a dialogue promise"
    user = (
        f"This is {kind_label}: \"{candidate_name}\"\n"
        f"Script has {total_scenes} scenes total.\n\n"
        f"All mentions found:\n{contexts_text}"
    )
    return system, user


def coverage_prompt(scene_overview: str, title: str, author: str) -> tuple[str, str]:
    system = (
        "You are writing professional script coverage, the standard industry format "
        "used by studios and agencies to quickly assess a screenplay. Be honest and "
        "specific, not generically positive. recommendation must be exactly one of "
        "\"pass\", \"consider\", or \"recommend\". "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Title: {title or '(untitled)'}\nAuthor: {author or '(unknown)'}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user
