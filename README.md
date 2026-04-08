# Automation Hub — Web Scraper + PDF Processor

A production-ready Python automation toolkit for web scraping and PDF processing, with AI summarization via Gemini.

[![CI](https://img.shields.io/badge/ci-github%20actions-blue)](#)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

Table of contents
- Overview
- Features
- Project structure
- Quickstart
- Installation
- Configuration / Environment
- CLI reference & examples
- Web API (FastAPI) usage
- Output layout
- Deployment (Docker & Compose)
- Testing & CI
- Development workflow
- Contributing
- Troubleshooting & FAQ
- Security
- License
- Changelog

---

## Overview

Automation Hub is an end-to-end toolkit that:
- Scrapes web pages (links, text, images, tables, meta).
- Processes PDFs (text extraction, table extraction, AI-powered summarization).
- Orchestrates scraping + PDF processing pipelines.
- Exposes both CLI entrypoints and a FastAPI web service with async/background jobs (Celery + Redis).
- Is designed to be deployable and horizontally scalable.

Use cases:
- Content ingestion for analytics
- Bulk PDF processing and automatic summarization
- Building searchable content stores and reports
- As a foundation for crawling + extracting structured data

---

## Features

- Robust HTTP fetcher with retries, timeouts and optional politeness delays.
- HTML parsing with CSS selectors and multiple extraction modes.
- PDF reading via pdfplumber with table detection and CSV export.
- AI summarization using Google Generative Language (Gemini) REST API (configurable model & prompt).
- Command-line entrypoints:
  - `web_scraper.py`, `pdf_processor.py`, `automation_pipeline.py`
- FastAPI backend with async job endpoints and job history persisted in SQLite.
- Docker + docker-compose manifests for production-like deployment.
- CI workflow for linting, tests and packaging.

---

## Project structure

```
automation_hub/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py
├── scraper/
│   ├── __init__.py
│   ├── fetcher.py
│   ├── parser.py
│   └── exporter.py
├── pdf_processor/
│   ├── __init__.py
│   ├── reader.py
│   ├── table_extractor.py
│   └── summarizer.py
├── pipeline/
│   ├── __init__.py
│   └── runner.py
├── tests/
│   ├── test_scraper.py
│   ├── test_pdf.py
│   └── test_pipeline.py
├── web_scraper.py
├── pdf_processor.py
├── automation_pipeline.py
├── webapp.py
└── automation_pipeline.py
```

---

## Quickstart

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy and edit environment variables:
```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY and other vars
```

3. Run the scraper:
```bash
python web_scraper.py --url https://example.com --mode all --format json
```

4. Process a PDF:
```bash
python pdf_processor.py --file report.pdf --op all --format md
```

5. Run full pipeline:
```bash
python automation_pipeline.py --url https://example.com --output-dir ./output
```

6. Run web app (development):
```bash
pip install -r requirements.txt
python -m uvicorn webapp:app --reload
# Open http://127.0.0.1:8000
```

Note: Use `python -m uvicorn` to ensure worker uses same environment as dependencies.

---

## Installation

- Recommended: Python 3.8+
- Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
- Key dependencies:
  - requests, beautifulsoup4 — scraping
  - pdfplumber — PDF text & table extraction
  - pandas — data handling & CSV export
  - python-dotenv — env var management
  - fastapi, uvicorn, gunicorn — web service
  - celery, redis — async job processing
  - (Gemini) Google Generative Language REST API client or just use requests

---

## Configuration / Environment

Copy `.env.example` to `.env` and set values:

- GOOGLE_API_KEY — required for AI summarization (Gemini).
- ADMIN_API_KEY — bootstrap admin key for web API auth.
- APP_DB_PATH — path to SQLite DB (default `app.db`).
- SCRAPER_DELAY — default delay between requests (seconds).
- SCRAPER_TIMEOUT — default request timeout.
- LOG_LEVEL — `DEBUG`, `INFO`, `WARNING`, `ERROR`.

Example `.env`:
```
GOOGLE_API_KEY=your_key_here
ADMIN_API_KEY=changeme
APP_DB_PATH=app.db
SCRAPER_DELAY=0
SCRAPER_TIMEOUT=15
LOG_LEVEL=INFO
```

Security note: Do not commit `.env` with secrets to source control.

---

## CLI Reference & Examples

web_scraper.py
- Arguments
  - `--url` (required)
  - `--mode` (all, links, text, images, tables, meta, custom) — default `all`
  - `--selector` — CSS selector for custom mode
  - `--format` — `json`, `csv`, `txt`, `md` (default `json`)
  - `--output-dir` — default `./output`
  - `--delay`, `--retries`, `--timeout`
Example:
```bash
python web_scraper.py --url https://example.com --mode text --format md --output-dir ./output
```

pdf_processor.py
- Arguments
  - `--file` (required) or `--url` (direct PDF URL)
  - `--op` (`extract`, `summarize`, `tables`, `all`) — default `all`
  - `--pages` (`all`, `1-5`, `1,3,7`) — default `all`
  - `--format` (`txt`, `json`, `md`, `csv`) — default `md`
  - `--ai-prompt`, `--model` (default `gemini-1.5-flash`)
Example (summarize first 3 pages):
```bash
python pdf_processor.py --file report.pdf --op summarize --pages 1-3 --format md
```

automation_pipeline.py
- Orchestrates scraping and pdf processing
Example:
```bash
python automation_pipeline.py \
  --url https://example.com \
  --scrape-mode all \
  --follow-pdfs True \
  --output-dir ./output
```

---

## Web API (FastAPI) usage

API endpoints:
- POST /api/scrape — run a scrape (sync or async)
- POST /api/pdf — process a PDF
- POST /api/pipeline — run pipeline
- POST /api/jobs/scrape — enqueue scrape job (async)
- POST /api/jobs/pdf — enqueue pdf job (async)
- POST /api/jobs/pipeline — enqueue pipeline job (async)
- GET /api/jobs/{job_id} — job status
- GET /api/jobs/history?limit=50 — job history
- GET /api/health — health check

Auth:
- API Key required: send header `X-API-Key: <key>`
- Bootstrap admin via env `ADMIN_API_KEY`

Example curl:
```bash
curl -X POST "http://127.0.0.1:8000/api/scrape" \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"all","format":"json"}'
```

Async job example (fallback behavior):
- If Redis/Celery are down, async endpoints will fall back to synchronous processing and return `"mode": "sync_fallback"` in the response.

---

## Output layout & file naming

- `web_scraper.py` writes auto-generated outputs directly under `--output-dir`.
- `automation_pipeline.py` writes scrape outputs and `pipeline_manifest_*.json` under `--output-dir`.
- PDF artifacts are kept under `--output-dir/pdf` and downloaded PDFs in `--output-dir/pdfs`.

Example:
```
output/
├── scraped_all_20260408_153045.json
├── pipeline_manifest_20260408_153045.json
├── pdf/
└── pdfs/
```

File names include timestamps to avoid overwriting and to make reproducible pipelines easier to trace.

---

## Deployment (Docker & docker-compose)

- Dockerfile builds the web API + static SPA.
- docker-compose.yml contains:
  - web (FastAPI + Gunicorn/Uvicorn)
  - worker (Celery)
  - redis (broker)
Usage:
```bash
docker compose up --build
# scale workers:
docker compose up --build --scale worker=3
```

If you use managed Redis or DB services, replace service endpoints via env vars in your deployment manifests.

Kubernetes manifests (k8s/) are provided for EKS/GKE deployments. Replace image tags and secrets prior to apply.

---

## Testing & CI

- Unit tests in `tests/` (pytest).
- Run tests:
```bash
pytest -q
```
- GitHub Actions CI workflow in `.github/workflows/ci-cd.yml` runs linting, tests, and package checks.

---

## Development workflow

- Create a branch for each feature/fix:
```bash
git checkout -b feature/your-feature
```
- Run tests locally, add unit tests for changes.
- Open a pull request against `main` and include a description and testing notes.

---

## Contributing

1. Fork the repo and create a branch.
2. Add tests for new features/bug fixes.
3. Keep changes small and focused.
4. Follow the repo's code style and run linters.

See CONTRIBUTING.md (create one if it does not exist) for full guidelines.

---

## Troubleshooting & FAQ

- Q: The PDF URL returns HTML — what happens?
  - A: `pdf_processor.py --url` validates `Content-Type` and PDF signature (`%PDF-`). If validation fails it exits with a clear error to prevent mis-parsing HTML.
- Q: Summaries are poor quality?
  - A: Tweak `--ai-prompt` and try a different Gemini model via `--model`.
- Q: Redis unavailable — jobs fail?
  - A: The async endpoints fall back automatically to synchronous execution and return `"mode":"sync_fallback"`. Check logs and redis health.

---

## Security & Privacy

- Keep `GOOGLE_API_KEY` and `ADMIN_API_KEY` secret.
- Avoid sending PII to third-party services unless you are allowed to.
- For production, secure access with HTTPS, rotate keys regularly, and enforce least-privilege IAM for cloud resources.

---

## License

MIT License — see LICENSE file.

---

## Changelog

- See CHANGELOG.md for release notes. If not present, add entries for notable changes (features, bugfixes, breaking changes).

---

## Contact / Support

Raise issues on the repository. For urgent or paid support, include contact details or an email in a SUPPORT.md file.
