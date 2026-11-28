"""A résumé's text as the screening reads it, the screening itself, and the dictionary
of synonyms it uses, for the people reviewing applications."""

from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import CompanyView, IsCompanyMember
from candidates.access import can_manage
from candidates.models import Application
from candidates.profile import ApplicationView
from jobs.views import CanSeeJobs
from screening import dictionary, matching, redaction, services
from screening.models import (
    RequirementMatch,
    ResumeExtraction,
    ResumePassage,
    Screening,
    Synonym,
)
from screening.serializers import ScreeningSerializer


class PeriodSerializer(serializers.Serializer):
    text = serializers.CharField()
    start = serializers.CharField()
    end = serializers.CharField(allow_null=True)
    ongoing = serializers.BooleanField()


class RedactionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=redaction.KINDS)
    start = serializers.IntegerField()
    end = serializers.IntegerField()


class PassageSerializer(serializers.ModelSerializer):
    periods = PeriodSerializer(many=True, read_only=True)
    redactions = RedactionSerializer(many=True, read_only=True)

    class Meta:
        model = ResumePassage
        fields = (
            "id",
            "page",
            "position",
            "section",
            "text",
            "periods",
            "redacted",
            "redactions",
        )
        read_only_fields = fields


class ResumeTextSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ResumeExtraction.Status.choices)
    reason = serializers.ChoiceField(choices=ResumeExtraction.Reason.choices, allow_blank=True)
    detail = serializers.CharField(allow_blank=True)
    pages = serializers.IntegerField()
    language = serializers.CharField(allow_blank=True)
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
        "language": extraction.language,
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


# Screening


def _result(requirement, match: RequirementMatch | None, passages: dict[int, ResumePassage]):
    result = {
        "id": requirement.id,
        "text": requirement.text,
        "kind": requirement.kind,
        "verdict": None,
        "signals": None,
        "evidence": [],
    }
    if match is None:  # added since the last screening: in the next one
        return result
    evidence = [
        {**item, "passage": passages[item["passage"]]}
        for item in match.evidence
        if item["passage"] in passages  # gone if the résumé was read again: screened soon
    ]
    return {**result, "verdict": match.verdict, "signals": match.signals, "evidence": evidence}


def describe_screening(application: Application) -> dict:
    screening = Screening.objects.filter(application=application).first()
    resume_status = None
    if application.resume_id:
        extraction = ResumeExtraction.objects.filter(resume_id=application.resume_id).first()
        # Not picked up yet: as good as pending.
        resume_status = extraction.status if extraction else ResumeExtraction.Status.PENDING
    if screening is None:
        screening = Screening(application=application, status=Screening.Status.WAITING)
    requirements = list(application.job.requirements.order_by("position"))
    matches: dict[int, RequirementMatch] = {}
    passages: dict[int, ResumePassage] = {}
    if screening.status == Screening.Status.READY:
        matches = {m.requirement_id: m for m in screening.matches.all()}
        ids = {item["passage"] for m in matches.values() for item in m.evidence}
        passages = {p.id: p for p in ResumePassage.objects.filter(id__in=ids)}
    weights, credit = matching.WEIGHTS, matching.PARTIAL_CREDIT
    must = screening.must_meets + credit * screening.must_partial
    nice = screening.nice_meets + credit * screening.nice_partial
    return {
        "status": screening.status,
        "resume_status": resume_status,
        "detail": screening.detail,
        "completed_at": screening.completed_at,
        "must_total": screening.must_total,
        "must_meets": screening.must_meets,
        "must_partial": screening.must_partial,
        "nice_total": screening.nice_total,
        "nice_meets": screening.nice_meets,
        "nice_partial": screening.nice_partial,
        "points": weights["must"] * must + weights["nice"] * nice,
        "max_points": weights["must"] * screening.must_total
        + weights["nice"] * screening.nice_total,
        "weights": {**weights, "partial": credit},
        "requirements": [_result(r, matches.get(r.id), passages) for r in requirements],
    }


