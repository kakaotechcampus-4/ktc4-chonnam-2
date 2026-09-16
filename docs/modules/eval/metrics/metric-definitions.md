# 평가지표 정의 — 확정본

> **Owner:** 김대원 (`eval`) · **최종 갱신:** 2026-09-16 · **대상 코드:** `eval/scorers/*.py`
> **버전:** candidate `s3` · plate `p1` · cost `c1` · normalizer `n1`

---

## 1. 이 문서의 소유 경계

**이 문서가 정하는 것** — 각 지표의 **계산 의미**: 분자·분모가 무엇이고, 무엇을 적중으로 판정하며,
어떤 조건에서 값이 `null` 이 되는가.

**이 문서가 정하지 않는 것**

| 무엇 | 소유자 |
| --- | --- |
| 어떤 stage 에 어떤 지표를 둘 것인가(지표 목록) | `architecture/module-architecture.md` §9-3 |
| 실행 의도·성공 정의·평가 원칙 | `modules/eval/initial-evaluation-plan.md` §1 · §2 · §3 |
| 하니스 구조·파일 배치·후속 항목(F1~F13) | `modules/eval/harness-v1-design.md` |
| 지표가 어느 문헌 전통에서 왔는가 | `modules/eval/research/metric-provenance.md` |
| 실패 분류 이름 | `modules/search/decisions/failure-taxonomy.md` · `modules/readout/decisions/failure-taxonomy.md` |

지표 값을 **계산하는 것은 코드**이고, **무엇을 계산해야 하는가는 이 문서**다.
둘이 어긋나면 버그다 — 어느 쪽을 고치든 한쪽만 조용히 바꾸지 않는다.

---

## 2. 현황 한눈에

| Stage | 지표 | 상태 | 지금 값이 나오나 |
| --- | --- | --- | --- |
| Candidate | `recall_at` 1/3/10 · `onset_error_sec` · `containment_rate` · `fp_per_clip` · `by_type` | **확정 · 구현** | 예 (B tier) |
| Classification | `recall_macro` · `precision_macro` · `recall_by_label` · 5×5 `confusion` · `target_correctness` · `by_condition` | **확정 · 구현** | 예. `NONE` 행·열은 `ab_mixed` manifest 에서만 채워진다 |
| Plate | `exact_accuracy` · `wrong_accept_rate` · `abstention_recall` | **확정 · 구현** | mock tier 만. 실데이터는 C tier 확보 전까지 `null` |
| Cost | `cost_per_case` · `cost_per_source_video_hour` · `total` | **확정 · 구현** | 예 (`UsageRecord` 가 있을 때) |
| Fine | Recall · Precision · Hard-negative FPR | 확정 · **미구현** | 아니오 |
| Timestamp | source agreement · offset error · overlay validation · UNKNOWN/CONFLICT rate | 확정 · **미구현** | 아니오 |
| E2E | Final Event Recall@3 · 사용자 검토 후보 수 | 확정 · **미구현** | 아니오 |
| Product | 사용자 직접 작업시간 · 준비 완료율 · handoff 행동 | 확정 · **코드 채점 아님** | 별도 사용자 테스트 |

「확정 · 미구현」은 지표 이름과 배치가 §9-3 에서 정해졌지만 scorer 가 없다는 뜻이다.
이 문서의 3~6절은 **구현된 것만** 정의한다. 미구현 지표의 계산 의미는 구현 시점에 여기에 추가한다.

---

## 3. Candidate — `eval/scorers/candidate.py` (`s3`)

입력은 clip 단위 후보 목록. 후보는 `score` 내림차순으로 **rank 를 1부터 재계산**한다
(impl 이 보낸 rank 값은 무시한다, `normalize.py`).

### 3-1. 적중 판정

후보 `c` 가 정답 사건 `t` 에 적중했다 ⟺ **두 조건을 모두** 만족

1. `c.event_type == t.violation_type`
2. `|c.representative_sec − t.t_onset_sec| ≤ tolerance_sec` (기본 **2.0초**)

