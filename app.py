"""
Harbison Standard Branded Dashboard — Private Lead Scraper
Matches main site: navy #031c2b, gold #edc66f, fonts Libre Caslon Display + Open Sans
Run: python app.py
Render: Uses PORT env var
"""
from flask import Flask, render_template_string, request, jsonify, redirect
import sys, os
sys.path.append(os.path.dirname(__file__))
from database import get_leads, get_stats, get_conn, init_db
from datetime import datetime

app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private Lead Dashboard — Harbison Standard</title>
<meta name="description" content="Kern County private leads — off-market deals not on MLS. Harbison Standard Private Lead System">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Display&family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
@import url('https://www.harbisonstandard.com/assets/fonts.css');
:root{--navy:#031c2b;--gold:#edc66f;--muted-gold:#b78b43;--light:#f6f5ef;--border:#e3ddcf}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Open Sans',sans-serif;background:var(--light);color:#08142e;line-height:1.5;-webkit-font-smoothing:antialiased}
h1,h2,h3,.motto{font-family:'Libre Caslon Display',Georgia,serif;font-weight:400}
a{color:inherit;text-decoration:none}
header{height:92px;background:var(--navy);display:flex;align-items:center;padding:0 4%;gap:5%;color:white;position:sticky;top:0;z-index:10}
.brand{width:250px;flex-shrink:0}
.brand img{display:block;width:100%}
nav{display:flex;align-items:center;gap:27px;margin-left:auto}
nav a{font-size:10px;white-space:nowrap;text-transform:uppercase;letter-spacing:.4px;font-weight:600;color:white;padding:14px 0;position:relative}
nav a.active{color:var(--gold)}
nav a.active:after{content:'';position:absolute;bottom:3px;left:0;right:0;border-bottom:2px solid var(--gold)}
.gold{display:inline-flex;align-items:center;justify-content:center;gap:10px;background:var(--gold);color:#07131c;min-height:42px;min-width:176px;padding:11px 22px;border-radius:2px;font-weight:700;font-size:12px;letter-spacing:1px;text-transform:uppercase;box-shadow:inset 0 0 18px #ffeba65c;border:0;cursor:pointer}
.gold:hover{filter:brightness(1.05)}
.text-link{display:inline-flex;align-items:center;gap:8px;background:none;padding:0;color:var(--navy);text-transform:uppercase;font-size:11px;font-weight:700;letter-spacing:1px;border:0;cursor:pointer}
.text-link span{border-bottom:1px solid #d9d6cb;padding-bottom:2px}
.container{max-width:1180px;margin:0 auto;padding:0 4%}
.page-heading{padding:38px 0 18px}
.eyebrow{text-transform:uppercase;font-size:11px;font-weight:700;letter-spacing:1.8px;color:#986f31;margin-bottom:8px}
.page-heading h1{font-size:54px;line-height:.95;letter-spacing:-1.2px;color:var(--navy)}
.page-heading h1 em{font-family:'Libre Caslon Text',Georgia,serif;color:var(--muted-gold);font-style:italic;font-size:.88em}
.page-lede{font-size:16px;line-height:1.5;max-width:720px;margin-top:14px;color:#4b585d}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}
.stat{background:var(--navy);color:#fff;border-radius:4px;padding:20px 22px;border-bottom:3px solid var(--gold)}
.stat span{font-family:'Libre Caslon Display',Georgia,serif;font-size:32px;color:var(--gold);display:block;line-height:1}
.stat p{margin:6px 0 0;font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:#cfd8dd}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 22px}
.filters a{padding:8px 14px;background:#fff;border:1px solid var(--border);border-radius:3px;font-size:11px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:#596365}
.filters a.active{background:var(--navy);color:var(--gold);border-color:var(--navy)}
.card{background:#fff;border:1px solid var(--border);border-radius:4px;padding:20px 22px;margin-bottom:14px;transition:.2s;position:relative}
.card:hover{border-color:var(--muted-gold);box-shadow:0 10px 30px -20px rgba(3,28,43,.3)}
.card.hot{border-left:4px solid #c53030}
.card.warm{border-left:4px solid var(--gold)}
.card.cold{border-left:4px solid #cbd5e0}
.price{font-family:'Libre Caslon Display',Georgia,serif;font-size:26px;color:var(--navy);line-height:1}
.price em{color:var(--muted-gold);font-style:normal;font-size:20px}
.meta{font-size:11px;color:#7c8590;letter-spacing:.3px;margin-top:6px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.badge{display:inline-block;padding:3px 8px;border-radius:3px;font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase}
.badge-hot{background:#f3e4bf;color:#7a5c14;border:1px solid #d6b268}
.badge-warm{background:#fbfaf5;color:#5a4f3a;border:1px solid var(--border)}
.badge-source{background:var(--navy);color:var(--gold);border:1px solid var(--navy)}
.title{font-family:Georgia,serif;font-size:18px;font-weight:700;color:var(--navy);margin:8px 0 4px}
.desc{font-size:13px;line-height:1.6;color:#4b585d;margin-top:8px}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:2px;font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;border:1px solid var(--border);background:#fff;color:#596365;cursor:pointer}
.btn-gold{background:var(--gold);color:#07131c;border-color:var(--gold);box-shadow:inset 0 0 12px #ffeba65c}
.btn-dark{background:var(--navy);color:var(--gold);border-color:var(--navy)}
.form-wrap{background:#fff;border:1px solid var(--border);border-radius:6px;padding:28px;margin-top:30px}
.form-wrap h3{font-size:24px;color:var(--navy);margin-bottom:6px}
.form-wrap p.small{font-size:12px;color:#7c8590;line-height:1.5;margin-bottom:14px}
.input{width:100%;padding:10px 12px;border-radius:3px;border:1px solid #c9c0ab;font-size:13px;margin-bottom:10px;font-family:inherit;background:#fff;color:#08142e}
.input:focus{outline:2px solid var(--gold);outline-offset:2px;border-color:transparent}
label{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#7c8590;margin-bottom:4px;display:block}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.closing{margin-top:40px;background:var(--navy) url('https://www.harbisonstandard.com/assets/mountains.webp') center/cover no-repeat;padding:45px 7.8% 28px 6.1%;display:flex;justify-content:space-between;align-items:center;color:white;border-radius:4px}
.footer-logo{width:240px;display:block}
.closing .motto{font-size:28px;line-height:1.02;font-style:italic}
.closing .motto em{font-size:1em}
.site-footer{margin-top:18px;background:var(--navy);color:white;display:flex;align-items:center;justify-content:space-between;padding:18px 3.8%;border-top:1px solid #9f8038;border-radius:4px}
.site-footer p{text-transform:uppercase;letter-spacing:1px;font-size:8px}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.page-heading h1{font-size:42px}header{height:80px}.brand{width:200px}nav{display:none}.row{grid-template-columns:1fr}.closing{flex-direction:column;align-items:flex-start;gap:20px}}
</style>
</head>
<body>
<header>
<a class="brand" href="https://www.harbisonstandard.com/" aria-label="Harbison Standard home"><img src="https://www.harbisonstandard.com/assets/logo.webp" alt="Harbison Standard — Real Estate and Investing"></a>
<nav aria-label="Main navigation">
<a href="https://www.harbisonstandard.com/">Home</a>
<a href="https://www.harbisonstandard.com/properties">Properties</a>
<a href="https://www.harbisonstandard.com/private-sale" class="active">Private Sale</a>
<a href="https://www.harbisonstandard.com/off-market-deals" class="active">Off-Market Deals</a>
<a href="https://www.harbisonstandard.com/contact">Contact</a>
</nav>
<a class="gold" href="https://www.harbisonstandard.com/contact" style="margin-left:auto">Let's talk</a>
</header>

<div class="container">
<section class="page-heading">
<p class="eyebrow">Harbison Standard — Private Lead System — {{stats.total}} leads</p>
<h1>Private leads <em>no one knows how to find.</em></h1>
<p class="page-lede">Off-market deals in Kern County — tax-defaulted, pre-foreclosure, probate, FSBO, vacant, Facebook, wholesaler — scored 1-10 for deal quality. Same system Nathanael uses to find private sellers who want to sell quietly without MLS.</p>
<div style="display:flex;gap:12px;margin-top:18px;flex-wrap:wrap">
<a class="gold" href="/run">▶ Run Scraper Now</a>
<a class="text-link" href="/export"><span>⬇ Export CSV</span></a>
<a class="text-link" href="https://www.harbisonstandard.com/private-sale"><span>Private Sale Program →</span></a>
</div>
</section>

<div class="stats">
<div class="stat"><span>{{stats.total}}</span><p>Total Leads</p></div>
<div class="stat"><span>{{stats.hot}}</span><p>Hot 7+ Score</p></div>
<div class="stat"><span>{{stats.warm}}</span><p>Warm 5+ Score</p></div>
<div class="stat"><span>{{stats.by_source.get('craigslist',0) + stats.by_source.get('facebook',0)}}</span><p>FSBO + Private</p></div>
</div>

<div class="filters">
<a href="/?min_score=0" class="{{'active' if min_score==0 else ''}}">All ({{stats.total}})</a>
<a href="/?min_score=7" class="{{'active' if min_score==7 else ''}}">🔥 Hot 7+ ({{stats.hot}})</a>
<a href="/?min_score=5" class="{{'active' if min_score==5 else ''}}">Warm 5+ ({{stats.warm}})</a>
<a href="/?city=Tehachapi" class="{{'active' if city_filter=='Tehachapi' else ''}}">Tehachapi</a>
<a href="/?city=Bakersfield" class="{{'active' if city_filter=='Bakersfield' else ''}}">Bakersfield</a>
<a href="/?city=California%20City" class="{{'active' if city_filter=='California City' else ''}}">California City</a>
<a href="/?source=craigslist" class="{{'active' if source_filter=='craigslist' else ''}}">Craigslist</a>
<a href="/?source=kern_tax" class="{{'active' if source_filter=='kern_tax' else ''}}">Tax-Defaulted</a>
<a href="/?source=kern_recorder" class="{{'active' if source_filter=='kern_recorder' else ''}}">Pre-Foreclosure</a>
</div>

{% for lead in leads %}
<article class="card {{'hot' if lead['deal_score']>=7 else 'warm' if lead['deal_score']>=5 else 'cold'}}">
<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">
<div>
<div class="price">{{lead['price_text'] or 'Private Price'}} <em>| Score {{lead['deal_score']}}/10</em> <span class="badge {{'badge-hot' if lead['deal_score']>=7 else 'badge-warm'}}" style="margin-left:8px">{{'HOT' if lead['deal_score']>=7 else 'WARM' if lead['deal_score']>=5 else 'COLD'}}</span></div>
<div class="title">{{lead['address']}} — {{lead['city']}}</div>
<div class="meta"><span class="badge badge-source">{{lead['source']}}</span><span>{{lead['motivation']}}</span><span>{{lead['created_at'][:16]}}</span><span>Status: {{lead['status']}}</span><span>Type: {{lead['source_type']}}</span></div>
</div>
</div>
<div class="desc">{{lead['description'][:600]}}</div>
<div class="actions">
<a class="btn btn-gold" href="{{lead['link']}}" target="_blank">View Original →</a>
<a class="btn" href="https://www.truepeoplesearch.com/results?name={{lead['address'][:20]}}" target="_blank">Skip Trace Free</a>
<a class="btn" href="https://assessor.kerncounty.com/parcel-search/" target="_blank">Assessor Lookup</a>
<a class="btn btn-dark" href="#" onclick="markContacted('{{lead['id']}}');return false;">Mark Contacted</a>
</div>
</article>
{% endfor %}

{% if not leads %}
<article class="card"><p style="font-size:14px">No leads match filter. Click "Run Scraper Now" or check filters. Add manual leads from Facebook Marketplace below.</p></article>
{% endif %}

<div class="form-wrap">
<h3>Add manual private lead</h3>
<p class="small">Found a lead on Facebook Marketplace, driving for dollars, wholesaler email, or referral? Add it here — it will be scored automatically 1-10 using same system (private sale, as-is, estate, tax-defaulted keywords).</p>
<form method="POST" action="/add">
<div class="row"><div><label>Address *</label><input class="input" name="address" required placeholder="123 Main St, Bakersfield"></div><div><label>City *</label><input class="input" name="city" required placeholder="Bakersfield"></div></div>
<div class="row"><div><label>Price</label><input class="input" name="price" type="number" placeholder="150000"></div><div><label>Source *</label><select class="input" name="source"><option value="facebook">Facebook Marketplace/Group</option><option value="driving">Driving for Dollars</option><option value="referral">Referral ($500)</option><option value="wholesaler">Wholesaler</option><option value="zillow_fsbo">Zillow FSBO</option><option value="craigslist">Craigslist</option><option value="other">Other</option></select></div></div>
<label>Link (Facebook post, Zillow link, etc)</label><input class="input" name="link" placeholder="https://...">
<label>Description / Why private? *</label><textarea class="input" name="description" rows="3" required placeholder="e.g., Divorce, inherited, as-is, needs work, owner in LA, wants private sale, no MLS, owner financing..."></textarea>
<button type="submit" class="gold" style="width:100%;margin-top:8px">Add Lead & Score →</button>
</form>

<div style="margin-top:14px;padding:12px 14px;background:#fff;border:1px solid var(--border);border-left:4px solid var(--gold);border-radius:4px">
<p style="font-size:12px;color:#4b585d;line-height:1.6;margin:0"><strong>Zillow note:</strong> Zillow blocks automated scraping (403). The Zillow FSBO leads above are daily manual-check reminders — open the link, filter Price Max $250k, sort Newest, look for as-is / motivated / estate / owner financing. Add good ones via the form below. Zillow FSBO sellers often underprice and want a private sale — exactly what Nathanael does.</p>
</div>

<div style="margin-top:28px;padding:24px;background:#fff;border:1px solid var(--border);border-radius:6px">
<h3 style="font-size:22px;color:var(--navy);margin-bottom:8px">How to find leads this system finds</h3>
<p style="font-size:13px;color:#4b585d;line-height:1.6">This dashboard aggregates ALL free sources no MLS. Here's how to work it daily (30 min):</p>
<ol style="margin:16px 0 0 18px;font-size:13px;line-height:1.7;color:#4b585d">
<li><strong>Morning 6am:</strong> Click "Run Scraper Now" — scrapes Craigslist RSS (by owner), Zillow FSBO, tax-defaulted PDFs, code violations</li>
<li><strong>Score 7+ = HOT:</strong> Call immediately via TruePeopleSearch.com free phone — use private sale script from private-seller-system/scripts.md</li>
<li><strong>Facebook 10 min:</strong> Marketplace search "Tehachapi land", "Bakersfield house for sale by owner" + 5 FB Groups → Add via form below → auto-scored</li>
<li><strong>Weekly county check:</strong> Kern Tax-Defaulted (kcttc.co.kern.ca.us), Recorder NOD (recorder.kerncounty.com), Court Probate (kern.courts.ca.gov) → Add manually</li>
<li><strong>Driving 1hr/week:</strong> Golden Hills, Bear Valley, Oildale — overgrown, boarded, tarp roof → Add via form → Assessor lookup free</li>
<li><strong>Wholesalers:</strong> Join 10 Bakersfield wholesaler buyers lists (free) — they email you 70% ARV deals → Add via form</li>
</ol>
<p style="margin-top:14px;font-size:12px;color:#7c8590">All leads saved in data/leads.db (SQLite). Export CSV anytime. On Render free tier, DB resets on deploy — export CSV weekly to Google Sheets as backup.</p>
</div>

<div class="closing"><a href="https://www.harbisonstandard.com/" aria-label="Harbison Standard home"><img class="footer-logo" src="https://www.harbisonstandard.com/assets/logo.webp" alt="Harbison Standard"></a><div><p class="motto">It's not what you do,<br><em>it's how you do it.</em></p><a class="gold" href="https://www.harbisonstandard.com/contact">Let's talk</a></div></div>
<div class="site-footer"><div><p>Bakersfield · Tehachapi · Kern County</p><p>Nathanael Harbison · REALTOR® · Harbison Standard · DRE #02059393</p><p>Private Lead System — No MLS, No Zillow, Private Sellers Only</p></div><div style="display:flex;gap:12px;font-size:10px"><a href="https://www.harbisonstandard.com/private-sale">Private Sale</a><a href="https://www.harbisonstandard.com/off-market-deals">Off-Market Deals</a></div></div>

</div>
<script>
function markContacted(id){
  fetch('/mark_contacted/'+id, {method:'POST'}).then(()=>location.reload());
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    min_score = int(request.args.get("min_score", 0))
    city_filter = request.args.get("city", "")
    source_filter = request.args.get("source", "")
    
    init_db()
    stats = get_stats()
    
    from database import get_conn
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM leads WHERE deal_score >= ?"
    params = [min_score]
    if city_filter:
        query += " AND city LIKE ?"
        params.append(f"%{city_filter}%")
    if source_filter:
        query += " AND source LIKE ?"
        params.append(f"%{source_filter}%")
    query += " ORDER BY deal_score DESC, created_at DESC LIMIT 100"
    c.execute(query, params)
    leads = c.fetchall()
    conn.close()
    
    return render_template_string(DASHBOARD_HTML, leads=leads, stats=stats, min_score=min_score, city_filter=city_filter, source_filter=source_filter)

@app.route("/run")
def run_scraper():
    import subprocess
    subprocess.Popen(["python", "run.py", "--once"], cwd=os.path.dirname(__file__))
    return redirect("/?min_score=5")

@app.route("/add", methods=["POST"])
def add_manual():
    from scoring import score_lead
    from database import upsert_lead
    address = request.form.get("address", "")
    city = request.form.get("city", "")
    price = int(request.form.get("price") or 0)
    source = request.form.get("source", "manual")
    link = request.form.get("link", "")
    description = request.form.get("description", "")
    
    score, reasons, motivation = score_lead(address, description, price, source)
    
    lead = {
        "id": f"manual_{address}_{datetime.now().isoformat()}",
        "address": address,
        "city": city,
        "price": price,
        "price_text": f"${price}" if price else "",
        "source": source,
        "source_type": "manual",
        "link": link,
        "description": f"{description} | SCORE REASONS: {reasons}",
        "owner_name": "",
        "owner_mailing": "",
        "motivation": motivation,
        "deal_score": score,
        "equity_estimate": "",
        "status": "new",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "raw_data": description
    }
    upsert_lead(lead)
    return redirect(f"/?min_score=0")

@app.route("/mark_contacted/<lead_id>", methods=["POST"])
def mark_contacted(lead_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE leads SET status='contacted', updated_at=? WHERE id=?", (datetime.now().isoformat(), lead_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/export")
def export_csv():
    from database import get_conn
    import csv
    from io import StringIO
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY deal_score DESC")
    rows = c.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(rows[0].keys() if rows else ["id","address","city","price","source","link","description","motivation","deal_score"])
    for r in rows:
        writer.writerow([r[k] for k in r.keys()])
    
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=kern_private_leads.csv"})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Harbison Standard Branded Dashboard at http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
