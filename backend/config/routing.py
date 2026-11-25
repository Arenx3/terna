"""WebSocket routes, served under /ws/ by nginx."""

from django.urls import path

from candidates.realtime import JobBoardConsumer

websocket_urlpatterns: list = [
    path("ws/jobs/<uuid:job_id>/board/", JobBoardConsumer.as_asgi()),
]
