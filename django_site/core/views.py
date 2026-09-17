"""
Django views for the Preprint Bot web interface.

Authentication uses Django's built-in auth system with PBUser as
the custom user model (AUTH_USER_MODEL).
"""

import json
import re
import time
from datetime import timedelta
from functools import wraps
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Max, Q
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from preprint_sources.taxonomies.arxiv import ARXIV_CODE_TO_LABEL, ARXIV_CATEGORY_TREE, label_for
from .auth_backend import (
    authenticate_pbuser,
    login_pbuser,
    logout_pbuser,
)
from .forms import (
    ForgotPasswordForm,
    LoginForm,
    OrcidCompleteForm,
    ProfileForm,
    RegisterForm,
    ResetPasswordForm,
    UserSettingsForm,
)
from .models import (
    Corpus,
    EmailLog,
    PBUser,
    Paper,
    ProcessingRun,
    Profile,
    Recommendation,
    RecommendationRun,
    Summary,
)
from .sources import paper_source_context, resolve_source, run_sync

# Users paste several ids at once, comma- or newline-separated; the
# shape of each id is the source's business, not this module's.
SOURCE_ID_SEPARATOR_RE = re.compile(r"[,\n]+")


# ── Paper storage helpers ──────────────────────────────────────────────────

def _compute_sha256(source):
    """Compute SHA-256 hash of a file path, bytes, or Django UploadedFile."""
    import hashlib
    h = hashlib.sha256()
    if isinstance(source, bytes):
        h.update(source)
    elif hasattr(source, "chunks"):
        # Django UploadedFile
        for chunk in source.chunks():
            h.update(chunk)
        source.seek(0)
    elif hasattr(source, "read"):
        for chunk in iter(lambda: source.read(8192), b""):
            h.update(chunk)
        source.seek(0)
    else:
        # Assume file path
        with open(source, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    return h.hexdigest()


def _paper_storage_path(sha256_hex):
    """Return the hash-based storage path for a paper's PDF."""
    return django_settings.PAPER_STORAGE_DIR / sha256_hex[:2] / f"{sha256_hex}.pdf"


def _store_paper_bytes(sha256_hex, data):
    """Store PDF bytes in the hash-based directory structure.

    Returns the Path. Skips writing if the file already exists (dedup).
    """
    dest = _paper_storage_path(sha256_hex)
    if dest.exists():
        return dest  # already stored
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def _store_paper_upload(sha256_hex, uploaded_file):
    """Store a Django UploadedFile in the hash-based directory structure.

    Returns the Path. Skips writing if the file already exists (dedup).
    """
    dest = _paper_storage_path(sha256_hex)
    if dest.exists():
        return dest  # already stored
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
    return dest


def _get_or_create_user_corpus(pb_user, profile):
    """Get or create the corpus for a user's profile."""
    corpus_name = f"user_{pb_user.pk}_profile_{profile.pk}"
    corpus, _ = Corpus.objects.get_or_create(
        user=pb_user,
        name=corpus_name,
        defaults={"description": f"Papers for {pb_user.email}, profile '{profile.name}'"},
    )
    return corpus


def _link_paper_to_corpus(paper, corpus):
    """Add a corpus link if it doesn't already exist."""
    paper.corpora.add(corpus)


def _pdf_has_text_layer(uploaded_file, min_chars=50, max_pages=3):
    """Check whether a PDF has extractable text.

    Reads up to *max_pages* pages and returns True if at least
    *min_chars* characters of text (after stripping leading/trailing
    whitespace) can be extracted.
    Returns True (allow upload) if pypdf is not installed or the
    PDF cannot be parsed, so we never block uploads due to a
    library issue.
    """
    try:
        from pypdf import PdfReader

        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages[:max_pages]:
            text += page.extract_text() or ""
            if len(text.strip()) >= min_chars:
                uploaded_file.seek(0)
                return True
        uploaded_file.seek(0)
        return len(text.strip()) >= min_chars
    except Exception:
        uploaded_file.seek(0)
        return True  # don't block uploads if the check itself fails


# ── Decorator ──────────────────────────────────────────────────────────────

# URL names reachable while onboarding is active (the flow itself plus the
# paper-action endpoints its papers screen reuses). Everything else GETs
# bounced back into the flow.
_ONBOARDING_EXEMPT = {
    "onboarding_profile", "onboarding_papers", "onboarding_finish",
    "onboarding_skip", "logout",
    "paper_upload", "paper_add_by_id", "paper_search_api",
    "paper_view", "paper_delete",
}


def _onboarding_redirect(user):
    """Resume onboarding at the right step: papers if a profile already
    exists (their most recent one), otherwise the profile step."""
    profile = Profile.objects.filter(user=user).order_by("-created_at").first()
    if profile:
        return redirect("onboarding_papers", profile_id=profile.pk)
    return redirect("onboarding_profile")


def pbuser_required(view_func):
    """Redirect to login if not authenticated, preserving the
    originally requested URL so we can bounce back after sign-in."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.utils.http import urlencode

            login_url = reverse("login")  # respects FORCE_SCRIPT_NAME
            next_url = request.get_full_path()
            return redirect(f"{login_url}?{urlencode({'next': next_url})}")
        request.pb_user = request.user  # convenience alias for templates

        # Keep brand-new accounts in the onboarding flow until they finish
        # or skip. Gate GET navigations only so form/API POSTs still land.
        if (
            request.session.get("onboarding")
            and request.method == "GET"
            and request.resolver_match
            and request.resolver_match.url_name not in _ONBOARDING_EXEMPT
        ):
            return _onboarding_redirect(request.user)

        return view_func(request, *args, **kwargs)

    return wrapper


def _send_verification_email(request, pb_user):
    """Send a tokenized email verification link to the user."""
    from django.contrib.auth.tokens import default_token_generator
    from django.core.mail import send_mail
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(pb_user.pk))
    token = default_token_generator.make_token(pb_user)
    verify_url = request.build_absolute_uri(
        reverse("verify_email", kwargs={"uidb64": uid, "token": token})
    )

    send_mail(
        subject=f"Verify your email – {django_settings.SITE_NAME}",
        message=(
            f"Hi {pb_user.name or pb_user.email},\n\n"
            f"Please verify your email address by clicking the link below:\n\n"
            f"{verify_url}\n\n"
            f"If you didn't create an account, you can ignore this email.\n\n"
            f"— {django_settings.SITE_NAME}"
        ),
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[pb_user.email],
        fail_silently=False,
    )
    return verify_url  # returned for DEBUG display


# ── Auth views ─────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    next_url = request.GET.get("next", request.POST.get("next", ""))

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        pb_user = authenticate_pbuser(request, email, password)
        if pb_user:
            # Block unverified users when verification is required
            if django_settings.REQUIRE_EMAIL_VERIFICATION and not pb_user.email_verified:
                request.session["resend_verification_email"] = pb_user.email
                messages.error(request, "Please verify your email before signing in.")
                return render(request, "auth/login.html", {
                    "form": form, "next": next_url, "show_resend_link": True,
                })
            login_pbuser(request, pb_user)
            # Validate next URL to prevent open redirect and HTTPS downgrade
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("dashboard")
        messages.error(request, "Invalid email or password.")

    return render(request, "auth/login.html", {"form": form, "next": next_url})


def register_view(request):
    if not django_settings.REGISTRATION_OPEN:
        messages.info(request, "Registration is currently closed on this site.")
        return redirect("login")

    if request.user.is_authenticated:
        return redirect("dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        name = form.cleaned_data.get("name", "")
        password = form.cleaned_data["password"]

        if PBUser.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with that email already exists.")
        else:
            from django.db import IntegrityError
            try:
                pb_user = PBUser.objects.create_user(
                    email=email,
                    password=password,
                    name=name,
                )
            except IntegrityError:
                messages.error(request, "An account with that email already exists.")
                return render(request, "auth/register.html", {"form": form})

            if django_settings.REQUIRE_EMAIL_VERIFICATION:
                verify_url = _send_verification_email(request, pb_user)
                return render(request, "auth/verify_email_sent.html", {
                    "email": pb_user.email,
                    "verify_url": verify_url if django_settings.DEBUG else None,
                })

            # No verification required — log in immediately
            login_pbuser(request, pb_user)
            messages.success(request, "Account created successfully!")
            return redirect("dashboard")

    return render(request, "auth/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout_pbuser(request)
    return redirect("login")


def verify_email_view(request, uidb64, token):
    """Handle the email verification link."""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        pb_user = PBUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, PBUser.DoesNotExist):
        pb_user = None

    if pb_user is None or not default_token_generator.check_token(pb_user, token):
        messages.error(request, "Invalid or expired verification link.")
        return redirect("login")

    pb_user.email_verified = True
    pb_user.save(update_fields=["email_verified"])
    messages.success(request, "Email verified! You can now sign in.")
    return redirect("login")


def resend_verification_view(request):
    """Resend the verification email for an unverified account."""
    email = request.session.get("resend_verification_email")
    if not email:
        messages.error(request, "No pending verification. Please register or log in.")
        return redirect("login")

    try:
        pb_user = PBUser.objects.get(email__iexact=email)
    except PBUser.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect("login")

    if pb_user.email_verified:
        messages.info(request, "Email is already verified. Please sign in.")
        return redirect("login")

    verify_url = _send_verification_email(request, pb_user)
    return render(request, "auth/verify_email_sent.html", {
        "email": pb_user.email,
        "verify_url": verify_url if django_settings.DEBUG else None,
    })


# ── ORCID OAuth2 ──────────────────────────────────────────────────────────

def orcid_login_view(request):
    """Redirect the user to ORCID's OAuth2 authorization page."""
    from . import orcid as orcid_helpers

    if not orcid_helpers.is_configured():
        messages.error(request, "ORCID sign-in is not configured.")
        return redirect("login")

    # Generate a random state token to prevent CSRF
    import secrets
    state = secrets.token_urlsafe(32)
    request.session["orcid_oauth_state"] = state

    redirect_uri = request.build_absolute_uri(reverse("orcid_callback"))
    authorize_url = orcid_helpers.get_authorize_url(redirect_uri, state=state)
    return redirect(authorize_url)


def orcid_callback_view(request):
    """Handle the ORCID OAuth2 callback after authorization."""
    from . import orcid as orcid_helpers

    if not orcid_helpers.is_configured():
        messages.error(request, "ORCID sign-in is not configured.")
        return redirect("login")

    # Verify state token
    state = request.GET.get("state", "")
    expected_state = request.session.pop("orcid_oauth_state", "")
    if not state or state != expected_state:
        messages.error(request, "Invalid ORCID callback. Please try again.")
        return redirect("login")

    # Check for error from ORCID (e.g. user denied access)
    error = request.GET.get("error")
    if error:
        messages.error(request, "ORCID sign-in was cancelled or denied.")
        return redirect("login")

    code = request.GET.get("code", "")
    if not code:
        messages.error(request, "No authorization code received from ORCID.")
        return redirect("login")

    # Exchange code for token (returns orcid, name, access_token)
    redirect_uri = request.build_absolute_uri(reverse("orcid_callback"))
    token_data = orcid_helpers.exchange_code(code, redirect_uri)
    if not token_data or not token_data.get("orcid"):
        messages.error(request, "Failed to verify your ORCID credentials. Please try again.")
        return redirect("login")

    orcid_id = token_data["orcid"]
    orcid_name = token_data.get("name", "")
    access_token = token_data.get("access_token", "")

    # ── Link mode: attach ORCID to the logged-in user's account ──
    if request.session.pop("orcid_link_mode", False):
        if not request.user.is_authenticated:
            messages.error(request, "Your session expired. Please log in and try again.")
            return redirect("login")
        # Check if this ORCID iD is already used by a different account
        existing = PBUser.objects.filter(orcid_id=orcid_id).exclude(pk=request.user.pk).first()
        if existing:
            messages.error(request, f"ORCID iD {orcid_id} is already linked to another account.")
        else:
            request.user.orcid_id = orcid_id
            request.user.save(update_fields=["orcid_id"])
            messages.success(request, f"ORCID iD ({orcid_id}) linked to your account.")
        return redirect("settings")

    # Check if a user with this ORCID iD already exists
    try:
        pb_user = PBUser.objects.get(orcid_id=orcid_id)
        # Existing user — log them in
        login_pbuser(request, pb_user)
        messages.success(request, f"Signed in with ORCID ({orcid_id}).")
        return redirect("dashboard")
    except PBUser.DoesNotExist:
        pass

    # New user — try to get their email from ORCID
    orcid_email = orcid_helpers.fetch_email(orcid_id, access_token) if access_token else None

    if orcid_email and not PBUser.objects.filter(email__iexact=orcid_email).exists():
        if not django_settings.REGISTRATION_OPEN:
            messages.info(request, "Registration is currently closed on this site.")
            return redirect("login")
        # Got an email and it's not taken — create the account directly
        pb_user = PBUser.objects.create_user(
            email=orcid_email,
            name=orcid_name,
            orcid_id=orcid_id,
            email_verified=True,  # ORCID authenticated their identity
        )
        login_pbuser(request, pb_user)
        messages.success(request, f"Account created with ORCID ({orcid_id}).")
        return redirect("dashboard")

    # No email from ORCID, or email already in use — ask for one
    if not django_settings.REGISTRATION_OPEN:
        messages.info(request, "Registration is currently closed on this site.")
        return redirect("login")
    request.session["orcid_pending"] = {
        "orcid_id": orcid_id,
        "name": orcid_name,
    }
    return redirect("orcid_complete")


def orcid_complete_view(request):
    """Collect email for a new ORCID user (first sign-in)."""
    if not django_settings.REGISTRATION_OPEN:
        messages.info(request, "Registration is currently closed on this site.")
        return redirect("login")

    pending = request.session.get("orcid_pending")
    if not pending:
        messages.error(request, "No pending ORCID sign-in. Please start again.")
        return redirect("login")

    orcid_id = pending["orcid_id"]
    orcid_name = pending.get("name", "")

    form = OrcidCompleteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]

        if PBUser.objects.filter(email__iexact=email).exists():
            messages.error(
                request,
                "An account with that email already exists. "
                "Sign in with your password to link your ORCID later.",
            )
        else:
            from django.db import IntegrityError
            try:
                pb_user = PBUser.objects.create_user(
                    email=email,
                    name=orcid_name,
                    orcid_id=orcid_id,
                    email_verified=True,  # ORCID authenticated their identity
                )
            except IntegrityError:
                messages.error(
                    request,
                    "An account with that email already exists. "
                    "Sign in with your password to link your ORCID later.",
                )
                return render(request, "auth/orcid_complete.html", {
                    "form": form, "orcid_id": orcid_id, "orcid_name": orcid_name,
                })
            # Clear pending session data
            del request.session["orcid_pending"]
            login_pbuser(request, pb_user)
            messages.success(request, f"Account created with ORCID ({orcid_id}).")
            return redirect("dashboard")

    return render(request, "auth/orcid_complete.html", {
        "form": form,
        "orcid_id": orcid_id,
        "orcid_name": orcid_name,
    })


