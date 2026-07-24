"""
Auth convenience helpers wrapping Django's built-in authentication.

PBUser is a proper Django auth model (AbstractBaseUser), so we use
Django's authenticate(), login(), and logout() directly.
"""

from django.contrib.auth import authenticate, login, logout

from .models import PBUser


def authenticate_pbuser(request, email: str, password: str):
    """Authenticate against the PBUser model.

    Django's ModelBackend uses USERNAME_FIELD (email) automatically.
    Emails are stored lowercase, so we normalize before lookup.
    """
    return authenticate(request, username=email.strip().lower(), password=password)


def login_pbuser(request, pb_user: PBUser):
    """Log in a PBUser via Django's session framework."""
    # flag brand-new accounts for onboarding.
    is_first_login = pb_user.last_login is None
    login(request, pb_user)
    if is_first_login:
        request.session["onboarding"] = True


def logout_pbuser(request):
    """Log out the current user."""
    logout(request)


def get_current_pbuser(request) -> PBUser | None:
    """Return the logged-in PBUser, or None."""
    if request.user.is_authenticated:
        return request.user
    return None
