"""Moving candidates through a job's pipeline."""

from django.db import transaction
from django.utils import timezone

from candidates.models import Application
from events.models import EventType
from events.outbox import emit
from jobs.models import PipelineStage, StageKind


class StageChangedError(Exception):
    """Someone else moved the candidate first; the caller's board is out of date."""

    def __init__(self, application: Application) -> None:
        super().__init__("stage changed")
        self.application = application


class ReasonRequiredError(Exception):
    """Rejecting someone needs a reason: it's what they and the analytics are told."""


class ForeignStageError(Exception):
    """The stage belongs to another job."""


def _describe(stage: PipelineStage) -> dict:
    return {"id": stage.id, "kind": stage.kind, "name": stage.name}


def move(
    application_id: int,
    stage: PipelineStage,
    *,
    expected_stage_id: int,
    reason: str = "",
    note: str = "",
) -> Application:
    """Move a candidate to `stage`, if they're still where the caller saw them.

    `expected_stage_id` makes concurrent moves safe: two recruiters dragging
    the same card can't silently overwrite each other; the second one is told.
    """
    with transaction.atomic():
        application = (
            Application.objects.select_for_update(of=("self",))
            .select_related("stage", "candidate", "job")
            .get(pk=application_id)
        )
        if stage.job_id != application.job_id:
            raise ForeignStageError
        if application.stage_id != expected_stage_id:
            raise StageChangedError(application)
        if stage.id == application.stage_id:
            return application
        rejecting = stage.kind == StageKind.REJECTED
        if rejecting and not reason:
            raise ReasonRequiredError

        previous = application.stage
        application.stage = stage
        application.stage_entered_at = timezone.now()
        application.rejection_reason = reason if rejecting else ""
        application.rejection_note = note if rejecting else ""
        application.save(
            update_fields=[
                "stage",
                "stage_entered_at",
                "rejection_reason",
                "rejection_note",
                "updated_at",
            ]
        )
        emit(
            EventType.APPLICATION_STAGE_CHANGED,
            entity_type="application",
            entity_id=application.id,
            label=application.candidate.full_name,
            payload={
                "job_id": str(application.job_id),
                "job_title": application.job.title,
                "from": _describe(previous),
                "to": _describe(stage),
                "reason": application.rejection_reason,
            },
        )
        return application
