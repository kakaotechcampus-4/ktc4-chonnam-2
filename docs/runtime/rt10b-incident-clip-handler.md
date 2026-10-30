# RT-10(b) INCIDENT_CLIP_BUILD — Implementation Notes

**IN_PROGRESS · Refs #297 (RT-10(b))** · 2026-10-28.

## Result and scope

The production Worker registry can execute Case-issued `INCIDENT_CLIP_BUILD`
through `RecordingService.build_incident_clip()`. Fine, clip and each readout
remain separate executions. Successful clip T2 issues `PLATE_READ` and
`OVERLAY_TIME_READ` with the same immutable `incident_clip_ref` using existing
Case reflection and enqueue. Those handlers, both export handlers and Case/Web
status presentation are outside this change. This is not complete RT-10 or
ReportPackage acceptance.

The start gate fetched origin/develop and verified branch
`codex/rt10b-incident-clip-handler`, HEAD and origin/develop both
`6764c8f7f6dc5ef284db3c9bff3d4d19e02bfe73`, clean working tree and empty index.
The existing checkout was used. No new worktree, staging, commit, push or PR
operation is part of this task.

## SoT and input bindings

- [Case decision](../modules/case/decisions/incident-clip-observation-input.md)
  fixes candidate, generation, span and Fine job in append-only observation input.
- [Runtime specification](runtime-tech-spec.md) owns checkpoint, T1/T2, retry and
  registry semantics. [Earlier composition checkpoint](rt10b-production-composition.md)
  remains historical evidence, not a test run of this change.
- [Owner terminal decision](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6464169000)
  closes the earlier mapping blocker. Its exact literal mapping is registered in
  [Recording taxonomy](../modules/recording/decisions/failure-taxonomy.md).

`IncidentClipInputs` runs only inside the composition-owned transaction. It calls
public `CaseStore.get_case`, `observation_input` for the clip and Fine jobs, and
`read_executions`; successful dependency payloads are read with `ProducedReader`.
It checks the clip/Fine/Coarse JobRecords' kinds, case and scope, the scope body,
Fine's candidate/generation/span against clip input, latest dependency attempts'
SUCCEEDED status, the Coarse candidate/run/scope/span and Fine run/evidence links.
A relative scope must bind the same timeline/revision. Its originally requested
range is not reapplied to candidates: Recording's actual frame coverage can
extend past the scope tail, and Search/Fine use that actual source.
An older successful Fine cannot override a newer failed attempt.

No input is taken from the current selected candidate. No stream ref is added to
Case input. Fine's public `analysis_run.input_ref` identifies the AnalysisSource;
public Recording metadata supplies its timeline/range and stream facts. Exactly
one VIDEO stream is required, with public `owns_asset` validation for the Case.
Ambiguity is rejected without choosing a first/default/front/rear stream.

Search emits CandidateSpan using `round(seconds * 1000)`. Source containment is
therefore compared in that same ms coordinate system, with the source endpoint
computed as `timeline_range.start_sec + duration_sec`, exactly as Search does.
Recording independently probes MP4 duration and actual frame coverage; the
actual range end is not substituted for Search's duration coordinate. The fixed Case request is
passed unchanged to Recording `resolve_span`; no clamping, new tolerance policy
or provenance rewrite occurs. Recording remains authoritative for PARTIAL and
usable spans and for actual media/frame coverage.

## Transaction, connection, lifecycle and terminal boundaries

1. Checkpoint, then durable input lookup in a short caller transaction.
2. After its connection returns, open an execution-local Recording context.
   Recording repository operations use their own short caller transactions via
   `TransactionalRecordingRepository`; no Connection or stream escapes input load.
3. Checkpoint between public metadata/ownership/resolve/build capabilities.
   Call `build_incident_clip(resolution)` once, with no internal handler retry.
4. Close the context on success/error/cancellation. Checkpoint again after close,
   including the known capability-failure path, before returning terminal facts.
5. Success returns a single `ProducedObject` payload exactly
   `{"incident_clip_ref": "<Recording ref>"}`. Its `incident_clip_result` receipt
   uses existing per-execution ref allocation; it is distinct from the immutable
   Recording clip ref, so a later clip job can reuse the same clip without an
   object-store uniqueness conflict.
6. Existing Worker T1 atomically stores terminal, produced refs and payload. Its
   rollback/COMMIT-unknown recovery reuses those facts without invoking the handler.
   Existing T2 persists Case reflection, follow-on jobs/enqueue and receipt together.
   Redelivery does not invoke media. No T1/T2 implementation was changed.

Only a `RecordingCapabilityError` with code `INCIDENT_CLIP_BUILD_FAILED` thrown by
the build invocation maps to `FAILED`,
`failure_kind=RECORDING_INCIDENT_CLIP_BUILD_FAILED`, empty produced/objects. Unknown
codes propagate to the existing registry exception boundary; no string-generated
Recording failure is introduced. Input/metadata/context/checkpoint/ValueError/DB/
transaction/persistence faults are outside this mapping. Cancellation retains its
existing control flow. Neither raw error text nor paths/locators are logged by
this handler. Fine success and its produced remain unchanged after clip failure;
Case can issue a new clip job. Ordinary FAILED automatic retry is not added.

