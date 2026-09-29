import csv
import tempfile
import unittest
from pathlib import Path

from reports import generate_reports


class ReportTests(unittest.TestCase):
    def test_generates_ranked_buckets_and_safe_csv(self):
        analyses = [
            {"property_id": "one", "address": "=1+1", "city": "Bakersfield", "score": 91,
             "confidence_grade": "A", "decision": "top", "risks": ["roof UNKNOWN"],
             "next_action": "verify roof", "triggers": ["price_cut"], "limitations": []},
            {"property_id": "two", "address": "2 Main", "city": "Bakersfield", "score": 55,
             "confidence_grade": "C", "decision": "watchlist", "rejection_reasons": [],
             "next_action": "obtain comps", "limitations": ["ARV UNKNOWN"]},
            {"property_id": "three", "address": "3 Main", "city": "Bakersfield", "score": 10,
             "confidence_grade": "U", "decision": "rejected",
             "rejection_reasons": ["insufficient verified evidence"], "limitations": []},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_reports(analyses, [], tmp, run_id="run-1")
            for name in ("top-10.csv", "top-3-deep-dive.csv", "watchlist.csv",
                         "rejected.csv", "change-events.csv", "intelligence-report.md"):
                self.assertTrue((Path(tmp) / name).exists(), name)
            with (Path(tmp) / "top-10.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["property_id"], "one")
            self.assertTrue(rows[0]["address"].startswith("'"))
            self.assertEqual(result["counts"], {"top10": 1, "top3": 1, "watchlist": 1, "rejected": 1, "events": 0})
            with (Path(tmp) / "top-3-deep-dive.csv").open(encoding="utf-8", newline="") as handle:
                deep = next(csv.DictReader(handle))
            self.assertIn("counterfactuals", deep)
            self.assertIn("score_breakdown", deep)

    def test_empty_reports_still_have_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate_reports([], [], tmp, run_id="empty")
            with (Path(tmp) / "top-10.csv").open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                self.assertGreater(len(next(reader)), 5)
                self.assertEqual(list(reader), [])


if __name__ == "__main__":
    unittest.main()
