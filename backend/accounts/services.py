from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction

from accounts.models import Membership, User, normalize_email
from accounts.tasks import send_account_email
from tenancy.context import tenant_context
from tenancy.services import create_company


def _email_later(kind: str, user: User) -> None:
    # Sent by a worker, and only once the transaction commits.
    user_id = str(user.id)
    transaction.on_commit(lambda: send_account_email.delay(kind, user_id))


def register_company(
    *, company_name: str, full_name: str, email: str, password: str, language: str
) -> None:
    """Create the company, its first admin and their membership, all or nothing.

    The caller always gets the same answer whether or not the address is taken,
    so sign-up cannot be used to discover who has an account. An existing
    owner gets an email saying so instead of a verification link.
    """
    email = normalize_email(email)
    existing = User.objects.filter(email=email).first()
    if existing is not None:
        make_password(password)  # same work as a real sign-up, so timing reveals nothing
        _email_later("account_exists", existing)
        return

    try:
        with transaction.atomic():
            user = User.objects.create_user(email, password, full_name=full_name, language=language)
            company = create_company(company_name)
            with tenant_context(company.id):
                Membership.objects.create(company=company, user=user, role=Membership.Role.ADMIN)
    except IntegrityError:
        # A concurrent sign-up took the address between the check and the insert.
        existing = User.objects.filter(email=email).first()
        if existing is not None:
            _email_later("account_exists", existing)
        return

    _email_later("verify_email", user)


def request_verification_email(email: str) -> None:
    user = User.objects.filter(email=normalize_email(email), is_active=True).first()
    if user is not None and not user.is_email_verified:
        _email_later("verify_email", user)


def request_password_reset(email: str) -> None:
    user = User.objects.filter(email=normalize_email(email), is_active=True).first()
    if user is not None and user.has_usable_password():
        _email_later("password_reset", user)
