# #470·#523 preview / Top-3 — Implementation Notes

## 기준선과 범위 (2026-11-02 KST)

담당: 정철원(Runtime/Recording). 현재 branch `codex/rt10b-preview-frames`,
HEAD `204b85eb461b4c751903101791928fd01b58825a`; 시작 시 tracked/untracked 변경과 index 없음.
전달받은 AGENTS.md 지침 적용. 저장소 AGENTS.md 파일은 없으며 CLAUDE.md와 해당 모듈/Runtime 문서 참조.
현재 브랜치에서만 작업하고 merge/cherry-pick/worktree/staging/commit/push/게시/배포하지 않는다.

직접 읽은 원본:

- [#470](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/470), 전체 timeline 8건 및 patch:
  OPEN, 미병합, head `1a49687430e889baec4a27d13390a25e1c827382`.
  `case.preview_frame.preview_frame_position(clip, span, representative_ms)`와 preview 소비는 PR에만 있다.
- [#523](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/523), 본문과 전체 댓글 5건:
  [A안·payload·안전 경계 합의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/523#issuecomment-6559417301).
- [#525 Web Owner 리뷰](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/525#pullrequestreview-5728965227):
  아무 running job을 preview 준비 중으로 해석하지 않는다.
- [Case 결정](../modules/case/decisions/evidence-preview-frame.md),
  [Recording frame capability](../modules/recording/local-frame-access.md),
  [기존 clip 경계](rt10b-incident-clip-handler.md),
  [다중 source 구현](multisource-incident-clip.md), Runtime Tech Spec §12와 실제 코드.

원격 compare 확인: develop은 현재 로컬 HEAD보다 3 commits 앞서며 변경 파일은 Readout 결정 문서 2개뿐이다.
#470 head와 최신 develop은 ahead 5 / behind 16, merge base `d8bb0d9f1fbfa40fb2c4ef06ff65076772b7bc90`.
PR 변경 6파일을 읽었으며 로컬로 합치지 않았다. PR 본문의 옛 T2 issuer 설명은 최신 patch와 다르다.

## 실행 계획 / 진행 기록

합의한 A안을 실행한다. Case 소유 계약·helper를 대신 구현하거나 공개 계약을 변경하지 않는다.
사용자 요청대로 이 문서에 계획/구현 기록을 두고 공통 Log는 원본 링크만 추가한다.

1. 입력 RED→GREEN: 고정 후보/대표 시각 detach, Case `is_current`를 통한 frame 자격 판단,
   Case가 선택해 준 Top-3 ID의 원래 generation/run/timeline/revision/rank 검증.
   clip의 기존 고정 입력과 실패/후속 정책은 유지한다.
2. handler RED→GREEN: Case 위치 함수 주입 경계. 선택 후보 preview는 clip provenance,
   각 thumbnail은 자기 후보 범위의 공개 resolve_span 결과를 해석한다.
   동일 STREAM_POSITION은 성공/null 모두 재사용. 허용 거부만 null; 취소/DB/checkpoint/저장 오류 전파.
3. reader RED→GREEN: common opaque 저장소는 유지하고 Worker 소비 경계에 strict payload 검증을 둔다.
   이전 missing/null은 preview null / 후보 map 없음으로 읽으며 receipt 원문을 고치지 않는다.
4. focused 회귀, 실제 MySQL T1/T2/replay 및 가능한 process/API 소유권 확인, quality/boundary/fixture/diff.
   전체 pytest/전체 mandatory MySQL은 로컬 일괄 실행하지 않는다.
5. 구현 이력을 받지 않은 fresh read-only reviewer, 수정 시 같은 reviewer 재확인.

Review focus: 오래된 세대/선택 변경, clip 밖 후보 provenance, 중복 위치/null 캐시,
저장 오류 오분류, receipt replay에서 미디어 재호출.

## 미해결 Owner 연결 (production 활성화 전 필수)

현재 Case helper가 없으므로 production 발급은 활성화하지 않는다. 아래는 Runtime 주입 접점 제안이며
Owner가 수락한 새 공개 Case API라는 뜻이 아니다. 테스트용 위치 함수/selector를 production에 연결하지 않는다.

- #470 helper의 공개 노출 경로와 병합된 코드가 필요하다.
- Case가 현재 generation의 Top-3 candidate ID를 선택하는 읽기 전용 함수가 필요하다.
  제안 입력은 `(case, fixed_observation_input, candidate_events)`, 결과는 후보 ID sequence.
- 각 후보의 SpanResolution JSON과 CandidateSpan/representative_ms에서 유일한 원본 위치를 반환하는
  Case helper가 필요하다. 후보 전체 범위(start < end), 명시적 VIDEO 선택으로 resolve_span한다.
- Case T2가 `candidate_frame_refs`를 현재 세대에만 저장·투영하고 missing/null을 받는 경로가 필요하다.
  현재 develop은 clip ref만 소비하며 #470도 Top-3 소비는 포함하지 않는다.
- Case/Web에 확인받을 준비 중 조건 제안: 현재 세대의 실제 발급 자격이 있는 clip job을 Case가 아직 기다리는 동안
  (T1 terminal 후 T2 반영 대기도 포함)만 준비 중이다. Fine/readout/export 등 다른 job은 근거가 아니다.
  미연결·취소·세대 변경·반영 완료 null은 준비 중으로 표시할 근거가 없다.
  `running_jobs.kind`만으로 세대/발급 자격을 구분할 수 있는지는 Case/Web 확인이 필요하다.
  화면 문구나 CaseView 계약은 이 작업에서 바꾸지 않는다. Owner에게 메시지를 게시하지 않았다.

## 구현된 독립 slice

`IncidentClipInputs`는 고정 선택 후보와 대표 시각, generation ID를 detach한다.
Case의 `is_current`/대기 상태와 후보 stale/span/revision을 확인하며, 주입된 Case selector가 준
ID를 원래 generation의 run/rank/timeline/revision 및 현재 Case projection과 대조한다.
Runtime이 Top-3를 새로 고르지 않는다. selector 미연결은 빈 tuple이다.

`IncidentFrameIssuer(preview_position=..., candidate_position=...)`는 handler 전용 실행 경계다.
preview helper의 인자는 #470과 같은 `(IncidentClip JSON, CandidateSpan JSON, representative_ms)`이며,
thumbnail helper의 제안 인자는 `(SpanResolution JSON, CandidateSpan JSON, representative_ms)`다.
두 함수는 `(media_stream_ref, source_offset_sec)` 또는 None을 돌려준다.
`IncidentClipInputs(..., thumbnail_candidates=...)`의 selector 결과는 후보 ID sequence다.
이 생성자/keyword는 Runtime seam이고, Case의 새 공개 API 이름/수락을 뜻하지 않는다.

후보마다 자기 범위와 명시적 Case VIDEO 목록으로 `resolve_span`한다. 다른 후보를 선택 clip의
provenance에 맞추지 않는다. 발급 전 전체 VIDEO 선택의 Case 소유권을 확인하고 같은 위치의
성공/null을 한 실행 내 재사용한다. `resolve_frame`의 `FRAME_NOT_FOUND`, `STREAM_UNAVAILABLE`,
`OUT_OF_RANGE`, `TEMPORARY_FAILURE`만 optional null이다. `UNKNOWN_REF`/미등록 code 및
metadata/resolve_span/helper/checkpoint/context/DB/transaction/persistence 오류는 이 catch 밖이다.
decode와 Recording metadata 저장은 TransactionalRecordingRepository의 짧은 개별 transaction으로 분리된다.

`incident_clip_registry(..., frames=...)`는 clip 생성 후 발급 결과를 payload에 합쳐 strict 검증한다.
실제 production `compose_incident_clip_registry`는 이 keyword나 selector를 주입하지 않으므로
아직 기존 clip-only payload를 낸다. 미병합 helper를 동적으로 import하거나 테스트 대역으로 대체하지 않는다.

Worker T2/stored adapter/Readout 입력의 ProducedReader에 소비 스키마를 연결했다.
common opaque produced 저장소와 receipt는 그대로다. preview string/null, 후보별 string/null map(최대 3개)을
검증한다. legacy missing/null은 preview None / 후보 map {}로 **읽기 결과만** 정규화한다.
이는 Case의 ref 저장/투영 구현과 별개이며 현재 Case는 여전히 clip ref만 소비한다.

## 직접 검증과 보존 증거

원본은 ignored `.codex-scratch/preview-frames-20261102/`에 둔다. 테스트 media/DB/환경 파일은 전달 대상이 아니다.
`github-snapshot.json`에 직접 조회한 PR/Issue/댓글/patch를 보존했다. 숫자는 조회 시점 snapshot이다.

| 검사 | 직접 관측한 결과 / 원본 |
| --- | --- |
| 기존 입력/handler 기준선 | 58 passed, `baseline.txt/xml` |
| 핵심 RED | `red-corrected.txt/xml`(새 모듈/필드 누락), `red-wiring.txt/xml`(handler/reader 미배선), `red-eligibility.txt/xml`(stale/대기 종료), `red-thumbnail-binding.txt/xml`(Case 소속/span) |
| focused GREEN | `focused-final.txt/xml`: 230 passed. 앞선 `focused-binding.txt/xml`은 229 passed |
| media/API focused 회귀 | `media-verified.txt/xml`: 71 passed, 외부 원본 opt-in 1 skipped, 47.28 s |
| 실제 MySQL frame 경계 | `mysql-green.txt/json/xml`: 6 passed, MySQL 8.4.13; T1 rollback, T2 rollback/redelivery, frame 저장 오류/취소 |
| 추가 MySQL/process 경계 | `mysql-process.txt/json/xml`: 3 passed, 6 deselected; 실제 T1 COMMIT OK 유실, 별도 Worker/API OS process, pre-T1 crash 새 attempt |
| 보강 후 최종 focused MySQL | `mysql-final.txt/json/xml`: 새 frame 9 + 기존 clip 7 = 16 passed, 8 deselected, 145.01 s. 선택 16개 및 setup/call/teardown 48개 모두 passed; collection error/skip/xfail 없음. JUnit과 대조 |
| quality | `quality-final.txt`: Ruff와 Linux/win32 mypy(89 source files) 모두 PASS |
| boundary / Contract fixture | `boundary.txt` PASS; `contracts.txt` 문서 62 / JSON 26 / 의미 104 검사 모두 PASS |

위 테스트들은 중복되므로 합산한 전체 suite 숫자로 쓰지 않는다. 초기 테스트 fixture의 frozen model 수정 오류,
Case INTAKE에서 receive한 설정 오류, 잘못된 `RESOLVED` status 대역은 테스트 코드에서 수정했다.
그 출력은 `red.txt`, `green.txt`, `mysql.txt`에 보존하며 제품 경계 RED/PASS로 세지 않는다.
`red-corrected`에서 입력 테스트 5건도 Case fixture 설정 오류였으므로 그 부분은 기능 RED 근거가 아니다.
입력의 실제 기능 RED는 `red-eligibility`와 `red-thumbnail-binding`으로 따로 확인했다.
처음 media 회귀는 sandbox 기본 temp 번호 디렉터리 생성 실패로 setup error였으며
`media-regression.txt/xml`로 보존한다. sandbox 전용 basetemp 재실행도 일부 진행 후 대기해
명령행으로 식별한 이 작업의 테스트 PID만 정리했다. 미완료 출력 `media-green.txt`는 PASS로 세지 않는다.
동일 focused 목록을 전용 basetemp와 진단 timeout으로 sandbox 밖 로컬에서 실행한
`media-verified.txt/xml`이 위 완료 결과다. test/product 소스 변경이나 skip 정책 완화는 하지 않았다.
boundary 첫 호출의 cp949 출력 오류는 UTF-8 재실행으로 확인했으며 source를 바꾸지 않았다.

별도 process 검증은 실제 MySQL/FFmpeg/공개 Worker·API·T1/T2를 사용한다.
Case selector/위치 함수는 `tests/worker/incident_frame_support.py`의 TEST ONLY 대역이다.
provider는 기존 offline transport이며 외부 호출이 없다. API child는 ASGI TestClient이며 TCP listener 검증이 아니다.
Worker child에서 실제 decode 1회, 입력 pool checkout 0, 재전달 추가 decode 0을 확인한다.
API child에서 durable PNG 200, 다른 Case와 exact ID 위반(뒤 공백) 404 및 원본 저장 bytes의 SHA-256 일치를 확인한다.
API/View에서 extractor 호출은 금지 assertion으로 차단했다. 실제 CaseView thumb가 여전히 null인 것도 확인한다.
이는 frame 발급 실행 경계와 HTTP 소유권 검증이며 **실제 Case helper/Top-3 소비/화면 통합 성공이 아니다**.

pre-T1 crash test는 첫 attempt decode 후 durable receipt가 없음을 확인하고 새 attempt의 두 번째 decode를 관측한다.
저장된 T1 receipt의 replay/T2/redelivery는 재디코딩하지 않는다. pre-T1 crash의 재디코딩 0회는 보장하지 않는다.

## Fresh read-only review

구현 이력을 전달하지 않은 reviewer가 현재 diff와 untracked 파일, 관련 계약 및 테스트 구현을 읽었다.
테스트/DB 실행이나 파일/index/branch 변경은 하지 않았다. 독립 Runtime slice에서 actionable P1/P2/P3 finding 없음.
production 미연결 및 Case 소비 부재는 통합 미해결로 별도 확인했다. ASGI TestClient/TCP 구분 제안을 이 문서에 반영했다.
같은 reviewer가 최종 15파일·추가 3후보 회귀·Notes/Log 및 최종 증거를 재확인했으며
남은 actionable P1/P2/P3 finding 없음으로 회신했다. 독립 테스트/DB 재실행은 하지 않았다.
이 검토는 Owner API 수락/merge 승인/배포 승인이 아니다.

## NOT_RUN / 남은 통합

실제 Case helper와 Top-3 selector/소비/CaseView 투영, #525 화면 및 준비 중 판정의 Case·Web 확인,
실제 Top-3 이미지 표시 E2E는 미완료다. Owner에게 외부 메시지를 게시하지 않았다.
전체 pytest, 전체 mandatory MySQL, 이 미게시 변경의 원격 CI, 실제 provider, 사용자 영상,
TCP API listener, AWS/EC2/배포는 NOT_RUN이다. Incident 화질/Analysis 한도/workflow/서비스 설정을 바꾸지 않았다.

## 전체 변경 파일

- `docs/runtime/rt10b-preview-frames.md`
- `docs/runtime/runtime-implementation-log.md` (후속 entry 추가만)
- `src/daesingo/worker/case_composition.py`
- `src/daesingo/worker/incident_clip_handlers.py`
- `src/daesingo/worker/incident_clip_inputs.py`
- `src/daesingo/worker/incident_frames.py`
- `src/daesingo/worker/produced_reader.py`
- `src/daesingo/worker/readout_inputs.py`
- `tests/worker/frame_process_support.py`
- `tests/worker/incident_frame_support.py`
- `tests/worker/test_incident_clip_composition.py`
- `tests/worker/test_incident_clip_handlers.py`
- `tests/worker/test_incident_clip_inputs.py`
- `tests/worker/test_incident_frames.py`
- `tests/worker/test_incident_frames_mysql.py`

scratch/RAW/JSON/JUnit/생성 media/환경 파일은 ignored이며 변경 파일 전달 목록에서 제외한다.
새 worktree는 없고 branch/HEAD/index를 유지한다.

## 자원 정리와 보존

일회용 MySQL 컨테이너 `codex-preview-frames-20261102`는 생성한 ID와 task label을 대조한 뒤
확인한 익명 volume 하나와 함께 제거했다. 마지막 조회의 스키마는 시스템 스키마와 작업의 빈 test base뿐이며,
조회자 외 client/transaction과 data lock은 모두 0이었다(`resource-before-cleanup.json`).
제거 뒤 task label container 목록과 해당 volume 목록은 비어 있음을 확인했다. 공유 Docker/WSL이나 기존 서비스는 중지하지 않았다.
spawned API/Worker child의 종료와 exit code 0은 테스트가 확인했다. 대기하던 sandbox 테스트 process는
자신의 command line/임시 경로/PID를 검증해 정리했고, 완료된 실행으로 세지 않았다.

이번 scratch root 아래임과 reparse point가 없음을 검증한 `*-temp` 디렉터리 여섯 개를 제거했다.
생성 source/clip/frame 관련 임시 media와 test 환경 파일, 일회용 mysql.env를 지웠으며
scratch에 디렉터리나 .env가 남지 않았음을 확인했다. 기존 scratch/사용자 파일은 건드리지 않았다.
GitHub snapshot, RED/GREEN text·JUnit·MySQL JSON, quality/boundary/Contract와 baseline git 기록은 그대로 보존한다.
기존 공통 Log 본문의 byte prefix가 보존됐음을 HEAD와 비교했다. 최종 diff 공백 검사 통과,
HEAD/branch 동일 및 index 비어 있음을 확인했다.

## 실제 Case 통합 후속 — 실행 계획 (2026-11-02 KST)

사용자 요청을 이 후속의 spec으로 삼는다. 기존 기록은 당시 상태로 보존한다.
시작 branch `codex/rt10b-preview-frames`, HEAD `a561f47583a2f5de5ab4f7f066c28c888a35583a`,
working tree/index는 비어 있었다. 최신 develop은 `ea2bc5e3d6be67b308b25073c7d36c29510bd135`.
#470은 병합됐고 #532는 Draft/미병합, 고정 HEAD `1ee6d66fb8f3097544c84c6bab5dee478670846c`.

**설계:** Case 공개 `thumbnail_candidate_ids(case, observation_input, events)`를 입력에,
`preview_frame_position(clip, span, representative_ms)`와
`candidate_frame_position(resolution, span, representative_ms)`를 issuer에 직접 주입한다.
Case 정책 복제나 optional import fallback은 두지 않는다. T1 전 발급/T2 ref 소비 경계를 유지한다.

**실행:** `executing-plans`로 이 세 작업을 직접 수행하고 마지막에 fresh read-only reviewer를 사용한다.
미커밋/미스테이징 종료, 다른 Owner 구현/브랜치/정책 변경 금지, 전체 suite 반복 금지를 우선한다.

- [x] Task 1: production composition 연결. `test_incident_clip_composition.py`에 실제 Case selector/위치 함수의
  주입 및 동작 회귀를 먼저 작성하고 임시 통합 사본에서 RED 확인 → 최소 production 배선 → GREEN.
- [x] Task 2: `test_incident_frames_mysql.py`와 `frame_process_support.py`를 production registry로 전환하고
  T1/T2/CaseView/HTTP assertion을 실제 소비에 맞춰 강화한다. 후보 0~3, stale/세대 변경,
  후보별 자기 resolution, 동일 위치 재사용, rollback/receipt/redelivery, pool checkout 0,
  clip 성공/두 Readout, legacy missing/null을 focused 검증한다.
- [x] Task 3: Web #525의 준비 중 조건과 Case running_jobs를 대조하고, focused quality/boundary/contract,
  fresh reviewer 지적 보완, 기록 append, 작업 소유 자원 정리, branch/HEAD/index 및 전체 diff 재확인.

**통합 사본:** ignored `.codex-scratch/case-frame-integration-20261102/tree`에 Git archive로 최신 develop을
추출하고 #532 diff 및 #527 단독 diff를 적용했다. Git branch/index를 만들거나 변경하지 않았다.
Runtime Log append 위치 충돌만 있었으며 임시 사본에서 develop 본문 뒤에 #527 추가분을 붙여 양쪽 이력을 보존했다.
최종 #527 단독 diff의 실행에는 #532 선행 병합과 develop 동기화가 필요하다.

**Review focus:** stale/세대 변경 중 T1→T2, rank 4 대체 금지, 자기 후보 resolution,
durable receipt 이후 추가 decode 금지, 허용 거부와 persistence 오류 분리, Web 대기 판정의 한계.

### 통합 구현 결과와 선행 조건

`worker/incident_clip_composition.py`가 위 세 Case 함수를 직접 import하여 production 입력/issuer에 연결한다.
기존 encoding/context가 없을 때 kind 미등록 정책은 유지한다. `incident_frames.py`는 활성화 설명만 갱신했다.
Case/Recording 구현, T1/T2 transaction, schema, workflow/inventory/timeout/skip, Incident 화질/Analysis 한도는 변경하지 않았다.
미사용 테스트 대역 `tests/worker/incident_frame_support.py`는 삭제했다. Case 정책을 Runtime에 복제하지 않았다.

이번 실행 기준은 **develop + 고정 #532 + #527 + 미커밋 변경**인 임시 사본이다.
원본 branch/HEAD에는 develop/#532를 병합하지 않았으므로, **원본 단독 checkout에는 새 Case API가 없어
현재 미커밋 production import를 실행할 수 없다.** optional import/fallback으로 숨기지 않은 선행 의존성이다.

| 조건 | 현재 상태 |
| --- | --- |
| #470 | 병합됨; develop에 preview 위치 함수/소비 포함 |
| #532 | Draft/미병합, `1ee6d66f` 고정 검증. develop 기준 #527 실행·CI에는 선행 병합 필요 |
| develop 동기화 | 원본 미수행. #527 mergeability 조회 결과 false. 임시 patch 적용에서는 Runtime Log append 충돌만 있었고 양쪽 이력을 보존 |
| #525 | OPEN, `f8906816`. 실제 Web 이미지 표시에는 별도 반영 필요; Runtime 검증에는 불필요 |
| 최종 전체 회귀 | 사용자가 선행 반영·commit/push한 뒤 원격 quality/regression/mysql/test/check로 검증할 조건. 이번에는 push/dispatch하지 않음 |

본문·전체 댓글·HEAD·check snapshot은 scratch의 `github-snapshot.json`, develop CI는 `develop-ci.json`에 보존했다.
develop `ea2bc5e3`, #470 `1a496874`, #527 `a561f475`, #532 `1ee6d66f`, #525 `f8906816`의
quality/regression/mysql/test/check는 직접 조회에서 모두 SUCCESS였다(#525 notify는 SKIPPED).
이는 미게시 통합 변경의 CI 결과가 아니다. #523 및 #532의 Runtime 답변도 원문 대조했다.

### 실제 검증·실패 기록

증거 root: `.codex-scratch/case-frame-integration-20261102/`. 아래 실행에는 중복이 있어 단순 합산하지 않는다.

| 실행 | 직접 관측한 결과 |
| --- | --- |
| `red-composition.txt` → `green-composition.txt` | `frames` 미주입으로 1 failed/4 passed → 실제 Case 배선 후 5 passed |
| `focused.txt/xml` | 입력/handler/composition/issuer + 실제 Case preview/Top-3: 155 passed |
| `mysql-local.txt/json/xml` | 실제 production Case/Recording, MySQL 8.4.13: 9 passed; setup/call/teardown 27개 모두 passed |
| `integrated.txt/json/xml` | 23개 중 17 passed/6 failed. single/chain clip T1 10종, 동일 clip의 두 receipt, 직접 T2 receipt replay 4종은 통과. Top-3 테스트 가정 실패는 아래 별도 재검증 |
| `legacy-process.txt/json/xml` | 별도 API/Worker process clip/fractional/chain 3종 + historical missing/null 실제 T1/T2 2종: 5 passed, 단계 15개 모두 passed |
| `top3-success.txt/json/xml` | 최종 후보 0/1/2/3, stale 2위, span 없는 2위, 실행 전 세대 변경, T1 후/T2 전 세대 변경: 8 passed, 단계 24개 모두 passed |
| `media.txt/xml` | clip multisource/Readout 입력/API frame/Recording frame: 91 passed, 사용자 영상 기존 opt-in 1 skipped |
| `quality.txt` | required Runtime Ruff + Linux/win32 mypy 각각 89 files PASS |
| `boundary.txt`, `contracts.txt` | 경계 PASS; fixture 구조 62/JSON 26/의미 104 PASS |

성공한 MySQL 실행은 collection error/skip/xfail이 없다. 마지막 시나리오별 유효 결과를 집계한 별도 요약도 보존한다.
실제 후보는 offline provider 응답에서 Search/Case가 만들며 Case selector/위치 함수는 대역이 아니다.
0개는 clip 발주/decode 없음, 1~3개는 모든 ref가 nonempty string이다. 무효 2위는 제외하고 4위로 채우지 않는다.
각 후보의 public resolve_span 요청/응답과 Case가 반환한 source-local 위치를 정확 비교한다.
다른 후보 대표 시각은 선택 clip 밖이다. preview/1위는 같은 ref이며 resolve/decode 수는 고유 후보 수와 같다.

T1 produced → 실제 Case T2 outcome → 새 transaction에서 복원한 CaseView thumb/현재 preview를 대조했다.
T1 후 세대 변경에서는 저장된 frame이 현재 View/후속 Readout에 섞이지 않는다. 정상 clip 성공은 같은 clip ref의
두 Readout 발주를 유지한다. 각 frame HTTP의 PNG bytes/content-type/signature를 저장값과 정확 비교하고,
다른 Case 및 뒤 공백 Case ID의 404를 검증했다. HTTP/View에서 extractor 호출을 금지했다.
T1 rollback/실제 COMMIT ACK 유실/T2 rollback/redelivery/직접 reflect_terminal receipt replay에 추가 decode가 없다.
decode/frame resolve/clip build에서 Runtime pool checkout 0을 확인했다. DB 저장 오류는 runtime FAILED,
취소는 CANCELLED이며 null 성공 receipt가 없다. T1 이전 crash 후 새 attempt의 두 번째 decode는 실제 관측했다.
historical fixture는 저장 전 옛 payload 형태로 직렬화했으며 durable receipt는 수정하지 않는다.
reader 정규화와 Case의 null/빈 map 소비를 확인하고 T2에서 누락 frame 재생성을 금지했다.

별도 Worker/API OS process 테스트도 production composition/MySQL/FFmpeg를 사용한다.
실제 public Readout 두 개는 offline OCR provider로 실행하여 CaseView `evidence.preview_ref`/`thumb_ref`까지 확인했다.
API child HTTP는 **ASGI TestClient**다. 실제 browser 화면·TCP listener·사용자 영상·live provider·AWS/배포는 NOT_RUN이다.

실패/진단 이력도 보존한다.

- archive 내 첫 git apply가 상위 저장소 탐색으로 파일을 무시했다. GIT_CEILING_DIRECTORIES로 탐색을 막고
  재적용한 뒤 실제 helper 존재와 최종 Runtime/test 파일 동일성을 확인했다. 잘못된 초기 Docker 설치 경로도 정정했다.
- sandbox localhost 제한의 MySQL preflight 실패(`mysql.txt`)는 전용 localhost 컨테이너의 로컬 실행으로 재검증했다.
- `top3.txt`(6 failed/2 passed), `integrated.txt`(6 failed/17 passed): 테스트가 source offset을 timeline 시각과
  같다고 정확 비교하고 build 내부 TimeRange 재조회까지 세었다. 실제 후보별 공개 resolution/Case 반환값의
  정확 비교로 수정했다. 허용오차나 production 위치 정책은 추가하지 않았다.
- `top3-final.txt`(3 failed/5 passed): 성공 fixture가 10fps exact PTS 부근을 요청하여 일부 ref가 null이었다.
  `pts-diagnostic.txt`에서 같은 원본으로 `0.6 → OK(0.6)`, `0.6000000000000001 → TEMPORARY_FAILURE`,
  `0.55 → OK(0.6)`를 실제 Recording 공개 호출로 재현했다. 이 기존 명시적 거부 경계는 변경하지 않았다.
  최종 성공 fixture는 PTS 사이 시각이며 모든 ref가 문자열인지 추가 검증한다. exact PTS 근처의 기존 동작은 남는다.
- 추가 test 파일 전체 Ruff 탐색은 기존 compact statement/pytest fixture import 관행 등 77 diagnostics로 실패했다.
  HEAD 동일 파일 66개와 비교한 `test-lint-comparison.json`을 보존했다. 새 compact statement 일부를 정리했지만
  이 탐색의 전체 PASS는 주장하지 않는다. required Runtime quality는 별도 PASS이며 ignore/정책을 바꾸지 않았다.

### Web 준비 중 판정 대조와 reviewer

#525는 thumb_ref, 선택 후보의 fallback evidence.preview_ref를 frameSrc로 그린다.
`CandidatesScreen`의 `pending = view.running_jobs.length > 0`을 CandidateCard 문구에 사용한다.
Case derive_running_jobs는 정산 전 job을 포함하여 T1 terminal/T2 대기도 보이지만 job별 candidate/generation/발급 자격은 없다.

| 실제 상태 | 현재 #525 판정의 한계 |
| --- | --- |
| 현재 세대의 자격 있는 clip 대기, T1 후 T2 대기 | frame 추가 가능 구간이지만 전체 job 유무로 자격까지 식별 불가 |
| clip T2 완료 + frame null + Readout만 진행 | 추가 thumbnail 작업 없이 준비 중 표시 가능 |
| Fine/export/다른 작업만 진행 | 그 작업 자체는 frame producer가 아니어도 pending=true 가능 |
| stale/세대 변경/대기 중단 | 현재 발급 자격과 결속된 표현을 일반 job 목록만으로 확정할 수 없음 |

Runtime은 Web 문구/정책이나 CaseView 계약을 대신 변경하지 않았다. Owner 후속과 실제 화면 확인이 남는다.
fresh read-only reviewer는 기존 MySQL/process 회귀 두 곳의 clip-only 필드 assertion을 P2로 지적했다.
같은 clip/receipt equality·Readout 연결 검증을 유지하고 새 3필드/frame/CaseView 검증을 추가하여 보완했다.
같은 reviewer가 최종 source/test diff(위 위치 비교·성공 fixture 수정 포함)를 재검토했고 추가 actionable P1/P2/P3는 없었다.
reviewer는 테스트/DB/네트워크를 독립 실행하지 않았다. 선행 PR 승인/병합 승인이 아니다.

### 이번 후속의 전체 변경 파일

- `docs/runtime/rt10b-preview-frames.md`
- `docs/runtime/runtime-implementation-log.md` (append only)
- `src/daesingo/worker/incident_clip_composition.py`
- `src/daesingo/worker/incident_frames.py` (설명만)
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_production_search_process_mysql.py`
- `tests/worker/frame_process_support.py`
- `tests/worker/incident_frame_support.py` (미사용 대역 삭제)
- `tests/worker/test_incident_clip_composition.py`
- `tests/worker/test_incident_clip_mysql.py`
- `tests/worker/test_incident_frames_mysql.py`

### 종료·자원 정리

`mysql-latest-summary.json`은 위 네 MySQL 실행에서 node별 마지막 결과를 골라 중복을 제거한 **33개 시나리오**다.
각 시나리오의 마지막 setup/call/teardown은 모두 passed이며 단일 33개 일괄 실행이라는 뜻은 아니다.
최종 Runtime/test 파일과 검증 사본의 byte 동일성은 삭제 전 `verified-files.json`으로 확인했다.
원격 고정 SHA, #532/#527 patch와 최종 미커밋 patch, RED/GREEN/실패 출력·JUnit/MySQL JSON은 보존한다.

작업 컨테이너 ID `91ea215d02b18701b69a5508ac2e579fcaaf2341352c3f6ccecde04d203bf71e`와 task label을
재확인했다. 정리 전 시스템 스키마와 작업 base 외 schema 없음, 다른 client/transaction/data lock 각각 0이었다
(`resource-before-cleanup.json`). 컨테이너와 그 익명 volume만 제거했고 재조회 목록은 비어 있었다.
이 작업 command line의 python/ffmpeg 잔존 process도 없었다. Docker Desktop/cache·기존 서비스는 보존했다.
scratch 절대경로 내부/reparse point 없음을 검사한 검증 사본과 임시 media 디렉터리를 제거했다.
작업 scratch에 디렉터리·env 파일이 남지 않았으며 원본/다른 작업 자료는 삭제하지 않았다.

기존 Log의 정규화한 byte prefix 보존을 HEAD와 대조했다. 최종 branch/HEAD는 시작과 같고 index는 비어 있다.
미커밋·미스테이징으로 종료한다. diff 공백 검사 PASS. 원본 단독 실행/최종 develop 기준 전체 회귀는 앞선 선행 조건을 유지한다.

### 기존 #527을 포함한 누적 전체 diff (18파일)

develop과의 merge-base 기준 파일 목록이다. develop/#532의 Owner 변경을 포함하지 않는다.

- `docs/runtime/rt10b-preview-frames.md`
- `docs/runtime/runtime-implementation-log.md`
- `src/daesingo/worker/case_composition.py`
- `src/daesingo/worker/incident_clip_composition.py`
- `src/daesingo/worker/incident_clip_handlers.py`
- `src/daesingo/worker/incident_clip_inputs.py`
- `src/daesingo/worker/incident_frames.py`
- `src/daesingo/worker/produced_reader.py`
- `src/daesingo/worker/readout_inputs.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_production_search_process_mysql.py`
- `tests/worker/frame_process_support.py`
- `tests/worker/test_incident_clip_composition.py`
- `tests/worker/test_incident_clip_handlers.py`
- `tests/worker/test_incident_clip_inputs.py`
- `tests/worker/test_incident_clip_mysql.py`
- `tests/worker/test_incident_frames.py`
- `tests/worker/test_incident_frames_mysql.py`


<a id="rt527-develop-integration-20261103"></a>

## 실제 브랜치 develop 통합·재검증 (2026-11-03 KST)

정철원(Runtime 구현·Recording). 이 절은 앞선 독립 배선과 임시 통합 사본의 기록을 대체하지 않는다.
이번 실행은 **현재 저장소의 실제 `codex/rt10b-preview-frames` 브랜치**에서 수행했다.
사용자 AGENTS 사실 기반 지침, 실제 저장소의 CLAUDE 라우터·docs 규칙과 관련 Runtime/Case/Recording 문서를 확인했다.
저장소가 추적하는 AGENTS.md는 없었다. 과거 임시 사본의 PASS를 이번 브랜치 PASS에 합산하지 않았다.

### 시작·종료와 승인된 merge

| 항목 | 직접 확인한 값 |
| --- | --- |
| 시작 HEAD | `f379276fc88a1e60b8c49d86cc06ae1bb98e7ad1` |
| 시작 working tree / staging | tracked·untracked 변경 없음 / 비어 있음 |
| 원격 develop | `git ls-remote` 조회·fetch로 `ba8e21ea57a400db1820594f5b50303bbf7df454` 확인. 종료 전 재조회도 동일 |
| 통합 merge / 종료 HEAD | `d0b5b6e947760fe151376c357eefff46a515df2c` |
| merge 부모 | 첫 부모 `f379276f`, 두 번째 부모 `ba8e21ea` |
| 보존 커밋 | `f379276f`가 HEAD의 조상임을 직접 검사. 재작성·reset·force push 없음 |
| 이번 새 수정 | 아래 process 테스트 1개와 Notes·Log 두 문서만 미커밋·미스테이징 |

`git merge --no-ff --no-commit origin/develop` 후 충돌을 검토하고 **이번 develop 통합 merge만** 커밋했다.
충돌 해결에 필요한 Log staging만 했으며 새 테스트 수정·기록은 그 이후에 작성해 index에 넣지 않았다.
다른 기존 변경이 없었으므로 별도 분리할 작업 트리는 없었다. baseline 대조에는 ignored archive 사본을 사용했고 새 worktree는 만들지 않았다.

### 원격 선행 상태·CI 구분

- [#527](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/527): OPEN/Draft, 원격 HEAD
  `a561f47583a2f5de5ab4f7f066c28c888a35583a`. 원격에는 실제 Case 연결 커밋이나 이번 merge가 없다.
  댓글 조회는 0건이었다. 기존 [python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/41329933290)·
  [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/41329933252)의 SUCCESS를 다시 조회했다.
  **이 CI는 옛 원격 HEAD의 결과이고 이번 로컬 통합 결과가 아니다.**
- [#532](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/532): MERGED,
  merge `ede73c59abd52d49096bf6b009272e98d5581a9f`, 검토 HEAD `1ee6d66fb8f3097544c84c6bab5dee478670846c`.
  [Case 인수 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/532#issuecomment-6594486300)의 추가 차단 없음과
  develop 반영→실제 브랜치 focused 검증→push→원격 CI 순서를 원문 확인했다.
  유소연 Owner 복귀 후 정책 검토는 후속으로 유지하며 이번 통합의 새 차단 조건으로 만들지 않는다.
- [#525](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/525): MERGED,
  merge `faf58080f42d81348d09f74d95abb32d547b9886`, HEAD `6fad3e93fd9f28e135676e7ce8624472ef8dfecc`.
  이전 절의 OPEN/전체 job pending 기록은 당시 상태다. 현재 코드는 아래 Web 대조가 기준이다.

### 충돌 해결·자동 병합 의미 점검

충돌은 `runtime-implementation-log.md`의 끝부분 1곳이었다. 공통 조상 뒤의 브랜치 append 3,423 bytes를
develop 전체 원문 818,312 bytes 뒤에 붙였다. develop 원문의 byte prefix와 브랜치 추가분의 byte suffix를 각각 검증했다.
오래된 브랜치의 Log 전체 파일로 덮어쓰지 않았다. merge 뒤 Notes·Log의 기존 본문도 보존하고 이 절만 append한다.

양쪽 변경 경로의 교집합은 Log와 `worker/incident_clip_composition.py` 두 곳뿐이었다.
자동 병합된 composition은 `f379276f`의 실제 Case 공개 함수 세 개 연결을 유지하면서 최신 develop의
`TransactionalRecordingRepository(..., temp_root=self.temp_root, temp_context=self.media.detached_temp ...)`도 보존했다.
source/test를 직접 읽고 단순 문법 성공과 별도로 이 의미를 대조했다.

교집합 밖 develop 유입 112개 경로는 통합 HEAD의 git tree entry가 develop과 정확히 같았고,
교집합 밖 기존 브랜치 경로는 `f379276f`와 정확히 같았다. 기존 Runtime 입력/reader/handler/process assertion을 보존했다.
최신 `prepared_metadata` encode/decode envelope, 청크 저장·분할 reader, detached stream 수명·temp lease는 그대로다.
schema·Contract·Search 정책·영상 한도·화질·workflow의 **새 임의 변경은 없다**. develop이 이미 병합한 관련 변경은 그대로 유입했다.

### 실제 Case 연결과 확인한 경계

production composition은 `case.preview_frame`의 `thumbnail_candidate_ids`, `preview_frame_position`,
`candidate_frame_position`을 직접 import해 입력과 issuer에 주입한다. 기존 `f379276f` 구현을 재사용하며
동일 기능 재작성이나 테스트 selector/위치 함수를 production에 연결하지 않았다.

| 확인 항목 | 이번 증거 |
| --- | --- |
| 현재 세대·소유권·timeline/revision, 후보 0~3 | focused 입력/Case 검사와 실제 MySQL Top-3 8경우. stale·span 없음·실행 전/후 세대 변경 포함 |
| rank 1~3, stale 제외·4위 대체 금지 | 실제 Case selector 및 Worker 원본 세대 대조, MySQL payload/View 정확 비교 |
| 후보 자기 위치·같은 위치 재사용 | 자기 `resolve_span`·Case 반환 source-local 위치 비교, preview/1위 동일 ref 및 고유 위치만 decode |
| 허용 거부만 null | `resolve_frame`의 명시적 거부 4종만 catch. DB·transaction·취소·checkpoint·metadata/helper·persistence 오류 전파 focused 검사, MySQL 저장 실패·취소 확인 |
| receipt replay·T2 redelivery | T1 rollback·실제 COMMIT ACK 유실·T2 rollback/redelivery·직접 receipt replay에 추가 decode 없음. T1 이전 crash의 새 attempt 재decode는 별도 확인 |
| 저장·재조회·투영 | 실제 Case MySQL 저장 후 새 transaction의 `preview_frame_ref`·`candidates[].thumb_ref` 및 HTTP PNG 비교 |
| 나중 null 보존 정책 | Case의 현재 세대 thumbnail 집계 공개 함수와 `test_later_clip_null_does_not_erase_an_issued_frame` 직접 실행. 기존 성공 thumbnail을 나중 null이 지우지 않음; 선택 후보 preview의 최근 clip 정책과 구분 |
| 기존 clip·두 Readout | 같은 durable clip의 receipt 재사용, single/fractional/chain 기존 process 시나리오, 두 실제 공개 Readout 호출·같은 clip 입력·CaseView 확인. 외부 OCR만 offline 대역 |
| decode 중 DB 반환 | build/resolve/extract 및 기존 process media 경계의 pool checkout 0 assertion. 청크 detached reader 실제 MySQL 검사 포함 |

frame HTTP 성공은 `image/png`, PNG signature·저장된 bytes/해시·다른 Case와 뒤 공백 Case ID 404로 확인했다.
별도 Worker/API **OS process**를 사용한 검사는 기존 process 시나리오를 재사용했으나 API child HTTP는
**ASGI TestClient**이다. TCP listener·실제 브라우저 이미지 표시 성공으로 표현하지 않는다.

### 직접 실행 결과와 실패 분류

증거 root는 ignored `.codex-scratch/rt527-develop-20261103/`이다. RAW·JSON/JUnit·진단·원격 snapshot은 여기에만 보존한다.
`run_checks.py`와 각 `*-run.json`에 실행 명령·HEAD를 남겼다. baseline은 이번 브랜치의 PASS로 합산하지 않는다.

| 실행 | 결과·범위 |
| --- | --- |
| `focused` | 실제 Case preview/Top-3 + Runtime 입력/handler/composition/issuer **155 passed** |
| `media` | multisource·Readout 입력·frame API/Recording·production media·metadata/청크 offline **150 passed, 1 skipped**. skip은 기존 사용자 영상 opt-in 미지정 |
| 첫 `mysql-frames` | **18 passed, 1 failed**. 아래 process 하네스 순서 가정 실패를 보존 |
| `mysql-frames-final` | 하네스 보완 후 **20 passed**. 강제 순서 fixture의 최종 위치 조정 전 실행임을 구분 |
| `mysql-process-final` | 최종 파일에서 PLATE 우선·OVERLAY 우선을 clip T2 후 각각 강제해 **2 passed**. 파일 SHA-256 `a35bbc9298bea280bc0fc2370e60c8a54d2cae431f0a432fa9d3c58603351388`, 실행 중 동일 |
| `mysql-compat` | chain clip·동일 clip 두 receipt + single/fractional/chain 별도 process **5 passed** |
| `mysql-develop` | metadata 정확한 숫자/legacy replay 두 kind, 청크 stream 수명·DB 반환, metadata SQL이 BLOB/청크를 읽지 않음 **6 passed** |
| `mysql-order-diagnostic` | 고정 kind 가정의 역순 queue 실패 경로 재현 **1 passed**. 제품 정상 성공 suite에 합산하지 않는 일회성 진단 |
| `baseline` | 고정 develop `ba8e21ea`의 기존 두 Readout success process와 단일 TestClient **2 passed**. 현재 브랜치 결과와 별도 |
| quality | required Ruff, mypy Linux/win32 각 **89 source files PASS** |
| boundary / Contract | 위반 0, fixture 구조 62·JSON 26·의미 104 PASS |
| diff·보존·증거 정합성 | `git diff --check`, 조상/부모·byte 보존·tree 동일성, MySQL JSON/JUnit의 setup/call/teardown 대조 PASS |

MySQL 8.4.13 결과는 중복 시나리오를 빼고 **31개의 마지막 setup/call/teardown이 모두 passed**인 증거다.
단일 31개 전체 suite 실행이라고 합산하지 않는다. 최종 두 순서 시나리오는 `mysql-process-final`을 근거로 하며
collection error·skip·xfail이 없다. 원본 실패 파일과 수정 전 성공 파일도 덮어쓰지 않았다.

첫 실패는 새 frame process 테스트가 PLATE→OVERLAY 순서를 고정한 하네스 결함이다.
기준 develop의 `test_readout_process_mysql.py`는 실제 queue 순서를 읽는다. Runtime claim은
`available_at, execution_id` 순인데 peer의 kind assertion은 stop 설정보다 먼저다.
일회성 실제 DB 역순 진단에서 OVERLAY→PLATE queue에 고정 PLATE peer를 주면 OVERLAY가
`FAILED/RUNTIME_HANDLER_ERROR`, PLATE가 `SUCCEEDED`, 남은 queue 0임을 재현했다.
그래서 다음 OVERLAY child는 대기할 수 있다. 최종 테스트는 queue 순서 조회와 두 kind 중복/누락 방지,
양쪽 첫 kind 강제 확인을 추가했다. assertion 삭제·skip·xfail·timeout 상향이나 제품 정책 보정은 없다.
관측한 제품 통합 회귀는 없고, 이 새 테스트 하네스 회귀는 수정했다.

별도 환경 이력: 첫 sandbox media 실행은 40개 뒤 첫 TestClient 검사에서 진행하지 않아 이번 소유 process만 확인해 중단했다.
그 실행은 미완료로 남긴다. 같은 단일 검사의 로컬 권한 실행과 기준 develop 단일 검사 모두 통과했고
동일 media focused 묶음도 로컬 권한에서 통과했다. sandbox 내부 지연의 세부 원인까지 확정하지 않는다.
초기 pytest cache 권한 경고는 이후 task scratch cache 경로를 사용했다.
boundary 검사는 exit 0/RAW PASS였으나 wrapper 출력에서 cp949 인코딩 오류가 났고 wrapper만 UTF-8로 고쳤다.
Starlette TestClient deprecation warning은 보존하며 의존성은 변경하지 않았다.

### Web #525 대조·후속

현재 `CandidatesScreen`은 `running_jobs.some(kind === 'INCIDENT_CLIP_BUILD')`일 때만 “미리보기 준비 중”이다.
PLATE_READ/Fine/export만으로 준비 중이 되는 과거 문제는 현재 코드에서 좁혀졌다.
Case `derive_running_jobs`는 terminal T1 뒤 T2 반영 전도 기다리는 job으로 포함한다.
그러나 카드별 rank/세대/발급 자격을 표현하는 정보는 이 목록에 없고, 4위 이하 카드에도 clip 작업 중 문구가 뜰 수 있다는
[Web 작성자 후속](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/525#issuecomment-6573023753)이 남아 있다.
세대 변경·발급 자격·취소·반영 완료 null과 실제 16:9 이미지 표시/오류 자리 복귀는 Web/Case Owner 후속으로 기록한다.
Web Owner 코드를 수정하거나 메시지·PR 댓글을 게시하지 않았다.

### 독립 리뷰·검증 한계

구현 이력을 전달하지 않은 fresh 읽기 전용 reviewer 1명에게 develop 대비 최종 source/test diff와 관련 최신 코드를 검토받았다.
초기에는 Notes·Log·과거 scratch 증거를 읽지 않고 Case 실제 연결·오류 경계·replay·최신 develop 보존을 정적으로 검토했으며
actionable 지적이 없었다. 직접 MySQL 실행에서 드러난 테스트 순서 가정은 초기 리뷰에서도 놓친 항목으로 기록한다.
하네스 보완 및 최종 강제 순서 delta를 **같은 reviewer**가 재확인해 추가 actionable P1/P2/P3가 없었다.
이후 reviewer는 최종 파일 해시·JSON/JUnit/RAW·baseline·역순 진단 산출물을 읽어 작성자 증거도 대조했다.
이는 **작성자 실행 증거 검토**이며 reviewer 자신의 테스트/DB/미디어 독립 실행이 아니다.

NOT_RUN: 전체 로컬 pytest·전체 mandatory MySQL, 이번 HEAD의 원격 CI, TCP listener, 실제 브라우저 이미지,
사용자 원본 영상, live provider, AWS·배포. 최종 전체 검증은 이후 사용자가 승인한 push의 원격 CI에 남긴다.
새 수정 commit/push, PR 본문·댓글 변경, Draft 해제·PR 병합·provider 호출을 하지 않았다.

push 전에는 이 미스테이징 테스트 보완·기록을 검토하고 별도 commit/push 범위를 승인해야 한다.
이후 이번 실제 연결/통합 revision의 원격 CI를 확인하고 PR 설명의 옛 미연결/선행 미병합 상태를 실제 상태와 정합화해야 한다.
Draft 해제 전 실제 Web 표시/남은 준비 중 조건의 검증 범위를 명시한다. Owner 복귀 정책 검토는 별도 후속이다.

### 전체 변경 경로

develop 대비 누적 기능 diff는 **18파일**이다. 이번 merge 이후 새 미커밋 수정은 테스트 1파일·문서 2파일이다.

- `docs/runtime/rt10b-preview-frames.md`
- `docs/runtime/runtime-implementation-log.md`
- `src/daesingo/worker/case_composition.py`
- `src/daesingo/worker/incident_clip_composition.py`
- `src/daesingo/worker/incident_clip_handlers.py`
- `src/daesingo/worker/incident_clip_inputs.py`
- `src/daesingo/worker/incident_frames.py`
- `src/daesingo/worker/produced_reader.py`
- `src/daesingo/worker/readout_inputs.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_production_search_process_mysql.py`
- `tests/worker/frame_process_support.py`
- `tests/worker/test_incident_clip_composition.py`
- `tests/worker/test_incident_clip_handlers.py`
- `tests/worker/test_incident_clip_inputs.py`
- `tests/worker/test_incident_clip_mysql.py`
- `tests/worker/test_incident_frames.py`
- `tests/worker/test_incident_frames_mysql.py`

이번 merge가 시작 `f379276f`에 유입한 전체 경로는 **114개**이며, 위 기능 diff와 분모가 다르다.
다른 Owner의 develop 변경은 재작성하지 않고 병합했다. 전체 경로는 다음과 같다.

```text
.env.example
.github/workflows/rt14-deploy.yml
.gitignore
Dockerfile
README.md
apps/web/src/__tests__/apiFlow.test.tsx
apps/web/src/__tests__/candidatesScreen.test.tsx
apps/web/src/__tests__/demoFlow.test.tsx
apps/web/src/__tests__/flowScreen.test.tsx
apps/web/src/__tests__/resultModel.test.tsx
apps/web/src/__tests__/uploadScreen.test.tsx
apps/web/src/components/AppHeader.tsx
apps/web/src/components/CandidateAxis.tsx
apps/web/src/components/CandidateCard.tsx
apps/web/src/screens/ApiFlow.tsx
apps/web/src/screens/CandidatesScreen.tsx
apps/web/src/screens/DemoFlow.tsx
apps/web/src/screens/FailedScreen.tsx
apps/web/src/screens/FlowScreen.tsx
apps/web/src/screens/NoResultScreen.tsx
apps/web/src/screens/NotObservedScreen.tsx
apps/web/src/screens/ResultScreen.tsx
apps/web/src/screens/SubScreens.tsx
apps/web/src/screens/UploadScreen.tsx
apps/web/src/screens/screenFocus.ts
apps/web/src/styles/global.css
apps/web/src/styles/refresh.css
docs/architecture/contracts/contract-job-record-case-view.md
docs/management/environment-and-deployment-config.md
docs/management/pre-deploy-security-review.md
docs/modules/case/decisions/evidence-preview-frame.md
docs/modules/eval/experiments/2026-10-30-aihub-best100-video-and-mixed.md
docs/modules/readout/decisions/README.md
docs/modules/readout/decisions/production-ocr-combo.md
docs/modules/recording/analysis-source-limits.md
docs/modules/recording/chunked-prepared-media.md
docs/modules/recording/experiments/2026-11-02-vfr-frame-coverage.md
docs/modules/recording/rec1a-persistence.md
docs/modules/search/decisions/README.md
docs/modules/search/decisions/external-ai-transfer-scope-2026-10-31.md
docs/product/product-spec.md
docs/runtime/README.md
docs/runtime/experiments/2026-11-02-incident720-config-real-e2e.md
docs/runtime/experiments/2026-11-02-local-capacity-probe.md
docs/runtime/experiments/2026-11-03-capacity-override.md
docs/runtime/experiments/2026-11-03-chunked-capacity-recheck.md
docs/runtime/experiments/2026-11-03-metadata-publish-fix.md
docs/runtime/experiments/2026-11-03-real-media-recheck.md
docs/runtime/experiments/README.md
docs/runtime/experiments/elice-runtime-capacity-smoke-plan.md
docs/runtime/local-runtime-environment.md
docs/runtime/ops-spec.md
docs/runtime/reviews/README.md
docs/runtime/reviews/kakao-map-build-config-2026-11-03.md
docs/runtime/reviews/runtime-p2-plan-audit-2026-11-02.md
docs/runtime/rt14-public-deployment.md
docs/runtime/runtime-implementation-log.md
docs/runtime/runtime-ops-workflow.md
docs/superpowers/plans/2026-11-02-chunked-prepared-media.md
docs/superpowers/plans/2026-11-03-capacity-override.md
docs/superpowers/plans/2026-11-03-prepared-metadata-exactness.md
eval/predictions/aihub_best100_all_s1_20261031.json
eval/predictions/aihub_best100_all_s2_20261031.json
eval/predictions/aihub_best100_all_s3_20261030.json
eval/predictions/aihub_best100_pilot_20261030.json
eval/predictions/aihub_best100_val_from_all_s1_20261031.json
eval/predictions/aihub_best100_val_from_all_s2_20261031.json
eval/predictions/aihub_best100_val_from_all_s3_20261031.json
eval/predictions/aihub_best100_val_s3_20261030.json
eval/predictions/aihub_mixed_100_v1_s1_fine_20261031.json
eval/predictions/aihub_mixed_100_v1_s2_fine_20261031.json
eval/predictions/aihub_mixed_100_v1_s3_fine_20261030.json
eval/predictions/aihub_mixed_pilot_mp2_s3_20261030.json
eval/predictions/aihub_mixed_pilot_mp2_s3_fine_20261030.json
eval/predictions/aihub_mixed_pilot_s3_20261030.json
eval/predictions/aihub_mixed_pilot_s3_retry_20261030.json
migrations/recording/versions/0002_media_chunks.py
scripts/backup_compose.py
scripts/check_mysql_test_report.py
scripts/recording_capacity_probe.py
scripts/recording_real_media_recheck.py
src/daesingo/case/preview_frame.py
src/daesingo/case/reflection.py
src/daesingo/case/view.py
src/daesingo/common/storage/media.py
src/daesingo/evidence/policy.py
src/daesingo/recording/chunked_media.py
src/daesingo/recording/materialization.py
src/daesingo/recording/multi_analysis.py
src/daesingo/recording/mysql_repository.py
src/daesingo/recording/prepared_metadata.py
src/daesingo/recording/repository.py
src/daesingo/recording/service.py
src/daesingo/recording/transactional.py
src/daesingo/worker/export_composition.py
src/daesingo/worker/incident_clip_composition.py
src/daesingo/worker/production_media.py
tests/case/test_candidate_thumbnails.py
tests/case/test_evidence_preview_frame.py
tests/common/db/integration/test_migrations.py
tests/deploy/test_backup_compose.py
tests/deploy/test_web_build_config.py
tests/eval/test_score_cli.py
tests/evidence/test_report_timezone.py
tests/recording/test_analysis_source_limits_mysql.py
tests/recording/test_chunked_media.py
tests/recording/test_chunked_media_mysql.py
tests/recording/test_prepared_metadata.py
tests/recording/test_prepared_metadata_mysql.py
tests/recording/test_recording_repository_mysql.py
tests/recording/test_vfr_materialization.py
tests/recording_acceptance.py
tests/runtime/test_capacity_probe.py
tests/runtime/test_real_media_recheck.py
```


### 종료 자원 정리·원문 보존 확인

실제 DB/media 실행 전 RAM 여유 5,323,350,016 bytes, C 디스크 여유 16,414,441,472 bytes를 직접 확인했다.
기존 image를 재사용한 작업 전용 MySQL의 memory limit은 768 MiB, 실행 중 관측 사용량은 약 259.6 MiB였다.
설정/성능 baseline 제안이 아니라 이번 최소 검증의 자원 관측값이다.

작업 컨테이너 `1028f15398587586af9726256924b52e0387ef52ae83c136371fa32f6fd2f501`의
task label·이름·mount ID를 다시 대조했다. 정리 전 시스템 schema와 빈 task test base만 남았고,
조회자 외 client·transaction·data lock은 모두 0이었다. 최초 transaction 1 관측은 삭제를 보류한 뒤
thread ID로 조회자 자신의 transaction임을 확인했다. 정상 stop 후 그 컨테이너와 새 익명 volume 하나만 제거했다.
보호 volume 3개는 정리 전후 유지됐고 공유 Docker/WSL 재시작·prune·image/cache 삭제·강제 앱 종료는 없었다.

이번 scratch 절대경계와 reparse point 없음을 검사한 뒤 생성 media·test env·credential·baseline 사본만 정리했다.
작업 Python/FFmpeg process, task label container, 작업 credential/media 잔존은 없었다.
RAW·원격 snapshot·실패/성공 JSON/JUnit·검증 명령/집계·원문 보존 증거는 ignored scratch에 남겼다.
다른 scratch·사용자 원본·기존 보호 volume·공유 image/cache는 건드리지 않았다.

종료 HEAD는 `d0b5b6e947760fe151376c357eefff46a515df2c`이며 Notes·Log의 HEAD 원문 byte prefix 보존,
미커밋 3파일·index 비어 있음·공백 오류 없음으로 종료한다. 별도 commit/push·원격 수정은 수행하지 않는다.
