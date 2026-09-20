# Automation Hub ⚡

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.8%2B%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-K8s_Ready-326CE5.svg?logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![Celery & Redis](https://img.shields.io/badge/Celery%20%26%20Redis-Distributed_Tasks-37814A.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Gemini AI](https://img.shields.io/badge/Google%20Gemini-AI_Summarization-8E75B2.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/Tests-68%20Passing-brightgreen.svg?logo=pytest&logoColor=white)](#-automated-testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Rahul_Roy-blueviolet.svg?logo=github)](https://github.com/Rahul03ll)

**Production-grade distributed web scraping, PDF intelligence, and pipeline orchestration engine with Google Gemini AI.**  
*Engineered with FastAPI, Celery, Redis, Docker, and Kubernetes for resilient cloud-native data workflows.*

</div>

---

## 📌 Overview

**Automation Hub** is an end-to-end data extraction and document intelligence platform designed to handle complex ingestion workflows at scale:

- 🕷️ **Multi-Mode Web Scraper**: High-performance HTTP client with automated retries, rate-limiting, politeness delays, SSL fallback, and selector-based structured extraction (links, text, tables, images, metadata).
- 📄 **PDF Intelligence & Extraction Engine**: Structured text extraction, tabular data extraction via `pdfplumber`, automatic format conversion (`json`, `csv`, `md`, `txt`), and content summarization powered by Google Gemini AI.
- 🔄 **Unified Pipeline Orchestrator**: Traverses web domains, discovers linked PDF documents, downloads and ingests them into structured formats, and generates comprehensive machine-readable run manifests.
- ⚡ **Asynchronous Microservice (FastAPI + Celery + Redis)**: Exposes high-throughput REST endpoints, persistent job tracking via SQLite/SQLAlchemy, and background task queues with automated synchronous fallbacks.
- 🐳 **Enterprise Container & Orchestration Ready**: Packaged with multi-stage `Dockerfile`, `docker-compose.yml`, and production-grade Kubernetes (`k8s/`) deployment manifests.

---

## 🏗️ System Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │               Client Request                 │
                               │        (CLI / REST API / Web UI)             │
                               └──────────────────────┬───────────────────────┘
                                                      │
                         ┌────────────────────────────┴────────────────────────────┐
                         ▼                                                         ▼
           ┌────────────────────────────┐                            ┌────────────────────────────┐
           │   CLI Pipeline Engine      │                            │     FastAPI Web Service    │
           │  automation_pipeline.py    │                            │         (webapp.py)        │
           └─────────────┬──────────────┘                            └─────────────┬──────────────┘
                         │                                                         │
                         ├────────────────────────────────────────┬────────────────┘
                         ▼                                        ▼
           ┌────────────────────────────┐           ┌────────────────────────────┐
           │     Web Scraper Engine     │           │   Celery Distributed Queue │
           │   (fetcher / parser)       │           │      (Redis Broker)        │
           └─────────────┬──────────────┘           └─────────────┬──────────────┘
                         │                                        │
                         ▼                                        ▼
           ┌────────────────────────────┐           ┌────────────────────────────┐
           │   PDF Processing Engine    │           │      Worker Execution      │
           │  (reader / table_extract)  │           │         (tasks.py)         │
           └─────────────┬──────────────┘           └─────────────┬──────────────┘
                         │                                        │
                         ▼                                        │
           ┌────────────────────────────┐                         │
           │   Google Gemini AI Engine  │ ◄───────────────────────┘
           │ (Summarization & Synthesis)│
           └─────────────┬──────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────────────────┐
        │                 Output Artifacts Store                 │
        │  • Structured JSON / CSV / Markdown Exports           │
        │  • Pipeline Execution Manifest (pipeline_manifest.json)│
        │  • SQLite Job History (app_db.py)                      │
        └────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

| Capability | Technical Details |
|---|---|
| **Resilient Scraping** | Exponential backoff, configurable timeouts, custom user agents, TLS fallback, and DOM sanitization to strip script/style noise. |
| **Table & Data Extraction** | Deterministic table identification and alignment into clean Markdown tables or CSV records. |
| **Google Gemini Integration** | Context-aware document summarization using Gemini 1.5 Flash / Pro REST API with retry cascades on rate limits (HTTP 429). |
| **Zero-Lock Pipeline** | Orchestrates crawling → link filtering → PDF downloading → parsing → AI summarization → manifest generation in a single command. |
| **Async Task Workers** | Distributed job processing powered by Celery & Redis, with zero-downtime graceful fallback to synchronous execution if brokers are offline. |
| **Database Audit Trail** | Persistent job run metadata, timestamps, input parameters, and completion statuses tracked via SQLAlchemy. |
| **Cloud-Native Deployment** | Production Dockerfile, multi-worker Docker Compose setup, and declarative Kubernetes deployments & services. |

---

## 📂 Project Structure

```
automation_hub/
├── config/
│   └── settings.py             # Centralized settings & environment loader with native fallback
├── scraper/
│   ├── fetcher.py              # HTTP client with retries, politeness delays & SSL handling
│   ├── parser.py               # BeautifulSoup parser & CSS selector extraction
│   └── exporter.py             # Exporters for JSON, CSV, Markdown, and plain text
├── pdf_processor/
│   ├── reader.py               # PDF validation, page range parsing & text reader
│   ├── table_extractor.py      # Tabular data extractor & Markdown/CSV converter
│   └── summarizer.py           # Google Gemini AI document summarization client
├── pipeline/
│   └── runner.py               # End-to-end web scrape + PDF ingestion orchestrator
├── webapp_static/              # Web dashboard frontend SPA
├── k8s/                        # Kubernetes manifests (deployments, services, configs)
├── tests/                      # Comprehensive test suite (68 unit & integration tests)
│   ├── test_scraper.py         # DOM parsing & export test suites
│   ├── test_pdf.py             # PDF reader, range parsing & exporter tests
│   ├── test_pipeline.py        # Pipeline orchestrator & CLI integration tests
│   └── test_summarizer.py      # Gemini API model fallback & retry tests
├── web_scraper.py              # Standalone web scraper CLI entrypoint
├── pdf_processor.py            # Standalone PDF processing & summarization CLI
├── automation_pipeline.py      # Unified crawler & PDF pipeline CLI
├── webapp.py                   # FastAPI REST API & Web Application
├── tasks.py                    # Celery background task definitions
├── app_db.py                   # SQLAlchemy database models & job tracking
├── docker-compose.yml          # Multi-container web + worker + redis stack
├── Dockerfile                  # Production container build specification
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment configuration template
├── LICENSE                     # MIT License
└── README.md                   # Project documentation
```

---

## 🚀 Quickstart

### Prerequisites
* Python 3.8+ (Python 3.10 / 3.12 recommended)
* Optional: Google Gemini API key (`GOOGLE_API_KEY`) for AI summarization features.

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Rahul03ll/automation_hub.git
cd automation_hub

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
```

Key environment variables:
```ini
# Google Generative Language API (for PDF AI summarization)
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_MODEL=gemini-1.5-flash

# API & Security
ADMIN_API_KEY=your_secret_admin_key
APP_DB_PATH=app.db

# Scraper Settings
SCRAPER_TIMEOUT=15
SCRAPER_RETRIES=3
SCRAPER_DELAY=0.5
SCRAPER_VERIFY_SSL=true

# Output Directory
OUTPUT_DIR=./output
```

---

## 💻 CLI Usage & Examples

### 1. Web Scraper (`web_scraper.py`)
Extract content from web pages across multiple extraction modes (`all`, `links`, `text`, `images`, `tables`, `meta`, `custom`):

```bash
# Extract all page elements and export to JSON
python web_scraper.py --url https://example.com --mode all --format json

# Extract text only and export as Markdown
python web_scraper.py --url https://news.ycombinator.com --mode text --format md

# Targeted extraction using custom CSS selectors
python web_scraper.py --url https://example.com --mode custom --selector "article.main-content" --format json
```

### 2. PDF Processor (`pdf_processor.py`)
Inspect, extract text/tables, and summarize PDF documents from local files or remote URLs:

```bash
# Extract text & tables from local PDF to Markdown
python pdf_processor.py --file document.pdf --op all --format md

# Extract tables only from specific pages to CSV
python pdf_processor.py --file financial_report.pdf --op tables --pages 5-12 --format csv

# Process remote PDF with Gemini AI executive summarization
python pdf_processor.py --url https://example.com/annual_report.pdf --op summarize --model gemini-1.5-flash
```

### 3. Unified Orchestration Pipeline (`automation_pipeline.py`)
Crawl web pages, discover linked PDFs, download, ingest, and summarize them end-to-end:

```bash
python automation_pipeline.py \
  --url https://example.com \
  --scrape-mode all \
  --follow-pdfs True \
  --output-dir ./output
```

---

## 🌐 Web API Service (FastAPI)

Automation Hub provides a full REST API for programmatic automation:

```bash
# Start FastAPI application
python -m uvicorn webapp:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation is available at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/scrape` | Execute a synchronous web scrape |
| `POST` | `/api/pdf` | Process uploaded PDF document |
| `POST` | `/api/pipeline` | Run complete scrape + PDF pipeline |
| `POST` | `/api/jobs/scrape` | Enqueue background asynchronous scrape |
| `POST` | `/api/jobs/pdf` | Enqueue background asynchronous PDF task |
| `GET` | `/api/jobs/{job_id}` | Check status and results of background job |
| `GET` | `/api/jobs/history` | Retrieve paginated job execution history |
| `GET` | `/api/health` | Service health check |

---

## 🐳 Docker & Kubernetes Deployment

### Run with Docker Compose

Spin up the complete distributed stack (FastAPI web app + Celery worker + Redis broker):

```bash
docker compose up --build
```

Scale worker nodes dynamically:
```bash
docker compose up --build --scale worker=3
```

### Deploy to Kubernetes

Production-ready Kubernetes configurations are located in `k8s/`:

```bash
kubectl apply -f k8s/
```

---

## 🧪 Automated Testing

The repository features 68 automated unit and integration tests verifying parsers, fetchers, exporters, PDF engines, error recovery, and Gemini AI fallback cascades:

```bash
pytest tests/ -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\...\automation_hub
configfile: pytest.ini
plugins: anyio-4.15.1, mock-3.15.1
collected 68 items

tests/test_pdf.py ................................                       [ 47%]
tests/test_pipeline.py ............                                      [ 64%]
tests/test_scraper.py .....................                              [ 95%]
tests/test_summarizer.py ...                                             [100%]

============================= 68 passed in 2.12s ==============================
```

---

## 👤 Author & Architecture

**Rahul Roy**  
*Final-Year B.Tech CSE, KIIT University*  
- **GitHub**: [@Rahul03ll](https://github.com/Rahul03ll)  
- **LinkedIn**: [linkedin.com/in/rahul-roy-362a12256](https://linkedin.com/in/rahul-roy-362a12256)  
- **Email**: rahulroy2259@gmail.com  

---

## 📜 License

This project is open source and licensed under the [MIT License](LICENSE).
