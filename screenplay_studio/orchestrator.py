"""
Orchestrator. Deliberately thin — it doesn't reimplement any piece's logic,
just calls each piece's existing public API in sequence and manages the
manifest between calls. Each of the three pieces stays fully independent
and usable on its own; this only adds a convenience layer on top.

Failure isolation: if analyze() fails (server down, bad grammar, etc.), the
manifest still has a valid, complete "parse" stage recorded. Calling run()
again picks up from analyze — parse isn't redone.
"""

from __future__ import annotations

from .manifest import ProjectManifest


class OrchestratorError(Exception):
    pass


class Orchestrator:
    def __init__(self, manifest: ProjectManifest):
        self.manifest = manifest

    # ---- stage: parse ----
    def run_parse(self) -> ProjectManifest:
        m = self.manifest
        if m.stage("parse").status == "complete":
            return m  # already done, nothing to do

        m.mark_running("parse")
        try:
            import os
            if not os.path.exists(m.source_path):
                raise OrchestratorError(f"Source file not found: {m.source_path}")

            from screenplay_parser import parse_screenplay, build_knowledge_graph

            doc = parse_screenplay(m.source_path)
            doc.save(m.parsed_path)

            kg = build_knowledge_graph(doc)
            kg.save(m.kg_path)

            m.mark_complete("parse", {"parsed": m.parsed_path, "kg": m.kg_path})
        except Exception as e:
            m.mark_failed("parse", str(e))
            raise OrchestratorError(f"Parse stage failed: {e}") from e
        return m

    # ---- stage: analyze ----
    def run_analyze(self, categories: tuple = None, report_language: str = None,
                    retry_failed: bool = False) -> ProjectManifest:
        m = self.manifest
        if m.stage("parse").status != "complete":
            raise OrchestratorError("Cannot analyze — parse stage hasn't completed successfully yet.")

        stage = m.stage("analyze")
        prev_outputs = None
        merging = False
        if stage.status == "complete" or stage.status == "failed":
            # A completed stage is normally a no-op (resume never redoes
            # finished work). The one exception: a *partial* completion — some
            # categories succeeded, some failed. With retry_failed=True, re-run
            # only the failed categories and merge their results into the
            # existing report instead of re-running everything. A "failed"
            # stage whose partial record was preserved (failed retry) resumes
            # the same way.
            failed = (stage.output_paths or {}).get("failed_categories") or []
            if not retry_failed or not failed:
                if stage.status == "complete":
                    return m  # fully complete, nothing to do
                # else: failed stage with no partial record — fall through and
                # re-run everything (pre-existing resume behavior)
            else:
                # genre / logline_test need coverage's genre+logline fields. If
                # they failed *independently* of coverage (a transient error on
                # their own model call), coverage must be re-run alongside them
                # — otherwise the fresh run's empty coverage gates them out and
                # step-7 re-marks them failed forever.
                if any(c in failed for c in ("genre", "logline_test")) and "coverage" not in failed:
                    failed = list(failed) + ["coverage"]
                categories = tuple(failed)
                print(f"Retrying failed analysis categories only: {', '.join(failed)}")
                merging = True
                prev_outputs = dict(stage.output_paths)

        if report_language:
            m.report_language = report_language
            m.save()
        language = m.report_language or "eng"

        m.mark_running("analyze")
        import json as _json
        try:
            from screenplay_parser.models import ScriptDocument
            from screenplay_analyzer.pipeline import analyze
            from screenplay_analyzer.llm_client import LlamaServerClient
            from screenplay_analyzer.report import save_report

            def progress_cb(event):
                import time as _t
                # ts = heartbeat: lets the webapp distinguish "still running"
                # from "the process died mid-stage" (a hard crash leaves no
                # done/failed write behind — without a timestamp that stale
                # 'running' file would lie forever).
                with open(m.progress_path, "w", encoding="utf-8") as f:
                    _json.dump(dict(event, ts=_t.time()), f)

            doc = ScriptDocument.load(m.parsed_path)
            client = LlamaServerClient(base_url=m.server_url, model=m.model_id, timeout=m.timeout,
                                       fallback_to_loaded=True, fast_model=m.fast_model)

            kwargs = {"report_language": language}
            if categories:
                kwargs["run_categories"] = categories

            result = analyze(doc, client, progress_cb=progress_cb, **kwargs)

            if merging and not result.category_outcomes:
                # The retry didn't get through a single category (e.g. server
                # unreachable at model resolve). Merging an empty re-run would
                # resurrect every previous finding (empty rerun set) and the
                # report would be overwritten with stale content — and the
                # partial record would look "complete" with no failures. Fail
                # the retry instead (the except handler marks it failed and
                # restores the previous partial record), preserving the report.
                error_summary = "; ".join(result.errors) or "Retry produced no category outcomes (no model calls succeeded)."
                raise OrchestratorError(f"Analyze retry failed before any category ran: {error_summary}")

            failed_categories = [c for c, s in (result.category_outcomes or {}).items() if s == "failed"]
            if merging:
                # Merge: keep the previously-successful findings, overlay this
                # re-run's fresh findings for the retried categories, and
                # recompute the verification summary over the combined set.
                result.merge(m.report_findings_path)

            save_report(result, m.report_md_path, m.report_findings_path)
            import time as _t
            with open(m.progress_path, "w", encoding="utf-8") as f:
                _json.dump({"stage": "done", "status": "complete", "detail": "Analysis complete", "ts": _t.time()}, f)

            if result.model_used:
                m.model_id = result.model_used

            produced_anything = bool(result.findings) or result.coverage is not None
            if result.errors and not produced_anything:
                # total failure (e.g. server was unreachable for the whole run) —
                # this is meaningfully different from a partial failure and
                # should be retried, not treated as a usable report.
                error_summary = "; ".join(result.errors)
                m.mark_failed("analyze", error_summary)
                raise OrchestratorError(f"Analyze stage produced no usable output: {error_summary}")
            elif result.errors:
                # partial success: some categories failed but the stage produced
                # a usable report — record as complete with the errors visible,
                # not as a hard failure, since a partial report is still useful.
                m.mark_complete("analyze", {
                    "report_md": m.report_md_path,
                    "report_findings": m.report_findings_path,
                    "partial_errors": result.errors,
                    "category_outcomes": dict(result.category_outcomes or {}),
                    "failed_categories": failed_categories,
                })
            else:
                m.mark_complete("analyze", {
                    "report_md": m.report_md_path,
                    "report_findings": m.report_findings_path,
                    "category_outcomes": dict(result.category_outcomes or {}),
                    "failed_categories": failed_categories,
                })
        except Exception as e:
            import json as _json2
            import time as _t2
            try:
                with open(m.progress_path, "w", encoding="utf-8") as f:
                    _json2.dump({"stage": "failed", "status": "failed", "detail": str(e), "ts": _t2.time()}, f)
            except Exception:
                pass
            m.mark_failed("analyze", str(e))
            # A retry that itself fails must not destroy the partial-completion
            # record (failed_categories + report paths). Restore the previous
            # output_paths so a later retry_failed can resume from exactly
            # where the last successful run stopped.
            if merging and prev_outputs is not None:
                m.stages["analyze"].output_paths = prev_outputs
                m.save()
            raise OrchestratorError(f"Analyze stage failed: {e}") from e
        return m

    # ---- stage: chat ----
    def start_chat(self):
        """Returns (session, engine, store) ready for interactive use — doesn't
        run the REPL itself, since that's Piece 3's CLI's job. Works even if
        analyze() never completed (falls back to script-only discussion)."""
        m = self.manifest
        if m.stage("parse").status != "complete":
            raise OrchestratorError("Cannot start chat — parse stage hasn't completed successfully yet.")

        m.mark_running("chat")
        try:
            from screenplay_cowriter.store import SessionStore
            from screenplay_cowriter.context import ScriptContext, ReportContext, load_json
            from screenplay_cowriter.discovery import resolve_model
            from screenplay_cowriter.engine import CoWriterEngine
            from screenplay_cowriter.llm_client import LlamaServerClient

            report_path = m.report_findings_path if m.stage("analyze").status == "complete" else None

            store = SessionStore(m.sessions_dir)
            if m.cowriter_session_id:
                try:
                    session = store.load(m.cowriter_session_id)
                except FileNotFoundError:
                    # The manifest's session was deleted (Clear chat does
                    # DELETE then start) — recover by starting a fresh page
                    # instead of bricking chat with a 502.
                    session = store.create(title=m.title, report_path=report_path, script_path=m.parsed_path)
                    m.cowriter_session_id = session.session_id
            else:
                session = store.create(title=m.title, report_path=report_path, script_path=m.parsed_path)
                m.cowriter_session_id = session.session_id

            client = LlamaServerClient(base_url=m.server_url, timeout=m.timeout, fallback_to_loaded=True)
            report_ctx = ReportContext(load_json(report_path) if report_path else None)
            model_id = resolve_model(client, report_ctx, explicit_model=m.model_id)

            session.server_url = m.server_url
            session.model_id = model_id
            store.save(session)

            script_ctx = ScriptContext(load_json(m.parsed_path))
            engine = CoWriterEngine(client, script_ctx, report_ctx, store=store)

            m.mark_complete("chat", {"session_id": session.session_id})
            return session, engine, store
        except Exception as e:
            m.mark_failed("chat", str(e))
            raise OrchestratorError(f"Chat stage failed to start: {e}") from e

    # ---- full pipeline ----
    def run_full(self, categories: tuple = None, skip_chat: bool = True, retry_failed: bool = False):
        """Runs parse -> analyze, and optionally prepares (but doesn't drive)
        chat. skip_chat=True by default since chat is inherently interactive —
        the CLI decides whether to hand off to a REPL after this returns."""
        self.run_parse()
        self.run_analyze(categories=categories, retry_failed=retry_failed)
        if not skip_chat:
            return self.start_chat()
        return None

    def status(self) -> dict:
        m = self.manifest
        return {
            "project_dir": m.project_dir,
            "title": m.title,
            "stages": {name: s.status for name, s in m.stages.items()},
            "errors": {name: s.error for name, s in m.stages.items() if s.error},
        }
