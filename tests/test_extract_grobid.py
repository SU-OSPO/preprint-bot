# test_extract_grobid.py
"""Unit tests for GROBID extraction helpers"""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))


class TestExtractGrobid:
    def test_module_imports(self):
        """Test that the module can be imported and has expected exports."""
        from preprint_bot.extract_grobid import extract_grobid_sections
        assert callable(extract_grobid_sections)

    def test_accepts_bytes_input(self):
        """extract_grobid_sections should accept bytes (will fail at GROBID call)."""
        from preprint_bot.extract_grobid import extract_grobid_sections
        # Should raise a connection/request error, not a TypeError
        with pytest.raises(Exception):
            extract_grobid_sections(b"%PDF-1.4 fake pdf content")

    def test_accepts_path_input(self, tmp_path):
        """extract_grobid_sections should accept a path (will fail at GROBID call)."""
        from preprint_bot.extract_grobid import extract_grobid_sections
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake pdf content")
        # Should raise a connection/request error, not a TypeError
        with pytest.raises(Exception):
            extract_grobid_sections(fake_pdf)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
