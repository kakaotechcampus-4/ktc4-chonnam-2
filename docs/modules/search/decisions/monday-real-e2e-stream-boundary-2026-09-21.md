# 월요일 Real E2E: Search의 VIDEO stream 전달 경계

작성: 2026-09-21 · 상태: 월요일 Baseline 접합 제안 (Case·Recording 확인 대기)

이 문서는 Search 측 실행 경계와 필요한 후속 접합을 기록한다. Canonical Contract의
`stream_selector` 직렬화나 기본 stream 선택 정책을 확정하지 않으며, Case·Recording의
책임을 Search가 단독으로 결정하지 않는다.

## 현재 구현

- Coarse Search는 실행마다 `AnalysisSource` 하나를 사용하고 `LinkedCoarseResult`에
  해당 `source_ref`를 보존한다. 이는 `media_stream_ref`가 아니다.
- `ResolvedAnalysisSource`와 `SourceMeta`에는 사용한 MediaStream ref가 없다.
  `CandidateEvent.span`에는 timeline ID·revision·ms 범위만 있다.
- Case의 현재 Real E2E는 Search가 선택한 stream을 전달하지 않는다. Recording의
  첫 번째 fixture `SpanResolution`에서 timeline·range를 읽어 `resolve_span()`을 호출한다.
  따라서 현 happy fixture의 VIDEO stream 결과만으로 이 접합이 검증됐다고 볼 수 없다.

## Search 측 월요일 Baseline 제안

1. Search는 `AnalysisSource.media_stream_refs[]`만 받지 않고, 각 ref의 Recording
   `media_type`을 함께 받은 실행 전용 `AnalysisSourceStream` 목록을 입력으로 받는다.
   이 목록에서 **VIDEO가 정확히 하나일 때만** 그 `media_stream_ref`를 선택한다. 복수
   stream 중 첫 항목을 고르거나 ref 문자열·camera role로 추론하지 않는다. VIDEO가 없거나
   여럿이면 조용히 기본값을 사용하지 않고 실행 경계에서 실패시킨다.
2. Search는 선택된 ref를 실행 결과와 연결해 Case에 제공한다. 월요일에는
   `CandidateEvent`의 Canonical 직렬화를 변경하지 않고
   `verify_visual_with_stream_context()`의 `VisualVerificationExecution`을 사용한다.
   결과의 `selected_video_stream`은 `{analysis_source_ref, media_stream_ref}`를 담는다.
   같은 실행의 candidate를 조회해도 원래 선택된 ref가 보존돼야 한다.
3. Search는 선택되지 않은 VIDEO/AUDIO stream을 이 실행의 대상으로 간주하지 않는다.
   월요일 Search·Recording span 해소 범위에서 AUDIO는 제외한다.

## 다른 모듈에 확인할 접합

- **입력 연결 정보:** `AnalysisSource`와 실제 사용 VIDEO `media_stream_ref`의 대응을
  누가 어떤 공개/실행 입력으로 제공할지 확인이 필요하다. 월요일 Case 호출은
  `AnalysisSourceStream(media_stream_ref, media_type)` 목록을 구성해야 하며,
  `media_type`은 Recording의 `MediaStream` 사실에서 읽는다. Search는 ref를 합성하거나
  ref 문자열에서 type을 추론하지 않는다.
- **Case:** 선택된 `CandidateEvent.span`의 timeline ID·생성 당시 revision·ms 범위를
  초 단위 `requested_range`로 변환하고, Search가 제공한 ref를 같은
  `resolve_span()` 호출까지 전달할지 확인이 필요하다. fixture의 첫 resolution을
  candidate 구간 대신 쓰는 현재 경로는 월요일 검증 대상이다.
- **Recording:** 명시적으로 전달된 VIDEO ref 하나만 기준으로 `SpanResolution`을
  계산하고, 선택되지 않은 VIDEO/AUDIO 및 duration 미확인 AUDIO를 결과 상태에서
  제외할지 확인이 필요하다. `resolve_span()`의 현재 Python 인자와 저장소 조회 키에는
  stream ref가 없으므로 구현 접합이 필요하다.

## 범위와 검증 기준

- 월요일에는 Search가 사용한 VIDEO ref 하나의 전달과 candidate의 원래
  timeline/revision/range 보존을 검증한다. `CandidateEvent` 계약 버전은 유지한다.
- Search 테스트는 여러 VIDEO/AUDIO가 있어도 명시된 ref만 전달되는지, ref가 없을 때
  임의 선택하지 않는지, 기존 Candidate 직렬화가 변하지 않는지를 확인한다.
- `stream_selector`의 정확한 Canonical 직렬화와 기본 선택 정책은 W7 후속 Pending이다.
  이 메모의 단일 ref 인자는 그 정책의 확정이 아니다.

참고: `docs/architecture/contracts/adr/adr-data-contract-call-closure-2026-09-08.md`
§10.2는 stream을 명시하고 selector 경로를 E2E 판정에서 제외하는 비차단 회피 방법을
기록한다.
