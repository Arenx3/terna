"""Date ranges in résumé lines, in Spanish and English, so matching can count years.

    "2019–2024", "ene 2020 – actual", "Jan 2020 - Present", "01/2020 - 12/2023",
    "marzo de 2018 a la fecha", "since 2021"

Each range keeps the exact text it came from, so the screen can point at it.
Months are optional: "2019-2024" is a range of years.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

MONTHS = {
    # Spanish
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3, "abr": 4, "abril": 4,
    "may": 5, "mayo": 5, "jun": 6, "junio": 6, "jul": 7, "julio": 7, "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "setiembre": 9, "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
    # English
    "jan": 1, "january": 1, "february": 2, "march": 3, "apr": 4, "april": 4,
    "june": 6, "july": 7, "aug": 8, "august": 8, "september": 9, "october": 10,
    "november": 11, "dec": 12, "december": 12,
}  # fmt: skip
ONGOING = (
    r"present|current|currently|now|today|ongoing|"
    r"presente|actual|actualidad|actualmente|hoy|la\s+fecha|la\s+actualidad|fecha"
)

_MONTH = r"(?P<{0}m>" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?(?:\s+de)?"
_YEAR = r"(?P<{0}y>19[5-9]\d|20\d\d)"
_NUMERIC = r"(?P<{0}n>0?[1-9]|1[0-2])\s*[/.]\s*"


def _date(side: str) -> str:
    """A month name and year, a numeric month/year, or a year alone."""
    return (
        rf"(?:{_MONTH.format(side)}\s*{_YEAR.format(side)}"
        rf"|{_NUMERIC.format(side + 'x')}{_YEAR.format(side + 'x')}"
        rf"|{_YEAR.format(side + 'o')})"
    )


_SEPARATOR = r"\s*(?:[-\u2010-\u2015~]+|\bto\b|\bal?\b|\bhasta\b)\s*"
RANGE = re.compile(
    rf"(?<![\w/.])(?:(?:from|de|desde)\s+)?{_date('s')}{_SEPARATOR}"
    rf"(?:(?:a\s+)?(?P<ongoing>{ONGOING})\b|{_date('e')})(?![\w/])",
    re.IGNORECASE,
)
SINCE = re.compile(rf"(?<!\w)(?:since|desde)\s+{_date('s')}(?![\w/])", re.IGNORECASE)


@dataclass(frozen=True)
class Period:
    text: str
    start: str  # "2019" or "2019-03"
    end: str | None  # None while ongoing
    ongoing: bool

    def as_dict(self) -> dict:
        return {"text": self.text, "start": self.start, "end": self.end, "ongoing": self.ongoing}


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def _side(match: re.Match, side: str) -> tuple[int, int | None] | None:
    groups = match.groupdict()
    if groups.get(f"{side}y"):
        return int(groups[f"{side}y"]), MONTHS[_fold(groups[f"{side}m"])]
    if groups.get(f"{side}xy"):
        return int(groups[f"{side}xy"]), int(groups[f"{side}xn"])
    if groups.get(f"{side}oy"):
        return int(groups[f"{side}oy"]), None
    return None


def _label(year: int, month: int | None) -> str:
    return f"{year}-{month:02d}" if month else str(year)


def find_periods(line: str, today: date | None = None) -> list[Period]:
    """Every plausible date range in a line, in reading order."""
    latest = (today or date.today()).year + 1
    found: list[tuple[int, Period]] = []
    taken: list[range] = []
    for pattern in (RANGE, SINCE):
        for match in pattern.finditer(line):
            span = range(*match.span())
            if any(span.start < other.stop and other.start < span.stop for other in taken):
                continue
            start = _side(match, "s")
            end = _side(match, "e")
            ongoing = pattern is SINCE or bool(match.groupdict().get("ongoing"))
            if start is None or not 1950 <= start[0] <= latest:
                continue
            if end is not None and (end[0] > latest or (end[0], end[1] or 12) < (start[0], 1)):
                continue
            taken.append(span)
            found.append(
                (
                    match.start(),
                    Period(
                        text=match.group(0).strip(),
                        start=_label(*start),
                        end=None if ongoing or end is None else _label(*end),
                        ongoing=ongoing,
                    ),
                )
            )
    return [period for _, period in sorted(found, key=lambda item: item[0])]


def duration_months(period: dict, today: date | None = None) -> int:
    """How long a period lasted. Years alone count whole years: "2019-2024" is 60 months."""
    today = today or date.today()
    start_year, _, start_month = period["start"].partition("-")
    if period["ongoing"] or not period["end"]:
        end_year, end_month = str(today.year), str(today.month)
    else:
        end_year, _, end_month = period["end"].partition("-")
    if start_month and end_month:
        months = (int(end_year) - int(start_year)) * 12 + int(end_month) - int(start_month) + 1
    else:
        months = (int(end_year) - int(start_year)) * 12
    return max(months, 1)
