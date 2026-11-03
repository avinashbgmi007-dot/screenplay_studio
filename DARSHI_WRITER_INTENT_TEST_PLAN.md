# Darshi — writer-intent quality test

**Status:** evaluation plan, not a model result or a diagnosis of the screenplay. The writer confirmed the intent in this conversation; the examples below must be checked against the PDF and by Telugu/Tenglish-capable readers.

## Confirmed creative intention

Darshi is not just a character out of a book: he embodies the impact a strong book character can have on a reader. After Ajay reads the book, Darshi comes out of it to help him; his influence lives on in Ajay's mind, asking questions, challenging or taunting him, and influencing the direction of his life. The story concerns that influence and Ajay's change. Returning the physical book does not end Darshi's impact.

**Protect:** the emotional magic and intended ambiguity. Do not equate preserving ambiguity with explaining nothing, or presume the writer's intention guarantees that every reader experiences it.

## Source anchors to verify

- PDF printed scene 5 / parsed internal scene 6: Ajay and Darshi's lake conversation.
- PDF printed scene 8 / parsed internal scene 9: Darshi's advice and Ajay's conversation with his father.
- PDF printed scene 10 / parsed internal scene 11: Ajay returns the book, asks why Darshi is still with him, and the final embrace of the book.

These are starting points, not a complete story map or proof of emotional impact. PDF parsing reported low confidence; its flashback markers were classified as characters, and internal numbering differs from printed numbering. A reader must check source page and scene references.

## Evaluation A — analysis

**Run two conditions on the same draft and model:** (1) no creative intention supplied, (2) the confirmed intention supplied. Label them clearly; do not judge the first run for lacking information it was never given. Repeat each condition where resources allow, and record model, settings, draft version, actual context coverage, latency and failure states. Provide context to all relevant passes, not only the final report.

Reviewers assess whether the result:

1. Separates page events from interpretations and cites relevant passages, including the ending when making ending claims.
2. Recognizes and preserves the intended role of Darshi when intention is supplied; asks instead of inventing the intention when it isn't.
3. Evaluates whether influence is dramatized through Ajay's choices, while recognizing that audience impact requires reader validation.
4. Does not automatically flag ambiguity or Darshi's presence as a continuity error or demand a literal explanation.
5. Can identify a meaningful concern **if genuinely supported**; it must not merely agree with or flatter the writer. Record counter-evidence and uncertainty.
6. Labels limited or truncated context and refuses definitive whole-story absence or ending claims when essential material wasn't seen.

Assess findings as correct / partial / incorrect / insufficient context; additionally rate relevance, usefulness, potential harm and missed important issues. Use independent judgments and note disagreement. No single example or script establishes accuracy.

## Evaluation B — Sushruta

Ask: “Darshi's influence stays with Ajay after the book is returned. Does the ending convey that?”

A good response distinguishes what the pages show from an untested audience interpretation, considers the lake conversation and final scene when available, acknowledges missing context, and offers a precise question for reader testing. If challenged with the writer's intention, Sushruta reassesses rather than defending the original finding. He may disagree constructively when he has evidence; he must not force a rewrite or erase uncertainty through voice post-processing.

## Evaluation C — Sameer

Ask: “Keep Darshi's magic and my intended ambiguity. Help me explore whether Ajay's change feels lived, not explained. Don't rewrite yet.”

A good response honors those constraints, engages with actual pages, listens, critiques or asks a useful question, and accepts “keep it as is” as a valid outcome. Do not volunteer solutions, suggestions or rewrites unless the writer explicitly asks; if asked, calibrate the depth and offer trade-offs rather than taking over. Answer direct questions directly rather than interrogating or withholding an answer. For an explicit rewrite proposal, compare it with the original and require the writer's approval.

## Evaluation D — handoff, UI and revision

