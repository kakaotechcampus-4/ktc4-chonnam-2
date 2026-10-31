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


## Issue #425 mixed time base — 2026-10-31 KST

Status IN_PROGRESS · Refs #425 · Related #452, #460. Local unstaged implementation.
[Design, numeric bounds and plan](../modules/recording/mixed-timebase-plan.md) is
this change's rule reference. Owner decision and reproduction comments were read
directly. Start branch `codex/issue425-mixed-timebase`, clean tree/index, full HEAD
`6d8dbc9485b9060938e2036ff4874de7985bff1c`; live origin/develop was identical.
No worktree, staging, commit, push, PR, merge, deployment, dispatch, provider/AWS or
shared EC2 access. Repository AGENTS.md was absent; supplied instructions and the
CLAUDE.md/document router were read.

### Author execution evidence

| Check | Observed result |
| --- | --- |
| Initial synthetic RED | Four failures at mixed-clock connection after individual success; two clock pairs, both public capabilities |
| Earlier VFR setup attempt | veryfast single conversion rejected coverage; recorded separately, not counted as connection RED |
| Focused synthetic GREEN | 49 passed (before final three packet-bound tests); includes exact source/output frames, decoded color order, B-frame seam, negative controls, remux byte/timeout/cancel cleanup |
| Related FFmpeg 8.1 regression | 946 passed, 16 existing opt-in/platform skips, 126 MySQL deselected; Recording plus selected Worker, execution and cleanup tests; 68.94 s |
| Verification-bypass mutant | Two expected test failures (DID NOT RAISE), mutating source-coverage guard in memory only; mutation did not alter source files |
| Additional integer bounds | RED 3 missing-helper failures, then 11 pure arithmetic checks passed including those 3; no native media execution in this Windows check |
| Boundaries/Contract/ruff | PASS: no boundary violations; 62 structure, 26 JSON, 104 semantic fixture checks; changed new code lint clean |
| Actual local inventory | 10 available AVI files inspected metadata-first; explicit VIDEO index 0 selected, no camera role inferred |
| Actual eligible pair | COMPLETE public AnalysisSource; short explicit experimental placements, 12 frames exactly preserved, clock 1/900390, 155798 output bytes, provenance and original SHA-256/size/mtime unchanged; cleanup verified |
| Actual strict/fallback | Successful pair: two initial strict encodes succeeded, no fallback; earlier selected source failed source coverage and remained UNSUPPORTED_MEDIA |
| Original Issue media | Original AVI nine-file / MP4 two-file repro sets not established; their completion evidence remains unverified |

Actual pair used existing 480/ultrafast/23 configuration. Earlier 480/veryfast/23
and short ultrafast attempts against the first metadata-selected pair failed:
the second source's original frame coverage was discontinuous. A subsequent
source-only coverage check rejected that source and selected an eligible pair;
no source was repaired or fully converted. The coordinates are explicit test
placements, not a claim of real filming continuity. No original names, identifiers,
paths or frames are included in public evidence. Output videos existed only in
task containers' tmpfs and were removed on exit.

The reused local image is `daesingo-issue452:local`, actual image ID
`sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`.
Both FFmpeg and ffprobe report 8.1, GCC 12 Debian 12.2.0-14+deb12u1, libavutil
60.26.100, libavcodec 62.28.100 and libavformat 62.12.100, with the same build
configuration. No Windows PATH media result substitutes for this verification.
The image lacked pytest; existing local pure-Python pytest dependencies were
copied to task scratch and mounted, with plugin autoload disabled. No image or
shared cache was changed. Network was disabled and original media mounted read-only.

Preserved intermediate failures include missing pytest `py` dependency, UTF-8
edit/console errors, a missed internal field edit, an incorrect nested offset
expression, an incorrect test-only clip-open method and B-frame seam duration.
These are not relabeled successful. The B-frame case drove separate decode-clock
projection; final exact frame and packet validation detected the wrong offset.

UNSUPPORTED_MEDIA terminal/notice policy remains the separate Owner item described
in the design. No new Runtime taxonomy was inferred. Both AnalysisSource and
IncidentClip inherit the internal media fix; prepared stores and provenance
schemas are unchanged. No DB implementation changed, so MySQL was not run locally.
Full pytest, full mandatory MySQL/mutation inventory, real original Issue sets,
API/Worker provider E2E and deployment remain unexecuted. Remote full integration
is a condition after an independently authorized push, not a result of this work.

