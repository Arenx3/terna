"""Sessions: a short-lived access token in memory, a rotating refresh token in a cookie.

The access token carries the active company (`company_id`), which the API uses
to scope every request. The refresh token lives in an httpOnly, SameSite=Strict
cookie restricted to /api/auth/, so JavaScript can never read it and other
sites can never send it.
"""

import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import connection
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from tenancy.api import COMPANY_CLAIM

USER_MEMBERSHIPS_FUNCTION = "app_user_memberships"


@dataclass(frozen=True)
class CompanyMembership:
    company_id: uuid.UUID
    company_name: str
    role: str


def user_memberships(user_id: uuid.UUID) -> list[CompanyMembership]:
    """Every company the user belongs to, oldest first.

    Row-level security only shows the active company, and at login there is
    none yet, so this goes through a SECURITY DEFINER function limited to one
    user's memberships.
    """
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {USER_MEMBERSHIPS_FUNCTION}(%s)", [user_id])  # noqa: S608
        return [CompanyMembership(*row) for row in cursor.fetchall()]


def membership_in(user_id: uuid.UUID, company_id: uuid.UUID) -> CompanyMembership | None:
    return next((m for m in user_memberships(user_id) if m.company_id == company_id), None)


def issue_refresh_token(user: User, company_id: uuid.UUID) -> RefreshToken:
    refresh = RefreshToken.for_user(user)
    refresh[COMPANY_CLAIM] = str(company_id)  # copied into every access token it mints
    return refresh


def set_refresh_cookie(response: Response, refresh: RefreshToken) -> None:
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="Strict",
        secure=settings.AUTH_COOKIE_SECURE,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_REFRESH_COOKIE_PATH, samesite="Strict"
    )
