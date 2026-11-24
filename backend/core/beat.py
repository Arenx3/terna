import os
from pathlib import Path

from celery.beat import PersistentScheduler

HEARTBEAT_FILE = Path(os.environ.get("BEAT_HEARTBEAT_FILE", "/tmp/celerybeat-heartbeat"))


class HeartbeatScheduler(PersistentScheduler):
    """Touches a file on every tick so the container healthcheck can tell a stuck beat from a live one."""

    def tick(self, *args, **kwargs):
        HEARTBEAT_FILE.touch()
        return super().tick(*args, **kwargs)
