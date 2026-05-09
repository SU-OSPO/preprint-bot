# Preprint Bot - Academic Paper Recommendation System

## Overview

Preprint Bot addresses the challenge of information discovery in academic research by automating the process of finding relevant papers from arXiv. Researchers create profiles with keywords and categories, upload their own papers, and receive personalized recommendations based on semantic similarity between their work and newly published preprints.

## Key Features

### Core Functionality
- **Automated arXiv Integration**: Fetch new papers daily, aligned to arXiv's announcement schedule
- **Multi-Profile Support**: Create multiple research profiles with different categories and papers per user
- **Semantic Search**: Vector similarity matching using sentence transformer embeddings
- **PDF Processing**: GROBID-based text extraction with section-level granularity
- **LLM Summarization**: Generate concise summaries using transformer or LLaMA models

### Technical Infrastructure
- **FastAPI Backend**: RESTful API with automatic OpenAPI documentation
- **PostgreSQL with pgvector**: Efficient vector similarity search at scale
- **Django Web Application**: Full-featured web interface for profile management and recommendation browsing
- **Nightly Automated Pipeline**: Background preprint processing

### User Features
- **Profile Management**: Create profiles with categories, frequency, and thresholds
- **Paper Upload**: Upload personal papers (PDFs) organized by profile
- **Smart Filtering**: Filter recommendations by date, score, keywords, and categories
- **Email Digests**: Automated email notifications with top recommendations

## System Architecture

> **Note:** Only actively maintained files are listed. Some legacy files scheduled for removal are present in the repository but omitted here.

```
preprint-bot/
├── django_site/                   # Django web application
│   ├── core/                      # Main Django app
│   │   ├── models.py              # ORM models
│   │   ├── views.py               # Request handlers
│   │   ├── urls.py                # URL routing
│   │   ├── forms.py               # Form definitions
│   │   ├── orcid.py               # ORCID OAuth integration
│   │   ├── auth_backend.py        # Custom authentication backend
│   │   ├── tests.py               # Django test suite
│   │   ├── templates/             # HTML templates
│   │   ├── static/                # CSS, JS, images
│   │   └── migrations/            # Database migrations
│   ├── preprint_bot_web/          # Django project settings
│   │   ├── settings.py
│   │   ├── local_settings.py      # Local overrides (not committed)
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── manage.py
├── routes/                        # FastAPI route modules
│   ├── auth.py                    # Authentication and password reset
│   ├── users.py                   # User management
│   ├── profiles.py                # Research profiles
│   ├── corpora.py                 # Paper collections
│   ├── papers.py                  # Paper metadata
│   ├── sections.py                # Paper sections
│   ├── embeddings.py              # Vector embeddings
│   ├── recommendations.py         # Recommendation results
│   ├── recommendation_runs.py     # Recommendation run tracking
│   ├── summaries.py               # Paper summaries
│   └── emails.py                  # Email digest sending
├── services/
│   └── email_service.py           # SMTP email handling
├── src/preprint_bot/              # Pipeline package
│   ├── pipeline.py                # Main orchestration pipeline
│   ├── api_client.py              # Async API client
│   ├── config.py                  # Global configuration constants
│   ├── sources/                   # Preprint server adapters
│   │   ├── base.py                # PaperEntry dataclass + PreprintSource ABC
│   │   └── arxiv.py               # arXiv RSS source (+ API fallback)
│   ├── download_arxiv_pdfs.py     # PDF downloading with rate limiting
│   ├── extract_grobid.py          # GROBID text extraction
│   ├── embed_papers.py            # Sentence transformer embeddings
│   ├── summarization_script.py    # Transformer and LLaMA summarization
│   ├── db_similarity_matcher.py   # Database-integrated similarity matching
│   └── user_mode_processor.py     # User paper processing
├── tests/                         # Pytest test suite
│   ├── conftest.py                # Shared fixtures
│   ├── test_config.py             # Configuration tests
│   ├── test_embed_papers.py       # Embedding tests
│   ├── test_extract_grobid.py     # Text extraction tests
│   ├── test_query_arxiv.py        # arXiv query tests
│   ├── test_schemas.py            # Schema validation tests
│   ├── test_similarity_matcher.py # Similarity computation tests
│   └── test_summarizer.py         # Text processing tests
├── main.py                        # FastAPI application entry point
├── database.py                    # AsyncPG connection pooling
├── schemas.py                     # Pydantic models and enums
├── setup.py                       # Package configuration
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Pytest configuration
└── README.md
```

