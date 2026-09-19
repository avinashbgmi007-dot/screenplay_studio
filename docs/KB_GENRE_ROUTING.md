# Genre: how it is detected, how it loads rules, and how well it holds up

**Status: ANALYSIS ONLY.** No product code was changed for this document. The knowledge base is
untouched. Every number below was measured by running the shipped resolvers, not read off a spec.

Reproduce the tables with:

    python .workbuddy-ai/scratch/genre_mismatch.py

---

## 0. Your question, answered directly

You asked whether genre-tagged rules are mapped to their genre so they fire only for that genre,
and whether the non-genre rules stay as they are.

**Yes. That is already exactly what the code does.** It is not a proposal - it is the shipped
behaviour, and it is implemented more strictly than you described:

- Every rule that carries a `genre` tag is **hard-excluded from every generic pass**
  (`rules_context.py:91-103`, `is_genre_scoped`; enforced at `:141` and `:162`).
- It is delivered **only** by the genre-scoped fragment, which is appended to one call - the
  genre-convention check (`genre.py:113-114`).
- I measured the exclusion: **90 genre-tagged rules, and ZERO of them reach a generic pass.**
- Non-genre rules are untouched by any of this.

So there is nothing to build here. What there *is* to fix is that the whole mechanism hangs off a
single unconstrained free-text string, and two resolvers that read that string disagree with each
other on **20 of 44** realistic labels. That is the real finding.

---

## 1. How genre is detected

Genre is not detected by any heuristic, keyword list, or classifier. It is **invented by the model
in one call, with no instruction about what a genre is**, and then used raw.

The chain, in order:

**Step 1 - scene summaries.** Scenes are summarised by the model into a scene-by-scene overview.
Genre is not involved yet.

**Step 2 - the coverage pass.** One model call produces logline, genre, tone, synopsis, strengths,
weaknesses, comparable films, recommendation (`pipeline.py:13`).

Here is the entire instruction the model gets about genre. The system prompt
(`prompts.py:426-434`), in full:

> "You are writing professional script coverage, the standard industry format used by studios and
> agencies to quickly assess a screenplay. Be honest and specific, not generically positive.
> recommendation must be exactly one of "pass", "consider", or "recommend"."

The user prompt (`prompts.py:435-438`) is `Title: ... / Author: ... / Scene-by-scene overview: ...`.

**The word "genre" never appears in either prompt.** What makes the model emit a genre at all is the
JSON grammar (`grammar.py:178`), which declares the field:

    "genre" : string

And the grammar's own string rule (`grammar.py:39`) is `string ::= "\"" char* "\""` - `char*` means
zero or more, so **an empty genre is schema-valid**.

So: the model is told "write coverage", is forced by the schema to emit a genre field, is given no
list of genres, no definition, no examples, and no constraint - and whatever it types is then used
as the key to the entire genre subsystem.

**Step 3 - used raw.** `genre.py:108` reads `coverage["genre"]` directly. There is no validation, no
normalisation at the boundary, no controlled vocabulary, and no user confirmation anywhere in the
product.

**Step 4 - two independent resolvers.** The string is passed to *two* lookups that were written
separately and are not kept in sync:

| resolver | file | answers the question |
|---|---|---|
| `KnowledgeBase.for_genre()` | `knowledge_base.py:135-170` | which **KB rules** apply? |
| `genre.conventions_for()` | `genre.py:82-99` | which **audience-expectation checklist** applies? |

`for_genre` has a hand-written alias table (`knowledge_base.py:112-127`) plus four fallback
strategies. `conventions_for` has **no alias table at all** - it does an exact dict hit, then a
substring test, then a word-overlap test, then defaults to drama (`genre.py:79`).

That asymmetry is where everything in section 3 comes from.

---

## 2. How the rules load - the routing, with real numbers

### 2.1 The exclusion

`is_genre_scoped(rule)` is true when the rule has a non-empty `genre` field
(`rules_context.py:103`). Both `rules_for_category` and `rules_for_pass` skip those rules unless
`include_genre_rules=True` is passed explicitly (`:141`, `:162`).

