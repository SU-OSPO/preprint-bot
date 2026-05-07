"""
Django views for the Preprint Bot web interface.

Authentication uses Django's built-in auth system with PBUser as
the custom user model (AUTH_USER_MODEL).
"""

import json
import re
import time
from functools import wraps
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .arxiv_categories import ARXIV_CODE_TO_LABEL, ARXIV_CATEGORY_TREE, label_for
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
    PBUser,
    Paper,
    Profile,
    Recommendation,
    RecommendationRun,
    Summary,
)

ARXIV_ID_RE = re.compile(
    r"^(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7})$", re.IGNORECASE
)


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


# ── Decorator ──────────────────────────────────────────────────────────────

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

    return render(
        request,
        "dashboard.html",
        {
            "pb_user": pb_user,
            "profiles": profiles,
            "total_recs": total_recs,
            "today_recs": today_recs[:20],
            "today_count": len(today_recs),
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
        "arxiv_search_per_page": django_settings.ARXIV_SEARCH_PER_PAGE,
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

    return redirect("profile_list")


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

    return redirect("profile_list")


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
def paper_add_arxiv_view(request, profile_id):
    """Add papers from arXiv by ID – downloads the PDF into the profile dir."""
    MAX_IDS_PER_REQUEST = 10  # cap to avoid blocking worker with time.sleep(3) delays
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)

    raw = request.POST.get("arxiv_ids", "")
    arxiv_ids = _parse_arxiv_ids(raw)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not arxiv_ids:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "No valid arXiv IDs provided."}, status=400)
        messages.error(request, "No valid arXiv IDs provided.")
        return redirect("profile_list")

    if not is_ajax and len(arxiv_ids) > MAX_IDS_PER_REQUEST:
        messages.warning(
            request,
            f"Too many IDs ({len(arxiv_ids)}). Only the first {MAX_IDS_PER_REQUEST} will be processed.",
        )
        arxiv_ids = arxiv_ids[:MAX_IDS_PER_REQUEST]

    if is_ajax:
        # AJAX: process a single ID and return the paper info
        aid = arxiv_ids[0]
        success, failed = _download_arxiv_pdfs(pb_user, profile, [aid])
        if failed:
            return JsonResponse({"ok": False, "error": f"Failed to download {aid}."}, status=400)
        # Look up the paper to return its info for the DOM
        paper = Paper.objects.filter(arxiv_id=aid).order_by("-id").first()
        if not paper:
            # Legacy data may have version suffix (e.g., 2507.08778v1);
            # prefer the newest matching row deterministically.
            paper = Paper.objects.filter(arxiv_id__startswith=aid + 'v').order_by("-id").first()
        if not paper:
            return JsonResponse({"ok": False, "error": f"Paper stored but could not be retrieved for arXiv ID {aid}."}, status=500)
        return JsonResponse({
            "ok": True,
            "paper": {
                "id": paper.pk,
                "title": paper.title,
                "arxiv_id": paper.arxiv_id,
                "source": paper.source,
            },
        })

    success, failed = _download_arxiv_pdfs(pb_user, profile, arxiv_ids)
    if success:
        messages.success(request, f"Added {success} paper(s) from arXiv.")
    for fid in failed:
        messages.warning(request, f"Failed to download {fid}.")

    return redirect("profile_list")


def _parse_arxiv_ids(raw: str) -> list[str]:
    """Extract valid arXiv IDs from free-form input."""
    ids = []
    for line in raw.replace(",", "\n").splitlines():
        token = line.strip()
        if not token:
            continue
        # Strip URL prefixes
        token = re.sub(r"https?://arxiv\.org/(abs|pdf)/", "", token)
        if token.lower().startswith("arxiv:"):
            token = token[6:]
        # Strip query/fragment suffixes, then .pdf, then trailing version
        token = re.sub(r"[?#].*$", "", token)
        token = re.sub(r"\.pdf$", "", token, flags=re.IGNORECASE)
        token = re.sub(r"v\d+$", "", token)
        if ARXIV_ID_RE.match(token) and token not in ids:
            ids.append(token)
    return ids


