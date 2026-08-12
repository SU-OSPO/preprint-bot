"""Unit tests for similarity computation"""
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock

from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))

class TestGrouping:
    def test_group_embeddings_by_paper(self):
        """Test grouping embeddings by paper_id"""
        from preprint_bot.db_similarity_matcher import group_embeddings_by_paper
        
        embeddings = [
            {'paper_id': 1, 'embedding': [0.1, 0.2]},
            {'paper_id': 1, 'embedding': [0.3, 0.4]},
            {'paper_id': 2, 'embedding': [0.5, 0.6]},
        ]
        
        result = group_embeddings_by_paper(embeddings)
        
        assert len(result) == 2
        assert len(result[1]) == 2
        assert len(result[2]) == 1
    
    def test_group_embeddings_empty_list(self):
        """Test grouping with empty list"""
        from preprint_bot.db_similarity_matcher import group_embeddings_by_paper
        
        result = group_embeddings_by_paper([])
        assert result == {}
    
    def test_group_embeddings_single_paper(self):
        """Test grouping with single paper"""
        from preprint_bot.db_similarity_matcher import group_embeddings_by_paper
        
        embeddings = [
            {'paper_id': 1, 'embedding': [0.1, 0.2]},
            {'paper_id': 1, 'embedding': [0.3, 0.4]},
            {'paper_id': 1, 'embedding': [0.5, 0.6]},
        ]
        
        result = group_embeddings_by_paper(embeddings)
        
        assert len(result) == 1
        assert len(result[1]) == 3


class TestCosineSimilarity:
    def test_compute_cosine_similarity_identical(self):
        """Test cosine similarity with identical vectors"""
        from preprint_bot.db_similarity_matcher import compute_cosine_similarity
        
        user_matrix = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        arxiv_matrix = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        
        similarity = compute_cosine_similarity(user_matrix, arxiv_matrix)
        
        # Should be very close to 1.0
        assert abs(similarity[0, 0] - 1.0) < 1e-5
    
    def test_compute_cosine_similarity_orthogonal(self):
        """Test cosine similarity with orthogonal vectors"""
        from preprint_bot.db_similarity_matcher import compute_cosine_similarity
        
        user_matrix = np.array([[1.0, 0.0]], dtype=np.float32)
        arxiv_matrix = np.array([[0.0, 1.0]], dtype=np.float32)
        
        similarity = compute_cosine_similarity(user_matrix, arxiv_matrix)
        
        # Should be very close to 0.0
        assert abs(similarity[0, 0]) < 1e-5
    
    def test_compute_cosine_similarity_opposite(self):
        """Test cosine similarity with opposite vectors"""
        from preprint_bot.db_similarity_matcher import compute_cosine_similarity
        
        user_matrix = np.array([[1.0, 0.0]], dtype=np.float32)
        arxiv_matrix = np.array([[-1.0, 0.0]], dtype=np.float32)
        
        similarity = compute_cosine_similarity(user_matrix, arxiv_matrix)
        
        # Should be close to -1.0
        assert abs(similarity[0, 0] - (-1.0)) < 1e-5
    
    def test_compute_cosine_similarity_multiple_vectors(self):
        """Test cosine similarity with multiple vectors"""
        from preprint_bot.db_similarity_matcher import compute_cosine_similarity
        
        user_matrix = np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ], dtype=np.float32)
        
        arxiv_matrix = np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ], dtype=np.float32)
        
        similarity = compute_cosine_similarity(user_matrix, arxiv_matrix)
        
        assert similarity.shape == (2, 2)
        # Diagonal should be 1.0
        assert abs(similarity[0, 0] - 1.0) < 1e-5
        assert abs(similarity[1, 1] - 1.0) < 1e-5