The only caller that passes `True` anywhere in the repo is a test
(`tests/test_rules_grounding.py:404`). **Production never includes genre rules in a generic pass.**

### 2.2 What that costs each pass - measured

| generic pass | rules it gets | rules it would get with genre rules | withheld |
|---|---:|---:|---:|
| `scene_function` | 29 | 39 | **10** |
| `dialogue` | 21 | 23 | **2** |
| `character` | 83 | 105 | **22** |
| `structure` | 15 | 28 | **13** |
| `theme` | 6 | 23 | **17** |
| `plot_thread` | 13 | 39 | **26** |
| | | | **90** |

The withheld total is exactly the 90 genre-tagged rules, and I verified the converse too: **no
genre-tagged rule reaches any generic pass.** The exclusion is total and clean.

Note the ratios. The `theme` pass loses 17 of its 23 rules (74%). `plot_thread` loses 26 of 39
(67%). These are the two most heavily genre-scoped levels in the KB.

### 2.3 The 90 rules, by genre and by home level

90 of 263 rules (34.2%) carry a genre tag. The eight genre files are **100% tagged** - every rule in
`action.json`, `comedy.json`, `drama.json`, `horror.json`, `mystery.json`, `romance.json`,
`scifi.json`, `thriller.json` is genre-scoped. Three other files (`dialogue_advanced.json`,
`story_macro.json`, `visual_storytelling.json`) contain the *field* but set it to `null`, so they
contribute nothing here.

| genre | rules | | home taxonomy level | rules |
|---|---:|---|---|---:|
| comedy | 12 | | plot_thread | 26 |
| horror | 12 | | character | 22 |
| thriller | 12 | | story_macro | 17 |
| action | 11 | | structure_pacing | 13 |
| drama | 11 | | scene | 10 |
| mystery | 11 | | dialogue | 2 |
| romance | 11 | | | |
| scifi | 10 | | | |

### 2.4 Where they are delivered - and the consequence

All 90 arrive in **one** place: the genre fragment, appended to the genre-convention call
(`genre.py:113-119`). For horror that fragment is 9,762 characters; for drama 8,211.

The consequence is worth stating plainly, because it is not obvious:

> A horror script's two **character-level** horror rules are excluded from the character pass and
> evaluated in the genre pass instead. Their findings are emitted with category `"genre"`
> (`genre.py:104`), so they surface in the report under **"Genre Conventions"**
> (`report.py:55`) - not under "Character", where a writer looking for character notes would go.

The same is true for the 26 plot_thread rules, the 17 story_macro rules, the 13 structure rules and
the 10 scene rules. Genre-scoping moves them out of their own category's report section and into
one bucket. The rule still fires; it just reports from a different drawer.

### 2.5 The rest of the chain

- Genre is printed to the writer as coverage (`report.py:118`), and the genre category appears in
  the score weights (`app.js:2158`) and the report labels (`app.js:3605`).
- If the genre comes back **empty**, the genre pass is skipped entirely
  (`pipeline.py:779`) - and, to the system's credit, the category is recorded as `"failed"` rather
  than silently dropped (`pipeline.py:816-819`). That is disclosed, not hidden.
- `RulesContext.dialogue_rules_for_genre()` (`rules_context.py:270-292`) is **dead code** - no
  caller anywhere in the repo. It was written to scope dialogue rules by genre; it never runs.

---

## 3. Where it breaks - all measured

### 3.1 Two resolvers, contradictory answers, on 20 of 44 labels

Because `for_genre` and `conventions_for` match differently, the same label can resolve to one genre
for the rules and a *different* genre for the conventions. Full table:
`docs/kb_genre_resolver_mismatch.csv`. The worst cases:

