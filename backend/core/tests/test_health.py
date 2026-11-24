import time

import pytest
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from core import health


@pytest.fixture
def client():
    return APIClient()


def test_liveness(client):
    response = client.get(reverse("liveness"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_health_reports_every_dependency(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"database", "redis", "storage"}
    for result in body["checks"].values():
        assert result["status"] == "ok"
        assert result["latency_ms"] >= 0
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_health_fails_when_a_dependency_is_down(client, monkeypatch):
    def storage_down():
        raise ConnectionError("Could not connect to storage.internal:9000")

    monkeypatch.setitem(health.CHECKS, "storage", storage_down)

    response = client.get(reverse("health"))

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["checks"]["storage"]["status"] == "error"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"


@pytest.mark.django_db
def test_health_never_leaks_failure_details(client, monkeypatch):
    def database_down():
        raise RuntimeError("password authentication failed for user terna at postgres:5432")

    monkeypatch.setitem(health.CHECKS, "database", database_down)

    content = client.get(reverse("health")).content.decode()

    assert "password" not in content
    assert "postgres:5432" not in content


@pytest.mark.django_db
def test_health_answers_within_the_deadline_when_a_check_hangs(client, monkeypatch):
    monkeypatch.setattr(health, "DEADLINE_SECONDS", 0.3)
    monkeypatch.setitem(health.CHECKS, "storage", lambda: time.sleep(2))

    started = time.perf_counter()
    response = client.get(reverse("health"))
    elapsed = time.perf_counter() - started

    assert response.status_code == 503
    assert response.json()["checks"]["storage"]["status"] == "error"
    assert elapsed < 1.5


def test_api_is_closed_by_default(rf):
    class Probe(APIView):
        def get(self, request):
            return Response({"secret": True})

    response = Probe.as_view()(rf.get("/api/probe/"))

    assert response.status_code == 403
