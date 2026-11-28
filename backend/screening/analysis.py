"""The only way from a résumé to the AI: its redacted text, never the original.

Matching, embeddings and any other model read passages through here, so none
of them can see a name, an age or an address, and none can rank by them.

Two forms of the same redacted passage come out. `redacted` replaces personal
data with markers ("[NOMBRE]") and is what models read. `masked` blanks the same
characters instead, so it is as long as the original and every position found in
it points at the same place in the résumé the recruiter sees.
"""

from dataclasses import dataclass, field

from screening import redaction
from screening.models import ResumeExtraction, ResumePassage

# What hidden characters become in `masked`: never a letter or digit, so no word
# or number can be found across them.
MASK = "█"


@dataclass(frozen=True)
class AnalysisPassage:
    id: int
    position: int
    section: str
    redacted: str
    masked: str
    # Date ranges outside the hidden data, each with where it sits: {"at": [start, end], ...}.
    periods: list[dict] = field(default_factory=list)


def mask(text: str, redactions: list[dict]) -> str:
    chars = list(text)
    for span in redactions:
        for index in range(span["start"], min(span["end"], len(chars))):
            chars[index] = MASK
    return "".join(chars)


def _placed_periods(masked: str, periods: list[dict]) -> list[dict]:
    """Each period with its position, in reading order; one inside hidden data is dropped."""
    placed, cursor = [], 0
    for period in periods:
        start = masked.find(period["text"], cursor)
        if start < 0:
            continue
        end = start + len(period["text"])
        placed.append({**period, "at": [start, end]})
        cursor = end
    return placed


def _ready():
    return ResumePassage.objects.filter(
        resume__extraction__status=ResumeExtraction.Status.READY,
        resume__extraction__redaction_version__gte=redaction.VERSION,
    )


def passages_for_analysis(resume_id) -> list[tuple[int, str]]:
    """(passage id, redacted text) in reading order. Empty until the résumé is redacted
    by the current rules."""
    return list(
        _ready().filter(resume_id=resume_id).order_by("position").values_list("id", "redacted")
    )


def analysis_passages(resume_id) -> list[AnalysisPassage]:
    """The résumé's passages as matching reads them. Empty until redacted by the current
    rules. The original text is read here only to blank it out."""
    rows = (
        _ready()
        .filter(resume_id=resume_id)
        .order_by("position")
        .values_list("id", "position", "section", "text", "redacted", "redactions", "periods")
    )
    return [as_analysis(*row) for row in rows]


def as_analysis(
    passage_id: int,
    position: int,
    section: str,
    text: str,
    redacted: str,
    redactions: list[dict],
    periods: list[dict],
) -> AnalysisPassage:
    masked = mask(text, redactions)
    return AnalysisPassage(
        id=passage_id,
        position=position,
        section=section,
        redacted=redacted,
        masked=masked,
        periods=_placed_periods(masked, periods),
    )