| label the model might produce | KB rules applied | conventions applied | |
|---|---|---|---|
| **"Drama / Thriller"** | drama (11) | **thriller** | opposite halves |
| **"Horror-Comedy"** | comedy (12) | **horror** | opposite halves |
| **"Sci-Fi Thriller"** | scifi (10) | **thriller** | opposite halves |
| "Romantic Comedy" | romance (11) | **comedy** | opposite halves |
| "action comedy" | action (11) | **comedy** | opposite halves |
| "scifi" | scifi (10) | **drama** (default!) | KB's own tag spelling |
| "Science Fiction" | scifi (10) | **drama** | |
| "SF" | scifi (10) | **drama** | |
| "Rom-Com" | romance (11) | **drama** | |
| "crime" / "detective" / "whodunit" | mystery (11) | **drama** | |
| "spy" / "suspense" | thriller (12) | **drama** | |
| "supernatural" | horror (12) | **drama** | |

**The first row is not hypothetical.** `"Drama / Thriller"` is the exact label the real `gun_pen_2`
fixture produced. On that script, the KB hands the genre pass 11 drama rules while the hardcoded
checklist tells the model to test thriller conventions. The thriller rules and the thriller
conventions never meet.

Why they disagree, mechanically: `for_genre` path 2 walks its tag table in *file order* (action,
comedy, drama, horror, mystery, romance, scifi, thriller) and returns the first tag found as a
substring - so "dramathriller" hits **drama** first. `conventions_for` walks its dict in *literal
order*, where `thriller` is the first key - so "drama / thriller" hits **thriller** first. Two
arbitrary iteration orders, pointing opposite ways.

### 3.2 The `scifi` trap

The KB tags its rules `"scifi"`. The conventions dict keys its list `"sci-fi"`. `conventions_for`
strips punctuation only via `.lower()`, not by removing it, so:

- `"scifi"` -> not an exact key, `"sci-fi" in "scifi"` is False, word overlap is 0 -> **drama**
- `"Sci-Fi"` -> exact key -> sci-fi

So the sci-fi conventions fire for *one specific spelling*, and the KB's own canonical tag spelling
is not it. "Science Fiction" and "SF" also miss.

### 3.3 Nine labels get zero genre rules

`western`, `fantasy`, `coming of age`, `noir`, `neo-noir`, `biopic`, `satire`, `mockumentary`, and
anything unrecognised resolve to **zero** KB rules. `western` and `fantasy` are the sharp ones:
`GENRE_CONVENTIONS` has full, well-written checklists for both (`genre.py:59-70`) but the KB has no
rules tagged for either, so those scripts get a genre pass with conventions and no craft grounding.

### 3.4 A non-genre label can match by substring

`for_genre` path 2 tests `tag in want or want in tag`, so derived words match:

- `"actionable"` -> 11 action rules
- `"dramatic"` -> 11 drama rules
- `"docudrama"` -> 11 drama rules

Unlikely from a coverage pass, but it shows the matcher is doing string containment where it should
be doing genre identity.

### 3.5 Two smaller things

- **The model cannot cite these rules.** `to_prompt_fragment()` (`knowledge_base.py:58-75`) emits
  the rule's *name*, attribution, definition, detection signal, counter-considerations, severity and
  tier - but **never the rule id**. Meanwhile `CITATION_INSTRUCTION_SUMMARY` (`prompts.py:44`) tells
  the model: *"If a specific named principle below grounds this finding, set rule_id to that
  principle's id."* The model is asked to cite an id it was never shown, and `app.js:4171` renders
  that id in the tooltip. This affects all 263 rules, not just genre - flagged as a cross-cutting
  observation, not a genre finding.
- **The writer cannot correct the genre.** There is no UI or API to set or override it. It is
  displayed (`report.py:118`) and used, but never editable.

---

## 4. How efficient is the detection?

Honest split: what I measured, and what I could not.

**Measured:**