- The writer can record, edit and remove the intent; it is identified as writer-stated, scoped to the relevant note/story and versioned—not an invented fact about the script or an immutable instruction.
- The finding, intent, original excerpts, internal and printed scene references, and context limitations carry to both partners. A finding's wording must never be labelled as a script quotation when no quote exists.
- Selecting a note does not presume it needs fixing. Disagreement and keeping the scene as written are first-class outcomes.
- Repeat with omitted scene evidence, a tight model context, a changed draft and a partner switch; disclose omissions, stale source and any ambiguous reconciliation. Passage change or disappearance of a note is not automatically resolution.
- Test actual audiences/readers, including Telugu/Tenglish speakers, for emotional impact and comprehension without giving them the intention first. Then discuss the intention separately. Avoid leading questions and preserve confidentiality.

## Self-critique

The source anchors were inspected from a low-confidence parse, not independently certified; do not use their wording as a quotation without PDF verification. Your intent is a vital reference, not a mandate that every reader interpret the ending identically. The design must still allow grounded dissent and cannot trade truth for agreement. No live model or human reader study was run here.

## Existing test coverage checked

Nine relevant existing test modules passed in a temporary environment: **211 passed** (PDF OCR, Indian languages, accuracy guards, observation contract, persona humanization, chat-language handling, language/human levers, cross-rule deduplication and consultant context). This selection overlaps the previously reported 166-test selection; do not add the totals. Examples covered include selected quotes reaching prompts, persona tagging, language detection, observation fields and preserved merged finding content.

Passing those tests does not validate this screenplay's flashback markers, reader intent, real model output or audience response. Add screenplay-specific regression fixtures only with the writer's permission and without committing their screenplay text. Planned synthetic tests: structural markers never become characters; printed and internal scene identifiers remain distinct; ending omissions surface in per-pass coverage; quote-less issue text cannot become a script excerpt; meaningful uncertainty survives persona transforms; writer intent and multi-scene evidence persist through handoff, trimming, session reload and version changes. Validate subjective outputs separately with consented human reviewers.

## Prompt-input trace on the attached PDF

Ran the actual `build_scene_summaries` and `run_dialogue_analysis` preparation paths with a recording-only client that returned empty placeholder arrays; no model was called and no findings or summaries were generated. Each made eight calls and included seven scene-truncation markers. Neither set of user prompts included the final action describing Ajay hugging the book as though embracing Darshi. The marker text appeared in both prompt sets. Summary calls requested the fast model tier; dialogue calls did not. The dialogue trace used an empty rules stub to inspect the scene input only, so it is not a full production prompt or a KB test.

Implication: the final action cannot inform these two model passes through their scene-text inputs. This does not establish what later passes or a real model might infer from other context. A redesigned evaluation should verify complete scene coverage through windows, evidence retrieval and explicit provenance, with the real model and writer-approved fixtures.

## Complete-scene coverage experiment — non-model, no implementation

For the actual parsed PDF, simulated simple 1,600-character windows with 250-character overlap within each scene. All 27,718 characters of parsed scene element text, including the ending, appear in at least one window; 24 windows contain 30,968 characters total (11.7% overlap overhead versus parsed source length). The current 2,200-character per-scene prefix covers 18,999 of 27,718 characters before adding markers. This experiment only counts characters; it does not measure tokens, model requests, GPU memory, latency, output quality, parser accuracy, or overhead from prompts and repeated KB fragments. It is not a production algorithm: arbitrary character cuts may divide words, dialogue cues, dramatic beats or graphemes, and overlapping windows can duplicate findings. A real design should preserve element/scene boundaries, record coverage, merge with reviewable provenance, protect whole-story and ending context separately, and benchmark costs against the current pipeline with a real model. Full parsed-text coverage does not correct mistakes from PDF extraction.

## Element-boundary window experiment

A second non-model simulation groups complete parsed elements into roughly 1,600-character windows with up to 250 characters of whole-element overlap. On this parse, all 26,776 nonempty element-text characters and all elements appeared in at least one of 24 windows; 29,650 element-text characters were included counting repetition, 10.7% overhead. This count excludes separators, so it is not directly the same denominator as the 27,718-character joined-text experiment. No element exceeded the size threshold in this screenplay.

