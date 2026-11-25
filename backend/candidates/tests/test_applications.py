import pytest

from candidates.tests.conftest import PDF

pytestmark = pytest.mark.django_db


@pytest.fixture
def applied(visitor, instant):
    assert visitor.apply(visitor.upload(PDF)).status_code == 202


def applications_url(job) -> str:
    return f"/api/jobs/{job['id']}/applications/"


def test_the_team_sees_who_applied(acme, open_job, applied):
    [application] = acme.client("recruiter").get(applications_url(open_job)).json()

    assert application["candidate"]["full_name"] == "Lucía Torres"
    assert application["stage"]["kind"] == "applied"
    assert application["resume"] == {"filename": "cv.pdf", "format": "pdf", "size": len(PDF)}

    link = acme.client("recruiter").get(f"/api/applications/{application['id']}/resume/")
    assert link.status_code == 200
    assert "X-Amz-Signature" in link.json()["url"]


def test_the_jobs_list_counts_applicants(acme, open_job, applied):
    [row] = acme.client("admin").get("/api/jobs/").json()

    assert row["applicants"] == 1
    assert row["must_haves"] == 2  # still right with the extra join


def test_interviewers_and_other_companies_see_nothing(acme, globex, open_job, applied):
    assert acme.client("interviewer").get(applications_url(open_job)).status_code == 403
    assert globex.client("admin").get(applications_url(open_job)).status_code == 404


def test_hiring_managers_see_applicants_of_their_own_jobs_only(acme, open_job, applied):
    response = acme.client("hiring_manager").get(applications_url(open_job))

    assert response.status_code == 404  # not their job


def test_a_stage_with_candidates_cannot_be_removed(acme, open_job, applied):
    client = acme.client("recruiter")
    stages = client.get(f"/api/jobs/{open_job['id']}/").json()["stages"]
    without_applied_stage = [{"kind": "applied"}, *stages[1:]]

    response = client.patch(
        f"/api/jobs/{open_job['id']}/", {"stages": without_applied_stage}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "stage_in_use"
