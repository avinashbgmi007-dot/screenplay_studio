#!/usr/bin/env python3
"""Keep docs/API_ROUTE_MAP.md honest about the webapp's URL map (gap 84).

The gap: the map documented 83 `/api` paths and the live app served 87. Four were
missing — `GET /api/rules/<rule_id>`, `GET /api/projects/<name>/passes`,
`POST /api/projects/<name>/quickcheck`, `POST /api/projects/<name>/findings/intent`.
The document's own totals paragraph was pinned by a test, so the *count* was
guarded while individual rows drifted — and the count test can only ever catch
drift in one direction: add two routes and delete two and the total still matches.

So this tool checks BOTH directions:

    undocumented  a live route with no row  -> the doc is behind the code
    dead          a documented row with no live route -> the doc describes nothing

It deliberately does NOT rewrite the map. The prose is written by a person and
carries the reasoning ("grounded in knowledge-base rule <id>", "no model call");
a generator that rewrote it would delete that to satisfy a checker. Instead it
appends a generated block, and the block is the only part it owns.

Usage:
    python tools/route_map.py            # report (exit 1 if drift)
    python tools/route_map.py --write    # regenerate the generated block
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "API_ROUTE_MAP.md")

BEGIN = "<!-- BEGIN GENERATED: route census (tools/route_map.py) -->"
END = "<!-- END GENERATED: route census -->"


def _normalise(path: str) -> str:
    """`<int:index>` and `<index>` are the same route to a reader."""
    return re.sub(r"<[^>]*>", "<x>", path.split("?")[0].rstrip("/"))


def live_routes() -> dict[tuple[str, str], str]:
    """(METHOD, rule) -> endpoint name, for every real /api route."""
    sys.path.insert(0, ROOT)
    from screenplay_studio import webapp_server as ws

    out = {}
    for rule in ws.app.url_map.iter_rules():
        path = str(rule)
        if not path.startswith("/api"):
            continue
        for method in rule.methods:
            if method in ("HEAD", "OPTIONS"):
                continue  # Flask's automatic companions, not surfaces
            out[(method, path)] = rule.endpoint
    return out


def documented_rows(text: str) -> set[tuple[str, str]]:
    """Every `| METHOD | `/api/...` |` row in the map.

    Scoped to `/api` on purpose: the same file also tabulates the co-writer
    server's routes and the demo model's `/v1/...` endpoints (gaps 83 and the
    three-server table). Those are not this webapp's URL map, and counting them
    as "dead rows" was my first bug here — the checker has to know which server
    it is checking.
    """
    rows = set()
    for method, path in re.findall(r"\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`(/api/[^`]+)`", text):
        rows.add((method, _normalise(path)))
    return rows


def drift(text: str) -> tuple[list, list]:
    live = {(m, _normalise(p)): ep for (m, p), ep in live_routes().items()}
    doc = documented_rows(text)
    # A row is satisfied when ANY documented method matches that path, and a path
    # is satisfied when any live method matches it. Method-level comparison is the
    # stricter reading, but the map legitimately lists one row per route with the
    # primary verb, so demanding an exact (method, path) pair would report drift
    # on routes that are documented correctly. Compare PATHS.
    live_paths = {p for (_m, p) in live}
    doc_paths = {p for (_m, p) in doc}
    undocumented = sorted(live_paths - doc_paths)
    dead = sorted(doc_paths - live_paths)
    return undocumented, dead


def generated_block() -> str:
    live = live_routes()
    lines = [BEGIN,
             "",
             "## Route census (generated — do not hand-edit this block)",
             "",
             "Written by `tools/route_map.py` from the live Flask URL map. The prose",
             "above is the human half (what each route *means*); this table is the",
             "mechanical half (what actually exists). `tests/test_route_map_is_current.py`",
             "checks both directions, so a route added without a row and a row left",
             "behind by a deleted route both fail the suite.",
             "",
             f"**{len(live)} live `/api` routes.**",
             "",
             "| Method | Path | Endpoint |",
             "|---|---|---|"]
    for (method, path), endpoint in sorted(live.items()):
        lines.append(f"| {method} | `{path}` | `{endpoint}` |")
    lines += ["", END, ""]
    return "\n".join(lines)


def apply(text: str) -> str:
    block = generated_block()
    if BEGIN in text and END in text:
        start = text.index(BEGIN)
        stop = text.index(END) + len(END)
        return text[:start] + block.rstrip("\n") + "\n" + text[stop:].lstrip("\n")
    return text.rstrip("\n") + "\n\n" + block


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="regenerate the block in place")
    args = ap.parse_args(argv)

    with open(DOC, encoding="utf-8") as f:
        text = f.read()

    if args.write:
        with open(DOC, "w", encoding="utf-8") as f:
            f.write(apply(text))
        print(f"route census regenerated in {os.path.relpath(DOC, ROOT)}")
        return 0

    undocumented, dead = drift(text)
    if not undocumented and not dead:
        print(f"route map is current: {len(live_routes())} live routes, all documented")
        return 0
    if undocumented:
        print(f"{len(undocumented)} live path(s) with no row in the map:")
        for p in undocumented:
            print(f"  {p}")
    if dead:
        print(f"{len(dead)} documented path(s) with no live route:")
        for p in dead:
            print(f"  {p}")
    print("\nRun `python tools/route_map.py --write` to regenerate the census block,")
    print("then add prose rows for the undocumented ones.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
