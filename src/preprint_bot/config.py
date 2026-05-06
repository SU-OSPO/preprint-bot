"""
Module to define global constants and create necessary directories
for the arXiv preprint recommendation pipeline.

DATABASE VERSION: Stores metadata in PostgreSQL, files in local directories.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# List of arXiv subject categories to query
ARXIV_CATEGORIES = [
    "cs.LG", 
]

# Predefined similarity thresholds for filtering paper recommendations
DEFAULT_THRESHOLD = 0.6

SIMILARITY_THRESHOLDS = {
    "low": 0.5,
    "medium": 0.7,
    "high": 0.9
}

# Maximum number of results to retrieve per query from arXiv
MAX_RESULTS = 30

# Default SentenceTransformer model used for embedding abstracts and sections
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"

# Root directory for storing files (NOT metadata - that goes to DB)
DATA_DIR = Path("pdf_data")

# Subdirectories for different file types
PDF_DIR = DATA_DIR / "pdfs"
PAPER_STORAGE_DIR = DATA_DIR / "papers"    # hash-based deduplicated storage


# Create all necessary directories
for directory in [DATA_DIR, PDF_DIR, PAPER_STORAGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "preprint_bot"
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str = ""

    # API
    API_BASE_URL: str = "http://127.0.0.1:8000"

    # Pipeline
    SYSTEM_USER_EMAIL: str = "abcd@syr.edu"
    USER_AGENT: str = "PreprintBot/1.0"


settings = Settings()

# Module-level aliases so existing imports (e.g. ``from .config import
# API_BASE_URL``) keep working without changes elsewhere.
API_BASE_URL = settings.API_BASE_URL
SYSTEM_USER_EMAIL = settings.SYSTEM_USER_EMAIL
SYSTEM_USER_NAME = "Preprint Bot"
USER_AGENT = settings.USER_AGENT

# Corpus naming
ARXIV_CORPUS_NAME = "arxiv_papers"
