"""Account emails, written per language in templates/accounts/emails/<language>/."""

from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.models import User
from accounts.tokens import make_password_reset_params, make_verification_token

KINDS = ("verify_email", "account_exists", "password_reset")


def app_url(path: str, **params: str) -> str:
    query = f"?{urlencode(params)}" if params else ""
    return f"{settings.PUBLIC_APP_URL.rstrip('/')}{path}{query}"


def _context(kind: str, user: User) -> dict:
    context = {"user": user, "app_url": app_url("/")}
    if kind == "verify_email":
        context["link"] = app_url("/verify-email", token=make_verification_token(user))
    elif kind == "account_exists":
        context["login_link"] = app_url("/login")
        context["reset_link"] = app_url("/forgot-password")
    elif kind == "password_reset":
        context["link"] = app_url("/reset-password", **make_password_reset_params(user))
    return context


def send_account_email(kind: str, user: User) -> None:
    if kind not in KINDS:
        raise ValueError(f"Unknown account email: {kind}")
    language = user.language if user.language in dict(settings.LANGUAGES) else "en"
    folder = f"accounts/emails/{language}"
    context = _context(kind, user)
    subject = render_to_string(f"{folder}/{kind}_subject.txt", context).strip()
    body = render_to_string(f"{folder}/{kind}.txt", context)
    send_mail(subject, body, None, [user.email])
