import json

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from asgiref.testing import ApplicationCommunicator
from channels.routing import URLRouter

from accounts.sessions import issue_refresh_token
from candidates import realtime
from candidates.models import Application
from candidates.tests.conftest import PDF
from config.routing import websocket_urlpatterns
from events import dispatch
from events.models import OutboxEvent
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

ROUTER = URLRouter(websocket_urlpatterns)


@pytest.fixture(autouse=True)
def _keep_the_test_connection(monkeypatch):
    """Channels closes "old" connections around consumer work, which in a test means
    the connection holding the test's transaction. Production keeps that
    housekeeping; tests run the same code on the same connection without it."""
    monkeypatch.setattr(realtime, "database_sync_to_async", sync_to_async)

    async def keep() -> None:
        return None

    # Consumers also close "old" connections before handling each message.
    monkeypatch.setattr("channels.consumer.aclose_old_connections", keep)
    monkeypatch.setattr("channels.generic.websocket.aclose_old_connections", keep)


@pytest.fixture
def application(acme, open_job, visitor, instant):
    assert visitor.apply(visitor.upload(PDF)).status_code == 202
    return acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()[0]


@pytest.fixture
def stages(acme, open_job):
    found = acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/").json()["stages"]
    return {stage["kind"]: stage["id"] for stage in reversed(found)}


def move(client, application, to: int, **extra):
    return client.post(
        f"/api/applications/{application['id']}/move/",
        {"stage": to, "from_stage": application["stage"]["id"], **extra},
        format="json",
    )


def test_a_recruiter_moves_a_candidate(acme, application, stages):
    response = move(acme.client("recruiter"), application, stages["screening"])

    assert response.status_code == 200
    assert response.json()["stage"]["kind"] == "screening"
    with tenant_context(acme.company.id):
        event = OutboxEvent.objects.get(type="application.stage_changed")
    assert event.actor_name == acme.people["recruiter"].full_name
    assert event.entity_label == "Lucía Torres"
    assert (event.payload["from"]["kind"], event.payload["to"]["kind"]) == ("applied", "screening")


def test_a_stale_board_cannot_overwrite_a_newer_move(acme, application, stages):
    move(acme.client("recruiter"), application, stages["screening"])

    # A second recruiter still sees the candidate in Applied.
    response = move(acme.client("admin"), application, stages["interview"])

    assert response.status_code == 409
    assert response.json()["code"] == "stage_changed"


def test_rejecting_needs_a_reason_and_moving_back_clears_it(acme, application, stages):
    client = acme.client("recruiter")
    refused = move(client, application, stages["rejected"])
    assert refused.status_code == 400
    assert "reason" in refused.json()

    rejected = move(client, application, stages["rejected"], reason="requirements").json()
    assert rejected["rejection_reason"] == "requirements"

    back = move(client, rejected, stages["screening"]).json()
    assert back["rejection_reason"] == ""


def test_stages_of_another_job_are_refused(acme, job_payload, application):
    client = acme.client("recruiter")
    other = client.post("/api/jobs/", job_payload(title="Other"), format="json").json()

    response = move(client, application, other["stages"][1]["id"])

    assert response.status_code == 400


def test_only_admins_and_recruiters_move_candidates(acme, globex, application, stages):
    for client in (acme.client("hiring_manager"), acme.client("interviewer")):
        assert move(client, application, stages["screening"]).status_code in (403, 404)
    assert move(globex.client("admin"), application, stages["screening"]).status_code == 404
    with tenant_context(acme.company.id):
        assert Application.objects.get().stage.kind == "applied"


# Live boards.


def token(team, role: str = "recruiter") -> str:
    return str(issue_refresh_token(team.people[role], team.company.id).access_token)


