"""
pipeline/runner.py
End-to-end orchestration: scrape → optionally detect PDFs → process them → unified report.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)


def run(
    url: str,
    scrape_mode: str = "all",
    scrape_format: str = "json",
    follow_pdfs: bool = False,
    pdf_op: str = "all",
    pdf_format: str = "md",
    output_dir: str = "./output",
    delay: float = 0,
    ai_prompt: Optional[str] = None,
) -> dict:
    """
    Full automation pipeline.

    Steps:
      1. Scrape the given URL.
      2. If the URL ends in .pdf, also run PDF processing on a downloaded copy.
      3. If follow_pdfs=True, find all .pdf links on the scraped page and process each.
      4. Write all outputs to output_dir.
      5. Return a manifest dict describing every output file.

    Returns:
        Manifest dict:
        {
          "started_at": str,
          "completed_at": str,
          "url": str,
          "outputs": [{"type": str, "file": str, "source": str}, ...]
        }
    """
    from scraper.fetcher import fetch_html
    from scraper.parser import parse_html, extract
    from scraper.exporter import export as scraper_export, auto_filename as scraper_autoname

    base_out_dir = Path(output_dir)
    base_out_dir.mkdir(parents=True, exist_ok=True)
    pipeline_out_dir = base_out_dir
    pdf_out_dir = base_out_dir / "pdf"
    pdf_out_dir.mkdir(parents=True, exist_ok=True)
    pdf_downloads_dir = base_out_dir / "pdfs"
    pdf_downloads_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "started_at": datetime.now().isoformat(),
        "url": url,
        "outputs": [],
    }

    # ── Step 1: Scrape ──────────────────────────────────────────────────────
    log.info(f"[Pipeline] Scraping {url} (mode={scrape_mode}) ...")
    try:
        html = fetch_html(url, delay=delay)
        soup = parse_html(html, base_url=url)
        data = extract(soup, mode=scrape_mode, base_url=url)

        scrape_file = pipeline_out_dir / scraper_autoname(scrape_mode, scrape_format, prefix="scraped")
        scraper_export(
            data,
            fmt=scrape_format,
            outfile=str(scrape_file),
            metadata={
                "url": url,
                "mode": scrape_mode,
                "scraped_at": datetime.now().isoformat(),
            },
        )
        manifest["outputs"].append({"type": "scrape", "file": str(scrape_file), "source": url})
        log.info(f"[Pipeline] Scrape saved → {scrape_file}")

    except Exception as e:
        log.error(f"[Pipeline] Scrape failed: {e}")
        manifest["errors"] = manifest.get("errors", []) + [f"scrape: {e}"]

    # ── Step 2: If URL is a direct PDF, process it ─────────────────────────
    if _is_pdf_url(url):
        log.info(f"[Pipeline] URL appears to be a PDF — downloading and processing ...")
        pdf_out = _process_remote_pdf(
            url=url,
            op=pdf_op,
            fmt=pdf_format,
            pdf_out_dir=pdf_out_dir,
            downloads_dir=pdf_downloads_dir,
            ai_prompt=ai_prompt,
        )
        if pdf_out:
            manifest["outputs"].append({"type": "pdf", "file": pdf_out, "source": url})

    # ── Step 3: Follow PDF links found on the page ─────────────────────────
    if follow_pdfs and not _is_pdf_url(url):
        pdf_links = _find_pdf_links(data, base_url=url)
        if pdf_links:
            log.info(f"[Pipeline] Found {len(pdf_links)} PDF link(s) — processing ...")
        for pdf_url in pdf_links:
            pdf_out = _process_remote_pdf(
                url=pdf_url,
                op=pdf_op,
                fmt=pdf_format,
                pdf_out_dir=pdf_out_dir,
                downloads_dir=pdf_downloads_dir,
                ai_prompt=ai_prompt,
            )
            if pdf_out:
                manifest["outputs"].append({"type": "pdf", "file": pdf_out, "source": pdf_url})

    # ── Finalise manifest ───────────────────────────────────────────────────
    manifest["completed_at"] = datetime.now().isoformat()

    report_path = base_out_dir / f"pipeline_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info(f"[Pipeline] Complete. Manifest → {report_path}")

    # Print summary to stdout
    _print_summary(manifest)
    return manifest


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_pdf_url(url: str) -> bool:
    """Heuristic: does the URL path end in .pdf (ignoring query string)?"""
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


def _find_pdf_links(data, base_url: str = "") -> list:
    """
    Extract .pdf href values from scraped data.
    Works whether data is a list of link dicts or an 'all'-mode dict.
    """
    links = []
    if isinstance(data, dict):
        links = data.get("links", [])
    elif isinstance(data, list) and data and isinstance(data[0], dict) and "href" in data[0]:
        links = data
    return [
        urljoin(base_url, lnk["href"])
        for lnk in links
        if isinstance(lnk, dict) and lnk.get("href", "").lower().endswith(".pdf")
    ]


def _process_remote_pdf(
    url: str,
    op: str,
    fmt: str,
    pdf_out_dir: Path,
    downloads_dir: Path,
    ai_prompt: Optional[str] = None,
) -> Optional[str]:
    """Download a PDF from URL and run the PDF processor on it. Returns output path or None."""
    from pdf_processor.reader import download_pdf, open_pdf, parse_page_range, extract_text, get_pdf_info
    from pdf_processor.table_extractor import extract_tables
    from pdf_processor.summarizer import summarize_pages
    from pdf_processor import exporter as pdf_exporter

    try:
        local_path = download_pdf(url, dest_dir=str(downloads_dir))
    except Exception as e:
        log.error(f"[Pipeline] Failed to download {url}: {e}")
        return None

    try:
        with open_pdf(local_path) as pdf:
            info = get_pdf_info(pdf)
            all_pages = parse_page_range("all", info["total_pages"])

            text_pages = {}
            tables = []
            summary = ""

            if op in ("extract", "all"):
                text_pages = extract_text(pdf, all_pages)
            if op in ("tables", "all"):
                tables = extract_tables(pdf, all_pages)
            if op in ("summarize", "all") and text_pages:
                summary = summarize_pages(text_pages, prompt=ai_prompt)

        outfile = pdf_out_dir / pdf_exporter.auto_filename(local_path, op, fmt)
        pdf_exporter.export(
            text_pages=text_pages,
            tables=tables,
            summary=summary,
            fmt=fmt,
            outfile=str(outfile),
            metadata={
                "source": url,
                "local_file": local_path,
                "op": op,
                "page_range": "all",
                "total_pages": info["total_pages"],
                "processed_at": datetime.now().isoformat(),
            },
        )
        return str(outfile)

    except Exception as e:
        log.error(f"[Pipeline] PDF processing failed for {local_path}: {e}")
        return None


def _print_summary(manifest: dict) -> None:
    print("\n" + "=" * 50)
    print("Pipeline complete")
    print("=" * 50)
    print(f"  URL:      {manifest['url']}")
    print(f"  Started:  {manifest['started_at']}")
    print(f"  Finished: {manifest.get('completed_at', '?')}")
    print(f"  Outputs:")
    for o in manifest["outputs"]:
        print(f"    [{o['type']:6s}] {o['file']}")
    if "errors" in manifest:
        print("  Errors:")
        for e in manifest["errors"]:
            print(f"    ✗ {e}")
    print("=" * 50 + "\n")
