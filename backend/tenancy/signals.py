from django.apps import apps
from django.conf import settings
from django.db import connections

from tenancy import db
from tenancy.models import Company, TenantModel


def tenant_models() -> list[type]:
    """Company plus every concrete, managed TenantModel in the project."""
    found: list[type] = [Company]
    for model in apps.get_models():
        meta = model._meta
        if issubclass(model, TenantModel) and meta.managed and not meta.proxy:
            found.append(model)
    return found


def apply_tenant_policies(using: str, **kwargs) -> None:
    """After every `migrate`: isolate each tenant table and grant the app role.

    Idempotent, so a new TenantModel is covered by the next migration with no
    extra step, and a changed policy definition reaches existing tables.
    """
    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    for model in tenant_models():
        db.enable_row_level_security(connection, model._meta.db_table, model.tenant_column)
    db.grant_app_role(connection, settings.DATABASE_APP_ROLE)
