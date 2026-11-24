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

Each worker consumes its own queue. A long transcription never delays an email or an upload.

## Main flows

### Application and screening

1. The candidate requests an upload URL, then uploads the résumé straight to storage. The file never passes through Django.
2. The application is created. An outbox event, `application.submitted`, is written in the same transaction.
3. `worker-ml` extracts the text, splits it into passages tagged with section and page, and redacts personal data.
4. It computes an embedding for each passage and matches the passages against each requirement.
5. The verdicts and their evidence are saved. The kanban board updates live over WebSockets.

### Async screening answer

1. The browser records with `MediaRecorder` and uploads each answer in parts (S3 multipart), so a dropped connection loses nothing.
2. `worker-media` converts the video to HLS, makes a thumbnail and extracts mono 16 kHz audio. Voice-only answers skip the video steps.
3. `worker-ml` transcribes with `faster-whisper`. It produces word-level timestamps and detects the language.
4. Transcript segments are indexed for full-text and semantic search. Text answers go straight to this step.

## Multi-tenancy

- Every row of customer data carries a `company_id`. All tenants share one schema.
- PostgreSQL row-level security policies compare that column to `app.company_id`. This setting is applied with `SET LOCAL` inside each request transaction and each Celery task.
- Django connects with an unprivileged role, and tables use `FORCE ROW LEVEL SECURITY`. Without it, a table's owner bypasses the policies.
- Django querysets also filter by company, as defense in depth.
- Isolation is tested both through the API and with raw SQL.

## Events and audit

- **Transactional outbox:** domain events are written in the same transaction as the change they describe. A dispatcher then delivers them to the audit log, notifications, analytics and real-time updates. A rolled-back change emits nothing, and a committed change is never lost.
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
| Matching | Multilingual `sentence-transformers` model, aliases and rules | Works across Spanish and English |
| Transcription | `faster-whisper` on CPU | Model size configurable. CI uses the smallest model. |

Models are downloaded once into a dedicated volume. No external API is called. Terna never analyzes faces, tone of voice or expressions.

## Authentication and access

- **Team members:** sign in with email. JWT access tokens, plus a refresh token kept in an `httpOnly`, `SameSite=Strict` cookie.
- **Roles per company:** admin, recruiter, hiring manager, interviewer. A person can belong to several companies.
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
| Screening | `Resume`, `ResumePassage` (text, page, embedding), `RequirementMatch` (verdict, evidence, override) |
| Async answers | `Answer` (text, voice or video), `TranscriptSegment`, `Clip` |
| Decision | `InterviewSlot`, `Interview`, `Scorecard`, `Shortlist` |
| Collaboration | `Comment`, `Notification` |
| Platform | `OutboxEvent`, `AuditEvent`, `EmailTemplate` |
| Privacy | `ConsentRecord`, `RetentionPolicy`, `DataRequest` |

## Planned decision records

- Multi-tenancy with a shared schema and row-level security
- Transactional outbox for domain events
- PostgreSQL for search instead of a dedicated search engine
- Local, deterministic AI only
- Separate task queues per workload
