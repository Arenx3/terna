from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.health import run_checks
from core.serializers import HealthSerializer


def liveness(request: HttpRequest) -> JsonResponse:
    """The process is up and serving requests. Used by the container healthcheck."""
    return JsonResponse({"status": "ok"})


class HealthView(APIView):
    """Readiness: checks every dependency the API needs."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        summary="Dependency health",
        description="Checks PostgreSQL, Redis and object storage. Returns 503 if any fails.",
        responses={200: HealthSerializer, 503: HealthSerializer},
        tags=["health"],
    )
    def get(self, request: Request) -> Response:
        checks = run_checks()
        healthy = all(result["status"] == "ok" for result in checks.values())
        return Response(
            {"status": "ok" if healthy else "error", "checks": checks},
            status=200 if healthy else 503,
            headers={"Cache-Control": "no-store"},
        )
