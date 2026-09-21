# `recording` — Source / Media / Timeline 계층

**Owner:** 정철원 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈1 · **문서 작업공간:** `docs/modules/recording/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈1)

사용자 원본 참조·파일과 stream 사실·시간축·파일 경계 해석(`resolve_span`)·시각 후보·GPS 관찰·분석용 사본·RemoteCopy registry·Incident Clip·Report Video·보관/삭제

## 이 폴더가 알면 안 되는 것 (§4-모듈1 「알면 안 되는 것」)

사건 종류·법적 위반 / 신고 규정 / 어느 Timestamp source가 정답인지 / AI 모델 / case stage / AI provider API 직접 호출(그건 `search/providers/`)

## 공개 경계

다른 모듈은 `RecordingService`와 `load_recording_fixture()`만 사용한다. 저장소와 Stub 구현은 공개 경계가 아니다.

- frame·사실: `resolve_frame()`, `read_frame()`, `lookup_asset_facts()`
- timeline·구간: `get_timeline()`, `get_latest_timeline()`, `resolve_span()`
- 분석 자산: `prepare_analysis_source()`, `open_analysis_source()`, `find_remote_copy()`, `register_remote_copy()`
- 사건·파생 자산: `build_incident_clip()`, `get_incident_clip()`, `register_derived_asset()`, `get_derived_asset()`, `purge_case()`

Consumer 실행 예시는 `examples/recording_consumer.py`에 있다.

명시적으로 선택된 단일 로컬 VIDEO span의 분석용 H.264 MP4 생성은
`LocalAnalysisProfile`과 `RecordingService.prepare_analysis_source()`로 시험할 수 있다.
지원 범위와 임시 파일 수명은 `docs/modules/recording/local-analysis-materialization.md`를 참조한다.

## 상태

1차 Mock E2E 공개 entry와 Contract 모델을 구현했다. 실제 ffmpeg, provider, storage와 DB Queue는 Tech Spec의 제외 범위대로 Stub 또는 in-memory 구현이며 후속 통합 대상이다.
