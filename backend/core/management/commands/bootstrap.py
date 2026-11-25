import time

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from config.env import env, env_bool
from core.storage import s3_client
from tenancy.db import ensure_app_role

STORAGE_ATTEMPTS = 10
STORAGE_RETRY_SECONDS = 3
MISSING_BUCKET_CODES = {"404", "NoSuchBucket", "NotFound"}


class Command(BaseCommand):
    help = (
        "Create the app database role, apply migrations, create the storage bucket and, "
        "unless DEMO_DATA=false, add the demo data. Runs as the migration role. "
        "Safe to run on every start."
    )

    def handle(self, *args, **options):
        self.ensure_app_role()
        call_command("migrate", interactive=False, verbosity=options["verbosity"])
        self.ensure_bucket()
        self.ensure_cors()
        if env_bool("DEMO_DATA", True):
            call_command("seed_demo")

    def ensure_app_role(self) -> None:
        role = settings.DATABASE_APP_ROLE
        if role == connection.settings_dict["USER"]:
            self.stdout.write("App and migration roles are the same; skipping role setup.")
            return
        password = env("POSTGRES_APP_PASSWORD")
        ensure_app_role(connection, role, password, connection.settings_dict["NAME"])
        self.stdout.write(f"Database role {role!r} is ready.")

    def ensure_bucket(self) -> None:
        bucket = settings.STORAGE_BUCKET
        client = s3_client()
        for attempt in range(1, STORAGE_ATTEMPTS + 1):
            try:
                client.head_bucket(Bucket=bucket)
                self.stdout.write(f"Bucket {bucket!r} already exists.")
                return
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in MISSING_BUCKET_CODES:
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

    def ensure_cors(self) -> None:
        """Let the app's own pages upload and download straight from storage, and no one else."""
        origins = sorted(set(settings.STORAGE_CORS_ORIGINS))
        s3_client().put_bucket_cors(
            Bucket=settings.STORAGE_BUCKET,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": origins,
                        "AllowedMethods": ["PUT", "GET"],
                        "AllowedHeaders": ["*"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            },
        )
        self.stdout.write(f"Storage accepts browser uploads from {', '.join(origins)}.")
