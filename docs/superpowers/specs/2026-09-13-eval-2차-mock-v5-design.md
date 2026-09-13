# `eval` 2차 완료 설계 — Mock Pack v5 기준

> **Owner:** 김대원(`eval`) · 작성 2026-09-13
> **입력 버전:** Mock Pack v5(develop `72e0e05`) · Architecture v4 · `analysis-run-candidate-event/v1.1`(2026-09-10 §4-1 Consumer—`eval` 정정) · `usage-record/v1.2` · `time-resolution/v1` · `plate-readout/v1.2` · `readout-run/v1`
> **체크리스트:** `docs/modules/eval/second-completion-checklist.md` — 이 스펙이 그 문서의 설계 근거다. 체크박스는 거기, 결정과 이유는 여기.
> **이 문서가 하는 일.** 2차에서 무엇을 왜 그렇게 만드는지를 정한다. 구현 순서와 단계별 검증은 후속 구현 계획이 맡는다.

---

## 1. 범위

Mock Pack v5를 받아 `eval` 하니스를 다음 상태로 만든다.

- 7개 시나리오 정답지가 `eval-expected/v2`로 존재하고 **공용 validator를 수정 없이 통과**한다
- `pytest tests/eval`이 **0 failed**
- candidate 매칭이 IoU가 아니라 **onset point error**로 동작한다
- **plate 채점 경로**와 **비용 지표 블록**이 열린다
- 결과 파일만으로 「어느 계약 · 어느 지표 정의 · 어느 예측」을 채점했는지 재현된다

**범위 밖**: 외부 입력 대기 항목(`YT_0001` 원본 URL·라이선스, 자료조사 6개 문서의 `[링크 필요]`), A/B tier 실측, `classification` stage 확장.

---

## 2. 설계를 바꾼 탐색 결과

설계 전 레포 실측에서 나온 사실 3가지다. 체크리스트 작성 시점의 전제 중 일부가 틀렸다.

### 2-1. 공용 validator §13은 교체하지 않아도 된다 — 체크리스트 #1-A 전제 오류

`data/mock/validate_mock_pack.py` §13(952~980줄)이 `expected/*.json`에 실제로 강제하는 것은 3개뿐이다.

```python
provisional_non_contract_schema == true          # v2도 유지하기로 이미 정함
metric_targets 가 비어있지 않을 것                 # ← 유일한 실질 장벽
walk_refs 로 모은 {kind, ref} 가 all_defined 안에 있을 것
```

`kind`는 **없으면 두 분기(`ALWAYS_CORRECT`/`DELIBERATELY_WRONG`)가 모두 건너뛴다.** 따라서 v2의 라벨 배열 이름을 `metric_targets`로 두면 **유소연님께 §13 교체를 요청하지 않고 현행 스크립트를 그대로 통과한다.**

이름 재사용은 끼워맞추기가 아니다. v2 내용이 실제로 「지표별 기대값 목록」이고, 1차에서 문제였던 것은 이름이 아니라 `actual_value` 사본이었다.

**대가:** §13이 라벨 *내용*을 검증하지는 못한다(비어있는지만 본다). 참값과 fixture의 일치 검사는 `tests/eval`이 책임진다 — §12.

### 2-2. `legibility`는 fixture 필드가 아니라 eval 소유 정답 라벨이다

`PlateReadout`이 싣는 것은 `observation.value` · `observation.status` · `abstained`뿐이다. `legibility`라는 필드는 계약에 없다. 즉 **「사람이 보면 읽히는가」는 eval이 새로 만드는 참값**이고, 사본 문제가 애초에 생기지 않는다.

그리고 재판독 케이스의 두 판독은 **입력이 서로 다르다**:

```
readout_p001_plate         source_profile: readout-native        value "17나28??"  status NEEDS_REVIEW  abstained=true
readout_p001_plate_reread  source_profile: readout-native-hires  value "17나2867"  status OK            abstained=false
```

체크리스트가 우려한 「UNREADABLE인데 재판독 성공」 모순은 **성립하지 않는다.** `legibility`가 (incident_clip, `source_profile`) 속성이므로 두 판독의 정답이 달라도 모순이 아니다. 따라서 판독 단위 배열은 편의가 아니라 **정확성 요구**이고, INITIAL의 abstain은 실패가 아니라 **정답**이다.

### 2-3. 비용 재료 실측 — 26행, 그리고 P2-9가 실제로 물린다

