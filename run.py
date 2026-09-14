"""
Main orchestrator — runs all scrapers and scores leads
Run: python run.py --once
     python run.py --loop (every hour)
"""
import argparse
import time
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(__file__))

from database import init_db, get_stats
from scrapers.craigslist import scrape_craigslist
from scrapers.kern_tax import scrape_kern_tax
from scrapers.bakersfield_code import scrape_bakersfield_code
from scrapers.zillow_fsbo import scrape_zillow_fsbo

def run_all():
    print(f"\n{'='*60}")
    print(f"KERN COUNTY NO-MLS LEAD SCRAPER — {datetime.now()}")
    print(f"{'='*60}")
    
    init_db()
    
    results = {}
    
    print("\n[1/4] Craigslist FSBO...")
    try:
        found, new, err = scrape_craigslist()
        results['craigslist'] = {"found": found, "new": new, "err": err}
    except Exception as e:
        print(f"Craigslist error: {e}")
        results['craigslist'] = {"found": 0, "new": 0, "err": str(e)}
    
    print("\n[2/4] Zillow FSBO...")
    try:
        found, new, err = scrape_zillow_fsbo()
        results['zillow_fsbo'] = {"found": found, "new": new, "err": err}
    except Exception as e:
        print(f"Zillow error: {e}")
        results['zillow_fsbo'] = {"found": 0, "new": 0, "err": str(e)}
    
    print("\n[3/4] Kern County Tax-Defaulted...")
    try:
        found, new, err = scrape_kern_tax()
        results['kern_tax'] = {"found": found, "new": new, "err": err}
    except Exception as e:
        print(f"Kern Tax error: {e}")
        results['kern_tax'] = {"found": 0, "new": 0, "err": str(e)}
    
    print("\n[4/4] Bakersfield Code / Vacant...")
    try:
        found, new, err = scrape_bakersfield_code()
        results['bakersfield_code'] = {"found": found, "new": new, "err": err}
    except Exception as e:
        print(f"Bakersfield Code error: {e}")
        results['bakersfield_code'] = {"found": 0, "new": 0, "err": str(e)}
    
    # Stats
    stats = get_stats()
    print(f"\n{'='*60}")
    print(f"SUMMARY — {datetime.now()}")
    print(f"{'='*60}")
    for src, res in results.items():
        print(f"{src}: Found {res['found']}, New {res['new']}, Err: {res['err'][:80] if res['err'] else 'None'}")
    
    print(f"\nDATABASE STATS:")
    print(f"Total leads: {stats['total']}")
    print(f"Hot (7+): {stats['hot']}")
    print(f"Warm (5+): {stats['warm']}")
    print(f"By source: {stats['by_source']}")
    print(f"By city: {stats['by_city']}")
    
    print(f"\nTop 5 Hot Leads:")
    from database import get_leads
    hot = get_leads(min_score=5, limit=5)
    for lead in hot:
        print(f"  Score {lead['deal_score']}/10 | ${lead['price']} | {lead['city']} | {lead['motivation']} | {lead['address'][:50]} | {lead['link'][:60]}")
    
    print(f"\nNext: Run dashboard: python app.py → http://localhost:5000")
    print(f"Or check DB: data/leads.db")
    
    return results

def run_loop():
    while True:
        run_all()
        print(f"\nSleeping 1 hour... Ctrl+C to stop")
        time.sleep(3600)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--loop", action="store_true", help="Run every hour")
    args = parser.parse_args()
    
    if args.loop:
        run_loop()
    else:
        run_all()
