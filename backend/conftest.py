import pytest
from django.conf import settings
from django.db import connection
from psycopg import sql
from rest_framework.test import APIClient

from tenancy.services import create_company


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
