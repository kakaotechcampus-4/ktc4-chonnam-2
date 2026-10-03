# 다중 span AnalysisSource Baseline

기존 `prepare_analysis_source(span, profile_ref, timeline_ref=...)`와
`open_analysis_source(ref)`는 유지한다. 다중 원본에는 다음 공개 capability를 사용한다.

```python
resolution = recording.resolve_span(
    timeline_ref, requested_range,
    media_stream_refs=explicit_video_refs,
)
prepared = recording.prepare_analysis_source_from_resolution(resolution, profile_ref)
opened = recording.open_analysis_source(prepared.analysis_source_ref)
with opened.stream as stream:
    content = stream.read()
```

`prepare_analysis_source_from_resolution(resolution: SpanResolution | dict,
profile_ref: str) -> AnalysisSource`는 COMPLETE인 연속 구간만 받는다.
배열 순서는 sequence로 정렬하지만 sequence를 새로 부여하지 않는다.
sequence가 Timeline 순서와 모순되거나 원본이 중복되면 입력 오류다.
현재 원본의 상태와 고정된 Timeline revision의 매핑도 다시 검증한다.
PARTIAL/FAILED, 변경·소실된 원본은 기존 machine-readable 오류로 거부한다.

각 원본의 선택 구간을 기존 profile로 인코딩하고, 검증된 임시 MP4들을
Timeline 순서로 연결한다. 모든 원본은 읽기만 하며 연결 전후 fingerprint를 검사한다.
임시 파일은 성공·실패·timeout에서 정리한다. 각 구간의 실제 frame coverage,
연결 출력의 VIDEO 구성·해상도·frame 수·상대 PTS·duration·faststart·bytes를 검증한다.
원본 전체의 snapshot/probe는 안전성 검사를 위해 실행할 수 있지만, 출력에는 선택한
구간의 VIDEO만 넣는다. AUDIO/subtitle은 포함하지 않는다.

실제 frame 경계는 아래 표현 오차 비교 한도 안에서 이어져야 한다. gap/overlap을 시간 압축,
frame 복제 또는 padding으로 보정하지 않는다. 바깥 시작·끝은 기존 단일 span과
같이 frame 선택 결과에 따라 달라질 수 있으며 실제 Timeline 범위를 반환한다.
MP4 duration metadata의 기존 반올림 허용 범위도 유지한다.

### 경계 비교 정밀도

Canonical 시간은 초 단위 숫자이며 내부 `TimeRange`/placement는 float다.
계약은 소수 자릿수나 1µs 정밀도를 지정하지 않는다. ffprobe의 관측 duration
`60.033333`과 rational frame 끝 `1801/30` 사이에는 약 0.333333µs 표현 차이가 있다.
독립적인 소수 6자리 반올림 경계의 차이를 다루기 위해, 내부 비교 한도를
`min(1µs, 관측 time-base tick / 2, 관측 최소 frame 길이 / 2)`로 제한한다.
이는 Canonical 정밀도나 일반 gap 허용 정책이 아니다.
입력 SpanResolution/placement의 논리적 연속성 검사는 기존처럼 정확한 일치를 요구한다.
이 한도는 해당 검사를 통과한 materialized 구간들의 관측 경계 비교에만 적용한다.

seam 각각과 전체 coverage/Timeline 길이 비교에 같은 상한을 적용하며 상한을
seam 개수만큼 늘리지 않는다. 1µs 초과 gap/overlap, 한 tick, 한 frame은 거부한다.
입력 timestamp·Timeline 범위·frame 목록은 반올림하거나 이동하지 않는다.
단일 frame coverage 검증과 출력 PTS/duration 검증의 기존 규칙은 변경하지 않는다.

Canonical 필드 추가 없이 직접 부모를 `source_refs[]`, 선택 VIDEO를
`media_stream_refs[]`, 좌표를 `timeline_ref`와 실제 `timeline_range`에 보존한다.
AnalysisSource에는 IncidentClip의 `source_provenance` 필드를 추가하지 않는다.
`duration_sec`과 `byte_size`는 최종 출력에서 측정한다. 같은 실행의 동일 요청은
현재 원본 상태를 재확인한 후 기존 ref/bytes를 재사용한다.

현재 연결은 같은 출력 time base·해상도에 한정한다. 서로 다른 geometry의 정규화,
자동 overlap, source-local trim 모델 확장, 기본 VIDEO 선택, IncidentClip stitching은
포함하지 않는다. 메모리에 구간 bytes와 최종 bytes를 보관하므로 장시간 영상의 메모리
최적화도 후속이다. 기존 trace는 개별 materialization을 기록하며 연결 전용 schema를 추가하지 않는다.

## 검증

```powershell
.venv/Scripts/python.exe -m pytest tests/recording/test_multi_span_analysis_source.py -q -p no:cacheprovider
```

합성 3원본의 색상/frame 순서, 2원본 부분 요청, 입력 배열 역순, provenance,
원본 불변, 오류와 cleanup을 검증한다. 실제 영상 opt-in에는 실행자가
`DAESINGO_RECORDING_PAIR_A`, `DAESINGO_RECORDING_PAIR_B`, 그리고
`DAESINGO_RECORDING_CHAIN_PLACEMENTS`(각 원본의 `[start,end]` JSON 배열)를 지정한다.
`test_opt_in_damaged_real_pair_fails_safely`는 알려진 손상 AVI pair 전용 **음성 검증**이다.
VIDEO ordinal 0을 명시적으로 선택하고 첫 원본 tail 인코딩이 기존
`TEMPORARY_FAILURE`로 종료되며 결과 미발급·원본 불변·cleanup이 유지되는지 확인한다.
`-xerror` 제거, decode 오류 무시, packet 임의 폐기는 하지 않는다.
이 배치는 실험 좌표이며 실제 촬영 overlap이나 절대 연속성을 증명하지 않는다.
실제 AVI 양성 연결은 완료되지 않았다. 양성 검증에는 깨끗한 실제 연속 원본과
명시적인 placement가 필요하다. 합성 2개·3개 원본의 성공 검증은 별도로 유지한다.
