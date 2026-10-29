# 시간축 전체 길이 — 최상위 `timeline_duration_ms` · `manifest_summary.duration_sec`

> 2026-10-28 · 결정 추적 [#184](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/184) · CaseView 계약 `case-view/v1.9` · 관련 [#423](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/423)(타임라인 좌표 정밀도)

## 1. 문제

- 후보 비교 타임라인은 후보 `marker_ms`를 시간축 전체 길이로 나눠 마커를 놓는다(core-user-flow §8-2). `marker_ms`는 v1.5부터 있었지만 **전체 길이가 CaseView에 없어** web이 시간축을 그리지 못했다.
- 위치와 이름은 2026-10-05에 정했다(#184 — 최상위 `timeline_duration_ms`, `int | null`). 길이 정의를 recording에 물었고, 2026-10-24에 답을 받았다: 0부터 `source_placements[].timeline_end_sec`의 최댓값까지, 원본 사이 빈 구간 포함.
- `manifest_summary.duration_sec`(「전체 구간 길이」)는 파일 길이를 더하면 틀려서(전방 · 후방이 같은 시간대) 지금까지 `0`이었다.

## 2. 결정

1. **값의 출처는 분석 시작이 받는 timeline port(`CaseTimeline.duration_ms`)다.** case는 계산하지 않는다. 첫 탐색 범위(`issue_initial_search()`)를 만들 때 `CaseAggregate.record_timeline_duration()`으로 남기고, CaseView 최상위 `timeline_duration_ms`로 내린다.
2. **`manifest_summary.duration_sec`도 같은 값(초)이다**(`duration_ms / 1000`). 두 값이 어긋날 여지를 두지 않는다.
3. **`null`인 동안.** 분석 시작 전, 그리고 설명이 있어 단서 구조화 결과를 기다리는 동안(타임라인은 첫 탐색을 발주할 때 받는다)은 `null` · `duration_sec=0`이다. web은 `null`이면 시간축을 그리지 않는다.
4. **ms 내림을 그대로 쓴다.** recording 답변은 `round(max(timeline_end_sec) * 1000)`이지만, timeline port는 #423에서 첫 탐색 끝점이 타임라인을 넘지 않게 내림으로 바꿨다. 표시용 길이도 같은 값을 써서 첫 탐색 범위의 `end_ms`와 일치시킨다. 차이는 1ms 미만이라 화면에 보이지 않는다.
5. **state에 저장한다**(`store_state._STATE_FIELDS`의 `timeline_duration_ms`). 이 키가 없는 이전 행은 기본값 `None`으로 읽는다.
6. **버전은 `case-view/v1.9`.** 필드 추가라 minor를 올린다. web은 버전을 검사하지 않는다.

## 3. 범위 밖

- **rebase(새 timeline revision).** case는 지금 case당 타임라인 하나만 쓴다. revision이 바뀌는 경로가 생기면 그때 이 값을 갱신한다. stale 후보의 `marker_ms=null`은 그대로다(#184 recording 답변 2 — 이전 배치 유지를 보장할 수 없다).
- **`manifest_summary.range`(촬영 절대시각 범위).** recording이 신뢰할 수 있는 range를 만들 수 없는 경우가 있어 `null`을 유지한다(#184 recording 답변).
- web 시간축 그리기 — web 소유.

## 4. 테스트

`tests/case/test_start_analysis_command.py` — 분석 시작 전 `null` · `0`, 빈 설명 시작 뒤 port 값 그대로 · 첫 탐색 `end_ms`와 같음, 저장 왕복, 타임라인 실패 시 남지 않음, 설명이 있으면 구조화 결과 뒤 첫 탐색 때 채워짐. mock 시나리오 fixture(`data/mock/case/*.json`)의 case view에도 `manifest_summary.duration_sec`과 같은 값을 넣었다.