**구간 IoU 로 판정하지 않는다.** 계약 v1.1 §4-1 이 `span` 을 「coarse 후보 창」으로 확정했기 때문이다 —
창은 「사건이 여기까지다」가 아니라 「여기를 더 보라」는 제안이므로, 창을 넓게 잡았다고 점수가
깎이면 안 된다. 창의 품질은 `containment_rate` 로만 본다.

**한 예측은 한 사건에만 쓰인다.** 위 조건을 만족하는 (후보, 사건) 쌍을 클립 단위로 모아
**최대 매칭**으로 1:1 배정한 뒤, 배정된 사건만 적중으로 센다. 배정하지 않으면 사건 둘이
`2×tolerance` 안에 있을 때 예측 하나가 적중 2건으로 세어져 recall 이 부풀어 오른다.

탐욕이 아니라 최대 매칭인 이유: 탐욕은 먼저 나온 사건이 후보를 삼켜 뒤의 사건이 굶을 수 있고,
그러면 **recall 이 정답지의 사건 나열 순서에 따라 달라진다.** 최대 매칭의 크기는 순서와 무관하다.

### 3-2. 지표

| 지표 | 분자 | 분모 | `null` 이 되는 때 |
| --- | --- | --- | --- |
| `recall_at.K` | 상위 K개 후보 중 하나라도 적중한 사건 수 | **채점 대상 사건 수** (클립 수 아님) | 사건이 0건 |
| `onset_error_sec.mean` / `.median` | `\|representative_sec − t_onset_sec\|` 의 평균 / 중앙값 | **최대 K(=10)에서 적중한 사건** | 적중이 0건 |
| `containment_rate` | 적중 후보의 창이 `t_start ≤ onset ≤ t_end` 인 건수 | 위와 같은 적중 사건 | 적중이 0건 |
| `fp_per_clip` | negative 클립에서 나온 **후보 개수 전부** | **negative 클립 수** | negative 클립이 0개 |
| `by_type[유형].recall_at.K` | 해당 유형에서 적중한 사건 수 | 해당 유형의 사건 수 | — (유형이 없으면 키가 없다) |

`onset_error_sec.tolerance_sec` 는 지표가 아니라 **그 실행에 쓴 임계값의 기록**이다. 결과 파일이
자기 판정 기준을 스스로 말하게 하려고 넣는다.

### 3-3. 분모에 무엇이 들어가는가

- **사건 분모(`n_events`)** — `targets` 중 `scoring == "INCLUDED"` 인 것만. `scoring` 키가 없으면
  `INCLUDED` 로 본다(없다고 빼면 분모가 조용히 줄어 recall 이 부풀려진다). 모르는 `scoring` 값은
  채우지 않고 예외로 올린다.
- **제외 사유** — `EXCLUDED`(채점 대상 아님) / `BOUNDARY_EXCLUDED`(클립 경계에 걸침). 제외 건수는
  `excluded_by_reason` 과 `coverage` 에 **반드시 적힌다** — 그래야 결과의 `n_events` 와 정답지의
  `clips_with_events` 가 어긋난 이유를 결과 파일만 보고 알 수 있다.
- **negative 클립 분모(`n_negative_clips`)** — `targets` 가 빈 항목. `not_applicable: true`(예측을
  만들 입력 자체가 없었던 항목)는 **분모에 넣지 않는다** — 「후보를 냈어야 하는데 안 냈다」와 다르다.
- `violation_type` 이 없는 `INCLUDED` target 은 채점할 수 없으므로 **예외**다(참값이 없으면 `EXCLUDED` 여야 한다).

### 3-4. FP/clip 을 소스별로 쪼개지 않는 이유

B tier 의 `YT_0002` 는 20초 원본에서 나온 조각 1개뿐이고 그 조각에 위반이 있다 — negative 가 없어
`source_video_id` 별 분모가 서지 않는다. 그래서 **전체 분모로만 읽는다**(`harness-v1-design.md` §4-1).
§9-3 이 「FP/hour 또는 FP/clip — dataset 성격에 맞게」라고 둘을 연 것이 이 경우다.

---

## 4. Classification — `eval/scorers/classification.py`

입력은 시퀀스 단위 분류 결과. 라벨 공간은 **4종 + `NONE` = 5** (`eval/enums.py`, 원본은 v4 §3-5).

### 4-1. 지표

