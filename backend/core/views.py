from django.http import HttpRequest, JsonResponse


def liveness(request: HttpRequest) -> JsonResponse:
    """The process is up and serving requests. Dependency checks live in /api/health/."""
    return JsonResponse({"status": "ok"})