## Database Schema

The system uses a 15-table PostgreSQL schema managed entirely via Django migrations (`django_site/core/migrations/`). Run `python manage.py migrate` to apply the schema.

**Core Tables:**
- `users`: User accounts with email-based authentication and optional ORCID linking (extends Django's `AbstractBaseUser`)
- `profiles`: Research profiles with preferences; keywords and arXiv categories are stored as `ArrayField` columns (no separate junction tables)
- `corpora`: Paper collections (arXiv corpus or user-uploaded)
- `papers`: Paper metadata, arXiv IDs, SHA-256 content hashes, and file paths
- `sections`: Extracted paper sections from GROBID
- `embeddings`: Vector embeddings (384-dimensional); linked to paper or section
- `summaries`: Generated paper summaries

**Recommendation Tables:**
- `recommendation_runs`: Tracking of recommendation computations
- `recommendations`: Scored and ranked paper recommendations
- `profile_recommendations`: Junction table linking profiles to recommendations

**Supporting Tables:**
- `profile_corpora`: Junction table linking profiles to corpora
- `auth_tokens`: SHA-256-hashed tokens for password reset and session management
- `email_logs`: Email delivery tracking
- `processing_runs`: Pipeline run status and error tracking
- `arxiv_daily_stats`: Per-category paper counts by submission date

## Prerequisites

### Required
- Python 3.10 or higher
- PostgreSQL 12+ with pgvector extension
- GROBID server 0.8.0+ (for PDF processing)
- 8GB RAM minimum, 16GB recommended
- 20GB disk space for paper storage

### Optional
- CUDA-capable GPU (for faster embedding generation)
- SMTP server (for email digests)

## Installation

### 1. System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib postgresql-server-dev-all
sudo apt-get install build-essential python3-dev
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Windows:**
Download and install PostgreSQL from https://www.postgresql.org/download/windows/

### 2. Install pgvector Extension
```bash
cd /tmp
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### 3. Database Setup
```bash
# Create database
sudo -u postgres createdb preprint_bot

# Create user
sudo -u postgres psql -c "CREATE USER preprint_user WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE preprint_bot TO preprint_user;"

# Connect and enable pgvector
sudo -u postgres psql preprint_bot -c "CREATE EXTENSION vector;"

# Apply database schema via Django migrations
cd django_site
python manage.py migrate
```

### 4. GROBID Setup

**Docker (Recommended):**
```bash
docker pull lfoppiano/grobid:0.8.0
docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0
```

**Manual Installation:**
```bash
wget https://github.com/kermitt2/grobid/archive/0.8.0.zip
unzip 0.8.0.zip
cd grobid-0.8.0
./gradlew run
```

Verify: `curl http://localhost:8070/api/isalive` should return `true`

### 5. Python Package Installation
```bash
# Clone repository
git clone https://github.com/SU-OSPO/preprint-bot.git
cd preprint-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install .

# Or install with all optional features
pip install ".[all]"

# Install specific extras
pip install ".[dev,test]"      # Development and testing
pip install ".[llama]"         # LLaMA summarization
```

### 6. Download LLaMA Model (default summarizer)

The pipeline uses LLaMA for summarization by default. Download the model and place it at the expected path:
```bash
mkdir -p models
# Download from Hugging Face (requires huggingface-cli)
pip install huggingface_hub
huggingface-cli download bartowski/Llama-3.2-3B-Instruct-GGUF \
    Llama-3.2-3B-Instruct-Q4_K_M.gguf \
    --local-dir models \
    --local-dir-use-symlinks False
mv models/Llama-3.2-3B-Instruct-Q4_K_M.gguf models/llama-3.2-3b-instruct-q4_k_m.gguf
```

Alternatively, skip LLaMA entirely and use the transformer-based summarizer instead:
```bash
preprint_bot --summarizer transformer
```

### 7. Configuration

The project uses two separate `.env` files — one for the FastAPI backend and pipeline, one for Django — plus `config.py` for hardcoded constants.

**Copy and configure `config.py`** (from `dummy_config.py`):
```bash
cp dummy_config.py config.py
```
Edit `config.py` and fill in all fields marked `TODO` (arXiv categories, email settings, paths). Never commit `config.py`.

**Create root `.env`** (FastAPI + pipeline runtime settings):
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=preprint_bot
DATABASE_USER=preprint_user
DATABASE_PASSWORD=your_db_password
API_BASE_URL=http://127.0.0.1:8000
SYSTEM_USER_EMAIL=system@yourdomain.edu
USER_AGENT=PreprintBot/1.0 (contact@yourdomain.edu)
```

**Create `django_site/.env`** (Django runtime settings):
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=preprint_bot
DATABASE_USER=preprint_user
DATABASE_PASSWORD=your_db_password
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.edu
API_BASE_URL=http://127.0.0.1:8000
PDF_DATA_DIR=/srv/preprint-bot/pdf_data
```

**Create `django_site/preprint_bot_web/local_settings.py`** (from the example):
```bash
cp django_site/preprint_bot_web/local_settings.py.example django_site/preprint_bot_web/local_settings.py
```
Edit `local_settings.py` and fill in your ORCID credentials, branding, CSRF trusted origins, and deployment-specific paths.

Add all config files to `.gitignore`:
```bash
echo ".env" >> .gitignore
echo "django_site/.env" >> .gitignore
echo "django_site/preprint_bot_web/local_settings.py" >> .gitignore
echo "config.py" >> .gitignore
```

## Usage

### Starting Services

**GROBID:**
```bash
docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0
```

**FastAPI Backend:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Django Web App:**
```bash
cd django_site
python manage.py runserver 8001
```

Access points:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Web UI: http://localhost:8001

### Pipeline Workflow

The pipeline is a single unified command. It automatically reads arXiv categories from all user profiles, fetches new papers, processes user-uploaded PDFs, generates embeddings, runs similarity matching, and sends email digests.

```bash
# Run the full pipeline (fetches the latest arXiv announcement)
preprint_bot

# Backfill a specific historical date
preprint_bot --date 2026-05-01

# Skip slow steps during development or testing
preprint_bot --skip-download --skip-parse --skip-summarize
```

### Advanced Usage

#### GPU Acceleration
```bash
# Enable GPU for embeddings (10-20x speedup)
# In embed_papers.py, remove: os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Check GPU usage
nvidia-smi
```

#### Custom Summarization
```bash
# Transformer-based (faster, lower quality)
preprint_bot --summarizer transformer

# LLaMA-based (slower, higher quality)
preprint_bot --summarizer llama \
    --llm-model models/llama-3.2-3b-instruct-q4_k_m.gguf
```

## API Reference

### Users
```bash
# Create user
POST /users/
Body: {"email": "user@example.com", "name": "Dr. User"}

# Get user
GET /users/{user_id}

# Update user
PATCH /users/{user_id}
Body: {"name": "Updated Name"}
```

### Profiles
```bash
# Create profile
POST /profiles/
Body: {
  "user_id": 1,
  "name": "AI Research",
  "keywords": ["machine learning", "neural networks"],
  "categories": ["cs.LG", "cs.AI"],
  "frequency": "weekly",
  "threshold": 0.7,
  "top_x": 10
}

# Get user profiles
GET /profiles/?user_id=1

# Update profile
PUT /profiles/{profile_id}
```

### Papers
```bash
# Create paper
POST /papers/
Body: {
  "corpus_id": 1,
  "arxiv_id": "2501.12345",
  "title": "Paper Title",
  "abstract": "Paper abstract...",
  "source": "arxiv"
}

# Get papers by corpus
GET /papers/?corpus_id=1

# Search similar papers
POST /embeddings/search/similar
Body: {
  "embedding": [0.1, 0.2, ...],  # 384-dim vector
  "corpus_id": 1,
  "threshold": 0.6,
  "limit": 10
}
```

### Recommendations
```bash
# Get recommendations for profile
GET /recommendations/profile/{profile_id}?limit=50

# Get recommendations with full paper details
GET /recommendations/run/{run_id}/with-papers?limit=50

# Create recommendation run
POST /recommendation-runs/
Body: {
  "user_id": 1,
  "profile_id": 1,
  "user_corpus_id": 2,
  "ref_corpus_id": 1,
  "threshold": 0.7,
  "method": "faiss"
}
```

### Email
```bash
# Send recommendations digest
POST /emails/send-digest
Body: {"user_id": 1, "profile_id": 1}

# Test email configuration
POST /emails/test-email?to_email=test@example.com
```

Complete API documentation available at http://localhost:8000/docs

## Configuration

The project uses four configuration files:

**Root `.env`** (FastAPI + pipeline runtime settings):
Database credentials, API URL, system user email, and User-Agent string. Loaded by `pydantic_settings` when FastAPI and the pipeline start. Never commit this file.

**`config.py`** (copied from `dummy_config.py`; FastAPI + pipeline constants):
Hardcoded settings that change infrequently — arXiv categories, similarity thresholds, model name, file paths, and email settings. Fill in all fields marked `TODO`. Never commit this file.

**`django_site/.env`** (Django runtime settings):
Database credentials, Django secret key, allowed hosts, debug flag, API URL, and PDF data directory. Never commit this file.

**`django_site/preprint_bot_web/local_settings.py`** (Django deployment overrides):
Deployment-specific Django settings — script prefix, static/media URLs, CSRF trusted origins, ORCID credentials, branding (site name, accent/nav colours, support email), registration control, and SSL proxy header. Copy from `local_settings.py.example` and fill in your values. Never commit this file.

### FastAPI + Pipeline Settings

**File:** `config.py`
```python
# arXiv categories to query
ARXIV_CATEGORIES = ["cs.LG"]

# Default similarity threshold
DEFAULT_THRESHOLD = 0.6

# Similarity thresholds by name
SIMILARITY_THRESHOLDS = {
    "low": 0.5,
    "medium": 0.7,
    "high": 0.9
}

# Maximum number of results to retrieve per arXiv query
MAX_RESULTS = 30

# Embedding model
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"

# File storage paths
DATA_DIR = Path("pdf_data")
PDF_DIR = DATA_DIR / "pdfs"
PAPER_STORAGE_DIR = DATA_DIR / "papers"  # hash-based deduplicated storage
```

### Database Settings

Both `.env` files share the same database connection variables:
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=preprint_bot
DATABASE_USER=preprint_user
DATABASE_PASSWORD=your_db_password
```

### Email Settings

Required for automated digest emails:
```env
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USER=your_email@university.edu
EMAIL_PASS=your_password
EMAIL_FROM_NAME=Preprint Bot
EMAIL_FROM_ADDRESS=your_email@university.edu
```

## Command Line Interface

The pipeline is invoked as a single unified `preprint_bot` command. arXiv categories are read automatically from user profiles — there is no need to specify them on the command line.

### Running the Pipeline
```bash
# Fetch and process the latest arXiv announcement (default)
preprint_bot

# Backfill a specific historical date
preprint_bot --date 2026-01-15
```

### Skipping Steps
```bash
preprint_bot --skip-download    # Skip PDF download
preprint_bot --skip-parse       # Skip GROBID section parsing
preprint_bot --skip-embed       # Skip embedding generation
preprint_bot --skip-summarize   # Skip summarization
```

### Summarization
```bash
# Transformer-based
preprint_bot --summarizer transformer

# LLaMA-based with a custom model path
preprint_bot --summarizer llama --llm-model models/llama-3.2-3b-instruct-q4_k_m.gguf
```

### All Arguments
```
--date DATE                   Fetch papers for a specific historical date
                              (YYYY-MM-DD); omit to fetch the latest announcement
--model MODEL                 Sentence transformer model name
                              (default: all-MiniLM-L6-v2)
--summarizer {transformer,llama}
                              Summarization backend (default: llama)
--llm-model PATH              Path to LLaMA model file
--skip-download               Skip PDF download
--skip-parse                  Skip GROBID section parsing
--skip-embed                  Skip embedding generation
--skip-summarize              Skip summarization
```

## Web Interface

The web interface is a Django application located in `django_site/`. It reads and writes directly to the shared PostgreSQL database via Django ORM. The FastAPI backend is used separately by the pipeline and is not called over HTTP by the Django app.

### Features

**Dashboard:**
- Profile and corpus counts
- Recent recommendations (today's papers)
- Quick access to latest papers

**Profiles:**
- Create/edit profiles with keywords, arXiv categories, frequency, threshold, and max recommendations
- Upload PDFs directly through the web interface
- View uploaded papers with file size
- Delete individual papers or entire profiles

**Recommendations:**
- Filter by profile, date range, score, keywords, and categories
- Quick filters: Today, Last 7 days, Last 30 days, All time
- Adjustable paper limit per profile
- Date-grouped display with expandable paper cards
- Direct links to arXiv

**Account:**
- User registration and login
- ORCID account linking and unlinking
- Password reset via email

### Starting the Web Interface
```bash
# Ensure FastAPI backend is running first (see Starting Services above)

# Start Django development server
cd django_site
python manage.py runserver 8001
```

Access at http://localhost:8001

## Testing

### Pipeline Tests (pytest)

The `tests/` directory contains unit tests for the pipeline package, run with pytest from the repo root.

```bash
# All pipeline tests
pytest -v

# Specific module
pytest tests/test_config.py -v

# With coverage
pytest --cov=src/preprint_bot --cov-report=html
open htmlcov/index.html

# Parallel execution (faster)
pip install pytest-xdist
pytest -n auto

# Stop on first failure
pytest -x

# Verbose output with full tracebacks
pytest -vv --tb=long
```

### Django Tests

The Django app has its own test suite in `django_site/core/tests.py`, covering arXiv ID parsing, SHA-256 hashing, form validation, auth flows (registration, login, logout, email verification, access control), profile CRUD and ownership, ORCID OAuth2 flows, and paper upload deduplication. Run these with Django's test runner from the `django_site/` directory:

```bash
cd django_site
python manage.py test core
```

### Writing New Tests

Follow the existing test structure:
```python
# tests/test_yourmodule.py
import pytest

class TestYourFeature:
    def test_basic_functionality(self):
        from preprint_bot.yourmodule import your_function
        
        result = your_function(test_input)
        assert result == expected_output
    
    @pytest.mark.parametrize("input,expected", [
        ("input1", "output1"),
        ("input2", "output2"),
    ])
    def test_parametrized(self, input, expected):
        from preprint_bot.yourmodule import your_function
        assert your_function(input) == expected
```

Use fixtures from `conftest.py` for common test data.

## Performance Optimization

### Database
```sql
-- Monitor slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Optimize vector index for your dataset size
-- For 100K vectors
CREATE INDEX idx_embeddings_vector ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 1000);

