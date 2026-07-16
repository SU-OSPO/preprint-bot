"""
Enhanced arXiv PDF downloader with better rate limiting and monitoring.
"""

import os
import time
import random
import requests
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from collections import deque
from .config import DATA_DIR, USER_AGENT

HEADERS = {
    "User-Agent": USER_AGENT
}

class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on server responses.
    Tracks request history to enforce hourly limits.
    """
    
    def __init__(self, min_delay=5, max_delay=15, requests_per_hour=100):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.requests_per_hour = requests_per_hour
        self.last_request_time = 0
        
        # Track request timestamps for hourly limit
        self.request_history = deque(maxlen=requests_per_hour)
        
        # Adaptive delay based on recent rate limits
        self.current_delay = min_delay
        self.consecutive_successes = 0
        self.consecutive_rate_limits = 0
    
    def wait(self):
        """Wait with adaptive delay before allowing next request."""
        # Check hourly limit
        self._enforce_hourly_limit()
        
        # Calculate delay with jitter
        elapsed = time.time() - self.last_request_time
        delay = random.uniform(self.current_delay, self.current_delay + 5)
        
        if elapsed < delay:
            sleep_time = delay - elapsed
            print(f"Rate limiting: waiting {sleep_time:.1f}s...")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_history.append(time.time())
    
    def _enforce_hourly_limit(self):
        """Ensure we don't exceed requests per hour."""
        if len(self.request_history) >= self.requests_per_hour:
            oldest_request = self.request_history[0]
            time_since_oldest = time.time() - oldest_request
            
            if time_since_oldest < 3600:  # Less than 1 hour
                sleep_time = 3600 - time_since_oldest + random.uniform(1, 5)
                print(f"\nHourly limit reached ({self.requests_per_hour} requests/hour)")
                print(f"   Sleeping for {sleep_time/60:.1f} minutes...")
                time.sleep(sleep_time)
    
    def record_success(self):
        """Adjust rate limit after successful request."""
        self.consecutive_successes += 1
        self.consecutive_rate_limits = 0
        
        # Gradually decrease delay after consistent successes
        if self.consecutive_successes >= 10:
            self.current_delay = max(
                self.min_delay,
                self.current_delay * 0.9
            )
            self.consecutive_successes = 0
            print(f"   Reduced delay to {self.current_delay:.1f}s")
    
    def record_rate_limit(self):
        """Adjust rate limit after being rate limited."""
        self.consecutive_rate_limits += 1
        self.consecutive_successes = 0
        
        # Increase delay after rate limiting
        self.current_delay = min(
            self.max_delay,
            self.current_delay * 1.5
        )
        print(f"Increased delay to {self.current_delay:.1f}s")
    
    def get_stats(self):
        """Get rate limiter statistics."""
        if not self.request_history:
            return {
                "total_requests": 0,
                "requests_last_hour": 0,
                "current_delay": self.current_delay
            }
        
        now = time.time()
        recent = [t for t in self.request_history if now - t < 3600]
        
        return {
            "total_requests": len(self.request_history),
            "requests_last_hour": len(recent),
            "current_delay": self.current_delay,
            "oldest_request": datetime.fromtimestamp(self.request_history[0]).strftime("%H:%M:%S") if self.request_history else "N/A"
        }


def download_arxiv_pdfs(
    paper_metadata, 
    output_folder="arxiv_pipeline_data/arxiv_pdfs", 
    use_s3=False,
    min_delay=3,  # arXiv requires 3 seconds minimum
    max_retries=2,
    initial_backoff=5
):
    """
    Downloads PDFs respecting arXiv's ToS:
    - 3 seconds between requests
    - Single connection only
    - NO hourly limit enforcement (let arXiv handle it)
    """
    os.makedirs(output_folder, exist_ok=True)
    
    # Try S3 first
    if use_s3:
        # boto3/botocore are optional (extras_require["s3"]); import lazily so the
        # default HTTP download path doesn't require them.
        from .download_s3_bulk import download_from_s3_bulk, _BOTO3_AVAILABLE
        if not _BOTO3_AVAILABLE:
            print("  use_s3=True but boto3 is not installed "
                  "(pip install '.[s3]'); falling back to HTTP download.")
        else:
            try:
                s3_stats = download_from_s3_bulk(paper_metadata, output_folder)
                failed_papers = [p for p in paper_metadata 
                               if not os.path.exists(os.path.join(output_folder, f"{p['arxiv_url'].split('/')[-1]}.pdf"))]
                
                if not failed_papers:
                    return s3_stats
                
                print(f"HTTP fallback for {len(failed_papers)} papers...")
                paper_metadata = failed_papers
            except:
                pass
    
    total = len(paper_metadata)
    est_time = (total * min_delay) / 60
    
    print(f"\n{'='*60}")
    print(f"arXiv Download ({min_delay}s delay between requests)")
    print(f"Papers: {total}")
    print(f"Estimated time: {est_time:.1f} minutes")
    print(f"{'='*60}\n")
    
    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "start_time": time.time()}
    
    for paper in tqdm(paper_metadata, desc="Downloading", unit="paper"):
        arxiv_id = paper["arxiv_url"].split("/")[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_path = os.path.join(output_folder, f"{arxiv_id}.pdf")
        
        # Skip if exists
        if os.path.exists(pdf_path):
            stats["skipped"] += 1
            continue
        
        # Download with retry
        success = False
        for attempt in range(max_retries):
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
                
                # Rate limited - exponential backoff
                if r.status_code in [403, 429, 503]:
                    if attempt < max_retries - 1:
                        backoff = initial_backoff * (2 ** attempt)
                        tqdm.write(f"  Rate limited, waiting {backoff}s...")
                        time.sleep(backoff)
                        continue
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(initial_backoff)
                    continue
        
        if not success:
            stats["failed"] += 1
            tqdm.write(f"  Failed: {arxiv_id}")
    
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