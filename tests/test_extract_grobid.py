# test_extract_grobid.py
"""Deterministic unit tests for GROBID TEI XML extraction.

`requests.post` is mocked with a fixed TEI document, so these tests need no
running GROBID server and assert exactly on the parsed title, abstract,
authors, date, and body sections (including back-matter header exclusion).
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))

from preprint_bot.extract_grobid import extract_grobid_sections


# A complete TEI document like GROBID returns: header metadata plus body
# sections — including back-matter sections that extraction excludes, a
# headless div, and a headed div with no paragraphs.
TEI_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>A Study of Deterministic Testing</title></titleStmt>
      <sourceDesc>
        <biblStruct>
          <analytic>
            <author><persName><forename>Ada</forename><surname>Lovelace</surname></persName></author>
            <author><persName><forename>Alan</forename><surname>Turing</surname></persName></author>
          </analytic>
          <monogr><imprint><date>2023-06-15</date></imprint></monogr>
        </biblStruct>
      </sourceDesc>
    </fileDesc>
    <profileDesc>
      <abstract><p>We present a deterministic method for testing GROBID parsing.</p></abstract>
    </profileDesc>
  </teiHeader>
  <text><body>
    <div><head>Introduction</head><p>Intro paragraph one.</p><p>Intro paragraph two.</p></div>
    <div><head>Methods</head><p>Methods paragraph.</p></div>
    <div><p>A section with no header.</p></div>
    <div><head>A header with no paragraphs.</head></div>
    <div><head>Conclusion</head><p>Conclusion paragraph.</p></div>
    <div><head>Acknowledgements</head><p>Thanks to everyone.</p></div>
    <div><head>References</head><p>Reference list.</p></div>
    <div><head>Bibliography</head><p>Bibliography list.</p></div>
    <div><head>Appendix A</head><p>Appendix content.</p></div>
    <div><head>Supplementary Material</head><p>Supplementary content.</p></div>
  </body></text>
</TEI>"""


def _grobid_response(content=TEI_XML):
    """A stand-in requests Response: .content bytes + a no-op raise_for_status."""
    resp = Mock()
    resp.content = content
    resp.raise_for_status = Mock()
    return resp


class TestGrobidInput:
    """Input handling and the GROBID call itself."""

    def test_module_exports_callable(self):
        assert callable(extract_grobid_sections)

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_sends_pdf_bytes_to_grobid(self, mock_post):
        mock_post.return_value = _grobid_response()
        extract_grobid_sections(b"%PDF-1.4 the bytes")
        _, kwargs = mock_post.call_args
        assert kwargs["files"]["input"][1] == b"%PDF-1.4 the bytes"

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_reads_pdf_from_path(self, mock_post, tmp_path):
        mock_post.return_value = _grobid_response()
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 from file")
        result = extract_grobid_sections(pdf)
        _, kwargs = mock_post.call_args
        assert kwargs["files"]["input"][1] == b"%PDF-1.4 from file"
        assert result["title"] == "A Study of Deterministic Testing"

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_raises_on_grobid_http_error(self, mock_post):
        resp = Mock()
        resp.raise_for_status = Mock(side_effect=Exception("GROBID 500"))
        mock_post.return_value = resp
        with pytest.raises(Exception):
            extract_grobid_sections(b"%PDF-1.4 fake")


class TestGrobidParsing:
    """TEI metadata and section extraction."""

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_extracts_title(self, mock_post):
        mock_post.return_value = _grobid_response()
        assert extract_grobid_sections(b"x")["title"] == "A Study of Deterministic Testing"

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_extracts_abstract(self, mock_post):
        mock_post.return_value = _grobid_response()
        assert (extract_grobid_sections(b"x")["abstract"]
                == "We present a deterministic method for testing GROBID parsing.")

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_extracts_authors_and_date(self, mock_post):
        mock_post.return_value = _grobid_response()
        result = extract_grobid_sections(b"x")
        assert result["authors"] == ["Ada Lovelace", "Alan Turing"]
        assert result["pub_date"] == "2023-06-15"

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_extracts_body_sections_in_order(self, mock_post):
        mock_post.return_value = _grobid_response()
        sections = extract_grobid_sections(b"x")["sections"]
        assert [s["header"] for s in sections] == ["Introduction", "Methods", "Untitled Section", "Conclusion"]
        assert sections[0]["text"] == "Intro paragraph one.\n\nIntro paragraph two."

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_excludes_back_matter_headers(self, mock_post):
        mock_post.return_value = _grobid_response()
        headers = [s["header"] for s in extract_grobid_sections(b"x")["sections"]]
        for excluded in ["Acknowledgements", "References", "Bibliography",
                         "Appendix A", "Supplementary Material"]:
            assert excluded not in headers

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_headless_div_is_untitled_section(self, mock_post):
        mock_post.return_value = _grobid_response()
        untitled = [s for s in extract_grobid_sections(b"x")["sections"]
                    if s["header"] == "Untitled Section"]
        assert len(untitled) == 1
        assert untitled[0]["text"] == "A section with no header."

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_div_with_head_but_no_paragraphs_is_dropped(self, mock_post):
        mock_post.return_value = _grobid_response()
        headers = [s["header"] for s in extract_grobid_sections(b"x")["sections"]]
        # A non-back-matter head with no paragraph text is dropped: only
        # sections that have paragraph text are kept.
        assert "A header with no paragraphs." not in headers

    @patch("preprint_bot.extract_grobid.requests.post")
    def test_missing_metadata_yields_empty(self, mock_post):
        minimal = (b'<?xml version="1.0" encoding="UTF-8"?>'
                   b'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body></body></text></TEI>')
        mock_post.return_value = _grobid_response(minimal)
        result = extract_grobid_sections(b"x")
        assert result["title"] == ""
        assert result["abstract"] == ""
        assert result["authors"] == []
        assert result["sections"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
