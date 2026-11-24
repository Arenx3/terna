import pytest

from config.celery import app

QUEUES = {"default", "media", "ml"}


def test_celery_declares_one_queue_per_worker_type():
    assert {queue.name for queue in app.conf.task_queues} == QUEUES
    assert app.conf.task_default_queue == "default"


def test_celery_tasks_survive_a_worker_crash():
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1


@pytest.mark.integration
def test_each_worker_consumes_only_its_queue():
    replies = app.control.inspect(timeout=5).active_queues()
    if not replies:
        pytest.skip("No workers running: start the stack with `docker compose up -d --wait`.")

    consumed = {
        node.split("@", 1)[0]: sorted(queue["name"] for queue in queues)
        for node, queues in replies.items()
    }

    assert consumed == {name: [name] for name in QUEUES}


def test_asgi_serves_http_and_websockets():
    from config.asgi import application

    assert set(application.application_mapping) == {"http", "websocket"}
