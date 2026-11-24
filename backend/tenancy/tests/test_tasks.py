import pytest
from django.db import connection

from tenancy import db
from tenancy.context import current_company_id, tenant_context
from testapp.models import Note
from testapp.tasks import note_titles, note_titles_unscoped

pytestmark = pytest.mark.django_db


@pytest.fixture
def notes(company_a, company_b):
    with tenant_context(company_a.id):
        Note.objects.create(title="a1")
    with tenant_context(company_b.id):
        Note.objects.create(title="b1")


def test_task_sees_only_its_company(notes, company_a, company_b):
    assert note_titles.apply(args=[company_a.id]).get() == ["a1"]
    assert note_titles.apply(args=[str(company_b.id)]).get() == ["b1"]


def test_row_level_security_alone_isolates_tasks(notes, company_a):
    assert note_titles_unscoped.apply(args=[company_a.id]).get() == ["a1"]


def test_task_requires_a_company():
    with pytest.raises(TypeError):
        note_titles.apply(args=[]).get()


def test_task_leaves_no_company_behind(notes, company_a):
    note_titles.apply(args=[company_a.id]).get()

    assert current_company_id() is None
    assert db.get_company(connection) == ""
