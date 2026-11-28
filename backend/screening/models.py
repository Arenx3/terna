from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

from candidates.models import Application, Resume
from jobs.models import Requirement
from tenancy.models import TenantModel

# Size of the vectors the embedding model returns (see `screening.embeddings`).
DIMENSIONS = 384


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
    language = models.CharField(_("language"), max_length=5, blank=True)
    # Passages redacted by an older version of the rules are redacted again.
    redaction_version = models.PositiveSmallIntegerField(_("redaction version"), default=0)
    # The model that embedded the passages; another model's vectors aren't comparable.
    embedding_model = models.CharField(_("embedding model"), max_length=120, blank=True)
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
    # What the AI reads: personal data replaced by markers ([NOMBRE], [TELÉFONO]).
    redacted = models.TextField(_("redacted text"), max_length=2000, blank=True)
    # The spans of `text` that were replaced: [{"kind", "start", "end"}].
    redactions = models.JSONField(_("redactions"), default=list, blank=True)
    # The meaning of the redacted text, for semantic matching across languages.
    embedding = VectorField(_("embedding"), dimensions=DIMENSIONS, null=True, blank=True)

    class Meta:
        verbose_name = _("résumé passage")
        verbose_name_plural = _("résumé passages")
        ordering = ["resume", "position"]  # noqa: RUF012 (Django API)
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["resume", "position"], name="screening_passage_position_once"
            ),
        ]
        indexes = [  # noqa: RUF012 (Django API)
            # For searching every candidate by meaning ("who has run Kubernetes?"). Matching
            # one application compares its few passages exactly and doesn't need it.
            HnswIndex(
                name="screening_passage_embedding",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.resume_id} #{self.position} ({self.section})"


class RequirementVector(TenantModel):
    """A requirement's embedding, kept until its text or the model changes."""

    requirement = models.OneToOneField(
        Requirement,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="vector",
        verbose_name=_("requirement"),
    )
    text = models.CharField(_("text"), max_length=300)
    model = models.CharField(_("model"), max_length=120)
    embedding = VectorField(_("embedding"), dimensions=DIMENSIONS)

    class Meta:
        verbose_name = _("requirement vector")
        verbose_name_plural = _("requirement vectors")

    def __str__(self) -> str:
        return self.text


class Synonym(TenantModel):
    """A company's own words for a skill, or its correction of an entry Terna ships with.

    "k8s", "EKS" and "Kubernetes" meet the same requirement. A row whose term
    matches a built-in entry replaces it, so a company can also take aliases away.
    """

    term = models.CharField(_("term"), max_length=80)
    # The term without accents or case: what makes two entries the same.
    key = models.CharField(_("key"), max_length=80, editable=False)
    aliases = models.JSONField(_("aliases"), default=list)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("synonym")
        verbose_name_plural = _("synonyms")
        ordering = ["key"]  # noqa: RUF012 (Django API)
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(fields=["company", "key"], name="screening_synonym_once"),
        ]

    def __str__(self) -> str:
        return self.term


class Screening(TenantModel):
    """How an application's résumé measures up to its job's requirements.

    Counts of verdicts, never a score of its own: every verdict has its
    evidence in `RequirementMatch`, and the person reviewing decides.
    """

    class Status(models.TextChoices):
        # The résumé hasn't been read (yet, or it couldn't be): nothing to compare.
        WAITING = "waiting", _("Waiting for the résumé")
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        READY = "ready", _("Ready")
        FAILED = "failed", _("Failed")

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="screening",
        verbose_name=_("application"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    detail = models.CharField(_("detail"), max_length=500, blank=True)
    # Each run claims the row by bumping this; a run only writes back its own result.
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    # Screenings done by an older version of the rules are done again.
    version = models.PositiveSmallIntegerField(_("version"), default=0)
    must_total = models.PositiveSmallIntegerField(_("must-haves"), default=0)
    must_meets = models.PositiveSmallIntegerField(_("must-haves met"), default=0)
    must_partial = models.PositiveSmallIntegerField(_("must-haves partly met"), default=0)
    nice_total = models.PositiveSmallIntegerField(_("nice-to-haves"), default=0)
    nice_meets = models.PositiveSmallIntegerField(_("nice-to-haves met"), default=0)
    nice_partial = models.PositiveSmallIntegerField(_("nice-to-haves partly met"), default=0)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("screening")
        verbose_name_plural = _("screenings")

    def __str__(self) -> str:
        return f"{self.application_id} ({self.status})"


class Verdict(models.TextChoices):
    MEETS = "meets", _("Meets")
    PARTIAL = "partial", _("Partly meets")
    NO_EVIDENCE = "no_evidence", _("No evidence")


class RequirementMatch(TenantModel):
    """One requirement against one résumé: the verdict, its evidence and why."""

    screening = models.ForeignKey(
        Screening, on_delete=models.CASCADE, related_name="matches", verbose_name=_("screening")
    )
    requirement = models.ForeignKey(
        Requirement, on_delete=models.CASCADE, related_name="+", verbose_name=_("requirement")
    )
    verdict = models.CharField(_("verdict"), max_length=11, choices=Verdict.choices)
    # What each signal found: {"keyword": {...}, "semantic": {...}, "years": {...}}.
    signals = models.JSONField(_("signals"), default=dict)
    # Where in the résumé: [{"passage", "spans": [[start, end]], "signals": [...]}]. Offsets
    # point into the passage's original text, so the screen highlights them in place.
    evidence = models.JSONField(_("evidence"), default=list)

    class Meta:
        verbose_name = _("requirement match")
        verbose_name_plural = _("requirement matches")
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["screening", "requirement"], name="screening_match_once"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.requirement_id}: {self.verdict}"
