"""Demo data: two fictional companies, a team per role and a few jobs.

Every name, company and address here is made up. The seed is idempotent: it
looks things up by their natural keys and only adds what is missing, so it can
run on every start without duplicating anything or undoing a visitor's edits.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership, User
from accounts.sessions import user_memberships
from events.outbox import acting_as
from jobs import services
from jobs.models import Job
from jobs.services import RequirementItem
from tenancy.context import tenant_context
from tenancy.models import Company
from tenancy.services import create_company

DEFAULT_PASSWORD = "terna-demo-2026"  # noqa: S105 (public demo credential, documented in the README)
OWNER_EMAIL = "ana@acme.mx"

Role = Membership.Role


@dataclass(frozen=True)
class Person:
    email: str
    full_name: str
    role: str


@dataclass(frozen=True)
class DemoJob:
    title: str
    status: str
    language: str
    department: str
    location: str
    workplace: str
    must: tuple[str, ...]
    nice: tuple[str, ...] = ()
    description: str = ""
    salary: tuple[int, int] | None = None
    owner: str | None = None


@dataclass(frozen=True)
class DemoCompany:
    name: str
    team: tuple[Person, ...]
    jobs: tuple[DemoJob, ...] = field(default=())


ANA = Person(OWNER_EMAIL, "Ana Pérez", Role.ADMIN)

COMPANIES = (
    DemoCompany(
        name="Acme Industrial",
        team=(
            ANA,
            Person("luis@acme.mx", "Luis Hernández", Role.RECRUITER),
            Person("marta@acme.mx", "Marta Gómez", Role.HIRING_MANAGER),
            Person("diego@acme.mx", "Diego Ramírez", Role.INTERVIEWER),
        ),
        jobs=(
            DemoJob(
                title="Senior Backend Engineer",
                status=Job.Status.OPEN,
                language="en",
                department="Engineering",
                location="Monterrey, NL",
                workplace=Job.Workplace.HYBRID,
                must=(
                    "5+ years building APIs in Python",
                    "Kubernetes in production",
                    "PostgreSQL at scale: query tuning, indexing, migrations",
                ),
                nice=(
                    "Event-driven systems with Kafka or RabbitMQ",
                    "Mentoring other engineers",
                ),
                description=(
                    "You'll own the services behind our ordering platform, which handles "
                    "3,000 orders a minute at peak. Small team, real ownership, on-call "
                    "shared fairly."
                ),
                salary=(80_000, 110_000),
                owner="marta@acme.mx",
            ),
            DemoJob(
                title="Diseñadora o diseñador de producto",
                status=Job.Status.OPEN,
                language="es",
                department="Producto",
                location="Ciudad de México",
                workplace=Job.Workplace.REMOTE,
                must=(
                    "Portafolio con productos SaaS publicados",
                    "Figma a nivel avanzado",
                    "Investigación con usuarios",
                ),
                nice=("Experiencia construyendo un sistema de diseño", "Nociones de HTML y CSS"),
                description=(
                    "Diseñarás las herramientas que usan nuestros técnicos de planta todos "
                    "los días. Trabajarás con ingeniería desde el primer boceto."
                ),
                salary=(55_000, 70_000),
                owner="marta@acme.mx",
            ),
            DemoJob(
                title="Analista de datos",
                status=Job.Status.DRAFT,
                language="es",
                department="Operaciones",
                location="Ciudad de México",
                workplace=Job.Workplace.ONSITE,
                must=("SQL avanzado",),
                nice=("Python con pandas", "Power BI o Looker"),
            ),
            DemoJob(
                title="Líder de Customer Success",
                status=Job.Status.CLOSED,
                language="es",
                department="Clientes",
                location="Guadalajara, Jal.",
                workplace=Job.Workplace.HYBRID,
                must=("3+ años en customer success B2B", "Inglés avanzado"),
                nice=("Experiencia con HubSpot",),
            ),
        ),
    ),
    DemoCompany(
        name="Globex México",
        team=(
            ANA,
            Person("paola@globex.mx", "Paola Reyes", Role.RECRUITER),
            Person("jorge@globex.mx", "Jorge Medina", Role.HIRING_MANAGER),
        ),
        jobs=(
            DemoJob(
                title="Contador o contadora sénior",
                status=Job.Status.OPEN,
                language="es",
                department="Finanzas",
                location="Querétaro, Qro.",
                workplace=Job.Workplace.ONSITE,
                must=(
                    "Licenciatura en Contaduría",
                    "Cierres mensuales y conciliaciones bancarias",
                    "CFDI 4.0 y obligaciones fiscales ante el SAT",
                ),
                nice=("SAP Business One",),
                salary=(38_000, 45_000),
                owner="jorge@globex.mx",
            ),
            DemoJob(
                title="Ejecutivo o ejecutiva de ventas B2B",
                status=Job.Status.OPEN,
                language="es",
                department="Ventas",
                location="Ciudad de México",
                workplace=Job.Workplace.HYBRID,
                must=("2+ años en ventas consultivas B2B", "Manejo de un CRM"),
                nice=("Cartera de clientes en el sector industrial",),
            ),
        ),
    ),
)


def seed(*, password: str) -> list[str]:
    report: list[str] = []
    owner = _person(ANA, password)
    existing = {m.company_name: m.company_id for m in user_memberships(owner.id)}
    for demo in COMPANIES:
        with transaction.atomic():
            company_id = existing.get(demo.name)
            if company_id is None:
                company_id = create_company(demo.name).id
                report.append(f"Created company {demo.name}.")
            # The audit log shows the demo jobs as Ana's work.
            with tenant_context(company_id), acting_as(owner):
                company = Company.objects.get()
                for person in demo.team:
                    _member(company, _person(person, password), person.role)
                created = [job.title for job in demo.jobs if _job(job, owner)]
            if created:
                report.append(f"{demo.name}: created jobs {', '.join(created)}.")
    return report or ["Demo data already in place."]


def _person(person: Person, password: str) -> User:
    user = User.objects.filter(email=person.email).first()
    if user is None:
        user = User.objects.create_user(
            person.email,
            password,
            full_name=person.full_name,
            language="es",
            email_verified_at=timezone.now(),
        )
    return user


def _member(company: Company, user: User, role: str) -> None:
    if not Membership.objects.filter(user=user).exists():
        Membership.objects.create(company=company, user=user, role=role)


def _job(demo: DemoJob, created_by: User) -> bool:
    if Job.objects.filter(title=demo.title).exists():
        return False
    owner = User.objects.filter(email=demo.owner).first() if demo.owner else None
    low, high = demo.salary or (None, None)
    job = services.create_job(
        created_by=created_by,
        fields={
            "title": demo.title,
            "department": demo.department,
            "location": demo.location,
            "workplace": demo.workplace,
            "language": demo.language,
            "description": demo.description,
            "salary_min": low,
            "salary_max": high,
            "hiring_manager_id": owner.id if owner else None,
        },
        requirements=[RequirementItem(text, "must") for text in demo.must]
        + [RequirementItem(text, "nice") for text in demo.nice],
    )
    if demo.status != Job.Status.DRAFT:
        services.publish(job)
    if demo.status == Job.Status.CLOSED:
        services.close(job)
    return True
