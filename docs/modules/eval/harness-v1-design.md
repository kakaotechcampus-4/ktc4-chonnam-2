# Evaluation Harness v1 — 설계

> **Owner:** 김대원 (`eval`) · **작성일:** 2026-09-06
> **입력 버전:** Architecture v4 · Canonical Contract 14건(2026-09-06 기준) · `ownership.md` v2 · Mock Pack v1 Seed Mode(`12aee4d`)
> **상태:** Draft — 구현 착수 전 설계 확정본. 이 문서는 지표 정의를 소유하지 않는다(그것은 v4 §9와 `initial-evaluation-plan.md` §2).

이 문서가 정하는 것은 **하니스의 구조**다. 무엇을 계산하는가가 아니라, 어떻게 실행하고 무엇을 파일로 남기는가를 정한다.

---

## 1. v1 범위

| Stage | v1 | 근거 |
| --- | --- | --- |
| Candidate | 포함 — Recall@1/3/10 · span error · FP/clip | B tier |
| Classification | 포함 — recall_macro · precision_macro · 5×5 confusion(4종+NONE) · target correctness · 조건별 breakdown | A tier + B tier negative |
| Plate | **스키마와 scorer만.** 데이터 없음 → 결과는 `null` | C tier 미확보 |
| Timestamp · Fine · E2E · Efficiency | 제외 — v2 이후 | §9 후속 항목 |

`ownership.md` §3 김대원 ⑤의 산출물(「4종별 점수 + Classification(A tier) 지표」)이 v1로 충족된다.

---

## 2. 결정

### 2-1. prediction 파일은 원문과 정규화 뷰를 함께 담는다

`predictions/<run_id>.json`:

```json
{
  "meta": {
    "run_id": "run_20260906_001", "impl": "fake:always_correct", "impl_version": "v1",
    "stage": "candidate", "manifest": "b_youtube",
    "manifest_version": "m1", "clip_rule_version": "c1",
    "normalizer_version": "n1", "code_commit": "<sha>", "created_at": "<ISO8601>"
  },
  "raw": ["impl이 반환한 원문 그대로"],
  "normalized": [
    { "clip_id": "YT_0001_C08",
      "candidates": [ { "rank": 1, "t_start_sec": 14.8, "t_end_sec": 18.0,
                        "event_type": "SIGNAL", "score": 0.91 } ] }
  ]
}
```

**왜.** scorer는 `normalized`만 읽는다. 계약(B01~B09 접합 Pending)이 움직여도 scorer와 과거 결과가 살아남는다. 동시에 `raw`를 손실 없이 보존하므로 새 지표를 낼 때 유료 API를 다시 호출하지 않는다 — v4 §9-2가 prediction을 immutable로 둔 목적이 이것이다.

**대가.** 파일이 커지고 `normalizer_version`을 따로 관리해야 한다. 수용한다.

**실물로 확인된 근거.** Mock Pack v1의 `docs/mock/CONTRACT_CONFLICTS.md` §4가 계약 간 필드명 불일치를 새로 보고했다 — 같은 「이게 어떻게 끝났는가」를 `AnalysisRun`/`ReadoutRun`은 `outcome`, `JobExecution`/`TimeResolution`/`Observation`/`SpanResolution`은 `status`, `RequirementReport`는 `overall`로 부르고 값 공간도 제각각이다(`SUCCEEDED/PARTIAL/FAILED` vs `OK/NEEDS_REVIEW/…` vs `PASS/WARN/BLOCK/UNKNOWN` vs `COMPLETE/PARTIAL/FAILED`). scorer가 계약을 직접 읽는 구조였다면 이 불일치를 전부 떠안았을 것이다. 정규화 뷰를 두는 결정이 실물로 뒷받침된다.

**검토한 대안.**

