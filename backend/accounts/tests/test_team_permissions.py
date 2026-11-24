"""What each role can do with the team. Only admins invite, change roles or remove members."""

import pytest

from accounts.models import Invitation, Membership
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

ROLES = [role for role, _ in Membership.Role.choices]
MEMBERS = "/api/team/members/"
INVITATIONS = "/api/team/invitations/"


@pytest.fixture
def team(member, add_member):
    """An admin, plus one person per role, plus a pending invitation."""
    admin = member()
    company = admin.company
    people = {"admin": admin}
    for role in ROLES:
        if role != "admin":
            people[role] = add_member(company, f"{role}@acme.test", role)
    with tenant_context(company.id):
        target = Membership.objects.get(user=people["interviewer"])
        invitation = Invitation.objects.create(
            company=company,
            email="pending@acme.test",
            role="recruiter",
            token_hash="x" * 64,
            invited_by=admin,
            expires_at="2999-01-01T00:00:00Z",
        )
    return company, people, target, invitation


@pytest.mark.parametrize("role", ROLES)
def test_every_member_can_see_the_team(team, as_user, role):
    company, people, _, _ = team

    response = as_user(people[role], company).get(MEMBERS)

    assert response.status_code == 200
    assert len(response.json()) == len(ROLES)


@pytest.mark.parametrize("role", ROLES)
def test_only_admins_manage_the_team(team, as_user, role, django_capture_on_commit_callbacks):
    company, people, target, invitation = team
    client = as_user(people[role], company)
    allowed = role == "admin"

    with django_capture_on_commit_callbacks(execute=True):
        responses = {
            "list invitations": client.get(INVITATIONS),
            "invite": client.post(
                INVITATIONS, {"email": "new@acme.test", "role": "interviewer"}, format="json"
            ),
            "change role": client.patch(
                f"{MEMBERS}{target.id}/", {"role": "recruiter"}, format="json"
            ),
            "revoke invitation": client.delete(f"{INVITATIONS}{invitation.id}/"),
            "remove member": client.delete(f"{MEMBERS}{target.id}/"),
        }

    for action, response in responses.items():
        if allowed:
            assert response.status_code in (200, 201, 204), action
        else:
            assert response.status_code == 403, action
            assert response.json()["code"] == "admin_required", action
