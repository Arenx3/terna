from celery import shared_task

from events.dispatch import dispatch_all


@shared_task(ignore_result=True)
def dispatch_outbox() -> int:
    """Deliver every company's pending events.

    Queued after each commit that emits events, and by beat every 30 seconds
    to pick up anything a crashed worker or an unreachable broker left behind.
    """
    return dispatch_all()
