"""Applying from the public careers page: no account, consent first."""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle

from candidates import services, storage
from jobs.models import Job
from jobs.public import PublicView
from tenancy.context import tenant_context

MESSAGES = {
    "form_expired": _("This form expired. Reload the page and try again."),
    "too_fast": _("That was quick. Check your details and send the form again."),
    "upload_expired": _("The upload expired. Attach your résumé again."),
    "resume_missing": _("We didn't receive your résumé. Attach it again."),
    "resume_empty": _("The résumé file is empty."),
    "resume_too_large": _("The résumé is larger than 10 MB."),
    "resume_wrong_type": _("The résumé must be a PDF or Word (.docx) file."),
}


class ApplyProblem(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST


def problem(code: str) -> ApplyProblem:
    return ApplyProblem(detail=MESSAGES[code], code=code)


class ApplyFormSerializer(serializers.Serializer):
    form_token = serializers.CharField()
    privacy_notice_version = serializers.CharField()
    max_size = serializers.IntegerField()
    content_types = serializers.ListField(child=serializers.CharField())


class ConsentField(serializers.BooleanField):
    default_error_messages = {  # noqa: RUF012 (DRF API)
        "required": _("Accept the privacy notice to apply."),
    }

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if value is not True:
            self.fail("required")
        return value


class UploadRequestSerializer(serializers.Serializer):
    form_token = serializers.CharField()
    # Consent comes before any personal data, the résumé included.
    consent = ConsentField()
    filename = serializers.CharField(max_length=255)
    content_type = serializers.ChoiceField(choices=list(storage.CONTENT_TYPES))
    size = serializers.IntegerField(min_value=1, max_value=storage.MAX_RESUME_BYTES)


class UploadTicketSerializer(serializers.Serializer):
    ticket = serializers.CharField()
    url = serializers.URLField()
    headers = serializers.DictField(child=serializers.CharField())


class ApplySerializer(serializers.Serializer):
    form_token = serializers.CharField()
    upload = serializers.CharField()
    consent = ConsentField()
    notice_version = serializers.CharField(max_length=20)
    full_name = serializers.CharField(min_length=2, max_length=150, trim_whitespace=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    # Left empty by people; filled by bots that complete every field.
    website = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_notice_version(self, value: str) -> str:
        if value != services.PRIVACY_NOTICE_VERSION:
            raise serializers.ValidationError(
                _("The privacy notice changed. Reload the page to read it."),
                code="notice_outdated",
            )
        return value


class AppliedSerializer(serializers.Serializer):
    status = serializers.CharField()


class OpenJobView(PublicView):
    throttle_scope = "apply"

    def open_job(self, pk) -> Job:
        job = Job.objects.filter(pk=pk, status=Job.Status.OPEN).first()
        if job is None:
            raise exceptions.NotFound
        return job


class ApplyView(OpenJobView):
    cacheable = False  # every visitor gets their own form token

    def get_throttles(self):
        # Opening the form is cheap and shouldn't use up the applying budget.
        return [] if self.request.method == "GET" else super().get_throttles()

    @extend_schema(responses={200: ApplyFormSerializer}, tags=["careers"])
    def get(self, request: Request, slug: str, pk) -> Response:
        company = self.company(slug)
        with tenant_context(company["id"]):
            job = self.open_job(pk)
            data = {
                "form_token": services.form_token(job),
                "privacy_notice_version": services.PRIVACY_NOTICE_VERSION,
                "max_size": storage.MAX_RESUME_BYTES,
                "content_types": list(storage.CONTENT_TYPES),
            }
        return Response(ApplyFormSerializer(data).data)

    @extend_schema(request=ApplySerializer, responses={202: AppliedSerializer}, tags=["careers"])
    def post(self, request: Request, slug: str, pk) -> Response:
        company = self.company(slug)
        form = ApplySerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        with tenant_context(company["id"]):
            job = self.open_job(pk)
            if data["website"]:
                # A bot: answer like a success, keep nothing.
                services.discard_upload(data["upload"], job)
                return Response({"status": "received"}, status=status.HTTP_202_ACCEPTED)
            try:
                services.check_form(data["form_token"], job, submitting=True)
                services.apply(
                    job,
                    services.Applicant(
                        full_name=data["full_name"],
                        email=data["email"],
                        phone=data["phone"],
                        language=getattr(request, "LANGUAGE_CODE", "es")[:2],
                        ip_address=BaseThrottle().get_ident(request),
                        user_agent=request.headers.get("User-Agent", ""),
                    ),
                    data["upload"],
                )
            except services.ApplyError as exc:
                raise problem(exc.code) from exc
        # The same answer whether or not they had applied before: nothing to learn here.
        return Response({"status": "received"}, status=status.HTTP_202_ACCEPTED)


class UploadView(OpenJobView):
    @extend_schema(
        request=UploadRequestSerializer, responses={201: UploadTicketSerializer}, tags=["careers"]
    )
    def post(self, request: Request, slug: str, pk) -> Response:
        company = self.company(slug)
        form = UploadRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        with tenant_context(company["id"]):
            job = self.open_job(pk)
            try:
                services.check_form(data["form_token"], job, submitting=False)
            except services.ApplyError as exc:
                raise problem(exc.code) from exc
            ticket, url = services.upload_ticket(
                job, filename=data["filename"], content_type=data["content_type"]
            )
        return Response(
            UploadTicketSerializer(
                {"ticket": ticket, "url": url, "headers": {"Content-Type": data["content_type"]}}
            ).data,
            status=status.HTTP_201_CREATED,
        )
