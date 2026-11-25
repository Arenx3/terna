"""A candidate's profile, its history and the team's conversation about them."""

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import CompanyView
from candidates import collaboration, storage
from candidates.access import can_manage, people_who_can_see, visible_applications
from candidates.models import Application, Comment, Notification
from candidates.views import ApplicationStageSerializer, ResumeFileSerializer
from events.models import AuditEvent, EventType
from events.outbox import emit
from jobs.models import Job

# Viewing personal data is recorded, but one entry per person and candidate per half hour.
VIEW_RECORD_SECONDS = 30 * 60
TIMELINE_EVENTS = (
    EventType.APPLICATION_SUBMITTED,
    EventType.APPLICATION_STAGE_CHANGED,
    EventType.APPLICATION_ASSIGNED,
    EventType.EMAIL_SENT,
)


class TeammateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "full_name")
        read_only_fields = fields


class ProfileCandidateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    language = serializers.CharField()
    created_at = serializers.DateTimeField()


class ProfileJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "title", "status")
        read_only_fields = fields


class OtherApplicationSerializer(serializers.ModelSerializer):
    job = ProfileJobSerializer(read_only=True)
    stage = ApplicationStageSerializer(read_only=True)

    class Meta:
        model = Application
        fields = ("id", "job", "stage", "created_at")
        read_only_fields = fields


class ProfileSerializer(serializers.ModelSerializer):
    candidate = ProfileCandidateSerializer(read_only=True)
    job = ProfileJobSerializer(read_only=True)
    stage = ApplicationStageSerializer(read_only=True)
    resume = ResumeFileSerializer(read_only=True, allow_null=True)
    rejection_reason = serializers.ChoiceField(
        choices=Application.RejectionReason.choices, allow_blank=True, read_only=True
    )
    other_applications = OtherApplicationSerializer(many=True, read_only=True)
    interviewers = TeammateSerializer(many=True, read_only=True)
    team = TeammateSerializer(
        many=True, read_only=True, help_text="People who can open this candidate."
    )
    can_manage = serializers.BooleanField(read_only=True)

    class Meta:
        model = Application
        fields = (
            "id",
            "candidate",
            "job",
            "stage",
            "stage_entered_at",
            "rejection_reason",
            "rejection_note",
            "resume",
            "source",
            "created_at",
            "other_applications",
            "interviewers",
            "team",
            "can_manage",
        )
        read_only_fields = fields


class ResumeLinkSerializer(serializers.Serializer):
    url = serializers.URLField()


class TimelineEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ("id", "type", "actor_name", "entity_id", "entity_label", "payload", "occurred_at")
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("id", "author_name", "body", "mentions", "created_at")
        read_only_fields = fields


class NewCommentSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)
    mentions = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class InterviewersSerializer(serializers.Serializer):
    users = serializers.ListField(child=serializers.UUIDField(), max_length=20)


class NotificationSerializer(serializers.ModelSerializer):
    candidate = serializers.CharField(source="application.candidate.full_name", read_only=True)
    job_id = serializers.UUIDField(source="application.job_id", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "kind",
            "actor_name",
            "application",
            "candidate",
            "job_id",
            "created_at",
            "read_at",
        )
        read_only_fields = fields


class InboxSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
    items = NotificationSerializer(many=True)


class MarkReadSerializer(serializers.Serializer):
    # Empty: everything.
    ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class ApplicationView(CompanyView):
    def get_application(self, request: Request, pk: int) -> Application:
        application = (
            visible_applications(request)
            .select_related("candidate", "job", "stage", "resume")
            .filter(pk=pk)
            .first()
        )
        if application is None:
            raise exceptions.NotFound
        return application


