"""
pdf_processor/reader.py
PDF reading and text extraction using pdfplumber.
Handles page-range selection, per-page extraction, and URL downloads.
"""
import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def open_pdf(file_path: str):
    """
    Open a PDF file with pdfplumber.
    Returns a pdfplumber.PDF context manager — caller should use 'with'.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"File is not a .pdf: {file_path}")

    try:
        import pdfplumber
        log.info(f"Opening PDF: {path} ({path.stat().st_size / 1024:.1f} KB)")
        return pdfplumber.open(str(path))
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError:
            class _BasicPage:
                def extract_text(self, *args, **kwargs):
                    return ""

            class _BasicPdfContext:
                def __init__(self, src: Path):
                    self._src = src
                    self.pages = []
                    self.metadata = {}

                def __enter__(self):
                    raw = self._src.read_bytes()
                    text = raw.decode("latin-1", errors="ignore")
                    page_count = len(re.findall(r"/Type\s*/Page\b", text))
                    if page_count <= 0:
                        page_count = 1
                    self.pages = [_BasicPage() for _ in range(page_count)]
                    self.metadata = {}
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _BasicPdfContext(path)

        class _PdfReaderContext:
            def __init__(self, src: Path):
                self._src = src
                self._reader = None
                self.pages = []
                self.metadata = {}

            def __enter__(self):
                self._reader = PdfReader(str(self._src))
                self.pages = self._reader.pages
                raw_meta = self._reader.metadata or {}
                self.metadata = {
                    "Title": str(raw_meta.get("/Title", "") or ""),
                    "Author": str(raw_meta.get("/Author", "") or ""),
                    "Subject": str(raw_meta.get("/Subject", "") or ""),
                    "Creator": str(raw_meta.get("/Creator", "") or ""),
                    "CreationDate": str(raw_meta.get("/CreationDate", "") or ""),
                    "ModDate": str(raw_meta.get("/ModDate", "") or ""),
                }
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _PdfReaderContext(path)


def download_pdf(url: str, dest_dir: str = ".") -> str:
    """
    Download a PDF from a URL and save it locally.

    Args:
        url:      Direct URL to a .pdf file.
        dest_dir: Directory to save the file.

    Returns:
        Local file path of the downloaded PDF.
    """
    from scraper.fetcher import fetch_url

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    # Derive filename from URL
    url_path = url.split("?")[0].rstrip("/")
    filename = url_path.split("/")[-1] or "downloaded.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    local_path = dest / filename
    log.info(f"Downloading PDF from {url} → {local_path}")
    response = fetch_url(url)
    data = response.content
    content_type = (response.headers.get("content-type") or "").lower()
    if "application/pdf" not in content_type and not data.startswith(b"%PDF-"):
        raise ValueError(
            "URL did not return a valid PDF. "
            f"content-type='{content_type or '?'}' url='{url}'"
        )
    local_path.write_bytes(data)
    log.info(f"Saved {len(data) / 1024:.1f} KB → {local_path}")
    return str(local_path)


def parse_page_range(spec: str, total_pages: int) -> list:
    """
    Convert a page-range string to a list of 0-based page indices.

    Examples:
        'all'    → [0, 1, 2, ..., total_pages-1]
        '1-5'    → [0, 1, 2, 3, 4]
        '1,3,7'  → [0, 2, 6]
        '2-'     → [1, 2, ..., total_pages-1]
        '-5'     → [0, 1, 2, 3, 4]
    """
    if not spec or spec.strip().lower() == "all":
        return list(range(total_pages))

    indices = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue

        # Open-ended range: "3-" or "-5"
        if part.endswith("-"):
            start = int(part[:-1]) - 1
            indices.extend(range(start, total_pages))
        elif part.startswith("-"):
            end = int(part[1:])
            indices.extend(range(0, end))
        elif "-" in part:
            a, b = part.split("-", 1)
            indices.extend(range(int(a) - 1, int(b)))
        else:
            indices.append(int(part) - 1)

    # Deduplicate, keep order, clamp to valid range
    seen = set()
    result = []
    for i in indices:
        if 0 <= i < total_pages and i not in seen:
            seen.add(i)
            result.append(i)
    return result


def extract_text(pdf, page_indices: list, clean: bool = True) -> dict:
    """
    Extract text from selected pages.

    Args:
        pdf:          Open pdfplumber.PDF object.
        page_indices: List of 0-based page indices.
        clean:        Normalise whitespace.

    Returns:
        Dict mapping 1-based page numbers to extracted text strings.
    """
    results = {}
    for idx in page_indices:
        page = pdf.pages[idx]
        try:
            raw = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
        except TypeError:
            raw = page.extract_text() or ""
        text = _normalise(raw) if clean else raw
        results[idx + 1] = text
        log.debug(f"  Page {idx + 1}: {len(text)} chars extracted")

    total_chars = sum(len(t) for t in results.values())
    log.info(f"Text extracted from {len(results)} pages — {total_chars:,} chars total")
    return results


def get_pdf_info(pdf) -> dict:
    """Return basic metadata about an open PDF."""
    meta = pdf.metadata or {}
    return {
        "total_pages": len(pdf.pages),
        "title":       meta.get("Title", ""),
        "author":      meta.get("Author", ""),
        "subject":     meta.get("Subject", ""),
        "creator":     meta.get("Creator", ""),
        "created":     meta.get("CreationDate", ""),
        "modified":    meta.get("ModDate", ""),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Clean up whitespace and common PDF extraction artefacts."""
    # Collapse multiple spaces (but not newlines)
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
