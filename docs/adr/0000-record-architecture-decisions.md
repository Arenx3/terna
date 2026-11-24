# 0000. Record architecture decisions

- **Status:** accepted
- **Date:** 2026-11-23

## Context

Terna makes decisions that are expensive to reverse: how tenants are isolated, where search runs, which AI models are used. Months later, the reasons behind those decisions are easy to forget, and newcomers to the code have no way to recover them.

## Decision

Every significant architecture decision is recorded as a short Markdown file in `docs/adr/`, numbered in sequence: `NNNN-title-in-kebab-case.md`.

Each record contains:

- **Status:** proposed, accepted, deprecated, or superseded by a later record
- **Date**
- **Context:** the forces at play and the problem being solved
- **Decision:** what was chosen
- **Alternatives considered:** the options rejected, and why
- **Consequences:** what becomes easier, what becomes harder, and the trade-offs accepted

A record is never edited after it is accepted, apart from changing its status. A changed decision gets a new record that supersedes the old one.

## Consequences

- The reasoning behind the architecture stays readable next to the code.
- A pull request that makes a significant decision includes its record.
- Writing a record takes a few minutes per decision.