`UsageRecord`는 **26행**이다(체크리스트의 23은 v4 수치). `case_id` 집계 실측:

```
case_h001 938 · case_u001 756 · case_p001 728 · case_r001 630
case_e001 434 · case_rb001  84 · case_x001   0        합계 3570 KRW  (전 행 KRW)
run_ref_reason:  null 22 · DIRECT_NO_RUN 2 · RUN_NOT_PRODUCED 2
```

그리고 `happy_001`의 timeline이 **전후방 2소스 둘 다 `0~1200s`** 다. 1차 A절 P2-9(「전후방 2소스를 합산하지 않는다」)가 mock pack에서 실제로 물린다 — 합산 2400s vs union 1200s, **2배 차이**.

---

## 3. 관측된 fixture 지형

설계가 딛고 있는 사실. 전부 실측이다.

| scenario | common | recording | search | readout | case | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `happy_001` | O | O | O | O | O | O |
| `empty_001` | O | O | O | · | O | · |
| `plate_reread_001` | O | O | O | O | O | O |
| `correction_rerun_001` | O | O | O | O | O | O |
| `unknown_abstain_partial_001` | O | O | O | O | O | O |
| `infra_failure_001` | O | O | **·** | O | O | · |
| `relative_rebase_001` | O | O | O | · | O | · |

**두 음성이 서로 다른 이유로 음성이다** — 이 구분이 `fp_per_clip`의 분모를 정한다.

```
empty_001          search fixture 있음, candidates 0건   →  후보 없음   (분모 O)
infra_failure_001  search fixture 없음                   →  대상 아님   (분모 X)
```

예측 쪽 `representative_ms` 5건은 정답 onset과 정확히 일치한다: `candidate_h001` 312480 · `candidate_p001` 612000 · `candidate_r001` 930000 · `candidate_u001` 615000 · `candidate_rb001` 512000 (전부 `timeline_revision: 1`).

---

## 4. A. `scoring` 어휘 — 두 이름 유지

`BOUNDARY_EXCLUDED`(B tier 클립 경계에 걸침)와 `EXCLUDED`(참값 유형 없음)를 **둘 다 둔다.** scorer는 `INCLUDED`가 아닌 것을 거르되 **사유별로 세어 `coverage`에 각각 적는다.**

```python
included = [t for t in item["targets"] if t.get("scoring", "INCLUDED") == "INCLUDED"]
for t in item["targets"]:
    if t.get("scoring", "INCLUDED") != "INCLUDED":
        excluded_by_reason[t["scoring"]] += 1
```

**왜 이렇게.** 현행 `candidate.py:40`은 `BOUNDARY_EXCLUDED`만 제외하는데 `unknown_abstain_partial_001`의 라벨은 `EXCLUDED`다. 그대로 두면 참값 유형이 없는 사건이 채점 대상에 들어가 **영원히 맞출 수 없는 miss**가 되고 recall이 부당하게 낮아진다.

**버린 대안.** 「한 이름 + `exclusion_reason` 필드」는 scorer가 약간 단순해지지만, 제외 사유가 값이 아니라 부속 필드로 내려가 GT 파일에서 덜 보인다. 알려진 사유가 정확히 둘인데 확장 슬롯을 미리 파는 셈이기도 하다.

**결과 파일 요구.** 두 사유는 의미가 다르므로 합산하지 않는다. `coverage`가 `"EXCLUDED — 1건 제외(참값 유형 없음); BOUNDARY_EXCLUDED — 0건"` 식으로 갈라 적어야, 결과만 보고 `n_events`가 GT와 어긋난 이유를 읽을 수 있다.

---

## 5. B. `eval-expected/v2` — 7개 신설, 기존 2개 폐기

### 5-1. 형태

```jsonc
{
  "schema": "eval-expected/v2",
  "scenario_id": "scenario_plate_reread_001",
  "provisional_non_contract_schema": true,       // §13 통과 조건
  "metric_targets": [ /* metric 4종 */ ]
}
```

`metric` 4종: `candidate_onset` · `plate_readout` · `occurred_at` · `negative_clip`, 그리고 미채점 표시용 `not_scored`.

**값 복사 금지.** `true_text` · `onset_ms` · `occurred_at`은 **정답**이지 fixture 사본이 아니다. 1차 🟡(`actual_value` 동기화 검사)은 사본을 없애는 것으로 해소한다 — 비교 대상은 실행 시 ref로 역참조한다.

