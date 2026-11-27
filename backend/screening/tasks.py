"""Reading résumés, on the `ml` worker.

A run claims the extraction in one short transaction, reads and splits the
file outside any transaction, then writes the result in another. Nothing is
raised out of the task: every outcome ends as a status with its reason, and the
worker moves on to the next résumé.
"""

import logging
from functools import partial

from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone

from candidates import storage
from screening import redaction, services
from screening.extraction import ExtractionError, extract
from screening.models import ResumeExtraction, ResumePassage
from tenancy.context import all_company_ids, tenant_context

logger = logging.getLogger(__name__)

Status = ResumeExtraction.Status
Reason = ResumeExtraction.Reason
# Storage hiccups are retried, with a growing delay, before giving up.
STORAGE_RETRIES = 3
# Waiting on a person: there's no text to read, or it's locked.
NEEDS_A_PERSON = (Reason.NO_TEXT, Reason.ENCRYPTED)


def _claim(company_id: str, resume_id: str) -> tuple[int, str, str, str] | None:
    with tenant_context(company_id):
        row = (
            ResumeExtraction.objects.select_for_update()
            .select_related("resume__candidate")
            .filter(resume_id=resume_id)
            .first()
        )
        if row is None:
            return None
        abandoned = (
            row.status == Status.PROCESSING
            and row.started_at is not None
            and row.started_at < timezone.now() - services.STALE_AFTER
        )
        if row.status != Status.PENDING and not abandoned:
            return None  # read already, or being read right now
        row.status = Status.PROCESSING
        row.attempts += 1
        row.started_at = timezone.now()
        row.save(update_fields=["status", "attempts", "started_at", "updated_at"])
        resume = row.resume
        return row.attempts, resume.storage_key, resume.format, resume.candidate.full_name


def _finish(
    company_id: str,
    resume_id: str,
    attempt: int,
    status: str,
    *,
    reason: str = "",
    detail: str = "",
    pages: int = 0,
    passages: list[dict] | None = None,
    language: str = "",
) -> bool:
    """Write this run's result, unless a newer run has claimed the résumé since."""
    with tenant_context(company_id):
        row = ResumeExtraction.objects.select_for_update().filter(resume_id=resume_id).first()
        if row is None or row.attempts != attempt or row.status != Status.PROCESSING:
            return False
        # Replaced as a whole, so reading a file twice never doubles its passages.
        ResumePassage.objects.filter(resume_id=resume_id).delete()
        ResumePassage.objects.bulk_create(
            ResumePassage(company_id=company_id, resume_id=resume_id, **passage)
            for passage in passages or []
        )
        row.status = status
        row.reason = reason
        row.detail = detail[:500]
        row.pages = pages
        row.language = language
        if status == Status.READY:
            row.redaction_version = redaction.VERSION
        if status == Status.READY:
            row.extracted_at = timezone.now()
        row.save()
        return True


@shared_task(ignore_result=True, soft_time_limit=120, time_limit=180)
def extract_resume(company_id: str, resume_id: str, retry: int = 0) -> str:
    """Read one résumé into passages. Safe to run twice: only a pending résumé is read."""
    claim = _claim(company_id, resume_id)
    if claim is None:
        return "skipped"
    attempt, key, kind, full_name = claim
    finish = partial(_finish, company_id, resume_id, attempt)

    try:
        content = storage.read(key)
        result = extract(content, kind)
        # Before anything else reads them, the passages lose their personal data.
        language = redaction.redact(result.passages, full_name)
    except ExtractionError as exc:
        status = Status.NEEDS_REVIEW if exc.reason in NEEDS_A_PERSON else Status.FAILED
        finish(status, reason=exc.reason, detail=exc.detail)
        return status
    except storage.InvalidResumeError as exc:
        finish(Status.FAILED, reason=Reason.UNREADABLE, detail=f"File {exc}")
        return Status.FAILED
    except (BotoCoreError, ClientError, OSError) as exc:
        detail = f"{type(exc).__name__}: {exc}"
        if retry >= STORAGE_RETRIES:
            finish(Status.FAILED, reason=Reason.STORAGE, detail=detail)
            return Status.FAILED
        _retry_later(company_id, resume_id, attempt, retry, detail)
        return "retrying"
    except SoftTimeLimitExceeded:
        finish(Status.FAILED, reason=Reason.ERROR, detail="Took too long to read")
        return Status.FAILED
    except Exception as exc:
        logger.exception("Résumé %s could not be read", resume_id)
        finish(Status.FAILED, reason=Reason.ERROR, detail=f"{type(exc).__name__}: {exc}")
        return Status.FAILED

    finish(Status.READY, pages=result.pages, passages=result.passages, language=language)
    return Status.READY


def _retry_later(company_id: str, resume_id: str, attempt: int, retry: int, detail: str) -> None:
    """Back to pending, with the reason, and another try in 30 s, 1 min, 2 min."""
    with tenant_context(company_id):
        updated = ResumeExtraction.objects.filter(
            resume_id=resume_id, attempts=attempt, status=Status.PROCESSING
        ).update(status=Status.PENDING, reason=Reason.STORAGE, detail=detail[:500])
        if updated:
            transaction.on_commit(
                lambda: extract_resume.apply_async(
                    (company_id, resume_id), {"retry": retry + 1}, countdown=30 * 2**retry
                )
            )


@shared_task(ignore_result=True)
def recover_resume_extractions() -> int:
    """Every few minutes: résumés that were never read, or whose worker died, go again."""
    total = 0
    for company_id in all_company_ids():
        with tenant_context(company_id):
            total += services.recover()
    return total
