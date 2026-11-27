"""When résumés are read: for every new application, on request, and as a safety net.

Scheduling writes a `pending` extraction in the caller's transaction and hands
the résumé to the `ml` worker once it commits. The worker claims the row, so
asking twice reads the file once.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from candidates.models import Application, Resume
from events.models import EventType, OutboxEvent
from screening import redaction
from screening.models import ResumeExtraction
from tenancy.context import require_company_id

# A run that hasn't finished in this long died with its worker; another may take over.
STALE_AFTER = timedelta(minutes=15)
# Pending rows younger than this were just handed to a worker.
RECOVER_AFTER = timedelta(minutes=2)
RECOVER_BATCH = 200


def _enqueue(resume_id) -> None:
    from screening.tasks import extract_resume

    company_id, resume_id = str(require_company_id()), str(resume_id)
    transaction.on_commit(lambda: extract_resume.delay(company_id, resume_id))


def on_event(event: OutboxEvent) -> None:
    """Outbox consumer: read the résumé of every application that arrives."""
    if event.type != EventType.APPLICATION_SUBMITTED:
        return
    resume_id = (
        Application.objects.filter(id=event.entity_id).values_list("resume_id", flat=True).first()
    )
    if resume_id is None:
        return
    extraction, created = ResumeExtraction.objects.get_or_create(resume_id=resume_id)
    if created or extraction.status == ResumeExtraction.Status.PENDING:
        _enqueue(resume_id)


def reprocess(extraction: ResumeExtraction) -> ResumeExtraction:
    """Read the file again. Its passages are replaced, never added to."""
    extraction.status = ResumeExtraction.Status.PENDING
    extraction.reason = ""
    extraction.detail = ""
    extraction.save(update_fields=["status", "reason", "detail", "updated_at"])
    _enqueue(extraction.resume_id)
    return extraction


def recover() -> int:
    """Résumés never read (older ones, a lost task, a dead worker): schedule them again."""
    now = timezone.now()
    missing = list(
        Resume.objects.filter(extraction__isnull=True).values_list("id", flat=True)[:RECOVER_BATCH]
    )
    ResumeExtraction.objects.bulk_create(
        [
            ResumeExtraction(resume_id=resume_id, company_id=require_company_id())
            for resume_id in missing
        ],
        ignore_conflicts=True,
    )
    stuck = ResumeExtraction.objects.filter(
        Q(status=ResumeExtraction.Status.PENDING, updated_at__lt=now - RECOVER_AFTER)
        | Q(status=ResumeExtraction.Status.PROCESSING, started_at__lt=now - STALE_AFTER)
    ).values_list("resume_id", flat=True)[:RECOVER_BATCH]
    # Redacted by older rules: read again, so the AI never sees what they missed.
    outdated = list(
        ResumeExtraction.objects.filter(
            status=ResumeExtraction.Status.READY, redaction_version__lt=redaction.VERSION
        ).values_list("resume_id", flat=True)[:RECOVER_BATCH]
    )
    ResumeExtraction.objects.filter(resume_id__in=outdated).update(
        status=ResumeExtraction.Status.PENDING, updated_at=now
    )
    scheduled = {*missing, *stuck, *outdated}
    for resume_id in scheduled:
        _enqueue(resume_id)
    return len(scheduled)
