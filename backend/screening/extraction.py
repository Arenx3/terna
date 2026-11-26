"""Résumé text, page by page, split into passages that can be cited as evidence.

Reading: PDF through pypdf, DOCX through python-docx; no OCR, so a scanned
page has no text and is left for a person to review.

Splitting: headings in Spanish or English ("Experiencia laboral", "Skills")
open a section, and so do inline labels ("Idiomas: inglés C1"). Each bullet or
line that starts an entry opens a passage; indented or lowercase lines that
carry on the previous one are joined to it, so one job is one passage.
"""

import io
import re
import unicodedata
from dataclasses import dataclass, field

from screening.models import Section
from screening.periods import find_periods

MAX_PAGES = 30
MAX_PASSAGES = 400
MAX_PASSAGE_CHARS = 1500
# Fewer letters and digits than this, in the whole file, and there's nothing to read.
MIN_TEXT_CHARS = 50

HEADINGS: dict[str, tuple[str, ...]] = {
    Section.SUMMARY: (
        "summary", "professional summary", "profile", "professional profile", "about me",
        "about", "objective", "career objective",
        "resumen", "resumen profesional", "perfil", "perfil profesional", "sobre mi",
        "acerca de mi", "objetivo", "objetivo profesional", "extracto",
    ),
    Section.EXPERIENCE: (
        "experience", "work experience", "professional experience", "employment",
        "employment history", "work history", "career history", "relevant experience",
        "experiencia", "experiencia laboral", "experiencia profesional", "trayectoria",
        "trayectoria profesional", "trayectoria laboral", "historial laboral", "empleos",
    ),
    Section.EDUCATION: (
        "education", "academic background", "academic history", "studies", "academic training",
        "educacion", "formacion", "formacion academica", "estudios", "estudios academicos",
        "preparacion academica", "escolaridad",
    ),
    Section.SKILLS: (
        "skills", "technical skills", "core skills", "key skills", "competencies",
        "core competencies", "technologies", "tech stack", "stack", "tools", "expertise",
        "habilidades", "habilidades tecnicas", "competencias", "competencias tecnicas",
        "conocimientos", "conocimientos tecnicos", "tecnologias", "herramientas", "aptitudes",
    ),
    Section.LANGUAGES: ("languages", "language skills", "idiomas", "lenguas", "lenguajes"),
    Section.CERTIFICATIONS: (
        "certifications", "certificates", "licenses", "licenses and certifications", "courses",
        "training", "certificaciones", "certificados", "cursos", "capacitacion",
        "cursos y certificaciones",
    ),
    Section.OTHER: (
        "projects", "personal projects", "awards", "honors", "volunteering", "volunteer work",
        "interests", "hobbies", "publications", "references", "portfolio", "achievements",
        "other", "additional information",
        "proyectos", "proyectos personales", "premios", "reconocimientos", "voluntariado",
        "intereses", "pasatiempos", "publicaciones", "referencias", "portafolio", "logros",
        "otros", "informacion adicional",
    ),
}  # fmt: skip
_HEADING_INDEX = {phrase: section for section, phrases in HEADINGS.items() for phrase in phrases}
# Labels that describe the job or degree above them ("Tecnologías: Python, Django")
# rather than open a section of their own.
_ENTRY_DETAILS = frozenset(
    {"technologies", "tech stack", "stack", "tools", "tecnologias", "herramientas"}
    | set(HEADINGS[Section.OTHER])
)
_JOINERS = re.compile(r"\s+(?:&|and|y|e)\s+|\s*[/,|]\s*")
_SPACED_OUT = re.compile(r"^(?:\w ){2,}\w$")
_INLINE_LABEL = re.compile(r"^(?P<label>[^:\d]{2,40}):\s*(?P<rest>\S.*)$")
BULLET = re.compile(r"^\s*(?:[•·●▪■◦‣○►▸➢➤✓✔*\-\u2013\u2014]|\d{1,2}[.)])\s+")
_CARRY_ON_END = re.compile(r"(?:[,;:(/&+\-\u2013]|\b(?:and|y|e|of|de|del|the|for|para|with|con))$")
_SPACES = re.compile(r"[ \t\u00a0\u2000-\u200b\u202f\u205f\u3000]+")


