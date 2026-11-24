from tenancy.tasks import tenant_task
from testapp.models import Note


@tenant_task
def note_titles(company_id) -> list[str]:
    return sorted(Note.objects.values_list("title", flat=True))


@tenant_task
def note_titles_unscoped(company_id) -> list[str]:
    # Skips the Django-level filter: only row-level security stands in the way.
    return sorted(Note.all_objects.values_list("title", flat=True))
