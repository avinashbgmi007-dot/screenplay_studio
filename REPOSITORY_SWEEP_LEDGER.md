# Repository sweep ledger

Inventory: 665 Git-tracked paths as of this review. Listing is mechanical, not proof that a file has been fully reviewed. Files and binary artifacts require different review methods. Generated planning documents and untracked concept images are outside this tracked inventory.

Status key: **I** = inventoried only or review depth not individually verified; **P** = selected portions inspected or exercised, not a complete line-by-line review. No file is represented as fully reviewed merely because tests pass. This ledger deliberately errs on the conservative side; the absence of P does not rule out prior inspection.

## (repository root) (27)

- [I] `.env.example`
- [I] `.gitignore`
- [I] `AGENTS.md`
- [I] `API_UI_COVERAGE_CRITIQUE_2026-10-04.md`
- [I] `CHANGELOG.md`
- [I] `CLAUDE.md`
- [I] `CONTEXT.md`
- [I] `CRITIQUE_OF_ASHNA_VERDICT_2026-10-04.md`
- [I] `CRITIQUE_OF_EVIDENCE_PRECISE_INK_2026-10-04.md`
- [I] `DESIGN.md`
- [I] `GATE3_REMEASUREMENT_2026-10-06.md`
- [I] `GATE5_CONSENT_FORM_2026-10-07.md`
- [I] `GATE5_PREFLIGHT_2026-10-07.md`
- [I] `GATE5_WRITER_STUDY_PROTOCOL_2026-10-06.md`
- [I] `GATE7B_SPLIT_RESIDUAL_2026-10-07.md`
- [I] `I2_MEASUREMENT_2026-10-06.md`
- [I] `LICENSE`
- [I] `MANIFEST.in`
- [I] `NOTES.md`
- [I] `README.md`
- [I] `TODOS.md`
- [I] `UI_CHANGES_DEFERRED.md`
- [I] `package-lock.json`
- [I] `package.json`
- [I] `pyproject.toml`
- [I] `requirements.lock.txt`
- [I] `requirements.txt`

## .agents (2)

- [I] `.agents/skills/sameer-humanizer/SKILL.md`
- [I] `.agents/skills/script-doctor-humanizer/SKILL.md`

## .claude (1)

- [I] `.claude/settings.json`

## .github (1)

- [I] `.github/workflows/ci.yml`

## docs (187)

