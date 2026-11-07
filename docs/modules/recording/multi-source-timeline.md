# 명시적 다중 원본 상대 Timeline Baseline

동일 논리 카메라의 원본·VIDEO ref·배치 시각을 호출자가 명시한다.
Recording은 파일명, 배열 순서, 해상도, role 또는 opaque ref에서 관계를 추론하지 않는다.
Canonical RecordingTimeline/AssetSpan/SpanResolution은 변경하지 않는다.
`relative_rebase_001`의 revision 2처럼 여러 placement와 사이 gap을 표현한다.

## 정렬 책임과 현재 RC 범위 — #510

여러 원본의 실제 촬영 순서·gap·동시 촬영 overlap을 해석해 RecordingTimeline을
구성하는 최종 책임은 **Recording**에 있다. [아키텍처의 Recording 책임](../../architecture/module-architecture.md)과
현재 capability의 차이는 책임 이전이 아니라 **자동 정렬 구현의 유예**다.
[Recording Owner 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/510#issuecomment-6547366917)과
[PM의 RC 범위 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/510#issuecomment-6553548214)을 따른다.

현재 Recording이 제공하는 것은 **호출자가 명시한 placement의 구성·검증과 해소**다.
명시된 시작 시각으로 정렬하고 gap을 표현하는 기능을, 원본 관찰에서 실제 순서·gap을
자동으로 알아내는 기능으로 설명하지 않는다. 파일명·불확실한 시각 후보·stream 순서로
카메라나 시간 관계를 추정하지 않는다.

### RC의 Case 임시 구현과 입력 제한

Case의 `RecordingSequentialTimelineSource`는 등록 순서대로 각 원본을 앞 원본 끝에
틈 없이 배치한다. 이는 실제 녹화 순서·연속성·동시 촬영 여부를 확인한 결과가 아니다.
이번 RC에서는 이 임시 구현을 유지하고 다음 조건이 사전에 확인된 입력으로 제한한다.

- 촬영 순서가 확인됐고 그 순서대로 등록한 입력
- 파일 사이 실제 gap이 없고 연속 입력임이 확인된 경우
- 사용할 카메라와 VIDEO stream이 확인된 입력

이 조건은 **지원 범위이며 제품이 조건을 자동 검증·차단한다는 뜻이 아니다.**
임의 업로드 순서의 복원, 실제 gap의 추론·복원, 전방/후방 별도 파일의 동시 촬영 정렬은
보장하지 않는다. 명시적 placement capability가 gap을 표현할 수 있어도, Case의 임시
sequential 배치가 실제 끊김을 복원하지는 않는다.

실제 끊김을 걸친 IncidentClip·신고용 영상의 동작은 #510에서 미확인으로 남긴다.
연속성이 확인된 입력의 연결 성공으로 실제 gap이 있는 입력의 안전성을 대신하지 않는다.
Case 측 결정과 한계는 [분석 시작 §3-1](../case/decisions/start-analysis.md)에 있다.

### 후속 capability와 교체 조건

Recording이 실제 순서·gap·overlap을 해석하는 공개 capability의 **입력·실패 계약을
공개하고 구현을 준비하면**, Case의 `CaseTimelineSource` 임시 구현을 교체한다.
구현 클래스·API/Worker 조립 지점·관련 테스트를 각 Owner와 함께 대조한다.
capability 이름·구현 일정·추가 입력·카메라 선택 주체·동일 입력의 timeline 재사용
identity와 기존 Case 재처리 정책은 아직 확정하지 않는다.

기존 scope·후보·관찰이 가리키는 timeline ID/revision을 새 의미로 덮어쓰거나,
기존 Case를 자동 재계산하는 전환으로 해석하지 않는다.
[Case 교체 범위](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/510#issuecomment-6556860866)와
[Recording 수락](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/510#issuecomment-6559421773)이 후속 검토 기준이다.
이번 문서화는 RC 유예·책임·교체 조건을 기록하며 자동 정렬 구현 완료나 #510 전체 종료를 뜻하지 않는다.

## 공개 capability

```python
create_relative_timeline_from_placements(
    placements: list[dict[str, Any]], *,
    base_timeline_ref: TimelineRef | dict[str, Any] | None = None,
) -> RecordingTimeline

resolve_span(
    timeline_ref, requested_range, *,
    media_stream_ref: str | None = None,
    media_stream_refs: list[str] | None = None,
) -> SpanResolution
```

기존 `create_relative_timeline(source_asset_ref)`와 단일 `media_stream_ref` 호출,
선택 없이 읽는 fixture 경로는 유지한다. 복수 원본은 `media_stream_refs`를 명시한다.
두 선택 인자를 혼용할 수 없다. 새 입력은 실행 시 capability 인자이며,
미확정 Canonical `stream_selector` 직렬화나 기본 카메라 선택 정책을 정의하지 않는다.

## 내부 입력 모델

`multi_source.PlacementInput`은 다음 네 필드만 받는 frozen/extra-forbid 실행 입력이다.

| 필드 | 의미 |
| --- | --- |
| source_asset_ref | 이미 등록한 실제 로컬 SourceAsset |
| media_stream_ref | 그 원본에 속하는 명시적 VIDEO 하나 |
| timeline_start_sec | 유한한 0 이상 timeline 시작 시각 |
| timeline_end_sec | 시작보다 크고 알려진 원본 길이를 초과하지 않는 끝 시각 |

각 placement는 **source-local 0부터** `end-start` 길이를 사용한다. 따라서 원본 앞부분을
건너뛰는 trim은 표현하지 않으며, 그런 입력은 아직 지원하지 않는다. 끝부분을 제외한
placement도 호출자가 정확한 끝을 명시해야 한다. 입력에 없는 trim/overlap은 만들어내지 않는다.

하나의 호출은 하나의 논리 카메라 체인이라는 명시적 실행 입력이다. 서로 다른 파일의
실제 카메라 동일성 자체를 Recording이 판별하지 않는다. 각 source를 한 번만 배치하고
VIDEO 하나만 포함한다. AUDIO 및 다른 VIDEO를 자동으로 추가하지 않는다.

Recording은 명시된 시작 시각으로 정렬하며 중복 source·중복/겹치는 placement·소속이
다른 stream·AUDIO·잘못된 길이를 ValueError로 거부한다. 정확한 overlap 경계가 확정되지
않은 원본은 연결하지 않는다. Consumer가 overlap을 다시 계산할 필요가 없는 결과만 반환한다.

## 해소와 revision

- placement 사이의 빈 구간을 Timeline.gaps로 생성한다. relative-only 상태는 기존
  `relative_rebase_001`처럼 USABLE_RELATIVE_ONLY로 유지한다. 요청의 PARTIAL 여부는 SpanResolution에 기록한다.
- 같은 revision의 모든 placement마다 VIDEO ref 하나를 명시해야 한다. 입력 목록 순서는 선택 의미가 아니다.
- Timeline 외부는 OUT_OF_TIMELINE_RANGE, 파일 사이 빈 구간은 TIMELINE_GAP이며 source_ref=null이다.
- 각 파일 내부는 기존 단일 원본 계산과 fingerprint/가용성 확인을 재사용한다.
  SOURCE_UNAVAILABLE/STREAM_UNAVAILABLE에는 기존 ContractRef를 유지한다.
- 반환 span은 timeline 순서의 sequence 0부터 발급하며, source-local 좌표는 placement 시작을 뺀 값이다.
- 위치를 알 수 있는 결과는 spans와 missing_ranges가 요청 범위를 빠짐없이, 중복 없이 설명한다.
  위치를 신뢰할 수 없는 내부 실패는 기존 failure를 보존한 FAILED·빈 배열로 반환한다.
- base_timeline_ref를 생략하면 새 identity/revision 1을 만든다. 제공하면 최신 revision인지
  검사한 뒤 같은 identity의 다음 revision을 만든다. stale/없는 ref는 입력 오류이며 새 revision을 남기지 않는다.
- 과거 revision 조회와 resolve는 provenance 재현을 위해 허용한다. 과거 결과를 최신 revision으로 치환하지 않는다.
- absolute anchor가 있는 Timeline의 배치 갱신은 이번 Baseline에서 거부한다.

저장 revision은 기존 in-memory repository의 deep copy/덮어쓰기 금지 규칙으로 보존한다.
DB 저장소나 원자적 동시 갱신 제어를 추가하지 않는다.

## 검증과 실제 원본 제한

```powershell
.venv/Scripts/python.exe -m pytest tests/recording/test_multi_source_timeline.py tests/recording/test_local_span_resolution.py tests/recording/test_relative_timeline_creation.py -q -p no:cacheprovider
```

단위 테스트의 가짜 probe 입력은 실제 media metadata라고 주장하지 않는다.
별도 합성 H.264 MKV 2개로 실제 등록·두 span 해소·원본 불변도 검사한다.

실제 pair 검증은 DAESINGO_RECORDING_PAIR_A/B에 실행자가 원본 경로를 지정하는 opt-in이다.
이번 실제 두 AVI에는 정확한 placement가 제공되지 않았으므로 등록·AssetFacts 조회와
전후 SHA-256·크기·mtime 검사만 한다. Timeline 생성·파일 경계 해소가 검증됐다고 주장하지 않는다.
사용자가 보고한 **첫 원본 rear stream 끝부분 decode 문제**는 미해결 실패 사례로 유지한다.
역할을 stream 순서로 추정하지 않으며 이번 metadata 검증에서 decode 문제를 재검증하거나
정상으로 바꾸지 않는다. Source AVAILABLE은 전체 stream decode 성공을 뜻하지 않는다.

AnalysisSource/IncidentClip의 다중 span stitching, 자동 overlap 탐지, 복수 카메라 선택 정책,
업로드 API/UI, GPS, 영속 저장소는 제외한다. 기존 materialization은 다중 원본 Timeline의
span을 받아 자동 stitching하지 않는다. 다음 단위는 확정된 source-local offset/overlap 경계
입력이 필요한지 합의한 뒤, 별도 승인 아래 다중 span 소비 경계를 구현하는 것이다.