### 5-2. 음성·미채점을 명시적으로 적는다

`empty_001`과 `infra_failure_001`은 `targets: []`라 순진하게 만들면 `metric_targets`가 비어 **§13이 FAIL한다.** 해법은 빈 배열이 아니라 음성을 라벨로 적는 것이고, 이쪽이 모델링으로도 낫다 — 빈 배열은 「라벨을 아직 안 만들었다」와 구분되지 않는다.

```jsonc
// scenario_empty_001.expected.json
"metric_targets": [
  { "metric": "negative_clip",
    "ref": {"kind": "recording_timeline", "ref": "tl_e001"},
    "expected_event_count": 0 }
]

// scenario_infra_failure_001.expected.json
"metric_targets": [
  { "metric": "negative_clip", "ref": {"kind": "recording_timeline", "ref": "tl_x001"},
    "expected_event_count": 0 },
  { "metric": "not_scored", "scope": "plate",       "reason": "READOUT_INFRA_FAILURE" },
  { "metric": "not_scored", "scope": "occurred_at", "reason": "NO_TIME_RESOLUTION" }
]
```

`tl_e001` · `tl_x001`은 §13의 `all_defined`에 들어있다(`timeline_id`가 ID 수집 대상 — validator 312줄). ref는 해석된다.

### 5-3. 7개 파일의 정답값 (전부 실물 ref로 확인)

| scenario | `candidate_onset` | `plate_readout` | `occurred_at` |
| --- | --- | --- | --- |
| `happy_001` | `candidate_h001` · `SOLID_LINE_LANE_CHANGE` · 312480ms · rev1 · `INCLUDED` | `readout_h001_plate` READABLE `12가3456` | `tres_h001` `2026-08-24T18:05:12+09:00` |
| `empty_001` | — (`negative_clip` `tl_e001`) | — | — |
| `plate_reread_001` | `candidate_p001` · `SIGNAL` · 612000ms · rev1 · `INCLUDED` | `readout_p001_plate` **UNREADABLE** / `readout_p001_plate_reread` READABLE `17나2867` | `tres_p001` `2026-08-29T20:10:12+09:00` |
| `correction_rerun_001` | `candidate_r001` · `MOTORCYCLE_HELMET_NON_USE` · 930000ms · rev1 · `INCLUDED` | `readout_r001_plate` READABLE `34나7890` | **`tres_r001_v2`** `2026-08-27T13:13:00+09:00` |
| `unknown_abstain_partial_001` | `candidate_u001` · `violation_type: null` · 615000ms · rev1 · **`EXCLUDED`** | `readout_u001_plate` READABLE `88부1234` | `tres_u001` **`expected: null`** · `expected_status: NEEDS_REVIEW` |
| `infra_failure_001` | — (`negative_clip` `tl_x001`) | `not_scored` `READOUT_INFRA_FAILURE` | `not_scored` `NO_TIME_RESOLUTION` |
| `relative_rebase_001` | `candidate_rb001` · `CENTER_LINE_CROSSING` · 512000ms · rev1 · `INCLUDED` | `not_scored` `NO_PLATE_READOUT` | `not_scored` `USABLE_RELATIVE_ONLY` |

주의할 두 곳:

- **`correction_rerun_001`은 시각 해석이 2개다.** `tres_r001_v1`(NEEDS_REVIEW · 13:15:30)을 `tres_r001_v2`(OK · 13:13:00 · `user_corrected=true`)가 대체했다. 정답은 **v2**를 가리킨다. anchor 정정이므로 offset 930s는 그대로다.
- **`unknown_abstain_partial_001`의 `occurred_at` 정답은 「값 없음」이 아니라 「확정하면 오답」이다.** fixture `tres_u001`은 NEEDS_REVIEW 상태로 값(`2026-08-26T22:20:15+09:00`)을 싣고 있다. 시각 충돌이 보존된 상태가 정답이므로, 확정값을 낸 구현은 틀린 것이다. `expected: null` + `expected_status: NEEDS_REVIEW`로 적어 이 판정이 가능하게 한다.

### 5-4. 기존 2개 폐기

`eval_fixture_correct_001.json` · `eval_fixture_wrong_001.json`을 지운다. ID 비교 채점 모델이고, 「채점기가 오류를 잡는가」는 `fake_always_correct` / `fake_always_wrong` 두 impl이 실제 파이프라인을 통과시켜 이미 증명한다.