- [I] `docs/API_ROUTE_MAP.md`
- [I] `docs/ARCHITECTURE.md`
- [I] `docs/CLI_REFERENCE.md`
- [I] `docs/CODEBASE_MAP.md`
- [I] `docs/CRITICAL_REVIEW_2026-09-18.md`
- [I] `docs/DATA_FORMATS.md`
- [I] `docs/DEVELOPMENT.md`
- [I] `docs/FULL_FEEDBACK_AUDIT_VERDICTS.md`
- [I] `docs/IMPROVEMENT_AUDIT.md`
- [I] `docs/KB_CATEGORY_ORDER.md`
- [I] `docs/KB_GENRE_ROUTING.md`
- [I] `docs/KB_TIER_REVIEW.md`
- [I] `docs/PAIN3_SESSION_RUN_CARD.md`
- [I] `docs/PHASE_B_FV_FOLD_SPEC.md`
- [I] `docs/PRD.md`
- [I] `docs/PROJECT_MEMORY.md`
- [I] `docs/PROJECT_OVERVIEW.md`
- [I] `docs/REAL_WRITER_VALIDATION.md`
- [I] `docs/REDESIGN_MASTER_PLAN.md`
- [I] `docs/SESSION_SUMMARY.md`
- [I] `docs/STATE_STORES.md`
- [I] `docs/TESTING.md`
- [I] `docs/UI_REDESIGN_PROPOSAL.md`
- [I] `docs/UI_UX_SPECIFICATION.md`
- [I] `docs/USER_PERSONAS.md`
- [I] `docs/audit/2026-09-30_e2e_readiness_report.md`
- [I] `docs/audit/2026-09-30_feedback_uiux_analysis.md`
- [I] `docs/audit/FIX_TRACKER.md`
- [I] `docs/audit/e2e_production_readiness_2026-09-25_round3.md`
- [I] `docs/audit/evidence-2026-09-30/README.md`
- [I] `docs/audit/evidence-2026-09-30/boot_evidence.json`
- [I] `docs/audit/evidence-2026-09-30/j1_console.json`
- [I] `docs/audit/evidence-2026-09-30/j1_j2_evidence.json`
- [I] `docs/audit/evidence-2026-09-30/j2_console.json`
- [I] `docs/audit/evidence-2026-09-30/j3_j4_console.json`
- [I] `docs/audit/evidence-2026-09-30/j3_j4_evidence.json`
- [I] `docs/audit/evidence-2026-09-30/j5_j6_j7_console.json`
- [I] `docs/audit/evidence-2026-09-30/j5_j6_j7_evidence.json`
- [I] `docs/audit/evidence-2026-09-30/phase2_api_evidence.json`
- [I] `docs/audit/evidence-2026-09-30/phase3_suites_evidence.json`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_boot_probe.py`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_common.py`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_j1_j2_journeys.py`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_j3_j4_journeys.py`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_j5_j6_j7.py`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_phase2_api_probes.py`
- [I] `docs/audit/evidence-2026-09-30/scripts/audit_phase3_suites.py`
- [I] `docs/audit/evidence-2026-09-30/shots/boot_welcome_1440x900.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j1_desk_after_upload.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j2_analysis_complete.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j2_stage_ladder_running.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j2c_failure_banner.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j3_dawn_after_mark.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j3_evidence_lens.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j3_legacy_feedback_tabs.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j3_loop_active.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j4_beatboard_exported.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j4_draft_activated.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j4_inline_edit.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j5_graduated_desk.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j5_idea_canvas.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j6_sushruta_lens.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j7_deep_links.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j7_palette.png`
- [I] `docs/audit/evidence-2026-09-30/shots/j7_xss_title_literal.png`
- [I] `docs/audit/feedback_probe_session.py`
- [I] `docs/audit/implementation_2026-09-24.md`
- [I] `docs/audit/implementation_2026-09-25_round4.md`
- [I] `docs/audit/pain3-session-00-dashboard.png`
- [I] `docs/audit/pain3-session-01-manuscript.png`
- [I] `docs/audit/pain3-session-02-board-widened.png`
- [I] `docs/audit/pain3-session-03-loop.png`
- [I] `docs/audit/plan_validation_2026-09-25.md`
- [I] `docs/audit/plan_validation_2026-09-25_revised.md`
- [I] `docs/audit/production_readiness_2026-09-20.md`
- [I] `docs/audit/production_readiness_2026-09-21.md`
- [I] `docs/audit/production_readiness_2026-09-24.md`
- [I] `docs/audit/production_readiness_2026-10-01.md`
- [I] `docs/audit/stage_pain3_session.py`
- [I] `docs/audit/ui_evidence_findings_2026-09-20.md`
- [I] `docs/audit/ui_ux_architecture_review_2026-09-20.md`
- [I] `docs/audit/ui_ux_restructure_plan_2026-09-20.md`
- [I] `docs/audit/validation-24-gap3-arrival-zero.png`
- [I] `docs/audit/validation-25-gap1-board-filter.png`
- [I] `docs/audit/validation-26-gap4-consult-context.png`
- [I] `docs/audit/validation-29-gap5-scoped-strip.png`
- [I] `docs/audit/validation-d10.py`
- [I] `docs/audit/validation-d2.py`
- [I] `docs/audit/validation-d3.py`
- [I] `docs/audit/validation-d4.py`
- [I] `docs/audit/validation-d5.py`
- [I] `docs/audit/validation-d6.py`
- [I] `docs/audit/validation-d7.py`
- [I] `docs/audit/validation-d8.py`
- [I] `docs/audit/validation-d9.py`
- [I] `docs/debates/sam-vs-premise-doctor-2026-08-15.md`
- [I] `docs/demo_transcripts/sameer_session.md`
- [I] `docs/demo_transcripts/sushruta_session.md`
- [I] `docs/design/R2_PRIMITIVES_SPEC.md`
- [I] `docs/design/R3_COMPOSITES_SPEC.md`
- [I] `docs/design/directions2026/1-marked-proof.html`
- [I] `docs/design/directions2026/2-night-room.html`
- [I] `docs/design/directions2026/3-the-consultation.html`
- [I] `docs/design/directions2026/4-screening-room-v2.1.html`
- [I] `docs/design/directions2026/4-screening-room-v2.html`
- [I] `docs/design/directions2026/4-screening-room.html`
- [I] `docs/design/directions2026/5-atelier.html`
- [I] `docs/design/directions2026/6-the-typescript.html`
- [I] `docs/design/directions2026/audit/a11y_audit_v21.py`
- [I] `docs/design/directions2026/audit/compute_fixes.py`
- [I] `docs/design/directions2026/audit/contrast_audit.py`
- [I] `docs/design/directions2026/audit/smoke_directions.py`
- [I] `docs/design/directions2026/audit/smoke_v21_interactions.py`
- [I] `docs/design/directions2026/audit/smoke_v2_interactions.py`
- [I] `docs/design/directions2026/index.html`
- [I] `docs/design/ink-layer/INK_LAYER_SPATIAL.md`
- [I] `docs/design/ink-layer/LIVE_VERIFICATION.md`
- [I] `docs/design/ink-layer/OPEN_QUESTIONS.md`
- [I] `docs/design/ink-layer/OPEN_QUESTIONS_ANSWERS.md`
- [I] `docs/design/ink-layer/REAL_SCRIPT_RESULTS.md`
- [I] `docs/design/ink-layer/SELF_CRITIQUE.md`
- [I] `docs/design/ink-layer/backend-patches/README.md`
- [I] `docs/design/ink-layer/backend-patches/revision_stale_guard.py`
- [I] `docs/design/ink-layer/backend-patches/webapp_apply_edits.py`
- [I] `docs/design/midnight-desk-preview.html`
- [I] `docs/design/scene-first/ARCHITECTURE.md`
- [I] `docs/design/scene-first/VERDICT_CHANNEL_SPEC.md`
- [I] `docs/design/scene-first/accuracy_meter.py`
- [I] `docs/design/scene-first/accuracy_report.py`
- [I] `docs/design/scene-first/grounding_pass.py`
- [I] `docs/design/scene-first/observation_rewrite.py`
- [I] `docs/design/ux2026/archive-v1/atlas-grid.html`
- [I] `docs/design/ux2026/archive-v1/console-dark.html`
- [I] `docs/design/ux2026/archive-v1/index.html`
- [I] `docs/design/ux2026/archive-v1/margins.html`
- [I] `docs/design/ux2026/archive-v1/paper-desk.html`
- [I] `docs/design/ux2026/archive-v1/shared/app.js`
- [I] `docs/design/ux2026/archive-v1/shared/base.css`
- [I] `docs/design/ux2026/archive-v1/splitline.html`
- [I] `docs/design/ux2026/archive-v1/spotlight-stage.html`
- [I] `docs/design/ux2026/beatwall.html`
- [I] `docs/design/ux2026/index.html`
- [I] `docs/design/ux2026/lumen.html`
- [I] `docs/design/ux2026/nocta-standalone.html`
- [I] `docs/design/ux2026/nocta.html`
- [I] `docs/design/ux2026/shared/graphics.css`
- [I] `docs/design/ux2026/shared/kit.css`
- [I] `docs/design/ux2026/shared/kit.js`
- [I] `docs/design/ux2026/shared/motion.css`
- [I] `docs/design/ux2026/wireframes/test.html`
- [I] `docs/designs/product-ui-alignment.md`
- [I] `docs/gun_pen.pdf_full_feedback_audit_—_split_matrix,_es-09142139.plan.md`
- [I] `docs/kb_category_taxonomy_order.csv`
- [I] `docs/kb_genre_resolver_mismatch.csv`
- [I] `docs/kb_tier_proposal.csv`
- [I] `docs/kb_tier_proposal.json`
- [I] `docs/superpowers/plans/2026-08-12-feedback-cowrite-rooms.md`
- [I] `docs/superpowers/plans/2026-08-12-writer-relationship-memory.md`
- [I] `docs/superpowers/plans/2026-08-26-studio-ux-v2-redesign.md`
- [I] `docs/superpowers/plans/2026-08-27-radically-distinct-uiux-previews.md`
- [I] `docs/superpowers/plans/2026-08-27-uiux-redesign-6-previews.md`
- [I] `docs/superpowers/plans/2026-08-30-six-worlds-uiux.md`
- [I] `docs/superpowers/plans/2026-09-01-feedback-view-popup-cleanup.md`
- [I] `docs/superpowers/plans/2026-09-01-uiux-session-summary.md`
- [I] `docs/superpowers/plans/2026-09-22-one-feedback-room.md`
- [I] `docs/superpowers/plans/2026-09-29-analyze-refreshes-strip-count.md`
- [I] `docs/superpowers/plans/2026-10-11-findings-accuracy-guards.md`
- [I] `docs/superpowers/plans/2026-10-11-findings-recall.md`
- [I] `docs/superpowers/plans/2026-10-11-ledger-precision.md`
- [I] `docs/superpowers/plans/2026-10-12-absence-falsification.md`
- [I] `docs/superpowers/plans/2026-10-13-identity-uncertainty.md`
- [I] `docs/superpowers/specs/2026-08-12-feedback-cowrite-rooms-design.md`
- [I] `docs/superpowers/specs/2026-08-12-writer-relationship-memory-design.md`
- [I] `docs/superpowers/specs/2026-08-13-midnight-desk-ui-redesign-design.md`
- [I] `docs/superpowers/specs/2026-08-26-studio-ux-v3-three-architectures-design.md`
- [I] `docs/superpowers/specs/2026-08-27-radically-distinct-uiux-redesigns-design.md`
- [I] `docs/superpowers/specs/2026-08-27-uiux-redesign-6-previews-design.md`
- [I] `docs/superpowers/specs/2026-08-30-v4-six-worlds-uiux-design.md`
- [I] `docs/superpowers/specs/2026-09-22-one-feedback-room-design.md`
- [I] `docs/superpowers/specs/2026-10-02-post-analysis-ia-design.md`
- [I] `docs/superpowers/specs/2026-10-11-findings-accuracy-design.md`
- [I] `docs/superpowers/specs/2026-10-11-ledger-precision-design.md`
- [I] `docs/superpowers/specs/2026-10-12-absence-falsification-design.md`
- [I] `docs/superpowers/specs/2026-10-13-identity-uncertainty-design.md`
- [I] `docs/superpowers/specs/_expert-dataflow-audit.md`
- [I] `docs/superpowers/specs/_expert-redteam-optionA.md`
- [I] `docs/superpowers/specs/_expert-ux-critique.md`

## impl-shots (20)