-- For 1M vectors
WITH (lists = 10000);

-- Regular maintenance
VACUUM ANALYZE embeddings;
VACUUM ANALYZE papers;
REINDEX INDEX idx_embeddings_vector;
```

### Embedding Generation
```python
# Enable GPU (10-20x speedup)
# In embed_papers.py, remove: os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Batch processing
model.encode(texts, batch_size=32, show_progress_bar=True)

# Use smaller model for speed
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, 384 dims

# Use larger model for accuracy
DEFAULT_MODEL_NAME = "all-mpnet-base-v2"  # Slower, 768 dims
```

### PDF Downloads
```python
# Downloads respect arXiv rate limits:
# - 3 seconds between requests
# - 100 requests per hour maximum
# - Single connection only

# For 200 papers: ~10 minutes
# For 1000 papers: ~50 minutes with automatic batching
```

### GROBID Processing
```python
# Increase timeout for large PDFs
# In extract_grobid.py
timeout=300  # 5 minutes instead of 60 seconds
```

## arXiv Integration

### Rate Limits and Best Practices

**Official arXiv Guidelines:**
- Maximum 1 request every 3 seconds
- Single connection at a time (no parallel downloads)
- Limit to 100 requests per hour for sustained access
- Use respectful User-Agent header

**Implementation:**
- Automatic rate limiting with adaptive delays
- Exponential backoff on 403/429/503 errors
- Progress tracking with estimated time remaining
- Automatic batching for large downloads (90 papers per batch)

### Publication Schedule

arXiv publishes new papers:
- **Time:** 8:00 PM US Eastern Time
- **Days:** Sunday through Thursday
- **No announcements:** Friday and Saturday

**Recommended Pipeline Schedule:**
```bash
# systemd timer: Run daily at 1:30 AM EST (after midnight RSS feed update)
# See /etc/systemd/system/preprint-bot.timer
OnCalendar=*-*-* 01:30:00
```

The pipeline uses arXiv RSS feeds (primary) for daily runs and falls
back to the arXiv search API with submission-window calculation for
backfilling historical dates. The RSS approach automatically handles
weekend gaps and holiday deferrals.

## Database Operations

### Manual Queries
```sql
-- Get user's profiles
SELECT * FROM profiles WHERE user_id = 1;

