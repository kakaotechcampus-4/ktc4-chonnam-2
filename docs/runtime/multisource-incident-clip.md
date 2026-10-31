<a id="multi-source-incidentclip--implementation-notes"></a>

# 다중 source IncidentClip — 구현 기록

**IN_PROGRESS · Refs #486 §8 · Related #458, #297, #425 · 2026-10-31 KST.**
로컬 unstaged 구현이며 PR/merge SHA는 미정이다. Runtime
인수를 종료하거나 실제 사용자 동영상 E2E 또는 원격 CI 인수를 주장하지 않는다.

<a id="cause-and-implementation"></a>

## 원인과 구현

시작 gate는 브랜치 `codex/multisource-incident-clip`, HEAD와
로컬 origin/develop ref가 `3ec753ef05b110f7765db018d48f4390a9c4dcb9`임, divergence
0/0, 깨끗한 worktree, 빈 index를 확인했다. 마무리 시 새 fetch는
sandbox에서 `.git/FETCH_HEAD`가 막힌 뒤 필요한 파일시스템 권한으로 재시도했으며,
최신 origin/develop이 여전히 이 HEAD와 일치함을 확인했다(0/0).
Checkout/worktree는 변경하지 않았다.
저장소 AGENTS.md는 발견되지 않았다. 사용자가 제공한 AGENTS.md 지침,
root CLAUDE.md router, 문서 규칙, Recording 계약, Runtime Plan §12가 적용된다.

