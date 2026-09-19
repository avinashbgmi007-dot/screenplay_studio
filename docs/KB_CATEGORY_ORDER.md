# The nine craft levels, ordered high -> low

**Status: REVIEW ONLY. Nothing under `knowledge_base/` was changed by this pass.**

Companion files: `docs/kb_category_taxonomy_order.csv` (the same ordering, machine-readable),
`docs/KB_TIER_REVIEW.md` (the earlier tier proposal this note builds on).

---

## 0. What was asked, and the sort key I actually used

You asked for the rules in **theme, scene, character, dialogue, plot_thread, relationship,
revision, story_macro, structure_pacing** -- these nine alone -- sorted **high -> low per
taxonomy_level, w.r.t. the rule theory of its own category**.

That phrase admits two readings, and they give different orders, so I am stating mine up
front rather than hiding it:

| Reading | Sort key | What it answers |
|---|---|---|
| **A. Theory-first** (what I did) | the level's **governing principle** -> structural technique -> local execution check, then confidence tier | "What does this craft area actually rest on, and what is merely detail?" |
| B. Tier-first | confidence tier high -> medium -> low | "Which of these rules is the machine allowed to assert?" |

I chose **A** because your sentence qualifies "high to low" with *"w.r.t. the rule theory of
its own category"* -- i.e. the theory is the yardstick. Confidence tier is carried as a
column, not as the sort key. If you meant B, the CSV re-sorts with one line.

**The exact key:** theory band (G -> S -> E) -> `confidence_tier` (high -> medium -> low) ->
`severity_default` (high -> medium -> low) -> rule id.

**The bands are mine, not a KB field.** I invented them; they are a reading of each
category's own theory:

- **G -- Governing.** The principle everything else in the level derives from. You cannot
  fix a script that violates a G rule by changing anything downstream.
- **S -- Structural.** How the principle is turned into shape (acts, arcs, threads, turns).
- **E -- Execution.** A local, checkable craft detail.

The nine levels are then presented **macro -> micro**, because that is the order a script
actually gets built and the order a consultant actually reads it.

---

## 1. The nine levels as a scope ladder

Ordered from whole-story down to single-line. Rule counts and current tier mix are from the
KB as it stands; the last column is how many rules the *pending* tier proposal would move.

| # | Level | Scope | Rules | high/med/low now | tier moves pending | which pass receives it |
|---|---|---|---|---|---|---|
| 1 | `story_macro` | the whole story: premise, theme, world, tone, resolution | 21 | 17 / 1 / 3 | 16 down | theme pass (`["story_macro","theme"]`) |
| 2 | `theme` | what the story is *about* | 2 | 2 / 0 / 0 | 2 down | theme pass |
| 3 | `structure_pacing` | the story's shape over time | 28 | 21 / 4 / 3 | 21 down, 5 up | structure pass |
| 4 | `plot_thread` | causal threads that cross scenes | 39 | 33 / 3 / 3 | 30 down | plot_thread pass |
| 5 | `character` | one person across the whole story | 39 | 29 / 5 / 5 | 29 down | character pass |
| 6 | `relationship` | what happens *between* two people | 2 | 0 / 0 / 2 | **0** | character pass |
| 7 | `scene` | one unit of story | 34 | 26 / 5 / 3 | 26 down | scene_function pass |
| 8 | `dialogue` | one line | 23 | 20 / 2 / 1 | 19 down | dialogue pass |
| 9 | `revision` | the writer's own process + line prose | 4 | 2 / 2 / 0 | **0** | scene_function pass, **by filename not by level** |

192 of the KB's 263 rules live in these nine levels. The other 71 are `psychology` (58),
`nonverbal` (6), `continuity` (4), `pitch` (3) -- all reachable, none of them in scope here.

**Two structural facts in that table are worth more than the ordering itself:**

