from django.urls import path

from apps.accounts import api, api_2fa

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
    path("auth/2fa", api_2fa.TwoFactorVerifyView.as_view(), name="auth-2fa"),
    path("auth/2fa/setup", api_2fa.TwoFactorSetupView.as_view(), name="auth-2fa-setup"),
    path("auth/2fa/enable", api_2fa.TwoFactorEnableView.as_view(), name="auth-2fa-enable"),
    path("auth/2fa/disable", api_2fa.TwoFactorDisableView.as_view(), name="auth-2fa-disable"),
    path("me", api.MeView.as_view(), name="me"),
]
