# 평가지표 정의 — 확정본

> **Owner:** 김대원 (`eval`) · **최종 갱신:** 2026-09-20 · **대상 코드:** `eval/scorers/*.py`
> **버전:** candidate `s4` · classification `cl2` · plate `p2` · cost `c2` · normalizer `n2`

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
| Candidate | `recall_at` 1/3/10 · **`localization_recall_at`** · **`type_accuracy_given_localized`** · `onset_error_sec` · `containment_rate` · `fp_per_clip` · `by_type` | **확정 · 구현** | 예 (B tier) |
| Classification | `recall_macro` · `precision_macro` · `recall_by_label` · 5×5 `confusion` · `target_correctness` | **확정 · 구현** | 예. `NONE` 행·열은 `ab_mixed` manifest 에서만 채워진다 |
| ~~Classification `by_condition`~~ | ~~촬영조건별 정확도~~ | **철회 (`cl2`)** | 아니오 — 근거는 §4-4 |
| Plate | `exact_accuracy` · `wrong_accept_rate` · `abstention_recall` · **`readable_abstention_rate`** · **`abstain_reasons`** | **확정 · 구현** | mock tier 만. 실데이터는 C tier 확보 전까지 `null` |
| Cost | `cost_per_case` · `cost_per_source_video_hour` · `total` · **`latency_ms`** · **`latency_per_source_video_hour`** | **확정 · 구현** | 예 (`UsageRecord` 가 있을 때) |
| Fine | Recall · Precision · Hard-negative FPR | 확정 · **미구현** | 아니오 |
| Timestamp | source agreement · offset error · overlay validation · UNKNOWN/CONFLICT rate | 확정 · **미구현** | 아니오 |
| E2E | Final Event Recall@3 · 사용자 검토 후보 수 | 확정 · **미구현** | 아니오 |
| Product | 사용자 직접 작업시간 · 준비 완료율 · handoff 행동 | 확정 · **코드 채점 아님** | 별도 사용자 테스트 |

「확정 · 미구현」은 지표 이름과 배치가 §9-3 에서 정해졌지만 scorer 가 없다는 뜻이다.
이 문서의 3~6절은 **구현된 것만** 정의한다. 미구현 지표의 계산 의미는 구현 시점에 여기에 추가한다.

---

## 3. Candidate — `eval/scorers/candidate.py` (`s4`)

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

**크기만 유일하고 어느 쌍으로 맺는지는 유일하지 않다.** `recall_at` 은 크기만 쓰므로 이걸로 충분하지만,
`onset_error_sec` 와 `containment_rate` 는 **선택된 쌍**을 쓴다. 그래서 배정을 두 가지로 고정한다:

- 사건을 **`(onset, event_id)` 정규 순서**로 처리한다 — 정답지 파일의 줄 순서가 아니다
- 각 사건의 후보를 **`(onset 오차, rank)` 오름차순**으로 본다 — 배정이 자유로우면 가까운 후보에 붙는다

고정하지 않으면 같은 예측·같은 사건인데 정답지의 줄 순서만 바꿔도 `containment_rate` 가
0.0 ↔ 1.0 으로 뒤집힌다. `event_id` 가 없고 `onset` 까지 같은 사건이 둘이면 그때는 파일 순서로 떨어진다.

**한 클립의 사건은 GT 항목이 여럿으로 쪼개져 있어도 한 번에 배정한다.** 항목별로 배정하면
같은 후보가 양쪽에서 적중으로 세어져 1:1 배정이 무의미해진다.

### 3-1-1. 시간 축과 유형 축은 따로 잰다

`recall_at` 은 위 두 조건이 **모두** 맞아야 적중이다. 그래서 「순간은 정확히 찾았는데 유형을
잘못 불렀다」와 「아예 못 찾았다」가 **똑같이 0** 으로 나온다 — 고쳐야 할 곳이 완전히 다른
두 실패다. 그래서 시간 축을 따로 낸다.

| 지표 | 적중 조건 |
| --- | --- |
| `recall_at.K` | 유형 일치 **그리고** 시간 허용 오차 이내 |
| `localization_recall_at.K` | **시간만** 허용 오차 이내 (유형을 보지 않는다) |
| `type_accuracy_given_localized` | 시간이 맞은 사건 중 유형까지 맞은 비율 |

유형을 보지 않는 배정에서도 **같은 거리라면 유형이 맞는 후보를 먼저** 잇는다. 아니면
유형 정확도가 동률 배정 운에 휘둘린다.

