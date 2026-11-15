from django.urls import path

from apps.accounts import api

urlpatterns = [
    path("auth/csrf", api.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login", api.LoginView.as_view(), name="auth-login"),
    path("auth/logout", api.LogoutView.as_view(), name="auth-logout"),
    path("auth/password", api.ChangePasswordView.as_view(), name="auth-password"),
    path("auth/password-reset", api.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm",
        api.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("me", api.MeView.as_view(), name="me"),
]
