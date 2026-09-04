# Initial Evaluation Plan

> Migration source: 서비스 기획안 1.3의 평가 관련 항목. 이 문서는 초기 실행 의도를 보존한다. contract·지표 이름은 `architecture/module-architecture.md` v4 §9를, 실패 분류 이름은 `modules/search/decisions/failure-taxonomy.md`·`modules/readout/decisions/failure-taxonomy.md`를 우선한다.

## 1. 성공 정의

> locked real long-dashcam에서 목표 event의 **Final Event Recall@3**를 중심으로 확인하고, 후보 검토수·사용자 직접 작업시간·신고 준비 완료율/실제 handoff 행동·비용·latency가 기존 방식보다 개선되는지 함께 본다.

AI 단계 평가는 eval이 담당하지만, **사용자 직접 작업시간·준비 완료율·handoff/실제 접수 행동은 코드 채점기가 아니라 별도 사용자 테스트**로 확인한다.

## 2. Evaluation Harness v1 지표

| Stage | Primary Metrics |
| --- | --- |
| Candidate | Recall@1 / @3 / @10, timestamp(span) error, FP/hour 또는 FP/clip — 데이터셋 성격에 맞게, raw duration과 함께 보고 |
| Fine | Recall, Hard-negative FPR, Precision |
| Classification (A tier — candidate 없는 frame sequence) | recall_macro, precision_macro, 5×5 confusion matrix(4종 + NONE), target correctness, 유형별 breakdown |
| Timestamp | source agreement, offset error, Overlay OCR format/continuity validation, UNKNOWN / CONFLICT rate |
| Plate | Exact Plate Accuracy, Wrong Accept Rate, Unreadable/Abstention Recall, 사용자 수정률·수정시간; 진단용 Detection Recall/Target Association/CER/Best-frame vs Multi-frame/Latency |
| E2E | Final Event Recall@3, 사용자 검토 후보 수 |
| Efficiency | **Runtime:** source-video-hour당 원가, latency, tokens, Fine exposure (원가 구성은 아래 각주) · **Eval clip suite:** cost_per_clip, fp_per_clip, processed_duration_sec — 둘을 같은 숫자로 보고하지 않는다(`architecture/module-architecture.md` §9-3) |
| Product | 사용자 직접 작업시간, 준비 완료율, handoff/실제 접수 행동 |

**Efficiency 각주 — `source-video-hour당 원가`의 구성 (1.3 「냅킨 계산」 원문)**

```
source-video-hour당 비용
= Coarse 분석
+ Fine exposure
+ Plate Pipeline/OCR
+ Timestamp Resolver/OCR fallback
+ storage/transfer
+ optional geocoder
```

**runtime 분모(source-video-hour)의 구성식은 이 문서가 소유한다.** eval clip 분모와의 관계는 `architecture/module-architecture.md` §4-모듈7 ⑤가 정한다 — 둘을 보존하고 `processed_duration_sec`로 환산한다. `search`의 `AnalysisRun.cost` 하나만 합산하면 `readout` OCR·storage·geocoder가 빠지므로, 무엇을 합산할지는 여기 정의를 따른다. 함께 기록하는 값은 latency, tokens, Fine exposure ratio, source-video-hour당 원가, 사용자 1건당 평균 탐색범위/재탐색 횟수다.

## 3. 평가 원칙

- `Top-3 Recall 90%`, `평가 300개` 같은 임의 숫자를 stage gate로 사용하지 않는다.
- Pilot을 동일 event에 수행한 뒤 모델 간 disagreement·confidence interval을 보고 평가 규모를 결정한다.
- `20분→3분`은 제품 UX 목표 가설이며 실측 전 성과수치로 말하지 않는다.
- Synthetic long-video는 architecture 개발용이다.
- 최종 제품 성능 주장은 **locked real long-dashcam test**에서만 한다.

## 4. Fine Verifier 초기 A/B

동일 candidate clip으로 다음 세 가지를 먼저 비교한다.

| 실험 | 목적 |
| --- | --- |
| Gemini Direct | 가장 단순한 baseline |
| Structured Evidence Prompt | 위반 상황 정의/근거 분해 효과 검증 |
| Structured + Positive/Hard-negative Reference | 고정 reference 효과 검증 |

TrafficRAG 전체 retrieval system은 바로 만들지 않고, 고정 reference 효과가 확인된 뒤 확장을 검토한다.

## 5. 초기 테스트 케이스

