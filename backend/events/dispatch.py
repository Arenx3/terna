"""Delivering outbox events to their consumers, at least once.

Each batch runs in one transaction that locks its events (SKIP LOCKED, so two
dispatchers never take the same event), hands each one to every consumer and
marks it dispatched. If the worker dies halfway, the transaction rolls back
and the events stay pending for the next run. Consumers must be idempotent.
"""

import logging
import uuid
from collections.abc import Callable

from django.db import connection, transaction
from django.utils import timezone

from events.models import AuditEvent, OutboxEvent
from tenancy.context import tenant_context

logger = logging.getLogger(__name__)

PENDING_COMPANIES_FUNCTION = "app_outbox_pending_companies"
BATCH_SIZE = 100
# Then the event is parked as failed, with its reason, for someone to look at.
MAX_ATTEMPTS = 8

Consumer = Callable[[OutboxEvent], None]


def record_audit(event: OutboxEvent) -> None:
    """Copy the event into the audit log. A second delivery inserts nothing."""
    AuditEvent.objects.bulk_create(
        [
            AuditEvent(
                company_id=event.company_id,
                source_event_id=event.id,
                type=event.type,
                actor_id=event.actor_id,
                actor_name=event.actor_name,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                entity_label=event.entity_label,
                payload=event.payload,
                occurred_at=event.occurred_at,
            )
        ],
        ignore_conflicts=True,
    )


# Notifications, real-time updates and analytics subscribe here as they arrive.
CONSUMERS: list[Consumer] = [record_audit]


def pending_companies() -> list[uuid.UUID]:
    """Companies with undelivered events. Row-level security hides the others'
    outbox, so this goes through a SECURITY DEFINER function that returns ids only."""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {PENDING_COMPANIES_FUNCTION}()")  # noqa: S608 (constant)
        return [row[0] for row in cursor.fetchall()]


def dispatch_all() -> int:
    return sum(dispatch_company(company_id) for company_id in pending_companies())


def dispatch_company(company_id: uuid.UUID) -> int:
    """Deliver one company's pending events, oldest first. Returns how many were delivered."""
    delivered = 0
    after = 0  # each event is tried once per run, even if it fails
    while True:
        with tenant_context(company_id):
            batch = list(
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.Status.PENDING, id__gt=after)
                .order_by("id")[:BATCH_SIZE]
            )
            for event in batch:
                delivered += deliver(event)
        if len(batch) < BATCH_SIZE:
            return delivered
        after = batch[-1].id


def deliver(event: OutboxEvent) -> bool:
    event.attempts += 1
    try:
        # A savepoint: a consumer that fails undoes only its own writes.
        with transaction.atomic():
            for consumer in CONSUMERS:
                consumer(event)
    except Exception as exc:
        event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        if event.attempts >= MAX_ATTEMPTS:
            event.status = OutboxEvent.Status.FAILED
        event.save(update_fields=["attempts", "last_error", "status"])
        logger.exception(
            "Outbox event %s (%s) failed on attempt %s", event.id, event.type, event.attempts
        )
        return False
    event.status = OutboxEvent.Status.DISPATCHED
    event.dispatched_at = timezone.now()
    event.save(update_fields=["attempts", "status", "dispatched_at"])
    return True
