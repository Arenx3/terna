import io

import pytest
from docx import Document

from candidates.tests.conftest import (  # noqa: F401 (pytest fixtures)
    _isolated_storage_and_throttles,
    instant,
    open_job,
    visitor,
)
from events import dispatch

DOCX_TEXT = {
    "es": {
        "header": "Lucía Torres · lucia.torres@example.com · +52 55 5555 0100",
        "summary": ("Perfil", "Ingeniera de datos con ocho años en manufactura."),
        "experience": (
            "Experiencia laboral",
            "Ingeniera de datos, Acme — ene 2020 – actual",
            ["Pipelines de ingesta en Python y Airflow.",
             "Modelo de pronóstico de demanda con 92 % de precisión."],
        ),
        "education": (
            "Formación académica",
            "Ingeniería Industrial, Tec de Monterrey, 2012 – 2016",
        ),
        "skills": ("Habilidades", ["Python", "SQL"]),
        "languages": ("Idiomas", "Inglés avanzado (C1)"),
    },
    "en": {
        "header": "Lucía Torres · lucia.torres@example.com · +52 55 5555 0100",
        "summary": ("Summary", "Data engineer with eight years in manufacturing."),
        "experience": (
            "Work experience",
            "Data Engineer, Acme — Jan 2020 – Present",
            ["Ingestion pipelines in Python and Airflow.",
             "Demand forecasting model at 92% accuracy."],
        ),
        "education": ("Education", "B.Sc. Industrial Engineering, Tec de Monterrey, 2012 – 2016"),
        "skills": ("Skills", ["Python", "SQL"]),
        "languages": ("Languages", "Spanish (native), English (C1)"),
    },
}  # fmt: skip


def docx_resume(language: str = "es") -> bytes:
    """A Word résumé the way people write them: header, headings, bullets, a table, two pages."""
    text = DOCX_TEXT[language]
    document = Document()
    header = document.sections[0].header
    header.is_linked_to_previous = False
    header.paragraphs[0].text = text["header"]

    heading, summary = text["summary"]
    document.add_heading(heading, level=1)
    document.add_paragraph(summary)
    heading, role, bullets = text["experience"]
    document.add_heading(heading, level=1)
    document.add_paragraph(role)
    for bullet in bullets:
        document.add_paragraph(bullet, style="List Bullet")
    document.add_page_break()
    heading, degree = text["education"]
    document.add_heading(heading, level=1)
    document.add_paragraph(degree)
    heading, skills = text["skills"]
    document.add_heading(heading, level=1)
    table = document.add_table(rows=1, cols=len(skills))
    for cell, skill in zip(table.rows[0].cells, skills, strict=True):
        cell.text = skill
    heading, languages = text["languages"]
    document.add_heading(heading, level=1)
    document.add_paragraph(languages)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def deliver(django_capture_on_commit_callbacks):
    """Run the outbox and whatever it hands to the workers, the way production would."""

    def run() -> None:
        with django_capture_on_commit_callbacks(execute=True):
            dispatch.dispatch_all()

    return run