---

## 6. C. mock_pack impl 7개 확장 + GT 재생성 — #3과 #4를 합친다

**따로 하지 않는다.** 1개 시나리오로 재배선한 뒤 곧바로 7개로 넓히는 것은 같은 코드를 두 번 고치는 일이다.

### 6-1. impl

`SCENARIO = "scenario_happy_001"` 상수를 7개 리스트로 바꾸고, 소멸한 경로(`search/candidate_events.<suffix>.json`)를 계약 산출물 경로로 바꾼다.

```
data/mock/search/scenario_<id>.json
  → analysis_run_candidate_events[].candidates[]
     → {rank, event_type_hint, span.representative_ms, span.timeline_revision, ranking_score}
```

`infra_failure_001`은 search fixture가 없다. **「후보 없음」이 아니라 「대상 아님」으로 구분**해 예측 목록에서 빼고, 그 사실을 envelope에 남긴다. 둘을 뭉개면 음성 클립 1건이 분모에 잘못 들어간다.

**`normalize.from_candidate_events`가 `representative_ms`를 아예 싣지 않는다.** 현재 출력은 `{candidate_id, run_id, timeline_id, rank, t_start_sec, t_end_sec, event_type, score}`뿐이고, `mock_pack.run()`은 그중 5개만 예측으로 넘긴다. §7의 점 오차 매처가 쓸 값이 **파이프라인 어디에도 없다.** 둘 다 고쳐야 한다.

- `normalize.from_candidate_events` — `representative_sec`(= `span.representative_ms / 1000`)과 `timeline_revision`을 출력에 추가
- `mock_pack.run()` — 두 필드를 예측 항목에 실어 보낸다

`timeline_revision`이 필요한 이유는 `relative_rebase_001`이다. timeline이 revision 2개를 갖는데 candidate는 rev 1에 달려 있어, revision을 버리면 offset 512s가 어느 시간축의 512s인지 결과 파일만 보고 말할 수 없다.

### 6-2. GT

`eval/manifests/mock_pack/gt/gt_candidate.json`을 7개 항목으로 재생성한다.

- span `690.0~708.0` → **`t_onset_sec` 기준**으로 교체(§7)
- `derived_from`이 지금 **존재하지 않는 두 파일**을 가리킨다 — 실경로로 갱신
- `coverage.clips_total` 7 · `clips_with_events` 5 · 음성 1(`empty_001`) · 대상 아님 1(`infra_failure_001`)
- **순환성 경고는 유지한다** — 구간이 채점 대상 예측과 같은 fixture에서 왔다. mock tier recall은 파이프라인 통과 확인이지 성능 근거가 아니다

### 6-3. 부수 개명 — 남은 것은 `tests/eval/` 안 2건뿐

체크리스트가 4건을 적어 뒀으나 **실측하니 3건은 이미 끝났다.**

| 옛 이름 | 남은 위치 |
| --- | --- |
| `cand_h001` → `candidate_h001` | `tests/eval/test_mock_pack_contract.py` · `tests/eval/test_normalize.py` |
| `scenario_partial_001` → `scenario_unknown_abstain_partial_001` | `tests/eval/test_mock_pack_contract.py:26,165` |
| ~~`run_h001_search` → `run_h001`~~ | **레포 어디에도 없다** — 이미 개명됨 |
| ~~`PLATE_OCR` → `READOUT_PLATE`~~ | `eval/`·`tests/`·`data/mock/`에 없다. 회고 언급만 남았고 evidence 3차 리뷰가 PASS로 확인했다 |
| ~~`OVERLAY_OCR` → `READOUT_OVERLAY_TIME`~~ | 위와 같다. 남은 매치 `VIDEO_OVERLAY_OCR`·`OVERLAY_TIME_OCR`은 **다른 식별자**이고 개명 대상이 아니다 |

즉 개명은 **데이터가 아니라 테스트 쪽 작업**이다. `data/mock/`은 손대지 않는다.

죽은 경로 `candidate_events.*`가 남은 곳은 정확히 3파일이다 — `eval/runners/impls/mock_pack.py:7,50` · `eval/manifests/mock_pack/gt/gt_candidate.json:15` · `tests/eval/test_mock_pack_contract.py:110,136,156`.

### 6-4. 얻는 것