| # | 입력 | 기대한 답 | 담당자 | eval 김대원 역할 |
| --- | --- | --- | --- | --- |
| 1 | 맑은 낮, 적색 신호 상태 → 정지선 → 차량 직진 통과 | 실제 사건을 Top-3 안에 반환하고, 정밀 검증에서 신호 상태 → 정지선 → 차량 통과의 시간순 근거 제시 | 서어진 `search` | **직접 평가·채점** |
| 2 | 정상주행만 있는 30~60분 영상 | 확실한 후보 없음 또는 낮은 점수로 처리하고, 과도한 오탐을 억제 | 서어진 `search` | **직접 평가·채점** |
| 3 | 황색 중앙선 침범 | 대상 차량의 이동 경로와 중앙선 침범 전·후 근거를 함께 제시 | 서어진 `search` | **직접 평가·채점** |
| 4 | 백색 실선 진로변경 + 유사한 점선 정상 차로변경 사례 | 실선 침범과 차량 이동 경로 근거를 제시하고, 점선에서의 정상 차로변경과 구분 | 서어진 `search` | **직접 평가·채점** |
| 5 | 이륜차 안전모 미착용 + 안전모 착용 정상 사례 | 이륜차·운전자·머리 영역·안전모 착용 여부를 연결해 판단하고, 착용 사례와 구분 | 서어진 `search` | **직접 평가·채점** |
| 6 | 하나의 사건이 두 블랙박스 파일 경계에 걸쳐 있음 | 인접한 두 파일의 사건 구간을 연결하여 하나의 증거 구간(Evidence Interval)으로 구성 | 정철원 `recording` + 서어진 `search` | Search 성능은 평가, **파일 경계 처리 자체는 실행·결과 기록 여부 확인** |
| 7 | 야간·우천·역광 환경에서 사건은 보이지만 번호판이 불명확 | 사건 후보는 찾되 번호판은 `확인 필요`로 처리하고, 가장 선명한 프레임(best frame)과 여러 프레임(multi-frame) 근거 제공 | 서어진 `search` + 신유민 `readout` | **AI 영상 + OCR 직접 평가·채점** |
| 8 | 사용자가 기억한 사건 시각이 실제보다 10~20분 틀림 | 사용자에게 시간 단서 보정 또는 재탐색 경로를 제공하고, 필요한 탐색 단계만 다시 실행 | 유소연 `case` + 서어진 `search` | Search 관련 결과는 평가, **보정 흐름은 실행·결과 기록 여부 확인** |
| 9 | 영상 화면에 시각 표시가 없고 파일 메타데이터의 촬영시각만 존재 | 원본 파일의 시작 시각 + 후보 구간의 시간 위치(offset)로 발생시각을 계산하고, 출처를 `FILE_METADATA`로 명확히 표시 | 정철원 `recording` + 신유민 `readout` | OCR 평가가 필요한 부분은 직접 평가, **메타데이터 기반 시각 처리 로직은 실행 여부 확인** |
| 10 | 메타데이터와 파일명의 시각이 충돌하거나, GPS가 없거나, 지원 범위 밖의 상황 | 값을 임의로 생성하지 않는다. 메타데이터와 파일명 시각이 충돌하면 파일명 시각을 기본값으로 쓰되 CONFLICT 출처를 보존해 표시하고 사용자가 수정할 수 있게 한다(`architecture/module-architecture.md` §3-2). GPS가 없으면 위치는 UNKNOWN, 지원 범위 밖이면 그 상태를 표시한다 | 신유민 `readout` + 김준영 `evidence` + 유소연 `case` | **실행·결과 기록 여부만 확인** |
| 11 | 주간, 정면, 선명한 번호판이 촬영된 위반 차량 | 번호판 전체 문자를 OCR로 정확히 추출하고, 읽을 수 있는 경우 높은 확신 상태로 표시 | 신유민 `readout` | **직접 평가·채점** |
| 12 | 야간, 신호등 색이 흐릿하게 촬영된 신호위반 의심 상황 | 신호위반 후보는 제시하되 신호색 판단이 불확실하면 `낮은 확신 / 확인 필요`로 표시하고, 맑은 낮의 신호위반 사례와 구분 | 서어진 `search` | **직접 평가·채점** |

케이스는 초기 4종이 요구하는 signal/line/trajectory/helmet attribute·temporal order·target association을 중심으로 positive/hard-negative를 만들고, 파일경계·시간오류·GPS/번호판/시각 provenance·범위 밖 failure를 포함한다.

## 6. Failure 기록 체계

**failure 이름과 stage 체계는 각 관찰 모듈의 결정 문서를 따른다** — `search` 실패는 `modules/search/decisions/failure-taxonomy.md`, 번호판·화면시각 실패는 `modules/readout/decisions/failure-taxonomy.md`. 이 문서는 taxonomy를 소유하지 않고, 여기에 목록을 복제하지도 않는다.

1.3의 초기 분류(`SEARCH / PRIMITIVE / TEMPORAL / TARGET / FINE_FN / OTHER`)는 **대체되었다.** 모듈 구조 설계가 `search`와 `readout`의 실패를 접두어로 분리하고(`PLATE_*`) `stage`와 함께 기록하도록 정했기 때문이다. 구 이름으로 기록하면 `search`의 대상 연결 실패와 `readout`의 번호판 대상 실패가 같은 통계로 뭉쳐진다.

집계는 `stage`별로 한다.
