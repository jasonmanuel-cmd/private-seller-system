"""
Kern County Tax-Defaulted Scraper — FREE public record
Scrapes treasurer site for tax sale info and delinquent parcel PDFs
"""
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import KERN_TAX_URLS, KERN_TAX_LIVE_AUCTION, HEADERS
from scoring import score_lead
from database import upsert_lead

def scrape_kern_tax():
    found = 0
    new_leads = 0
    errors = ""
    tax_sale_manual_created = False

    for url in KERN_TAX_URLS:
        try:
            print(f"Fetching {url}...")
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                errors = f"Status {r.status_code} for {url}"
                print(f"Failed: {errors}")
                continue

            soup = BeautifulSoup(r.text, 'lxml')

            # Extract PDF links from the page
            pdf_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text().strip().lower()
                if href.lower().endswith('.pdf'):
                    if href.startswith('/'):
                        href = "https://www.kcttc.co.kern.ca.us" + href
                    elif not href.startswith('http'):
                        base = url.rsplit('/', 1)[0] if '/' in url else url
                        href = base + '/' + href
                    pdf_links.append((href, a.get_text().strip()[:80]))

            pdf_links = list(dict.fromkeys(pdf_links))
            print(f"Found {len(pdf_links)} PDF links on {url}")

            for link, text in pdf_links[:10]:
                found += 1
                deal_id = f"kern_tax_pdf_{link[-50:].replace('/','_').replace('.','_')}"
                title = f"Kern Tax PDF: {text[:60]}"

                score, reasons, motivation = score_lead(title, text, 0, "tax_defaulted")
                score = max(score, 8)

                lead = {
                    "id": deal_id,
                    "address": f"Kern Tax-Defaulted — {text[:50]}",
                    "city": "Kern County",
                    "price": 0,
                    "price_text": "See PDF for parcel details and minimum bids $5k-50k",
                    "source": "kern_tax",
                    "source_type": "tax_defaulted",
                    "link": link,
                    "description": f"{title} | Download PDF, extract APN/parcels, look up owner free via Assessor (assessor.kerncounty.com), skip trace free via TruePeopleSearch.com, contact owner before auction. Owner can redeem until day before auction. SCORE: {reasons}",
                    "owner_name": "",
                    "owner_mailing": "",
                    "motivation": "tax delinquent — unpaid taxes 5+ years",
                    "deal_score": score,
                    "equity_estimate": "High — owner hasn't paid taxes 5 years, motivated to sell",
                    "status": "new",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "raw_data": link
                }

                is_new = upsert_lead(lead)
                if is_new:
                    new_leads += 1
                    print(f"[NEW] Kern Tax PDF: {text[:60]} | {link}")

            # Manual instruction lead — only once
            if "showGeneralTaxSaleInfo" in url and not tax_sale_manual_created:
                tax_sale_manual_created = True
                lead = {
                    "id": "kern_tax_manual_instruction",
                    "address": "Kern County Tax-Defaulted Auction — Manual Check Weekly",
                    "city": "Bakersfield / California City",
                    "price": 0,
                    "price_text": "$5k-50k min bids (parcel-dependent)",
                    "source": "kern_tax",
                    "source_type": "tax_defaulted",
                    "link": KERN_TAX_URLS[0],
                    "description": f"Weekly check: Visit {KERN_TAX_URLS[0]} for current tax sale info and delinquent parcel list. Download latest PDF, extract APN, look up owner free via Assessor (assessor.kerncounty.com), skip trace free via TruePeopleSearch.com. Call owner: 'I saw your property going to tax auction — I buy privately as-is and can pay your back taxes + cash before auction.' Next sale date: check the page. Live auction portal: {KERN_TAX_LIVE_AUCTION}",
                    "owner_name": "",
                    "owner_mailing": "",
                    "motivation": "tax delinquent — 5+ years unpaid, facing auction",
                    "deal_score": 9,
                    "equity_estimate": "High — owner hasn't paid taxes 5 years, motivated to sell before losing property",
                    "status": "new",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "raw_data": KERN_TAX_URLS[0]
                }
                upsert_lead(lead)
                print("[NEW] Kern Tax manual instruction lead created")

        except Exception as e:
            errors = f"{errors}; {url}: {e}" if errors else f"{url}: {e}"
            print(f"Error scraping {url}: {e}")
            import traceback
            traceback.print_exc()

    # Live auction portal lead
    if KERN_TAX_LIVE_AUCTION:
        found += 1
        deal_id = "kern_tax_live_auction"
        title = "Kern County Tax Sale — Live Auction Portal"

        score, reasons, motivation = score_lead(title, "Tax sale auction", 0, "tax_defaulted")
        score = max(score, 9)

        lead = {
            "id": deal_id,
            "address": "Kern County Tax Sale — Live Auction (Govease)",
            "city": "Kern County",
            "price": 0,
            "price_text": "Bidding opens — minimum bids vary by parcel",
            "source": "kern_tax",
            "source_type": "tax_defaulted",
            "link": KERN_TAX_LIVE_AUCTION,
            "description": f"Live auction portal for Kern County tax sales: {KERN_TAX_LIVE_AUCTION}. Register to bid on tax-defaulted properties. Download parcel list from kcttc.co.kern.ca.us, look up owners free via Assessor, skip trace free via TruePeopleSearch.com, contact owners before auction to offer private buyout. SCORE: {reasons}",
            "owner_name": "",
            "owner_mailing": "",
            "motivation": "tax delinquent — auction approaching",
            "deal_score": score,
            "equity_estimate": "High — auction properties often sell below market",
            "status": "new",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "raw_data": KERN_TAX_LIVE_AUCTION
        }

        is_new = upsert_lead(lead)
        if is_new:
            new_leads += 1
            print(f"[NEW] Kern Tax Live Auction lead created")

    return found, new_leads, errors

if __name__ == "__main__":
    from database import init_db
    init_db()
    found, new, err = scrape_kern_tax()
    print(f"Kern Tax: Found {found}, New {new}, Err {err}")
