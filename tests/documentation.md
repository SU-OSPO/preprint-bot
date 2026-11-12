# Preprint Bot Test Suite Documentation

## Overview

Test suite for the Preprint Bot academic paper recommendation system. Contains 64 unit tests covering core functionality across 8 test modules with comprehensive coverage of configuration, data processing, similarity matching, and API schemas.

## Test Structure
```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_config.py           # Configuration and directory structure tests
├── test_embed_papers.py     # Embedding and arXiv ID normalization tests
├── test_extract_grobid.py   # GROBID text extraction tests
├── test_pdf_retry.py        # PDF download retries, within a run and in later runs
├── test_query_arxiv.py      # arXiv API query tests
├── test_schemas.py          # Pydantic schema validation tests
├── test_similarity_matcher.py  # Vector similarity computation tests
└── test_summarizer.py       # Text processing and summarization tests
```

## Running Tests

### Basic Execution
```bash
pytest tests/ -v
```

### With Coverage Report
```bash
pytest tests/ --cov=src/preprint_bot --cov-report=html
```

### Specific Test File
```bash
pytest tests/test_config.py -v
```

### Specific Test Class
```bash
pytest tests/test_config.py::TestConfig -v
```

## Test Modules

### conftest.py

Provides shared fixtures used across test modules.

**Fixtures:**
- `temp_dir`: Creates temporary directory for file operations
- `temp_user_structure`: Creates test UID/PID directory structure with dummy PDFs
- `sample_embeddings`: Provides sample embedding vectors for testing
- `sample_text`: Markdown-formatted text for section extraction tests

### test_config.py

Tests configuration management and directory structure utilities.

**Test Classes:**
- `TestConfig`: Core configuration tests
- `TestParametrizedThresholds`: Validates all similarity threshold levels

**Key Tests:**
- Similarity thresholds are properly ordered (low < medium < high)
- All thresholds are within valid range (0.0 to 1.0)
- Directory structure scanning with valid UID/PID format
- Handling of invalid/non-numeric directories
- Non-existent directory handling

### test_embed_papers.py

Tests arXiv ID normalization and embedding utilities.

**Test Classes:**
- `TestEmbedPapers`: Basic normalization tests
- `TestParametrizedArxivIds`: Parametrized tests for edge cases

**Key Tests:**
- Removes version suffixes from arXiv IDs (e.g., v1, v2)
- Handles IDs without version suffixes
- Edge cases with multiple 'v' characters
- Empty string handling

### test_extract_grobid.py

Tests GROBID text extraction and tokenization.

**Test Classes:**
- `TestExtractGrobid`: Tokenization tests with and without spaCy

**Key Tests:**
- Sentence tokenization with spaCy disabled (fallback mode)
- Empty string handling
- Single sentence tokenization
- Blank line separation in fallback mode

### test_pdf_retry.py

Tests retrying rejected PDF downloads (`download_arxiv_pdfs`, `pipeline.recover_missing_fulltext`).

**Test Classes:**
- `TestRetryAfter`: Parsing `Retry-After` as seconds or an HTTP date
- `TestDownloadRetries`: Exponential backoff with jitter, `Retry-After`, non-retryable statuses, and the consecutive-failure cap
- `TestRecoverMissingFulltext`: Later runs retry recent papers without sections, leaving this run's papers to the normal download
- `TestRematch`: Recovered papers are matched again, skipping profiles they were already recommended to

### test_query_arxiv.py

Tests arXiv API query functionality.

**Test Classes:**
- `TestConfiguration`: API configuration and query tests

**Key Tests:**
- MAX_RESULTS configuration validation
- API query returns list (mocked to avoid external dependencies)
- Multi-category fetching function existence

### test_schemas.py

Tests Pydantic schema enums and validation.

**Test Classes:**
- `TestEnums`: Individual enum value tests
- `TestEnumMembership`: Parametrized enum member validation

**Key Tests:**
- FrequencyEnum values (daily, weekly, monthly)
- ThresholdEnum values (low, medium, high)
- SourceEnum values (user, arxiv)
- ModeEnum values (abstract, full)
- TypeEnum values (abstract, section)
- StatusEnum values (sent, failed)

### test_similarity_matcher.py

Tests vector similarity computations and paper matching.

**Test Classes:**
- `TestGrouping`: Embedding grouping by paper
- `TestCosineSimilarity`: Cosine similarity calculations
- `TestPaperSimilarity`: Paper-to-paper similarity