**`empty_001`이 pack 최초 음성 케이스**다. `fp_per_clip`이 `null`(`NO_NEGATIVE_CLIPS`)에서 처음으로 실제 값이 된다.

---

## 7. D. 매칭 규칙 교체 — IoU → onset point error

1차 매처를 점 오차로 바꾼다.

```python
matched = next((c for c in topk
                if c["event_type"] == vt
                and abs(c["representative_sec"] - t["t_onset_sec"]) <= tolerance_sec), None)
```

- **`_iou`는 삭제한다.** GT target에서 외연(`t_start_sec`/`t_end_sec`)이 없어지고 `t_onset_sec`만 남으므로 IoU는 **계산 자체가 불가능**해진다. 이 변경이 만든 고아이므로 지운다
- 보조 sanity 신호는 IoU가 아니라 **containment**다 — `pred.t_start_sec <= gt.t_onset_sec <= pred.t_end_sec`. coarse 창이 정답 시점을 품고 있는지를 `containment_rate`로 따로 낸다. 점 오차는 맞는데 창이 onset을 안 품으면 `search` 쪽 창 생성이 의심된다
- 결과 키 `span_error_sec` → **`onset_error_sec`**으로 개명한다. 이름이 구간 오차를 뜻하는 채로 점 오차를 담으면 결과를 읽는 사람이 반드시 오해한다
- `span_error_sec`의 이름·정의를 **onset 오차**로 정리하고 결과 파일에 명시한다. 현행 docstring은 「GT 시작 시각과의 절대 오차」라고 적혀 있어 새 정의와 어긋난다
- **근거**: `contract-analysis-run-candidate-event.md` §4-1 Consumer—`eval`(2026-09-10) — `span`은 coarse 후보 창이지 사건 외연이 아니다. span IoU는 폐기됐다. `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`
- **이 변경이 §9 `scorer_version`을 올리는 첫 계기다**

---

## 8. E. plate 채점 경로 신설

### 8-1. 배관

지금 `score.py:40`이 `plate.score(norm, None)`을 **stage와 무관하게 매번** 호출하고, 그 함수는 인자를 보지도 않고 전부 `null`을 반환한다. `run.py --stage` 선택지에 `plate`가 없다.

```
eval/runners/normalize.py            + from_plate_readouts()
eval/run.py                          --stage plate 추가 (_NORMALIZERS 키)
eval/manifests/mock_pack/gt/gt_plate.json   신설
eval/scorers/plate.py                GT 분기 재구현 (F6 해소)
```

**F6 교훈을 지킨다** — 검증할 GT가 없는 분기를 다시 만들지 않는다. 지금은 GT가 5건 있으므로 조건이 충족된다.

### 8-2. 판정

정답 판정은 **`abstained` × GT `legibility`** 교차표다.

| | GT READABLE | GT UNREADABLE |
| --- | --- | --- |
| `abstained=false` | `exact_match`: `observation.value` == `true_text` | **`wrong_accept`** |
| `abstained=true` | 놓친 판독 | **`abstention_recall` 적중** |

실측 분모: `exact_match` **4/4**(`happy` · `reread` · `u001` · `correction_rerun`) · `abstention_recall` **1/1**(`readout_p001_plate`) · `wrong_accept_rate` **0/1**.

### 8-3. 한계를 결과에 적는다 — plate도 순환적이다

**`exact_match` 4/4는 성능이 아니다.** `true_text`가 판독 결과(`observation.value`)에서 왔기 때문에 mock tier에서 이 값은 **구조상 만점일 수밖에 없다.** candidate 쪽에는 이미 GT `meta`에 순환성 경고가 있는데(§6-2) plate 쪽에는 없다 — **같은 경고를 `gt_plate.json`에도 넣는다.**

`wrong_accept_rate`의 **분자도 0건**이다. pack에 「확신에 차서 틀리게 읽은」 케이스가 없어 이 수치는 「우리 구현이 안전하다」는 증거가 **아니다.**

따라서 각 plate 라벨은 자신이 pack에서 파생됐는지를 **파일에 적는다.**

```jsonc
{ "metric": "plate_readout", "ref": {...}, "legibility": "READABLE",
  "true_text": "17나2867", "derived_from_pack": true }
```

