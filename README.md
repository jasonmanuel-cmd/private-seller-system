# Private Seller System — Harbison Standard

Private, local lead-research dashboard for Kern County, California. The maintained application is **the Python application at this repository root**. The `non-mls-deal-finder/` folder is an older prototype; `private-seller-system/` contains marketing drafts and standalone page assets, not another installed website.

## Open on this Windows computer

Double-click **Start Dashboard.cmd**, then open **http://127.0.0.1:5000**. Keep the terminal window open; Ctrl+C stops the server. The launcher uses the project-specific Python 3.11 environment, not the machine's potentially incompatible default Python.

Manual setup (requires Python 3.11 or uv):

```text
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe serve.py
```

On Linux/macOS, substitute `.venv/bin/python` for `.venv/Scripts/python.exe`.

## What the system actually does

- Stores actual imported or manually entered property leads in SQLite.
- Retains immutable property observations and material changes instead of overwriting the only known history.
- Produces an evidence-adjusted 100-point opportunity score alongside the legacy keyword score. **Neither score is a valuation, verified equity estimate, or proof of seller motivation.**
- Calculates seller-pressure velocity and a seller-capitulation index only from dated changes such as verified reductions, status transitions, and newly observed listing language.
- Analyzes supplied comparable sales, rehabilitation ranges, optionality signals, listing quality, data conflicts, and counterfactual scenarios. Missing inputs remain `UNKNOWN`.
- Generates Top 10, Top 3 deep-dive, watchlist, rejected, and change-event reports without manufacturing enough properties to fill a list.
- Filters leads, records contacted status, and exports CSV.
- Offers on-demand source checking with visible progress and per-source outcomes.
- Separates manual-research resources from real property leads. A search link or a tax-sale brochure is **not** a lead and must never inflate the hot-lead count.

**Source limitations:** Craigslist may block requests or no longer serve RSS. Zillow may block automation. County source URLs and auction lists change; a generic PDF is not a verified parcel listing. Facebook, probate, recorder, and wholesaler research are manual unless an actual supported import is implemented. An empty database is an honest result, not permission to generate example properties. Do not bypass access controls.

## Daily workflow

1. Open the dashboard and run a source check. Read source errors, not just the lead count.
2. Review actual leads using city/source/score filters; open the original record and confirm listing date, location, owner/agent status, and availability.
3. For sources requiring manual research, open their resource links and add a specific property using **Add Manual Lead**. Include its real source URL and factual notes.
4. Mark contacted only after outreach. Respect opt-outs, applicable calling/texting restrictions, and brokerage requirements. An assessor lookup or people-search link does not verify ownership or contact consent.
5. Export CSV regularly. For a complete restorable backup, stop the app and copy the entire `data/` directory, including any SQLite companion files. Keep backups private.

Do not promise a closing date, referral compensation, MLS exclusion, or marketing/legal compliance based only on the draft marketing documents. Obtain seller consent and brokerage/legal review for the actual transaction.

## Storage and privacy

Default database: `data/leads.db`, resolved relative to this project, not the shell working directory. Optional **DB_PATH** environment variable overrides it. Local storage survives restarts and deployments of files as long as that directory is preserved.

The supported server (`serve.py`) binds only to **127.0.0.1** by default. Do not port-forward an unprotected dashboard. Public binding requires a **DASHBOARD_TOKEN** environment variable; set a durable **SECRET_KEY** for cloud sessions. Use HTTPS before sending authentication over a network. Keep these values in your host's secret settings, never in source control or URLs.

CSV contains private research data. Share only with authorized recipients. Test fixtures are isolated from the real database.

## Optional hosting — not deployed automatically

`render.yaml` is an **optional paid** single-web-service deployment with a persistent disk. Review and approve current provider pricing before applying it. It intentionally does not launch a separate scraper worker: two independent SQLite files on two services would not share leads. On-demand scraping runs inside the dashboard process and writes to its disk.

The previous instructions incorrectly described free persistent storage and a shared database across independent services. Do not use that setup. The historical handoff and marketing files may contain outdated claims; this README describes the supported root application.

`Dockerfile` runs the same single-process server. Mount persistent storage at `/app/data` and supply `DASHBOARD_TOKEN`; the container refuses an unauthenticated public bind. Docker and Render require their own deployment verification; successful local tests do not prove a cloud deployment.

For local scheduled runs, `run.py --once` checks sources once and then analyzes stored properties. `run.py --reports-only` recalculates intelligence without source collection. `run.py --loop --interval-minutes 60` repeats safely while the process remains running. A durable database lock prevents overlapping collection cycles. This does not install an operating-system startup task.

