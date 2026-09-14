"""
Kern County Tax-Defaulted Scraper — FREE public record
Scrapes treasurer site for PDF links
"""
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import KERN_TAX_URL, HEADERS
from scoring import score_lead
from database import upsert_lead

def scrape_kern_tax():
    found = 0
    new_leads = 0
    errors = ""
    
    try:
        print(f"Fetching {KERN_TAX_URL}...")
        r = requests.get(KERN_TAX_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            errors = f"Status {r.status_code}"
            print(f"Failed: {errors}")
            return found, new_leads, errors
        
        soup = BeautifulSoup(r.text, 'lxml')
        
        # Find all PDF links and tax-defaulted related links
        pdf_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text().lower()
            if ('tax-defaulted' in href.lower() or 'tax_defaulted' in href.lower() or href.lower().endswith('.pdf')) and ('tax' in text or 'default' in text or 'sale' in text or 'list' in text or href.lower().endswith('.pdf')):
                # Make absolute
                if href.startswith('/'):
                    href = "https://www.kcttc.co.kern.ca.us" + href
                elif not href.startswith('http'):
                    href = KERN_TAX_URL + href
                pdf_links.append((href, a.get_text().strip()))
        
        # Deduplicate
        pdf_links = list(dict.fromkeys(pdf_links))[:10]
        
        print(f"Found {len(pdf_links)} tax-defaulted PDFs/links")
        
        for link, text in pdf_links:
            found += 1
            # Create a lead for each PDF as a source to check manually
            # In full version, we'd download PDF and parse parcels
            deal_id = f"kern_tax_{link[-50:]}"
            title = f"Tax-Defaulted List: {text[:80]}"
            
            score, reasons, motivation = score_lead(title, text, 0, "tax_defaulted")
            # Tax defaulted is always high score
            score = max(score, 8)
            
            lead = {
                "id": deal_id,
                "address": f"Tax-Defaulted List — {text[:50]}",
                "city": "Kern County",
                "price": 0,
                "price_text": "See PDF for min bids $5k-50k",
                "source": "kern_tax",
                "source_type": "tax_defaulted",
                "link": link,
                "description": f"{title} | {text} | This is a PDF of tax-defaulted properties going to auction. Download, get APN, look up owner via Assessor (free), contact before auction. Owner can redeem until day before auction. SCORE: {reasons}",
                "owner_name": "",
                "owner_mailing": "",
                "motivation": "tax delinquent — 5+ years unpaid",
                "deal_score": score,
                "equity_estimate": "High — owner hasn't paid taxes 5 years, wants to sell",
                "status": "new",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "raw_data": link
            }
            
            is_new = upsert_lead(lead)
            if is_new:
                new_leads += 1
                print(f"[NEW] Tax List: {text[:60]} | {link}")
        
        # Also add manual instruction lead
        lead = {
            "id": "kern_tax_manual_instruction",
            "address": "Kern County Tax-Defaulted Auction — Manual Check Required Weekly",
            "city": "California City / Bakersfield",
            "price": 0,
            "price_text": "$5k-20k min bids",
            "source": "kern_tax",
            "source_type": "tax_defaulted",
            "link": KERN_TAX_URL,
            "description": "Weekly check: Download latest Tax-Defaulted PDF, extract APN, look up owner free via Assessor (assessor.kerncounty.com), skip trace free via TruePeopleSearch.com, call owner: 'I saw your property going to tax auction, I buy privately as-is, can pay taxes + cash to you before auction.'",
            "owner_name": "",
            "owner_mailing": "",
            "motivation": "tax delinquent",
            "deal_score": 9,
            "equity_estimate": "",
            "status": "new",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "raw_data": KERN_TAX_URL
        }
        upsert_lead(lead)
        
    except Exception as e:
        errors = str(e)
        print(f"Error scraping tax: {e}")
        import traceback
        traceback.print_exc()
    
    return found, new_leads, errors

if __name__ == "__main__":
    from database import init_db
    init_db()
    found, new, err = scrape_kern_tax()
    print(f"Kern Tax: Found {found}, New {new}, Err {err}")
