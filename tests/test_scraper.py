"""
tests/test_scraper.py
Unit tests for the scraper module (parser + exporter).
Run: pytest tests/test_scraper.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.parser import extract, parse_html
from scraper.exporter import export, auto_filename


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Test Page</title>
  <meta name="description" content="A test page for unit tests">
  <meta property="og:title" content="Test OG Title">
</head>
<body>
  <h1>Main Heading</h1>
  <h2>Sub Heading</h2>
  <p>First paragraph with some text.</p>
  <p>Second paragraph with more text.</p>
  <a href="/relative-link">Relative Link</a>
  <a href="https://external.example.com">External Link</a>
  <img src="/img/photo.jpg" alt="A photo" width="800" height="600">
  <table>
    <tr><th>Name</th><th>Value</th></tr>
    <tr><td>Alpha</td><td>1</td></tr>
    <tr><td>Beta</td><td>2</td></tr>
  </table>
  <ul>
    <li>List item one</li>
    <li>List item two</li>
  </ul>
  <script>alert("noise")</script>
  <style>.noise { display: none }</style>
</body>
</html>
"""

BASE_URL = "https://test.example.com"


@pytest.fixture
def soup():
    return parse_html(SAMPLE_HTML, base_url=BASE_URL)


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestParser:

    def test_parse_returns_soup(self, soup):
        assert soup is not None
        assert soup.title.string == "Test Page"

    def test_extract_all_returns_dict(self, soup):
        result = extract(soup, mode="all", base_url=BASE_URL)
        assert isinstance(result, dict)
        assert "title" in result
        assert "headings" in result
        assert "paragraphs" in result
        assert "links" in result
        assert "images" in result
        assert "tables" in result

    def test_extract_all_title(self, soup):
        result = extract(soup, mode="all", base_url=BASE_URL)
        assert result["title"] == "Test Page"

    def test_extract_all_headings(self, soup):
        result = extract(soup, mode="all", base_url=BASE_URL)
        assert "Main Heading" in result["headings"]
        assert "Sub Heading" in result["headings"]

    def test_extract_text(self, soup):
        result = extract(soup, mode="text")
        assert isinstance(result, list)
        contents = [item["content"] for item in result]
        assert any("First paragraph" in c for c in contents)
        assert any("List item one" in c for c in contents)

    def test_extract_links(self, soup):
        result = extract(soup, mode="links", base_url=BASE_URL)
        assert isinstance(result, list)
        hrefs = [lnk["href"] for lnk in result]
        # Relative link should be resolved to absolute
        assert any("/relative-link" in h for h in hrefs)
        assert any("external.example.com" in h for h in hrefs)

    def test_extract_images(self, soup):
        result = extract(soup, mode="images", base_url=BASE_URL)
        assert isinstance(result, list)
        assert len(result) >= 1
        img = result[0]
        assert "src" in img
        assert img["alt"] == "A photo"

    def test_extract_tables(self, soup):
        result = extract(soup, mode="tables")
        assert isinstance(result, list)
        assert len(result) == 1
        table = result[0]
        assert "rows" in table
        assert len(table["rows"]) >= 2

    def test_extract_meta(self, soup):
        result = extract(soup, mode="meta")
        assert isinstance(result, list)
        names = [m["name"] for m in result]
        assert "description" in names

    def test_extract_custom(self, soup):
        result = extract(soup, mode="custom", selector="h1, h2")
        assert isinstance(result, list)
        contents = [item["content"] for item in result]
        assert "Main Heading" in contents

    def test_invalid_mode_raises(self, soup):
        with pytest.raises(ValueError, match="Unknown mode"):
            extract(soup, mode="nonsense")

    def test_custom_without_selector_raises(self, soup):
        with pytest.raises(ValueError, match="CSS selector required"):
            extract(soup, mode="custom", selector="")

    def test_script_noise_removed(self, soup):
        result = extract(soup, mode="text")
        contents = " ".join(item["content"] for item in result)
        assert "alert" not in contents
        assert "display: none" not in contents

    def test_clean_whitespace(self, soup):
        result = extract(soup, mode="text", clean=True)
        for item in result:
            assert "\n" not in item["content"]
            assert "  " not in item["content"]


# ── Exporter tests ────────────────────────────────────────────────────────────

class TestExporter:

    def test_json_export(self, tmp_path, soup):
        data = extract(soup, mode="links", base_url=BASE_URL)
        out = tmp_path / "out.json"
        export(data, fmt="json", outfile=str(out), metadata={"url": BASE_URL})
        assert out.exists()
        payload = json.loads(out.read_text())
        assert "metadata" in payload
        assert "data" in payload
        assert isinstance(payload["data"], list)

    def test_csv_export(self, tmp_path, soup):
        data = extract(soup, mode="links", base_url=BASE_URL)
        out = tmp_path / "out.csv"
        export(data, fmt="csv", outfile=str(out))
        assert out.exists()
        content = out.read_text()
        assert "href" in content  # header row

    def test_txt_export(self, tmp_path, soup):
        data = extract(soup, mode="text")
        out = tmp_path / "out.txt"
        export(data, fmt="txt", outfile=str(out), metadata={"url": BASE_URL, "mode": "text"})
        assert out.exists()
        assert out.stat().st_size > 0

    def test_md_export(self, tmp_path, soup):
        data = extract(soup, mode="all", base_url=BASE_URL)
        out = tmp_path / "out.md"
        export(data, fmt="md", outfile=str(out), metadata={"url": BASE_URL, "mode": "all"})
        assert out.exists()
        text = out.read_text()
        assert "# Scraped Data" in text

    def test_invalid_format_raises(self, tmp_path, soup):
        data = extract(soup, mode="text")
        with pytest.raises(ValueError, match="Unknown format"):
            export(data, fmt="xlsx", outfile=str(tmp_path / "out.xlsx"))

    def test_auto_filename_format(self):
        name = auto_filename("links", "json", "scraped")
        assert name.startswith("scraped_links_")
        assert name.endswith(".json")

    def test_output_dir_created(self, tmp_path, soup):
        data = extract(soup, mode="text")
        nested = tmp_path / "a" / "b" / "c"
        export(data, fmt="txt", outfile=str(nested / "out.txt"))
        assert (nested / "out.txt").exists()
