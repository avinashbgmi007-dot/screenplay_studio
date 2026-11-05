# Evidence screenshots: what was shrunk, and how it was checked

Gap 112. The repo carried **71 PNGs of UI evidence, 30.6 MB**, and the audit
entries in this directory cite them by filename. They are the proof for a lot of
what the register claims, so the goal was to make them cheaper **without losing
any of the wording they show**.

**Result: 30.6 MB → 12.9 MB (−58%) across 60 files. 11 files were left at their
original size because no safe reduction existed for them.**

## Why palette quantisation, not resizing

I tried both. A half-size downscale keeps the text but makes it **visibly
mushy** — I compared crops side by side at native size, and the small print
turns grey and soft. That destroys exactly what the evidence is for. Quantising
to a 128–256 colour palette leaves **every pixel where it is** and only coarsens
the colour table, which is invisible on a flat-palette UI screenshot. That is
where the size was.

## How "still readable" was measured

No OCR binary is available in this environment, so the check is structural:
threshold the image, label the dark blobs, and count those sized like glyphs
(3–26 px tall, 2–22 px wide). If quantisation makes two letters merge or a line
dissolve, that count collapses and the median glyph height drops. A converted
file had to keep **≥80% of its glyph blobs** and its median glyph height; the
file was re-read **after writing** and re-checked, so the verification covers
what landed on disk, not what was intended.

On top of the metric I looked at crops myself, native against converted, on the
worst-scoring file and on a flat-UI board shot: indistinguishable at 1:1.

A file that failed at 128 colours was retried at 256; if both failed it was left
untouched. That is the 11 below.

## The 11 left at original size

```
docs/audit/evidence-2026-09-30/shots/j2_analysis_complete.png
docs/audit/evidence-2026-09-30/shots/j2_stage_ladder_running.png
docs/audit/evidence-2026-09-30/shots/j3_dawn_after_mark.png
docs/audit/evidence-2026-09-30/shots/j3_evidence_lens.png
docs/audit/evidence-2026-09-30/shots/j3_legacy_feedback_tabs.png
docs/audit/evidence-2026-09-30/shots/j4_beatboard_exported.png
docs/audit/evidence-2026-09-30/shots/j4_draft_activated.png
docs/audit/evidence-2026-09-30/shots/j4_inline_edit.png
docs/audit/evidence-2026-09-30/shots/j7_xss_title_literal.png
docs/audit/validation-25-gap1-board-filter.png
impl-shots/ESC-5-sushruta-reply.png
```

## A real finding that fell out of this pass

Three groups of PNGs are **byte-identical under different names**:

```
j4_beatboard_exported.png == j4_draft_activated.png == j4_inline_edit.png
impl-shots/A-scene_function.png == impl-shots/B-character-dials.png
impl-shots/A02-evidence-lens-full.png == impl-shots/B-coverage.png
```

At most one caption per group can be correct; the others are showing the wrong
screenshot for what the audit text says they show. That is an **evidence**
defect, not a size one, and it is filed rather than silently deleted — deduping
would have destroyed the signal. See gap 112's row for the follow-up.

## Reproducing

The conversion is not a script in the repo (it needs Pillow + scikit-image, and
it was a one-off). What it did is fully described above; re-running it on these
files is idempotent in effect (a quantised PNG re-quantises to nearly the same
size) but the originals are recoverable from git history if any image is
disputed.

**Not done:** history was not rewritten. The blobs from earlier commits stay in
`.git`, so a fresh clone is still ~19 MB of history; the working tree and every
future checkout are 33% smaller. Rewriting history on a shared branch would
change every commit SHA and is the branch owner's call, not mine.
