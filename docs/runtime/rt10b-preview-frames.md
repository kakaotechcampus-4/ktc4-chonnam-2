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