def _fetch_arxiv_metadata(arxiv_ids):
    """Batch-fetch metadata (title, abstract, date) from arXiv API.

    Returns a dict keyed by arxiv_id (version-stripped).
    Falls back gracefully if the arxiv package is unavailable.
    """
    metadata = {}
    try:
        import arxiv as arxiv_lib

        client = arxiv_lib.Client()
        search = arxiv_lib.Search(id_list=arxiv_ids)
        for paper in client.results(search):
            aid = paper.get_short_id().split("v")[0]  # strip version
            metadata[aid] = {
                "title": paper.title,
                "abstract": paper.summary,
                "submitted_date": paper.published,
                "authors": [a.name for a in paper.authors],
                "categories": [c for c in paper.categories],
            }
    except ImportError:
        pass  # arxiv package not installed; titles will be arXiv IDs
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to fetch arXiv metadata")
    return metadata


def _download_arxiv_pdfs(pb_user, profile, arxiv_ids):
    """Download PDFs for a list of arXiv IDs, deduplicating by SHA-256.

    Creates Paper rows and links them to the profile's corpus.
    Returns (success_count, failed_ids).
    """
    import logging
    import requests as http_requests

    MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
    logger = logging.getLogger(__name__)
    corpus = _get_or_create_user_corpus(pb_user, profile)

    # Batch-fetch metadata (title, abstract, date) from arXiv API
    arxiv_meta = _fetch_arxiv_metadata(arxiv_ids)

    success = 0
    failed = []
    for i, aid in enumerate(arxiv_ids):
        # Respect arXiv rate limits: no more than one request every 3 seconds
        if i > 0:
            time.sleep(3)
        try:
            resp = http_requests.get(f"https://arxiv.org/pdf/{aid}.pdf", timeout=30)
            resp.raise_for_status()
            # Reject early if Content-Length header exceeds limit
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_PDF_BYTES:
                logger.warning("arXiv PDF for %s too large per Content-Length (%s bytes)", aid, content_length)
                failed.append(aid)
                continue
            if "application/pdf" not in resp.headers.get("Content-Type", ""):
                logger.warning("arXiv returned non-PDF content for %s", aid)
                failed.append(aid)
                continue
            if len(resp.content) > MAX_PDF_BYTES:
                logger.warning("arXiv PDF for %s exceeds size limit (%d bytes)", aid, len(resp.content))
                failed.append(aid)
                continue

            # Compute hash and check for existing paper
            file_hash = _compute_sha256(resp.content)
            existing = Paper.objects.filter(sha256=file_hash).first()
            if existing:
                # Paper already in DB — just link to this corpus
                _link_paper_to_corpus(existing, corpus)
                success += 1
                continue

            # New paper — store file and create DB row
            dest = _store_paper_bytes(file_hash, resp.content)
            meta = arxiv_meta.get(aid, {})
            from django.db import IntegrityError
            try:
                paper = Paper.objects.create(
                    arxiv_id=aid,
                    sha256=file_hash,
                    title=meta.get("title", aid),
                    abstract=meta.get("abstract"),
                    submitted_date=meta.get("submitted_date"),
                    metadata={"categories": meta.get("categories", []),
                              "authors": meta.get("authors", [])},
                    pdf_path=str(dest),
                    source="arxiv",
                )
            except IntegrityError:
                # Race condition: another request created it first
                paper = Paper.objects.get(sha256=file_hash)
            _link_paper_to_corpus(paper, corpus)
            success += 1
        except Exception:
            logger.exception("Failed to download arXiv PDF %s", aid)
            failed.append(aid)
    return success, failed