| | |
|---|---|
| KB share gated on the one genre string | **90 / 263 = 34.2%** |
| Model guidance for the genre field | **none** - the word does not appear in the coverage prompt |
| Schema constraint on the value | **none** - any string, including empty |
| Validation / normalisation at the call site | **none** |
| Resolver disagreement rate over realistic labels | **20 / 44 = 45%** |
| Realistic labels that yield zero genre rules | **9** |
| Genres with conventions but no rules | **2** (western, fantasy) |
| User-facing override | **none** |
| Dead genre-aware code path | **1** (`dialogue_rules_for_genre`) |
| Behaviour when the label is empty | pass skipped, category reported `failed` (disclosed) |

**Not measured - and I am not going to pretend otherwise:**

- **How often the model's label is right.** That needs a live model and a labelled corpus. I did not
  run one.
- **Whether the label is stable across runs.** Temperature is not pinned per-field, so the genre
  could differ between two analyses of the same script - which would mean the rules applied differ
  between runs.
- **Whether the applied genre changes any finding.** Unmeasurable without a live model.

The only real-data sample available is tiny and I will not dress it up: the two fixtures in
`studio_projects/` report `"Drama"` and `"Drama / Thriller"`. **n=2.** One of the two is a hybrid
that triggers the resolver contradiction. That is an illustration of a structural defect, not
evidence about the model's accuracy.

**The structural verdict, which does not depend on the unmeasured parts:** the mechanism is
well-built and the exclusion is clean and total. The *input* to the mechanism is one unconstrained
string invented with no guidance, consumed by two resolvers that disagree with each other 45% of the
time on labels a model plausibly produces. A 34%-of-KB gate is a lot of downstream behaviour to hang
on a string with no contract.

---

## 5. The brainstorm - a working screenwriter's read

Written in two voices, as asked: a script consultant giving notes on a draft, and a co-writer
embedded in the tool. Every rule id it cites was checked against the KB and the proposal CSV; the
checkable claims all held, with one nuance noted at the end.

### 5.1 Voice 1 - the consultant

**THEME.** First: can I state the controlling idea as a cause-and-effect sentence derived from the
climax (`controlling_idea`)? Then: where is it *dramatised* rather than named? Never asserted flat:
"preachy", "not earned", "disconnected". `weiland_theme_from_arc`'s own detection signal is
literally "feels preachy" - a taste verdict, not a test. The theory ladder runs Egri's premise ->
McKee's controlling idea (cause and effect) -> Weiland's Lie/Truth arc -> Martell's dramatise
through choices, not speeches (`martell_theme_through_characters`) -> execution note: cut the line
where someone names the theme.

**SCENE.** First: what value turns, and by how much (`scene_must_turn`, McKee)? Then the unit:
goal, conflict, disaster (Swain). Never flat: "this scene is filler - cut it". `scene_necessity_test`
and `obligatory_scene` are low for good reason; withholding an obligatory confrontation can be a
choice. Ladder: McKee's value-shift (governing) -> Swain's G-C-D (unit) -> Field/Snyder placement ->
Lakin hook and enter-late/leave-early (execution). Note `lakin_scene_hook` and
`enter_late_leave_early` say the same thing at two different tiers today.

**CHARACTER.** First: what does this person want versus need, and what does a choice under pressure
reveal (`want_vs_need`, `true_character_vs_characterization`)? Never flat: "no arc", "unnecessary
character" - `character_arc_change` and `character_necessity` are both low, and flat arcs are
legitimate. Ladder: Egri's three-dimensional contradiction -> McKee's true character and cast
polarization -> Hauge/Truby want-need-wound -> Weiland's Lie/Ghost -> Seger's earned transformation.

**DIALOGUE.** First: subtext - does anyone say the opposite of what they mean
(`on_the_nose_vs_subtext`, `martell_say_the_opposite`)? Never flat: "these characters sound alike" -
`distinct_character_voice` is low and its own text admits stylometry is unreliable for a local
model. Ladder: McKee's exposition-as-ammunition (dialogue is action) -> subtext -> economy
(`martell_three_line_rule`) -> lexical tells (`martell_see_and_say_rule`).

