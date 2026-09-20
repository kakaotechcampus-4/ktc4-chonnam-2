# 평가용 정답지 스키마 — 자료조사 원문(v0.2)과 현행 대조

> **이 문서가 하는 일.** 8/31 회의에서 공유한 A tier(AI Hub) 평가용 정답지 스키마 **v0.2 원문을 보존**하고, 그 뒤 계약·구현이 바뀌면서 달라진 지점을 대조한다.
> **결정 문서가 아니다.** 현행 스키마의 authoritative source는 `eval/manifests/a_aihub/gt/gt_classification.json`(`gt_version: g1`)과 `eval/scorers/classification.py`다. 이 문서와 어긋나면 코드가 이긴다.
> **Owner:** 김대원(`eval`) · 원문 작성 2026-08-31 · 대조 갱신 2026-09-12

---

## 1. 원문 — v0.2 (2026-08-31, 그대로 보존)

**평가 형태**: 시퀀스(폴더) 1개 = 케이스 1건 → Gemini에 프레임 순서대로 입력 → 5지선다 분류

```yaml
case:
  case_id: SIG_RED_LEFT-20230222-0000000001
  source_path: 신호위반/적색신호시좌회전/20230222_적색신호시좌회전_0000000001
  frames: [..._01.jpg, ..._02.jpg, ...]   # 순번 오름차순 = 입력 순서
  n_frames: 17

  # ── 채점 정답 ──
  gt_label: SIGNAL | CENTER_LINE_CROSSING | LANE_CHANGE | MOTORCYCLE_HELMET_NON_USE | NONE
  gt_label_source: FOLDER | DERIVED_NONE

  # ── 두 출처 병기 (정답지는 판단 안 함) ──
  label_folder: SIGNAL              # 폴더명 = 처분 결과
  label_annotation: SIGNAL          # 위반 클래스 존재 여부로 도출
  label_conflict: false

  # ── 부가 채점 ──
  onset_frame: 4                    # 라벨 플립 프레임. NONE이면 null
  violation_target_bbox: [584,412,693,496]   # onset_frame의 위반 차량
  n_violation_targets: 1
  n_normal_targets: 3               # 같은 프레임 정상 차량 = hard-negative

  # ── NONE 케이스 전용 ──
  none_type: null | TRUNCATED_PRE_ONSET | NO_VIOLATION_LABEL | OTHER_TYPE

  # ── 분할·층화 ──
  group_key: 20230222__SIG_RED_LEFT
  split: dev | locked
  subtype_code: SIG_RED_LEFT
  weather: 맑음
  daynight: 주간
  road_type: 일반도로

  unjudgeable: false
  unjudgeable_reason: null
```

### NONE 케이스 3종 (원문)

| `none_type` | 만드는 법 | 무엇을 재나 |
| --- | --- | --- |
| `TRUNCATED_PRE_ONSET` | 플립 이전 프레임만 남김 | 위반 직전을 위반이라고 하는가 |
| `NO_VIOLATION_LABEL` | 위반 차량 라벨이 0프레임인 시퀀스 (`_0000000003` 유형) | 신고됐지만 화면에 안 보이는 케이스 |
| `OTHER_TYPE` | 다른 종 시퀀스 (해당 종 질문에 대해서만 NONE) | 종 간 혼동 |

`OTHER_TYPE`은 5지선다로 한 번에 물으면 자동으로 생긴다. 별도 생성 불필요.

### 채점 항목 3개 (원문)

| 지표 | 계산 | 단위 |
| --- | --- | --- |
| `label_acc` | 5×5 혼동행렬. 종별 분리 + macro 평균 | case |
| `onset_frame_error` | `\|pred − onset_frame\|`. median / p90 / ±2프레임 이내 비율 | 맞힌 case |
| `target_correct` | 예측 대상이 `violation_target_bbox`와 일치 | 맞힌 case |

**절대 금지**: 이 정확도를 제품 성능으로 발표. 위반 시퀀스만 모은 폴더라 base rate가 인위적이다.

### 실행 시 인자 (원문)

