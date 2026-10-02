# docs/audit/feedback_probe_session.py - LIVE probe for the feedback + co-writer
# quality baseline (2026-10-01). Boots the REAL studio (no demo model) against the
# local llama-server, runs a full analysis on the bundled sample, dumps the report
# and findings JSON, then drives Sameer and Sushruta chat turns through the real
# engine. DELETED after use. Results -> docs/audit/_probe_results.json
import json
import os
import sys
import threading
import time
import urllib.parse

import requests

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

PORT = 8511
B = f"http://127.0.0.1:{PORT}"
RESULTS = os.path.join(REPO, "docs", "audit", "_probe_results.json")

results = {"log": []}


def log(msg):
    print(f"[probe] {msg}", flush=True)
    results["log"].append(msg)


def save():
    json.dump(results, open(RESULTS, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


def main_boot():
    os.environ["SCREENPLAY_STUDIO_DEMO_MODEL"] = "0"  # fallback OFF: a dead server must fail loudly, not fake the baseline
    from screenplay_studio.webapp_server import main
    sys.argv = [
        "webapp_server", "--no-token", "--port", str(PORT),
        "--projects-dir", os.path.join(REPO, "docs", "audit", "_probe_projects"),
        # 127.0.0.1 on purpose: localhost resolves ::1 first on Windows and
        # llama-server binds IPv4 only, so the startup probe read it as down.
        "--server", "http://127.0.0.1:8080",
    ]
    main()


threading.Thread(target=main_boot, daemon=True).start()
for _ in range(120):
    try:
        if requests.get(f"{B}/api/config", timeout=2).status_code == 200:
            break
    except Exception:
        time.sleep(0.5)
else:
    log("studio never came up")
    save()
    sys.exit(1)
log("studio is up")

# ---- create the bundled sample as a real project -----------------------------
import shutil  # noqa: E402

from screenplay_studio.sample import SAMPLE_SCRIPT  # noqa: E402

proj_dir = os.path.join(REPO, "docs", "audit", "_probe_projects")
shutil.rmtree(proj_dir, ignore_errors=True)  # fresh: no _2 suffix, no stale demo report
os.makedirs(proj_dir, exist_ok=True)
fountain = os.path.join(proj_dir, "_sample_input.fountain")
with open(fountain, "w", encoding="utf-8") as f:
    f.write(SAMPLE_SCRIPT)

qname = urllib.parse.quote("The Late Hour")
r = requests.post(f"{B}/api/projects", timeout=60,
                  files={"file": ("The Late Hour.fountain",
                                  open(fountain, "rb").read(), "text/plain")},
                  data={"title": "The Late Hour"})
log(f"create project: {r.status_code} {r.text[:200]}")
assert r.status_code in (200, 201), r.text
name = r.json().get("project") or "The_Late_Hour"
qname = urllib.parse.quote(name)
log(f"create project: {r.status_code} {r.text[:200]}")
assert r.status_code in (200, 201), r.text

# ---- run the REAL analysis (in-request; this blocks until done) --------------
t0 = time.time()
r = requests.post(f"{B}/api/projects/{qname}/analyze", timeout=2700, json={})
dur = time.time() - t0
log(f"analyze: {r.status_code} in {dur:.0f}s: {r.text[:300]}")
results["analyze_status"] = r.status_code
results["analyze_seconds"] = round(dur, 1)
save()
if r.status_code != 200:
    sys.exit(1)

# ---- pull the report and findings --------------------------------------------
rep = requests.get(f"{B}/api/projects/{qname}/report", timeout=60)
results["report_status"] = rep.status_code
report = rep.json() if rep.status_code == 200 else {}
results["report_keys"] = sorted(report.keys())
fd = requests.get(f"{B}/api/projects/{qname}/findings", timeout=60)
findings_doc = fd.json() if fd.status_code == 200 else {}
findings = findings_doc.get("findings") or report.get("findings") or []
results["findings_count"] = len(findings)

# ---- per-category efficiency + verification honesty ---------------------------
from collections import defaultdict  # noqa: E402

by_cat = defaultdict(lambda: {"n": 0, "sev": defaultdict(int), "ver": defaultdict(int),
                              "with_quote": 0, "conf_sum": 0.0, "conf_n": 0,
                              "samples": []})
for f_ in findings:
    c = f_.get("category") or "?"
    d = by_cat[c]
    d["n"] += 1
    d["sev"][f_.get("severity") or "?"] += 1
    ver = (f_.get("verification") or {})
    d["ver"][ver.get("status") or "none"] += 1
    if (f_.get("evidence_quote") or "").strip():
        d["with_quote"] += 1
    conf = ver.get("confidence")
    if isinstance(conf, (int, float)):
        d["conf_sum"] += conf
        d["conf_n"] += 1
    if len(d["samples"]) < 2:
        d["samples"].append({
            "title": (f_.get("title") or f_.get("message") or "")[:140],
            "scene_refs": f_.get("scene_refs"),
            "quote": (f_.get("evidence_quote") or "")[:120],
            "verification": ver.get("status"),
            "confidence": ver.get("confidence"),
        })
results["by_category"] = {
    c: {**{k: v for k, v in d.items() if k not in ("sev", "ver", "conf_sum", "conf_n")},
        "severities": dict(d["sev"]),
        "verification": dict(d["ver"]),
        "verified_pct_of_quoted": round(
            100.0 * d["ver"].get("verified", 0) / max(1, d["with_quote"]), 1)
        if d["with_quote"] else None,
        "mean_conf": round(d["conf_sum"] / d["conf_n"], 3) if d["conf_n"] else None}
    for c, d in by_cat.items()}
results["coverage"] = report.get("coverage") or {
    k: report.get(k) for k in ("logline", "genre", "synopsis", "recommendation")
    if k in report}
# WHICH MODEL ANSWERED — a probe that cannot tell demo from real produces a
# baseline that lies. demo-craft-model means the fallback hijacked the run.
results["model_used"] = report.get("model_used")
results["real_model"] = report.get("model_used") not in (None, "demo-craft-model")
save()

# ---- chat legs through the REAL engine ----------------------------------------
def chat(persona, text, label):
    r = requests.post(f"{B}/api/projects/{qname}/chat/start", timeout=120, json={})
    sid = None
    if r.status_code == 200:
        j = r.json()
        sid = j.get("session_id") or (j.get("session") or {}).get("session_id")
    log(f"{label}: start {r.status_code} sid={sid}")
    if not sid:
        results[label] = {"error": r.text[:300]}
        save()
        return
    requests.post(f"{B}/api/projects/{qname}/chat/sessions/{sid}/settings",
                  timeout=60, json={"persona": persona})
    t0 = time.time()
    r = requests.post(
        f"{B}/api/projects/{qname}/chat/sessions/{sid}/messages",
        timeout=900, json={"text": text})
    dt = time.time() - t0
    j = {}
    try:
        j = r.json()
    except Exception:
        pass
    reply = (j.get("reply") or j.get("message", {}).get("text")
             or json.dumps(j)[:400])
    log(f"{label}: {r.status_code} in {dt:.0f}s, reply {len(reply)} chars")
    results[label] = {"status": r.status_code, "seconds": round(dt, 1),
                      "persona": persona, "question": text, "reply": reply}
    save()


chat("writing_partner",
     "What is the weakest beat in this script, and what specifically would you do about it?",
     "sameer")
chat("script_consultant",
     "Diagnose this script's structural problems in order of severity, citing scenes.",
     "sushruta")

log("DONE - results written")