**PLOT THREAD.** First: causality - remove this scene, does anything break (`lyons_story_spine`)?
Then setups and payoffs (`chekhovs_gun`). Never flat: "this thread is abandoned" -
`setup_payoff_general` is low, and mystery red herrings are legitimate. Ladder: Aristotle (no deus ex
machina) -> McKee's progressive complications and subplot resonance -> Chekhov's economy -> Martell's
plants and payoffs.

**RELATIONSHIP.** First: is there a credible antagonistic force (`antagonist_force_balance` -
McKee's "force", not a literal villain). Never flat: "the relationship changed implausibly" -
`relationship_dynamic_consistency` is low, and marked time skips justify offscreen change. There are
only **two** rules in this level. The file is too thin to carry a taxonomy level on its own.

**REVISION.** First: was the story found, or is the prose merely polished
(`epps_revision_first_draft`)? Never flat: any claim about the writer's *process* -
`epps_rewrite_distance` ("too close to the work") is unobservable in a screenplay. Ladder: Epps on
discovery -> Stein on show-versus-tell -> Zinsser on lexical clutter.

**STORY MACRO.** First: the controlling idea plus the genre contract
(`genre_convention_fulfillment`). Never flat: "the theme contradicts itself" - `theme_contradiction`
is low, because telling intended irony from an accident is the hardest read in the KB. Ladder:
McKee's controlling idea -> theme and anti-theme -> Snyder's genre types -> world rules.

**STRUCTURE / PACING.** First: where is the ending, and does the middle escalate
(`martell_know_your_destination`, `pacing_escalation`)? Never flat: "your midpoint is wrong".
Field, Snyder and Vogler are *lenses*; `three_act_structure`'s own counter-considerations say to
flag it as a discussion. Ladder: Aristotle/Field acts -> McKee's five-part design -> Snyder's 15 and
Vogler's 12 as placement lenses -> Gulino's sequences.

### 5.2 Voice 2 - the co-writer

The taxonomy ladder *is* the delivery schedule. The governing band speaks once, at the end of a
pass. The structural band batches at scene or sequence boundaries. The execution band may interrupt.
Never interrupt on a graph rule.

| area | interrupt when | stay silent | ask |
|---|---|---|---|
| theme | theme is stated in dialogue and dramatised nowhere | through Act 1 - theme is legitimately latent | "is this the idea the climax proves?" - once |
| scene | a scene has no turn AND no function | short transitions and Swain sequels | "what changes here?" |
| character | a choice under pressure contradicts established values with no setup | flat-arc leads | "what does she want here versus need?" |
| dialogue | a pattern (three or more instances) | climactic confessions | "what does he want from her in this exchange?" |
| plot thread | an emphasised, planted object never returns | mystery red herrings | "is this thread meant to be open?" |
| relationship | the tenor jumps between consecutive shared scenes with no intervening event | marked time skips | "what happened between these two scenes?" |
| revision | lexical tells, and only if a line edit was requested | while drafting | structure before line, never both at once |
| story macro | rarely - theme belongs to the writer | mostly | question form only |
| structure/pacing | the middle plateaus or the ending is not set up | deliberate non-linear work | "where does the story turn from reaction to action?" |

The consequence worth stating plainly: **20 of 23 dialogue rules are `high` today**, so a co-writer
honouring its own tiers would comment on nearly every line. The tier question is a UX question, not
polish.

### 5.3 Genre is a contract, not a label

A genre is not a shelf a script sits on; it is a **promise the audience holds you to**, and the
promise has different terms in each. Horror promises that the rules of the threat will be coherent
and that safety is unavailable. Romance promises that the obstacle to intimacy is real and that the
resolution is specific to these two people. Comedy promises escalation - the same setup must pay off
differently each time. The promise is what the audience is *testing you against*, which is why a
mislabel is not cosmetic: it changes which promises the tool holds the script to.

Real scripts are frequently two genres at once, and each blend promises something neither genre
promises alone: *Alien* (horror's rules inside science fiction's world - the promise is that the
rules will be learned before the crew is lost), *Get Out* (horror's escalation carrying a social
thriller's argument), *Shaun of the Dead* (comedy's escalation and horror's rules, one feeding the
other), *Parasite* (drama's moral complexity executed as a thriller's structural turn), *Blade
Runner* (science fiction's rules in noir's moral weather), *When Harry Met Sally* (comedy's engine
resolving into romance's specific ending), *Se7en* (mystery's fair-clue contract broken
deliberately - which is the point), *Little Miss Sunshine* (comedy's tone carrying drama's
stakes).

What a writer **loses** when the tool resolves a hybrid to one half is exactly the half that made
the script interesting. On a "Drama / Thriller" script, the tool applies drama's rules and thriller's
conventions. The thriller *rules* - active protagonist, villain drives the plot, reversals escalate,
ticking clock - are never applied, while the drama *conventions* - values over goals, wants deepen -
are never tested. The script is judged against one genre's craft standards and a different genre's
audience expectations, and the writer is told nothing about which was which.

### 5.4 The hard question: filter, weight, or lens?

- **(a) Hard-exclude** (today's rule-side behaviour). Clean and predictable: a romance never sees
  horror's rules. But it is all-or-nothing, and it makes the tool's judgement entirely hostage to a
  single unconstrained label. Wrong label -> silently wrong rules, no recourse.
- **(b) Dedicated genre pass** (today's delivery-side behaviour). Keeps the generic passes
  genre-neutral, which is right - a scene note should be a scene note. But it *relocates* 90 rules
  away from their home category (section 2.4), and it puts them all in one call, so a script-level
  horror rule competes with a line-level dialogue rule for the same 1,200-token budget.
- **(c) Soft prior** - run genre rules in their home pass, but weighted by whether the genre matches.
  Best craft outcome: a horror script's horror character rules land in the *character* notes, where
  a writer looks for them. But it needs the genre to be trustworthy, and it weakens the clean
  genre-neutrality of the generic passes.

**Recommendation:** (a)+(b) are the right skeleton and should stay; the failure is not the shape, it
is that the input is unverified and the two resolvers contradict each other. Fix the input (options
1-3) *before* considering (c). Moving to a soft prior on top of a 45%-disagreement resolver would
just distribute the wrong rules more widely.

### 5.5 Hybrid and wrong labels

A hybrid should deliver **both** genres' rules, with the primary genre's rules unscored and the
secondary's marked as conditional - because the whole reason a writer blends two genres is that both
promises are live. Picking one half is a silent loss (section 5.3).

When the label is wrong, or empty, the tool should say so rather than guess. The specific failure a
working writer would notice and be annoyed by is not "the genre is wrong" - it is **"the notes are
for a different film."** Romance notes on a thriller read as a tool that did not understand the
script, and there is currently no way to correct it. That is the annoyance: not an error message,
but confidently irrelevant craft advice with no off switch.

### 5.6 What I would cut

From the 90 genre-tagged ids, these read as generic craft wearing a genre label, or as the same
claim filed under several genres:

- **The agency cluster** - `action_hero_must_be_active`, `thriller_active_protagonist`,
  `thriller_characters_active`. Three ids, one principle. It is not genre-specific at all; every
  genre needs an active protagonist.
- **The villain-strength pair** - `action_villain_strength`, `thriller_villain_strength`.
- **The physical-death trio** - `action_stakes_physical_death`, `horror_stakes_physical_death`,
  `thriller_physical_death_stakes`. Three copies of one rule, and all three stay `high` in the
  pending proposal.
- **The logline pair** - `mystery_logline_clarity`, `scifi_simple_logline`. The same demand for a
  clear logline, filed twice.
- **The midpoint pair** - `comedy_midpoint_physical_intimacy`, `romance_midpoint_no_return`. Two
  names for the midpoint no-return beat.
- **`drama_transformation_earned` and `seger_transformation_earned`** - identical names, two levels.

And the reverse case: `comedy_subtext_not_literal` and `drama_dialogue_subtext` are the only two
dialogue-level rules in the whole genre set. "Dialogue should carry subtext" is not a comedy rule or
a drama rule - it is the governing principle of dialogue in every genre, and it is currently
unreachable from the dialogue pass for every script.

*Verification note: all ids above exist and the tier claims check out against
`docs/kb_tier_proposal.csv`. One nuance - the midpoint pair is filed at the same tier today (both
`high` -> `medium`), so the duplication is real but the tiers do not diverge there.*


---

## 6. Self-critique of this analysis

1. **I did not measure model accuracy, and section 4 says so.** The one thing that would actually
   answer "how efficient is the detection" - running the model on a labelled set and scoring the
   genre field - I did not do. Everything I report is structural, not empirical about the model.

2. **My first framing of the file count was wrong and I corrected it.** `grep -l '"genre"'` matches
   11 rule files, which invites the conclusion that 11 files carry genre tags. Only 8 do; the other
   3 set `"genre": null`, and the grep matched the *key*. I checked each file's actual tags before
   writing the 90-rule figure.

3. **The `conventions_for` "bug" is a mismatch, not necessarily a defect in isolation.** If the two
   resolvers were never meant to agree - one scoping rules, one scoping a checklist - then some
   divergence is by design. What is not defensible is that they diverge in *opposite directions on
   the same label*, with no documented relationship between them. I have stated it as a
   contradiction rather than assuming which side is wrong, because deciding that is a craft call,
   not a code call.

4. **The 45% disagreement rate depends on my label list.** I chose 44 labels to be realistic
   (tag spellings, aliases, hybrids, unmapped genres, derived adjectives). A different list gives a
   different rate. The specific contradictions are facts; the percentage is a property of my sample.
   The CSV is committed so the list can be challenged.

5. **The "reporting from a different drawer" consequence (2.4) is read from the code, not observed
   in a running report.** I traced `category="genre"` to `report.py:55`, but I did not generate a
   real report for a horror script and look at where the notes landed. It is a code-path
   conclusion and is stated as such.

6. **The writer-voice brainstorm in section 5 is a subagent on the same model, not a real
   consultant.** I verified every checkable claim it made against `docs/kb_tier_proposal.csv` -
   all of them held - but its craft opinions are opinions, and I have not labelled them as
   authoritative.

---

## 7. Options, for your decision - nothing implemented

Ranked by how much they change, smallest first.

**Option 1 - give the genre field a contract (small, high leverage).**
Tell the coverage prompt what a genre is and what values are acceptable, and normalise the returned
label at the boundary (trim, lowercase, collapse punctuation, split on separators into a primary and
secondary genre). This does not change the routing at all; it makes the string the routing depends
on well-formed. It would fix the `scifi` trap and the "SF" / "Science Fiction" misses outright.

**Option 2 - make the two resolvers agree (small, mechanical).**
Either route both through one shared normaliser plus one alias table, or delete `conventions_for`'s
own matching and have it consume the same resolved genre that `for_genre` produces. This removes the
opposite-halves contradiction by construction.

**Option 3 - let the writer see and correct the genre (medium, product decision).**
The genre is displayed but not editable. Since it gates 34% of the KB, a wrong label silently
changes the analysis with no recourse. A visible, editable genre - or a confirmation step - is the
only defence that does not depend on the model being right.

**Option 4 - decide what a hybrid label means (medium, craft decision).**
Today a hybrid resolves to one half for rules and the other half for conventions, by iteration
order. Should a hybrid deliver **both** genres' rules? A primary with a secondary at reduced weight?
Or should the tool refuse to guess and ask? This is the question section 5 argues.

**Option 5 - fill the two gaps (small).**
`western` and `fantasy` have conventions but no rules. Either author the rules or drop the
checklists so the tool does not imply grounding it does not have. Relatedly, delete or wire up the
dead `dialogue_rules_for_genre`.
