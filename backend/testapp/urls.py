from django.urls import include, path
from rest_framework.routers import DefaultRouter

from testapp.views import NoteViewSet

router = DefaultRouter()
router.register("notes", NoteViewSet)

urlpatterns = [
    path("", include("config.urls")),
    path("api/test/", include(router.urls)),
]
