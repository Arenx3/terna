import time

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.storage import s3_client

STORAGE_ATTEMPTS = 10
STORAGE_RETRY_SECONDS = 3


class Command(BaseCommand):
    help = "Apply migrations and create the storage bucket. Safe to run on every start."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=options["verbosity"])
        self.ensure_bucket()

    def ensure_bucket(self) -> None:
        bucket = settings.STORAGE_BUCKET
        client = s3_client()
        for attempt in range(1, STORAGE_ATTEMPTS + 1):
            try:
                client.head_bucket(Bucket=bucket)
                self.stdout.write(f"Bucket {bucket!r} already exists.")
                return
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket", "NotFound"}:
                    error: Exception = exc
                else:
                    client.create_bucket(Bucket=bucket)
                    self.stdout.write(self.style.SUCCESS(f"Created bucket {bucket!r}."))
                    return
            except BotoCoreError as exc:
                error = exc
            self.stderr.write(f"Storage not ready ({error}); retry {attempt}/{STORAGE_ATTEMPTS}.")
            time.sleep(STORAGE_RETRY_SECONDS)
        raise CommandError(f"Could not reach storage to create bucket {bucket!r}.")
