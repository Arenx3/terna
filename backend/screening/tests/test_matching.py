"""The matching rules on their own: résumés read and redacted by the real pipeline, the
embedding model played by the stand-in (see the root conftest)."""

from datetime import date

import pytest

from screening import dictionary, matching, redaction
from screening.analysis import MASK, AnalysisPassage, as_analysis
from screening.extraction import Line, split
from screening.models import Verdict
from screening.periods import find_periods

TODAY = date(2026, 11, 27)

MATEO = [
    "Mateo Rivera",
    "Backend Engineer · Monterrey, NL · mateo.rivera@example.com",
    "Summary",
    "Backend engineer with nine years building Python APIs for logistics and payments.",
    "Experience",
    "Senior Backend Engineer, Logística Norte (Jan 2019 – Present)",
    "• Led the move of 40 services to Python 3.12 and FastAPI; p95 latency down 35%.",
    "• Ran our EKS clusters in production for three years: Helm, autoscaling, on-call.",
    "• Tuned PostgreSQL 15 queries and indexes for a 2 TB orders database.",
    "Backend Developer, Grupo Andino (2016 – 2018)",
    "• Django REST APIs for 2M customers; Celery and RabbitMQ for billing jobs.",
    "• Mentored three junior developers through their first year.",
    "Education",
    "B.Sc. Computer Systems Engineering, Tecnológico de Monterrey, 2011 – 2015",
    "Skills",
    "Python, FastAPI, Django, Kubernetes, PostgreSQL, Kafka, Terraform, AWS",
    "Languages",
    "Spanish (native), English (C1)",
]

CAMILA = [
    "Camila Ortega",
    "Desarrolladora full-stack · Ciudad de México · camila.ortega@example.com",
    "Experiencia",
    "Full-stack Developer, Agencia Digital (2022 – 2025)",
    "• Sitios y paneles en React y Node.js para doce clientes.",
    "Desarrolladora junior, independiente (2020 – 2022)",
    "• Sitios en WordPress y PHP con bases de datos MySQL.",
    "Educación",
    "Licenciatura en Informática, UNAM, 2016 – 2020",
    "Idiomas",
    "Inglés intermedio (B1)",
]


def read(lines: list[str], full_name: str) -> tuple[list[AnalysisPassage], str]:
    """A résumé through extraction and redaction, the way the ml worker reads it."""
    passages = [
        {
            "page": 1,
            "position": position,
            "section": passage.section,
            "text": passage.text,
            "periods": [period.as_dict() for period in find_periods(passage.text, TODAY)],
        }
        for position, passage in enumerate(split([Line(1, line) for line in lines]))
    ]
    language = redaction.redact(passages, full_name)
    return [
        as_analysis(
            p["position"] + 1,
            p["position"],
            p["section"],
            p["text"],
            p["redacted"],
            p["redactions"],
            p["periods"],
        )
        for p in passages
    ], language


def run(model, requirements, lines, full_name, *, job_language="en", entries=None):
    passages, language = read(lines, full_name)
    needs = [
        matching.Need(index, text, kind) for index, (text, kind) in enumerate(requirements, start=1)
    ]
    similarity = {
        need.id: {
            p.id: sum(
                a * b
                for a, b in zip(model.vector(need.text), model.vector(p.redacted), strict=True)
            )
            for p in passages
        }
        for need in needs
    }
    results = matching.screen(
        needs,
        passages,
        job_language=job_language,
        resume_language=language,
        entries=dictionary.built_in_entries() if entries is None else entries,
        similarity=similarity,
        today=TODAY,
    )
    texts = {p.id: p.masked for p in passages}
    return results, texts


def highlighted(result, texts) -> list[str]:
    return [texts[e["passage"]][start:end] for e in result.evidence for start, end in e["spans"]]


def test_an_alias_is_evidence_and_points_at_the_words_in_the_resume(model):
    [result], texts = run(model, [("Kubernetes in production", "must")], MATEO, "Mateo Rivera")
    assert result.verdict == Verdict.MEETS
    assert result.signals["keyword"]["found"][:2] == [
        {"term": "Kubernetes", "matched": "EKS"},
        {"term": "production", "matched": "production"},
    ]
    assert "EKS" in highlighted(result, texts)
    assert result.signals["keyword"]["missing"] == []


def test_without_evidence_the_verdict_says_so_and_shows_what_was_looked_for(model):
    [result], _ = run(model, [("Kubernetes in production", "must")], CAMILA, "Camila Ortega")
    assert result.verdict == Verdict.NO_EVIDENCE
    assert result.evidence == []
    assert result.signals["keyword"]["missing"] == ["Kubernetes", "production"]


@pytest.mark.parametrize(
    ("requirement", "lines", "name", "verdict", "months"),
    [
        # Jan 2019 – Nov 2026 plus 2016 – 2018: both roles are Python APIs.
        ("5+ years building APIs in Python", MATEO, "Mateo Rivera", Verdict.MEETS, 95 + 24),
        # Ten years asked; nine and a half found.
        ("10+ years building APIs in Python", MATEO, "Mateo Rivera", Verdict.PARTIAL, 119),
        # No role near Python.
        ("5+ years building APIs in Python", CAMILA, "Camila Ortega", Verdict.NO_EVIDENCE, 0),
    ],
)
def test_years_are_counted_from_the_dates_of_the_roles_that_match(
    model, requirement, lines, name, verdict, months
):
    [result], texts = run(model, [(requirement, "must")], lines, name)
    assert result.verdict == verdict
    assert result.signals["years"]["months"] == months
    if verdict != Verdict.NO_EVIDENCE:
        assert "Jan 2019 – Present" in highlighted(result, texts)


