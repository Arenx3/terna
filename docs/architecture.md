# Architecture

This document describes the target architecture. It evolves with the code. Significant decisions are recorded in [architecture decision records](adr/).

## Services

Everything runs from a single `docker compose up`.

| Service | Role |
|---|---|
| `nginx` | Reverse proxy and static frontend. Upgrades WebSocket connections. |
| `backend` | Django on ASGI: REST API and WebSockets (Django Channels). |
| `worker-default` | Email, notifications, outbox dispatch, alerts, retention purges. |
| `worker-media` | FFmpeg: adaptive HLS, thumbnails, audio extraction. |
| `worker-ml` | Résumé parsing, embeddings and transcription. Runs one task at a time because of memory use. |
| `beat` | Scheduled tasks: retention, reminders, response alerts, recovery of stuck jobs. |
| `postgres` | PostgreSQL 16 with `pgvector`. Row-level security on all tenant data. |
| `redis` | Celery broker, Channels layer and cache, each in its own logical database. |
| `storage` | RustFS, S3-compatible object storage for résumés, recordings and HLS output. |
| `mailpit` | Local inbox that catches all outgoing email. |
| `secrets-init` | Generates secrets on first start, so no configuration is required. |
| `bootstrap` | One-shot, as the database owner: creates the unprivileged app role, applies migrations (which enable row-level security) and creates the storage bucket before the API and workers start. |

Each worker consumes its own queue. A long transcription never delays an email or an upload.

## Main flows

### Application and screening

1. The candidate requests an upload URL, then uploads the résumé straight to storage. The file never passes through Django.
2. The application is created. An outbox event, `application.submitted`, is written in the same transaction.
3. `worker-ml` extracts the text, splits it into passages tagged with section and page, and redacts personal data: rules for contact details, IDs (CURP, RFC, NSS), age, birth date, marital status, gender, nationality and address; the candidate's own name in any form; and a small local entity recognizer whose findings are only kept where context confirms them. Each passage keeps its original for the people who can open the profile, plus a redacted copy.
4. It computes an embedding for each passage and matches the passages against each requirement: keywords with Spanish and English synonyms, meaning (a local multilingual model over `pgvector`), and rules for years of experience and language levels. Everything that feeds a model reads passages through `screening.analysis`, which only hands out the redacted copy. See [ADR 0003](adr/0003-explainable-requirement-matching.md).
5. Each requirement's verdict is saved with the signals behind it and the exact spans of the résumé that prove it. `screening.completed` updates the kanban card and the open profile live over WebSockets.
6. When the job's requirements or the company's synonyms change, its candidates are screened again.

### Async screening answer

1. The browser records with `MediaRecorder` and uploads each answer in parts (S3 multipart), so a dropped connection loses nothing.
2. `worker-media` converts the video to HLS, makes a thumbnail and extracts mono 16 kHz audio. Voice-only answers skip the video steps.
3. `worker-ml` transcribes with `faster-whisper`. It produces word-level timestamps and detects the language.
4. Transcript segments are indexed for full-text and semantic search. Text answers go straight to this step.

## Multi-tenancy

Decision record: [ADR-0001](adr/0001-multi-tenancy-with-row-level-security.md).

- Every row of customer data carries a `company_id`. All tenants share one schema. Models with customer data subclass `TenantModel`.
- PostgreSQL row-level security policies compare that column to `app_current_company()`, which reads `app.company_id`. This setting is applied with `SET LOCAL` inside each request transaction (`ATOMIC_REQUESTS`) and each Celery task (`@tenant_task`). With no company set, queries return no rows.
- The API takes the company from the `company_id` claim of the access token (`TenantScopedMixin`). Switching company means a new token.
- Django connects as `terna_app`: no superuser, no `BYPASSRLS`, owns no table. Tables use `FORCE ROW LEVEL SECURITY`, so even an owner would not bypass the policies. Only the bootstrap service, which runs migrations, uses the owner role.
- Every `migrate` applies the policies to new tenant tables automatically. A test fails if a table is neither tenant-scoped nor declared global.
- Django querysets also filter by company, in SQL, as defense in depth.
- Isolation is tested through the API and with raw SQL, and the whole test suite runs as the app role.

## Events and audit

- **Transactional outbox:** domain events are written in the same transaction as the change they describe. A dispatcher then delivers them to the audit log, notifications, analytics and real-time updates. A rolled-back change emits nothing, and a committed change is never lost. See [ADR 0002](adr/0002-transactional-outbox.md).
- **Append-only audit log:** a database trigger rejects `UPDATE` and `DELETE` on audit rows. Recruiter overrides, stage moves, blind-mode reveals and data access are all recorded.

