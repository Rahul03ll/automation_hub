#!/usr/bin/env python3
"""
automation_pipeline.py
CLI entrypoint for the Automation Hub end-to-end pipeline.

Scrapes a URL, optionally follows and processes any PDF links found,
and writes all outputs + a JSON manifest to an output directory.

Usage examples:
  python automation_pipeline.py --url https://example.com
  python automation_pipeline.py --url https://example.com/report.pdf --pdf-op all --format md
  python automation_pipeline.py --url https://example.com --follow-pdfs --output-dir ./results
  python automation_pipeline.py --url https://example.com --scrape-mode links --pdf-op summarize
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    SCRAPER_DELAY,
    SCRAPER_VALID_FORMATS,
    SCRAPER_VALID_MODES,
    PDF_VALID_OPS,
    DEFAULT_OUTPUT_DIR,
    configure_logging,
)
from pipeline.runner import run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Automation Hub — Full Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--url", required=True, help="Starting URL (web page or direct PDF link)")
    p.add_argument(
        "--scrape-mode",
        default="all",
        choices=SCRAPER_VALID_MODES,
        help="Scraper extraction mode (default: all)",
    )
    p.add_argument(
        "--scrape-format",
        default="json",
        choices=SCRAPER_VALID_FORMATS,
        help="Scraper output format (default: json)",
    )
    p.add_argument(
        "--follow-pdfs",
        action="store_true",
        help="Auto-detect and process PDF links found on the scraped page",
    )
    p.add_argument(
        "--pdf-op",
        default="all",
        choices=PDF_VALID_OPS,
        help="PDF processing operation (default: all)",
    )
    p.add_argument(
        "--pdf-format",
        default="md",
        choices=["txt", "json", "md", "csv"],
        help="PDF output format (default: md)",
    )
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for all output files (default: ./output)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=SCRAPER_DELAY,
        help="Polite delay in seconds between requests (default: 0)",
    )
    p.add_argument(
        "--ai-prompt",
        default=None,
        help="Custom AI summarization prompt for PDF processing",
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

    manifest = run(
        url=args.url,
        scrape_mode=args.scrape_mode,
        scrape_format=args.scrape_format,
        follow_pdfs=args.follow_pdfs,
        pdf_op=args.pdf_op,
        pdf_format=args.pdf_format,
        output_dir=args.output_dir,
        delay=args.delay,
        ai_prompt=args.ai_prompt,
    )

    return 0 if "errors" not in manifest else 1


if __name__ == "__main__":
    sys.exit(main())