@pbuser_required
def orcid_link_view(request):
    """Initiate ORCID OAuth2 to link an ORCID iD to the current account."""
    from . import orcid as orcid_helpers

    if not orcid_helpers.is_configured():
        messages.error(request, "ORCID is not configured.")
        return redirect("settings")

    if request.pb_user.orcid_id:
        messages.info(request, "Your account already has an ORCID iD linked.")
        return redirect("settings")

    # Flag this OAuth flow as a link (not login/register)
    import secrets
    state = secrets.token_urlsafe(32)
    request.session["orcid_oauth_state"] = state
    request.session["orcid_link_mode"] = True

    redirect_uri = request.build_absolute_uri(reverse("orcid_callback"))
    authorize_url = orcid_helpers.get_authorize_url(redirect_uri, state=state)
    return redirect(authorize_url)


@pbuser_required
@require_POST
def orcid_unlink_view(request):
    """Remove the linked ORCID iD from the current account."""
    pb_user = request.pb_user
    if not pb_user.orcid_id:
        messages.info(request, "No ORCID iD is linked to your account.")
    else:
        old_id = pb_user.orcid_id
        pb_user.orcid_id = None
        pb_user.save(update_fields=["orcid_id"])
        messages.success(request, f"ORCID iD ({old_id}) has been unlinked.")
    return redirect("settings")


