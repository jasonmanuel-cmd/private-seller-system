"""
Config for Kern County No-MLS Lead Scraper
"""
import os

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "leads.db")

# Scraping targets
CRAIGSLIST_RSS = [
    "https://bakersfield.craigslist.org/search/reo?format=rss&query=Tehachapi|Bakersfield|California%20City&srchType=T",  # by owner
    "https://bakersfield.craigslist.org/search/rea?format=rss&query=land|acre|owner%20financing&srchType=T",
    "https://bakersfield.craigslist.org/search/rea?format=rss&query=Tehachapi&srchType=T",
    "https://bakersfield.craigslist.org/search/rea?format=rss&query=Bakersfield&bundleDuplicates=1&hasPic=1&srchType=T",
]

# Zillow FSBO search pages (free to browse, scraping via mobile API attempt)
ZILLOW_FSBO_URLS = [
    "https://www.zillow.com/homes/for_sale/Bakersfield-CA/fsbo/",
    "https://www.zillow.com/homes/for_sale/Tehachapi-CA/fsbo/",
    "https://www.zillow.com/homes/for_sale/California-City-CA/fsbo/",
    "https://www.zillow.com/homes/for_sale/93308_fsbo/",
]

# Kern County public sources
KERN_TAX_URL = "https://www.kcttc.co.kern.ca.us/tax-defaulted-property-sales/"
KERN_RECORDER_URL = "https://recorder.kerncounty.com/"
BAKERSFIELD_DATA_URL = "https://data.bakersfieldcity.us/"

# Scoring weights
SCORE_KEYWORDS = {
    "as-is": 3, "as is": 3, "motivated": 3, "must sell": 3, "estate": 3, "probate": 4,
    "trust sale": 3, "tlc": 2, "handyman": 2, "fixer": 2, "investor": 2, "needs work": 2,
    "vacant": 3, "owner financing": 3, "owner will carry": 3, "private sale": 4,
    "no mls": 4, "off market": 3, "divorce": 3, "relocating": 2, "behind on payments": 4
}

# Headers to avoid blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

ZILLOW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.zillow.com/",
}
