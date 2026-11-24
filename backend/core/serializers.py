from rest_framework import serializers

STATUS_CHOICES = ["ok", "error"]


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    latency_ms = serializers.FloatField()


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    checks = serializers.DictField(child=HealthCheckSerializer())
