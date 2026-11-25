import io
import zipfile

import pytest
from botocore.exceptions import ClientError
from django.core import signing
from django.core.cache import cache
from rest_framework.test import APIClient

from candidates import services
from conftest import TEST_BUCKET
from core.storage import s3_client

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer\n%%EOF\n"


def docx_bytes(with_document: bool = True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        if with_document:
            archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def _isolated_storage_and_throttles(test_bucket):
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def instant(monkeypatch):
    """Skip the minimum time a person needs to fill the form."""
    monkeypatch.setattr(services, "MIN_FORM_SECONDS", 0)


@pytest.fixture
def open_job(acme, job_payload):
    client = acme.client("recruiter")
    job = client.post("/api/jobs/", job_payload(), format="json").json()
    client.post(f"/api/jobs/{job['id']}/publish/")
    return job


class Visitor:
    """A browser on the careers page: opens the form, uploads, applies."""

    def __init__(self, team, job: dict) -> None:
        self.client = APIClient()
        self.base = f"/api/careers/{team.company.slug}/jobs/{job['id']}"

    def open_form(self) -> str:
        return self.client.get(f"{self.base}/apply/").json()["form_token"]

    def upload(self, content: bytes, content_type: str = "application/pdf", **extra) -> str:
        response = self.client.post(
            f"{self.base}/uploads/",
            {
                "form_token": extra.pop("form_token", None) or self.open_form(),
                "consent": True,
                "filename": "cv.pdf" if content_type == "application/pdf" else "cv.docx",
                "content_type": content_type,
                "size": len(content) or 1,
                **extra,
            },
            format="json",
        )
        assert response.status_code == 201, response.json()
        ticket = response.json()["ticket"]
        # What the browser does with the presigned URL, through the internal endpoint.
        key = self.key(ticket)
        s3_client().put_object(Bucket=TEST_BUCKET, Key=key, Body=content, ContentType=content_type)
        return ticket

    @staticmethod
    def key(ticket: str) -> str:
        return signing.loads(ticket, salt=services.UPLOAD_SALT)["k"]

    def apply(self, ticket: str, headers: dict | None = None, **fields):
        payload = {
            "form_token": self.open_form(),
            "upload": ticket,
            "consent": True,
            "notice_version": services.PRIVACY_NOTICE_VERSION,
            "full_name": "Lucía Torres",
            "email": "Lucia@Example.com",
            "phone": "+52 81 5555 0101",
            **fields,
        }
        return self.client.post(f"{self.base}/apply/", payload, format="json", **(headers or {}))


@pytest.fixture
def visitor(acme, open_job):
    return Visitor(acme, open_job)


def stored(key: str) -> bool:
    try:
        s3_client().head_object(Bucket=TEST_BUCKET, Key=key)
    except ClientError:
        return False
    return True
