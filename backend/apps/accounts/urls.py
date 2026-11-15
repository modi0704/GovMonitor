from django.urls import path

from apps.accounts import api, api_2fa, users_api

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
    path("users", users_api.UserListView.as_view(), name="users"),
    path("users/<uuid:user_id>", users_api.UserDetailView.as_view(), name="user"),
    path("users/<uuid:user_id>/reset-password", users_api.UserResetPasswordView.as_view(), name="user-reset"),
    path("users/<uuid:user_id>/scope", users_api.UserScopeView.as_view(), name="user-scope"),
    path("role-assignments", users_api.RoleAssignmentListView.as_view(), name="role-assignments"),
    path(
        "role-assignments/<uuid:assignment_id>",
        users_api.RoleAssignmentDetailView.as_view(),
        name="role-assignment",
    ),
]
