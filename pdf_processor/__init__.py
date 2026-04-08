"""
pdf_processor — PDF processing module for Automation Hub.

Public API:
    process(file_path, op, pages, ai_prompt, **kwargs) -> dict
    process_and_export(file_path, op, fmt, outfile, **kwargs) -> Path
"""
from pdf_processor.reader import open_pdf, extract_text, parse_page_range, get_pdf_info, download_pdf
from pdf_processor.table_extractor import extract_tables
from pdf_processor.summarizer import summarize_pages
from pdf_processor import exporter


def process(
    file_path: str,
    op: str = "all",
    pages: str = "all",
    ai_prompt: str = None,
) -> dict:
    """
    High-level: open PDF, run op, return dict of results.
    op: 'extract' | 'summarize' | 'tables' | 'all'
    """
    with open_pdf(file_path) as pdf:
        info = get_pdf_info(pdf)
        indices = parse_page_range(pages, info["total_pages"])

        text_pages = {}
        tables = []
        summary = ""

        if op in ("extract", "all", "summarize"):
            text_pages = extract_text(pdf, indices)
        if op in ("tables", "all"):
            tables = extract_tables(pdf, indices)
        if op in ("summarize", "all") and text_pages:
            summary = summarize_pages(text_pages, prompt=ai_prompt)

    return {"info": info, "text_pages": text_pages, "tables": tables, "summary": summary}


def process_and_export(file_path, op="all", fmt="md", outfile=None, pages="all", ai_prompt=None):
    """Process a PDF and write to file. Returns output Path."""
    from datetime import datetime
    result = process(file_path, op=op, pages=pages, ai_prompt=ai_prompt)
    if outfile is None:
        outfile = exporter.auto_filename(file_path, op, fmt)
    return exporter.export(
        text_pages=result["text_pages"],
        tables=result["tables"],
        summary=result["summary"],
        fmt=fmt,
        outfile=outfile,
        metadata={"source": file_path, "op": op, "page_range": pages,
                  "total_pages": result["info"]["total_pages"],
                  "processed_at": datetime.now().isoformat()},
    )


__all__ = ["process", "process_and_export", "open_pdf", "extract_text",
           "extract_tables", "summarize_pages", "exporter"]
