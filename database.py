"""
Database for leads.

Also persists a durable last-run summary so the dashboard can show the most
recent full scrape outcome even after restarts.
"""
import json
import os
import hashlib
import uuid
from typing import Any
from datetime import datetime, timedelta, timezone
import sqlite3
from contextlib import closing
from config import DB_PATH


MATERIAL_LEAD_FIELDS = (
    "address", "city", "price", "price_text", "source", "source_type", "link",
    "description", "owner_name", "owner_mailing", "motivation", "equity_estimate",
    "raw_data",
)

_RUN_LOCK_TOKENS: dict[str, str] = {}


def canonical_snapshot(value: Any) -> Any:
    """Return a stable, JSON-compatible representation without inventing values."""
    if isinstance(value, dict):
        return {str(key): canonical_snapshot(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [canonical_snapshot(item) for item in value]
    if isinstance(value, set):
        items = [canonical_snapshot(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def snapshot_fingerprint(value: Any) -> str:
    payload = json.dumps(
        canonical_snapshot(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lead_snapshot(lead: dict) -> dict[str, Any]:
    snapshot = {field: lead.get(field) for field in MATERIAL_LEAD_FIELDS}
    raw = snapshot.get("raw_data")
    if isinstance(raw, str):
        try:
            snapshot["raw_data"] = json.loads(raw)
        except (TypeError, ValueError):
            pass
    structured = snapshot.get("raw_data") if isinstance(snapshot.get("raw_data"), dict) else {}
    snapshot["listing_status"] = structured.get("listing_status")
    snapshot["broker"] = structured.get("broker")
    return canonical_snapshot(snapshot)


def get_conn() -> sqlite3.Connection:
    db_dir = os.path.dirname(os.fspath(DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            address TEXT,
            city TEXT,
            price INTEGER,
            price_text TEXT,
            source TEXT,
            source_type TEXT,
            link TEXT,
            description TEXT,
            owner_name TEXT,
            owner_mailing TEXT,
            motivation TEXT,
            deal_score INTEGER,
            equity_estimate TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT,
            updated_at TEXT,
            raw_data TEXT
        )
        """
        )
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            source_type TEXT,
            found INTEGER,
            new_leads INTEGER,
            error TEXT,
            created_at TEXT
        )
        """
        )
        # Migration: add source_type to scrape_log for pre-existing databases
        try:
            c.execute("ALTER TABLE scrape_log ADD COLUMN source_type TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        c.execute(
            "CREATE TABLE IF NOT EXISTS last_run_summary ("
            "id INTEGER PRIMARY KEY CHECK (id = 1),"
            "started_at TEXT,"
            "finished_at TEXT,"
            "total_found INTEGER,"
            "total_new INTEGER,"
            "source_summary TEXT,"
            "error TEXT"
            ")"
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS property_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                source TEXT,
                fingerprint TEXT NOT NULL,
                snapshot TEXT NOT NULL
            )"""
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_property_time "
            "ON property_observations(property_id, observed_at DESC, id DESC)"
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS property_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                details TEXT NOT NULL,
                UNIQUE(property_id, fingerprint)
            )"""
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_property_time "
            "ON property_events(property_id, detected_at DESC, id DESC)"
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS property_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id TEXT NOT NULL,
                analysis_type TEXT NOT NULL,
                model_version TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                analysis TEXT NOT NULL
            )"""
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_property_type_time "
            "ON property_analyses(property_id, analysis_type, analyzed_at DESC, id DESC)"
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS report_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                report TEXT NOT NULL
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS system_locks (
                lock_name TEXT PRIMARY KEY,
                acquired_at TEXT NOT NULL,
                owner_token TEXT
            )"""
        )
        try:
            c.execute("ALTER TABLE system_locks ADD COLUMN owner_token TEXT")
        except sqlite3.OperationalError:
            pass


def upsert_lead(lead: dict) -> bool:
    conn = get_conn()
    try:
        with conn:
            return _upsert_lead(conn, lead)
    finally:
        conn.close()


def _upsert_lead(conn: sqlite3.Connection, lead: dict) -> bool:
    conn.execute("BEGIN IMMEDIATE")
    c = conn.cursor()
    c.execute("SELECT id FROM leads WHERE id=?", (lead["id"],))
    exists = c.fetchone()
    if exists:
        c.execute(
            """
        UPDATE leads SET address=:address, city=:city, price=:price,
            price_text=:price_text, source=:source, source_type=:source_type,
            link=:link, description=:description, owner_name=:owner_name,
            owner_mailing=:owner_mailing, motivation=:motivation,
            deal_score=:deal_score, equity_estimate=:equity_estimate,
            updated_at=:updated_at, raw_data=:raw_data
        WHERE id=:id
        """,
            lead,
        )
    else:
        c.execute(
            """
        INSERT INTO leads (id, address, city, price, price_text, source, source_type,
            link, description, owner_name, owner_mailing, motivation, deal_score,
            equity_estimate, status, created_at, updated_at, raw_data)
        VALUES (:id, :address, :city, :price, :price_text, :source, :source_type,
            :link, :description, :owner_name, :owner_mailing, :motivation, :deal_score,
            :equity_estimate, :status, :created_at, :updated_at, :raw_data)
        """,
            lead,
        )
    _save_property_observation(
        conn,
        lead["id"],
        _lead_snapshot(lead),
        observed_at=lead.get("updated_at") or _utc_now(),
        source=lead.get("source"),
    )
    return exists is None


def _save_property_observation(
    conn: sqlite3.Connection,
    property_id: str,
    snapshot: dict,
    *,
    observed_at: str,
    source: str | None,
) -> bool:
    canonical = canonical_snapshot(snapshot)
    fingerprint = snapshot_fingerprint(canonical)
    latest = conn.execute(
        "SELECT fingerprint FROM property_observations WHERE property_id=? "
        "ORDER BY observed_at DESC, id DESC LIMIT 1",
        (property_id,),
    ).fetchone()
    if latest and latest["fingerprint"] == fingerprint:
        return False
    cursor = conn.execute(
        "INSERT INTO property_observations "
        "(property_id, observed_at, source, fingerprint, snapshot) VALUES (?, ?, ?, ?, ?)",
        (property_id, observed_at, source, fingerprint,
         json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)),
    )
    return cursor.rowcount == 1


def save_property_observation(
    property_id: str,
    snapshot: dict,
    *,
    observed_at: str | None = None,
    source: str | None = None,
) -> bool:
    with closing(get_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        return _save_property_observation(
            conn, property_id, snapshot, observed_at=observed_at or _utc_now(), source=source,
        )


def get_property_observations(property_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    query = (
        "SELECT * FROM property_observations WHERE property_id=? "
        "ORDER BY observed_at DESC, id DESC"
    )
    params: list[Any] = [property_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(max(0, limit))
    with closing(get_conn()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row, snapshot=json.loads(row["snapshot"])) for row in rows]


def save_property_event(
    property_id: str,
    event_type: str,
    details: dict,
    *,
    detected_at: str | None = None,
    fingerprint: str | None = None,
) -> bool:
    canonical = canonical_snapshot(details)
    event_fingerprint = fingerprint or snapshot_fingerprint({
        "property_id": property_id, "event_type": event_type, "details": canonical,
    })
    with closing(get_conn()) as conn, conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO property_events "
            "(property_id, event_type, detected_at, fingerprint, details) VALUES (?, ?, ?, ?, ?)",
            (property_id, event_type, detected_at or _utc_now(), event_fingerprint,
             json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)),
        )
        return cursor.rowcount == 1


def get_property_events(property_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT * FROM property_events"
    params: list[Any] = []
    if property_id is not None:
        query += " WHERE property_id=?"
        params.append(property_id)
    query += " ORDER BY detected_at DESC, id DESC LIMIT ?"
    params.append(max(0, limit))
    with closing(get_conn()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row, details=json.loads(row["details"])) for row in rows]


def save_property_analysis(
    property_id: str,
    analysis: dict,
    *,
    analyzed_at: str | None = None,
    analysis_type: str = "opportunity",
    model_version: str = "1",
) -> int:
    payload = json.dumps(canonical_snapshot(analysis), sort_keys=True, ensure_ascii=False)
    with closing(get_conn()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO property_analyses "
            "(property_id, analysis_type, model_version, analyzed_at, analysis) "
            "VALUES (?, ?, ?, ?, ?)",
            (property_id, analysis_type, model_version, analyzed_at or _utc_now(), payload),
        )
        return int(cursor.lastrowid)


def get_latest_property_analysis(
    property_id: str, analysis_type: str = "opportunity"
) -> dict[str, Any] | None:
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT * FROM property_analyses WHERE property_id=? AND analysis_type=? "
            "ORDER BY analyzed_at DESC, id DESC LIMIT 1",
            (property_id, analysis_type),
        ).fetchone()
    return dict(row, analysis=json.loads(row["analysis"])) if row else None


def get_latest_property_analyses(limit: int = 1000) -> list[dict[str, Any]]:
    """Return one newest analysis per property without exposing owner/contact fields."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT pa.* FROM property_analyses pa "
            "WHERE pa.id=(SELECT pa2.id FROM property_analyses pa2 "
            "WHERE pa2.property_id=pa.property_id AND pa2.analysis_type=pa.analysis_type "
            "ORDER BY pa2.analyzed_at DESC, pa2.id DESC LIMIT 1) "
            "ORDER BY pa.analyzed_at DESC, pa.id DESC LIMIT ?", (max(0, limit),)
        ).fetchall()
    return [dict(row, analysis=json.loads(row["analysis"])) for row in rows]


def save_report_run(
    report: dict,
    *,
    run_id: str | None = None,
    created_at: str | None = None,
) -> str:
    actual_run_id = run_id or uuid.uuid4().hex
    payload = json.dumps(canonical_snapshot(report), sort_keys=True, ensure_ascii=False)
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO report_runs (run_id, created_at, report) VALUES (?, ?, ?) "
            "ON CONFLICT(run_id) DO UPDATE SET created_at=excluded.created_at, report=excluded.report",
            (actual_run_id, created_at or _utc_now(), payload),
        )
    return actual_run_id


def get_report_runs(limit: int = 20) -> list[dict[str, Any]]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM report_runs ORDER BY created_at DESC, rowid DESC LIMIT ?", (max(0, limit),)
        ).fetchall()
    return [dict(row, report=json.loads(row["report"])) for row in rows]


def acquire_run_lock(lock_name: str = "intelligence", stale_after_minutes: int = 120) -> bool:
    now = datetime.now(timezone.utc)
    owner_token = uuid.uuid4().hex
    conn = get_conn()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT acquired_at FROM system_locks WHERE lock_name=?", (lock_name,)
            ).fetchone()
            if row:
                try:
                    acquired = datetime.fromisoformat(row["acquired_at"])
                    if acquired.tzinfo is None:
                        acquired = acquired.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    acquired = now
                if acquired > now - timedelta(minutes=max(0, stale_after_minutes)):
                    return False
            conn.execute(
                "INSERT INTO system_locks (lock_name, acquired_at, owner_token) VALUES (?, ?, ?) "
                "ON CONFLICT(lock_name) DO UPDATE SET acquired_at=excluded.acquired_at, "
                "owner_token=excluded.owner_token",
                (lock_name, now.isoformat(), owner_token),
            )
            _RUN_LOCK_TOKENS[lock_name] = owner_token
            return True
    finally:
        conn.close()


def release_run_lock(lock_name: str = "intelligence") -> bool:
    owner_token = _RUN_LOCK_TOKENS.pop(lock_name, None)
    if not owner_token:
        return False
    with closing(get_conn()) as conn, conn:
        cursor = conn.execute("DELETE FROM system_locks WHERE lock_name=? AND owner_token=?",
                              (lock_name, owner_token))
        return cursor.rowcount == 1


def renew_run_lock(lock_name: str = "intelligence") -> bool:
    """Renew only the lease owned by this process."""
    owner_token = _RUN_LOCK_TOKENS.get(lock_name)
    if not owner_token:
        return False
    with closing(get_conn()) as conn, conn:
        cursor = conn.execute(
            "UPDATE system_locks SET acquired_at=? WHERE lock_name=? AND owner_token=?",
            (_utc_now(), lock_name, owner_token),
        )
        return cursor.rowcount == 1


def get_leads(min_score: int = 0, city: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        query = "SELECT * FROM leads WHERE deal_score >= ?"
        params: list[Any] = [min_score]
        if city:
            query += " AND city LIKE ?"
            params.append(f"%{city}%")
        query += " ORDER BY deal_score DESC, created_at DESC LIMIT ?"
        params.append(limit)
        c.execute(query, params)
        return c.fetchall()


def get_stats() -> dict[str, Any]:
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        stats: dict[str, Any] = {}
        c.execute("SELECT COUNT(*) FROM leads")
        stats["total"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM leads WHERE deal_score >= 7")
        stats["hot"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM leads WHERE deal_score >= 5")
        stats["warm"] = c.fetchone()[0]
        c.execute("SELECT source, COUNT(*) as cnt FROM leads GROUP BY source")
        stats["by_source"] = dict(c.fetchall())
        c.execute("SELECT city, COUNT(*) as cnt FROM leads GROUP BY city ORDER BY cnt DESC")
        stats["by_city"] = dict(c.fetchall())
        return stats


def get_recent_scrapes(limit: int = 20) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM scrape_log ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def save_last_run_summary(
    source_summary: dict[str, dict[str, Any]],
    total_found: int,
    total_new: int,
    error: str | None = None,
) -> bool:
    conn = get_conn()
    try:
        with conn:
            c = conn.cursor()
            finished_at = datetime.now(timezone.utc).isoformat()
            c.execute(
                "INSERT OR REPLACE INTO last_run_summary "
                "(id, started_at, finished_at, total_found, total_new, source_summary, error) "
                "VALUES (1, 0, ?, ?, ?, ?, ?)",
                (finished_at, total_found, total_new, json.dumps(source_summary), error or ""),
            )
        return True
    except Exception:
        return False
    finally:
        conn.close()


def load_last_run_summary() -> dict[str, Any] | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM last_run_summary WHERE id = 1"
        ).fetchone()
        if not row:
            return None
        try:
            source_summary = json.loads(row["source_summary"]) if row["source_summary"] else {}
        except Exception:
            source_summary = {}
        return {
            "started_at": row["started_at"] or "",
            "finished_at": row["finished_at"],
            "total_found": row["total_found"],
            "total_new": row["total_new"],
            "source_summary": source_summary,
            "error": row["error"],
        }
    finally:
        conn.close()
