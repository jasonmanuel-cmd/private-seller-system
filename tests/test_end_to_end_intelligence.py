import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import database
from intelligence_pipeline import analyze_all_properties
from reports import generate_reports


class IntelligenceEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.report_dir = root / "reports"
        self.db_patch = patch.object(database, "DB_PATH", str(root / "leads.db"))
        self.db_patch.start()
        database.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def _lead(self, price, updated_at):
        now = datetime.now(timezone.utc).isoformat()
        return {"id": "e2e-1", "address": "100 Test Ave", "city": "Bakersfield",
                "price": price, "price_text": f"${price:,}", "source": "licensed listing",
                "source_type": "listing", "link": "https://example.com/e2e-1",
                "description": "As-is property", "owner_name": "", "owner_mailing": "",
                "motivation": "unknown", "deal_score": 2, "equity_estimate": "UNKNOWN",
                "status": "new", "created_at": now, "updated_at": updated_at,
                "raw_data": json.dumps({
                    "comps": [
                        {"sold_price": 320000, "sold_date": "2026-09-20", "distance_miles": .2, "source_url": "https://broker.example/1"},
                        {"sold_price": 310000, "sold_date": "2026-09-19", "distance_miles": .3, "source_url": "https://broker.example/2"},
                        {"sold_price": 300000, "sold_date": "2026-09-18", "distance_miles": .4, "source_url": "https://broker.example/3"}],
                    "rehab": {"low": 30000, "base": 45000, "high": 65000,
                              "source_url": "https://contractor.example/estimate",
                              "observed_at": "2026-09-21"},
                    "evidence": [{"field": "lot_sqft", "value": 9000,
                                  "source_type": "official", "source": "county",
                                  "source_url": "https://example.gov/parcel"}],
                })}

    def _analyze_and_report(self, run_id):
        pipeline = analyze_all_properties(opportunity_threshold=50, watchlist_threshold=25)
        events = [{"property_id": row["property_id"], "event_type": row["event_type"],
                   "observed_at": row["detected_at"], **row["details"]}
                  for row in database.get_property_events(limit=100)]
        report = generate_reports(pipeline["analyses"], events, self.report_dir, run_id=run_id)
        return pipeline, report

    def test_initial_idempotent_and_changed_runs_produce_valid_outputs(self):
        database.upsert_lead(self._lead(250000, "2026-09-01T00:00:00+00:00"))
        first, first_report = self._analyze_and_report("first")
        second, _ = self._analyze_and_report("second")
        self.assertEqual(first["processed"], 1)
        self.assertEqual(second["events_created"], 0)

        database.upsert_lead(self._lead(210000, "2026-09-15T00:00:00+00:00"))
        changed, changed_report = self._analyze_and_report("changed")
        self.assertGreaterEqual(changed["events_created"], 1)
        self.assertGreaterEqual(changed_report["counts"]["events"], 1)

        for name in ("top-10.csv", "top-3-deep-dive.csv", "watchlist.csv", "rejected.csv"):
            with (self.report_dir / name).open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                self.assertIsInstance(rows, list)
        self.assertEqual(sum(changed_report["counts"][key] for key in ("top10", "watchlist", "rejected")), 1)
        self.assertTrue((self.report_dir / "runs" / first_report["run_id"] / "intelligence-report.md").exists())


if __name__ == "__main__":
    unittest.main()
