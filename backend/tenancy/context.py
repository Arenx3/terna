"""The active company, for Python code and for the database.

Two layers hold it, and they are always set together:
- a context variable, read by Python (model saves, tasks);
- the `app.company_id` setting of the current transaction (SET LOCAL), read by
  the row-level security policies.

Use `tenant_context(company_id)` around any code that touches tenant data. API
views get it from `tenancy.api.TenantScopedMixin`, Celery tasks from
`tenancy.tasks.tenant_task`.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from django.core.exceptions import ImproperlyConfigured
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from tenancy import db

_current_company: ContextVar[uuid.UUID | None] = ContextVar("current_company", default=None)


class NoActiveCompanyError(RuntimeError):
    """Tenant data was touched with no company chosen."""


def _as_uuid(company_id: uuid.UUID | str) -> uuid.UUID:
    return company_id if isinstance(company_id, uuid.UUID) else uuid.UUID(str(company_id))


def current_company_id() -> uuid.UUID | None:
    return _current_company.get()


def require_company_id() -> uuid.UUID:
    company_id = _current_company.get()
    if company_id is None:
        raise NoActiveCompanyError("No active company. Wrap this code in tenant_context().")
    return company_id


def activate(company_id: uuid.UUID | str, using: str = DEFAULT_DB_ALIAS) -> Token:
    """Set the company for the current transaction. Returns a token for `deactivate`.

    Must run inside a transaction (ATOMIC_REQUESTS for views, `tenant_context`
    elsewhere): outside one, SET LOCAL would vanish before the next query.
    """
    company_id = _as_uuid(company_id)
    connection = connections[using]
    if not connection.in_atomic_block:
        raise ImproperlyConfigured("activate() needs a transaction; use tenant_context().")
    db.set_company(connection, str(company_id))
    return _current_company.set(company_id)


def deactivate(token: Token, using: str = DEFAULT_DB_ALIAS) -> None:
    """Undo `activate`. Clears the database setting if the transaction is still usable."""
    _current_company.reset(token)
    connection = connections[using]
    if connection.in_atomic_block and not connection.needs_rollback:
        previous = _current_company.get()
        db.set_company(connection, str(previous) if previous else "")


@contextmanager
def tenant_context(
    company_id: uuid.UUID | str, using: str = DEFAULT_DB_ALIAS
) -> Iterator[uuid.UUID]:
    """Run a block as `company_id`, in a transaction (a savepoint if one is open).

    On success the previous company is restored. On error the savepoint is
    rolled back, and PostgreSQL reverts the setting with it.
    """
    company_id = _as_uuid(company_id)
    with transaction.atomic(using=using):
        token = activate(company_id, using=using)
        try:
            yield company_id
        except BaseException:
            _current_company.reset(token)
            raise
        deactivate(token, using=using)


def all_company_ids(using: str = DEFAULT_DB_ALIAS) -> list[uuid.UUID]:
    """Every company id, for system jobs that fan out one task per company.

    Row-level security hides other companies from the app role, so this goes
    through a SECURITY DEFINER function that returns ids and nothing else.
    """
    with connections[using].cursor() as cursor:
        cursor.execute(f"SELECT * FROM {db.ALL_COMPANIES_FUNCTION}()")  # noqa: S608 (constant name)
        return [row[0] for row in cursor.fetchall()]
