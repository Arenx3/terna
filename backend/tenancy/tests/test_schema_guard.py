"""Guards for future migrations: every table must be either global or isolated."""

import pytest
from django.conf import settings
from django.db import connection

from tenancy.db import CURRENT_COMPANY_FUNCTION, POLICY_NAME
from tenancy.models import GLOBAL_TABLES

pytestmark = pytest.mark.django_db


def query(statement: str, params: tuple = ()) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def public_tables() -> dict[str, tuple[bool, bool]]:
    rows = query(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        """
    )
    return {name: (enabled, forced) for name, enabled, forced in rows}


def tenant_tables() -> set[str]:
    rows = query(
        """
        SELECT table_name FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name = 'company_id'
        """
    )
    return {name for (name,) in rows} | {"tenancy_company"}


def policies() -> dict[str, tuple[str, str]]:
    rows = query(
        "SELECT tablename, qual, with_check FROM pg_policies "
        "WHERE schemaname = 'public' AND policyname = %s",
        (POLICY_NAME,),
    )
    return {table: (qual, check) for table, qual, check in rows}


def test_every_table_is_either_global_or_tenant_scoped():
    unclassified = set(public_tables()) - tenant_tables() - GLOBAL_TABLES
    assert not unclassified, (
        f"Tables with no company and not declared global: {sorted(unclassified)}. "
        "Make the model a TenantModel, or add the table to GLOBAL_TABLES if it holds "
        "no customer data."
    )


def test_every_tenant_table_has_forced_row_level_security():
    tables = public_tables()
    unprotected = [name for name in tenant_tables() if tables.get(name) != (True, True)]
    assert not unprotected, f"Row-level security missing or not forced on: {unprotected}"


def test_every_tenant_table_has_the_isolation_policy():
    found = policies()
    for table in tenant_tables():
        assert table in found, f"No {POLICY_NAME} policy on {table}"
        qual, check = found[table]
        assert CURRENT_COMPANY_FUNCTION in qual
        assert CURRENT_COMPANY_FUNCTION in check


def test_app_role_has_no_way_around_the_policies():
    [(superuser, bypass_rls, create_role, create_db)] = query(
        "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
        "FROM pg_roles WHERE rolname = %s",
        (settings.DATABASE_APP_ROLE,),
    )
    assert (superuser, bypass_rls, create_role, create_db) == (False, False, False, False)

    owned = query(
        "SELECT tablename FROM pg_tables WHERE tableowner = %s", (settings.DATABASE_APP_ROLE,)
    )
    assert owned == [], "The app role must not own tables: owners can drop policies."
