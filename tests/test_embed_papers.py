# test_embed_papers.py
"""Unit tests for embedding functionality"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))


class TestEmbedSinglePaper:
    """Tests for embed_single_paper (shared by both pipeline paths)."""

    @pytest.fixture
    def mock_api_client(self):
        client = AsyncMock()
        client.get_sections_by_paper = AsyncMock(return_value=[])
        client.create_embedding = AsyncMock()
        return client

    @pytest.fixture
    def mock_model(self):
        import numpy as np
        model = MagicMock()
        # Return a fake normalized embedding vector
        model.encode = MagicMock(
            return_value=np.array([[0.1] * 384], dtype="float32")
        )
        return model

    @pytest.mark.asyncio
    async def test_skips_paper_with_no_content(self, mock_api_client, mock_model):
        """Papers with no title, abstract, or sections should be skipped."""
        from preprint_bot.embed_papers import embed_single_paper

        paper = {"id": 1, "title": "", "abstract": ""}
        stored = await embed_single_paper(mock_api_client, paper, mock_model, "test-model")
        assert stored == 0
        mock_api_client.create_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_embeds_abstract_from_title_and_abstract(self, mock_api_client, mock_model):
        """Should create an abstract embedding from title + abstract."""
        from preprint_bot.embed_papers import embed_single_paper

        paper = {
            "id": 1,
            "title": "Test Paper Title",
            "abstract": "This is the abstract of the test paper with enough words.",
        }
        stored = await embed_single_paper(mock_api_client, paper, mock_model, "test-model")
        assert stored >= 1
        # Verify the model was called with title + abstract
        call_args = mock_model.encode.call_args_list[0]
        text = call_args[0][0][0]
        assert "Test Paper Title" in text
        assert "abstract of the test paper" in text

    @pytest.mark.asyncio
    async def test_embeds_sections_over_20_words(self, mock_api_client, mock_model):
        """Should embed sections with >20 words and skip short ones."""
        from preprint_bot.embed_papers import embed_single_paper

        long_text = " ".join(["word"] * 25)
        short_text = "too short"

        mock_api_client.get_sections_by_paper = AsyncMock(return_value=[
            {"id": 10, "text": long_text},
            {"id": 11, "text": short_text},
        ])

        paper = {"id": 1, "title": "Title", "abstract": "A sufficient abstract here for testing."}
        stored = await embed_single_paper(mock_api_client, paper, mock_model, "test-model")
        # 1 abstract + 1 eligible section = 2
        assert stored == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
