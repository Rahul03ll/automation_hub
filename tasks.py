"""
Celery tasks for scalable async processing.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from celery import Celery

from config.settings import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, DEFAULT_OUTPUT_DIR
from pipeline.runner import run as run_pipeline
from pdf_processor import exporter as pdf_exporter
from pdf_processor.reader import download_pdf, extract_text, get_pdf_info, open_pdf, parse_page_range
from pdf_processor.summarizer import summarize_pages
from pdf_processor.table_extractor import extract_tables
from scraper.exporter import auto_filename as scraper_auto_filename, export as scraper_export
from scraper.fetcher import fetch_html
from scraper.parser import extract as scrape_extract, parse_html


celery_app = Celery("automation_hub", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC")

ROOT = Path(__file__).parent


@celery_app.task(name="tasks.scrape_job")
def scrape_job(payload: dict) -> dict:
    out_dir = ROOT / payload.get("output_dir", DEFAULT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    html = fetch_html(payload["url"])
    soup = parse_html(html, base_url=payload["url"])
    data = scrape_extract(
        soup,
        mode=payload.get("mode", "all"),
        base_url=payload["url"],
        selector=payload.get("selector", ""),
        clean=not payload.get("no_clean", False),
        include_meta=payload.get("include_meta", False),
    )
    out_name = scraper_auto_filename(payload.get("mode", "all"), payload.get("format", "json"), prefix="scraped")
    out_path = out_dir / out_name
    scraper_export(data, fmt=payload.get("format", "json"), outfile=str(out_path), metadata={"url": payload["url"], "scraped_at": datetime.now().isoformat()})
    return {"ok": True, "output_file": str(out_path.relative_to(ROOT))}


@celery_app.task(name="tasks.pipeline_job")
def pipeline_job(payload: dict) -> dict:
    manifest = run_pipeline(
        url=payload["url"],
        scrape_mode=payload.get("scrape_mode", "all"),
        scrape_format=payload.get("scrape_format", "json"),
        follow_pdfs=payload.get("follow_pdfs", False),
        pdf_op=payload.get("pdf_op", "all"),
        pdf_format=payload.get("pdf_format", "md"),
        output_dir=str(ROOT / payload.get("output_dir", DEFAULT_OUTPUT_DIR)),
        delay=payload.get("delay", 0),
        ai_prompt=payload.get("ai_prompt"),
    )
    return {"ok": "errors" not in manifest, "manifest": manifest}


@celery_app.task(name="tasks.pdf_job")
def pdf_job(payload: dict) -> dict:
    out_dir = ROOT / payload.get("output_dir", DEFAULT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    local_file = payload["local_file"]
    source_label = payload.get("source_label", local_file)
    if payload.get("source_url"):
        local_file = download_pdf(payload["source_url"], dest_dir=str(out_dir / "pdfs"))
        source_label = payload["source_url"]
    text_pages = {}
    tables = []
    summary = ""
    with open_pdf(local_file) as pdf:
        info = get_pdf_info(pdf)
        page_indices = parse_page_range(payload.get("pages", "all"), info["total_pages"])
        op = payload.get("op", "all")
        if op in ("extract", "all", "summarize"):
            text_pages = extract_text(pdf, page_indices)
        if op in ("tables", "all"):
            tables = extract_tables(pdf, page_indices)
        if op in ("summarize", "all") and text_pages:
            summary = summarize_pages(text_pages, prompt=payload.get("ai_prompt"), model=payload.get("model", "gemini-1.5-flash"))
    out_pdf_dir = out_dir / "pdf"
    out_pdf_dir.mkdir(parents=True, exist_ok=True)
    out_name = pdf_exporter.auto_filename(local_file, payload.get("op", "all"), payload.get("fmt", "md"))
    out_path = out_pdf_dir / out_name
    pdf_exporter.export(text_pages=text_pages, tables=tables, summary=summary, fmt=payload.get("fmt", "md"), outfile=str(out_path), metadata={"source": source_label, "processed_at": datetime.now().isoformat()})
    return {"ok": True, "output_file": str(out_path.relative_to(ROOT)), "tables_extracted": len(tables), "has_summary": bool(summary and not summary.strip().startswith("["))}
