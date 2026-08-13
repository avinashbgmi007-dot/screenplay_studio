"""E2E driver for the writer-relationship-memory verification.

Usage:
    python _e2e_memory.py "message one" "message two" ...
    python _e2e_memory.py --get          # just GET /api/writer-memory

Sends each message to the running webapp chat session, prints the reply
prefix + elapsed time, then dumps the writer-memory profile and card.
"""

import json
import sys
import time
import urllib.request

BASE = "http://localhost:8500"
PROJECT = "Pain_PDF_Direct"
SESSION = "9ae5f312"


def post(path, payload=None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=590) as resp:
        return json.loads(resp.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as resp:
        return json.loads(resp.read())


def dump_memory(tag):
    m = get("/api/writer-memory")
    p = m["profile"]
    print(f"\n--- MEMORY after {tag} ---")
    print("total_turns_observed:", p["meta"]["total_turns_observed"])
    for dim, d in p["dimensions"].items():
        ev = d["evidence"]
        print(f"  {dim}: value={d['value']} conf={d['confidence']} "
              f"evidence pos={ev['pos']} neg={ev['neg']}")
    print("topic_gravity:", p["topic_gravity"])
    print("observations:", len(p["observations"]))
    for o in p["observations"]:
        print(f"  - [{o['source']}] {o['text']} (conf={o['confidence']}, "
              f"suppressed={o['suppressed']}, contradictions={o['contradictions']})")
    print("card:", (m["card"] or "null")[:300])
    return p


def main():
    args = sys.argv[1:]
    if args and args[0] == "--get":
        dump_memory("GET")
        return
    for i, text in enumerate(args, 1):
        t0 = time.time()
        resp = post(f"/api/projects/{PROJECT}/chat/sessions/{SESSION}/messages",
                    {"text": text})
        dt = time.time() - t0
        reply = resp.get("reply", "")
        print(f"TURN {i} ({dt:.0f}s) in: {text[:80]}")
        print(f"  reply ({len(reply)} chars): {reply[:160]}")
    dump_memory(f"{len(args)} turns")


if __name__ == "__main__":
    main()
