"""Emails to candidates: written now, sent by a worker, recorded either way.

Queuing writes the message and an `email.queued` event in the caller's
transaction. The outbox hands the event to `enqueue`, which schedules the
Celery task; nothing is ever sent inside an HTTP request, and a rolled-back
change sends nothing.
"""

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from candidates.models import Application
from events.models import EventType, OutboxEvent
from events.outbox import current_actor, emit
from jobs.models import PipelineStage
from messaging import templates
from messaging.models import EmailMessage, EmailTemplate
from tenancy.models import Company

_UNSET = object()


def effective(kind: str, language: str) -> tuple[templates.Text, EmailTemplate | None]:
    """The company's own wording if it has one, otherwise Terna's default."""
    row = EmailTemplate.objects.filter(kind=kind, language=language).first()
    if row is not None:
        return templates.Text(row.subject, row.body), row
    return templates.DEFAULTS[(kind, language)], None


def values_for(application: Application, stage: PipelineStage | None = None) -> dict[str, str]:
    candidate = application.candidate
    stage = stage or application.stage
    return {
        "candidate.first_name": candidate.full_name.split(" ")[0],
        "candidate.full_name": candidate.full_name,
        "job.title": application.job.title,
        "company.name": Company.objects.values_list("name", flat=True).get(),
        "stage.name": stage.name or stage.get_kind_display(),
    }


def language_of(application: Application) -> str:
    return (
        application.candidate.language if application.candidate.language in ("es", "en") else "es"
    )


def draft(application: Application, kind: str, language: str | None = None) -> templates.Text:
    """The email as it would go out now, ready to be edited before sending."""
    language = language or language_of(application)
    text, _ = effective(kind, language)
    values = values_for(application)
    return templates.Text(
        templates.render(text.subject, values), templates.render(text.body, values)
    )


def queue(
    application: Application,
    *,
    kind: str,
    subject: str,
    body: str,
    language: str | None = None,
    scheduled_for: datetime | None = None,
    actor=_UNSET,
) -> EmailMessage:
    """Write the email down and leave its sending to the outbox and a worker.

    The author is whoever is acting (the request's user); `actor=None` marks
    an automatic email that Terna sends on the company's behalf.
    """
    who = current_actor() if actor is _UNSET else actor
    with transaction.atomic():
        message = EmailMessage.objects.create(
            application=application,
            kind=kind,
            language=language or language_of(application),
            to=application.candidate.email,
            subject=subject,
            body=body,
            scheduled_for=scheduled_for,
            created_by_name=getattr(who, "full_name", ""),
        )
        emit(
            EventType.EMAIL_QUEUED,
            entity_type="application",
            entity_id=application.id,
            label=application.candidate.full_name,
            payload={"message_id": message.id, "kind": kind, "subject": subject},
            actor=who,
        )
    return message


def queue_from_template(application: Application, kind: str) -> EmailMessage:
    """An automatic email (no one wrote it): the template, as Terna itself."""
    text = draft(application, kind)
    return queue(application, kind=kind, subject=text.subject, body=text.body, actor=None)


def retry(message: EmailMessage) -> EmailMessage:
    with transaction.atomic():
        message.status = EmailMessage.Status.QUEUED
        message.attempts = 0
        message.failure_reason = ""
        message.scheduled_for = None
        message.save(update_fields=["status", "attempts", "failure_reason", "scheduled_for"])
        emit(
            EventType.EMAIL_QUEUED,
            entity_type="application",
            entity_id=message.application_id,
            label=message.application.candidate.full_name,
            payload={"message_id": message.id, "kind": message.kind, "subject": message.subject},
        )
    return message


def cancel(message: EmailMessage) -> EmailMessage:
    message.status = EmailMessage.Status.CANCELED
    message.save(update_fields=["status"])
    return message


def enqueue(event: OutboxEvent) -> None:
    """Outbox consumer: hand queued emails to the worker, at their time if scheduled."""
    if event.type != EventType.EMAIL_QUEUED:
        return
    from messaging.tasks import send_email_message

    message = EmailMessage.objects.filter(id=event.payload.get("message_id")).first()
    if message is None or message.status != EmailMessage.Status.QUEUED:
        return
    company_id, message_id, when = str(event.company_id), message.id, message.scheduled_for
    eta = when if when and when > timezone.now() else None
    transaction.on_commit(lambda: send_email_message.apply_async((company_id, message_id), eta=eta))
