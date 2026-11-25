import pytest
from rest_framework.test import APIClient

from tenancy.services import company_by_slug, create_company

pytestmark = pytest.mark.django_db


@pytest.fixture
def visitor():
    return APIClient()


def careers(slug: str) -> str:
    return f"/api/careers/{slug}/"


def published(team, payload, **overrides) -> dict:
    client = team.client("recruiter")
    job = client.post("/api/jobs/", payload(**overrides), format="json").json()
    assert client.post(f"/api/jobs/{job['id']}/publish/").status_code == 200
    return job


def test_companies_get_a_readable_unique_slug(db):
    first = create_company("Globex México")
    second = create_company("Globex México")

    assert first.slug == "globex-mexico"
    assert second.slug == "globex-mexico-2"
    assert company_by_slug("globex-mexico") == (first.id, "Globex México")
    assert company_by_slug("nobody") is None


def test_the_careers_page_lists_only_open_jobs(acme, job_payload, visitor):
    open_job = published(acme, job_payload, title="Open role")
    acme.client("recruiter").post("/api/jobs/", job_payload(title="Draft"), format="json")
    closed = published(acme, job_payload, title="Closed role")
    acme.client("recruiter").post(f"/api/jobs/{closed['id']}/close/")

    response = visitor.get(careers(acme.company.slug))

    assert response.status_code == 200
    assert response.json()["company"] == {"name": "Acme", "slug": acme.company.slug}
    assert [job["id"] for job in response.json()["jobs"]] == [open_job["id"]]
    assert response["Cache-Control"] == "public, max-age=60"


def test_drafts_and_closed_jobs_are_not_found(acme, job_payload, visitor):
    draft = acme.client("recruiter").post("/api/jobs/", job_payload(), format="json").json()
    closed = published(acme, job_payload, title="Closed")
    acme.client("recruiter").post(f"/api/jobs/{closed['id']}/close/")

    for job in (draft, closed):
        url = f"{careers(acme.company.slug)}jobs/{job['id']}/"
        assert visitor.get(url).status_code == 404


def test_a_job_is_only_found_under_its_own_company(acme, globex, job_payload, visitor):
    job = published(acme, job_payload)

    assert visitor.get(f"{careers(acme.company.slug)}jobs/{job['id']}/").status_code == 200
    assert visitor.get(f"{careers(globex.company.slug)}jobs/{job['id']}/").status_code == 404
    assert visitor.get(careers(globex.company.slug)).json()["jobs"] == []
    assert visitor.get(careers("no-such-company")).status_code == 404


def test_the_public_job_shows_nothing_internal(acme, job_payload, visitor):
    manager = acme.people["hiring_manager"]
    job = published(acme, job_payload, hiring_manager_id=str(manager.id))

    data = visitor.get(f"{careers(acme.company.slug)}jobs/{job['id']}/").json()["job"]

    assert set(data) == {
        "id",
        "title",
        "department",
        "location",
        "country",
        "workplace",
        "employment",
        "language",
        "published_at",
        "description",
        "salary",
        "requirements",
        "posting",
    }
    assert data["requirements"][0] == {"text": "5+ years building APIs in Python", "kind": "must"}
    assert manager.full_name not in str(data)
    assert manager.email not in str(data)


def test_salary_is_public_only_as_a_full_range(acme, job_payload, visitor):
    only_min = published(acme, job_payload, title="Min only", salary_min=50000)
    full = published(acme, job_payload, title="Range", salary_min=50000, salary_max=70000)

    def salary(job):
        url = f"{careers(acme.company.slug)}jobs/{job['id']}/"
        return visitor.get(url).json()["job"]["salary"]

    assert salary(only_min) is None
    assert salary(full) == {"min": 50000, "max": 70000, "currency": "MXN", "period": "month"}


def test_the_posting_is_valid_job_posting_structured_data(acme, job_payload, visitor):
    job = published(
        acme,
        job_payload,
        description="Own the checkout services.\n\nSmall team.",
        salary_min=80000,
        salary_max=110000,
    )

    posting = visitor.get(f"{careers(acme.company.slug)}jobs/{job['id']}/").json()["job"]["posting"]

    # Required by Google for JobPosting rich results.
    assert posting["@context"] == "https://schema.org/"
    assert posting["@type"] == "JobPosting"
    for field in ("title", "description", "datePosted", "hiringOrganization"):
        assert posting[field], field
    assert posting["hiringOrganization"] == {"@type": "Organization", "name": "Acme"}
    assert posting["jobLocation"]["address"] == {
        "@type": "PostalAddress",
        "addressCountry": "MX",
        "addressLocality": "Monterrey, NL",
    }
    assert posting["employmentType"] == "FULL_TIME"
    assert posting["baseSalary"]["value"] == {
        "@type": "QuantitativeValue",
        "minValue": 80000,
        "maxValue": 110000,
        "unitText": "MONTH",
    }
    assert posting["url"].endswith(f"/careers/{acme.company.slug}/jobs/{job['id']}")
    assert "<p>Own the checkout services.</p>" in posting["description"]
    assert "<li>Kubernetes in production</li>" in posting["description"]


def test_remote_jobs_say_where_applicants_can_be(acme, job_payload, visitor):
    job = published(acme, job_payload, workplace="remote", country="CO")

    posting = visitor.get(f"{careers(acme.company.slug)}jobs/{job['id']}/").json()["job"]["posting"]

    assert posting["jobLocationType"] == "TELECOMMUTE"
    assert posting["applicantLocationRequirements"] == {"@type": "Country", "name": "CO"}
    assert "jobLocation" not in posting


def test_user_text_is_escaped_in_the_structured_description(acme, job_payload, visitor):
    job = published(acme, job_payload, description="<script>alert(1)</script>")

    posting = visitor.get(f"{careers(acme.company.slug)}jobs/{job['id']}/").json()["job"]["posting"]

    assert "<script>" not in posting["description"]
    assert "&lt;script&gt;" in posting["description"]


def test_members_read_their_companys_slug(acme):
    response = acme.client("interviewer").get("/api/company/")

    assert response.json() == {
        "id": str(acme.company.id),
        "name": "Acme",
        "slug": acme.company.slug,
    }
