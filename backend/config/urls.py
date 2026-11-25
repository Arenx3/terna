from django.db import transaction
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts.team_urls import public_urlpatterns as invitation_urls
from accounts.team_views import CurrentCompanyView
from candidates.views import JobApplicationsView, ResumeLinkView
from core.views import HealthView, liveness
from events.views import AuditLogView

# These never touch tenant data. Outside ATOMIC_REQUESTS they open no transaction,
# so liveness and readiness keep answering (200 and 503) while the database is down.
no_transaction = transaction.non_atomic_requests

urlpatterns = [
    path("healthz", no_transaction(liveness), name="liveness"),
    path("api/health/", no_transaction(HealthView.as_view()), name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/team/", include("accounts.team_urls")),
    path("api/jobs/", include("jobs.urls")),
    path("api/careers/", include("jobs.public_urls")),
    path("api/careers/", include("candidates.public_urls")),
    path(
        "api/jobs/<uuid:pk>/applications/",
        JobApplicationsView.as_view(),
        name="job-applications",
    ),
    path("api/applications/<int:pk>/resume/", ResumeLinkView.as_view(), name="resume-link"),
    path("api/company/", CurrentCompanyView.as_view(), name="company"),
    path("api/audit/", AuditLogView.as_view(), name="audit"),
    path("api/invitations/", include(invitation_urls)),
    path("api/schema/", no_transaction(SpectacularAPIView.as_view()), name="schema"),
    path(
        "api/docs/",
        no_transaction(SpectacularSwaggerView.as_view(url_name="schema")),
        name="docs",
    ),
]
