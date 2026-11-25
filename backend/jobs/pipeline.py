"""Pipeline shape rules, shared by the company template and each job."""

from collections.abc import Sequence
from dataclasses import dataclass

from django.utils.translation import gettext as _

from jobs.models import StageKind

MAX_STAGES = 12
CLOSING_KINDS = [StageKind.HIRED, StageKind.REJECTED]
MIDDLE_KINDS = frozenset({StageKind.SCREENING, StageKind.INTERVIEW, StageKind.OFFER})


@dataclass(frozen=True)
class Stage:
    kind: str
    name: str = ""
    id: int | None = None


# Names left blank: each reader sees the kind's label in their own language.
DEFAULT_PIPELINE: tuple[Stage, ...] = (
    Stage(StageKind.APPLIED),
    Stage(StageKind.SCREENING),
    Stage(StageKind.INTERVIEW),
    Stage(StageKind.OFFER),
    Stage(StageKind.HIRED),
    Stage(StageKind.REJECTED),
)


class PipelineShapeError(ValueError):
    pass


def check_shape(stages: Sequence[Stage]) -> None:
    """Applied first, hired and rejected last, the company's own stages in between.

    Fixed ends let analytics read any pipeline the same way: everyone enters
    at `applied` and leaves through `hired` or `rejected`.
    """
    kinds = [stage.kind for stage in stages]
    if len(kinds) > MAX_STAGES:
        message = _("A pipeline can have at most %(max)d stages.") % {"max": MAX_STAGES}
        raise PipelineShapeError(message)
    if len(kinds) < 3 or kinds[0] != StageKind.APPLIED or kinds[-2:] != CLOSING_KINDS:
        raise PipelineShapeError(
            _("A pipeline starts with Applied and ends with Hired and Rejected.")
        )
    if any(kind not in MIDDLE_KINDS for kind in kinds[1:-2]):
        raise PipelineShapeError(
            _("Stages in between can only be screening, interview or offer stages.")
        )
