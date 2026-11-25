# 0002. Transactional outbox for domain events

- **Status:** accepted
- **Date:** 2026-11-25

## Context

Many changes in Terna need follow-up work outside the request that makes them. A stage move must reach the audit log, the board other recruiters have open, analytics and sometimes an email to the candidate. Recruiter overrides, blind-review reveals and access to personal data must leave a record that nobody can alter. That record is part of how Terna answers to the LFPDPPP and the GDPR.

Doing that work inside the request would make it slow and fragile. Sending it to Celery directly from the view has two failure modes:
- The task is queued, and then the transaction rolls back. The world hears about a change that never happened.
- The transaction commits, and then the broker is down or the process dies before queuing. The change happened, but its audit entry and notifications are lost.

## Decision

Domain events go through a transactional outbox.

- **Written with the change.** `events.outbox.emit()` inserts an `OutboxEvent` row in the same transaction as the change, and refuses to run outside one. A rollback removes the event with the change, and a commit keeps both.
- **Delivered after commit, at least once.**
  - `emit()` registers an `on_commit` hook that queues the `dispatch_outbox` task. The hook is robust: a broker that is down is logged, not raised.
  - Beat runs the same task every 30 seconds as a safety net.
  - The dispatcher locks a batch of pending events with `SELECT … FOR UPDATE SKIP LOCKED`, so concurrent dispatchers never take the same event. It hands each event to every consumer and marks it dispatched in the same transaction. If a worker dies halfway, the batch rolls back and its events stay pending.
- **Idempotent consumers.** Delivery is at least once, so every consumer must tolerate repeats. The audit consumer inserts with `ON CONFLICT DO NOTHING` on a unique `source_event_id`.
- **Failures are visible.**
  - A consumer runs inside a savepoint, so its failure only undoes its own writes.
  - The event records the attempt and the error, and is retried on the next run.
  - After 8 attempts it is parked as `failed`, with its reason, for a person to look at.
- **Tenancy.** Outbox and audit rows are tenant data under row-level security. The dispatcher has no company, so it asks `app_outbox_pending_companies()`, a `SECURITY DEFINER` function that returns company ids only, and processes each company in its own `tenant_context`.
- **Who did it.** API views set the actor for the request. Code outside requests, such as workers and the demo seed, uses `acting_as(user)`. The actor's id and name, and the entity's label, are copied into the event, not linked, so an entry still reads correctly after the person leaves or the job is deleted.
- **Append-only audit log.** `AuditEvent` has a `BEFORE UPDATE OR DELETE` trigger that raises for every role, the table owner included. The app role is never granted `TRUNCATE`. Admins read the log through `/api/audit/`, filtered by area, person and date range.

## Alternatives considered

- **Queue Celery tasks directly from views.** Simplest, and it suffers from both failure modes above.
- **Django signals.** Synchronous and in-process: they run inside the request, and a failure in one consumer breaks the request or is silently swallowed. Nothing survives a crash.
- **Change data capture** (Debezium on the PostgreSQL WAL). It catches every row change without touching application code. But it needs Kafka or a similar broker and a connector service, which goes against a self-contained `docker compose up`. And row changes are not domain events: the intent (a stage move, a reveal) has to be reconstructed.
- **An external event bus** (Kafka, RabbitMQ streams). Durable and scalable, but another stateful service to run, and the dual-write problem between the database and the bus remains without an outbox.

## Consequences

- No event is lost after a commit, and none is emitted for a change that rolled back.
- Consumers must be idempotent; that is the price of at-least-once delivery.
- Delivery is near real time (right after commit), with up to 30 seconds of delay when the broker was unreachable.
- The outbox table grows with every change. Dispatched rows can be purged by a retention job without touching the audit log.
- Audit rows can't be changed or deleted by the application, including by cascades: deleting a company would fail on its audit log. Removing a company's data will need an explicit, recorded procedure run as the owner role, as part of the privacy work in Phase 5.
- New consumers (real-time board, notifications, analytics) subscribe by adding to `events.dispatch.CONSUMERS`.
