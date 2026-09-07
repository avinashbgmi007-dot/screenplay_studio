# User Personas — Script Doctor Studio

Primary user types and their goals. Grounded in `docs/designs/product-ui-alignment.md`
(the 2026-08 positioning doc) and the observed usage patterns in NOTES.md.
Last synced 2026-09-06.

> The system is single-user, local-first, and privacy-first. There are no roles,
> permissions, or multi-tenancy — "personas" here are writer archetypes that shape
> information architecture and progressive disclosure, not access control.

---

## Persona 1 — "The Aspiring Screenwriter" (Avinash, primary)

**Who:** Early-to-intermediate screenwriter actively learning craft (books, courses,
YouTube). Writes in English, Tenglish, or Telugu-influenced registers. Works on a laptop
with a local llama-server.

**Goals:**
- Understand WHY a script doesn't work, not just THAT it doesn't.
- Get expert-grade feedback between drafts without paying for human coverage.
- Learn craft vocabulary (setup/payoff, scene function, character dials) while fixing.
- Have a mentor (Sameer) who knows their past work and habits.

**Behaviors:**
- Uploads `.fountain`/`.fdx`/`.pdf` drafts; runs the full analysis; walks the Fix Queue.
- Treats findings as lessons: clicks a finding → reads the attributed rule + verified
  quote → discusses with Sameer → accepts or dismisses.
- Uses the Idea room to develop premises before writing pages; graduates them later.
- Writes margin notes in their own hand; stashes passages that might be reused.

**Needs from the UI:** progressive revelation (Level 1 upload→score→top findings, up to
Level 4 master views); honest connection status (green/amber/red); craft-first language
everywhere; no cloud anxiety — nothing leaves the machine.

**Pains:** overwhelmed by pro-coverage tools; generic AI chatbots that praise everything;
mojibake in Indian-language scripts; losing work to crashes.

---

## Persona 2 — "The Working Rewriter" (the same writer, mid-draft)

**Who:** The primary persona a few drafts deep, now in the revision loop. The mode the
product spends most of its time in.

**Goals:**
- Fix specific diagnosed issues without breaking what works.
- Track which findings are addressed vs still present as they edit.
- Compare drafts to verify improvement; keep an undoable edit trail.
- Timebox work sessions (sprint timer) and keep momentum on the desk.

**Behaviors:**
- Lives in Revision view + Problem Board; uses inline line editing (double-click) with
  change stars and undo/redo.
- Accepts rewrite candidates selectively; never bulk-applies.
- Reorders scenes on the Beat Board, exports a reordered draft, compares against previous.
- Returns after days away and resumes exactly where they left off (session restore).

**Needs from the UI:** locality — finding → quote → line → edit in one glance; the dawn
meter as progress fuel; drafts/compare/diff as honest before/after evidence.

**Pains:** silent analysis failures; edits that vanish; state that resets on reload.

---

## Persona 3 — "The Idea-Stage Writer" (the same writer, pre-pages)

**Who:** The primary persona before a draft exists — developing the premise on the blank
canvas with Sameer on call.

**Goals:**
- Pressure-test a premise with the Premise Doctor lens before committing pages.
- Capture spark-of-inspiration fragments (the Stash, idea pages) without ceremony.
- Graduate into a project without losing the conversation or the memory.

**Behaviors:**
- Free-writes on the Spark Wall; uses `/sameer <ask>` and explore chips.
- Uses dictation (mic) for hands-free capture; hover-translates Sameer's replies.
- Keeps several ideas alive on the shelf; graduates the strongest.

**Needs from the UI:** a blank page that autosaves near-instantly (300ms) and never feels
like a form; strict isolation (idea chat never sees past scripts); one idea = one session.

---

## Anti-persona — "The Collaborative Team / Studio Executive"

Not served: no sharing, no comments-for-others, no cloud sync, no multi-user roles, no
export-to-studio-workflow. The product is deliberately one writer, one desk, one machine.
Requests in this direction should be treated as out of scope (see AGENTS.md principles).

---

## Derived design rules

1. **One writer, many modes** — the three personas are the same person at different stages;
   never build role-based UI.
2. **Progressive revelation is mandatory** — Level 1 (score + top findings) must land before
   Level 3 (fix queue + co-write) unlocks itself visually.
3. **Mentor-led** — Sameer is a character, not a chatbot; Dr. Sushruta argues with the
   script, never the writer.
4. **Language reality** — English/Tenglish/Hindi/Telugu/Tamil (reports) and Hinglish
   (translate) are first-class; UI chrome stays English.
5. **Privacy is a feature** — zero external requests; demo model honestly amber.
