import secrets
import uuid
from collections.abc import Iterator

from django.db import IntegrityError, connection, transaction
from django.utils.text import slugify

from tenancy.context import tenant_context
from tenancy.db import COMPANY_BY_SLUG_FUNCTION
from tenancy.models import Company

SLUG_MAX_LENGTH = 50


def _slug_candidates(name: str) -> Iterator[str]:
    """ "Acme Industrial" → acme-industrial, acme-industrial-2 … then a random suffix."""
    base = slugify(name)[:SLUG_MAX_LENGTH].strip("-") or "company"
    yield base
    for number in range(2, 10):
        yield f"{base}-{number}"
    while True:
        yield f"{base}-{secrets.token_hex(3)}"


def create_company(name: str) -> Company:
    """Create a company with a unique public slug.

    Row-level security only lets a company insert itself, so its id is chosen
    first and becomes the active company for the insert. Other companies'
    slugs are invisible here; the unique index still sees them, so a taken
    slug fails the insert and the next candidate is tried.
    """
    company_id = uuid.uuid4()
    with tenant_context(company_id):
        for slug in _slug_candidates(name):
            try:
                with transaction.atomic():
                    return Company.objects.create(id=company_id, name=name, slug=slug)
            except IntegrityError:
                continue
    raise AssertionError("unreachable: slug candidates never run out")


def company_by_slug(slug: str) -> tuple[uuid.UUID, str] | None:
    """(id, name) of the company with this public slug, for anonymous visitors.

    Visitors have no company, so this goes through a SECURITY DEFINER function
    that matches one exact slug and returns its id and name only.
    """
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {COMPANY_BY_SLUG_FUNCTION}(%s)", [slug])  # noqa: S608
        row = cursor.fetchone()
    return (row[0], row[1]) if row else None