[Issue #486 §8](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/486)과
[멘토 inline 및 후속 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/458#discussion_r4413533556)은
단일 VIDEO 제한을 지적한다. 실제 Recording/FFmpeg 핸들러 테스트는
제품 코드를 수정하기 전에 두 실패를 재현했다. 경계를 넘는 사건은
`len(videos) != 1`로 거부됐고, B 내부의 사건은 단일 resolution 경로로 들어가
로컬 기준선에서 multi-placement timeline을 해석하지 못했다. RED 세 건
(분리된 Case 선택값 누락 포함)은 제외된 scratch에 보존한다.

기존 입력과 공개 기능은 이미 필요한 사실을 표현한다.

| 경계 | 기존 권위 기준 / 새 어댑터 사용 |
| --- | --- |
| SourceAsset / MediaStream | 물리 파일 하나가 동시 VIDEO stream을 포함할 수 있다. role, filename, 첫 stream으로 추론하지 않는다. |
| Case source | Search가 이미 하는 것처럼 명시적 `video_stream_ref` 값을 분리된 tuple로 복사한다. |
| Fine AnalysisSource | 해당 VIDEO ref는 timeline의 모든 placement가 아닌 실제 분석한 pixel을 식별한다. |
| Recording `resolve_span` | 체인의 기존 복수형 인자로 revision의 모든 명시적 선택을 제공한다. 겹치는 span 선택과 source-local 좌표 계산은 Recording만 수행한다. |
| SpanResolution / IncidentClip | 반환된 모든 사용 stream이 build 전에 Fine VIDEO provenance에 있어야 한다. Recording은 clip provenance에 요청, revision, 순서가 있는 AssetSpan을 보존한다. |

Fine VIDEO ref와 Case 선택은 모두 비어 있지 않고 고유하며 호환돼야 한다.
선택한 모든 source의 소유권은 공개 Recording metadata와
`owns_asset`으로 확인한다. Case가 A→B를 선택해도 Fine은 B만 참조할 수 있다. Resolver 입력에는
여전히 A와 B를 모두 포함하며 결과의 사용 span에는 B만 포함한다. 필요한
Fine stream이 없을 때 다른 Case 선택으로 조용히 보충하지 않는다.
선택된 VIDEO가 하나면 단일 기능 경로를 유지한다. 동일한 물리 파일의 여러 camera
stream은 선택이 명시적이지 않으면 여전히 모호하며,
Recording의 기존 placement별 검증이 모호한 목록을 거부한다.

Runtime은 Recording 스키마/내부 저장소를 읽지 않으며 placement
필터링, span 생성, source-local 좌표 계산, 정렬 또는 camera 추측을 수행하지 않는다.
Recording 구현과 정식 계약은 그대로다. 길이 검사 삭제,
첫 VIDEO 선택, resolver 논리의 Runtime 복사와 같은 대안은
이 경계를 충족하지 못한다.

<a id="transaction-lifecycle-and-replay"></a>

## 트랜잭션, 수명주기 및 재실행

`IncidentClipInputs`는 기존의 짧은 caller 트랜잭션에서 Case/의존 produced 사실과
stream 선택을 로드한다. 분리된 값을 반환하며 Connection이나
lazy stream은 밖으로 나가지 않는다. 기존 프로덕션 구성은 입력 connection을
반환한 뒤 짧은 `TransactionalRecordingRepository` 콜백으로 지원되는
실행별 Recording service를 연다. Metadata, ownership, resolve 호출의
checkpoint를 유지한다. dispatch마다 build를 한 번 실행하며, 성공, 실패, 취소 시
context exit와 종료 후 checkpoint를 유지한다.

기존의 정확한 build 전용 오류 매핑은
`INCIDENT_CLIP_BUILD_FAILED` → `RECORDING_INCIDENT_CLIP_BUILD_FAILED`이며
produced는 없다. Binding/ownership/resolve/context/DB 오류는 Runtime 경계를 유지한다.
새 terminal taxonomy, Contract 의미, duration 허용오차 또는 encoding 정책은
선택하지 않는다. 성공은 계속 `{"incident_clip_ref": "..."}`만 반환하고
기존 실행별 receipt와 T1/T2 persistence를 사용한다.

테스트는 terminal 트랜잭션 rollback/COMMIT 결과 불명 receipt 복구와
T2 재전달을 T1 전 crash와 구분한다. 후자는 실제 build 뒤
record 경계에서 `SystemExit`를 주입하고, 해당 테스트 lease만 만료시킨 뒤
기존 sweeper/새 attempt를 사용한다. 주입 crash 테스트이며 clip
프로세스를 OS kill한 것이 아니다. 기존의 일반 Runtime OS kill 사례는 별도로 RUNNING
복구와 T1→T2 구간을 검증한다. 새 attempt는 rebuild할 수 있다. commit된 terminal receipt나
T2 재실행은 build 또는 encode를 다시 호출하면 안 된다. 두 Readout job은 여전히
변경하지 않은 Case T2를 통해 같은 clip ref를 받는다.

<a id="support-and-limits"></a>

## 지원과 한계

| 입력 / 조건 | 결과 |
| --- | --- |
| 선택한 VIDEO 하나 | 기존 경로 유지. |
| 명시적 순차 A→B 경계 교차 | 필요한 source span을 모두 순서대로 사용. timeline과 source-local 좌표 보존. |
| A→B의 B 내부 사건 | 전체 Case 선택을 resolve하며 clip은 B만 사용. |
| 한 파일의 동시 VIDEO stream 두 개 | 명시적 stream 선택은 성공하며 모호한 선택은 거부. front/rear role 추론 없음. |
| 선택/source 누락, 다른 소유자, 잘못된 timeline/revision, Fine provenance 불일치 | 안전하게 거부하며 성공 produced receipt 없음. |
| Gap, overlap, 손상/변경 media, 알 수 없는 coverage 또는 미지원 media | 기존 Recording 검사가 계속 권위 있는 기준. |
| 서로 다른 출력 time base | 기존 안전 거부 유지. 이 어댑터 수정은 #425 지원 구현을 제공하지 않음. |

[#425 Recording Owner 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6493673627)은
서로 다른 time base를 정확한 frame/coverage 검증을 전제로 지원 목표로 삼는다.
구현됐다는 주장은 아니다. 최초의 혼합 AVI/MP4 프로세스 fixture는
Search HTTP 전에 현재 `UNSUPPORTED_MEDIA` guard를 드러냈다. 실패 원본과
진단은 제외된 scratch에 유지한다. 성공 경로 fixture는
명시적으로 일치하는 1/10 source time base를 사용한다. 프로덕션 검증은 완화하지 않았다.
서로 다른 time base를 가진 별도의 실제 MP4 입력은 여전히 안전하게 실패한다.

제외 범위: #470 preview/payload, #486 §9 Case/Evidence 시간 offset, GPS, 새 camera
정책, 운영 제한/profile, provider/AWS/배포, workflow/inventory/
timeout 변경, 광범위한 형식 변경, 전체 pytest/필수 MySQL/Docker rebuild.
마무리 시 GitHub API로 `RT14_EXECUTION_ENABLED`를 읽었으며 계속
`false`였다. 변수를 변경하거나 RT14 작업을 호출하지 않았다.

<a id="verification-record"></a>

## 검증 기록

상세 명령 출력, JSON/JUnit, RED와 실패 원본은
`.codex-scratch/multisource-incident-20261031/` 아래에만 있으며 PR 후보가 아니다. 아래 수치는
별도 실행이며 고유 테스트 검증 수로 합산하면 안 된다.

| 직접 실행 | 증거 / 결과 |
| --- | --- |
| 제품 변경 전 제품 경계 RED | `red.txt`: 예상대로 3건 실패. |
| 최초 handler/input/composition GREEN | `green.txt`: 63건 통과. |
| 확장 Windows handler/input/media | `expanded2.txt`: 71건 통과. |
| Frame PTS/duration과 다른 timebase 거부 | `timebase.txt`: 14건 통과. |
| 추가 선택 / 실제 encode 중 취소 | `cancel2.txt`: 2건 통과; context 종료 및 temp 비어 있음. |
| Linux Python 3.12.16 / FFmpeg + ffprobe 8.1 | 기존 로컬 image `daesingo-issue452:local` (`f76274a9b66b`), 현재 source를 읽기 전용 mount, rebuild 없음. |
| Linux 집중 media/경계 suite | `linux-focused.txt/xml`: 463건 통과, 원래 opt-in skip 4건, quality-tool 환경 실패 3건. |
| Quality-tool 환경 실패 | 기존 runtime image에 Ruff/mypy가 없음. `test_real_quality_command_accepts_clean_and_rejects_violations` 변형 세 개 실패. test/strict/skip 규칙 변경 없음. |
| 잠긴 tool을 사용하는 Windows의 동일 quality 테스트 | `quality-test.txt`: 19건 통과. |
| Linux quality 환경 복구 / 대상 재실행 | 다운로드한 wheel 일곱 개의 SHA-256 값이 `uv.lock`과 일치. network를 비활성화하고 제외된 scratch에만 설치했으며 image rebuild 없음. `linux-quality.txt/xml`: 19건이 30.96s에 통과. 앞선 도구 누락 실패 세 건은 해결된 환경 실패임. |
| Runtime quality 명령 | `quality-final.txt`: Ruff 통과; mypy Linux/win32 대상 각각 87개 파일 통과. |
| 경계 / Contract | `boundaries.txt`, `contracts.txt`: 경계 위반 0건; 구조 62 / JSON 26 / 의미 검사 104건 통과. 최초 Windows 콘솔 encoding 오류는 UTF-8로 재실행. |
| 실제 MySQL / 별도 프로세스 | 최종 결과는 아래 마무리 기록에 기재. 앞선 실패는 보존하며 위에서 설명. |

opt-in skip 네 건은 local incident clip, local
span resolution, multi-source timeline, multi-span AnalysisSource의 실제 사용자 media/pair 테스트다. 원래
사용자 동영상이나 명시적 실제 placement는 제공되지 않았다. 합성 media와
실제 사용자 영상은 인수 증거로 서로 대체할 수 없다. 원격 CI와
전체 회귀는 향후 push/PR 조건으로 남으며, 이 작업은 push하지 않는다.

테스트 파일에 추가로 탐색 실행한 Ruff는 Runtime quality gate 밖의 fixture-import와
compact-statement 진단을 보고했다. 관련 없는
lint 정리는 적용하지 않았다. 새로 추가한 multisource 테스트 파일은 Ruff를 통과한다.

<a id="fresh-review"></a>

## 새로운 검토

별도의 읽기 전용 검토자에게 구현 이력 없이 요구사항과 checkout만
전달했다. 최초 finding: P0/P1/P2/P3 없음. 직접
handler/input 테스트 58개와 실제 FFmpeg multisource 테스트 13개를 실행했다. 최초 기본 temp에 쓸 수 없는
실행은 격리된 쓰기 가능 basetemp로 대체했다. MySQL/process 증거는 살폈지만
실행하지 않았다. 최종 delta 검토와 남은
한계는 마무리에 기록하며, PM Runtime 인수는 계속 유보 상태다.

<a id="changed-file-inventory"></a>

## 변경 파일 목록

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

<a id="draft-reply-to-pr-458-inline-not-posted"></a>

## PR #458 inline 답변 초안 (게시하지 않음)

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

<a id="closeout-evidence"></a>

## 마무리 증거

최종 Linux 실행(`linux-finalmysql.txt/xml/json`)은 **MySQL 8.4.13**에서
145.16초 동안 skip/xfail 없이 **테스트 17개**를 통과했다. single/chain T1/T2 fault
사례 열 개, 기존 취소/실패/새 job/불변
receipt 사례, chain의 T1 전 주입 crash/새 attempt, 별도 API와
Worker OS process의 single/chain 사례를 포함한다. 독립적인 정상 chain dispatch마다
build 한 번과 span 두 개 encode를 수행한다. rollback/receipt 복구/T2 재전달은
build/encode를 추가하지 않는다. T1 전에 중단된 attempt와 대체 attempt는 각각 build
한 번/encode 두 번(총 build 두 번/span encode 네 번)이며, 이후 T2는 추가하지 않는다.

별도 프로세스 테스트는 오프라인 transport를 통해 Coarse HTTP=1, Fine HTTP=1, clip HTTP=0과
서로 다른 parent/API/Worker PID를 assertion으로 확인한다. Build와 실제 span별 encode 시 Runtime pool checkout은
없다. 프로세스 peer는 decode/concat을 포함한
Recording media 명령 경계에서도 없는지 확인한다. T2는
두 Readout을 정확히 같은 clip ref로 영속 enqueue한다. Readout provider 실행 자체는
이 테스트 범위 밖이다.

앞선 `linux-mysql2`는 일반 Runtime **OS kill** 복구 사례 두 개와
다른 사례 아홉 개를 성공적으로 실행했다. Chain 실패 여섯 건은
Search 전 timebase 불일치 fixture였으며 실패 증거로 유지한다. 이후
`linux-probe`/`linux-probe2` 실패는 테스트 계측과
오프라인 playback 좌표 오류를 드러냈다. 이 실행들은 통과한 E2E로 세지 않는다.
최종 실행은 제품 검증을 변경하지 않고 해당 fixture를 수정한다.

새 delta 검토는 현재 오프라인 media 테스트 **16**개를 직접 실행했으며
P0/P1/P2/P3 문제를 찾지 못했다. 같은 검토자는 이후 최종 17개 MySQL 사례의 text,
XML, JSON(선택 사례 17개 / phase report 51개)을 살폈고 추가 finding은 없었다.
해당 suite는 실행하지 않았다. 취소 테스트는 진행 중인 FFmpeg subprocess 중단이 아니라
결국 도달하는 기존 checkpoint에서의 취소와 context/temp 정리를
입증한다. PM Runtime 인수는 여전히 미완료다.

남은 한계는 #425 구현, 실제 사용자 영상/실제
placement 인수, 기존 전체 span의 메모리 내 materialization, 원격
CI/전체 회귀다. 새 검토자 P1/P2/P3 중 미해결 항목은 없다. Staging,
commit, push, 외부 답변, PR, merge 또는 배포는 수행하지 않았다.

소유한 MySQL container와 익명 volume, network, 성공한 모든 생성
media/테스트 디렉터리, 임시 quality 의존성, 검토자 temp 디렉터리 두 개를
제거했다. Windows 정리가 Linux 생성 pytest symlink에서 안전하게 멈춘 뒤,
동일한 로컬 image 안에서 해당 symlink를 확인하고 제거했다.
작은 실패 원본 media 파일 다섯 개(총 31,302바이트), 로그, JSON/XML,
최소 runner/요약만 제외된 scratch에 남는다. 공유 image/cache와
다른 작업 데이터는 보존했다. 최종 목록: 변경/untracked 파일 12개,
branch/HEAD 그대로, 빈 index. 큰 성공 media 사본은 누적되지 않았다.
