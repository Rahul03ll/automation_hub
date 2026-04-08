#!/usr/bin/env python3
"""
web_scraper.py
CLI entrypoint for the Automation Hub web scraper.

Usage examples:
  python web_scraper.py --url https://example.com
  python web_scraper.py --url https://news.ycombinator.com --mode links --format csv
  python web_scraper.py --url https://example.com --mode custom --selector "article h2" --format md
  python web_scraper.py --url https://example.com --mode all --format json --output result.json
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Make sure package root is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    SCRAPER_DELAY,
    SCRAPER_RETRIES,
    SCRAPER_TIMEOUT,
    SCRAPER_VALID_FORMATS,
    SCRAPER_VALID_MODES,
    DEFAULT_OUTPUT_DIR,
    configure_logging,
)
from scraper.exporter import auto_filename, export
from scraper.fetcher import fetch_html
from scraper.parser import extract, parse_html


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Automation Hub — Web Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--url", required=True, help="Target URL to scrape")
    p.add_argument(
        "--mode",
        default="all",
        choices=SCRAPER_VALID_MODES,
        help="Extraction mode (default: all)",
    )
    p.add_argument(
        "--selector",
        default="",
        help="CSS selector — required when --mode custom",
    )
    p.add_argument(
        "--format",
        default="json",
        choices=SCRAPER_VALID_FORMATS,
        help="Output format (default: json)",
    )
    p.add_argument("--output", default=None, help="Output file path (auto-generated if omitted)")
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for auto-generated output files (default: ./output)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=SCRAPER_DELAY,
        help="Polite delay in seconds before requesting (default: 0)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=SCRAPER_TIMEOUT,
        help=f"Request timeout in seconds (default: {SCRAPER_TIMEOUT})",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=SCRAPER_RETRIES,
        help=f"Retry attempts on failure (default: {SCRAPER_RETRIES})",
    )
    p.add_argument(
        "--no-clean",
        action="store_true",
        help="Disable whitespace normalisation",
    )
    p.add_argument(
        "--include-meta",
        action="store_true",
        help="Include <meta> tags in 'all' mode output",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(args.log_level)
    import logging
    log = logging.getLogger(__name__)

    # Validation
    if args.mode == "custom" and not args.selector:
        parser.error("--selector is required when --mode is 'custom'")

    # Determine output path
    if args.output:
        outfile = args.output
    else:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = auto_filename(args.mode, args.format, prefix="scraped")
        outfile = str(out_dir / filename)
    log.info(f"Starting scrape: {args.url}  mode={args.mode}  format={args.format}")

    # Fetch
    try:
        html = fetch_html(args.url, timeout=args.timeout, delay=args.delay)
    except Exception as e:
        log.error(f"Fetch failed: {e}")
        return 1

    # Parse & extract
    soup = parse_html(html, base_url=args.url)
    data = extract(
        soup,
        mode=args.mode,
        base_url=args.url,
        selector=args.selector,
        clean=not args.no_clean,
        include_meta=args.include_meta,
    )

    # Export
    metadata = {
        "url": args.url,
        "mode": args.mode,
        "scraped_at": datetime.now().isoformat(),
        "selector": args.selector or None,
    }
    try:
        out_path = export(data, fmt=args.format, outfile=outfile, metadata=metadata)
    except Exception as e:
        log.error(f"Export failed: {e}")
        return 1

    print(f"\nDone.\n  Output: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
