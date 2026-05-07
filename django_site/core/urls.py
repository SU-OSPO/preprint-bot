from django.urls import path
from . import views

urlpatterns = [
    # Dashboard (home)
    path("", views.dashboard_view, name="dashboard"),

    # Auth
    path("auth/login/", views.login_view, name="login"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("auth/forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("auth/reset-password/<str:uidb64>/<str:token>/", views.reset_password_view, name="reset_password"),
    path("auth/verify-email/<str:uidb64>/<str:token>/", views.verify_email_view, name="verify_email"),
    path("auth/resend-verification/", views.resend_verification_view, name="resend_verification"),
    path("auth/orcid/login/", views.orcid_login_view, name="orcid_login"),
    path("auth/orcid/callback/", views.orcid_callback_view, name="orcid_callback"),
    path("auth/orcid/complete/", views.orcid_complete_view, name="orcid_complete"),
    path("auth/orcid/link/", views.orcid_link_view, name="orcid_link"),
    path("auth/orcid/unlink/", views.orcid_unlink_view, name="orcid_unlink"),

    # Profiles
    path("profiles/", views.profile_list_view, name="profile_list"),
    path("profiles/create/", views.profile_create_view, name="profile_create"),
    path("profiles/<int:profile_id>/edit/", views.profile_edit_view, name="profile_edit"),
    path("profiles/<int:profile_id>/delete/", views.profile_delete_view, name="profile_delete"),

    # Paper management (within a profile)
    path("profiles/<int:profile_id>/upload/", views.paper_upload_view, name="paper_upload"),
    path("profiles/<int:profile_id>/papers/<int:paper_id>/delete/", views.paper_delete_view, name="paper_delete"),
    path("profiles/<int:profile_id>/papers/<int:paper_id>/", views.paper_view, name="paper_view"),
    path("profiles/<int:profile_id>/add-arxiv/", views.paper_add_arxiv_view, name="paper_add_arxiv"),
    path("profiles/<int:profile_id>/search-arxiv/", views.paper_search_arxiv_api_view, name="paper_search_arxiv_api"),

    # Recommendations
    path("recommendations/", views.recommendations_view, name="recommendations"),
    path("recommendations/add/<int:profile_id>/<int:paper_id>/", views.recommendation_add_to_profile_view, name="recommendation_add_to_profile"),

    # Settings
    path("settings/", views.settings_view, name="settings"),
    path("settings/toggle-email/<int:profile_id>/", views.toggle_profile_email_view, name="toggle_profile_email"),
    path("settings/pause-all-emails/", views.pause_all_emails_view, name="pause_all_emails"),
    path("settings/deactivate/", views.deactivate_account_view, name="deactivate_account"),
    path("settings/delete-account/", views.delete_account_view, name="delete_account"),

    # Help
    path("help/", views.help_view, name="help"),
]
