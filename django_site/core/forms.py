"""
Django forms for authentication, profile CRUD, and paper uploads.
"""

from django import forms


# ── Auth ───────────────────────────────────────────────────────────────────

class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autofocus": True}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )


class RegisterForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autofocus": True}),
    )
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Your name (optional)"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Choose a password"}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password"}),
    )

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if pw and confirm and pw != confirm:
            raise forms.ValidationError("Passwords do not match.")
        if pw:
            from django.contrib.auth.password_validation import validate_password
            validate_password(pw)
        return cleaned


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
    )


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "New password"}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm new password"}),
    )

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if pw and confirm and pw != confirm:
            raise forms.ValidationError("Passwords do not match.")
        if pw:
            from django.contrib.auth.password_validation import validate_password
            validate_password(pw)
        return cleaned


# ── ORCID ──────────────────────────────────────────────────────────────────

class OrcidCompleteForm(forms.Form):
    """Collect email after first ORCID sign-in."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autofocus": True}),
    )


# ── Profiles ───────────────────────────────────────────────────────────────

FREQUENCY_CHOICES = [
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
]


class ProfileForm(forms.Form):
    """Create / edit a research profile."""

    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "e.g. AI Research"}),
    )
    frequency = forms.ChoiceField(choices=FREQUENCY_CHOICES, initial="daily")
    threshold = forms.FloatField(
        min_value=0.40,
        max_value=0.75,
        initial=0.6,
        widget=forms.HiddenInput(),  # actual input is the range slider in the template
    )
    top_x = forms.IntegerField(
        min_value=5,
        max_value=999,
        initial=999,
        label="Max recommendations",
        help_text="Maximum number of recommendations per day (up to 999).",
    )
    categories = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text="Selected via the category tree widget (stored as comma-separated codes).",
    )

    def clean_categories(self):
        from .arxiv_categories import ARXIV_LEAF_CODES
        raw = self.cleaned_data.get("categories", "")
        cats = [c.strip() for c in raw.split(",") if c.strip()]
        if not cats:
            raise forms.ValidationError("Select at least one arXiv category.")
        invalid = [c for c in cats if c not in ARXIV_LEAF_CODES]
        if invalid:
            raise forms.ValidationError(f"Unknown category code(s): {', '.join(invalid)}")
        return cats


# ── Paper upload ───────────────────────────────────────────────────────────


# ── Settings ───────────────────────────────────────────────────────────────

class UserSettingsForm(forms.Form):
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Your name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}))
