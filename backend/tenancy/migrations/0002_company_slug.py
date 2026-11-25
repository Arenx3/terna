from django.db import migrations, models
from django.utils.text import slugify


def fill_slugs(apps, schema_editor):
    """Give existing companies a slug from their name, oldest first."""
    Company = apps.get_model("tenancy", "Company")
    taken: set[str] = set()
    for company in Company._base_manager.order_by("created_at"):
        base = slugify(company.name)[:50].strip("-") or "company"
        slug, number = base, 2
        while slug in taken:
            slug, number = f"{base}-{number}", number + 1
        taken.add(slug)
        company.slug = slug
        company.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="slug",
            field=models.SlugField(max_length=60, null=True, verbose_name="slug"),
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
    ]
