# Writer sitting protocol

**Status:** blank protocol. Do not run until every pre-execution item is
checked. This is not a simulated review and not a substitute for a writer.

## Purpose

Observe whether the shipped desk keeps its promises to a real writer on a real,
full-length screenplay. The session judges felt usefulness and comprehension,
not whether the automated machinery is green. It must not be used to tune
IMPACT weights or the quote threshold; those are separate packets.

## Preconditions

- [ ] A real writer has agreed to one sitting and understands the purpose.
- [ ] Written or recorded consent covers notes, optional screen/audio capture,
      and local storage.
- [ ] The writer has provided a full-length draft they own or may use, plus
      permission to analyze it locally.
- [ ] A real analysis report exists for that draft. It was produced by a real
      `llama-server`, not the demo model.
- [ ] The application revision is frozen and recorded. The Wave 1A baseline is
      `5dd0baa`; do not silently test a different revision.
- [ ] The app and model server are local/loopback. No draft or recording leaves
      the machine.
- [ ] An observer/facilitator is present and has read the recording rules.
- [ ] A fresh project copy is available; the writer's working draft is not at
      risk. Analysis may be pre-run to avoid a long idle wait, but the writer
      must not see findings before the session. Record `preanalyzed=yes/no`.

## Roles

- **Writer:** the participant. They drive; the observer does not operate the
  desk for them.
- **Observer/facilitator:** keeps time, takes timestamped notes, asks the
  questions neutrally, and protects the writer's consent and draft.
- **Owner:** confirms the frozen revision, real-model provenance, permissions,
  and storage location. The owner does not coach during the session.

## Materials and setup

- Local studio command:
  `python -m screenplay_studio.webapp_server --port 8500 --projects-dir ./studio_projects`
- Chrome at `http://localhost:8500`.
- The project must show a served revision matching the frozen revision. Record
  `/api/health` including `demo_model: false`.
- Have the 13-question results template open in a private local file, not on
  the writer's screen.

## Session script (about 45–60 minutes, plus any analysis wait)

### 0. Opening (3 min)

Read a neutral framing:

> "This is a usability sitting, not a test of you or your script. I'm watching
> how the desk works for you. Please think aloud when it is comfortable. If
> something is confusing, say so; that is useful data. I may ask you to stop
> and answer a question. You can stop at any time."

Confirm consent and whether recording is on. Start with the writer's own words
about what they expect from an analysis pass; do not describe the features.

### 1. Arrival (5–8 min)

Open the project. Do not point at anything. Let the writer look, then ask:

- "What do you notice first?"
- "What are you about to do?"

Let them act for up to three minutes. Record whether they read the arrival
strip, skipped it, or used the fix-loop call to action. Do not explain the
strip. Ask the arrival-strip questions from the results template while the
surface is still in front of them.

### 2. Fix loop (12–15 min)

Ask the writer to press the **fix loop** control (or use the loop button) and
step through at least ten findings with N/↓ and P/↑. Then have them handle five
to eight findings by hand, or mark them addressed / next pass, and make one
small edit in the manuscript.

Observe:

- whether the eyes stay on the manuscript;
- whether the dock card auto-open helps or distracts;
- whether mark / next pass / Discuss / copy are where their hands are;
- whether Esc leaves cleanly with the Evidence lens still open.

Do not describe the shortcuts unless the writer cannot find the control after
a genuine attempt. Record the assistance.

### 3. Second pass (wait + 5 min)

Run the second analysis. When the arrival strip appears, stop the writer before
they touch anything and ask:

> "Before you do anything else: what did you do first?"

That answer is the primary arrival datum. Record it verbatim, then let them
continue. Ask the three arrival-strip questions again only where the template
calls for it; do not turn the session into a questionnaire.

### 4. New pass and marks (8–10 min)

Return to the loop with the new pass live. Inspect deferred and ghosted marks.
Ask whether the marks read honestly and whether the counts agree with what the
writer sees on the page and in the queue. Any page/queue disagreement is a bug;
record the exact scene, finding and visible numbers rather than debating it.

### 5. Desk and rooms (8–10 min)

Let the writer use the desk without a task for a few minutes: talk with Sameer,
open the Dr. Sushruta lens, toggle dawn/night once. Then ask the remaining
questions. Record what they actually did, not what they say they usually do.

### 6. Close (3 min)

Ask the final "anything noisy, slow, or wrongly defaulted" question. Thank the
writer. Stop recording. Confirm what will be kept and for how long. Do not
summarize findings as conclusions in front of the writer.

## Observer notes

Record one row per event with:

- timestamp and session step;
- surface (arrival strip, filter row, fix queue, manuscript, Evidence lens,
  chat, etc.);
- what the writer did, in observable terms;
- the writer's exact words where possible;
- hesitation (approximately how long), error, recovery, or assistance;
- whether the observer had to explain a control, and what was said;
- environment/server issues separately from product observations.

Mark each note **observed** or **reported**. Do not write inferred feelings as
observations. Do not lead with feature names the writer has not used. Neutral
prompts only: "What are you looking at?", "What did you expect there?", "What
would you do next?"

## Recording rules

- Notes are the default. Screen, audio, or video capture requires explicit
  consent and a stated local storage location.
- Use a participant ID, not a name, in the results file.
- Do not upload the draft, report, notes, or recordings to a cloud service.
- If the writer withdraws consent, stop, delete any capture if requested, and
  record only that the session was aborted.
- Do not quote the draft's creative content in the results unless it is needed
  to explain a UI failure; prefer scene numbers and finding IDs.

## Stop and abort conditions

Stop the session and record the reason if:

- the writer withdraws consent or is uncomfortable;
- the served revision does not match the frozen revision;
- the report came from the demo model or is missing;
- the app loses the writer's edits or cannot save safely;
- the writer is too fatigued to continue;
- the observer cannot remain neutral or the session turns into coaching.

Do not replace a missed answer with an inference. Leave it blank and say why.

## What this session may and may not decide

It may decide whether the arrival strip, filter row, fix loop, ink, evidence
lens, and defaults feel useful enough to keep, revise, or investigate. It may
not change IMPACT weights or the `0.72` threshold. It may not be reported as a
completed empirical calibration until the real session has occurred and the
results file is filled from it.

## Stop before execution

The required owner inputs are: writer availability, the permissioned draft and
report, a frozen revision, and a qualified observer. If any is missing, leave
the packet blank and pause.
