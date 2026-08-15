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

# Report language: the analysis report (findings, coverage) can be produced in
# English (default), Tenglish (Telugu spoken-lines written in the Latin/Roman
# alphabet — the everyday writing style of Telugu screenwriting), Hindi
# (Devanagari), or Tamil. The instruction is appended to every category prompt.
# evidence_quote is exempt: quotes must stay verbatim from the script so the
# verifier can check them.
REPORT_LANGUAGES = {
    "eng": "",
    "tenglish": (
        "\n\nIMPORTANT — Write your entire response in Tenglish: Telugu (and Hindi, where "
        "natural) rendered in the Latin/Roman alphabet exactly as spoken in everyday "
        "Telugu conversation, e.g. \"ippativarku Siddharth unconscious unnadani cheppaledu\", "
        "\"noppi ni feel avvaledu\". Keep English for technical craft terms (scene, act, "
        "arc, pacing, premise). Exception: evidence_quote must remain verbatim from the "
        "script, never translated."
    ),
    "hindi": (
        "\n\nIMPORTANT — Write your entire response in Hindi, in Devanagari script. "
        "Keep English for technical craft terms (scene, act, arc, pacing, premise). "
        "Exception: evidence_quote must remain verbatim from the script, never translated."
    ),
    "telugu": (
        "\n\nIMPORTANT — Write your entire response in Telugu, in Telugu script (తెలుగు). "
        "Keep English for technical craft terms (scene, act, arc, pacing, premise). "
        "Exception: evidence_quote must remain verbatim from the script, never translated."
    ),
    "tamil": (
        "\n\nIMPORTANT — Write your entire response in Tamil, in Tamil script. "
        "Keep English for technical craft terms (scene, act, arc, pacing, premise). "
        "Exception: evidence_quote must remain verbatim from the script, never translated."
    ),
}


def language_instruction(language: str = "eng") -> str:
    """Suffix appended to category prompts to control the report's language.
    English (default) adds nothing, so existing behavior is unchanged."""
    return REPORT_LANGUAGES.get(language or "eng", "")


LANGUAGE_META_INSTRUCTION = (
    "Never comment on the script's LANGUAGE itself. Do not identify, classify, or "
    "speculate about what language or dialect the script is written in (e.g. \"reads "
    "as regional\", \"probably Telugu\", \"a South Indian language\", \"mixed "
    "language\", \"code-switching\"), and never mention subtitles, translation, or "
    "what non-native speakers will or won't understand. The writer knows what "
    "language their pages are in. Feedback is about story, character, dialogue, "
    "structure, and craft — nothing else."
)


def scene_summary_prompt(scenes_chunk: list[dict], language: str = "eng") -> tuple[str, str]:
    system = (
        "You are a script analyst assistant. Summarize each screenplay scene in 1-2 "
        "plain sentences: what happens, who's involved, and its narrative purpose. "
        "Be concise and factual — no evaluation, just what happens. "
        "Respond only with JSON matching the required schema."
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION}"
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


def dialogue_analysis_prompt(scenes_chunk: list[dict], rules_fragment: str = "", chekhov_fragment: str = "", language: str = "eng") -> tuple[str, str]:
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
        "Idiolect consistency: when the chunk spans several scenes, notice if a "
        "character's dialogue suddenly changes rhythm, vocabulary, or formality "
        "between scenes with no dramatic reason (a deliberate register shift under "
        "pressure is fine; a voice that silently swaps is a draft artifact). "
        f"{CITATION_INSTRUCTION} Use category \"dialogue\" for dialogue/action findings. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    parts = []
    for s in scenes_chunk:
        parts.append(f"Scene {s['scene_number']} — {s['heading_raw']}\n{s['full_text']}\n")
    user = "Review these scenes:\n\n" + "\n---\n".join(parts)
    return system, user