| 지표 | 정의 | `null` 이 되는 때 |
| --- | --- | --- |
| `recall_by_label[L]` | `TP(L) / (TP(L) + FN(L))` | 그 라벨의 GT 가 0건 |
| `precision_macro` / `recall_macro` | 라벨별 값의 **단순 평균**. 값이 `null` 인 라벨은 평균에서 **뺀다** | 모든 라벨이 `null` |
| `confusion[truth][pred]` | 5×5 건수 | stage 미실행 |
| `target_correctness` | 예측 bbox 와 GT bbox 의 **2-D IoU ≥ 0.5** 인 비율 | `target_bbox` 있는 GT 가 0건 |
| `by_condition.day_night[주간\|야간]` | 그 조건의 정확도와 `n` | — |

**macro 를 쓰는 이유.** A tier 시퀀스가 SIGNAL 2,065 : 안전모 412 로 5배 차이 난다. micro 로 재면
신호위반만 잘하는 모델이 전체 점수를 가져간다. 제품은 4종을 **모두** 약속했다.

**`null` 라벨을 평균에서 빼는 이유.** 데이터가 없는 클래스를 0점으로 세면 「측정 못 했다」가
「성능이 나빴다」로 바뀐다 — 7절의 null 규율과 같은 원칙이다.

### 4-2. 예측·라벨이 이상할 때

| 경우 | 처리 | 기록되는 곳 |
| --- | --- | --- |
| GT 라벨이 baseline enum 밖 | **채점에서 제외**(진실을 지어낼 수 없다) | `n_invalid_gt_labels` · `coverage` |
| 예측이 baseline enum 밖 | `NONE` 으로 접어서 채점(사라지지도, `NONE` 보다 유리하지도 않게) | `n_invalid_predictions` · `coverage` |
| 해당 시퀀스에 예측이 없음 | `NONE` 을 예측한 것으로 채점(미탐으로 잡힌다) | confusion 의 `NONE` 열 |
| GT `target_bbox` 가 `None` | `target_correctness` **분모에서 제외**(미탐으로 세지 않는다) | — |
| 예측 bbox 형식이 깨짐(길이≠4) | `target_correctness` **분모에는 남고 분자에는 안 들어간다** | `n_invalid_bboxes` · `coverage` |

### 4-3. `NONE` 은 `ab_mixed` manifest 에서만 나온다

A tier(`a_aihub`) 단독으로 채점하면 **`NONE` 행·열이 전부 0** 이다 — AI-Hub 시퀀스는 전부 4종 중
하나여서 「아무 위반도 아닌 것」이 없다. 5×5 라고 부르지만 실측은 4×4 가 된다.

`NONE` 은 B tier 의 **검토를 마친 negative 클립**에서 온다(§4-2). 두 tier 를 이어 붙인 것이
`manifests/ab_mixed` 이며 `eval/tools/build_ab_mixed.py` 가 만든다(현재 A 120 + NONE 30 = 150).

- 뽑은 클립은 `meta.coverage.sampling`(`rule_version` · `seed`)에 기록된다 — **샘플링이 GT 의 일부다.**
- 항목마다 `source_tier`(`A` / `B`)가 있다. A 는 AI-Hub 원본 프레임, B 는 YouTube 재인코딩 영상이라
  해상도·압축 특성이 다르고, 그 차이를 지운 채 한 숫자로 뭉치면 결과가 거짓말을 한다.
- B tier 항목에는 `target_bbox` · `condition` 이 **없다**(`null`). 없는 라벨을 지어내지 않으므로
  그 항목들은 `target_correctness` 와 `by_condition` 의 분모에서 빠진다.
- B tier 정답지의 검토가 끝나지 않았으면(`clips_reviewed < clips_total` 또는
  `negatives_confirmed: false`) 빌더가 **거부한다** — 검토 안 된 클립을 「사건 없음」 정답으로 쓸 수 없다.

---

## 5. Plate — `eval/scorers/plate.py` (`p1`)

정답 판정은 **`abstained` × GT `legibility` 교차표** 하나다.

| | GT `READABLE` | GT `UNREADABLE` |
| --- | --- | --- |
| `abstained = false` | `exact_accuracy` 의 분모 · 값이 맞으면 분자 | **`wrong_accept_rate` 의 분자** |
| `abstained = true` | 놓친 판독 (어느 지표에도 안 들어간다) | `abstention_recall` 의 분자 |