-- Get recommendations for profile
SELECT r.score, p.title, p.arxiv_id
FROM recommendations r
JOIN recommendation_runs rr ON r.run_id = rr.id
JOIN papers p ON r.paper_id = p.id
WHERE rr.profile_id = 1
ORDER BY r.score DESC
LIMIT 10;

-- Find papers by keyword
SELECT title, abstract
FROM papers
WHERE title ILIKE '%transformer%'
   OR abstract ILIKE '%transformer%';

-- Check embedding coverage
SELECT 
    COUNT(DISTINCT p.id) as total_papers,
    COUNT(DISTINCT e.paper_id) as papers_with_embeddings
FROM papers p
LEFT JOIN embeddings e ON p.id = e.paper_id;

-- Vector similarity search (raw SQL)
SELECT p.title, 1 - (e.embedding <=> '[0.1,0.2,...]'::vector) as similarity
FROM embeddings e
JOIN papers p ON e.paper_id = p.id
WHERE e.type = 'abstract'
ORDER BY e.embedding <=> '[0.1,0.2,...]'::vector
LIMIT 10;
```

### Backup and Restore
```bash
# Backup database
pg_dump -U preprint_user preprint_bot > backup_$(date +%Y%m%d).sql

# Restore database
psql -U preprint_user preprint_bot < backup_20260113.sql

