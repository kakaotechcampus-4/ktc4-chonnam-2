# RT-10(b) Readout handler Implementation Notes

**IN_PROGRESS · Refs #297 (RT-10(b))**

Base: `debc783266d011ab46b102020c8d696a7dbd818e` (PR #440).
Work uses the existing `codex/rt10b-readout-handlers` checkout. No new branch,
worktree, staging, commit, push, PR or Issue mutation is part of this task.

## Authority and scope

- [Readout usage values](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469413593).
- [Runtime PARTIAL, timing and begin policy](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469456244).
- [Readout A decision](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469784532).
- [Runtime A recovery decision](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6469908092).
- [PR #440 caller-issued Run ID](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/440).
- Existing Readout public API/contracts/taxonomy, Case observation input/storage
  decisions and Runtime UsageSink/ProducedObject/T1 contracts remain authoritative.

Only `PLATE_READ` and `OVERLAY_TIME_READ` are added. Readout algorithms,
Case/Web policy, exports, schemas, migrations, workflows and gate inventories
are unchanged. Tests inject offline OCR; no live OCR or Search HTTP is used.

## Input, invocation and resources

`ReadoutInputs` uses a short caller transaction. It reads Case's public
`get_case`, `observation_input(case_id, job_id)` and execution read port, and
reads immutable payloads with `ProducedReader`. It validates the requested
case/job/kind, fixed generation/scope/candidate and a successful clip job for
that same candidate/generation whose produced clip matches the fixed ref.
It does not replace a queued job's input with the current selection.

The returned `ReadoutInput` contains detached scalar facts. The input
transaction and connection have returned before opening the OCR context.
`RecordingOcrFactory` reads clip identity/duration through Recording's public
`get_incident_clip`; `recording_ocr_factory` composes an execution-local
RecordingService with short transactional repository callbacks. Recording's
context closes on success, capability error, usage error and cancellation.

The handler checkpoints before/after input reads, after context entry, after
usage begin, after usage finish, and after resource closure. Returned Run
observations are sent to `finish` before observing cancellation after OCR.

Each invocation issues a new `rr_` UUID, distinct from execution identity:

```text
new rr_ ID
  -> UsageSink.begin(exact readout_run ref)
  -> matching public readout function once, with the same run_id
  -> UsageSink.finish(actual observations)
  -> ProducedObject preparation
  -> resource closure/checkpoint
  -> existing Worker T1 terminal + object transaction
  -> existing reconciliation
```

There is no handler retry, pre-T1 `finalize`, exception-string parsing or
Runtime port/schema extension. If begin fails, OCR is not invoked. Usage
recovery, T1 receipt replay and T2 reflection never invoke OCR. A STALE new
attempt may invoke OCR with a new Run ID under the existing retry policy.

## Outcome and usage mapping

| Public result | JobExecution | Usage observation |
| --- | --- | --- |
| `ReadoutRun.outcome=FAILED` | FAILED / `READOUT_INFRA`; Run retained, result null | FAILED / `READOUT_INFRA` |
| `SUCCEEDED` or `PARTIAL` | SUCCEEDED; original Run retained | SUCCEEDED / null |
| Plate abstain / NEEDS_REVIEW | SUCCEEDED | SUCCEEDED / null |
| Overlay OK | SUCCEEDED | SUCCEEDED / null |
| Overlay NOT_APPLICABLE / `readout.overlay.not_present` | SUCCEEDED | SUCCEEDED / null |
| Overlay UNKNOWN / `readout.overlay.presence_undetermined` | SUCCEEDED | SUCCEEDED / null |
| Overlay UNKNOWN / `readout.overlay.ocr_failed` | SUCCEEDED | SUCCEEDED / null |

The full `ReadoutRun.failure` (including code) remains in the payload. Invalid
input `ValueError` and input/DB/checkpoint/context/persistence faults keep the
existing Runtime boundary; they are not converted to `READOUT_INFRA`.
Cancellation and UsageError propagate to the existing Worker lifecycle.

Owner-confirmed usage fields are `READOUT_PLATE` / `READOUT_OVERLAY_TIME`,
`ocr-local`, `{pricing_id: local-2026-09, unit: per_second}`,
`{amount: "0", currency: KRW}`, token usage null and incident clip duration
(null if unknown). `occurred_at` remains the sink clock; `latency_ms` comes
from Run started_at/ended_at (null if ended_at is unknown). Run usage_refs
remain the API-returned derived value; the ledger's run_ref is authoritative.

## Durable objects and recovery

One ProducedObject has `kind=readout_run`, explicit `ref=run.run_id` and payload:

- Plate: `{"readout_run": run.to_dict(), "plate_readout": result.to_dict() | null}`.
- Overlay: `{"readout_run": run.to_dict(), "overlay_time_readout": result.to_dict() | null}`.

This is the existing ProducedReader / StoredObservationAdapter shape. The
explicit Run ref lets current planned-run reconciliation inspect durable T1.
Before T1, a terminal execution without that produced Run resolves to
`RUN_NOT_PRODUCED`; durable usage observations survive. After T1, even a
FAILED Run resolves to its stored readout_run. Lost COMMIT acknowledgements
use existing durable receipt verification. Reconciliation uses the existing
usage identity and does not append a second Final row.

## Explicit composition

`compose_registry(..., readout_provider_factory=...)` merges both Readout
handlers with existing Search and clip handlers. Its default is None, so
unconfigured production remains unregistered. No fixture default or new
environment key enables OCR implicitly.

For an explicitly configured local Paddle deployment, construct the factory
with `recording_ocr_factory(transaction=..., storage_root=...,
ocr_factory=lambda recording: PaddleOcrProvider(RecordingFrameSource(recording)))`
and pass it to the registry. The application assembling that dependency must
install/read the Readout-owned dependencies and model configuration. Model
download, Linux/production hardware latency and live Paddle execution are
not validated by the offline tests in this change.

## Verification ledger

Direct evidence is local to `.codex-scratch/rt10b-readout/`, excluded from PR.
The internal `plan.md`, RAW console output, JSON/JUnit reports, generated
videos/env files and disposable DB material are not deliverable source files.

| Evidence | Result |
| --- | --- |
| Handler initial RED | 25 failed: handler module absent |
| Handler GREEN | 25 passed |
| Inputs/composition RED | 28 failed / 1 existing default-registration pass |
| Combined focused + existing clip composition GREEN | 57 passed |
| Resume focused, without clip composition duplication | 54 passed |
| Real MySQL new handler receipt/recovery | 18 passed, 31.31 s |
| Existing real MySQL reconciliation | 30 passed, 60.20 s |
| Boundary | 0 violations |
| Contract fixtures | structure 62 / JSON 26 / semantics 104, all passed |

The first handler tests had incorrect test data (`KNOWN` vs contract `OK`,
empty OCR vs low-confidence abstain, and no samples vs unreadable samples).
Those were corrected against public contracts; they are not product fixes.
The first MySQL run passed 16 and failed 2 because a test tried to retry a row
already marked STALE. Using real lease expiry/sweep produced the 18-pass run.
Early process probes exposed a wrong adapter access method and later a peer
timeout; neither is counted as passing E2E. The original boundary invocation
failed only while printing a Unicode dash under cp949; UTF-8 invocation passed.

### Resume verification (2026-10-29 KST)

| Direct execution on this checkout | Result |
| --- | --- |
| Focused handlers/inputs/composition including DB/checkpoint/object errors and reselect/new-generation input preservation | 69 passed, 2.33 s |
| Related Worker/Readout/Case/Recording/Search/jobs/usage non-MySQL selection | 2254 passed / 48 failed / 21 existing skipped / 831 deselected, 231.81 s |
| Only the 48 failures, with writable task TEMP/TMP outside sandbox restrictions | 48 passed, 57.83 s |
| Related real MySQL Search/clip/usage/produced/Case subset | 49 passed, 123.37 s, 147 phases |
| Separate API/Worker full-chain Readout process E2E, 6 modes | 6 passed, 248.37 s, 18 phases |
| Existing separate-process normal/hint/fractional-clip helper regression | 3 passed, 56.88 s, 9 phases |

The two regression runs cover the selected tests without unresolved failures;
they are not a single green full-suite run. Existing skips include absent
`typer`, private real-video opt-ins and missing real-video files. Existing
warnings are FastAPI/Starlette TestClient deprecation and malformed-usage
Pydantic serializer probes. They were not suppressed or changed.

The 18-handler-MySQL / 30-existing-reconciliation runs above were directly
executed earlier in this same task and preserved across the usage-limit
interruption. Product code did not change after those runs. The final focused,
49-MySQL and 6-process runs were executed after resuming; none substitutes for
remote full regression. MySQL reports explicitly contain server `8.4.13`.
Scoped validation checks every collected/selected node, all setup/call/teardown
phases, no duplicate phases, no failed/skipped/xfail phase, and the JUnit identity
using the existing validator. It does not invoke or weaken the mandatory full
inventory gate.

The E2E timeout was traced to a test assumption that Plate is claimed first.
Both jobs share one enqueue timestamp; Runtime actually orders by
available_at/execution_id. The test now follows that order and intentionally
rolls back **both** Readout T2 transactions after real Case writes. With both
provider processes exited, redelivery applies stored results and repeats
without new usage or OCR. All six statuses include matching public call count
1, distinct Run IDs, same durable clip, zero checked-out main-engine connections
inside the fake provider, returned connections, restored adapter observations
and no remaining child processes. The three overlay notices remain distinct.
No timeout, skip or production orchestration policy was changed to make this pass.

Initial fresh read-only review found no confirmed product P1/P2/P3 and
independently ran the earlier 54-test focused set. It re-fetched the exact
Owner decisions. Final evidence/documentation recheck is recorded below.

### Resources and review limits

After testing, the dedicated DB had no unexpected test schema, no non-audit
transaction, no data lock and no other client. The first audit included its
own transaction; an autocommit audit excluding itself verified zero remaining.
The task's `codex-rt10b-readout-mysql` container and its inspected anonymous
volume were removed. Nine resolved child test directories under this task's
scratch root were removed, including generated videos/env files. RAW console
logs, evidence JSON/JUnit, internal plan and audit scripts remain ignored.
The tests asserted child process termination and returned engine connections.
The shared Docker engine was left running.

Review considerations not adopted as findings were a hypothetical falsey custom
provider triggering the existing Readout fallback, old clip jobs without public
observation input, and corrupted cross-execution ProducedReader references.
No failing valid production path was established for those concerns; no new
fallback/migration/common-store policy was introduced. Cancellation before
durable T1 follows the approved RUN_NOT_PRODUCED semantics. Actual candidate
reselection and a new generation were subsequently added to focused coverage.
Operational deployment still requires explicit provider injection; this PR does
not enable Paddle by default or verify its installation/model/hardware behavior.

### Final same-reviewer recheck

The same fresh read-only reviewer rechecked the final 13-file working delta,
independently ran focused **69 passed (3.67 s)**, validated all five scoped
MySQL JSON/JUnit sets, matched the exact initial 48 regression failures to the
48 passing reruns, and verified the original 718,403-byte runtime-log prefix
against HEAD and its SHA-256. Final verdict: **no P1/P2/P3**. No reviewer fix
round was needed. No source/index/HEAD changes were made by the reviewer.
Its remaining qualifications are the explicitly unrun full suites/CI/live
Paddle path and the split regression evidence, not a claim of full GREEN.

Final state: 13 changed files, zero staged files, HEAD and origin/develop remain
the base SHA. No commit/push/PR/Issue mutation. Status remains
**IN_PROGRESS · Refs #297 (RT-10(b))**.

## Exact intended file set

- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/readout_handlers.py`
- `src/daesingo/worker/readout_inputs.py`
- `src/daesingo/worker/readout_composition.py`
- `tests/worker/readout_support.py`
- `tests/worker/test_readout_handlers.py`
- `tests/worker/test_readout_inputs.py`
- `tests/worker/test_readout_composition.py`
- `tests/worker/test_readout_mysql.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_readout_process_mysql.py`
- `docs/runtime/rt10b-readout-handlers.md`
- `docs/runtime/runtime-implementation-log.md` (append only)

Full local pytest, full mandatory MySQL gate and remote CI are not run here.
Existing gate/workflow/skip/xfail/30-minute/900-second policies stay unchanged.
