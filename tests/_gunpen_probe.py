"""Session-only probe: dump the real gun_pen report's shape + numbers.

Reads the live studio (E2E_BASE, default :8500) and prints everything the
feedback-projection audit needs to verify against real data. No writes.
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8500")
PROJECT = os.environ.get("GUNPEN_PROJECT", "gun_pen_2")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    projects = get("/api/projects")
    print("=== /api/projects keys ===")
    print(type(projects).__name__, len(projects) if isinstance(projects, list) else list(projects))
    rows = projects if isinstance(projects, list) else projects.get("projects", [])
    for p in rows:
        if PROJECT in json.dumps(p):
            print("--- matching project row ---")
            print(json.dumps(p, indent=2, ensure_ascii=False)[:1500])
            break

    rep = get(f"/api/projects/{PROJECT}/report")
    print("\n=== /report top-level keys ===")
    print(sorted(rep.keys()))
    findings = rep.get("findings") or []
    print(f"findings: {len(findings)}")
    print("first finding keys:", sorted((findings[0] or {}).keys()) if findings else "-")

    # category / severity histogram
    from collections import Counter
    cat = Counter((f.get("category") or "other") for f in findings)
    sev = Counter((f.get("severity") or "?").lower() for f in findings)
    print("categories:", dict(cat))
    print("severities:", dict(sev))

    # verification status histogram
    vstat = Counter(((f.get("verification") or {}).get("status") or "none") for f in findings)
    print("verification statuses:", dict(vstat))
    vs = rep.get("verification_summary")
    print("verification_summary:", vs)
    if vs:
        total = sum(vs.get(k, 0) for k in ("verified", "not_found", "no_quote", "scene_not_found"))
        print("  computed total:", total,
              "| pct:", round(100 * vs.get("verified", 0) / total) if total else "-")

    # quote presence per finding
    with_quote = sum(1 for f in findings if (f.get("evidence_quote") or "").strip())
    print(f"findings WITH evidence_quote: {with_quote}/{len(findings)}")

    # report-section blocks
    for k in ("coverage", "setup_payoff", "character_reads", "logline_test",
              "character_dials", "pacing", "genre", "formatting_findings"):
        v = rep.get(k)
        if v is None:
            print(f"  {k}: ABSENT")
        elif isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
        elif isinstance(v, dict):
            print(f"  {k}: dict keys={sorted(v.keys())}")
        else:
            print(f"  {k}: {type(v).__name__}")

    # rule_id / check_id split sanity
    rid = sum(1 for f in findings if f.get("rule_id"))
    cid = sum(1 for f in findings if f.get("check_id"))
    print(f"findings with rule_id: {rid} | with check_id: {cid}")

    print("\n=== fixqueue ===")
    try:
        fq = get(f"/api/projects/{PROJECT}/fixqueue")
        print("fixqueue keys:", sorted(fq.keys()) if isinstance(fq, dict) else type(fq).__name__)
        if isinstance(fq, dict):
            print("  items:", len(fq.get("items") or []),
                  "| total_count:", fq.get("total_count"),
                  "| dismissed:", len(fq.get("dismissed_flags") or []))
    except Exception as e:
        print("fixqueue error:", e)

    print("\n=== script ===")
    try:
        sc = get(f"/api/projects/{PROJECT}/script")
        print("script keys:", sorted(sc.keys()))
        print("  scenes:", len(sc.get("scenes") or []))
    except Exception as e:
        print("script error:", e)

    print("\n=== report.md ===")
    try:
        with urllib.request.urlopen(BASE + f"/api/projects/{PROJECT}/report/export", timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
        print("export bytes:", len(body), "| first line:", body.splitlines()[0][:120] if body else "-")
    except Exception as e:
        print("export error:", e)


if __name__ == "__main__":
    main()


def deep():
    rep = get(f"/api/projects/{PROJECT}/report")
    print("\n=== stats ===")
    print(json.dumps(rep.get("stats"), indent=2, ensure_ascii=False)[:1200])
    print("\n=== coverage ===")
    print(json.dumps(rep.get("coverage"), indent=2, ensure_ascii=False)[:1400])
    print("\n=== setup_payoff ===")
    for e in rep.get("setup_payoff") or []:
        print(" ", e.get("status"), "| kind:", e.get("kind"), "| setup_scenes:", e.get("setup_scenes"),
              "| payoff_scenes:", e.get("payoff_scenes"), "|", (e.get("setup") or "")[:70])
    print("\n=== pacing ===")
    print(json.dumps(rep.get("pacing"), ensure_ascii=False)[:700])
    print("\n=== character_dials ===")
    print(json.dumps(rep.get("character_dials"), ensure_ascii=False)[:700])
    print("\n=== character_reads ===")
    print(json.dumps(rep.get("character_reads"), ensure_ascii=False)[:700])
    print("\n=== logline_test ===")
    print(json.dumps(rep.get("logline_test"), ensure_ascii=False)[:900])
    print("\n=== last_pass.json on disk ===")
    lp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "studio_projects", PROJECT, "last_pass.json")
    try:
        with open(lp_path, encoding="utf-8") as f:
            lp = json.load(f)
        print("keys:", sorted(lp.keys()))
        print("ids:", len(lp.get("ids") or []), "| computed_at:", lp.get("computed_at"))
        print("last_total:", lp.get("last_total"), "| still_live:", lp.get("still_live"),
              "| fixed:", lp.get("fixed"), "| new:", lp.get("new"))
        print("ghosted_marks:", len(lp.get("ghosted_marks") or []))
        rep_ids = [f.get("id") for f in (rep.get("findings") or [])]
        print("report findings:", len(rep_ids), "| last_pass ids:", len(lp.get("ids") or []))
    except Exception as e:
        print("last_pass error:", e)
    print("\n=== raw report.md ===")
    md = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "studio_projects", PROJECT, "report.md")
    try:
        with open(md, encoding="utf-8") as f:
            body = f.read()
        print("bytes:", len(body), "| lines:", body.count(chr(10)))
        print("first 2 lines:", body.splitlines()[:2])
        print("contains '35'?", "35" in body, "| contains 'Gun'?", "Gun" in body or "gun" in body)
    except Exception as e:
        print("report.md error:", e)


if __name__ == "__main__":
    pass