class ScreeningView(ApplicationView):
    """Every requirement with its verdict and the lines of the résumé behind it."""

    @extend_schema(responses={200: ScreeningSerializer}, tags=["applications"])
    def get(self, request: Request, pk: int) -> Response:
        application = self.get_application(request, pk)
        return Response(ScreeningSerializer(describe_screening(application)).data)


class RescreenView(ApplicationView):
    @extend_schema(request=None, responses={202: ScreeningSerializer}, tags=["applications"])
    def post(self, request: Request, pk: int) -> Response:
        if not can_manage(request):
            raise exceptions.PermissionDenied
        application = self.get_application(request, pk)
        if application.resume_id is None:
            raise exceptions.ValidationError(
                {"resume": ["This application has no résumé to screen."]}, code="no_resume"
            )
        services.schedule_screenings([application.id])
        return Response(
            ScreeningSerializer(describe_screening(application)).data,
            status=status.HTTP_202_ACCEPTED,
        )


# The dictionary


def _clean(value: str) -> str:
    return " ".join(value.split())


class EntrySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, read_only=True)
    term = serializers.CharField(max_length=dictionary.MAX_TERM)
    aliases = serializers.ListField(
        child=serializers.CharField(max_length=dictionary.MAX_TERM),
        max_length=dictionary.MAX_ALIASES,
    )
    built_in = serializers.BooleanField(read_only=True)
    overrides = serializers.BooleanField(read_only=True)

    def validate_term(self, value: str) -> str:
        value = _clean(value)
        if not any(ch.isalnum() for ch in value):
            raise serializers.ValidationError("Write the term.", code="blank")
        return value

    def validate(self, attrs: dict) -> dict:
        """Aliases trimmed, each once, and never the term itself."""
        seen = {dictionary.key_of(attrs["term"])}
        aliases = []
        for alias in map(_clean, attrs["aliases"]):
            key = dictionary.key_of(alias)
            if key not in seen and any(ch.isalnum() for ch in alias):
                seen.add(key)
                aliases.append(alias)
        attrs["aliases"] = aliases
        return attrs


class TermExists(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Your dictionary already has this term. Edit that entry instead."
    default_code = "term_exists"


def _entries() -> list:
    return EntrySerializer(dictionary.entries(), many=True).data


def _save(entry: Synonym, data: dict) -> None:
    entry.term = data["term"]
    entry.key = dictionary.key_of(entry.term)
    entry.aliases = data["aliases"]
    try:
        with transaction.atomic():
            entry.save()
    except IntegrityError as exc:
        raise TermExists from exc
    # Every job still being filled is screened again with the new words.
    services.screen_company_again()


class DictionaryView(CompanyView):
    """Terna's synonyms with the company's own on top."""

    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    @extend_schema(responses={200: EntrySerializer(many=True)}, tags=["screening"])
    def get(self, request: Request) -> Response:
        return Response(_entries())

    @extend_schema(
        request=EntrySerializer, responses={201: EntrySerializer(many=True)}, tags=["screening"]
    )
    def post(self, request: Request) -> Response:
        form = EntrySerializer(data=request.data)
        form.is_valid(raise_exception=True)
        _save(Synonym(), form.validated_data)
        return Response(_entries(), status=status.HTTP_201_CREATED)


class DictionaryEntryView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, CanSeeJobs)

    def get_entry(self, pk: int) -> Synonym:
        entry = Synonym.objects.filter(pk=pk).first()
        if entry is None:
            raise exceptions.NotFound
        return entry

    @extend_schema(
        request=EntrySerializer, responses={200: EntrySerializer(many=True)}, tags=["screening"]
    )
    def put(self, request: Request, pk: int) -> Response:
        entry = self.get_entry(pk)
        form = EntrySerializer(data=request.data)
        form.is_valid(raise_exception=True)
        _save(entry, form.validated_data)
        return Response(_entries())

    @extend_schema(responses={200: EntrySerializer(many=True)}, tags=["screening"])
    def delete(self, request: Request, pk: int) -> Response:
        """A built-in entry the company had replaced comes back."""
        self.get_entry(pk).delete()
        services.screen_company_again()
        return Response(_entries())
