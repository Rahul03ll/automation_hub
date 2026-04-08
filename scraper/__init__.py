"""
scraper — Web scraping module for Automation Hub.

Public API:
    scrape(url, mode, **kwargs) -> dict | list
    scrape_and_export(url, mode, fmt, outfile, **kwargs) -> Path
"""
from scraper.fetcher import fetch_html
from scraper.parser import parse_html, extract
from scraper.exporter import export, auto_filename


def scrape(
    url: str,
    mode: str = "all",
    selector: str = "",
    clean: bool = True,
    include_meta: bool = False,
    delay: float = 0,
    timeout: int = 15,
):
    """High-level: fetch + parse + extract in one call."""
    html = fetch_html(url, timeout=timeout, delay=delay)
    soup = parse_html(html, base_url=url)
    return extract(soup, mode=mode, base_url=url, selector=selector,
                   clean=clean, include_meta=include_meta)


def scrape_and_export(url, mode="all", fmt="json", outfile=None, **scrape_kwargs):
    """Scrape a URL and write the result to a file. Returns output Path."""
    from datetime import datetime
    data = scrape(url, mode=mode, **scrape_kwargs)
    if outfile is None:
        outfile = auto_filename(mode, fmt)
    return export(data, fmt=fmt, outfile=outfile,
                  metadata={"url": url, "mode": mode, "scraped_at": datetime.now().isoformat()})


__all__ = ["scrape", "scrape_and_export", "fetch_html", "parse_html", "extract", "export", "auto_filename"]
