"""
scraper/parser.py
HTML parsing and content extraction using BeautifulSoup.
Supports: all, essential, links, text, images, tables, meta, custom CSS selector.
"""
import logging
import re
import json
from typing import Any, Union
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def parse_html(html: str, base_url: str = "") -> BeautifulSoup:
    """
    Parse raw HTML into a BeautifulSoup tree.
    Uses lxml if available for speed, falls back to html.parser.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    return soup


def extract(
    soup: BeautifulSoup,
    mode: str,
    base_url: str = "",
    selector: str = "",
    clean: bool = True,
    include_meta: bool = False,
) -> Union[dict, list]:
    """
    Extract content from a parsed page.

    Args:
        soup:         Parsed BeautifulSoup document.
        mode:         Extraction mode (all/links/text/images/tables/meta/custom).
        base_url:     Used to resolve relative URLs.
        selector:     CSS selector string (mode='custom' only).
        clean:        Strip excess whitespace from text content.
        include_meta: Attach page metadata to 'all' result.

    Returns:
        A dict (mode='all') or list of dicts for all other modes.
    """
    dispatch = {
        "essential": _extract_essential,
        "links":  _extract_links,
        "text":   _extract_text,
        "images": _extract_images,
        "tables": _extract_tables,
        "meta":   _extract_meta,
        "custom": _extract_custom,
        "all":    _extract_all,
    }

    if mode not in dispatch:
        raise ValueError(f"Unknown mode '{mode}'. Valid: {list(dispatch)}")

    # Keep <script> content around for 'essential' so we can parse embedded JSON on sites
    # like YouTube. For other modes we can safely remove it.
    if mode != "essential":
        _remove_noise(soup)

    kwargs: dict[str, Any] = {"soup": soup, "base_url": base_url, "clean": clean}
    if mode == "custom":
        kwargs["selector"] = selector
    if mode == "all":
        kwargs["include_meta"] = include_meta

    result = dispatch[mode](**kwargs)
    _log_summary(mode, result)
    return result


# ── Mode implementations ──────────────────────────────────────────────────────

def _extract_links(soup: BeautifulSoup, base_url: str = "", clean: bool = True, **_) -> list:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "#", "")):
            if href.startswith("javascript:"):
                continue
        abs_href = urljoin(base_url, href) if base_url else href
        text = _clean(a.get_text()) if clean else a.get_text()
        links.append({
            "text":  text,
            "href":  abs_href,
            "title": a.get("title", ""),
            "rel":   " ".join(a.get("rel", [])),
        })
    return links


def _extract_text(soup: BeautifulSoup, clean: bool = True, **_) -> list:
    items = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
        text = _clean(tag.get_text()) if clean else tag.get_text()
        if text:
            items.append({"tag": tag.name, "content": text})
    return items


def _extract_images(soup: BeautifulSoup, base_url: str = "", **_) -> list:
    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        if not src:
            continue
        abs_src = urljoin(base_url, src) if base_url else src
        images.append({
            "src":    abs_src,
            "alt":    img.get("alt", ""),
            "title":  img.get("title", ""),
            "width":  img.get("width", ""),
            "height": img.get("height", ""),
        })
    return images


def _extract_tables(soup: BeautifulSoup, clean: bool = True, **_) -> list:
    tables = []
    for idx, table in enumerate(soup.find_all("table")):
        rows = []
        for tr in table.find_all("tr"):
            cells = [
                (_clean(td.get_text()) if clean else td.get_text())
                for td in tr.find_all(["td", "th"])
            ]
            if any(cells):
                rows.append(cells)
        if rows:
            # First row treated as header if it contains <th> elements
            has_header = bool(table.find("th"))
            tables.append({
                "table_index": idx,
                "caption":     _clean(table.find("caption").get_text()) if table.find("caption") else "",
                "has_header":  has_header,
                "rows":        rows,
            })
    return tables


def _extract_meta(soup: BeautifulSoup, **_) -> list:
    meta_tags = []
    for m in soup.find_all("meta"):
        entry = {
            "name":       m.get("name", ""),
            "property":   m.get("property", ""),
            "content":    m.get("content", ""),
            "http_equiv": m.get("http-equiv", ""),
            "charset":    m.get("charset", ""),
        }
        if any(entry.values()):
            meta_tags.append(entry)
    return meta_tags


def _extract_custom(soup: BeautifulSoup, selector: str = "", clean: bool = True, **_) -> list:
    if not selector:
        raise ValueError("CSS selector required for mode='custom'")
    items = []
    for i, el in enumerate(soup.select(selector)):
        text = _clean(el.get_text()) if clean else el.get_text()
        items.append({
            "index":   i,
            "tag":     el.name,
            "content": text,
            "html":    str(el)[:500],   # truncated raw HTML for reference
        })
    return items


def _extract_all(
    soup: BeautifulSoup,
    base_url: str = "",
    clean: bool = True,
    include_meta: bool = False,
    **_,
) -> dict:
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    result: dict = {
        "title":      title,
        "headings":   [_clean(h.get_text()) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)],
        "paragraphs": [_clean(p.get_text()) for p in soup.find_all("p") if p.get_text(strip=True)],
        "links":      _extract_links(soup, base_url=base_url, clean=clean),
        "images":     _extract_images(soup, base_url=base_url),
        "tables":     _extract_tables(soup, clean=clean),
    }
    if include_meta:
        result["meta"] = _extract_meta(soup)
    return result


def _extract_essential(
    soup: BeautifulSoup,
    base_url: str = "",
    clean: bool = True,
    **_,
) -> dict:
    """
    "Essential" extraction: only the most useful fields.

    - For YouTube watch pages: extract structured video metadata from embedded JSON.
    - For other sites: return title + meta description + a short main-text snippet + pdf links.
    """
    if _is_youtube_watch_url(base_url):
        yt = _extract_youtube_watch(soup, url=base_url)
        if yt:
            return yt

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    m = soup.find("meta", attrs={"name": "description"})
    if m and m.get("content"):
        meta_desc = m.get("content", "").strip()

    # Light text snippet (avoid pulling the entire page).
    chunks = []
    for tag in soup.find_all(["h1", "h2", "p", "li"]):
        t = tag.get_text(" ", strip=True)
        if clean:
            t = _clean(t)
        if t:
            chunks.append(t)
        if sum(len(c) for c in chunks) > 2000:
            break
    main_text = "\n".join(chunks).strip()

    # Only keep PDF links (common downstream need).
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].strip()) if base_url else a["href"].strip()
        if href.lower().split("?", 1)[0].endswith(".pdf"):
            pdf_links.append(href)
    pdf_links = list(dict.fromkeys(pdf_links))  # de-dupe keep order

    return {
        "url": base_url,
        "title": title,
        "description": meta_desc,
        "main_text": main_text,
        "pdf_links": pdf_links,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _remove_noise(soup: BeautifulSoup) -> None:
    """Remove script, style, noscript, and comment nodes in-place."""
    # Keep <script> tags; some sites (e.g., YouTube) embed useful JSON in them.
    for tag in soup(["style", "noscript", "iframe"]):
        tag.decompose()


def _clean(text: str) -> str:
    """Normalise whitespace in a text string."""
    return re.sub(r"\s+", " ", text).strip()


def _log_summary(mode: str, result: Union[dict, list]) -> None:
    if isinstance(result, list):
        log.debug(f"Extraction mode='{mode}' → {len(result)} items")
    elif isinstance(result, dict):
        counts = {k: len(v) if isinstance(v, list) else "—" for k, v in result.items()}
        log.debug(f"Extraction mode='{mode}' → {counts}")


def _is_youtube_watch_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.netloc not in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        return False
    return p.path == "/watch" and ("v=" in (p.query or ""))


def _extract_youtube_watch(soup: BeautifulSoup, url: str) -> dict | None:
    """
    Extract key metadata from a YouTube watch HTML document.

    YouTube includes a large JSON blob in the page containing `ytInitialPlayerResponse`.
    We parse that to get stable fields like title, channel, duration, viewCount, etc.
    """
    html = str(soup)

    # Common patterns:
    # - var ytInitialPlayerResponse = {...};
    # - ytInitialPlayerResponse = {...};
    m = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\})\s*;\s*</script>", html, re.DOTALL)
    if not m:
        # Fallback: stop at "};" without requiring </script>
        m = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\})\s*;\s*", html, re.DOTALL)
    if not m:
        return None

    try:
        player = json.loads(m.group(1))
    except Exception:
        return None

    video = (player.get("videoDetails") or {})
    micro = (player.get("microformat") or {}).get("playerMicroformatRenderer", {}) or {}

    # Meta tags as a fallback for thumbnails/title.
    og_title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        og_title = og.get("content", "").strip()

    thumbs = (video.get("thumbnail") or {}).get("thumbnails", []) or []
    thumbnail = thumbs[-1]["url"] if thumbs else ""

    return {
        "platform": "youtube",
        "url": url,
        "video_id": video.get("videoId", ""),
        "title": video.get("title") or og_title,
        "channel": video.get("author", ""),
        "short_description": (video.get("shortDescription") or "")[:4000],
        "duration_seconds": int(video.get("lengthSeconds") or 0),
        "view_count": int(video.get("viewCount") or 0),
        "publish_date": micro.get("publishDate", ""),
        "category": micro.get("category", ""),
        "thumbnail": thumbnail,
        "is_live": bool(video.get("isLiveContent")),
    }
