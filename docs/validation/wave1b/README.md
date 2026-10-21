# Wave 1B validation packets

**Status:** PREPARED ONLY. No writer sitting has occurred, no participant
judgment has been collected, and no calibration run has been executed. These
are blank protocols and templates.

**Frozen application revision:** `5dd0baa` closed Wave 1A. This packet adds
documentation only; it does not change application code, tests, gates, IMPACT
weights or `FUZZY_MATCH_THRESHOLD`. Run empirical sessions only after the owner
confirms this revision (or deliberately freezes a later one) and supplies the
inputs below.

## Packets

| Packet | Protocol | Blank record |
|---|---|---|
| Writer sitting | [WRITER_SITTING_PROTOCOL.md](WRITER_SITTING_PROTOCOL.md) | [WRITER_SITTING_RESULTS.md](WRITER_SITTING_RESULTS.md) |
| IMPACT calibration | [IMPACT_CALIBRATION_PROTOCOL.md](IMPACT_CALIBRATION_PROTOCOL.md) | [templates/impact_case_manifest.csv](templates/impact_case_manifest.csv) + [templates/impact_blind_set.csv](templates/impact_blind_set.csv) |
| Quote-threshold calibration | [QUOTE_THRESHOLD_PROTOCOL.md](QUOTE_THRESHOLD_PROTOCOL.md) | [templates/quote_material_intake.csv](templates/quote_material_intake.csv) |

## Immediate owner input (only these three)

1. **Writer availability** — a real writer, a time, and consent.
2. **The draft and report to use** — a permissioned full-length screenplay and
   the real-model report produced from it.
3. **Authentic register material** — permissioned Hindi, Telugu, and Tamil
   pages with provenance, for the separate quote-threshold packet.

Do not ask for calibration decisions, weight changes, or UI changes yet. The
remaining preconditions below are confirmed when execution is scheduled.

## Required before empirical execution

1. A real writer's availability, consent, and a permissioned full-length draft
   plus the report produced from it.
2. A frozen application revision and a local (loopback) model that produced a
   real analysis. Demo-model output is not calibration data.
3. For quote matching: permissioned, authentic Hindi, Telugu, and Tamil
   register material, with an adjudicator qualified in each register.
4. An observer/facilitator where the packet calls for one, and a local-only
   storage location for notes and recordings.

## Explicit non-goals and stop conditions

- Do not fill writer answers with simulated or inferred judgments.
- Do not invent native-language pages, translations, or goldens.
- Do not change IMPACT weights or the `0.72` quote-match threshold in this
  wave's prep.
- Do not treat a pilot, a single sitting, or preparation as completed
  empirical validation.
- Do not expand this into UI implementation. Findings about the UI are recorded
  for a separate, approved change.
- Stop and record the blocker if consent, permission, provenance, a real
  revision, or a qualified adjudicator is missing.

## Data handling

Participant and source material stay local. Use participant IDs, not names, in
records. Do not upload drafts, screen recordings, or register material to a
cloud service. Keep raw notes and recordings in a permissioned local folder;
the owner decides retention and deletion.
