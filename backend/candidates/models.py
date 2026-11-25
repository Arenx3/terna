import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from jobs.models import Job, PipelineStage
from tenancy.models import TenantModel


class Candidate(TenantModel):
    """A person who applied to the company. One per company and email address.

    Personal data (LFPDPPP/GDPR): every candidate arrives with a consent record.
    """

    full_name = models.CharField(_("full name"), max_length=150)
    email = models.EmailField(_("email"))  # stored lowercased
    phone = models.CharField(_("phone"), max_length=40, blank=True)
    # The language they applied in: emails to them use it.
    language = models.CharField(
        _("language"), max_length=5, choices=settings.LANGUAGES, default="es"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("candidate")
        verbose_name_plural = _("candidates")
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["company", "email"], name="candidates_candidate_one_per_company"
            ),
        ]

    def __str__(self) -> str:
        return self.full_name


class Resume(TenantModel):
    """A résumé file in object storage. The bytes never pass through Django."""

    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        DOCX = "docx", "DOCX"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="resumes", verbose_name=_("candidate")
    )
    storage_key = models.CharField(_("storage key"), max_length=300, unique=True)
    filename = models.CharField(_("file name"), max_length=255)
    format = models.CharField(_("format"), max_length=4, choices=Format.choices)
    size = models.PositiveIntegerField(_("size in bytes"))
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("résumé")
        verbose_name_plural = _("résumés")

    def __str__(self) -> str:
        return self.filename


class Application(TenantModel):
    """A candidate applying to one job. Applying again changes nothing."""

    class Source(models.TextChoices):
        CAREERS = "careers", _("Careers page")

    class RejectionReason(models.TextChoices):
        REQUIREMENTS = "requirements", _("Doesn't meet the requirements")
        OTHER_CANDIDATE = "other_candidate", _("Another candidate was chosen")
        WITHDREW = "withdrew", _("Withdrew")
        NO_RESPONSE = "no_response", _("Stopped responding")
        COMPENSATION = "compensation", _("Compensation expectations")
        OTHER = "other", _("Other")

    job = models.ForeignKey(
        Job, on_delete=models.PROTECT, related_name="applications", verbose_name=_("job")
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("candidate"),
    )
    # PROTECT: a stage with people in it can't silently disappear from the pipeline.
    stage = models.ForeignKey(
        PipelineStage,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name=_("stage"),
    )
    resume = models.ForeignKey(
        Resume,
        on_delete=models.SET_NULL,
        null=True,
        related_name="applications",
        verbose_name=_("résumé"),
    )
    source = models.CharField(
        _("source"), max_length=20, choices=Source.choices, default=Source.CAREERS
    )
    stage_entered_at = models.DateTimeField(_("in this stage since"), default=timezone.now)
    # Why someone was rejected; empty in every other stage.
    rejection_reason = models.CharField(
        _("rejection reason"), max_length=20, choices=RejectionReason.choices, blank=True
    )
    rejection_note = models.TextField(_("rejection note"), blank=True, max_length=1000)
    created_at = models.DateTimeField(_("applied at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("application")
        verbose_name_plural = _("applications")
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["job", "candidate"], name="candidates_application_once_per_job"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.candidate_id} → {self.job_id}"


class ConsentRecord(TenantModel):
    """Proof that a candidate accepted a specific privacy notice, when and from where."""

    class Purpose(models.TextChoices):
        RECRUITMENT = "recruitment", _("Recruitment for the job applied to")

    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="consents", verbose_name=_("candidate")
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.SET_NULL,
        null=True,
        related_name="consents",
        verbose_name=_("application"),
    )
    notice_version = models.CharField(_("privacy notice version"), max_length=20)
    purpose = models.CharField(_("purpose"), max_length=20, choices=Purpose.choices)
    accepted_at = models.DateTimeField(_("accepted at"), default=timezone.now)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=300, blank=True)

    class Meta:
        verbose_name = _("consent record")
        verbose_name_plural = _("consent records")

    def __str__(self) -> str:
        return f"{self.candidate_id} accepted {self.notice_version}"
