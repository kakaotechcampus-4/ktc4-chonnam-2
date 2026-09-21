# 단일 원본 Timeline의 명시적 VIDEO span 계산

Owner: 정철원. 3주 설계서 §5.4/OI-3의 Search→Case→Recording 전달 합의를 구현한다.
Canonical CandidateEvent·SpanResolution 구조와 정식 stream_selector 직렬화는 변경하지 않는다.

## 공개 호출

```python
resolution = service.resolve_span(
    timeline_ref,
    requested_range,
    media_stream_ref=used_video_ref,
)
```

공개 시그니처는 `resolve_span(timeline_ref, requested_range, *, media_stream_ref: str | None = None)`이다.
실제 로컬 원본 계산에서 ref는 필수다. None 기본값은 기존 fixture 기반 2인자 호출의 호환용이며,
실제 계산의 기본 stream 선택을 뜻하지 않는다. Case는 Search가 실제 사용한 VIDEO ref를 그대로 전달한다.
등록 결과의 첫 원소, role, ref 이름으로 stream을 추론하지 않는다.

```powershell
uv run --locked python -m examples.recording_resolve_span <로컬영상> --start 1 --end 2 --video-index 1
```

예제의 필수 video-index는 사용자가 명시하는 VIDEO 목록의 0 기반 순번이다. CLI가 그 항목의 실제
opaque ref를 공개 함수로 전달한다. 기본 순번은 없으며 production Case에는 순번 대신 ref를 전달한다.
root Python 3.12와 ffprobe가 필요하다. 원본이나 파생 파일을 저장하지 않는다.

## 선택 검증과 오류

Canonical Timeline 계약 §9는 잘못된 참조·범위를 입력 오류로, 정상 입력의 해소 불가를 FAILED로 구분한다.
이번 함수의 VIDEO ref도 입력 참조이므로 다음은 ValueError이며 SpanResolution을 만들지 않는다.

- 로컬 호출의 ref 누락·빈 값·미등록 값, AUDIO ref
- 요청한 Timeline revision의 placement에 없거나 둘 이상 존재하는 ref
- ref의 SourceAsset 소속이 placement와 불일치하거나 SourceAsset 안에서 중복된 경우
- 음수·비유한 범위, start>=end, 미등록 Timeline/revision

유효한 VIDEO가 명시적으로 UNAVAILABLE이면 기존 STREAM_UNAVAILABLE missing 규칙으로 처리한다.
원본 소실·변경은 SOURCE_UNAVAILABLE와 source_asset ref다. 이는 잘못된 입력 ref와 구분한다.
선택되지 않은 AUDIO의 null duration이나 다른 VIDEO의 가용성은 status 계산에 사용하지 않는다.

기존 무선택 happy fixture의 front-only COMPLETE도 유지한다. 명시 선택으로 fixture를 호출할 때도
반환 span이 선택 ref와 정확히 일치하는 한 개여야 하며, 없거나 여러 개이면 기존
RecordingCapabilityError(TEMPORARY_FAILURE)로 실패한다. 첫 항목을 선택하거나 결과를 필터링하지 않는다.

## 계산과 반환

- 단일 placement, 선택 VIDEO 한 개만 계산한다. 선택 ref와 다른 AssetSpan은 반환하지 않는다.
- 단위는 초이며 [start,end)다. placement 시작이 source-local 0이다. Decimal 계산 후 계약 float로 반환한다.
- 요청 범위를 바꾸지 않고 placement 경계·명시 gap·선택 stream 끝에서 나눈다.
- OUT_OF_TIMELINE_RANGE와 TIMELINE_GAP의 source_ref는 null이다.
- 알려진 stream 끝 이후 또는 명시적 UNAVAILABLE은 STREAM_UNAVAILABLE와 선택 media_stream ref다.
- 선택 stream의 duration 미관측은 coverage를 확정할 수 없는 FAILED이며 가짜 STREAM_UNAVAILABLE을 만들지 않는다.
- UNKNOWN stream 가용성은 decode 미검증 상태로 유지한다. 유한한 길이 안의 metadata 좌표 매핑만 허용한다.
- span만 있으면 COMPLETE, span과 missing이 있으면 PARTIAL, usable span이 없으면 FAILED다.
  FAILED도 정식 결과이며 어디가 해소 불가인지 missing/failure로 설명한다.
- gap 등으로 선택 stream의 span이 여러 개면 월요일 단일-span 연결 조건을 충족하지 못하므로
  기존 TEMPORARY_FAILURE capability 오류를 반환한다. 합치거나 첫 값을 사용하지 않는다.
- source fingerprint를 재검증하며 결과를 캐시하지 않는다. 이전 결과·Timeline revision은 보존한다.

## 실패 vocabulary

이전 미커밋 계산 단계의 값을 유지하며 새 code는 추가하지 않았다. 임시 STREAM_SELECTION_REQUIRED는 삭제했다.
입력 오류와 단일-span 불일치에는 새 failure code를 만들지 않는다. 아래 값은 기존 계산 문서의 정의다.

| kind | code | 의미 |
| --- | --- | --- |
| UNRESOLVED | STREAM_COVERAGE_UNKNOWN | 선택 stream의 길이가 미확인 |
| UNAVAILABLE | NO_USABLE_SPAN | missing_ranges가 설명하는 범위에서 usable span 없음 |
| TEMPORARY | SOURCE_INSPECTION_FAILED | IO/권한/동시 변경으로 원본 상태 판정 불가 |
| INVALID_STATE | TIMELINE_METADATA_INVALID | 내부 Timeline metadata 불일치 |
| UNSUPPORTED | TIMELINE_NOT_SUPPORTED | 다중 placement 등 지원 범위 밖 |

NO_USABLE_SPAN 외에는 missing_ranges=[]다. 다른 Owner의 실패 enum이나 Evidence 정책에 값을 추가하지 않는다.

## 검증과 한계

`tests/recording/test_local_span_resolution.py`는 내부 함수를 직접 호출하지 않고 공개 service로
선택 검증·COMPLETE/PARTIAL/FAILED·원본 보존·fixture 호환을 검사한다. 생성 AVI CLI도 공개 함수를 호출한다.
실제 두 AVI는 각 VIDEO ref를 명시해 1–2초 요청의 단일 COMPLETE span과 정확한 ref 일치를 검사한다.
꼬리 구간은 선택 stream 길이와 Timeline 경계를 반영한다. 미관측 audio는 계산에서 제외한다.

단일 원본의 metadata 매핑에 한정한다. 실제 decode coverage, 컨테이너 내 stream 시작 지연 보정,
다중 원본 연결, AnalysisSource·IncidentClip 생성은 미구현이다. 원본 전체 hash를 읽는 비용이 있다.
정식 stream_selector 직렬화와 기본 선택 정책은 W7 후속이다. Search→Case 실행 문맥 배선 및 전체
Real E2E의 완료는 별도이며, Recording 공개 capability의 검증 결과와 구분한다.
