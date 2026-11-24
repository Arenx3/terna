from django.db import models

from tenancy.models import TenantModel


class Note(TenantModel):
    title = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.title
