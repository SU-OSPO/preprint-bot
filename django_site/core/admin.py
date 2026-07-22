from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    PBUser, Profile, Corpus, Paper, Section,
    Summary, RecommendationRun, Recommendation,
    ProcessingRun, EmailLog, ArxivDailyStats,
)


@admin.register(PBUser)
class PBUserAdmin(BaseUserAdmin):
    """Admin for the custom email-based user model."""

    list_display = ("id", "email", "name", "is_staff", "is_active", "created_at")
    search_fields = ("email", "name")
    ordering = ("-created_at",)

    # Fields shown when editing an existing user
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )

    # Fields shown when creating a new user via admin
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "frequency", "threshold", "top_x")
    list_filter = ("frequency",)
    search_fields = ("name",)


@admin.register(Corpus)
class CorpusAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "created_at")
    search_fields = ("name",)


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ("id", "arxiv_id", "title_short", "source", "sha256_short", "submitted_date")
    list_filter = ("source",)
    search_fields = ("arxiv_id", "title", "sha256")

    @admin.display(description="Title")
    def title_short(self, obj):
        return obj.title[:80]

    @admin.display(description="SHA-256")
    def sha256_short(self, obj):
        return obj.sha256[:12] + "…" if obj.sha256 else "—"


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "paper", "score", "rank")
    list_filter = ("run",)


@admin.register(RecommendationRun)
class RecommendationRunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "profile", "method", "threshold",
        "total_papers_fetched", "target_date", "created_at", "completed_at",
    )
    list_filter = ("method", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


# ── Monitoring / operational tables ─────────────────────────────────────────

@admin.register(ProcessingRun)
class ProcessingRunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "run_type", "category", "status",
        "papers_processed", "started_at", "completed_at",
    )
    list_filter = ("status", "run_type", "category", "started_at")
    date_hierarchy = "started_at"
    ordering = ("-started_at",)

    # Audit log — written by the pipeline, viewed (not edited) here.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "profile", "subject", "status", "sent_at")
    list_filter = ("status", "sent_at")
    search_fields = ("subject", "user__email")
    date_hierarchy = "sent_at"
    ordering = ("-sent_at",)

    # Delivery log — written by the digest route, viewed (not edited) here.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ArxivDailyStats)
class ArxivDailyStatsAdmin(admin.ModelAdmin):
    list_display = ("id", "submission_date", "category", "total_papers", "created_at")
    list_filter = ("category", "submission_date")
    date_hierarchy = "submission_date"
    ordering = ("-submission_date",)