- **계약 직결** (prediction = `AnalysisRun` 원문) — scorer가 계약에 직접 묶여, 접합부가 변경되면 과거 결과와의 비교가 끊긴다.
- **eval 중립 포맷만** — impl별 어댑터가 곧 구현을 아는 코드가 되어 `ownership.md` 김대원 ⑦(「공개 함수만 부른다」)의 취지에 어긋난다.

### 2-2. manifest는 tier 단위로 묶는다

```
manifests/b_youtube/    manifests/a_aihub/    (향후) manifests/c_team_sd/
```

§4-모듈7 ③이 tier별로 낼 지표를 이미 갈라놨다(「한 dataset이 모든 metric을 책임하지 않는다」). 소스는 tier 안에서 `source_video_id`로 구분한다.

소스 단위·실험 회차 단위 묶음은 채택하지 않는다 — 전자는 같은 tier의 집계가 흩어지고, 후자는 회차와 데이터 정체성이 섞인다.

### 2-3. `--impl`은 딕셔너리 레지스트리로 등록한다

`runners/registry.py`에 이름표 → 호출 가능 객체. entry_points·동적 로딩은 채택하지 않는다(6인 10주 규모에 과하다). 이름표가 그대로 `meta.impl`에 기록되어 결과 파일이 자기 출처를 말한다.

### 2-4. prediction은 두 종류가 공존한다 — 역할이 다르다

Mock Pack v1이 `data/mock/eval/prediction_{correct,wrong}.happy_001.json`을 이미 만들었다. 형태가 평평한 단일 객체라 위 envelope과 다르다. **둘을 통일하지 않고 역할로 나눈다.**

| | `data/mock/eval/prediction_*.json` | `eval/predictions/<run_id>.json` |
| --- | --- | --- |
| 무엇 | Mock E2E 접합 확인용 **샘플 1건** | runner 실행 산출물 **N건** |
| 생산자 | `case` Owner (Mock Pack) | eval runner |
| 형태 | 평평한 단일 객체 | `{meta, raw, normalized}` |
| 쓰임 | `ownership.md` §7-④ 기준 ⑤(「eval이 fixture를 읽어 결과 파일을 내는가」) | 실제 채점 |

scorer는 양쪽을 모두 읽을 수 있어야 하므로, **Mock Pack 형태를 `normalized`로 옮기는 어댑터를 하나 둔다**(`runners/normalize.py`의 별도 함수). Mock Pack 쪽 형식을 바꾸라고 요구하지 않는다 — 그건 `case` Owner의 산출물이고, 목적(접합 확인)에는 그 형태로 충분하다.

이 분리는 `ownership.md` §12의 Mock 검수표가 `eval / expected result` 검수를 eval Owner에게 둔 것에 따른 판단이다. `data/mock/expected/scenario_happy_001.expected.json`이 「Mock Runtime Output이 아니라 사람이 라벨링한 정답」이라고 스스로 명시해 GT와 Mock을 섞지 않은 점은 §4의 원칙과 일치하므로 그대로 수용한다.

### 2-5. runner는 GT를 모른다

가짜 구현만 GT 파일을 **스스로** 읽는다. runner가 GT를 impl에 전달하는 경로를 만들지 않는다 — 실제 구현에 정답이 새는 통로가 되기 때문이다. 가짜 구현은 `fake:` 접두어로 레지스트리에서 격리한다.

---

## 3. 구조

### 3-1. 폴더

```
eval/
├─ run.py  score.py            CLI 진입점 2개 (§9-2의 분리를 CLI에서 강제)
├─ runners/
│  ├─ registry.py              이름표 → 호출 가능 객체
│  ├─ normalize.py             impl 출력 → normalized 뷰
│  └─ impls/                   fake_always_correct.py · fake_always_wrong.py
├─ scorers/                    candidate.py · classification.py · plate.py
├─ manifests/                  b_youtube/ · a_aihub/
├─ datasets/                   gitignore. 아카이브 원본 + 추출된 샘플
├─ predictions/                커밋
└─ results/                    커밋
```

