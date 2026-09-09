"""
CLI for Piece 1 (Parser).

Usage:
    python -m screenplay_parser parse script.fdx -o script.json
    python -m screenplay_parser parse script.pdf -o script.json --stats
    python -m screenplay_parser stats script.json
"""

import argparse
import json
import sys

from . import parse_screenplay, ScriptDocument, build_knowledge_graph
from . import stats as stats_module


def cmd_parse(args):
    try:
        doc = parse_screenplay(args.input)
    except Exception as e:
        print(f"ERROR: failed to parse '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    out_path = args.output or (args.input.rsplit(".", 1)[0] + ".json")
    doc.save(out_path)

    print(f"Parsed '{args.input}' ({doc.source_format}) -> '{out_path}'")
    print(f"  confidence: {doc.parse_confidence}")
    print(f"  scenes: {doc.scene_count}")
    print(f"  characters: {len(doc.all_characters)}")
    if doc.estimated_page_count:
        print(f"  estimated pages: {doc.estimated_page_count}")
    if doc.warnings:
        print(f"  warnings: {len(doc.warnings)}")
        for w in doc.warnings:
            print(f"    [{w.severity}] {w.message}")

    if args.stats:
        stats_path = out_path.rsplit(".", 1)[0] + ".stats.json"
        report = stats_module.full_stats_report(doc)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Stats written -> '{stats_path}'")

    if args.kg:
        kg_path = out_path.rsplit(".", 1)[0] + ".kg.json"
        kg = build_knowledge_graph(doc)
        kg.save(kg_path)
        print(f"Knowledge graph written -> '{kg_path}'")
        print(f"  characters: {len(kg.characters)}")
        print(f"  prop candidates (recurring 2+ scenes): {len(kg.prop_candidates)}")
        print(f"  promise candidates: {len(kg.promise_candidates)}")


def cmd_stats(args):
    doc = ScriptDocument.load(args.input)
    report = stats_module.full_stats_report(doc)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(prog="screenplay_parser", description="Screenplay parser (Piece 1)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parse a screenplay file into structured JSON")
    p_parse.add_argument("input", help="Path to .fdx / .pdf / .txt / .fountain / .md screenplay")
    p_parse.add_argument("-o", "--output", help="Output JSON path (default: <input>.json)")
    p_parse.add_argument("--stats", action="store_true", help="Also compute deterministic analytics")
    p_parse.add_argument("--kg", action="store_true", help="Also build the knowledge graph (character/prop/timeline candidates)")
    p_parse.set_defaults(func=cmd_parse)

    p_stats = sub.add_parser("stats", help="Print deterministic analytics for an already-parsed JSON file")
    p_stats.add_argument("input", help="Path to a ScriptDocument JSON file (output of 'parse')")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