| 지표 | 분자 | 분모 |
| --- | --- | --- |
| `exact_accuracy` | `value == true_text` 인 건수 (**부분 일치 없음**) | GT `READABLE` + 기권 안 한 건수 |
| `wrong_accept_rate` | GT `UNREADABLE` 인데 기권 안 한 건수 | **GT 가 `UNREADABLE` 인 항목 전체** |
| `abstention_recall` | GT `UNREADABLE` 이고 기권한 건수 | **GT 가 `UNREADABLE` 인 항목 전체** |

아래 두 지표는 **분모가 같고 합이 1** 이다. 같은 교차표 열의 두 칸이기 때문이다.

### 5-1. `wrong_accept_rate` 의 분모를 못 박는다

분모는 **「정답이 `UNREADABLE` 인 항목」**이다. **「예측이 `abstained=true` 인 항목」이 아니다.**

읽을 수 없는 번호판에 확신을 담아 값을 내는 것 — 사용자가 검증할 방법이 없는 값을 신고서에
옮기게 되는 것 — 이 이 지표가 잡아야 할 오류다. v1 구현은 분모에서 abstain 항목을 빠뜨려
이 오탐을 **항상 0으로 보고**했고, 검증할 GT 가 없어 그 사실이 드러나지 않았다. 그래서 해당 분기는
비활성화가 아니라 **삭제**했다가 `p1` 에서 이 정의로 다시 만들었다(`harness-v1-design.md` §9 F6).

### 5-2. 데이터가 없을 때

- 정답지 자체가 없으면 전부 `null` + `NO_PLATE_GT`. A tier 는 번호판이 비식별 처리되어 문자 정답이
  없다(§4-3) — **C tier 확보(F1) 전까지 실데이터 값은 나오지 않는다.**
- 정답지에 없는 `readout_id` 는 채점 대상이 아니라 조용히 건너뛴다(`n` 에도 안 들어간다).
- `n_unreadable` 이 0이면 아래 두 지표는 `null`.
- `wrong_accept_rate` 의 **분자가 0이면 경고를 단다** — 「안전하다」가 아니라 「pack 에 그런 케이스가
  없다」이기 때문이다(`ZERO_NUMERATOR`).

---

## 6. Cost — `eval/scorers/cost.py` (`c1`)

| 지표 | 정의 |
| --- | --- |
| `cost_per_case` | `case_id` 별 `UsageRecord.cost.amount` 합 |
| `total` | 위의 총합 |
| `cost_per_source_video_hour` | `total / (processed_duration_sec / 3600)` |

**집계 키는 `case_id` 다** (`contract-usage-record.md` §9-2). `run_ref` 로 묶으면 run 이 산출되지 않은
attempt(`run_ref = null`, `RUN_NOT_PRODUCED`)가 통째로 빠져 **비용이 과소 보고된다.**

- **통화가 섞이면 합산하지 않는다.** 환율은 `pricing_context` 에 귀속되며 eval 이 정할 값이 아니다 → 전부 `null` + `MIXED_CURRENCY`.
- 분모(`processed_duration_sec`)는 호출부가 넘긴다. 이 모듈은 파일을 읽지 않는다.
- 0원 case 가 있으면 `coverage` 에 그 `case_id` 를 적는다 — 평균만 보면 안 보인다.
- **runtime 원가와 eval 실행 비용을 같은 숫자로 보고하지 않는다**(v4 §9-3). runtime 분모
  (source-video-hour)의 구성식은 `initial-evaluation-plan.md` §2 각주가 소유한다.

---

## 7. 전 단계 공통 규율

1. **데이터가 없는 지표는 `0` 이 아니라 `null` + 사유 문자열.** 0으로 적으면 「측정했고 나빴다」로 오독된다.
2. **돌지 않은 stage 도 키를 전부 채우고 값만 `null`.** 키를 빼면 결과를 모으는 쪽이 「키가 없는 모양」과
   「키가 `null` 인 모양」을 따로 처리해야 한다. `by_type`·`confusion` 도 `{}` 가 아니라 `null` 이다 —
   빈 dict 는 「세어 봤더니 하나도 없었다」로 읽힌다.
