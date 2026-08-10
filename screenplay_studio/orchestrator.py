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
    def run_analyze(self, categories: tuple = None) -> ProjectManifest:
        m = self.manifest
        if m.stage("parse").status != "complete":
            raise OrchestratorError("Cannot analyze — parse stage hasn't completed successfully yet.")
        if m.stage("analyze").status == "complete":
            return m

        m.mark_running("analyze")
        try:
            from screenplay_parser.models import ScriptDocument
            from screenplay_analyzer.pipeline import analyze
            from screenplay_analyzer.llm_client import LlamaServerClient
            from screenplay_analyzer.report import save_report

            doc = ScriptDocument.load(m.parsed_path)
            client = LlamaServerClient(base_url=m.server_url, model=m.model_id, timeout=m.timeout)

            kwargs = {}
            if categories:
                kwargs["run_categories"] = categories

            result = analyze(doc, client, **kwargs)
            save_report(result, m.report_md_path, m.report_findings_path)

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
                })
            else:
                m.mark_complete("analyze", {"report_md": m.report_md_path, "report_findings": m.report_findings_path})
        except Exception as e:
            m.mark_failed("analyze", str(e))
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
                session = store.load(m.cowriter_session_id)
            else:
                session = store.create(title=m.title, report_path=report_path, script_path=m.parsed_path)
                m.cowriter_session_id = session.session_id

            client = LlamaServerClient(base_url=m.server_url, timeout=m.timeout)
            report_ctx = ReportContext(load_json(report_path) if report_path else None)
            model_id = resolve_model(client, report_ctx, explicit_model=m.model_id)

            session.server_url = m.server_url
            session.model_id = model_id
            store.save(session)

            script_ctx = ScriptContext(load_json(m.parsed_path))
            engine = CoWriterEngine(client, script_ctx, report_ctx)

            m.mark_complete("chat", {"session_id": session.session_id})
            return session, engine, store
        except Exception as e:
            m.mark_failed("chat", str(e))
            raise OrchestratorError(f"Chat stage failed to start: {e}") from e

    # ---- full pipeline ----
    def run_full(self, categories: tuple = None, skip_chat: bool = True):
        """Runs parse -> analyze, and optionally prepares (but doesn't drive)
        chat. skip_chat=True by default since chat is inherently interactive —
        the CLI decides whether to hand off to a REPL after this returns."""
        self.run_parse()
        self.run_analyze(categories=categories)
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