**Key Tests:**
- Grouping embeddings by paper_id
- Cosine similarity with identical vectors (result near 1.0)
- Cosine similarity with orthogonal vectors (result near 0.0)
- Cosine similarity with opposite vectors (result near -1.0)
- Multiple vector similarity matrices
- Maximum similarity selection across embeddings

### test_summarizer.py

Tests text processing and summarization utilities.

**Test Classes:**
- `TestTextCleaning`: Text normalization tests
- `TestSectionExtraction`: Section parsing tests
- `TestTextChunking`: Text chunking for summarization

**Key Tests:**
- Line break removal
- Citation marker removal ([1], [23])
- Hyphenated line break handling
- Whitespace normalization
- Markdown section header extraction
- Reference section exclusion
- Custom exclusion list support
- Token limit enforcement in chunking

## Coverage Areas

### Core Functionality
- Configuration management and validation
- Directory structure scanning
- arXiv ID normalization

### Data Processing
- PDF text extraction with GROBID
- Markdown section parsing
- Text cleaning and normalization
- Sentence tokenization

### Vector Operations
- Embedding grouping
- Cosine similarity computation
- Paper similarity scoring
- Multi-vector comparison

### Schema Validation
- Enum definitions and values
- Pydantic model validation
- Type checking

### External APIs
- arXiv API query construction
- Multi-category fetching
- Error handling

## Test Fixtures

### temp_dir
Creates isolated temporary directory for file operation tests. Automatically cleaned up after test completion.

### temp_user_structure
Creates realistic UID/PID directory structure:
```
temp_dir/
  1/
    1/paper1.pdf
    2/paper2.pdf
  2/
    3/
```

### sample_embeddings
Provides test embedding vectors:
```python
[
    {'paper_id': 1, 'embedding': [0.1, 0.2, 0.3]},
    {'paper_id': 1, 'embedding': [0.4, 0.5, 0.6]},
    {'paper_id': 2, 'embedding': [0.7, 0.8, 0.9]}
]
```

### sample_text
Markdown-formatted text with multiple sections for parsing tests.

## Parametrized Tests

Several test classes use pytest parametrization for comprehensive coverage:

### TestParametrizedThresholds
Tests all threshold levels (low, medium, high) with single test function.

### TestParametrizedArxivIds
Tests multiple arXiv ID formats with expected outputs:
- "2511.13418v1" -> "2511.13418"
- "2511.13418v2" -> "2511.13418"
- "1234.5678v10" -> "1234.5678"
- "2511.13418" -> "2511.13418"
- "" -> ""

### TestEnumMembership
Validates all enum classes have expected members using parametrization.

## Mocking Strategy

External dependencies are mocked to ensure tests are:
- Fast (no network calls)
- Reliable (no external service dependencies)
- Isolated (test only internal logic)

**Mocked Components:**
- arXiv API requests (test_query_arxiv.py)
- GROBID server calls (when needed)
- Database connections (when needed)

## Test Execution Time

Typical execution times:
- Full suite: 50-60 seconds
- Individual module: 5-10 seconds
- Mocked tests: <1 second each
- Tests with real computation: 1-5 seconds each

## Known Issues

### Warnings
- Pydantic V2 deprecation warnings (non-critical, will update in future)
- model_name field conflicts with protected namespace (cosmetic)
- Event loop deprecation in sync_client (addressed in fixes)

### External Dependencies
- spaCy optional dependency (tests handle both with/without)
- GROBID server not required for most tests
- arXiv API calls are mocked to avoid flakiness

## Continuous Integration

Tests are designed to run in CI environments:
- No external service dependencies
- All file operations use temp directories
- Mocked network calls
- Deterministic results

Recommended CI configuration:
```yaml
pytest tests/ --cov=src/preprint_bot --cov-report=xml --cov-report=term
```

## Test Data

Tests use minimal, representative data:
- Small embedding vectors (3-5 dimensions)
- Short text samples
- Simple directory structures
- Mock API responses

No large fixtures or external data files required.

## Maintenance

When adding new features:
1. Add corresponding test class in appropriate module
2. Use existing fixtures where applicable
3. Mock external dependencies
4. Use parametrization for multiple input scenarios
5. Keep tests isolated and independent

## Test Philosophy

- Unit tests focus on individual functions
- Integration tests would go in separate directory
- Mock external dependencies
- Test edge cases and error conditions
- Keep tests fast and deterministic