def forgot_password_view(request):
    form = ForgotPasswordForm(request.POST or None)
    reset_link = None
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        try:
            pb_user = PBUser.objects.get(email__iexact=email)
            from django.contrib.auth.tokens import default_token_generator
            from django.utils.http import urlsafe_base64_encode
            from django.utils.encoding import force_bytes

            uid = urlsafe_base64_encode(force_bytes(pb_user.pk))
            token = default_token_generator.make_token(pb_user)
            reset_url = request.build_absolute_uri(
                reverse("reset_password", kwargs={"uidb64": uid, "token": token})
            )

            # Send the reset link via email
            from django.core.mail import send_mail
            send_mail(
                subject=f"Password reset – {django_settings.SITE_NAME}",
                message=(
                    f"Hi {pb_user.name or pb_user.email},\n\n"
                    f"Click the link below to reset your password:\n\n"
                    f"{reset_url}\n\n"
                    f"If you didn't request this, you can ignore this email.\n\n"
                    f"— {django_settings.SITE_NAME}"
                ),
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[pb_user.email],
                fail_silently=True,
            )

            # Also show the link on-page in DEBUG mode
            if django_settings.DEBUG:
                reset_link = reset_url
        except PBUser.DoesNotExist:
            pass  # don't reveal whether the email exists
        messages.success(request, "If that email exists, a reset link has been generated.")

    return render(
        request, "auth/forgot_password.html", {"form": form, "reset_link": reset_link}
    )


def reset_password_view(request, uidb64, token):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        pb_user = PBUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, PBUser.DoesNotExist):
        pb_user = None

    if pb_user is None or not default_token_generator.check_token(pb_user, token):
        messages.error(request, "Invalid or expired reset link.")
        return redirect("forgot_password")

    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pb_user.set_password(form.cleaned_data["new_password"])
        pb_user.save()
        messages.success(request, "Password updated. Please log in.")
        return redirect("login")

    return render(request, "auth/reset_password.html", {"form": form})


# ── Dashboard ──────────────────────────────────────────────────────────────

def home_view(request):
    """Root: public landing page for anonymous visitors, dashboard for
    signed-in users."""
    if not request.user.is_authenticated:
        return render(request, "landing.html")
    return dashboard_view(request)


@pbuser_required
def dashboard_view(request):
    pb_user = request.pb_user

    profiles = Profile.objects.filter(user=pb_user)

    # Use the same query path as the recommendations page
    all_recs = _query_profile_recommendations(pb_user)
    total_recs = len(all_recs)

    # Filter to the most recent date for the "Latest" section
    latest_date = None
    for r in all_recs:
        d = r.get("date_obj")
        if d and (latest_date is None or d > latest_date):
            latest_date = d

    if latest_date:
        today_recs = sorted(
            [r for r in all_recs if r.get("date_obj") == latest_date],
            key=lambda x: x["score"],
            reverse=True,
        )
    else:
        today_recs = []

    # One-time congrats after finishing onboarding.
    just_onboarded = request.session.pop("onboarding_just_finished", False)

    return render(
        request,
        "dashboard.html",
        {
            "pb_user": pb_user,
            "profiles": profiles,
            "total_recs": total_recs,
            "today_recs": today_recs[:20],
            "today_count": len(today_recs),
            "just_onboarded": just_onboarded,
        },
    )


# ── Profiles ───────────────────────────────────────────────────────────────

@pbuser_required
def profile_list_view(request):
    pb_user = request.pb_user
    profiles = Profile.objects.filter(user=pb_user).order_by("-created_at")

    # Prefetch all user corpora
    user_corpora = {
        c.name: c for c in Corpus.objects.filter(user=pb_user)
    }

    profile_data = []
    for profile in profiles:
        corpus_name = f"user_{pb_user.pk}_profile_{profile.pk}"
        corpus = user_corpora.get(corpus_name)

        # Get papers linked to this profile's corpus via M2M
        if corpus:
            papers = list(
                Paper.objects.filter(corpora=corpus)
                .order_by("-created_at")
            )
        else:
            papers = []

        profile_data.append({
            "profile": profile,
            "paper_count": len(papers),
            "papers": papers,
            "categories_display": [label_for(c) for c in (profile.categories or [])],
        })

    return render(request, "profiles/list.html", {
        "pb_user": pb_user,
        "profile_data": profile_data,
        "code_to_label": ARXIV_CODE_TO_LABEL,
        "search_per_page": django_settings.SOURCE_SEARCH_PER_PAGE,
        **paper_source_context(),
    })


