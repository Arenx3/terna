import pytest
from django.db import DatabaseError, connection, transaction

from events import dispatch
from events.models import AuditEvent, EventType, OutboxEvent
from events.outbox import OutsideTransactionError, acting_as, emit
from tenancy.context import tenant_context

pytestmark = pytest.mark.django_db


def emit_job_event(company_id, title: str = "Data Analyst", actor=None) -> OutboxEvent:
    with tenant_context(company_id), acting_as(actor):
        return emit(EventType.JOB_CREATED, entity_type="job", entity_id="j-1", label=title)


def audit_rows(company_id) -> list[AuditEvent]:
    with tenant_context(company_id):
        return list(AuditEvent.objects.order_by("id"))


def outbox_rows(company_id) -> list[OutboxEvent]:
    with tenant_context(company_id):
        return list(OutboxEvent.objects.order_by("id"))


class RolledBackError(Exception):
    pass


def test_a_rolled_back_change_emits_nothing(acme):
    def change_that_fails():
        with tenant_context(acme.company.id):
            emit(EventType.JOB_CREATED, entity_type="job", entity_id="j-1", label="Gone")
            raise RolledBackError

    with pytest.raises(RolledBackError):
        change_that_fails()

    assert outbox_rows(acme.company.id) == []


@pytest.mark.django_db(transaction=True)
def test_events_need_the_changes_transaction():
    # Autocommit: an event written here could survive a change that rolls back.
    with pytest.raises(OutsideTransactionError):
        emit(EventType.JOB_CREATED, entity_type="job", entity_id="j-1")


def test_committed_events_reach_the_audit_log_with_their_actor(acme):
    ana = acme.people["admin"]
    event = emit_job_event(acme.company.id, actor=ana)

    assert dispatch.dispatch_all() == 1

    [row] = audit_rows(acme.company.id)
    assert (row.type, row.actor_id, row.actor_name) == ("job.created", ana.id, ana.full_name)
    assert row.entity_label == "Data Analyst"
    [sent] = outbox_rows(acme.company.id)
    assert sent.id == event.id
    assert sent.status == OutboxEvent.Status.DISPATCHED
    assert sent.dispatched_at is not None


def test_a_second_delivery_records_nothing_new(acme):
    event = emit_job_event(acme.company.id)

    with tenant_context(acme.company.id):
        dispatch.record_audit(event)
        dispatch.record_audit(event)

    assert len(audit_rows(acme.company.id)) == 1


def test_a_worker_dying_halfway_loses_nothing(acme, monkeypatch):
    emit_job_event(acme.company.id, "First")
    emit_job_event(acme.company.id, "Second")
    real_deliver = dispatch.deliver
    delivered: list[int] = []

    def die_on_second(event):
        if delivered:
            raise SystemExit("worker killed")
        delivered.append(event.id)
        return real_deliver(event)

    monkeypatch.setattr(dispatch, "deliver", die_on_second)
    with pytest.raises(SystemExit):
        dispatch.dispatch_company(acme.company.id)

    # The batch's transaction rolled back: nothing recorded, everything still pending.
    assert audit_rows(acme.company.id) == []
    assert {e.status for e in outbox_rows(acme.company.id)} == {OutboxEvent.Status.PENDING}

    monkeypatch.undo()
    assert dispatch.dispatch_all() == 2
    assert [row.entity_label for row in audit_rows(acme.company.id)] == ["First", "Second"]


def test_a_failing_consumer_is_retried_then_parked_with_its_reason(acme, monkeypatch):
    emit_job_event(acme.company.id)

    def broken(event):
        raise ValueError("search index unavailable")

    monkeypatch.setattr(dispatch, "CONSUMERS", [dispatch.record_audit, broken])
    for _ in range(dispatch.MAX_ATTEMPTS):
        dispatch.dispatch_all()

    [event] = outbox_rows(acme.company.id)
    assert event.status == OutboxEvent.Status.FAILED
    assert event.attempts == dispatch.MAX_ATTEMPTS
    assert event.last_error == "ValueError: search index unavailable"
    # The audit write shared the failed delivery's savepoint, so it was undone too.
    assert audit_rows(acme.company.id) == []
    assert dispatch.pending_companies() == []


def test_one_run_delivers_every_companys_events_to_its_own_log(acme, globex):
    emit_job_event(acme.company.id, "Acme job")
    emit_job_event(globex.company.id, "Globex job")

    assert sorted(dispatch.pending_companies()) == sorted([acme.company.id, globex.company.id])
    assert dispatch.dispatch_all() == 2

    assert [r.entity_label for r in audit_rows(acme.company.id)] == ["Acme job"]
    assert [r.entity_label for r in audit_rows(globex.company.id)] == ["Globex job"]


@pytest.mark.parametrize(
    "change",
    [
        lambda: AuditEvent.objects.update(actor_name="Someone else"),
        lambda: AuditEvent.objects.all().delete(),
        lambda: connection.cursor().execute("UPDATE events_auditevent SET entity_label = 'x'"),
        lambda: connection.cursor().execute("DELETE FROM events_auditevent"),
    ],
    ids=["orm-update", "orm-delete", "sql-update", "sql-delete"],
)
def test_the_audit_log_cannot_be_rewritten(acme, change):
    emit_job_event(acme.company.id)
    dispatch.dispatch_all()

    with (
        pytest.raises(DatabaseError, match="append-only"),
        tenant_context(acme.company.id),
        transaction.atomic(),
    ):
        change()

    [row] = audit_rows(acme.company.id)
    assert row.entity_label == "Data Analyst"
