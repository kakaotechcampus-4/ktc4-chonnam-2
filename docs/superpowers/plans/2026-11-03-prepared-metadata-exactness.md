# Prepared metadata exactness implementation plan

> **For agentic workers:** execute inline under the user's current authorization; fresh read-only review is required before completion. No commits, staging, push or deployment.

**Goal:** preserve prepared-media metadata exactly across MySQL JSON storage while retaining immutable-ref conflicts.

**Architecture:** encode only analysis_source/incident_clip rows with a strict versioned envelope containing the original model JSON as a string. Decode at the repository read boundary, including lists. MySQL never reparses the inner numeric literals. Legacy dictionaries remain readable and are not rewritten. Public model, stable_media fingerprint, exact equality and media validators stay unchanged.

**Spec:** user request; `docs/architecture/contracts/contract-analysis-source-derived.md` §4/§6, `docs/modules/recording/chunked-prepared-media.md`; the earlier real-media experiment and its retained failure evidence.

## Constraints

- Stay on the current branch/HEAD and preserve inherited uncommitted changes/evidence.
- No epsilon, rounding, equality removal, PTS/duration/provenance relaxation or cap changes.
- No schema migration or automatic recovery of legacy values already changed by native JSON.
- Reject malformed/unknown envelopes and non-JSON numbers; keep legacy exact unequal refusal.
- Read-only originals; owned resources only; no provider/HTTP, AWS or operations.

## Tasks and verification

- [x] Capture actual100 comparison before product changes: end_sec float hex differs by1ULP. Retain original failure separately.
- [x] RED: actual MySQL AnalysisSource/IncidentClip exact-number publication fails at immutable comparison.
- [x] Add focused codec in `src/daesingo/recording/prepared_metadata.py`; wire `_row`, `_get`, `_models` only for the two prepared kinds.
- [x] GREEN: codec boundary cases (subnormal/max float/negative zero/Unicode/nonfinite/corruption), actual MySQL exact read/replay/conflict/metadata-only attachment/legacy compatibility.
- [x] Preserve new test identities in independent MySQL inventories.
- [x] Focused existing chunked/immutable regressions, Runtime quality, boundary, Contract and whitespace checks.
- [x] Recheck stage budgets; actual10 then identical100, commit/fresh physical read/detached Search/strict decode with transmission blocked. Conditional240 only after the preceding gates.
- [x] Fresh read-only reviewer checks implementation, evidence and conclusions; address and recheck findings.
- [x] Verify originals and protected resources; clean only task-owned resources; record final outcome with initial failures intact.

## Review focus

- Exact nextafter differences remain conflicts and leave rows/chunks/case links unchanged.
- Nested IncidentClip provenance and list/read/metadata-only paths use the same decoding boundary.
- Recognized malformed envelopes never fall back to legacy, including outer mutations and unknown versions.
- Legacy equal replay does not rewrite old payloads; old values cannot be repaired without original evidence.
- New stored representation cannot be read by older code: document rollback compatibility despite no DDL change.