@pbuser_required
def profile_create_view(request):
    pb_user = request.pb_user

    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"].strip()
            # Check for duplicate name
            if Profile.objects.filter(user=pb_user, name__iexact=name).exists():
                messages.error(request, f"A profile named '{name}' already exists.")
            else:
                Profile.objects.create(
                    user=pb_user,
                    name=name,
                    categories=form.cleaned_data["categories"],
                    frequency=form.cleaned_data["frequency"],
                    threshold=form.cleaned_data["threshold"],
                    top_x=form.cleaned_data["top_x"],
                )
                messages.success(request, f"Profile '{name}' created.")
                return redirect("profile_list")
    else:
        form = ProfileForm()

    return render(request, "profiles/create.html", {
        "pb_user": pb_user,
        "form": form,
        "category_tree_json": json.dumps(ARXIV_CATEGORY_TREE),
    })


@pbuser_required
def profile_edit_view(request, profile_id):
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)

    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"].strip()
            dup = Profile.objects.filter(user=pb_user, name__iexact=name).exclude(pk=profile.pk)
            if dup.exists():
                messages.error(request, f"A profile named '{name}' already exists.")
            else:
                profile.name = name
                profile.categories = form.cleaned_data["categories"]
                profile.frequency = form.cleaned_data["frequency"]
                profile.threshold = form.cleaned_data["threshold"]
                profile.top_x = form.cleaned_data["top_x"]
                profile.save()
                messages.success(request, f"Profile '{name}' updated.")
                return redirect("profile_list")
    else:
        form = ProfileForm(initial={
            "name": profile.name,
            "frequency": profile.frequency,
            "threshold": max(0.40, min(0.75, profile.threshold if profile.threshold is not None else 0.6)),
            "top_x": profile.top_x or 10,
            "categories": ",".join(profile.categories or []),
        })

    return render(request, "profiles/create.html", {
        "pb_user": pb_user,
        "form": form,
        "editing": True,
        "profile": profile,
        "category_tree_json": json.dumps(ARXIV_CATEGORY_TREE),
        "initial_categories_json": json.dumps(profile.categories or []),
    })


@pbuser_required
@require_POST
def profile_delete_view(request, profile_id):
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)
    name = profile.name
    profile.delete()
    messages.success(request, f"Profile '{name}' deleted.")
    return redirect("profile_list")


# ── Onboarding (first-login walkthrough) ──────────────────────────────────

def _safe_next(request, default_url_name):
    """Return a caller-supplied ``next`` path when it's a safe local URL,
    otherwise the reversed default. Lets shared endpoints return into the
    onboarding flow without changing their normal behaviour."""
    from django.utils.http import url_has_allowed_host_and_scheme
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return reverse(default_url_name)


@pbuser_required
def onboarding_profile_view(request):
    """Step 1: create the first profile."""
    pb_user = request.pb_user

    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"].strip()
            if Profile.objects.filter(user=pb_user, name__iexact=name).exists():
                messages.error(request, f"A profile named '{name}' already exists.")
            else:
                profile = Profile.objects.create(
                    user=pb_user,
                    name=name,
                    categories=form.cleaned_data["categories"],
                    frequency=form.cleaned_data["frequency"],
                    threshold=form.cleaned_data["threshold"],
                    top_x=form.cleaned_data["top_x"],
                )
                return redirect("onboarding_papers", profile_id=profile.pk)
    else:
        form = ProfileForm()

    return render(request, "onboarding/profile.html", {
        "pb_user": pb_user,
        "form": form,
        "category_tree_json": json.dumps(ARXIV_CATEGORY_TREE),
    })


@pbuser_required
def onboarding_papers_view(request, profile_id):
    """Step 2: add papers to the just-created profile."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)

    corpus_name = f"user_{pb_user.pk}_profile_{profile.pk}"
    corpus = Corpus.objects.filter(user=pb_user, name=corpus_name).first()
    papers = (
        list(Paper.objects.filter(corpora=corpus).order_by("-created_at"))
        if corpus else []
    )

    return render(request, "onboarding/papers.html", {
        "pb_user": pb_user,
        "profile": profile,
        "papers": papers,
        "category_tree_json": json.dumps(ARXIV_CATEGORY_TREE),
        "code_to_label": ARXIV_CODE_TO_LABEL,
        "search_per_page": django_settings.SOURCE_SEARCH_PER_PAGE,
        **paper_source_context(),
    })


@pbuser_required
@require_POST
def onboarding_finish_view(request):
    """Finish onboarding and land on the dashboard with a congrats note.
    Requires the profile to have at least one paper."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=request.POST.get("profile_id"), user=pb_user)

    corpus_name = f"user_{pb_user.pk}_profile_{profile.pk}"
    corpus = Corpus.objects.filter(user=pb_user, name=corpus_name).first()
    if not (corpus and Paper.objects.filter(corpora=corpus).exists()):
        messages.error(request, "Add at least one paper before finishing.")
        return redirect("onboarding_papers", profile_id=profile.pk)

    request.session.pop("onboarding", None)
    request.session["onboarding_just_finished"] = True
    return redirect("dashboard")


@pbuser_required
@require_POST
def onboarding_skip_view(request):
    """Abandon onboarding entirely from either step."""
    request.session.pop("onboarding", None)
    return redirect("dashboard")


# ── Paper uploads (within a profile) ──────────────────────────────────────

