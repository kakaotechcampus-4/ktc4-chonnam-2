# 김대원 (`eval`) 2차 완료 체크리스트 — Mock Pack v5 기준

> **입력 버전:** Mock Pack v5(develop `72e0e05`) · Architecture v4 · `analysis-run-candidate-event/v1.1`(2026-09-10 §4-1·Consumer—`eval` 정정) · `usage-record/v1.2` · `case-view/v1.3` · `readout` failure-taxonomy(PR #27)
> **1차:** `first-completion-checklist.md` — 판정은 `seed-v0` 기준이며 그대로 둔다. 경로가 죽은 6곳에 `[v5 무효]` 표시만 달려 있다.
> **작성 2026-09-13**

---

## 0. 지금 상태 (사실)

```
python data/mock/validate_mock_pack.py   46 files / 7 scenarios  PASSED (exit 0)
python -m pytest tests/eval -q            6 failed · 75 passed · 6 skipped
```

- 실패 6건은 전부 **구 경로·구 식별자**다. 하니스 본체는 통과한다.
- **CI는 이 실패를 잡지 않는다.** `.github/workflows/boundary-check.yml`이 도는 것은 `scripts/check_boundaries.py`(의존 방향)와 `scripts/check_contract_fixtures.py`(계약 fixture 디렉터리)뿐이고, `pytest`도 `validate_mock_pack.py`도 CI에 없다. 즉 **2차 완료 판정은 로컬 실행 증빙으로만 선다.**
- **v5는 eval 라벨 값을 바꾸지 않았다** — 아래 #2 표가 v4와 동일하다.

---

## 1. 착수 전에 풀어야 하는 것 — 그냥 진행하면 깨진다

### #1-A. 공용 validator가 구 `expected/` 스키마를 강제한다 — **의존 있음(유소연)**

`data/mock/validate_mock_pack.py` §13(952~980줄)은 `expected/*.json` **전부**에 대해 이렇게 검사한다.

```python
if not doc.get("provisional_non_contract_schema"): err(...)
targets = doc.get("metric_targets", [])
if not targets: err(f"[EVAL] {name}: metric_targets is empty")
kind_label = doc.get("kind")   # ALWAYS_CORRECT / DELIBERATELY_WRONG 규칙
```

새 스키마 `eval-expected/v2`에는 `metric_targets`도 `kind`도 없다. **7개 파일을 넣는 순간 `[EVAL] ...: metric_targets is empty` 7건으로 validator가 FAIL한다.**

- [ ] 결정: (a) 새 스키마에 맞게 §13을 교체 요청 — `expected/`는 eval 소유이고 소유권은 이슈 #22 B-1에서 확인됐다 / (b) 스크립트 수정 전까지 새 파일을 `expected/`가 아닌 곳에 두고 나중에 옮긴다
- [ ] (a)면 대체 검사 3건을 함께 제안한다 — ① 모든 ref가 pack 안 객체로 해석될 것(현행 `walk_refs` 재사용) ② `legibility=READABLE`이면 `true_text` == 해당 `PlateReadout.observation.value` ③ `legibility=UNREADABLE`이면 그 판독의 `abstained=true`
- [ ] `provisional_non_contract_schema: true`는 새 스키마도 유지한다(현행 검사 통과)

### #1-B. `scoring` 어휘가 scorer와 어긋난다 — **혼자 해결 가능**

`eval/scorers/candidate.py:40`은 `BOUNDARY_EXCLUDED`만 제외한다.

```python
included = [t for t in item["targets"] if t.get("scoring") != "BOUNDARY_EXCLUDED"]
```

그런데 `unknown_abstain_partial_001`의 라벨은 **참값 유형이 없어 `EXCLUDED`**다. 그대로 두면 u001이 채점 대상에 포함돼 **참값 없는 사건이 miss로 잡히고 recall이 부당하게 낮아진다.**

- [ ] 어휘 결정: `EXCLUDED`(사유 필드 동반) 하나로 통일할지, `BOUNDARY_EXCLUDED`(B tier 경계)와 `EXCLUDED`(참값 없음)를 둘 다 둘지
- [ ] scorer의 제외 조건과 `coverage` 문구를 그 결정에 맞게 고친다 — **제외 사유가 결과 파일에 남아야 한다**(둘은 제외 이유가 다르다)

---

## 2. `expected/` 7개 신설 + 기존 2개 폐기

- [ ] `eval_fixture_correct_001.json` · `eval_fixture_wrong_001.json` 폐기 — ID 비교 채점 모델이고, 「채점기가 오류를 잡는가」는 `fake_always_correct`/`fake_always_wrong` 두 impl이 실제 파이프라인을 통과시켜 이미 증명한다
- [ ] `data/mock/expected/<scenario_id>.expected.json` 7개 신설 — 스키마 `eval-expected/v2`, **값 복사 금지**(`readout_ref`·`resolution_ref`·`timeline_ref` 참조만). 사본을 없애는 것이 1차 🟡(`actual_value` 동기화 검사)의 해소안이다
- [ ] plate 라벨은 **판독 단위 배열** — `legibility`는 (clip, `source_profile`) 속성이라 시나리오당 하나면 「UNREADABLE인데 재판독 성공」이 모순으로 보인다

**라벨 값 (v5 기준, v4와 동일 — 확인 완료)**

| 시나리오 | candidate (type · onset · rev) | plate | time |
| --- | --- | --- | --- |
| `happy_001` | `SOLID_LINE_LANE_CHANGE` · 312.48s · 1 | READABLE `12가3456` | `2026-08-24T18:05:12+09:00` |
| `empty_001` | `targets: []` — **음성 케이스**(`fp_per_clip` 분모) | 없음 | 없음 |
| `plate_reread_001` | `SIGNAL` · 612.00s · 1 | INITIAL UNREADABLE / REREAD READABLE · 참값 `17나2867` | `2026-08-29T20:10:12+09:00` |
| `correction_rerun_001` | `MOTORCYCLE_HELMET_NON_USE` · 930.00s · 1 | READABLE `34나7890` | `2026-08-27T13:13:00+09:00` (USER_OVERRIDE — anchor 정정이므로 offset 930s 유지) |
| `unknown_abstain_partial_001` | 615.00s · 1 · **`EXCLUDED`**(참값 유형 없음, #1-B) | READABLE `88부1234` | `null` (시각 충돌 보존) |
| `infra_failure_001` | `targets: []` | `not_scored.plate = READOUT_INFRA_FAILURE` | `null` (v5에서 overlay 2건 추가됐으나 둘 다 `UNKNOWN`·value null) |
| `relative_rebase_001` | `CENTER_LINE_CROSSING` · 512.00s · 1 | 없음 | `null` (`USABLE_RELATIVE_ONLY`) |

---

## 3. 접합부 재배선 — 완료 판정 `pytest 0 failed`

- [ ] `eval/runners/impls/mock_pack.py` — `search/candidate_events.<suffix>.json` → `search/scenario_<id>.json`의 `analysis_run_candidate_events[].candidates[]`
- [ ] `eval/runners/normalize.py` `from_mock_pack` — 소멸한 `data/mock/eval/prediction_*.json` 경로 정리
- [ ] `eval/manifests/mock_pack/gt/gt_candidate.json` — span 690~708초 → **onset 312.48초** 기준 재생성, `derived_from` 경로 갱신(현재 존재하지 않는 두 파일을 가리킨다)
- [ ] `tests/eval/test_mock_pack_contract.py` — `scenario_partial_001` → `scenario_unknown_abstain_partial_001`, `<scenario>.expected.json` 경로
- [ ] 식별자 개명 반영 — `cand_h001`→`candidate_h001` · `run_h001_search`→`run_h001` · `PLATE_OCR`→`READOUT_PLATE` · `OVERLAY_OCR`→`READOUT_OVERLAY_TIME`

## 4. mock manifest를 7개 시나리오로 확장 — **신규**

지금 `mock_pack.py`는 `SCENARIO = "scenario_happy_001"` 상수 하나이고 GT도 1건, `clips: []`다. 7개로 넓히면 얻는 것이 분명하다.

- [ ] `mock_pack` impl이 7개 시나리오를 순회한다 (search fixture가 없는 `infra_failure_001`은 「후보 없음」이 아니라 **대상 아님**으로 구분)
- [ ] GT `gt_candidate.json`을 7개 항목으로 재생성
- [ ] **`empty_001`이 pack 최초 음성 케이스**다 — `fp_per_clip`이 `null`(`NO_NEGATIVE_CLIPS`)에서 처음으로 실제 값이 된다
- [ ] 순환성 경고는 유지 — mock tier recall은 파이프라인 통과 확인이고 성능 근거가 아니다

## 5. 매칭 규칙 교체 (IoU → point error)

- [ ] `eval/scorers/candidate.py` — 1차 매처를 `abs(representative_ms − gt_onset_ms) <= tolerance`로 교체
- [ ] span containment(`start_ms <= gt_onset <= end_ms`)는 **보조 sanity 신호로만** 남긴다
- [ ] `span_error_sec`의 이름·정의를 onset 오차 의미로 정리하고 결과 파일에 명시
- [ ] 근거: `contract-analysis-run-candidate-event.md` §4-1 · Consumer—`eval`(2026-09-10) · `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`
- [ ] **주의:** 이 변경이 #7 `scorer_version`을 올리는 첫 계기다

## 6. plate 채점 경로를 열 것인가 — **결정 필요(신규)**

`#2`가 참값(`17나2867`)과 `legibility`를 만들지만, **지금은 그걸 소비할 경로가 없다.**

- `eval/run.py`의 `--stage` 선택지는 `_NORMALIZERS` 키뿐이다 — `candidate` · `classification`. **plate stage가 없다.**
- `eval/score.py`는 `plate.score(norm, None)`을 무조건 호출하고, 그 함수는 항상 `null` + `NO_C_TIER_DATA`를 반환한다(GT 계산 분기는 F6에서 삭제됨).

- [ ] 결정: (a) mock tier plate 지표를 연다 — `abstention_recall`·`wrong_accept_rate`·`plate_exact_match_rate`의 **배관을 1건으로 검증**할 수 있다 / (b) C tier까지 계속 `null`로 둔다
- [ ] (a)면 plate stage 추가 + `plate.score`에 GT 분기 재구현. **F6 교훈을 지킨다** — 검증할 GT가 없는 분기를 다시 만들지 않는다. 지금은 GT가 1건이라도 있으므로 조건은 충족된다
- [ ] 어느 쪽이든 **분자가 0건**이라는 한계를 결과 `coverage`에 적는다 — pack에 「확신에 차서 틀리게 읽은」 케이스가 없어 `wrong_accept_rate`는 `0/1`로 나온다

## 7. 결과 envelope 누락 4건

- [ ] `predictions/`에 `contract_version` · `processed_duration_sec` 추가
- [ ] `results/`에 `scorer_version` · `prediction_ref`(경로 + sha256) 추가
- [ ] `contract_version` 기준으로 「버전이 다르면 비교 거부」(v4 §9-2 규칙 5)를 코드에서 강제 — 지금은 근거값 자체가 결과에 없다
- [ ] 근거·상세: `research/version-fields-proposal.md` §3

## 8. 비용 지표를 열 것인가 — **결정 필요(신규)**

결과 파일에 cost 블록이 없다. 그런데 재료는 이미 다 있다 — mock pack에 `UsageRecord` 23행, 정본 집계 키 `case_id` 확정(`usage-record/v1.2`), KRW 정규화 완료(9건 ×1400 검증), `run_ref_reason`으로 실패 attempt까지 구분된다.

- [ ] 결정: `cost_per_case`(mock tier)만 먼저 열지, `cost_per_source_video_hour`까지 갈지
- [ ] 후자면 분모는 **중복 제거한 사건 timeline 길이**다 — 전후방 2소스를 합산하지 않는다(1차 A절 P2-9 확정)
- [ ] `run_ref`가 아니라 `case_id`로 집계한다 — STALE attempt row(`run_ref=null`·`RUN_NOT_PRODUCED`)가 빠지지 않게

## 9. `clip_id` ↔ `scenario_id` / `timeline_id` 대응 — **미결(신규)**

`mock_pack.py` 독스트링이 「계약은 `timeline_id` + 밀리초 offset으로, 정답지는 `clip_id`로 위치를 말하는데 그 대응을 아직 어느 계약도 정하지 않았다」고 남겨둔 항목이다. 시나리오 1건일 때는 `scenario_id`를 `clip_id`로 취급해 우회했지만 **#4에서 7개로 넓히면 우회가 계속 유효한지 다시 봐야 한다.**

- [ ] mock tier에서 `scenario_id = clip_id` 규약을 그대로 유지할지 결정하고, 결정했으면 정답지 `meta`에 그 규약을 명시한다
- [ ] B tier(`clip_id` 실재)와 mock tier(시나리오)가 같은 scorer를 타므로, 규약이 결과 파일만 보고 읽히게 한다

## 10. 내 문서 문구 2곳

- [ ] `docs/modules/eval/experiment-guide.md:483` — `OVERCONFIDENT`가 런타임 실패 이름들과 한 표에 있다. 층위(런타임 5 + 사후 1) 한 줄 추가
- [ ] `docs/modules/eval/harness-v1-design.md:267`(F6) — 「`wrong_accept_rate` 분모에 abstain 항목 포함」이 `abstained=true`를 넣으라는 뜻으로 읽힌다. 「정답이 `UNREADABLE`인 항목」으로 정정(ADR §4.10 정의와 같은 뜻)

## 11. 외부 입력 대기 — 완료 정의에서 제외

- [ ] `eval/manifests/b_youtube/clips.json`에 `source_url`·`license` 추가 — **`YT_0001` 원본 URL·라이선스 표기 필요**
- [ ] 자료조사 6개 문서의 `[링크 필요]` 채우기 — AI-Hub 71555 상세/이용조건/일반 이용정책/구축 설명서, 제조사 매뉴얼 5종
- [ ] `research/blackbox-storage-survey.md`는 **출처 0건이라 현재 인용 금지** 상태다

## 12. v5 신규 검수 — 조치 없음 (확인 완료)

- [x] v5가 eval 라벨 값을 바꾸지 않았다 — onset 5건·참값·abstain 상태 전부 v4와 동일
- [x] `validate_mock_pack.py` 46 files · 7 scenarios PASS (validator +170줄 보강 포함)
- [x] `infra_failure_001`에 overlay 판독 2건이 추가됐으나 둘 다 `UNKNOWN`·value null → 라벨 `time: null` 유지
- [x] `correction_rerun_001`의 `verification=AGREED`는 evidence 소유 미결(4차 공지 🔴 1건)이며 내 시각 라벨(13:13:00)에 영향 없음

---

## 2차 완료 정의

> 7개 시나리오 정답지가 `eval-expected/v2`로 존재하고 공용 validator를 통과하며, `pytest tests/eval`이 **0 failed**이고, candidate 매칭이 point error로 동작하며, 결과 파일만으로 **「어느 계약 · 어느 지표 정의 · 어느 예측」**을 채점했는지 재현할 수 있으면 2차 완료로 본다.
> **완료 정의에서 제외:** #11(외부 입력 대기) · #6과 #8의 「열지 않는다」 선택지.

## 순서 제안

```
#1-B (어휘 결정)  →  #2 (expected 7개)  →  #1-A (validator 교체 요청, #2와 병행)
      ↓
#3 (재배선)  →  #4 (7개 확장)  →  #5 (point error)  →  #7 (envelope)
      ↓
#6 · #8 (열지 여부 결정)  →  #9 (clip_id 규약 명시)  →  #10 (문서 문구)
```

## 검증 명령

```bash
python data/mock/validate_mock_pack.py            # 46 files / 7 scenarios PASS 유지
python -m pytest tests/eval -q                    # 목표: 0 failed
python -m eval.run   --impl mock_pack:contracts --manifest mock_pack --stage candidate --run-id mock_e2e
python -m eval.score --prediction mock_e2e
python scripts/check_boundaries.py                # CI가 실제로 도는 검사
```

> Windows에서 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`을 앞에 붙인다.
