"""Applying to a job from the public careers page.

1. The apply form asks for a form token when it opens (it times the visit).
2. With consent given, the browser asks for an upload ticket and PUTs the
   résumé straight to storage.
3. It submits the form. The file is checked by its bytes, moved out of the
   upload area, and the candidate, application and consent are saved together.
"""

import logging
import time
from dataclasses import dataclass
from types import SimpleNamespace

from django.core import signing
from django.db import IntegrityError, transaction

from accounts.models import normalize_email
from candidates import storage
from candidates.models import Application, Candidate, ConsentRecord, Resume
from events.models import EventType
from events.outbox import emit
from jobs.models import Job
from messaging import sending
from messaging.models import TemplateKind

logger = logging.getLogger(__name__)

# Bump when the privacy notice text changes: consent is recorded per version.
PRIVACY_NOTICE_VERSION = "2026-11-25"

FORM_SALT = "candidates.apply-form"
UPLOAD_SALT = "candidates.resume-upload"
# A person needs a few seconds to fill the form; a script needs none.
MIN_FORM_SECONDS = 3
FORM_MAX_AGE = 2 * 60 * 60
UPLOAD_MAX_AGE = 60 * 60


class ApplyError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Applicant:
    full_name: str
    email: str
    phone: str
    language: str
    ip_address: str | None
    user_agent: str


def form_token(job: Job) -> str:
    return signing.dumps({"j": str(job.id), "t": time.time()}, salt=FORM_SALT)


def check_form(token: str, job: Job, *, submitting: bool) -> None:
    try:
        form = signing.loads(token, salt=FORM_SALT, max_age=FORM_MAX_AGE)
    except signing.BadSignature as exc:
        raise ApplyError("form_expired") from exc
    if form.get("j") != str(job.id):
        raise ApplyError("form_expired")
    if submitting and time.time() - form["t"] < MIN_FORM_SECONDS:
        raise ApplyError("too_fast")


def upload_ticket(job: Job, *, filename: str, content_type: str) -> tuple[str, str]:
    """(ticket, url): the browser PUTs the file to `url` and sends `ticket` with the form."""
    extension = storage.CONTENT_TYPES[content_type]
    key = storage.incoming_key(job.company_id, extension)
    ticket = signing.dumps({"k": key, "j": str(job.id), "n": filename[:255]}, salt=UPLOAD_SALT)
    return ticket, storage.upload_url(key, content_type)


def _read_ticket(ticket: str, job: Job) -> dict:
    try:
        upload = signing.loads(ticket, salt=UPLOAD_SALT, max_age=UPLOAD_MAX_AGE)
    except signing.BadSignature as exc:
        raise ApplyError("upload_expired") from exc
    if upload.get("j") != str(job.id):
        raise ApplyError("upload_expired")
    return upload


def discard_upload(ticket: str, job: Job) -> None:
    """Throw away an upload that won't become an application (a bot, a repeat)."""
    try:
        storage.discard(_read_ticket(ticket, job)["k"])
    except Exception:
        logger.warning("Could not discard an unused upload", exc_info=True)


def apply(job: Job, applicant: Applicant, ticket: str) -> tuple[Application, bool]:
    """Create the application, or return the existing one. Runs as the job's company.

    Returns (application, created). Applying twice to the same job keeps the
    first application and discards the second file.
    """
    upload = _read_ticket(ticket, job)
    try:
        size, file_format = storage.inspect(upload["k"])
    except storage.InvalidResumeError as exc:
        discard_upload(ticket, job)
        raise ApplyError(f"resume_{exc}") from exc

    email = normalize_email(applicant.email)
    existing = Application.objects.filter(job=job, candidate__email=email).first()
    if existing is not None:
        discard_upload(ticket, job)
        return existing, False

    final_key = storage.promote(upload["k"], job.company_id, file_format)
    try:
        with transaction.atomic():
            candidate, _ = Candidate.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": applicant.full_name,
                    "phone": applicant.phone,
                    "language": applicant.language,
                },
            )
            resume = Resume.objects.create(
                candidate=candidate,
                storage_key=final_key,
                filename=upload["n"],
                format=file_format,
                size=size,
            )
            application = Application.objects.create(
                job=job,
                candidate=candidate,
                stage=job.stages.order_by("position").first(),
                resume=resume,
            )
            ConsentRecord.objects.create(
                candidate=candidate,
                application=application,
                notice_version=PRIVACY_NOTICE_VERSION,
                purpose=ConsentRecord.Purpose.RECRUITMENT,
                ip_address=applicant.ip_address,
                user_agent=applicant.user_agent[:300],
            )
            emit(
                EventType.APPLICATION_SUBMITTED,
                entity_type="application",
                entity_id=application.id,
                label=job.title,
                payload={"job_id": str(job.id)},
                # Candidates have no account: the event names them, without a user id.
                actor=SimpleNamespace(id=None, full_name=candidate.full_name),
            )
            # The confirmation, in the company's own words and the candidate's language.
            sending.queue_from_template(application, TemplateKind.APPLICATION_RECEIVED)
    except IntegrityError:
        # The same person submitted twice at the same moment: keep the first.
        storage.discard(final_key)
        return Application.objects.get(job=job, candidate__email=email), False
    except Exception:
        storage.discard(final_key)
        raise

    return application, True
