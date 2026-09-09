"""
CLI for Piece 2 (Analyzer).

Usage:
    python -m screenplay_analyzer analyze script.json \\
        --server http://localhost:8080 \\
        --model qwen-agentworld-35b-a3b-mxfp4_moe.gguf \\
        -o report.md

If --model is omitted, whatever model llama-server has loaded is used
(queried live from /v1/models — llama-server serves one model per instance,
so there's only ever one real choice unless you're running multiple
instances/ports).
"""

import argparse
import sys

from screenplay_parser.models import ScriptDocument

from .llm_client import LlamaServerClient, LlamaServerError
from .pipeline import analyze
from .report import save_report


def main():
    parser = argparse.ArgumentParser(prog="screenplay_analyzer")
    parser.add_argument("input", help="Path to a ScriptDocument JSON file (output of Piece 1)")
    parser.add_argument("--server", default="http://localhost:8080", help="llama-server base URL")
    parser.add_argument("--model", default=None, help="Model id (default: whatever is loaded)")
    parser.add_argument("-o", "--output", default=None, help="Output .md path (default: <input>.report.md)")
    parser.add_argument("--categories", default="dialogue,theme,character,structure,scene_function,coverage",
                         help="Comma-separated categories to run")
    args = parser.parse_args()

    doc = ScriptDocument.load(args.input)
    client = LlamaServerClient(base_url=args.server, model=args.model)

    try:
        client.resolve_model()
    except LlamaServerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    result = analyze(doc, client, run_categories=tuple(args.categories.split(",")))

    md_path = args.output or (args.input.rsplit(".", 1)[0] + ".report.md")
    json_path = md_path.rsplit(".", 1)[0] + ".findings.json"
    save_report(result, md_path, json_path)

    print(f"Report -> {md_path}")
    print(f"Findings JSON -> {json_path}")
    print(f"Model: {result.model_used}")
    print(f"Findings: {len(result.findings)} | Verification: {result.verification}")
    if result.errors:
        print("Errors:")
        for e in result.errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
