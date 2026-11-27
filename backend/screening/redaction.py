"""Personal data out of the text the AI reads.

Every passage gets a redacted copy in which personal data is replaced by a
readable marker ([NOMBRE], [TELÉFONO], [EDAD]) that keeps the sentence's
meaning, plus the spans that were replaced, so the screen can show what the AI
doesn't see. People who can open the profile keep the original; matching and
embeddings only ever read the redacted copy (see `screening.analysis`).

Three layers, each careful with skills, companies and job titles:
- rules: emails, phones, personal URLs, CURP, RFC, NSS, birth dates, ages,
  marital status, gender, nationality, addresses and places;
- the candidate's own name, known from the application: with or without
  accents, in any order, in capitals, with initials;
- a small multilingual entity recognizer (spaCy `xx_ent_wiki_sm`, local). It
  calls "Kafka" a person, so its people are only trusted where something else
  agrees: the résumé header, a first name from a list, a references line.

Only text is read: photos inside a PDF never reach this module.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import cache

from screening import gazetteer
from screening.models import Section

# Bump when the rules change: résumés redacted by an older version are read again.
VERSION = 1

PLACEHOLDERS = {
    "es": {
        "name": "NOMBRE",
        "email": "CORREO",
        "phone": "TELÉFONO",
        "url": "URL",
        "curp": "CURP",
        "rfc": "RFC",
        "nss": "NSS",
        "birthdate": "FECHA DE NACIMIENTO",
        "age": "EDAD",
        "marital_status": "ESTADO CIVIL",
        "gender": "GÉNERO",
        "nationality": "NACIONALIDAD",
        "address": "DIRECCIÓN",
        "location": "UBICACIÓN",
    },
    "en": {
        "name": "NAME",
        "email": "EMAIL",
        "phone": "PHONE",
        "url": "URL",
        "curp": "CURP",
        "rfc": "RFC",
        "nss": "SSN",
        "birthdate": "BIRTH DATE",
        "age": "AGE",
        "marital_status": "MARITAL STATUS",
        "gender": "GENDER",
        "nationality": "NATIONALITY",
        "address": "ADDRESS",
        "location": "LOCATION",
    },
}
KINDS = tuple(PLACEHOLDERS["es"])
# When two findings overlap, the more specific one names the span.
PRIORITY = {
    "email": 0,
    "curp": 0,
    "rfc": 0,
    "nss": 0,
    "birthdate": 1,
    "url": 1,
    "phone": 2,
    "age": 2,
    "address": 3,
    "marital_status": 3,
    "gender": 3,
    "nationality": 3,
    "name": 4,
    "location": 5,
}
# Where a person says who and where they are.
ABOUT_ME = (Section.HEADER, Section.SUMMARY)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "start": self.start, "end": self.end}


def fold(text: str) -> str:
    """Lowercase without accents, one character for one, so positions match `text`."""
    out = []
    for char in text:
        base = unicodedata.normalize("NFD", char)[0].lower()
        out.append(base if len(base) == 1 else char)
    return "".join(out)


# Patterns marked "folded" run on `fold(text)`, the others on the text itself.

NAME_ATOM = r"[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü'’-]+"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(  # folded
    r"(?:https?://|www\.)[^\s,;·|()<>]+"
    r"|(?<![\w@.])(?:[a-z0-9-]+\.)+(?:com|mx|io|dev|net|org|me|co|app|page|site|xyz|info|ai"
    r"|tech|design|link|bio|es|us)(?:/[^\s,;·|()<>]*)?(?![\w@])"
)
NOT_URLS = frozenset({"asp.net", "ado.net", "vb.net", "socket.io"})
SOCIAL = re.compile(
    r"linkedin|github|gitlab|bitbucket|behance|dribbble|twitter|x\.com|instagram|facebook"
    r"|medium\.com/@|wa\.me|t\.me|youtube|tiktok|stackoverflow|kaggle"
)
WEBSITE_CUE = re.compile(r"portafolio|portfolio|sitio|website|\bweb\b|blog|perfil|profile")
PHONE = re.compile(
    r"(?<![\w+/.])(?:\+\s?\d{1,3}[\s.-]?)?(?:\(\s?\d{1,4}\s?\)[\s.-]?)?\d{1,5}"
    r"(?:[\s.-]\d{1,5}){0,5}(?![\w/])"
)
YEAR = re.compile(r"(?:19|20)\d\d")
CURP = re.compile(
    r"\b[A-Z][AEIOUX][A-Z]{2}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[HMX]"
    r"(?:AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS"
    r"|TL|VZ|YN|ZS|NE)[B-DF-HJ-NP-TV-Z]{3}[A-Z\d]\d\b",
    re.IGNORECASE,
)
RFC = re.compile(
    r"\b[A-ZÑ&]{3,4}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[A-Z\d]{2}[A\d]\b",
    re.IGNORECASE,
)
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
DATE = re.compile(  # folded
    r"\d{1,2}[/.-]\d{1,2}[/.-](?:19|20)?\d\d|(?:19|20)\d\d-\d\d-\d\d"
    r"|\d{1,2}\s+de\s+[a-z]{3,10}\.?\s+(?:de|del)\s+(?:19|20)\d\d"
    r"|[a-z]{3,10}\.?\s+\d{1,2},?\s+(?:19|20)\d\d|\d{1,2}\s+[a-z]{3,10}\.?\s+(?:19|20)\d\d"
)
SEPARATORS = "·|•;"
# What follows a label: a date, a word or two, a place, or text up to a separator.
LABELS: tuple[tuple[str, str, str], ...] = (
    ("birthdate", r"(?:fecha de nacimiento|f\.? de nac\.?|nacimiento|nacid[oa] el|date of birth"
     r"|birth ?date|d\.?o\.?b\.?|born(?: on)?)\s*[:\-]?\s*(?:el\s+)?", "date"),
    ("age", r"(?<![\w-])(?:edad|age)\s*[:\-]\s*(?=\d)", "until"),
    ("marital_status", r"(?:estado civil|marital status|civil status)\s*[:\-]?\s*", "words"),
    ("gender", r"(?<!\w)(?:sexo|genero|gender|sex)\s*:\s*", "words"),
    ("nationality", r"(?:nacionalidad|nationality|ciudadania|citizenship)\s*[:\-]?\s*", "words"),
    ("address", r"(?:direccion|domicilio|home address|address)\s*:\s*", "line"),
    ("location", r"(?:ubicacion|lugar de residencia|residencia actual|location|lugar de "
     r"nacimiento|place of birth|vivo en|radico en|resido en|based in|located in|living in"
     r"|nacid[oa] en|born in|originari[oa] de)\s*[:\-]?\s*", "place"),
    ("nss", r"(?:nss|n\.s\.s\.|imss|numero de seguridad social|seguro social|ssn"
     r"|social security(?: number)?)\s*[:#.]?\s*(?=\d)", "until"),
)  # fmt: skip
TWO_WORD_VALUES = frozenset({"union libre", "costa rican", "puerto rican"})
PLACE_PART = rf"(?:{NAME_ATOM}|[A-Z]{{2,5}}\b|(?:[A-Z]\.){{1,3}}|[A-Z][a-z]{{1,4}}\.)"
PLACE_VALUE = re.compile(rf"{PLACE_PART}(?:,?\s+(?:(?:de|del|la|los)\s+)?{PLACE_PART})*")
AGE_YEARS = re.compile(r"(?<![\d.,])(1[89]|[2-7]\d)\s+anos?\b(\s+de\s+edad)?")  # folded
AGE_EN = re.compile(r"(?<![\d.,])(1[89]|[2-7]\d)[\s-]+years?[\s-]+old\b|\baged\s+(1[89]|[2-7]\d)\b")
AGE_CUE_BEFORE = re.compile(r"(?:tengo|edad|age)\W*$")
NOT_AN_AGE_AFTER = re.compile(
    r"\s*(?:de\s+(?!edad)|en\b|como\b|con\b|a\b|al\b|trabajando|liderando|of\b|in\b)"
)
MARITAL_ES = re.compile(
    r"\b(?:solter[oa]s?|casad[oa]s?|divorciad[oa]s?|viud[oa]s?|union libre|separad[oa]s?)\b"
    r"(?!\s+(?:por|de|en|con)\b)"
)
MARITAL_EN = re.compile(r"\b(?:single|married|divorced|widowed)\b")
GENDER_WORDS = re.compile(r"\b(?:masculino|femenino|hombre|mujer|male|female)\b")
SELF_CUE = re.compile(r"\b(?:soy|i am|i'm|ciudadan[oa]|citizen)\s+(?:\w+\s+){0,2}$")
STREET = re.compile(  # folded
    r"\b(?:calle|av\.|avenida|blvd\.?|boulevard|calz\.|calzada|privada|priv\.|prol\.|prolongacion"
    r"|carretera|cerrada|andador|street|st\.|ave\.|avenue|road|rd\.)\s+[^,·|;\n]{2,50}?"
    r"\s#?\s?\d+[a-z]?\b(?:\s*(?:int|interior|depto|dpto|apt|apto|ext)\.?\s*#?\s*\w+)?"
    r"|\b\d{1,5}\s+(?:[a-z]+\s+){1,3}(?:street|st\.|avenue|ave\.|road|rd\.|blvd|boulevard|lane"
    r"|ln\.|drive|dr\.|terrace|way|court|ct\.)"
)
NEIGHBORHOOD = re.compile(r"\b(?:col\.|colonia|fracc\.|fraccionamiento)\s+[^,·|;\n]{2,40}")
POSTCODE = re.compile(r"\b(?:c\.\s?p\.|cp|codigo postal|zip(?: code)?)\s*:?\s*\d{5}(?:-\d{4})?\b")
ZIP = re.compile(r"(?<![\d-])\d{5}(?:-\d{4})?(?![\d-])")
REFERENCE_CUE = re.compile(
    r"referencia|reference|contacto|contact|jef[ea]|supervisor|director|gerente|manager"
    r"|recomend|tel\.|cel\.|phone|correo|email|whatsapp"
)
NAME_PARTICLES = frozenset(
    {"del", "las", "los", "san", "van", "von", "der", "dos", "das", "mac", "de", "la", "da", "di"}
)
GIVEN_AND_SURNAMES = re.compile(
    rf"(?<![\w])({NAME_ATOM})((?:\s+(?:(?:de|del|la)\s+)?{NAME_ATOM}){{1,3}})"
)
INITIALS_BEFORE = re.compile(r"(?:^|(?<=\s))((?:[A-ZÁÉÍÓÚÑ]\.\s*){1,3})$")
INITIAL_AFTER = re.compile(r"\s+[A-ZÁÉÍÓÚÑ]\.(?!\w)")


@dataclass(frozen=True)
class KnownName:
    """The candidate's name as the application gives it, ready to find in any form."""

    tokens: tuple[str, ...]

    @classmethod
    def of(cls, full_name: str) -> "KnownName":
        tokens = [fold(token) for token in re.findall(r"[^\W\d_]+", full_name)]
        return cls(tuple(t for t in tokens if len(t) >= 3 and t not in NAME_PARTICLES))

    def in_text(self, folded: str) -> bool:
        return any(token in folded for token in self.tokens)

    def spans(self, folded: str) -> list[Span]:
        return [
            Span(*match.span(), "name")
            for token in self.tokens
            for match in re.finditer(rf"(?<!\w){re.escape(token)}(?!\w)", folded)
        ]