## Property-intelligence architecture

```text
lawful collectors/manual imports
              ↓
current lead + immutable observations
              ↓
change events and evidence conflicts
              ↓
pressure · capitulation · optionality · market/rehab analysis
              ↓
evidence-adjusted 0–100 opportunity score
              ↓
Top 10 · Top 3 · watchlist · rejected · event reports
```

The original `leads` table remains the dashboard's current-state projection. The additive `property_observations`, `property_events`, `property_analyses`, and `report_runs` tables preserve history and analysis runs. Reimporting an identical record does not create a false observation or trigger.

### Evidence hierarchy and confidence

The system prefers evidence in this order:

1. Official government/public records.
2. Original broker or listing information.
3. Public marketplaces and published notices.
4. Secondary sources.
5. Clearly labelled analyst-derived assumptions.

Conflicting claims are retained and flagged rather than silently discarded. An official record may be selected as the working fact while the conflicting listing value remains visible. Confidence grades describe the evidence supplied to this system; they do not guarantee that a deal is correct.

`UNKNOWN` is a deliberate result. It means the system lacks enough supported information and must never be interpreted as zero. Owner identity, zoning/ADU legality, liens, occupancy, permits, motivation, ARV, or rehabilitation cost are never invented from unrelated fields.

### Supplying analysis inputs

Collectors can place structured, sourced inputs inside a lead's `raw_data` JSON. The intelligence engine recognizes:

```json
{
  "evidence": [
    {"field": "sqft", "value": 1520, "source_type": "official", "source": "county assessor", "source_url": "https://official.example/record"}
  ],
  "comps": [
    {"sold_price": 300000, "sold_date": "2026-08-15", "distance_miles": 0.4, "sqft": 1480}
  ],
  "rehab": {"low": 30000, "base": 45000, "high": 65000}
}
```

Only use comparable sales and costs that you are authorized to use and can trace to a source. Optionality signals raise research priority but do not establish subdivision, ADU, rezoning, or permit feasibility.

## Reports and API

Reports default to `data/reports/` and are excluded from Git because they may contain private research. Every run writes a timestamped archive plus atomic latest files:

- `top-10.csv`
- `top-3-deep-dive.csv`
- `watchlist.csv`
- `rejected.csv`
- `change-events.csv`
- `intelligence-report.md`

The dashboard links to these files and exposes authenticated/local-only read APIs at `/api/intelligence`, `/api/properties/<id>/history`, `/api/properties/<id>/analysis`, and `/api/events`. CSV cells are protected against spreadsheet-formula execution. Reports intentionally omit owner/contact fields.

## Configuration

Copy `.env.example` to an untracked `.env` or set host environment variables:

| Setting | Default | Purpose |
|---|---:|---|
| `DB_PATH` | `data/leads.db` | Persistent SQLite database |
| `REPORT_DIR` | `data/reports` | Private report output directory |
| `RUN_INTERVAL_MINUTES` | `60` | Loop interval |
| `OPPORTUNITY_THRESHOLD` | `75` | Minimum evidence-gated Top 10 score |
| `WATCHLIST_THRESHOLD` | `50` | Watchlist score threshold |
| `STALE_DATA_DAYS` | `30` | Configured review horizon |
| `MIN_COMP_COUNT` | `3` | Configured comp-quality target |

Invalid numeric configuration fails at startup instead of silently changing behavior.

### Windows unattended example

From an Administrator or ordinary user PowerShell prompt, create a Task Scheduler entry through the Windows UI with:

```text
Program/script: C:\path\to\private-seller-system-main\.venv\Scripts\python.exe
Arguments: run.py --once
Start in: C:\path\to\private-seller-system-main
```

Set the trigger to the desired local time, enable “Run task as soon as possible after a scheduled start is missed,” and keep the database/report directory on persistent private storage. For cron, run the equivalent absolute Python and `run.py --once` paths. These examples do not install, enable, or verify a scheduler.

## Verification

```text
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m compileall -q app.py database.py config.py scoring.py run.py serve.py property_intelligence.py intelligence_pipeline.py reports.py scrapers
```

For an offline report-only verification, run `.venv/Scripts/python.exe run.py --reports-only`. Run it a second time to confirm unchanged observations do not create new events. `GET /health` checks server/database readiness. Source availability is separate: inspect dashboard source results. Passing local tests does not prove an external source is reachable, Task Scheduler is installed, hosted storage is persistent, or a deployment is live.

## Owner

Nathanael Harbison, REALTOR®, DRE #02059393 — Harbison Standard, Kern County.
(661) 472-7499 · nate85.realtor@gmail.com