```bash
--polarity-rule folder_wins | annotation_wins | agree_only
--none-ratio 0.2          # NONE 케이스 비율. 결과에 필수 기록
--frames-per-case 25|8    # 샘플링
```

`--none-ratio`가 곧 base rate라 **기록 안 된 결과는 해석 불가**다.

### 설계 이유 3개 (원문)

- **시퀀스 = 1건** — 4종 중 셋이 시간 순서로 정의된다. 프레임 1장은 최소 단위가 안 된다.
- **`label_folder` / `label_annotation` 병기** — `_0000000003`처럼 둘이 다른 경우가 실재한다. 정답지는 둘 다 기록만 하고 판정은 실행 인자로.
- **시간은 프레임 인덱스.**

---

## 2. 현행 대조 (2026-09-12)

### 2-1. 이름이 바뀐 것 — 원문대로 쓰면 어긋난다

| v0.2 | 현행(`g1`) | 비고 |
| --- | --- | --- |
| `gt_label: ... LANE_CHANGE ...` | **`SOLID_LINE_LANE_CHANGE`** | baseline enum은 `module-architecture.md` §3-5의 4종(사본 `eval/enums.py`). `LANE_CHANGE`로 쓰면 **5×5 혼동행렬이 조용히 어긋난다** |
| `case_id` | `sequence_id` | `sequences.json`·`gt_classification.json` 양쪽 동일 |
| `gt_label` | `label` | |
| `violation_target_bbox` | `target_bbox` | 원본 라벨에 위반 차량 bbox가 없는 시퀀스 5건은 `null`이고 채점 분모에서 제외한다 |
| `n_normal_targets` | `distractor_count` | |
| (없음) | `target_frame` | bbox를 딴 프레임의 **파일명**. v0.2의 `onset_frame`(정수 인덱스)과 다른 개념이다 |
| `weather` / `daynight` / `road_type` 평면 | `condition: {weather, day_night, road_type}` 중첩 | |
| `subtype_code: SIG_RED_LEFT` | `sub_type: 중앙선주황색실선위반` | 원본 한글 폴더명을 그대로 쓴다. 코드화하지 않았다 |
| `source_path` · `frames[]` · `n_frames` | `archive` · `archive_path` · `frame_count` (`sequences.json`) | 프레임 목록은 zip 인덱스에서 매번 푼다. 정답지가 파일명을 복제하지 않는다 |
| (없음) | `source_tier: A` | 해상도·재인코딩 특성이 다르다는 사실을 결과가 스스로 말하게 한다 |

### 2-2. 의미가 바뀐 것

**① `onset_frame` — A tier에서 빠지고 candidate 단계 지표로 자리를 옮겼다.**
`g1`에는 onset이 없다. 대신 2026-09-10에 `CandidateEvent.span` 의미가 **coarse 후보 창**으로 확정되면서(`docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`), coarse localization 지표가 **`|representative_ms − gt_onset_ms|` point error**로 계약에 등재됐다(`contract-analysis-run-candidate-event.md` §4-1 · Consumer—`eval`). span IoU는 1차 매처에서 폐기됐다.
즉 v0.2의 「시간은 프레임 인덱스」·onset 오차 발상은 살아남았고, **적용 지점이 A tier 분류가 아니라 candidate 단계로 옮겨간 것**이다. A tier에 onset을 되살리려면 프레임 인덱스 → ms 매핑이 필요한데 현재 manifest에 프레임 간격이 없다.

**② NONE 케이스 3종 — A tier로는 만들 수 없다(실측 확인).**
`harness-v1-design.md` §4-2: 「`NONE` 클래스는 B tier negative 클립에서 만든다. A tier는 전 시퀀스가 4종 중 하나여서 §9-3이 요구한 5×5를 자체적으로 못 채운다.」 따라서 v0.2의 `TRUNCATED_PRE_ONSET`·`NO_VIOLATION_LABEL` 생성안은 **미채택**이고 `none_type`·`--none-ratio`도 구현하지 않았다. `OTHER_TYPE`(종 간 혼동)은 원문 설명대로 5지선다에서 자동으로 생긴다.