위는 **목표 구조**다. 현재 실물은 `manifests/set1/`(B tier)과 `manifests/02.라벨링데이터/`(A tier 아카이브)이며, `b_youtube/`·`a_aihub/`로의 이동은 구현 1단계에 포함한다.

### 3-2. 흐름

```
manifest + scope fixture
   ↓  python -m eval.run --impl <이름표> --stage <candidate|classification>
predictions/<run_id>.json                 immutable · 커밋
   ↓  python -m eval.score --prediction <run_id> --gt <gt_version>
results/<run_id>.<gt_version>.json        커밋 (§10-2 「Eval result: JSON + git」)
```

`AnalysisScope` fixture의 Producer는 eval이다(계약 정합성 감사 §4.1 ⑤). absolute anchor가 있는 고정 입력부터 만든다 — relative input(B08)과 timeline provenance(B09)가 미해결이라 해석이 갈린다.

---

## 4. 데이터

### 4-1. B tier — YouTube (확보)

55 클립(각 60초, 단일 원본 `YT_0001`) · CONFIRMED 이벤트 5건 · split 전부 DEV.

기존 라벨 구조를 그대로 승계한다: `manifest_version`/`clip_rule_version`/`gt_version` 3종 버전 · `sha256` · `source_video_id` 그룹 키 · `scoring: INCLUDED | BOUNDARY_EXCLUDED`.

### 4-2. A tier — AI-Hub (확보)

5,619 시퀀스 / 224,859 프레임. 위반유형이 v4 §3-5 baseline enum과 1:1 대응한다.

| AI-Hub | baseline enum | 시퀀스 |
| --- | --- | ---: |
| 신호위반 | `SIGNAL` | 2,065 |
| 중앙선침범 | `CENTER_LINE_CROSSING` | 1,767 |
| 진로변경위반 | `SOLID_LINE_LANE_CHANGE` | 1,375 |
| 안전모미착용 | `MOTORCYCLE_HELMET_NON_USE` | 412 |

프레임 라벨에 위반 차량 bbox와 `정상 차량` bbox가 함께 있어 **target correctness**가 계산된다. `condition`(Weather 4종 · 주야간 · roadType)이 균형적이어서 **조건별 breakdown**이 가능하다.

**샘플링이 GT의 일부다.** 5,619 시퀀스는 평가 규모가 아니다. `sequences.json`의 `meta.sampling`에 `rule_version`·`seed`·`strategy`·`per_type`을 기록해 어떤 시퀀스를 뽑았는지 재현 가능하게 한다. 51.4GB 아카이브는 풀지 않고 샘플링된 시퀀스만 추출한다.

**안전모 불균형** — 시퀀스당 3.7프레임(다른 유형은 38~53). 유형별 **시퀀스 수**를 맞춰 흡수하고, 프레임 단위 지표는 내지 않는다.

**`NONE` 클래스는 B tier negative 클립에서 만든다.** A tier는 전 시퀀스가 4종 중 하나여서 §9-3이 요구한 5×5를 자체적으로 못 채운다. GT 항목에 `source_tier`를 명시해 해상도·재인코딩 특성이 다르다는 사실을 결과가 스스로 말하게 한다.

### 4-3. A tier로 할 수 없는 것 — 번호판이 마스킹되어 있다

원본 이미지를 확인한 결과 위반 차량의 번호판이 **비식별 처리(블러/모자이크)** 되어 있다. 폭 900~1100px의 대형 bbox에서도 동일하다. 라벨에 번호판 객체가 없는 것은 누락이 아니라 원본에 정보가 없기 때문이다.

따라서 Plate 3종(Exact Plate Accuracy · Wrong Accept Rate · Abstention Recall)은 **A tier로 열 수 없다.** 전부 문자 정답을 요구한다. v4 §4-모듈7 ③이 Plate를 C tier(팀원 SD 원본)에 배정한 근거가 실측으로 확인됐다.

