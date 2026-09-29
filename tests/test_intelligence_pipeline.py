import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import database
from intelligence_pipeline import analyze_all_properties


def lead(**changes):
    now = datetime.now(timezone.utc).isoformat()
    value = dict(id="listing-1", address="1 Test St", city="Bakersfield", price=200000,
                 price_text="$200,000", source="broker", source_type="listing",
                 link="https://example.com/1", description="Needs work", owner_name="",
                 owner_mailing="", motivation="unknown", deal_score=2, equity_estimate="UNKNOWN",
                 status="new", created_at=now, updated_at=now,
                 raw_data=json.dumps({"comps": [
                     {"sold_price": 310000, "sold_date": "2026-09-10", "distance_miles": .3, "source_url": "https://broker.example/1"},
                     {"sold_price": 300000, "sold_date": "2026-09-11", "distance_miles": .4, "source_url": "https://broker.example/2"},
                     {"sold_price": 320000, "sold_date": "2026-09-12", "distance_miles": .5, "source_url": "https://broker.example/3"}],
                                      "rehab": {"low": 30000, "base": 45000, "high": 60000,
                                                "source_url": "https://contractor.example/estimate",
                                                "observed_at": "2026-09-15"}}))
    value.update(changes)
    return value


class IntelligencePipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(database, "DB_PATH", str(Path(self.tmp.name) / "test.db"))
        self.patch.start()
        database.init_db()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_analysis_is_persisted_and_classified(self):
        database.upsert_lead(lead())
        result = analyze_all_properties(opportunity_threshold=60, watchlist_threshold=30)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(len(result["analyses"]), 1)
        row = result["analyses"][0]
        self.assertIn(row["decision"], {"top", "watchlist", "rejected"})
        self.assertNotIn("owner_name", row)
        stored = database.get_latest_property_analysis("listing-1")
        self.assertEqual(stored["analysis"]["property_id"], "listing-1")

    def test_second_changed_observation_creates_deduplicated_trigger(self):
        database.upsert_lead(lead(updated_at="2026-01-01T00:00:00+00:00", price=250000))
        database.upsert_lead(lead(updated_at="2026-01-15T00:00:00+00:00", price=225000))
        first = analyze_all_properties()
        second = analyze_all_properties()
        self.assertGreaterEqual(first["events_created"], 1)
        self.assertEqual(second["events_created"], 0)

    def test_untrusted_import_cannot_self_certify_as_official(self):
        value = lead(raw_data=json.dumps({"evidence": [{"field": "zoning", "value": "R-2",
            "source_type": "official", "source": "manual note", "source_url": "https://example.com/note"}]}))
        database.upsert_lead(value)
        result = analyze_all_properties()["analyses"][0]["analysis"]
        zoning = [item for item in result["data_conflicts"] if item.get("field") == "zoning"]
        self.assertEqual(zoning, [])
        self.assertLess(result["confidence"]["score"], 85)

        # Suffix lookalikes and private/contact conflicts are not trusted or reported.
        database.upsert_lead(lead(id="listing-2", raw_data=json.dumps({"evidence": [
            {"field": "zoning", "value": "R-3", "source_type": "official",
             "source": "lookalike", "source_url": "https://notkerncounty.com/record"},
            {"field": "seller_phone", "value": "555-0100", "source_type": "official",
             "source": "note", "source_url": "https://county.gov/record"}]})))
        second = [row for row in analyze_all_properties()["analyses"] if row["property_id"] == "listing-2"][0]
        self.assertNotIn("555-0100", json.dumps(second))
        self.assertNotEqual(second["analysis"]["confidence"]["grade"], "A")

    def test_listing_status_and_broker_changes_flow_from_structured_observations(self):
        database.upsert_lead(lead(updated_at="2026-09-01T00:00:00+00:00",
            raw_data=json.dumps({"listing_status": "pending", "broker": "Broker A"})))
        database.upsert_lead(lead(updated_at="2026-09-05T00:00:00+00:00",
            raw_data=json.dumps({"listing_status": "active", "broker": "Broker B"})))
        result = analyze_all_properties()["analyses"][0]["analysis"]
        event_types = {event["type"] for event in result["change_events"]}
        self.assertIn("back_on_market", event_types)
        self.assertIn("broker_changed", event_types)


if __name__ == "__main__":
    unittest.main()
