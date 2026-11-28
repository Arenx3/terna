"""Screening applications end to end: scheduled by the outbox, run on the (eager) ml
worker with the stand-in model, read through the API, broadcast to the board."""

import asyncio

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection

from candidates.realtime import board_group
from demo.resumes import resume_pdf
from events.models import AuditEvent, EventType
from screening import services, tasks
from screening.models import (
    RequirementMatch,
    RequirementVector,
    ResumeExtraction,
    ResumePassage,
    Screening,
)
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db

RESUME = [
    "Lucía Torres",
    "Backend Engineer · Monterrey, NL · lucia.torres@example.com",
    "# Experience",
    "Senior Backend Engineer, Logística Norte (Jan 2019 – Present)",
    "• Python and FastAPI services; REST APIs for 2M customers.",
    "• Ran our EKS clusters in production for three years.",
    "# Languages",
    "Spanish (native), English (C1)",
]


@pytest.fixture
def apply(acme, open_job, visitor, instant):
    def send(lines: list[str] = RESUME) -> dict:
        response = visitor.apply(visitor.upload(resume_pdf(lines)))
        assert response.status_code == 202
        return acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()[0]

    return send


@pytest.fixture
def screened(apply, deliver) -> dict:
    application = apply()
    deliver()
    return application


def url(application: dict, suffix: str = "") -> str:
    return f"/api/applications/{application['id']}/screening/{suffix}"


def by_text(screening: dict) -> dict[str, dict]:
    return {r["text"]: r for r in screening["requirements"]}


def test_an_application_is_screened_once_its_resume_is_read(acme, apply, deliver):
    application = apply()
    recruiter = acme.client("recruiter")
    waiting = recruiter.get(url(application)).json()
    assert (waiting["status"], waiting["resume_status"]) == ("waiting", "pending")
    assert all(r["verdict"] is None for r in waiting["requirements"])

    deliver()

    screening = recruiter.get(url(application)).json()
    assert screening["status"] == "ready"
    assert (screening["must_total"], screening["must_meets"]) == (2, 2)
    assert (screening["nice_total"], screening["nice_meets"]) == (1, 1)
    # Must-haves weigh twice: 2 * 2 + 1 * 1.
    assert (screening["points"], screening["max_points"]) == (5, 5)
    assert screening["weights"] == {"must": 2, "nice": 1, "partial": 0.5}

    kubernetes = by_text(screening)["Kubernetes in production"]
    assert kubernetes["verdict"] == "meets"
    assert {"term": "Kubernetes", "matched": "EKS"} in kubernetes["signals"]["keyword"]["found"]
    [evidence, *_] = kubernetes["evidence"]
    text = evidence["passage"]["text"]
    assert [text[start:end] for start, end in evidence["spans"]][:2] == ["EKS", "production"]

    years = by_text(screening)["5+ years building APIs in Python"]
    assert years["verdict"] == "meets"
    assert years["signals"]["years"]["required"] == 5
    assert years["signals"]["years"]["months"] >= 60


def test_the_board_card_carries_the_counts_and_hears_when_they_change(
    acme, open_job, apply, deliver
):
    application = apply()
    layer = get_channel_layer()
    channel = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(board_group(acme.company.id, open_job["id"]), channel)

    deliver()

    async def heard() -> list[dict]:
        messages = []
        while True:
            try:
                messages.append(await asyncio.wait_for(layer.receive(channel), 1))
            except TimeoutError:
                return messages

    update = async_to_sync(heard)()[-1]
    assert update["event"] == EventType.SCREENING_COMPLETED
    assert update["application"]["id"] == application["id"]
    assert update["application"]["screening"]["must_meets"] == 2

    board = acme.client("recruiter").get(f"/api/jobs/{open_job['id']}/applications/").json()
    assert board[0]["screening"] == {
        "status": "ready",
        "must_total": 2,
        "must_meets": 2,
        "must_partial": 0,
        "nice_total": 1,
        "nice_meets": 1,
        "nice_partial": 0,
    }


def test_the_audit_log_records_each_screening_as_terna(acme, screened):
    with tenant_context(acme.company.id):
        event = AuditEvent.objects.get(type=EventType.SCREENING_COMPLETED)
    assert event.actor_id is None
    assert event.payload["must"] == [2, 2]


def test_changing_the_requirements_screens_everyone_again(acme, open_job, screened, deliver):
    recruiter = acme.client("recruiter")
    job = recruiter.get(f"/api/jobs/{open_job['id']}/").json()
    requirements = [*job["requirements"], {"text": "Terraform", "kind": "must"}]
    recruiter.patch(f"/api/jobs/{open_job['id']}/", {"requirements": requirements}, format="json")
    deliver()

    screening = recruiter.get(url(screened)).json()
    assert screening["status"] == "ready"
    assert screening["must_total"] == 3
    terraform = by_text(screening)["Terraform"]
    assert terraform["verdict"] == "no_evidence"
    assert terraform["evidence"] == []
    assert terraform["signals"]["keyword"]["missing"] == ["Terraform"]
    with tenant_context(acme.company.id):
        assert AuditEvent.objects.filter(type=EventType.JOB_REQUIREMENTS_CHANGED).count() == 1


def test_vectors_are_computed_once_and_reused(acme, screened, model):
    with tenant_context(acme.company.id):
        assert RequirementVector.objects.count() == 3
        assert not ResumePassage.objects.filter(embedding__isnull=True).exists()
        services.schedule_screenings([screened["id"]])
    calls = len(model.calls)
    tasks.screen_application(str(acme.company.id), screened["id"])
    assert len(model.calls) == calls  # nothing new to embed


