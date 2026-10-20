# G5 recovery options: correct first task, no waived gate

**Date:** 2026-10-20

**Branch:** `arena/e6a57b71-screenplay-studio`

**Last measured runtime:** `422f4ebbd52cc46074eac30f08c5a45b5992a123`

**Status:** G5 FAIL. Options only; no G5 presentation change implemented.

## Corrected baseline

The runner used one fixed report/project directory across revisions, without reseeding:

| Runtime | First measured row | Card height | Bottom | Gate meaning |
|---|---|---|---|---|
| `bd86a8e` | Index 1, an incorrectly admitted ungrounded demo finding | 262px in the controlled comparison | 882px | The former PASS is withdrawn; wrong subject |
| `422f4eb` | Index 0, the real grounded continuity finding | 357px | 978px | FAIL against `<900px` |

The correct card was also 357px at `07e5d9b`. The flags change is not the cause of this height: no flag means no added wrapper. The long observation and quote are actual reading content.

Recover **more than 78px**, not exactly 78px. A bottom of 900px still fails. If the card remains 357px, its top coordinate must be `<543px`; that is a derived budget, not a new measurement.

The separate AA/probe/isolation patch changes pointer opacity and test behavior, not card geometry. It does not repair G5.

## A. Compact non-evidence presentation first

Keep the observation, quote, attribution, truth judgment, intent and rank explanation available as currently agreed. Recover height from measured non-evidence layout: stacked worklist/panel chrome, repeated labels, gaps or explanatory presentation.

- Keep scope counts, filters, current-scene orientation and the uncalibrated warning visible and truthful.
- Preserve font floors and the single closed action row.
- Retain a visible rank reason on every card. Moving it behind `marks` is not an equivalent migration.
- Do not count relocating a hint from the card into the preamble as a saving unless the first actionable card's measured bottom actually improves.
- The earlier preamble was already compacted. Whether another >78px exists safely is unknown until component rectangles are measured.

**Trade-off:** preserves the evidence-reading contract, but may not supply sufficient height without harmful crowding.

## B. Explicit quote preview with expansion, only if needed

Keep the falsifiable observation fully visible. For a long quotation, show an explicitly labelled preview with a keyboard-accessible expand/collapse control and the complete original quotation on expansion. Short quotes stay unchanged.

- Requires approval: this changes the default deep-card evidence presentation.
- No silent `overflow: hidden`, arbitrary clipping, lost text or reduced reading font.
- Keep verification, attribution and the writer's truth/intent controls visible.
- Existing deep-card content checks survive. Add actual default/expanded render and keyboard coverage; do not make them pass merely because hidden text remains in the DOM.
- Measure default G5 and expanded-state behavior separately. Do not claim that quote-only preview supplies >78px without the quote rectangle and a browser measurement. It may need a combination with A.

**Trade-off:** creates room for action while retaining the full citation, but introduces a disclosure and can hide useful context. Collapsing the observation as well is not my recommendation.

## Recommendation and next measurement

Start with A's measurement, not another speculative CSS patch. Consider B only if adequate non-evidence savings cannot be demonstrated and its trade-off is approved.

On the same fixed report, record:

1. Served revision and first actionable finding index/content id/category/groundedness.
2. The pre-card blocks: arrival, notices, filter, current-scene strip, section header, queue preamble and lane/category heading.
3. Card components: header, issue, why, observation, quote, verification/flags, attribution, verdict, actions, intent hint and rank reason.
4. The card's top/bottom and lens scroll position, at 1440×900 with no manual scrolling.

Then choose the smallest supported change and rerun the unchanged `<900px` gate on the pushed revision. No predicted pixel saving is an acceptance result. Real-writer validation and register calibration remain separate requirements.
