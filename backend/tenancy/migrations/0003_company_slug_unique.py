from django.db import migrations, models

# Anonymous visitors of a careers page have no company: they arrive with a slug.
# SECURITY DEFINER runs as the migration role; it matches one exact slug and
# returns the company's id and name, nothing else.
COMPANY_BY_SLUG_FUNCTION = """
CREATE OR REPLACE FUNCTION app_company_by_slug(p_slug text)
RETURNS TABLE (id uuid, name text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT c.id, c.name::text FROM public.tenancy_company c WHERE c.slug = p_slug
$$;

REVOKE ALL ON FUNCTION app_company_by_slug(text) FROM PUBLIC;
"""


class Migration(migrations.Migration):
    # Separate from 0002: PostgreSQL won't alter a table in the transaction that
    # just updated its rows while deferred foreign-key checks are pending.
    dependencies = [
        ("tenancy", "0002_company_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="company",
            name="slug",
            field=models.SlugField(max_length=60, unique=True, verbose_name="slug"),
        ),
        migrations.RunSQL(
            COMPANY_BY_SLUG_FUNCTION,
            reverse_sql="DROP FUNCTION IF EXISTS app_company_by_slug(text);",
        ),
    ]
