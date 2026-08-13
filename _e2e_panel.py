"""E2E driver for the notes-panel behaviors: refresh-now, forget (suppress),
and error paths — exactly what the 'Sam's notes on you' modal calls."""

import json
import time
import urllib.error
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
    try:
        with urllib.request.urlopen(req, timeout=590) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as resp:
        return resp.status, json.loads(resp.read())


print("=== 1. GET /api/writer-memory (panel open) ===")
status, m = get("/api/writer-memory")
print("status:", status, "| card present:", m["card"] is not None)
obs = m["profile"]["observations"]
ids = [o["id"] for o in obs]
print("observations:", [(o["id"], o["text"][:40], o["suppressed"]) for o in obs])

print("\n=== 2. POST /api/writer-memory/refresh (refresh-now button) ===")
t0 = time.time()
status, m = post("/api/writer-memory/refresh", {"project": PROJECT, "session_id": SESSION})
dt = time.time() - t0
print(f"status: {status} ({dt:.0f}s)")
meta = m["profile"]["meta"]
print("refresh_count:", meta["refresh_count"], "| last_refresh set:", meta["last_refresh"] is not None,
      "| turns_at_last_refresh:", meta["turns_at_last_refresh"])
print("dimensions after refresh:")
for dim, d in m["profile"]["dimensions"].items():
    print(f"  {dim}: value={d['value']} conf={d['confidence']}")
print("card now:", (m["card"] or "null")[:200])

print("\n=== 3. Forget (suppress) — first observation ===")
target = ids[0]
print(f"suppressing {target} ...")
status, _ = post(f"/api/writer-memory/observations/{target}/suppress")
print("suppress status:", status, "(expect 200)")

print("\n=== 4. Re-suppress same id (panel can't double-forget) ===")
status, body = post(f"/api/writer-memory/observations/{target}/suppress")
print("re-suppress status:", status, body, "(expect 404)")

print("\n=== 5. Suppress unknown id (stale id after refresh) ===")
status, body = post("/api/writer-memory/observations/obs_deadbeef/suppress")
print("unknown suppress status:", status, body, "(expect 404)")

print("\n=== 6. GET after forget — suppressed excluded from card ===")
status, m = get("/api/writer-memory")
obs = m["profile"]["observations"]
print("remaining observations:", [(o["text"][:40], o["suppressed"]) for o in obs])
print("card mentions forgotten phrase:", "no softening" in (m["card"] or ""))
print("card:", (m["card"] or "null")[:200])

print("\n=== 7. Refresh with bad payload (panel guards) ===")
status, body = post("/api/writer-memory/refresh", {})
print("status:", status, body, "(expect 400)")