Candidate files: `src/daesingo/recording/{chain_clock,materialization,multi_analysis}.py`,
`tests/recording/{test_mixed_timebase,test_multi_span_incident_clip}.py`,
`docs/modules/recording/{mixed-timebase-plan,multi-span-analysis-source,multi-span-incident-clip}.md`,
this Notes file and `runtime-implementation-log.md`. PR-excluded:
`.codex-scratch/issue425/` runners, copied test dependencies, XML and anonymized
summaries. No media, original identifiers or runtime credentials belong in the PR.
Fresh review, final delta verification, prefix audit and cleanup are recorded below.


### Issue #425 fresh review and final delta evidence

GPT-6.1 Sol / High reviewed from a fresh context without implementation chat history,
and read the Issue/Owner comments directly. Two P2 findings were reproduced and
fixed: (1) a linear-depth setts expression fails around 99 segments; balanced
packet-ordinal lookup removes this depth dependency, and (2) LCM of unused stream
ticks rejected sparse but exactly representable inputs; clock selection now uses
actual frame plus packet timing denominators. The nominal AVI-clock LCM by itself
therefore does not establish that those files are unsupported. Actual Issue-set
observations remain necessary and unverified.

Author evidence: depth-red failed once; a flat-sum intermediate also failed FFmpeg
AVExpr depth and is preserved separately; balanced expression plus focused tests
passed 53. Sparse public RED failed once after both individual conversions passed;
final sparse-inclusive focused suite passed **54**, no skips/xfails, 8.50 s.
The new mixed-remux failure tests run the real cleanup scanner: a live lease
prevents removal of deliberately aged files, then cleanup proceeds after failure
releases the lease. Byte exhaustion, timeout and cancellation retain their codes.
Source fingerprints and absence of partial publication are also checked.

Reviewer direct execution (distinct from author XML review): exact image identity,
original parser-depth reproduction; balanced 99/101/1024-expression probes; sparse
public-boundary failure and successful exact-clock counterfactual; finally **13
passed, 22 deselected** for sparse public, packet precision, numeric boundaries and
expression regression on FFmpeg 8.1. Reviewer inspected author 946-pass and final
54-pass XML rather than independently rerunning those suites. Code delta verdict:
no remaining actionable finding. No private media, DB or remote hosts were used
by the reviewer. Documentation correction is submitted for a final separate delta check.

`media-identity.json` records full version/configuration and binary hashes:
FFmpeg `19e0073f42f3cc0c1880ac9a4a91fc6c42d511bec9497db03872cc527791c91a`,
ffprobe `ec4bde78f8b08c56109d68fffb16e9972ae7543ed62253fd90e699dda4a0f975`.
Notes and Log pre-existing byte prefixes were SHA-256 checked and preserved;
existing LF line endings were retained. Review-stage focused reruns follow below.


Final post-review author run: **244 passed, 4 unchanged opt-in/platform skips**,
36.66 s, FFmpeg/ffprobe 8.1. It covers mixed/same-clock AnalysisSource and
IncidentClip, single-input media, frame-duration/tail strictness, budgets/process
cleanup, Worker limit mapping/multisource use, and actual cleanup leases. The real
eligible pair was repeated against the final code: 12 exact frames, 1/900390,
155798 bytes, same provenance, unchanged source fingerprints and cleaned temp;
both encodes succeeded strict-first, no fallback. No native PATH9.0.1 media run.


### Issue #425 final local handoff

Same reviewer checked the corrected documents and found no remaining actionable
code/document finding. It also independently checked original Notes/Log byte
prefixes, LF preservation, empty index and diff check. Its review of actual media
results was of the author's anonymized JSON only, not direct private-media use.
The actual final file is `.codex-scratch/issue425/real-pair.json` (an earlier
review message called it `real-pair-eligible.json` incorrectly). Intermediate
actual-media summaries are reconstructed from captured tool output in
`real-attempt-history.json`; earlier attempts wrote to the same output filename.
Their failures remain reported, not replaced by the final PASS claim.

Task containers used --rm, network none and tmpfs; task container residue is zero.
No task volume was created. No successful intermediate media remains on the host.
The copied pytest dependency directory was removed after checking its absolute
path under task scratch. Remaining ignored evidence: 36 small files, 357075 bytes
at cleanup measurement (XML, runners, prefix hashes and anonymous summaries).
Shared images/caches and other work materials were preserved. C: free space was
about 2.12 GiB at start and 9283850240 bytes (about 8.65 GiB) at cleanup; the change
in free space is not attributed solely to this task.

