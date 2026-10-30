# Multi-source IncidentClip — Implementation Notes

**IN_PROGRESS · Refs #486 §8 · Related #458, #297, #425 · 2026-10-31 KST.**
Local unstaged implementation; PR/merge SHA pending. This does not close Runtime
acceptance or claim actual user-video E2E or remote CI acceptance.

## Cause and implementation

The start gate checked branch `codex/multisource-incident-clip`, HEAD and the
local origin/develop ref at `3ec753ef05b110f7765db018d48f4390a9c4dcb9`, divergence
0/0, clean worktree and empty index. A fresh closeout fetch, retried with the
required filesystem permission after `.git/FETCH_HEAD` was blocked in the sandbox,
confirmed that the latest origin/develop still matches this HEAD (0/0).
No checkout/worktree change was made.
No repository AGENTS.md was found; the user-supplied AGENTS.md instructions,
root CLAUDE.md router, docs rules, Recording contracts and Runtime Plan §12 apply.

[Issue #486 §8](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/486)
and [the mentor inline and follow-up](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/458#discussion_r4413533556)
identify the single VIDEO restriction. A real Recording/FFmpeg handler test
reproduced both failures before modifying product code: a crossing event was
rejected by `len(videos) != 1`; an event wholly in B took singular resolution,
whose local baseline does not resolve a multi-placement timeline. Three REDs
(including missing detached Case selection) are preserved in excluded scratch.

The existing input and public capabilities already express the required facts:

| Boundary | Existing authority / new adapter use |
| --- | --- |
| SourceAsset / MediaStream | A physical file may contain simultaneous VIDEO streams. No role, filename or first-stream inference. |
| Case sources | Copy explicit `video_stream_ref` values into a detached tuple, as Search already does. |
| Fine AnalysisSource | Its VIDEO refs identify actual analyzed pixels, not every placement in the timeline. |
| Recording `resolve_span` | Supply all explicit selections for the revision using the existing plural argument for a chain. Recording alone selects intersecting spans and computes source-local coordinates. |
| SpanResolution / IncidentClip | Every returned used stream must be in Fine VIDEO provenance before build. Recording preserves the request, revision and ordered AssetSpans in clip provenance. |

Both Fine VIDEO refs and Case selections must be nonempty, unique and compatible;
all selected source ownership is checked through public Recording metadata and
`owns_asset`. Fine may reference only B while Case selects A→B. Resolver input
still includes A and B, and the resulting used spans include only B. A missing
required Fine stream cannot be supplied silently from another Case selection.
Single selected VIDEO retains the singular capability path. Multiple camera
streams from the same physical file remain ambiguous unless selection is explicit;
Recording's existing per-placement validation rejects ambiguous lists.

Runtime reads no Recording schema/internal repository and performs no placement
filtering, span construction, source-local coordinate calculation, sorting or camera guessing.
Recording implementation and canonical contracts are unchanged. Alternatives
such as deleting the length check, choosing the first VIDEO, or copying resolver
logic into Runtime do not satisfy these boundaries.

## Transaction, lifecycle and replay

`IncidentClipInputs` loads Case/dependency produced facts and stream selections in
the existing short caller transaction. It returns detached values; no Connection
or lazy stream escapes. Existing production composition opens an execution-local
Recording service backed by short `TransactionalRecordingRepository` callbacks
after the input connection has returned. Metadata, ownership and resolve calls
retain checkpoints. Build runs once per dispatch; context exit and the post-close
checkpoint are preserved on success, failure and cancellation.

The existing exact build-only error mapping remains
`INCIDENT_CLIP_BUILD_FAILED` → `RECORDING_INCIDENT_CLIP_BUILD_FAILED` with no
produced. Binding/ownership/resolve/context/DB errors keep their Runtime boundary.
No new terminal taxonomy, Contract meaning, duration tolerance or encoding policy
is selected. Success still returns only `{"incident_clip_ref": "..."}` and uses
the existing execution-specific receipt and T1/T2 persistence.

Tests distinguish terminal transaction rollback/unknown COMMIT receipt recovery
and T2 redelivery from a pre-T1 crash. The latter test injects `SystemExit` at the
record boundary after a real build, expires only its test lease and uses the
existing sweeper/new attempt. It is an injected crash test, not an OS kill of the
clip process. Existing generic Runtime OS kill cases separately cover RUNNING
recovery and the T1→T2 gap. A new attempt may rebuild; a committed terminal receipt
or T2 replay must not call build or encode again. Both Readout jobs still receive
the same clip ref through unchanged Case T2.

## Support and limits

| Input / condition | Result |
| --- | --- |
| Single selected VIDEO | Existing path preserved. |
| Explicit sequential A→B crossing | All required ordered source spans; timeline and source-local coordinates preserved. |
| Event within B of A→B | Full Case selection is resolved; clip uses B only. |
| One file, two simultaneous VIDEO streams | Explicit selected stream succeeds; ambiguous selection is refused. No front/rear role inference. |
| Missing selection/source, foreign ownership, wrong timeline/revision, Fine provenance mismatch | Safe refusal; no successful produced receipt. |
| Gap, overlap, corrupt/changed media, unknown coverage or unsupported media | Existing Recording checks remain authoritative. |
| Different output time bases | Existing safe refusal remains. #425 support implementation is not supplied by this adapter fix. |

[The #425 Recording Owner decision](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6493673627)
makes differing time bases a support target, with exact frame/coverage validation;
it does not claim implementation. The first mixed AVI/MP4 process fixture exposed
the current `UNSUPPORTED_MEDIA` guard before Search HTTP. Its failure originals
and diagnosis are retained in excluded scratch. The successful-path fixture uses
explicit matching 1/10 source time bases. No production validation was weakened.
Separate actual MP4 inputs with differing time bases still fail safely.

Excluded: #470 preview/payload, #486 §9 Case/Evidence time offset, GPS, new camera
policy, operational limits/profiles, provider/AWS/deployment, workflow/inventory/
timeout changes, broad formatting, full pytest/mandatory-MySQL/Docker rebuild.
`RT14_EXECUTION_ENABLED` was read through the GitHub API at closeout and remained
`false`; no variable was changed and no RT14 operation was invoked.

## Verification record

Detailed command output, JSON/JUnit, RED and failure originals live only under
`.codex-scratch/multisource-incident-20261031/` and are not PR candidates. Counts
below are separate runs and must not be added as unique test coverage.

| Direct execution | Evidence / result |
| --- | --- |
| Product-boundary RED before product change | `red.txt`: 3 failed as expected. |
| Initial handler/input/composition GREEN | `green.txt`: 63 passed. |
| Expanded Windows handler/input/media | `expanded2.txt`: 71 passed. |
| Frame PTS/duration and differing timebase refusal | `timebase.txt`: 14 passed. |
| Cancel during extra selection / real encode | `cancel2.txt`: 2 passed; context closed and temp empty. |
| Linux Python 3.12.16 / FFmpeg + ffprobe 8.1 | Existing local image `daesingo-issue452:local` (`f76274a9b66b`), current source mounted read-only, no rebuild. |
| Linux focused media/boundary suite | `linux-focused.txt/xml`: 463 passed, 4 original opt-in skips, 3 quality-tool environment failures. |
| Quality-tool environment failures | Existing runtime image lacks Ruff/mypy; three `test_real_quality_command_accepts_clean_and_rejects_violations` variants failed. No test/strict/skip rule changed. |
| Same quality tests on Windows with locked tools | `quality-test.txt`: 19 passed. |
| Linux quality environment repair / targeted rerun | Seven downloaded wheel SHA-256 values matched `uv.lock`; installed only into excluded scratch with network disabled, no image rebuild. `linux-quality.txt/xml`: 19 passed in 30.96s. The earlier three missing-tool failures are resolved environment failures. |
| Runtime quality command | `quality-final.txt`: Ruff passed; mypy Linux/win32 targets each passed 87 files. |
| Boundary / Contract | `boundaries.txt`, `contracts.txt`: 0 boundary violations; 62 structure / 26 JSON / 104 semantic checks passed. Initial Windows console encoding error was rerun with UTF-8. |
| Real MySQL / separate processes | Final results recorded at closeout below; earlier failures retained and explained above. |

Four opt-in skips are actual user media/pair tests in local incident clip, local
span resolution, multi-source timeline and multi-span AnalysisSource. No original
user video or explicit real-world placement was supplied. Synthetic media and
actual user footage are not interchangeable acceptance evidence. Remote CI and
full regression remain a future push/PR condition; this task does not push.

Additional exploratory Ruff on test files reported fixture-import and
compact-statement diagnostics outside the Runtime quality gate. No unrelated
lint cleanup was applied. The newly added multisource test file passes Ruff.

## Fresh review

A separate read-only reviewer received the requirements and checkout only,
without implementation history. Initial finding: no P0/P1/P2/P3. It directly ran
58 handler/input tests and 13 real-FFmpeg multisource tests; an initial unwritable
default-temp run was replaced with an isolated writable basetemp. It inspected,
but did not execute, MySQL/process evidence. Final delta review and remaining
limitations are recorded at closeout; PM Runtime acceptance remains deferred.

## Changed-file inventory

- `src/daesingo/worker/incident_clip_inputs.py`
- `src/daesingo/worker/incident_clip_handlers.py`
- `tests/worker/test_incident_clip_inputs.py`
- `tests/worker/test_incident_clip_handlers.py`
- `tests/worker/test_incident_clip_multisource.py`
- `tests/worker/test_incident_clip_mysql.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_production_search_process_mysql.py`
- `tests/recording/test_multi_span_incident_clip.py`
- `docs/runtime/multisource-incident-clip.md`
- `docs/runtime/rt10b-incident-clip-handler.md`
- `docs/runtime/runtime-implementation-log.md`

## Draft reply to PR #458 inline (not posted)

원인은 Runtime이 Fine AnalysisSource의 VIDEO를 하나로 제한하고 그 하나를
단일 ref의 resolve_span에 전달한 데 있었습니다.

다중 원본 P0를 로컬 수정했습니다. Case에 이미 저장된 원본별 명시적 VIDEO 선택을
짧은 transaction에서 분리해 읽고, Recording 공개 `resolve_span(...,
media_stream_refs=...)`으로 전체 선택을 전달합니다. 사건에 실제 쓰인 span이 Fine의
VIDEO provenance에 속하는지도 확인합니다. 순차 A→B와 한 파일의 동시 camera를
구분하며, 첫 VIDEO나 camera role을 임의로 고르지 않습니다.

단일/경계 교차/B 내부 사건, 명시적 camera 선택과 모호성 거부, 실제 FFmpeg frame
coverage·source provenance·원본 불변, T1/T2 및 offline process 검증 결과는 이
Implementation Notes의 closeout에 기록했습니다. 서로 다른 출력 time base 지원은
#425 후속이며 현재 안전 거부를 유지합니다. 실제 사용자 원본 E2E와 원격 CI는
미실행입니다. 현재 변경은 미커밋/미스테이징이며 PR/commit 링크는 아직 없습니다.
PM Runtime acceptance와 멘토 확인 전에는 이 thread를 resolve하지 않습니다.

## Closeout evidence

The final Linux run (`linux-finalmysql.txt/xml/json`) passed **17 tests** in
145.16 seconds against **MySQL 8.4.13**, without skips/xfails. It includes ten
single/chain T1/T2 fault cases, existing cancellation/failure/new-job/immutable
receipt cases, the chain pre-T1 injected crash/new attempt, and separate API and
Worker OS process single/chain cases. Each independent normal chain dispatch
builds once and encodes two spans; rollback/receipt recovery/T2 redelivery adds
zero builds/encodes. The pre-T1 interrupted attempt and replacement each build
once/encode twice (two builds/four span encodes total); subsequent T2 adds zero.

Separate process tests assert Coarse HTTP=1, Fine HTTP=1, clip HTTP=0 through
offline transport, and distinct parent/API/Worker PIDs. Runtime pool checkout is
zero at build and actual per-span encode; process peers also check zero at the
Recording media command boundary, including decode/concat. T2 durably enqueues
both Readouts with the exact same clip ref. Readout provider execution itself is
outside this test's scope.

Earlier `linux-mysql2` ran two generic Runtime **OS kill** recovery cases
successfully along with nine other passing cases; its six chain failures were
the pre-Search mismatched-timebase fixture, retained as failed evidence. The
subsequent `linux-probe`/`linux-probe2` failures exposed test instrumentation and
offline playback-coordinate errors. Those runs are not counted as passing E2E.
The final run corrects those fixtures without changing product validation.

Fresh delta review directly ran **16** current offline media tests and found no
P0/P1/P2/P3 issues. The same reviewer then inspected final 17-case MySQL text,
XML and JSON (17 selected cases / 51 phase reports), with no additional finding.
It did not execute that suite. Cancellation tests demonstrate cancellation at
the eventual existing checkpoint and context/temp cleanup, not interruption of
an active FFmpeg subprocess. PM Runtime acceptance is still outstanding.

Remaining limitations are #425 implementation, actual user footage/real-world
placement acceptance, existing whole-span in-memory materialization, and remote
CI/full regression. No new reviewer P1/P2/P3 was left unresolved. No staging,
commit, push, external reply, PR, merge or deployment was performed.

Owned MySQL container and its anonymous volume, network, all generated successful
media/test directories, temporary quality dependencies and both reviewer temp
directories were removed. Linux-created pytest symlinks were checked and removed
inside the same local image after the Windows cleanup safely stopped on them.
Only five small failure-original media files (31,302 bytes total), logs, JSON/XML
and minimal runners/summaries remain in excluded scratch. Shared images/cache
and other tasks' data were preserved. Final inventory: 12 changed/untracked files,
unchanged branch/HEAD, empty index; no large successful-media copies accumulated.