- [I] `impl-shots/A-dialogue.png`
- [I] `impl-shots/A-scene_function.png`
- [I] `impl-shots/A-structure.png`
- [I] `impl-shots/A00-baseline-board.png`
- [I] `impl-shots/A01-widened-board.png`
- [I] `impl-shots/A02-evidence-lens-full.png`
- [I] `impl-shots/B-character-dials.png`
- [I] `impl-shots/B-coverage.png`
- [I] `impl-shots/B-craft-panels.png`
- [I] `impl-shots/C-clean-bill.png`
- [I] `impl-shots/C00-phantom-addressed.png`
- [I] `impl-shots/C01-desk-status.png`
- [I] `impl-shots/ESC-0-loop-bar.png`
- [I] `impl-shots/ESC-1-sameer-quote-pinned.png`
- [I] `impl-shots/ESC-2-sameer-reply.png`
- [I] `impl-shots/ESC-3-discussed-tag.png`
- [I] `impl-shots/ESC-4-sushruta-why-seeded.png`
- [I] `impl-shots/ESC-5-sushruta-reply.png`
- [I] `impl-shots/PASS2-arrival-strip.png`
- [I] `impl-shots/audit_results.json`

## knowledge_base (31)

- [I] `knowledge_base/README.md`
- [I] `knowledge_base/__init__.py`
- [I] `knowledge_base/index.json`
- [I] `knowledge_base/knowledge_base.py`
- [I] `knowledge_base/rules/action.json`
- [I] `knowledge_base/rules/body_language.json`
- [I] `knowledge_base/rules/character.json`
- [I] `knowledge_base/rules/comedy.json`
- [I] `knowledge_base/rules/continuity.json`
- [I] `knowledge_base/rules/dialogue.json`
- [I] `knowledge_base/rules/dialogue_advanced.json`
- [I] `knowledge_base/rules/drama.json`
- [I] `knowledge_base/rules/horror.json`
- [I] `knowledge_base/rules/mystery.json`
- [I] `knowledge_base/rules/pitch.json`
- [I] `knowledge_base/rules/plot_thread.json`
- [I] `knowledge_base/rules/power_dynamics.json`
- [I] `knowledge_base/rules/psychology.json`
- [I] `knowledge_base/rules/relationship.json`
- [I] `knowledge_base/rules/revision.json`
- [I] `knowledge_base/rules/romance.json`
- [I] `knowledge_base/rules/scene.json`
- [I] `knowledge_base/rules/scene_design.json`
- [I] `knowledge_base/rules/scifi.json`
- [I] `knowledge_base/rules/story_macro.json`
- [I] `knowledge_base/rules/structure_pacing.json`
- [I] `knowledge_base/rules/theme.json`
- [I] `knowledge_base/rules/thriller.json`
- [I] `knowledge_base/rules/visual_storytelling.json`
- [I] `knowledge_base/rules/writing_habits.json`
- [I] `knowledge_base/schema.json`

## screenplay_analyzer (26)

- [I] `screenplay_analyzer/__init__.py`
- [I] `screenplay_analyzer/__main__.py`
- [I] `screenplay_analyzer/cli.py`
- [I] `screenplay_analyzer/continuity.py`
- [P] `screenplay_analyzer/dedupe.py`
- [I] `screenplay_analyzer/deterministic_utils.py`
- [I] `screenplay_analyzer/dials.py`
- [P] `screenplay_analyzer/feedback_filter.py`
- [P] `screenplay_analyzer/finding_integrity.py`
- [I] `screenplay_analyzer/formatting_check.py`
- [I] `screenplay_analyzer/genre.py`
- [I] `screenplay_analyzer/grammar.py`
- [I] `screenplay_analyzer/graph.json`
- [I] `screenplay_analyzer/llm_client.py`
- [I] `screenplay_analyzer/llm_client_base.py`
- [P] `screenplay_analyzer/observation_pass.py`
- [I] `screenplay_analyzer/pacing.py`
- [P] `screenplay_analyzer/pipeline.py`
- [I] `screenplay_analyzer/principles_engine.py`
- [P] `screenplay_analyzer/prompts.py`
- [P] `screenplay_analyzer/report.py`
- [I] `screenplay_analyzer/reveal_scan.py`
- [P] `screenplay_analyzer/rules_context.py`
- [I] `screenplay_analyzer/setup_payoff.py`
- [P] `screenplay_analyzer/verifier.py`
- [I] `screenplay_analyzer/voice.py`

## screenplay_cowriter (20)

- [I] `screenplay_cowriter/__init__.py`
- [I] `screenplay_cowriter/__main__.py`
- [I] `screenplay_cowriter/cli.py`
- [P] `screenplay_cowriter/context.py`
- [P] `screenplay_cowriter/craft_history.py`
- [I] `screenplay_cowriter/discovery.py`
- [P] `screenplay_cowriter/engine.py`
- [P] `screenplay_cowriter/language_meta.py`
- [P] `screenplay_cowriter/language_mirror.py`
- [P] `screenplay_cowriter/llm_client.py`
- [P] `screenplay_cowriter/memory.py`
- [P] `screenplay_cowriter/models.py`
- [P] `screenplay_cowriter/orientation.py`
- [P] `screenplay_cowriter/peer.py`
- [I] `screenplay_cowriter/persona_specs.py`
- [P] `screenplay_cowriter/personas.py`
- [P] `screenplay_cowriter/reply_transforms.py`
- [I] `screenplay_cowriter/server.py`
- [P] `screenplay_cowriter/store.py`
- [I] `screenplay_cowriter/writer_library.py`

## screenplay_parser (15)

- [P] `screenplay_parser/__init__.py`
- [I] `screenplay_parser/__main__.py`
- [P] `screenplay_parser/cli.py`
- [P] `screenplay_parser/export.py`
- [P] `screenplay_parser/fdx_parser.py`
- [I] `screenplay_parser/graph_output.json`
- [P] `screenplay_parser/heuristics.py`
- [P] `screenplay_parser/knowledge_graph.py`
- [P] `screenplay_parser/models.py`
- [P] `screenplay_parser/pdf_parser.py`
- [P] `screenplay_parser/quotematch.py`
- [P] `screenplay_parser/scenekey.py`
- [P] `screenplay_parser/stats.py`
- [P] `screenplay_parser/structure.py`
- [P] `screenplay_parser/text_parser.py`

## screenplay_studio (106)

