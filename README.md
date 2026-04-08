# Automation Hub — Web Scraper + PDF Processor

A production-ready Python automation toolkit for web scraping and PDF processing, with AI summarization via Gemini.

---

## Project Structure

```
automation_hub/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py          # Centralized config & constants
├── scraper/
│   ├── __init__.py
│   ├── fetcher.py           # HTTP fetching with retry logic
│   ├── parser.py            # HTML parsing & content extraction
│   └── exporter.py          # Output to JSON/CSV/TXT/MD
├── pdf_processor/
│   ├── __init__.py
│   ├── reader.py            # PDF reading & text extraction
│   ├── table_extractor.py   # Table detection & CSV export
│   └── summarizer.py        # AI summarization via Gemini API
├── pipeline/
│   ├── __init__.py
│   └── runner.py            # End-to-end orchestration
├── tests/
│   ├── test_scraper.py
│   ├── test_pdf.py
│   └── test_pipeline.py
├── web_scraper.py            # CLI entrypoint — scraper
├── pdf_processor.py          # CLI entrypoint — PDF
└── automation_pipeline.py    # CLI entrypoint — full pipeline
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key (for AI summarization)
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

# 3. Run the scraper
python web_scraper.py --url https://example.com --mode all --format json

# 4. Process a PDF
python pdf_processor.py --file report.pdf --op all --format md

# 5. Full pipeline
python automation_pipeline.py --url https://example.com --output-dir ./output

# 6. Run web app
uvicorn webapp:app --reload
# Open http://127.0.0.1:8000
```

---

## CLI Reference

### web_scraper.py

| Argument | Default | Description |
|---|---|---|
| `--url` | required | Target URL to scrape |
| `--mode` | `all` | `all`, `links`, `text`, `images`, `tables`, `meta`, `custom` |
| `--selector` | — | CSS selector (when `--mode custom`) |
| `--format` | `json` | `json`, `csv`, `txt`, `md` |
| `--output` | auto | Output filename |
| `--output-dir` | `./output` | Directory for auto-generated output files |
| `--delay` | `0` | Polite delay in seconds between requests |
| `--retries` | `3` | Retry attempts on failure |
| `--timeout` | `15` | Request timeout in seconds |
| `--no-headers` | — | Skip page headers in output |
| `--clean` | `True` | Strip extra whitespace |

### pdf_processor.py

| Argument | Default | Description |
|---|---|---|
| `--file` | required | PDF file path |
| `--url` | — | Direct PDF URL (downloaded automatically; HTML pages are rejected) |
| `--op` | `all` | `extract`, `summarize`, `tables`, `all` |
| `--pages` | `all` | Page range: `all`, `1-5`, `1,3,7`, `2-` |
| `--format` | `md` | `txt`, `json`, `md`, `csv` |
| `--output` | auto | Output filename |
| `--ai-prompt` | default | Custom summarization prompt |
| `--model` | `gemini-1.5-flash` | Gemini model to use |

### automation_pipeline.py

| Argument | Default | Description |
|---|---|---|
| `--url` | required | Starting URL (page or direct PDF) |
| `--scrape-mode` | `all` | Scraper extraction mode |
| `--follow-pdfs` | `False` | Auto-download & process PDFs found on page |
| `--pdf-op` | `all` | PDF operation |
| `--scrape-format` | `json` | Scraper output format |
| `--pdf-format` | `md` | PDF output format |
| `--output-dir` | `./output` | Directory for all output files |

---

## Output Paths

- `web_scraper.py` now writes auto-generated files directly under `--output-dir` (not inside a `scraper/` subfolder).
- `automation_pipeline.py` now writes scrape outputs and `pipeline_manifest_*.json` directly under `--output-dir`.
- `automation_pipeline.py` still keeps PDF artifacts under `--output-dir/pdf` and downloaded PDFs under `--output-dir/pdfs`.

Example paths:

```text
output/
├── scraped_all_YYYYMMDD_HHMMSS.json
├── pipeline_manifest_YYYYMMDD_HHMMSS.json
├── pdf/
└── pdfs/
```

---

## Web App

Automation Hub also includes a full-stack web app:

- Backend: FastAPI (`webapp.py`)
- Frontend: static SPA (`webapp_static/index.html`)
- APIs:
  - `POST /api/scrape`
  - `POST /api/pdf`
  - `POST /api/pipeline`
  - `GET /api/health`
- File downloads are served from `/output/...`

Run:

```bash
pip install -r requirements.txt
uvicorn webapp:app --reload
```

Then open:

- `http://127.0.0.1:8000`

---

## Deployable + Scalable Setup

This project now ships with production deployment primitives:

- `Dockerfile` for the web API/UI service
- `docker-compose.yml` with:
  - `web` (FastAPI + Gunicorn/Uvicorn workers)
  - `worker` (Celery async jobs)
  - `redis` (broker/result backend)
- Async job APIs:
  - `POST /api/jobs/scrape`
  - `POST /api/jobs/pdf`
  - `POST /api/jobs/pipeline`
  - `GET /api/jobs/{job_id}`

Run locally in production-like mode:

```bash
docker compose up --build
```

Scale workers:

```bash
docker compose up --build --scale worker=3
```

This gives horizontal job-processing scalability while keeping the web API responsive under heavy workloads.

---

## Authentication + API Keys

- API endpoints under `/api/*` are protected by API key auth (except `/api/health`).
- Send API key via header:
  - `X-API-Key: <your_key>`
- Bootstrap admin key via env:
  - `ADMIN_API_KEY=...`
- Create additional keys:
  - `POST /api/admin/api-keys` (multipart field `name`)

---

## Persistent Job Metadata/History

- SQLite-backed app DB (`app.db` by default) stores:
  - API keys (`api_keys` table)
  - async job lifecycle (`jobs` table)
- Job history endpoint:
  - `GET /api/jobs/history?limit=50`
- DB path configurable by env:
  - `APP_DB_PATH=/path/to/app.db`

---

## CI/CD + Cloud Manifests

Included files:

- GitHub Actions workflow:
  - `.github/workflows/ci-cd.yml`
- Render:
  - `render.yaml`
- Railway:
  - `railway.json`
- Kubernetes (EKS/GKE compatible):
  - `k8s/deployment-web.yaml`
  - `k8s/deployment-worker.yaml`
  - `k8s/deployment-redis.yaml`
  - `k8s/service-web.yaml`
  - `k8s/service-redis.yaml`
  - `k8s/secret-example.yaml`

AWS/GCP deployment notes:

- For AWS EKS and GCP GKE, apply the `k8s/` manifests after replacing image and secrets.
- For managed Redis/DB services, swap in cloud service endpoints via env vars.

---

## PDF URL Notes

- `pdf_processor.py --url` expects a direct PDF response.
- The downloader validates response type using `Content-Type` and PDF file signature (`%PDF-`).
- If you pass a normal webpage URL (for example an article URL), the CLI exits with a clear validation error instead of attempting to parse HTML as a PDF.

---

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Required for AI summarization |
| `SCRAPER_DELAY` | Default request delay (seconds) |
| `SCRAPER_TIMEOUT` | Default request timeout |
| `LOG_LEVEL` | Logging level (`INFO`, `DEBUG`, `WARNING`) |

---

## Dependencies

See `requirements.txt`. Key packages:
- `requests` + `beautifulsoup4` — web scraping
- `pdfplumber` — PDF text & table extraction
- Gemini summarization — via Google Generative Language REST API
- `pandas` — data handling & CSV export
- `python-dotenv` — environment variable management
