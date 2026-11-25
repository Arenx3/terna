"""Jobs API. Admins and recruiters manage jobs; hiring managers see the jobs they own."""

from django.db.models import Count, Q, QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Membership
from accounts.permissions import CompanyView, IsCompanyAdmin, IsCompanyMember, current_membership
from jobs import services
from jobs.models import Job, Requirement
from jobs.pipeline import PipelineShapeError
from jobs.serializers import JobSerializer, JobSummarySerializer, StageListSerializer

Role = Membership.Role
MANAGERS = frozenset({Role.ADMIN, Role.RECRUITER})
VIEWERS = MANAGERS | {Role.HIRING_MANAGER}


class CanSeeJobs(BasePermission):
    """Reading needs a role that works with jobs; changing them, admin or recruiter."""

    message = "Your role can't do this."
    code = "role_forbidden"

    def has_permission(self, request: Request, view: APIView) -> bool:
        membership = current_membership(request)
        if membership is None:
            return False
        allowed = VIEWERS if request.method in SAFE_METHODS else MANAGERS
        return membership.role in allowed


class PublishBlocked(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Add at least one must-have requirement before publishing."
    default_code = "publish_needs_must_have"


class NotDraft(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Only drafts can be deleted. Close the job instead."
    default_code = "job_not_draft"


def visible_jobs(request: Request) -> QuerySet[Job]:
    """The jobs the caller may see: all of them, or only their own as hiring manager."""
    jobs = Job.objects.select_related("hiring_manager")
    membership = current_membership(request)
    if membership is not None and membership.role == Role.HIRING_MANAGER:
        jobs = jobs.filter(hiring_manager_id=request.user.id)
    return jobs


def shape_error(exc: Exception) -> exceptions.ValidationError:
    if isinstance(exc, services.UnknownItemError):
        return exceptions.ValidationError({exc.field: ["Unknown item."]}, code="unknown_item")
    return exceptions.ValidationError({"stages": [str(exc)]}, code="pipeline_shape")


class JobsView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    @extend_schema(
        parameters=[OpenApiParameter("status", enum=Job.Status.values, required=False)],
        responses={200: JobSummarySerializer(many=True)},
        tags=["jobs"],
    )
    def get(self, request: Request) -> Response:
        jobs = visible_jobs(request).annotate(
            must_haves=Count("requirements", filter=Q(requirements__kind=Requirement.Kind.MUST)),
            nice_to_haves=Count("requirements", filter=Q(requirements__kind=Requirement.Kind.NICE)),
        )
        wanted = request.query_params.get("status")
        if wanted in Job.Status.values:
            jobs = jobs.filter(status=wanted)
        return Response(JobSummarySerializer(jobs.order_by("-updated_at"), many=True).data)

    @extend_schema(request=JobSerializer, responses={201: JobSerializer}, tags=["jobs"])
    def post(self, request: Request) -> Response:
        serializer = JobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields, requirements, stages = serializer.split()
        try:
            job = services.create_job(
                created_by=request.user,
                fields=fields,
                requirements=requirements or (),
                stages=stages,
            )
        except PipelineShapeError as exc:
            raise shape_error(exc) from exc
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


class JobDetailView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    def get_job(self, request: Request, pk) -> Job:
        job = visible_jobs(request).filter(pk=pk).first()
        if job is None:
            raise exceptions.NotFound
        return job

    @extend_schema(responses={200: JobSerializer}, tags=["jobs"])
    def get(self, request: Request, pk) -> Response:
        return Response(JobSerializer(self.get_job(request, pk)).data)

    @extend_schema(request=JobSerializer, responses={200: JobSerializer}, tags=["jobs"])
    def patch(self, request: Request, pk) -> Response:
        job = self.get_job(request, pk)
        serializer = JobSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields, requirements, stages = serializer.split()
        try:
            job = services.update_job(job, fields=fields, requirements=requirements, stages=stages)
        except (PipelineShapeError, services.UnknownItemError) as exc:
            raise shape_error(exc) from exc
        except services.PublishBlockedError as exc:
            raise PublishBlocked from exc
        return Response(JobSerializer(job).data)

    @extend_schema(responses={204: None}, tags=["jobs"])
    def delete(self, request: Request, pk) -> Response:
        try:
            services.delete_draft(self.get_job(request, pk))
        except services.NotDraftError as exc:
            raise NotDraft from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublishJobView(JobDetailView):
    @extend_schema(request=None, responses={200: JobSerializer}, tags=["jobs"])
    def post(self, request: Request, pk) -> Response:
        try:
            job = services.publish(self.get_job(request, pk))
        except services.PublishBlockedError as exc:
            raise PublishBlocked from exc
        return Response(JobSerializer(job).data)


class CloseJobView(JobDetailView):
    @extend_schema(request=None, responses={200: JobSerializer}, tags=["jobs"])
    def post(self, request: Request, pk) -> Response:
        return Response(JobSerializer(services.close(self.get_job(request, pk))).data)


class PipelineTemplateView(CompanyView):
    """The company's default pipeline. Everyone who manages jobs reads it; admins change it."""

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated(), IsCompanyMember(), CanSeeJobs()]
        return [IsAuthenticated(), IsCompanyMember(), IsCompanyAdmin()]

    @extend_schema(responses={200: StageListSerializer}, tags=["jobs"])
    def get(self, request: Request) -> Response:
        return Response(StageListSerializer({"stages": services.template_stages()}).data)

    @extend_schema(request=StageListSerializer, responses={200: StageListSerializer}, tags=["jobs"])
    def put(self, request: Request) -> Response:
        serializer = StageListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            stages = services.save_template(serializer.to_stages())
        except (PipelineShapeError, services.UnknownItemError) as exc:
            raise shape_error(exc) from exc
        return Response(StageListSerializer({"stages": stages}).data)
