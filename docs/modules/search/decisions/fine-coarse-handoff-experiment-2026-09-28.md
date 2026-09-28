# Coarse→Fine 인계와 UNCERTAIN 지시 실험

날짜: 2026-09-28. 범위: Search 진단 실행기·프롬프트 리소스·문서. 운영 경로(`fine-p3`, `FineRequest`, `verify_fine`)는 바꾸지 않는다. [p3 진단 결정](decision-trace-2026-09-26.md)의 「한 변경씩 비교」 단계에 해당한다.

## 배경

2026-09-26 7영상 진단 실행([결과 JSON](../experiments/decision-trace-seven-video-2026-09-26-results.json))에서 Coarse가 영상 확인 위치를 잡은 양성 2개를 Fine이 모두 NOT_OBSERVED로 기각했다. 이번 실험은 그중 다음 두 관찰에서 출발한다.

- `YT_0002_C00`: Coarse는 "흰색 승용차가 황색 복선 중앙선을 바퀴로 침범"을 보고했다. Fine은 대상 연결 `NOT_FOUND`, "특정된 위반 차량이나 대상 차량 힌트가 없음"으로 답하고 다른 움직임을 근거로 기각했다.
- `youtube_clip_01`, `YT_0002_C00`: 두 Fine 모두 불확실성 목록이 비어 있고 신뢰도 0.9 이상으로 기각했다. 공통 p3 지시문에는 「확정할 수 없으면 UNCERTAIN」이 있지만 실선·중앙선 사건별 지시에는 없다(신호·안전모에는 있다).

7영상 단회 관찰이므로 원인 확정이나 채택 근거가 아니다.

## 확인한 사실

- 운영 Fine 입력(`FineRequest`)은 사건 유형, 사용자 `target_hint`, Coarse 후보 `span` ± padding으로 자른 구간뿐이다. `CandidateEvent`에 있는 `summary`(Coarse `observed` 연결), `span.representative_ms`, `uncertainties`는 Fine 프롬프트에 들어가지 않는다. 진단 실행기는 `target_hint`를 "없음"으로 고정한다.
- Search 문서(`decisions/`, `experiments/`, `research/`, `search-design-advancement-2026-09-18.md`)와 `module-architecture.md`에서 Coarse 관찰을 Fine에 **넘기지 않기로 한 결정은 찾지 못했다.** 폐기된 p4 계획도 Fine에 시간 경계만 추가하려 했다.
- `module-architecture.md` 원칙 8은 제품과 Eval이 같은 Fine capability를 쓰도록 요구한다. 현재 실제 `verify_visual()`은 `candidate`가 없으면 `MissingCandidateError`를 낸다. 따라서 `candidate.summary`는 이미 공개 입력 안에 있다. 다만 Eval이 Fine을 따로 잴 때 넣는 candidate의 summary 조건이 제품과 달라지면 측정이 제품을 대표하지 못한다.

## 결정

- 운영 `fine-p3`와 사건별 p3 지시문은 그대로 둔다. 전환은 이번 범위가 아니다.
- 진단 실행기에 Fine 변형 profile 두 개를 추가한다. 두 profile 모두 `diagnostic-v1`의 Coarse·출력 형식을 그대로 쓰고 Fine 지시문 하나만 덧붙인다. 내용과 실행은 [진단 가이드](../experiments/decision-trace-guide.md#fine)가 소유한다.
  - `diagnostic-uncertain-v1`: 실선·중앙선에 모호하면 UNCERTAIN을 쓰라는 지시를 덧붙인다.
  - `diagnostic-handoff-v1`: Coarse 관찰과 clip 기준 핵심 시각을 **검증되지 않은 단서**로 넘긴다. 영상과 다르면 영상을 따르고 차이를 불확실성으로 남기게 한다.
- 두 변경을 한 profile에 섞지 않는다. 각각 `diagnostic-v1` 9/26 회차와 비교한다.
- Coarse `uncertainties` 전달과 Coarse 횡단 기준 완화는 이번 변형에 넣지 않는다.

## 비교할 것

- 양성: Coarse O였던 `youtube_clip_01`·`YT_0002_C00`의 Fine 판정, 대상 연결 상태, 불확실성 기록.
- 음성: handoff는 Coarse 설명에 끌려갈 위험이 있다. `20260620_141628_EVT_1`처럼 Fine이 기각하던 음성 후보가 OBSERVED로 바뀌는지 따로 센다.
- UNCERTAIN 증가는 개선과 같지 않다. 판정 분포 변화로만 기록한다.

## 채택 경로

운영 반영은 [challenger 정책](challenger-policy.md)의 `FINE_FALSE_NEGATIVE`·`TARGET_ASSOCIATION` 개방 절차를 따른다. eval 채점 근거와 주간 회의 안건이 필요하다. handoff를 운영에 넣을 때는 원칙 8 때문에 Eval에 먼저 알린다. Fine 단독 측정의 candidate·summary 조건이 바뀌기 때문이다.

## 미결

- 반복 횟수와 공식 매칭 기준: [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158) 답변 대기.
- 제품에서 사용자 `target_hint`와 Coarse 관찰을 함께 줄 때의 우선순위: 미정.
- 실험 결과: 미실행.
