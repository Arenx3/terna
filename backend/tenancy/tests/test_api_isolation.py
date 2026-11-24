"""Isolation through the API: company A can never read, change or delete company B's data."""

import pytest

from tenancy.context import tenant_context
from testapp.models import Note

pytestmark = pytest.mark.django_db

URL = "/api/test/notes/"


@pytest.fixture
def note_a(company_a):
    with tenant_context(company_a.id):
        return Note.objects.create(title="a1")


@pytest.fixture
def note_b(company_b):
    with tenant_context(company_b.id):
        return Note.objects.create(title="b1")


def titles_of(company) -> list[str]:
    with tenant_context(company.id):
        return sorted(Note.objects.values_list("title", flat=True))


def test_lists_only_its_own_company(api_as, company_a, note_a, note_b):
    response = api_as(company_a).get(URL)

    assert response.status_code == 200
    assert [note["title"] for note in response.json()] == ["a1"]


def test_cannot_read_another_companys_record(api_as, company_a, note_b):
    response = api_as(company_a).get(f"{URL}{note_b.id}/")

    assert response.status_code == 404


def test_cannot_edit_another_companys_record(api_as, company_a, company_b, note_b):
    response = api_as(company_a).patch(f"{URL}{note_b.id}/", {"title": "hacked"}, format="json")

    assert response.status_code == 404
    assert titles_of(company_b) == ["b1"]


def test_cannot_delete_another_companys_record(api_as, company_a, company_b, note_b):
    response = api_as(company_a).delete(f"{URL}{note_b.id}/")

    assert response.status_code == 404
    assert titles_of(company_b) == ["b1"]


def test_creates_in_its_own_company_whatever_the_payload_says(api_as, company_a, company_b):
    response = api_as(company_a).post(
        URL, {"title": "new", "company": str(company_b.id)}, format="json"
    )

    assert response.status_code == 201
    assert titles_of(company_a) == ["new"]
    assert titles_of(company_b) == []


def test_edits_and_deletes_its_own_records(api_as, company_a, note_a):
    client = api_as(company_a)

    assert client.patch(f"{URL}{note_a.id}/", {"title": "edited"}, format="json").status_code == 200
    assert titles_of(company_a) == ["edited"]
    assert client.delete(f"{URL}{note_a.id}/").status_code == 204
    assert titles_of(company_a) == []


@pytest.mark.parametrize("claim", [None, "", "not-a-uuid"])
def test_requires_a_valid_active_company(api_as, note_a, claim):
    response = api_as(claim=claim).get(URL)

    assert response.status_code == 403
    assert "a1" not in response.content.decode()


def test_requires_authentication(client, note_a):
    response = client.get(URL)

    assert response.status_code in (401, 403)


def test_switching_company_switches_all_visible_data(api_as, company_a, company_b, note_a, note_b):
    assert [n["title"] for n in api_as(company_a).get(URL).json()] == ["a1"]
    assert [n["title"] for n in api_as(company_b).get(URL).json()] == ["b1"]
