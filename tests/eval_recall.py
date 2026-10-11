"""Local recall eval: golden facts vs a real-model report. Real model required;
never CI. Usage: python tests/eval_recall.py <project-dir> <golden-json>"""
import json
import sys


def hit_rate(report_path, golden_path):
    report = json.load(open(report_path, encoding="utf-8"))
    goldens = json.load(open(golden_path, encoding="utf-8"))
    texts = [f"{f.get('issue', '')} {f.get('observation', '')} {f.get('evidence_quote', '')}".lower()
             for f in report.get("findings", [])]
    rows = []
    for fact in goldens["facts"]:
        hit = any(a.lower() in t for a in fact["anchors"] for t in texts)
        rows.append((fact["id"], hit))
    return rows


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        import tempfile, os
        tmp = tempfile.mkdtemp()
        rep = os.path.join(tmp, "report.findings.json")
        json.dump({"findings": [{"issue": "The countdown pays at 00:00.",
                                 "observation": "", "evidence_quote": ""}]}, open(rep, "w", encoding="utf-8"))
        gold = os.path.join(tmp, "gold.json")
        json.dump({"facts": [{"id": "a", "anchors": ["00:00"]},
                             {"id": "b", "anchors": ["never-mentioned-xyz"]}]},
                  open(gold, "w", encoding="utf-8"))
        rows = hit_rate(rep, gold)
        assert rows == [("a", True), ("b", False)], rows
        print("selftest OK")
        sys.exit(0)
    rows = hit_rate(sys.argv[1] + "/report.findings.json", sys.argv[2])
    for fid, hit in rows:
        print(("HIT  " if hit else "MISS ") + fid)
    print(f"{sum(1 for _, h in rows if h)}/{len(rows)} facts hit")
    sys.exit(0 if all(h for _, h in rows) else 1)
