"""
config/settings.py
Centralized configuration for Automation Hub.
Values are loaded from environment variables (or .env file), with sensible defaults.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)

# ── Output ────────────────────────────────────────────────────────────────────
# Default output directory for all CLI entrypoints (scraper, pdf processor, pipeline).
DEFAULT_OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./output")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", f"{DEFAULT_OUTPUT_DIR}/uploads")


# ── Google (Gemini / Generative Language API) ────────────────────────────────
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")

# ── Scraper ──────────────────────────────────────────────────────────────────
SCRAPER_USER_AGENT: str = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; AutomationHub/1.0; +https://github.com/you/automation-hub)",
)
SCRAPER_TIMEOUT: int = int(os.getenv("SCRAPER_TIMEOUT", "15"))
SCRAPER_RETRIES: int = int(os.getenv("SCRAPER_RETRIES", "3"))
SCRAPER_DELAY: float = float(os.getenv("SCRAPER_DELAY", "0"))

# TLS / HTTPS verification controls.
# Default keeps verification ON; if it fails, we can do a single fallback attempt with verify=False
# (helps in environments with misconfigured corporate CA chains).
SCRAPER_VERIFY_SSL: bool = os.getenv("SCRAPER_VERIFY_SSL", "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
)
SCRAPER_ALLOW_INSECURE_SSL_FALLBACK: bool = os.getenv(
    "SCRAPER_ALLOW_INSECURE_SSL_FALLBACK", "true"
).strip().lower() in ("1", "true", "yes", "y")
SCRAPER_CA_BUNDLE: str = os.getenv("SCRAPER_CA_BUNDLE", "")

SCRAPER_DEFAULT_HEADERS: dict = {
    "User-Agent": SCRAPER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

SCRAPER_VALID_MODES: tuple = (
    "all",
    "essential",
    "links",
    "text",
    "images",
    "tables",
    "meta",
    "custom",
)
SCRAPER_VALID_FORMATS: tuple = ("json", "csv", "txt", "md")

# ── PDF Processor ─────────────────────────────────────────────────────────────
PDF_MAX_PAGES: int = int(os.getenv("PDF_MAX_PAGES", "500"))
PDF_AI_MAX_CHARS: int = int(os.getenv("PDF_AI_MAX_CHARS", "8000"))
PDF_DEFAULT_AI_PROMPT: str = (
    "Summarize this document concisely. "
    "Include: main topic, key findings or arguments, and any clear action items or conclusions."
)
PDF_VALID_OPS: tuple = ("extract", "summarize", "tables", "all")
PDF_VALID_FORMATS: tuple = ("txt", "json", "md", "csv")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ── Web/App scalability ───────────────────────────────────────────────────────
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
APP_WORKERS: int = int(os.getenv("APP_WORKERS", "2"))
ENABLE_CORS: bool = os.getenv("ENABLE_CORS", "true").strip().lower() in ("1", "true", "yes", "y")
ALLOWED_ORIGINS: list[str] = [s.strip() for s in os.getenv("ALLOWED_ORIGINS", "*").split(",") if s.strip()]

# Celery/Redis (for async jobs)
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Security + persistence
REQUIRE_API_KEY: bool = os.getenv("REQUIRE_API_KEY", "true").strip().lower() in ("1", "true", "yes", "y")
ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
APP_DB_PATH: str = os.getenv("APP_DB_PATH", str(Path(__file__).parent.parent / "app.db"))


def configure_logging(level: str = LOG_LEVEL) -> None:
    """Call once at application startup to configure root logging."""
    numeric = getattr(logging, level, logging.INFO)
    logging.basicConfig(
        level=numeric,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    # Quieten noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
