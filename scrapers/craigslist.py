"""
Craigslist scraper — FREE, no API, uses RSS
"""
import feedparser
import re
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import CRAIGSLIST_RSS
from scoring import score_lead, extract_price
from database import upsert_lead
import sqlite3

def scrape_craigslist():
    new_leads = 0
    found = 0
    errors = []
    
    for rss_url in CRAIGSLIST_RSS:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                found += 1
                title = entry.get('title', '')
                link = entry.get('link', '')
                desc = entry.get('description', '')[:2000]
                pub = entry.get('published', '')
                deal_id = f"craigslist_{entry.get('id', link)}"
                
                price = extract_price(title + " " + desc)
                
                # City detection
                city = "Bakersfield"
                low_title = title.lower()
                if "tehachapi" in low_title or "tehachapi" in rss_url.lower():
                    city = "Tehachapi"
                elif "california city" in low_title:
                    city = "California City"
                elif "stallion" in low_title:
                    city = "Stallion Springs"
                
                # Address extraction attempt
                address = title.split("$")[0].strip()[:100] if "$" in title else title[:100]
                
                score, reasons, motivation = score_lead(title, desc, price, "fsbo")
                
                lead = {
                    "id": deal_id,
                    "address": address,
                    "city": city,
                    "price": price,
                    "price_text": f"${price}" if price else "",
                    "source": "craigslist",
                    "source_type": "fsbo",
                    "link": link,
                    "description": f"{title} | {desc} | SCORE REASONS: {reasons}",
                    "owner_name": "",
                    "owner_mailing": "",
                    "motivation": motivation,
                    "deal_score": score,
                    "equity_estimate": "",
                    "status": "new",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "raw_data": str(entry)[:2000]
                }
                
                is_new = upsert_lead(lead)
                if is_new:
                    new_leads += 1
                    print(f"[NEW] Score {score}/10 | ${price} | {city} | {motivation} | {title[:60]}")
                    
        except Exception as e:
            errors.append(f"{rss_url}: {e}")
            print(f"Error {rss_url}: {e}")
    
    return found, new_leads, "; ".join(errors)

if __name__ == "__main__":
    from database import init_db
    init_db()
    found, new_leads, err = scrape_craigslist()
    print(f"\nCraigslist: Found {found}, New {new_leads}, Errors: {err}")