class ProfileView(ApplicationView):
    @extend_schema(responses={200: ProfileSerializer}, tags=["applications"])
    def get(self, request: Request, pk: int) -> Response:
        application = self.get_application(request, pk)
        key = f"viewed:{application.company_id}:{request.user.id}:{application.id}"
        if cache.add(key, True, VIEW_RECORD_SECONDS):
            emit(
                EventType.CANDIDATE_VIEWED,
                entity_type="application",
                entity_id=application.id,
                label=application.candidate.full_name,
                payload={"job_id": str(application.job_id)},
            )
        application.other_applications = (
            visible_applications(request)
            .filter(candidate_id=application.candidate_id)
            .exclude(pk=application.pk)
            .select_related("job", "stage")
            .order_by("-created_at")
        )
        application.interviewers = [
            assignment.user
            for assignment in application.assignments.select_related("user").order_by(
                "user__full_name"
            )
        ]
        application.team = people_who_can_see(application)
        application.can_manage = can_manage(request)
        return Response(ProfileSerializer(application).data)


class TimelineView(ApplicationView):
    """What happened to this candidate, across the jobs the caller can see."""

    @extend_schema(responses={200: TimelineEventSerializer(many=True)}, tags=["applications"])
    def get(self, request: Request, pk: int) -> Response:
        application = self.get_application(request, pk)
        ids = [
            str(app_id)
            for app_id in visible_applications(request)
            .filter(candidate_id=application.candidate_id)
            .values_list("id", flat=True)
        ]
        events = AuditEvent.objects.filter(
            Q(entity_type="application") & Q(entity_id__in=ids) & Q(type__in=TIMELINE_EVENTS)
        ).order_by("-occurred_at")[:200]
        return Response(TimelineEventSerializer(events, many=True).data)


class CommentsView(ApplicationView):
    @extend_schema(responses={200: CommentSerializer(many=True)}, tags=["applications"])
    def get(self, request: Request, pk: int) -> Response:
        application = self.get_application(request, pk)
        return Response(CommentSerializer(application.comments.all(), many=True).data)

    @extend_schema(
        request=NewCommentSerializer, responses={201: CommentSerializer}, tags=["applications"]
    )
    def post(self, request: Request, pk: int) -> Response:
        application = self.get_application(request, pk)
        form = NewCommentSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        comment = collaboration.add_comment(
            application, request.user, form.validated_data["body"], form.validated_data["mentions"]
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class InterviewersView(ApplicationView):
    @extend_schema(
        request=InterviewersSerializer,
        responses={200: TeammateSerializer(many=True)},
        tags=["applications"],
    )
    def put(self, request: Request, pk: int) -> Response:
        if not can_manage(request):
            raise exceptions.PermissionDenied
        application = self.get_application(request, pk)
        form = InterviewersSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        try:
            people = collaboration.assign_interviewers(application, form.validated_data["users"])
        except collaboration.NotAnInterviewerError as exc:
            raise exceptions.ValidationError(
                {"users": ["Only interviewers can be assigned."]}, code="not_interviewer"
            ) from exc
        return Response(TeammateSerializer(people, many=True).data)


class ResumeView(ApplicationView):
    """A short-lived link to the résumé, to download or to show in the browser."""

    @extend_schema(
        parameters=[OpenApiParameter("inline", bool, description="Open in the browser.")],
        responses={200: ResumeLinkSerializer},
        tags=["applications"],
    )
    def get(self, request: Request, pk: int) -> Response:
        application = self.get_application(request, pk)
        resume = application.resume
        if resume is None:
            raise exceptions.NotFound
        inline = request.query_params.get("inline") in ("1", "true")
        return Response(
            {"url": storage.download_url(resume.storage_key, resume.filename, inline=inline)}
        )


class InboxView(CompanyView):
    @extend_schema(responses={200: InboxSerializer}, tags=["notifications"])
    def get(self, request: Request) -> Response:
        mine = Notification.objects.filter(recipient_id=request.user.id)
        items = mine.select_related("application__candidate").order_by("-created_at")[:30]
        return Response(
            InboxSerializer(
                {"unread": mine.filter(read_at__isnull=True).count(), "items": items}
            ).data
        )


class MarkReadView(CompanyView):
    @extend_schema(request=MarkReadSerializer, responses={204: None}, tags=["notifications"])
    def post(self, request: Request) -> Response:
        form = MarkReadSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        unread = Notification.objects.filter(recipient_id=request.user.id, read_at__isnull=True)
        if form.validated_data["ids"]:
            unread = unread.filter(id__in=form.validated_data["ids"])
        unread.update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
