import uuid

from django.db import migrations, models

# The company of the current transaction. NULL when none is set: it matches no row.
CURRENT_COMPANY_FUNCTION = """
CREATE OR REPLACE FUNCTION app_current_company() RETURNS uuid
LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT NULLIF(current_setting('app.company_id', true), '')::uuid $$;
"""

# Ids only, for system jobs that fan out one task per company. SECURITY DEFINER runs
# it as the migration role, which bypasses row-level security; the pinned
# search_path and the qualified table name keep callers from hijacking it.
ALL_COMPANIES_FUNCTION = """
CREATE OR REPLACE FUNCTION app_all_company_ids() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$ SELECT id FROM public.tenancy_company ORDER BY created_at $$;

REVOKE ALL ON FUNCTION app_all_company_ids() FROM PUBLIC;
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            CURRENT_COMPANY_FUNCTION,
            reverse_sql="DROP FUNCTION IF EXISTS app_current_company();",
        ),
        migrations.CreateModel(
            name="Company",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=200, verbose_name="name")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
            ],
            options={
                "verbose_name": "company",
                "verbose_name_plural": "companies",
            },
        ),
        migrations.RunSQL(
            ALL_COMPANIES_FUNCTION,
            reverse_sql="DROP FUNCTION IF EXISTS app_all_company_ids();",
        ),
    ]
