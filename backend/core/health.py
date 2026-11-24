"""Dependency checks behind /api/health/.

Each check raises on failure. The reason goes to the log, never to the response,
so the endpoint stays safe to expose without authentication.

Checks run in parallel under one deadline: client timeouts do not cover every
stall (a DNS lookup for a stopped container can take seconds), the deadline does.
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from typing import TypedDict

import redis
from botocore.client import BaseClient
from django.conf import settings
from django.db import connection

from core.storage import s3_client

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 2
DEADLINE_SECONDS = 3.0


class CheckResult(TypedDict):
    status: str
    latency_ms: float


def check_database() -> None:
    # Runs in a worker thread, which gets its own connection: close it so none are left behind.
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        connection.close()


def check_redis() -> None:
    client = redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_timeout=TIMEOUT_SECONDS,
        socket_connect_timeout=TIMEOUT_SECONDS,
    )
    try:
        client.ping()
    finally:
        client.close()


_storage_client: BaseClient | None = None
_storage_client_lock = threading.Lock()


def _health_storage_client() -> BaseClient:
    # Building a boto3 client is slow and not thread safe, so build it once.
    global _storage_client
    with _storage_client_lock:
        if _storage_client is None:
            _storage_client = s3_client(timeout=TIMEOUT_SECONDS)
        return _storage_client


def check_storage() -> None:
    _health_storage_client().head_bucket(Bucket=settings.STORAGE_BUCKET)


CHECKS: dict[str, Callable[[], None]] = {
    "database": check_database,
    "redis": check_redis,
    "storage": check_storage,
}


def _run_one(name: str, check: Callable[[], None]) -> CheckResult:
    started = time.perf_counter()
    try:
        check()
        status = "ok"
    except Exception:
        logger.exception("Health check %r failed", name)
        status = "error"
    return {"status": status, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}


def run_checks() -> dict[str, CheckResult]:
    executor = ThreadPoolExecutor(max_workers=len(CHECKS), thread_name_prefix="health")
    try:
        futures = {name: executor.submit(_run_one, name, check) for name, check in CHECKS.items()}
        done, _ = wait(futures.values(), timeout=DEADLINE_SECONDS)
        results: dict[str, CheckResult] = {}
        for name, future in futures.items():
            if future in done:
                results[name] = future.result()
            else:
                logger.error("Health check %r timed out after %ss", name, DEADLINE_SECONDS)
                results[name] = {"status": "error", "latency_ms": DEADLINE_SECONDS * 1000}
        return results
    finally:
        # Never wait for a stuck check: it finishes on its own client timeout.
        executor.shutdown(wait=False, cancel_futures=True)
