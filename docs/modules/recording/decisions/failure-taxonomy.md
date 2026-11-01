<a id="recording-execution-failure-taxonomy"></a>

# Recording 실행 실패 분류 체계

Runtime과 Recording Owner가 [#297 댓글 6464169000](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6464169000)에서 확인함, 2026-10-28.

| 공개 capability 오류 | JobExecution 상태 | failure_kind | produced |
| --- | --- | --- | --- |
| `build_incident_clip()`의 `RecordingCapabilityError.code == "INCIDENT_CLIP_BUILD_FAILED"` | `FAILED` | `RECORDING_INCIDENT_CLIP_BUILD_FAILED` | `[]` |

이는 문자 그대로의 일대일 매핑이며 prefix 생성 규칙이 아니다. 알 수 없는 코드는
이 매핑으로 분류하지 않는다. terminal failure에는 원시 예외, 경로, locator, 자격
증명을 포함하지 않는다. 입력 읽기, context lifecycle, checkpoint, 트랜잭션, 영속화
오류는 Runtime 경계를 유지한다. handler는 한 execution 안에서 capability를
재시도하지 않는다. Case는 새 clip job을 발행할 수 있다. Fine 성공과 produced는
변경하지 않는다. Runtime 자동 재시도는 기존 STALE 정책으로 계속 제한한다.

<a id="rt-10b-export-wiring--2026-10-29-provisional-implementation"></a>

## RT-10(b) export 연결 — 2026-10-29 잠정 구현

구현 요청의 PM 위임은 아래 Runtime 연결 선택을 허용하며 #47 Owner 검토는 연기됐다.
이는 새 Owner 승인이나 기존 report export Contract의 변경이 아니다.

| 해당 호출에서만 발생한 capability 오류 | status | failure_kind |
| --- | --- | --- |
| `export_report_video`: `REPORT_VIDEO_EXPORT_FAILED` | `FAILED` | `REPORT_VIDEO_EXPORT_FAILED` |
| `export_plate_image`: `PLATE_IMAGE_EXPORT_FAILED` | `FAILED` | `PLATE_IMAGE_EXPORT_FAILED` |
| `export_plate_image`: `PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE` | `FAILED` | `PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE` |

각 실패에는 produced 객체가 없다. 알 수 없는 코드와 입력/영속화/context 오류는
Runtime 처리를 유지한다. 취소는 전파한다. Case는 처음 두 항목을 기존
`recording.report_video_export_failed`와 `recording.plate_image_export_failed`
notice 코드에 매핑한다. 제한 소진도 plate 실패 notice를 사용하며 동일 입력의
`GENERATE_PLATE_IMAGE` action은 없다. 한정된 전략과 연기된 항목은
[구현 메모](../../../runtime/rt10b-recording-exports.md)에 있다.

<a id="425-analysis-input-preparation--2026-10-31-request-specification"></a>

## #425 분석 입력 준비 — 2026-10-31 요청 명세

아래 literal은 이 구현 요청에서 채택한다. #425 Owner 댓글에서 이전에 승인한
terminal 값이 아니다.

| 해당 호출에서만 발생한 capability 오류 | JobExecution 상태 | failure_kind | produced |
| --- | --- | --- | --- |
| `prepare_analysis_source_from_resolution`: `RecordingCapabilityError.code == "UNSUPPORTED_MEDIA"` | `FAILED` | `RECORDING_UNSUPPORTED_MEDIA` | `[]` |

`COARSE_SEARCH`와 `FINE_VERIFY`가 공유하는 운영 분석 입력 준비에 적용하며
`HINT_EXTRACT`에는 적용하지 않는다. 이는 자동 prefix 규칙이나 전역 Recording
예외 변환기가 아니다. 알 수 없는 코드, 입력/메타데이터 읽기, factory 설정,
DB/트랜잭션/commit/영속화 오류, checkpoint, 취소, usage, Search/provider 호출,
context 종료/정리는 기존 경계를 유지한다. factory는 단일 준비 호출만 catch하며
그 저장소 호출은 데이터베이스/트랜잭션 예외를 변경 없이 전파한다.
예외 문구, 파일 이름, 경로, locator, 비디오 내용은 terminal에 들어가지 않는다.
기존 크기 제한, IncidentClip, export 매핑은 변경하지 않는다.

Case는 기존 projection과 notice를 통해 FAILED를 계속 소비한다. 이 매핑은 새
notice, action, 재시도 정책을 정하지 않는다. 세부 내용과 게시하지 않은 Case Owner
제안은 [구현 메모](../../../runtime/issue425-media-failure-mapping.md)에 있다.
