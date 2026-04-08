"""
pdf_processor/table_extractor.py
Table detection and extraction from PDFs using pdfplumber.
Exports to CSV, JSON-serialisable dicts, or pandas DataFrames.
"""
import csv
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def extract_tables(pdf, page_indices: list) -> list:
    """
    Extract all tables from selected pages.

    Args:
        pdf:          Open pdfplumber.PDF object.
        page_indices: List of 0-based page indices.

    Returns:
        List of table dicts:
        [
          {
            "page": int (1-based),
            "table_index": int,
            "caption": str,
            "headers": list[str] | None,
            "rows": list[list[str]],
            "row_count": int,
            "col_count": int,
          },
          ...
        ]
    """
    all_tables = []

    table_settings = {
        "vertical_strategy":   "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance":      3,
        "join_tolerance":      3,
        "edge_min_length":     3,
        "min_words_vertical":  1,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
    }

    for idx in page_indices:
        page = pdf.pages[idx]

        # pdfplumber.extract_tables() returns list of list-of-lists
        try:
            raw_tables = page.extract_tables(table_settings)
        except Exception as e:
            log.warning(f"Page {idx+1}: table extraction error — {e}")
            raw_tables = []

        for t_idx, raw in enumerate(raw_tables):
            if not raw:
                continue

            # Clean cell values
            cleaned = [[_clean_cell(cell) for cell in row] for row in raw if any(cell for cell in row)]
            if not cleaned:
                continue

            # Heuristic: if first row looks like headers (no numbers, short strings)
            headers, rows = _split_header(cleaned)

            all_tables.append({
                "page":        idx + 1,
                "table_index": t_idx,
                "caption":     "",          # pdfplumber doesn't detect captions
                "headers":     headers,
                "rows":        rows,
                "row_count":   len(rows),
                "col_count":   len(cleaned[0]) if cleaned else 0,
            })
            log.debug(f"  Page {idx+1}, Table {t_idx}: {len(rows)} rows × {len(cleaned[0])} cols")

    log.info(f"Extracted {len(all_tables)} table(s) from {len(page_indices)} page(s)")
    return all_tables


def tables_to_csv(tables: list, outfile: str) -> Path:
    """
    Write all extracted tables to a single CSV file.
    Tables are separated by a blank row and a header comment.
    """
    path = Path(outfile)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for t in tables:
            writer.writerow([f"# Page {t['page']} — Table {t['table_index'] + 1}"])
            if t["headers"]:
                writer.writerow(t["headers"])
            writer.writerows(t["rows"])
            writer.writerow([])  # blank separator

    log.info(f"Tables saved → {path}")
    return path


def tables_to_markdown(tables: list) -> str:
    """Render extracted tables as Markdown."""
    lines = []
    for t in tables:
        lines.append(f"### Page {t['page']}, Table {t['table_index'] + 1}")
        if t["caption"]:
            lines.append(f"_{t['caption']}_")
        lines.append("")

        headers = t["headers"] or ([f"Col {i+1}" for i in range(t["col_count"])])
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "---|" * len(headers))
        for row in t["rows"]:
            # Pad row to header width
            padded = list(row) + [""] * (len(headers) - len(row))
            lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in padded) + " |")
        lines.append("")

    return "\n".join(lines)


def tables_to_dataframes(tables: list):
    """
    Convert extracted tables to a list of pandas DataFrames.
    Requires pandas.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for DataFrame output: pip install pandas")

    dfs = []
    for t in tables:
        cols = t["headers"] or [f"col_{i}" for i in range(t["col_count"])]
        # Pad each row to column count
        n = len(cols)
        rows = [list(r) + [""] * (n - len(r)) for r in t["rows"]]
        df = pd.DataFrame(rows, columns=cols)
        df.attrs["page"] = t["page"]
        df.attrs["table_index"] = t["table_index"]
        dfs.append(df)

    return dfs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_cell(cell) -> str:
    if cell is None:
        return ""
    return str(cell).replace("\n", " ").strip()


def _split_header(rows: list) -> tuple:
    """
    Heuristically decide if the first row is a header.
    Returns (headers_or_None, data_rows).
    """
    if len(rows) < 2:
        return None, rows

    first = rows[0]
    # Treat as header if all cells are short strings without digits predominating
    if all(isinstance(c, str) and len(c) < 60 for c in first):
        return first, rows[1:]
    return None, rows