지금은 5건 전부 `true`다. 나중에 독립 참값이나 「일부러 틀린」 fixture가 오면 그 라벨만 `false`가 되고, 그때 `exact_match`가 처음으로 의미를 갖는다. 이 플래그는 §12의 테스트 범위도 정한다.

`not_scored` 2건(`infra_failure` · `relative_rebase`)도 사유와 함께 `coverage`에 적는다.

---

## 9. F. 결과 envelope 누락 4건

| 파일 | 추가 | 막고 있던 것 |
| --- | --- | --- |
| `predictions/` | `contract_version` | 계약이 바뀐 전후의 결과가 구분되지 않는다 |
| `predictions/` | `processed_duration_sec` | 시간당 환산치를 결과 파일만으로 재현할 수 없다 |
| `results/` | `scorer_version` | **§7의 IoU→point error 전후가 파일상 구분되지 않는다** |
| `results/` | `prediction_ref` (경로 + sha256) | 예측을 덮어써도 결과가 그 사실을 모른다 |

그리고 `contract_version` 불일치 시 `score.py`가 **비교를 거부한다**(v4 §9-2 규칙 5를 코드로 강제). 지금은 근거값 자체가 결과에 없어 규칙을 강제할 수단이 없다.

`processed_duration_sec` 값은 **이 실행이 실제로 예측을 만든 시나리오들의 timeline union 합**이다(§10-1과 같은 계산). 대상 아님으로 뺀 시나리오는 분모에도 들어가지 않는다.

상세: `docs/modules/eval/research/version-fields-proposal.md` §3.

---

## 10. G. 비용 지표 블록

### 10-1. 계산

`eval/scorers/cost.py`를 신설하고 `score.py`에 `result["cost"]`를 더한다.

- **집계 키는 `case_id`** — `run_ref`가 아니다(`usage-record/v1.2` §9-2). STALE attempt row(`run_ref=null` · `RUN_NOT_PRODUCED` 2건)가 빠지지 않게 한다
- **분모는 timeline union** — `happy_001`의 전후방 2소스를 합산하지 않고(1200s), `relative_rebase_001`은 **최신 revision(rev 2)** 의 두 placement에서 gap `600~630s`를 뺀 1200s
- **분자와 분모를 같은 시나리오 집합으로 맞추고**, 그 집합을 `coverage`에 적는다

```
cost_per_case                case_id별 KRW 합
cost_per_source_video_hour   Σcost / (Σ union timeline sec / 3600)
```

### 10-2. 주의

- 전 26행이 KRW다. 통화가 섞이면 환산하지 말고 **거부한다** — 환율은 `pricing_context`에 귀속되지 eval이 정할 값이 아니다
- `case_x001`은 **0원**이다. 평균이 아니라 분포로 보이게 `cost_per_case`를 case별로 남긴다

---

## 11. H. `clip_id` 규약과 문서 문구

### 11-1. `scenario_id = clip_id` 유지 + 명문화

7개로 넓혀도 1:1이 깨지지 않는다 — 시나리오당 timeline이 1개다(`relative_rebase_001`은 같은 `tl_rb001`의 revision 2개). 규약을 유지하되 GT `meta.clip_id_convention`에 적는다. B tier는 `clip_id`가 실재하고 같은 scorer를 타므로, **결과 파일만 보고 어느 쪽인지 읽혀야 한다.**

### 11-2. 문서 2곳

- `docs/modules/eval/experiment-guide.md:483` — `OVERCONFIDENT`가 런타임 실패 이름들과 한 표에 있다. 층위(런타임 5 + 사후 분류 1) 한 줄 추가
- `docs/modules/eval/harness-v1-design.md:267`(F6) — **의미는 이미 맞다.** 원문이 「`wrong_accept_rate`의 분모에 abstain 항목**(판독 불가로 답이 없는 번호판)**을 포함해야 한다」라고 괄호로 풀어 뒀다. 고칠 것은 **용어**다 — 「abstain 항목」은 예측 쪽 어휘(`abstained=true`)인데 가리키는 대상은 정답 쪽 집합이라, 괄호를 못 보면 반대로 읽힌다. **「정답이 `UNREADABLE`인 항목」**으로 바꿔 §8-2 교차표·ADR §4.10과 용어를 맞춘다. 의미를 바꾸는 수정이 아니다

---

## 12. 테스트 전략

