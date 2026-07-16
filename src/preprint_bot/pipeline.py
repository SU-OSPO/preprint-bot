from __future__ import annotations
"""
Database-integrated Preprint Recommender Pipeline
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import List
from datetime import datetime, timezone, date as date_type
from email.utils import parsedate_to_datetime
import requests

from .config import (
    API_BASE_URL, DATA_DIR, DEFAULT_MODEL_NAME,
    PDF_DIR,
    SYSTEM_USER_EMAIL, SYSTEM_USER_NAME, ARXIV_CORPUS_NAME,
)
from .api_client import APIClient
from .download_arxiv_pdfs import download_arxiv_pdfs
from .embed_papers import embed_and_store_papers
from .extract_grobid import extract_grobid_sections
from .summarization_script import TransformerSummarizer
from .user_mode_processor import process_unprocessed_papers
from .db_similarity_matcher import run_similarity_matching
from .sources import ArxivSource, PaperEntry


async def get_all_profile_categories(api_client: APIClient) -> List[str]:
    try:
        response = await api_client.client.get(f"{api_client.base_url}/profiles/")
        response.raise_for_status()
        profiles = response.json()
        all_categories = set()
        for profile in profiles:
            all_categories.update(profile.get('categories', []))
        categories_list = list(all_categories)
        print(f"Found {len(categories_list)} unique categories from user profiles: {categories_list}")
        return categories_list
    except Exception as e:
        print(f"Error fetching profile categories: {e}")
        return []


async def fetch_preprint_papers(
    categories: List[str],
    target_date: datetime = None,
) -> List[PaperEntry]:
    """Fetch new papers from configured preprint sources.

    When ``target_date`` is None, fetches the latest announcement.
    When a date is provided, fetches papers for that specific
    historical date.
    """
    source = ArxivSource()

    if target_date is None:
        return await source.fetch_latest(categories)
    else:
        return await source.fetch_by_date(target_date, categories)


async def store_fetched_papers(
    api_client: APIClient,
    entries: List[PaperEntry],
    skip_download: bool = False,
    skip_parse: bool = False,
) -> tuple[int, set[int], set[int], int]:
    """Create a corpus and store fetched papers in the database.

    Returns ``(corpus_id, paper_ids, new_paper_ids, stored_count)`` where
    ``paper_ids`` is the full set of database IDs for all fetched papers
    (both newly stored and already existing), ``new_paper_ids`` is the
    subset that were newly created, and ``stored_count`` is how many
    were newly created.
    """
    user = await api_client.get_or_create_user(SYSTEM_USER_EMAIL, SYSTEM_USER_NAME)
    print(f"Using system user: {user['email']}")

    corpus = await api_client.get_or_create_corpus(
        user_id=user['id'],
        name=ARXIV_CORPUS_NAME,
        description="Automatically fetched preprint papers"
    )
    print(f"Using corpus: {corpus['name']} (ID: {corpus['id']})")

    if not entries:
        print("No papers to store")
        return corpus['id'], set(), set(), 0

    stored_count = 0
    paper_ids: set[int] = set()  # all paper IDs (new + existing)
    new_paper_ids: set[int] = set()  # only newly created papers
    for paper in entries:
        existing = await api_client.get_paper_by_arxiv_id(paper.source_id)
        if existing:
            paper_ids.add(existing['id'])
            continue

        submitted_date = None
        if paper.published:
            try:
                # Try ISO 8601 first (from API), then RFC 2822 (from RSS)
                try:
                    submitted_date = datetime.fromisoformat(
                        paper.published.replace('Z', '+00:00')
                    )
                except ValueError:
                    submitted_date = parsedate_to_datetime(paper.published)
                if submitted_date.tzinfo is not None:
                    submitted_date = submitted_date.astimezone(
                        timezone.utc
                    ).replace(tzinfo=None)
            except Exception as e:
                print(f"Failed to parse date for {paper.source_id}: {e}")

        try:
            created = await api_client.create_paper(
                corpus_id=corpus['id'],
                arxiv_id=paper.source_id,
                title=paper.title,
                abstract=paper.abstract,
                metadata={
                    "published": paper.published,
                    "arxiv_url": paper.url,
                    "authors": paper.authors,
                    "categories": paper.categories,
                    **paper.metadata,
                },
                source=paper.source,
                pdf_path=str(PDF_DIR / f"{paper.source_id}.pdf"),
                submitted_date=submitted_date,
            )
            paper_ids.add(created['id'])
            new_paper_ids.add(created['id'])
            stored_count += 1
        except Exception as e:
            print(f"Failed to store {paper.source_id}: {e}")

    print(f"Stored {stored_count} new papers in database ({len(paper_ids)} total)")

    if not skip_download and stored_count > 0:
        stats = download_arxiv_pdfs(
            [{"arxiv_url": p.url} for p in entries],
            output_folder=str(PDF_DIR),
            use_s3=False,
            min_delay=3,
        )

        # Warn if all downloads failed
        if stats and stats.get("downloaded", 0) == 0 and stats.get("failed", 0) > 0:
            print(
                f"WARNING: All {stats['failed']} PDF downloads failed. "
                f"Check network connectivity and file permissions."
            )

    if not skip_parse and stored_count > 0:
        print("\nParsing PDFs with GROBID...")
        await _parse_and_store_sections(api_client, corpus['id'], entries)

    return corpus['id'], paper_ids, new_paper_ids, stored_count


async def _parse_and_store_sections(
    api_client: APIClient, corpus_id: int, entries: List[PaperEntry]
):
    """Run GROBID on each paper's PDF and store sections directly to DB.

    Unlike the old process_folder → _output.txt → store_sections flow,
    this goes straight from GROBID's structured output to the database.
    """
    papers = await api_client.get_papers_by_corpus(corpus_id)
    entry_ids = {e.source_id for e in entries}
    papers = [p for p in papers if p.get('arxiv_id') in entry_ids]

    parsed = 0
    for paper in papers:
        pdf_path = paper.get('pdf_path')
        if not pdf_path or not Path(pdf_path).exists():
            continue

        try:
            info = extract_grobid_sections(Path(pdf_path))

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

            parsed += 1
            if sections_stored > 0:
                print(f"  {paper['arxiv_id']}: {sections_stored} sections")

        except Exception as e:
            print(f"  Failed to process {paper.get('arxiv_id', paper['id'])}: {e}")

    print(f"Parsed {parsed} papers, stored sections to database")


async def summarize_papers(
    api_client: APIClient,
    corpus_id: int,
    summarizer,
    entries: List[PaperEntry],
    mode: str = "abstract",
    paper_ids: set[int] | None = None,
):
    print(f"\nGenerating summaries using {type(summarizer).__name__}...")
    papers = await api_client.get_papers_by_corpus(corpus_id)
    entry_ids = {e.source_id for e in entries}
    papers = [p for p in papers if p.get('arxiv_id') in entry_ids]

    if paper_ids is not None:
        papers = [p for p in papers if p['id'] in paper_ids]
        print(f"  Filtered to {len(papers)} recommended papers")

    if not papers:
        print("  No papers found to summarize")
        return

    summarized_count = 0
    for paper in papers:
        if not paper.get('abstract'):
            continue
        try:
            summary_text = summarizer.summarize(paper['abstract'], max_length=150, mode=mode)
            await api_client.create_summary(
                paper_id=paper['id'],
                mode=mode,
                summary_text=summary_text,
                summarizer=type(summarizer).__name__
            )
            summarized_count += 1
            print(f"  {paper['title'][:60]}...")
        except Exception as e:
            print(f"  Failed: {paper.get('arxiv_id', paper['id'])}: {e}")

    print(f"\nGenerated {summarized_count} summaries")


async def generate_recommendations(api_client: APIClient, arxiv_corpus_id: int, user_corpora: List, target_date: datetime, paper_ids: set[int] = None) -> set:
    if not user_corpora:
        print("No user corpora to generate recommendations for")
        return set()

    print(f"Generating recommendations for {len(user_corpora)} user corpora")

    recommended_paper_ids = set()

    for corpus_info in user_corpora:
        user_corpus_id = corpus_info['corpus_id']
        user_id = corpus_info['user_id']
        profile = corpus_info['profile']

        print(f"\n  Profile: {profile['name']} (User {user_id})")

        try:
            run_id = await run_similarity_matching(
                api_client,
                user_id=user_id,
                user_corpus_id=user_corpus_id,
                arxiv_corpus_id=arxiv_corpus_id,
                profile_id=profile['id'],
                target_date=target_date,
                threshold=profile['threshold'],
                method='cosine',
                model_name=DEFAULT_MODEL_NAME,
                use_sections=True,
                paper_ids=paper_ids,
            )
            if run_id is None:
                print(f"    ✗ Skipped: no embeddings found")
                continue
            print(f"    ✓ Created recommendation run ID: {run_id}")

            recs = await api_client.get_recommendations_by_run(run_id)
            for rec in recs:
                recommended_paper_ids.add(rec['paper_id'])

        except Exception as e:
            print(f"    ✗ Failed: {e}")

    print(f"\n  Total unique recommended papers: {len(recommended_paper_ids)}")
    return recommended_paper_ids


async def send_all_digests(api_client: APIClient, run_date: str = None):
    run_date = run_date or str(date_type.today())
    run_date_obj = date_type.fromisoformat(run_date)

    try:
        response = await api_client.client.get(f"{api_client.base_url}/profiles/")
        response.raise_for_status()
        profiles = response.json()
    except Exception as e:
        print(f"  Failed to fetch profiles: {e}")
        return

    for profile in profiles:
        if not profile.get("email_notify", False):
            continue

        frequency = profile.get("frequency", "daily")

        # Check if today is the right day to send for this frequency
        if frequency == "weekly":
            # Send on Mondays only
            if run_date_obj.weekday() != 0:
                print(f"  - [{profile['name']}] skipped: weekly frequency, not Monday")
                continue
        elif frequency == "monthly":
            # Send on the 1st of each month only
            if run_date_obj.day != 1:
                print(f"  - [{profile['name']}] skipped: monthly frequency, not 1st of month")
                continue
        # "daily" falls through and always sends

        profile_id = profile["id"]
        user_id = profile["user_id"]

        resp = None
        try:
            resp = await api_client.client.post(
                f"{api_client.base_url}/emails/send-digest",
                json={"user_id": user_id, "profile_id": profile_id, "run_date": run_date}
            )
            resp.raise_for_status()
            result = resp.json()
            status = result.get("status")
            if status == "sent":
                print(f"  ✓ [{profile['name']}] → {result.get('to')} ({result.get('papers_count')} papers)")
            else:
                print(f"  - [{profile['name']}] skipped: {result.get('reason')}")
        except Exception as e:
            if resp is not None:
                print(
                    f"  ✗ [{profile['name']}] failed: {e} "
                    f"(status={getattr(resp, 'status_code', 'unknown')}, body={getattr(resp, 'text', '')})"
                )
            else:
                print(f"  ✗ [{profile['name']}] failed before receiving a response: {e}")


def _preflight_checks(args):
    """Verify the environment is correctly configured before running.

    Catches common problems (wrong user, unreachable services, missing
    directories) early so the pipeline fails fast with a clear message
    instead of producing orphaned DB records or silent download failures.
    """
    import os
    errors = []

    # ── Writable directories ───────────────────────────────────────────
    for d in [DATA_DIR, PDF_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        test_file = d / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            errors.append(
                f"Cannot write to {d} — are you running as the correct user? "
                f"(current uid={os.getuid()})"
            )

    # ── FastAPI reachable ──────────────────────────────────────────────
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if r.status_code != 200:
            errors.append(
                f"FastAPI at {API_BASE_URL} returned status {r.status_code} "
                f"(expected 200)"
            )
    except requests.ConnectionError:
        errors.append(f"Cannot connect to FastAPI at {API_BASE_URL}")
    except Exception as e:
        errors.append(f"FastAPI health check failed: {e}")

    # ── GROBID reachable (unless parsing is skipped) ──────────────────
    if not args.skip_parse:
        try:
            r = requests.get("http://localhost:8070/api/isalive", timeout=5)
            if r.status_code != 200:
                errors.append(
                    f"GROBID at localhost:8070 returned status {r.status_code}"
                )
        except requests.ConnectionError:
            errors.append(
                "Cannot connect to GROBID at localhost:8070 — "
                "is the grobid service running?"
            )
        except Exception as e:
            errors.append(f"GROBID health check failed: {e}")

    # ── LLaMA summarizer available (unless summarization is skipped) ──
    if not args.skip_summarize and args.summarizer == "llama":
        from .summarization_script import _LLAMA_AVAILABLE
        if not _LLAMA_AVAILABLE:
            errors.append(
                "llama-cpp-python is not installed but --summarizer llama "
                "was selected. Install it with: pip install '.[llama]', "
                "or use --summarizer transformer / --skip-summarize."
            )
        if not Path(args.llm_model).exists():
            errors.append(
                f"LLM model not found at {args.llm_model} — "
                f"use --summarizer transformer or --skip-summarize"
            )

    if errors:
        print("\n" + "=" * 60)
        print("PREFLIGHT CHECK FAILED")
        print("=" * 60)
        for err in errors:
            print(f"  ✗ {err}")
        print("=" * 60 + "\n")
        sys.exit(1)

    print("Preflight checks passed.\n")


async def run_pipeline(args):
    _preflight_checks(args)

    api_client = APIClient(base_url=API_BASE_URL)

    try:
        if args.date:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
            print("\n" + "="*80)
            print(f"PREPRINT BOT PIPELINE - {target_date.strftime('%Y-%m-%d')} (backfill)")
            print("="*80 + "\n")
        else:
            target_date = datetime.combine(date_type.today(), datetime.min.time())
            print("\n" + "="*80)
            print(f"PREPRINT BOT PIPELINE - latest announcement")
            print("="*80 + "\n")

        # Step 1 always runs — process papers uploaded since the last run
        print("="*60)
        print("STEP 1: Processing User Papers")
        print("="*60)
        user_result = await process_unprocessed_papers(
            api_client, skip_parse=args.skip_parse, skip_embed=args.skip_embed
        )
        print(f"  Summary: {user_result['parsed']} parsed, {user_result['embedded']} embedded")

        print("\n" + "="*60)
        print("STEP 2: Getting Categories from User Profiles")
        print("="*60)
        categories = await get_all_profile_categories(api_client)

        if not categories:
            print("ERROR: No categories found in user profiles.")
            print("Please create user profiles with categories before running the pipeline.")
            sys.exit(1)

        print("\n" + "="*60)
        print("STEP 3: Fetching Preprint Papers")
        print("="*60)
        entries = await fetch_preprint_papers(
            categories,
            target_date=target_date if args.date else None,
        )

        if not entries:
            print("No new papers fetched. Skipping steps 4–7.")
        else:
            print(f"Fetched {len(entries)} papers")

            corpus_id, paper_ids, new_paper_ids, stored_count = await store_fetched_papers(
                api_client,
                entries,
                skip_download=args.skip_download,
                skip_parse=args.skip_parse,
            )

            print("\n" + "="*60)
            print("STEP 4: Generating Embeddings")
            print("="*60)
            if not args.skip_embed and stored_count > 0:
                await embed_and_store_papers(
                    api_client,
                    corpus_id=corpus_id,
                    model_name=args.model,
                    paper_ids=new_paper_ids,  # only embed newly created papers
                )
            elif stored_count == 0:
                print("No new papers — skipping.")

            print("\n" + "="*60)
            print("STEP 5: Generating Summaries")
            print("="*60)
            if not args.skip_summarize and stored_count > 0:
                if args.summarizer == "llama":
                    if not Path(args.llm_model).exists():
                        print(f"Warning: LLM model not found at {args.llm_model}. Skipping summarization.")
                    else:
                        from .summarization_script import LlamaSummarizer
                        summarizer = LlamaSummarizer(model_path=args.llm_model)
                        await summarize_papers(api_client, corpus_id, summarizer, entries, mode="abstract")
                else:
                    summarizer = TransformerSummarizer()
                    await summarize_papers(api_client, corpus_id, summarizer, entries, mode="abstract")
            elif stored_count == 0:
                print("No new papers — skipping.")
            else:
                print("Skipping summarization.")

            # Gather user corpora for recommendations
            try:
                response = await api_client.client.get(f"{api_client.base_url}/profiles/")
                response.raise_for_status()
                all_profiles = response.json()
            except Exception as e:
                print(f"Failed to fetch profiles: {e}")
                all_profiles = []

            system_user = await api_client.get_user_by_email(SYSTEM_USER_EMAIL)
            system_user_id = system_user['id'] if system_user else None

            user_corpora = []
            for profile in all_profiles:
                if profile['user_id'] == system_user_id:
                    continue
                corpus_name = f"user_{profile['user_id']}_profile_{profile['id']}"
                corpus = await api_client.get_corpus_by_name(profile['user_id'], corpus_name)
                if corpus:
                    user_corpora.append({
                        'user_id': profile['user_id'],
                        'corpus_id': corpus['id'],
                        'profile': profile,
                    })

            print("\n" + "="*60)
            print("STEP 6: Generating Recommendations")
            print("="*60)
            await generate_recommendations(api_client, corpus_id, user_corpora, target_date, paper_ids=paper_ids)

            print("\n" + "="*60)
            print("STEP 7: Sending Email Digests")
            print("="*60)
            await send_all_digests(api_client, run_date=target_date.strftime("%Y-%m-%d"))

        # Cleanup always runs
        print("\n" + "="*60)
        print("STEP 8: Cleanup")
        print("="*60)
        print("Cleaning up temporary arXiv PDF files...")
        try:
            deleted_pdfs = 0
            for pdf in PDF_DIR.glob("*.pdf"):
                pdf.unlink()
                deleted_pdfs += 1
            print(f"  ✓ Deleted {deleted_pdfs} PDFs")
            print(f"  ✓ User paper files are safe (hash-based storage)")
        except Exception as e:
            print(f"  Warning: Cleanup failed: {e}")

        print("\n" + "="*80)
        print("PIPELINE COMPLETE!")
        print("="*80)
        print(f"  • Date: {target_date.strftime('%Y-%m-%d')}")
        print(f"  • User papers: {user_result['parsed']} parsed, {user_result['embedded']} embedded")
        print(f"  • Preprint papers: {len(entries)} fetched")
        print("="*80 + "\n")

    finally:
        await api_client.close()


def main():
    parser = argparse.ArgumentParser(description="Preprint Bot Pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--latest", action="store_true", default=True,
                      help="Fetch the latest announcement (default)")
    mode.add_argument("--date", help="Fetch papers for a specific historical date (YYYY-MM-DD)")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME, help="Embedding model name")
    parser.add_argument("--skip-download", action="store_true", help="Skip PDF download")
    parser.add_argument("--skip-parse", action="store_true", help="Skip GROBID parsing")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation")
    parser.add_argument("--skip-summarize", action="store_true", help="Skip summarization")
    parser.add_argument("--summarizer", default="llama", choices=["transformer", "llama"], help="Summarizer to use")
    parser.add_argument("--llm-model", default="models/llama-3.2-3b-instruct-q4_k_m.gguf", help="Path to LLM model")

    args = parser.parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
