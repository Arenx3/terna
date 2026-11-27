"""Synthetic résumés with their personal data marked, to measure redaction.

`[[kind|text]]` is personal data that must never reach the redacted text;
`{{text}}` is what must survive it (skills, companies, job titles, numbers).
Every person, address and number here is made up.
"""

import re
from dataclasses import dataclass

MARK = re.compile(r"\[\[(\w+)\|(.+?)\]\]|\{\{(.+?)\}\}")


@dataclass(frozen=True)
class Sample:
    name: str  # as the application gives it
    kind: str  # "pdf" or "docx"
    lines: tuple[str, ...]

    def parsed(self) -> tuple[list[str], list[tuple[str, str]], list[str]]:
        """(clean lines, [(kind, personal text)], [text to keep])."""
        clean, personal, keep = [], [], []
        for line in self.lines:
            for match in MARK.finditer(line):
                if match.group(1):
                    personal.append((match.group(1), match.group(2)))
                else:
                    keep.append(match.group(3))
            clean.append(MARK.sub(lambda m: m.group(2) or m.group(3), line))
        return clean, personal, keep


SAMPLES = {
    "es-full-header": Sample(
        "Lucía Torres Gómez",
        "pdf",
        (
            "[[name|Lucía Torres Gómez]]",
            "{{Ingeniera de datos}} · [[location|Monterrey, N.L.]] · "
            "[[email|lucia.torres92@example.com]] · [[phone|+52 81 1234 5678]]",
            "[[url|linkedin.com/in/lucia-torres-gomez]] · [[url|github.com/ltorres]]",
            "CURP: [[curp|TOGL920214MNLRMC08]] · RFC: [[rfc|TOGL920214AB1]]",
            "Fecha de nacimiento: [[birthdate|14/02/1992]] · [[age|32 años]] · "
            "Estado civil: [[marital_status|casada]]",
            "Sexo: [[gender|femenino]] · Nacionalidad: [[nationality|mexicana]]",
            "Dirección: [[address|Av. Constitución 1500, Col. Centro, C.P. 64000]], "
            "[[location|Monterrey, N.L.]]",
            "# Perfil",
            "{{Ingeniera de datos}} con {{8 años de experiencia}} en {{Python}}, {{SQL}} y "
            "{{Power BI}}.",
            "# Experiencia laboral",
            "{{Ingeniera de datos}}, {{Acme Industrial}} — ene 2020 – actual",
            "• Diseñé el data lake en {{AWS}} y pipelines en {{Airflow}}.",
            "{{Analista de datos}}, {{Grupo Andino}} (2016 – 2019)",
            "• Reportes en {{Power BI}} para {{12 plantas}}.",
            "# Educación",
            "{{Ingeniería Industrial}}, {{Tecnológico de Monterrey}}, 2010 – 2015",
            "# Idiomas",
            "Español (nativo), {{inglés C1}}",
            "# Referencias",
            "[[name|Juan Pérez]], director de TI en {{Acme Industrial}}, tel. "
            "[[phone|81 2345 6789]]",
        ),
    ),
    "en-designer-docx": Sample(
        "Daniel Smith",
        "docx",
        (
            "[[name|Daniel Smith]]",
            "{{Senior Product Designer}} | [[location|Guadalajara, Jalisco]] | "
            "[[phone|(33) 3456-7890]] | [[email|dan.smith@example.com]]",
            "[[url|https://dribbble.com/dansmith]] · [[url|www.dansmith.design]]",
            "Date of birth: [[birthdate|March 3, 1990]] · [[age|34 years old]] · "
            "Marital status: [[marital_status|married]] · Nationality: [[nationality|American]]",
            "# Summary",
            "{{Product designer}} with {{10 years of experience}} in {{B2B SaaS}}, {{Figma}} "
            "and {{design systems}}.",
            "# Experience",
            "{{Senior Product Designer}}, {{Fintech Pacífico}} (Jan 2021 – Present)",
            "• Led research with {{40 users}} per quarter; redesigned the {{Kubernetes}} console.",
            "{{Product Designer}}, {{Logística Norte}} (2015 – 2020)",
            "# Education",
            "{{B.A. Industrial Design}}, {{Universidad de Guadalajara}}, 2009 – 2013",
            "# Skills",
            "{{Figma}}, {{Framer}}, {{HTML}}, {{CSS}}, {{React}}",
            "# References",
            "[[name|Laura Méndez]], {{VP of Product}} at {{Fintech Pacífico}} — "
            "[[email|laura.mendez@example.com]]",
        ),
    ),
    "es-name-variants": Sample(
        "José Ángel Hernández López",
        "pdf",
        (
            "[[name|JOSÉ ÁNGEL HERNÁNDEZ]]",
            "[[name|Hernández, José Ángel]] — {{Desarrollador backend}}",
            "Tel. [[phone|55-1234-5678]] · [[email|jose.angel.hdz@example.com]] · "
            "[[location|Ciudad de México]]",
            "[[age|29 años]], [[marital_status|soltero]], [[nationality|mexicano]]",
            "NSS: [[nss|12345678901]]",
            "# Perfil profesional",
            "Soy [[name|Jose Angel]], {{desarrollador backend}} con {{6 años en Django}} y {{Go}}.",
            "# Experiencia",
            "{{Backend Developer}}, {{Grupo Bimbo}} — 2019 – 2025",
            "• Migré {{40 servicios}} a {{Kubernetes}} con {{Helm}} y {{ArgoCD}}.",
            "• Colas con {{Kafka}} y {{RabbitMQ}}; datos separados por comas en {{CSV}}.",
            "# Habilidades",
            "{{Python}}, {{Django}}, {{Go}}, {{PostgreSQL}}, {{Kafka}}, {{Terraform}}",
            "# Certificaciones",
            "{{Certified Kubernetes Administrator (CKA)}}, 2021",
            "# Otros",
            "Firma: [[name|J. Á. Hernández]]",
        ),
    ),
    "en-us-address": Sample(
        "Emily Johnson",
        "pdf",
        (
            "[[name|Emily Johnson]]",
            "[[address|742 Evergreen Terrace]], [[location|Springfield, IL]] "
            "[[address|62704]] · [[phone|+1 (217) 555-0142]]",
            "[[email|emily.j@example.com]] · [[url|github.com/emilyj]]",
            "SSN: [[nss|123-45-6789]] · DOB: [[birthdate|1988-07-21]] · Gender: [[gender|Female]]",
            "# Professional experience",
            "{{Data Engineer}}, {{Acme Corp}} (2018 - present)",
            "• Built {{Spark}} jobs on {{Databricks}}; cut costs {{35%}}.",
            "• Mentored {{5 engineers}}; ran {{SQL}} training for {{Marketing}}.",
            "# Education",
            "{{M.S. Computer Science}}, {{University of Illinois}}, 2012 - 2014",
            "# Languages",
            "{{English (native)}}, {{Spanish (B2)}}",
        ),
    ),
    "es-references": Sample(
        "Valeria Ruiz",
        "pdf",
        (
            "[[name|Valeria Ruiz]]",
            "{{Gerente de proyectos}} · [[email|valeria.ruiz@example.com]] · WhatsApp "
            "[[phone|+57 300 123 4567]]",
            "# Sobre mí",
            "Tengo [[age|35 años]], soy de nacionalidad [[nationality|colombiana]] y vivo en "
            "[[location|Bogotá]].",
            "{{Gerente de proyectos}} con {{12 años de experiencia}} en {{logística}} y {{Scrum}}.",
            "# Experiencia",
            "{{PMO}}, {{Retail Occidente}} — feb 2018 – dic 2024",
            "• Coordiné {{15 personas}} y un presupuesto de {{2 millones}}.",
            "# Formación",
            "{{Maestría en Administración}}, {{Universidad de los Andes}}, 2012 – 2014",
            "# Referencias",
            "[[name|Carlos Ramírez]] — {{Director de Operaciones}}, [[phone|+57 310 555 1212]]",
            "[[name|Ximena Altamirano]], jefa directa, [[email|ximena.a@example.com]]",
        ),
    ),
    "en-no-headings": Sample(
        "Michael Brown",
        "pdf",
        (
            "[[name|Michael Brown]]",
            "[[email|mbrown@example.com]] / [[phone|415-555-0199]]",
            "{{Software engineer}} at {{Stripe}} since 2019, building {{payments APIs}} in "
            "{{Ruby}} and {{Go}}.",
            "Previously {{QA analyst}} at {{Oracle}} (2014 - 2019). {{AWS Certified Developer}}.",
        ),
    ),
}