# Backup only schema
pg_dump -U preprint_user --schema-only preprint_bot > schema.sql

# Backup only data
pg_dump -U preprint_user --data-only preprint_bot > data.sql
```

## Troubleshooting

### Common Issues

**GROBID Connection Failed:**
```bash
# Check if GROBID is running
curl http://localhost:8070/api/isalive

# Restart GROBID
docker restart grobid

# Check logs
docker logs grobid
```

**Database Connection Errors:**
```bash
# Test connection
psql -U preprint_user -d preprint_bot -c "SELECT 1;"

# Check if PostgreSQL is running
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql
```

**pgvector Extension Not Found:**
```sql
-- Check if installed
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- Enable extension
CREATE EXTENSION vector;

-- Verify
\dx
```

**Import Errors:**
```bash
# Reinstall in development mode
pip install -e .

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Verify installation
python -c "import preprint_bot; print(preprint_bot.__file__)"
```

**Out of Memory:**
```python
# Reduce batch size in embed_papers.py
embeddings = model.encode(texts, batch_size=16)

# Force CPU usage
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Process in smaller batches
for i in range(0, len(papers), 100):
    batch = papers[i:i+100]
    process_batch(batch)
```

**GROBID Timeouts:**
```python
# Increase timeout in extract_grobid.py
resp = requests.post(GROBID_URL, files=files, timeout=300)