---

## 5. 결측·실패 처리

- **데이터가 없는 지표는 `0`이 아니라 `null` + 사유 문자열로 적는다.** 0으로 적으면 「성능이 나빴다」로 오독된다.
- `results.json`에 `coverage` 블록을 두어 무엇을 못 냈고 왜인지를 결과 파일이 스스로 설명한다.
- **`coverage`는 두 가지를 함께 적는다** — 「어떤 지표가 왜 `null`인가」와 「무엇을 채점에서 제외했는가」다. 후자는 지표가 전부 `null`이 아니어도 실린다(예: `BOUNDARY_EXCLUDED`로 제외한 사건 수, baseline enum 밖의 GT 라벨·예측 건수). 사유가 여럿이면 `"; "`로 잇는다. 이 규칙이 있어야 결과의 `n_events`와 GT의 `clips_with_events`가 어긋난 이유를 결과 파일만 보고 알 수 있다.
- **돌지 않은 stage의 블록도 키를 전부 채우고 값만 `null`로 둔다.** `{"coverage": "NOT_RUN — …"}`처럼 키를 빼면 `results/*.json`을 모으는 쪽이 「키가 없는 모양」과 「키가 `null`인 모양」을 따로 처리해야 한다. 아래 plate 무데이터 블록이 그 기준 모양이다.

```json
"plate": {
  "exact_accuracy": null, "wrong_accept_rate": null, "abstention_recall": null,
  "coverage": "NO_C_TIER_DATA — plate text GT 부재. A tier는 번호판 마스킹(§4-3)"
}
```

- **실패 분류 이름은 eval이 소유하지 않는다.** `modules/search/decisions/failure-taxonomy.md`와 `modules/readout/decisions/failure-taxonomy.md`를 참조하고, 미확정이면 `UNKNOWN`으로 둔다.
- **ref는 해석하지 않는다.** `input_ref`·자산 ref는 불투명 문자열로 통과시킨다(recording 계약 2건 미작성, B06~B09).

---

## 6. 테스트

- `fake:always_correct` → 모든 지표 만점, `fake:always_wrong` → 최저. **이것이 지표 계산의 검증이다**(`ownership.md` §3 김대원 ⑤).
- GT 불변식 pytest: `t_start < t_end` · span이 클립 길이 안 · `violation_type`이 baseline 4종 · `file_path` 존재 · `sha256` 일치.
- `experiment-guide.md` §14의 결정론적 검사 원칙을 따른다. CI는 아직 붙이지 않고 로컬 pytest로 돌린다.

---

## 7. 공개 / 비공개 분리

레포가 PUBLIC이고 `product-strategy.md` §6이 「세부 실패 사례와 Hard-negative 데이터셋」·「차량번호」를 비공개로 둔다. 그래서 GT를 둘로 나눈다.

| 커밋 (`*.manifest.json` · `gt/*.json`) | gitignore |
| --- | --- |
| `clip_id` · `sequence_id` · `source_video_id` | 번호판 문자열 (`*.private.json`) |
| `violation_type` · span · `label` | hard-negative가 어려운 이유 서술 (`*.private.json`) |
| `split` · `tier` · `condition` | 정확한 위치 (`*.private.json`) |
| `meta.coverage` (검토 실적) | 아카이브 원본 (`*.zip`) · 미디어 |
| | 중간 작업 파일 (`events_draft.json`) |

왼쪽만으로 v1 지표가 전부 계산된다. §6이 「집계된 성능 비교 결과」를 공개 가능으로 둔 것과 일치한다.

적용된 `.gitignore` 규칙:

```gitignore
eval/datasets/*
!eval/datasets/README.md
eval/manifests/**/*.zip
eval/manifests/02.라벨링데이터/
eval/manifests/**/*.private.json
eval/manifests/**/events_draft.json
```

### 7-1. 검토 실적은 GT가 소유한다