def theme_analysis_prompt(scene_overview: str, title: str, rules_fragment: str = "", language: str = "eng") -> tuple[str, str]:
    system = (
        "You are a professional script doctor analyzing theme and subtext across an "
        "entire screenplay.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"theme\" for all findings. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = f"Screenplay: {title or '(untitled)'}\n\nScene-by-scene overview:\n\n{scene_overview}"
    return system, user


def character_analysis_prompt(scene_overview: str, title: str, characters: list[str], rules_fragment: str = "", language: str = "eng") -> tuple[str, str]:
    system = (
        "You are a professional script doctor analyzing character arcs across an "
        "entire screenplay. Focus on the characters with the most scene presence — "
        "don't force findings for minor characters.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"character\" for all findings. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay: {title or '(untitled)'}\n"
        f"Characters: {', '.join(characters)}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def structure_analysis_prompt(scene_overview: str, title: str, total_scenes: int, estimated_pages, rules_fragment: str = "", language: str = "eng") -> tuple[str, str]:
    page_note = f"~{estimated_pages} pages" if estimated_pages else "page count unknown"
    system = (
        "You are a professional script doctor analyzing structure and pacing.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        "Run the structural checkpoints explicitly before writing findings: "
        "(1) ACT ONE — does the premise land and the protagonist commit within the first "
        "quarter, with a clear point-of-no-return? (2) MIDPOINT — is there a real reversal "
        "around the middle that raises the stakes and changes the nature of the goal? "
        "(3) ACT TWO — does the middle escalate instead of treading water? (4) LOW POINT / "
        "DARKEST HOUR — does the protagonist hit a genuine bottom before the end? "
        "(5) CLIMAX & RESOLUTION — does the ending confront the central conflict head-on, "
        "and does it land where the story promised it would? Flag only checkpoints that "
        "are genuinely weak or missing — a quiet character piece may skip a textbook "
        "midpoint on purpose, so judge by whether the story earns its own shape, not by "
        "a formula.\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"structure\" for all findings. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay: {title or '(untitled)'} — {total_scenes} scenes, {page_note}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def logline_test_prompt(logline: str, scene_overview: str, title: str, language: str = "eng") -> tuple[str, str]:
    system = (
        "You are a professional script doctor. A logline's job is to land the whole "
        "premise in one sentence: a specific protagonist, a concrete want, a real "
        "obstacle, and stakes the audience can feel. Judge the screenplay's logline "
        "against that standard and report a signal: strong (it lands), workable "
        "(it mostly lands but needs tightening), or muddled (a reader can't tell "
        "what the movie is). Diagnose only — say what works, what muddles it, and "
        "which element(s) a clean logline needs that are missing. Offer one \"tightened\" "
        "example that keeps the writer's actual premise intact — never invent plot "
        "that isn't in the scene overview. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay: {title or '(untitled)'}\n\n"
        f"Current logline: {logline or '(none)'}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def character_reads_prompt(scene_overview: str, title: str, characters: list[str], language: str = "eng") -> tuple[str, str]:
    system = (
        "You are an impartial first-time reader — you have never met these characters "
        "and don't know what the writer intends. For each main character, report how "
        "they ACTUALLY come across on the page to a stranger (the impression their "
        "words and actions create), what the script appears to intend them to be, "
        "and the gap between the two. Be specific and evidence-anchored. If a "
        "character reads exactly as intended, say the gap is minimal — don't force "
        "a divergence. Only include characters with real scene presence. Diagnose "
        "only, never prescribe fixes. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay: {title or '(untitled)'}\n"
        f"Characters: {', '.join(characters)}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def scene_function_prompt(scene_overview: str, title: str, rules_fragment: str = "", language: str = "eng") -> tuple[str, str]:
    system = (
        "You are a professional script doctor evaluating whether each scene earns "
        "its place. Be conservative: only flag a scene if you're genuinely confident "
        "it isn't pulling weight.\n\n"
        f"{rules_fragment}\n\n{CONFIDENCE_TIER_INSTRUCTION}\n\n"
        "Judge every scene you're unsure about against the stakes test: does the "
        "character want something concrete in this scene (WANT), is there a real "
        "obstacle or cost in the way (OBSTACLE), and does something actually change "
        "by the scene's end (CHANGE)? A scene where want, obstacle, or change is "
        "missing is a candidate for the cut or the merge — name which of the three "
        "is missing in the finding.\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"scene_function\" for all findings. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
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
    language: str = "eng",
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
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
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


def setup_payoff_ledger_prompt(
    scene_overview: str,
    seed_block: str,
    rule_fragment: str = "",
    total_scenes: int = 0,
    language: str = "eng",
) -> tuple[str, str]:
    """The final whole-script audit. Unlike the Principles Engine's
    per-candidate judgment (which sees only a candidate's own mentions), this
    runs with the entire script's scene-by-scene overview in context, so
    'paid off?' is judged against the actual arc, not a snippet."""
    system = (
        "You are a script doctor doing the FINAL setup/payoff audit of a complete "
        "screenplay. You have read the whole story below, scene by scene. Your job "
        "is the ledger every consultant keeps at the end of a read: what did the "
        "story set up, and did it ever come back?\n\n"
        "A setup is anything given narrative weight with the clear shape of a "
        "promise: an object the camera lingers on or a character reacts to, a "
        "dialogue promise ('I'll tell you everything'), a stated goal or deadline, "
        "a relationship or secret the script makes us wait for. A payoff is the "
        "moment the promise lands — the object is used, the information is "
        "delivered, the goal is confronted.\n\n"
        "Mechanically-flagged candidates from the parser are listed below — treat "
        "them as leads, NOT verdicts: most are ordinary continuity, and only some "
        "are true setups. Judge each against the WHOLE arc. Also add any true "
        "setups the list missed that you can see clearly in the overview (a "
        "thematic promise, an emphasized object that never recurs, a secret the "
        "story abandons).\n\n"
        "Use the four statuses precisely:\n"
        "- paid: set up, and the script delivers on it (cite the payoff scene).\n"
        "- dangling: set up with real weight and never paid off — this is the "
        "finding the writer needs.\n"
        "- abandoned: set up, then the story simply stops caring (no payoff, but "
        "lower emotional cost than dangling — flag it anyway).\n"
        "- red_herring: deliberately planted to mislead, and that misdirection "
        "itself resolves — this is a legit exception, not an error.\n\n"
        "Be conservative and specific: a passing mention is NOT a setup. Only "
        "include entries you can point at in the overview. Keep notes to one or "
        "two sentences, named to the scene where the reader can feel it. Cite "
        "scene numbers from the overview, never invented ones. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Screenplay has {total_scenes} scenes.\n\n"
        f"MECHANICALLY FLAGGED CANDIDATES (leads, not verdicts):\n{seed_block}\n\n"
        f"THE WHOLE STORY, SCENE BY SCENE:\n{scene_overview}\n\n"
        "Now produce the setup/payoff ledger for this script."
    )
    return system, user


def genre_check_prompt(genre: str, conventions: list[str], scene_overview: str, language: str = "eng") -> tuple[str, str]:
    conventions_text = "\n".join(f"- {c}" for c in conventions)
    system = (
        "You are a genre specialist checking whether this screenplay delivers on its "
        "genre's audience expectations. The conventions below are expectations to "
        "test, not rules to obey — a great script can violate any of them on purpose. "
        "For each one, judge whether the script delivers, misses, or deliberately "
        "subverts it. Only report findings that are genuinely actionable or genuinely "
        "notable — don't manufacture findings for conventions the script simply "
        "doesn't emphasize. When a miss looks like a deliberate choice, say so.\n\n"
        f"CONVENTIONS TO TEST ({genre or 'unknown genre'}):\n{conventions_text}\n\n"
        f"{CITATION_INSTRUCTION_SUMMARY} Use category \"genre\" for all findings. "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        "Evaluate this screenplay against the genre conventions above. "
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user


def coverage_prompt(scene_overview: str, title: str, author: str, language: str = "eng") -> tuple[str, str]:
    system = (
        "You are writing professional script coverage, the standard industry format "
        "used by studios and agencies to quickly assess a screenplay. Be honest and "
        "specific, not generically positive. recommendation must be exactly one of "
        "\"pass\", \"consider\", or \"recommend\". "
        f"{language_instruction(language)} {LANGUAGE_META_INSTRUCTION} "
        "Respond only with JSON matching the required schema."
    )
    user = (
        f"Title: {title or '(untitled)'}\nAuthor: {author or '(unknown)'}\n\n"
        f"Scene-by-scene overview:\n\n{scene_overview}"
    )
    return system, user
