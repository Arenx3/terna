from datetime import timedelta

import pytest
from botocore.exceptions import EndpointConnectionError
from django.utils import timezone

from candidates import storage
from candidates.models import Resume
from candidates.tests.conftest import DOCX, Visitor
from demo.resumes import resume_pdf
from screening import tasks
from screening.models import ResumeExtraction, ResumePassage
from screening.tests.conftest import docx_resume
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

RESUME = [
    "Lucía Torres",
    "Ingeniera de datos · Ciudad de México · lucia.torres@example.com",
    "# Experiencia",
    "Ingeniera de datos, Acme — ene 2020 – actual",
    "• Pipelines de ingesta en Python y Airflow.",
    "# Idiomas",
    "Inglés avanzado (C1)",
]


@pytest.fixture
def apply(acme, open_job, visitor, instant):
    """Send an application with this résumé; returns it as the recruiter sees it."""

    def send(content: bytes = resume_pdf(RESUME), content_type: str = "application/pdf") -> dict:
        response = visitor.apply(visitor.upload(content, content_type))
        assert response.status_code == 202
        return acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()[0]

    return send


def text_url(application: dict) -> str:
    return f"/api/applications/{application['id']}/resume/text/"


def reprocess_url(application: dict) -> str:
    return f"/api/applications/{application['id']}/resume/reprocess/"


def extraction(team) -> ResumeExtraction:
    with tenant_context(team.company.id):
        return ResumeExtraction.objects.get()


def test_every_new_application_has_its_resume_read(acme, apply, deliver):
    application = apply()
    recruiter = acme.client("recruiter")
    assert recruiter.get(text_url(application)).json()["status"] == "pending"

    deliver()

    text = recruiter.get(text_url(application)).json()
    assert text["status"] == "ready"
    assert text["pages"] == 1
    assert [(p["section"], p["text"]) for p in text["passages"]] == [
        ("header", "Lucía Torres"),
        ("header", "Ingeniera de datos · Ciudad de México · lucia.torres@example.com"),
        ("experience", "Ingeniera de datos, Acme — ene 2020 – actual"),
        ("experience", "Pipelines de ingesta en Python y Airflow."),
        ("languages", "Inglés avanzado (C1)"),
    ]
    assert text["passages"][2]["periods"] == [
        {"text": "ene 2020 – actual", "start": "2020-01", "end": None, "ongoing": True}
    ]


def test_word_resumes_too(acme, apply, deliver):
    application = apply(docx_resume("en"), DOCX)
    deliver()

    text = acme.client("recruiter").get(text_url(application)).json()
    assert text["status"] == "ready"
    assert text["pages"] == 2
    assert {p["section"] for p in text["passages"]} == {
        "header", "summary", "experience", "education", "skills", "languages",
    }  # fmt: skip


def test_reading_again_replaces_the_passages(
    acme, apply, deliver, django_capture_on_commit_callbacks
):
    application = apply()
    deliver()
    recruiter = acme.client("recruiter")
    before = recruiter.get(text_url(application)).json()["passages"]

    with django_capture_on_commit_callbacks(execute=True):
        response = recruiter.post(reprocess_url(application))
    assert response.status_code == 202
    assert response.json()["status"] == "pending"

    after = recruiter.get(text_url(application)).json()["passages"]
    assert [p["text"] for p in after] == [p["text"] for p in before]
    assert {p["id"] for p in after}.isdisjoint(p["id"] for p in before)
    with tenant_context(acme.company.id):
        assert ResumePassage.objects.count() == len(before)
    # And a second copy of the same task finds nothing to do.
    resume_id = str(extraction(acme).resume_id)
    assert tasks.extract_resume(str(acme.company.id), resume_id) == "skipped"


def test_a_scan_without_text_waits_for_a_person(acme, apply, deliver):
    application = apply(resume_pdf([""]))
    deliver()

    text = acme.client("recruiter").get(text_url(application)).json()
    assert text["status"] == "needs_review"
    assert text["reason"] == "no_text"
    assert text["passages"] == []


def test_a_failure_is_written_down_and_can_be_retried(
    acme, apply, deliver, monkeypatch, django_capture_on_commit_callbacks
):
    application = apply()

    def broken(*args):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(tasks, "extract", broken)
    deliver()  # the worker survives: nothing is raised out of the task

    failed = acme.client("recruiter").get(text_url(application)).json()
    assert (failed["status"], failed["reason"]) == ("failed", "error")
    assert failed["detail"] == "RuntimeError: parser exploded"

    monkeypatch.undo()
    with django_capture_on_commit_callbacks(execute=True):
        acme.client("recruiter").post(reprocess_url(application))
    assert acme.client("recruiter").get(text_url(application)).json()["status"] == "ready"


