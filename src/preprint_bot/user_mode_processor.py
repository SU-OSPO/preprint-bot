"""
Paper-centric processor for user-uploaded papers.

Finds all unprocessed papers in the database (regardless of which user
or profile they belong to), runs Grobid extraction, and generates
embeddings.  This avoids redundant processing when the same paper is
linked to multiple profiles.
"""
from pathlib import Path

from .config import DEFAULT_MODEL_NAME
from .api_client import APIClient
from .extract_grobid import extract_grobid_sections


# ── Grobid processing (paper-centric) ─────────────────────────────────────

async def process_unprocessed_papers(
    api_client: APIClient,
    skip_parse: bool = False,
    skip_embed: bool = False,
):
    """Find and process all papers that need Grobid and/or embeddings.

    This is the main entry point called by the pipeline.  It works
    directly on the papers table — no user/profile/corpus awareness.
    """
    parse_count = 0
    embed_count = 0

    # ── Step A: Grobid extraction for papers without sections ──────
    if not skip_parse:
        papers = await api_client.get_papers_needing_processing()
        print(f'\nFound {len(papers)} paper(s) needing Grobid processing')

        for paper in papers:
            pdf_path = paper.get('pdf_path')
            if not pdf_path or not Path(pdf_path).exists():
                print(f"  Skipping paper {paper['id']}: PDF not found at {pdf_path}")
                continue

            try:
                info = extract_grobid_sections(Path(pdf_path))

                # Update title/abstract from Grobid if still a placeholder
                grobid_title = info.get('title', '').strip()
                grobid_abstract = info.get('abstract', '').strip()
                updates = {}
                current_title = paper.get('title', '')
                is_placeholder = (
                    not current_title
                    or current_title == paper.get('arxiv_id')  # arXiv ID as title
                    or current_title == f"paper_{paper['id']}"  # auto-generated
                    or paper.get('source') == 'user'  # filename as title (safe:
                    # this only runs on first processing before sections exist,
                    # and there is no UI to manually edit paper titles)
                )
                if grobid_title and is_placeholder:
                    updates['title'] = grobid_title
                if grobid_abstract and not paper.get('abstract'):
                    updates['abstract'] = grobid_abstract
                if updates:
                    try:
                        await api_client.update_paper(paper['id'], **updates)
                    except Exception:
                        pass  # non-critical — placeholder title still works

                # Store sections
                sections_stored = 0
                for sec in info.get('sections', []):
                    try:
                        await api_client.create_section(
                            paper_id=paper['id'],
                            header=sec['header'],
                            text=sec['text'],
                        )
                        sections_stored += 1
                    except Exception:
                        pass

                parse_count += 1
                title = updates.get('title', current_title)
                print(f'  Processed: {title[:60]}... ({sections_stored} sections)')

            except Exception as e:
                print(f"  Failed to process paper {paper['id']}: {e}")

        print(f'  Grobid processing complete: {parse_count} paper(s)')

    # ── Step B: Embeddings for papers without them ─────────────────
    if not skip_embed:
        papers = await api_client.get_papers_needing_embeddings()
        print(f'\nFound {len(papers)} paper(s) needing embeddings')

        if papers:
            from .embed_papers import load_model, embed_single_paper

            model = load_model(DEFAULT_MODEL_NAME)

            for paper in papers:
                try:
                    abs_stored, sec_stored = await embed_single_paper(
                        api_client, paper, model, DEFAULT_MODEL_NAME
                    )
                    stored = abs_stored + sec_stored
                    if stored > 0:
                        embed_count += 1
                        print(f"  Embedded: {paper['title'][:60]}... ({stored} vectors)")
                except Exception as e:
                    print(f"  Failed to embed paper {paper['id']}: {e}")

            print(f'  Embedding complete: {embed_count} paper(s)')

    return {'parsed': parse_count, 'embedded': embed_count}
