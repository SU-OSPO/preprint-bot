"""
Database-integrated similarity matcher
Uses embeddings stored in PostgreSQL to find similar papers
"""
import json
import numpy as np
from typing import Set
from sklearn.metrics.pairwise import cosine_similarity
import faiss
from datetime import datetime
from .config import SIMILARITY_THRESHOLDS, DEFAULT_THRESHOLD

async def run_similarity_matching(
    api_client,
    user_id: int,
    user_corpus_id: int,
    arxiv_corpus_id: int,
    profile_id: int = None,
    target_date: datetime = None,  
    threshold: float = 0.6,
    method: str = "cosine",
    model_name: str = "all-MiniLM-L6-v2",
    top_k: int = 50,
    use_sections: bool = True,
    paper_ids: Set[int] = None,
):
    """
    Run similarity matching between user papers and arXiv papers.
    paper_ids restricts which arXiv papers are compared: a set limits the
    comparison to those papers (an empty set means there is nothing to
    compare and no recommendations are produced) and None compares against
    the whole reference corpus.  Restricted papers are filtered further by
    the profile's categories when a profile is given.  target_date is
    recorded on the run but does not filter papers.
    """
    
    if isinstance(threshold, str):
        threshold_value = SIMILARITY_THRESHOLDS.get(threshold, DEFAULT_THRESHOLD)
    else:
        threshold_value = float(threshold) if threshold is not None else DEFAULT_THRESHOLD
    print(f"\nSimilarity Matching Configuration:")
    print(f"  Method: {method}")
    print(f"  Threshold: {threshold} ({threshold_value})")
    if target_date:
        print(f"  Target date: {target_date.strftime('%Y-%m-%d')}")
    print(f"  Using: {'Section embeddings' if use_sections else 'Abstract embeddings only'}")
    print(f"  Top-K: {top_k}")
    
    # Get profile categories for filtering
    profile_categories = []
    if profile_id:
        try:
            profile_resp = await api_client.client.get(f"{api_client.base_url}/profiles/{profile_id}")
            profile = profile_resp.json()
            profile_categories = profile.get('categories', [])
            
            if profile_categories:
                print(f"  Profile categories: {profile_categories}")
        except Exception as e:
            print(f"  Warning: Could not fetch profile categories: {e}")
    
    # Determine which arXiv papers to compare against.
    # None means no restriction; an empty set means restricted to nothing.
    candidate_ids = set(paper_ids) if paper_ids is not None else None

    if candidate_ids is None:
        print("  Warning: no paper_ids provided, comparing against all arXiv papers in corpus")

    # Filter candidates by profile categories
    if candidate_ids and profile_categories:
        papers = await api_client.get_papers_by_corpus(arxiv_corpus_id)
        papers_by_id = {p['id']: p for p in papers}

        filtered = set()
        for pid in candidate_ids:
            p = papers_by_id.get(pid)
            if not p:
                continue
            metadata = p.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            paper_cats = metadata.get('categories', [])
            if any(cat in paper_cats for cat in profile_categories):
                filtered.add(pid)

        candidate_ids = filtered

    total_papers_fetched = len(candidate_ids) if candidate_ids is not None else 0
    print(f"  Candidate papers: {total_papers_fetched}")
    
    # Create recommendation run with total_papers_fetched
    run = await api_client.create_recommendation_run(
            profile_id=profile_id,
            user_id=user_id,
            user_corpus_id=user_corpus_id,
            ref_corpus_id=arxiv_corpus_id,
            threshold=threshold,
            method=f"{method}_{'sections' if use_sections else 'abstract'}",
            total_papers_fetched=total_papers_fetched,
            target_date=target_date.date() if target_date else None
        )
    run_id = run["id"]
    print(f"\nCreated recommendation run ID: {run_id}")

    # An explicit but empty candidate set means there is nothing to recommend
    if candidate_ids is not None and not candidate_ids:
        print("  No candidate papers after filtering; nothing to recommend.")
        return run_id

    # Fetch embeddings based on mode
    # Fetch embeddings for user's papers
    emb_type = None if use_sections else "abstract"
    print(f"\nFetching embeddings ({'abstract + sections' if use_sections else 'abstract only'})...")
    user_embeddings = await api_client.get_embeddings_by_corpus(user_corpus_id, type=emb_type)
    
    # Fetch embeddings for new arXiv papers
    if candidate_ids is not None:
        arxiv_embeddings = await api_client.get_embeddings_by_corpus(
            arxiv_corpus_id, type=emb_type, paper_ids=list(candidate_ids)
        )
    else:
        arxiv_embeddings = await api_client.get_embeddings_by_corpus(arxiv_corpus_id, type=emb_type)
    
    if not user_embeddings:
        print("Error: No user embeddings found. Run embedding step first.")
        return None
    
    if not arxiv_embeddings:
        print("Error: No arXiv embeddings found for candidate papers.")
        return None
    
    print(f"  User embeddings: {len(user_embeddings)}")
    print(f"  arXiv embeddings: {len(arxiv_embeddings)}")
    
    # Group embeddings by paper
    user_papers = group_embeddings_by_paper(user_embeddings)
    arxiv_papers = group_embeddings_by_paper(arxiv_embeddings)
    
    print(f"  User papers: {len(user_papers)}")
    print(f"  arXiv papers: {len(arxiv_papers)}")
    
    # Compute similarities
    print(f"\nComputing paper-to-paper similarities...")
    
    paper_scores = {}
    
    for i, (arxiv_paper_id, arxiv_embs) in enumerate(arxiv_papers.items()):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(arxiv_papers)} arXiv papers...")
        
        max_similarity = 0.0
        
        for user_paper_id, user_embs in user_papers.items():
            similarity = compute_paper_similarity(user_embs, arxiv_embs, method)
            max_similarity = max(max_similarity, similarity)
        
        paper_scores[arxiv_paper_id] = max_similarity
    
    # Show score distribution
    print(f"\nSimilarity Score Distribution:")
    all_scores = list(paper_scores.values())
    if all_scores:
        print(f"  Max: {max(all_scores):.3f}")
        print(f"  Min: {min(all_scores):.3f}")
        print(f"  Mean: {sum(all_scores)/len(all_scores):.3f}")
        print(f"  Median: {sorted(all_scores)[len(all_scores)//2]:.3f}")
        
        for t_name, t_val in [("low", 0.5), ("medium", 0.6), ("high", 0.75)]:
            count = sum(1 for s in all_scores if s >= t_val)
            print(f"  Above {t_name} ({t_val}): {count} papers")
    
    # Show top matches regardless of threshold
    print(f"\nTop 10 Matches (regardless of threshold):")
    sorted_all = sorted(paper_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    for rank, (paper_id, score) in enumerate(sorted_all, 1):
        try:
            paper = await api_client.get_paper_by_id(paper_id)
            if paper:
                print(f"  {rank}. [{score:.3f}] {paper['title'][:70]}...")
        except:
            pass
    
    # Filter by threshold
    filtered_papers = {pid: score for pid, score in paper_scores.items() if score >= threshold_value}
    
    print(f"\nPapers above threshold ({threshold_value}): {len(filtered_papers)}")
    
    # Sort and take top-k
    sorted_papers = sorted(filtered_papers.items(), key=lambda x: x[1], reverse=True)[:top_k]
    
    print(f"Storing top {len(sorted_papers)} recommendations...")
    
    # Store recommendations
    stored_count = 0
    for rank, (paper_id, score) in enumerate(sorted_papers, 1):
        try:
            paper = await api_client.get_paper_by_id(paper_id)
            
            if not paper:
                continue
            
            await api_client.create_recommendation(
                run_id=run_id,
                paper_id=paper_id,
                score=score,
                rank=rank,
                summary=paper.get("abstract", "")[:500]
            )
            stored_count += 1
            
            if rank <= 10:
                print(f"  {rank}. [{score:.3f}] {paper['title'][:70]}...")
            
        except Exception as e:
            print(f"  Failed to store recommendation for paper {paper_id}: {e}")
    
    print(f"\nStored {stored_count} recommendations")
    
    return run_id
    

def group_embeddings_by_paper(embeddings):
    """Group embeddings by paper_id"""
    papers = {}
    for emb in embeddings:
        paper_id = emb['paper_id']
        if paper_id not in papers:
            papers[paper_id] = []
        papers[paper_id].append(emb['embedding'])
    return papers


def compute_paper_similarity(user_embs, arxiv_embs, method="cosine"):
    """
    Compute similarity between two papers using all their embeddings.
    Returns the maximum similarity across all embedding pairs.
    """
    user_matrix = np.array(user_embs, dtype=np.float32)
    arxiv_matrix = np.array(arxiv_embs, dtype=np.float32)
    
    if method == "faiss":
        similarities = compute_faiss_similarity(user_matrix, arxiv_matrix)
    else:
        similarities = compute_cosine_similarity(user_matrix, arxiv_matrix)
    
    return float(np.max(similarities))


def compute_cosine_similarity(user_matrix: np.ndarray, arxiv_matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between user and arXiv embeddings."""
    user_norm = user_matrix / (np.linalg.norm(user_matrix, axis=1, keepdims=True) + 1e-8)
    arxiv_norm = arxiv_matrix / (np.linalg.norm(arxiv_matrix, axis=1, keepdims=True) + 1e-8)
    return cosine_similarity(user_norm, arxiv_norm)


def compute_faiss_similarity(user_matrix: np.ndarray, arxiv_matrix: np.ndarray) -> np.ndarray:
    """Compute similarity using FAISS."""
    faiss.normalize_L2(user_matrix)
    faiss.normalize_L2(arxiv_matrix)
    dim = arxiv_matrix.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(arxiv_matrix)
    k = arxiv_matrix.shape[0]
    scores, _ = index.search(user_matrix, k)
    return scores
