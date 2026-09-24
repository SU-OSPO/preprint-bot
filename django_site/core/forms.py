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
        help_text=(
            "Selected via the category tree widget, as comma-separated " "source:code tokens."
        ),
    )

    def clean_categories(self):
        """Parse "source:code" tokens into ``{source: [codes]}``.

        Split on the first colon only, since a server's own codes may contain
        one. A token with no colon is accepted as belonging to the sole
        enabled source but is rejected once more than one source is enabled.
        """
        from .sources import leaf_codes_by_source

        raw = self.cleaned_data.get("categories", "")
        valid = leaf_codes_by_source()
        lone_source = next(iter(valid)) if len(valid) == 1 else None

        selected = {}
        unknown_sources = []
        invalid_codes = []

        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            if ":" in token:
                source_name, _, code = token.partition(":")
                source_name, code = source_name.strip(), code.strip()
            else:
                source_name, code = lone_source, token
            if not source_name or not code:
                invalid_codes.append(token)
                continue
            if source_name not in valid:
                if source_name not in unknown_sources:
                    unknown_sources.append(source_name)
                continue
            if code not in valid[source_name]:
                invalid_codes.append(code)
                continue
            codes = selected.setdefault(source_name, [])
            if code not in codes:
                codes.append(code)

        if unknown_sources:
            raise forms.ValidationError(f"Unknown source(s): {', '.join(unknown_sources)}")
        if invalid_codes:
            raise forms.ValidationError(f"Unknown category code(s): {', '.join(invalid_codes)}")
        if not selected:
            raise forms.ValidationError("Select at least one category.")
        return selected


# ── Paper upload ───────────────────────────────────────────────────────────


# ── Settings ───────────────────────────────────────────────────────────────


class UserSettingsForm(forms.Form):
    name = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": "Your name"})
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}))
