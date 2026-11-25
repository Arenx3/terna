from django.urls import path

from candidates import public

urlpatterns = [
    path("<slug:slug>/jobs/<uuid:pk>/apply/", public.ApplyView.as_view(), name="careers-apply"),
    path("<slug:slug>/jobs/<uuid:pk>/uploads/", public.UploadView.as_view(), name="careers-upload"),
]
