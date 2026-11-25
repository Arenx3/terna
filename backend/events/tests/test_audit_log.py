"""Events from real actions, and the admin audit log API."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Membership
from events import dispatch
from events.models import AuditEvent
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

AUDIT = "/api/audit/"


def recorded(company_id) -> list[AuditEvent]:
    dispatch.dispatch_all()
    with tenant_context(company_id):
        return list(AuditEvent.objects.order_by("id"))


def membership_id(team, role: str) -> int:
    with tenant_context(team.company.id):
        return Membership.objects.get(user=team.people[role]).id


def test_job_lifecycle_is_recorded_with_who_did_it(acme):
    recruiter = acme.client("recruiter")
    job = recruiter.post(
        "/api/jobs/",
        {"title": "SRE", "requirements": [{"text": "Linux", "kind": "must"}]},
        format="json",
    ).json()
    recruiter.post(f"/api/jobs/{job['id']}/publish/")
    recruiter.post(f"/api/jobs/{job['id']}/publish/")  # already open: nothing new
    recruiter.post(f"/api/jobs/{job['id']}/close/")
    recruiter.post(f"/api/jobs/{job['id']}/publish/")

    rows = recorded(acme.company.id)
    assert [r.type for r in rows] == [
        "job.created",
        "job.published",
        "job.closed",
        "job.reopened",
    ]
    assert {r.actor_name for r in rows} == {acme.people["recruiter"].full_name}
    assert {r.entity_id for r in rows} == {job["id"]}


def test_deleting_a_draft_is_recorded(acme):
    admin = acme.client("admin")
    job = admin.post("/api/jobs/", {"title": "Temp"}, format="json").json()
    admin.delete(f"/api/jobs/{job['id']}/")

    assert [r.type for r in recorded(acme.company.id)] == ["job.created", "job.deleted"]


def test_team_changes_are_recorded(acme):
    admin = acme.client("admin")
    interviewer = acme.people["interviewer"]
    admin.patch(
        f"/api/team/members/{membership_id(acme, 'interviewer')}/",
        {"role": "recruiter"},
        format="json",
    )
    admin.delete(f"/api/team/members/{membership_id(acme, 'hiring_manager')}/")
    invitation = admin.post(
        "/api/team/invitations/", {"email": "new@acme.test", "role": "interviewer"}, format="json"
    ).json()
    admin.delete(f"/api/team/invitations/{invitation['id']}/")

    rows = recorded(acme.company.id)
    assert [(r.type, r.entity_label) for r in rows] == [
        ("member.role_changed", interviewer.full_name),
        ("member.removed", acme.people["hiring_manager"].full_name),
        ("invitation.sent", "new@acme.test"),
        ("invitation.revoked", "new@acme.test"),
    ]
    assert rows[0].payload == {"from": "interviewer", "to": "recruiter"}
    assert rows[1].payload == {"role": "hiring_manager"}


def test_joining_through_an_invitation_is_recorded_as_the_newcomer(acme, monkeypatch):
    monkeypatch.setattr("accounts.invitations.secrets.token_urlsafe", lambda _: "known-token")
    acme.client("admin").post(
        "/api/team/invitations/", {"email": "lucia@acme.test", "role": "recruiter"}, format="json"
    )

    response = APIClient().post(
        "/api/invitations/known-token/accept/",
        {"full_name": "Lucía Torres", "password": "a-long-and-unusual-passphrase"},
        format="json",
    )
    assert response.status_code == 200, response.json()

    joined = recorded(acme.company.id)[-1]
    assert (joined.type, joined.actor_name, joined.payload) == (
        "member.joined",
        "Lucía Torres",
        {"role": "recruiter"},
    )


def test_only_admins_read_the_audit_log(acme):
    for role in ("recruiter", "hiring_manager", "interviewer"):
        response = acme.client(role).get(AUDIT)
        assert response.status_code == 403, role


def test_each_company_reads_only_its_own_log(acme, globex):
    acme.client("admin").post("/api/jobs/", {"title": "Acme only"}, format="json")
    dispatch.dispatch_all()

    assert globex.client("admin").get(AUDIT).json()["results"] == []
    [row] = acme.client("admin").get(AUDIT).json()["results"]
    assert row["entity_label"] == "Acme only"


def test_filters_and_pages(acme):
    admin, recruiter = acme.client("admin"), acme.client("recruiter")
    admin.post("/api/jobs/", {"title": "One"}, format="json")
    recruiter.post("/api/jobs/", {"title": "Two"}, format="json")
    admin.patch(
        f"/api/team/members/{membership_id(acme, 'interviewer')}/",
        {"role": "recruiter"},
        format="json",
    )
    dispatch.dispatch_all()

    def labels(**params) -> list[str]:
        return [row["entity_label"] for row in admin.get(AUDIT, params).json()["results"]]

    assert labels() == [acme.people["interviewer"].full_name, "Two", "One"]  # newest first
    assert labels(type="job") == ["Two", "One"]
    assert labels(type="member.role_changed") == [acme.people["interviewer"].full_name]
    assert labels(actor=str(acme.people["recruiter"].id)) == ["Two"]
    assert labels(since=(timezone.now() + timedelta(minutes=1)).isoformat()) == []

    first = admin.get(AUDIT, {"limit": 2}).json()
    assert len(first["results"]) == 2
    rest = admin.get(AUDIT, {"limit": 2, "before": first["next_before"]}).json()
    assert [row["entity_label"] for row in rest["results"]] == ["One"]
    assert rest["next_before"] is None


def test_unknown_types_are_rejected(acme):
    response = acme.client("admin").get(AUDIT, {"type": "payroll"})

    assert response.status_code == 400
