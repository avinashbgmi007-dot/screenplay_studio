"""
Model selection, matching the priority order requested:
  1. Explicit --model flag always wins.
  2. Otherwise, if a report (Piece 2 output) is loaded and its `model_used`
     field names a model that's *currently* loaded on the target server,
     inherit it automatically — this is "pick up the prior piece's model
     if integrated."
  3. Otherwise, fall back to whatever's loaded on the server (matches
     Piece 1/2's same convention: llama-server serves one model per
     instance, so there's usually only one real choice).
"""

from .llm_client import LlamaServerClient, LlamaServerError
from .context import ReportContext


def resolve_model(client: LlamaServerClient, report_ctx: ReportContext, explicit_model: str = None) -> str:
    if explicit_model:
        client.model = explicit_model
        return client.resolve_model()  # raises ModelNotFoundError with a clear message if not loaded

    available = client.list_models()
    if not available:
        raise LlamaServerError(f"llama-server at {client.base_url} reports no loaded models.")

    inherited = report_ctx.model_used
    if inherited and inherited in available:
        client.model = inherited
        return inherited

    # fall back to whatever's loaded
    client.model = available[0]
    return available[0]