`targets: []`만으로는 **「검토해서 사건 없음」과 「아직 라벨하지 않음」이 구분되지 않는다.** FP/clip은 negative 클립에서 오탐을 세고, Classification의 `NONE` 클래스도 이 클립들에서 나오므로, 검토 사실이 확인되지 않으면 두 지표가 모두 흔들린다.

그래서 검토 실적을 GT의 `meta.coverage`에 둔다. 중간 작업 파일(`events_draft.json`)에만 있던 사실을 GT로 승격시킨 것이다.

```json
"meta": {
  "gt_version": "g1", "tier": "B", "stage": "candidate",
  "coverage": {
    "clips_total": 55, "clips_reviewed": 55, "clips_with_events": 5,
    "negatives_confirmed": true,
    "reviewed_by": "daewon", "reviewed_at": "2026-09-06"
  }
}
```

클립을 추가했는데 아직 검토하지 않은 것이 있으면 `clips_reviewed < clips_total`이 되어 **GT가 스스로 미검토 상태를 드러낸다.** §6의 불변식 테스트가 이 두 값과 실제 `items` 수를 대조한다.

---

## 8. 이미 적용한 보정

| 항목 | 내용 |
| --- | --- |
| enum 정정 | `LANE_CHANGE` → `SOLID_LINE_LANE_CHANGE` 9곳(`events.json`·`events_draft.json`·`gt_candidate.json`). v4 §3-5 baseline 위반이었고 `check_boundaries.py:131`이 아는 드리프트다 |
| 경로 정합 | 클립 55개를 `clips.json`이 선언한 `eval/datasets/youtube/clips/`로 이동. `file_path` 55건 전수 존재 · `sha256` 55건 전수 일치 확인 |
| 커밋 위험 차단 | `VL.zip`(247MB)이 커밋 대상이었다. `.gitignore`에 규칙 추가 |

`check_boundaries.py`는 `contracts/`만 훑으므로 `eval/manifests/`의 enum 드리프트를 잡지 못한다. §6의 GT 불변식 테스트가 이 공백을 메운다.

---

## 9. 후속 항목

| # | 항목 | 열리는 지표 | 필요한 것 | 담당 |
| --- | --- | --- | --- | --- |
| F1 | **C tier 확보**(팀원 SD 원본) | Plate 3종 · Timestamp source agreement | 실제 촬영 원본. 주차 차량 20~30장이면 Exact Accuracy·Abstention 검증 착수 가능 | 김대원 + 신유민(`readout`) |
| F2 | **Overlay time 라벨링** (v2) | Overlay OCR format / continuity | A tier 화면에 시각이 찍혀 있다. 사람이 읽어 입력 가능 | 김대원 |
| F3 | B tier 이벤트 5건 → 10~20건, 4종 채우기 | Recall@K 신뢰구간 · 4종별 breakdown | 라벨링 | 김대원 |
| F4 | Hard-negative 대조쌍 | Hard-negative FPR | 실선 침범 ↔ 점선 정상 변경 대조 라벨 | 김대원 |
| F5 | Fine / E2E / Efficiency stage | Fine Recall · HN-FPR · Final Recall@3 · 비용 | `search` 구현과 `UsageRecord` | 서어진 · 김준영 |
| F6 | **Plate 채점 로직 재구현** (v1은 branch를 아예 제거함) | Exact Accuracy · Wrong-Accept Rate · Abstention Recall (C tier) | F1의 C tier plate text GT | 김대원 |
| F7 | **후보 1건이 같은 클립의 GT 2건을 동시에 만족한다** | Recall@K의 정직성 | 1:1 배정(Hungarian 등) 또는 「매칭된 예측은 소비한다」 규칙 | 김대원 |
| F8 | **임계값 0.5 두 개를 실험으로 정한다** | target correctness · Recall@K의 민감도 | 임계값 sweep 실험 | 김대원 |
| F9 | `code_commit`이 구조적으로 직전 커밋을 가리킨다 | — (해석 규칙) | §5에 의미를 명시하거나 재생성 후 amend | 김대원 |
| F10 | `TARGET_OBJECTS`가 위반유형별로 좁혀져 있지 않다 | Classification target correctness의 GT 품질 | 유형별 대상 객체 매핑 | 김대원 |
| F11 | 형식이 깨진 예측 bbox에 카운터가 없다 | target correctness의 해석 가능성 | `n_invalid_bboxes` 카운터 + coverage 사유 | 김대원 |
| F12 | **`NONE` 클래스에 데이터 경로가 없다** | 5×5 confusion의 NONE 행·열 | A tier 시퀀스와 B tier negative 클립을 잇는 manifest | 김대원 |
| F13 | `check_invariants`가 `a_aihub`에서 돌지 않는다 | A tier GT 불변식 (candidate의 7종에 대응) | 시퀀스 manifest용 검사기 | 김대원 |

