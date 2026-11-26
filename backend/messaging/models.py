from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from candidates.models import Application
from tenancy.models import TenantModel


class TemplateKind(models.TextChoices):
    APPLICATION_RECEIVED = "application_received", _("Application received")
    STAGE_ADVANCED = "stage_advanced", _("Moved forward")
    REJECTION = "rejection", _("Not moving forward")
    INTERVIEW_INVITATION = "interview_invitation", _("Interview invitation")


class EmailTemplate(TenantModel):
    """A company's own wording for one kind of email, in one language.

    Only customized templates are stored; without a row, Terna's default text
    is used. Resetting to the default deletes the row.
    """

    kind = models.CharField(_("kind"), max_length=30, choices=TemplateKind.choices)
    language = models.CharField(_("language"), max_length=5, choices=settings.LANGUAGES)
    subject = models.CharField(_("subject"), max_length=200)
    body = models.TextField(_("body"), max_length=5000)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by_name = models.CharField(_("updated by"), max_length=150, blank=True)

    class Meta:
        verbose_name = _("email template")
        verbose_name_plural = _("email templates")
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["company", "kind", "language"], name="messaging_template_once"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} ({self.language})"


class EmailMessage(TenantModel):
    """One email to one candidate, exactly as written when it was queued."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("Queued")
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")
        CANCELED = "canceled", _("Canceled")

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="emails",
        verbose_name=_("application"),
    )
    kind = models.CharField(_("kind"), max_length=30, choices=TemplateKind.choices)
    language = models.CharField(_("language"), max_length=5, choices=settings.LANGUAGES)
    to = models.EmailField(_("to"))
    subject = models.CharField(_("subject"), max_length=200)
    body = models.TextField(_("body"), max_length=5000)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.QUEUED
    )
    # Empty: as soon as possible.
    scheduled_for = models.DateTimeField(_("scheduled for"), null=True, blank=True)
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    failure_reason = models.CharField(_("failure reason"), max_length=500, blank=True)
    created_by_name = models.CharField(_("created by"), max_length=150, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("email message")
        verbose_name_plural = _("email messages")
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.kind} to {self.to} ({self.status})"
