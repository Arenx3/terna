from datetime import timedelta
from smtplib import SMTPServerDisconnected

import pytest
from django.core import mail
from django.utils import timezone

from candidates.tests.conftest import PDF
from events import dispatch
from events.models import OutboxEvent
from messaging import tasks
from messaging.models import EmailMessage
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

TEMPLATES = "/api/email-templates/"


@pytest.fixture
def deliver(django_capture_on_commit_callbacks):
    """Run the outbox and whatever it queues, the way the workers would."""

    def run() -> None:
        with django_capture_on_commit_callbacks(execute=True):
            dispatch.dispatch_all()

    return run


@pytest.fixture
def application(acme, open_job, visitor, instant):
    assert (
        visitor.apply(visitor.upload(PDF), headers={"HTTP_ACCEPT_LANGUAGE": "es"}).status_code
        == 202
    )
    return acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()[0]


def messages(team) -> list[EmailMessage]:
    with tenant_context(team.company.id):
        return list(EmailMessage.objects.order_by("id"))


def emails_url(application) -> str:
    return f"/api/applications/{application['id']}/emails/"


def test_no_email_leaves_during_the_request(acme, application, deliver):
    [confirmation] = messages(acme)
    assert confirmation.status == "queued"
    assert mail.outbox == []  # the candidate's request is long gone before this is sent

    deliver()

    [sent] = messages(acme)
    assert sent.status == "sent"
    [email] = mail.outbox
    assert email.subject == "Recibimos tu postulación a Senior Backend Engineer"
    assert email.body.startswith("Hola, Lucía:")
    with tenant_context(acme.company.id):
        assert OutboxEvent.objects.filter(type="email.sent").count() == 1


def test_the_company_can_write_its_own_confirmation(acme, open_job, instant, deliver):
    admin = acme.client("admin")
    response = admin.put(
        f"{TEMPLATES}application_received/es/",
        {
            "subject": "¡Gracias, {{ candidate.first_name }}!",
            "body": "Recibimos tu CV para {{job.title}}. — {{ company.name }}",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["customized"] is True

    from candidates.tests.conftest import Visitor

    visitor = Visitor(acme, open_job)
    visitor.apply(visitor.upload(PDF), headers={"HTTP_ACCEPT_LANGUAGE": "es"})
    deliver()

    [email] = mail.outbox
    assert email.subject == "¡Gracias, Lucía!"
    assert email.body == "Recibimos tu CV para Senior Backend Engineer. — Acme"

    reset = admin.delete(f"{TEMPLATES}application_received/es/").json()
    assert reset["customized"] is False
    assert reset["subject"].startswith("Recibimos tu postulación")


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ("Hola {{ candidate.salary }}", "candidate.salary"),
        ("Etapa: {{ stage.name }}", "stage.name"),  # only for "moved forward" emails
        ("Hola {{ candidate.first_name }", "{{"),
    ],
)
def test_templates_only_use_variables_that_exist(acme, body, fragment):
    response = acme.client("admin").put(
        f"{TEMPLATES}rejection/es/", {"subject": "Asunto", "body": body}, format="json"
    )

    assert response.status_code == 400
    assert fragment in response.json()["body"][0]


def test_only_admins_edit_templates(acme):
    payload = {"subject": "x", "body": "y"}
    for role in ("recruiter", "hiring_manager"):
        response = acme.client(role).put(f"{TEMPLATES}rejection/es/", payload, format="json")
        assert response.status_code == 403
    assert acme.client("interviewer").get(TEMPLATES).status_code == 403


def test_every_kind_has_a_default_in_both_languages(acme):
    rows = acme.client("recruiter").get(TEMPLATES).json()

    assert len(rows) == 8
    advanced = next(r for r in rows if r["kind"] == "stage_advanced" and r["language"] == "en")
    assert "stage.name" in advanced["variables"]
    assert advanced["sample"]["candidate.first_name"] == "Lucía"


def test_a_rejection_can_be_written_and_scheduled(acme, application, deliver):
    deliver()  # the confirmation
    mail.outbox.clear()
    draft = (
        acme.client("recruiter")
        .get(f"{emails_url(application)}draft/", {"kind": "rejection"})
        .json()
    )
    assert draft["language"] == "es"
    assert draft["subject"] == "Sobre tu postulación a Senior Backend Engineer"
    assert "{{" not in draft["body"]

    tomorrow = timezone.now() + timedelta(days=1)
    response = acme.client("recruiter").post(
        emails_url(application),
        {
            "kind": "rejection",
            "subject": draft["subject"],
            "body": draft["body"] + "\n\nPD: te escribiremos si abre algo similar.",
            "scheduled_for": tomorrow.isoformat(),
        },
        format="json",
    )
    assert response.status_code == 201
    deliver()

    # Not before its time: the worker leaves it queued.
    rejection = messages(acme)[-1]
    assert rejection.status == "queued"
    assert mail.outbox == []

    canceled = acme.client("recruiter").post(f"/api/emails/{rejection.id}/cancel/")
    assert canceled.json()["status"] == "canceled"


def test_text_still_holding_variables_is_not_sent(acme, application):
    response = acme.client("recruiter").post(
        emails_url(application),
        {"kind": "rejection", "subject": "Hola", "body": "Hola {{ candidate.first_name }}"},
        format="json",
    )

    assert response.status_code == 400


def test_a_failing_email_is_retried_then_parked_with_its_reason(
    acme, application, monkeypatch, deliver
):
    def broken(*args, **kwargs):
        raise SMTPServerDisconnected("Connection unexpectedly closed")

    monkeypatch.setattr(tasks, "send_mail", broken)
    [message] = messages(acme)
    for _ in range(tasks.MAX_ATTEMPTS):
        tasks.send_email_message(str(acme.company.id), message.id)

    [failed] = messages(acme)
    assert failed.status == "failed"
    assert failed.attempts == tasks.MAX_ATTEMPTS
    assert failed.failure_reason == "SMTPServerDisconnected: Connection unexpectedly closed"

    monkeypatch.undo()
    retried = acme.client("recruiter").post(f"/api/emails/{failed.id}/retry/").json()
    assert retried["status"] == "queued"
    deliver()

    assert messages(acme)[0].status == "sent"
    assert len(mail.outbox) == 1


def test_a_sent_email_is_never_sent_twice(acme, application, deliver):
    deliver()
    [message] = messages(acme)

    assert tasks.send_email_message(str(acme.company.id), message.id) == "skipped"
    assert len(mail.outbox) == 1


def test_who_can_send_and_read(acme, globex, application):
    payload = {"kind": "rejection", "subject": "Hola", "body": "Gracias"}
    assert acme.client("hiring_manager").post(
        emails_url(application), payload, format="json"
    ).status_code in (403, 404)
    assert globex.client("admin").get(emails_url(application)).status_code == 404
    [listed] = acme.client("recruiter").get(emails_url(application)).json()
    assert listed["kind"] == "application_received"
