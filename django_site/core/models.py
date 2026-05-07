"""
Django ORM models for Preprint Bot.

All models are fully managed by Django (migrations create/alter the tables).
Table names match the original schema where possible so the FastAPI pipeline
continues to work.  Note that the Django-managed ``users`` table follows
Django's auth model (e.g. ``password`` column) rather than the legacy auth
schema (``password_hash``), so existing FastAPI auth endpoints are not
guaranteed to work against this schema without updates.
"""

from django.db import models
from django.db.models.functions import Lower
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField


# ── Users ──────────────────────────────────────────────────────────────────

class PBUserManager(BaseUserManager):
    """Manager for email-based authentication (no username)."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()  # fully lowercase
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class PBUser(AbstractBaseUser, PermissionsMixin):
    """System users and researchers.

    Uses email as the login identifier. Extends Django's auth system
    so the same account works for both the site and the admin panel.
    """

    email = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    orcid_id = models.CharField(max_length=19, blank=True, null=True, unique=True)
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PBUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []           # email is already required by USERNAME_FIELD

    class Meta:
        db_table = "users"
        swappable = "AUTH_USER_MODEL"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="users_email_ci_unique",
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.email


# ── Profiles ───────────────────────────────────────────────────────────────

class Profile(models.Model):
    """User research profiles and preferences."""

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    user = models.ForeignKey(PBUser, on_delete=models.CASCADE, related_name="profiles")
    name = models.CharField(max_length=255)
    keywords = ArrayField(models.TextField(), default=list, blank=True)
    categories = ArrayField(models.TextField(), default=list, blank=True)
    email_notify = models.BooleanField(default=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="daily")
    threshold = models.FloatField(default=0.6)
    top_x = models.IntegerField(default=999)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="profiles_user_name_unique",
            ),
            models.UniqueConstraint(
                Lower("name"), "user",
                name="profiles_user_name_ci_unique",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"


# ── Corpora ────────────────────────────────────────────────────────────────

class Corpus(models.Model):
    """Collections of papers (arXiv corpus or user collections)."""

    user = models.ForeignKey(PBUser, on_delete=models.CASCADE, related_name="corpora")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "corpora"
        unique_together = [("user", "name")]
        verbose_name_plural = "corpora"

    def __str__(self):
        return self.name


# ── Profile ↔ Corpus junction ─────────────────────────────────────────────

class ProfileCorpus(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    corpus = models.ForeignKey(Corpus, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profile_corpora"
        unique_together = [("profile", "corpus")]


# ── Papers ─────────────────────────────────────────────────────────────────

class Paper(models.Model):
    """Academic papers from arXiv or user uploads.

    Papers are deduplicated by SHA-256 hash.  A single Paper can be linked
    to multiple corpora via the ``corpora`` ManyToManyField.  Files are
    stored at ``{PAPER_STORAGE_DIR}/{sha256[:2]}/{sha256}.pdf``.
    """

    SOURCE_CHOICES = [("user", "User"), ("arxiv", "arXiv")]

    # Legacy FK — no longer populated or queried; kept for schema compat
    corpus = models.ForeignKey(
        Corpus, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="papers_legacy",
        help_text="Deprecated — not populated. Use corpora M2M. Can be dropped in a future migration.",
    )
    corpora = models.ManyToManyField(Corpus, blank=True, related_name="papers")
    arxiv_id = models.CharField(max_length=50, blank=True, null=True)
    sha256 = models.CharField(max_length=64, unique=True, blank=True, null=True)
    title = models.TextField()
    abstract = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    pdf_path = models.TextField(blank=True, null=True)
    processed_text_path = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="arxiv")
    submitted_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "papers"
        indexes = [
            models.Index(fields=["arxiv_id"], name="papers_arxiv_id_idx"),
            models.Index(fields=["submitted_date"], name="papers_submitted_date_idx"),
        ]

    def __str__(self):
        return self.title[:80]

    @property
    def arxiv_url(self):
        if self.arxiv_id:
            return f"https://arxiv.org/abs/{self.arxiv_id}"
        return ""

    @property
    def categories_list(self):
        if self.metadata and isinstance(self.metadata, dict):
            return self.metadata.get("categories", [])
        return []


# ── Sections ───────────────────────────────────────────────────────────────

class Section(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="sections")
    section_header = models.TextField(blank=True, null=True)
    section_text = models.TextField(blank=True, null=True)
    section_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sections"


# ── Summaries ──────────────────────────────────────────────────────────────

class Summary(models.Model):
    MODE_CHOICES = [("abstract", "Abstract"), ("full", "Full")]

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="summaries")
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="abstract")
    summary_text = models.TextField(blank=True, null=True)
    summarizer = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "summaries"
        unique_together = [("paper", "mode")]
        verbose_name_plural = "summaries"


# ── Embeddings ─────────────────────────────────────────────────────────────

class Embedding(models.Model):
    """Vector embeddings for semantic similarity search.
    Requires the ``pgvector-django`` package for the vector(384) column.
    """

    TYPE_CHOICES = [("abstract", "Abstract"), ("section", "Section")]

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="embeddings")
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, blank=True, null=True, related_name="embeddings"
    )
    embedding = VectorField(dimensions=384)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="abstract")
    model_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "embeddings"
        constraints = [
            models.UniqueConstraint(
                fields=["paper", "type", "model_name"],
                condition=models.Q(section__isnull=True),
                name="embeddings_paper_type_model_null_section_unique",
            ),
            models.UniqueConstraint(
                fields=["paper", "section", "type", "model_name"],
                condition=models.Q(section__isnull=False),
                name="embeddings_paper_section_type_model_unique",
            ),
        ]


# ── Processing runs ────────────────────────────────────────────────────────

class ProcessingRun(models.Model):
    run_type = models.CharField(max_length=50)
    category = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default="started")
    papers_processed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "processing_runs"


# ── Recommendation runs ───────────────────────────────────────────────────

class RecommendationRun(models.Model):
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, blank=True, null=True, related_name="runs"
    )
    user = models.ForeignKey(PBUser, on_delete=models.CASCADE, related_name="recommendation_runs")
    user_corpus = models.ForeignKey(Corpus, on_delete=models.CASCADE, related_name="user_runs")
    ref_corpus = models.ForeignKey(Corpus, on_delete=models.CASCADE, related_name="ref_runs")
    threshold = models.FloatField(blank=True, null=True)
    method = models.CharField(max_length=20, blank=True, null=True)
    total_papers_fetched = models.IntegerField(default=0)
    target_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "recommendation_runs"


# ── Recommendations ────────────────────────────────────────────────────────

class Recommendation(models.Model):
    run = models.ForeignKey(
        RecommendationRun, on_delete=models.CASCADE, related_name="recommendations"
    )
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="recommendations")
    score = models.FloatField()
    rank = models.IntegerField()
    summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendations"
        unique_together = [("run", "paper")]


# ── Profile ↔ Recommendation junction ─────────────────────────────────────

class ProfileRecommendation(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profile_recommendations"
        unique_together = [("profile", "recommendation")]


# ── Auth tokens ────────────────────────────────────────────────────────────

class AuthToken(models.Model):
    user = models.ForeignKey(PBUser, on_delete=models.CASCADE, related_name="auth_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_tokens"


# ── Email logs ─────────────────────────────────────────────────────────────

class EmailLog(models.Model):
    STATUS_CHOICES = [("sent", "Sent"), ("failed", "Failed")]

    user = models.ForeignKey(PBUser, on_delete=models.CASCADE, related_name="email_logs")
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, blank=True, null=True)
    subject = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_logs"


# ── ArXiv daily stats ─────────────────────────────────────────────────────

class ArxivDailyStats(models.Model):
    submission_date = models.DateField()
    category = models.CharField(max_length=50)
    total_papers = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "arxiv_daily_stats"
        unique_together = [("submission_date", "category")]
