# RT-10(b) Recording exports — Implementation Notes

Refs #297, #47, #351. Work date: 2026-10-29 KST.

## Authority and provisional decisions

The PM delegation in the implementation request permits minimal reversible
Runtime wire decisions. Existing Contract, Evidence policy and #351 timing are
binding; #47 Owner confirmation is deferred review, not a pre-implementation gate.

The plate request is `incident_clip_ref`, `frame_ref`, `plate_bbox_xywh`,
`max_byte_size`. Neither crop identity nor associated vehicle region is used.
The limit is relayed from the existing Evidence attachment policy (30_000_000
bytes), never calculated or interpreted by Case. All request fields participate
in the fingerprint. Recording attempts bounded PNG crop/downscale within one
capability invocation; ordinary failure and inability to fit the output have
distinct codes. Limit failure has no same-input retry action.

Report input fixes the selected clip and Evidence's post-stamp decision/value.
Case issues exports after the selected situation response and assembled evidence,
before READY, once per input; command and observation T2 share this gate.

Export inputs use a separate append-only Case map and public read method. Worker
preloads a detached Recording snapshot in a short transaction, invokes exactly
one export with no DB operations, then publishes immutable output outside that
invocation. Existing produced receipts, T1, reconciliation and T2 own replay.
No global exactly-once claim is made for process death before durable T1.

## Implementation plan and verification ledger

- [x] Recording public capabilities: real media RED, bounded failure, provenance,
  actual size, immutable regeneration, safe errors, then GREEN.
- [x] Detached Worker inputs/context/handlers and complete JOB_KINDS registry:
  RED then GREEN; cancellation and infrastructure boundaries.
- [x] Case #351 automatic order, immutable input/fingerprint, retry/notice and
  current-input asset projection: RED then GREEN.
- [x] Real MySQL T1/T2 rollback/lost COMMIT, reconciliation, duplicate delivery,
  cancellation, restart and separate API/Worker process E2E.
- [x] Focused and related regression, boundary, Contract fixture, diff check.
- [x] Fresh read-only reviewer of the entire uncommitted diff, P1/P2 fix/recheck.

User requires current branch, no staging/commit/push/PR. Full local pytest and
entire mandatory MySQL inventory may remain for remote split CI; record omissions.
Scratch, media, credentials, RAW/JSON/JUnit and disposable DB are excluded.

## Results, file manifest and remaining risks

Start gate: branch `codex/rt10b-recording-export-handlers`, clean tree/index,
HEAD `85dd30b91b82711a4d56bbc3ea916a3bd3c2a355`. Existing checkout is explicitly
requested; no worktree or branch switch. Implementation uses the existing Python,
SQLAlchemy, Pydantic, ffmpeg and MySQL stack without new dependencies.

### RED / GREEN and direct execution (overlapping snapshots)

| Execution | Observed result |
| --- | --- |
| Recording initial RED | 10 setup errors: absent export module; repeat with explicit missing-capability assertion also failed all 10 at setup |
| Recording GREEN | 10 passed, 15.12 s; actual generated MP4/PNG, crop, limit/downscale, immutable refs, stamp |
| Handler/order RED | 29 failed: missing implementation modules |
| Handler/order GREEN | 29 passed, 0.24 s |
| Export-input immutability RED | 2 failed, 12 passed: mutation/removal was accepted |
| Focused inputs/handlers/orders GREEN | 46 passed, 0.29 s |
| Existing notice + initial wiring | 39 passed, 0.31 s |
| First related offline run | 35 failed, 1739 passed, 17 opt-in skips, 657 deselected, 180.61 s; not a passing run |
| Native media subset outside sandbox | 74 passed, 6 opt-in skips, 29.93 s; confirms the 16 media failures were sandbox default-temp access |
| Entrypoint/READY compatibility fix run | 81 passed, 1 tmp-directory permission setup error, 22.18 s; not an all-green run |
| Actual MySQL export fault/cancel run | 20 passed, 56.30 s, MySQL 8.4.13, no skips/xfails |
| Separate API/Worker process E2E | 2 passed, 82.81 s; both command-triggered and observation-T2-triggered automatic order |
| Boundary / Contract fixtures / diff | PASS, 0 boundary violations; 62 structure / 26 JSON / 104 semantic checks |

Intermediate failures are preserved separately under ignored
`.codex-scratch/rt10b-exports-20261029/`: UTF-8 script decoding, incorrect use of
OpenedDerivedAsset as a context manager, localhost preflight sandbox rejection,
FrameRef model versus ref-string fixture error, accidentally placed MySQL
immutability query in insert rather than save, and fault probe targeting the
wrong table name. These were fixed; their failed runs are not relabeled PASS.
Boundary initially rejected a report error message containing a forbidden domain
word; the message was made generic without weakening the checker.

