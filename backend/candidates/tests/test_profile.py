import pytest

from candidates.tests.conftest import PDF, Visitor
from events import dispatch
from events.models import OutboxEvent
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def application(acme, open_job, visitor, instant, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):  # the confirmation email too
        assert visitor.apply(visitor.upload(PDF)).status_code == 202
    return acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()[0]


def url(application, part: str = "") -> str:
    return f"/api/applications/{application['id']}/{part + '/' if part else ''}"


def assign(team, application, *roles):
    users = [str(team.people[role].id) for role in roles]
    return team.client("admin").put(
        url(application, "interviewers"), {"users": users}, format="json"
    )


def test_the_profile_brings_the_candidate_together(acme, job_payload, application, instant):
    other_job = (
        acme.client("recruiter")
        .post("/api/jobs/", job_payload(title="Platform Engineer"), format="json")
        .json()
    )
    acme.client("recruiter").post(f"/api/jobs/{other_job['id']}/publish/")
    elsewhere = Visitor(acme, other_job)
    elsewhere.apply(elsewhere.upload(PDF))

    profile = acme.client("recruiter").get(url(application)).json()

    assert profile["candidate"]["full_name"] == "Lucía Torres"
    assert profile["candidate"]["email"] == "lucia@example.com"
    assert profile["resume"]["format"] == "pdf"
    assert [other["job"]["title"] for other in profile["other_applications"]] == [
        "Platform Engineer"
    ]
    assert profile["can_manage"] is True
    team = {person["full_name"] for person in profile["team"]}
    assert acme.people["recruiter"].full_name in team
    assert acme.people["interviewer"].full_name not in team  # not assigned yet


def test_opening_a_profile_is_recorded_once_per_half_hour(acme, application):
    client = acme.client("recruiter")
    client.get(url(application))
    client.get(url(application))

    with tenant_context(acme.company.id):
        views = OutboxEvent.objects.filter(type="candidate.viewed")
        assert views.count() == 1
        assert views.get().actor_name == acme.people["recruiter"].full_name


def test_interviewers_only_see_the_candidates_they_are_assigned(acme, application):
    interviewer = acme.client("interviewer")
    assert interviewer.get(url(application)).status_code == 404

    assert assign(acme, application, "interviewer").status_code == 200

    assert interviewer.get(url(application)).status_code == 200
    assert interviewer.get(url(application, "resume")).status_code == 200
    # They can see and discuss the candidate, but not reassign anyone.
    response = interviewer.put(url(application, "interviewers"), {"users": []}, format="json")
    assert response.status_code == 403


def test_only_interviewers_can_be_assigned(acme, application):
    response = assign(acme, application, "recruiter")

    assert response.status_code == 400


def test_hiring_managers_and_other_companies(acme, globex, application):
    assert acme.client("hiring_manager").get(url(application)).status_code == 404
    assert globex.client("admin").get(url(application)).status_code == 404
    assert globex.client("admin").get(url(application, "comments")).status_code == 404


def test_mentions_notify_only_people_who_can_open_the_candidate(acme, application):
    admin = acme.client("admin")
    recruiter, interviewer = acme.people["recruiter"], acme.people["interviewer"]
    response = admin.post(
        url(application, "comments"),
        {
            "body": "@Recruiter Acme strong on Kubernetes. @Interviewer Acme?",
            "mentions": [str(recruiter.id), str(interviewer.id), str(acme.people["admin"].id)],
        },
        format="json",
    )
    assert response.status_code == 201
    # The interviewer isn't assigned, so the mention is dropped rather than leaking.
    assert response.json()["mentions"] == [str(recruiter.id), str(acme.people["admin"].id)]
    dispatch.dispatch_all()

    inbox = acme.client("recruiter").get("/api/notifications/").json()
    assert inbox["unread"] == 1
    [item] = inbox["items"]
    assert (item["kind"], item["candidate"], item["actor_name"]) == (
        "mention",
        "Lucía Torres",
        acme.people["admin"].full_name,
    )
    # Mentioning yourself notifies no one.
    assert acme.client("admin").get("/api/notifications/").json()["unread"] == 0

    acme.client("recruiter").post("/api/notifications/read/", {}, format="json")
    assert acme.client("recruiter").get("/api/notifications/").json()["unread"] == 0


def test_assigned_interviewers_are_notified_once(acme, application):
    assign(acme, application, "interviewer")
    dispatch.dispatch_all()
    dispatch.dispatch_all()

    inbox = acme.client("interviewer").get("/api/notifications/").json()

    assert [item["kind"] for item in inbox["items"]] == ["assigned"]


def test_the_timeline_tells_what_happened(acme, application):
    job = acme.client("recruiter").get(f"/api/applications/{application['id']}/").json()["job"]
    stages = acme.client("recruiter").get(f"/api/jobs/{job['id']}/").json()["stages"]
    acme.client("recruiter").post(
        url(application, "move"),
        {"stage": stages[1]["id"], "from_stage": application["stage"]["id"]},
        format="json",
    )
    acme.client("recruiter").post(url(application, "comments"), {"body": "Call her"}, format="json")
    dispatch.dispatch_all()

    events = acme.client("recruiter").get(url(application, "timeline")).json()

    # Newest first; comments live in their own thread, profile views in the audit log only.
    assert [event["type"] for event in events] == [
        "application.stage_changed",
        "email.sent",
        "application.submitted",
    ]
    assert events[0]["payload"]["to"]["kind"] == "screening"


def test_the_resume_can_open_in_the_browser(acme, application):
    link = acme.client("recruiter").get(url(application, "resume"), {"inline": "1"}).json()["url"]

    assert "response-content-disposition=inline" in link
