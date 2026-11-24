import uuid

from tenancy.context import tenant_context
from tenancy.models import Company


def create_company(name: str) -> Company:
    """Create a company. Row-level security only lets a company insert itself,
    so its id is chosen first and becomes the active company for the insert."""
    company_id = uuid.uuid4()
    with tenant_context(company_id):
        return Company.objects.create(id=company_id, name=name)
