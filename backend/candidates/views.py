"""Applications, for the people who work on the job."""

from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import CompanyView, IsCompanyMember
from candidates import storage
from candidates.models import Application, Candidate, Resume
from jobs.models import PipelineStage
from jobs.views import CanSeeJobs, visible_jobs


class ApplicantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ("id", "full_name", "email", "phone")
        read_only_fields = fields


class ApplicationStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineStage
        fields = ("id", "name", "kind")
        read_only_fields = fields


class ResumeFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ("filename", "format", "size")
        read_only_fields = fields


class ApplicationSerializer(serializers.ModelSerializer):
    candidate = ApplicantSerializer(read_only=True)
    stage = ApplicationStageSerializer(read_only=True)
    resume = ResumeFileSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Application
        fields = ("id", "candidate", "stage", "resume", "source", "created_at")
        read_only_fields = fields


class ResumeLinkSerializer(serializers.Serializer):
    url = serializers.URLField()


class JobApplicationsView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    @extend_schema(responses={200: ApplicationSerializer(many=True)}, tags=["applications"])
    def get(self, request: Request, pk) -> Response:
        job = visible_jobs(request).filter(pk=pk).first()
        if job is None:
            raise exceptions.NotFound
        applications = (
            Application.objects.filter(job=job)
            .select_related("candidate", "stage", "resume")
            .order_by("-created_at")
        )
        return Response(ApplicationSerializer(applications, many=True).data)


class ResumeLinkView(CompanyView):
    """A short-lived download link. The file goes from storage to the browser."""

    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    @extend_schema(responses={200: ResumeLinkSerializer}, tags=["applications"])
    def get(self, request: Request, pk: int) -> Response:
        application = (
            Application.objects.filter(pk=pk, job__in=visible_jobs(request))
            .select_related("resume")
            .first()
        )
        if application is None or application.resume is None:
            raise exceptions.NotFound
        resume = application.resume
        return Response({"url": storage.download_url(resume.storage_key, resume.filename)})
