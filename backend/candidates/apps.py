from django.apps import AppConfig


class CandidatesConfig(AppConfig):
    name = "candidates"

    def ready(self) -> None:
        # Live boards hear about new and moved candidates through the outbox.
        from candidates import realtime
        from events import dispatch

        if realtime.broadcast not in dispatch.CONSUMERS:
            dispatch.CONSUMERS.append(realtime.broadcast)
