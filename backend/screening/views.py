"""A résumé's text, as the screening reads it, for the people reviewing the application."""

from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from candidates.access import can_manage
from candidates.models import Application
from candidates.profile import ApplicationView
from screening import services
from screening.models import ResumeExtraction, ResumePassage


class PeriodSerializer(serializers.Serializer):
    text = serializers.CharField()
    start = serializers.CharField()
    end = serializers.CharField(allow_null=True)
    ongoing = serializers.BooleanField()


class PassageSerializer(serializers.ModelSerializer):
    periods = PeriodSerializer(many=True, read_only=True)

    class Meta:
        model = ResumePassage
        fields = ("id", "page", "position", "section", "text", "periods")
        read_only_fields = fields


class ResumeTextSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ResumeExtraction.Status.choices)
    reason = serializers.ChoiceField(choices=ResumeExtraction.Reason.choices, allow_blank=True)
    detail = serializers.CharField(allow_blank=True)
    pages = serializers.IntegerField()
    extracted_at = serializers.DateTimeField(allow_null=True)
    passages = PassageSerializer(many=True)


def describe(application: Application) -> dict:
    resume = application.resume
    extraction = ResumeExtraction.objects.filter(resume=resume).first()
    if extraction is None:  # not picked up yet
        extraction = ResumeExtraction(resume=resume)
    ready = extraction.status == ResumeExtraction.Status.READY
    return {
        "status": extraction.status,
        "reason": extraction.reason,
        "detail": extraction.detail,
        "pages": extraction.pages,
        "extracted_at": extraction.extracted_at,
        "passages": ResumePassage.objects.filter(resume=resume) if ready else [],
    }


class ResumeTextMixin(ApplicationView):
    def application_with_resume(self, request: Request, pk: int) -> Application:
        application = self.get_application(request, pk)
        if application.resume is None:
            raise exceptions.NotFound
        return application


class ResumeTextView(ResumeTextMixin):
    """The passages read from the résumé, from the database: the file itself isn't touched."""

    @extend_schema(responses={200: ResumeTextSerializer}, tags=["applications"])
    def get(self, request: Request, pk: int) -> Response:
        application = self.application_with_resume(request, pk)
        return Response(ResumeTextSerializer(describe(application)).data)


class ReprocessView(ResumeTextMixin):
    @extend_schema(request=None, responses={202: ResumeTextSerializer}, tags=["applications"])
    def post(self, request: Request, pk: int) -> Response:
        if not can_manage(request):
            raise exceptions.PermissionDenied
        application = self.application_with_resume(request, pk)
        extraction, created = ResumeExtraction.objects.select_for_update().get_or_create(
            resume=application.resume
        )
        if not created and extraction.status in (
            ResumeExtraction.Status.PENDING,
            ResumeExtraction.Status.PROCESSING,
        ):
            raise exceptions.ValidationError(
                {"status": ["This résumé is already being read."]}, code="resume_reading"
            )
        services.reprocess(extraction)
        return Response(
            ResumeTextSerializer(describe(application)).data, status=status.HTTP_202_ACCEPTED
        )
