"""Résumé files in object storage. Browsers upload and download directly;
Django only signs URLs and reads a few bytes to check what a file really is."""

import uuid
from datetime import timedelta

from botocore.exceptions import ClientError
from django.conf import settings
from django.utils import timezone

from candidates.models import Resume
from core.storage import s3_client

MAX_RESUME_BYTES = 10 * 1024 * 1024
CONTENT_TYPES = {
    "application/pdf": Resume.Format.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": Resume.Format.DOCX,
}
UPLOAD_URL_SECONDS = 15 * 60
DOWNLOAD_URL_SECONDS = 5 * 60
INCOMING_PREFIX = "incoming/"
# A DOCX is a ZIP whose central directory, at the end, lists word/document.xml.
ZIP_TAIL_BYTES = 64 * 1024


class InvalidResumeError(ValueError):
    """The uploaded file is missing, empty, too big, or not really a PDF or DOCX."""


def incoming_key(company_id, extension: str) -> str:
    return f"{INCOMING_PREFIX}{company_id}/{uuid.uuid4()}.{extension}"


def upload_url(key: str, content_type: str) -> str:
    """A URL the browser PUTs the file to, valid for 15 minutes, for this key and type only."""
    return s3_client(public=True).generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.STORAGE_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=UPLOAD_URL_SECONDS,
    )


def download_url(key: str, filename: str, *, inline: bool = False) -> str:
    """Five minutes to open or download the file, straight from storage."""
    safe_name = filename.replace('"', "")
    disposition = "inline" if inline else "attachment"
    return s3_client(public=True).generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.STORAGE_BUCKET,
            "Key": key,
            "ResponseContentDisposition": f'{disposition}; filename="{safe_name}"',
        },
        ExpiresIn=DOWNLOAD_URL_SECONDS,
    )


def _read(client, key: str, byte_range: str) -> bytes:
    response = client.get_object(Bucket=settings.STORAGE_BUCKET, Key=key, Range=byte_range)
    return response["Body"].read()


def inspect(key: str) -> tuple[int, str]:
    """(size, format) of an uploaded file, judged by its bytes, not its name or headers."""
    client = s3_client()
    try:
        size = client.head_object(Bucket=settings.STORAGE_BUCKET, Key=key)["ContentLength"]
    except ClientError as exc:
        raise InvalidResumeError("missing") from exc
    if size == 0:
        raise InvalidResumeError("empty")
    if size > MAX_RESUME_BYTES:
        raise InvalidResumeError("too_large")
    head = _read(client, key, "bytes=0-7")
    if head.startswith(b"%PDF-"):
        return size, Resume.Format.PDF
    if head.startswith(b"PK\x03\x04"):
        tail = _read(client, key, f"bytes=-{min(size, ZIP_TAIL_BYTES)}")
        if b"PK\x05\x06" in tail and b"word/document.xml" in tail:
            return size, Resume.Format.DOCX
    raise InvalidResumeError("wrong_type")


def promote(key: str, company_id, extension: str) -> str:
    """Move an accepted upload out of the incoming area, inside storage."""
    final_key = f"resumes/{company_id}/{uuid.uuid4()}.{extension}"
    client = s3_client()
    client.copy_object(
        Bucket=settings.STORAGE_BUCKET,
        Key=final_key,
        CopySource={"Bucket": settings.STORAGE_BUCKET, "Key": key},
    )
    client.delete_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    return final_key


def discard(key: str) -> None:
    s3_client().delete_object(Bucket=settings.STORAGE_BUCKET, Key=key)


def purge_incoming(older_than: timedelta = timedelta(hours=24)) -> int:
    """Delete uploads that were never turned into an application."""
    client = s3_client()
    cutoff = timezone.now() - older_than
    removed = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.STORAGE_BUCKET, Prefix=INCOMING_PREFIX):
        stale = [
            {"Key": item["Key"]}
            for item in page.get("Contents", [])
            if item["LastModified"] < cutoff
        ]
        if stale:
            client.delete_objects(Bucket=settings.STORAGE_BUCKET, Delete={"Objects": stale})
            removed += len(stale)
    return removed
