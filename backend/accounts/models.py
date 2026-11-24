import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tenancy.models import TenantModel


def normalize_email(email: str | None) -> str:
    """One account per address, whatever the casing or surrounding spaces."""
    return (email or "").strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **fields) -> "User":
        email = normalize_email(email)
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email, **fields)
        user.set_password(password)  # None leaves an unusable password
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email: str) -> "User":
        return self.get(email=normalize_email(email))


class User(AbstractBaseUser):
    """A person. Global: the same person can belong to several companies (Membership)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email"), unique=True)
    full_name = models.CharField(_("full name"), max_length=150)
    language = models.CharField(
        _("language"), max_length=5, choices=settings.LANGUAGES, default="en"
    )
    email_verified_at = models.DateTimeField(_("email verified at"), null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]  # noqa: RUF012 (Django API)

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [  # noqa: RUF012 (Django API)
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")), name="accounts_user_email_lowercase"
            ),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = normalize_email(self.email)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


class Membership(TenantModel):
    """A person's role in a company. Tenant data: isolated by row-level security."""

    class Role(models.TextChoices):
        ADMIN = "admin", _("Admin")
        RECRUITER = "recruiter", _("Recruiter")
        HIRING_MANAGER = "hiring_manager", _("Hiring manager")
        INTERVIEWER = "interviewer", _("Interviewer")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("user"),
    )
    role = models.CharField(_("role"), max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        constraints = [  # noqa: RUF012 (Django API)
            models.UniqueConstraint(
                fields=["company", "user"], name="accounts_membership_one_per_company"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.company_id} ({self.role})"