The first related regression also found two product regressions introduced here:
export composition eagerly required full RuntimeConfig from lightweight existing
entrypoint test setups, and observation T2 unnecessarily assembled a full view
for adapters with no export request port. Both were fixed while preserving those
adapters' prior READY behavior. Full related rerun and expanded MySQL are pending
in this ledger.

### Boundaries and deferred review

- #47 Owner deferred review: request field names/version, image output-limit code,
  fingerprint framing, transform metadata representation, and PNG crop/downscale
  strategy. Existing `best_frame.plate_bbox_xywh`, source ownership, Case response
  timing and Evidence policy meanings remain binding. No crop_ref or vehicle
  associated_region is used.
- Report errors retain `REPORT_VIDEO_EXPORT_FAILED` and the existing dotted
  notice mapping. Plate uses `PLATE_IMAGE_EXPORT_FAILED` versus provisional
  `PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE`; the latter has no retry action.
- Export service/encoder use detached immutable bytes with no connection or
  transaction. Capability returns before publication. Publication's retries reuse
  the same new DerivedAsset and transform. T1 result refs are per execution,
  separate from Recording refs; T1/T2/reconciliation core is unchanged.
- Case selection uses successful, reflected produced refs matching current full
  request, so changed stamp/crop/limit does not silently select a prior output.
  Actual output size is stored and relayed to Evidence. Recording transform facts
  supply `post_stamp_applied`; Case does not infer pixel work from request alone.
- Each E2E stage is a new spawned OS Worker; API is a separate persistent child
  using ASGI TestClient (not a TCP API listener). Search HTTP/OCR are offline at
  provider boundaries. Recording refs, frames, encoding, repositories, T1/T2 and
  MySQL are real. Export T2 is deliberately rolled back, then redelivered without
  a media process.

Whole pytest, the complete mandatory MySQL/nested mutation inventory, remote CI,
Linux/cross-platform ffmpeg, live provider/OCR, large media, deployment and abrupt
process-kill before durable T1 remain unverified here. Remote split CI still owns
full regression/mysql/test gates; this uncommitted diff has no remote CI result.
If a process dies after Recording publication but before T1, orphan media may
remain and a later STALE execution can encode again. Exactly-once is per entered
execution and committed-terminal replay, not crash-proof global media execution.
No new retention or cleanup policy is introduced. PNG downscale may reduce
legibility; no new OCR/quality judgment or internal byte target is imposed.
Report stamping uses a fixed supplied time value with Recording's provisional
H.264 strategy and ffmpeg's installed font; deployment font consistency remains
an operational risk.

Final test results, full file manifest, independent review and resource cleanup
will be appended after the running checks.

### Related regression after compatibility fixes

`python -m pytest tests/worker tests/recording tests/case tests/common/jobs -m
'not mysql' -q -p no:cacheprovider --basetemp=<ignored task scratch>
--junitxml=<ignored task scratch>/regression-final.xml`: **1774 passed, 17 existing
opt-in skips, 660 deselected, 134.91 s**. This is the relevant module selection,
not whole pytest. One upstream Starlette TestClient/httpx deprecation warning is
preserved. All 35 failures in the first run are covered by this successful rerun.

The 20-test MySQL export run and 2-test process run have been cross-checked:
MySQL 8.4.13; exact collected/selected/JUnit identity agreement, 60 and 6 complete
setup/call/teardown phases, respectively; no skip/xfail/error/failure.
These scoped checks do not claim the full mandatory inventory gate passed.

### Expanded MySQL and canonical fact follow-up

The expanded selection ran **56 passed, 206.21 s**, MySQL8.4.13, zero skip/xfail:
23 export tests, 2 independent API/Worker process tests, 4 Case composition tests,
9 IncidentClip tests and 18 Readout tests. JSON/JUnit agreed on 56 identities and
168 setup/call/teardown phases. It included publication/T1/T2 deadlock rollback
and lost COMMIT acknowledgements, T2 interruption/redelivery, reconciliation
interruption, actual capability cancellation, plate ordinary failure versus size
exhaustion, and MySQL append-only input enforcement.

After this run the author added a direct canonical AssetFacts assertion: new
exports were visible through list-case fallback but direct lookup returned
UNKNOWN_REF (**1 failing test**). `lookup_asset_facts` now computes metadata/content
facts for this new export-transform-backed class only; legacy fixture lookup
rules are retained. Follow-up focused **102 passed, 31.87 s**, and all export
MySQL **23 passed, 55.37 s**; the latter has exact23/69 identity/phase agreement.
The 1774/56 rows describe the earlier source; they are not silently relabeled as
post-follow-up runs. Relevant changed behavior was directly rerun.

