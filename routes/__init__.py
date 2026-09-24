# routes/__init__.py
"""
API Routes Package
All route modules are imported here for easy access
"""

from . import (
    users,
    papers,
    corpora,
    sections,
    embeddings,
    recommendations,
)

# Optional imports (create these files based on remaining_routes.py)
try:
    from . import profiles
except ImportError:
    profiles = None

try:
    from . import profile_corpora
except ImportError:
    profile_corpora = None

try:
    from . import summaries
except ImportError:
    summaries = None

try:
    from . import profile_recommendations
except ImportError:
    profile_recommendations = None

try:
    from . import email_logs
except ImportError:
    email_logs = None

__all__ = [
    "users",
    "papers",
    "corpora",
    "sections",
    "embeddings",
    "recommendations",
    "profiles",
    "profile_corpora",
    "summaries",
    "profile_recommendations",
    "email_logs",
]