> **`recall_at` 은 두 축의 곱이 아니다.** 유형을 요구하면 후보-사건 그래프가 달라지고 최대
> 매칭도 달라지므로, 두 축은 **서로 다른 배정**에서 나온다. 곱으로 검산하지 않는다.

`localization_recall_at` 은 정의상 `recall_at` 보다 작을 수 없다 — 더 느슨한 조건이기 때문이다.
뒤집혔다면 배정이 잘못된 것이다.

### 3-2. 지표

| 지표 | 분자 | 분모 | `null` 이 되는 때 |
| --- | --- | --- | --- |
| `recall_at.K` | 상위 K개 후보 중 하나라도 적중한 사건 수 | **채점 대상 사건 수** (클립 수 아님) | 사건이 0건 |
| `localization_recall_at.K` | 상위 K개 중 **시간만** 맞은 사건 수 | 위와 같은 사건 수 | 사건이 0건 |
| `type_accuracy_given_localized` | 시간이 맞은 사건 중 유형까지 맞은 건수 | **시간이 맞은 사건 수** | 시간이 맞은 사건이 0건 (`NO_LOCALIZED_EVENTS`) |
| `onset_error_sec.mean` / `.median` | `\|representative_sec − t_onset_sec\|` 의 평균 / 중앙값 | **최대 K(=10)에서 적중한 사건** | 적중이 0건 |
| `containment_rate` | 적중 후보의 창이 `t_start ≤ onset ≤ t_end` 인 건수 | 위와 같은 적중 사건 | 적중이 0건 |
| `fp_per_clip` | negative 클립에서 나온 **후보 개수 전부** | **negative 클립 수** | negative 클립이 0개 |
| `by_type[유형].recall_at.K` | 해당 유형에서 적중한 사건 수 | 해당 유형의 사건 수 | — (유형이 없으면 키가 없고, `coverage` 에 `NO_EVENTS_FOR_TYPE` 로 적힌다) |

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

## 4. Classification — `eval/scorers/classification.py` (`cl2`)

입력은 시퀀스 단위 분류 결과. 라벨 공간은 **4종 + `NONE` = 5** (`eval/enums.py`, 원본은 v4 §3-5).

### 4-1. 지표

| 지표 | 정의 | `null` 이 되는 때 |
| --- | --- | --- |
| `recall_by_label[L]` | `TP(L) / (TP(L) + FN(L))` | 그 라벨의 GT 가 0건 |
| `precision_macro` / `recall_macro` | 라벨별 값의 **단순 평균**. 값이 `null` 인 라벨은 평균에서 **뺀다** | 모든 라벨이 `null` |
| `confusion[truth][pred]` | 5×5 건수 | stage 미실행 |
| `target_correctness` | 예측 bbox 와 GT bbox 의 **2-D IoU ≥ 0.5** 인 비율 | `target_bbox` 있는 GT 가 0건 |

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
| GT `target_bbox` 가 `None` | `target_correctness` **분모에서 제외**(미탐으로 세지 않는다) | `coverage` (`NO_TARGET_BBOX_GT`) |
| 예측 bbox 형식이 깨짐(길이≠4, 또는 넓이 ≤ 0) | `target_correctness` **분모에는 남고 분자에는 안 들어간다** | `n_invalid_bboxes` · `coverage` |

### 4-3. `NONE` 은 `ab_mixed` manifest 에서만 나온다

A tier(`a_aihub`) 단독으로 채점하면 **`NONE` 행·열이 전부 0** 이다 — AI-Hub 시퀀스는 전부 4종 중
하나여서 「아무 위반도 아닌 것」이 없다. 5×5 라고 부르지만 실측은 4×4 가 된다.

`NONE` 은 B tier 의 **검토를 마친 negative 클립**에서 온다(§4-2). 두 tier 를 이어 붙인 것이
`manifests/ab_mixed` 이며 `eval/tools/build_ab_mixed.py` 가 만든다(현재 A 120 + NONE 30 = 150).

- 뽑은 클립은 `meta.coverage.sampling`(`rule_version` · `seed`)에 기록된다 — **샘플링이 GT 의 일부다.**
  선택에 `random.sample` 을 쓰지 않는다. CPython 이 버전 간 보장하는 것은 `random()` 스트림뿐이고
  `sample()` 의 알고리즘은 구현 세부라, 파이썬을 올리면 뽑히는 클립이 조용히 달라질 수 있다.
