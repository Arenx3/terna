"""Email templates: Terna's defaults, the variables they may use, and a renderer.

The syntax is a deliberately tiny one, `{{ candidate.first_name }}`, filled
from a fixed list of values. It is not Django's template language: a company
admin can't reach anything but those values, and an unknown variable is an
error at save time rather than an empty gap in a candidate's inbox.
"""

import re
from dataclasses import dataclass

from messaging.models import TemplateKind

TOKEN = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
BASE_VARIABLES = ("candidate.first_name", "candidate.full_name", "job.title", "company.name")
VARIABLES: dict[str, tuple[str, ...]] = {
    TemplateKind.APPLICATION_RECEIVED: BASE_VARIABLES,
    TemplateKind.STAGE_ADVANCED: (*BASE_VARIABLES, "stage.name"),
    TemplateKind.REJECTION: BASE_VARIABLES,
    TemplateKind.INTERVIEW_INVITATION: BASE_VARIABLES,
}

SAMPLE = {
    "es": {
        "candidate.first_name": "Lucía",
        "candidate.full_name": "Lucía Torres",
        "job.title": "Ingeniera o ingeniero backend",
        "company.name": "Acme Industrial",
        "stage.name": "Entrevista",
    },
    "en": {
        "candidate.first_name": "Lucía",
        "candidate.full_name": "Lucía Torres",
        "job.title": "Backend Engineer",
        "company.name": "Acme Industrial",
        "stage.name": "Interview",
    },
}


@dataclass(frozen=True)
class Text:
    subject: str
    body: str


DEFAULTS: dict[tuple[str, str], Text] = {
    (TemplateKind.APPLICATION_RECEIVED, "es"): Text(
        "Recibimos tu postulación a {{ job.title }}",
        "Hola, {{ candidate.first_name }}:\n\n"
        "Gracias por postularte a {{ job.title }} en {{ company.name }}. Recibimos tu CV "
        "y el equipo lo revisará con atención.\n\n"
        "Te escribiremos a este correo cuando haya novedades sobre tu proceso.\n\n"
        "Tus datos se usan solo para esta vacante, como dice el aviso de privacidad que "
        "aceptaste. Puedes pedir verlos, corregirlos o borrarlos cuando quieras.\n\n"
        "Saludos,\nEl equipo de {{ company.name }}",
    ),
    (TemplateKind.APPLICATION_RECEIVED, "en"): Text(
        "We received your application for {{ job.title }}",
        "Hi {{ candidate.first_name }},\n\n"
        "Thanks for applying to {{ job.title }} at {{ company.name }}. We received your "
        "résumé and the team will review it carefully.\n\n"
        "We'll write to this address when there's news about your application.\n\n"
        "Your data is used only for this position, as described in the privacy notice you "
        "accepted. You can ask to see, correct or delete it at any time.\n\n"
        "Best,\nThe {{ company.name }} team",
    ),
    (TemplateKind.STAGE_ADVANCED, "es"): Text(
        "Avanzas en el proceso para {{ job.title }}",
        "Hola, {{ candidate.first_name }}:\n\n"
        "Buenas noticias: tu candidatura a {{ job.title }} pasó a la etapa "
        "«{{ stage.name }}».\n\n"
        "Pronto te contactaremos con los siguientes pasos.\n\n"
        "Saludos,\nEl equipo de {{ company.name }}",
    ),
    (TemplateKind.STAGE_ADVANCED, "en"): Text(
        "You're moving forward for {{ job.title }}",
        "Hi {{ candidate.first_name }},\n\n"
        "Good news: your application for {{ job.title }} moved to the "
        "“{{ stage.name }}” stage.\n\n"
        "We'll be in touch soon with the next steps.\n\n"
        "Best,\nThe {{ company.name }} team",
    ),
    (TemplateKind.REJECTION, "es"): Text(
        "Sobre tu postulación a {{ job.title }}",
        "Hola, {{ candidate.first_name }}:\n\n"
        "Gracias por tu interés en {{ job.title }} y por el tiempo que le dedicaste al "
        "proceso.\n\n"
        "Después de revisar con cuidado todas las candidaturas, decidimos continuar con "
        "otras personas cuyo perfil se ajusta más a lo que el puesto necesita en este "
        "momento. No es un juicio sobre tu valor profesional.\n\n"
        "Nos gustaría tenerte en cuenta para futuras vacantes. Te deseamos mucho éxito.\n\n"
        "Saludos,\nEl equipo de {{ company.name }}",
    ),
    (TemplateKind.REJECTION, "en"): Text(
        "About your application for {{ job.title }}",
        "Hi {{ candidate.first_name }},\n\n"
        "Thank you for your interest in {{ job.title }} and for the time you gave to the "
        "process.\n\n"
        "After carefully reviewing every application, we've decided to move forward with "
        "other candidates whose experience is closer to what the role needs right now. "
        "This isn't a judgment of your professional worth.\n\n"
        "We'd like to keep you in mind for future openings. We wish you every success.\n\n"
        "Best,\nThe {{ company.name }} team",
    ),
    (TemplateKind.INTERVIEW_INVITATION, "es"): Text(
        "Queremos conocerte: entrevista para {{ job.title }}",
        "Hola, {{ candidate.first_name }}:\n\n"
        "Nos gustó tu perfil para {{ job.title }} y queremos invitarte a una entrevista.\n\n"
        "En breve te enviaremos opciones de horario. Si necesitas algún ajuste para la "
        "entrevista, avísanos.\n\n"
        "Saludos,\nEl equipo de {{ company.name }}",
    ),
    (TemplateKind.INTERVIEW_INVITATION, "en"): Text(
        "Let's talk: interview for {{ job.title }}",
        "Hi {{ candidate.first_name }},\n\n"
        "We liked your profile for {{ job.title }} and would like to invite you to an "
        "interview.\n\n"
        "We'll send you some time options shortly. If you need any accommodation for the "
        "interview, just let us know.\n\n"
        "Best,\nThe {{ company.name }} team",
    ),
}


class TemplateError(ValueError):
    def __init__(self, unknown: list[str], broken: bool = False) -> None:
        super().__init__(", ".join(unknown) or "unbalanced braces")
        self.unknown = unknown
        self.broken = broken


def check(kind: str, *texts: str) -> None:
    """Every `{{ … }}` must be a variable this kind of email offers."""
    allowed = set(VARIABLES[kind])
    unknown: list[str] = []
    for text in texts:
        for name in TOKEN.findall(text):
            if name not in allowed and name not in unknown:
                unknown.append(name or "{{ }}")
        leftover = TOKEN.sub("", text)
        if "{{" in leftover or "}}" in leftover:
            raise TemplateError(unknown, broken=True)
    if unknown:
        raise TemplateError(unknown)


def render(text: str, values: dict[str, str]) -> str:
    return TOKEN.sub(lambda match: values.get(match.group(1), match.group(0)), text)
