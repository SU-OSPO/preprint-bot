# test_config.py
"""Unit tests for config module"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))


class TestConfig:
    # def test_similarity_thresholds(self):
    #     """Test that similarity thresholds are properly defined"""
    #     from preprint_bot.config import SIMILARITY_THRESHOLDS

    #     assert "low" in SIMILARITY_THRESHOLDS
    #     assert "medium" in SIMILARITY_THRESHOLDS
    #     assert "high" in SIMILARITY_THRESHOLDS

    #     # Thresholds should be increasing
    #     assert SIMILARITY_THRESHOLDS["low"] < SIMILARITY_THRESHOLDS["medium"]
    #     assert SIMILARITY_THRESHOLDS["medium"] < SIMILARITY_THRESHOLDS["high"]

    #     # All should be between 0 and 1
    #     for threshold in SIMILARITY_THRESHOLDS.values():
    #         assert 0.0 <= threshold <= 1.0

    def test_arxiv_categories_not_empty(self):
        """Test that arXiv categories are defined"""
        from preprint_bot.config import ARXIV_CATEGORIES

        assert isinstance(ARXIV_CATEGORIES, list)
        assert len(ARXIV_CATEGORIES) > 0
        assert all(isinstance(cat, str) for cat in ARXIV_CATEGORIES)

    def test_default_model_name_defined(self):
        """Test that default model is specified"""
        from preprint_bot.config import DEFAULT_MODEL_NAME

        assert isinstance(DEFAULT_MODEL_NAME, str)
        assert len(DEFAULT_MODEL_NAME) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
