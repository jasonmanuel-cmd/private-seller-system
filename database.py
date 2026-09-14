"""
Database for leads
"""
import sqlite3
import os
from config import DB_PATH

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
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
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS scrape_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        found INTEGER,
        new_leads INTEGER,
        error TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def upsert_lead(lead):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM leads WHERE id=?", (lead['id'],))
    exists = c.fetchone()
    if exists:
        # Update score if higher
        c.execute("""
            UPDATE leads SET deal_score=MAX(deal_score, ?), updated_at=?, description=?, price=?
            WHERE id=?
        """, (lead.get('deal_score',0), lead.get('updated_at'), lead.get('description','')[:2000], lead.get('price',0), lead['id']))
    else:
        c.execute("""
            INSERT INTO leads (id, address, city, price, price_text, source, source_type, link, description, owner_name, owner_mailing, motivation, deal_score, equity_estimate, status, created_at, updated_at, raw_data)
            VALUES (:id, :address, :city, :price, :price_text, :source, :source_type, :link, :description, :owner_name, :owner_mailing, :motivation, :deal_score, :equity_estimate, :status, :created_at, :updated_at, :raw_data)
        """, lead)
    conn.commit()
    conn.close()
    return not exists

def get_leads(min_score=0, city=None, limit=100):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM leads WHERE deal_score >= ?"
    params = [min_score]
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")
    query += " ORDER BY deal_score DESC, created_at DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) FROM leads")
    stats['total'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE deal_score >= 7")
    stats['hot'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE deal_score >= 5")
    stats['warm'] = c.fetchone()[0]
    c.execute("SELECT source, COUNT(*) as cnt FROM leads GROUP BY source")
    stats['by_source'] = dict(c.fetchall())
    c.execute("SELECT city, COUNT(*) as cnt FROM leads GROUP BY city ORDER BY cnt DESC")
    stats['by_city'] = dict(c.fetchall())
    conn.close()
    return stats
