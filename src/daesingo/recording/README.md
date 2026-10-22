# `recording` — Source / Media / Timeline 계층

**Owner:** 정철원 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈1 · **문서 작업공간:** `docs/modules/recording/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈1)

사용자 원본 참조·파일과 stream 사실·시간축·파일 경계 해석(`resolve_span`)·시각 후보·GPS 관찰·분석용 사본·RemoteCopy registry·Incident Clip·Report Video·보관/삭제

## 이 폴더가 알면 안 되는 것 (§4-모듈1 「알면 안 되는 것」)

사건 종류·법적 위반 / 신고 규정 / 어느 Timestamp source가 정답인지 / AI 모델 / case stage / AI provider API 직접 호출(그건 `search/providers/`)

## 공개 경계

다른 모듈은 `RecordingService`와 `load_recording_fixture()`만 사용한다. 저장소와 Stub 구현은 공개 경계가 아니다.

- frame·사실: `resolve_frame()`, `read_frame()`, `lookup_asset_facts()`
- 소유·형식·영속 bytes: `owns_frame()`, `owns_asset()`, `read_frame_image()`, `open_derived_asset()`
- case 소유 저장 이미지: `read_owned_frame_image(case_id, frame_ref)` — caller transaction에서 소유를 먼저 확인하고 detached `FrameImage`를 반환한다. unknown/cross-case는 `UNKNOWN_REF`, 소유하지만 bytes/이미지 형식이 없으면 `FRAME_NOT_FOUND`다. provider·재생성·원본 재처리는 호출하지 않는다.
- timeline·구간: `get_timeline()`, `get_latest_timeline()`, `resolve_span()`
- 분석 자산: `prepare_analysis_source()`, `open_analysis_source()`, `find_remote_copy()`, `register_remote_copy()`
- 사건·파생 자산: `build_incident_clip()`, `get_incident_clip()`, `register_derived_asset()`, `get_derived_asset()`, `purge_case()`

Consumer 실행 예시는 `examples/recording_consumer.py`에 있다.

실제 시각 관찰은 `observe_time_sources()`, `get_time_sources()`,
`get_time_source_candidate()`를 사용한다. 명시적인 수동 확인 입력으로만
`apply_filename_anchor()`가 새 Timeline revision을 만든다.
설정과 재현 방법은 [로컬 시각 관찰](../../../docs/modules/recording/local-time-sources.md)에 있다.

## 상태

REC-1(a)는 호출자 Connection을 사용하는 내부 MySQL repository와
`migrations/recording/`을 추가한다. SourceAsset·FrameRef(bytes 포함)·DerivedAsset
metadata·기존 case/ref 연결을 새 service에서 복원한다. 원본 locator는 주입한
storage root 아래 상대 경로이며 파일 publication은 하지 않는다.
범위와 후속 acceptance는 [구현 경계](../../../docs/modules/recording/rec1a-persistence.md)를 따른다.

REC-1(b)는 `register_local_source()`의 `original_filename` 입력을 내부 metadata로
보존·복원하고, canonical locator와 분리해 시각 관찰에 사용한다. 등록 실패는
`UNSUPPORTED_MEDIA`와 `TEMPORARY_FAILURE`로 구분하며 선택적 `case_id` 연결은
기존 Recording 관계를 같은 caller transaction에 저장한다. Case 승인·집계와
HTTP 조립은 기존 Case 공개 함수 및 RT-11 경계다.
[등록 입력 경계](../../../docs/modules/recording/rec1b-registration-input.md)를 따른다.

REC-1(c)는 Recording이 저장한 case 관계로 source/frame/derived 소유를 조회하고,
저장된 FrameRef bytes의 PNG 형식과 DerivedAsset bytes·Content-Type을 제공한다.
읽기는 원본·ffmpeg를 다시 실행하지 않는다. DerivedAsset 등록의 선택적 bytes·형식·
case 관계는 같은 caller transaction에 원자적으로 저장한다. legacy metadata-only
자산은 bytes unavailable이며, 현재 bytes adapter는 기존 Recording 출력인 PNG와
isom MP4 container를 식별한다. 지원 범위·오류·용량 한계와 검증 결과는
[REC-1(c) 경계](../../../docs/modules/recording/rec1c-ownership-reads.md)를 따른다.

1차 Mock E2E 공개 entry와 Contract 모델을 구현했다. 실제 ffmpeg, provider, storage와 DB Queue는 Tech Spec의 제외 범위대로 Stub 또는 in-memory 구현이며 후속 통합 대상이다.
