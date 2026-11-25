from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import Membership, User
from jobs.models import Job, Requirement, StageKind
from jobs.pipeline import MAX_STAGES, Stage
from jobs.services import RequirementItem

MAX_REQUIREMENTS = 30


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "email"]


class RequirementSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    text = serializers.CharField(max_length=300, trim_whitespace=True)
    kind = serializers.ChoiceField(choices=Requirement.Kind.choices)


class StageSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=60, allow_blank=True, default="", trim_whitespace=True)
    kind = serializers.ChoiceField(choices=StageKind.choices)


class StageListSerializer(serializers.Serializer):
    stages = StageSerializer(many=True, max_length=MAX_STAGES)

    def to_stages(self) -> list[Stage]:
        return [Stage(**item) for item in self.validated_data["stages"]]


class JobSummarySerializer(serializers.ModelSerializer):
    """A row of the jobs list."""

    hiring_manager = PersonSerializer(read_only=True, allow_null=True)
    must_haves = serializers.IntegerField(read_only=True)
    nice_to_haves = serializers.IntegerField(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "department",
            "location",
            "workplace",
            "employment",
            "language",
            "status",
            "hiring_manager",
            "must_haves",
            "nice_to_haves",
            "created_at",
            "updated_at",
            "published_at",
            "closed_at",
        ]
        read_only_fields = fields


class JobSerializer(serializers.ModelSerializer):
    """A whole job: its details, requirements and pipeline, saved together."""

    hiring_manager = PersonSerializer(read_only=True, allow_null=True)
    hiring_manager_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    requirements = RequirementSerializer(many=True, required=False, max_length=MAX_REQUIREMENTS)
    stages = StageSerializer(many=True, required=False, max_length=MAX_STAGES)

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "department",
            "location",
            "workplace",
            "employment",
            "language",
            "description",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_period",
            "status",
            "hiring_manager",
            "hiring_manager_id",
            "requirements",
            "stages",
            "created_at",
            "updated_at",
            "published_at",
            "closed_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at", "published_at", "closed_at"]

    def to_representation(self, instance: Job) -> dict:
        data = super().to_representation(instance)
        data["requirements"] = RequirementSerializer(instance.requirements.all(), many=True).data
        data["stages"] = StageSerializer(instance.stages.all(), many=True).data
        return data

    def validate_hiring_manager_id(self, value):
        if value is None:
            return None
        # Membership is tenant-scoped: only people in the active company match.
        allowed = Membership.objects.filter(user_id=value).exclude(role=Membership.Role.INTERVIEWER)
        if not allowed.exists():
            raise serializers.ValidationError(
                _("Choose someone from your team who can own a job."), code="invalid_owner"
            )
        return value

    def validate_requirements(self, value):
        seen: set[str] = set()
        for item in value:
            key = " ".join(item["text"].lower().split())
            if key in seen:
                raise serializers.ValidationError(
                    _("Each requirement can appear only once."), code="duplicate_requirement"
                )
            seen.add(key)
        return value

    def validate(self, attrs):
        low, high = attrs.get("salary_min"), attrs.get("salary_max")
        if self.instance is not None:
            low = attrs.get("salary_min", self.instance.salary_min)
            high = attrs.get("salary_max", self.instance.salary_max)
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError(
                {"salary_max": _("The maximum can't be lower than the minimum.")},
                code="salary_range",
            )
        return attrs

    def split(self) -> tuple[dict, list[RequirementItem] | None, list[Stage] | None]:
        """Job fields, requirements and stages, each in the shape the services take."""
        data = dict(self.validated_data)
        requirements = data.pop("requirements", None)
        stages = data.pop("stages", None)
        return (
            data,
            None if requirements is None else [RequirementItem(**item) for item in requirements],
            None if stages is None else [Stage(**item) for item in stages],
        )
