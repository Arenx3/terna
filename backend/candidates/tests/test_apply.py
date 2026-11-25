from datetime import timedelta

import pytest
from django.core import mail

from candidates import storage
from candidates.models import Application, Candidate, ConsentRecord, Resume
from candidates.services import PRIVACY_NOTICE_VERSION
from candidates.tests.conftest import DOCX, PDF, Visitor, docx_bytes, stored
from events.models import OutboxEvent
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db


def rows(team, model):
    with tenant_context(team.company.id):
        return list(model.objects.all())


def test_a_candidate_applies_with_a_pdf(acme, visitor, instant, django_capture_on_commit_callbacks):
    ticket = visitor.upload(PDF)

    with django_capture_on_commit_callbacks(execute=True):
        response = visitor.apply(ticket, headers={"HTTP_ACCEPT_LANGUAGE": "es"})

    assert response.status_code == 202
    assert response.json() == {"status": "received"}
    [application] = rows(acme, Application)
    with tenant_context(acme.company.id):
        assert application.stage.kind == "applied"
        candidate = application.candidate
        assert (candidate.email, candidate.full_name) == ("lucia@example.com", "Lucía Torres")
        resume = application.resume
        assert (resume.format, resume.size, resume.filename) == ("pdf", len(PDF), "cv.pdf")
        [consent] = ConsentRecord.objects.all()
        assert consent.notice_version == PRIVACY_NOTICE_VERSION
        assert consent.application_id == application.id
        assert consent.ip_address == "127.0.0.1"
        [event] = OutboxEvent.objects.filter(type="application.submitted")
        assert (event.actor_name, event.actor_id) == ("Lucía Torres", None)
    # The file left the upload area for its final place.
    assert not stored(visitor.key(ticket))
    assert stored(resume.storage_key)
    [email] = mail.outbox
    assert email.to == ["lucia@example.com"]
    assert "Recibimos tu postulación" in email.subject


def test_a_real_docx_is_accepted(acme, visitor, instant):
    response = visitor.apply(visitor.upload(docx_bytes(), DOCX))

    assert response.status_code == 202
    [resume] = rows(acme, Resume)
    assert resume.format == "docx"


@pytest.mark.parametrize(
    ("content", "content_type", "code"),
    [
        (b"MZ\x90\x00 an executable", "application/pdf", "resume_wrong_type"),
        (docx_bytes(with_document=False), DOCX, "resume_wrong_type"),
        (b"", "application/pdf", "resume_empty"),
    ],
    ids=["exe-named-pdf", "zip-not-docx", "empty"],
)
def test_files_that_are_not_really_a_resume_are_rejected(
    acme, visitor, instant, content, content_type, code
):
    ticket = visitor.upload(content, content_type)

    response = visitor.apply(ticket)

    assert response.status_code == 400
    assert response.json()["code"] == code
    assert rows(acme, Candidate) == []
    assert not stored(visitor.key(ticket))


def test_the_real_size_is_checked_after_upload(acme, visitor, instant, monkeypatch):
    ticket = visitor.upload(PDF)
    monkeypatch.setattr(storage, "MAX_RESUME_BYTES", 16)

    response = visitor.apply(ticket)

    assert response.json()["code"] == "resume_too_large"
    assert rows(acme, Candidate) == []


def test_declared_size_and_type_are_checked_before_upload(visitor):
    base = {"form_token": visitor.open_form(), "consent": True, "filename": "cv.pdf"}

    too_big = {**base, "content_type": "application/pdf", "size": storage.MAX_RESUME_BYTES + 1}
    wrong_type = {**base, "content_type": "application/zip", "size": 100}

    for payload in (too_big, wrong_type):
        response = visitor.client.post(f"{visitor.base}/uploads/", payload, format="json")
        assert response.status_code == 400


def test_applying_twice_keeps_one_application(acme, visitor, instant):
    assert visitor.apply(visitor.upload(PDF)).status_code == 202
    second = visitor.upload(PDF)

    response = visitor.apply(second, email="lucia@example.com", full_name="Lucía T.")

    assert response.status_code == 202
    assert len(rows(acme, Application)) == 1
    assert len(rows(acme, Resume)) == 1
    assert rows(acme, Candidate)[0].full_name == "Lucía Torres"
    assert not stored(visitor.key(second))


def test_one_candidate_can_apply_to_several_jobs(acme, job_payload, visitor, instant):
    other_job = (
        acme.client("recruiter")
        .post("/api/jobs/", job_payload(title="Platform Engineer"), format="json")
        .json()
    )
    acme.client("recruiter").post(f"/api/jobs/{other_job['id']}/publish/")
    visitor.apply(visitor.upload(PDF))
    elsewhere = Visitor(acme, other_job)
    elsewhere.apply(elsewhere.upload(PDF))

    assert len(rows(acme, Candidate)) == 1
    assert len(rows(acme, Application)) == 2


def test_without_consent_nothing_is_kept(acme, visitor, instant):
    refused_upload = visitor.client.post(
        f"{visitor.base}/uploads/",
        {
            "form_token": visitor.open_form(),
            "consent": False,
            "filename": "cv.pdf",
            "content_type": "application/pdf",
            "size": 100,
        },
        format="json",
    )
    assert refused_upload.status_code == 400
    assert "consent" in refused_upload.json()

    refused_apply = visitor.apply(visitor.upload(PDF), consent=False)
    assert refused_apply.status_code == 400
    assert rows(acme, Candidate) == []
    assert rows(acme, ConsentRecord) == []


def test_bots_filling_the_hidden_field_get_a_polite_nothing(acme, visitor, instant):
    ticket = visitor.upload(PDF)

    response = visitor.apply(ticket, website="https://spam.example")

    assert response.status_code == 202
    assert rows(acme, Candidate) == []
    assert not stored(visitor.key(ticket))


def test_instant_submissions_are_refused(acme, visitor):
    response = visitor.apply(visitor.upload(PDF))

    assert response.status_code == 400
    assert response.json()["code"] == "too_fast"


def test_an_outdated_privacy_notice_is_refused(acme, visitor, instant):
    response = visitor.apply(visitor.upload(PDF), notice_version="2020-01-01")

    assert response.status_code == 400
    assert "notice_version" in response.json()


def test_only_open_jobs_take_applications(acme, open_job, visitor, instant):
    acme.client("recruiter").post(f"/api/jobs/{open_job['id']}/close/")

    assert visitor.client.get(f"{visitor.base}/apply/").status_code == 404


def test_a_form_for_one_job_does_not_work_for_another(acme, job_payload, visitor, instant):
    other = (
        acme.client("recruiter")
        .post("/api/jobs/", job_payload(title="Other"), format="json")
        .json()
    )
    acme.client("recruiter").post(f"/api/jobs/{other['id']}/publish/")
    ticket = visitor.upload(PDF)

    response = Visitor(acme, other).apply(ticket)

    assert response.status_code == 400
    assert response.json()["code"] == "upload_expired"


def test_forgotten_uploads_are_purged(visitor):
    ticket = visitor.upload(PDF)

    assert storage.purge_incoming(older_than=timedelta(seconds=-60)) >= 1
    assert not stored(visitor.key(ticket))
