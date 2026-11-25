from smtplib import SMTPException

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

from candidates import storage
from candidates.models import Application
from tenancy.models import Company
from tenancy.tasks import tenant_task


@tenant_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=6,
)
def send_application_received(company_id: str, application_id: int) -> None:
    """Confirms receipt to the candidate, in the language they applied in."""
    application = (
        Application.objects.select_related("candidate", "job").filter(id=application_id).first()
    )
    if application is None:
        return
    candidate = application.candidate
    language = candidate.language if candidate.language in ("es", "en") else "en"
    folder = f"candidates/emails/{language}"
    context = {
        "name": candidate.full_name.split(" ")[0],
        "job": application.job.title,
        "company": Company.objects.values_list("name", flat=True).get(),
    }
    subject = render_to_string(f"{folder}/application_received_subject.txt", context).strip()
    body = render_to_string(f"{folder}/application_received.txt", context)
    send_mail(subject, body, None, [candidate.email])


@shared_task(ignore_result=True)
def purge_incoming_uploads() -> int:
    """Hourly: delete uploads older than a day that never became an application."""
    return storage.purge_incoming()
