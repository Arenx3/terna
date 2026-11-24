"""Invitations from the admin's form to the invitee's first session."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Invitation, Membership, User
from accounts.sessions import issue_refresh_token
from accounts.tests.conftest import link_in
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

INVITATIONS = "/api/team/invitations/"


@pytest.fixture
def invite(member, django_capture_on_commit_callbacks, mailoutbox):
    """Invite an address as Acme's admin; returns the token from the email.

    The admin uses a client of their own, so `api` stays anonymous for the invitee.
    """
    admin = member()
    client = APIClient()
    access = issue_refresh_token(admin, admin.company.id).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def send(email: str = "new@acme.test", role: str = "recruiter", **extra) -> str:
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                INVITATIONS, {"email": email, "role": role}, format="json", **extra
            )
        assert response.status_code == 201, response.content
        assert "token" not in response.json()
        link = link_in(mailoutbox[-1], "/invitations/accept")
        return parse_qs(urlparse(link).query)["token"][0]

    send.admin = admin
    return send


def accept(api, token: str, data: dict | None = None, **extra):
    return api.post(f"/api/invitations/{token}/accept/", data or {}, format="json", **extra)


def test_invitation_email_names_the_company_role_and_inviter(invite, mailoutbox):
    invite(role="hiring_manager")

    [message] = mailoutbox
    assert message.to == ["new@acme.test"]
    assert message.subject == "Ana Pérez invited you to Acme on Terna"
    assert "as hiring manager" in message.body


def test_invitation_email_follows_the_inviters_language(invite, mailoutbox):
    invite(HTTP_ACCEPT_LANGUAGE="es")

    assert mailoutbox[0].subject == "Ana Pérez te invitó a Acme en Terna"
    assert "como reclutador" in mailoutbox[0].body


def test_preview_describes_the_invitation(invite, api):
    token = invite()

    response = api.get(f"/api/invitations/{token}/")

    assert response.status_code == 200
    assert response.json() == {
        "company_name": "Acme",
        "email": "new@acme.test",
        "role": "recruiter",
        "status": "valid",
        "account_exists": False,
    }


def test_new_person_accepts_with_a_new_account(invite, api):
    token = invite()

    response = accept(api, token, {"full_name": "Nina New", "password": "a-fresh-passphrase-5"})

    assert response.status_code == 200
    body = response.json()
    assert body["company"]["name"] == "Acme"
    assert body["company"]["role"] == "recruiter"
    assert settings.AUTH_REFRESH_COOKIE in response.cookies
    user = User.objects.get(email="new@acme.test")
    assert user.is_email_verified  # the emailed link proved the address
    with tenant_context(invite.admin.company.id):
        assert Membership.objects.get(user=user).role == "recruiter"


def test_invitation_works_once(invite, api):
    token = invite()
    accept(api, token, {"full_name": "Nina New", "password": "a-fresh-passphrase-5"})

    response = accept(api, token, {"full_name": "Someone", "password": "another-passphrase-6"})

    assert response.status_code == 400
    assert response.json()["code"] == "invitation_used"


def test_expired_invitation_is_rejected(invite, api):
    token = invite()
    with tenant_context(invite.admin.company.id):
        Invitation.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

    response = accept(api, token, {"full_name": "Nina", "password": "a-fresh-passphrase-5"})

    assert response.status_code == 400
    assert response.json()["code"] == "invitation_expired"
    assert api.get(f"/api/invitations/{token}/").json()["status"] == "expired"


def test_revoked_invitation_is_rejected(invite, api, as_user):
    token = invite()
    with tenant_context(invite.admin.company.id):
        invitation = Invitation.objects.get()
    as_user(invite.admin, invite.admin.company).delete(f"{INVITATIONS}{invitation.id}/")
    api.credentials()

    response = accept(api, token, {"full_name": "Nina", "password": "a-fresh-passphrase-5"})

    assert response.json()["code"] == "invitation_revoked"


def test_inviting_again_replaces_the_pending_link(invite, api):
    first = invite()
    second = invite()
    api.credentials()

    assert (
        accept(api, first, {"full_name": "N", "password": "a-fresh-passphrase-5"}).json()["code"]
        == "invitation_revoked"
    )
    assert (
        accept(api, second, {"full_name": "N", "password": "a-fresh-passphrase-5"}).status_code
        == 200
    )


def test_unknown_token_is_rejected(api):
    response = accept(api, "not-a-real-token")

    assert response.status_code == 400
    assert response.json()["code"] == "invitation_invalid"


def test_new_account_password_must_be_strong(invite, api):
    token = invite()

    response = accept(api, token, {"full_name": "Nina", "password": "password"})

    assert response.status_code == 400
    assert "password" in response.json()
    assert not User.objects.filter(email="new@acme.test").exists()


def test_existing_account_must_log_in_first(invite, member, api):
    member("bob@globex.test", "Globex")
    token = invite(email="bob@globex.test")
    api.credentials()

    response = accept(api, token)

    assert response.status_code == 400
    assert response.json()["code"] == "login_required"
    assert api.get(f"/api/invitations/{token}/").json()["account_exists"] is True


def test_existing_account_joins_while_signed_in(invite, member, as_user):
    bob = member("bob@globex.test", "Globex")
    token = invite(email="bob@globex.test", role="interviewer")
    client = as_user(bob, bob.company)

    response = accept(client, token)

    assert response.status_code == 200
    body = response.json()
    assert body["company"] == {
        "id": str(invite.admin.company.id),
        "name": "Acme",
        "role": "interviewer",
    }
    assert sorted(c["name"] for c in body["companies"]) == ["Acme", "Globex"]


def test_signed_in_as_someone_else_cannot_accept(invite, member, as_user):
    carl = member("carl@initech.test", "Initech")
    token = invite(email="new@acme.test")

    response = accept(as_user(carl, carl.company), token)

    assert response.status_code == 400
    assert response.json()["code"] == "invitation_email_mismatch"


def test_cannot_invite_an_existing_member(member, add_member, as_user):
    admin = member()
    add_member(admin.company, "bob@acme.test", "recruiter")

    response = as_user(admin, admin.company).post(
        INVITATIONS, {"email": "BOB@acme.test", "role": "admin"}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "already_member"


def test_admins_see_only_pending_invitations(invite, as_user, api):
    token = invite(email="accepted@acme.test")
    invite(email="pending@acme.test")
    api.credentials()
    accept(api, token, {"full_name": "A", "password": "a-fresh-passphrase-5"})

    response = as_user(invite.admin, invite.admin.company).get(INVITATIONS)

    assert [i["email"] for i in response.json()] == ["pending@acme.test"]
