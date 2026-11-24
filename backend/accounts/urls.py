from django.urls import path

from accounts import views

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="auth-signup"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path(
        "verify-email/resend/",
        views.ResendVerificationView.as_view(),
        name="auth-resend-verification",
    ),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("password-reset/", views.PasswordResetView.as_view(), name="auth-password-reset"),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("me/", views.MeView.as_view(), name="auth-me"),
]
