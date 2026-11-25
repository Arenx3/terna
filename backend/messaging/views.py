"""Email templates for admins, and emails to candidates for the people hiring them."""

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import CompanyView, IsCompanyAdmin, IsCompanyMember
from candidates.access import can_manage, visible_applications
from candidates.models import Application
from jobs.views import CanSeeJobs
from messaging import sending, templates
from messaging.models import EmailMessage, EmailTemplate, TemplateKind

LANGUAGES = [code for code, _name in settings.LANGUAGES]


class TemplateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TemplateKind.choices)
    language = serializers.ChoiceField(choices=settings.LANGUAGES)
    subject = serializers.CharField()
    body = serializers.CharField()
    customized = serializers.BooleanField()
    variables = serializers.ListField(child=serializers.CharField())
    sample = serializers.DictField(child=serializers.CharField())
    updated_at = serializers.DateTimeField(allow_null=True)
    updated_by_name = serializers.CharField(allow_blank=True)


class TemplateInputSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200, trim_whitespace=True)
    body = serializers.CharField(max_length=5000, trim_whitespace=True)


class EmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        fields = (
            "id",
            "kind",
            "language",
            "to",
            "subject",
            "body",
            "status",
            "scheduled_for",
            "sent_at",
            "attempts",
            "failure_reason",
            "created_by_name",
            "created_at",
        )
        read_only_fields = fields


class DraftSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TemplateKind.choices)
    language = serializers.ChoiceField(choices=settings.LANGUAGES)
    subject = serializers.CharField()
    body = serializers.CharField()


class NewEmailSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TemplateKind.choices)
    subject = serializers.CharField(max_length=200, trim_whitespace=True)
    body = serializers.CharField(max_length=5000, trim_whitespace=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True, default=None)


def describe(kind: str, language: str) -> dict:
    text, row = sending.effective(kind, language)
    return {
        "kind": kind,
        "language": language,
        "subject": text.subject,
        "body": text.body,
        "customized": row is not None,
        "variables": list(templates.VARIABLES[kind]),
        "sample": templates.SAMPLE[language],
        "updated_at": row.updated_at if row else None,
        "updated_by_name": row.updated_by_name if row else "",
    }


def checked(kind: str, data: dict) -> None:
    try:
        templates.check(kind, data["subject"], data["body"])
    except templates.TemplateError as exc:
        message = (
            _("Close every {{ with }}.")
            if exc.broken
            else _("These variables don't exist: %(names)s") % {"names": ", ".join(exc.unknown)}
        )
        raise exceptions.ValidationError({"body": [message]}, code="unknown_variable") from exc


class TemplatesView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    @extend_schema(responses={200: TemplateSerializer(many=True)}, tags=["emails"])
    def get(self, request: Request) -> Response:
        rows = [describe(kind, language) for kind in TemplateKind.values for language in LANGUAGES]
        return Response(TemplateSerializer(rows, many=True).data)


class TemplateDetailView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, IsCompanyAdmin)

    def parse(self, kind: str, language: str) -> None:
        if kind not in TemplateKind.values or language not in LANGUAGES:
            raise exceptions.NotFound

    @extend_schema(
        request=TemplateInputSerializer, responses={200: TemplateSerializer}, tags=["emails"]
    )
    def put(self, request: Request, kind: str, language: str) -> Response:
        self.parse(kind, language)
        form = TemplateInputSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        checked(kind, form.validated_data)
        EmailTemplate.objects.update_or_create(
            kind=kind,
            language=language,
            defaults={**form.validated_data, "updated_by_name": request.user.full_name},
        )
        return Response(TemplateSerializer(describe(kind, language)).data)

    @extend_schema(responses={200: TemplateSerializer}, tags=["emails"])
    def delete(self, request: Request, kind: str, language: str) -> Response:
        """Back to Terna's default wording."""
        self.parse(kind, language)
        EmailTemplate.objects.filter(kind=kind, language=language).delete()
        return Response(TemplateSerializer(describe(kind, language)).data)


class ApplicationEmailsMixin(CompanyView):
    def application(self, request: Request, pk: int) -> Application:
        application = (
            visible_applications(request)
            .select_related("candidate", "job", "stage")
            .filter(pk=pk)
            .first()
        )
        if application is None:
            raise exceptions.NotFound
        return application

    def require_manager(self, request: Request) -> None:
        if not can_manage(request):
            raise exceptions.PermissionDenied


class ApplicationEmailsView(ApplicationEmailsMixin):
    @extend_schema(responses={200: EmailMessageSerializer(many=True)}, tags=["emails"])
    def get(self, request: Request, pk: int) -> Response:
        application = self.application(request, pk)
        return Response(EmailMessageSerializer(application.emails.all(), many=True).data)

    @extend_schema(
        request=NewEmailSerializer, responses={201: EmailMessageSerializer}, tags=["emails"]
    )
    def post(self, request: Request, pk: int) -> Response:
        self.require_manager(request)
        application = self.application(request, pk)
        form = NewEmailSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        # What's sent is final text: leftover {{ }} would reach the candidate as is.
        if "{{" in data["subject"] + data["body"] or "}}" in data["subject"] + data["body"]:
            raise exceptions.ValidationError(
                {"body": [_("Replace the {{ variables }} before sending.")]},
                code="unrendered_variable",
            )
        message = sending.queue(
            application,
            kind=data["kind"],
            subject=data["subject"],
            body=data["body"],
            scheduled_for=data["scheduled_for"],
        )
        return Response(EmailMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class DraftView(ApplicationEmailsMixin):
    @extend_schema(
        parameters=[OpenApiParameter("kind", str, enum=TemplateKind.values, required=True)],
        responses={200: DraftSerializer},
        tags=["emails"],
    )
    def get(self, request: Request, pk: int) -> Response:
        application = self.application(request, pk)
        kind = request.query_params.get("kind", "")
        if kind not in TemplateKind.values:
            raise exceptions.ValidationError({"kind": ["Unknown kind."]})
        language = sending.language_of(application)
        text = sending.draft(application, kind, language)
        return Response(
            DraftSerializer(
                {"kind": kind, "language": language, "subject": text.subject, "body": text.body}
            ).data
        )


class MessageActionView(ApplicationEmailsMixin):
    action = ""

    def message(self, request: Request, pk: int) -> EmailMessage:
        self.require_manager(request)
        message = (
            EmailMessage.objects.filter(pk=pk, application__in=visible_applications(request))
            .select_related("application__candidate")
            .first()
        )
        if message is None:
            raise exceptions.NotFound
        return message


class RetryView(MessageActionView):
    @extend_schema(request=None, responses={200: EmailMessageSerializer}, tags=["emails"])
    def post(self, request: Request, pk: int) -> Response:
        message = self.message(request, pk)
        if message.status != EmailMessage.Status.FAILED:
            raise exceptions.ValidationError({"status": ["Only failed emails can be retried."]})
        return Response(EmailMessageSerializer(sending.retry(message)).data)


class CancelView(MessageActionView):
    @extend_schema(request=None, responses={200: EmailMessageSerializer}, tags=["emails"])
    def post(self, request: Request, pk: int) -> Response:
        message = self.message(request, pk)
        if message.status != EmailMessage.Status.QUEUED:
            raise exceptions.ValidationError({"status": ["Only queued emails can be canceled."]})
        return Response(EmailMessageSerializer(sending.cancel(message)).data)
