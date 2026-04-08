"""
tests/test_pdf.py
Unit tests for the PDF processor module.
Run: pytest tests/test_pdf.py -v

Note: Tests that require actual PDF files use a minimal in-memory PDF
generated with pypdf so no external test fixtures are needed.
"""
import json
import sys
from io import BytesIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_processor.reader import parse_page_range, get_pdf_info
from pdf_processor.table_extractor import tables_to_markdown, tables_to_csv
from pdf_processor.exporter import export, auto_filename


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_minimal_pdf(tmp_path: Path) -> str:
    """
    Create a minimal valid PDF file using pypdf for testing.
    Falls back to writing raw PDF bytes if pypdf writer is unavailable.
    """
    pdf_path = tmp_path / "test.pdf"
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
    except Exception:
        # Absolute minimal valid PDF (2 pages)
        content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R 4 0 R]/Count 2>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
4 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000174 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
233
%%EOF"""
        pdf_path.write_bytes(content)
    return str(pdf_path)


# ── parse_page_range tests ────────────────────────────────────────────────────

class TestParsePageRange:

    def test_all(self):
        assert parse_page_range("all", 5) == [0, 1, 2, 3, 4]

    def test_empty_string(self):
        assert parse_page_range("", 5) == [0, 1, 2, 3, 4]

    def test_single_page(self):
        assert parse_page_range("3", 5) == [2]

    def test_range(self):
        assert parse_page_range("2-4", 5) == [1, 2, 3]

    def test_comma_list(self):
        assert parse_page_range("1,3,5", 5) == [0, 2, 4]

    def test_mixed(self):
        assert parse_page_range("1,3-5", 6) == [0, 2, 3, 4]

    def test_open_end(self):
        assert parse_page_range("3-", 5) == [2, 3, 4]

    def test_open_start(self):
        assert parse_page_range("-3", 5) == [0, 1, 2]

    def test_out_of_range_clamped(self):
        result = parse_page_range("1,10,20", 5)
        assert result == [0]  # only page 1 is valid

    def test_deduplication(self):
        result = parse_page_range("1,1,2,2", 5)
        assert result == [0, 1]

    def test_full_range_equals_all(self):
        assert parse_page_range("1-5", 5) == parse_page_range("all", 5)


# ── Table extraction helper tests ─────────────────────────────────────────────

class TestTableHelpers:

    SAMPLE_TABLES = [
        {
            "page": 1,
            "table_index": 0,
            "caption": "",
            "headers": ["Name", "Score", "Grade"],
            "rows": [
                ["Alice", "95", "A"],
                ["Bob", "82", "B"],
                ["Carol", "78", "C"],
            ],
            "row_count": 3,
            "col_count": 3,
        },
        {
            "page": 2,
            "table_index": 0,
            "caption": "Revenue Table",
            "headers": ["Quarter", "Revenue"],
            "rows": [
                ["Q1", "$1.2M"],
                ["Q2", "$1.5M"],
            ],
            "row_count": 2,
            "col_count": 2,
        },
    ]

    def test_tables_to_markdown_structure(self):
        md = tables_to_markdown(self.SAMPLE_TABLES)
        assert "### Page 1, Table 1" in md
        assert "### Page 2, Table 1" in md
        assert "| Name | Score | Grade |" in md
        assert "Alice" in md
        assert "Q1" in md

    def test_tables_to_markdown_pipe_escaping(self):
        tables = [{
            "page": 1, "table_index": 0, "caption": "",
            "headers": ["Col A"],
            "rows": [["value|with|pipes"]],
            "row_count": 1, "col_count": 1,
        }]
        md = tables_to_markdown(tables)
        assert "value\\|with\\|pipes" in md

    def test_tables_to_csv(self, tmp_path):
        out = tmp_path / "tables.csv"
        tables_to_csv(self.SAMPLE_TABLES, str(out))
        assert out.exists()
        content = out.read_text()
        assert "Alice" in content
        assert "Q1" in content
        assert "# Page 1" in content
        assert "# Page 2" in content

    def test_tables_to_csv_empty(self, tmp_path):
        out = tmp_path / "empty.csv"
        tables_to_csv([], str(out))
        assert out.exists()


# ── PDF exporter tests ────────────────────────────────────────────────────────

class TestPdfExporter:

    TEXT_PAGES = {
        1: "This is page one content. It has several sentences.",
        2: "This is page two. More interesting content here.",
        3: "",  # blank page
    }

    TABLES = [
        {
            "page": 1, "table_index": 0, "caption": "",
            "headers": ["A", "B"],
            "rows": [["1", "2"], ["3", "4"]],
            "row_count": 2, "col_count": 2,
        }
    ]

    SUMMARY = "This document covers two main topics with supporting data."

    METADATA = {
        "source": "test.pdf",
        "op": "all",
        "page_range": "all",
        "total_pages": 3,
        "processed_at": "2026-01-01T00:00:00",
    }

    def test_export_txt(self, tmp_path):
        out = tmp_path / "out.txt"
        export(self.TEXT_PAGES, self.TABLES, self.SUMMARY, "txt", str(out), self.METADATA)
        assert out.exists()
        content = out.read_text()
        assert "PDF PROCESSING REPORT" in content
        assert "AI SUMMARY" in content
        assert "page one content" in content
        assert "TABLES" in content

    def test_export_json(self, tmp_path):
        out = tmp_path / "out.json"
        export(self.TEXT_PAGES, self.TABLES, self.SUMMARY, "json", str(out), self.METADATA)
        payload = json.loads(out.read_text())
        assert "metadata" in payload
        assert "summary" in payload
        assert "text_pages" in payload
        assert "tables" in payload
        assert payload["summary"] == self.SUMMARY
        assert "1" in payload["text_pages"]

    def test_export_md(self, tmp_path):
        out = tmp_path / "out.md"
        export(self.TEXT_PAGES, self.TABLES, self.SUMMARY, "md", str(out), self.METADATA)
        content = out.read_text()
        assert "# PDF Processing Report" in content
        assert "## AI Summary" in content
        assert "## Extracted Text" in content
        assert "## Tables" in content

    def test_export_csv(self, tmp_path):
        out = tmp_path / "out.csv"
        export(self.TEXT_PAGES, self.TABLES, self.SUMMARY, "csv", str(out), self.METADATA)
        assert out.exists()
        content = out.read_text()
        assert "Page 1" in content

    def test_export_no_summary(self, tmp_path):
        out = tmp_path / "out.txt"
        export(self.TEXT_PAGES, [], "", "txt", str(out), self.METADATA)
        content = out.read_text()
        assert "AI SUMMARY" not in content

    def test_export_no_tables(self, tmp_path):
        out = tmp_path / "out.md"
        export(self.TEXT_PAGES, [], self.SUMMARY, "md", str(out), self.METADATA)
        content = out.read_text()
        assert "## Tables" not in content

    def test_export_empty_all(self, tmp_path):
        out = tmp_path / "out.json"
        export({}, [], "", "json", str(out), self.METADATA)
        payload = json.loads(out.read_text())
        assert payload["summary"] is None
        assert payload["text_pages"] == {}
        assert payload["tables"] == []

    def test_invalid_format_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown format"):
            export(self.TEXT_PAGES, [], "", "html", str(tmp_path / "out.html"))

    def test_auto_filename_structure(self):
        name = auto_filename("my_doc.pdf", "all", "md")
        assert name.startswith("my_doc_all_")
        assert name.endswith(".md")

    def test_output_directory_created(self, tmp_path):
        nested = tmp_path / "x" / "y" / "z"
        export(self.TEXT_PAGES, [], "", "txt", str(nested / "out.txt"), self.METADATA)
        assert (nested / "out.txt").exists()

    def test_blank_pages_handled(self, tmp_path):
        """Pages with no text should not crash the exporter."""
        pages = {1: "", 2: "", 3: ""}
        out = tmp_path / "blank.md"
        export(pages, [], "", "md", str(out), self.METADATA)
        content = out.read_text()
        assert "No text detected" in content


# ── Reader utility tests ──────────────────────────────────────────────────────

class TestReaderUtils:

    def test_open_nonexistent_raises(self):
        from pdf_processor.reader import open_pdf
        with pytest.raises(FileNotFoundError):
            open_pdf("/nonexistent/path/file.pdf").__enter__()

    def test_open_wrong_extension_raises(self, tmp_path):
        from pdf_processor.reader import open_pdf
        f = tmp_path / "doc.txt"
        f.write_text("not a pdf")
        with pytest.raises(ValueError, match="not a .pdf"):
            open_pdf(str(f)).__enter__()

    def test_open_valid_pdf(self, tmp_path):
        from pdf_processor.reader import open_pdf
        pdf_path = make_minimal_pdf(tmp_path)
        with open_pdf(pdf_path) as pdf:
            assert len(pdf.pages) == 2

    def test_get_pdf_info(self, tmp_path):
        from pdf_processor.reader import open_pdf
        pdf_path = make_minimal_pdf(tmp_path)
        with open_pdf(pdf_path) as pdf:
            info = get_pdf_info(pdf)
        assert info["total_pages"] == 2
        assert "title" in info
        assert "author" in info


class TestDownloadPdfValidation:
    def test_download_pdf_rejects_html_response(self, monkeypatch, tmp_path):
        from pdf_processor.reader import download_pdf

        class _Resp:
            headers = {"content-type": "text/html; charset=utf-8"}
            content = b"<html><body>Not a PDF</body></html>"

        def _fake_fetch_url(url, **kwargs):
            return _Resp()

        monkeypatch.setattr("scraper.fetcher.fetch_url", _fake_fetch_url)

        with pytest.raises(ValueError, match="did not return a valid PDF"):
            download_pdf("https://example.com/page", dest_dir=str(tmp_path))

    def test_download_pdf_accepts_pdf_signature_without_mime(self, monkeypatch, tmp_path):
        from pdf_processor.reader import download_pdf

        class _Resp:
            headers = {"content-type": "application/octet-stream"}
            content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"

        def _fake_fetch_url(url, **kwargs):
            return _Resp()

        monkeypatch.setattr("scraper.fetcher.fetch_url", _fake_fetch_url)
        out = download_pdf("https://example.com/file", dest_dir=str(tmp_path))
        assert Path(out).exists()
