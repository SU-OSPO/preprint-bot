"""
Module for embedding paper content using Sentence Transformers.
Database-integrated version — reads content from the API and stores
embeddings back via the same API.
"""
import torch
from sentence_transformers import SentenceTransformer
from typing import Dict, Set, Optional


def load_model(model_name: str) -> SentenceTransformer:
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = model.to(device)
    print(f"Model moved to {device}")
    return model


async def embed_single_paper(
    api_client,
    paper: Dict,
    model: SentenceTransformer,
    model_name: str,
) -> tuple[int, int]:
    """Generate and store embeddings for a single paper from DB content.

    Creates an abstract embedding (title + abstract) and section
    embeddings for each substantial section (>20 words).

    Returns ``(abstract_stored, sections_stored)``.
    """

    # Abstract embedding from title + abstract (fall back to sections if too short)
    title = paper.get('title', '')
    abstract = paper.get('abstract', '')
    abstract_text = f'{title}. {abstract}'.strip()

    # If title+abstract is too short, supplement with early section text
    sections = await api_client.get_sections_by_paper(paper['id'])
    if len(abstract_text.split()) <= 5 and sections:
        section_text = ' '.join(
            s.get('text', '') for s in sections[:3]  # first 3 sections
        ).strip()
        abstract_text = f'{abstract_text} {section_text}'.strip()

    if len(abstract_text.split()) > 5:  # need some content to embed
        emb = model.encode([abstract_text], normalize_embeddings=True)[0]
        await api_client.create_embedding(
            paper_id=paper['id'],
            embedding=emb.tolist(),
            type='abstract',
            model_name=model_name,
        )
        abstract_stored = 1
    else:
        abstract_stored = 0

    # Section embeddings — batch encode for efficiency
    sections_stored = 0
    eligible_sections = [
        s for s in sections if len(s.get('text', '').split()) > 20
    ]
    if eligible_sections:
        texts = [s['text'] for s in eligible_sections]
        embeddings = model.encode(texts, normalize_embeddings=True)
        for section, emb in zip(eligible_sections, embeddings):
            await api_client.create_embedding(
                paper_id=paper['id'],
                section_id=section['id'],
                embedding=emb.tolist(),
                type='section',
                model_name=model_name,
            )
            sections_stored += 1

    return abstract_stored, sections_stored


async def embed_and_store_papers(
    api_client,
    corpus_id: int,
    model_name: str,
    paper_ids: Optional[Set[int]] = None,
):
    """Embed papers in a corpus and store embeddings via the API.

    Reads paper content (title, abstract, sections) directly from the
    database — no intermediate text files.  When *paper_ids* is provided,
    only those papers are embedded; otherwise all papers in the corpus
    are processed.
    """
    print(f"\nEmbedding papers from corpus {corpus_id}")
    print(f"  Model: {model_name}")

    model = load_model(model_name)

    papers = await api_client.get_papers_by_corpus(corpus_id)
    if paper_ids is not None:
        papers = [p for p in papers if p['id'] in paper_ids]
    print(f"  Papers to embed: {len(papers)}")

    if not papers:
        print("  No papers to embed!")
        return

    abstract_count = 0
    section_count = 0
    skipped = 0

    for i, paper in enumerate(papers, 1):
        try:
            abs_stored, sec_stored = await embed_single_paper(api_client, paper, model, model_name)
            if abs_stored + sec_stored > 0:
                abstract_count += abs_stored
                section_count += sec_stored
                if i % 25 == 0:
                    print(f"  Embedded {i}/{len(papers)} papers...")
            else:
                skipped += 1
        except Exception as e:
            print(f"  Failed to embed paper {paper.get('arxiv_id', paper['id'])}: {e}")
            skipped += 1

    print(f"\nEmbedding complete!")
    print(f"  Abstract embeddings: {abstract_count}")
    print(f"  Section embeddings: {section_count}")
    if skipped:
        print(f"  Skipped: {skipped}")