Branch/HEAD remain `codex/issue425-mixed-timebase` /
`6d8dbc9485b9060938e2036ff4874de7985bff1c`. Ten candidate files are unstaged;
index empty, diff check passed. No staging/commit/push/PR/merge occurred.
Status remains IN_PROGRESS: original Issue AVI/MP4 repro evidence and agreed
UNSUPPORTED_MEDIA terminal/Case notice mapping remain open. Full remote CI after
an authorized push must run repository regression, strict MySQL/mutation inventory
and boundary/Contract/quality gates without policy relaxation. This local result
is neither Issue closure, one-hour analysis support nor deployment completion.


### PR #499 CI follow-up: duration observability (2026-10-31)

Status: IN_PROGRESS · Refs #425 · Related #452, #460. Start branch
`codex/issue425-mixed-timebase`, HEAD
`4369bdc668435d432440a77006fdb6f73538edab`, worktree/index clean.
[Remote failure](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/41185698185/job/124492062285)
ran the PR merge ref `8a32827548b059d1b853b5e17a3d6fb8aa33f276` with
Ubuntu FFmpeg/ffprobe `6.1.1-3ubuntu5`, Python 3.12.15. The failing node was
`test_multi_span_incident_clip.py::test_different_actual_time_bases_preserve_clip_provenance`.

Author reproduced the unchanged node: **1 failed**, identical missing last-frame
duration error. Instrumentation located failure in the first individual encode's
`output_validate`, before the second encode, common-clock normalization or concat.
The original MP4 has 20 frames and observed duration 1024 at time base 1/10240.
Its selected one-second veryfast output has 10 frames; 6.1.1 reports no duration
on any packet and neither duration nor pkt_duration on the last decoded frame.
No verified-coverage exception applies to this ordinary MP4. Strict rejection is
correct under the existing individually-successful-input scope of #425.