# Add retry logic
for attempt in range(3):
    try:
        result = extract_grobid_sections(pdf)
        break
    except:
        time.sleep(2 ** attempt)
```

**arXiv Rate Limiting:**
```
Rate limited (HTTP 403/429/503)
```
Solution: System automatically handles this with exponential backoff. If persistent, reduce `requests_per_hour` or increase `min_delay`.

## Development

### Project Structure
```python
# Pipeline modules
pipeline.py                # Orchestrates the full corpus/user workflow
api_client.py              # Async API client for the FastAPI backend
sources/arxiv.py           # arXiv RSS fetching + API fallback
sources/base.py            # PreprintSource ABC + PaperEntry dataclass
embed_papers.py            # Sentence transformer embedding generation
db_similarity_matcher.py   # FAISS / cosine similarity matching

# Processing modules
download_arxiv_pdfs.py     # PDF downloading with rate limiting
extract_grobid.py          # GROBID text extraction
summarization_script.py    # Transformer and LLaMA summarization
user_mode_processor.py     # User paper processing

# FastAPI modules (repo root)
main.py                    # FastAPI application entry point
routes/                    # Endpoint definitions
schemas.py                 # Request/response models
database.py                # AsyncPG connection management

# Django web app
django_site/core/views.py  # Request handlers
django_site/core/models.py # ORM models
django_site/core/orcid.py  # ORCID OAuth integration
```

### Adding New Features

1. **New API Endpoint:**
   - Add route in `routes/`
   - Define schemas in `schemas.py`
   - Update `main.py` to include router
   - Add tests in `tests/`

2. **New Pipeline Step:**
   - Implement function in appropriate module
   - Add to `pipeline.py` workflow
   - Add CLI arguments
   - Add tests

3. **New Similarity Method:**
   - Implement in `db_similarity_matcher.py`
   - Update `run_similarity_matching()`

### Code Style
```bash
# Format code
pip install black isort
black src/ tests/
isort src/ tests/

