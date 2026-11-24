from smtplib import SMTPException

from celery import shared_task

from accounts import emails
from accounts.models import User


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