F2의 Overlay time은 A tier 화면에 시각이 남아 있어 라벨 비용이 낮지만, §9-4에 따라 **overlay 판독 정확도만** 채점하고 source agreement(메타데이터 vs 파일명 vs overlay 대조)는 C tier 몫으로 남긴다.

F6: v1의 `plate.score`는 한때 GT가 있는 경우의 계산 분기를 갖고 있었으나, 검증할 GT가 없어 그 분기는 한 번도 실행되지 않은 채로 이미 틀린 숫자를 내고 있었다(`wrong_accept_rate`의 분모에서 abstain 항목을 빠뜨려, 판독 불가 번호판에 대한 오탐을 0으로 보고). 못 쓰는 채로 남겨 두면 나중에 C tier를 잇는 사람이 검증됐다고 믿고 그대로 쓸 위험이 있어(CLAUDE.md §2, 미검증 코드는 없는 것보다 위험하다), 이 분기는 **비활성화가 아니라 삭제**했다(task-8 리뷰 Important 2). C tier로 재구현할 때는 `wrong_accept_rate`의 분모에 abstain 항목(판독 불가로 답이 없는 번호판)을 **포함**해야 한다 — 판독 불가 번호판에 대한 잘못된 인식이야말로 이 지표가 잡아야 할 오류이기 때문이다.

F7: `candidate.score`는 사건마다 독립으로 후보를 훑을 뿐 1:1 배정을 하지 않는다. 그래서 한 클립 안에 사건이 둘이면, 둘을 모두 덮는 넓은 예측 **하나**가 적중 2건으로 세어진다. 지금 B tier 사건 5건은 전부 다른 클립에 있어 실측이 흔들리지 않지만, 한 클립에 사건이 둘 이상 들어오는 순간 Recall@K가 **조용히 부풀어 오른다.** 그러므로 이 항목은 F3(사건 10~20건으로 확대)처럼 다중 사건 클립을 들여오는 후속 항목과 **같은 커밋에서** 고쳐야 한다. 나중에 따로 고치면 그 사이의 숫자가 전부 재계산 대상이 된다.

F8: 값 `0.5`가 두 곳에 있지만 **서로 무관한 임계값**이다 — `classification._TARGET_BBOX_IOU_THRESHOLD`는 bbox의 2-D 공간 IoU이고, `candidate.score`의 `iou_threshold`는 구간의 1-D 시간 IoU다. 같은 값인 것은 우연이며 함께 움직여야 할 이유가 없다. 둘 다 튜닝 대상으로 열어 둔다: 전자는 A tier bbox를 사람이 판정한 「맞다/아니다」와 대조해, 후자는 B tier 사건의 span 라벨 폭 편차를 재서 정한다.

