"""Login, refresh, logout and the company carried by the access token."""

import pytest
from django.conf import settings

from accounts.models import Membership, User
from accounts.tests.conftest import PASSWORD
from tenancy.context import tenant_context
from testapp.models import Note

pytestmark = pytest.mark.django_db

LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
LOGOUT = "/api/auth/logout/"
ME = "/api/auth/me/"
COOKIE = settings.AUTH_REFRESH_COOKIE


def login(post, email="ana@acme.test", password=PASSWORD):
    return post(LOGIN, {"email": email, "password": password})


def test_login_returns_access_token_user_and_company(post, member):
    user = member()

    response = login(post, email="  ANA@acme.test ")

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": str(user.id),
        "email": "ana@acme.test",
        "full_name": "Ana Pérez",
        "language": "en",
    }
    assert body["company"] == {"id": str(user.company.id), "name": "Acme", "role": "admin"}
    assert body["companies"] == [body["company"]]
    assert body["access"]


def test_refresh_token_only_travels_in_a_locked_down_cookie(post, member):
    member()

    response = login(post)

    cookie = response.cookies[COOKIE]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert cookie["path"] == "/api/auth/"
    assert cookie.value not in response.content.decode()
    assert "refresh" not in response.json()


def test_access_token_reaches_only_its_company_data(post, api, member):
    ana = member("ana@acme.test", "Acme")
    bob = member("bob@globex.test", "Globex")
    with tenant_context(ana.company.id):
        Note.objects.create(title="acme note")
    with tenant_context(bob.company.id):
        Note.objects.create(title="globex note")

    access = login(post).json()["access"]
    response = api.get("/api/test/notes/", HTTP_AUTHORIZATION=f"Bearer {access}")

    assert response.status_code == 200
    assert [note["title"] for note in response.json()] == ["acme note"]


@pytest.mark.parametrize(
    ("email", "password"),
    [("ana@acme.test", "wrong-password-123"), ("nobody@acme.test", PASSWORD)],
)
def test_bad_credentials_look_the_same_for_known_and_unknown_addresses(
    post, member, email, password
):
    member()

    response = login(post, email, password)

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert COOKIE not in response.cookies


def test_unverified_address_cannot_log_in(post, member):
    user = member()
    User.objects.filter(id=user.id).update(email_verified_at=None)

    response = login(post)

    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_account_without_company_cannot_log_in(post, member):
    user = member()
    with tenant_context(user.company.id):
        Membership.objects.all().delete()

    response = login(post)

    assert response.status_code == 403
    assert response.json()["code"] == "no_company"


def test_login_is_rate_limited_per_address(post, member):
    member()

    statuses = [login(post, password=f"wrong-{i}-password").status_code for i in range(6)]

    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


def test_refresh_rotates_the_cookie_and_rejects_reuse(post, api, member):
    member()
    login(post)
    first = api.cookies[COOKIE].value

    refreshed = post(REFRESH)
    assert refreshed.status_code == 200
    assert refreshed.json()["access"]
    second = api.cookies[COOKIE].value
    assert second != first

    api.cookies[COOKIE] = first  # replaying the old, already used token
    replay = post(REFRESH)
    assert replay.status_code == 401
    assert replay.json()["code"] == "session_expired"


def test_refresh_without_cookie_means_no_session(post):
    response = post(REFRESH)

    assert response.status_code == 204
    assert not response.content


def test_refresh_with_a_forged_cookie_is_rejected(post, api):
    api.cookies[COOKIE] = "not-a-token"

    response = post(REFRESH)

    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"


def test_refresh_stops_once_the_membership_is_removed(post, member):
    user = member()
    login(post)
    with tenant_context(user.company.id):
        Membership.objects.all().delete()

    response = post(REFRESH)

    assert response.status_code == 401


def test_logout_ends_the_session(post, api, member):
    member()
    login(post)
    cookie = api.cookies[COOKIE].value

    response = post(LOGOUT)

    assert response.status_code == 204
    assert response.cookies[COOKIE].value == ""
    api.cookies[COOKIE] = cookie
    assert post(REFRESH).status_code == 401


def test_me_describes_the_session(post, api, member):
    user = member()
    access = login(post).json()["access"]

    response = api.get(ME, HTTP_AUTHORIZATION=f"Bearer {access}")

    assert response.status_code == 200
    assert response.json()["company"]["id"] == str(user.company.id)


def test_me_requires_a_valid_access_token(api):
    response = api.get(ME, HTTP_AUTHORIZATION="Bearer not-a-token")

    assert response.status_code == 401
