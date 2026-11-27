import re

import pytest

from demo.resumes import resume_pdf
from screening.extraction import extract
from screening.redaction import fold, redact
from screening.tests.conftest import docx_from_lines
from screening.tests.pii_corpus import SAMPLES


def appears(needle: str, haystack: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(fold(needle))}(?!\w)", fold(haystack)) is not None


@pytest.fixture(scope="module")
def corpus():
    """Each synthetic résumé, read and redacted the way the worker does it."""
    results = {}
    for key, sample in SAMPLES.items():
        lines, personal, keep = sample.parsed()
        content = resume_pdf(lines) if sample.kind == "pdf" else docx_from_lines(lines)
        passages = extract(content, sample.kind).passages
        redact(passages, sample.name)
        results[key] = (passages, personal, keep)
    return results


def ai_text(passages: list[dict]) -> str:
    return "\n".join(passage["redacted"] for passage in passages)


@pytest.mark.parametrize("key", SAMPLES)
def test_no_personal_data_reaches_the_ai(corpus, key):
    passages, personal, _ = corpus[key]
    text = ai_text(passages)

    assert [(kind, value) for kind, value in personal if appears(value, text)] == []


@pytest.mark.parametrize("key", SAMPLES)
def test_skills_companies_and_titles_survive(corpus, key):
    passages, _, keep = corpus[key]
    text = ai_text(passages)

    assert [value for value in keep if not appears(value, text)] == []


def test_precision_over_the_whole_set(corpus):
    """Of every character hidden, how many were really personal data."""
    hidden = wrong = 0
    for passages, personal, _ in corpus.values():
        for passage in passages:
            folded = fold(passage["text"])
            truth = [False] * len(folded)
            for _, value in personal:
                for match in re.finditer(re.escape(fold(value)), folded):
                    truth[match.start() : match.end()] = [True] * (match.end() - match.start())
            for span in passage["redactions"]:
                for index in range(span["start"], span["end"]):
                    if folded[index] in " ,.":
                        continue
                    hidden += 1
                    wrong += not truth[index]

    assert hidden > 0
    assert 1 - wrong / hidden >= 0.98


def test_markers_keep_the_sentence_readable(corpus):
    passages, _, _ = corpus["es-references"]
    about = next(p for p in passages if p["text"].startswith("Tengo"))

    assert about["redacted"] == (
        "Tengo [EDAD], soy de nacionalidad [NACIONALIDAD] y vivo en [UBICACIÓN]."
    )
    passages, _, _ = corpus["en-us-address"]
    assert passages[0]["redacted"] == "[NAME]"


def hide(text: str, section: str = "experience", name: str = "Lucía Torres") -> str:
    passage = {"text": text, "section": section}
    redact([passage], name, language="es")
    return passage["redacted"]


@pytest.mark.parametrize(
    ("text", "section", "expected"),
    [
        ("Tel. 81 2345 6789", "header", "Tel. [TELÉFONO]"),
        ("Ingeniera de software · Guadalajara, Jal. · v.cruz@example.com", "header",
         "Ingeniera de software · [UBICACIÓN] · [CORREO]"),
        ("Periodos 2014 2018 2022 en planta", "experience", "Periodos 2014 2018 2022 en planta"),
        ("3,000 órdenes por minuto con Python 3.12", "experience", None),
        ("Ingeniera, 32 años, casada", "header", "Ingeniera, [EDAD], [ESTADO CIVIL]"),
        ("Tengo 41 años y vivo en Puebla.", "summary", "Tengo [EDAD] y vivo en [UBICACIÓN]."),
        ("Con 12 años de experiencia en logística", "summary", None),
        ("Con 25 años en la industria automotriz", "summary", None),
        ("30 years of experience, aged 30", "summary", "30 years of experience, [EDAD]"),
        ("Datos separados por comas y casados con SAP", "experience", None),
        ("Lancé acme.com y migré a ASP.NET y Socket.io", "experience", None),
        ("Código en github.com/ltorres", "experience", "Código en [URL]"),
        ("Kafka, Helm, Kubernetes y Terraform", "skills", None),
        ("Calle 5 de Mayo 120, Col. Juárez, CP 06600", "other", "[DIRECCIÓN]"),
        ("TORRES, Lucía — L. Torres — Lucia Torres", "other", "[NOMBRE] — [NOMBRE] — [NOMBRE]"),
        ("Referencia: Pedro Gómez, gerente en Acme Industrial", "other",
         "Referencia: [NOMBRE], gerente en Acme Industrial"),
    ],
)  # fmt: skip
def test_what_is_hidden_and_what_is_not(text, section, expected):
    assert hide(text, section) == (text if expected is None else expected)


def test_markers_follow_the_resume_language():
    passages = [
        {"text": "Daniel Smith", "section": "header"},
        {"text": "Designer with 10 years of experience in the B2B space", "section": "summary"},
    ]

    assert redact(passages, "Daniel Smith") == "en"
    assert passages[0]["redacted"] == "[NAME]"
    assert passages[0]["redactions"] == [{"kind": "name", "start": 0, "end": 12}]