F9: `_git_commit()`이 실행 시점의 HEAD를 읽고 산출물은 그 뒤에 커밋되므로, 커밋된 `predictions/`·`results/`의 `code_commit`은 **자기를 담은 커밋의 부모**를 가리킨다. 틀린 값이 아니라 「이 실행이 딛고 선 트리」다. 이 의미를 §5에 못 박거나, 산출물을 재생성해 같은 커밋에 amend 하는 절차를 규칙으로 삼는 두 가지 선택지가 있다. v1은 전자로 해석하고 값은 그대로 둔다.

F10: `eval/tools/sample_aihub.py`의 `TARGET_OBJECTS`는 위반유형과 무관한 전역 목록이다. 그래서 신호위반 시퀀스의 프레임에 중앙선침범용 대상 객체가 어노테이션돼 있으면 그 bbox를 target으로 가져간다. 실측으로 확인된 오류는 아직 없지만 GT 품질의 잠재 위험이며, F13의 A tier 불변식 검사기가 잡아야 할 후보다.

F11: `classification.score`는 baseline enum 밖의 **예측 라벨**은 세어서 `n_invalid_predictions`와 coverage에 적지만, 형식이 깨진 **예측 bbox**(길이가 4가 아닌 값)는 `_iou_2d`가 조용히 `0.0`으로 처리하고 아무 데도 적지 않는다. 지금은 치트 구현만 bbox를 내므로 닿지 않는 경로지만, 실제 분류기를 붙이는 순간 「bbox가 틀렸다」와 「bbox 형식이 깨졌다」가 같은 0점으로 섞인다. 라벨 쪽과 같은 모양의 `n_invalid_bboxes` 카운터를 그때 함께 만든다.

F12: §4-2가 `NONE`을 B tier negative 클립에서 만든다고 정했지만, A tier 시퀀스 manifest와 B tier 클립을 잇는 manifest가 아직 없다. 그래서 실제 데이터로 채점하면 5×5 confusion의 `NONE` 행과 열이 **전부 0으로 비어 있다.** 이걸 채울 것은 두 tier를 함께 나열하는 classification manifest(가칭 `manifests/ab_mixed/sequences.json`)이며, 항목마다 `source_tier`를 남겨 해상도·재인코딩 차이가 결과에 드러나게 한다.

F13: `a_aihub`에는 `clips.json`이 없어 `manifests_io.check_invariants`가 돌지 않는다(그 함수는 clip과 span을 전제한다). 대신 `tests/eval/test_sample_aihub.py`의 A tier GT 자기정합성 테스트가 커밋된 정답지만 검사한다. 시퀀스 단위 불변식 검사기는 F12의 manifest가 정해진 뒤에 만든다 — 지금 만들면 곧 바뀔 모양을 굳힌다.

---

## 10. 열린 결정 (이 문서가 채우지 않는다)

| 항목 | 왜 열려 있나 | 누가 닫나 |
| --- | --- | --- |
| `verify_visual(input_ref, target_hint?)` 시그니처 | `ownership.md` 서어진 ⑤의 미제출 산출물 | 서어진 |
| `input_ref`의 실제 모양 | recording 계약 2건 미작성(B06~B09) | 정철원 |
| A tier fixture의 impl 호출부 스키마 | 위 둘에 의존 | 서어진 · 정철원 |
| `locked_test` 개봉 횟수·승인 정책 | v4 §10-3 미결 | 김대원(운영 정책 제안) |

이 항목들은 **경로와 자리만** 스펙에 반영했다. 값을 채우지 않는다.

---

## 참조

`architecture/module-architecture.md` §2 원칙 8 · §3-5 · §4-모듈7 · §9 · §10-2 · RT7 · RT10 ·
`management/ownership.md` §3 김대원 · §7 ·
`management/contract-consistency-audit-2026-09-06.md` §4.1 ⑤ ·
`modules/eval/initial-evaluation-plan.md` §2 · §5 · `modules/eval/experiment-guide.md` §3 · §4 · §14 ·
`product/product-strategy.md` §6 · `architecture/contracts/adr/adr-analysis-scope.md`
