"""
pdf_processor/exporter.py
Format and write PDF processing results to various output formats.
"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def export(
    text_pages: dict,
    tables: list,
    summary: str,
    fmt: str,
    outfile: str,
    metadata: Optional[dict] = None,
) -> Path:
    """
    Write PDF processing results to a file.

    Args:
        text_pages: {page_num: text_string} — extracted text per page.
        tables:     List of table dicts from table_extractor.
        summary:    AI-generated summary string (empty string if not run).
        fmt:        Output format: 'txt' | 'json' | 'md' | 'csv'.
        outfile:    Destination file path.
        metadata:   Optional metadata dict (filename, op, timestamp…).

    Returns:
        Path object pointing to the written file.
    """
    path = Path(outfile)
    path.parent.mkdir(parents=True, exist_ok=True)

    if metadata is None:
        metadata = {"processed_at": datetime.now().isoformat()}

    dispatch = {
        "txt":  _to_txt,
        "json": _to_json,
        "md":   _to_md,
        "csv":  _to_csv,
    }

    if fmt not in dispatch:
        raise ValueError(f"Unknown format '{fmt}'. Valid: {list(dispatch)}")

    dispatch[fmt](text_pages, tables, summary, path, metadata)
    log.info(f"PDF output [{fmt.upper()}] → {path} ({path.stat().st_size} bytes)")
    return path


# ── Format writers ────────────────────────────────────────────────────────────

def _to_txt(text_pages, tables, summary, path, metadata):
    lines = [
        "=" * 60,
        f"PDF PROCESSING REPORT",
        "=" * 60,
        f"File:       {metadata.get('source', '?')}",
        f"Operation:  {metadata.get('op', '?')}",
        f"Pages:      {metadata.get('page_range', 'all')}",
        f"Generated:  {metadata.get('processed_at', '?')}",
        "=" * 60,
        "",
    ]

    if summary:
        lines += ["── AI SUMMARY ──", "", summary, ""]

    if text_pages:
        lines.append("── EXTRACTED TEXT ──")
        for pg, text in sorted(text_pages.items()):
            lines += [f"\n--- Page {pg} ---", text if text else "(no text on this page)"]

    if tables:
        lines += ["", "── TABLES ──"]
        for t in tables:
            lines.append(f"\n[Page {t['page']}, Table {t['table_index']+1}]")
            if t["headers"]:
                lines.append("  " + " | ".join(t["headers"]))
                lines.append("  " + "-+-".join("-" * len(h) for h in t["headers"]))
            for row in t["rows"]:
                lines.append("  " + " | ".join(str(c) for c in row))

    path.write_text("\n".join(lines), encoding="utf-8")


def _to_json(text_pages, tables, summary, path, metadata):
    payload = {
        "metadata": metadata,
        "summary":  summary or None,
        "text_pages": {str(pg): text for pg, text in sorted(text_pages.items())},
        "tables": tables,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _to_md(text_pages, tables, summary, path, metadata):
    from pdf_processor.table_extractor import tables_to_markdown

    lines = [
        "# PDF Processing Report",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Source | `{metadata.get('source', '?')}` |",
        f"| Operation | `{metadata.get('op', '?')}` |",
        f"| Pages | `{metadata.get('page_range', 'all')}` |",
        f"| Generated | `{metadata.get('processed_at', '?')}` |",
        "",
    ]

    if summary:
        lines += ["## AI Summary", "", summary, ""]

    if text_pages:
        lines.append("## Extracted Text")
        lines.append("")
        for pg, text in sorted(text_pages.items()):
            lines += [f"### Page {pg}", "", text if text else "_No text detected on this page._", ""]

    if tables:
        lines += ["## Tables", "", tables_to_markdown(tables)]

    path.write_text("\n".join(lines), encoding="utf-8")


def _to_csv(text_pages, tables, summary, path, metadata):
    """
    CSV output: tables are written as-is; text pages as one-row-per-page.
    If tables exist, they are the primary output; text becomes a second sheet
    (we write a single file with section markers since CSV has no sheets).
    """
    rows = []

    if tables:
        for t in tables:
            rows.append([f"# Page {t['page']}, Table {t['table_index']+1}"])
            if t["headers"]:
                rows.append(t["headers"])
            rows.extend(t["rows"])
            rows.append([])  # blank separator

    if text_pages:
        rows.append(["# Extracted Text"])
        rows.append(["page", "text"])
        for pg, text in sorted(text_pages.items()):
            rows.append([pg, text])

    if summary:
        rows.append(["# AI Summary"])
        rows.append([summary])

    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def auto_filename(source: str, op: str, fmt: str) -> str:
    """Generate a timestamped output filename based on the source PDF name."""
    stem = Path(source).stem if source else "pdf"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{op}_{ts}.{fmt}"
