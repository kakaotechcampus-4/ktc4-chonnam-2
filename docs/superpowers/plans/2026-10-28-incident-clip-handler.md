# INCIDENT_CLIP_BUILD Implementation Plan

> Execute inline using superpowers:executing-plans; fresh read-only reviewer after implementation. No staging, commits, pushes or PR operations.

**Goal:** Execute Case-issued clip jobs through Recording's public capability and existing T1/T2.

**Architecture:** Detached inputs from a short caller transaction; per-execution Recording context; media after connection return. Fine produced identifies its AnalysisSource; public Recording metadata supplies the explicit VIDEO stream. No current-selection fallback.

**Tech Stack:** Python, SQLAlchemy Core, MySQL 8.4, ffmpeg, pytest.

**Spec:** `docs/modules/case/decisions/incident-clip-observation-input.md`, `docs/runtime/runtime-tech-spec.md`, #297 comment 6464169000 and the user's implementation request.

## Constraints and review focus

- IN_PROGRESS · Refs #297 (RT-10(b)). Readout/export handlers and Case/Web presentation excluded.
- Fixed candidate/generation/span/Fine/scope must agree; latest failed Fine cannot reuse older success.
- Only INCIDENT_CLIP_BUILD_FAILED maps to RECORDING_INCIDENT_CLIP_BUILD_FAILED; unknown codes propagate.
- No media with an input transaction open; checkpoints between public calls; close on cancellation/error.
- Exactly one build invocation per entered execution; T1 replay and T2 redelivery cannot invoke it again.
- Explicit clip encoding required; absent capability leaves the kind unregistered.

## Tasks

- [x] Add failing tests in `tests/worker/test_incident_clip_handlers.py` and `test_incident_clip_inputs.py`; preserve RED under ignored scratch.
- [x] Implement `IncidentClipInput`, `IncidentClipInputs`, `incident_clip_registry`; test fixed bindings, exact payload, known/unknown errors, Runtime exceptions, cancellation and connection release.
- [x] Add explicit Recording clip encoding configuration and production per-execution factory; wire aggregate registry in Worker main; preserve missing-config behavior. Test production composition before implementation.
- [x] Add real MySQL durable restoration, rollback/commit-ACK loss/retry, cancellation and real AVI generation tests; run RED then GREEN.
- [x] Add separate API/Worker process acceptance through Fine success, clip success and same-ref readout issuance (handlers remain absent); run RED then GREEN.
- [x] Run focused and related regressions, required MySQL subset, boundary and Contract fixture checks; leave full pytest and mandatory MySQL to remote regression/mysql/test CI without policy changes.
- [x] Document the confirmed taxonomy and separate Implementation Notes; append implementation log. Fresh independent read-only review; fix actual defects with TDD, reverify, report all paths and remaining limitations.