@pbuser_required
def paper_search_arxiv_api_view(request, profile_id):
    """JSON API: search arXiv by title/author for inline results."""
    pb_user = request.pb_user
    profile = get_object_or_404(Profile, pk=profile_id, user=pb_user)

    # Rate limit: one search per 3 seconds per session
    SEARCH_COOLDOWN = 3  # seconds
    now = time.time()
    last_search = request.session.get("arxiv_search_ts", 0)
    if now - last_search < SEARCH_COOLDOWN:
        wait = int(SEARCH_COOLDOWN - (now - last_search)) + 1
        return JsonResponse(
            {"error": f"Please wait {wait}s before searching again."},
            status=429,
        )
    request.session["arxiv_search_ts"] = now

    title_q = request.GET.get("title", "").strip().replace('"', "")
    author_q = request.GET.get("author", "").strip().replace('"', "")

    if not title_q and not author_q:
        return JsonResponse({"error": "Enter a title or author."}, status=400)

    try:
        import arxiv as arxiv_lib

        parts = []
        if title_q:
            parts.append(f'ti:"{title_q}"')
        if author_q:
            parts.append(f'au:"{author_q}"')
        query_string = " AND ".join(parts)

        client = arxiv_lib.Client()
        search = arxiv_lib.Search(
            query=query_string,
            max_results=django_settings.ARXIV_SEARCH_MAX_RESULTS,
            sort_by=arxiv_lib.SortCriterion.SubmittedDate,
            sort_order=arxiv_lib.SortOrder.Descending,
        )

        # Existing paper arxiv_ids for this profile (to flag already-added ones)
        corpus = _get_or_create_user_corpus(pb_user, profile)
        existing_ids = set(
            Paper.objects.filter(corpora=corpus, arxiv_id__isnull=False)
            .values_list("arxiv_id", flat=True)
        )

        results = []
        for paper in client.results(search):
            aid = paper.get_short_id().split("v")[0]  # strip version
            # Truncate author list after 25 names
            author_names = [a.name for a in paper.authors]
            if len(author_names) > 25:
                authors_str = ", ".join(author_names[:25]) + " et al."
            else:
                authors_str = ", ".join(author_names)
            results.append({
                "arxiv_id": aid,
                "title": paper.title,
                "authors": authors_str,
                "published": paper.published.strftime("%Y-%m-%d"),
                "already_added": aid in existing_ids,
            })

        return JsonResponse({"results": results})

    except ImportError:
        return JsonResponse(
            {"error": "The 'arxiv' package is not installed. Run: pip install arxiv"},
            status=500,
        )
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("arXiv search failed")
        # Detect upstream rate limiting from arXiv
        is_rate_limited = (
            hasattr(exc, 'response') and getattr(exc.response, 'status_code', None) == 429
        ) or '429' in str(exc)
        if is_rate_limited:
            return JsonResponse(
                {"error": "arXiv is rate-limiting requests. Please wait a minute and try again."},
                status=429,
            )
        detail = str(exc) if django_settings.DEBUG else "Search failed. Please try again."
        return JsonResponse({"error": detail}, status=500)


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
    recs_list = list(
        Recommendation.objects.filter(run__in=runs)
        .select_related("paper", "run")
        .order_by("-paper__submitted_date", "-score", "paper__arxiv_id")
        [:5000]
    )

    # Prefetch summaries for all papers in one query
    paper_ids = {rec.paper_id for rec in recs_list}
    summaries_map = {
        s.paper_id: s.summary_text or ""
        for s in Summary.objects.filter(paper_id__in=paper_ids, mode="abstract")
    }

    # Deduplicate by arxiv_id keeping highest score
    seen = {}
    for rec in recs_list:
        paper = rec.paper
        aid = paper.arxiv_id or f"_pk_{paper.pk}"
        if aid in seen and rec.score <= seen[aid]["score"]:
            continue

        dt = paper.submitted_date
        date_obj = dt.date() if dt else None
        date_str = dt.strftime("%d %B %Y") if dt else "Unknown Date"

        seen[aid] = {
            "title": paper.title,
            "score": rec.score,
            "rank": rec.rank,
            "arxiv_id": paper.arxiv_id,
            "abstract": paper.abstract or "",
            "summary_text": summaries_map.get(paper.pk, ""),
            "date_obj": date_obj,
            "date_str": date_str,
            "categories": paper.categories_list,
            "total_papers_fetched": rec.run.total_papers_fetched,
        }

    return list(seen.values())


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
