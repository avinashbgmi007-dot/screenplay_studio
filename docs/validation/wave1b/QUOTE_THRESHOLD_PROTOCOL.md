# Quote-threshold calibration protocol

**Status:** blank protocol. No authentic register material has been collected,
no goldens have been adjudicated, and `FUZZY_MATCH_THRESHOLD` remains `0.72`.
This harness needs no model, server, GPU or network.

## Purpose and boundary

Measure how the deterministic verifier classifies real and deliberately
distorted quotes in the product's supported registers. This is a test of the
**verifier's classification band**, not of whether an LLM produced a good
finding. The verifier is a pure function of `(finding, document)`; a model is
irrelevant to this measurement.

This packet does not change `verifier.py`, the threshold, the UI, or the
verification denominator. It prepares the intake and decision procedure.

## What the existing harness is, and is not

`tests/test_verifier_perturbation_bands.py` is a **synthetic structural probe**.
It uses one invented English line and two synthetic scene shapes. It reports
the band and pins only threshold-independent properties. Do not present its
numbers as register calibration, and do not fill it with invented Hindi,
Telugu, or Tamil pages.

The real-material harness is intentionally not written in this prep step. The
existing harness's bucket and scene-shape concepts are the extension points;
the material must arrive before the runner is built or run.

## Registers and material

Required registers: **Hindi (Devanagari), Telugu, Tamil**. English/Tenglish may
be included as a control, not as a substitute for the three required registers.

Material must be:

- authentic, permissioned writing in the register, not machine translation and
  not invented by the calibrator;
- accompanied by the surrounding scene text used for matching;
- stored locally, with a hash of the source and extracted scene text;
- adjudicated by a person qualified in that register.

Minimum counts:

| Stage | Cases per register | Per bucket | Scenes |
|---|---|---|---|
| Pilot (checks intake and harness only) | 15 | 3 | at least 3 |
| Decision-grade | 50 | 10 | at least 5 |

Do not change the threshold on pilot data. If a register cannot supply the
minimum, record the gap; do not pad it with translations or synthetic lines.

## Expected-verdict buckets

Each case is one quote with one intended bucket. The adjudicator records the
transformation so a later reader can audit it.