def test_overlapping_roles_count_once():
    periods = [
        {"start": "2019-01", "end": "2020-12", "ongoing": False},
        {"start": "2020-01", "end": "2021-12", "ongoing": False},
    ]
    assert matching.covered_months(periods, TODAY) == 36


def test_a_language_level_is_compared_with_the_one_asked_for(model):
    requirement = [("Inglés avanzado", "must")]
    [mateo], texts = run(model, requirement, MATEO, "Mateo Rivera", job_language="es")
    assert mateo.verdict == Verdict.MEETS
    assert mateo.signals["level"] == {"language": "Inglés", "required": "C1", "found": "C1"}
    assert highlighted(mateo, texts) == ["English", "C1"]
    assert "semantic" not in mateo.signals

    [camila], _ = run(model, requirement, CAMILA, "Camila Ortega", job_language="es")
    assert camila.verdict == Verdict.PARTIAL
    assert camila.signals["level"]["found"] == "B1"


def test_either_of_two_alternatives_meets_the_requirement(model):
    [result], _ = run(
        model, [("Event-driven systems with Kafka or RabbitMQ", "nice")], MATEO, "Mateo Rivera"
    )
    assert result.verdict in (Verdict.MEETS, Verdict.PARTIAL)
    assert "Kafka / RabbitMQ" not in result.signals["keyword"]["missing"]


def test_meaning_alone_finds_evidence_across_languages(model):
    # No shared words: the model is what knows these say the same thing.
    model.close("Opera infraestructura de contenedores en la nube", "Ran our EKS clusters")
    [result], texts = run(
        model,
        [("Opera infraestructura de contenedores en la nube", "must")],
        MATEO,
        "Mateo Rivera",
        job_language="es",
        entries=[],
    )
    assert result.verdict == Verdict.MEETS
    assert result.signals["semantic"]["level"] == matching.STRONG
    assert any("EKS clusters" in text for text in highlighted(result, texts))


def test_personal_data_is_never_evidence(model):
    # The name and the city are in the résumé's header, but matching reads it redacted.
    [name, city], texts = run(
        model, [("Mateo", "must"), ("Monterrey, NL", "nice")], MATEO, "Mateo Rivera"
    )
    assert name.verdict == Verdict.NO_EVIDENCE
    header = {pid for pid, text in texts.items() if text.startswith("Backend Engineer ·")}
    assert header
    assert not header & {e["passage"] for e in city.evidence}


def test_the_header_is_never_evidence_of_meaning_and_hidden_data_is_never_highlighted(model):
    lines = [
        *MATEO[:3],
        "References from my cloud work: mateo.rivera@example.com, ask for them",
        *MATEO[4:],
    ]
    requirement = "Experiencia en la nube"
    model.close(requirement, "Backend Engineer ·")  # the header line
    model.close(requirement, "References from my cloud work")
    [result], texts = run(
        model, [(requirement, "nice")], lines, "Mateo Rivera", job_language="es", entries=[]
    )
    header = {pid for pid, text in texts.items() if text.startswith("Backend Engineer ·")}
    assert result.verdict != Verdict.NO_EVIDENCE
    assert result.signals["semantic"]["passage"] not in header
    for text in highlighted(result, texts):
        assert MASK not in text
        assert "example.com" not in text


def test_a_company_can_take_an_alias_away(model):
    entries = [e for e in dictionary.built_in_entries() if e.term != "Kubernetes"] + [
        dictionary.Entry("Kubernetes", ("k8s",), built_in=False)
    ]
    [result], _ = run(
        model, [("Kubernetes in production", "must")], MATEO, "Mateo Rivera", entries=entries
    )
    # "EKS" no longer counts; the skills line still says Kubernetes.
    assert {"term": "Kubernetes", "matched": "EKS"} not in result.signals["keyword"]["found"]
    assert {"term": "Kubernetes", "matched": "Kubernetes"} in result.signals["keyword"]["found"]


def test_every_verdict_but_no_evidence_has_something_to_show(model):
    requirements = [
        ("5+ years building APIs in Python", "must"),
        ("Kubernetes in production", "must"),
        ("PostgreSQL at scale: query tuning, indexing, migrations", "must"),
        ("Event-driven systems with Kafka or RabbitMQ", "nice"),
        ("Mentoring other engineers", "nice"),
        ("Inglés avanzado", "nice"),
    ]
    for lines, name in ((MATEO, "Mateo Rivera"), (CAMILA, "Camila Ortega")):
        results, texts = run(model, requirements, lines, name)
        for result in results:
            assert (result.verdict == Verdict.NO_EVIDENCE) == (not result.evidence)
            for item in result.evidence:
                for start, end in item["spans"]:
                    assert 0 <= start < end <= len(texts[item["passage"]])


def test_a_requirement_reads_its_skills_years_and_level():
    known = matching.concepts(dictionary.built_in_entries(), "es")
    parsed = matching.parse("3+ años en ventas consultivas B2B", "es", known)
    assert parsed.years == 3
    assert [[m.concept.term for m in group] for group in parsed.groups] == [
        ["Ventas consultivas"],
        ["B2B"],
    ]
    parsed = matching.parse("Power BI o Looker", "es", known)
    assert [[m.concept.term for m in group] for group in parsed.groups] == [["Power BI", "Looker"]]
    parsed = matching.parse("Inglés B2 o superior", "es", known)
    assert parsed.level == 4
    assert parsed.language.concept.term == "Inglés"
