"""
Fast bulk PDF download using arXiv's S3 bucket
No rate limits! ~200-300 papers per minute
"""
from pathlib import Path
from tqdm import tqdm

# boto3/botocore are an optional dependency (extras_require["s3"]). The S3 bulk
# download path is opt-in (use_s3=True) and unused by the default pipeline, so
# guard the import; download_from_s3_bulk() raises a clear error if called
# without it.
try:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
    _BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    UNSIGNED = None
    Config = None
    _BOTO3_AVAILABLE = False


def download_from_s3_bulk(paper_metadata, output_folder):
    """
    Download PDFs from arXiv S3 bucket with multiple path format attempts
    
    arXiv S3 bucket: arxiv
    Path formats to try:
    1. pdf/YYMM/YYMM.NNNNN.pdf (standard)
    2. pdf/arXiv_pdf_YYMM_NNN.tar (old bulk format)
    3. src/arXiv_src_YYMM_NNN.tar (source files)
    
    Args:
        paper_metadata: List of dicts with 'arxiv_url' keys
        output_folder: Where to save PDFs
    
    Returns:
        dict: Download statistics
    """
    if not _BOTO3_AVAILABLE:
        raise ImportError(
            "boto3 is required for S3 bulk download but is not installed. "
            "Install it with: pip install '.[s3]', or use the default HTTP "
            "downloader (use_s3=False)."
        )
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Anonymous S3 client (no credentials needed for public bucket)
    s3 = boto3.client('s3', 
                     region_name='us-east-1',
                     config=Config(signature_version=UNSIGNED))
    bucket = 'arxiv'
    
    stats = {
        'downloaded': 0,
        'failed': 0,
        'skipped': 0
    }
    
    print(f"\n{'='*60}")
    print(f"S3 Bulk Download (Fast Mode - No Rate Limits!)")
    print(f"Papers to download: {len(paper_metadata)}")
    print(f"{'='*60}\n")
    
    for paper in tqdm(paper_metadata, desc="Downloading from S3", unit="paper"):
        # Extract arXiv ID
        arxiv_id = paper["arxiv_url"].split("/")[-1]
        
        # Remove version suffix (e.g., v1, v2)
        clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
        
        local_path = output_path / f"{arxiv_id}.pdf"
        
        # Skip if exists
        if local_path.exists():
            stats['skipped'] += 1
            continue
        
        # Try different S3 path formats
        success = False
        
        try:
            # Parse YYMM from arxiv_id
            parts = clean_id.split('.')
            if len(parts) >= 2:
                yymm = parts[0]
                
                # Try multiple path formats
                s3_paths = [
                    f"pdf/{yymm}/{clean_id}.pdf",           # Standard: pdf/2601/2601.05789.pdf
                    f"pdf/{yymm}/{arxiv_id}.pdf",           # With version: pdf/2601/2601.05789v1.pdf
                    f"{yymm}/{clean_id}.pdf",               # Without pdf/ prefix
                    f"{yymm}/{arxiv_id}.pdf",               # Without pdf/ prefix, with version
                ]
                
                for s3_key in s3_paths:
                    try:
                        s3.download_file(bucket, s3_key, str(local_path))
                        stats['downloaded'] += 1
                        success = True
                        break
                    except:
                        continue
            
            if not success:
                stats['failed'] += 1
                if stats['failed'] <= 10:
                    tqdm.write(f"  S3 miss: {arxiv_id}")
        
        except Exception as e:
            stats['failed'] += 1
            if stats['failed'] <= 10:
                tqdm.write(f"  S3 error for {arxiv_id}: {str(e)[:50]}")
    
    print(f"\n{'='*60}")
    print("S3 Download Complete!")
    print(f"{'='*60}")
    print(f"  ✓ Downloaded: {stats['downloaded']}")
    print(f"  ⊘ Skipped: {stats['skipped']}")
    print(f"  ✗ Failed: {stats['failed']} (will retry via HTTP)")
    print(f"{'='*60}\n")
    
    return stats