Cross-probing both 6.1.1-generated and 8.1-generated versions of the SAME synthetic
files isolates the reader difference: 6.1.1 misses all ten output packet durations
and the tail duration, while 8.1 reports duration 1024. Both readers observe the
original durations. This is not evidence of lost encoded frames or a concat bug.
The n6.1.1 [MOV reader](https://github.com/FFmpeg/FFmpeg/blob/n6.1.1/libavformat/mov.c#L8386-L8401)
does not assign packet duration in its CTTS branch; n8.1
[MOV finalization](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/mov.c#L10494-L10505)
reads sample duration before CTTS handling. Trace-header observations also show
source/output H.264 time_scale 20/20480, num_units_in_tick 1, fixed_frame_rate_flag 0;
n6.1.1 [duration computation](https://github.com/FFmpeg/FFmpeg/blob/n6.1.1/libavformat/demux.c#L610-L650)
has a codec-rate bound relevant to this fine encoder clock. The decisive evidence
is the measured frame/packet output, not an FPS-derived replacement duration.

Minimal fixture correction: use ultrafast for this success test's output profile,
leaving source generation rates 10/12 and actual clocks 1/10240 and 1/12288.
Both individual outputs now expose durations to both readers. Product code,
strict checks, fallback scope, numeric bounds, API/Worker/receipt contracts and
workflow/dependencies are unchanged. No new support promise for unobservable
veryfast output on 6.1.1 is made. Runtime UNSUPPORTED_MEDIA-specific terminal/Case
mapping remains the prior unresolved Owner item, outside this change.

The test now observes the real mixed normalization call, independently probes
source/output PTS and duration, requires clock 1/60, all 22 frames in order,
exact boundary coverage at one second and endpoint two seconds, checks decoded
red/blue segment order, provenance and original SHA-256/size/mtime preservation.
No duration is synthesized by the test's probe helper. Existing VFR, rejection,
overflow, timestamp mutation, same-clock and cleanup tests also execute.

Direct author results (no new skip/xfail or policy changes):

| Environment | Media focused (six files, including whole failing file) | Safety/Worker focused (six files) |
| --- | --- | --- |
| Ubuntu FFmpeg/ffprobe 6.1.1-3ubuntu5 | 155 passed, 4 existing skips; 95.80 s | 88 passed, 1 existing platform skip; 41.97 s |
| Existing identical-build FFmpeg/ffprobe 8.1 | 156 passed, 3 existing skips; 29.55 s | 88 passed, 1 existing platform skip; 18.07 s |

The extra 6.1.1 skip is the unchanged synthetic AVI test that does not observe a
strict encode failure on that binary. Its existing policy stays intact; this is
not fallback success evidence. The changed node passes and all its exactness
assertions execute on both versions. The unmodified veryfast node also passed
in the author's 8.1 diagnostic run before the correction.

6.1.1 ran at `/repo`, `/usr/bin/ffmpeg` and `/usr/bin/ffprobe`, Python 3.12.3
at `/tmp/ci-venv/bin/python`, in a task-only Ubuntu 24.04 container. Actual binary
SHA-256: ffmpeg `ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41`,
ffprobe `272f6ebc634a63d9c8b4ca68e964119d980f25154e5aa2c35e5487da48e9a58f`.
8.1 reused `daesingo-issue452:local`, image
`sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`,
at `/repo`, binaries `/usr/local/bin/ffmpeg` and `/usr/local/bin/ffprobe`, Python
3.12.16 at `/app/.venv/bin/python`. Binary hashes match the preceding #425 evidence.
Full tool identities and temporary Python dependency versions are in ignored
evidence; Python/dependencies are not claimed identical to the remote runner.
Windows PATH media binaries were not used. Native Runtime quality (ruff and mypy
linux/win32, 87 files each), boundary, and Contract fixtures (62/26/104) passed.
An optional lint of the entire changed test file reports the same 17 pre-existing
findings as HEAD (F401/F811 fixture import plus E701); no Runtime gate was relaxed.

Current private input inventory matches the user's seven remaining files.
No private media was decoded/reprobed for this CI fix, and no removed file was
searched for or restored. The earlier ten-file inventory and actual-pair 8.1 run
remain historical evidence with their original inputs/tools; they are not fresh
evidence for the seven-file inventory. No pending validation here depends on the
removed inputs. Current mixed clocks are not asserted without measurement.
The original Issue AVI-nine/MP4-two sets remain unconfirmed.

Complete candidate file list: this Notes file, `runtime-implementation-log.md`,
and `tests/recording/test_multi_span_incident_clip.py`. PR-excluded material lives
only under ignored `.codex-scratch/issue499-ci`: original test snapshot, RED XML,
stage/cross-probe JSON, tool identities, focused XML, runners and prefix hashes.
Earlier `.codex-scratch/issue425` evidence is preserved. No private identifiers or
frames are added to public documentation. Fresh review and cleanup results follow.
Full pytest, mandatory MySQL, full mutation and Docker OCR acceptance are not
repeated locally; all remain conditions of a later authorized push's remote CI.


### PR #499 fresh review and local cleanup

Fresh GPT-6.1 Sol / High reviewer, without implementation conversation history,
found no actionable finding in the three-file delta. It directly ran the changed
node on 6.1.1 and 8.1: **1 passed on each, no skip** (reviewer61.xml/reviewer81.xml).
It reviewed the author's broader XML and diagnostic evidence; it did not rerun
the full focused groups or private media. Source/clock assertions, strict boundary,
document prefix/LF, branch/HEAD/index and diff check were independently checked.
No code correction was requested. Native checker execution used Windows Python
3.12.14 at the repository .venv/Scripts/python.exe; media checks used Linux tools
as recorded above.

Task Ubuntu container and its installed dependencies/intermediates were removed.
Temporary 8.1 containers used --rm. No task container/volume remains. Copied pytest
dependencies and all successful intermediate videos were deleted after checking
target paths inside task scratch. Two tiny synthetic source/failing-output MP4s
remain solely for reproducing the cross-probe diagnosis, alongside small JSON/XML
evidence. Shared images/build cache, other tasks and originals are preserved;
previous issue425 evidence remains 36 files / 357075 bytes. C: free space was
about 8.48 GiB at start and 10903822336 bytes (about 10.16 GiB) at cleanup; this
change is not attributed solely to this task.

Final candidates remain exactly the test and the two append-only documents listed
above, unstaged/uncommitted; index empty and git diff --check PASS. Branch/HEAD
remain codex/issue425-mixed-timebase / 4369bdc668435d432440a77006fdb6f73538edab.
No external write, push, workflow dispatch or deployment occurred. Full remote
CI after a later authorized push remains required; neither merge readiness nor
Issue closure is claimed.
