"""When résumés are read and applications screened: as they arrive, when what they're
measured against changes, on request, and as a safety net.

Scheduling writes a `pending` row in the caller's transaction and hands the work
to the `ml` worker once it commits. The worker claims the row, so asking twice
does the work once, and a run whose row was reset meanwhile throws its result away.
"""

from collections.abc import Iterable
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from candidates.models import Application, Resume
from events.models import EventType, OutboxEvent
from jobs.models import Job
from screening import matching, redaction
from screening.models import ResumeExtraction, Screening
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
    """Outbox consumer: read the résumé of every application that arrives, and screen a
    job's candidates again when its requirements change."""
    if event.type == EventType.JOB_REQUIREMENTS_CHANGED:
        schedule_screenings(
            Application.objects.filter(job_id=event.entity_id).values_list("id", flat=True)
        )
        return
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
    # Their evidence points at passages about to be replaced: screened again once read.
    Screening.objects.filter(application__resume_id=extraction.resume_id).update(
        status=Screening.Status.WAITING, updated_at=timezone.now()
    )
    _enqueue(extraction.resume_id)
    return extraction


# Screening


def _enqueue_screening(application_id) -> None:
    from screening.tasks import screen_application

    company_id, application_id = str(require_company_id()), int(application_id)
    transaction.on_commit(lambda: screen_application.delay(company_id, application_id))


def schedule_screenings(application_ids: Iterable[int]) -> int:
    """Screen these applications (again), once the caller's transaction commits.

    A run already in progress loses its claim: its result, measured against what
    changed, is thrown away, and the new run takes over.
    """
    ids = list(
        Application.objects.filter(id__in=list(application_ids), resume__isnull=False)
        .values_list("id", flat=True)
        .order_by("id")
    )
    if not ids:
        return 0
    company_id = require_company_id()
    Screening.objects.bulk_create(
        [Screening(application_id=pk, company_id=company_id) for pk in ids],
        ignore_conflicts=True,
    )
    Screening.objects.filter(application_id__in=ids).update(
        status=Screening.Status.PENDING, detail="", updated_at=timezone.now()
    )
    for pk in ids:
        _enqueue_screening(pk)
    return len(ids)


def screen_resume_applications(resume_id) -> int:
    """The résumé was just read: screen every application that sent it."""
    return schedule_screenings(
        Application.objects.filter(resume_id=resume_id).values_list("id", flat=True)
    )


def screen_company_again() -> int:
    """The company's dictionary changed: screen again every job still being filled."""
    return schedule_screenings(
        Application.objects.exclude(job__status=Job.Status.CLOSED).values_list("id", flat=True)
    )


def recover_screenings() -> int:
    """Applications whose résumé was read but never screened (older ones, a lost task,
    a dead worker), or screened by older rules: screen them again."""
    now = timezone.now()
    ready = Application.objects.filter(
        resume__extraction__status=ResumeExtraction.Status.READY,
        resume__extraction__redaction_version__gte=redaction.VERSION,
    )
    never = ready.filter(screening__isnull=True).values_list("id", flat=True)[:RECOVER_BATCH]
    stuck = Screening.objects.filter(
        Q(status=Screening.Status.PENDING, updated_at__lt=now - RECOVER_AFTER)
        | Q(status=Screening.Status.PROCESSING, started_at__lt=now - STALE_AFTER)
        | Q(status=Screening.Status.READY, version__lt=matching.VERSION)
        | Q(status=Screening.Status.WAITING, application__in=ready)
    ).values_list("application_id", flat=True)[:RECOVER_BATCH]
    return schedule_screenings({*never, *stuck})


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
