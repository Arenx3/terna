"""Reading résumés, on the `ml` worker.

A run claims the extraction in one short transaction, reads and splits the
file outside any transaction, then writes the result in another. Nothing is
raised out of the task: every outcome ends as a status with its reason, and the
worker moves on to the next résumé.
"""

import logging
from collections import Counter
from dataclasses import dataclass
from functools import partial

from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import worker_ready
from django.db import transaction
from django.utils import timezone

from candidates import storage
from candidates.models import Application
from events.models import EventType
from events.outbox import emit
from screening import dictionary, embeddings, matching, redaction, services
from screening.analysis import AnalysisPassage, analysis_passages
from screening.extraction import ExtractionError, extract
from screening.models import (
    RequirementMatch,
    RequirementVector,
    ResumeExtraction,
    ResumePassage,
    Screening,
    Verdict,
)
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
        row.embedding_model = ""  # new passages, not embedded yet
        if status == Status.READY:
            row.redaction_version = redaction.VERSION
            row.extracted_at = timezone.now()
        row.save()
        if status == Status.READY:
            services.screen_resume_applications(resume_id)
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


# Screening


@dataclass(frozen=True)
class Inputs:
    needs: list[matching.Need]
    passages: list[AnalysisPassage]
    job_language: str
    resume_language: str
    entries: list[dictionary.Entry]
    # Texts still without a vector from the current model.
    unembedded_passages: list[tuple[int, str]]
    unembedded_needs: list[tuple[int, str]]


def _claim_screening(company_id: str, application_id: int) -> tuple[int, object] | None:
    with tenant_context(company_id):
        row = (
            Screening.objects.select_for_update()
            .select_related("application")
            .filter(application_id=application_id)
            .first()
        )
        if row is None:
            return None
        abandoned = (
            row.status == Screening.Status.PROCESSING
            and row.started_at is not None
            and row.started_at < timezone.now() - services.STALE_AFTER
        )
        if row.status != Screening.Status.PENDING and not abandoned:
            return None
        row.status = Screening.Status.PROCESSING
        row.attempts += 1
        row.started_at = timezone.now()
        row.save(update_fields=["status", "attempts", "started_at", "updated_at"])
        return row.attempts, row.application.resume_id


def _inputs(company_id: str, application_id: int, resume_id) -> Inputs | None:
    """What the screening reads, or None while the résumé isn't ready to be read."""
    model = embeddings.name()
    with tenant_context(company_id):
        extraction = ResumeExtraction.objects.filter(resume_id=resume_id).first()
        passages = analysis_passages(resume_id)
        if extraction is None or not passages:
            return None
        application = Application.objects.select_related("job").get(pk=application_id)
        requirements = list(application.job.requirements.order_by("position"))
        vectors = dict(
            RequirementVector.objects.filter(requirement__in=requirements, model=model).values_list(
                "requirement_id", "text"
            )
        )
        stale = extraction.embedding_model != model
        embedded = set(
            ResumePassage.objects.filter(resume_id=resume_id, embedding__isnull=False).values_list(
                "id", flat=True
            )
        )
        return Inputs(
            needs=[matching.Need(r.id, r.text, r.kind) for r in requirements],
            passages=passages,
            job_language=application.job.language,
            resume_language=extraction.language or "es",
            entries=dictionary.entries(),
            unembedded_passages=[
                (p.id, p.redacted) for p in passages if stale or p.id not in embedded
            ],
            unembedded_needs=[(r.id, r.text) for r in requirements if vectors.get(r.id) != r.text],
        )


def _store_vectors(company_id: str, resume_id, inputs: Inputs) -> None:
    passage_vectors = embeddings.encode([text for _, text in inputs.unembedded_passages])
    need_vectors = embeddings.encode([text for _, text in inputs.unembedded_needs])
    model = embeddings.name()
    with tenant_context(company_id):
        for (passage_id, _), vector in zip(
            inputs.unembedded_passages, passage_vectors, strict=True
        ):
            ResumePassage.objects.filter(pk=passage_id).update(embedding=vector)
        for (requirement_id, text), vector in zip(
            inputs.unembedded_needs, need_vectors, strict=True
        ):
            RequirementVector.objects.update_or_create(
                requirement_id=requirement_id,
                defaults={"text": text, "model": model, "embedding": vector},
            )
        ResumeExtraction.objects.filter(resume_id=resume_id).update(embedding_model=model)


