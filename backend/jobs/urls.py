from django.urls import path

from jobs import views

urlpatterns = [
    path("", views.JobsView.as_view(), name="jobs"),
    path("pipeline-template/", views.PipelineTemplateView.as_view(), name="pipeline-template"),
    path("<uuid:pk>/", views.JobDetailView.as_view(), name="job"),
    path("<uuid:pk>/publish/", views.PublishJobView.as_view(), name="job-publish"),
    path("<uuid:pk>/close/", views.CloseJobView.as_view(), name="job-close"),
]
