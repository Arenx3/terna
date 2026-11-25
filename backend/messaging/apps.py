from django.apps import AppConfig


class MessagingConfig(AppConfig):
    name = "messaging"

    def ready(self) -> None:
        # Queued emails leave through the outbox: a rolled-back change sends nothing.
        from events import dispatch
        from messaging import sending

        if sending.enqueue not in dispatch.CONSUMERS:
            dispatch.CONSUMERS.append(sending.enqueue)
