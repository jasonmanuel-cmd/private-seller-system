"""
Zillow FSBO Scraper — FREE attempt using mobile search API
Zillow blocks heavily, so this tries multiple methods and falls back to manual URLs
"""
import requests
import json
import re
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import ZILLOW_FSBO_URLS, ZILLOW_HEADERS, HEADERS
from scoring import score_lead
from database import upsert_lead

def try_zillow_search_api():
    """
    Try to use Zillow's internal search API — may be blocked, but worth trying
    """
    found = 0
    new_leads = 0
    
    # Zillow search API endpoint pattern (changes often)
    # We try to get search results for Bakersfield FSBO
    search_states = [
        {"regionId": 20334, "regionType": 6, "city": "Bakersfield"},  # Bakersfield city
        {"regionId": 48987, "regionType": 6, "city": "Tehachapi"},
    ]
    
    for state in search_states:
        try:
            # Attempt to fetch search page and extract data from HTML
            url = f"https://www.zillow.com/homes/for_sale/{state['city']}-CA/fsbo/"
            print(f"Trying Zillow: {url}")
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"Zillow blocked or status {r.status_code} for {state['city']}")
                continue
            
            # Try to extract JSON data from page
            # Zillow embeds data in <script id="__NEXT_DATA__">
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'lxml')
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                try:
                    data = json.loads(next_data.string)
                    # Navigate to listings
                    # Structure changes, try to find cat1 searchResults
                    search_results = str(data)[:5000]  # debug
                    # For now, we count as found but need manual parsing
                    print(f"Found __NEXT_DATA__ for {state['city']}, length {len(next_data.string)}")
                except Exception as e:
                    print(f"Error parsing NEXT_DATA for {state['city']}: {e}")
            
            # Fallback: regex for addresses and prices in HTML
            # Look for pattern: "address": "...", "price": ...
            addresses = re.findall(r'"streetAddress":"([^"]+)"', r.text)
            prices = re.findall(r'"price":(\d+)', r.text)
            print(f"Found {len(addresses)} addresses, {len(prices)} prices in {state['city']} HTML")
            
            # Create leads from regex if found
            for i, addr in enumerate(addresses[:10]):
                price = int(prices[i]) if i < len(prices) else 0
                deal_id = f"zillow_fsbo_{addr}_{state['city']}"
                title = f"{addr}, {state['city']} — FSBO"
                score, reasons, motivation = score_lead(title, "FSBO Zillow", price, "fsbo")
                
                lead = {
                    "id": deal_id,
                    "address": addr,
                    "city": state['city'],
                    "price": price,
                    "price_text": f"${price}" if price else "",
                    "source": "zillow_fsbo",
                    "source_type": "fsbo",
                    "link": url,
                    "description": f"Zillow FSBO: {addr}, {state['city']} — Price ${price} | Found via HTML regex | SCORE: {reasons} | Verify on Zillow FSBO page",
                    "owner_name": "",
                    "owner_mailing": "",
                    "motivation": motivation,
                    "deal_score": score,
                    "equity_estimate": "",
                    "status": "new",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "raw_data": title
                }
                is_new = upsert_lead(lead)
                if is_new:
                    new_leads += 1
                    found += 1
                    print(f"[NEW] Zillow FSBO: {addr} ${price} {state['city']} Score {score}")
            
        except Exception as e:
            print(f"Error scraping Zillow {state['city']}: {e}")
            import traceback
            traceback.print_exc()
    
    return found, new_leads

def create_manual_zillow_leads():
    """
    Create manual instruction leads for Zillow FSBO — always valuable
    """
    new_leads = 0
    found = 0
    
    for url in ZILLOW_FSBO_URLS:
        city = "Bakersfield"
        if "Tehachapi" in url:
            city = "Tehachapi"
        elif "California-City" in url:
            city = "California City"
        elif "93308" in url:
            city = "Bakersfield NW 93308"
        
        found += 1
        deal_id = f"zillow_manual_{city}"
        
        lead = {
            "id": deal_id,
            "address": f"Zillow FSBO — {city} — Manual Check Daily",
            "city": city,
            "price": 0,
            "price_text": "FSBO — often under market",
            "source": "zillow_fsbo",
            "source_type": "fsbo",
            "link": url,
            "description": f"Daily manual check: Open {url}, filter Price Max $250k, sort Newest, look for keywords as-is, motivated, estate, owner financing. FSBO sellers often underprice and open to private sale, no MLS. Add good ones to this system manually via dashboard. | Private seller opportunity — they want private guy like Nathanael.",
            "owner_name": "",
            "owner_mailing": "",
            "motivation": "private seller / FSBO",
            "deal_score": 6,
            "equity_estimate": "",
            "status": "new",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "raw_data": url
        }
        is_new = upsert_lead(lead)
        if is_new:
            new_leads += 1
    
    return found, new_leads

def scrape_zillow_fsbo():
    print("=== Scraping Zillow FSBO ===")
    found1, new1 = try_zillow_search_api()
    found2, new2 = create_manual_zillow_leads()
    total_found = found1 + found2
    total_new = new1 + new2
    print(f"Zillow FSBO: Found {total_found}, New {total_new}")
    return total_found, total_new, ""

if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_zillow_fsbo()