# Lint
pip install flake8
flake8 src/ tests/ --max-line-length=120

# Type checking
pip install mypy
mypy src/
```

## Deployment

### Production Deployment

**Deploying API using systemd:**
```ini
[Unit]
Description=Preprint Bot API
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/preprint-bot
Environment="PATH=/opt/preprint-bot/venv/bin"
ExecStart=/opt/preprint-bot/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Caddy Reverse Proxy:**
```
preprint-bot.yourdomain.edu {
    handle /docs* {
        reverse_proxy localhost:8000
    }
    handle /redoc* {
        reverse_proxy localhost:8000
    }
    handle /openapi.json {
        reverse_proxy localhost:8000
    }
    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle {
        reverse_proxy localhost:8001
    }
}
```

### Automated Scheduling
**Using systemd Timer:**

Create two unit files:

`/etc/systemd/system/preprint-bot-pipeline.service`:
```ini
[Unit]
Description=Preprint Bot Pipeline
After=network.target postgresql.service

[Service]
Type=oneshot
User=preprint-bot
WorkingDirectory=/opt/preprint-bot
Environment="PATH=/opt/preprint-bot/venv/bin"
ExecStart=/opt/preprint-bot/daily_pipeline.sh
```

`/etc/systemd/system/preprint-bot-pipeline.timer`:
```ini
[Unit]
Description=Preprint Bot Pipeline Timer

[Timer]
OnCalendar=*-*-* 01:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now preprint-bot-pipeline.timer

# Check status
sudo systemctl status preprint-bot-pipeline.timer

# Run pipeline manually
sudo systemctl start --no-block preprint-bot-pipeline
```

## Monitoring

### Logging
```python
# Configure logging in main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('preprint_bot.log'),
        logging.StreamHandler()
    ]
)
```

### Metrics
```bash
# Check database stats
curl http://localhost:8000/stats

# Monitor API health
curl http://localhost:8000/health
```

### Database Monitoring
```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'preprint_bot';

-- Table sizes
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan;
```

## Contributing

### Development Setup
```bash
# Install with development dependencies
pip install ".[dev,test]"

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Pull Request Process

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run test suites: `pytest -v` and `cd django_site && python manage.py test core`
5. Format code: `black src/ tests/`
6. Commit changes: `git commit -m "Add new feature"`
7. Push to branch: `git push origin feature/new-feature`
8. Submit pull request with description

### Coding Standards

- Follow PEP 8 style guide
- Add docstrings to all functions
- Include type hints where appropriate
- Write tests for new functionality
- Update documentation for API changes
- Keep functions focused and modular

## Maintenance

### Regular Tasks

**Daily:**
- Monitor API logs for errors
- Check GROBID server status
- Verify recommendation runs completed

**Weekly:**
- Review failed downloads/processing
- Check database growth and performance
- Update user profiles if needed

**Monthly:**
- Vacuum and analyze database
- Review and archive old recommendations
- Update dependencies: `pip list --outdated`

### Updating Dependencies
```bash
# Update all packages
pip install --upgrade -r requirements.txt

# Update specific package
pip install --upgrade sentence-transformers

# Check for security vulnerabilities
pip install safety
safety check
```

## Citation
```bibtex
@software{preprint_bot_2026,
  title={Preprint Bot: Database-Integrated Academic Paper Recommendation System},
  author={Syracuse University OSPO},
  year={2026},
  url={https://github.com/SU-OSPO/preprint-bot},
  note={FastAPI + PostgreSQL + pgvector + Django implementation}
}
```

## Support

- GitHub Issues: https://github.com/SU-OSPO/preprint-bot/issues
- API Documentation: http://localhost:8000/docs
- Email: ospo@syr.edu

## Acknowledgments

- arXiv for providing open access to scientific preprints
- GROBID for robust PDF text extraction
- Sentence Transformers for state-of-the-art embeddings
- pgvector for efficient vector similarity search in PostgreSQL
- FastAPI for modern async web framework
- Django for the web application framework
