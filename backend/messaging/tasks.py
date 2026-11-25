from datetime import timedelta
from smtplib import SMTPException

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from events.models import EventType
from events.outbox import emit
from messaging.models import EmailMessage
from tenancy.tasks import tenant_task

MAX_ATTEMPTS = 5


def _backoff(attempt: int) -> int:
    return min(600, 30 * 2 ** (attempt - 1))


@tenant_task()
def send_email_message(company_id: str, message_id: int) -> str:
    """Send one queued email. Safe to run twice: only a queued message goes out.

    Failures are written down instead of raised, so the record survives: the
    next attempt is scheduled with a growing delay, and after the last one the
    message is marked failed, with the reason, for someone to retry.
    """
    message = (
        EmailMessage.objects.select_for_update()
        .select_related("application__candidate")
        .filter(id=message_id)
        .first()
    )
    if message is None or message.status != EmailMessage.Status.QUEUED:
        return "skipped"
    if message.scheduled_for and message.scheduled_for > timezone.now() + timedelta(seconds=5):
        return "not yet"  # an early copy; the scheduled one comes later

    message.attempts += 1
    try:
        send_mail(message.subject, message.body, None, [message.to])
    except (SMTPException, OSError) as exc:
        message.failure_reason = f"{type(exc).__name__}: {exc}"[:500]
        if message.attempts >= MAX_ATTEMPTS:
            message.status = EmailMessage.Status.FAILED
            message.save(update_fields=["attempts", "failure_reason", "status"])
            _record(message, EventType.EMAIL_FAILED)
            return "failed"
        message.save(update_fields=["attempts", "failure_reason"])
        delay = _backoff(message.attempts)
        transaction.on_commit(
            lambda: send_email_message.apply_async((company_id, message_id), countdown=delay)
        )
        return "retrying"

    message.status = EmailMessage.Status.SENT
    message.sent_at = timezone.now()
    message.failure_reason = ""
    message.save(update_fields=["attempts", "status", "sent_at", "failure_reason"])
    _record(message, EventType.EMAIL_SENT)
    return "sent"


def _record(message: EmailMessage, kind: str) -> None:
    """On the candidate's timeline and in the audit log: what they were sent, or not."""
    emit(
        kind,
        entity_type="application",
        entity_id=message.application_id,
        label=message.application.candidate.full_name,
        payload={
            "message_id": message.id,
            "kind": message.kind,
            "subject": message.subject,
            "reason": message.failure_reason,
        },
        actor=None,
    )
