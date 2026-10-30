# AnalysisSource 저장 한도

IN_PROGRESS · Refs #452 · Related #460, #450, #72 · 2026-10-30

근거: [#452 본문·전체 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452),
[Case 결정 PR #454](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/454),
[현재 Runtime 실행환경](../../runtime/local-runtime-environment.md).
MVP DB 한 행 저장을 유지한다. DB `max_allowed_packet`을 제품 상한으로 읽거나 변경하지 않는다.

## 설정과 전달

| 설정 | 단위·허용 범위 | 적용 |
| --- | --- | --- |
| `DAESINGO_RECORDING_ANALYSIS_MAX_BYTES` | 양의 정수 bytes, 기본값 없음 | 각 encode의 남은 누적 예산, 구간 결과 합계, 최종 MP4 전체, publish 직전 |
| `DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS` | 양의 정수 milliseconds, 기본값 없음 | 단일 span/전체 resolution 요청 길이, encode 이전 |

두 한도는 기존 Analysis profile 4개와 하나의 필수 그룹이다. 그룹 전체가 없으면 Analysis
capability는 비활성이고, 일부 누락·빈 값·0·음수·분수·NaN/Inf는 구성 단계에서 거부한다.
`RecordingSettings.from_mapping` → `build_recording_service` → `RecordingService`가 소비한다.
실행별 context scope로 materializer와 concat에 남은 bytes/checkpoint를 전달하고 예외에도 복원한다.
저수준 fixture/직접 service는 명시적 `AnalysisSourceLimits` 주입이 가능하며 기존 무설정 fixture 의미는 유지한다.
기본 production factory는 profile만 설정하고 한도를 빠뜨리는 구성을 허용하지 않는다.

경계와 같은 크기·길이는 허용하고 초과만 거부한다. CRF 출력 byte를 길이만으로 정확히 예측하지 않는다.
길이는 독립된 지원 범위 정책이며 byte 검사를 대체하지 않는다. source provenance·frame coverage·
gap/overlap·strict decode·원본 SHA/mtime 불변 검사와 best-effort AVI의 좁은 조건을 유지한다.

## 중단 지점과 자원 한계

- 요청 길이를 단일/다중 preparation 시작 때 검사하여 encode를 호출하지 않는다.
- 구간 결과를 순서대로 준비하고 남은 누적 예산을 다음 encode에 적용한다. 초과하면 다음 span/concat/DB write로 진행하지 않는다.
- FFmpeg encode와 concat/mux 중 출력 파일 크기를 약 50ms 간격으로 감시한다. 초과·취소·timeout에서
  자식을 kill/wait하고 pipe reader를 join한 뒤 기존 TemporaryDirectory로 파생 파일을 정리한다.
  검사 간격·OS scheduling·FFmpeg buffering 때문에 감지 전 overshoot는 가능하다. 하드 디스크/RSS quota가 아니다.
- encode/concat 반환 직후 stat을 검사하고 output probe/bytes read 전에 거부한다. 최종 파일은 span 합계와
  별도로 검사하여 mux/container overhead도 포함한다. read도 `limit + 1`까지 제한하고 다시 검사한다.
- publish 직전에 service가 byte를 재검사한다. 주입 materializer도 이 guard를 우회하여 BLOB INSERT를 할 수 없다.
  초과 경로에서는 `stable_media`·repository write를 호출하지 않는다.
- span bytes 합계는 한도 이하로만 보유하지만 concat 시 parts와 최종 content가 함께 존재할 수 있다.
  FFmpeg working memory·ffprobe frame JSON·Python 객체·DB driver의 SQL escaping/packet buffer는 이 한도의 범위 밖이다.
  임시 디스크도 parts와 최종 파일·faststart 작업 및 감지 전 overshoot가 함께 필요하다.
  배포자는 byte 값 외에 동시 실행 수·메모리·temp 용량과 DB 전송 여유를 검증해야 한다.
- 기존 caller transaction·repository 원자 저장·rollback 책임을 바꾸지 않는다. encode 중 DB transaction을 새로 열지 않는다.
  Worker의 checkpoint를 준비 scope·출력 감시·publish 직전에 전달하며 CancellationRequested를 삼키지 않는다.

## typed 실패와 Case 연결

Recording `RecordingCapabilityError.code = ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`.
고정된 진단문만 사용하고 크기·경로·argv·SQL·credential·도구 stderr를 공개 오류에 넣지 않는다.
Worker는 Search media resource 진입에서 이 code만
`FAILED / RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`로 옮긴다. Search/provider를 호출하거나
AnalysisRun/produced receipt를 만들지 않는다. 다른 Recording 오류, Search 본문/exit 오류는 이 매핑에 섞지 않는다.
기존 Runtime terminal FAILED이며 STALE 자동 재시도 대상이 아니다.

Case reflector는 이미 `failure_kind`를 `ExecutionOutcome`에 전달한다. 현재 coarse 실패 projection은
원인을 구분하지 않고 일반 `search.candidate_search_failed`/`RETRY_SEARCH`를 사용한다.
따라서 재시도 없는 별도 notice는 아직 완료가 아니다. #454에 따라 Case Owner가 terminal code를
소비하여 notice code·message_key·계약·web 문구를 등재할 후속이 필요하다. Case에 수치를 복제하지 않는다.

## pending 운영 결정과 측정

운영 대표 bytes·지원 길이·encoding은 미확정. 기존 64MiB packet 관측, “약 5분” 추정,
테스트의 낮은 한도를 운영 기본값으로 사용하지 않는다. 실행하려면 Owner가 아래 근거로 두 설정을 확정해야 한다.

1. 실제 Runtime의 확정 profile로 대표/복잡한 영상과 지원하려는 길이를 측정: 구간/누적/최종 bytes,
   encode/concat/준비 경과, peak RSS/temp 사용량, 원본 불변·coverage.
2. 운영 DB packet과 driver escaping/statement metadata 여유를 포함해 선택한 byte 한도가 실제로 저장·복원·rollback 가능한지 검증.
3. Search inline/request byte 상한과 준비·큐·Search 각각의 시간 및 기존 Case 180초 대기를 함께 검증.
4. 22개 실제 원본으로 재검증. 작은 합성 영상 검증은 해당 실제 입력 검증이나 제품 한도 결정이 아니다.

## 검증 (합성 입력)

| 검증 | 결과 |
| --- | --- |
| RED | 설정 미거부 16개, 신규 limits 경로 부재 18개, Worker 일반 오류 매핑 3개를 수정 전 확인 |
| focused | Python 3.12/Linux·고정 FFmpeg/ffprobe 8.1: Recording 전체 + 관련 Worker/Search/config **837 PASS, 15 opt-in SKIP**, MySQL 110개 deselect |
| MySQL 최소 부분집합 | 전용 MySQL 8.4·packet 1MiB 테스트 환경: 초과 무INSERT/연결 유지, exact byte 저장·재조회, caller rollback 및 기존 packet/rollback **5 PASS** |
| 실행 중 중단 | 실제 FFmpeg `-re`/lavfi 합성 입력에서 낮은 byte 한도 초과 시 `progress=end` 이전 중단·자식 회수 확인; 취소/timeout/cleanup 회귀 포함 |
| 회귀 보완 | 무한도 fixture의 기존 bytes-read 오류 주입 4개 RED→GREEN. 긴 stderr의 AVI 표식 손실 1개 RED→GREEN, bounded stderr에서도 전체 스트림의 두 고정 표식만 보존 |
| boundary·Contract fixture | PASS; 구조 62, JSON 26, 의미 104; `git diff --check` PASS |
| fresh read-only reviewer | 구현 대화 이력 없이 최초 승인. stderr 보완 뒤 같은 reviewer 재승인, 추가 수정 필요 사항 없음. 독립 process/AVI 38개·marker 분할 54개·classifier 대조 4개 PASS |

Windows native의 첫 broad run은 809 PASS/20 FAIL/15 SKIP였다. 4개는 위 read 오류 주입 회귀로
수정했고, 나머지 example/benchmark 실패는 존재하는 일반 workspace TEMP/TMP를 명시하면 통과했다.
해당 파일군 최종 native 재실행은 51 PASS/4 opt-in SKIP다. 초기 실패를 최종 Linux PASS와 합산하지 않는다.
실제 22개 원본은 확보하지 않아 검증하지 않았다. 전체 pytest/전체 mandatory MySQL·실제 provider/Paddle
process E2E·운영 동시 실행 RSS/temp 실측은 미실행이다. 전체 suite는 후속 PR 원격 CI 대상으로 남긴다.
이 작업에서는 commit/push/PR/외부 댓글을 작성하지 않는다.
