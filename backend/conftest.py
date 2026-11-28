import hashlib
import math
import re

import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import connection
from django.utils import timezone
from psycopg import sql
from rest_framework.test import APIClient

from accounts.models import Membership, User
from accounts.sessions import issue_refresh_token
from core.storage import s3_client
from screening import embeddings
from screening.models import DIMENSIONS
from screening.redaction import fold
from tenancy.context import tenant_context
from tenancy.services import create_company


class StandInModel:
    """Takes the embedding model's place in tests: the real one is a download away, and
    only the ml image has it. Words hashed into the vector, so texts that share words
    are close; `close(a, b)` makes two texts close without sharing any, the way the
    real model brings Spanish and English together."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.pairs: list[tuple[str, str]] = []
        self.broken: Exception | None = None

    def close(self, a: str, b: str) -> None:
        self.pairs.append((a, b))

    def vector(self, text: str) -> list[float]:
        values = [0.0] * DIMENSIONS
        for word in re.findall(r"[a-z0-9]{3,}", fold(text)):
            values[int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        for index, (a, b) in enumerate(self.pairs):
            if a in text or b in text:
                values[(index * 7) % DIMENSIONS] += 10.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self.broken:
            raise self.broken
        self.calls.append(list(texts))
        return [self.vector(text) for text in texts]


@pytest.fixture(autouse=True)
def model(monkeypatch) -> StandInModel:
    stand_in = StandInModel()
    monkeypatch.setattr(embeddings, "encode", lambda texts: stand_in.encode(texts) if texts else [])
    return stand_in


@pytest.fixture(autouse=True)
def _run_as_app_role(request):
    """Every database test runs as the unprivileged app role, like production.

    The test runner connects as the owner role to create the test database,
    and owners can bypass row-level security. Switching role per test makes
    the policies apply to the whole suite, not only to the isolation tests.
    """
    marker = request.node.get_closest_marker("django_db")
    if marker is None:
        yield
        return

    transactional = marker.kwargs.get("transaction", False)
    request.getfixturevalue("transactional_db" if transactional else "db")
    # In a test transaction SET LOCAL ends with its rollback; otherwise reset by hand.
    scope = sql.SQL("SESSION" if transactional else "LOCAL")
    with connection.cursor() as cursor:
        statement = sql.SQL("SET {} ROLE {}").format(
            scope, sql.Identifier(settings.DATABASE_APP_ROLE)
        )
        cursor.execute(statement.as_string(cursor.connection))
    yield
    if transactional:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


@pytest.fixture
def company_a(db):
    return create_company("Acme")


@pytest.fixture
def company_b(db):
    return create_company("Globex")


class _Member:
    """Stand-in for an authenticated user until accounts exist (#7)."""

    is_authenticated = True


@pytest.fixture
def api_as():
    """An API client whose access token carries `company`, as a real login will."""

    def make(company=None, *, claim: str | None = None) -> APIClient:
        value = str(company.id) if company is not None else claim
        client = APIClient()
        client.force_authenticate(
            user=_Member(), token={} if value is None else {"company_id": value}
        )
        return client

    return make


Role = Membership.Role


class Team:
    """A company with one person per role, and API clients logged in as each."""

    def __init__(self, name: str) -> None:
        self.company = create_company(name)
        self.people: dict[str, User] = {}
        slug = name.lower()
        for role in Role.values:
            user = User.objects.create_user(
                f"{role}@{slug}.test",
                "correct-horse-battery-42",
                full_name=f"{role.replace('_', ' ').title()} {name}",
                email_verified_at=timezone.now(),
            )
            with tenant_context(self.company.id):
                Membership.objects.create(company=self.company, user=user, role=role)
            self.people[role] = user

    def client(self, role: str) -> APIClient:
        client = APIClient()
        token = issue_refresh_token(self.people[role], self.company.id).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client


@pytest.fixture
def acme(db):
    return Team("Acme")


@pytest.fixture
def globex(db):
    return Team("Globex")


@pytest.fixture
def job_payload():
    def make(**overrides) -> dict:
        payload = {
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "location": "Monterrey, NL",
            "workplace": "hybrid",
            "employment": "full_time",
            "language": "es",
            "description": "Build the services behind checkout.",
            "requirements": [
                {"text": "5+ years building APIs in Python", "kind": "must"},
                {"text": "Kubernetes in production", "kind": "must"},
                {"text": "Advanced English", "kind": "nice"},
            ],
        }
        payload.update(overrides)
        return payload

    return make


TEST_BUCKET = "terna-tests"


@pytest.fixture
def test_bucket(settings):
    """A bucket of its own for tests that store files, so they never touch the demo's."""
    settings.STORAGE_BUCKET = TEST_BUCKET
    client = s3_client()
    try:
        client.head_bucket(Bucket=TEST_BUCKET)
    except ClientError:
        client.create_bucket(Bucket=TEST_BUCKET)
    return TEST_BUCKET