def _labeled_value(text: str, folded: str, start: int, mode: str) -> tuple[int, int] | None:
    if mode == "date":
        date = DATE.match(folded, start)
        return date.span() if date else None
    if mode == "place":
        place = PLACE_VALUE.match(text, start)
        return place.span() if place else None
    if mode == "words":
        word = re.compile(r"[a-z]+(?:\s+[a-z]+)?").match(folded, start)
        if not word:
            return None
        two = word.group(0)
        if two in TWO_WORD_VALUES:
            return word.span()
        return start, start + len(two.split()[0])
    end = start
    longest = 120 if mode == "line" else 24
    while end < min(len(folded), start + longest):
        char = folded[end]
        if char in SEPARATORS or (mode == "until" and char == ","):
            break
        end += 1
    while end > start and folded[end - 1] in " ,.:-":
        end -= 1
    return (start, end) if end > start else None


def _rule_spans(text: str, folded: str, section: str, known: KnownName) -> list[Span]:
    spans: list[Span] = []

    def add(start: int, end: int, kind: str) -> None:
        if end > start:
            spans.append(Span(start, end, kind))

    emails = []
    for match in EMAIL.finditer(text):
        add(*match.span(), "email")
        emails.append(range(*match.span()))
    for match in URL.finditer(folded):
        value = match.group(0).rstrip(".")
        if value in NOT_URLS or any(match.start() in email for email in emails):
            continue
        if (
            SOCIAL.search(value)
            or section in ABOUT_ME
            or known.in_text(value)
            or (section == Section.OTHER and WEBSITE_CUE.search(folded))
        ):
            add(match.start(), match.start() + len(value), "url")
    for pattern, kind in ((CURP, "curp"), (RFC, "rfc"), (SSN, "nss")):
        for match in pattern.finditer(text):
            add(*match.span(), kind)

    for kind, label, mode in LABELS:
        for match in re.finditer(label, folded):
            value = _labeled_value(text, folded, match.end(), mode)
            if value:
                add(*value, kind)

    for match in PHONE.finditer(text):
        groups = re.findall(r"\d+", match.group(0))
        if 10 <= len("".join(groups)) <= 13 and not all(YEAR.fullmatch(g) for g in groups):
            add(*match.span(), "phone")

    for match in AGE_YEARS.finditer(folded):
        before = folded[max(0, match.start() - 12) : match.start()]
        after = folded[match.end() : match.end() + 16]
        stated = match.group(2) or AGE_CUE_BEFORE.search(before)
        if stated or (section in ABOUT_ME and not NOT_AN_AGE_AFTER.match(after)):
            add(*match.span(), "age")
    for match in AGE_EN.finditer(folded):
        add(*match.span(), "age")

    if section in (*ABOUT_ME, Section.OTHER):
        for match in MARITAL_ES.finditer(folded):
            add(*match.span(), "marital_status")
    if section == Section.HEADER:
        for match in MARITAL_EN.finditer(folded):
            add(*match.span(), "marital_status")
        for match in GENDER_WORDS.finditer(folded):
            add(*match.span(), "gender")
    for match in re.finditer(r"[a-z]+", folded):
        if match.group(0) in gazetteer.NATIONALITIES and (
            section == Section.HEADER
            or SELF_CUE.search(folded[max(0, match.start() - 30) : match.start()])
        ):
            add(*match.span(), "nationality")

    for pattern in (STREET, NEIGHBORHOOD, POSTCODE):
        for match in pattern.finditer(folded):
            add(*match.span(), "address")
    has_address = any(span.kind == "address" for span in spans)
    for match in ZIP.finditer(text):
        if section == Section.HEADER or (has_address and _next_to(spans, *match.span())):
            add(*match.span(), "address")
    if section in ABOUT_ME or has_address:
        spans += _places(text, folded)
    return spans


