import pytest

pytestmark = pytest.mark.django_db

TEMPLATE = "/api/jobs/pipeline-template/"
CUSTOM = [
    {"kind": "applied"},
    {"kind": "screening", "name": "Phone screen"},
    {"kind": "interview", "name": "Technical interview"},
    {"kind": "interview", "name": "Culture fit"},
    {"kind": "hired"},
    {"kind": "rejected"},
]


def test_companies_start_with_terna_pipeline(acme):
    stages = acme.client("recruiter").get(TEMPLATE).json()["stages"]

    assert [s["kind"] for s in stages] == [
        "applied",
        "screening",
        "interview",
        "offer",
        "hired",
        "rejected",
    ]


def test_admin_template_is_used_by_new_jobs(acme, job_payload):
    admin = acme.client("admin")
    assert admin.put(TEMPLATE, {"stages": CUSTOM}, format="json").status_code == 200

    job = admin.post("/api/jobs/", job_payload(), format="json").json()

    assert [s["name"] for s in job["stages"]][1:4] == [
        "Phone screen",
        "Technical interview",
        "Culture fit",
    ]


def test_only_admins_change_the_template(acme):
    response = acme.client("recruiter").put(TEMPLATE, {"stages": CUSTOM}, format="json")

    assert response.status_code == 403


def test_the_template_follows_the_pipeline_rules(acme):
    broken = [{"kind": "applied"}, {"kind": "interview"}]
    response = acme.client("admin").put(TEMPLATE, {"stages": broken}, format="json")

    assert response.status_code == 400


def test_each_company_has_its_own_template(acme, globex):
    acme.client("admin").put(TEMPLATE, {"stages": CUSTOM}, format="json")

    stages = globex.client("admin").get(TEMPLATE).json()["stages"]

    assert all(stage["name"] == "" for stage in stages)