def test_storage_hiccups_are_retried_before_giving_up(acme, apply, deliver, monkeypatch):
    apply()
    calls = []

    def unreachable(key):
        calls.append(key)
        raise EndpointConnectionError(endpoint_url="http://storage:9000")

    monkeypatch.setattr(storage, "read", unreachable)
    deliver()  # eager tasks: the retries run one after another

    row = extraction(acme)
    assert len(calls) == tasks.STORAGE_RETRIES + 1
    assert (row.status, row.reason) == ("failed", "storage")
    assert "Could not connect" in row.detail


def test_reading_happens_in_the_worker_never_in_a_request(acme, open_job, instant, monkeypatch):
    """Requests read a few bytes to check the file type; only the worker reads it all."""
    ranges = []
    real_client = storage.s3_client

    class Recorder:
        def __init__(self, client):
            self.client = client

        def __getattr__(self, name):
            return getattr(self.client, name)

        def get_object(self, **params):
            ranges.append(params.get("Range"))
            return self.client.get_object(**params)

    monkeypatch.setattr(storage, "s3_client", lambda **kw: Recorder(real_client(**kw)))
    visitor = Visitor(acme, open_job)
    visitor.apply(visitor.upload(resume_pdf(RESUME)))
    application = acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()
    acme.client("recruiter").get(f"/api/applications/{application[0]['id']}/")
    acme.client("recruiter").get(text_url(application[0]))

    assert ranges
    assert all(ranges)  # every read was a byte range


def test_who_can_read_and_reprocess(acme, globex, apply, deliver):
    application = apply()
    deliver()

    assert globex.client("admin").get(text_url(application)).status_code == 404
    assert acme.client("interviewer").get(text_url(application)).status_code == 404
    assert acme.client("hiring_manager").post(reprocess_url(application)).status_code == 403


def test_a_resume_being_read_is_not_queued_twice(acme, apply):
    application = apply()
    recruiter = acme.client("recruiter")
    assert recruiter.post(reprocess_url(application)).status_code == 202

    response = recruiter.post(reprocess_url(application))  # still pending

    assert response.status_code == 400
    assert response.json()["status"]


def test_resumes_never_read_are_picked_up(acme, apply, django_capture_on_commit_callbacks):
    apply()  # the outbox never ran: no extraction at all
    with tenant_context(acme.company.id):
        assert not ResumeExtraction.objects.exists()

    with django_capture_on_commit_callbacks(execute=True):
        assert tasks.recover_resume_extractions() == 1
    assert extraction(acme).status == "ready"

    # A run whose worker died long ago is taken over.
    with tenant_context(acme.company.id):
        ResumeExtraction.objects.update(
            status="processing", started_at=timezone.now() - timedelta(hours=1)
        )
    with django_capture_on_commit_callbacks(execute=True):
        assert tasks.recover_resume_extractions() == 1
    row = extraction(acme)
    assert (row.status, row.attempts) == ("ready", 2)


def test_deleting_the_candidate_deletes_the_text(acme, apply, deliver):
    apply()
    deliver()
    with tenant_context(acme.company.id):
        assert ResumePassage.objects.exists()
        Resume.objects.get().candidate.delete()
        assert not ResumePassage.objects.exists()
        assert not ResumeExtraction.objects.exists()


def test_the_ai_only_ever_reads_the_redacted_text(acme, apply, deliver):
    application = apply()
    deliver()

    text = acme.client("recruiter").get(text_url(application)).json()
    assert text["language"] == "es"
    assert [p["redacted"] for p in text["passages"][:2]] == [
        "[NOMBRE]",
        "Ingeniera de datos · [UBICACIÓN] · [CORREO]",
    ]
    assert text["passages"][1]["redactions"] == [
        {"kind": "location", "start": 21, "end": 37},
        {"kind": "email", "start": 40, "end": 64},
    ]
    with tenant_context(acme.company.id):
        analysis = analysis_text(extraction(acme).resume_id)
    assert "Lucía" not in analysis
    assert "lucia.torres@example.com" not in analysis
    assert "Pipelines de ingesta en Python y Airflow." in analysis


def analysis_text(resume_id) -> str:
    from screening.analysis import passages_for_analysis

    return "\n".join(text for _, text in passages_for_analysis(resume_id))


def test_resumes_redacted_by_older_rules_are_redacted_again(
    acme, apply, deliver, django_capture_on_commit_callbacks
):
    apply()
    deliver()
    with tenant_context(acme.company.id):
        ResumeExtraction.objects.update(redaction_version=0)
        ResumePassage.objects.update(redacted="Lucía Torres")
        # Until then, nothing reaches the AI.
        assert analysis_text(extraction(acme).resume_id) == ""

    with django_capture_on_commit_callbacks(execute=True):
        assert tasks.recover_resume_extractions() == 1

    row = extraction(acme)
    assert (row.status, row.redaction_version) == ("ready", tasks.redaction.VERSION)
    with tenant_context(acme.company.id):
        assert "Lucía" not in analysis_text(row.resume_id)
