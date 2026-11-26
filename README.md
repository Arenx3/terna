# Terna

[![CI](https://github.com/Arenx3/terna/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Arenx3/terna/actions/workflows/ci.yml)

**From 300 résumés to your shortlist, with evidence.**

Terna is a multi-tenant applicant tracking system (ATS) built on one idea: every hiring decision should rest on evidence you can see. It screens résumés requirement by requirement. Candidates answer screening questions in text, voice or video, whichever they prefer. And it helps the team build the *terna*: the three finalists presented to the hiring manager.

All AI runs on your own machine. No API keys, no external accounts, no cost.

[Leer en español](README.es.md)

> **Status:** in development, Phase 3 (explainable screening). The features below are the roadmap. Each one is checked off as it ships.

## Why

- Recruiters review hundreds of résumés per opening, coordinate interviews over email and decide from scattered notes.
- AI-powered ATSs output an "87% match" without saying why.
- Candidates wait weeks without hearing back.
- One-way video interviews push away the many people who don't want to be on camera.

## What makes it different

| | |
|---|---|
| **Explainable screening** | Every job requirement is shown next to the résumé passage that proves it, or flagged as "no evidence". No score comes without a reason. The AI suggests and the recruiter decides. |
| **Async screening, on the candidate's terms** | Recruiters set the questions for each job. Candidates answer on the spot, with prep time and retakes, in **text, voice or video**. Voice and video answers are transcribed automatically. |
| **Transcript-first review** | Reviewers read the answers before watching anything. With blind mode on, a candidate can be evaluated without their face or voice being seen or heard. |
| **Blind review** | Hides name, photo, age, gender and school during résumé screening to reduce bias. |
| **Search across answers** | "Who mentioned Kubernetes?" searches every transcript and jumps to the exact second. Clips can be shared with the hiring manager. |
| **Calibrated scorecards** | Interviewers score independently and back each score with written evidence. Terna flags interviewers who score consistently harsher or softer than the rest of the panel. |
| **The Terna view** | Three finalists side by side, with their evidence, scorecards and clips, ready for the hiring manager. |
| **Candidate portal** | Live application status, self-scheduling, and a respectful close for everyone not selected. No ghosting. |
| **Privacy by design** | Consent records, automatic data retention, and data subject requests: ARCO rights under Mexico's LFPDPPP, plus the GDPR. |
| **Bilingual** | Full English and Spanish interface. Matching also works across languages, such as a job posted in Spanish and a résumé written in English. |

Terna never analyzes faces, tone of voice or facial expressions. It only looks at what the candidate said.

## Architecture

```
 browser (React) ──► nginx ──► Django backend (ASGI: REST + WebSockets)
                                  │                  │
                  PostgreSQL + pgvector        Redis (broker, channels, cache)
                  (row-level security)               │
                          ┌──────────────────────────┼──────────────────────┐
                    worker-default              worker-media             worker-ml
                    email, alerts,              FFmpeg: HLS,             résumé parsing,
                    outbox, retention           thumbnails               embeddings, Whisper
                          └──────────── RustFS (S3-compatible storage) ─────┘
```

Details in [docs/architecture.md](docs/architecture.md).

## Tech stack

- **Backend:** Django 5.2 LTS, Django REST Framework, Django Channels, Celery
- **Data:** PostgreSQL 16 with `pgvector` and row-level security, Redis
- **Local AI:** `faster-whisper` for transcription, multilingual `sentence-transformers` for résumé-to-job matching
- **Media:** FFmpeg (adaptive HLS), RustFS (S3-compatible storage)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, i18n (en/es)
- **Quality:** GitHub Actions CI, cross-tenant isolation tests, matching quality evaluation, Playwright end-to-end tests

## Roadmap

- [x] **Phase 1, Foundations:** zero-config Docker stack, CI, multi-tenancy with row-level security, auth, roles and invitations, design direction
- [x] **Phase 2, Core ATS:** jobs with requirements and stages, public careers page, applications, real-time kanban pipeline, candidate profile, email, audit log
- [ ] **Phase 3, Explainable screening:** résumé parsing, personal data redaction, requirement matching with evidence, recruiter overrides, blind review
- [ ] **Phase 4, Async screening:** per-job questions answered in text, voice or video, in-browser recorder, resumable uploads, transcription, search and clips
- [ ] **Phase 5, Decision and product:** interview scheduling, calibrated scorecards, the Terna view, analytics, candidate portal, privacy requests, demo data

Progress is tracked in the [milestones](https://github.com/Arenx3/terna/milestones).

## Run it

```bash
git clone https://github.com/Arenx3/terna.git
cd terna
docker compose up -d --build --wait
```

No accounts, API keys or `.env` needed. Secrets are generated on first start and kept in the `terna_secrets` volume. To change a default (ports, email or storage provider), copy `.env.example` to `.env`.

The first start also adds demo data: two fictional companies with a team and a few jobs. Sign in as **ana@acme.mx** with the password **terna-demo-2026**. Set `DEMO_DATA=false` for a real deployment.

**Requirements:** Docker with Compose v2.24 or later. Give Docker at least 8 GB of memory: the local AI models in later phases need it.

| URL | What |
|---|---|
| http://localhost:8080 | Terna |
| http://localhost:8080/api/docs/ | API reference (OpenAPI) |
| http://localhost:8080/api/health/ | Health of the database, Redis and storage |
| http://localhost:8025 | Mailpit, the inbox that catches every email |
| http://localhost:9001/rustfs/console/ | Storage console (RustFS) |

Every port is bound to `127.0.0.1` only. Storage console credentials:

```bash
docker compose exec backend sh -c 'cat /run/secrets/storage_access_key; echo; cat /run/secrets/storage_secret_key; echo'
```

Stop with `docker compose down`. Add `-v` to also delete the data and the generated secrets.

The stack runs today; product features land phase by phase.

## Development

Tests and lint run in containers, so the only requirement is Docker:

```bash
docker compose --profile test run --rm tests                  # backend tests
docker compose --profile test run --rm --no-deps tests \
  sh -c 'ruff check . && ruff format --check .'               # lint and formatting
python scripts/smoke_test.py                                  # end-to-end check of a running stack
```

CI runs the same checks on every pull request (lint, backend tests, frontend, and a smoke test of the full stack), and all of them must pass before merging to `main`.

The frontend runs on the host with hot reload, against the running stack (Node 24 or later; CI and the Docker build use Node 26 LTS):

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173, proxies /api to the stack on :8080
npm run lint && npm run typecheck && npm run build
npm run api:types    # regenerate the typed API client after backend changes
npm run test:e2e     # browser tests against the stack (MAILPIT_URL if Mailpit is not on :8025)
```

Every visible string lives in `frontend/src/i18n/locales/` (English and Spanish). The lint fails on hardcoded text in components, and the type check fails when a key is missing in either language.

Install the Git hooks once with `pre-commit install` (via `pipx`, `uv tool` or `pip`). They run Ruff, keep `uv.lock` in sync and catch common mistakes before each commit.

## Documentation

- [Product vision](docs/vision.md): the problem, the principles, the users and the full hiring journey
- [Architecture](docs/architecture.md): services, data flows, multi-tenancy, local AI and data model
- [Architecture decision records](docs/adr/)

## The name

In Mexican recruiting, a *terna* is the shortlist of three finalists presented to the hiring manager. Building it is what this tool is for.
