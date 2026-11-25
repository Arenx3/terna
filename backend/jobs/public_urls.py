from django.urls import path

from jobs import public

urlpatterns = [
    path("<slug:slug>/", public.CareersView.as_view(), name="careers"),
    path("<slug:slug>/jobs/<uuid:pk>/", public.PublicJobView.as_view(), name="careers-job"),
]
