import pytest

from accounts.models import User
from accounts.sessions import user_memberships
from candidates.models import Application, ConsentRecord
from demo.seed import APPLICANTS, COMPANIES, OWNER_EMAIL, seed
from jobs.models import Job
from tenancy.context import tenant_context

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("test_bucket")]


def test_seed_creates_the_demo_and_can_run_again():
    seed(password="demo-password-123")
    seed(password="demo-password-123")

    owner = User.objects.get(email=OWNER_EMAIL)
    assert owner.check_password("demo-password-123")
    memberships = user_memberships(owner.id)
    assert sorted(m.company_name for m in memberships) == sorted(c.name for c in COMPANIES)
    for membership, demo in zip(
        sorted(memberships, key=lambda m: m.company_name),
        sorted(COMPANIES, key=lambda c: c.name),
        strict=True,
    ):
        with tenant_context(membership.company_id):
            titles = sorted(Job.objects.values_list("title", flat=True))
            assert titles == sorted(job.title for job in demo.jobs)
            statuses = dict(Job.objects.values_list("title", "status"))
            assert all(statuses[job.title] == job.status for job in demo.jobs)
            # Fictional applicants, each with a stored résumé and a consent record.
            expected = sum(len(APPLICANTS.get(job.title, ())) for job in demo.jobs)
            assert Application.objects.count() == expected
            assert ConsentRecord.objects.count() == expected


def test_seed_keeps_what_visitors_changed():
    seed(password="demo-password-123")
    owner = User.objects.get(email=OWNER_EMAIL)
    acme = next(m for m in user_memberships(owner.id) if m.company_name == "Acme Industrial")
    with tenant_context(acme.company_id):
        Job.objects.filter(title="Analista de datos").update(department="Finanzas")

    seed(password="demo-password-123")

    with tenant_context(acme.company_id):
        assert Job.objects.get(title="Analista de datos").department == "Finanzas"