class TestPaperSimilarity:
    def test_compute_paper_similarity_returns_max(self):
        """Test that paper similarity returns maximum across embeddings"""
        from preprint_bot.db_similarity_matcher import compute_paper_similarity
        
        user_embs = [[1.0, 0.0], [0.0, 1.0]]
        arxiv_embs = [[1.0, 0.0], [0.5, 0.5]]
        
        similarity = compute_paper_similarity(user_embs, arxiv_embs, method="cosine")
        
        # Maximum similarity should be 1.0 (first embedding pair)
        assert similarity >= 0.99
    
    def test_compute_paper_similarity_single_embeddings(self):
        """Test similarity with single embedding per paper"""
        from preprint_bot.db_similarity_matcher import compute_paper_similarity
        
        user_embs = [[1.0, 0.0]]
        arxiv_embs = [[0.0, 1.0]]
        
        similarity = compute_paper_similarity(user_embs, arxiv_embs, method="cosine")
        
        # Should be near 0 for orthogonal vectors
        assert abs(similarity) < 0.1
    
    def test_compute_paper_similarity_many_embeddings(self):
        """Test with many embeddings per paper"""
        from preprint_bot.db_similarity_matcher import compute_paper_similarity
        
        # Create 10 random embeddings per paper
        np.random.seed(42)
        user_embs = np.random.randn(10, 5).tolist()
        arxiv_embs = np.random.randn(10, 5).tolist()
        
        similarity = compute_paper_similarity(user_embs, arxiv_embs, method="cosine")
        
        # Should return a single float value
        assert isinstance(similarity, float)
        assert -1.0 <= similarity <= 1.0


class TestCandidateSelection:
    """An empty candidate set must mean "recommend nothing", not "compare
    against every paper in the reference corpus"."""

    def _mock_api_client(self, profile_categories=None, papers=None, run_id=1364):
        client = AsyncMock()
        client.base_url = "http://testserver"
        client.client.get = AsyncMock(
            return_value=MagicMock(
                json=MagicMock(return_value={"categories": profile_categories or []})
            )
        )
        client.get_papers_by_corpus = AsyncMock(return_value=papers or [])
        client.create_recommendation_run = AsyncMock(return_value={"id": run_id})
        client.get_embeddings_by_corpus = AsyncMock(return_value=[])
        client.create_recommendation = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_empty_paper_ids_stores_no_recommendations(self):
        """No papers fetched should short-circuit before any embedding fetch."""
        from preprint_bot.db_similarity_matcher import run_similarity_matching

        client = self._mock_api_client()

        run_id = await run_similarity_matching(
            client,
            user_id=1,
            user_corpus_id=1,
            arxiv_corpus_id=2,
            profile_id=None,
            paper_ids=set(),
        )

        assert run_id == 1364
        client.get_embeddings_by_corpus.assert_not_called()
        client.create_recommendation.assert_not_called()
        kwargs = client.create_recommendation_run.call_args.kwargs
        assert kwargs["total_papers_fetched"] == 0

    @pytest.mark.asyncio
    async def test_category_filter_emptying_candidates_stores_no_recommendations(self):
        """Candidates filtered down to nothing must not fall back to the corpus."""
        from preprint_bot.db_similarity_matcher import run_similarity_matching

        client = self._mock_api_client(
            profile_categories=["cs.GL"],
            papers=[{"id": 10, "metadata": {"categories": ["cs.LG"]}}],
        )

        run_id = await run_similarity_matching(
            client,
            user_id=1,
            user_corpus_id=1,
            arxiv_corpus_id=2,
            profile_id=7,
            paper_ids={10},
        )

        assert run_id == 1364
        client.get_embeddings_by_corpus.assert_not_called()
        client.create_recommendation.assert_not_called()

    @pytest.mark.asyncio
    async def test_surviving_candidates_restrict_the_embedding_fetch(self):
        """Candidates that pass the category filter are the only ones fetched."""
        from preprint_bot.db_similarity_matcher import run_similarity_matching

        client = self._mock_api_client(
            profile_categories=["cs.GL"],
            papers=[{"id": 10, "metadata": {"categories": ["cs.GL"]}}],
        )

        await run_similarity_matching(
            client,
            user_id=1,
            user_corpus_id=1,
            arxiv_corpus_id=2,
            profile_id=7,
            paper_ids={10},
        )

        # First call is the user corpus, second is the restricted arXiv fetch.
        arxiv_call = client.get_embeddings_by_corpus.call_args_list[1]
        assert arxiv_call.kwargs["paper_ids"] == [10]

    @pytest.mark.asyncio
    async def test_no_paper_ids_still_compares_against_whole_corpus(self):
        """paper_ids=None keeps the unrestricted behaviour for ad-hoc callers."""
        from preprint_bot.db_similarity_matcher import run_similarity_matching

        client = self._mock_api_client()

        await run_similarity_matching(
            client,
            user_id=1,
            user_corpus_id=1,
            arxiv_corpus_id=2,
            profile_id=None,
            paper_ids=None,
        )

        arxiv_call = client.get_embeddings_by_corpus.call_args_list[1]
        assert "paper_ids" not in arxiv_call.kwargs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])