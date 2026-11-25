"""Job changes. Callers run inside the active company (tenant context)."""

from collections.abc import Sequence
from dataclasses import dataclass

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from events.models import EventType
from events.outbox import emit
from jobs.models import Job, PipelineStage, Requirement, StageTemplate
from jobs.pipeline import DEFAULT_PIPELINE, Stage, check_shape


@dataclass(frozen=True)
class RequirementItem:
    text: str
    kind: str
    id: int | None = None


class UnknownItemError(ValueError):
    """An item id that does not belong to this job (or template)."""

    def __init__(self, field: str, item_id: int) -> None:
        super().__init__(f"{field}: unknown id {item_id}")
        self.field = field


class PublishBlockedError(Exception):
    """A job can't be published without at least one must-have requirement."""


class StageInUseError(Exception):
    """A stage can't be removed while applications sit in it."""


class NotDraftError(Exception):
    """Only drafts can be deleted: published jobs are closed instead, keeping their history."""


def template_stages() -> list[Stage]:
    """The company's default pipeline, or Terna's until an admin changes it."""
    rows = StageTemplate.objects.order_by("position")
    return [Stage(kind=row.kind, name=row.name, id=row.id) for row in rows] or list(
        DEFAULT_PIPELINE
    )


@transaction.atomic
def save_template(stages: Sequence[Stage]) -> list[Stage]:
    check_shape(stages)
    _sync(StageTemplate.objects.all(), stages, StageTemplate, ("name", "kind"), "stages")
    return template_stages()


@transaction.atomic
def create_job(
    *,
    created_by,
    fields: dict,
    requirements: Sequence[RequirementItem] = (),
    stages: Sequence[Stage] | None = None,
) -> Job:
    job = Job.objects.create(created_by=created_by, **fields)
    # New rows only: ids from the payload (or the template) mean nothing for a new job.
    _sync(
        job.requirements.none(),
        [RequirementItem(text=item.text, kind=item.kind) for item in requirements],
        lambda: Requirement(job=job),
        ("text", "kind"),
        "requirements",
    )
    pipeline = [Stage(kind=s.kind, name=s.name) for s in (stages or template_stages())]
    check_shape(pipeline)
    _sync(job.stages.none(), pipeline, lambda: PipelineStage(job=job), ("name", "kind"), "stages")
    _emit(EventType.JOB_CREATED, job)
    return job


@transaction.atomic
def update_job(
    job: Job,
    *,
    fields: dict,
    requirements: Sequence[RequirementItem] | None = None,
    stages: Sequence[Stage] | None = None,
) -> Job:
    for name, value in fields.items():
        setattr(job, name, value)
    if requirements is not None:
        _sync(
            job.requirements.all(),
            requirements,
            lambda: Requirement(job=job),
            ("text", "kind"),
            "requirements",
        )
    if stages is not None:
        check_shape(stages)
        _sync(job.stages.all(), stages, lambda: PipelineStage(job=job), ("name", "kind"), "stages")
    if job.status == Job.Status.OPEN and not _has_must_have(job):
        raise PublishBlockedError
    job.save()
    return job


@transaction.atomic
def publish(job: Job) -> Job:
    if not _has_must_have(job):
        raise PublishBlockedError
    previous = job.status
    job.status = Job.Status.OPEN
    job.published_at = job.published_at or timezone.now()
    job.closed_at = None
    job.save(update_fields=["status", "published_at", "closed_at", "updated_at"])
    if previous != Job.Status.OPEN:
        reopened = previous == Job.Status.CLOSED
        _emit(EventType.JOB_REOPENED if reopened else EventType.JOB_PUBLISHED, job)
    return job


@transaction.atomic
def close(job: Job) -> Job:
    if job.status == Job.Status.CLOSED:
        return job
    job.status = Job.Status.CLOSED
    job.closed_at = timezone.now()
    job.save(update_fields=["status", "closed_at", "updated_at"])
    _emit(EventType.JOB_CLOSED, job)
    return job


@transaction.atomic
def delete_draft(job: Job) -> None:
    if job.status != Job.Status.DRAFT:
        raise NotDraftError
    _emit(EventType.JOB_DELETED, job)
    job.delete()


def _emit(type: EventType, job: Job) -> None:
    emit(type, entity_type="job", entity_id=job.id, label=job.title)


def _has_must_have(job: Job) -> bool:
    return job.requirements.filter(kind=Requirement.Kind.MUST).exists()


def _sync(queryset, items: Sequence, build, attrs: tuple[str, ...], field: str) -> None:
    """Make the rows match `items`, in order: update by id, create the rest, drop the missing.

    Ids are kept for unchanged items, so anything that points at a requirement
    or stage (screening evidence, applications) survives an edit.
    """
    existing = {row.id: row for row in queryset}
    kept: set[int] = set()
    for position, item in enumerate(items):
        if item.id is not None:
            row = existing.get(item.id)
            if row is None or item.id in kept:
                raise UnknownItemError(field, item.id)
            kept.add(item.id)
        else:
            row = build()
        for attr in attrs:
            setattr(row, attr, getattr(item, attr))
        row.position = position
        row.save()
    for row_id, row in existing.items():
        if row_id not in kept:
            try:
                row.delete()
            except ProtectedError as exc:
                raise StageInUseError from exc
