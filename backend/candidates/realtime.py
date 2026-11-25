"""Live job boards over WebSockets (Django Channels).

One group per board, named after the company and the job, so a socket only
ever hears its own company's board. The browser sends its access token in the
first message, never in the URL (URLs end up in logs). Presence is announced
peer to peer: a newcomer says hello, everyone already there answers.
"""

import asyncio
import logging
import secrets
import uuid

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Membership
from candidates.models import Application
from events.models import EventType, OutboxEvent
from jobs.models import Job
from tenancy.api import COMPANY_CLAIM
from tenancy.context import tenant_context

logger = logging.getLogger(__name__)

AUTH_TIMEOUT_SECONDS = 5
# Close codes the client acts on: 4401 get a fresh token and retry, 4403 give up.
UNAUTHENTICATED = 4401
FORBIDDEN = 4403

VIEWER_ROLES = {Membership.Role.ADMIN, Membership.Role.RECRUITER, Membership.Role.HIRING_MANAGER}
BOARD_EVENTS = {EventType.APPLICATION_SUBMITTED, EventType.APPLICATION_STAGE_CHANGED}


def board_group(company_id, job_id) -> str:
    return f"board.{company_id}.{job_id}"


def _viewer(token: str, job_id: uuid.UUID) -> tuple[dict | None, int]:
    """(viewer, close code): who this token belongs to, if they may watch this board."""
    try:
        access = AccessToken(token)
        user_id = uuid.UUID(str(access["user_id"]))
        company_id = uuid.UUID(str(access[COMPANY_CLAIM]))
    except (TokenError, KeyError, ValueError):
        return None, UNAUTHENTICATED
    with tenant_context(company_id):
        membership = Membership.objects.select_related("user").filter(user_id=user_id).first()
        if membership is None or membership.role not in VIEWER_ROLES:
            return None, FORBIDDEN
        jobs = Job.objects.filter(pk=job_id)
        if membership.role == Membership.Role.HIRING_MANAGER:
            jobs = jobs.filter(hiring_manager_id=user_id)
        if not jobs.exists():
            return None, FORBIDDEN
        user = membership.user
        return {"id": str(user.id), "name": user.full_name, "company": str(company_id)}, 0


class JobBoardConsumer(AsyncJsonWebsocketConsumer):
    group: str | None = None
    viewer: dict | None = None

    async def connect(self) -> None:
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        # Tells this browser's tabs apart in the presence list.
        self.key = secrets.token_hex(6)
        await self.accept()
        self.auth_timer = asyncio.get_running_loop().call_later(
            AUTH_TIMEOUT_SECONDS, lambda: asyncio.ensure_future(self.close(code=UNAUTHENTICATED))
        )

    async def disconnect(self, code: int) -> None:
        self.auth_timer.cancel()
        if self.group:
            await self.channel_layer.group_send(
                self.group, {"type": "presence.leave", "key": self.key}
            )
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs) -> None:
        if self.group is not None:
            return  # moves go through the REST API, where permissions and the outbox live
        if not isinstance(content, dict) or content.get("type") != "auth":
            await self.close(code=UNAUTHENTICATED)
            return
        viewer, code = await database_sync_to_async(_viewer)(
            str(content.get("token", "")), self.job_id
        )
        if viewer is None:
            await self.close(code=code)
            return
        self.auth_timer.cancel()
        self.viewer = viewer
        self.group = board_group(viewer["company"], self.job_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.send_json({"type": "ready", "key": self.key})
        await self.channel_layer.group_send(
            self.group,
            {"type": "presence.join", "key": self.key, "channel": self.channel_name, **self._me()},
        )

    def _me(self) -> dict:
        viewer = self.viewer or {}
        return {"user": {"id": viewer.get("id"), "name": viewer.get("name")}}

    # Group messages.

    async def presence_join(self, event: dict) -> None:
        if event["key"] == self.key:
            return
        await self.send_json({"type": "presence.join", "key": event["key"], "user": event["user"]})
        # Answer the newcomer directly, so they learn who was already here.
        await self.channel_layer.send(
            event["channel"], {"type": "presence.here", "key": self.key, **self._me()}
        )

    async def presence_here(self, event: dict) -> None:
        await self.send_json({"type": "presence.join", "key": event["key"], "user": event["user"]})

    async def presence_leave(self, event: dict) -> None:
        if event["key"] != self.key:
            await self.send_json({"type": "presence.leave", "key": event["key"]})

    async def board_update(self, event: dict) -> None:
        await self.send_json(
            {
                "type": "board.update",
                "event": event["event"],
                "application": event["application"],
                "by": event["by"],
            }
        )


def broadcast(event: OutboxEvent) -> None:
    """Outbox consumer: push board changes to everyone watching that job.

    Best effort on purpose. A board that misses a message catches up when it
    reconnects; the audit log, which shares this delivery, must not wait on it.
    """
    if event.type not in BOARD_EVENTS:
        return
    from candidates.views import ApplicationSerializer

    try:
        application = (
            Application.objects.select_related("candidate", "stage", "resume")
            .filter(pk=int(event.entity_id))
            .first()
        )
        if application is None:
            return
        async_to_sync(get_channel_layer().group_send)(
            board_group(application.company_id, application.job_id),
            {
                "type": "board.update",
                "event": event.type,
                "application": ApplicationSerializer(application).data,
                "by": {
                    "id": str(event.actor_id) if event.actor_id else None,
                    "name": event.actor_name,
                },
            },
        )
    except Exception:
        logger.warning("Could not broadcast %s #%s", event.type, event.id, exc_info=True)