| Bucket | Definition | Expected verdict |
|---|---|---|
| `verbatim` | Exact line from the source scene. | `verified` |
| `formatting_only` | Same words; only case, punctuation or wrapper characters differ. | `verified` |
| `light_paraphrase` | One or two content words changed; meaning preserved. | `verified` (the verifier's stated lenient intent) |
| `heavy_paraphrase` | About half the content words changed; meaning preserved. | `not_found` |
| `fabricated` | Topically adjacent but not present in the source. | `not_found` |

`no_quote` and `scene_not_found` are real verifier statuses, but they are not
calibration buckets here; do not manufacture them. If they occur on a
quote-bearing case, report them as data and investigate the intake.

## Intake schema and provenance

One row per case in `templates/quote_material_intake.csv`. Required fields:

| Field | Meaning |
|---|---|
| `case_id` | Stable unique case identifier. |
| `material_id` | Source work/packet identifier. |
| `register` | `hindi`, `telugu`, or `tamil` (plus optional control). |
| `work_title` | Title or neutral source label. |
| `author_or_source` | Author/source as permitted to record. |
| `permission_status` | Who permitted local use, and the scope. |
| `permission_evidence` | Local pointer to the permission record. |
| `source_file` | Original file name/path. Never upload it. |
| `source_sha256` | SHA-256 of the original source file. |
| `collection_date` | ISO date. |
| `collected_by` | Collector identifier. |
| `scene_id` | Stable scene identifier in the source. |
| `scene_number` | Number used by the parsed document. |
| `scene_text_path` | Local path to the exact scene text used. |
| `scene_sha256` | SHA-256 of that extracted scene text. |
| `quote_id` | Stable quote identifier. |
| `quote_text` | The quote as tested. |
| `bucket` | One of the five buckets above. |
| `expected_verdict` | `verified` or `not_found` from the table. |
| `transformation` | What was changed, in enough detail to audit it. |
| `adjudicator_id` | Qualified adjudicator identifier. |
| `adjudication_status` | `agreed`, `disputed`, or `excluded`. |
| `second_adjudicator_id` | Optional 20% blind second review. |
| `language_script` | e.g. Devanagari, Telugu, Tamil. |
| `word_count` | Quote word count. |
| `sensitive_content` | yes/no; never copy sensitive text into reports. |
| `storage_location` | Local-only folder. |
| `notes` | Caveats, source context, exclusions. |

Provenance is not satisfied by "a native speaker said it was fine." Record the
permission basis and the exact source. If permission or provenance is missing,
exclude the case and say why; do not fill the gap.

## Scene shapes

The verifier's score depends on how much other text is in the scene. Test every
case in two authentic shapes:

1. **Cited element:** the source element containing the quote, as parsed.
2. **Full scene:** the complete real scene containing that element.

Do not use synthetic padding. Report a **shape flip** when the same case
changes status between shapes. A shape flip is a finding about the verifier,
not a reason to delete the case.

## Procedure

1. Confirm permission, provenance, adjudication, and local storage.
2. Copy the source and extracted scene text into a local working folder; hash
   both. Do not edit the source.
3. Build the intake rows. Assign `expected_verdict` from the bucket table.
   Record every transformation.
4. Freeze the application revision and the parser output used to build the
   `ScriptDocument`.
5. Run the verifier at the shipped `FUZZY_MATCH_THRESHOLD` (`0.72`) for every
   `(case, scene shape)` pair. Do not change the threshold during the run.
6. Record `status`, `confidence`, `matched_scene`, and any verifier note.
7. Compare against the golden. Count false negatives (real quote not verified)
   and false positives (fabricated quote verified) separately.
8. Produce the report in a fixed order: register, bucket, case_id, shape.
9. Stop. Do not tune, then re-run, then report the tuned result. Any proposed
   threshold change is a separate decision and task.

## Deterministic report

The runner may be Python or an extension of the existing harness; it must not
call a model. Outputs:

- `report.md` — human-readable tables.
- `report.json` — same data with sorted keys, for audit.

Case-level columns:

`case_id, register, bucket, shape, expected, status, confidence,
delta_to_threshold, matched_scene, golden_match, note`

Summary columns, grouped by register × bucket × shape:

`n, verified, not_found, other_status, verified_rate, median_confidence,
min_confidence, max_confidence, false_negatives, false_positives,
shape_flips`

Also report:

- every scene-shape flip, with both statuses and confidences;
- every `not_found` on `verbatim` or `formatting_only` (hard failure);
- every `verified` on `fabricated` (false acceptance);
- the threshold (`0.72`) and application revision on every report;
- the exact intake hash so a report can be tied to its material.

No aggregate may hide a register-level failure. Do not pool the three required
registers into one rate unless the per-register table is shown beside it.

## Decision criteria

- `0.72` remains unchanged until a decision-grade set exists and a separate
  decision is approved.
- `verbatim` and `formatting_only` must have **zero** false negatives. A single
  failure is a hard finding and blocks a threshold recommendation until
  explained.
- `fabricated` must have **zero** false positives. A single acceptance is a
  hard finding.
- Light-paraphrase false negatives and heavy-paraphrase false positives are the
  primary trade-off. Report them per register and per shape; do not average
  them away.
- If the bands overlap within a register, or the verdict changes with scene
  shape, a single global scalar is not supported. The options are the ones in
  `2026-10-15-fuzzy-match-threshold-design.md` §5.5: per-register threshold,
  composition-aware rule, or a third verdict state. Choosing among them needs
  the data, not this prep.
- Any change is a separate implementation task with its own acceptance tests.
  This packet does not authorize it.

## Stop rules

Stop and record why if:

- permission, provenance, or local storage is missing;
- material is synthetic, machine-translated, or invented by the calibrator;
- no qualified adjudicator is available for a register;
- a case has no authentic scene context;
- the source or parser revision is not frozen;
- a run changes the threshold midstream;
- a pilot is presented as decision-grade evidence.

## Artifacts

- `templates/quote_material_intake.csv` — blank intake rows.
- Local source/scene text with hashes.
- `report.md` and `report.json` from the frozen run.
- `analysis.md` with the decision, limits, and any excluded material.

Do not add example pages or example verdicts to the blank templates.