3. **`coverage` 는 두 가지를 함께 적는다** — ① 어떤 지표가 왜 `null` 인가 ② 무엇을 채점에서 제외했는가.
   ②는 지표가 전부 `null` 이 아니어도 실린다. 사유가 여럿이면 `"; "` 로 잇는다.
4. **순환 경고.** 정답지 `meta.coverage.derived_from_mock_pack` 이거나 `independent_ground_truth: false` 면
   `coverage` 에 순환 경고를 단다 — mock tier 의 onset·`true_text` 는 채점 대상 예측과 같은 fixture 에서
   유도한 값이라 점수가 **구조상 만점**이다. 성능 근거가 아니다.
5. **계약 버전이 다르면 채점하지 않는다.** 정답지와 예측의 `contract_version` 이 둘 다 있고 다르면
   `ContractMismatch` 로 거부한다(exit 4). 한쪽만 `null` 인 것은 거부하지 않는다.
6. **실패 분류 이름은 eval 이 소유하지 않는다.** 미확정이면 `UNKNOWN`.

### `coverage` 사유 문자열 목록

| 사유 | 뜻 |
| --- | --- |
| `NOT_RUN — stage=… 실행이다` | 이번 실행의 stage 가 아니다 |
| `NO_EVENTS` | 정답지에 채점할 사건이 없다 |
| `NO_NEGATIVE_CLIPS` | `fp_per_clip` 의 분모가 없다 |
| `NO_MATCHED_EVENTS` | 적중이 없어 `onset_error_sec` 를 못 낸다 |
| `EXCLUDED` / `BOUNDARY_EXCLUDED — N건` | 채점에서 뺀 사건 수 |
| `INVALID_GT_LABELS` / `INVALID_PREDICTIONS` / `INVALID_BBOXES` | enum 밖 라벨·예측, 형식이 깨진 bbox 처리 결과 |
| `NO_SEQUENCES` | classification 정답지가 비었다 |
| `NO_PLATE_GT` | 이 manifest 에 plate 정답지가 없다 |
| `NO_SCORED_READOUTS` | 정답지와 겹치는 판독이 없다 |
| `NO_USAGE_RECORDS` / `MIXED_CURRENCY` / `ZERO_PROCESSED_DURATION` / `NO_PROCESSED_DURATION` / `ZERO_COST_CASES` | cost 쪽 사유 |
| `순환 경고 — …` / `wrong_accept_rate 분자 0건 — …` | 숫자를 성능 근거로 쓰지 말라는 경고 |

---

## 8. 버전 — 어떤 숫자끼리 비교해도 되는가

결과 파일 `meta` 에 실리는 값이다. **하나라도 다르면 같은 표에 나란히 놓지 않는다.**

| 필드 | 무엇이 바뀌면 올라가나 | 현재 |
| --- | --- | --- |
| `scorer_version` | 지표 계산 규칙 | candidate `s3` · plate `p1` · cost `c1` |
| `gt_version` | 정답지 내용 | B tier `g3` · A tier `g1` · mock `mp1` · 정답지 없으면 `nogt` |
| `normalizer_version` | impl 출력 → scorer 입력 변환 | `n1` |
| `manifest_version` · `clip_rule_version` | 데이터셋 구성·클립 분할 규칙 | 정답지 `meta` |
| `contract_version` | 계약 | 다르면 채점 거부 |
| `code_commit` | — | **이 실행이 딛고 선 트리**(자기를 담은 커밋의 부모). 틀린 값이 아니다(F9) |

`scorer_version` 은 **stage 별로 기록한다.** 전 stage 에 candidate 의 값을 쓰면 plate 결과가
candidate 의 지표 정의(「IoU → onset point error」)를 자기 것인 양 적어 낸다.

---

## 9. 결과 파일에서 읽는 법

