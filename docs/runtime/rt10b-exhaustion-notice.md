# RT-10(b) HINT_EXTRACT exhaustion notice — Implementation Notes

`RT-10 IN_PROGRESS · Refs #297 (RT-10(b)) · Related #405`

2026-10-28 · uncommitted / unstaged · PR/merge SHA pending.
Agreement: [#405](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/405), including Runtime/Case port agreement and Case PR #415.
Case semantics remain authoritative in [hint-exhaustion](../modules/case/decisions/hint-exhaustion.md).

## 구현 결과

Runtime owns `common/jobs/exhaustion.py`, its DTO/port, outbox delivery, and the new
`job_exhaustion_notice` table. `case/exhaustion_adapter.py` delegates to the merged
`service.receive_hint_exhaustion()` on the caller Connection and drops the Case
diagnostic `reason`. `worker/case_composition.py` supplies the existing durable
Recording timeline capability; the production entrypoint supplies both adapters.

`sweep_expired()` inserts a notice only when an uncancelled HINT_EXTRACT becomes
STALE with no retry. STALE and INSERT share the same transaction. `sweep_once()`
pins a notice ID before entering B-D8 retries, alongside the existing retry ID.
Unknown-COMMIT recovery locks the original execution, confirms its durable
STALE/ended_at and the original notice identity/facts, and never synthesizes a
replacement notice for an already-STALE row. `SweepOutcome` and metric meanings
are retained. Other kinds get no exhaustion notification.

## Schema · migration

Forward migration `runtime_0006` follows `runtime_0005`. Frozen DDL is independent
of live metadata. Columns: notice_id (PK), job_id (UNIQUE), case_id, kind,
final_execution_id, attempt, terminal_status, reason, exhausted_at, trace_id,
case_acknowledged_at. Only case_acknowledged_at is nullable. Both timestamps are
DATETIME(6), stored in UTC. exhausted_at is read from the terminal UPDATE's actual
durable ended_at, including its existing causal lower bound.

The FK targets the Runtime-owned job_execution.execution_id; there is no
cross-module Case/JobRecord FK. CHECKs constrain HINT_EXTRACT, STALE, EXHAUSTED,
and positive attempt. The pending scan index is (case_acknowledged_at, notice_id).
Runtime validates the notice against its execution/job/case/attempt/status/time/
trace facts and rejects a later attempt before receipt. Cancellation is checked
under the generation lock; a later STOP_ANALYSIS marker on STALE is mutable and
allows the already-created notice to acknowledge NO_CHANGE(CANCELLED).

The existing runner is unchanged: migrate once before API/Worker startup;
forward-only, no operational downgrade, no startup migration, no automatic
DDL/unknown-COMMIT replay. Already-applied head is a no-op. The same-process guard
is retained; deployment must serialize separate migration processes. MySQL DDL
can leave partial schema on failure and requires existing manual repair policy.
No repository migration checksum registry was found; head/table fixtures were
updated without changing historical migration files.

## 생성 · 전달 · receipt transaction

1. Scan pending notice IDs without locks, then begin one B-D8 transaction per ID.
2. Read the notice receipt without a lock on every transaction replay. A durable
   receipt skips the Case receiver, including after a lost COMMIT response.
3. The Case adapter calls the public service, which locks Case first, validates
   Case-issued job/kind, and applies EXHAUSTED or returns NO_CHANGE.
4. Runtime locks the notice FOR UPDATE and checks its immutable snapshot plus
   the corresponding terminal execution. No Runtime lock precedes the Case lock.
5. APPLIED returns exactly one COARSE_SEARCH record; Runtime projects only
   job_id/case_id/kind through existing enqueue. NO_CHANGE has no followups.
6. Runtime writes case_acknowledged_at using UTC_TIMESTAMP(6). Case save,
   followup enqueue and receipt commit/rollback together.

Concurrent delivery serializes at Case. A receipt discovered after that lock
suppresses duplicate enqueue; an inconsistent APPLIED with an existing receipt
is an error. Invalid Case/job/kind, invalid port results, immutable mismatch,
enqueue failure or receipt failure rolls the whole candidate back. A failed
candidate does not stop other candidates. Scan failures propagate to the
existing startup admission retry or periodic DB-error policy.

`SweepService.redeliver_exhaustion` is separate from its existing T2 callback.
Startup completes both before the first claim. Periodic sweep runs both; the
existing stop/join lifecycle is retained. An absent optional receiver leaves
notices pending, matching the existing optional T2 reflector pattern.

## Port · operational event

`JobExhaustionNotice` has only the agreed notice/job/case/kind/final execution/
attempt/status/reason/exhausted_at fields. trace_id remains Runtime correlation
storage, outside the public DTO. `ExhaustionResult` contains only APPLIED or
NO_CHANGE and appended_job_records. Case's settlement reason is not exported.
The receiver never commits, rolls back or performs transaction retries.

`runtime.exhaustion.failed` is a predefined ERROR with status=FAILED. It clears
ambient correlation for that event and records no notice/job/case IDs, payload,
provider response, original exception, locator, file name or path. Candidate
failure leaves receipt NULL for a future sweep. The event catalog is extended;
no notice content or raw exception is added to logging.

## Plan 대비 변경 · 새 implementation detail

The agreed #405 boundary is a separate RT-10(b) slice. Optional composition
arguments follow existing T2 patterns. A same-module FK and strict minimal
enqueue projection were selected as physical implementation details. Existing
T2, ExecutionOutcome, produced and job_execution.case_applied_at are unchanged.
No new retry policy, scheduler, timeout, provider invocation or config value.

## Contract / Decision / Baseline 영향

- Contract 변경: 없음. The implementation consumes the agreed #405 port.
- Decision 변경: 없음. Case PR #415 public behavior is consumed unchanged.
- Baseline 변경: 없음. Existing retry limits/timing, B-D8 and admission remain.
- Owner 확인 포인트: audit the separate terminal outbox, event and migration;
  Fine/readout/export exhaustion policy remains outside this implementation.

## Verification

RED evidence precedes product edits: three actual-MySQL creation/atomicity/
migration failures, two delivery/startup failures; nine family-omission tests
failed before adding checker inventory. Initial integration run had 44 passes
and two test-fixture/driver-exception expectation failures, then corrected.

Fresh local evidence on owned MySQL 8.4.7:

- New exhaustion + Case exhaustion + entrypoint: 75 passed.
- Additional stored adapter/port/scan-policy + DTO + normal Search process E2E:
  31 passed (including real independent API/Worker OS processes).
- Actual exhaustion-only strict-checker scope: 61 tests / 61 parameter boundaries /
  12 families; 927 omissions/metadata/phase/skip/xfail/JUnit mutations rejected.
  This is not a full mandatory-MySQL or full strict-gate result.
- Boundary check: zero violations. Contract fixtures: 62 structure, 26 JSON,
  104 semantic checks passed. Workflow policy unchanged; diff check passed.
- Related sweep/T2/reflection/composition/produced/timestamp/migration MySQL
  regressions: 224 passed; one existing Starlette TestClient deprecation warning.
- Existing cancellation states/transaction/sweep controls: 9 passed, 10 deselected.
- Gate unit omission controls: 7160 passed, 2031 deselected (before the final two
  cancellation obligations); all 372 current exhaustion gate controls reran in
  the final focused pass.
- The pass after the late-cancellation fix: 461 passed (60 actual MySQL
  boundaries, 18 Runtime DTO tests, 11 Case exhaustion tests, 372 gate controls).
- Catalog regression: 1 RED from unintended metric auto-inclusion, then 25 GREEN
  and zero real-emitter schema violations. Existing metric inventory is retained.
- Late real STOP_ANALYSIS delivery/unknown-COMMIT recovery: 2 RED, then GREEN in
  the 461-test final pass. Cancellation can mark STALE after notice generation;
  it is mutable state, not a contradiction of the earlier exhaustion fact.
- Fresh read-only reviewer, with no implementation history: initially two P2s,
  no P1. Both reproduced with valid RED and fixed; the same reviewer confirmed
  both resolved with no new/remaining P1/P2 for this scope.
- Review fix 1: include exhaustion in nested metadata/family count and output
  inventories. A focused control executes the original nested omission stage,
  including its final assertion, against controlled input: 244 metadata and 12
  family omissions. It is not a full nested database-child execution.
- Review fix 2: compare the returned execution_id exactly in Python. MySQL's
  ascii_bin PAD SPACE comparison accepts a trailing-space FK/WHERE alias; the
  actual-MySQL RED demonstrated incorrect APPLIED/enqueue before the fix.
  The first literal-comparison fixture attempt was corrected and is not treated
  as valid product RED; the subsequent real-column RED and GREEN are preserved.
- After both review fixes, the final focused run: 469 passed (61 actual MySQL,
  18 DTO, 11 Case exhaustion, 378 gate controls, 1 nested omission control).
- The reviewer confirmed the 469-test evidence. The implementer subsequently
  refreshed the actual scoped checker to 61 parameters / 927 rejected mutations;
  the reviewer did not inspect that refreshed mutation artifact.
- This is a scope review, not full CI/merge approval.

Full pytest, complete mandatory MySQL and its nested strict gate are deliberately
left for remote CI, as requested. Checker calculation logic is unchanged; only
inventory and independent test inventories are extended. Existing skip/xfail,
nested 900-second and workflow 30-minute policies are retained.

## 남은 위험

Worker absence still has no finite delivery SLA; pending notices need a running
sweeper. Repeatedly miswired notices remain pending with a safe failure event;
repair is operational. No historical STALE backfill is attempted: this migration
starts the atomic outbox for newly finalized sweeps. Other kind exhaustion and
retention/purge policy are separate decisions. Full remote CI remains required.
