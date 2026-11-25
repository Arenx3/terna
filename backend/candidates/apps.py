from django.apps import AppConfig


class CandidatesConfig(AppConfig):
    name = "candidates"

    def ready(self) -> None:
        # Through the outbox: live boards hear about new and moved candidates,
        # and mentions and assignments become notifications.
        from candidates import collaboration, realtime
        from events import dispatch

        for consumer in (realtime.broadcast, collaboration.notify):
            if consumer not in dispatch.CONSUMERS:
                dispatch.CONSUMERS.append(consumer)
