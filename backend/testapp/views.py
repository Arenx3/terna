from rest_framework import serializers, viewsets

from tenancy.api import TenantScopedMixin
from testapp.models import Note


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title"]


class NoteViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
