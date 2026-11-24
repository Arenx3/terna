"""Container healthchecks.

python docker/healthcheck.py http            # ASGI server answers /healthz
python docker/healthcheck.py worker <queue>  # worker for <queue> answers a ping via the broker
python docker/healthcheck.py beat            # Celery beat ticked recently
"""

import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BEAT_MAX_SILENCE_SECONDS = 90


def check_http() -> bool:
    with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=3) as response:
        return response.status == 200


def check_worker(queue: str) -> bool:
    from config.celery import app

    replies = app.control.ping(destination=[f"{queue}@{socket.gethostname()}"], timeout=5)
    return bool(replies)


def check_beat() -> bool:
    from core.beat import HEARTBEAT_FILE

    return time.time() - os.path.getmtime(HEARTBEAT_FILE) < BEAT_MAX_SILENCE_SECONDS


def main(argv: list[str]) -> int:
    match argv:
        case ["http"]:
            healthy = check_http()
        case ["worker", queue]:
            healthy = check_worker(queue)
        case ["beat"]:
            healthy = check_beat()
        case _:
            print(__doc__, file=sys.stderr)
            return 2
    return 0 if healthy else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # any failure means unhealthy
        print(f"unhealthy: {exc}", file=sys.stderr)
        sys.exit(1)
