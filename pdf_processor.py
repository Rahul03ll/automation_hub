#!/usr/bin/env python3
"""
pdf_processor.py
CLI entrypoint for the Automation Hub PDF processor.

Usage examples:
  python pdf_processor.py --file report.pdf
  python pdf_processor.py --file report.pdf --op summarize --format md
  python pdf_processor.py --file report.pdf --op all --pages 1-10 --format json
  python pdf_processor.py --url https://example.com/doc.pdf --op extract --format txt
  python pdf_processor.py --file report.pdf --op summarize --ai-prompt "List all action items"
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    PDF_VALID_FORMATS,
    PDF_VALID_OPS,
    DEFAULT_OUTPUT_DIR,
    GOOGLE_MODEL,
    configure_logging,
)
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Automation Hub — PDF Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="Local PDF file path")
    source.add_argument("--url", help="URL to a remote PDF (downloaded automatically)")

    p.add_argument(
        "--op",
        default="all",
        choices=PDF_VALID_OPS,
        help="Operation to perform (default: all)",
    )
    p.add_argument(
        "--pages",
        default="all",
        help="Page range: 'all', '1-5', '1,3,7', '3-' (default: all)",
    )
    p.add_argument(
        "--format",
        default="md",
        choices=PDF_VALID_FORMATS,
        help="Output format (default: md)",
    )
    p.add_argument("--output", default=None, help="Output file path (auto-generated if omitted)")
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for auto-generated output files (default: ./output)",
    )
    p.add_argument(
        "--ai-prompt",
        default=None,
        help="Custom prompt for AI summarization (op=summarize or all)",
    )
    p.add_argument(
        "--model",
        default=GOOGLE_MODEL,
        help=f"Gemini model for AI summarization (default: {GOOGLE_MODEL})",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(args.log_level)
    import logging
    log = logging.getLogger(__name__)

    # ── Resolve source file ──────────────────────────────────────────────────
    if args.url:
        log.info(f"Downloading PDF from {args.url} ...")
        try:
            downloads_dir = str(Path(args.output_dir) / "pdfs")
            local_file = download_pdf(args.url, dest_dir=downloads_dir)
        except Exception as e:
            log.error(f"Download failed: {e}")
            return 1
        source_label = args.url
    else:
        local_file = args.file
        source_label = args.file

    # ── Open & process ───────────────────────────────────────────────────────
    text_pages: dict = {}
    tables: list = []
    summary: str = ""

    try:
        with open_pdf(local_file) as pdf:
            info = get_pdf_info(pdf)
            log.info(
                f"PDF: {info['total_pages']} pages"
                + (f"  title='{info['title']}'" if info["title"] else "")
            )

            page_indices = parse_page_range(args.pages, info["total_pages"])
            log.info(f"Processing pages: {_describe_range(page_indices, info['total_pages'])}")

            if args.op in ("extract", "all", "summarize"):
                text_pages = extract_text(pdf, page_indices)

            if args.op in ("tables", "all"):
                tables = extract_tables(pdf, page_indices)

            if args.op in ("summarize", "all"):
                if text_pages:
                    summary = summarize_pages(text_pages, prompt=args.ai_prompt, model=args.model)
                else:
                    log.warning("No text extracted — skipping AI summarization")

    except FileNotFoundError as e:
        log.error(str(e))
        return 1
    except Exception as e:
        log.error(f"PDF processing error: {e}")
        return 1

    # ── Export ───────────────────────────────────────────────────────────────
    if args.output:
        outfile = args.output
    else:
        # Keep all PDF processor outputs under a consistent subfolder.
        out_dir = Path(args.output_dir) / "pdf"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = pdf_exporter.auto_filename(local_file, args.op, args.format)
        outfile = str(out_dir / filename)

    metadata = {
        "source": source_label,
        "op": args.op,
        "page_range": args.pages,
        "total_pages": info["total_pages"] if "info" in dir() else "?",
        "model": args.model if args.op in ("summarize", "all") else None,
        "processed_at": datetime.now().isoformat(),
    }

    try:
        out_path = pdf_exporter.export(
            text_pages=text_pages,
            tables=tables,
            summary=summary,
            fmt=args.format,
            outfile=outfile,
            metadata=metadata,
        )
    except Exception as e:
        log.error(f"Export failed: {e}")
        return 1

    has_summary = bool(summary and not summary.strip().startswith("["))

    print(f"\nDone.")
    print(f"  Pages processed:  {len(text_pages) or '—'}")
    print(f"  Tables extracted: {len(tables)}")
    print(f"  AI summary:       {'yes' if has_summary else 'no'}")
    print(f"  Output:           {out_path}")
    return 0


def _describe_range(indices: list, total: int) -> str:
    if len(indices) == total:
        return f"all ({total})"
    return f"{len(indices)} of {total}"


if __name__ == "__main__":
    sys.exit(main())
