"""
scraper/exporter.py
Export scraped data to JSON, CSV, plain text, or Markdown.
"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Union

log = logging.getLogger(__name__)


def export(
    data: Union[dict, list],
    fmt: str,
    outfile: str,
    metadata: dict = None,
) -> Path:
    """
    Write scraped data to a file.

    Args:
        data:      Extracted data (dict for mode='all', list otherwise).
        fmt:       Output format: 'json' | 'csv' | 'txt' | 'md'.
        outfile:   Destination file path.
        metadata:  Optional dict of metadata to attach (url, mode, timestamp…).

    Returns:
        Path object pointing to the written file.
    """
    path = Path(outfile)
    path.parent.mkdir(parents=True, exist_ok=True)

    if metadata is None:
        metadata = {"exported_at": datetime.now().isoformat()}

    dispatch = {
        "json": _to_json,
        "csv":  _to_csv,
        "txt":  _to_txt,
        "md":   _to_md,
    }

    if fmt not in dispatch:
        raise ValueError(f"Unknown format '{fmt}'. Valid: {list(dispatch)}")

    dispatch[fmt](data, path, metadata)
    log.info(f"Exported [{fmt.upper()}] → {path} ({path.stat().st_size} bytes)")
    return path


# ── Format writers ────────────────────────────────────────────────────────────

def _to_json(data: Any, path: Path, metadata: dict) -> None:
    payload = {"metadata": metadata, "data": data}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _to_csv(data: Any, path: Path, metadata: dict) -> None:
    rows = _flatten_to_rows(data)
    if not rows:
        path.write_text("(no data)", encoding="utf-8")
        return

    # Collect all keys across all rows for a consistent header
    all_keys: list = []
    for row in rows:
        for k in row:
            if k not in all_keys:
                all_keys.append(k)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _to_txt(data: Any, path: Path, metadata: dict) -> None:
    lines = [
        f"# Scraped: {metadata.get('url', '?')}",
        f"# Mode: {metadata.get('mode', '?')}",
        f"# At: {metadata.get('scraped_at', metadata.get('exported_at', '?'))}",
        "",
    ]
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or item.get("href") or str(item)
            else:
                content = str(item)
            lines.append(f"[{i}] {content}")
    elif isinstance(data, dict):
        for key, val in data.items():
            lines.append(f"--- {key.upper()} ---")
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        lines.append("  " + "  |  ".join(f"{k}: {v}" for k, v in item.items()))
                    else:
                        lines.append(f"  {item}")
            else:
                lines.append(f"  {val}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _to_md(data: Any, path: Path, metadata: dict) -> None:
    url = metadata.get("url", "?")
    mode = metadata.get("mode", "?")
    ts = metadata.get("scraped_at", metadata.get("exported_at", "?"))

    lines = [
        f"# Scraped Data",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| URL | `{url}` |",
        f"| Mode | `{mode}` |",
        f"| Scraped at | `{ts}` |",
        f"",
    ]

    if isinstance(data, list):
        if not data:
            lines.append("_No items found._")
        elif isinstance(data[0], dict) and len(data[0]) > 1:
            # Render as a Markdown table
            keys = list(data[0].keys())
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("|" + "---|" * len(keys))
            for row in data:
                cells = [str(row.get(k, "")).replace("|", "\\|")[:120] for k in keys]
                lines.append("| " + " | ".join(cells) + " |")
        else:
            for item in data:
                if isinstance(item, dict):
                    content = item.get("content") or item.get("text") or item.get("href") or str(item)
                else:
                    content = str(item)
                lines.append(f"- {content}")

    elif isinstance(data, dict):
        for key, val in data.items():
            lines.append(f"## {key.replace('_', ' ').title()}")
            if isinstance(val, list) and val:
                if isinstance(val[0], dict) and len(val[0]) > 1:
                    keys = list(val[0].keys())
                    lines.append("| " + " | ".join(keys) + " |")
                    lines.append("|" + "---|" * len(keys))
                    for row in val:
                        cells = [str(row.get(k, "")).replace("|", "\\|")[:120] for k in keys]
                        lines.append("| " + " | ".join(cells) + " |")
                else:
                    for item in val:
                        if isinstance(item, dict):
                            text = item.get("content") or item.get("text") or item.get("href") or str(item)
                        else:
                            text = str(item)
                        lines.append(f"- {text}")
            elif isinstance(val, list):
                lines.append("_(empty)_")
            else:
                lines.append(str(val))
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ── Utility ───────────────────────────────────────────────────────────────────

def _flatten_to_rows(data: Any) -> list:
    """
    Convert data (list or dict) to a flat list of dicts suitable for CSV.
    Tables within 'all' mode get serialised as stringified rows.
    """
    if isinstance(data, list):
        flat = []
        for item in data:
            if isinstance(item, dict):
                flat.append({k: _scalar(v) for k, v in item.items()})
            else:
                flat.append({"value": str(item)})
        return flat

    if isinstance(data, dict):
        # 'all' mode — flatten each sub-section
        rows = []
        for section, items in data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        row = {"section": section}
                        row.update({k: _scalar(v) for k, v in item.items()})
                    else:
                        row = {"section": section, "value": str(item)}
                    rows.append(row)
            else:
                rows.append({"section": section, "value": _scalar(items)})
        return rows

    return [{"value": str(data)}]


def _scalar(val: Any) -> str:
    """Reduce a value to a plain string for CSV cells."""
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def auto_filename(mode: str, fmt: str, prefix: str = "scraped") -> str:
    """Generate a timestamped output filename."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{mode}_{ts}.{fmt}"
