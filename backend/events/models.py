from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tenancy.models import TenantModel


class EventType(models.TextChoices):
    """Every domain event Terna records. Values never change: clients key on them."""

    JOB_CREATED = "job.created", _("Job created")
    JOB_PUBLISHED = "job.published", _("Job published")
    JOB_REOPENED = "job.reopened", _("Job reopened")
    JOB_CLOSED = "job.closed", _("Job closed")
    JOB_DELETED = "job.deleted", _("Draft job deleted")
    MEMBER_JOINED = "member.joined", _("Member joined")
    MEMBER_ROLE_CHANGED = "member.role_changed", _("Member role changed")
    MEMBER_REMOVED = "member.removed", _("Member removed")
    INVITATION_SENT = "invitation.sent", _("Invitation sent")
    INVITATION_REVOKED = "invitation.revoked", _("Invitation cancelled")


class EventFields(models.Model):
    """What happened, who did it and to what, as it was at that moment.

    The actor and the entity are copied, not linked: an event must still read
    correctly after the person leaves or the job is deleted, and a foreign key
    would make the database rewrite audit rows (SET NULL) on those deletions.
    """

    type = models.CharField(_("type"), max_length=64, choices=EventType.choices)
    actor_id = models.UUIDField(_("actor"), null=True, blank=True)
    actor_name = models.CharField(_("actor name"), max_length=150, blank=True)
    entity_type = models.CharField(_("entity type"), max_length=40)
    entity_id = models.CharField(_("entity id"), max_length=64)
    entity_label = models.CharField(_("entity label"), max_length=300, blank=True)
    payload = models.JSONField(_("payload"), default=dict, encoder=DjangoJSONEncoder)
    occurred_at = models.DateTimeField(_("occurred at"), default=timezone.now)

    class Meta:
        abstract = True


class OutboxEvent(TenantModel, EventFields):
    """A domain event, written in the same transaction as the change it describes.

    A rolled-back change leaves no event; a committed one is delivered at
    least once by the dispatcher, so every consumer must be idempotent.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        DISPATCHED = "dispatched", _("Dispatched")
        FAILED = "failed", _("Failed")

    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    last_error = models.TextField(_("last error"), blank=True)
    dispatched_at = models.DateTimeField(_("dispatched at"), null=True, blank=True)

    class Meta:
        verbose_name = _("outbox event")
        verbose_name_plural = _("outbox events")
        indexes = [  # noqa: RUF012 (Django API)
            # The dispatcher only ever looks for pending events, oldest first.
            models.Index(
                fields=["company", "id"],
                condition=Q(status="pending"),
                name="events_outbox_pending",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} #{self.id} ({self.status})"


class AuditEvent(TenantModel, EventFields):
    """The append-only audit log. A database trigger rejects UPDATE and DELETE."""

    # One row per outbox event, whatever the number of deliveries.
    source_event_id = models.BigIntegerField(_("source event"), unique=True, editable=False)
    recorded_at = models.DateTimeField(_("recorded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("audit event")
        verbose_name_plural = _("audit events")
        indexes = [  # noqa: RUF012 (Django API)
            models.Index(fields=["company", "-occurred_at"], name="events_audit_recent"),
            models.Index(fields=["company", "type"], name="events_audit_type"),
            models.Index(fields=["company", "actor_id"], name="events_audit_actor"),
        ]

    def __str__(self) -> str:
        return f"{self.type} by {self.actor_name or 'Terna'}"
