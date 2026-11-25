"""Applications, for the people who work on the job."""

from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import CompanyView, IsCompanyMember
from candidates import pipeline
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
    # Empty unless the candidate is in a rejected stage.
    rejection_reason = serializers.ChoiceField(
        choices=Application.RejectionReason.choices, allow_blank=True, read_only=True
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "candidate",
            "stage",
            "resume",
            "source",
            "created_at",
            "stage_entered_at",
            "rejection_reason",
        )
        read_only_fields = fields


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


class MoveSerializer(serializers.Serializer):
    stage = serializers.IntegerField()
    # Where the caller saw the candidate: protects against concurrent moves.
    from_stage = serializers.IntegerField()
    reason = serializers.ChoiceField(
        choices=Application.RejectionReason.choices, required=False, allow_blank=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")


class StageChanged(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Someone else moved this candidate. The board has been updated."
    default_code = "stage_changed"


class MoveApplicationView(CompanyView):
    """Admins and recruiters move candidates; hiring managers watch their boards."""

    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    @extend_schema(
        request=MoveSerializer, responses={200: ApplicationSerializer}, tags=["applications"]
    )
    def post(self, request: Request, pk: int) -> Response:
        application = Application.objects.filter(pk=pk, job__in=visible_jobs(request)).first()
        if application is None:
            raise exceptions.NotFound
        form = MoveSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        stage = PipelineStage.objects.filter(pk=data["stage"], job_id=application.job_id).first()
        if stage is None:
            raise exceptions.ValidationError({"stage": ["Unknown stage."]}, code="unknown_stage")
        try:
            moved = pipeline.move(
                application.id,
                stage,
                expected_stage_id=data["from_stage"],
                reason=data["reason"],
                note=data["note"],
            )
        except pipeline.StageChangedError as exc:
            raise StageChanged from exc
        except pipeline.ReasonRequiredError as exc:
            raise exceptions.ValidationError(
                {"reason": ["Choose why the candidate is rejected."]}, code="reason_required"
            ) from exc
        moved = Application.objects.select_related("candidate", "stage", "resume").get(pk=moved.pk)
        return Response(ApplicationSerializer(moved).data)