```
eval/results/<run_id>.<gt_version>.json
  meta        run_id · impl · stage · manifest · gt_version · scorer_version · prediction_ref{path, sha256}
  candidate   { recall_at, onset_error_sec, containment_rate, fp_per_clip,
                n_events, n_negative_clips, excluded_by_reason, by_type, coverage }
  classification { recall_macro, precision_macro, recall_by_label, confusion,
                   target_correctness, by_condition, n,
                   n_invalid_predictions, n_invalid_gt_labels, coverage }
  plate       { exact_accuracy, wrong_accept_rate, abstention_recall, n, coverage }
  cost        { cost_per_case, cost_per_source_video_hour, total, currency,
                n_rows, scenarios, coverage, scorer_version }
```

`cost` 는 stage 와 무관하게 **항상** 계산된다(`UsageRecord` 가 없으면 `NO_USAGE_RECORDS`).
나머지 세 블록 중 이번 stage 가 아닌 것은 `not_run()` 모양이다.

**어떤 블록이든 먼저 `coverage` 를 읽는다.** 숫자만 보고 판단하지 않는다.

---

## 10. 아직 확정되지 않은 것

| # | 항목 | 지표에 미치는 영향 |
| --- | --- | --- |
| F8 | `tolerance_sec = 2.0` 과 bbox IoU `0.5` 가 실험으로 정해지지 않았다 | 두 값은 **서로 무관**하다(1-D 시간 vs 2-D 공간). 같은 값인 것은 우연 |
| F1 | C tier(실제 촬영 원본) 미확보 | plate 3종이 실데이터로 나오지 않는다. **촬영이 필요해 코드로 못 푼다** |
| F2 | 화면시각 라벨 없음 | Timestamp 지표 전체. **라벨링이 필요하다** |
| F4 | hard-negative 대조쌍 없음 | Hard-negative FPR. **라벨링이 필요하다** |
| F5 | `search`·`evidence` 구현 대기 | Fine · E2E · Efficiency stage. **다른 Owner 의존** |
| F3 | B tier 에 **안전모 사건이 0건** | `by_type` 에 `MOTORCYCLE_HELMET_NON_USE` 행이 없다. 사건 10건은 `recall_at` 의 신뢰구간이 여전히 넓다 |
| — | `NONE` 은 `a_aihub` 단독 채점에서 여전히 0 | manifest 선택이 곧 측정 범위다 (§4-3) |

**해소된 항목** (2026-09-16): F7(1:1 배정) · F11(깨진 bbox 카운터) · F12(`NONE` 데이터 경로) ·
F13(시퀀스 불변식 검사기) · F10(유형별 대상 객체) · F6(plate 채점) · F3(B tier 123클립 확장).
근거와 실측은 `harness-v1-design.md` §9.

미결은 미결로 둔다. 이 표의 항목을 「대충 정한 값」으로 채워 문서를 완성시키지 않는다.

---

## 11. 지금 이 숫자로 말해도 되는 것 / 안 되는 것

**말해도 되는 것**

- 지표 계산이 검증됐다 — `fake:always_correct` 는 만점, `fake:always_wrong` 은 최저를 받는다.
- 정답지 불변식이 지켜진다 — `t_start < t_end`, span 이 클립 길이 안, `violation_type` 이 4종,
  `file_path` 존재, `sha256` 일치.
- 결과 파일이 자기 한계를 스스로 말한다 — `coverage` · 순환 경고 · 버전 필드.

**말하면 안 되는 것**

- mock tier 의 점수를 성능 근거로 쓰는 것 — 정답이 채점 대상과 같은 fixture 에서 나왔다(순환).
- plate 지표 — 실데이터가 없다.
- `NONE` 을 포함한 5×5 성능 — 그 행·열은 비어 있다.
- `Top-3 Recall 90%` 같은 임의 숫자를 stage gate 로 쓰는 것(`initial-evaluation-plan.md` §3).
- 최종 제품 성능 주장 — **locked real long-dashcam test 에서만** 한다.

---

## 참조

`architecture/module-architecture.md` §3-5 · §9-2 · §9-3 · §9-4 ·
`modules/eval/initial-evaluation-plan.md` §2 · §3 ·
`modules/eval/harness-v1-design.md` §4 · §5 · §7-1 · §9 ·
`modules/eval/research/metric-provenance.md` ·
`eval/scorers/candidate.py` · `classification.py` · `plate.py` · `cost.py` · `eval/score.py` · `eval/enums.py`