- [I] `screenplay_studio/__init__.py`
- [I] `screenplay_studio/__main__.py`
- [P] `screenplay_studio/beatboard.py`
- [P] `screenplay_studio/character_track.py`
- [P] `screenplay_studio/cli.py`
- [I] `screenplay_studio/demo_model.py`
- [P] `screenplay_studio/diff.py`
- [P] `screenplay_studio/feedback_ledger.py`
- [P] `screenplay_studio/ideas.py`
- [P] `screenplay_studio/jsonio.py`
- [I] `screenplay_studio/logsetup.py`
- [P] `screenplay_studio/manifest.py`
- [P] `screenplay_studio/metrics.py`
- [P] `screenplay_studio/net_guard.py`
- [P] `screenplay_studio/notes.py`
- [P] `screenplay_studio/orchestrator.py`
- [P] `screenplay_studio/pass_history.py`
- [P] `screenplay_studio/revision.py`
- [I] `screenplay_studio/sample.py`
- [P] `screenplay_studio/stash_store.py`
- [P] `screenplay_studio/stt.py`
- [P] `screenplay_studio/watch.py`
- [P] `screenplay_studio/webapp/app.js`
- [P] `screenplay_studio/webapp/core.js`
- [I] `screenplay_studio/webapp/design_session.html`
- [I] `screenplay_studio/webapp/fonts/Caveat-706a1c41.woff2`
- [I] `screenplay_studio/webapp/fonts/CourierPrime-094f4033.woff2`
- [I] `screenplay_studio/webapp/fonts/CourierPrime-6664e8d0.woff2`
- [I] `screenplay_studio/webapp/fonts/CourierPrime-cdc2c233.woff2`
- [I] `screenplay_studio/webapp/fonts/DMSans-i400-5da946c1.woff2`
- [I] `screenplay_studio/webapp/fonts/DMSans-n400-9fea608a.woff2`
- [I] `screenplay_studio/webapp/fonts/IBMPlexMono-0bc96cd0.woff2`
- [I] `screenplay_studio/webapp/fonts/IBMPlexMono-e2661bcc.woff2`
- [I] `screenplay_studio/webapp/fonts/InstrumentSerif-i400-5a51946d.woff2`
- [I] `screenplay_studio/webapp/fonts/InstrumentSerif-n400-5eb09b5a.woff2`
- [I] `screenplay_studio/webapp/fonts/JetBrainsMono-n400-83c005d4.woff2`
- [I] `screenplay_studio/webapp/fonts/SourceSerif4-20a22824.woff2`
- [I] `screenplay_studio/webapp/fonts/SourceSerif4-a15d607a.woff2`
- [I] `screenplay_studio/webapp/fonts/SpecialElite-ee78eab2.woff2`
- [I] `screenplay_studio/webapp/index.html`
- [I] `screenplay_studio/webapp/preview-design/beatwall.html`
- [I] `screenplay_studio/webapp/preview-design/lumen.html`
- [I] `screenplay_studio/webapp/preview-design/nocta.html`
- [I] `screenplay_studio/webapp/preview-design/r2_primitives.html`
- [I] `screenplay_studio/webapp/preview-design/shared/graphics.css`
- [I] `screenplay_studio/webapp/preview-design/shared/kit.css`
- [I] `screenplay_studio/webapp/preview-design/shared/kit.js`
- [I] `screenplay_studio/webapp/preview-design/shared/motion.css`
- [I] `screenplay_studio/webapp/preview-ia/_ia.js`
- [I] `screenplay_studio/webapp/preview-ia/index.html`
- [I] `screenplay_studio/webapp/preview-ink-layer/build-single.mjs`
- [I] `screenplay_studio/webapp/preview-ink-layer/core.js`
- [I] `screenplay_studio/webapp/preview-ink-layer/detent.css`
- [I] `screenplay_studio/webapp/preview-ink-layer/index.html`
- [I] `screenplay_studio/webapp/preview-ink-layer/ink-layer-preview.html`
- [I] `screenplay_studio/webapp/preview-ink-layer/ink-layer.css`
- [I] `screenplay_studio/webapp/preview-ink-layer/ink-layer.js`
- [I] `screenplay_studio/webapp/preview-ink-layer/tests/core.test.mjs`
- [I] `screenplay_studio/webapp/preview-ink-layer/tests/dom.test.mjs`
- [I] `screenplay_studio/webapp/preview-ink-layer/tests/measure-anchors.mjs`
- [I] `screenplay_studio/webapp/preview-next/_lab.css`
- [I] `screenplay_studio/webapp/preview-next/_lab.js`
- [I] `screenplay_studio/webapp/preview-next/_payload.js`
- [I] `screenplay_studio/webapp/preview-next/canvas-first.html`
- [I] `screenplay_studio/webapp/preview-next/chat-first.html`
- [I] `screenplay_studio/webapp/preview-next/command-first.html`
- [I] `screenplay_studio/webapp/preview-next/index.html`
- [I] `screenplay_studio/webapp/preview-next/inspector-first.html`
- [I] `screenplay_studio/webapp/preview-next/report-first.html`
- [I] `screenplay_studio/webapp/preview-next/stream-first.html`
- [I] `screenplay_studio/webapp/preview-r4/direction-1-nocta.html`
- [I] `screenplay_studio/webapp/preview-r4/direction-2-editorial.html`
- [I] `screenplay_studio/webapp/preview-r4/direction-3-screening.html`
- [I] `screenplay_studio/webapp/preview-r4/index.html`
- [I] `screenplay_studio/webapp/preview-r4/shots/d1-dock.png`
- [I] `screenplay_studio/webapp/preview-r4/shots/d1-landing.png`
- [I] `screenplay_studio/webapp/preview-r4/shots/d2-dock.png`
- [I] `screenplay_studio/webapp/preview-r4/shots/d2-landing.png`
- [I] `screenplay_studio/webapp/preview-r4/shots/d3-dock.png`
- [I] `screenplay_studio/webapp/preview-r4/shots/d3-landing.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/concept-a-instrument.html`
- [I] `screenplay_studio/webapp/preview-r4/v2/concept-b-atelier.html`
- [I] `screenplay_studio/webapp/preview-r4/v2/concept-board.html`
- [I] `screenplay_studio/webapp/preview-r4/v2/concept-c-monolith.html`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/a-analysis.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/a-dock.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/a-landing.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/b-desk.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/b-dock.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/b-landing.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/board-axes.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/board-minis.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/c-desk.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/c-dock.png`
- [I] `screenplay_studio/webapp/preview-r4/v2/shots/c-landing.png`
- [I] `screenplay_studio/webapp/preview-redesigns/brutal.html`
- [I] `screenplay_studio/webapp/preview-redesigns/index.html`
- [I] `screenplay_studio/webapp/preview-redesigns/noir.html`
- [I] `screenplay_studio/webapp/preview-redesigns/organic.html`
- [I] `screenplay_studio/webapp/preview-redesigns/paper.html`
- [I] `screenplay_studio/webapp/preview-redesigns/swiss.html`
- [I] `screenplay_studio/webapp/preview-redesigns/terminal.html`
- [I] `screenplay_studio/webapp/style.css`
- [I] `screenplay_studio/webapp/tungsten.css`
- [P] `screenplay_studio/webapp_demo.py`
- [P] `screenplay_studio/webapp_server.py`

## tests (229)

- [I] `tests/_gunpen_clean_bill.py`
- [I] `tests/_gunpen_probe.py`
- [I] `tests/_p1_visual_gate.py`
- [I] `tests/_run_e2e_sweep.py`
- [I] `tests/_ui_capture.py`
- [I] `tests/_ui_verify.py`
- [I] `tests/conftest.py`
- [I] `tests/e2e_browser_403_advice.py`
- [I] `tests/e2e_browser_beatboard_drag.py`
- [I] `tests/e2e_browser_branch_ui.py`
- [I] `tests/e2e_browser_common.py`
- [I] `tests/e2e_browser_connection_modes.py`
- [I] `tests/e2e_browser_counting_contract.py`
- [I] `tests/e2e_browser_deep_links.py`
- [I] `tests/e2e_browser_delivery_contract.py`
- [I] `tests/e2e_browser_design_session.py`
- [I] `tests/e2e_browser_desk_controls.py`
- [I] `tests/e2e_browser_dock_sections.py`
- [P] `tests/e2e_browser_export_flush.py`
- [I] `tests/e2e_browser_feedback_ledger.py`
- [I] `tests/e2e_browser_finding_id_parity.py`
- [I] `tests/e2e_browser_gun_pen_audit.py`
- [I] `tests/e2e_browser_ideas.py`
- [I] `tests/e2e_browser_ideas_v3.py`
- [I] `tests/e2e_browser_identity_forensics.py`
- [I] `tests/e2e_browser_keyboard_edit.py`
- [I] `tests/e2e_browser_layout_audit.py`
- [I] `tests/e2e_browser_library_delete.py`
- [P] `tests/e2e_browser_live_regions.py`
- [I] `tests/e2e_browser_modal_guards.py`
- [I] `tests/e2e_browser_one_matcher.py`
- [I] `tests/e2e_browser_palette_craft.py`
- [I] `tests/e2e_browser_palette_restyle.py`
- [I] `tests/e2e_browser_pass_arc.py`
- [I] `tests/e2e_browser_phase10_structural_tools.py`
- [P] `tests/e2e_browser_phase11_responsive.py`
- [I] `tests/e2e_browser_phase12_visual_motion.py`
- [I] `tests/e2e_browser_phase13_legacy_cleanup.py`
- [P] `tests/e2e_browser_phase14_signoff_journey.py`
- [I] `tests/e2e_browser_phase5_dock.py`
- [P] `tests/e2e_browser_phase6_evidence.py`
- [P] `tests/e2e_browser_phase7_chat_lenses.py`
- [P] `tests/e2e_browser_phase8_lifecycle.py`
- [I] `tests/e2e_browser_phase9_idea_canvas.py`
- [I] `tests/e2e_browser_preview_next.py`
- [I] `tests/e2e_browser_preview_redesigns.py`
- [I] `tests/e2e_browser_quickcheck.py`
- [P] `tests/e2e_browser_race_guards.py`
- [I] `tests/e2e_browser_readiness_gate.py`
- [I] `tests/e2e_browser_real_transport.py`
- [I] `tests/e2e_browser_render_scale.py`
- [I] `tests/e2e_browser_rewrite_loop.py`
- [I] `tests/e2e_browser_script_search.py`
- [I] `tests/e2e_browser_selection_translate.py`
- [I] `tests/e2e_browser_server_url_guard.py`
- [I] `tests/e2e_browser_session_breaks.py`
- [I] `tests/e2e_browser_smoke.py`
- [I] `tests/e2e_browser_spark_wall.py`
- [I] `tests/e2e_browser_stale_socket_recovery.py`
- [I] `tests/e2e_browser_store_busy.py`
- [I] `tests/e2e_browser_text_popup.py`
- [I] `tests/e2e_browser_token_mode.py`
- [I] `tests/e2e_browser_translate_mic.py`
- [I] `tests/e2e_browser_trust_line.py`
- [P] `tests/e2e_browser_two_contexts.py`
- [I] `tests/e2e_browser_ui_batch.py`
- [I] `tests/e2e_browser_ui_fixes.py`
- [I] `tests/e2e_browser_ungrounded_filter.py`
- [I] `tests/e2e_browser_verdict_channel.py`
- [I] `tests/e2e_browser_viewport_ladder.py`
- [I] `tests/e2e_browser_width_budget.py`
- [I] `tests/e2e_browser_withdrawal_ledger.py`
- [P] `tests/e2e_browser_xss_inert.py`
- [I] `tests/eval_recall.py`
- [I] `tests/fixtures/Pain_FD_4_scenes.pdf`
- [I] `tests/fixtures/Pain_FD_4_scenes_recoverable.pdf`
- [I] `tests/fixtures/pain_tenglish.fountain`
- [I] `tests/fixtures/recall_goldens/gunpen.json`
- [I] `tests/fixtures/recall_goldens/pain3.json`
- [I] `tests/js/core.test.js`
- [I] `tests/js/verification_readout.test.js`
- [I] `tests/mock_unified_server.py`
- [I] `tests/probe_ink_layer_trap_frame.py`
- [I] `tests/route_recorder.py`
- [I] `tests/run_browser_suites.py`
- [I] `tests/test_a11y_outline_guard.py`
- [I] `tests/test_accuracy_guards.py`
- [I] `tests/test_analyze_cancel.py`
- [I] `tests/test_analyze_contract.py`
- [I] `tests/test_analyze_preflight.py`
- [I] `tests/test_analyzer_prompt_sizing.py`
- [I] `tests/test_anti_ai_filter.py`
- [I] `tests/test_app_symbol_integrity.py`
- [I] `tests/test_apply_race.py`
- [I] `tests/test_asset_cache_bust.py`
- [I] `tests/test_audit_hardening.py`
- [I] `tests/test_audit_remediation.py`
- [I] `tests/test_bare_array_tolerance.py`
- [I] `tests/test_beatboard.py`
- [I] `tests/test_browser_check_hygiene.py`
- [I] `tests/test_bugfix_batch.py`
- [I] `tests/test_c10_residuals.py`
- [I] `tests/test_capability_token.py`
- [I] `tests/test_character_reads_logline.py`
- [I] `tests/test_chat_json_truncation_retry.py`
- [P] `tests/test_chat_language_meta.py`
- [I] `tests/test_checkpoint_evidence.py`
- [I] `tests/test_chunk_recovery_visibility.py`
- [I] `tests/test_clear_redo_lock.py`
- [I] `tests/test_cli_memory_default.py`
- [I] `tests/test_cli_output_encoding.py`
- [I] `tests/test_code_revision.py`
- [I] `tests/test_compare.py`
- [I] `tests/test_connection_modes.py`
- [I] `tests/test_consult_context.py`
- [I] `tests/test_continuity_idiolect.py`
- [P] `tests/test_cowriter_personas.py`
- [P] `tests/test_cowriter_server.py`
- [I] `tests/test_craft_history.py`
- [I] `tests/test_cross_rule_dedup.py`
- [I] `tests/test_cycle_continuity.py`
- [I] `tests/test_dead_surface_retirement.py`
- [I] `tests/test_delete_project.py`
- [I] `tests/test_delete_retry.py`
- [I] `tests/test_delivery_contract.py`
- [I] `tests/test_demo_banner.py`
- [I] `tests/test_destructive_paths.py`
- [I] `tests/test_diff.py`
- [I] `tests/test_dismiss_index.py`
- [I] `tests/test_doc_surface_hygiene.py`
- [I] `tests/test_empty_kb_guard.py`
- [I] `tests/test_eval_coverage.py`
- [I] `tests/test_evidence_depth.py`
- [P] `tests/test_export.py`
- [I] `tests/test_fake_composer_removed.py`
- [I] `tests/test_feature_batch.py`
- [I] `tests/test_feedback_filter.py`
- [I] `tests/test_feedback_ledger.py`
- [I] `tests/test_finding_id_scene_key.py`
- [I] `tests/test_finding_integrity_gate.py`
- [I] `tests/test_finding_verdict_channel.py`
- [I] `tests/test_fix_batch.py`
- [I] `tests/test_fixqueue.py`
- [I] `tests/test_generation_timeout.py`
- [I] `tests/test_genre.py`
- [I] `tests/test_grammar_compat.py`
- [I] `tests/test_h7_chat_fix.py`
- [I] `tests/test_host_header_guard.py`
- [I] `tests/test_humanization_v2.py`
- [I] `tests/test_idea_room_v2.py`
- [I] `tests/test_idea_room_v3.py`
- [I] `tests/test_ideas.py`
- [P] `tests/test_indian_languages.py`
- [I] `tests/test_kb_schema.py`
- [I] `tests/test_kb_text_hygiene.py`
- [I] `tests/test_language_and_human_levers.py`
- [I] `tests/test_library_backup.py`
- [I] `tests/test_llm_client.py`
- [I] `tests/test_lock_order.py`
- [I] `tests/test_logsetup.py`
- [I] `tests/test_metrics.py`
- [I] `tests/test_negative.py`
- [I] `tests/test_neutral_edge.py`
- [I] `tests/test_nonascii_titles.py`
- [I] `tests/test_notes.py`
- [I] `tests/test_observation_contract.py`
- [I] `tests/test_observation_pass.py`
- [I] `tests/test_orientation.py`
- [I] `tests/test_pacing_dials_track.py`
- [I] `tests/test_packaging_data_files.py`
- [I] `tests/test_pass_history.py`
- [P] `tests/test_pdf_fixture.py`
- [P] `tests/test_pdf_layout.py`
- [P] `tests/test_pdf_ocr.py`
- [I] `tests/test_peer_guardrails.py`
- [I] `tests/test_persona_humanization.py`
- [I] `tests/test_positive.py`
- [I] `tests/test_post_trust_hardening.py`
- [I] `tests/test_preview_lab.py`
- [I] `tests/test_production_readiness.py`
- [I] `tests/test_project_dir_authority.py`
- [P] `tests/test_prompt_budget.py`
- [P] `tests/test_prompt_budget_default.py`
- [I] `tests/test_prompt_extensions.py`
- [P] `tests/test_quote_agreement.py`
- [I] `tests/test_recall.py`
- [P] `tests/test_reply_quote_guard.py`
- [I] `tests/test_reply_register.py`
- [I] `tests/test_repo_hygiene.py`
- [I] `tests/test_report_atomicity.py`
- [I] `tests/test_report_duplicate_rows.py`
- [I] `tests/test_report_export_progress.py`
- [I] `tests/test_report_language.py`
- [I] `tests/test_revision.py`
- [I] `tests/test_route_coverage.py`
- [I] `tests/test_route_smoke.py`
- [I] `tests/test_rules_grounding.py`
- [I] `tests/test_runtime.py`
- [I] `tests/test_sample.py`
- [I] `tests/test_security_hardening.py`
- [I] `tests/test_selection_translate_sloppiness.py`
- [I] `tests/test_server_url_guard.py`
- [I] `tests/test_session_lost_update.py`
- [I] `tests/test_session_selection_merge.py`
- [I] `tests/test_setup_payoff.py`
- [I] `tests/test_shelf_cache.py`
- [P] `tests/test_sidebar_translate_stt.py`
- [I] `tests/test_spa_contract.py`
- [I] `tests/test_spa_security_headers.py`
- [I] `tests/test_stale_proposal_guard.py`
- [I] `tests/test_stash.py`
- [I] `tests/test_store_busy.py`
- [I] `tests/test_store_concurrency.py`
- [I] `tests/test_store_fault_injection.py`
- [I] `tests/test_stress.py`
- [P] `tests/test_structure.py`
- [I] `tests/test_two_tier_watchdog.py`
- [I] `tests/test_undo_redo.py`
- [I] `tests/test_undo_redo_lock_race.py`
- [I] `tests/test_upload_validation.py`
- [I] `tests/test_verification_summary_surface.py`
- [I] `tests/test_voice_drift_acts.py`
- [I] `tests/test_voice_subtext.py`
- [I] `tests/test_watch.py`
- [I] `tests/test_webapp_api.py`
- [I] `tests/test_webapp_revision.py`
- [I] `tests/test_webapp_text_hygiene.py`
- [P] `tests/test_writer_library.py`
- [I] `tests/test_writer_memory.py`

## Priorities for continuing

1. Application and library source, configuration, migrations, CLI and persistence paths: read in small batches; log checked functions and data flows, not just filenames.
2. Tests and fixtures: compare claimed coverage with exercised behavior, edge cases and assertions; preserve false-positive/flaky results as such.
3. Knowledge base and parser: review rules, assumptions, multilingual input, output and compatibility.
4. Documentation, build/packaging, shipped assets and binary artifacts: validate links/configuration, provenance, intended behavior and accessibility as applicable.
5. Update the consolidated register for confirmed defects and explicitly distinguish suspected risks from reproductions. No claim of full audit until every applicable path has a documented review and remaining limitations are disclosed.

## Storage batch — reviewed scope

Read the listed notes, stash, ideas, beat-board, feedback-ledger, pass-history, metrics, session-store and session-model modules; traced selected API/UI callers; ran controlled in-memory or temporary-file failure/concurrency probes. The P marker remains partial because dependent routes, migrations, platform behavior and all integration paths have not been exhausted. Findings and limitations are in gaps 18–20 and 13.

## Import/export batch — reviewed scope

Inspected parser dispatch, document schema, export, FDX and text parsers, scene keys, selected stats/knowledge-graph code and export tests. Ran a minimal two-speaker round trip, a synthetic styled/numbered FDX round trip, and Fountain/TXT/FDX reparse comparisons on the locally parsed representations of both user PDFs. P remains partial: PDF extraction, many grammar and format features, external application behavior, and parser correctness against both complete PDFs still need examination. See gaps 21–22.

## Parser/evidence batch — reviewed scope

Read PDF extraction/OCR, cue heuristics, quote normalization, knowledge-graph presence and pacing structure code, and traced their use in selected analyzer prompts. Ran controlled mixed-page PDF, no-OCR parse, Telugu cue, Unicode-quote, silent-character and boundary probes. These paths remain P, not fully reviewed, because broad multilingual fixtures, supported-platform OCR, whole-PDF ground truth and downstream integrations still require validation. Existing applicable suite results and findings appear in gaps 23–27.

## Collaborator batch — reviewed scope

Inspected and traced portions of collaborator scene retrieval, prompt assembly, response cleaning, language behavior, library digest and streaming transport. Ran synthetic fake-client checks for short turns, erased answers, whole-turn payload size, cross-project prompt inclusion and reasoning-content SSE handling, plus selected existing test suites. Paths remain partially reviewed; actual provider compatibility, UI consent, real-model behavior, session security and broader integrations still need validation. See gaps 28–32.

## Security, connection and recovery batch — reviewed scope

Traced selected URL/Host/token guards, analyzer and collaborator request calls, STT transport, manifest and archive paths, logging and sample creation; inspected applicable tests. Controlled synthetic checks reproduced an analyzer redirect escaping initial URL validation (with destination mapped to loopback), key-bearing manifest mode under umask 022, external-target symlink inclusion in both archives, overwriting a damaged sample-named project, and stale context-window caching. Ran 201 relevant existing tests successfully. This remains partial: collaborator/STT redirect behavior, DNS/proxy/rebinding and TLS details, actual platform ACLs, complete routes and restore paths, and deployment threat models remain to be reviewed; do not infer an actual leak or security-audit completion. See gaps 33–36.

## CLI, intake, provider and packaging batch — reviewed scope

Read the studio CLI, watch worker, character-track builder, relevant launch/connection code, STT transport and packaging/CI configuration; ran isolated open-file intake, Unicode watched-name and CLI exit probes, mocked local provider and settings-save failure probes, and controlled 307 tests for collaborator and STT transports. Ran ruff, 66 selected Python tests and 134 JS tests successfully. The source paths remain partial: real provider behavior, producer protocols, supported-platform filesystem behavior, full CLI interactions, packaging installs on other platforms, all UI surfaces and detailed CI execution remain unverified. Documented findings in gaps 16 and 33, 37–42. Existing demo mode has UI disclosures in the inspected code; their presence is not evidence of a complete real-model provenance design.

## Deterministic craft and report batch — reviewed scope

Inspected deterministic voice/subtext, continuity and pacing passes, cross-rule dedup, category-outcome handling and Markdown report rendering. Synthetic scenes exercised direct emotion, day/night cuts, equal-count pacing comparisons, distinct same-rule findings and a failed category rendered as empty; ran 115 relevant existing tests successfully. This is a bounded adversarial review, not an evaluation of all deterministic checks or an independent reader study. See gaps 43–47; absorbed dedup findings are retained in structured data and have a UI detail path.

Prompt-construction trace: inspected selected analyzer scene prompts and collaborator system context assembly for instruction/data boundaries. Recorded a potential prompt-injection test gap (48), not a demonstrated model exploit; full prompt-path inventory and real-model adversarial testing remain open.

## Narrative inference and identity/CLI batch — reviewed scope

Inspected deterministic continuity and pacing, reveal scanning and model verdict grounding, setup/payoff adjudication and pipeline call sites, idea and session creation, selected CLI entrypoints, watch outcomes, character-track consumers and associated tests. Synthetic probes exposed recurrence-as-payoff, a fabricated twist quote accepted as confirmed, prescriptive time/pacing conclusions, forced short-ID collisions overwriting ideas/chats, orphan source overwrite in CLI creation, and normal watch-once return on mocked failure. Parsed both attached PDFs for limited deterministic candidate counts only; no interpretive or audience ground truth was asserted. Related existing suites: 89 and 16 tests passed. An earlier test command named a nonexistent pacing file and collected nothing; recall was rerun. These modules remain partially reviewed; scene-level quality, all CLI combinations, long-running races and real-model output remain open. See gaps 39, 44–45 and 49–54.

## Editing and narrative-mechanics batch — reviewed scope

Traced edit apply/undo/redo routes and UI result handling, document scene/speaker metadata, exporters, reveal probe and report/prompt consumers, and setup/payoff adjudication. Reproduced duplicate-text undo failure and structural heading/cue inconsistencies through real Flask endpoints, and unsupported twist promotion and recurrence-as-payoff with isolated synthetic/fake-client tests. Existing relevant revision/export/track suites (112), setup/continuity suites (35) and JS suite (134) passed. This is still partial: not all editing entry points, overlapping groups, model outputs, downstream consumers or actual browser edge-case behavior have been exhausted. See gaps 51–54.

## Idea handoff and startup-mode batch — reviewed scope

Inspected idea persistence, graduation route and UI handoff, server import and normal startup fallback. Controlled API checks injected a carry failure and compared scene-less graduation with ordinary creation; a separate import/main process checked the demo opt-out and mode transition. Ran 58 relevant existing tests. These paths remain partial: transfer races, all idea UI flows, startup integrations and real provider reconnects remain to verify. See gaps 55–56.

## Settings and report-provenance batch — reviewed scope

Inspected the real settings form, config and connection-test routes, per-project sync, effective chat destination, model URL builder, startup fallback and HTML report export. Mocked/synthetic checks reproduced reuse of an old provider's token on a new endpoint, non-atomic settings failure, a local-only API switch retaining a remote project/chat destination, and demo-report banner dependence on current global state. Reconfirmed the `/v1` duplication and startup fallback discrepancy already recorded. No outbound provider request or real secret was used. Corrected existing test selection: 106 passed; one earlier command named a nonexistent file and collected none. Still partial: actual browser traversal of every settings path, in-flight switching, real provider behavior and historical mixed-run migrations remain unvalidated. See gaps 41–42 and 56–59.

**Register maintenance:** independently recorded batches had reused numbers 37–42. Reconciled unique findings into 49–56, preserved corroborating probes for repeated findings, and updated affected cross-references. The register now has one unique number per gap; this is organization, not proof of full-file review.


## Model deadline batch — reviewed scope

Inspected analyzer grammar/client retry flow, model deadline tests, metric and character-track paths. A fake-clock, mocked-transport test exposed nested busy retries after the logical deadline; 14 existing timeout/client tests passed. This does not measure real model latency or provider cancellation. Character importance/physical-presence limitations remain recorded under gap 26; other grammar/provider compatibility paths remain partial. See gap 60.

## Draft lifecycle, workspace confinement and store-lock batch — reviewed scope

Read the full draft-switch/upload routes, `diff.py` snapshot and activation code, `_project_dir`/`check_safe_id`, `jsonio` lock internals, the character-track and scene-analytics consumers, analysis lock/cancel/progress helpers, startup revision probe and the SPA's draft picker. Synchronized synthetic concurrent uploads, a relative-name activation across two projects, an outside-`PROJECTS_DIR` relative target, a failed-format upload followed by reactivation, an upload during a stubbed running analysis, cancel during `retry-failed`, in-process versus cross-process lock budgets, a mocked metrics timeout and both attached PDFs through the script/characters endpoints. 60 relevant tests passed; all interleavings were forced, so no frequency is claimed. Not reviewed here: launch/install paths, full SPA views, real-model runs, restore of archives, watch intake after the recorded failures, and the preview/design-lab documents. See gaps 61–69.

## Persistence, archive and idea-store batch — reviewed scope

Read `manifest.py` merge/save/load, the idea store, the notes/stash/beat-board/metrics/pass-history readers, both archive routes, the premise route, the export route and the router table. Calls were made against synthetic stores: corrupting each JSON store to see damage handling, two independently loaded manifests writing the same stage, a library archive with an idea and a profile file present, leftovers of another source format, and the absence of any restore route. Every JSON store except `idea.json` raised a distinguishable damage error and preserved the file. Not reviewed here: `webapp_demo.py`, the STT/whisper server modules, the preview/design-lab HTML labs, packaging/launch scripts, and any real-model path. See gaps 70–76.

## Continuity, analytics and export-footprint batch — reviewed scope

Read the deterministic continuity pass end to end (time flips, name variants, normalization helpers), formatting checks, scene statistics, and export dispatch. Ran synthetic day/night and near-name scripts, and parsed both attached PDFs to compare continuity output with the actual cast and headings. Deterministic checks are now mapped; what remains unread or unexercised is the model-facing half of the analyzer prompts, the preview labs, packaging and real-model output. See gaps 77–79.

## Documentation and surface-drift batch — reviewed scope

Compared `docs/API_ROUTE_MAP.md` mechanically against the live Flask URL map, ran both CLIs' `--help`, and read the standalone co-writer server's entrypoint plus the docs that describe it. The four undocumented live routes and the "no standalone server" claim are recorded as gaps 83–86; I did not start the standalone server or exercise its routes. Remaining unread: `docs/*` beyond route/architecture/CLI references, the preview design labs' HTML, and packaging/CI execution.

## End-to-end demo-run batch — reviewed scope

Started the built-in demo craft model on loopback and drove the real pipeline, the real Flask routes and the real session store end to end: parse + analyze + report + fix queue + chat start + persona switch + two turns, on a synthetic two-scene script and on both attached screenplays. This exercised routing, persistence, report rendering and the demo client together for the first time in this sweep. It is not a real-model evaluation and says nothing about Sameer/Sushruta quality beyond the demo's canned replies. See gaps 87–94. Remaining unread or unexercised: preview design-lab HTML, most narrative docs beyond routes/architecture/CLI, packaging and CI execution, and all real-model behaviour.

## Collaborator-intent batch — reviewed scope

Read the remaining co-writer modules not yet covered end to end (`peer.py`, `craft_history.py`, the probe path in `engine.py`, persona/mode validation) and probed the pure intent classifiers with the writer's own documented phrasings from the two attached scripts and the Darshi statements. These are deterministic function calls; no model was invoked. The collaborator's *voice quality* remains unvalidated by design (real-model gate). See gaps 98–101.

## Knowledge-base grounding batch — reviewed scope

Inventoried all 26 rule files (263 rules, no duplicate ids), called `RulesContext` for every pass name and category the pipeline uses, and traced the grounding call sites in `pipeline.py`, `dials.py` and `genre.py`. This closes the KB-coverage question: which passes are grounded, which are silent, and how large the fragments get. Not reviewed: rule content quality per se, and how a real model uses any of it. See gaps 102–105.

## Completion audit — what is now covered, and what a sweep cannot reach

Mechanical coverage check: **all 83 Python modules** in the four packages are named in this ledger, **all 222 test files** are in the inventory, and every batch above records its own limits. The full default suite was re-run at the end of this phase: **2,236 passed, 4 skipped, 12 deselected** (browser suites excluded), and `ruff` is clean. **These passes are not evidence about the gaps**: none of the 60+ findings recorded here has a failing existing test, which is exactly why they had to be reproduced by hand.

Genuinely unreviewed, stated plainly so nobody mistakes this for total coverage:
- the preview design-lab HTML beyond route reachability, the fourteen font files, the nine root concept PNGs;
- narrative docs beyond `API_ROUTE_MAP`, `ARCHITECTURE`, `CLI_REFERENCE`, `CODEBASE_MAP`, `CONTEXT`, and `AGENTS`;
- packaging/CI execution beyond the existing guard tests, and any non-Linux platform behaviour;
- **real-model behaviour of any kind** — accuracy, latency, disagreement quality, multilingual output — which no local probe here can substitute for;
- audience reception of either attached screenplay, which is the user's untested question and not something a code sweep can answer.

The register stood at 108 uniquely numbered gaps when this line was written; it is now **127 numbered entries, 6 withdrawn, 4 proven non-gaps, 117 live**, graded individually in `ENTRY_GRADE_TABLE.md`. The count is a measure of how much the system asserts versus how much it verifies, not a release checklist; the coordinated fix order starts with containment and revision safety, and is unchanged.

## Self-critique pass — reviewed scope and corrected standard

Re-ran the four highest-severity early findings through real interfaces (draft switch destroying edits, export speaker merge, Indic quote normalization, draft-name containment), then graded the whole register: A = real-interface reproduction, B = constructed/conditional, C = source inference, D = opinion/docs, W = withdrawn. Results, corrections and the five withdrawals are in `SELF_CRITIQUE_OF_GAP_REGISTER.md`, and a headnote in `GAP_REGISTER_AND_EXECUTION_PLAN.md` carries the corrected reading.

Also graded the previously ungraded surfaces this pass: the SPA document and its security headers (strict CSP with frame-ancestors, nosniff, no-referrer, no inline handlers, no external origins — no gap), `/api/config` secret withholding (no leak — reproduced negative), `ruff check .` at the repository root (passes — withdrawn suspicion), CLI create/status round-trip (works; positional asymmetry noted), repository weight (`docs/` 12 MB, `impl-shots/` 7.2 MB — housekeeping only), and summary/queue/count arithmetic agreement (one real inconsistency, finding 113).

**Sixth pass — the areas §13 named as remaining, actually swept.** The Python floor (`requires-python >=3.10`) was checked by parsing every module with `ast.parse(feature_version=(3,10))`: honest, with one UTF-8 BOM in `tests/test_h7_chat_fix.py` that pytest reads and whose 5 tests pass — recorded as a hygiene note, not a gap. JS reproducibility was checked from a clean install (`npm ci` then `npm test`): **134/134** across both suites, while the docstring inside `preview-ink-layer/tests/dom.test.mjs` still says 127, and the obvious `node --test tests/js/` invocation fails on Node 22 — documentation and invocation trap only. The knowledge-base failure modes were driven through the real paths: malformed file → `JSONDecodeError`, schema-invalid entry → `TypeError` from `Rule(**e)`, empty rules directory → 0 rules accepted silently, and an analyze run on a corrupted install → `OrchestratorError`, webapp **502** carrying the parser text, `/report` afterwards **400** "Analysis hasn't completed" although the prior report was intact on disk. That last one is filed as gap **119** (grade A, medium) in `SELF_CRITIQUE_OF_GAP_REGISTER.md` §17. The full default suite was re-run in the rebuilt environment at the end of this pass: **2,248 passed, 4 skipped**, 87 s, and `ruff check .` is clean.

**Stop rule:** findings had stopped being independent — the last several batches produced new instances of the same composition seam rather than new mechanisms. Remaining unverifiable-here areas are named explicitly in `SELF_CRITIQUE_OF_GAP_REGISTER.md` §13 and §17 (real-model behaviour, audience reception, assistive technology, non-Linux platforms, preview-lab internals) and are not going to be faked. No application code changed in any of these passes; the suite remained green and root lint clean throughout.

## Eighth pass — the last product modules at "inventory only"

Short pass, graded as written. `screenplay_studio/stt.py` and its route pair were read end to end and driven
through the real Flask client in five failure states plus the two URL-guard bypasses the module's own comment
describes; `screenplay_studio/webapp_demo.py` was driven with a stub over `webapp_server.main` to confirm the
argv handoff and the forced demo flag. Findings **125** (the languages endpoint advertises a whisper server the
guard then refuses — grade A, low) and **126** (no magic-byte or duration check on dictated audio, 256 MB
ceiling inherited from uploads — grade B, low) are in `SELF_CRITIQUE_OF_GAP_REGISTER.md` §20.

Negatives from this batch, recorded with the findings: the whisper URL guard refuses `127.0.0.1@evil.com` before
any request; `/api/stt` produces five distinct actionable messages and no traceback in every failure state I
could create; `webapp_demo.py` hands `['--demo-model', '--port', …]` to the canonical `main`, so the token is
minted and the bind stays loopback; the forced-language auto-retry is deliberate and has two tests.

**Coverage after this pass: no product module remains `[I]`.** Every one of the 83 Python modules has been read
by me or reviewed within a named batch. What remains unreviewed is exactly the list in §13 of the critique —
real-model behaviour, audience reception, assistive technology, non-Linux platforms, preview-lab HTML internals —
plus one environment gap stated precisely: **playwright is not installed in this environment, so the 30
`e2e_browser_*.py` suites have not been executed by me in any pass.** Every UI claim here is source-, DOM- or
test-client-based, never a rendered page. Installing playwright and running that gate is the only remaining
mechanical work a sweep can do on this repository.

Per-entry grades for all 127 entries, with the counts computed from the table rather than typed, are in
`ENTRY_GRADE_TABLE.md`: **51 A, 44 B, 11 C, 11 D, 6 withdrawn, 4 proven non-gaps — 117 live findings.**

## Ninth pass — packaging, and the gate that cannot open here

Built the wheel for the first time in this sweep (`python -m build --wheel`) and installed it into a clean
`--target` outside the repository, then booted it: **180 files, 4.04 MB, 26 rule files (263 rules),
`index.json`/`schema.json`, the whole SPA and its fonts, no tests, no PNGs, no analysis scratch files**, `/` →
200 (48 KB), `/api/health`, `/api/config` and `/api/stt/languages` → 200, `KnowledgeBase()` loads 263 rules from
the installed copy. Gap **127** is filed in `SELF_CRITIQUE_OF_GAP_REGISTER.md` §21 and is narrow: the ten
packaging tests read the source tree rather than a wheel, so they could pass while an installed copy broke.
Half of gap 86 is contradicted by the artefact — `graph.json` does not ship; the finding holds only for the
source tree.

**Browser gate: closed as un-runnable, with the reason measured.** `playwright` installs; `playwright install
chromium` fails because `cdn.playwright.dev` is unreachable from this sandbox, and no system Chromium or Firefox
exists to substitute. All 30 `e2e_browser_*.py` suites therefore remain unexecuted by me. Every UI claim in this
register is source-, DOM- or test-client-based. This is now stated as a limit rather than left as a pending item.
