# RSS Pipeline — Orchestrated Architecture

A production-grade scraping and analysis pipeline coordinated by `main.py`.
Three independent steps run in sequence; all state is tracked in Supabase Postgres
and all outputs are stored in Supabase Storage.

---

## Project Structure

```
rss_pipeline/
├── main.py                    ← Orchestrator (the only new file you run)
├── manage.py                  ← Django management CLI
├── render.yaml                ← One-click Render deployment
├── requirements.txt
├── .env.example               ← Copy → .env and fill in secrets
│
├── config/
│   ├── settings.py            ← Django settings (reads from .env)
│   ├── urls.py
│   └── wsgi.py
│
├── pipeline/
│   ├── step1_scraper.py       ← Refactored cs3.py  (returns list[dict])
│   ├── step2_detector.py      ← Refactored pdf_m.py (returns list[dict])
│   ├── step3_reporter.py      ← Refactored report.py (returns list[dict])
│   └── storage.py             ← Supabase Storage client
│
└── dashboard/
    ├── models.py              ← PipelineRun, Article, SiteConfig, …
    ├── admin.py               ← Django Admin UI (Dashboard + Config)
    ├── signals.py             ← Auto-queue run on config save
    ├── apps.py
    └── migrations/
```

---

## What Changed vs the Original Scripts

| Original | New | What changed |
|---|---|---|
| `cs3.py` | `pipeline/step1_scraper.py` | `main()` → `run(config) -> list[dict]`; hardcoded vars become config params |
| `pdf_m.py` | `pipeline/step2_detector.py` | Input is article dicts from step1, not local file paths; returns list[dict] |
| `report.py` | `pipeline/step3_reporter.py` | Internal PDF fetched from Supabase URL, not local disk; returns list[dict] |
| _(new)_ | `main.py` | Orchestrates all three steps, tracks status in DB, uploads to Storage |

---

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone <your-repo>
cd rss_pipeline
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Create your `.env`

```bash
cp .env.example .env
# Open .env and fill in all required values
```

Required variables:
```
SERPER_API_KEY=...
GEMINI_API_KEY=...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_BUCKET=rss
DJANGO_SECRET_KEY=some-long-random-string
DATABASE_URL=postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
```

> **Getting DATABASE_URL from Supabase:**  
> Go to your Supabase project → Settings → Database → Connection string → URI mode.

### 3. Run migrations

```bash
python manage.py migrate
python manage.py createsuperuser   # create admin login
```

### 4. Seed initial config (optional — or use the admin UI)

```bash
python manage.py shell <<'EOF'
from dashboard.models import SiteConfig, DateRangeConfig, SearchTermConfig

# Sites
for domain in ["thewire.in", "scroll.in", "ndtv.com", "indianexpress.com", "thehindu.com"]:
    SiteConfig.objects.get_or_create(domain=domain)

# Date range
DateRangeConfig.objects.get_or_create(
    date_from="03/01/2024", date_to="03/31/2025",
    defaults={"label": "2024-2025"}
)

# Search terms
for term in ["RSS", "Rashtriya Swayamsevak Sangh", "rss", "Rss"]:
    SearchTermConfig.objects.get_or_create(term=term)

print("Done")
EOF
```

### 5. Start the Django admin dashboard

```bash
python manage.py runserver
# Visit http://localhost:8000/admin
```

### 6. Run the pipeline

```bash
python main.py
```

---

## Django Admin Dashboard

Visit `/admin/` after logging in:

| Section | What you can do |
|---|---|
| **Pipeline Runs** | See all runs with status badge (green/yellow/red), auto-refreshes every 10s. Click a run to see step-by-step breakdown and all articles. |
| **Articles** | Browse all scraped articles with detection counts, scores, and links to JSON reports in Supabase Storage. |
| **Sites to Scrape** | Add/remove domains. Saving auto-queues a new run. |
| **Date Ranges** | Add/remove date windows. Saving auto-queues a new run. |
| **Search Terms** | Manage keywords. |
| **Pending Runs** | View the queue of runs waiting to execute. |

**Start New Run button:** Select any row in Pipeline Runs → Actions → "▶ Start a new pipeline run".

---

## Storage Layout in Supabase

```
rss/                              ← bucket name
└── runs/
    └── {run_id}/
        ├── step1_scraped/
        │   ├── thewire_in__article_title__0001.json
        │   └── ...
        ├── step2_detections/
        │   ├── thewire_in__article_title__0001__detection.json
        │   └── ...
        └── step3_reports/
            ├── thewire_in__article_title__0001__report.json
            └── ...
```

The internal PDF (`Internaldoc.docx.pdf`) is already in the `rss` bucket root.
`step3_reporter.py` fetches it from there at runtime. To update it, just replace
the file in Supabase Storage — same filename, no code change.

---

## Deployment on Render

1. Push this repo to GitHub.
2. In Render → New Web Service → connect your repo.
3. Render auto-detects `render.yaml`.
4. In the Render dashboard, set the secret environment variables:
   - `DJANGO_SECRET_KEY`
   - `DATABASE_URL` (from Supabase)
   - `SUPABASE_URL`, `SUPABASE_KEY`
   - `SERPER_API_KEY`, `GEMINI_API_KEY`
5. Deploy. The build command runs migrations automatically.
6. Visit `https://your-app.onrender.com/admin/` to access the dashboard.

To trigger a run from Render: use the admin "Start New Run" action, or set up
a Render Cron Job that calls `python main.py` on a schedule.

---

## Error Handling

- Every step is wrapped in `try/except` in `main.py`.
- On failure: DB run record is updated with `status=failed`, `failed_at_step`, and the Python exception message.
- Partial outputs from completed steps are **not** lost — they remain in Supabase Storage.
- If a second run is triggered while one is active, it is saved as a `PendingRun` and executed automatically when the active run finishes.
- On restart (Render container restart), `main.py` checks for pending runs and resumes the queue.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SERPER_API_KEY` | ✅ | Serper.dev API key for Google search |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `SUPABASE_URL` | ✅ | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase service role key |
| `SUPABASE_BUCKET` | ✅ | Storage bucket name (default: `rss`) |
| `DATABASE_URL` | ✅ | Postgres connection string from Supabase |
| `DJANGO_SECRET_KEY` | ✅ | Long random string for Django |
| `DJANGO_DEBUG` | — | `True` for local, `False` for production |
| `DJANGO_ALLOWED_HOSTS` | — | Comma-separated hostnames |
| `INTERNAL_DOC_URL` | — | Supabase public URL to the internal PDF |
| `BRIGHTDATA_WSS` | — | Bright Data WebSocket URL (optional, Tier 4) |
| `COUNTRY` | — | Country code for Serper search (default: `in`) |
| `MAX_RESULTS_PER_SITE` | — | Max articles per site per search (default: `50`) |