@pbuser_required
@require_POST
def paper_upload_view(request, profile_id):
    """Upload PDF files, deduplicating by SHA-256 hash."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)
    corpus = _get_or_create_user_corpus(pb_user, profile)

    MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB per file

    uploaded = request.FILES.getlist("files")
    count = 0
    skipped = 0
    for f in uploaded:
        safe_name = Path(f.name).name  # strip directory components
        if not safe_name.lower().endswith(".pdf"):
            skipped += 1
            continue
        if f.size > MAX_UPLOAD_BYTES:
            messages.warning(request, f"Skipped {safe_name}: exceeds 50 MB limit.")
            skipped += 1
            continue
        # Validate PDF header: look for %PDF- marker in first 1KB
        # (valid PDFs may have leading whitespace, BOM, or comments)
        header = f.read(1024)
        f.seek(0)
        if b"%PDF-" not in header:
            messages.warning(request, f"Skipped {safe_name}: not a valid PDF file.")
            skipped += 1
            continue

        # Check for extractable text layer (reject scanned/image-only PDFs)
        if not _pdf_has_text_layer(f):
            messages.warning(
                request,
                f"Skipped {safe_name}: no extractable text found. "
                f"Please upload a PDF with a text layer (not a scanned image).",
            )
            skipped += 1
            continue

        # Compute hash and check for existing paper
        file_hash = _compute_sha256(f)
        existing = Paper.objects.filter(sha256=file_hash).first()
        if existing:
            # Paper already in DB — just link to this corpus
            _link_paper_to_corpus(existing, corpus)
            count += 1
            continue

        # New paper — store file and create DB row
        dest = _store_paper_upload(file_hash, f)
        from django.db import IntegrityError
        try:
            paper = Paper.objects.create(
                title=Path(safe_name).stem,  # use filename as placeholder title
                sha256=file_hash,
                pdf_path=str(dest),
                source="user",
            )
        except IntegrityError:
            # Race condition: another request created it first
            paper = Paper.objects.get(sha256=file_hash)
        _link_paper_to_corpus(paper, corpus)
        count += 1

    if count:
        messages.success(request, f"Added {count} paper(s).")
    else:
        messages.warning(request, "No valid PDF files selected.")

    return redirect(_safe_next(request, "profile_list"))


@pbuser_required
@require_POST
def paper_delete_view(request, profile_id, paper_id):
    """Unlink a paper from this profile's corpus (does not delete the file)."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)
    paper = get_object_or_404(Paper, pk=paper_id)
    corpus = _get_or_create_user_corpus(pb_user, profile)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    was_linked = paper.corpora.filter(pk=corpus.pk).exists()
    if was_linked:
        paper.corpora.remove(corpus)
        if is_ajax:
            return JsonResponse({"ok": True})
        messages.success(request, f"Removed '{paper.title[:60]}' from this profile.")
    else:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Paper not linked to this profile."}, status=400)
        messages.error(request, "Paper not linked to this profile.")

    return redirect(_safe_next(request, "profile_list"))


@pbuser_required
def paper_view(request, profile_id, paper_id):
    """Serve a paper's PDF for viewing in the browser."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)
    paper = get_object_or_404(Paper, pk=paper_id)

    # Verify the paper is linked to this user's profile corpus
    corpus = _get_or_create_user_corpus(pb_user, profile)
    if not paper.corpora.filter(pk=corpus.pk).exists():
        raise Http404("Paper not linked to this profile.")

    if not paper.pdf_path:
        raise Http404("No PDF file available.")

    pdf_path = Path(paper.pdf_path)
    if not pdf_path.exists():
        raise Http404("PDF file not found on disk.")

    return FileResponse(open(pdf_path, "rb"), content_type="application/pdf")


@pbuser_required
@require_POST
def paper_add_by_id_view(request, profile_id):
    """Add papers from a preprint source by ID – downloads each PDF.

    The source comes from the ``source`` POST field; with a single source
    enabled the UI omits it and the first add-capable source is used.
    """
    MAX_IDS_PER_REQUEST = 10  # cap to avoid blocking a worker on rate-limit sleeps
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    source = resolve_source(request.POST.get("source", ""), "supports_add_by_id")
    if source is None:
        return _add_by_id_error(request, is_ajax, "No source available to add papers by ID.")

    raw = request.POST.get("source_ids", "")
    source_ids = _parse_source_ids(source, raw)
    if not source_ids:
        return _add_by_id_error(request, is_ajax, f"No valid {source.label} IDs provided.")

    if not is_ajax and len(source_ids) > MAX_IDS_PER_REQUEST:
        messages.warning(
            request,
            f"Too many IDs ({len(source_ids)}). Only the first {MAX_IDS_PER_REQUEST} will be processed.",
        )
        source_ids = source_ids[:MAX_IDS_PER_REQUEST]

    if is_ajax:
        # AJAX: process a single ID and return the paper info
        sid = source_ids[0]
        papers, failed = _download_source_papers(pb_user, profile, source, [sid])
        if failed or not papers:
            return JsonResponse({"ok": False, "error": f"Failed to download {sid}."}, status=400)
        # The helper hands back the row it linked, which after SHA-256 dedup
        # may be an existing paper under a different source or id.
        return JsonResponse({"ok": True, "paper": _paper_json(papers[0])})

    papers, failed = _download_source_papers(pb_user, profile, source, source_ids)
    if papers:
        messages.success(request, f"Added {len(papers)} paper(s) from {source.label}.")
    for fid in failed:
        messages.warning(request, f"Failed to download {fid}.")

    return redirect(_safe_next(request, "profile_list"))


def _add_by_id_error(request, is_ajax, message):
    """Report an add-by-ID failure the way the caller expects."""
    if is_ajax:
        return JsonResponse({"ok": False, "error": message}, status=400)
    messages.error(request, message)
    return redirect(_safe_next(request, "profile_list"))


def _paper_json(paper):
    """Paper fields the add-paper JS needs to render a row."""
    return {
        "id": paper.pk,
        "title": paper.title,
        "source_id": paper.source_id,
        "source": paper.source,
        "source_label": paper.source_label,
        "landing_url": paper.landing_url,
    }


def _parse_source_ids(source, raw: str) -> list[str]:
    """Extract valid IDs for *source* from free-form input.

    Each token is handed to the source's own parser, so URL, prefixed and
    bare-ID forms are the source's business rather than the view's.
    """
    ids = []
    for token in SOURCE_ID_SEPARATOR_RE.split(raw or ""):
        source_id = source.normalize_id(token)
        if source_id and source_id not in ids:
            ids.append(source_id)
    return ids


def _published_datetime(raw):
    """Parse a source's ISO published timestamp, or None."""
    return parse_datetime(raw) if raw else None


def _published_date_str(raw) -> str:
    """YYYY-MM-DD from a source's ISO published timestamp."""
    dt = _published_datetime(raw)
    return dt.date().isoformat() if dt else (raw or "")[:10]


def _format_author_list(names, cap: int = 25) -> str:
    """Join author names, capping at *cap* names with 'et al.'."""
    names = list(names or [])
    if len(names) > cap:
        return ", ".join(names[:cap]) + " et al."
    return ", ".join(names)


