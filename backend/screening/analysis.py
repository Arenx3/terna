"""The only way from a résumé to the AI: its redacted text, never the original.

Matching, embeddings and any other model read passages through here, so none
of them can see a name, an age or an address, and none can rank by them.
"""

from screening import redaction
from screening.models import ResumeExtraction, ResumePassage


def passages_for_analysis(resume_id) -> list[tuple[int, str]]:
    """(passage id, redacted text) in reading order. Empty until the résumé is redacted
    by the current rules."""
    return list(
        ResumePassage.objects.filter(
            resume_id=resume_id,
            resume__extraction__status=ResumeExtraction.Status.READY,
            resume__extraction__redaction_version__gte=redaction.VERSION,
        )
        .order_by("position")
        .values_list("id", "redacted")
    )
