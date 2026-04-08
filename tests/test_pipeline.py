"""
tests/test_pipeline.py
Integration tests for the pipeline runner.
Uses mocking to avoid real HTTP calls.
Run: pytest tests/test_pipeline.py -v
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


SAMPLE_HTML = """
<html>
<head><title>Test</title></head>
<body>
  <h1>Test Page</h1>
  <p>Some paragraph text.</p>
  <a href="https://example.com/doc.pdf">Download PDF</a>
  <a href="https://example.com/other">Other link</a>
</body>
</html>
"""


# ── Pipeline runner tests ─────────────────────────────────────────────────────

class TestPipelineRunner:

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_basic_run_creates_output(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        manifest = run(
            url="https://example.com",
            scrape_mode="all",
            scrape_format="json",
            follow_pdfs=False,
            pdf_op="extract",
            pdf_format="txt",
            output_dir=str(tmp_path),
        )
        assert "outputs" in manifest
        assert len(manifest["outputs"]) >= 1
        assert manifest["outputs"][0]["type"] == "scrape"
        scrape_file = Path(manifest["outputs"][0]["file"])
        assert scrape_file.exists()

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_manifest_json_written(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        manifest = run(
            url="https://example.com",
            output_dir=str(tmp_path),
        )
        manifest_files = list(tmp_path.glob("pipeline_manifest_*.json"))
        assert len(manifest_files) == 1
        saved = json.loads(manifest_files[0].read_text())
        assert saved["url"] == "https://example.com"
        assert "started_at" in saved
        assert "completed_at" in saved

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_manifest_has_correct_url(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        url = "https://example.com/page"
        manifest = run(url=url, output_dir=str(tmp_path))
        assert manifest["url"] == url

    @patch("scraper.fetcher.fetch_html", side_effect=Exception("Connection refused"))
    def test_fetch_failure_recorded_in_manifest(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        manifest = run(url="https://bad-url.example.com", output_dir=str(tmp_path))
        assert "errors" in manifest

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_output_dir_created(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        nested = tmp_path / "nested" / "deep"
        run(url="https://example.com", output_dir=str(nested))
        assert nested.exists()

    def test_is_pdf_url_detection(self):
        from pipeline.runner import _is_pdf_url
        assert _is_pdf_url("https://example.com/doc.pdf") is True
        assert _is_pdf_url("https://example.com/doc.PDF") is True
        assert _is_pdf_url("https://example.com/doc.pdf?v=1") is True
        assert _is_pdf_url("https://example.com/page") is False
        assert _is_pdf_url("https://example.com/") is False

    def test_find_pdf_links_from_all_mode(self):
        from pipeline.runner import _find_pdf_links
        data = {
            "links": [
                {"href": "https://example.com/report.pdf", "text": "Report"},
                {"href": "https://example.com/page.html", "text": "Page"},
                {"href": "/local/doc.pdf", "text": "Local PDF"},
            ]
        }
        links = _find_pdf_links(data, base_url="https://example.com")
        assert len(links) == 2
        assert "report.pdf" in links[0]

    def test_find_pdf_links_from_list_mode(self):
        from pipeline.runner import _find_pdf_links
        data = [
            {"href": "https://example.com/a.pdf", "text": "A"},
            {"href": "https://example.com/b.html", "text": "B"},
        ]
        links = _find_pdf_links(data, base_url="https://example.com")
        assert len(links) == 1
        assert links[0].endswith("a.pdf")

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_scrape_output_is_valid_json(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        manifest = run(
            url="https://example.com",
            scrape_format="json",
            output_dir=str(tmp_path),
        )
        scrape_file = manifest["outputs"][0]["file"]
        payload = json.loads(Path(scrape_file).read_text())
        assert "metadata" in payload
        assert "data" in payload

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_all_scrape_formats(self, mock_fetch, tmp_path):
        from pipeline.runner import run
        for fmt in ("json", "csv", "txt", "md"):
            subdir = tmp_path / fmt
            manifest = run(
                url="https://example.com",
                scrape_format=fmt,
                output_dir=str(subdir),
            )
            files = list(subdir.glob(f"*.{fmt}"))
            assert len(files) >= 1, f"No .{fmt} output for format={fmt}"


# ── CLI entrypoint smoke tests ─────────────────────────────────────────────────

class TestCLIEntrypoints:
    """
    Light smoke tests that import and call main() with patched I/O.
    These verify argument parsing and wiring without real network calls.
    """

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_web_scraper_cli(self, mock_fetch, tmp_path):
        import web_scraper
        sys_argv_backup = sys.argv[:]
        sys.argv = [
            "web_scraper.py",
            "--url", "https://example.com",
            "--mode", "text",
            "--format", "txt",
            "--output-dir", str(tmp_path),
        ]
        try:
            rc = web_scraper.main()
            assert rc == 0
            outputs = list(tmp_path.glob("*.txt"))
            assert len(outputs) == 1
        finally:
            sys.argv = sys_argv_backup

    @patch("scraper.fetcher.fetch_html", return_value=SAMPLE_HTML)
    def test_automation_pipeline_cli(self, mock_fetch, tmp_path):
        import automation_pipeline
        sys_argv_backup = sys.argv[:]
        sys.argv = [
            "automation_pipeline.py",
            "--url", "https://example.com",
            "--scrape-mode", "links",
            "--output-dir", str(tmp_path),
        ]
        try:
            rc = automation_pipeline.main()
            assert rc == 0
        finally:
            sys.argv = sys_argv_backup


import sys  # ensure sys is available in TestCLIEntrypoints methods
