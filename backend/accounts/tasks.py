from smtplib import SMTPException

from celery import shared_task

from accounts import emails
from accounts.models import Invitation, User
from tenancy.models import Company
from tenancy.tasks import tenant_task


@shared_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=6,
)
def send_account_email(kind: str, user_id: str) -> None:
    """Users are global, so no company is needed. Links are signed at send time."""
    user = User.objects.filter(id=user_id).first()
    if user is not None:
        emails.send_account_email(kind, user)


@tenant_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=6,
)
def send_invitation_email(company_id: str, invitation_id: int, token: str) -> None:
    """Runs as the inviting company. Skips invitations revoked before sending."""
    invitation = (
        Invitation.objects.select_related("invited_by")
        .filter(id=invitation_id, accepted_at__isnull=True, revoked_at__isnull=True)
        .first()
    )
    if invitation is not None:
        company_name = Company.objects.values_list("name", flat=True).get()
        emails.send_invitation_email(invitation, company_name, token)
