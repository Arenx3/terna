"""Words that mean the same skill, in Spanish and English: "k8s" is Kubernetes.

Terna ships the entries below. A company adds its own, or replaces one of these
with an entry under the same term (see `Synonym`), from its settings. Matching
reads the merged result, so a correction applies to every screening after it.
"""

import unicodedata
from dataclasses import dataclass

# term: aliases. The term is how the entry is shown; it also counts as an alias.
BUILT_IN: dict[str, tuple[str, ...]] = {
    # Software
    "Kubernetes": ("k8s", "EKS", "GKE", "AKS", "OpenShift"),
    "PostgreSQL": ("Postgres", "psql"),
    "SQL": ("PostgreSQL", "Postgres", "MySQL", "SQL Server", "T-SQL", "PL/SQL", "SQLite"),
    "JavaScript": ("JS", "ECMAScript"),
    "TypeScript": ("TS",),
    "Python": (),
    "Node.js": ("Node", "NodeJS"),
    "React": ("React.js", "ReactJS"),
    "API": ("APIs", "REST", "RESTful", "GraphQL"),
    "Docker": ("contenedores Docker",),
    "AWS": ("Amazon Web Services",),
    "Google Cloud": ("GCP",),
    "Azure": ("Microsoft Azure",),
    "Terraform": (),
    "Kafka": ("Apache Kafka",),
    "RabbitMQ": (),
    "CI/CD": (
        "integración continua",
        "continuous integration",
        "GitHub Actions",
        "GitLab CI",
        "Jenkins",
    ),
    "Git": ("GitHub", "GitLab"),
    "Machine learning": ("aprendizaje automático", "ML"),
    "HTML": ("HTML5",),
    "CSS": ("CSS3", "Tailwind", "Sass"),
    "Figma": (),
    # Data and business tools
    "Excel": ("Microsoft Excel", "hojas de cálculo", "spreadsheets"),
    "Power BI": ("PowerBI",),
    "Looker": ("Looker Studio",),
    "Tableau": (),
    "pandas": (),
    "CRM": ("Salesforce", "HubSpot", "Zoho", "Pipedrive", "Dynamics 365"),
    "HubSpot": (),
    "Salesforce": (),
    "SAP Business One": ("SAP B1",),
    "SAP": (),
    # Finance (Mexico)
    "Contaduría": ("contabilidad", "contador público", "contadora pública", "accounting"),
    "Conciliaciones bancarias": ("conciliación bancaria", "bank reconciliation"),
    "Cierres mensuales": ("cierre mensual", "cierre contable", "month-end close"),
    "CFDI": ("factura electrónica", "facturación electrónica", "e-invoicing"),
    "Nómina": ("payroll",),
    # Sales and customers
    "Ventas": ("sales", "venta"),
    "Ventas consultivas": ("venta consultiva", "consultative selling", "solution selling"),
    "B2B": ("business to business", "empresa a empresa"),
    "Customer success": ("éxito del cliente", "éxito de clientes"),
    # Product and design
    "Investigación con usuarios": (
        "investigación de usuarios",
        "user research",
        "UX research",
        "entrevistas con usuarios",
        "pruebas de usabilidad",
        "usability testing",
    ),
    "Sistema de diseño": ("design system",),
    "Portafolio": ("portfolio",),
    "SaaS": ("software as a service",),
    # Ways of working
    "Liderazgo": ("leadership", "líder de equipo", "team lead"),
    "Mentoría": ("mentoring", "mentorship", "mentor", "mentora", "mentored"),
    "Metodologías ágiles": ("agile", "ágil", "Scrum", "Kanban"),
    "Gestión de proyectos": ("project management", "PMP"),
    "Reclutamiento": ("recruiting", "recruitment", "talent acquisition", "atracción de talento"),
    # Industry
    "Lean manufacturing": ("manufactura esbelta", "Six Sigma", "Seis Sigma", "Kaizen"),
    "Montacargas": ("forklift",),
    "AutoCAD": (),
    # Languages
    "Inglés": ("English",),
    "Español": ("Spanish",),
    "Francés": ("French",),
    "Portugués": ("Portuguese",),
    "Alemán": ("German",),
}

# Languages people state a level for ("inglés B2"), checked by their own rule.
LANGUAGES = frozenset({"ingles", "espanol", "frances", "portugues", "aleman"})

MAX_TERM = 80
MAX_ALIASES = 30


def fold(text: str) -> str:
    """Lowercase without accents: "Contaduría" -> "contaduria"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def key_of(term: str) -> str:
    return " ".join(fold(term).split())


@dataclass(frozen=True)
class Entry:
    term: str
    aliases: tuple[str, ...]
    built_in: bool
    # A company's entry that replaces a built-in one.
    overrides: bool = False
    id: int | None = None

    @property
    def key(self) -> str:
        return key_of(self.term)

    @property
    def words(self) -> tuple[str, ...]:
        """The term and every alias, each once."""
        seen, out = set(), []
        for word in (self.term, *self.aliases):
            if key_of(word) not in seen:
                seen.add(key_of(word))
                out.append(word)
        return tuple(out)


def built_in_entries() -> list[Entry]:
    return [Entry(term, aliases, built_in=True) for term, aliases in BUILT_IN.items()]


def entries() -> list[Entry]:
    """The active company's dictionary: Terna's entries with the company's on top."""
    from screening.models import Synonym

    merged = {entry.key: entry for entry in built_in_entries()}
    for row in Synonym.objects.order_by("key"):
        merged[row.key] = Entry(
            row.term,
            tuple(row.aliases),
            built_in=False,
            overrides=row.key in merged and merged[row.key].built_in,
            id=row.id,
        )
    return sorted(merged.values(), key=lambda entry: entry.key)
