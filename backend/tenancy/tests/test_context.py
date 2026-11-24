import uuid

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from tenancy import db
from tenancy.context import NoActiveCompanyError, activate, current_company_id, tenant_context
from testapp.models import Note


def db_company() -> str:
    return db.get_company(connection)


@pytest.mark.django_db
def test_nested_contexts_restore_the_outer_company(company_a, company_b):
    with tenant_context(company_a.id):
        with tenant_context(company_b.id):
            assert current_company_id() == company_b.id
            assert db_company() == str(company_b.id)
        assert current_company_id() == company_a.id
        assert db_company() == str(company_a.id)
    assert current_company_id() is None
    assert db_company() == ""


@pytest.mark.django_db
def test_an_error_inside_restores_the_outer_company(company_a, company_b):
    with tenant_context(company_a.id):
        with pytest.raises(ZeroDivisionError), tenant_context(company_b.id):
            1 / 0  # noqa: B018
        assert current_company_id() == company_a.id
        assert db_company() == str(company_a.id)


@pytest.mark.django_db
def test_saving_tenant_data_needs_an_active_company():
    with pytest.raises(NoActiveCompanyError):
        Note.objects.create(title="orphan")


@pytest.mark.django_db
def test_new_rows_take_the_active_company(company_a):
    with tenant_context(company_a.id):
        note = Note.objects.create(title="a1")
    assert note.company_id == company_a.id


def test_rejects_an_invalid_company_id():
    with pytest.raises(ValueError, match="badly formed"):
        tenant_context("not-a-uuid").__enter__()


@pytest.mark.django_db(transaction=True)
def test_activate_needs_a_transaction():
    # Outside a transaction SET LOCAL would be gone before the next query.
    with pytest.raises(ImproperlyConfigured):
        activate(uuid.uuid4())