Remaining defect: even element-boundary windows can begin inside an attributed dialogue or parenthetical passage. This occurred in four windows (internal scenes 6, 8, 9, 11), so an element boundary does not guarantee the character cue or conversation context is in the same window. Production design should group a character cue, parentheticals and associated dialogue, and give oversized groups an explicit continuation label; attach stable source IDs and scene/character context. Spot-check parser attribution first. Character counts do not predict token counts, calls or latency, and these simulations have not evaluated model judgment or finding duplication.

## Cue-and-dialogue grouping experiment

A further temporary, no-model simulation grouped each parsed character cue with the immediately following dialogue and parentheticals attributed to that character, then packed whole groups in approximately 1,600-character windows with up to 250 characters of whole-group overlap. On this low-confidence parse: 24 windows covered all 26,776 element-text characters, with 29,533 sent including overlap (10.3% element-text repetition); no group exceeded 1,600 characters, and no dialogue or parenthetical started without an immediately preceding attributable cue. These are properties of this parse, not proof the speaker attribution is correct. The code used for the one-off simulation is not a production implementation. It grouped other elements individually; action beats, cue interpretation, actual tokenization and oversized dialogue remain untested. Because the parser incorrectly categorizes flashback markers as character cues, grouping alone does not fix parser defects. No real-model calls, duplicate-finding assessment, or latency benchmarks were performed.

## Actual chat retrieval probe — real parsed PDF, no model

Using `ScriptContext` and `resolve_referenced_scenes` on the parsed PDF, with no selected quote and a four-scene cap:

- “Darshi’s influence continues with Ajay beyond the physical book. Does the ending convey that?” resolved internal scenes `[1, 3, 5, 6]`; the closing action was not in the scene context block.
- Even “In Scene 11, does the ending convey Darshi’s influence on Ajay?” resolved `[1, 3, 5, 6]`: the resolver sorts all references before slicing, so early character-associated scenes displace the explicit scene 11. This is an internal scene number, not a printed-scene-number claim.
- “What happens at the end?” resolved no scenes under this probe.

The character extractor also returned `AJAY` more than once and `AJAY'S FATHER` for a question mentioning Ajay, showing an additional relevance risk. Selected quotes can explicitly append their scene in the engine, and other report/summary context may still be present; these are not proofs of a final model response or total lack of ending knowledge. No model was called.

Recommended contract: retain explicit requested scene and selected evidence as priority; identify ending/beginning references; resolve printed vs internal IDs; choose additional context by relevance and story coverage rather than earliest scene order; account for token budget across system prompt, history, scene text and output; and disclose missing or ambiguous context. Regression-test the exact questions above, explicit scene 11, multiple explicit scenes over budget, selected quote, similarly named characters, long scenes and intent. Evaluate answer quality and latency with a real model; avoid claiming exact relevance or correctness from a retrieval test alone.

## Retrieval-priority experiment — real PDF, no model

A disposable local simulation preserved explicitly referenced internal scenes first, added the final parsed scene for simple English “end/ending/final scene” requests, then filled remaining slots from existing character matches. It did not alter application code.

- Writer's Darshi/ending question: current `[1, 3, 5, 6]`; experimental `[11, 1, 3, 5]`, with the closing action present.
- Explicit internal scene 11 and ending: current `[1, 3, 5, 6]`; experimental `[11, 1, 3, 5]`.
- “What happens at the end?”: current `[]`; experimental `[11]`.
- Compare internal scenes 6 and 11: current `[6, 8, 9, 11]`; experimental `[6, 11, 8, 9]`.

This verifies only selection and assembled scene-block content, not final prompt survival or model quality. The assembled block for the first query was about 13,526 characters before persona, report, history and output, potentially exceeding small context windows; other context might be shed or truncated. The character-based filler still picks earlier, not necessarily relevant scenes. The simple English ending regex will miss other phrasings and Telugu/Tenglish, printed numbers remain ambiguous, and if more explicit requests exist than slots the prototype does not disclose omissions. A production design must solve those issues, validate the parser, reserve token-budget space, and test with real models before claiming the ending informed an answer.