class Socket(ApplicationCommunicator):
    """A browser's WebSocket, driven at the ASGI level (what channels' own helper wraps)."""

    async def send_json_to(self, data: dict) -> None:
        await self.send_input({"type": "websocket.receive", "text": json.dumps(data)})

    async def receive_json_from(self, timeout: float = 1) -> dict:
        message = await self.receive_output(timeout)
        assert message["type"] == "websocket.send", message
        return json.loads(message["text"])

    async def disconnect(self) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": 1000})
        await self.wait(1)


async def connect(job_id: str, access: str | None) -> Socket:
    socket = Socket(
        ROUTER,
        {
            "type": "websocket",
            "path": f"/ws/jobs/{job_id}/board/",
            "headers": [],
            "subprotocols": [],
        },
    )
    await socket.send_input({"type": "websocket.connect"})
    assert (await socket.receive_output(1))["type"] == "websocket.accept"
    if access is not None:
        await socket.send_json_to({"type": "auth", "token": access})
    return socket


def test_a_move_reaches_everyone_watching_the_board(acme, open_job, application, stages):
    acme_admin_token = token(acme, "admin")
    recruiter = acme.client("recruiter")
    dispatch.dispatch_all()  # the application itself was announced before anyone watched

    async def scenario():
        watcher = await connect(open_job["id"], acme_admin_token)
        assert (await watcher.receive_json_from())["type"] == "ready"

        await sync_to_async(move)(recruiter, application, stages["interview"])
        await sync_to_async(dispatch.dispatch_all)()

        message = await watcher.receive_json_from(timeout=2)
        assert message["type"] == "board.update"
        assert message["event"] == "application.stage_changed"
        assert message["application"]["stage"]["kind"] == "interview"
        assert message["by"]["name"] == acme.people["recruiter"].full_name
        await watcher.disconnect()

    async_to_sync(scenario)()


def test_a_socket_never_joins_another_companys_board(acme, globex, open_job):
    globex_admin_token = token(globex, "admin")

    async def scenario():
        intruder = await connect(open_job["id"], globex_admin_token)
        closed = await intruder.receive_output(timeout=2)
        assert closed == {"type": "websocket.close", "code": realtime.FORBIDDEN}

    async_to_sync(scenario)()


@pytest.mark.parametrize("role", ["interviewer", "hiring_manager"])
def test_roles_without_this_board_are_turned_away(acme, open_job, role):
    access = token(acme, role)

    async def scenario():
        socket = await connect(open_job["id"], access)
        assert (await socket.receive_output(timeout=2))["code"] == realtime.FORBIDDEN

    async_to_sync(scenario)()


def test_a_bad_token_or_no_token_closes_the_socket(acme, open_job, monkeypatch):
    monkeypatch.setattr(realtime, "AUTH_TIMEOUT_SECONDS", 0.2)

    async def scenario():
        forged = await connect(open_job["id"], "not-a-token")
        assert (await forged.receive_output(timeout=2))["code"] == realtime.UNAUTHENTICATED
        silent = await connect(open_job["id"], None)
        assert (await silent.receive_output(timeout=2))["code"] == realtime.UNAUTHENTICATED

    async_to_sync(scenario)()


def test_viewers_see_who_else_is_on_the_board(acme, open_job):
    acme_admin_token = token(acme, "admin")
    acme_recruiter_token = token(acme, "recruiter")

    async def scenario():
        first = await connect(open_job["id"], acme_admin_token)
        assert (await first.receive_json_from())["type"] == "ready"
        second = await connect(open_job["id"], acme_recruiter_token)
        assert (await second.receive_json_from())["type"] == "ready"

        joined = await first.receive_json_from(timeout=2)
        assert joined["type"] == "presence.join"
        assert joined["user"]["name"] == acme.people["recruiter"].full_name
        already_here = await second.receive_json_from(timeout=2)
        assert already_here["user"]["name"] == acme.people["admin"].full_name

        await second.disconnect()
        left = await first.receive_json_from(timeout=2)
        assert (left["type"], left["key"]) == ("presence.leave", joined["key"])
        await first.disconnect()

    async_to_sync(scenario)()
