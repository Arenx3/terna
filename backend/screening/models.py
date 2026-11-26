from django.db import models
from django.utils.translation import gettext_lazy as _

from candidates.models import Resume
from tenancy.models import TenantModel


class Section(models.TextChoices):
    """Where a passage sits in the résumé. `header` is what comes before the first heading."""

    HEADER = "header", _("Header")
    SUMMARY = "summary", _("Summary")
    EXPERIENCE = "experience", _("Experience")
    EDUCATION = "education", _("Education")
    SKILLS = "skills", _("Skills")
    LANGUAGES = "languages", _("Languages")
    CERTIFICATIONS = "certifications", _("Certifications")
    OTHER = "other", _("Other")


class ResumeExtraction(TenantModel):
    """Whether a résumé's text has been read, and if not, why."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        READY = "ready", _("Ready")
        NEEDS_REVIEW = "needs_review", _("Needs review")
        FAILED = "failed", _("Failed")

    class Reason(models.TextChoices):
        NO_TEXT = "no_text", _("The file has no text to read, like a scanned page")
        ENCRYPTED = "encrypted", _("The file is password protected")
        UNREADABLE = "unreadable", _("The file is damaged or not a valid document")
        STORAGE = "storage", _("The file couldn't be read from storage")
        ERROR = "error", _("Unexpected error")

    resume = models.OneToOneField(
        Resume,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="extraction",
        verbose_name=_("résumé"),
    )
    status = models.CharField(
        _("status"), max_length=12, choices=Status.choices, default=Status.PENDING
    )
    reason = models.CharField(_("reason"), max_length=12, choices=Reason.choices, blank=True)
    detail = models.CharField(_("detail"), max_length=500, blank=True)
    pages = models.PositiveSmallIntegerField(_("pages"), default=0)
    # Each run claims the row by bumping this; a run only writes back its own result.
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    extracted_at = models.DateTimeField(_("extracted at"), null=True, blank=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("résumé extraction")
        verbose_name_plural = _("résumé extractions")

    def __str__(self) -> str:
        return f"{self.resume_id} ({self.status})"


class ResumePassage(TenantModel):
    """A line or entry of a résumé, small enough to cite as evidence for a requirement."""

    resume = models.ForeignKey(
        Resume, on_delete=models.CASCADE, related_name="passages", verbose_name=_("résumé")
    )
    page = models.PositiveSmallIntegerField(_("page"))
    position = models.PositiveSmallIntegerField(_("position"))
    section = models.CharField(_("section"), max_length=16, choices=Section.choices)
    text = models.TextField(_("text"), max_length=2000)
    # Date ranges found in the text: [{"text", "start", "end", "ongoing"}].
    periods = models.JSONField(_("periods"), default=list, blank=True)

    class Meta:
        verbose_name = _("résumé passage")
        verbose_name_plural = _("résumé passages")
        ordering = ["resume", "position"]  # noqa: RUF012 (Django API)
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["resume", "position"], name="screening_passage_position_once"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.resume_id} #{self.position} ({self.section})"