### Fresh reviewer: first finding and fix

A single reviewer was dispatched with `fork_turns=none`, the complete35-file
manifest, requirements and SoT pointers, read-only and without DB/test mutation.
It independently reproduced P2: A export fails, B is ordered, selection returns
A; the visible A notice invoked the most recent B job. The fix selects retry
basis by complete current export request inside command processing, while legacy
adapters retain prior behavior. Both report and plate command regressions were
**RED2** (clip-B instead of clip), then `test_export_ordering.py` plus
`test_command.py` **63 passed, 0.46 s**. The same reviewer is checking this delta
and the rest of the entire diff. No new reviewer or inherited-history review is
used. Final review verdict remains pending here.

### Final fresh read-only review and resource state

The same fresh reviewer completed the entire35-file diff and relevant Contracts,
then rechecked the P2 fix. It independently exercised real execute_command with
no-file `python -B` probes: report and plate both retry A after A→B→A. It also
probed StoredObservationAdapter with changed bbox on the same clip: old image
excluded, current image/report retained. **No unresolved P1/P2** was found. The
reviewer did not run pytest, DB/media tests or audit all raw JSON/JUnit.

P3 validation improvements are deferred and remain visible: (1) persist a
production adapter correction/reread regression for bbox/stamp changes; (2)
assert actual stamped-frame pixel change and byte preservation when disabled.
These are test-strength gaps, not claims of independent pixel verification.
Forced process death before T1, Linux/font consistency, large media, full
mandatory CI and #47 final wire review were explicitly not judged.

After the P2 fix, API/Evidence non-MySQL regression **335 passed, 248 deselected,
95.34 s**, one existing Starlette/httpx deprecation warning. The earlier sandbox
attempt stopped at its first API cleanup test without completing; it was
terminated by verified task process IDs. Cause was not established; the same
selection outside the sandbox passed. Two newly created zero-byte root cleanup
locks were verified exclusively openable and removed after the test processes
ended. No product or timeout policy was changed for this test environment.

The task-owned MySQL container and its inspected anonymous /var/lib/mysql volume
were removed after an autocommit audit showed unexpected schemas0, other clients0,
InnoDB transactions0 and data locks0. Container/volume inventories confirm absence.
RAW/reports and generated test media/env live only under the ignored task scratch
root; no source-tree credential/config was created or modified. Source helpers
carry only offline provider data. Scratch/media/RAW/JSON/JUnit are not delivery
files. No index/HEAD/remote change or Issue/PR operation occurred.

### Complete changed-file manifest (35 files)

- `docs/modules/case/decisions/report-video-export.md`
- `docs/modules/recording/decisions/failure-taxonomy.md`
- `docs/runtime/rt10b-recording-exports.md`
- `docs/runtime/runtime-implementation-log.md`
- `src/daesingo/api/composition.py`
- `src/daesingo/case/command.py`
- `src/daesingo/case/domain.py`
- `src/daesingo/case/exports.py`
- `src/daesingo/case/jobs.py`
- `src/daesingo/case/real_e2e.py`
- `src/daesingo/case/reflection.py`
- `src/daesingo/case/service.py`
- `src/daesingo/case/store.py`
- `src/daesingo/case/store_mysql.py`
- `src/daesingo/case/store_state.py`
- `src/daesingo/case/stored_observation.py`
- `src/daesingo/recording/README.md`
- `src/daesingo/recording/exports.py`
- `src/daesingo/recording/mysql_repository.py`
- `src/daesingo/recording/queries.py`
- `src/daesingo/recording/repository.py`
- `src/daesingo/recording/service.py`
- `src/daesingo/worker/case_composition.py`
- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/export_composition.py`
- `src/daesingo/worker/export_handlers.py`
- `src/daesingo/worker/export_inputs.py`
- `tests/case/test_export_ordering.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_export_process_mysql.py`
- `tests/recording/test_exports.py`
- `tests/worker/export_support.py`
- `tests/worker/test_export_handlers.py`
- `tests/worker/test_export_inputs.py`
- `tests/worker/test_export_mysql.py`


Final same-reviewer documentation delta recheck: no unresolved P1/P2 or evidence
inconsistency. Reviewer verified the exact35-file manifests in both documents,
reviewed source fixes, unchanged HEAD/empty index, original Log byte prefix and
git diff --check. No reviewer file/test/DB mutation. P3 two test-strength items
and #47/CI/operational deferred boundaries remain as stated. Final state is
uncommitted and unstaged; no staging, commit, push, PR or Issue operation.
