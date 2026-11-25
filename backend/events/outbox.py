"""Emitting domain events: `emit()` inside the transaction that makes the change.

    with transaction.atomic():
        job.status = Job.Status.OPEN
        job.save()
        emit(EventType.JOB_PUBLISHED, entity=job, label=job.title)

The actor is whoever is acting in this request or task (`acting_as`); pass
`actor=` to name someone else, or `actor=None` for Terna itself.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from django.db import connection, transaction

from events.models import EventType, OutboxEvent

logger = logging.getLogger(__name__)

_actor: ContextVar[object | None] = ContextVar("event_actor", default=None)
_UNSET = object()


def current_actor():
    return _actor.get()


def set_actor(user) -> Token:
    """For request-scoped code (API views); everything else uses `acting_as`."""
    return _actor.set(user)


def reset_actor(token: Token) -> None:
    _actor.reset(token)


@contextmanager
def acting_as(user) -> Iterator[None]:
    """Attribute the events emitted inside the block to `user`."""
    token = _actor.set(user)
    try:
        yield
    finally:
        _actor.reset(token)


class OutsideTransactionError(RuntimeError):
    """An event emitted outside a transaction could outlive a change that rolls back."""


def emit(
    type: EventType,
    *,
    entity_type: str,
    entity_id: object,
    label: str = "",
    payload: dict | None = None,
    actor=_UNSET,
) -> OutboxEvent:
    if not connection.in_atomic_block:
        raise OutsideTransactionError("emit() must run inside the change's transaction.")
    who = current_actor() if actor is _UNSET else actor
    event = OutboxEvent.objects.create(
        type=type,
        actor_id=getattr(who, "id", None),
        actor_name=getattr(who, "full_name", ""),
        entity_type=entity_type,
        entity_id=str(entity_id),
        entity_label=label[:300],
        payload=payload or {},
    )
    # Deliver right away once committed. If the broker is down, beat retries later.
    transaction.on_commit(_kick, robust=True)
    return event


def _kick() -> None:
    from events.tasks import dispatch_outbox

    dispatch_outbox.delay()
