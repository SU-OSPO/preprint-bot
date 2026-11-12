"""Test package for the core app.

Split by feature area (test_auth, test_orcid, test_papers, ...).
Run the whole suite with: python manage.py test core
"""

import os

# Run the suite against a single-source deployment, whatever the local .env enables.
os.environ["PREPRINT_ENABLED_SOURCES"] = "arxiv"