def _finish_screening(
    company_id: str,
    application_id: int,
    attempt: int,
    status: str,
    *,
    detail: str = "",
    results: list[matching.Result] | None = None,
) -> bool:
    """Write this run's result, unless the screening was reset or claimed again since."""
    with tenant_context(company_id):
        row = (
            Screening.objects.select_for_update()
            .select_related("application__candidate", "application__job")
            .filter(application_id=application_id)
            .first()
        )
        if row is None or row.attempts != attempt or row.status != Screening.Status.PROCESSING:
            return False
        row.status = status
        row.detail = detail[:500]
        if status == Screening.Status.READY:
            results = results or []
            RequirementMatch.objects.filter(screening=row).delete()
            RequirementMatch.objects.bulk_create(
                RequirementMatch(
                    company_id=company_id,
                    screening=row,
                    requirement_id=result.need.id,
                    verdict=result.verdict,
                    signals=result.signals,
                    evidence=result.evidence,
                )
                for result in results
            )
            counts = Counter((result.need.kind, result.verdict) for result in results)
            row.must_total = sum(n for (kind, _), n in counts.items() if kind == "must")
            row.must_meets = counts[("must", Verdict.MEETS)]
            row.must_partial = counts[("must", Verdict.PARTIAL)]
            row.nice_total = sum(n for (kind, _), n in counts.items() if kind == "nice")
            row.nice_meets = counts[("nice", Verdict.MEETS)]
            row.nice_partial = counts[("nice", Verdict.PARTIAL)]
            row.version = matching.VERSION
            row.completed_at = timezone.now()
        row.save()
        if status == Screening.Status.READY:
            application = row.application
            emit(
                EventType.SCREENING_COMPLETED,
                entity_type="application",
                entity_id=application.id,
                label=application.candidate.full_name,
                payload={
                    "job_id": str(application.job_id),
                    "must": [row.must_meets, row.must_total],
                    "nice": [row.nice_meets, row.nice_total],
                },
                actor=None,  # Terna itself
            )
        return True


@shared_task(ignore_result=True, soft_time_limit=300, time_limit=360)
def screen_application(company_id: str, application_id: int) -> str:
    """Match one application's résumé against its job's requirements. Safe to run twice:
    only a pending screening runs, and only its latest run writes."""
    claim = _claim_screening(company_id, application_id)
    if claim is None:
        return "skipped"
    attempt, resume_id = claim
    finish = partial(_finish_screening, company_id, application_id, attempt)
    try:
        inputs = _inputs(company_id, application_id, resume_id)
        if inputs is None:
            # Screened as soon as the résumé is read (see `_finish`).
            finish(Screening.Status.WAITING)
            return Screening.Status.WAITING
        _store_vectors(company_id, resume_id, inputs)
        with tenant_context(company_id):
            similarity = embeddings.similarities(resume_id, [need.id for need in inputs.needs])
        results = matching.screen(
            inputs.needs,
            inputs.passages,
            job_language=inputs.job_language,
            resume_language=inputs.resume_language,
            entries=inputs.entries,
            similarity=similarity,
        )
    except SoftTimeLimitExceeded:
        finish(Screening.Status.FAILED, detail="Took too long to screen")
        return Screening.Status.FAILED
    except Exception as exc:
        logger.exception("Application %s could not be screened", application_id)
        finish(Screening.Status.FAILED, detail=f"{type(exc).__name__}: {exc}")
        return Screening.Status.FAILED
    finish(Screening.Status.READY, results=results)
    return Screening.Status.READY


@shared_task(ignore_result=True, soft_time_limit=1800, time_limit=1900)
def load_model() -> None:
    """On the ml worker's start: load the model (downloading it the first time), so the
    first screening doesn't wait for it."""
    embeddings.load()


@worker_ready.connect
def _load_model_on_ml_worker(sender, **kwargs) -> None:
    queues = {queue.name for queue in sender.app.amqp.queues.consume_from.values()}
    if "ml" in queues:
        load_model.delay()


@shared_task(ignore_result=True)
def recover_screenings() -> int:
    """Every few minutes: applications never screened, or by older rules, go again."""
    total = 0
    for company_id in all_company_ids():
        with tenant_context(company_id):
            total += services.recover_screenings()
    return total
