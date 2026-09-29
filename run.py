"""
Run sources, persist every source outcome, and return structured results.

Sources:
- craigslist       — Craigslist RSS feeds for Kern County metros (timeout-bounded HTTP).
- zillow_fsbo      — Zillow FSBO search pages (403 to automated access; manual resource).
- kern_tax         — Kern County Tax Auction: general page → GovEase browse page (public).
- bakersfield_code — Bakersfield code enforcement availability check.
- browser_sources  — Playwright browser investigation of public-government surfaces
                     (assessor, permits, probate, code enforcement, auctions). Only runs
                     when playwright + a chromium browser are available; in every other case
                     the orchestrator skips it and still records a scrape_log row for the
                     source so the dashboard shows it was considered.
"""
import argparse
import time
import uuid
from datetime import datetime, timezone
from config import OPPORTUNITY_THRESHOLD, REPORT_DIR, RUN_INTERVAL_MINUTES, WATCHLIST_THRESHOLD
from database import (acquire_run_lock, get_conn, init_db,
                      release_run_lock, renew_run_lock, save_report_run)
from intelligence_pipeline import analyze_all_properties
from reports import generate_reports
from scrapers.kern_code_cases import scrape_kern_code_cases
from scrapers.newspaper_auctions import scrape_newspaper_auctions
from scrapers.craigslist import scrape_craigslist
from scrapers.kern_tax import scrape_kern_tax
from scrapers.bakersfield_code import scrape_bakersfield_code
from scrapers.zillow_fsbo import scrape_zillow_fsbo
try:
    from scrapers.browser_source import scrape_browser_sources as _scrape_browser_sources
    scrape_browser_sources = _scrape_browser_sources
except Exception:
    scrape_browser_sources = None


def run_intelligence_reports(report_dir=REPORT_DIR) -> dict:
    """Analyze stored leads and generate complete operational reports."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    pipeline = analyze_all_properties(opportunity_threshold=OPPORTUNITY_THRESHOLD,
                                      watchlist_threshold=WATCHLIST_THRESHOLD)
    report = generate_reports(pipeline["analyses"], pipeline["new_events"], report_dir, run_id=run_id)
    report["pipeline"] = {key: value for key, value in pipeline.items()
                          if key not in {"analyses", "new_events"}}
    save_report_run(report, run_id=run_id)
    return report


def run_all() -> dict[str, dict]:
    init_db()
    if not acquire_run_lock():
        return {"system": {"found": 0, "new": 0, "errors": "another intelligence run is active",
                           "err": "another intelligence run is active"}}
    results: dict[str, dict] = {}
    source_summary: dict[str, dict] = {}
    total_found = 0
    total_new = 0
    sources = [
        ('kern_code_cases', scrape_kern_code_cases),
        ('newspaper_auctions', scrape_newspaper_auctions),
        ('craigslist', scrape_craigslist),
        ('zillow_fsbo', scrape_zillow_fsbo),
        ('kern_tax', scrape_kern_tax),
        ('bakersfield_code', scrape_bakersfield_code),
    ]
    if scrape_browser_sources is not None:
        sources.append(('browser_sources', scrape_browser_sources))
    try:
        for source, scrape in sources:
            if not renew_run_lock():
                raise RuntimeError('intelligence run lease was lost')
            try:
                found, new, errors = scrape()
            except Exception as exc:
                found, new, errors = 0, 0, f'{type(exc).__name__}: {exc}'
            created_at = datetime.now(timezone.utc).isoformat()
            result = dict(found=found, new=new, errors=errors, err=errors, created_at=created_at)
            source_summary[source] = result
            total_found += found
            total_new += new
            results[source] = result
            print(f'{source}: found={found}, new={new}, errors={errors or "none"}')
        conn = get_conn()
        try:
            with conn:
                for source, result in source_summary.items():
                    conn.execute(
                        'INSERT INTO scrape_log (source, source_type, found, new_leads, error, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                        (source,
                         'browser_sources' if source == 'browser_sources' else 'http',
                         result['found'],
                         result['new'],
                         result['errors'],
                         result['created_at']),
                    )
        finally:
            conn.close()
        try:
            if not renew_run_lock():
                raise RuntimeError('intelligence run lease was lost before analysis')
            intelligence = run_intelligence_reports()
            results['intelligence'] = dict(found=intelligence['pipeline']['processed'], new=intelligence['pipeline']['events_created'],
                                           errors='; '.join(item['error'] for item in intelligence['pipeline']['failures']),
                                           err='; '.join(item['error'] for item in intelligence['pipeline']['failures']),
                                           created_at=datetime.now(timezone.utc).isoformat(), reports=intelligence['counts'])
        except Exception as exc:
            results['intelligence'] = dict(found=0, new=0, errors=f'{type(exc).__name__}: {exc}',
                                           err=f'{type(exc).__name__}: {exc}',
                                           created_at=datetime.now(timezone.utc).isoformat())
        try:
            from database import save_last_run_summary
            save_last_run_summary(source_summary, total_found, total_new)
        except Exception:
            pass
        return results
    finally:
        release_run_lock()


def run_loop(interval_minutes: int = RUN_INTERVAL_MINUTES) -> None:
    while True:
        try:
            run_all()
        except Exception as exc:
            print(f'intelligence cycle failed: {type(exc).__name__}: {exc}')
        time.sleep(interval_minutes * 60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--once', action='store_true', help='Run once (default)')
    mode.add_argument('--loop', action='store_true', help='Run every hour')
    mode.add_argument('--reports-only', action='store_true', help='Analyze stored leads without collecting sources')
    parser.add_argument('--interval-minutes', type=int, default=RUN_INTERVAL_MINUTES,
                        help='Minutes between unattended cycles (default from RUN_INTERVAL_MINUTES)')
    args = parser.parse_args()
    if args.interval_minutes < 1:
        parser.error('--interval-minutes must be at least 1')
    if args.reports_only:
        init_db()
        if not acquire_run_lock():
            parser.error('another intelligence run is active')
        try:
            print(run_intelligence_reports())
        finally:
            release_run_lock()
    elif args.loop:
        run_loop(args.interval_minutes)
    else:
        run_all()