CI는 이 중 아무것도 돌리지 않는다. `.github/workflows/boundary-check.yml`이 도는 것은 `scripts/check_boundaries.py`와 `scripts/check_contract_fixtures.py`뿐이고 `pytest`도 `validate_mock_pack.py`도 없다. **2차 완료 판정은 로컬 실행 증빙으로 선다.**

§2-1에서 §13이 라벨 *내용*을 검증하지 못하기로 한 만큼, 그 자리를 `tests/eval`이 메운다.

**단 한 가지를 조심한다.** 「라벨 값 == fixture 값」을 무조건 단언하면 **mock impl이 항상 옳다고 못 박는 꼴**이 된다. 그러면 §8-3이 지적한 빈자리를 메울 「일부러 틀린」 fixture가 들어오는 순간 테스트가 먼저 깨져서, 정작 필요한 케이스를 테스트가 막는다. 그래서 등식 검사는 **`derived_from_pack: true`인 라벨에만** 건다.

| 검사 | 범위 | 무엇을 막나 |
| --- | --- | --- |
| ~~모든 `metric_targets[].ref`가 pack 안 객체로 해석~~ | — | **§13이 이미 한다**(`walk_refs`). 중복해서 짜지 않는다 |
| `legibility=READABLE`이면 `true_text`가 있고, `UNREADABLE`이면 없다 | 전체 | 라벨 자체의 앞뒤가 안 맞음 |
| `true_text` == 해당 `PlateReadout.observation.value` | **`derived_from_pack: true`만** | 파생 라벨이 원본과 조용히 갈라짐 |
| `candidate_onset.onset_ms` == 해당 candidate의 `span.representative_ms` | mock tier | GT 재생성 누락 (mock tier onset은 파생값이다 — §6-2) |
| `scoring` 값이 `INCLUDED`/`EXCLUDED`/`BOUNDARY_EXCLUDED` 안에 있음 | 전체 | 오타로 인한 조용한 제외 |
| 7개 시나리오 전부에 expected 파일이 있음 | 전체 | 파일 누락 |

`abstained` 값은 **단언하지 않는다.** 그것은 채점 대상이지 전제가 아니다 — §8-2 교차표가 판정할 값을 테스트가 미리 고정하면 `abstention_recall`과 `wrong_accept_rate`가 둘 다 무의미해진다.

```bash
python data/mock/validate_mock_pack.py     # 46+ files / 7 scenarios PASS 유지
python -m pytest tests/eval -q              # 목표: 0 failed
python -m eval.run --impl mock_pack:contracts --manifest mock_pack --stage candidate --run-id mock_e2e
python -m eval.run --impl mock_pack:contracts --manifest mock_pack --stage plate     --run-id mock_plate
python -m eval.score --prediction mock_e2e
python scripts/check_boundaries.py          # CI가 실제로 도는 검사
```

Windows에서 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`을 앞에 붙인다.

---

## 13. 완료 정의

7개 시나리오 정답지가 `eval-expected/v2`로 존재하고 **공용 validator를 수정 없이** 통과하며, `pytest tests/eval`이 **0 failed**이고, candidate 매칭이 onset point error로 동작하며, **plate 교차표와 cost 블록이 실제 수치를 내고**, 결과 파일만으로 「어느 계약 · 어느 지표 정의 · 어느 예측」을 채점했는지 재현할 수 있으면 2차 완료로 본다.

**완료 정의에서 제외:** 외부 입력 대기 항목(체크리스트 #11).

## 14. 순서

```
A 어휘  →  B expected 7개  →  C impl 7개 + GT 재생성(#3+#4)  →  D point error
      →  E plate 경로  →  F envelope  →  G cost  →  H 규약·문서
```

§12의 테스트는 B · C · E와 함께 붙인다. C 끝에서 `pytest tests/eval` **0 failed**를 찍는다. 각 단계 뒤 `validate_mock_pack.py`와 `pytest`를 둘 다 돌린다.

## 15. 관련 문서

- `docs/modules/eval/second-completion-checklist.md` — 이 설계의 체크박스
- `docs/modules/eval/first-completion-checklist.md` — 1차 판정(`seed-v0` 기준, `[v5 무효]` 표시 6곳)
- `docs/modules/eval/research/version-fields-proposal.md` §3 — envelope 누락 4건의 근거
- `docs/architecture/contracts/contract-analysis-run-candidate-event.md` §4-1 — span 의미와 point error
- `docs/architecture/contracts/contract-usage-record.md` §9-2 — `case_id` 정본 집계 키
