"""Unit tests for text processing in summarization"""

import pytest


class TestTextCleaning:
    def test_clean_text_removes_line_breaks(self):
        """Test that line breaks are properly removed"""
        from preprint_bot.summarization_script import clean_text

        text = "This is\na test\nwith breaks"
        result = clean_text(text)
        assert "\n" not in result
        assert "This is" in result

    def test_clean_text_removes_citations(self):
        """Test that citation markers are removed"""
        from preprint_bot.summarization_script import clean_text

        text = "This is a test [1] with citations [23]."
        result = clean_text(text)
        assert "[1]" not in result
        assert "[23]" not in result

    def test_clean_text_removes_hyphenated_line_breaks(self):
        """Test that hyphenated line breaks are handled"""
        from preprint_bot.summarization_script import clean_text

        text = "This is a hyphen-\nated word."
        result = clean_text(text)
        assert "-\n" not in result
        assert "hyphenated" in result or "hyphen ated" in result

    def test_clean_text_normalizes_whitespace(self):
        """Test that multiple spaces are normalized"""
        from preprint_bot.summarization_script import clean_text

        text = "This  has    multiple     spaces"
        result = clean_text(text)
        assert "  " not in result

    def test_clean_text_empty_string(self):
        """Test with empty string"""
        from preprint_bot.summarization_script import clean_text

        result = clean_text("")
        assert result == ""


class TestSectionExtraction:
    def test_extract_sections_markdown_format(self):
        """Test section extraction from markdown-style headers"""
        from preprint_bot.summarization_script import extract_sections_from_txt_markdown

        txt = """### Introduction
This is the introduction text.
More introduction.

### Methods
This is the methods text.

### Results
This is the results text.
"""
        sections = extract_sections_from_txt_markdown(txt)

        assert len(sections) == 3
        assert sections[0]["header"] == "introduction"
        assert sections[1]["header"] == "methods"
        assert sections[2]["header"] == "results"
        assert "introduction text" in sections[0]["text"].lower()

    def test_extract_sections_excludes_references(self):
        """Test that reference sections are excluded"""
        from preprint_bot.summarization_script import extract_sections_from_txt_markdown

        txt = """### Introduction
Introduction text.

### References
Reference 1
Reference 2

### Acknowledgements
Thanks to everyone.
"""
        sections = extract_sections_from_txt_markdown(txt)

        # Should only have Introduction
        assert len(sections) == 1
        assert sections[0]["header"] == "introduction"

    def test_extract_sections_custom_exclusions(self):
        """Test custom exclusion list"""
        from preprint_bot.summarization_script import extract_sections_from_txt_markdown

        txt = """### Introduction
Intro text.

### Custom Section
Custom text.

### Conclusion
Conclusion text.
"""
        sections = extract_sections_from_txt_markdown(txt, exclude_sections=["custom section"])

        assert len(sections) == 2
        headers = [s["header"] for s in sections]
        assert "introduction" in headers
        assert "conclusion" in headers
        assert "custom section" not in headers

    def test_extract_sections_empty_text(self):
        """Test with empty text"""
        from preprint_bot.summarization_script import extract_sections_from_txt_markdown

        sections = extract_sections_from_txt_markdown("")
        assert sections == []


class TestTextChunking:
    def test_chunk_text_respects_max_tokens(self):
        """Test that text chunking respects token limits"""
        from preprint_bot.summarization_script import chunk_text

        # Create text with predictable sentence structure
        text = ". ".join([f"Sentence {i}" for i in range(100)])

        chunks = chunk_text(text, max_tokens=50)

        # Each chunk should be under limit
        for chunk in chunks:
            assert len(chunk.split()) <= 50

        # Should have multiple chunks
        assert len(chunks) > 1

    def test_chunk_text_single_sentence(self):
        """Test chunking with single short sentence"""
        from preprint_bot.summarization_script import chunk_text

        text = "This is a short sentence."
        chunks = chunk_text(text, max_tokens=100)

        assert len(chunks) == 1
        assert chunks[0].strip() == text.strip()

    def test_chunk_text_empty_string(self):
        """Test chunking empty string"""
        from preprint_bot.summarization_script import chunk_text

        chunks = chunk_text("", max_tokens=100)
        # Empty input might return empty list or list with empty string
        assert len(chunks) == 0 or (len(chunks) == 1 and chunks[0].strip() == "")

    def test_chunk_text_exact_limit(self):
        """Test chunking when text is exactly at limit"""
        from preprint_bot.summarization_script import chunk_text

        text = " ".join(["word"] * 50)
        chunks = chunk_text(text, max_tokens=50)

        assert len(chunks) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
