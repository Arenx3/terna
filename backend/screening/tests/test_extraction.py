import io

import pytest
from pypdf import PdfWriter

from candidates.tests.conftest import PDF, docx_bytes
from demo.resumes import resume_pdf
from demo.seed import APPLICANTS
from screening.extraction import BULLET, ExtractionError, extract
from screening.tests.conftest import docx_resume

# What each heading of the demo résumés means, written out by hand.
DEMO_HEADINGS = {
    "Summary": "summary",
    "Perfil": "summary",
    "Perfil profesional": "summary",
    "Experience": "experience",
    "Professional experience": "experience",
    "Experiencia": "experience",
    "Experiencia laboral": "experience",
    "Education": "education",
    "Educación": "education",
    "Formación académica": "education",
    "Skills": "skills",
    "Habilidades": "skills",
    "Habilidades técnicas": "skills",
    "Languages": "languages",
    "Idiomas": "languages",
    "Certifications": "certifications",
    "Otros": "other",
    "Portafolio": "other",
}
DEMO = [person for people in APPLICANTS.values() for person in people]


def sections(result) -> list[tuple[str, str]]:
    return [(passage["section"], passage["text"]) for passage in result.passages]


@pytest.mark.parametrize("person", DEMO, ids=[person.full_name for person in DEMO])
def test_demo_resumes_are_split_into_their_sections(person):
    expected, section = [], "header"
    for line in person.resume:
        if line.startswith("# "):
            section = DEMO_HEADINGS[line[2:]]
        else:
            expected.append((section, BULLET.sub("", line)))

    assert sections(extract(resume_pdf(list(person.resume)), "pdf")) == expected


def test_lines_that_carry_on_are_joined_into_one_entry():
    pdf = resume_pdf(
        [
            "Lucía Torres",
            "# Experiencia",
            "2019 - 2024 Ingeniera de datos, Acme: diseñé el data lake y los",
            "pipelines de ingesta en Python.",
            "Ene 2017 – Dic 2018 Analista, Globex: reportes en Power BI y SQL",
            "   para el área de finanzas.",
            "• Automaticé la conciliación ban-",
            "caria con pandas.",
            "Tecnologías: Python, SQL",
            "# Skills & tools",
            "Python, SQL, Power BI",
            "Idiomas: inglés avanzado (C1)",
        ]
    )

    result = extract(pdf, "pdf")

    assert sections(result) == [
        ("header", "Lucía Torres"),
        (
            "experience",
            "2019 - 2024 Ingeniera de datos, Acme: diseñé el data lake y los "
            "pipelines de ingesta en Python.",
        ),
        (
            "experience",
            "Ene 2017 – Dic 2018 Analista, Globex: reportes en Power BI y SQL "
            "para el área de finanzas.",
        ),
        ("experience", "Automaticé la conciliación bancaria con pandas."),
        ("experience", "Tecnologías: Python, SQL"),  # about the job above, not a section
        ("skills", "Python, SQL, Power BI"),
        ("languages", "Idiomas: inglés avanzado (C1)"),
    ]
    assert result.passages[1]["periods"] == [
        {"text": "2019 - 2024", "start": "2019", "end": "2024", "ongoing": False}
    ]
    assert result.passages[2]["periods"][0]["start"] == "2017-01"


def test_each_passage_knows_its_page():
    projects = [f"• Proyecto {n}: migración de servicios a Kubernetes." for n in range(40)]
    pdf = resume_pdf(
        ["Lucía Torres", "# Experience", *projects, "# Education", "B.Sc. Ingeniería, 2010 – 2014"]
    )

    result = extract(pdf, "pdf")

    assert result.pages == 2
    education = result.passages[-1]
    assert (education["section"], education["page"]) == ("education", 2)
    assert result.passages[1]["page"] == 1
    assert [passage["position"] for passage in result.passages] == list(range(len(result.passages)))


@pytest.mark.parametrize("language", ["es", "en"])
def test_word_documents(language):
    result = extract(docx_resume(language), "docx")

    if language == "es":
        assert sections(result) == [
            ("header", "Lucía Torres · lucia.torres@example.com · +52 55 5555 0100"),
            ("summary", "Ingeniera de datos con ocho años en manufactura."),
            ("experience", "Ingeniera de datos, Acme — ene 2020 – actual"),
            ("experience", "Pipelines de ingesta en Python y Airflow."),
            ("experience", "Modelo de pronóstico de demanda con 92 % de precisión."),
            ("education", "Ingeniería Industrial, Tec de Monterrey, 2012 – 2016"),
            ("skills", "Python"),
            ("skills", "SQL"),
            ("languages", "Inglés avanzado (C1)"),
        ]
    else:
        assert sections(result)[2:5] == [
            ("experience", "Data Engineer, Acme — Jan 2020 – Present"),
            ("experience", "Ingestion pipelines in Python and Airflow."),
            ("experience", "Demand forecasting model at 92% accuracy."),
        ]
    # A page break before the education section.
    assert result.pages == 2
    assert {p["page"] for p in result.passages if p["section"] == "experience"} == {1}
    assert {p["page"] for p in result.passages if p["section"] == "education"} == {2}


def test_a_scan_has_no_text_to_read():
    with pytest.raises(ExtractionError) as error:
        extract(resume_pdf([""]), "pdf")

    assert error.value.reason == "no_text"
    assert error.value.detail == "0 characters of text in 1 page(s)"


def test_a_password_protected_pdf_is_left_for_a_person():
    writer = PdfWriter(clone_from=io.BytesIO(resume_pdf(["Lucía Torres", "Python " * 20])))
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    locked = io.BytesIO()
    writer.write(locked)

    with pytest.raises(ExtractionError) as error:
        extract(locked.getvalue(), "pdf")

    assert error.value.reason == "encrypted"


@pytest.mark.parametrize(("content", "kind"), [(PDF, "pdf"), (docx_bytes(), "docx")])
def test_a_damaged_file_says_why(content, kind):
    with pytest.raises(ExtractionError) as error:
        extract(content, kind)

    assert error.value.reason == "unreadable"
    assert error.value.detail