def _download_source_papers(pb_user, profile, source, source_ids):
    """Download PDFs for a list of source IDs, deduplicating by SHA-256.

    Creates Paper rows and links them to the profile's corpus.
    Returns (papers, failed_ids).
    """
    import logging
    import requests as http_requests

    MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
    logger = logging.getLogger(__name__)
    corpus = _get_or_create_user_corpus(pb_user, profile)
    delay = source.request_delay_seconds

    # One batched metadata call up front, so the loop below only fetches PDFs
    try:
        entries = run_sync(source.fetch_many(source_ids))
    except Exception:
        logger.exception("Failed to fetch %s metadata", source.name)
        entries = {}

    papers = []
    failed = []
    for i, sid in enumerate(source_ids):
        # Respect the source's published rate limit between requests
        if i > 0 and delay:
            time.sleep(delay)
        entry = entries.get(sid)
        if entry is None or not entry.pdf_url:
            logger.warning("%s has no PDF for %s", source.name, sid)
            failed.append(sid)
            continue
        try:
            resp = http_requests.get(entry.pdf_url, timeout=30)
            resp.raise_for_status()
            # Reject early if Content-Length header exceeds limit
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_PDF_BYTES:
                logger.warning("PDF for %s too large per Content-Length (%s bytes)", sid, content_length)
                failed.append(sid)
                continue
            if "application/pdf" not in resp.headers.get("Content-Type", ""):
                logger.warning("%s returned non-PDF content for %s", source.name, sid)
                failed.append(sid)
                continue
            if len(resp.content) > MAX_PDF_BYTES:
                logger.warning("PDF for %s exceeds size limit (%d bytes)", sid, len(resp.content))
                failed.append(sid)
                continue

            # Compute hash and check for existing paper
            file_hash = _compute_sha256(resp.content)
            existing = Paper.objects.filter(sha256=file_hash).first()
            if existing:
                # Paper already in DB — just link to this corpus
                _link_paper_to_corpus(existing, corpus)
                papers.append(existing)
                continue

            # New paper — store file and create DB row
            dest = _store_paper_bytes(file_hash, resp.content)
            from django.db import IntegrityError
            try:
                paper = Paper.objects.create(
                    source_id=entry.source_id,
                    sha256=file_hash,
                    title=entry.title or sid,
                    abstract=entry.abstract or None,
                    submitted_date=_published_datetime(entry.published),
                    metadata={"categories": entry.categories,
                              "authors": entry.authors},
                    pdf_path=str(dest),
                    source=source.name,
                )
            except IntegrityError:
                # Race condition: another request created it first
                paper = Paper.objects.get(sha256=file_hash)
            _link_paper_to_corpus(paper, corpus)
            papers.append(paper)
        except Exception:
            logger.exception("Failed to download %s PDF %s", source.name, sid)
            failed.append(sid)
    return papers, failed


