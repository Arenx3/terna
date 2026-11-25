import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from tenancy.models import TenantModel


class StageKind(models.TextChoices):
    """What a pipeline stage means, whatever the company calls it.

    Analytics and automations key on the kind, so renaming a stage never
    breaks them. A pipeline always starts at `applied` and ends at `hired`
    and `rejected`; the stages in between are the company's own.
    """

    APPLIED = "applied", _("Applied")
    SCREENING = "screening", _("Screening")
    INTERVIEW = "interview", _("Interview")
    OFFER = "offer", _("Offer")
    HIRED = "hired", _("Hired")
    REJECTED = "rejected", _("Rejected")


class Job(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")

    class Workplace(models.TextChoices):
        ONSITE = "onsite", _("On-site")
        HYBRID = "hybrid", _("Hybrid")
        REMOTE = "remote", _("Remote")

    class Employment(models.TextChoices):
        FULL_TIME = "full_time", _("Full-time")
        PART_TIME = "part_time", _("Part-time")
        CONTRACT = "contract", _("Contract")
        INTERNSHIP = "internship", _("Internship")

    class Currency(models.TextChoices):
        MXN = "MXN", "MXN"
        USD = "USD", "USD"

    class SalaryPeriod(models.TextChoices):
        MONTH = "month", _("Per month")
        YEAR = "year", _("Per year")

    # A UUID, not a sequence: job links are public once the careers page exists.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_("title"), max_length=160)
    department = models.CharField(_("department"), max_length=120, blank=True)
    location = models.CharField(_("location"), max_length=160, blank=True)
    workplace = models.CharField(
        _("workplace"), max_length=10, choices=Workplace.choices, default=Workplace.ONSITE
    )
    employment = models.CharField(
        _("employment type"),
        max_length=12,
        choices=Employment.choices,
        default=Employment.FULL_TIME,
    )
    # The language the posting is written in; the careers page shows it as is.
    language = models.CharField(
        _("language"), max_length=5, choices=settings.LANGUAGES, default="es"
    )
    description = models.TextField(_("description"), blank=True, max_length=20_000)
    salary_min = models.PositiveIntegerField(_("minimum salary"), null=True, blank=True)
    salary_max = models.PositiveIntegerField(_("maximum salary"), null=True, blank=True)
    salary_currency = models.CharField(
        _("currency"), max_length=3, choices=Currency.choices, default=Currency.MXN
    )
    salary_period = models.CharField(
        _("salary period"), max_length=5, choices=SalaryPeriod.choices, default=SalaryPeriod.MONTH
    )
    status = models.CharField(
        _("status"), max_length=6, choices=Status.choices, default=Status.DRAFT
    )
    hiring_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("hiring manager"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    published_at = models.DateTimeField(_("first published at"), null=True, editable=False)
    closed_at = models.DateTimeField(_("closed at"), null=True, editable=False)

    class Meta:
        verbose_name = _("job")
        verbose_name_plural = _("jobs")
        indexes = [models.Index(fields=["company", "status"], name="jobs_job_company_status")]  # noqa: RUF012
        constraints = [  # noqa: RUF012 (Django API)
            models.CheckConstraint(
                condition=Q(salary_min__isnull=True)
                | Q(salary_max__isnull=True)
                | Q(salary_min__lte=F("salary_max")),
                name="jobs_job_salary_range",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class Requirement(TenantModel):
    """One thing the job needs. Screening judges each one and shows its evidence."""

    class Kind(models.TextChoices):
        MUST = "must", _("Must-have")
        NICE = "nice", _("Nice-to-have")

    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="requirements", verbose_name=_("job")
    )
    text = models.CharField(_("text"), max_length=300)
    kind = models.CharField(_("kind"), max_length=4, choices=Kind.choices)
    position = models.PositiveSmallIntegerField(_("position"))

    class Meta:
        verbose_name = _("requirement")
        verbose_name_plural = _("requirements")
        ordering = ["position"]  # noqa: RUF012

    def __str__(self) -> str:
        return self.text


class StageFields(models.Model):
    # Blank means "use the kind's label in the reader's language".
    name = models.CharField(_("name"), max_length=60, blank=True)
    kind = models.CharField(_("kind"), max_length=10, choices=StageKind.choices)
    position = models.PositiveSmallIntegerField(_("position"))

    class Meta:
        abstract = True
        ordering = ["position"]  # noqa: RUF012


class PipelineStage(TenantModel, StageFields):
    """A column of a job's pipeline."""

    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="stages", verbose_name=_("job")
    )

    class Meta(StageFields.Meta):
        verbose_name = _("pipeline stage")
        verbose_name_plural = _("pipeline stages")

    def __str__(self) -> str:
        return self.name or self.kind


class StageTemplate(TenantModel, StageFields):
    """The company's default pipeline, copied into each new job."""

    class Meta(StageFields.Meta):
        verbose_name = _("stage template")
        verbose_name_plural = _("stage templates")

    def __str__(self) -> str:
        return self.name or self.kind