def test_a_run_whose_screening_was_reset_throws_its_result_away(acme, screened):
    company = str(acme.company.id)
    with tenant_context(company):
        services.schedule_screenings([screened["id"]])
    attempt, _ = tasks._claim_screening(company, screened["id"])
    with tenant_context(company):
        services.schedule_screenings([screened["id"]])  # the requirements changed meanwhile
    assert not tasks._finish_screening(company, screened["id"], attempt, "ready", results=[])
    with tenant_context(company):
        assert Screening.objects.get().status == Screening.Status.PENDING
        assert RequirementMatch.objects.count() == 3  # the last good result stays


def test_a_failure_is_written_down_and_can_be_retried(acme, apply, deliver, model):
    application = apply()
    model.broken = RuntimeError("out of memory")
    deliver()
    recruiter = acme.client("recruiter")
    failed = recruiter.get(url(application)).json()
    assert failed["status"] == "failed"
    assert failed["detail"] == "RuntimeError: out of memory"

    model.broken = None
    response = recruiter.post(url(application, "rerun/"))
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    tasks.screen_application(str(acme.company.id), application["id"])
    assert recruiter.get(url(application)).json()["status"] == "ready"


def test_without_a_readable_resume_the_screening_waits(acme, screened):
    company = str(acme.company.id)
    with tenant_context(company):
        ResumeExtraction.objects.update(status=ResumeExtraction.Status.FAILED)
        services.schedule_screenings([screened["id"]])
    assert tasks.screen_application(company, screened["id"]) == "waiting"
    screening = acme.client("recruiter").get(url(screened)).json()
    assert (screening["status"], screening["resume_status"]) == ("waiting", "failed")


def test_screenings_never_done_are_picked_up(acme, screened):
    with tenant_context(acme.company.id):
        Screening.objects.all().delete()
        assert services.recover_screenings() == 1


def test_who_sees_and_who_reruns(acme, globex, screened):
    # Not the hiring manager's job, not an interviewer's assignment.
    assert acme.client("hiring_manager").get(url(screened)).status_code == 404
    assert acme.client("interviewer").get(url(screened)).status_code == 404
    assert acme.client("recruiter").get(url(screened)).status_code == 200
    assert acme.client("admin").post(url(screened, "rerun/")).status_code == 202
    # Another company never sees it, or reruns it.
    assert globex.client("admin").get(url(screened)).status_code == 404
    assert globex.client("admin").post(url(screened, "rerun/")).status_code == 404


def test_matches_and_vectors_stay_inside_their_company(acme, globex, screened):
    with tenant_context(globex.company.id):
        assert not Screening.objects.exists()
        assert not RequirementMatch.objects.exists()
        assert not RequirementVector.objects.exists()


def test_passages_have_a_cosine_hnsw_index():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'screening_passage_embedding'"
        )
        [definition] = cursor.fetchone()
    assert "hnsw" in definition
    assert "vector_cosine_ops" in definition


# The dictionary


DICTIONARY = "/api/screening/dictionary/"


def entry(entries: list[dict], term: str) -> dict:
    return next(e for e in entries if e["term"] == term)


def test_the_dictionary_lists_terna_entries_with_the_company_ones_on_top(acme, globex):
    recruiter = acme.client("recruiter")
    entries = recruiter.get(DICTIONARY).json()
    kubernetes = entry(entries, "Kubernetes")
    assert kubernetes["built_in"]
    assert "k8s" in kubernetes["aliases"]

    created = recruiter.post(
        DICTIONARY,
        {"term": "Montacargas", "aliases": ["forklift", " Forklift ", "grúa"]},
        format="json",
    )
    assert created.status_code == 201
    mine = entry(created.json(), "Montacargas")
    assert (mine["built_in"], mine["overrides"]) == (False, True)
    assert mine["aliases"] == ["forklift", "grúa"]  # trimmed, each once

    # The other company still has Terna's entry.
    assert entry(globex.client("recruiter").get(DICTIONARY).json(), "Montacargas")["built_in"]


def test_a_term_once_per_company(acme):
    recruiter = acme.client("recruiter")
    assert (
        recruiter.post(DICTIONARY, {"term": "Grúa", "aliases": []}, format="json").status_code
        == 201
    )
    again = recruiter.post(DICTIONARY, {"term": "grua", "aliases": ["crane"]}, format="json")
    assert again.status_code == 409
    assert again.json()["code"] == "term_exists"


def test_replacing_a_built_in_entry_screens_again_and_deleting_brings_it_back(acme, screened):
    recruiter = acme.client("recruiter")
    company = str(acme.company.id)
    created = recruiter.post(
        DICTIONARY, {"term": "Kubernetes", "aliases": ["k8s"]}, format="json"
    ).json()
    assert recruiter.get(url(screened)).json()["status"] == "pending"
    tasks.screen_application(company, screened["id"])
    found = by_text(recruiter.get(url(screened)).json())["Kubernetes in production"]
    assert {"term": "Kubernetes", "matched": "EKS"} not in found["signals"]["keyword"]["found"]

    mine = entry(created, "Kubernetes")
    restored = recruiter.delete(f"{DICTIONARY}{mine['id']}/").json()
    assert entry(restored, "Kubernetes")["built_in"]
    tasks.screen_application(company, screened["id"])
    found = by_text(recruiter.get(url(screened)).json())["Kubernetes in production"]
    assert {"term": "Kubernetes", "matched": "EKS"} in found["signals"]["keyword"]["found"]


def test_only_admins_and_recruiters_change_the_dictionary(acme):
    manager = acme.client("hiring_manager")
    assert manager.get(DICTIONARY).status_code == 200
    assert (
        manager.post(DICTIONARY, {"term": "Grúa", "aliases": []}, format="json").status_code == 403
    )
    assert acme.client("interviewer").get(DICTIONARY).status_code == 403
