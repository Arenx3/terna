# 0001. Multi-tenancy with a shared schema and row-level security

- **Status:** accepted
- **Date:** 2026-11-24

## Context

Many companies share one Terna installation. Their data is personal data about candidates, covered by the LFPDPPP in Mexico and the GDPR in Europe. One company seeing another's candidates would be a serious breach, and it only takes one query without a company filter: a new endpoint, a raw SQL report, a background task, a future contributor who does not know the convention.

The installation must also stay small enough to run with a single `docker compose up`, and to handle hundreds of companies without per-company operations.

## Decision

All companies share one schema. Every table with customer data has a `company_id` column, and PostgreSQL row-level security enforces the isolation, so the database refuses to return or accept another company's rows whatever the application asks for.

- **Two roles.** Migrations run as the owner role. The API, the workers and beat connect as `terna_app`, which is not a superuser, has no `BYPASSRLS` and owns no table, so it cannot skip, drop or change a policy. The bootstrap service creates it with a password generated on first start.
- **One policy per table.** `tenant_isolation` compares the row's company with `app_current_company()`, a SQL function that reads the `app.company_id` setting of the current transaction. Tables use `FORCE ROW LEVEL SECURITY`, so the policy applies to the owner too unless it is a superuser.
- **Fail closed.** With no company set, the function returns NULL, which matches no row: a forgotten company shows nothing and writes nothing.
- **Transaction-scoped company.** The company is set with `set_config(..., true)`, the equivalent of `SET LOCAL`, so it disappears when the transaction ends and can never leak into the next request on a reused connection. Each API request is one transaction (`ATOMIC_REQUESTS`). `TenantScopedMixin` takes the company from the `company_id` claim of the access token, which is only issued after checking membership. Celery tasks declared with `@tenant_task` take the company as their first argument and run inside `tenant_context(company_id)`.
- **Defense in depth in Django.** `TenantModel`'s default manager repeats the same predicate in SQL, so a table whose policy were ever lost would still not leak. New rows take the active company automatically.
- **Automatic policies.** After every `migrate`, a `post_migrate` hook enables row-level security and (re)creates the policy on every `TenantModel` table. A test fails if any table is neither isolated nor declared global in `GLOBAL_TABLES`, so a new table cannot slip through unclassified.
- **Cross-company system jobs** (retention, reminders) list company ids through `app_all_company_ids()`, a `SECURITY DEFINER` function that returns ids and nothing else, then fan out one task per company.
- **Tested as production runs.** The whole test suite runs as the app role, and dedicated tests check reads, updates, deletes and inserts across companies through the API and with raw SQL, plus attempts to turn row security off, drop a policy or escalate to the owner role.

## Alternatives considered

- **Application filtering only.** Simplest, and what most Django projects do. One missing `.filter(company=...)` leaks, and raw SQL, reports and new code paths have no safety net. Kept as the second layer, not the only one.
- **Schema per company** (for example with `django-tenants`). Strong isolation, but every migration runs once per company, connections juggle `search_path`, cross-company analytics and shared reference data get awkward, and thousands of schemas bloat the catalog.
- **Database per company.** Strongest isolation, but each company needs its own database to provision, migrate, back up and pool connections for. It does not fit a self-contained installation.
- **Session-level `SET` instead of `SET LOCAL`.** Same policies, but a setting that outlives its transaction can leak to the next user of a pooled connection if a reset is ever missed.

## Consequences

- Isolation is enforced by the database: application bugs fail closed instead of leaking.
- One schema and one migration run, whatever the number of companies.
- Every request runs in a transaction. Endpoints that must work without the database (liveness, health, API docs) opt out with `non_atomic_requests`.
- Long tasks such as transcription must keep their tenant transactions short: read inputs, process outside the transaction, then write in a new `tenant_context`.
- Policies are applied by the `post_migrate` hook rather than written in each migration file. The schema guard tests make up for that visibility.
- The migration role must be a superuser or have `BYPASSRLS`, and the app role must never own tables or run migrations.
- Transaction-scoped settings stay compatible with a transaction-mode connection pooler such as PgBouncer, if one is ever added.
