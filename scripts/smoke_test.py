#!/usr/bin/env python3
"""End-to-end check of a running stack. Standard library only, so it runs anywhere.

    docker compose up -d --build --wait
    python scripts/smoke_test.py

Ports follow the same variables as compose.yaml (TERNA_HTTP_PORT, MAILPIT_UI_PORT).
Exits non-zero, listing every failed check, if anything is wrong.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

LONG_RUNNING = {
    "nginx",
    "backend",
    "worker-default",
    "worker-media",
    "worker-ml",
    "beat",
    "postgres",
    "redis",
    "storage",
    "mailpit",
}
ONE_SHOT = {"secrets-init", "bootstrap"}
QUEUES = {"default", "media", "ml"}

BASE_URL = f"http://127.0.0.1:{os.environ.get('TERNA_HTTP_PORT', '8080')}"
MAILPIT_URL = f"http://127.0.0.1:{os.environ.get('MAILPIT_UI_PORT', '8025')}"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}{f': {detail}' if detail else ''}")
        failures.append(name)


def get(url: str) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 (fixed local URLs)
            body = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.headers), body
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8", errors="replace")
    except OSError as error:
        return 0, {}, str(error)


def compose(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 (fixed command)
        ["docker", "compose", *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def check_services() -> None:
    print("Services")
    rows = [json.loads(line) for line in compose("ps", "--all", "--format", "json").splitlines() if line]
    services = {row["Service"]: row for row in rows}

    for name in sorted(LONG_RUNNING):
        row = services.get(name)
        state = f"{row['State']}/{row.get('Health') or 'no healthcheck'}" if row else "missing"
        check(name, bool(row) and row["State"] == "running" and row.get("Health") == "healthy", state)

    for name in sorted(ONE_SHOT):
        row = services.get(name)
        state = f"{row['State']} (exit {row.get('ExitCode')})" if row else "missing"
        check(f"{name} completed", bool(row) and row["State"] == "exited" and row.get("ExitCode") == 0, state)


def check_http() -> None:
    print("HTTP")
    status, _, body = get(f"{BASE_URL}/api/health/")
    try:
        health = json.loads(body)
    except json.JSONDecodeError:
        health = {}
    check("API health reports every dependency ok", status == 200 and health.get("status") == "ok", f"{status} {body[:200]}")

    status, headers, body = get(f"{BASE_URL}/")
    check("app shell served", status == 200 and '<div id="root">' in body, str(status))
    check("app shell revalidated", headers.get("Cache-Control") == "no-cache", headers.get("Cache-Control", "none"))

    asset = re.search(r'/assets/[^"]+\.js', body)
    if asset:
        status, headers, _ = get(f"{BASE_URL}{asset.group(0)}")
        check("assets cached as immutable", status == 200 and "immutable" in headers.get("Cache-Control", ""), str(status))
    else:
        check("assets cached as immutable", False, "no script in the app shell")

    status, _, body = get(f"{BASE_URL}/some/client/route")
    check("client routes fall back to the app shell", status == 200 and '<div id="root">' in body, str(status))

    status, _, _ = get(f"{BASE_URL}/api/docs/")
    check("API docs served", status == 200, str(status))

    status, _, _ = get(f"{MAILPIT_URL}/api/v1/info")
    check("Mailpit reachable", status == 200, str(status))


def check_queues() -> None:
    print("Workers")
    script = (
        "import json; from config.celery import app; "
        "replies = app.control.inspect(timeout=5).active_queues() or {}; "
        "print(json.dumps({node: [q['name'] for q in queues] for node, queues in replies.items()}))"
    )
    try:
        replies = json.loads(compose("exec", "-T", "backend", "python", "-c", script).strip().splitlines()[-1])
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError) as error:
        check("workers answer", False, str(error))
        return

    consumed = {node.split("@", 1)[0]: sorted(queues) for node, queues in replies.items()}
    for queue in sorted(QUEUES):
        check(f"queue {queue!r} consumed only by its worker", consumed.get(queue) == [queue], str(consumed.get(queue)))


def main() -> int:
    check_services()
    check_http()
    check_queues()
    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
