from django.apps import AppConfig


class ScreeningConfig(AppConfig):
    name = "screening"

    def ready(self) -> None:
        # Every application that arrives has its résumé read, through the outbox:
        # a rolled-back application never reaches the worker.
        from events import dispatch
        from screening import services

        if services.on_event not in dispatch.CONSUMERS:
            dispatch.CONSUMERS.append(services.on_event)
