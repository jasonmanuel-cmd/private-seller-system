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

## How to Find Leads — Daily Routine (30 min morning)
The system scrapes automatically, but you still close the loop manually. Here's your checklist:

**Every morning (30 min)**
1. Open dashboard at `http://localhost:5000` (or Render URL when deployed)
2. Click **Run Scraper Now** — Craigslist RSS, Kern tax, code violations run automatically
3. Check **Hot 7+** filter — these are your best leads (as-is, private sale, no MLS, probate, motivated, tax-defaulted)
4. For each Hot lead: click **Skip Trace Free** (TruePeopleSearch) to get phone number
5. Call or text — use phone scripts in `private-seller-system/`

**Daily manual checks (10 min)**
- Facebook Marketplace — Bakersfield/Tehachapi "owner" and "land" searches → Add via **Add Manual Lead** form
- Facebook Groups — 5 local groups (Bakersfield Housing, Tehachapi Community, Kern County Real Estate, etc.) → Add leads via dashboard form
- Craigslist — manual check of "by owner" and "land" if scraper returns 0 (Craigslist blocks automated RSS sometimes)

**Weekly (1 hour)**
- Kern County tax-defaulted auctions — check `https://www.kcttc.co.kern.ca.us/` for new sale lists
- Probate leads — check county recorder/probate court
- NOD (Notices of Default) — pre-foreclosure leads from county records
- Driving for dollars — drive neighborhoods, note vacant/boarded homes, add via dashboard

**How the Private Sale Program works**
Homeowners who want privacy call Nathanael directly instead of listing on MLS. Private Sale Program handles: divorce, financial pressure, inherited property, bad tenants, houses needing work. One private walkthrough, no open houses, private offers from vetted 20+ buyer network. Close in 7-14 days cash. Legal in California using C.A.R. Form SELM (Seller Instruction to Exclude Listing from MLS).

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

## Run Locally
```bash
pip install -r requirements.txt
python run.py --once
python app.py
# Open http://localhost:5000
```

## Deploy to Render.com (Free Permanent URL)
One-click deploy with `render.yaml` Blueprint — creates web dashboard + hourly scraper worker:
1. Go to https://dashboard.render.com → New → Blueprint
2. Connect this repo (`jasonmanuel-cmd/private-seller-system`)
3. Apply `render.yaml` — creates `private-seller-dashboard` (web) + `private-seller-scraper` (worker)
4. Dashboard at `https://private-seller-dashboard.onrender.com` (or similar)

Or manually:
1. Fork this repo on GitHub
2. Render → New → Web Service → Connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `python app.py`
5. Free tier, deploy — permanent URL like `https://private-seller-system.onrender.com`
6. Add hourly scraper: New → Background Worker → Start: `python run.py --loop`

**Note:** Render free tier filesystem is ephemeral — `data/leads.db` resets on each deploy. Add a Render Disk (1GB free) mounted at `/app/data` or export CSV weekly to Google Sheets.

## Cost
$0 to start. Optional $5/day FB ads, $0.70/letter handwritten mail.

## Owner
Nathanael Harbison, REALTOR® DRE #02059393, Harbison Standard, Kern County
Phone: (661) 472-7499

## License
Private — for Harbison Standard use
