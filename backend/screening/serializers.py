"""How a screening reads in the API: the counts on a board card, and every verdict
with the evidence behind it on the candidate's profile."""

from rest_framework import serializers

from screening import matching
from screening.models import ResumeExtraction, Screening, Section, Verdict

SIGNAL_LEVELS = (matching.STRONG, matching.MEDIUM, matching.SOME, matching.NONE)
SIGNALS = ("keyword", "semantic", "years", "level")


class ScreeningSummarySerializer(serializers.ModelSerializer):
    """The counts, for the board. The evidence is one click away, on the profile."""

    class Meta:
        model = Screening
        fields = (
            "status",
            "must_total",
            "must_meets",
            "must_partial",
            "nice_total",
            "nice_meets",
            "nice_partial",
        )
        read_only_fields = fields


class FoundTermSerializer(serializers.Serializer):
    term = serializers.CharField(help_text="As the requirement writes it.")
    matched = serializers.CharField(help_text="As the résumé writes it: an alias, maybe.")


class KeywordSignalSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=SIGNAL_LEVELS)
    found = FoundTermSerializer(many=True)
    missing = serializers.ListField(child=serializers.CharField())


class SemanticSignalSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=SIGNAL_LEVELS)
    score = serializers.FloatField(help_text="Cosine similarity of the closest passage.")
    passage = serializers.IntegerField(allow_null=True)


class YearsSignalSerializer(serializers.Serializer):
    required = serializers.IntegerField()
    months = serializers.IntegerField(help_text="Covered by the matching roles, overlaps once.")
    roles = serializers.ListField(child=serializers.IntegerField())


class LevelSignalSerializer(serializers.Serializer):
    language = serializers.CharField()
    required = serializers.CharField()
    found = serializers.CharField(allow_null=True)


class SignalsSerializer(serializers.Serializer):
    keyword = KeywordSignalSerializer()
    # Not for language levels, where only the stated level counts.
    semantic = SemanticSignalSerializer(required=False)
    years = YearsSignalSerializer(required=False)
    level = LevelSignalSerializer(required=False)


class EvidencePassageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    page = serializers.IntegerField()
    position = serializers.IntegerField()
    section = serializers.ChoiceField(choices=Section.choices)
    text = serializers.CharField()


class EvidenceSerializer(serializers.Serializer):
    passage = EvidencePassageSerializer()
    spans = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField(), min_length=2, max_length=2),
        help_text="[start, end) offsets into the passage text.",
    )
    signals = serializers.ListField(child=serializers.ChoiceField(choices=SIGNALS))


class RequirementResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    text = serializers.CharField()
    kind = serializers.CharField()
    # Null while a requirement added since the last screening waits for the next one.
    verdict = serializers.ChoiceField(choices=Verdict.choices, allow_null=True)
    signals = SignalsSerializer(allow_null=True)
    evidence = EvidenceSerializer(many=True)


class WeightsSerializer(serializers.Serializer):
    must = serializers.IntegerField()
    nice = serializers.IntegerField()
    partial = serializers.FloatField(help_text="Credit for a partly met requirement.")


class ScreeningSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Screening.Status.choices)
    # The résumé's reading, which the screening waits on. Null without a résumé.
    resume_status = serializers.ChoiceField(
        choices=ResumeExtraction.Status.choices, allow_null=True
    )
    detail = serializers.CharField(allow_blank=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    must_total = serializers.IntegerField()
    must_meets = serializers.IntegerField()
    must_partial = serializers.IntegerField()
    nice_total = serializers.IntegerField()
    nice_meets = serializers.IntegerField()
    nice_partial = serializers.IntegerField()
    points = serializers.FloatField()
    max_points = serializers.IntegerField()
    weights = WeightsSerializer()
    requirements = RequirementResultSerializer(many=True)
