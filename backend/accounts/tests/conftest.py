import re

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Membership, User
from accounts.sessions import issue_refresh_token
from tenancy.context import tenant_context
from tenancy.services import create_company

PASSWORD = "correct-horse-battery-42"


@pytest.fixture(autouse=True)
def _fresh_throttles():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def post(api, django_capture_on_commit_callbacks):
    """POST JSON and run on-commit callbacks, so queued emails are actually sent."""

    def send(url: str, data: dict | None = None, **extra):
        with django_capture_on_commit_callbacks(execute=True):
            return api.post(url, data or {}, format="json", **extra)

    return send


@pytest.fixture
def member(db):
    """A verified admin of a company, ready to log in."""

    def make(email: str = "ana@acme.test", company_name: str = "Acme", **fields) -> User:
        user = User.objects.create_user(
            email, PASSWORD, full_name="Ana Pérez", email_verified_at=timezone.now(), **fields
        )
        company = create_company(company_name)
        with tenant_context(company.id):
            Membership.objects.create(company=company, user=user, role=Membership.Role.ADMIN)
        user.company = company
        return user

    return make


def link_in(message, path: str) -> str:
    """The app link to `path` in an email body, made relative to the app."""
    match = re.search(rf"https?://[^\s]+{re.escape(path)}\?[^\s]+", message.body)
    assert match, f"No {path} link in: {message.body}"
    return match.group(0)


@pytest.fixture
def add_member(db):
    """Add a verified person to an existing company with a role."""

    def add(company, email: str, role: str, full_name: str = "Team Member") -> User:
        user = User.objects.filter(email=email).first() or User.objects.create_user(
            email, PASSWORD, full_name=full_name, email_verified_at=timezone.now()
        )
        with tenant_context(company.id):
            Membership.objects.create(company=company, user=user, role=role)
        return user

    return add


@pytest.fixture
def as_user(api):
    """Authenticate the API client as `user` in `company`, as a real login would."""

    def login(user, company) -> APIClient:
        refresh = issue_refresh_token(user, company.id)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return api

    return login
