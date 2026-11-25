import pytest

pytestmark = pytest.mark.django_db

JOBS = "/api/jobs/"


def job_url(job_id, action: str = "") -> str:
    return f"{JOBS}{job_id}/{action + '/' if action else ''}"


def create(client, payload) -> dict:
    response = client.post(JOBS, payload, format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def test_creating_a_job_copies_the_default_pipeline(acme, job_payload):
    job = create(acme.client("recruiter"), job_payload())

    assert job["status"] == "draft"
    assert [r["kind"] for r in job["requirements"]] == ["must", "must", "nice"]
    assert [s["kind"] for s in job["stages"]] == [
        "applied",
        "screening",
        "interview",
        "offer",
        "hired",
        "rejected",
    ]


def test_list_counts_requirements_and_filters_by_status(acme, job_payload):
    client = acme.client("admin")
    draft = create(client, job_payload(title="Data Analyst"))
    opened = create(client, job_payload())
    assert client.post(job_url(opened["id"], "publish")).status_code == 200

    rows = client.get(JOBS).json()
    assert {row["title"] for row in rows} == {"Data Analyst", "Senior Backend Engineer"}
    assert rows[0]["must_haves"] == 2
    assert rows[0]["nice_to_haves"] == 1

    open_only = client.get(JOBS, {"status": "open"}).json()
    assert [row["id"] for row in open_only] == [opened["id"]]
    assert draft["id"] not in [row["id"] for row in open_only]


def test_a_company_never_sees_another_companys_jobs(acme, globex, job_payload):
    job = create(acme.client("admin"), job_payload())
    other = globex.client("admin")

    assert other.get(JOBS).json() == []
    assert other.get(job_url(job["id"])).status_code == 404
    assert other.patch(job_url(job["id"]), {"title": "Mine"}, format="json").status_code == 404
    assert other.post(job_url(job["id"], "close")).status_code == 404


def test_hiring_managers_see_only_the_jobs_they_own(acme, job_payload):
    recruiter = acme.client("recruiter")
    manager = acme.people["hiring_manager"]
    owned = create(recruiter, job_payload(hiring_manager_id=str(manager.id)))
    create(recruiter, job_payload(title="Someone else's"))

    client = acme.client("hiring_manager")
    assert [row["id"] for row in client.get(JOBS).json()] == [owned["id"]]
    assert client.get(job_url(owned["id"])).json()["hiring_manager"]["id"] == str(manager.id)
    # Owning a job is reviewing it, not editing it.
    assert client.patch(job_url(owned["id"]), {"title": "x"}, format="json").status_code == 403
    assert client.post(JOBS, job_payload(), format="json").status_code == 403


def test_interviewers_do_not_see_jobs(acme):
    response = acme.client("interviewer").get(JOBS)

    assert response.status_code == 403
    assert response.json()["code"] == "role_forbidden"


def test_the_owner_must_be_a_teammate_who_can_own_jobs(acme, globex, job_payload):
    client = acme.client("admin")
    outsider = globex.people["hiring_manager"]
    interviewer = acme.people["interviewer"]

    for person in (outsider, interviewer):
        response = client.post(JOBS, job_payload(hiring_manager_id=str(person.id)), format="json")
        assert response.status_code == 400
        assert "hiring_manager_id" in response.json()


def test_publishing_needs_a_must_have(acme, job_payload):
    client = acme.client("recruiter")
    job = create(client, job_payload(requirements=[{"text": "Spanish", "kind": "nice"}]))

    blocked = client.post(job_url(job["id"], "publish"))
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "publish_needs_must_have"

    requirements = [*job["requirements"], {"text": "SQL", "kind": "must"}]
    client.patch(job_url(job["id"]), {"requirements": requirements}, format="json")
    published = client.post(job_url(job["id"], "publish")).json()
    assert published["status"] == "open"
    assert published["published_at"] is not None


def test_an_open_job_keeps_at_least_one_must_have(acme, job_payload):
    client = acme.client("recruiter")
    job = create(client, job_payload())
    client.post(job_url(job["id"], "publish"))

    nice_only = [{"text": "Advanced English", "kind": "nice"}]
    response = client.patch(job_url(job["id"]), {"requirements": nice_only}, format="json")

    assert response.status_code == 409
    assert len(client.get(job_url(job["id"])).json()["requirements"]) == 3  # rolled back


def test_editing_keeps_ids_and_follows_the_new_order(acme, job_payload):
    client = acme.client("recruiter")
    job = create(client, job_payload())
    first, second, third = job["requirements"]

    edited = [
        {**third, "kind": "must"},
        {"id": first["id"], "text": "6+ years building APIs in Python", "kind": "must"},
        {"text": "Go", "kind": "nice"},
    ]
    updated = client.patch(job_url(job["id"]), {"requirements": edited}, format="json").json()

    ids = [r["id"] for r in updated["requirements"]]
    assert ids[:2] == [third["id"], first["id"]]
    assert second["id"] not in ids
    assert updated["requirements"][1]["text"] == "6+ years building APIs in Python"
    assert updated["requirements"][0]["kind"] == "must"


def test_ids_from_another_job_are_rejected(acme, job_payload):
    client = acme.client("recruiter")
    one = create(client, job_payload())
    two = create(client, job_payload(title="Other"))

    stolen = [{"id": one["requirements"][0]["id"], "text": "x", "kind": "must"}]
    response = client.patch(job_url(two["id"]), {"requirements": stolen}, format="json")

    assert response.status_code == 400
    assert "requirements" in response.json()


@pytest.mark.parametrize(
    "kinds",
    [
        ["screening", "applied", "hired", "rejected"],  # applied must come first
        ["applied", "interview", "rejected", "hired"],  # hired, then rejected, at the end
        ["applied", "hired", "hired", "rejected"],  # hired only at the end
        ["applied", "rejected"],
    ],
)
def test_pipelines_start_at_applied_and_end_at_hired_and_rejected(acme, job_payload, kinds):
    stages = [{"kind": kind} for kind in kinds]
    response = acme.client("recruiter").post(JOBS, job_payload(stages=stages), format="json")

    assert response.status_code == 400
    assert "stages" in response.json()


def test_custom_stage_names_are_kept(acme, job_payload):
    stages = [
        {"kind": "applied"},
        {"kind": "screening", "name": "Technical test"},
        {"kind": "interview", "name": "Panel"},
        {"kind": "hired"},
        {"kind": "rejected"},
    ]
    job = create(acme.client("recruiter"), job_payload(stages=stages))

    assert [s["name"] for s in job["stages"]] == ["", "Technical test", "Panel", "", ""]


def test_requirements_must_be_distinct(acme, job_payload):
    duplicated = [
        {"text": "Kubernetes in production", "kind": "must"},
        {"text": "kubernetes  in production", "kind": "nice"},
    ]
    response = acme.client("recruiter").post(
        JOBS, job_payload(requirements=duplicated), format="json"
    )

    assert response.status_code == 400


def test_salary_range_must_make_sense(acme, job_payload):
    client = acme.client("recruiter")
    response = client.post(JOBS, job_payload(salary_min=90000, salary_max=60000), format="json")

    assert response.status_code == 400
    assert "salary_max" in response.json()


def test_only_drafts_can_be_deleted(acme, job_payload):
    client = acme.client("admin")
    draft = create(client, job_payload())
    published = create(client, job_payload(title="Published"))
    client.post(job_url(published["id"], "publish"))

    assert client.delete(job_url(draft["id"])).status_code == 204
    refused = client.delete(job_url(published["id"]))
    assert refused.status_code == 409
    assert refused.json()["code"] == "job_not_draft"


def test_closing_and_reopening(acme, job_payload):
    client = acme.client("recruiter")
    job = create(client, job_payload())
    first = client.post(job_url(job["id"], "publish")).json()["published_at"]

    closed = client.post(job_url(job["id"], "close")).json()
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None

    reopened = client.post(job_url(job["id"], "publish")).json()
    assert reopened["status"] == "open"
    assert reopened["closed_at"] is None
    assert reopened["published_at"] == first


def test_status_only_changes_through_its_actions(acme, job_payload):
    client = acme.client("recruiter")
    job = create(client, job_payload())

    client.patch(job_url(job["id"]), {"status": "open"}, format="json")

    assert client.get(job_url(job["id"])).json()["status"] == "draft"
