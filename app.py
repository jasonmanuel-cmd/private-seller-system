"""
Dashboard for No-MLS Lead Scraper — Harbison Standard
Run: python app.py
Open: http://localhost:5000
Render: Uses PORT env var (10000)
"""
from flask import Flask, render_template_string, request, jsonify, redirect
import sys, os
sys.path.append(os.path.dirname(__file__))
from database import get_leads, get_stats, get_conn, init_db
from datetime import datetime

app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kern Private Lead Scraper — Harbison Standard</title>
<style>
:root{--navy:#031c2b;--gold:#d4a574;--mid:#0a2a3f;--light:#f5f1eb}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--navy);color:#fff;line-height:1.5;padding:0}
a{color:var(--gold);text-decoration:none}
.container{max-width:1200px;margin:0 auto;padding:20px}
.header{padding:20px 0;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.header h1{font-size:28px}
.header h1 em{color:var(--gold);font-style:italic}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.stat{background:var(--mid);border-radius:10px;padding:14px;text-align:center;border:1px solid rgba(255,255,255,.08)}
.stat .num{font-size:28px;font-weight:800;color:var(--gold)}
.stat .label{font-size:12px;color:#8aa0b0;text-transform:uppercase;letter-spacing:.5px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.filters a{padding:8px 14px;background:var(--mid);border:1px solid rgba(255,255,255,.1);border-radius:8px;color:#fff;font-size:14px}
.filters a.active{background:var(--gold);color:var(--navy);font-weight:700}
.card{background:var(--mid);border-radius:12px;padding:16px;margin-bottom:12px;border-left:4px solid var(--gold);border-top:1px solid rgba(255,255,255,.06);border-right:1px solid rgba(255,255,255,.06);border-bottom:1px solid rgba(255,255,255,.06)}
.card.hot{border-left-color:#ff4d4d}
.card.warm{border-left-color:#ffcc00}
.card.cold{border-left-color:#4caf50}
.price{font-size:22px;font-weight:800;color:var(--gold)}
.meta{font-size:13px;color:#8aa0b0;margin-top:4px}
.title{font-weight:700;margin:8px 0;font-size:16px}
.desc{font-size:14px;color:#cbd5e1;margin-top:6px;line-height:1.4}
.btn{display:inline-block;padding:8px 12px;border-radius:6px;font-weight:600;font-size:13px;margin-top:10px;margin-right:8px}
.btn-gold{background:var(--gold);color:var(--navy)}
.btn-dark{background:var(--navy);color:#fff;border:1px solid rgba(255,255,255,.15)}
.badge{display:inline-block;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.3px}
.badge-hot{background:rgba(255,77,77,.15);color:#ff6b6b;border:1px solid rgba(255,77,77,.3)}
.badge-warm{background:rgba(255,204,0,.15);color:#ffcc00;border:1px solid rgba(255,204,0,.3)}
.badge-cold{background:rgba(76,175,80,.15);color:#4caf50;border:1px solid rgba(76,175,80,.3)}
.badge-source{background:rgba(212,165,116,.15);color:var(--gold);border:1px solid rgba(212,165,116,.3)}
.form-wrap{background:#fff;color:var(--navy);border-radius:12px;padding:20px;margin-top:30px}
.input{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #cbd5e1;margin-bottom:10px;font-size:14px}
label{font-size:12px;font-weight:700;color:#334155;margin-bottom:4px;display:block}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:700px){.row{grid-template-columns:1fr}.header h1{font-size:22px}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<div>
<h1>🏜️ Kern <em>Private Lead</em> Scraper</h1>
<div style="font-size:13px;color:#8aa0b0">Harbison Standard — No MLS, No Zillow, Private Sellers Only — {{stats.total}} leads</div>
</div>
<div style="display:flex;gap:8px">
<a class="btn btn-gold" href="/run" style="text-decoration:none">▶ Run Scraper Now</a>
<a class="btn btn-dark" href="/export" style="text-decoration:none">⬇ Export CSV</a>
</div>
</div>

<div class="stats">
<div class="stat"><div class="num">{{stats.total}}</div><div class="label">Total Leads</div></div>
<div class="stat"><div class="num">{{stats.hot}}</div><div class="label">Hot 7+ Score</div></div>
<div class="stat"><div class="num">{{stats.warm}}</div><div class="label">Warm 5+ Score</div></div>
<div class="stat"><div class="num">{{stats.by_source.get('craigslist',0)}}</div><div class="label">Craigslist</div></div>
<div class="stat"><div class="num">{{stats.by_source.get('zillow_fsbo',0) + stats.by_source.get('kern_tax',0) + stats.by_source.get('bakersfield_code',0)}}</div><div class="label">Other Free</div></div>
</div>

<div class="filters">
<a href="/?min_score=0" class="{{'active' if min_score==0 else ''}}">All ({{stats.total}})</a>
<a href="/?min_score=7" class="{{'active' if min_score==7 else ''}}">🔥 Hot 7+ ({{stats.hot}})</a>
<a href="/?min_score=5" class="{{'active' if min_score==5 else ''}}">Warm 5+ ({{stats.warm}})</a>
<a href="/?city=Tehachapi" class="{{'active' if city_filter=='Tehachapi' else ''}}">Tehachapi</a>
<a href="/?city=Bakersfield" class="{{'active' if city_filter=='Bakersfield' else ''}}">Bakersfield</a>
<a href="/?city=California%20City" class="{{'active' if city_filter=='California City' else ''}}">California City</a>
<a href="/?source=craigslist" class="{{'active' if source_filter=='craigslist' else ''}}">Craigslist Only</a>
<a href="/?source=kern_tax" class="{{'active' if source_filter=='kern_tax' else ''}}">Tax-Defaulted</a>
</div>

{% for lead in leads %}
<div class="card {{'hot' if lead['deal_score']>=7 else 'warm' if lead['deal_score']>=5 else 'cold'}}">
<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap">
<div>
<div class="price">{{lead['price_text'] or '$0'}} <span style="font-size:14px;font-weight:400;color:#8aa0b0">| Score {{lead['deal_score']}}/10</span> <span class="badge {{'badge-hot' if lead['deal_score']>=7 else 'badge-warm' if lead['deal_score']>=5 else 'badge-cold'}}">{{'HOT' if lead['deal_score']>=7 else 'WARM' if lead['deal_score']>=5 else 'COLD'}}</span></div>
<div class="title">{{lead['address']}} — {{lead['city']}}</div>
<div class="meta"><span class="badge badge-source">{{lead['source']}}</span> <span style="margin-left:8px">{{lead['motivation']}}</span> • {{lead['created_at'][:16]}} • Status: {{lead['status']}}</div>
</div>
<div style="text-align:right">
<div style="font-size:12px;color:#8aa0b0">{{lead['source_type']}}</div>
</div>
</div>
<div class="desc">{{lead['description'][:500]}}</div>
<div style="margin-top:10px">
<a class="btn btn-gold" href="{{lead['link']}}" target="_blank">View Original →</a>
<a class="btn btn-dark" href="https://www.truepeoplesearch.com/results?name={{lead['address'][:20]}}" target="_blank">Skip Trace Free</a>
<a class="btn btn-dark" href="https://assessor.kerncounty.com/parcel-search/" target="_blank">Assessor Lookup</a>
<a class="btn btn-dark" href="#" onclick="markContacted('{{lead['id']}}');return false;">Mark Contacted</a>
</div>
</div>
{% endfor %}

{% if not leads %}
<div class="card"><p>No leads match filter. Click "Run Scraper Now" or check filters.</p></div>
{% endif %}

<div class="form-wrap">
<h3>➕ Add Manual Private Lead (Facebook, Driving, Referral)</h3>
<p style="font-size:13px;color:#64748b;margin-bottom:12px">Found a lead on Facebook Marketplace, driving, or referral? Add it here — it will be scored automatically.</p>
<form method="POST" action="/add">
<div class="row"><div><label>Address *</label><input class="input" name="address" required placeholder="123 Main St"></div><div><label>City *</label><input class="input" name="city" required placeholder="Bakersfield"></div></div>
<div class="row"><div><label>Price</label><input class="input" name="price" type="number" placeholder="150000"></div><div><label>Source *</label><select class="input" name="source"><option value="facebook">Facebook Marketplace/Group</option><option value="driving">Driving for Dollars</option><option value="referral">Referral</option><option value="wholesaler">Wholesaler</option><option value="zillow_fsbo">Zillow FSBO</option><option value="other">Other</option></select></div></div>
<label>Link (Facebook post, Zillow link, etc)</label><input class="input" name="link" placeholder="https://...">
<label>Description / Why private? *</label><textarea class="input" name="description" rows="3" required placeholder="e.g., Divorce, inherited, as-is, needs work, owner in LA, wants private sale, no MLS..."></textarea>
<button type="submit" class="btn btn-gold" style="width:100%;border:0;cursor:pointer;padding:12px">Add Lead & Score →</button>
</form>
</div>

<div style="margin-top:30px;padding:20px;background:var(--mid);border-radius:12px">
<h3 style="color:var(--gold)">How This System Finds Private Leads No One Knows</h3>
<ol style="margin-left:20px;margin-top:10px;color:#cbd5e1;font-size:14px;line-height:1.6">
<li><strong>Craigslist RSS:</strong> Scrapes Bakersfield Craigslist by owner + land every hour — FSBO sellers who don't want MLS</li>
<li><strong>Zillow FSBO:</strong> Checks Zillow FSBO pages for Bakersfield/Tehachapi/California City — private sellers avoiding agents</li>
<li><strong>Kern Tax-Defaulted:</strong> Scrapes county treasurer for tax-defaulted auction PDFs — 5+ years unpaid = motivated, can contact before auction</li>
<li><strong>Bakersfield Code / Vacant:</strong> Vacant/distressed houses from open data + driving for dollars</li>
<li><strong>Manual:</strong> You add Facebook Marketplace, FB Groups, wholesaler emails, driving leads — all scored same system</li>
<li><strong>Scoring:</strong> Keywords (as-is, estate, probate, private sale, no MLS, owner financing) + price + source type = 1-10 score. 7+ = call immediately</li>
<li><strong>Next Steps:</strong> For each lead: Assessor lookup free (assessor.kerncounty.com) → TruePeopleSearch.com free phone → Call with private sale script</li>
</ol>
<p style="margin-top:12px;font-size:13px;color:#8aa0b0">Free to run. No MLS. No paid APIs. Add Facebook leads manually (FB blocks scraping). Run scraper hourly via cron or Render.com free tier.</p>
</div>

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
    
    # Build query
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
    # Run scraper in background
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
    print(f"Starting dashboard at http://0.0.0.0:{port}")
    # Use 0.0.0.0 for Render, debug False for production
    app.run(host="0.0.0.0", port=port, debug=False)
