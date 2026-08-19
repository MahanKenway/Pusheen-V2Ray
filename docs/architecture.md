# Kaveh Architecture Decision Record

## Decision

Kaveh starts as a **modular monolith with task-oriented commands**. The code is one Python package, but the domain does not depend on any framework, database, HTTP client, or runtime core. This gives the project a small operational footprint without binding its quality rules to a particular deployment.

## Dependency direction

```text
domain ← application ← interfaces
  ↑           ↑
  └ adapters / infrastructure
```

The `domain` package contains models, policies, and ports. `application` defines use cases such as ingestion, validation, and publication. Protocol parsers and feed formats live in `adapters`; HTTP, filesystem, persistence, and probes live in `infrastructure`. Interfaces should orchestrate commands, not duplicate business logic.

## Publication invariant

A public feed is built under a unique snapshot identifier. Every file is written atomically. Only after all artifacts exist is the `latest.txt` pointer changed. A run with no qualified configurations returns a non-publication result and must not overwrite `latest.txt`.

## Quality invariant

TCP connectivity is a diagnostic stage, not a qualification decision. Qualification requires a successful `END_TO_END` probe result, recorded under a versioned policy. The foundation already enforces this distinction in `ValidationSupervisor` and `ValidateBatch`; the next milestone provides an isolated runtime adapter that produces this result.

## Security invariant

Raw proxy URIs can include credentials. They may be stored only where required for feed generation and must not be inserted into logs, metrics, parse errors, or public manifests. Source URLs are registry-controlled, HTTPS-only, bounded by timeout and response size, and treated as untrusted input.

## Growth triggers

Do not split services merely because jobs are scheduled. Separate a validation worker only when runtime isolation or job duration cannot be accommodated in the main deployment. Replace the database-backed queue only after measured concurrency or locking limits justify it.
