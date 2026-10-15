"""The recall eval must search every writer-visible analysis section.

Trial-15 lesson, three times learned: findings-only search missed the
twist channel, then the ledger, then coverage — each time understating
recall until a trial caught it. This test fails when to_findings_json
gains a top-level section in neither SEARCHED_SECTIONS nor
EXCLUDED_SECTIONS, forcing an explicit classify-don't-ignore decision.
"""
import os

from screenplay_parser import parse_fountain
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer import report as report_mod
from tests.eval_recall import (  # noqa: E402  (eval-only helper, never CI)
    EXCLUDED_SECTIONS, SEARCHED_SECTIONS, _search_texts)

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")


def test_every_report_section_is_classified():
    doc = parse_fountain(FIXTURE)
    payload = report_mod.to_findings_json(AnalysisResult(doc))
    unclassified = (set(payload) - set(SEARCHED_SECTIONS)
                    - set(EXCLUDED_SECTIONS))
    assert not unclassified, (
        f"new report sections the eval ignores: {sorted(unclassified)} — "
        "add to SEARCHED_SECTIONS (writer-visible analysis) or "
        "EXCLUDED_SECTIONS (with a reason)")


def test_withdrawals_never_searched():
    assert "withdrawals" in EXCLUDED_SECTIONS
    report = {"findings": [],
              "withdrawals": [{"finding": {"issue": "quuxploy sting"}}]}
    goldens = {"facts": [{"id": "q", "anchors": ["quuxploy"]}]}

    import json
    import tempfile
    tmp = tempfile.mkdtemp()
    rep = os.path.join(tmp, "report.findings.json")
    json.dump(report, open(rep, "w", encoding="utf-8"))
    gold = os.path.join(tmp, "gold.json")
    json.dump(goldens, open(gold, "w", encoding="utf-8"))

    from tests.eval_recall import hit_rate
    assert hit_rate(rep, gold) == [("q", False)]


def test_search_covers_all_searched_sections():
    doc = parse_fountain(FIXTURE)
    payload = report_mod.to_findings_json(AnalysisResult(doc))
    texts = _search_texts(payload)
    assert isinstance(texts, list) and all(isinstance(t, str) for t in texts)
