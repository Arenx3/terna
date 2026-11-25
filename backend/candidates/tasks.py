from celery import shared_task

from candidates import storage


@shared_task(ignore_result=True)
def purge_incoming_uploads() -> int:
    """Hourly: delete uploads older than a day that never became an application."""
    return storage.purge_incoming()