class ExtractionError(Exception):
    """The file couldn't be read. `reason` is a `ResumeExtraction.Reason` value."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Line:
    page: int
    text: str


@dataclass
class Passage:
    page: int
    section: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.lines)


@dataclass(frozen=True)
class Result:
    pages: int
    passages: list[dict]


def _fold(text: str) -> str:
    """Lowercase, without accents: "Formación Académica" -> "formacion academica"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def clean(text: str) -> str:
    """One line as a person would read it: ligatures undone, spacing collapsed."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if c == "\t" or unicodedata.category(c)[0] != "C")
    return _SPACES.sub(" ", text).strip()


def _heading_phrase(text: str) -> str | None:
    """The known heading a line consists of, folded: "Formación académica:" -> its phrase."""
    folded = _fold(clean(text)).strip(" :.-\u2013\u2014•*#|_=")
    if _SPACED_OUT.match(folded):  # "E X P E R I E N C I A"
        folded = folded.replace(" ", "")
    if not folded or len(folded) > 45:
        return None
    if folded in _HEADING_INDEX:
        return folded
    # "Skills & tools", "Educación y certificaciones": the first part decides.
    first = _JOINERS.split(folded, maxsplit=1)[0]
    return first if first != folded and first in _HEADING_INDEX else None


def heading_of(text: str) -> str | None:
    """The section a line names, if the line is nothing but a heading."""
    phrase = _heading_phrase(text)
    return _HEADING_INDEX[phrase] if phrase else None


# Reading files


def pdf_lines(content: bytes) -> tuple[int, list[Line]]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            try:
                opened = reader.decrypt("")  # some files are "protected" with no password
            except Exception:
                opened = False
            if not opened:
                raise ExtractionError("encrypted")
        pages = len(reader.pages)
        lines = [
            Line(number, raw)
            for number, page in enumerate(reader.pages[:MAX_PAGES], start=1)
            for raw in (page.extract_text() or "").splitlines()
        ]
    except ExtractionError:
        raise
    except Exception as exc:  # a broken file can fail anywhere inside the parser
        raise ExtractionError("unreadable", f"{type(exc).__name__}: {exc}"[:500]) from exc
    return pages, lines


def docx_lines(content: bytes) -> tuple[int, list[Line]]:
    try:
        return _docx_lines(content)
    except Exception as exc:
        raise ExtractionError("unreadable", f"{type(exc).__name__}: {exc}"[:500]) from exc


def _docx_lines(content: bytes) -> tuple[int, list[Line]]:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    document = Document(io.BytesIO(content))
    page = 1
    lines: list[Line] = []

    def add(paragraph: Paragraph) -> None:
        nonlocal page
        element = paragraph._p
        # Where Word last broke the page, or a manual page break.
        page += len(element.xpath(".//w:lastRenderedPageBreak")) or len(
            element.xpath('.//w:br[@w:type="page"]')
        )
        text = paragraph.text
        properties = element.pPr
        style = (paragraph.style.name if paragraph.style is not None else "") or ""
        listed = (properties is not None and properties.numPr is not None) or style.startswith(
            "List"
        )
        for number, part in enumerate(text.split("\n")):
            lines.append(Line(page, f"• {part}" if listed and number == 0 and part else part))
        lines.append(Line(page, ""))  # a paragraph ends an entry

    # Contact details often live in the page header.
    if document.sections and not document.sections[0].header.is_linked_to_previous:
        for paragraph in document.sections[0].header.paragraphs:
            add(paragraph)
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            add(Paragraph(child, document._body))
        elif child.tag == qn("w:tbl"):  # layout tables: read cell by cell
            for element in child.iter(qn("w:p")):
                add(Paragraph(element, document._body))
    return page, lines


# Splitting into passages


def _starts_entry(text: str) -> bool:
    """A bullet, or a line that opens with a date range ("2019-2024 Engineer, …")."""
    if BULLET.match(text):
        return True
    periods = find_periods(text)
    return bool(periods) and text.lstrip().startswith(periods[0].text[:4])


def _carries_on(previous: Passage, raw: str, text: str) -> bool:
    last = previous.lines[-1]
    if len(previous.text) + len(text) > MAX_PASSAGE_CHARS:
        return False
    if raw[:1].isspace() and raw.strip():  # indented under the line above
        return True
    if text[:1].islower():
        return True
    return bool(_CARRY_ON_END.search(last))


def split(lines: list[Line]) -> list[Passage]:
    passages: list[Passage] = []
    section = Section.HEADER
    open_passage: Passage | None = None
    saw_heading = False

    for line in lines:
        text = clean(line.text)
        if not text:
            open_passage = None
            continue
        heading = heading_of(text)
        if heading:
            section, open_passage, saw_heading = heading, None, True
            continue
        label = _INLINE_LABEL.match(text)
        if label and (phrase := _heading_phrase(label.group("label"))):
            saw_heading = True
            in_entry = section in (Section.EXPERIENCE, Section.EDUCATION)
            if not (in_entry and phrase in _ENTRY_DETAILS):
                section = _HEADING_INDEX[phrase]
            open_passage = Passage(line.page, section, [text])
            passages.append(open_passage)
            continue
        if (
            open_passage is not None
            and open_passage.page == line.page
            and not _starts_entry(text)
            and _carries_on(open_passage, line.text, text)
        ):
            last = open_passage.lines[-1]
            if last.endswith("-") and last[-2:-1].isalpha() and text[:1].islower():
                open_passage.lines[-1] = last[:-1] + text  # a word broken across lines
            else:
                open_passage.lines.append(text)
            continue
        open_passage = Passage(line.page, section, [BULLET.sub("", text) or text])
        passages.append(open_passage)
        if len(passages) >= MAX_PASSAGES:
            break

    if not saw_heading:
        # No structure to go by: the first entry is the name and contact, the rest is "other".
        for passage in passages[1:]:
            passage.section = Section.OTHER
    return passages


def extract(content: bytes, kind: str) -> Result:
    """Passages of a PDF or DOCX file. Raises `ExtractionError` when there's nothing to read."""
    pages, lines = pdf_lines(content) if kind == "pdf" else docx_lines(content)
    readable = sum(ch.isalnum() for line in lines for ch in line.text)
    if readable < MIN_TEXT_CHARS:
        raise ExtractionError("no_text", f"{readable} characters of text in {pages} page(s)")
    return Result(
        pages=pages,
        passages=[
            {
                "page": passage.page,
                "position": position,
                "section": passage.section,
                "text": passage.text[:2000],
                "periods": [period.as_dict() for period in find_periods(passage.text)],
            }
            for position, passage in enumerate(split(lines))
        ],
    )