**(a) `revision` is not a routed level.** `rules_context.py` lists it in
`CATEGORY_TO_TAXONOMY_LEVELS` *and* in `UNROUTED_CATEGORIES`. Its four rules reach a prompt
only through `PASS_EXTRAS["scene_function"] = [..., "revision.json"]` -- that is, **by
filename, into the scene pass.** So `epps_revision_first_draft` ("First Draft Is Discovery,
Not Perfection") is injected as scene-level guidance, and the README's claim that
"`taxonomy_level` is the only routing axis" is not the whole truth: file extras route too.

**(b) `relationship` is the thinnest level and the only wholly unassertive one.** Two rules,
both `low`. Meanwhile `theme` -- arguably the most contested concept in the craft -- has two
rules, both `high`. The two levels with the least coverage sit at opposite ends of the
confidence scale, and the pending proposal changes **neither**.

---

## 2. Brainstorm -- Voice 1: the professional script consultant

This is the order a story editor actually works in, area by area: what they look at **first**,
what they would **never** state as fact, and how that area's own theory is internally ordered.
I have cited the rule whose own `detection_signal` proves the point, so this is checkable
against the KB rather than asserted.

### story_macro -- start with the sentence, end with the proof
A consultant opens by asking the writer to say the movie in one sentence. If that sentence
does not exist, nothing downstream can be fixed, because every scene is being written toward
an unclear target. Then: what is it *about*? Then: does the world keep its own rules?

**Never asserted as fact:** that a theme is wrong. Only that it is *unstated* or *unearned*.
**Theory order:** premise/logline -> controlling idea (McKee) -> world rules -> tone ->
resolution.

The KB is inverted here. `controlling_idea` -- McKee's own definition, and the single most
important theme rule in the file -- is correctly `low`. But five rules whose `category` is
`theme` are tagged `high`, and three of them are *genre instances* (`romance_theme_love`,
`scifi_emotional_core`, `scifi_relationship_to_technology`). The generic rule is honest; the
genre copies are confident. That is backwards: a genre instance of a `low` rule cannot be
`high`.

### theme -- derive it, never impose it
The first question is not "what is your theme" but "where does your protagonist change, and
what did that change cost them?" Theme is a *conclusion* drawn from the arc, not a thesis
inserted into it.

**Never asserted as fact:** that the theme *is* X. Only: "the script returns to sacrifice in
these three scenes -- was that deliberate?"
**Theory order:** theme-as-choice-under-pressure (Martell) -> theme-derived-from-arc
(Weiland). Both are `framework` sources, both correctly ordered, and there are only two.

### structure_pacing -- destination, then foundation, then shape, then placement
A consultant asks: do you know your ending? Then: is there a protagonist with an objective
and escalating confrontation? Only then do they talk about beats -- and beat sheets are the
*last* thing they reach for, not the first, because a beat sheet is a description of a story
that already works, not a recipe for one.

**Never asserted as fact:** that a beat is "late". Page position is measurable only when page
count is known, and *which* scene fulfils a beat is interpretive -- the KB's own `save_the_cat`
signal admits this.
**Theory order:** destination (`martell_know_your_destination`) -> plot foundation
(`bell_lock_system`) -> act structure (Field/Aristotle, McKee's five-part, Gulino's sequences)
-> midpoint -> pacing/escalation -> beat placement (Snyder, Vogler).

**The pending proposal breaks this order in the wrong direction.** It *raises*
`three_act_structure` and `save_the_cat_15_beats` to `high` while *lowering*
`gulino_sequence_climax` to `medium` -- even though Gulino's own rationale in the proposal
reads "the 8-sequence partition is mechanical". An eight-way page partition is more
mechanically checkable than a fifteen-beat one against percentage windows. The proposal
promotes the more prescriptive lens and demotes the more measurable one.

### plot_thread -- conflict first, then causality, then stakes
The first question is whether the antagonist is an *active force with a plan*. Then: does
every cause have an effect? Then: what is at risk?

**Never asserted as fact:** that a red herring is "unfair", or that stakes "feel" life-or-death.
**Theory order:** premise -> conflict (Egri: incontrovertible confrontation) -> causality
(Aristotle; Lyons' story spine) -> antagonist force -> plot mechanics -> stakes -> escalation
-> setup/payoff -> subplot.

This level's centre of gravity is **stakes** -- nine of its 39 rules -- and stakes is the least
checkable thing in it. `romance_psychological_death_stakes` asks whether the stakes "feel
genuinely life-altering". `hauge_five_stakes_levels` flags scripts "where the stakes feel too
small". These are the definitions of a judgment call, tagged `high`.

### character -- the lie, the want, the need, the cost
A consultant asks what the protagonist *believes that is false* (Weiland's Lie), what they
*want* versus what they *need*, and whether the change cost them something. Everything else
about character is downstream of that.

**Never asserted as fact:** "true character". McKee's definition is that true character is
revealed under pressure -- you can *observe the pressure*, but you cannot certify the truth
behind it.
**Theory order:** lie/wound -> want vs need -> arc as value change (McKee) -> transformation
earned -> contradiction (Egri) -> cast function.

**Gating matters more than tier here.** 28 of the level's 39 rules require the knowledge graph
(`requires: knowledge_graph`). If the graph is absent, 72% of the character level cannot fire
at all -- silently. A `medium` character rule that needs the graph is *less* likely to produce
a finding than a `high` dialogue rule that needs only `scene_text`.

### relationship -- the thinnest level, and the most load-bearing
The first question is whether the antagonistic force is of comparable power -- an
uncontested protagonist is not a story. Then: does the dynamic stay consistent scene to scene?

**Never asserted as fact:** that a relationship is "underdeveloped". You can report what
changes and what does not; you cannot grade the intimacy.
**Theory order:** antagonism (McKee) -> dynamic consistency.

Two rules. Both `low`. Both require the knowledge graph. This is the level with the most drama
in it and the least support under it, and the pending proposal does not touch it.

### revision -- separate what is checkable from what is a lecture
First: is the writer telling or showing? Then: is any word not earning its place?

**Never asserted as fact:** anything about the writer's *process* read off the draft.
`epps_revision_first_draft` flags "writers who spend excessive time on first-draft prose" --
that is not observable in a PDF. `epps_rewrite_distance` flags "the writer has made dozens of
passes without improvement" -- equally unobservable.
**Theory order:** the draft's surface (show vs tell, prose economy) -> process (unverifiable).

The level's two `high` rules are both line-craft and both correct. Its two `medium` rules are
both process claims that no analyzer can check, and they are injected into the *scene* pass.

### scene -- does it turn, then does it have an objective
First: does the value flip? A scene that starts and ends in the same place is not a scene.
Then: is there a clear objective and a real obstacle?

**Never asserted as fact:** that a scene is unnecessary, without naming which of plot /
character / theme it fails to serve.
**Theory order:** turn (McKee) -> Goal-Conflict-Disaster (Swain) -> scene-as-mini-story
(Lyons) -> objective/obstacle (Dunne) -> hook and economy -> atmosphere -> image.

**This level contains ten rules about film production, not screenwriting.** The
`visual_storytelling.json` rules ask the analyzer to check *camera angles*, *shot size*,
*lighting*, *composition*, *sound design*, *movement choreography* and *props*. Their
`detection_signal` for `visual_camera_angles_convey_perspective` reads: "Check if camera angle
descriptions match the emotional intent of scenes." A spec screenplay usually does not
describe camera angles -- that is the director's and the DP's work. Eight of the ten are
tagged `high`.

### dialogue -- subtext first, everything else second
First: does anyone say what they actually mean? Then: do the characters have distinguishable
voices? Then: is exposition doing work or filling space?

**Never asserted as fact:** that a line is "on the nose". You can point at the line; the call
is taste. The KB agrees with itself here in one place and contradicts itself in another --
`distinct_character_voice` is `low` (its own signal calls itself "a genuine [judgment call]"),
while `dialogue_voice_distinct` -- the same claim -- is `high`.
**Theory order:** subtext (say the opposite) -> conflict -> exposition-as-ammunition -> voice
-> rhythm -> silence.

Twenty of twenty-three rules here are `high`, for the most taste-bound craft in the file.
`dialogue_purpose_driven` -- "check if every line serves a clear purpose" -- is `high`.
`dialogue_callbacks_payoffs` -- "used effectively ... creates meaning" -- is `high`.

---

## 3. Brainstorm -- Voice 2: the co-writer who suggests all along

A consultant reads once and writes notes. A co-writer is *present*, so its failure mode is the
opposite one: nagging. Its problem is not knowledge, it is **timing and volume**. The taxonomy
ladder turns out to be exactly the delivery schedule it needs -- scope already encodes when a
note is useful.

### The policy

| Band | When to speak | Form |
|---|---|---|
| **E (execution)** | interrupt, at the line the writer is in | statement -- it is verifiable from the text in front of them |
| **S (structural)** | batch, at end of scene or sequence | question, with the evidence quoted |
| **G (governing)** | end of pass, once | question about intent, never a verdict |
| **knowledge-graph rules** | never mid-scene | end of pass, always |

Three further rules for the co-writer:

1. **Interrupt only on a verifiable, cheap, taste-free finding.** In practice: a line
   repeating what we just watched (`martell_see_and_say_rule`), a four-line speech
   (`martell_three_line_rule`), a plant with no payoff (`martell_plants_and_payoffs`). These
   are `E`/`S` band, text-local, and fixable in one keystroke.
2. **Never interrupt on a graph rule mid-scene.** The co-writer cannot see the graph while
   the writer is inside one scene. All 28 graph-dependent character rules and 21 of the 39
   plot_thread rules batch at end of pass.
3. **Say something positive when a plant pays off.** A co-writer that only surfaces defects
   is a linter, not a collaborator. `martell_plants_and_payoffs` and `setup_payoff_general`
   fire on *success* as naturally as on failure.

### Per area

- **story_macro** -- never interrupt. Speak once, at the end: premise, then controlling idea.
- **theme** -- never interrupt. One question at the end: "the script keeps choosing sacrifice
  -- deliberate?" Theme is the area where an unasked verdict does the most damage.
- **structure_pacing** -- interrupt only at act turns and the midpoint; everything else at end
  of pass. A beat-placement note delivered mid-scene is unusable.
- **plot_thread** -- interrupt on a broken plant/payoff (it is local and verifiable); batch
  stakes, escalation and causality.
- **character** -- batch, always. This is the level where a mid-scene note reads as an attack
  on the writer's person.
- **relationship** -- rarely, and only as a question. Both rules are `low` by definition, so
  they are discussion prompts already.
- **revision** -- on request, never uninvited. Process advice offered unasked is a lecture.
- **scene** -- interrupt at the scene just written, and only if it does not turn.
- **dialogue** -- interrupt only on a lexical pattern (see-and-say, three-line block, repeated
  exposition). Never on "on the nose", never on "distinct voice".

### The consequence worth stating plainly

**Twenty of twenty-three dialogue rules are `high` today.** A co-writer honouring its own
confidence tiers would therefore comment on nearly every line of dialogue in a script. That
is the nagging failure mode, and it is caused by the *tier*, not by the plumbing. The tier
recalibration is not cosmetic polish -- for the co-writer it is the difference between a
collaborator and a paperclip.

---

## 4. What the ordering exposes

Findings that fell out of doing this, in descending order of how much they matter.

### 4.1 The schema measures the wrong risk for ten rules
`confidence_tier` is defined as "how mechanically checkable a rule is, **once the right data
exists**". It never asks whether the data exists *in a screenplay*. The ten
`visual_storytelling` rules ask for camera angles, shot size, lighting, composition and sound
design; eight are `high`. A `high` rule asking for evidence the artifact normally does not
contain will produce either silence or invention -- and the product's law is that it must not
invent. This is a **second axis the schema lacks**, and it is not fixed by re-tiering: it is
fixed by either dropping those rules from the scene pass or explicitly marking them as
"only when the script supplies camera direction".

**I tried to measure this, and the corpus cannot settle it.** The obvious test is to count
production vocabulary in the scripts the product ships with. I ran it: across all 34
`.fountain` files, unambiguous camera-direction terms (`CLOSE ON`, `ANGLE ON`, `SHOT SIZE`,
`LENS`, `POV`, `DOLLY`, `CRANE`, `AERIAL`...) occur **zero** times in 2,686 non-blank lines.
That looks like confirmation, and it is not -- because the corpus is **four distinct scripts**.
The 34 files are near-duplicates of one another (12 are 84-line copies of the same courier
story), with real sizes of 20, 31 and 84 lines: they are test fixtures, not screenplays. The
same probe found **zero** descriptive lighting words and only 256 blocking verbs, which says
the fixtures are thin in *all* description rather than that screenplays lack camera direction.

So 4.1 remains a **hypothesis**. Settling it needs a corpus of real spec scripts; the check
itself is about ten lines and is reusable.

*Method note, because it nearly went wrong twice: my first probe reported two camera hits, both
false positives -- the word "pan" in "cracks an egg into a hot **pan**". A vocabulary count over
prose needs word boundaries and an unambiguous term list, or ordinary nouns inflate it.*

### 4.2 Tier is only the first gate; capability is the second, and it is invisible
The levels split cleanly in two:

| Text-only (fires on any script) | Graph-dependent (fires only if the graph exists) |
|---|---|
| `scene` 33/34, `dialogue` 22/23, `structure_pacing` 26/28, `revision` 4/4, `story_macro` 16/21 | `character` 28/39, `plot_thread` 21/39, `theme` 2/2, `relationship` 2/2 |

So a rule's *effective* assertiveness is `confidence_tier` **and** capability. The pending
proposal reasons about tier alone. `drama_transformation_earned` moving `high -> low` is a
smaller change than the fact that 28 character rules cannot run without the graph.

### 4.3 Four tier incoherences survive the pending proposal
Verified against `docs/kb_tier_proposal.csv`:

| Claim | Rules | Now | After the proposal | Problem |
|---|---|---|---|---|
| plant/payoff | `martell_plants_and_payoffs` / `chekhovs_gun` / `setup_payoff_general` | high / medium / low | medium / medium / low | same claim, two tiers remain |
| escalation | `pacing_escalation` / `progressive_complications_no_repetition` | low / low | **medium / low** | near-identical claims, one moved and its twin not |
| earned change | `drama_transformation_earned` / `seger_transformation_earned` | high / medium | **low / medium** | *identical rule name*, two tiers -- and the proposal widens the gap |
| want vs need | `weiland_want_vs_need` / `want_vs_need` | high / low | low / low | **converges -- correct** |

The proposal gets two of these right (want/need, distinct voice) and leaves two unresolved.
`drama_transformation_earned` and `seger_transformation_earned` carry the *same name*; leaving
them at `low` and `medium` is a defect the re-tag was supposed to remove.

### 4.4 Three rules are literally the same rule
`action_stakes_physical_death`, `horror_stakes_physical_death` and
`thriller_physical_death_stakes` share the identical `name` ("Physical Death at Stake"), the
identical `taxonomy_level` (`plot_thread`), the identical `requires` (`scene_summaries`) and
the identical detection signal text. All three stay `high` in the proposal. That is one rule
written three times, and it inflates the plot_thread level by 2.

### 4.5 84 of 192 rules have no attributed originator
62 of them have a null `originator` outright; all 84 are `source_type: general_craft`. The KB's
entire stated purpose is *"an explicit, structured, attributed set of screenwriting craft
principles ... instead of a model relying on whatever it happens to remember from training."*
Forty-four percent of the rules in these nine levels are unattributed -- which is exactly the
failure the file was created to prevent, surviving inside the file.

Worst by level: `scene` 18, `plot_thread` 19, `dialogue` 15.

### 4.6 Prose vocabulary inside a screenplay product
`stein_four_dangers_of_telling` -- in the `revision` level -- reads: "Long character
descriptions in the **first chapter**." `epps_revision_first_draft` speaks of "first-draft
prose". `zinsser_dump_the_clutter` is sourced from Zinsser's *On Writing Well*, a nonfiction
prose guide. Twenty-one rules across the KB use novel/manuscript vocabulary. It is a small
thing that tells a writer the tool is not entirely sure what it is analysing.

### 4.7 The `theme` level is a two-rule stub inside a seven-rule topic
`theme` has 2 rules. `story_macro` holds 5 more whose `category` is `theme`, including
`controlling_idea` -- the most important theme rule in the file. Both levels are routed
together, so nothing breaks; but the *level* named `theme` is a stub, and anyone reasoning
about coverage from level counts would misread the KB.

---

## 5. Self-critique

Points where this note is weaker than it looks.

1. **The sort key is my interpretation, and the alternative is equally defensible.** You may
   have meant confidence-tier-first. I chose theory-first and said so; if that is wrong, the
   ladders are re-ordered by the CSV, not rebuilt.
2. **The G/S/E bands are invented by me.** They are not a KB field and no test guards them. I
   read each category's own theory and assigned the band by judgment -- e.g. I put `stakes` in
   **S** for `plot_thread`, but a consultant could argue stakes are **G**, since an unclear
   stake invalidates everything downstream. Any band you dispute is arguable, and the CSV
   carries the band per rule so you can overrule it row by row.
3. **Some bands rest on a rule's name and category, not its full text.** I read the complete
   detail for `story_macro`, `theme` and `structure_pacing`; for `plot_thread`, `character`,
   `scene` and `dialogue` I read name, category, tier, severity, source and the operational
   `detection_signal`, but not every `counter_considerations` paragraph. A band assignment
   that hinges on an exception clause could be wrong.
4. **I did not run a model.** "This changes how assertive a report sounds" remains unmeasured
   -- the same limit the tier proposal carries. Nothing here proves the tone moves.
5. **The expert voices are subagents running the same model as me.** They are not a working
   script consultant. Their value is that they read the files independently, in a fresh
   context, and disagreed with me usefully. I checked every checkable claim they made against
   the CSV.
6. **I corrected one of their claims.** One review argued the tier proposal is "mostly
   cosmetic because high and medium are tonally identical in the global prompt". That is half
   right: `prompts.py:49` does treat high and medium identically, but
   `knowledge_base.py:73-74` emits a *per-rule* gloss that differs -- "treat findings as
   near-certain" versus "treat findings as a judgment call". Every rule is injected with that
   line attached, so high -> medium is not cosmetic. The reviewer overstated it; the note
   above reflects the corrected version.
7. **The camera-angle finding is a hypothesis I tried and failed to measure.** I set out to
   upgrade 4.1 from a craft claim to a measurement, and the attempt is documented in 4.1
   precisely because it did not work: the only script corpus in the repo is four short test
   fixtures, so "zero camera terms" reflects thin fixtures, not screenplay convention. I could
   have reported the zero as confirmation; it would have been a false positive dressed as
   evidence. The check is written down so it can be run against real scripts.
8. **This note changes no tier.** Every `proposed_tier` cited comes from the *pending*
   proposal, which is still unapproved. Nothing here is applied.

---

## 6. The ordered ladders

For each level: **G** governing -> **S** structural -> **E** execution, and within each band
ordered by confidence tier (high -> medium -> low) then severity. The `->proposed` column is
the pending proposal's tier, bolded where it differs.

### 6.1 `story_macro` -- the whole story -- premise, theme, world, tone, resolution
*21 rules  (high 17 / medium 1 / low 3)*

**G -- the level's foundational principle**  (9)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `romance_theme_love` | Theme Must Be Love-Related | theme | high | **medium** | high | K.M. Weiland |
| 2 | `mystery_logline_clarity` | Mystery Logline Must Be Clear | concept | high | **medium** | medium | David Hohl |
| 3 | `scifi_concept_simplicity` | Keep Sci-Fi Concepts Simple | concept | high | **medium** | medium | Scriptshadow/Amber |
| 4 | `scifi_emotional_core` | Sci-Fi Must Have Emotional Core | theme | high | **low** | medium | *general_craft* |
| 5 | `scifi_relationship_to_technology` | Sci-Fi Themes Explore Man vs Technology | theme | high | **low** | medium | Randy Ingermanson |
| 6 | `scifi_simple_logline` | Sci-Fi Logline Must Be Understandable | concept | high | **medium** | medium | Scriptshadow/Amber |
| 7 | `thriller_contained_premise` | Contained Thriller Structure | concept | high | **medium** | low | Scriptshadow/Amber |
| 8 | `controlling_idea` | Controlling Idea (Theme as Cause-and-Effect Statement) | theme | low | low | medium | Robert McKee |
| 9 | `theme_contradiction` | Theme Contradiction Without Earned Justification | theme | low | low | medium | Robert McKee |

**S -- how the principle becomes structure**  (11)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `drama_emotional_authenticity` | Emotional Authenticity Over Plot Mechanics | tone | high | **low** | high | Robert McKee |
| 2 | `horror_tone_set_immediately` | First Page Sets Horror Tone | tone | high | **medium** | high | David Hohl |
| 3 | `mystery_clue_game` | Riddle as Game Between Writer and Audience | structure | high | **medium** | high | Ronald Tobias |
| 4 | `mystery_solution_satisfying` | Mystery Solution Must Be Satisfying | resolution | high | **low** | high | *general_craft* |
| 5 | `romance_satisfying_resolution` | Romance Resolution Must Be Satisfying | resolution | high | high | high | *general_craft* |
| 6 | `scifi_rules_established_early` | World Rules Must Be Established Early | worldbuilding | high | **medium** | high | Angus Fletcher |
| 7 | `horror_rules_established_early` | Horror World Rules Established Early | worldbuilding | high | **medium** | medium | Angus Fletcher |
| 8 | `drama_ambiguity_preserved` | Drama Preserves Ambiguity | resolution | high | **low** | low | *general_craft* |
| 9 | `horror_ordinary_world_horror` | Ordinary World Must Contrast Horror | contrast | high | **medium** | low | Christopher Vogler |
| 10 | `romance_adult_children_opening` | Lovers Introduced as Adult Children | structure | high | **low** | low | Angus Fletcher |
| 11 | `world_rule_consistency` | World-Building Rule Consistency | world_building | medium | medium | medium | *general_craft* |

**E -- a specific, local craft check**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `genre_convention_fulfillment` | Genre Convention Fulfillment | genre | low | low | low | *general_craft* |


### 6.2 `theme` -- what the story is about
*2 rules  (high 2 / medium 0 / low 0)*

**G -- the level's foundational principle**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `martell_theme_through_characters` | Theme Expressed Through Character Choices | theme | high | **medium** | high | William Martell |

**S -- how the principle becomes structure**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `weiland_theme_from_arc` | Theme Emerges from the Character's Arc | theme_construction | high | **low** | medium | K.M. Weiland |


### 6.3 `structure_pacing` -- the story's shape over time
*28 rules  (high 21 / medium 4 / low 3)*

**G -- the level's foundational principle**  (6)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `bell_lock_system` | LOCK System: Lead, Objective, Confrontation, Knockout | plot_foundation | high | **medium** | high | James Scott Bell |
| 2 | `gulino_sequence_climax` | Sequence Approach: Each Sequence Has Its Own Mini-Climax | act_structure | high | **medium** | high | Paul Gulino |
| 3 | `martell_act_two_conflict` | Act Two Is the Conflict Act | act_structure | high | **medium** | high | William Martell |
| 4 | `martell_know_your_destination` | Know Your Ending Before You Write | ending | high | **low** | high | William Martell |
| 5 | `mckee_five_part_design` | Five-Part Story Design | act_structure | medium | medium | medium | Robert McKee |
| 6 | `three_act_structure` | Three-Act Structure | act_structure | medium | **high** | low | Aristotle (Poetics); formalized for screenwriting by Syd Field |

**S -- how the principle becomes structure**  (16)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `martell_deadlines_drive_momentum` | Deadlines Drive Act Two Momentum | pacing | high | **medium** | high | William Martell |
| 2 | `mystery_reveal_timing` | Explanation Before Climax | structure | high | **medium** | high | Ronald Tobias |
| 3 | `romance_midpoint_no_return` | Midpoint as Point of No Return | structure | high | **medium** | high | David Hohl |
| 4 | `thriller_locked_in_by_act_end` | Protagonist Must Be Locked In by Act I End | structure | high | **medium** | high | David Hohl |
| 5 | `action_pacing_relentless` | Action Pacing Is Relentless | pacing | high | **medium** | medium | William Martell |
| 6 | `bell_midpoint_shift` | The Midpoint Shifts the Story from Reaction to Action | midpoint | high | **medium** | medium | James Scott Bell |
| 7 | `comedy_midpoint_physical_intimacy` | Rom-Com Midpoint Physical Intimacy | structure | high | **medium** | medium | David Hohl |
| 8 | `comedy_reel_laugh` | Every Reel Needs a Big Laugh | structure | high | **medium** | medium | David Hohl |
| 9 | `gulino_dramatic_question` | Each Sequence Must Raise and Answer a Dramatic Question | structure | high | **medium** | medium | Paul Gulino |
| 10 | `horror_reel_event_requirement` | Every Reel Must Have a Horror Payoff | structure | high | **medium** | medium | David Hohl |
| 11 | `horror_tension_building` | Tension Builds Through Unanswered Questions | tension | high | **medium** | medium | James Scott Bell |
| 12 | `mystery_pacing_controlled` | Mystery Pacing Is Controlled | pacing | high | **low** | medium | *general_craft* |
| 13 | `romance_third_act_breakup` | Third Act Breakup Must Be Earned | structure | high | **medium** | medium | *general_craft* |
| 14 | `thriller_ticking_clock` | Ticking Clock Creates Urgency | urgency | high | **medium** | medium | Michael Hauge |
| 15 | `alderson_false_summit` | The False Summit Before the True Climax | climax_structure | medium | medium | low | Martha Alderson |
| 16 | `pacing_escalation` | Escalation of Conflict (Law of Conflict) | pacing | low | **medium** | medium | Robert McKee |

**E -- a specific, local craft check**  (6)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `comedy_timing_is_everything` | Comedic Timing in Scene Length | pacing | high | **low** | medium | *general_craft* |
| 2 | `drama_pacing_meditative` | Drama Allows Meditative Pacing | pacing | high | **low** | low | *general_craft* |
| 3 | `visual_ellipsis_time_passage` | Visual Ellipsis for Time Passage | editing | high | **medium** | low | *general_craft* |
| 4 | `save_the_cat_15_beats` | Save the Cat 15-Beat Sheet | beat_sheet | medium | **high** | low | Blake Snyder |
| 5 | `heros_journey_12_stages` | Hero's Journey (12 Stages) | beat_sheet | low | **medium** | low | Christopher Vogler, adapting Joseph Campbell |
| 6 | `opening_closing_bookend` | Opening/Closing Image Bookend | act_structure | low | **medium** | low | Blake Snyder |


### 6.4 `plot_thread` -- causal threads that cross scenes
*39 rules  (high 33 / medium 3 / low 3)*

**G -- the level's foundational principle**  (8)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `horror_monster_defeat` | Central Struggle Against Monster | conflict | high | **medium** | high | Randy Ingermanson |
| 2 | `lyons_story_spine` | The Story Spine (Because of That, Not And Then) | causality | high | **medium** | high | Jeff Lyons |
| 3 | `comedy_relationship_difficulty` | If Boy Can Easily Get Girl, No Story | premise | high | **medium** | medium | Michael Hauge |
| 4 | `drama_internal_conflict_primary` | Internal Conflict Drives Drama | conflict_type | high | **medium** | medium | James Scott Bell |
| 5 | `scifi_man_vs_nature` | Sci-Fi Can Be Man vs Nature | conflict_type | high | **medium** | medium | Randy Ingermanson |
| 6 | `egri_character_incontrovertible` | Character in Incontrovertible Confrontation | conflict | medium | medium | high | Lajos Egri |
| 7 | `no_coincidental_resolution` | No Coincidental Resolution | causality | medium | medium | high | Aristotle, widely echoed in modern craft writing |
| 8 | `progressive_complications_no_repetition` | Progressive Complications Without Repetition | causality | low | low | medium | Robert McKee |

**S -- how the principle becomes structure**  (23)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `action_escalation_constant` | Action Escalates Constantly | escalation | high | **medium** | high | William Martell |
| 2 | `action_stakes_physical_death` | Physical Death at Stake | stakes | high | high | high | William Martell |
| 3 | `action_villain_plan_clear` | Villain's Plan Must Be Clear | antagonist_structure | high | **medium** | high | William Martell |
| 4 | `alderson_cause_and_effect_scenes` | Scenes Must Be Linked by Cause and Effect | scene_linking | high | **medium** | high | Martha Alderson |
| 5 | `comedy_death_stakes` | Comedy Stakes Are Psychological Death | stakes | high | **medium** | high | Randy Ingermanson |
| 6 | `cron_external_plot_spur` | The External Plot Must Spur the Internal Struggle | plot_character_link | high | **medium** | high | Lisa Cron |
| 7 | `drama_consequences_real` | Drama Has Real Consequences | consequences | high | **medium** | high | *general_craft* |
| 8 | `horror_stakes_physical_death` | Physical Death at Stake | stakes | high | high | high | Randy Ingermanson |
| 9 | `romance_psychological_death_stakes` | Psychological Death as Romance Stakes | stakes | high | **medium** | high | Randy Ingermanson |
| 10 | `romance_trivial_stakes_comedy` | Romance Stakes Must Feel Life-or-Death | stakes | high | **medium** | high | Scriptshadow/Amber |
| 11 | `thriller_physical_death_stakes` | Physical Death at Stake | stakes | high | high | high | Randy Ingermanson |
| 12 | `thriller_things_go_wrong` | Escalating Things Going Wrong | escalation | high | **medium** | high | Scriptshadow/Amber |
| 13 | `comedy_escalation_pattern` | Comedy Escalates Through Pattern Breaking | escalation | high | **medium** | medium | *general_craft* |
| 14 | `drama_relationships_drive_plot` | Relationships Drive Plot in Drama | plot_mechanics | high | **medium** | medium | *general_craft* |
| 15 | `drama_stakes_personal` | Drama Stakes Are Personal | stakes | high | **medium** | medium | *general_craft* |
| 16 | `hauge_five_stakes_levels` | Five Levels of Stakes | stakes | high | **medium** | medium | Michael Hauge |
| 17 | `horror_vulnerability_escalation` | Vulnerability Escalates Through Isolation | escalation | high | **medium** | medium | *general_craft* |
| 18 | `martell_four_ds` | The Four Ds: Inside Moves (Dilemma, Denial, Decision, Drama) | plot_mechanics | high | **medium** | medium | William Martell |
| 19 | `mystery_stakes_personal` | Mystery Stakes Must Be Personal | stakes | high | **medium** | medium | *general_craft* |
| 20 | `scifi_consequences_realistic` | Sci-Fi Consequences Must Feel Real | consequences | high | **medium** | medium | *general_craft* |
| 21 | `thriller_reversals_escalate` | Reversals Must Escalate Stakes | reversals | high | **medium** | medium | Robert McKee |
| 22 | `thriller_unexpected_complications` | Every Plan Must Have Unexpected Complications | plot_mechanics | high | **medium** | medium | James Scott Bell |
| 23 | `thriller_villain_drives_plot` | Villain Drives the Plot | antagonist_structure | high | **medium** | medium | Michael Hauge |

**E -- a specific, local craft check**  (8)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `martell_plants_and_payoffs` | Plants Must Pay Off | setup_payoff | high | **medium** | high | William Martell |
| 2 | `mystery_foreshadowed_surprises` | Surprises Must Be Foreshadowed | plot | high | **medium** | high | David Hohl |
| 3 | `mystery_red_herrings` | Red Herrings Must Be Fair | misdirection | high | **low** | medium | *general_craft* |
| 4 | `romance_enemies_to_lovers` | Enemies-to-Lovers Requires Genuine Friction | subgenre | high | **medium** | medium | *general_craft* |
| 5 | `seger_subplot_resonance` | Subplots Must Resonate with Main Plot | subplot | high | **medium** | medium | Linda Seger |
| 6 | `chekhovs_gun` | Chekhov's Gun | setup_payoff | medium | medium | medium | Anton Chekhov |
| 7 | `setup_payoff_general` | General Setup and Payoff | setup_payoff | low | low | medium | Robert McKee |
| 8 | `subplot_resonance_or_contradiction` | Subplot Function (Resonance or Contradiction) | subplot | low | low | medium | Robert McKee |


### 6.5 `character` -- one person across the whole story
*39 rules  (high 29 / medium 5 / low 5)*

**G -- the level's foundational principle**  (6)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `seger_goal_spine` | Character Goal as Story Spine | motivation | high | **medium** | high | Linda Seger |
| 2 | `weiland_lie_believed` | Every Character Arc Is Driven by a Lie the Character Believes | arc_foundation | high | **medium** | high | K.M. Weiland |
| 3 | `weiland_want_vs_need` | The Conflict Between What the Character Wants and What They Need | motivation | high | **low** | high | K.M. Weiland |
| 4 | `true_character_vs_characterization` | True Character vs. Characterization | consistency | low | low | high | Robert McKee |
| 5 | `character_arc_change` | Character Arc as Value Change | arc | low | low | medium | Robert McKee |
| 6 | `want_vs_need` | Conscious Want vs. Unconscious Need | motivation | low | low | medium | Common across McKee's Object of Desire and Truby-school character theory |

**S -- how the principle becomes structure**  (23)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `action_hero_must_be_active` | Hero Must Be Active | protagonist | high | **medium** | high | William Martell |
| 2 | `action_villain_strength` | Villain Must Be Formidable | antagonist | high | **low** | high | William Martell |
| 3 | `drama_transformation_earned` | Character Transformation Must Be Earned | character_arc | high | **low** | high | Robert McKee |
| 4 | `hauge_inner_conflict_drives_outer` | Inner Conflict Must Drive Outer Conflict | character_arc | high | **medium** | high | Michael Hauge |
| 5 | `martell_supporting_character_function` | Supporting Characters Must Serve the Protagonist | supporting_cast | high | **medium** | high | William Martell |
| 6 | `stc_save_the_cat_scene` | Save the Cat Scene | hero_introduction | high | **medium** | high | Blake Snyder |
| 7 | `thriller_villain_strength` | Strong Villain Required | antagonist | high | **low** | high | David Hohl |
| 8 | `action_hero_competence` | Hero Must Demonstrate Competence | protagonist | high | **medium** | medium | *general_craft* |
| 9 | `action_hero_underdog` | Hero Must Be Underdog | protagonist | high | **medium** | medium | William Martell |
| 10 | `action_hero_villain_flipside` | Hero and Villain Are Flip Sides | character_relationship | high | **medium** | medium | William Martell |
| 11 | `alderson_character_emotional_development` | Track the Character's Emotional Arc Across the Entire Story | emotional_arc | high | **medium** | medium | Martha Alderson |
| 12 | `drama_moral_complexity` | Moral Complexity in Character Choices | moral_dimension | high | **low** | medium | Robert McKee |
| 13 | `horror_final_girl_strength` | Final Girl Must Earn Survival | character_arc | high | **low** | medium | *general_craft* |
| 14 | `mystery_detective_competence` | Detective Must Be Competent | protagonist | high | **medium** | medium | *general_craft* |
| 15 | `mystery_multiple_suspects` | Multiple Suspects Create Depth | cast_design | high | **medium** | medium | *general_craft* |
| 16 | `romance_emotional_vulnerability` | Emotional Vulnerability Required | character_depth | high | **medium** | medium | *general_craft* |
| 17 | `scifi_grounding_reality` | Sci-Fi Must Ground in Human Reality | character_depth | high | **low** | medium | *general_craft* |
| 18 | `thriller_active_protagonist` | Protagonist Must Be Active | protagonist | high | **medium** | medium | Scriptshadow/Amber |
| 19 | `weiland_ghost_wound` | The Ghost Is the Origin of the Lie | backstory | high | **medium** | medium | K.M. Weiland |
| 20 | `seger_transformation_earned` | Character Transformation Must Be Earned | character_arc | medium | medium | high | Linda Seger |
| 21 | `egri_character_contradiction` | Character Contradiction as Source of Drama | character_depth | medium | medium | medium | Lajos Egri |
| 22 | `hauge_identity_transformation` | Six-Stage Character Transformation | character_arc | medium | medium | medium | Michael Hauge |
| 23 | `cast_polarization` | Cast Polarization | cast_design | low | low | low | Robert McKee |

**E -- a specific, local craft check**  (10)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `comedy_trivial_taken_seriously` | Comedy Characters in Tragedy | tone | high | **medium** | high | Scriptshadow/Amber |
| 2 | `comedy_character_flaws_funny` | Character Flaws Create Comedy | character_design | high | **low** | medium | *general_craft* |
| 3 | `comedy_contradictory_characters` | Contradictory Character Placements | concept | high | **medium** | medium | Randy Ingermanson |
| 4 | `drama_ensemble_depth` | Ensemble Characters Have Depth | ensemble | high | **medium** | medium | *general_craft* |
| 5 | `romance_complementary_flaws` | Romantic Leads Have Complementary Flaws | character_design | high | **medium** | medium | *general_craft* |
| 6 | `thriller_characters_active` | Characters Must Be Active in Contained Thrillers | character_behavior | high | **medium** | medium | Scriptshadow/Amber |
| 7 | `action_physical_consequences` | Action Has Physical Consequences | realism | high | **medium** | low | *general_craft* |
| 8 | `horror_virgin_archetype` | The Virgin Survivor Archetype | archetype | medium | medium | low | David Hohl |
| 9 | `weiland_five_arc_types` | Five Character Arc Types: Positive, Flat, Disillusionment, Fall, Corruption | arc_taxonomy | medium | medium | low | K.M. Weiland |
| 10 | `character_necessity` | Character Necessity | necessity | low | low | low | *general_craft* |


### 6.6 `relationship` -- what happens between two people
*2 rules  (high 0 / medium 0 / low 2)*

**G -- the level's foundational principle**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `antagonist_force_balance` | Antagonistic Force of Comparable Power | antagonism | low | low | medium | Robert McKee |

**S -- how the principle becomes structure**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `relationship_dynamic_consistency` | Relationship Dynamic Consistency | consistency | low | low | medium | *general_craft* |


### 6.7 `revision` -- the writer's process and line-level prose
*4 rules  (high 2 / medium 2 / low 0)*

**G -- the level's foundational principle**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `epps_revision_first_draft` | First Draft Is Discovery, Not Perfection | revision | medium | medium | low | Jack Epps Jr. |

**S -- how the principle becomes structure**  (1)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `epps_rewrite_distance` | Rewriting Requires Emotional Distance | revision | medium | medium | low | Jack Epps Jr. |

**E -- a specific, local craft check**  (2)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `stein_four_dangers_of_telling` | Four Danger Areas of Telling: Backstory, Description, Setting, Emotion | show_vs_tell | high | high | medium | Sol Stein |
| 2 | `zinsser_dump_the_clutter` | Dump the Clutter--Every Word Must Earn Its Place | prose_economy | high | high | medium | William Zinsser |


### 6.8 `scene` -- one unit of story
*34 rules  (high 26 / medium 5 / low 3)*

**G -- the level's foundational principle**  (5)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `dunne_scene_objective` | Every Scene Has a Clear Objective and Obstacle | scene_design | high | **medium** | high | Will Dunne |
| 2 | `lyons_scene_is_story` | Each Scene Is a Mini-Story | scene_design | high | **medium** | high | Jeff Lyons |
| 3 | `goal_conflict_disaster` | Scene Structure: Goal, Conflict, Disaster | scene_structure | medium | medium | medium | Dwight V. Swain |
| 4 | `lakin_five_layers` | Five Layers of Scene Construction | scene_design | medium | medium | medium | C.S. Lakin |
| 5 | `scene_must_turn` | Every Scene Must Turn | scene_structure | medium | medium | medium | Robert McKee |

**S -- how the principle becomes structure**  (14)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `bell_opening_cromise` | The Opening Must Make a Promise to the Reader | opening | high | **medium** | high | James Scott Bell |
| 2 | `weiland_characteristic_moment` | The Characteristic Moment Must Establish the Protagonist Immediately | opening | high | **medium** | high | K.M. Weiland |
| 3 | `action_set_pieces_varied` | Action Set Pieces Must Be Varied | scene_craft | high | **medium** | medium | *general_craft* |
| 4 | `alderson_dramatic_vs_passive` | Prefer Dramatic Action Over Passive Action | scene_energy | high | **medium** | medium | Martha Alderson |
| 5 | `horror_atmosphere_over_dialogue` | Atmosphere Over Dialogue | scene_craft | high | **low** | medium | *general_craft* |
| 6 | `horror_discovery_phase_no_urgency` | Discovery Phase Needs Time to Breathe | pacing | high | **medium** | medium | Scriptshadow/Amber |
| 7 | `lakin_scene_hook` | Scene Must Hook at Start and Leave with Tension | scene_craft | high | **medium** | medium | C.S. Lakin |
| 8 | `mystery_atmosphere_tension` | Mystery Atmosphere Creates Tension | atmosphere | high | **low** | medium | *general_craft* |
| 9 | `romance_grand_gesture` | Grand Gesture Must Be Personal | climax | high | **low** | medium | *general_craft* |
| 10 | `scifi_exposition_through_action` | Sci-Fi Exposition Through Action | exposition | high | **medium** | medium | *general_craft* |
| 11 | `scifi_visual_storytelling` | Sci-Fi Requires Strong Visual Storytelling | visual_narrative | high | **medium** | medium | *general_craft* |
| 12 | `visual_show_dont_tell` | Show Don't Tell Through Visuals | visual_narrative | high | **medium** | medium | *general_craft* |
| 13 | `weiland_normal_world` | The Normal World Must Demonstrate the Lie in Action | setup | high | **medium** | medium | K.M. Weiland |
| 14 | `obligatory_scene` | The Obligatory Scene | payoff | low | low | medium | Robert McKee |

**E -- a specific, local craft check**  (15)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `alderson_scene_tracker_elements` | Every Scene Must Track Seven Essential Elements | scene_craft | high | **medium** | medium | Martha Alderson |
| 2 | `comedy_exaggeration_mechanism` | Exaggeration as Comedic Mechanism | scene_craft | high | **low** | medium | *general_craft* |
| 3 | `comedy_start_late_leave_early` | Start Scenes Late, Leave Early | scene_craft | high | **medium** | medium | David Hohl |
| 4 | `stein_dynamic_description` | Descriptions Should Be Dynamic, Not Static | description_craft | high | **medium** | medium | Sol Stein |
| 5 | `thriller_bonding_moment` | Ensemble Bonding Scene | ensemble_dynamics | high | **medium** | medium | Scriptshadow/Amber |
| 6 | `visual_camera_angles_convey_perspective` | Camera Angles Convey Perspective | cinematography | high | **medium** | medium | *general_craft* |
| 7 | `visual_composition_framing` | Composition Frames Character Relationships | composition | high | **medium** | medium | *general_craft* |
| 8 | `visual_movement_choreography` | Movement Conveys Character State | choreography | high | **medium** | medium | *general_craft* |
| 9 | `visual_shot_size_emphasis` | Shot Size Controls Emphasis | cinematography | high | **medium** | medium | *general_craft* |
| 10 | `visual_lighting_mood` | Lighting Establishes Mood | atmosphere | high | **low** | low | *general_craft* |
| 11 | `visual_sound_design_atmosphere` | Sound Design Creates Atmosphere | sound | high | **medium** | low | *general_craft* |
| 12 | `visual_color_symbolism` | Color Can Symbolize Theme | symbolism | medium | medium | low | *general_craft* |
| 13 | `visual_props_meaningful` | Props Can Carry Meaning | props | medium | medium | low | *general_craft* |
| 14 | `scene_necessity_test` | Scene Necessity (Plot / Character / Theme Test) | scene_economy | low | low | medium | *general_craft* |
| 15 | `enter_late_leave_early` | Enter Late, Leave Early | scene_economy | low | low | low | *general_craft* |


### 6.9 `dialogue` -- one line
*23 rules  (high 20 / medium 2 / low 1)*

**G -- the level's foundational principle**  (5)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `dialogue_conflict_essential` | Every Dialogue Scene Needs Conflict | conflict | high | **medium** | high | James Scott Bell |
| 2 | `martell_dialogue_is_character` | Dialogue Is Character | character_voice | high | **low** | high | William Martell |
| 3 | `dialogue_subtext_layers` | Dialogue Contains Multiple Subtext Layers | subtext | high | **medium** | medium | Robert McKee |
| 4 | `martell_say_the_opposite` | Say the Opposite (Subtext Through Contradiction) | subtext | high | **medium** | medium | William Martell |
| 5 | `on_the_nose_vs_subtext` | On-the-Nose Dialogue vs. Subtext | subtext | medium | medium | medium | *general_craft* |

**S -- how the principle becomes structure**  (11)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `martell_five_types_bad_exposition` | Five Types of Bad Exposition | exposition | high | **medium** | high | William Martell |
| 2 | `martell_see_and_say_rule` | See and Say Rule (Don't Repeat What Was Shown) | exposition | high | **medium** | high | William Martell |
| 3 | `stc_laying_pipe` | Laying Pipe (Exposition Through Action) | exposition | high | **medium** | high | Blake Snyder |
| 4 | `comedy_subtext_not_literal` | Dialogue Must Have Subtext | dialogue | high | **medium** | medium | Scriptshadow/Amber |
| 5 | `dialogue_emotional_leakage` | Emotions Leak Through Dialogue | emotion | high | **medium** | medium | *general_craft* |
| 6 | `dialogue_exposition_disguised` | Exposition Must Be Disguised | exposition | high | **medium** | medium | *general_craft* |
| 7 | `dialogue_power_dynamics` | Dialogue Reveals Power Dynamics | power | high | **medium** | medium | *general_craft* |
| 8 | `dialogue_purpose_driven` | Every Line Must Have Purpose | purpose | high | **medium** | medium | *general_craft* |
| 9 | `dialogue_voice_distinct` | Each Character Has Distinct Voice | character_voice | high | **low** | medium | James Scott Bell |
| 10 | `drama_dialogue_subtext` | Dramatic Dialogue Contains Subtext | dialogue_craft | high | **medium** | medium | *general_craft* |
| 11 | `exposition_as_ammunition` | Exposition as Ammunition, Not Data Dump | exposition | medium | medium | medium | Robert McKee |

**E -- a specific, local craft check**  (7)

| # | rule id | name | own category | tier | ->proposed | sev | theory source |
|---|---|---|---|---|---|---|---|
| 1 | `dialogueGMEMATICultural` | Dialogue Reflects Cultural Context | cultural | high | **medium** | medium | *general_craft* |
| 2 | `dialogue_rhythm_pacing` | Dialogue Rhythm Affects Pacing | rhythm | high | **medium** | medium | *general_craft* |
| 3 | `dialogue_silence_powerful` | Silence Can Be Most Powerful Dialogue | silence | high | **low** | medium | *general_craft* |
| 4 | `martell_three_line_rule` | Three Line Rule (Dialogue Brevity) | dialogue_craft | high | high | medium | William Martell |
| 5 | `dialogue_callbacks_payoffs` | Dialogue Callbacks Create Cohesion | cohesion | high | **medium** | low | *general_craft* |
| 6 | `dialogue_interrupts_overlaps` | Interruptions and Overlaps Create Realism | realism | high | **medium** | low | *general_craft* |
| 7 | `distinct_character_voice` | Distinct Character Voice | voice | low | low | low | *general_craft* |

---

## 7. What this does not decide

- **Whether to re-order anything.** The ladders are an analysis, not a plan. Nothing in the KB
  moves because of this note.
- **Whether the G/S/E bands should become real.** They could become a `theory_band` field on
  each rule, which would make the co-writer's interrupt policy data-driven instead of
  hard-coded. That is a design proposal, not a change.
- **The tier distribution.** Still `14 / 198 / 51` or the conservative variant, still your
  call.
- **4.1 and 4.2.** The "data does not exist in a screenplay" axis and the capability gate are
  the two findings here that re-tiering cannot fix. They need a decision of their own.