def _next_to(spans: list[Span], start: int, end: int, gap: int = 3) -> bool:
    return any(0 <= start - s.end <= gap or 0 <= s.start - end <= gap for s in spans)


def _places(text: str, folded: str) -> list[Span]:
    """Known places, and "City, ST" with a known region after the comma."""
    spans = []
    for phrase in gazetteer.PLACES:
        for match in re.finditer(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", folded):
            spans.append(Span(*match.span(), "location"))
    for region in gazetteer.REGION_ABBREVIATIONS:
        pattern = rf"((?:{NAME_ATOM}\s){{0,3}}{NAME_ATOM})?,\s*({re.escape(region)})(?![\w.])"
        for match in re.finditer(pattern, text):
            start = match.start(1) if match.group(1) else match.start(2)
            spans.append(Span(start, match.end(2), "location"))
    return spans


def _is_place(word: str) -> bool:
    return (
        fold(word) in gazetteer.PLACES
        or word in gazetteer.REGION_ABBREVIATIONS
        or f"{word}." in gazetteer.REGION_ABBREVIATIONS
    )


def _looks_like_a_person(words: list[str]) -> bool:
    folded = [fold(word) for word in words]
    return not any(w in gazetteer.TITLE_WORDS or w in gazetteer.ORG_WORDS for w in folded)


def _people(doc, text: str, folded: str, section: str) -> list[Span]:
    """People the recognizer found, or a listed first name with surnames, where context agrees."""
    spans = []
    reference = bool(REFERENCE_CUE.search(folded))
    for entity in doc.ents:
        if entity.label_ != "PER":
            continue
        atoms = list(re.finditer(NAME_ATOM, entity.text))
        first = next(
            (i for i, atom in enumerate(atoms) if fold(atom.group(0)) in gazetteer.GIVEN_NAMES),
            None,
        )
        if first is not None and len(atoms) - first >= 2:
            atoms = atoms[first:]  # "Soy Lucía Torres" starts at "Lucía"
        elif not (section == Section.HEADER or (reference and len(atoms) >= 2)):
            continue
        elif any(_is_place(atom.group(0)) for atom in atoms):
            continue  # "Guadalajara" or "Jal" with no first name is a place, not a person
        if not atoms or not _looks_like_a_person([atom.group(0) for atom in atoms]):
            continue
        spans.append(
            Span(entity.start_char + atoms[0].start(), entity.start_char + atoms[-1].end(), "name")
        )
    if section == Section.HEADER or reference:
        for match in GIVEN_AND_SURNAMES.finditer(text):
            words = match.group(0).split()
            if fold(match.group(1)) in gazetteer.GIVEN_NAMES and _looks_like_a_person(words):
                spans.append(Span(*match.span(), "name"))
    return spans


def _overlap_kind(a: Span, b: Span) -> str:
    """Emails, IDs, links and birth dates name whatever they overlap; otherwise the
    longer finding does: a person found inside "Guadalajara, Jal." is still a place."""
    if min(PRIORITY[a.kind], PRIORITY[b.kind]) <= 1:
        return min(a, b, key=lambda s: PRIORITY[s.kind]).kind
    return max(a, b, key=lambda s: (s.end - s.start, -PRIORITY[s.kind])).kind


def _resolve(spans: list[Span], text: str) -> list[Span]:
    """One span per stretch of text: overlaps settled by priority, neighbors joined."""
    ordered = sorted(spans, key=lambda s: (s.start, PRIORITY[s.kind], -(s.end - s.start)))
    kept: list[Span] = []
    for span in ordered:
        if kept and span.start < kept[-1].end:
            last = kept[-1]
            kind = _overlap_kind(last, span)
            kept[-1] = Span(last.start, max(last.end, span.end), kind)
        else:
            kept.append(span)

    joined: list[Span] = []
    for span in kept:
        if joined:
            last = joined[-1]
            places = {last.kind, span.kind} <= {"address", "location"}
            names = last.kind == span.kind == "name"
            if (places or names) and re.fullmatch(r"[\s,]*", text[last.end : span.start]):
                kind = "address" if "address" in (last.kind, span.kind) else last.kind
                joined[-1] = Span(last.start, span.end, kind)
                continue
        joined.append(span)

    # Initials next to a name are part of it: "J. Á. Hernández", "Mateo R."
    final = []
    for span in joined:
        start, end = span.start, span.end
        if span.kind == "name":
            if before := INITIALS_BEFORE.search(text[:start]):
                start = before.start(1)
            if after := INITIAL_AFTER.match(text, end):
                end = after.end()
        final.append(Span(start, end, span.kind))
    return final


def apply(text: str, spans: list[Span], language: str) -> str:
    out, cursor = [], 0
    for span in spans:
        out += [text[cursor : span.start], f"[{PLACEHOLDERS[language][span.kind]}]"]
        cursor = span.end
    out.append(text[cursor:])
    return "".join(out)


ES_WORDS = gazetteer.words("de la el en y con para los las del por una experiencia años")
EN_WORDS = gazetteer.words("the and of in with for to on a an experience years")


def language_of(texts: list[str]) -> str:
    words = re.findall(r"[a-záéíóúñ]+", " ".join(texts).lower())
    english = sum(word in EN_WORDS for word in words)
    spanish = sum(word in ES_WORDS for word in words)
    return "en" if english > spanish else "es"


@cache
def _recognizer():
    import spacy

    return spacy.load("xx_ent_wiki_sm")


def redact(passages: list[dict], full_name: str, language: str | None = None) -> str:
    """Add `redacted` and `redactions` to each passage; returns the résumé's language."""
    language = language or language_of([passage["text"] for passage in passages])
    known = KnownName.of(full_name)
    docs = _recognizer().pipe(passage["text"] for passage in passages)
    for passage, doc in zip(passages, docs, strict=True):
        text, section = passage["text"], passage["section"]
        folded = fold(text)
        spans = (
            _rule_spans(text, folded, section, known)
            + known.spans(folded)
            + _people(doc, text, folded, section)
        )
        resolved = _resolve(spans, text)
        passage["redacted"] = apply(text, resolved, language)
        passage["redactions"] = [span.as_dict() for span in resolved]
    return language
