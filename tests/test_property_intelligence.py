import unittest

from property_intelligence import (UNKNOWN, analyze_property, detect_data_conflicts,
                                   grade_evidence, resolve_evidence)


class PropertyIntelligenceTests(unittest.TestCase):
    def test_official_evidence_wins_and_conflict_is_retained(self):
        result = resolve_evidence([
            {"value": 210000, "source_type": "marketplace", "source": "portal"},
            {"value": 205000, "source_type": "official", "source": "county"},
        ])
        self.assertEqual(result["value"], 205000)
        self.assertTrue(result["has_conflict"])
        self.assertEqual(len(result["alternatives"]), 1)

    def test_missing_evidence_is_unknown_not_invented(self):
        self.assertEqual(resolve_evidence([])["value"], UNKNOWN)
        self.assertEqual(grade_evidence([])["grade"], "UNKNOWN")

    def test_conflict_intelligence_groups_by_field(self):
        conflicts = detect_data_conflicts([
            {"field": "sqft", "value": 1400, "source_type": "official", "source": "assessor"},
            {"field": "sqft", "value": 1550, "source_type": "listing", "source": "broker"},
            {"field": "beds", "value": 3, "source_type": "official", "source": "assessor"},
        ])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["field"], "sqft")
        self.assertEqual(conflicts[0]["selected_value"], 1400)

    def test_change_pressure_and_capitulation(self):
        history = [
            {"observed_at": "2026-01-01", "price": 255000, "listing_status": "active", "description": "Nice home"},
            {"observed_at": "2026-01-18", "price": 239000, "listing_status": "active", "description": "Seller concession"},
            {"observed_at": "2026-02-01", "price": 225000, "listing_status": "pending", "description": "Seller concession"},
            {"observed_at": "2026-02-08", "price": 209000, "listing_status": "active", "description": "Cash only, as-is"},
        ]
        result = analyze_property({"address": "1 Test St", "price": 209000}, history=history)
        self.assertGreater(result["seller_pressure_velocity"]["score"], 60)
        self.assertGreater(result["seller_capitulation_index"]["score"], 60)
        event_types = {e["type"] for e in result["change_events"]}
        self.assertIn("price_reduction", event_types)
        self.assertIn("back_on_market", event_types)
        self.assertIn("motivation_language_added", event_types)

    def test_optionality_market_rehab_and_counterfactuals(self):
        prop = {
            "address": "2 Test St", "price": 180000, "lot_sqft": 15000,
            "corner_lot": True, "zoning": None, "description": "poor photos fixer",
            "bedrooms": 3, "bathrooms": 2, "sqft": 1400,
        }
        comps = [
            {"sold_price": 300000, "distance_miles": .3, "sold_date": "2026-09-01", "sqft": 1450, "source_url": "https://broker.example/1"},
            {"sold_price": 290000, "distance_miles": .7, "sold_date": "2026-09-02", "sqft": 1350, "source_url": "https://broker.example/2"},
            {"sold_price": 295000, "distance_miles": .5, "sold_date": "2026-09-03", "sqft": 1400, "source_url": "https://broker.example/3"},
        ]
        result = analyze_property(prop, comps=comps, rehab={"low": 30000, "base": 45000, "high": 65000,
                                  "source_url": "https://contractor.example/estimate",
                                  "observed_at": "2026-09-20"}, as_of="2026-09-29")
        self.assertGreater(result["hidden_optionality"]["score"], 0)
        self.assertEqual(result["hidden_optionality"]["zoning_verified"], False)
        self.assertEqual(result["micro_market"]["arv"], 295000)
        self.assertEqual(result["renovation_spread"]["base"], 70000)
        self.assertEqual(len(result["counterfactuals"]), 3)
        self.assertGreater(result["marketing_inefficiency"]["score"], 0)

    def test_economic_inputs_require_valid_provenance(self):
        comps = [{"sold_price": 300000, "sold_date": "2026-10-01", "distance_miles": .2,
                  "source_url": "https://broker.example/future"} for _ in range(3)]
        result = analyze_property({"price": 150000}, comps=comps,
            rehab={"low": 1, "base": 1, "high": 1, "source_url": "x", "verified": True},
            as_of="2026-09-29")
        self.assertEqual(result["micro_market"]["arv"], UNKNOWN)
        self.assertEqual(result["renovation_spread"]["base"], UNKNOWN)
        self.assertTrue(all(row["estimated_spread"] == UNKNOWN for row in result["counterfactuals"]))

    def test_unverified_arv_does_not_create_profit_score(self):
        result = analyze_property({"address": "3 Test St", "price": 100000})
        self.assertEqual(result["micro_market"]["arv"], UNKNOWN)
        self.assertEqual(result["score_breakdown"]["profit_spread"], 0)
        self.assertEqual(result["confidence"]["grade"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