@pbuser_required
def paper_search_api_view(request, profile_id):
    """JSON API: search a preprint source by title/author for inline results."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)

    source = resolve_source(request.GET.get("source", ""), "supports_search")
    if source is None:
        return JsonResponse({"error": "No source available to search."}, status=400)

    # Rate limit: honour the source's own request spacing, per session
    cooldown = source.request_delay_seconds
    session_key = f"search_ts_{source.name}"
    now = time.time()
    last_search = request.session.get(session_key, 0)
    if cooldown and now - last_search < cooldown:
        wait = int(cooldown - (now - last_search)) + 1
        return JsonResponse(
            {"error": f"Please wait {wait}s before searching again."},
            status=429,
        )
    request.session[session_key] = now

    title_q = request.GET.get("title", "").strip()
    author_q = request.GET.get("author", "").strip()

    if not title_q and not author_q:
        return JsonResponse({"error": "Enter a title or author."}, status=400)

    try:
        entries = run_sync(source.search(
            title=title_q,
            author=author_q,
            max_results=django_settings.SOURCE_SEARCH_MAX_RESULTS,
        ))
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("%s search failed", source.name)
        # Detect upstream rate limiting from the source
        is_rate_limited = (
            hasattr(exc, 'response') and getattr(exc.response, 'status_code', None) == 429
        ) or '429' in str(exc)
        if is_rate_limited:
            return JsonResponse(
                {"error": f"{source.label} is rate-limiting requests. Please wait a minute and try again."},
                status=429,
            )
        detail = str(exc) if django_settings.DEBUG else "Search failed. Please try again."
        return JsonResponse({"error": detail}, status=500)

    # Existing paper source_ids for this profile (to flag already-added ones)
    corpus = _get_or_create_user_corpus(pb_user, profile)
    existing_ids = set(
        Paper.objects.filter(
            corpora=corpus, source=source.name, source_id__isnull=False
        ).values_list("source_id", flat=True)
    )

    results = [
        {
            "source_id": entry.source_id,
            "title": entry.title,
            "authors": _format_author_list(entry.authors),
            "published": _published_date_str(entry.published),
            "landing_url": source.landing_url(entry.source_id),
            "already_added": entry.source_id in existing_ids,
        }
        for entry in entries
    ]

    return JsonResponse({
        "source": source.name,
        "label": source.label,
        "results": results,
    })


# ── Recommendations ────────────────────────────────────────────────────────

@pbuser_required
def recommendations_view(request):
    pb_user = request.pb_user
    profiles = Profile.objects.filter(user=pb_user).order_by("name")

    if not profiles.exists():
        return render(request, "recommendations/list.html", {
            "pb_user": pb_user,
            "profiles": [],
            "recs_json": "[]",
            "categories_json": "[]",
        })

    # Selected profile (from GET param); default to all profiles
    selected_id = request.GET.get("profile", "")
    selected_profile = None
    if selected_id and selected_id != "all":
        try:
            selected_profile = profiles.get(pk=int(selected_id))
        except (Profile.DoesNotExist, ValueError):
            pass

    # Query all recommendations for this profile (or all)
    recs = _query_profile_recommendations(pb_user, selected_profile)

    # Serialize for JS — convert date_obj to ISO string, drop it
    for r in recs:
        r["date_iso"] = r["date_obj"].isoformat() if r.get("date_obj") else None
        del r["date_obj"]

    # Categories for filter checkboxes
    if selected_profile:
        profile_categories = sorted(selected_profile.categories or [])
    else:
        cats = set()
        for p in profiles:
            cats.update(p.categories or [])
        profile_categories = sorted(cats)

    profile_param = selected_profile.pk if selected_profile else "all"

    return render(request, "recommendations/list.html", {
        "pb_user": pb_user,
        "profiles": profiles,
        "selected_profile": selected_profile,
        "profile_param": profile_param,
        "recs_json": json.dumps(recs),
        "categories_json": json.dumps(profile_categories),
        "code_to_label_json": json.dumps(ARXIV_CODE_TO_LABEL),
        "profiles_json": json.dumps([
            {"id": p.pk, "name": p.name} for p in profiles
        ]),
    })


def _query_profile_recommendations(pb_user, profile=None):
    """
    Fetch recommendations for a profile (or all profiles if None).

    Returns a deduplicated list of recommendation dicts, unsorted
    (the caller applies the final sort).
    """
    if profile:
        corpus_name = f"user_{pb_user.pk}_profile_{profile.pk}"
        try:
            user_corpora = [Corpus.objects.get(user=pb_user, name=corpus_name)]
        except Corpus.DoesNotExist:
            return []
    else:
        # All profiles: collect every user corpus
        user_corpora = list(Corpus.objects.filter(
            user=pb_user, name__startswith=f"user_{pb_user.pk}_profile_"
        ))
        if not user_corpora:
            return []

    # Get runs that used any of these corpora
    runs = RecommendationRun.objects.filter(user_corpus__in=user_corpora)

    # Build a mapping from corpus ID to profile ID by parsing corpus names
    corpus_to_profile = {}
    profile_prefix = f"user_{pb_user.pk}_profile_"
    for c in user_corpora:
        if c.name.startswith(profile_prefix):
            profile_id_str = c.name[len(profile_prefix):]
            if profile_id_str.isdigit():
                corpus_to_profile[c.pk] = int(profile_id_str)

    recs_list = list(
        Recommendation.objects.filter(run__in=runs)
        .select_related("paper", "run")
        .order_by("-paper__submitted_date", "-score", "paper__source_id")
        [:5000]
    )

    # Prefetch summaries for all papers in one query
    paper_ids = {rec.paper_id for rec in recs_list}
    summaries_map = {
        s.paper_id: s.summary_text or ""
        for s in Summary.objects.filter(paper_id__in=paper_ids, mode="abstract")
    }

    # Check which recommended papers are already in each profile's corpus
    # (restricted to paper_ids in this batch for efficiency)
    profile_paper_ids = {}  # {profile_id: set of paper_ids}
    for paper_pk, corpus_pk in Paper.objects.filter(
        pk__in=paper_ids, corpora__in=user_corpora
    ).values_list("pk", "corpora__pk"):
        pid = corpus_to_profile.get(corpus_pk)
        if pid:
            profile_paper_ids.setdefault(pid, set()).add(paper_pk)

    # Deduplicate keeping the highest score. Keyed on (source, source_id).
    seen = {}
    for rec in recs_list:
        paper = rec.paper
        key = (paper.source, paper.source_id) if paper.source_id else f"_pk_{paper.pk}"
        if key in seen and rec.score <= seen[key]["score"]:
            continue

        dt = paper.submitted_date
        date_obj = dt.date() if dt else None
        date_str = dt.strftime("%d %B %Y") if dt else "Unknown Date"

        seen[key] = {
            "paper_id": paper.pk,
            "profile_id": corpus_to_profile.get(rec.run.user_corpus_id),
            "in_corpus": [
                prof_id for prof_id, paper_set in profile_paper_ids.items()
                if paper.pk in paper_set
            ],
            "title": paper.title,
            "score": rec.score,
            "rank": rec.rank,
            "source_id": paper.source_id,
            "source": paper.source,
            "source_label": paper.source_label,
            "landing_url": paper.landing_url,
            "abstract": paper.abstract or "",
            "summary_text": summaries_map.get(paper.pk, ""),
            "date_obj": date_obj,
            "date_str": date_str,
            "categories": paper.categories_list,
            "authors": paper.authors_list,
            "total_papers_fetched": rec.run.total_papers_fetched,
        }

    return list(seen.values())


@pbuser_required
@require_POST
def recommendation_add_to_profile_view(request, profile_id, paper_id):
    """Add a recommended paper to a profile's corpus (AJAX).

    Unlike paper_add_by_id_view, this doesn't download anything — the paper
    already exists in the DB from the pipeline.
    """
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)
    paper = get_object_or_404(Paper, pk=paper_id)

    # Verify the paper was actually recommended to this user
    was_recommended = Recommendation.objects.filter(
        paper=paper, run__user=pb_user
    ).exists()
    if not was_recommended:
        return JsonResponse({"ok": False, "error": "Paper not found."}, status=404)

    corpus = _get_or_create_user_corpus(pb_user, profile)

    already_linked = paper.corpora.filter(pk=corpus.pk).exists()
    if already_linked:
        return JsonResponse({"ok": True, "already_linked": True})

    _link_paper_to_corpus(paper, corpus)
    return JsonResponse({
        "ok": True,
        "already_linked": False,
        "paper": _paper_json(paper),
    })


# ── Settings ───────────────────────────────────────────────────────────────

@pbuser_required
def settings_view(request):
    pb_user = request.pb_user
    profiles = Profile.objects.filter(user=pb_user).order_by("name")

    if request.method == "POST":
        form = UserSettingsForm(request.POST)
        if form.is_valid():
            pb_user.name = form.cleaned_data["name"]
            new_email = form.cleaned_data["email"]
            if new_email != pb_user.email:
                if PBUser.objects.filter(email__iexact=new_email).exclude(pk=pb_user.pk).exists():
                    messages.error(request, "That email is already taken.")
                else:
                    pb_user.email = new_email
            pb_user.save()
            login_pbuser(request, pb_user)  # refresh session
            messages.success(request, "Settings updated.")
            return redirect("settings")
    else:
        form = UserSettingsForm(initial={"name": pb_user.name or "", "email": pb_user.email})

    # Are ALL profiles paused?
    all_paused = profiles.exists() and not profiles.filter(email_notify=True).exists()

    return render(request, "settings.html", {
        "pb_user": pb_user,
        "form": form,
        "profiles": profiles,
        "all_paused": all_paused,
    })


@pbuser_required
@require_POST
def toggle_profile_email_view(request, profile_id):
    """Toggle email_notify for a single profile."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)
    profile.email_notify = not profile.email_notify
    profile.save(update_fields=["email_notify"])
    state = "enabled" if profile.email_notify else "paused"
    messages.success(request, f"Emails {state} for '{profile.name}'.")
    # Redirect back to wherever the user came from, only if local
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("profile_list")


@pbuser_required
@require_POST
def pause_all_emails_view(request):
    """Pause or resume emails for every profile the user owns."""
    pb_user = request.pb_user
    action = request.POST.get("action", "pause")  # "pause" or "resume"
    new_value = action == "resume"
    Profile.objects.filter(user=pb_user).update(email_notify=new_value)
    word = "resumed" if new_value else "paused"
    messages.success(request, f"Email notifications {word} for all profiles.")
    return redirect("settings")


@pbuser_required
@require_POST
def deactivate_account_view(request):
    """Deactivate the account (sets is_active=False, logs out).

    An admin can reactivate the account later via /admin/.
    """
    pb_user = request.pb_user
    # Pause all emails so the pipeline stops sending immediately
    Profile.objects.filter(user=pb_user).update(email_notify=False)
    pb_user.is_active = False
    pb_user.save(update_fields=["is_active"])
    logout_pbuser(request)
    messages.success(request, "Your account has been deactivated.")
    return redirect("login")


@pbuser_required
@require_POST
def delete_account_view(request):
    """Permanently delete the account and all associated data."""
    pb_user = request.pb_user

    # Require the user to type "DELETE" as confirmation
    confirmation = request.POST.get("confirmation", "").strip()
    if confirmation != "DELETE":
        messages.error(request, "Please type DELETE to confirm account deletion.")
        return redirect("settings")

    # Delete the user (cascades to profiles, corpora, paper-corpus links, etc.)
    # Orphaned paper files are cleaned up by: python manage.py cleanup_orphan_papers
    pb_user.delete()
    logout_pbuser(request)
    messages.success(request, "Your account and all data have been permanently deleted.")
    return redirect("login")