**③ 지표 이름.**

| v0.2 | 현행(`eval/scorers/classification.py`) |
| --- | --- |
| `label_acc` (5×5 + macro) | `confusion`(5×5) · `recall_macro` · `precision_macro` · `recall_by_label` |
| `target_correct` | `target_correctness` — bbox가 `null`인 GT 항목은 **분모에서 제외**(미탐으로 세지 않는다) |
| `onset_frame_error` | 미구현 (위 ①) |

### 2-3. 미채택·미구현으로 남은 것

- **`label_folder`/`label_annotation` 병기 · `label_conflict` · `--polarity-rule`** — `g1`은 `label` 단일이다. 샘플링이 폴더 기준(type-stratified, seed `20260906`, 종당 30개)이라 두 출처가 갈리는 `_0000000003` 유형이 표본 120건에 들어오지 않았다. **원문의 문제의식은 유효하다** — 충돌 케이스를 표본에 넣는 순간 다시 필요해진다.
- `group_key`(그룹 누수 방지) · `unjudgeable` / `unjudgeable_reason` · `split`의 `locked` 값(현재 전부 `DEV`).
- `--frames-per-case` — 샘플러 인자는 `--per-type`·`--seed`뿐이다(`eval/tools/sample_aihub.py`).

### 2-4. 그대로 유효한 것

- **시퀀스 = 1건**(프레임 1장은 최소 단위가 아니다) — 현행 manifest·정답지·채점기 전부 시퀀스 단위다.
- **base rate 경고** — 「이 정확도를 제품 성능으로 발표 금지」. 현행에서도 같은 이유로 성능 근거는 가짜 구현 2종(`fake_always_correct`/`fake_always_wrong`)의 점수 대비에서 나온다.
- ~~조건별 분리 집계(날씨·주야·도로)~~ — `by_condition.day_night`으로 일부 구현했다가 **철회했다**(`cl2`, 2026-09-20). AI-Hub 71555의 조명·날씨 라벨이 클립 안에서 갈려 무작위에 가까웠다. 근거·판단은 `metrics/metric-definitions.md` §4-4. **원문의 문제의식은 유효하다** — 재려면 라벨이 새로 필요하다.

---

## 3. 현행 스키마 (authoritative는 코드)

```jsonc
// eval/manifests/a_aihub/gt/gt_classification.json — gt_version "g1"
{
  "sequence_id": "20230222_중앙선주황색실선위반_0000005763",
  "label": "CENTER_LINE_CROSSING",          // SIGNAL | CENTER_LINE_CROSSING | SOLID_LINE_LANE_CHANGE | MOTORCYCLE_HELMET_NON_USE | NONE
  "target_bbox": [0, 542, 103, 678],        // null 가능 (원본 라벨에 위반 차량 bbox 부재)
  "target_frame": "..._003.jpg",
  "distractor_count": 1,
  "condition": { "weather": "흐림", "day_night": "주간", "road_type": "일반도로" },
  "source_tier": "A"
}
```

커버리지(`meta.coverage`): 120 시퀀스 · `target_bbox` 있는 항목 115건 · 샘플링 규칙 `s1` · seed `20260906`.

---

## 4. 출처

> **[작성 필요]** 원문 자료조사에 쓴 출처 링크를 여기에 남긴다 — 이번 정리의 목적이 출처 유실 방지다.

- AI Hub 데이터셋 원본 페이지 — `[링크 필요]`
- 데이터셋 라벨 명세/구축 가이드 — `[링크 필요]`
- 위반 유형 정의의 근거(도로교통법 조문·경찰청 자료 등) — `[링크 필요]`

---

## 5. 관련 문서

- `docs/modules/eval/harness-v1-design.md` §4 — tier별로 열 수 있는 지표와 못 여는 지표(A tier 번호판 마스킹 포함)
- `docs/modules/eval/research/architecture-input-memo.md` — v4 작성 근거가 된 압축 메모
- `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md` — onset point error 확정
- `eval/manifests/a_aihub/` · `eval/scorers/classification.py` — 현행 구현