## Real time

Django Channels with the Redis channel layer. Each company and each job has its own group, carrying:
- pipeline moves
- who is viewing a candidate (presence)
- comments and mentions
- processing progress

## Search

- PostgreSQL full-text search, with English and Spanish configurations, for keywords.
- `pgvector` with an HNSW index for semantic similarity.
- No separate search engine: one less service to run.

## Local AI

| Task | Tool | Notes |
|---|---|---|
| Text extraction | PDF and DOCX parsers | Scanned PDFs without text are flagged for manual review |
| Personal data redaction | Rules plus entity recognition | Runs before any embedding is computed |
| Matching | `paraphrase-multilingual-MiniLM-L12-v2` (`sentence-transformers`, CPU), synonyms and rules | Works across Spanish and English. Pinned revision, only in the ml image |
| Transcription | `faster-whisper` on CPU | Model size configurable. CI uses the smallest model. |

Models are downloaded once into a dedicated volume. No external API is called. Terna never analyzes faces, tone of voice or expressions.

## Authentication and access

- **Team members:** sign in with email. The access token lives 10 minutes, only in memory, and carries the active company (`company_id`), which scopes every request. The refresh token lives in an `httpOnly`, `SameSite=Strict` cookie restricted to `/api/auth/`, so JavaScript never reads it and other sites never send it. Each refresh rotates it and revokes the old one, and checks the membership again.
- **Sign-up** creates the company, its first admin and their membership in one transaction, then sends a verification link. Login requires a verified address.
- **No account discovery:** sign-up, resending verification and password reset answer the same whether or not the address has an account. A sign-up with a taken address emails its owner instead. Unknown addresses still cost a password hash, so timing reveals nothing either.
- **Rate limits** per client IP and per target address on every authentication endpoint.
- **Emails** (verification, recovery) are sent by the default worker, in the person's language, with links signed at send time. Recovery links expire in 2 hours and work once.
- **People are global** (`accounts_user`): one person can belong to several companies. Memberships are tenant data under row-level security; at login, when no company is active yet, a `SECURITY DEFINER` function lists one person's own memberships.
- **Roles per company:** admin, recruiter, hiring manager, interviewer. The role is read from the membership on every request, never trusted from the token, so removing someone or changing their role takes effect immediately. Only admins invite, change roles or remove members, and every company keeps at least one admin: changes lock the company's admin memberships first, so two simultaneous demotions cannot both succeed.
- **Invitations** are tenant data. Only a hash of the link token is stored; links expire after 7 days and work once. Accepting creates the account if needed (already verified: the link proves the address) or joins an existing one, which must be signed in as the invited address.
- **Several companies per person:** switching issues new tokens for the other company, after checking the membership, and revokes the previous refresh token. The app then drops every cached query, so nothing from the previous company stays on screen.
- **Candidates:** signed magic links, each limited to a single application and set to expire.
- **Shared clips and Terna views:** signed, expiring links that are never indexed.

## Security

- Upload validation by content type, not file extension, with size limits. Résumé parsing runs in a worker, never in the request path.
- Short-lived presigned URLs for all stored files.
- Rate limits on authentication and public endpoints.
- No hardcoded credentials. Development defaults are safe and documented.

## Data model

| Area | Entities |
|---|---|
| Identity | `Company`, `User`, `Membership`, `Invitation` |
| Jobs | `Job`, `Requirement`, `PipelineStage`, `QuestionSet`, `Question` |
| Candidates | `Candidate` (unique per company by email), `Application` |
| Screening | `Resume`, `ResumePassage` (text, redacted text, page, embedding), `Screening` (counts per application), `RequirementMatch` (verdict, signals, evidence), `RequirementVector`, `Synonym` |
| Async answers | `Answer` (text, voice or video), `TranscriptSegment`, `Clip` |
| Decision | `InterviewSlot`, `Interview`, `Scorecard`, `Shortlist` |
| Collaboration | `Comment`, `Notification` |
| Platform | `OutboxEvent`, `AuditEvent`, `EmailTemplate` |
| Privacy | `ConsentRecord`, `RetentionPolicy`, `DataRequest` |

## Planned decision records

- PostgreSQL for search instead of a dedicated search engine
- Local, deterministic AI only
- Separate task queues per workload
