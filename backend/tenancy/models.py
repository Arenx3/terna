import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from tenancy import db
from tenancy.context import require_company_id

# Tables without customer data. Every other table must belong to a company
# (a `company_id` column, isolated by row-level security); a test fails otherwise.
GLOBAL_TABLES = frozenset(
    {
        "django_migrations",
        "django_content_type",
        "auth_permission",
        "auth_group",
        "auth_group_permissions",
        "auth_user",
        "auth_user_groups",
        "auth_user_user_permissions",
        # People are global: one person can belong to several companies.
        "accounts_user",
        "token_blacklist_outstandingtoken",
        "token_blacklist_blacklistedtoken",
    }
)


class CurrentCompany(models.Func):
    """The company of the current transaction, as the database sees it (NULL if none)."""

    function = db.CURRENT_COMPANY_FUNCTION
    template = "%(function)s()"
    output_field = models.UUIDField()


class TenantManager(models.Manager):
    """Scopes every query to the active company, in SQL, as defense in depth.

    It repeats the row-level security predicate, so a table whose policy were
    ever dropped would still not leak. The predicate is evaluated by the
    database at query time, so class-level querysets stay correct.
    """

    def __init__(self, field: str = "company_id") -> None:
        super().__init__()
        # Not `self.field`: Django's related managers (job.requirements) set that
        # attribute to the foreign key, which would break the filter below.
        self.tenant_field = field

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(**{self.tenant_field: CurrentCompany()})


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=200)
    # The company's address on its public careers page: /careers/<slug>.
    slug = models.SlugField(_("slug"), max_length=60, unique=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    # Row-level security on this table keys on the primary key, not on company_id.
    tenant_column = "id"

    objects = TenantManager(field="id")
    # Still under row-level security: only drops the Django-level filter.
    all_objects = models.Manager()  # noqa: DJ012 (ruff only treats "objects" as a manager)

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")

    def __str__(self) -> str:
        return self.name


class TenantModel(models.Model):
    """Base for every model with customer data.

    Migrations enable row-level security on each subclass's table (see
    `tenancy.signals`). New rows take the active company automatically.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="+",
        editable=False,
        verbose_name=_("company"),
    )

    tenant_column = "company_id"

    objects = TenantManager()
    all_objects = models.Manager()  # noqa: DJ012 (ruff only treats "objects" as a manager)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs) -> None:
        if self.company_id is None:
            self.company_id = require_company_id()
        super().save(*args, **kwargs)
