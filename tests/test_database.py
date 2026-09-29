"""Persistence regressions; each test uses an isolated, real SQLite database."""
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested" / "leads.db"
        self.db_patch = patch.object(database, "DB_PATH", str(self.path))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

    def lead(self, **changes):
        lead = dict(id="one", address="Old address", city="Old city", price=100,
                    price_text="$100", source="old", source_type="fsbo",
                    link="https://old.example", description="old description",
                    owner_name="Old owner", owner_mailing="Old mailing",
                    motivation="old motivation", deal_score=9,
                    equity_estimate="old equity", status="new",
                    created_at="2026-01-01", updated_at="2026-01-01",
                    raw_data="old raw")
        lead.update(changes)
        return lead

    def test_rescrape_refreshes_fields_preserves_workflow_and_creation(self):
        original = self.lead()
        self.assertIs(database.upsert_lead(original), True)
        conn = database.get_conn()
        try:
            conn.execute("UPDATE leads SET status='contacted' WHERE id='one'")
            conn.commit()
        finally:
            conn.close()
        refreshed = {key: "changed " + key for key in original}
        refreshed.update(id="one", price=50, deal_score=2, status="new")
        self.assertIs(database.upsert_lead(refreshed), False)
        actual = dict(database.get_leads()[0])
        expected = dict(refreshed, status="contacted", created_at=original['created_at'])
        self.assertEqual(actual, expected)
        self.assertEqual(original, self.lead(), "input must not be mutated")

    def test_relative_filename_initializes_in_current_directory(self):
        previous = os.getcwd()
        try:
            os.chdir(self.temp.name)
            with patch.object(database, "DB_PATH", "relative.db"):
                database.init_db()
                self.assertTrue(database.upsert_lead(self.lead()))
                self.assertEqual(len(database.get_leads()), 1)
        finally:
            os.chdir(previous)

    def test_recent_scrapes_are_newest_first_and_limited(self):
        self.assertEqual(database.get_recent_scrapes(), [])
        conn = database.get_conn()
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO scrape_log (source, found, new_leads, error, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [("latest", 3, 1, None, "2026-03-01"),
                     ("old", 0, 0, "network error", "2026-01-01"),
                     ("tie", 1, 0, None, "2026-03-01")])
        finally:
            conn.close()
        rows = database.get_recent_scrapes(limit=2)
        self.assertEqual([row['source'] for row in rows], ['tie', 'latest'])
        self.assertEqual(rows[1]['new_leads'], 1)
        self.assertEqual(database.get_recent_scrapes(limit=0), [])

    def test_failed_write_releases_lock_and_leaves_existing_lead_intact(self):
        database.upsert_lead(self.lead())
        invalid = self.lead(price=object())
        with self.assertRaises(sqlite3.Error):
            database.upsert_lead(invalid)
        self.assertEqual(database.get_leads()[0]['price'], 100)
        self.assertFalse(database.upsert_lead(self.lead(price=200)))
        self.assertEqual(database.get_leads()[0]['price'], 200)

    def test_existing_schema_filters_stats_and_repeated_init(self):
        database.upsert_lead(self.lead())
        database.upsert_lead(self.lead(id='two', city='Bakersfield', deal_score=5))
        database.upsert_lead(self.lead(id='three', city='Bakersfield', deal_score=1))
        database.init_db()
        self.assertEqual(len(database.get_leads(min_score=5, city='Bakers', limit=1)), 1)
        self.assertEqual(database.get_stats(), {
            'total': 3, 'hot': 1, 'warm': 2,
            'by_source': {'old': 3}, 'by_city': {'Bakersfield': 2, 'Old city': 1}})

    def test_concurrent_upserts_count_exactly_one_new_lead(self):
        workers = 16
        barrier = Barrier(workers)

        def save(index):
            barrier.wait(timeout=10)
            return database.upsert_lead(self.lead(price=index))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(save, range(workers)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(database.get_leads()), 1)

    def test_upsert_records_only_materially_changed_observations(self):
        first = self.lead(raw_data='{"b": 2, "a": 1}')
        self.assertTrue(database.upsert_lead(first))
        same_facts = self.lead(
            updated_at="2026-02-01",
            status="contacted",
            raw_data='{"a":1,"b":2}',
        )
        self.assertFalse(database.upsert_lead(same_facts))
        self.assertEqual(len(database.get_property_observations("one")), 1)

        self.assertFalse(database.upsert_lead(self.lead(price=90, updated_at="2026-03-01")))
        observations = database.get_property_observations("one")
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0]["snapshot"]["price"], 90)
        self.assertEqual(observations[1]["snapshot"]["price"], 100)
        self.assertFalse(database.upsert_lead(self.lead(price=100, updated_at="2026-04-01")))
        self.assertEqual(len(database.get_property_observations("one")), 3)

    def test_canonical_snapshot_and_fingerprint_are_deterministic(self):
        left = {"z": [{"b": 2, "a": 1}], "a": None}
        right = {"a": None, "z": [{"a": 1, "b": 2}]}
        self.assertEqual(database.canonical_snapshot(left), database.canonical_snapshot(right))
        self.assertEqual(database.snapshot_fingerprint(left), database.snapshot_fingerprint(right))

    def test_analysis_event_and_report_helpers_round_trip_json(self):
        self.assertTrue(database.save_property_event(
            "one", "price_drop", {"from": 100, "to": 90}, fingerprint="drop-1",
        ))
        self.assertFalse(database.save_property_event(
            "one", "price_drop", {"from": 100, "to": 90}, fingerprint="drop-1",
        ))
        event = database.get_property_events("one")[0]
        self.assertEqual(event["details"], {"from": 100, "to": 90})

        analysis_id = database.save_property_analysis(
            "one", {"score": 82, "confidence": "B"}, model_version="v2"
        )
        self.assertIsInstance(analysis_id, int)
        latest = database.get_latest_property_analysis("one")
        self.assertEqual(latest["analysis"], {"score": 82, "confidence": "B"})
        self.assertEqual(latest["model_version"], "v2")

        run_id = database.save_report_run(
            {"top_10": ["one"], "counts": {"rejected": 4}}, run_id="run-1"
        )
        self.assertEqual(run_id, "run-1")
        self.assertEqual(database.get_report_runs()[0]["report"]["top_10"], ["one"])

    def test_intelligence_tables_are_repeat_safe(self):
        database.init_db()
        database.init_db()
        with closing(database.get_conn()) as conn:
            names = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertTrue({
            "property_observations", "property_events", "property_analyses", "report_runs"
        }.issubset(names))

    def test_run_lock_prevents_overlap_and_can_be_released(self):
        self.assertTrue(database.acquire_run_lock())
        self.assertFalse(database.acquire_run_lock())
        self.assertTrue(database.release_run_lock())
        self.assertFalse(database.release_run_lock())
        self.assertTrue(database.acquire_run_lock())

    def test_stale_run_lock_can_be_recovered(self):
        with closing(database.get_conn()) as conn, conn:
            conn.execute(
                "INSERT INTO system_locks (lock_name, acquired_at) VALUES (?, ?)",
                ("old", "2020-01-01T00:00:00+00:00"),
            )
        self.assertTrue(database.acquire_run_lock("old", stale_after_minutes=60))

    def test_run_lock_renewal_requires_current_owner(self):
        self.assertFalse(database.renew_run_lock("renew-test"))
        self.assertTrue(database.acquire_run_lock("renew-test"))
        self.assertTrue(database.renew_run_lock("renew-test"))
        self.assertTrue(database.release_run_lock("renew-test"))
        self.assertFalse(database.renew_run_lock("renew-test"))


if __name__ == "__main__":
    unittest.main()