## Explicit production configuration

Recording owns three optional configuration keys, independent of AnalysisSource
profile configuration: `DAESINGO_RECORDING_INCIDENT_HEIGHT`,
`DAESINGO_RECORDING_INCIDENT_PRESET`, `DAESINGO_RECORDING_INCIDENT_CRF`. All three
must be provided together and pass the existing encoder validation. There are no
new encoding defaults. The new clip-only factory supplies `LocalIncidentMaterializer`
and durable prepared storage; the existing Analysis service factory is unchanged.
Worker wraps the materializer with the existing configured temp-root lease.
Absent explicit encoding/context leaves the kind unregistered. Registry merging
rejects duplicate kinds and preserves the existing Search registration rules.

## Direct execution evidence and preserved records

Evidence for this task is excluded under `.codex-scratch/rt10b-incident-20261028/`.
Each row is a separate execution, never an additive total or a replacement for
remote CI. Historical evidence from earlier RT-10 tasks is not counted here.

| Check / snapshot | Observed result |
| --- | --- |
| Initial handler/input RED | 36 failed: implementation modules absent |
| Composition/config RED, corrected writable temp root | 8 failed, 7 passed |
| Reused immutable clip receipt RED | 1 failed: two executions reused the same result-store ref |
| Initial relative scope validation RED | 3 failed; review later identified requested-range containment as an incorrect additional policy, removed with its own positive regression |
| Cancellation during close after known build failure RED | 1 failed |
| Fractional source boundary RED | 1 failed before ms coordinate comparison |
| Fresh review scope-tail / duration-coordinate RED | 1 failed each, then 72 focused tests passed in 2.09 s |
| Focused handler/input/composition/Recording config after precision fix | 71 passed, 1.79 s |
| Earlier related offline snapshot | 1614 passed, 17 existing opt-in skips, 614 deselected, 116.82 s |
| Earlier actual MySQL subset, before final precision/close follow-up | 57 passed, 193.60 s; MySQL 8.4.13 |
| Independent successful executions sharing one durable clip | 1 passed, 8.21 s; not added to the 57-test count |
| Pre-review final-pass snapshot, includes 30fps process E2E | 59 passed, 268.49 s; superseded only by explicit post-review checks, not relabeled as final-source execution |
| Pre-review offline follow-up | 1633 passed, 17 existing opt-in skips, 619 deselected, 198.47 s |
| Boundary / Contract fixtures | PASS; fixture checks 62 structure / 26 JSON / 104 semantic |

Intermediate import/fixture errors remain recorded separately: wrong AnalysisRun
package import, API 200 versus actual 202 expectation, intentional persistent
cleanup-lock mistaken for media leakage, and wrong `issue_same_input` argument.
The corrected MySQL run covered those paths without changing product policy.
Sandbox socket/temp permission failures and one Python startup memory error are
environment failures, not feature RED or PASS. A later short 20-frame source E2E
probe stopped before the Coarse provider; that fixture did not reach clip handling.
The 30fps clip test uses a one-second source and the same fractional candidate
boundaries; the source-tail preparation limitation is not claimed fixed here.

Final current-source regression, MySQL, review and resource cleanup results are
recorded below. Full pytest and the entire mandatory MySQL suite
are intentionally not duplicated locally; PR remote CI's `regression` / `mysql` /
`test` jobs must verify them under unchanged workflow, inventory, timeout and
skip/xfail policy. No remote CI job has been started by this task.

## Test boundaries and remaining limitations

MySQL tests exercise durable Case/Fine restoration, real AVI-to-H.264 clip
generation after connection return, T1 rollback and lost COMMIT ACK, T2 rollback
and redelivery, cancel after actual build, Recording error versus DB error, a new
Case clip job without Fine/provider replay, and immutable clip reuse across
executions. Spies wrap the real build/encoder and assert exactly one invocation
per entered execution and zero main-pool checkouts at those slow boundaries.

API and Worker acceptance uses distinct spawned OS processes and a new Worker
for each stage. API HTTP is through ASGI TestClient inside the API child, not a
TCP API listener. Real MySQL, ffmpeg, public services, registry and T1/T2 remain;
only external Search provider HTTP uses MockTransport. Clip worker HTTP calls
are zero; build and encode calls are one. Readout jobs are asserted QUEUED with
the same clip ref; readout execution/package readiness is not claimed.

The slice supports one explicit VIDEO stream; multi-video selection is not
defined. Stronger process-kill recovery/encode-cost avoidance, orphan retention,
Case/Web failure presentation, readout/export execution, live provider, deployment
and cross-platform FFmpeg acceptance remain outside this validation. A process
dying after durable Recording publication but before T1 can leave prepared media;
existing retention policy and STALE handling are unchanged. A new execution can
encode again; exactly-once is per entered execution, not global crash-proof media
execution.

