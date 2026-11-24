"""Isolation enforced by PostgreSQL itself, with raw SQL and no Django filtering.

These run as the app role (see conftest.py), exactly like the API and workers.
"""

import psycopg
import pytest
from django.conf import settings
from django.db import DatabaseError, connection, transaction
from psycopg import sql

from config.env import env
from tenancy.context import all_company_ids, tenant_context
from tenancy.models import Company
from testapp.models import Note

pytestmark = pytest.mark.django_db


def query(statement: str, params: tuple = ()) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def execute(statement: str, params: tuple = ()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.rowcount


@pytest.fixture
def notes(company_a, company_b):
    with tenant_context(company_a.id):
        Note.objects.create(title="a1")
        Note.objects.create(title="a2")
    with tenant_context(company_b.id):
        Note.objects.create(title="b1")


def titles() -> list[str]:
    return [row[0] for row in query("SELECT title FROM testapp_note ORDER BY title")]


def test_tests_run_as_the_unprivileged_app_role():
    [(user, superuser, bypass_rls)] = query(
        "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    )
    assert user == settings.DATABASE_APP_ROLE
    assert superuser is False
    assert bypass_rls is False


def test_no_active_company_sees_no_rows(notes):
    assert titles() == []
    assert query("SELECT count(*) FROM tenancy_company") == [(0,)]


def test_reads_only_its_own_rows(notes, company_a, company_b):
    with tenant_context(company_a.id):
        assert titles() == ["a1", "a2"]
        assert query("SELECT id FROM tenancy_company") == [(company_a.id,)]
    with tenant_context(company_b.id):
        assert titles() == ["b1"]


def test_cannot_update_another_companys_rows(notes, company_a, company_b):
    with tenant_context(company_a.id):
        updated = execute(
            "UPDATE testapp_note SET title = 'hacked' WHERE company_id = %s", (company_b.id,)
        )
    assert updated == 0
    with tenant_context(company_b.id):
        assert titles() == ["b1"]


def test_cannot_delete_another_companys_rows(notes, company_a, company_b):
    with tenant_context(company_a.id):
        deleted = execute("DELETE FROM testapp_note WHERE company_id = %s", (company_b.id,))
    assert deleted == 0
    with tenant_context(company_b.id):
        assert titles() == ["b1"]


def test_cannot_insert_rows_for_another_company(company_a, company_b):
    with pytest.raises(DatabaseError, match="row-level security"), tenant_context(company_a.id):
        execute(
            "INSERT INTO testapp_note (title, company_id) VALUES ('planted', %s)", (company_b.id,)
        )


def test_cannot_move_a_row_to_another_company(notes, company_a, company_b):
    with pytest.raises(DatabaseError, match="row-level security"), tenant_context(company_a.id):
        execute("UPDATE testapp_note SET company_id = %s", (company_b.id,))


def test_cannot_insert_without_an_active_company(company_a):
    with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
        execute(
            "INSERT INTO testapp_note (title, company_id) VALUES ('orphan', %s)", (company_a.id,)
        )


def test_cannot_switch_row_security_off(notes, company_a):
    # With row_security off, PostgreSQL refuses the query instead of filtering it.
    with tenant_context(company_a.id):
        execute("SET LOCAL row_security = off")
        with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
            query("SELECT title FROM testapp_note")


def test_cannot_drop_the_policies(company_a):
    with pytest.raises(DatabaseError, match="must be owner"), transaction.atomic():
        execute("ALTER TABLE testapp_note DISABLE ROW LEVEL SECURITY")


def app_role_session() -> psycopg.Connection:
    """A separate session that logs in as the app role, exactly like the API does.

    The test connection logs in as the owner and switches role, and SET ROLE is
    checked against the login user, so escalation can only be tested this way.
    """
    password = env("POSTGRES_APP_PASSWORD", "")
    if not password:
        pytest.skip("POSTGRES_APP_PASSWORD is not available (run through docker compose).")
    db = connection.settings_dict
    return psycopg.connect(
        host=db["HOST"],
        port=db["PORT"],
        dbname=db["NAME"],
        user=settings.DATABASE_APP_ROLE,
        password=password,
        autocommit=True,
    )


def test_app_role_cannot_become_the_owner_role():
    owner = sql.Identifier(connection.settings_dict["USER"])
    with app_role_session() as session:
        assert session.execute("SELECT current_user").fetchone() == (settings.DATABASE_APP_ROLE,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            session.execute(sql.SQL("SET ROLE {}").format(owner))


def test_other_companies_are_invisible_even_unfiltered(company_a, company_b):
    with tenant_context(company_a.id):
        assert list(Company.all_objects.values_list("id", flat=True)) == [company_a.id]
        assert list(Note.all_objects.all()) == []


def test_all_company_ids_lists_every_company_without_their_data(company_a, company_b):
    assert {company_a.id, company_b.id} <= set(all_company_ids())
