from django.urls import path

from core.views import liveness

urlpatterns = [
    path("healthz", liveness, name="liveness"),
]
