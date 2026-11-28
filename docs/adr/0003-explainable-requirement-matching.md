# 0003. Explainable requirement matching

- **Status:** accepted
- **Date:** 2026-11-28

## Context

Screening is Terna's main promise: every requirement of a job sits next to the line of the résumé that meets it, or is plainly marked as having no evidence. A single fit score is not acceptable. Nobody can check a score, so recruiters either ignore it or trust it blindly, and both are worse than reading the résumé.

The matching also has to:
- Work across Spanish and English. Mexican companies write requirements in either language, and candidates send résumés in either.
- Run locally, at no cost, with no API keys, on the CPU of a laptop with 8 GB for Docker.
- Read only redacted text (see `screening.analysis`), so it can't rank anyone by name, age, gender or address.
- Stay correct while the job changes. Recruiters edit requirements after candidates have applied.

## Decision

Each requirement gets a verdict, `meets`, `partial` or `no_evidence`, from three kinds of signal. The signals are stored with what they found, so the screen can show why.

- **Keywords.** The requirement's skills are looked up in a dictionary of synonyms in Spanish and English ("k8s" and "EKS" are Kubernetes, "contabilidad" is accounting). Each company can add its own entries or replace Terna's. The requirement's other content words are looked up as well, stemmed with Snowball. "Kafka or RabbitMQ" is met by either. Without the skill itself, the other words prove nothing.
- **Meaning.** `paraphrase-multilingual-MiniLM-L12-v2` (`sentence-transformers`, Apache-2.0, 384 dimensions) embeds every redacted passage and every requirement. Its weights are pinned to a revision and downloaded once into the ml worker's volume. After that the model loads from disk only. Vectors live in `pgvector`. Similarities are computed in SQL with exact cosine distance over the application's own passages. An HNSW index on all passages is there for searching every candidate later. It is not used to match one application, because an approximate scan filtered to one résumé can come back short.
- **Rules.**
  - *Years of experience:* "5+ years building APIs in Python" counts the months of the roles that name the skill or read like the requirement. Overlapping roles count once.
  - *Language level:* "inglés avanzado" compares the level the résumé states next to the language (C1, B2, intermediate…) with the one asked for.

The thresholds were measured on the demo résumés. Unrelated work lines reach about 0.45 similarity.

| Similarity | What it does |
|---|---|
| ≥ 0.70 | Meets the requirement on its own |
| ≥ 0.50 | Partial evidence on its own |
| ≥ 0.35 | Backs up a skill the keywords found, in the same line |

The header (name, contact, location) is never evidence of meaning. Highlights never cover redacted text. A verdict other than `no_evidence` always has at least one passage to show.

**The summary is a weighted count, shown with its formula:** a must-have weighs 2, a nice-to-have 1, and partly meeting one earns half. Recruiters see "2 of 3 must-haves" and how the points add up, never an unexplained number. The board card shows the same thing as a bar with one segment per requirement, each as wide as its weight.

**When it runs.** Screening runs in the ml worker, never in a request.
- A résumé finishes reading.
- The job's requirements change, signalled by the `job.requirements_changed` outbox event.
- The company's dictionary changes.
- Someone asks for it again.
- A beat task picks up applications that were missed or screened by an older `matching.VERSION`.

A run claims the screening row first. If the row is reset while the run is working, for example because the requirements changed, the run's result is thrown away. Each finished screening emits `screening.completed`, which goes to the audit log and to the live board.

## Consequences

- Every verdict can be checked against the résumé. Where the matching is wrong, recruiters can see why. #42 will let them correct it, and #44 will measure it.
- Torch, even the CPU-only build, adds about 1.7 GB to the ml image (about 2.6 GB in total). The API and the other workers don't install it. Tests use a stand-in for the model, so CI doesn't download it for unit tests. The end-to-end run downloads it once (about 470 MB).
- The first screening on a fresh install waits for that one download. The worker starts loading the model as soon as it is up.
- Thresholds are a tuning surface. Changing them, the rules or the model means bumping `matching.VERSION`, which screens everything again.

## Alternatives considered

- **One score per candidate:** fast to read and impossible to check. It hides how a verdict was reached and invites ranking by a number nobody can explain.
- **A hosted LLM to judge each requirement:** needs an API key and a paid account, and sends personal data out of the machine. It also gives different answers to the same question.
- **Keywords only:** misses "Opero clústeres de Kubernetes" for "Kubernetes in production", and anything written in the other language.
- **ONNX Runtime without torch:** a much smaller image, but it would mean writing our own tokenization and pooling instead of using `sentence-transformers` as designed. We can revisit this if the image size becomes a problem.
