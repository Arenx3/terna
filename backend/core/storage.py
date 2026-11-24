import boto3
from botocore.client import BaseClient
from botocore.config import Config
from django.conf import settings


def s3_client(*, public: bool = False) -> BaseClient:
    """S3 client for internal traffic, or for URLs that a browser will open when ``public`` is set."""
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_PUBLIC_URL if public else settings.STORAGE_ENDPOINT_URL,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
