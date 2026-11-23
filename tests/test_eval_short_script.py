import json
import tempfile
import unittest
from pathlib import Path

from tests.eval_short_script import evaluate_manifest, evaluate_run


def report(findings, **extra):
    return {"findings": findings, "model_used": "local-test", **extra}


def annotation(rows):
    return {"judgments": rows}


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class ShortScriptEvalTests(unittest.TestCase):
    def test_page_limit_is_strictly_under_thirty(self):
        manifest = {"script_id": "x", "page_count": 30,
                    "runs": [{"run_id": "r1", "report": "r.json", "judgments": "j.json"}]}
        with self.assertRaisesRegex(ValueError, "under 30"):
            evaluate_manifest(manifest)

    def test_metrics_keep_truth_support_and_quote_location_separate(self):
        data = report([{
            "category": "character", "issue": "Raj distrusts the visitor.",
            "severity": "high", "scene_refs": [2],
            "verification": {"status": "verified", "matched_scene": 2},
        }])
        row = {"finding_index": 1, "reviewer_role": "writer", "truth": "partial",
               "claim_support": "does_not_support", "quote_location": "located_in_cited_scene"}
        writer = evaluate_run("r1", data, annotation([row]))["reviewers"]["writer"]
        self.assertEqual(writer["truth"]["not_wrong_rate_pct"], 100.0)
        self.assertEqual(writer["truth"]["strict_correct_rate_pct"], 0.0)
        self.assertEqual(writer["claim_support"]["strict_support_rate_pct"], 0.0)
        self.assertEqual(writer["quote_location"]["located_in_cited_scene_rate_pct"], 100.0)
        self.assertEqual(writer["high_severity_claims_judged_not_supported"], 1)

    def test_unclear_and_not_applicable_are_not_in_decisive_denominators(self):
        data = report([
            {"issue": "A", "verification": {"status": "no_quote"}},
            {"issue": "B", "verification": {"status": "not_found"}},
        ])
        rows = [
            {"finding_index": 1, "reviewer_role": "independent", "claim_support": "unclear",
             "quote_location": "not_applicable"},
            {"finding_index": 2, "reviewer_role": "independent", "claim_support": "supports",
             "quote_location": "unclear"},
        ]
        metrics = evaluate_run("r1", data, annotation(rows))["reviewers"]["independent"]
        self.assertEqual(metrics["claim_support"]["rated_excluding_unclear"], 1)
        self.assertEqual(metrics["quote_location"]["rated_excluding_unclear_and_not_applicable"], 0)
        self.assertIsNone(metrics["quote_location"]["located_in_cited_scene_rate_pct"])
        self.assertEqual(metrics["findings_without_any_judgment"], 0)

    def test_bad_indexes_and_duplicate_role_judgments_are_rejected(self):
        data = report([{"issue": "A"}])
        with self.assertRaisesRegex(ValueError, "finding_index"):
            evaluate_run("r1", data, annotation([{"finding_index": 2, "reviewer_role": "writer"}]))
        duplicate = [
            {"finding_index": 1, "reviewer_role": "writer"},
            {"finding_index": 1, "reviewer_role": "writer"},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate judgment"):
            evaluate_run("r1", data, annotation(duplicate))

    def test_independent_reviewer_does_not_inflate_writer_truth_rate(self):
        data = report([{"issue": "A"}])
        rows = [{"finding_index": 1, "reviewer_role": "independent", "truth": "correct"}]
        metrics = evaluate_run("r1", data, annotation(rows))["reviewers"]
        self.assertEqual(metrics["independent"]["truth"]["judged"], 1)
        self.assertEqual(metrics["writer"]["truth"]["judged"], 0)
        self.assertIsNone(metrics["writer"]["truth"]["not_wrong_rate_pct"])

    def test_run_churn_is_reported_as_lexical_repeatability(self):
        manifest = {
            "script_id": "short-a", "page_count": 12,
            "runs": [
                {"run_id": "r1", "report": "r1.json", "judgments": "j1.json"},
                {"run_id": "r2", "report": "r2.json", "judgments": "j2.json"},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root / "r1.json", report([{"category": "theme", "issue": "The choice costs Raj.", "scene_refs": [3]}]))
            write(root / "r2.json", report([{"category": "theme", "issue": "The choice costs Raj.", "scene_refs": [3]},
                                             {"category": "dialogue", "issue": "A line repeats.", "scene_refs": [4]}]))
            write(root / "j1.json", annotation([]))
            write(root / "j2.json", annotation([]))
            result = evaluate_manifest(manifest, root)
        churn = result["run_to_run_churn"][0]
        self.assertEqual(churn["findings_added"], 1)
        self.assertEqual(churn["findings_missing_from_next_run"], 0)
        self.assertEqual(churn["text_and_scene_churn_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