- 항목마다 `source_tier`(`A` / `B`)가 있다. A 는 AI-Hub 원본 프레임, B 는 YouTube 재인코딩 영상이라
  해상도·압축 특성이 다르고, 그 차이를 지운 채 한 숫자로 뭉치면 결과가 거짓말을 한다.
- B tier 항목에는 `target_bbox` · `condition` 이 **없다**(`null`). 없는 라벨을 지어내지 않으므로
  그 항목들은 `target_correctness` 의 분모에서 빠진다.
- B tier 정답지의 검토가 끝나지 않았으면(`clips_reviewed < clips_total` 또는
  `negatives_confirmed: false`) 빌더가 **거부한다** — 검토 안 된 클립을 「사건 없음」 정답으로 쓸 수 없다.

### 4-4. `by_condition` 을 내렸다 (`cl1` → `cl2`, 2026-09-20)

**있던 지표를 지웠다.** 못 믿을 라벨 위에 서 있었기 때문이다.

AI-Hub 71555 의 촬영조건 라벨은 **한 클립 안에서 값이 갈린다** — 전수 5,619클립 기준
`DayNights` **97.54%** · `Weather` 98.36%. 근거는 readout PR
[#93](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/93) 의 `condition-label-audit.txt` 다.

대조군이 결정적이다. **해상도는 값이 45종인데 클립 안에서 한 번도 안 흔들린다(0.00%).**
클립 묶음이 정확하다는 뜻이고, 따라서 97.54% 는 묶음 오류가 아니라 **라벨 자체가 무작위에 가깝다.**
클립 내 「주간」 비율이 중앙 0.50(p10 0.40 · p90 0.60)이라 무작위 배정과 구분되지 않는다.

여기에 우리 쪽 문제가 겹쳤다 — `sample_aihub.py` 는 시퀀스의 조건을 **첫 프레임 라벨**에서
가져온다. 값이 클립 안에서 갈린다면 그건 **동전 한 번 던진 값**이다.

그리고 `by_condition` 은 **`day_night` 하나로만** 잘랐다. 지표 전체가 그 축 위에 있었다.

**왜 아무도 몰랐나.** 커밋된 결과가 `야간 n=66 · 주간 n=54` 로 비율이 그럴듯했고, impl 이
치트(전부 맞힘/전부 틀림)라 정확도가 `1.0`/`0.0` 으로만 나와 **차이가 생길 자리가 없었다.**
실제 모델이 도는 순간 이 표는 근거 없는 「야간이 더 어렵다」를 말하게 된다.

**`road_type` 으로 갈아타지 않았다.** 그 축은 0.00% 로 멀쩡하지만, 원래 의도는 조명·날씨였지
도로종류가 아니다. 엉뚱한 축을 남겨 두면 **의도가 채워진 것처럼 보인다.** 조건별 성능은
이제 못 잰다 — 그 사실을 §10 에 미결로 남긴다.

**키를 `null` 로 남기지 않고 지웠다.** `null` 은 「이번 실행에 데이터가 없었다」로 읽힌다(§7 규율 1).
여기는 그게 아니라 **지표를 철회한 것**이다. 파일명의 `cl1` → `cl2` 가 그 경계를 말한다.

**`condition` 라벨 자체는 manifest·정답지에서 지우지 않는다.** 원본이 그렇게 말했다는 것은
사실이고, 그 기록까지 지우면 나중에 이 판단을 재검토할 수 없다. 쓰지 않을 뿐이다.

---

## 5. Plate — `eval/scorers/plate.py` (`p2`)

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

### 5-0. 기권만 하는 모델을 막는다

위 세 지표만으로는 **아무것도 읽지 않는 모델이 만점 두 개를 받는다.** 실측:

```
exact_accuracy      null     <- 답한 게 없어 분모가 0
wrong_accept_rate   0.0      <- 확신에 차서 틀린 적이 없다
abstention_recall   1.0      <- 기권해야 할 걸 전부 기권했다
```

`exact_accuracy` 의 `null` 이 「정답지가 없다」인지 「모델이 기권했다」인지도 구분되지 않았다.

| 지표 | 분자 | 분모 | `null` 이 되는 때 |
| --- | --- | --- | --- |
| `readable_abstention_rate` | GT `READABLE` 인데 기권한 건수 | **GT 가 `READABLE` 인 항목 전체** | `READABLE` 이 0건 (`NO_READABLE_GT`) |
| `abstain_reasons` | `abstain_reason` 값별 기권 건수 (dict) | — | 실행 안 함 |

`READABLE` 을 **전부** 기권하면 `coverage` 에 `ANSWERED_NOTHING` 이 붙는다 —
`exact_accuracy` 가 `null` 인 이유가 정답지가 아니라 모델이라는 것을 결과 파일이 말한다.

**가중 합산 점수는 여기서 만들지 않는다.** 「기권 1건이 오답 몇 건 값이냐」는 제품이 정할
값이지 채점기가 정할 값이 아니다(§1 소유 경계). 채점기는 가중치를 고르는 대신
**기권만 하면 반드시 나빠 보이는 숫자**를 둔다.

### 5-0-1. 기권 사유를 남긴다

`abstain_reason` 은 `plate-readout/v1.3` 이 authoritative 로 둔 필드다. 예측 파일의 `raw` 에
들어와 있었으나 `normalize` 가 버려 채점 결과까지 올라오지 못했다 — `n2` 에서 잇는다.
`target_association.status`(어느 차를 읽었다고 봤는가)도 함께 옮긴다.

사유 없는 기권은 `n_abstained_without_reason` 과 `NO_ABSTAIN_REASON` 으로 드러낸다.
기권률만으로는 무엇을 고쳐야 하는지 알 수 없다.

`frame_results[]`·`samples` 는 옮기지 않는다 — 계약 §9 가 eval 의 기본 제공 범위를
`consensus`·`best_frame`·`abstained`·`target_association`·`validation` 으로 두고 상세 진단에만
쓰라고 한다. 원문은 예측 파일 `raw` 에 그대로 남는다.

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

## 6. Cost — `eval/scorers/cost.py` (`c2`)

| 지표 | 정의 |
| --- | --- |
| `cost_per_case` | `case_id` 별 `UsageRecord.cost.amount` 합 |
| `total` | 위의 총합 |
| `cost_per_source_video_hour` | `total / (processed_duration_sec / 3600)` |
| `latency_ms.p50` / `.p90` / `.max` | `UsageRecord.latency_ms` 의 분포 (**보간하지 않는 nearest-rank**) |
| `latency_per_source_video_hour` | `sum(latency_ms)/1000 / (processed_duration_sec / 3600)` — 초 단위 |

**집계 키는 `case_id` 다** (`contract-usage-record.md` §9-2). `run_ref` 로 묶으면 run 이 산출되지 않은
attempt(`run_ref = null`, `RUN_NOT_PRODUCED`)가 통째로 빠져 **비용이 과소 보고된다.**

- **통화가 섞이면 합산하지 않는다.** 환율은 `pricing_context` 에 귀속되며 eval 이 정할 값이 아니다 → 전부 `null` + `MIXED_CURRENCY`.
- 분모(`processed_duration_sec`)는 호출부가 넘긴다. 이 모듈은 파일을 읽지 않는다.
- 0원 case 가 있으면 `coverage` 에 그 `case_id` 를 적는다 — 평균만 보면 안 보인다.

### 6-1. 속도

`latency_ms` 는 `usage-record/v1.2` §9-4 가 이미 필수 키로 둔 값이다. eval 이 새로 만드는
값이 아니라 `c1` 이 읽지 않고 버리던 값이다.

- **평균을 내지 않고 분포로 낸다.** 평균 하나로는 「대부분 빠른데 가끔 30초」가 안 보인다.
- **분위수를 보간하지 않는다.** 호출 건수가 적을 때 보간하면 실제로 일어나지 않은 지연
  시간이 결과 파일에 적힌다. 실측값 중 하나를 고른다.
- **`latency_per_source_video_hour` 는 경과시간이 아니다.** 호출이 병렬이면 합은 벽시계를
  넘는다. 「영상 1시간을 처리하는 데 든 **총 호출 대기 시간**(초)」이며 그 이상을 주장하지 않는다.
- `latency_ms` 가 없는 row 는 `n_missing` 으로 센다 + `PARTIAL_LATENCY`. 분모가 조용히 줄면
  「전부 빨랐다」로 읽힌다. 어느 row 에도 없으면 `null` + `NO_LATENCY` — 빨랐다는 뜻이 아니라
  재지 않았다는 뜻이다.
- **통화가 섞여 비용 집계가 멈추는 자리에서도 속도는 낸다.** 통화는 비용의 문제다.
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
7. **채점 결과를 덮어쓰지 않는다.** 파일명이 숫자를 만든 버전을 전부 싣고(§9), 같은 이름이
   이미 있으면 `eval.score` 는 쓰지 않고 `rc 3` 으로 멈춘다 — 예측과 같은 규율이다.
   채점 프로세스가 바뀌면 이름이 달라져 옛 결과 옆에 남는다.

### `coverage` 사유 문자열 목록

| 사유 | 뜻 |
| --- | --- |
| `NOT_RUN — stage=… 실행이다` | 이번 실행의 stage 가 아니다 |
| `NO_EVENTS` | 정답지에 채점할 사건이 없다 |
| `NO_NEGATIVE_CLIPS` | `fp_per_clip` 의 분모가 없다 |
| `NO_MATCHED_EVENTS` | 적중이 없어 `onset_error_sec` 를 못 낸다 |
| `NO_LOCALIZED_EVENTS` | 시간이 맞은 사건이 없어 `type_accuracy_given_localized` 를 못 낸다. 「유형을 다 틀렸다」가 아니다 |
| `EXCLUDED` / `BOUNDARY_EXCLUDED — N건` | 채점에서 뺀 사건 수 |
| `INVALID_GT_LABELS` / `INVALID_PREDICTIONS` / `INVALID_BBOXES` | enum 밖 라벨·예측, 형식이 깨진 bbox 처리 결과 |
| `NO_TARGET_BBOX_GT` | 라벨이 없어 분모에서 뺀 항목 수. 뺀 수를 적어야 결과만으로 분모가 복원된다 |
| `NO_EVENTS_FOR_TYPE` | 정답지에 사건이 하나도 없는 baseline 유형. `by_type` 에 **키가 없는 것**과 0점을 구분한다 |
| `NO_SEQUENCES` | classification 정답지가 비었다 |
| `NO_PLATE_GT` | 이 manifest 에 plate 정답지가 없다 |
| `NO_SCORED_READOUTS` | 정답지와 겹치는 판독이 없다 |
| `NO_READABLE_GT` | 정답지에 `READABLE` 이 없다. `exact_accuracy`·`readable_abstention_rate` 의 분모가 0 |
| `ANSWERED_NOTHING` | `READABLE` 을 전부 기권했다. `exact_accuracy` 의 `null` 이 정답지 탓이 아니라 모델 탓이다 |
| `NO_ABSTAIN_REASON` | 사유 없는 기권 건수. 진단할 수 없는 기권이다 |
| `NO_USAGE_RECORDS` / `MIXED_CURRENCY` / `ZERO_PROCESSED_DURATION` / `NO_PROCESSED_DURATION` / `ZERO_COST_CASES` | cost 쪽 사유 |
| `NO_LATENCY` / `PARTIAL_LATENCY` | 속도를 못 재거나 일부만 쟀다. 「빨랐다」가 아니라 「안 쟀다」 |
| `순환 경고 — …` / `wrong_accept_rate 분자 0건 — …` | 숫자를 성능 근거로 쓰지 말라는 경고 |

---

## 8. 버전 — 어떤 숫자끼리 비교해도 되는가

결과 파일 `meta` 에 실리는 값이다. **하나라도 다르면 같은 표에 나란히 놓지 않는다.**

| 필드 | 무엇이 바뀌면 올라가나 | 현재 |
| --- | --- | --- |
| `scorer_version` | 지표 계산 규칙 | candidate `s4` · classification `cl2` · plate `p2` · cost `c2` |
| `gt_version` | 정답지 내용 | B tier `g3` · A tier `g1` · mock `mp1` · 정답지 없으면 `nogt` |
| `normalizer_version` | impl 출력 → scorer 입력 변환 | `n2` |
| `manifest_version` · `clip_rule_version` | 데이터셋 구성·클립 분할 규칙 | 정답지 `meta` |
| `contract_version` | 계약 | 다르면 채점 거부 |
| `code_commit` | — | **이 실행이 딛고 선 트리**(자기를 담은 커밋의 부모). 틀린 값이 아니다(F9) |
| `prediction_ref.sha256` | 예측 파일 내용 | 산출물은 `newline="
"` 로 쓴다. 텍스트 모드로 쓰면 Windows 에서 CRLF 가 되는데 `.gitattributes` 는 `eol=lf` 라, 기록된 지문이 **커밋된 파일의 지문이 아니게 된다** |

`scorer_version` 은 **stage 별로 기록한다.** 전 stage 에 candidate 의 값을 쓰면 plate 결과가
candidate 의 지표 정의(「IoU → onset point error」)를 자기 것인 양 적어 낸다.

---

## 9. 결과 파일에서 읽는 법

```
eval/results/<run_id>.<gt_version>.<scorer_version>-<cost_scorer_version>.json
  meta        run_id · impl · stage · manifest · gt_version · scorer_version ·
              cost_scorer_version · normalizer_version · code_commit ·
              prediction_ref{path, sha256}
  candidate   { recall_at, localization_recall_at, type_accuracy_given_localized,
                onset_error_sec, containment_rate, fp_per_clip,
                n_events, n_negative_clips, excluded_by_reason, by_type, coverage }
  classification { recall_macro, precision_macro, recall_by_label, confusion,
                   target_correctness, n,
                   n_invalid_predictions, n_invalid_gt_labels, coverage }
  plate       { exact_accuracy, wrong_accept_rate, abstention_recall,
                readable_abstention_rate, n_readable,
                abstain_reasons, n_abstained_without_reason, n, coverage }
  cost        { cost_per_case, cost_per_source_video_hour, total, currency,
                latency_ms{p50,p90,max,n,n_missing}, latency_per_source_video_hour,
                n_rows, scenarios, coverage, scorer_version }
```

**파일명이 숫자를 만든 버전을 전부 싣는다.** 이름이 `<run_id>.<gt_version>.json` 이던 동안
`s2 → s3` 개정에서 s2 결과가 통째로 사라졌다 — 정답지가 같으면 파일명이 같았기 때문이다.
정답지가 같아도 채점기가 다르면 다른 숫자이고, 다른 숫자는 다른 파일이어야 비교할 수 있다.

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
| — | **산출물 드리프트를 아무도 안 잡는다** | 채점 코드를 고치고 `results/` 재생성을 빠뜨려도 통과한다. 커밋된 예측을 재채점해 결과와 대조하는 검사가 필요하다 (CI 또는 테스트) |
| — | `locked_test/` 가 비어 있다 | 「최종 제품 성능 주장은 locked test 에서만 한다」(`initial-evaluation-plan.md` §3)의 **근거가 아직 없다.** 개봉 횟수·승인 정책도 미결(v4 §10-3) |
| — | pytest 가 CI 에서 안 돈다 | 테스트 255개가 로컬 실행 증빙으로만 선다. CI 는 `check_boundaries.py`·`check_contract_fixtures.py` 두 개뿐이다 |
| — | **촬영조건별 성능을 못 잰다** | `by_condition` 을 `cl2` 에서 **철회했다**(§4-4) — AI-Hub 71555 의 조명·날씨 라벨이 무작위에 가까웠다. `road_type` 은 멀쩡하지만 원래 의도한 축이 아니라 갈아타지 않았다. **조명·날씨별 성능을 재려면 라벨이 새로 필요하다** — 코드로 못 푼다 |
| — | **candidate·classification 에 판단 근거가 없다** | `CandidateEvent` 계약에 근거 필드가 **아예 없다**. plate 는 `abstain_reason` 으로 이었지만(§5-0-1) 이쪽은 옮길 값 자체가 없다. **계약 개정 사안이라 `search` Owner 소유** |

**해소된 항목** (2026-09-16~18): F7(1:1 배정) · F11(깨진 bbox 카운터) · F12(`NONE` 데이터 경로) ·
F13(시퀀스 불변식 검사기) · F10(유형별 대상 객체) · F6(plate 채점) · F3(B tier 123클립 확장) ·
코드 리뷰 지적 9건(배정 순서 의존 · stage 별 `scorer_version` · 분모 기록 · 샘플링 재현성 ·
산출물 지문 · 측정 공백). 근거와 실측은 `harness-v1-design.md` §9.

**멘토 피드백 해소** (2026-09-20 · 안용준 멘토): ① 판독 판단 근거 보존(§5-0-1 · `n1 → n2`) ·
② 기권만 하는 모델(§5-0 · `p1 → p2`) · ③ 채점 결과 보존(§7-7 · §9) · ④ 속도(§6-1 · `c1 → c2`) ·
⑤ 시간 축과 유형 축 분리(§3-1-1 · `s3 → s4`). ①의 candidate·classification 쪽은 계약에 필드가
없어 위 표에 미결로 남겼다.

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