## Final verification and fresh review

The following executions used the final product/test snapshot after the review
fixes. They overlap; do not add them to one another or to earlier rows.

| Direct check | Result |
| --- | --- |
| Focused input/handler/composition/Recording config | 72 passed, 2.09 s |
| Worker / Recording / Case / common jobs, `-m 'not mysql'` | 1634 passed, 17 existing opt-in skips, 619 deselected, 169.36 s |
| Selected actual MySQL files below | 59 passed, 268.12 s; zero failures/errors/skips/xfails |
| MySQL report / JUnit cross-check | 59 unique tests, 177 setup/call/teardown phases, exact selected/collected/JUnit identity match; MySQL 8.4.13 |
| Boundary / Contract fixtures / diff whitespace | PASS; policies and Contract source unchanged |

MySQL selection: `tests/worker/test_incident_clip_mysql.py`,
`tests/e2e_runtime/test_production_search_process_mysql.py`,
`tests/worker/test_search_handlers_mysql.py`,
`tests/worker/test_case_composition_mysql.py`,
`tests/recording/test_durable_facts_mysql.py`,
`tests/case/test_result_reflection_mysql.py`,
`tests/worker/test_produced_store_mysql.py`. The seven process scenarios include
the existing normal/PARTIAL/Coarse-failed/Fine-failed/HINT cases and two actual
clip paths (10fps and 30fps). Each clip execution wrapped the real build/encode
and observed one call each, zero Search HTTP calls, and zero main-pool checkouts
at the slow entry points. Failure/new-job probes observed two builds for two
independent clip jobs; persistence/T2 replay added no build calls.

The offline skip identities exactly match the earlier 17 opt-in cases: fifteen
Recording external-media inputs and two Case external videos. No new skip or
xfail was introduced. The observed warning is the existing Starlette/httpx
TestClient deprecation. Workflow, mandatory inventory, timeout and skip/xfail
policies were not edited. Full pytest, all mandatory MySQL, remote CI, live
provider and deployment remain unexecuted, as explicitly scoped above.

The fresh reviewer started without implementation history, inspected the full
tracked/untracked product/test/doc delta and existing transaction/Recording
contracts, and performed no mutations or test/DB runs. It found one P2: incorrectly
restricting valid frame-aligned candidates to the originally requested scope.
The author reproduced it RED, retained scope/run/timeline/revision binding and
removed only that added range policy. The reviewer's separate inferred duration
coordinate risk was also reproduced RED and corrected to Search's start+duration
coordinate. Read-only follow-up inspected both actual fixes and positive
regressions, and the preserved 72-case GREEN text/XML: **no remaining product
P1/P2/P3 findings**. Its obsolete-scope documentation correction is incorporated.
An earlier reviewer attempt ended on a usage limit; it is not counted as a
completed review or independent execution evidence. This is not merge approval.

Docker stopped during resume; only the owned test container was restarted after
starting the daemon, and its new endpoint was used for final validation. Before
cleanup the server contained only system schemas and the task's disposable base;
non-audit clients, InnoDB transactions and data locks were all zero. The owned
container and its inspected anonymous volume were removed. All 21 task `*-temp`
directories (including generated AVI/MP4 and test env files) were removed after
checking resolved paths stay below the task scratch root and are not reparse
points. No such directories remain. The removed endpoint's bounded TCP probe
returned Windows 10035 (no connection); immediate connection refusal is not
claimed. Shared Docker/WSL processes were not stopped. Raw/JSON/JUnit evidence
remains ignored and excluded from PR candidates; no temporary DB data is retained.

## Changed-file inventory

- `docs/modules/recording/decisions/README.md`
- `docs/modules/recording/decisions/failure-taxonomy.md`
- `docs/runtime/rt10b-incident-clip-handler.md`
- `docs/runtime/rt10b-production-composition.md`
- `docs/runtime/runtime-implementation-log.md` (append only)
- `docs/superpowers/plans/2026-10-28-incident-clip-handler.md`
- `src/daesingo/recording/factory.py`
- `src/daesingo/worker/__main__.py`
- `src/daesingo/worker/registry.py`
- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/incident_clip_composition.py`
- `src/daesingo/worker/incident_clip_handlers.py`
- `src/daesingo/worker/incident_clip_inputs.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_production_search_process_mysql.py`
- `tests/recording/test_factory_config.py`
- `tests/worker/test_incident_clip_composition.py`
- `tests/worker/test_incident_clip_handlers.py`
- `tests/worker/test_incident_clip_inputs.py`
- `tests/worker/test_incident_clip_mysql.py`

RAW, JSON/JUnit, generated media, temporary DBs, env files and runners remain
excluded scratch evidence, not PR candidates. No original user media is used.

## 2026-10-31 follow-up — #486 §8

The single-VIDEO restriction described above is the historical RT-10(b) baseline.
The current unstaged sequential-source adapter and its verification are recorded
in [Multi-source IncidentClip Implementation Notes](multisource-incident-clip.md).
Earlier execution evidence and the original implementation history are preserved.
