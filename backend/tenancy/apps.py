from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TenancyConfig(AppConfig):
    name = "tenancy"

    def ready(self) -> None:
        from tenancy.signals import apply_tenant_policies

        # Sent once per app after `migrate`; listening for this app alone runs it once.
        post_migrate.connect(apply_tenant_policies, sender=self, dispatch_uid="tenancy-policies")
