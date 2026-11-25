"""The audit log, for admins: what happened in the company, who did it and when."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import CompanyView, IsCompanyAdmin, IsCompanyMember
from events.models import AuditEvent, EventType

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "type",
            "actor_id",
            "actor_name",
            "entity_type",
            "entity_id",
            "entity_label",
            "payload",
            "occurred_at",
        ]
        read_only_fields = fields


class AuditPageSerializer(serializers.Serializer):
    results = AuditEventSerializer(many=True)
    # Pass as `before` to get the next, older page. Null on the last page.
    next_before = serializers.IntegerField(allow_null=True)


class AuditQuerySerializer(serializers.Serializer):
    # An exact type ("job.published") or a whole area ("job").
    type = serializers.CharField(required=False, max_length=64)
    actor = serializers.UUIDField(required=False)
    since = serializers.DateTimeField(required=False)
    until = serializers.DateTimeField(required=False)
    before = serializers.IntegerField(required=False, min_value=1)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_LIMIT, default=DEFAULT_LIMIT
    )

    def validate_type(self, value: str) -> str:
        areas = {choice.split(".")[0] for choice in EventType.values}
        if value not in EventType.values and value not in areas:
            raise serializers.ValidationError("Unknown event type.")
        return value


class AuditLogView(CompanyView):
    permission_classes = (IsAuthenticated, IsCompanyMember, IsCompanyAdmin)

    @extend_schema(
        parameters=[
            OpenApiParameter("type", str, description='Event type, or an area such as "job".'),
            OpenApiParameter("actor", str, description="Only what this person did (user id)."),
            OpenApiParameter("since", str, description="ISO 8601 date-time, inclusive."),
            OpenApiParameter("until", str, description="ISO 8601 date-time, exclusive."),
            OpenApiParameter("before", int, description="Cursor from `next_before`."),
            OpenApiParameter("limit", int, description=f"Page size, up to {MAX_LIMIT}."),
        ],
        responses={200: AuditPageSerializer},
        tags=["audit"],
    )
    def get(self, request: Request) -> Response:
        query = AuditQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        events = AuditEvent.objects.all()
        if kind := params.get("type"):
            events = (
                events.filter(type=kind)
                if "." in kind
                else events.filter(type__startswith=f"{kind}.")
            )
        if "actor" in params:
            events = events.filter(actor_id=params["actor"])
        if "since" in params:
            events = events.filter(occurred_at__gte=params["since"])
        if "until" in params:
            events = events.filter(occurred_at__lt=params["until"])
        if "before" in params:
            events = events.filter(id__lt=params["before"])

        # Ids follow commit order closely enough for paging; newest first.
        limit = params["limit"]
        page = list(events.order_by("-id")[: limit + 1])
        more = len(page) > limit
        page = page[:limit]
        return Response(
            AuditPageSerializer(
                {"results": page, "next_before": page[-1].id if more else None}
            ).data
        )
