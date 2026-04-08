#!/usr/bin/env python3
"""
webapp.py
FastAPI web application for Automation Hub.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app_db import create_api_key, has_api_keys, init_db, insert_job, list_jobs, update_job, validate_api_key
from config.settings import ADMIN_API_KEY, ALLOWED_ORIGINS, DEFAULT_OUTPUT_DIR, ENABLE_CORS, REQUIRE_API_KEY
from pipeline.runner import run as run_pipeline
from pdf_processor import exporter as pdf_exporter
from pdf_processor.reader import (
    download_pdf,
    extract_text,
    get_pdf_info,
    open_pdf,
    parse_page_range,
)
from pdf_processor.summarizer import summarize_pages
from pdf_processor.table_extractor import extract_tables
from scraper.exporter import auto_filename as scraper_auto_filename, export as scraper_export
from scraper.fetcher import fetch_html
from scraper.parser import extract as scrape_extract, parse_html


ROOT = Path(__file__).parent
WEB_DIR = ROOT / "webapp_static"
OUTPUT_ROOT = ROOT / DEFAULT_OUTPUT_DIR
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / "uploads").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Automation Hub Web App", version="1.0.0")
if ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if ALLOWED_ORIGINS == ["*"] else ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")
app.mount("/output", StaticFiles(directory=str(OUTPUT_ROOT)), name="output")


try:
    from tasks import pdf_job, pipeline_job, scrape_job  # type: ignore
except Exception:  # pragma: no cover
    pdf_job = pipeline_job = scrape_job = None


class ScrapeRequest(BaseModel):
    url: str
    mode: str = "all"
    format: str = "json"
    selector: str = ""
    include_meta: bool = False
    no_clean: bool = False
    output_dir: str = DEFAULT_OUTPUT_DIR


class PipelineRequest(BaseModel):
    url: str
    scrape_mode: str = "all"
    scrape_format: str = "json"
    follow_pdfs: bool = False
    pdf_op: str = "all"
    pdf_format: str = "md"
    output_dir: str = DEFAULT_OUTPUT_DIR
    delay: float = 0
    ai_prompt: Optional[str] = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if not REQUIRE_API_KEY:
        return await call_next(request)
    path = request.url.path
    if path in ("/", "/api/health") or path.startswith("/assets/") or path.startswith("/output/"):
        return await call_next(request)
    if path.startswith("/api/"):
        if path == "/api/admin/api-keys":
            if not has_api_keys():
                return await call_next(request)
            admin_hdr = request.headers.get("X-Admin-Key", "")
            if ADMIN_API_KEY and admin_hdr == ADMIN_API_KEY:
                return await call_next(request)
            client_host = (request.client.host if request.client else "") or ""
            if not ADMIN_API_KEY and client_host in {"127.0.0.1", "localhost", "testclient"}:
                return await call_next(request)
        provided = request.headers.get("X-API-Key", "")
        if not provided or not validate_api_key(provided):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/admin/api-keys")
def api_create_key(name: str = Form("default")) -> dict:
    created = create_api_key(name=name)
    return {"ok": True, "api_key": created}


@app.get("/api/jobs/history")
def api_jobs_history(limit: int = 50) -> dict:
    return {"ok": True, "items": list_jobs(limit=limit)}


@app.post("/api/scrape")
def api_scrape(req: ScrapeRequest) -> dict:
    out_dir = ROOT / req.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_html(req.url)
    soup = parse_html(html, base_url=req.url)
    data = scrape_extract(
        soup,
        mode=req.mode,
        base_url=req.url,
        selector=req.selector,
        clean=not req.no_clean,
        include_meta=req.include_meta,
    )
    out_name = scraper_auto_filename(req.mode, req.format, prefix="scraped")
    out_path = out_dir / out_name
    scraper_export(
        data,
        fmt=req.format,
        outfile=str(out_path),
        metadata={
            "url": req.url,
            "mode": req.mode,
            "scraped_at": datetime.now().isoformat(),
            "selector": req.selector or None,
        },
    )
    return {
        "ok": True,
        "output_file": str(out_path.relative_to(ROOT)),
        "download_url": f"/output/{out_path.relative_to(OUTPUT_ROOT).as_posix()}",
    }


@app.post("/api/pipeline")
def api_pipeline(req: PipelineRequest) -> dict:
    manifest = run_pipeline(
        url=req.url,
        scrape_mode=req.scrape_mode,
        scrape_format=req.scrape_format,
        follow_pdfs=req.follow_pdfs,
        pdf_op=req.pdf_op,
        pdf_format=req.pdf_format,
        output_dir=str(ROOT / req.output_dir),
        delay=req.delay,
        ai_prompt=req.ai_prompt,
    )
    return {"ok": "errors" not in manifest, "manifest": manifest}


@app.post("/api/jobs/scrape")
def api_scrape_job(req: ScrapeRequest) -> dict:
    if scrape_job is None:
        raise HTTPException(status_code=503, detail="Async worker not available")
    try:
        task = scrape_job.delay(req.model_dump())
    except Exception:
        result = scrape_job.run(req.model_dump())
        return {"ok": True, "mode": "sync_fallback", "result": result}
    insert_job(task.id, "scrape", "PENDING", req.model_dump())
    return {"ok": True, "job_id": task.id}


@app.post("/api/jobs/pipeline")
def api_pipeline_job(req: PipelineRequest) -> dict:
    if pipeline_job is None:
        raise HTTPException(status_code=503, detail="Async worker not available")
    try:
        task = pipeline_job.delay(req.model_dump())
    except Exception:
        result = pipeline_job.run(req.model_dump())
        return {"ok": True, "mode": "sync_fallback", "result": result}
    insert_job(task.id, "pipeline", "PENDING", req.model_dump())
    return {"ok": True, "job_id": task.id}


@app.post("/api/pdf")
async def api_pdf(
    op: str = Form("all"),
    fmt: str = Form("md"),
    pages: str = Form("all"),
    ai_prompt: Optional[str] = Form(None),
    model: str = Form("gemini-1.5-flash"),
    source_url: Optional[str] = Form(None),
    source_file: Optional[UploadFile] = File(None),
    output_dir: str = Form(DEFAULT_OUTPUT_DIR),
) -> dict:
    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not source_url and not source_file:
        raise HTTPException(status_code=400, detail="Provide source_url or source_file")

    if source_url and source_file:
        raise HTTPException(status_code=400, detail="Provide only one source")

    local_file: str
    source_label: str
    if source_url:
        local_file = download_pdf(source_url, dest_dir=str(out_dir / "pdfs"))
        source_label = source_url
    else:
        upload_name = source_file.filename or f"upload-{uuid.uuid4().hex}.pdf"
        target = OUTPUT_ROOT / "uploads" / upload_name
        target.write_bytes(await source_file.read())
        local_file = str(target)
        source_label = upload_name

    text_pages: dict = {}
    tables: list = []
    summary: str = ""

    with open_pdf(local_file) as pdf:
        info = get_pdf_info(pdf)
        page_indices = parse_page_range(pages, info["total_pages"])
        if op in ("extract", "all", "summarize"):
            text_pages = extract_text(pdf, page_indices)
        if op in ("tables", "all"):
            tables = extract_tables(pdf, page_indices)
        if op in ("summarize", "all") and text_pages:
            summary = summarize_pages(text_pages, prompt=ai_prompt, model=model)

    out_pdf_dir = out_dir / "pdf"
    out_pdf_dir.mkdir(parents=True, exist_ok=True)
    out_name = pdf_exporter.auto_filename(local_file, op, fmt)
    out_path = out_pdf_dir / out_name
    pdf_exporter.export(
        text_pages=text_pages,
        tables=tables,
        summary=summary,
        fmt=fmt,
        outfile=str(out_path),
        metadata={
            "source": source_label,
            "op": op,
            "page_range": pages,
            "processed_at": datetime.now().isoformat(),
        },
    )
    return {
        "ok": True,
        "output_file": str(out_path.relative_to(ROOT)),
        "download_url": f"/output/{out_path.relative_to(OUTPUT_ROOT).as_posix()}",
        "tables_extracted": len(tables),
        "has_summary": bool(summary and not summary.strip().startswith("[")),
    }


@app.post("/api/jobs/pdf")
async def api_pdf_job(
    op: str = Form("all"),
    fmt: str = Form("md"),
    pages: str = Form("all"),
    ai_prompt: Optional[str] = Form(None),
    model: str = Form("gemini-1.5-flash"),
    source_url: Optional[str] = Form(None),
    source_file: Optional[UploadFile] = File(None),
    output_dir: str = Form(DEFAULT_OUTPUT_DIR),
) -> dict:
    if pdf_job is None:
        raise HTTPException(status_code=503, detail="Async worker not available")
    if not source_url and not source_file:
        raise HTTPException(status_code=400, detail="Provide source_url or source_file")
    if source_url and source_file:
        raise HTTPException(status_code=400, detail="Provide only one source")

    local_file = ""
    source_label = ""
    if source_url:
        source_label = source_url
    else:
        upload_name = source_file.filename or f"upload-{uuid.uuid4().hex}.pdf"
        target = OUTPUT_ROOT / "uploads" / upload_name
        target.write_bytes(await source_file.read())
        local_file = str(target)
        source_label = upload_name
    try:
        task = pdf_job.delay(
            {
                "op": op,
                "fmt": fmt,
                "pages": pages,
                "ai_prompt": ai_prompt,
                "model": model,
                "source_url": source_url,
                "local_file": local_file,
                "source_label": source_label,
                "output_dir": output_dir,
            }
        )
    except Exception:
        result = pdf_job.run(
            {
                "op": op,
                "fmt": fmt,
                "pages": pages,
                "ai_prompt": ai_prompt,
                "model": model,
                "source_url": source_url,
                "local_file": local_file,
                "source_label": source_label,
                "output_dir": output_dir,
            }
        )
        return {"ok": True, "mode": "sync_fallback", "result": result}
    insert_job(
        task.id,
        "pdf",
        "PENDING",
        {
            "op": op,
            "fmt": fmt,
            "pages": pages,
            "source_url": source_url,
            "source_label": source_label,
        },
    )
    return {"ok": True, "job_id": task.id}


@app.get("/api/jobs/{job_id}")
def api_job_status(job_id: str) -> dict:
    if scrape_job is None:
        raise HTTPException(status_code=503, detail="Async worker not available")
    result = scrape_job.AsyncResult(job_id)
    payload = {"job_id": job_id, "status": result.status}
    if result.successful():
        payload["result"] = result.result
        update_job(job_id, result.status, result=result.result)
    elif result.failed():
        payload["error"] = str(result.result)
        update_job(job_id, result.status, error=str(result.result))
    else:
        update_job(job_id, result.status)
    return payload
