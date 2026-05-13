"""
Configuration file for the arXiv preprint recommendation pipeline.

SETUP INSTRUCTIONS:
1. Copy this file and rename it to config.py
2. Fill in the values marked with TODO
3. Do not commit config.py to version control - it contains sensitive credentials

DATABASE VERSION: Stores metadata in PostgreSQL, files in local directories.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# ==================== ARXIV SETTINGS ====================

# List of arXiv subject categories to fetch papers from
# Full list of categories: https://arxiv.org/category_taxonomy
# Examples: "cs.LG", "cs.CV", "cs.CL", "stat.ML"
ARXIV_CATEGORIES = [
    "cs.LG",  # TODO: add or remove categories as needed
]

# Similarity thresholds for filtering recommendations
# low: more results, less precise
# medium: balanced (recommended starting point)
# high: fewer results, more precise
SIMILARITY_THRESHOLDS = {
    "low": 0.5,
    "medium": 0.6,
    "high": 0.75
}

# Maximum number of papers to fetch per category per run
MAX_RESULTS = 10  # TODO: increase for production use

# ==================== MODEL SETTINGS ====================

# SentenceTransformer model for generating embeddings
# all-MiniLM-L6-v2 is fast and lightweight, good default
# For better quality try: all-mpnet-base-v2 (slower, more accurate)
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"  # TODO: change if needed

# ==================== DIRECTORY SETTINGS ====================

# Root directory for storing PDF files and processed text
# This directory will be created automatically if it doesn't exist
DATA_DIR = Path("pdf_data")  # TODO: change to an absolute path if needed

# Subdirectories - these are derived from DATA_DIR, no need to change
PDF_DIR = DATA_DIR / "pdfs"
PAPER_STORAGE_DIR = DATA_DIR / "papers"  # hash-based deduplicated storage

# Create all necessary directories on startup
for directory in [DATA_DIR, PDF_DIR, PAPER_STORAGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==================== SITE SETTINGS ====================

# Public-facing URL for the web interface (used in email digests)
SITE_URL = "https://preprint-bot.yourdomain.edu/"  # TODO: set to your deployment URL

# ==================== API SETTINGS ====================

# Base URL for the FastAPI backend
# Change this if running the API on a different host or port
API_BASE_URL = "http://127.0.0.1:8000"  # TODO: change for production deployment

# ==================== SYSTEM USER SETTINGS ====================

# System user for automated arXiv fetching operations
# This user is created automatically on first run
SYSTEM_USER_EMAIL = "your-email@institution.edu"  # TODO: change to your email
SYSTEM_USER_NAME = "Preprint Bot"  # TODO: change if desired

# Name of the corpus that stores arXiv papers
ARXIV_CORPUS_NAME = "arxiv_papers"  # TODO: change if desired

# ==================== PIPELINE / CRON SETTINGS ====================

# Email address to notify when the pipeline fails
NOTIFY_EMAIL = "your-email@institution.edu"  # TODO: change to your email

# Directory where cron job logs are stored
LOG_DIR = Path("logs/cron")  # TODO: change to an absolute path if needed

# Name of the pipeline script to run
PIPELINE_SCRIPT = "date_pipeline.py"

# Number of days to keep log files before deleting
LOG_RETENTION_DAYS = 30  # TODO: change if desired

# ==================== EMAIL SETTINGS ====================

# SMTP settings for email digests (optional — leave EMAIL_HOST empty to disable)
EMAIL_HOST = ""  # TODO: e.g. "smtp.office365.com"
EMAIL_PORT = 587
EMAIL_USER = ""  # TODO: SMTP login username
EMAIL_PASSWORD = ""  # TODO: SMTP login password
EMAIL_FROM_ADDRESS = "noreply@localhost"  # TODO: sender address
EMAIL_FROM_NAME = "Preprint Bot"  # TODO: sender display name

# ==================== DATABASE SETTINGS ====================

class Settings(BaseSettings):
    # TODO: change all values below to match your PostgreSQL setup
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "preprint_bot"  # TODO: name of your PostgreSQL database
    DATABASE_USER: str = "your_db_user"  # TODO: your PostgreSQL username
    DATABASE_PASSWORD: str = "your_db_password"  # TODO: your PostgreSQL password

    class Config:
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

