from django.db import transaction
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import HealthView, liveness

# These never touch tenant data. Outside ATOMIC_REQUESTS they open no transaction,
# so liveness and readiness keep answering (200 and 503) while the database is down.
no_transaction = transaction.non_atomic_requests

urlpatterns = [
    path("healthz", no_transaction(liveness), name="liveness"),
    path("api/health/", no_transaction(HealthView.as_view()), name="health"),
    path("api/schema/", no_transaction(SpectacularAPIView.as_view()), name="schema"),
    path(
        "api/docs/",
        no_transaction(SpectacularSwaggerView.as_view(url_name="schema")),
        name="docs",
    ),
]
