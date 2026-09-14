# Private Seller System — Harbison Standard
**No MLS, $0 — Find Private Sellers Who Want to Sell Quietly**

This repo contains:

## 1. Lead Scraper System (`/` root)
Auto-scrapes free sources to find private leads no one knows:
- Craigslist Bakersfield RSS (FSBO)
- Zillow FSBO (manual check URLs, auto-scoring)
- Kern County Tax-Defaulted (300+ parcels $5k-20k)
- Pre-Foreclosure NOD, Probate, Code Violations, Driving for Dollars
- Facebook Marketplace + Groups (manual add via dashboard)
- Wholesaler buyers lists

**Live Dashboard:** Flask app at `app.py` — scores leads 1-10, filter by Hot 7+, city, source, add manual leads, export CSV.

### Quick Start
```bash
pip install -r requirements.txt
python run.py --once
python app.py
# Open http://localhost:5000
```

### Deploy to Render.com (Free Permanent URL) — 2 min
1. Fork this repo on GitHub
2. Go to https://dashboard.render.com → New → Web Service → Connect this repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python app.py`
5. Instance Type: Free
6. Deploy — you get permanent URL like https://private-seller-system.onrender.com
7. For hourly scraper: Create second service → Background Worker → Start Command: `python run.py --loop`

Or one-click deploy with `render.yaml` included.

## 2. Private Seller System (`/private-seller-system/`)
- Landing page `/private-sale` (private-sale.html)
- Direct mail letters (5 handwritten letters that get private sellers to call)
- Facebook Ads ($5/day)
- Phone scripts
- Target lists (how to build absentee, senior, NOD, tax, probate lists for $0)
- Full README with Private Sale Program playbook

## 3. Dev Playbook
- `DEV_PLAYBOOK_HARBISON.md` — Fix Google + AI visibility for harbisonstandard.com
- `llms.txt` — Upload to /public/llms.txt for ChatGPT/Perplexity
- `harbison-seo-ai-plan.md` — 90-day SEO plan

## Cost
$0 to start. Optional $5/day FB ads, $0.70/letter handwritten mail.

## Owner
Nathanael Harbison, REALTOR® DRE #02059393, Harbison Standard, Kern County
Phone: (661) 472-7499

## License
Private — for Harbison Standard use
