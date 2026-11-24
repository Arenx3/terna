"""Team changes: roles, removals, the last-admin rule and company switching."""

import pytest
from django.conf import settings

from accounts.models import Membership
from accounts.tests.conftest import PASSWORD
from tenancy.context import tenant_context
from testapp.models import Note

pytestmark = pytest.mark.django_db

MEMBERS = "/api/team/members/"


def membership_of(user, company) -> Membership:
    with tenant_context(company.id):
        return Membership.objects.get(user=user)


def test_admin_changes_a_role(member, add_member, as_user):
    admin = member()
    bob = add_member(admin.company, "bob@acme.test", "interviewer")

    response = as_user(admin, admin.company).patch(
        f"{MEMBERS}{membership_of(bob, admin.company).id}/", {"role": "recruiter"}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["role"] == "recruiter"
    assert membership_of(bob, admin.company).role == "recruiter"


def test_the_last_admin_cannot_be_demoted(member, as_user):
    admin = member()

    response = as_user(admin, admin.company).patch(
        f"{MEMBERS}{membership_of(admin, admin.company).id}/", {"role": "recruiter"}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"
    assert membership_of(admin, admin.company).role == "admin"


def test_the_last_admin_cannot_be_removed(member, as_user):
    admin = member()

    response = as_user(admin, admin.company).delete(
        f"{MEMBERS}{membership_of(admin, admin.company).id}/"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"


def test_an_admin_can_step_down_when_another_admin_remains(member, add_member, as_user):
    admin = member()
    add_member(admin.company, "second@acme.test", "admin")

    response = as_user(admin, admin.company).patch(
        f"{MEMBERS}{membership_of(admin, admin.company).id}/", {"role": "recruiter"}, format="json"
    )

    assert response.status_code == 200


def test_removed_members_lose_access_immediately(member, add_member, as_user, api):
    admin = member()
    bob = add_member(admin.company, "bob@acme.test", "recruiter")
    bob_client = as_user(bob, admin.company)
    bob_token = bob_client._credentials["HTTP_AUTHORIZATION"]
    assert bob_client.get(MEMBERS).status_code == 200

    as_user(admin, admin.company).delete(f"{MEMBERS}{membership_of(bob, admin.company).id}/")

    # Same, still unexpired access token: the membership is checked on every request.
    api.credentials(HTTP_AUTHORIZATION=bob_token)
    response = api.get(MEMBERS)
    assert response.status_code == 403
    assert response.json()["code"] == "not_member"


def test_admins_cannot_touch_another_companys_members(member, as_user):
    acme = member("ana@acme.test", "Acme")
    globex = member("gus@globex.test", "Globex")

    response = as_user(acme, acme.company).patch(
        f"{MEMBERS}{membership_of(globex, globex.company).id}/",
        {"role": "interviewer"},
        format="json",
    )

    assert response.status_code == 404
    assert membership_of(globex, globex.company).role == "admin"


def test_switching_company_switches_every_visible_record(post, api, member, add_member):
    ana = member("ana@acme.test", "Acme")
    globex = member("gus@globex.test", "Globex")
    add_member(globex.company, "ana@acme.test", "recruiter")
    with tenant_context(ana.company.id):
        Note.objects.create(title="acme note")
    with tenant_context(globex.company.id):
        Note.objects.create(title="globex note")

    session = post("/api/auth/login/", {"email": "ana@acme.test", "password": PASSWORD}).json()
    assert [c["name"] for c in session["companies"]] == ["Acme", "Globex"]
    old_cookie = api.cookies[settings.AUTH_REFRESH_COOKIE].value

    def notes(access):
        response = api.get("/api/test/notes/", HTTP_AUTHORIZATION=f"Bearer {access}")
        return [note["title"] for note in response.json()]

    assert notes(session["access"]) == ["acme note"]

    switched = post(
        "/api/auth/switch-company/",
        {"company_id": str(globex.company.id)},
        HTTP_AUTHORIZATION=f"Bearer {session['access']}",
    )

    assert switched.status_code == 200
    assert switched.json()["company"] == {
        "id": str(globex.company.id),
        "name": "Globex",
        "role": "recruiter",
    }
    assert notes(switched.json()["access"]) == ["globex note"]

    # The previous company's refresh cookie no longer works.
    api.cookies[settings.AUTH_REFRESH_COOKIE] = old_cookie
    assert post("/api/auth/refresh/").status_code == 401


def test_cannot_switch_to_a_company_you_do_not_belong_to(post, member):
    member("ana@acme.test", "Acme")
    globex = member("gus@globex.test", "Globex")
    access = post("/api/auth/login/", {"email": "ana@acme.test", "password": PASSWORD}).json()[
        "access"
    ]

    response = post(
        "/api/auth/switch-company/",
        {"company_id": str(globex.company.id)},
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "not_member"
