"""
Preprint PDF downloader with rate limiting and retries.
"""

import os
import time
import random
import requests
from tqdm import tqdm
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from .config import USER_AGENT

HEADERS = {"User-Agent": USER_AGENT}

# Rejections worth retrying: rate limits (bioRxiv/medRxiv's Cloudflare
# answers 403) and server errors. Any other response won't change in a minute.
RETRYABLE_STATUSES = {403, 429, 500, 502, 503, 504}


def safe_filename(source_id: str, source: str = "") -> str:
    """Filesystem-safe stem for a source id (e.g. bioRxiv DOIs contain '/').

    The source is part of the stem because ids are only unique within their
    own server: without it two servers sharing an id write to one file, and
    the skip-if-exists check silently leaves the second paper pointing at the
    first one's PDF. Omitting *source* keeps the pre-multi-source naming, so
    paths already stored on existing rows still resolve.
    """
    stem = f"{source}_{source_id}" if source else source_id
    return stem.replace("/", "_")


def _retry_after_seconds(response) -> Optional[float]:
    """Seconds a ``Retry-After`` header asks for (delay or HTTP date), or None."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def download_arxiv_pdfs(
    paper_metadata,
    output_folder="arxiv_pipeline_data/arxiv_pdfs",
    use_s3=False,
    min_delay=3,  # arXiv requires 3 seconds minimum
    max_retries=5,
    initial_backoff=5,
    max_backoff=120,
    max_consecutive_failures=3,
):
    """
    Downloads PDFs respecting arXiv's ToS:
    - 3 seconds between requests
    - Single connection only
    - NO hourly limit enforcement (let arXiv handle it)

    A rejected or failed request (see RETRYABLE_STATUSES) is tried up to
    *max_retries* times, waiting ``initial_backoff * 2**attempt`` seconds plus
    up to 10% jitter between tries, or longer if the response's
    ``Retry-After`` asks. A paper whose next wait would exceed *max_backoff*
    is given up on for this run. Once *max_consecutive_failures* papers in a
    row fail after retrying, the rest are tried once each, so a long outage
    doesn't cost minutes per paper; the pipeline retries them in later runs.
    """
    os.makedirs(output_folder, exist_ok=True)

    # Try S3 first
    if use_s3:
        # boto3/botocore are optional (the [s3] extra); import lazily so the
        # default HTTP download path doesn't require them.
        from .download_s3_bulk import download_from_s3_bulk, _BOTO3_AVAILABLE

        if not _BOTO3_AVAILABLE:
            print(
                "  use_s3=True but boto3 is not installed "
                "(pip install '.[s3]'); falling back to HTTP download."
            )
        else:
            try:
                s3_stats = download_from_s3_bulk(paper_metadata, output_folder)
                failed_papers = [
                    p
                    for p in paper_metadata
                    if not os.path.exists(
                        os.path.join(output_folder, f"{p['arxiv_url'].split('/')[-1]}.pdf")
                    )
                ]

                if not failed_papers:
                    return s3_stats

                print(f"HTTP fallback for {len(failed_papers)} papers...")
                paper_metadata = failed_papers
            except Exception as e:
                print(f"  S3 bulk download failed ({e}); falling back to HTTP.")

    total = len(paper_metadata)
    est_time = (total * min_delay) / 60

    print(f"\n{'='*60}")
    print(f"arXiv Download ({min_delay}s delay between requests)")
    print(f"Papers: {total}")
    print(f"Estimated time: {est_time:.1f} minutes")
    print(f"{'='*60}\n")

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "start_time": time.time()}
    attempts_per_paper = max_retries
    # Papers in a row that were rejected and still failed after retrying
    consecutive_failures = 0

    for paper in tqdm(paper_metadata, desc="Downloading", unit="paper"):
        # Use the source-provided PDF URL directly; the stored filename mirrors
        # pipeline.store_fetched_papers' pdf_path.
        source_id = paper["source_id"]
        pdf_url = paper["pdf_url"]
        stem = safe_filename(source_id, paper.get("source", ""))
        pdf_path = os.path.join(output_folder, f"{stem}.pdf")

        # Skip if exists
        if os.path.exists(pdf_path):
            stats["skipped"] += 1
            continue

        # Download with retry
        success = False
        rejected = False
        for attempt in range(attempts_per_paper):
            retry_after = None
            try:
                # Enforce minimum delay
                time.sleep(min_delay)

                r = requests.get(pdf_url, headers=HEADERS, timeout=30)

                if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
                    with open(pdf_path, "wb") as f:
                        f.write(r.content)
                    stats["downloaded"] += 1
                    success = True
                    break

                if r.status_code not in RETRYABLE_STATUSES:
                    tqdm.write(f"  HTTP {r.status_code} for {source_id}, not retrying")
                    break
                retry_after = _retry_after_seconds(r)

            except Exception:
                pass

            # Rejected or errored - exponential backoff, or Retry-After if longer
            rejected = True
            if attempt == attempts_per_paper - 1:
                break
            backoff = max(initial_backoff * (2**attempt), retry_after or 0)
            if backoff > max_backoff:
                tqdm.write(f"  Asked to wait {backoff:.0f}s for {source_id}; giving up this run")
                break
            backoff += random.uniform(0, 0.1 * backoff)
            tqdm.write(
                f"  Attempt {attempt + 1}/{attempts_per_paper} failed for {source_id}, "
                f"waiting {backoff:.1f}s..."
            )
            time.sleep(backoff)

        if success:
            consecutive_failures = 0
        else:
            stats["failed"] += 1
            tqdm.write(f"  Failed: {source_id}")
            if rejected:
                consecutive_failures += 1
            if attempts_per_paper > 1 and consecutive_failures >= max_consecutive_failures:
                attempts_per_paper = 1
                tqdm.write(
                    f"  {consecutive_failures} papers in a row failed after retrying; "
                    "trying the rest once each"
                )

    # Final summary
    elapsed = time.time() - stats["start_time"]
    print(f"\n{'='*60}")
    print("Download Complete!")
    print(f"{'='*60}")
    print(f"   ✓ Downloaded: {stats['downloaded']}")
    print(f"  ⊘ Skipped: {stats['skipped']}")
    print(f"   ✗ Failed: {stats['failed']}")
    print(f"    Total time: {elapsed/60:.1f} minutes")
    print(f"   Speed: {stats['downloaded']/(elapsed/60) if elapsed > 0 else 0:.1f} papers/min")
    print(f"{'='*60}\n")

    return stats
