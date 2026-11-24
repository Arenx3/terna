import os
from pathlib import Path

from celery.beat import PersistentScheduler

# Inside the beat container only; nothing else shares its /tmp.
HEARTBEAT_FILE = Path(os.environ.get("BEAT_HEARTBEAT_FILE", "/tmp/celerybeat-heartbeat"))  # noqa: S108


class HeartbeatScheduler(PersistentScheduler):
    """Touches a file on every tick, so the healthcheck can tell a stuck beat from a live one."""

    def tick(self, *args, **kwargs):
        HEARTBEAT_FILE.touch()
        return super().tick(*args, **kwargs)