# ── Help page ──────────────────────────────────────────────────────────────

def help_view(request):
    return render(request, "help.html")


# ── Monitoring dashboard (staff only) ──────────────────────────────────────

@staff_member_required
def monitoring_dashboard_view(request):
    """Operational dashboard: pipeline freshness, delivery, ingestion, users."""
    now = timezone.now()
    window_days = 30
    since = now - timedelta(days=window_days)

    def _age(ts):
        """Return (human label, hours) for a timestamp, or (None, None)."""
        if not ts:
            return None, None
        delta = now - ts
        hours = delta.total_seconds() / 3600
        if hours < 1:
            label = f"{int(delta.total_seconds() // 60)} min ago"
        elif hours < 48:
            label = f"{int(hours)} h ago"
        else:
            label = f"{int(hours // 24)} d ago"
        return label, hours

    def _daily_series(base_qs, days):
        """Dense oldest→newest daily counts for a vertical bar chart.

        Zero-fills missing days so the x-axis represents real time, tags each
        day with a bar height % (nonzero days get at least 1%), and flags
        Mondays for an x-axis label (once per week). Grouping and the window
        use the local date (USE_TZ).
        """
        end = timezone.localdate()
        start = end - timedelta(days=days - 1)
        counts = {
            r["day"]: r["n"]
            for r in base_qs.filter(created_at__date__gte=start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(n=Count("id"))
        }
        peak = max(counts.values(), default=0) or 1
        series = []
        for i in range(days):
            d = start + timedelta(days=i)
            n = counts.get(d, 0)
            series.append({
                "day": d,
                "n": n,
                "pct": max(1, round(n / peak * 100)) if n else 0,
                "show_label": d.weekday() == 0,  # Mondays (once per week)
            })
        return series

    # ── Pipeline health ──
    last_proc = ProcessingRun.objects.order_by("-started_at").first()
    if last_proc:
        last_run_label, last_run_hours = _age(last_proc.started_at)
        last_run_status = last_proc.status
    else:
        last_run_label, last_run_hours, last_run_status = None, None, None
    last_paper = Paper.objects.aggregate(t=Max("created_at"))["t"]
    last_email = EmailLog.objects.aggregate(t=Max("sent_at"))["t"]
    last_paper_label, _ = _age(last_paper)
    last_email_label, _ = _age(last_email)
    # The pipeline runs nightly, so a gap >26h or a failed last run is a real problem
    pipeline_stale = last_run_hours is None or last_run_hours > 26
    pipeline_failed = last_run_status == "failed"
    recent_processing_runs = list(ProcessingRun.objects.order_by("-started_at")[:10])

    # ── Email delivery (real) ──
    email_counts = EmailLog.objects.filter(sent_at__gte=since).aggregate(
        sent=Count("id", filter=Q(status="sent")),
        failed=Count("id", filter=Q(status="failed")),
    )
    email_sent = email_counts["sent"] or 0
    email_failed = email_counts["failed"] or 0
    email_total = email_sent + email_failed
    email_failure_rate = (email_failed / email_total * 100) if email_total else 0
    _recent_emails = EmailLog.objects.filter(sent_at__gte=since).select_related("user")
    recent_sent = list(_recent_emails.filter(status="sent").order_by("-sent_at")[:100])
    recent_failed = list(_recent_emails.filter(status="failed").order_by("-sent_at")[:100])

    # ── Ingestion (real; ArxivDailyStats is empty, so derive from Paper) ──
    total_papers = Paper.objects.count()
    papers_by_source = {
        row["source"]: row["n"]
        for row in Paper.objects.values("source").annotate(n=Count("id"))
    }
    papers_with_abstract_emb = (
        Paper.objects.filter(embeddings__type="abstract").distinct().count()
    )
    papers_missing_embeddings = total_papers - papers_with_abstract_emb
    papers_per_day = _daily_series(Paper.objects.all(), window_days)
    papers_window_total = sum(r["n"] for r in papers_per_day)

    # ── Recommendations (real) ──
    runs_in_window = RecommendationRun.objects.filter(created_at__gte=since).count()
    recs_in_window = Recommendation.objects.filter(created_at__gte=since).count()
    avg_fetched = RecommendationRun.objects.filter(
        created_at__gte=since
    ).aggregate(a=Avg("total_papers_fetched"))["a"]
    recs_sent_per_day = _daily_series(
        Recommendation.objects.filter(sent_in_email=True), window_days
    )
    recs_sent_window_total = sum(r["n"] for r in recs_sent_per_day)

    # ── User activity (real) ──
    user_total = PBUser.objects.count()
    user_active = PBUser.objects.filter(is_active=True).count()
    user_verified = PBUser.objects.filter(email_verified=True).count()
    user_with_orcid = (
        PBUser.objects.exclude(orcid_id__isnull=True).exclude(orcid_id="").count()
    )
    signups_per_day = _daily_series(PBUser.objects.all(), window_days)
    signups_window_total = sum(r["n"] for r in signups_per_day)
    profiles_total = Profile.objects.count()
    profiles_email_on = Profile.objects.filter(email_notify=True).count()

    context = {
        "window_days": window_days,
        # pipeline health
        "last_run_label": last_run_label,
        "last_run_status": last_run_status,
        "last_paper_label": last_paper_label,
        "last_email_label": last_email_label,
        "pipeline_stale": pipeline_stale,
        "pipeline_failed": pipeline_failed,
        "recent_processing_runs": recent_processing_runs,
        # email
        "email_sent": email_sent,
        "email_failed": email_failed,
        "email_failure_rate": round(email_failure_rate, 1),
        "recent_sent": recent_sent,
        "recent_failed": recent_failed,
        # ingestion
        "total_papers": total_papers,
        "papers_by_source": papers_by_source,
        "papers_missing_embeddings": papers_missing_embeddings,
        "papers_per_day": papers_per_day,
        "papers_window_total": papers_window_total,
        # recommendations
        "runs_in_window": runs_in_window,
        "recs_in_window": recs_in_window,
        "avg_fetched": round(avg_fetched, 1) if avg_fetched is not None else None,
        "recs_sent_per_day": recs_sent_per_day,
        "recs_sent_window_total": recs_sent_window_total,
        # users
        "user_total": user_total,
        "user_active": user_active,
        "user_verified": user_verified,
        "user_with_orcid": user_with_orcid,
        "signups_per_day": signups_per_day,
        "signups_window_total": signups_window_total,
        "profiles_total": profiles_total,
        "profiles_email_on": profiles_email_on,
    }
    return render(request, "monitoring.html", context)
