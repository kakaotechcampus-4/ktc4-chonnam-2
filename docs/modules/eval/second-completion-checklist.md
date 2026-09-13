# 김대원 (`eval`) 2차 완료 체크리스트 — Mock Pack v5 기준

> **입력 버전:** Mock Pack v5(develop `72e0e05`) · Architecture v4 · `analysis-run-candidate-event/v1.1`(2026-09-10 §4-1·Consumer—`eval` 정정) · `usage-record/v1.2` · `case-view/v1.3` · `readout` failure-taxonomy(PR #27)
> **설계 근거:** `docs/superpowers/specs/2026-09-13-eval-2차-mock-v5-design.md` — **결정과 이유는 그 문서, 체크박스는 여기.**
> **1차:** `first-completion-checklist.md` — 판정은 `seed-v0` 기준이며 그대로 둔다. 경로가 죽은 6곳에 `[v5 무효]` 표시만 달려 있다.
> **작성 2026-09-13 · 설계 확정 후 개정 2026-09-13**

---

## 0. 지금 상태 (사실)

```
python data/mock/validate_mock_pack.py   46 files / 7 scenarios  PASSED (exit 0)
python -m pytest tests/eval -q            6 failed · 75 passed · 6 skipped
```

- 실패 6건은 전부 **구 경로·구 식별자**다. 하니스 본체는 통과한다.
- **CI는 이 실패를 잡지 않는다.** `.github/workflows/boundary-check.yml`이 도는 것은 `scripts/check_boundaries.py`(의존 방향)와 `scripts/check_contract_fixtures.py`(계약 fixture 디렉터리)뿐이고, `pytest`도 `validate_mock_pack.py`도 CI에 없다. 즉 **2차 완료 판정은 로컬 실행 증빙으로만 선다.**
- **v5는 eval 라벨 값을 바꾸지 않았다** — 아래 B 표가 v4와 동일하다.

### 설계 단계에서 뒤집힌 전제 3가지

1. **공용 validator §13은 교체하지 않아도 된다.** §13이 강제하는 것은 `provisional_non_contract_schema` · `metric_targets` 비어있지 않을 것 · ref 해석 3개뿐이고, `kind`는 **없으면 검사 분기가 통째로 건너뛴다.** v2의 라벨 배열 이름을 `metric_targets`로 두면 현행 스크립트를 그대로 통과한다 → **유소연님 의존 없음.**
2. **`legibility`는 fixture 필드가 아니다.** `PlateReadout`은 `observation.value`·`status`·`abstained`만 싣는다. 그리고 재판독은 `source_profile`이 `readout-native` → `readout-native-hires`로 **다르다.** 「UNREADABLE인데 재판독 성공」은 모순이 아니고, INITIAL의 abstain은 **정답**이다.
3. **`UsageRecord`는 26행이다**(23은 v4 수치). `case_x001`이 0원이고, `happy_001`의 전후방 2소스가 둘 다 `0~1200s`라 **P2-9 합산금지가 실제로 물린다**(2400s vs 1200s).

---

## A. `scoring` 어휘 — **결정: 두 이름 유지**

`BOUNDARY_EXCLUDED`(B tier 클립 경계) · `EXCLUDED`(참값 유형 없음)를 둘 다 둔다. 버린 대안은 「한 이름 + `exclusion_reason` 필드」.

- [ ] `eval/scorers/candidate.py:40`을 `t.get("scoring", "INCLUDED") == "INCLUDED"` 기준으로 교체
- [ ] **사유별로 세어 `coverage`에 갈라 적는다** — 합산하지 않는다. 결과만 보고 `n_events`가 GT와 어긋난 이유가 읽혀야 한다
- [ ] 지금 그대로 두면 `unknown_abstain_partial_001`이 채점 대상에 들어가 **영원히 맞출 수 없는 miss**가 되고 recall이 부당하게 낮아진다

## B. `expected/` 7개 신설 + 기존 2개 폐기

- [ ] `eval_fixture_correct_001.json` · `eval_fixture_wrong_001.json` 폐기 — ID 비교 채점 모델이고, 「채점기가 오류를 잡는가」는 `fake_always_correct`/`fake_always_wrong`이 이미 증명한다
- [ ] `data/mock/expected/<scenario_id>.expected.json` 7개 신설 — 스키마 `eval-expected/v2`, 라벨 배열 이름은 **`metric_targets` 유지**(§13 통과), `provisional_non_contract_schema: true` 유지
- [ ] **값 복사 금지** — `true_text`·`onset_ms`·`occurred_at`은 정답이지 사본이 아니다. 비교 대상은 실행 시 ref로 역참조한다 (1차 🟡 해소)
- [ ] plate 라벨은 **판독 단위 배열** — `legibility`가 (incident_clip, `source_profile`) 속성이기 때문
- [ ] **음성 2건을 명시적 라벨로 적는다** — `empty_001`·`infra_failure_001`을 빈 배열로 두면 `metric_targets is empty`로 §13이 FAIL한다. `negative_clip`(+`not_scored`)으로 적는다

**라벨 값 (v5 기준, v4와 동일 — 확인 완료)**

| 시나리오 | `candidate_onset` | `plate_readout` | `occurred_at` |
| --- | --- | --- | --- |
| `happy_001` | `candidate_h001` · `SOLID_LINE_LANE_CHANGE` · 312480ms · rev1 · `INCLUDED` | `readout_h001_plate` READABLE `12가3456` | `tres_h001` `2026-08-24T18:05:12+09:00` |
| `empty_001` | — (`negative_clip` `tl_e001`) | — | — |
| `plate_reread_001` | `candidate_p001` · `SIGNAL` · 612000ms · rev1 · `INCLUDED` | `readout_p001_plate` **UNREADABLE** / `readout_p001_plate_reread` READABLE `17나2867` | `tres_p001` `2026-08-29T20:10:12+09:00` |
| `correction_rerun_001` | `candidate_r001` · `MOTORCYCLE_HELMET_NON_USE` · 930000ms · rev1 · `INCLUDED` | `readout_r001_plate` READABLE `34나7890` | **`tres_r001_v2`** `2026-08-27T13:13:00+09:00` |
| `unknown_abstain_partial_001` | `candidate_u001` · `violation_type: null` · 615000ms · rev1 · **`EXCLUDED`** | `readout_u001_plate` READABLE `88부1234` | `tres_u001` **`expected: null`** · `expected_status: NEEDS_REVIEW` |
| `infra_failure_001` | — (`negative_clip` `tl_x001`) | `not_scored` `READOUT_INFRA_FAILURE` | `not_scored` `NO_TIME_RESOLUTION` |
| `relative_rebase_001` | `candidate_rb001` · `CENTER_LINE_CROSSING` · 512000ms · rev1 · `INCLUDED` | `not_scored` `NO_PLATE_READOUT` | `not_scored` `USABLE_RELATIVE_ONLY` |

- [ ] **`correction_rerun_001`은 시각 해석이 2개다** — `tres_r001_v1`(NEEDS_REVIEW · 13:15:30)을 `tres_r001_v2`(OK · 13:13:00 · `user_corrected=true`)가 대체했다. 정답은 **v2**를 가리킨다
- [ ] **`u001`의 시각 정답은 「값 없음」이 아니라 「확정하면 오답」이다** — fixture는 NEEDS_REVIEW 상태로 값을 싣고 있다. 충돌 보존이 정답

## C. impl 7개 확장 + GT 재생성 — **결정: 옛 #3·#4를 합친다**

1개로 재배선한 뒤 곧바로 7개로 넓히는 것은 같은 코드를 두 번 고치는 일이다. **완료 판정 `pytest 0 failed`.**

- [ ] `eval/runners/impls/mock_pack.py` — `SCENARIO` 상수 → 7개 리스트, `search/candidate_events.<suffix>.json` → `search/scenario_<id>.json`의 `analysis_run_candidate_events[].candidates[]`
- [ ] **두 음성을 구분한다** — `empty_001`은 search fixture 있고 candidates 0건이라 「후보 없음」(`fp_per_clip` 분모 O) / `infra_failure_001`은 search fixture 자체가 없어 「대상 아님」(분모 X). 뭉개면 음성 1건이 분모에 잘못 들어간다
- [ ] `eval/runners/normalize.py` `from_mock_pack` — 소멸한 `data/mock/eval/prediction_*.json` 경로 정리
- [ ] `eval/manifests/mock_pack/gt/gt_candidate.json` — 7개 항목 재생성, span 690~708초 → **onset 기준**, `derived_from` 갱신(현재 존재하지 않는 두 파일을 가리킨다)
- [ ] `coverage`: `clips_total` 7 · `clips_with_events` 5 · 음성 1 · 대상 아님 1. **순환성 경고 유지** — mock tier recall은 파이프라인 통과 확인이지 성능 근거가 아니다
- [ ] `tests/eval/test_mock_pack_contract.py` — `scenario_partial_001` → `scenario_unknown_abstain_partial_001`, `<scenario>.expected.json` 경로
- [ ] 식별자 개명 — `cand_h001`→`candidate_h001` · `run_h001_search`→`run_h001` · `PLATE_OCR`→`READOUT_PLATE` · `OVERLAY_OCR`→`READOUT_OVERLAY_TIME`
- [ ] **`empty_001`이 pack 최초 음성 케이스**다 — `fp_per_clip`이 `null`(`NO_NEGATIVE_CLIPS`)에서 처음으로 실제 값이 된다

**예측 onset 5건이 라벨과 정확히 일치함을 확인했다** — 312480 · 612000 · 930000 · 615000 · 512000, 전부 `timeline_revision: 1`.

## D. 매칭 규칙 교체 (IoU → onset point error)

- [ ] `eval/scorers/candidate.py` — 1차 매처를 `abs(representative_ms − gt_onset_ms) <= tolerance`로 교체
- [ ] `_iou`는 지우지 않고 **보조 sanity 신호로만** 남긴다
- [ ] `span_error_sec`의 이름·정의를 onset 오차 의미로 정리하고 결과 파일에 명시 — **현행 docstring이 「GT 시작 시각과의 절대 오차」라 새 정의와 어긋난다**
- [ ] 근거: `contract-analysis-run-candidate-event.md` §4-1 · Consumer—`eval`(2026-09-10) · `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`
- [ ] **주의:** 이 변경이 F `scorer_version`을 올리는 첫 계기다

## E. plate 채점 경로 — **결정: 연다**

지금 `score.py:40`이 `plate.score(norm, None)`을 stage와 무관하게 매번 부르고, 그 함수는 인자를 보지도 않고 전부 `null`을 반환한다. `run.py --stage`에 `plate`가 없다.

- [ ] `eval/runners/normalize.py` — `from_plate_readouts()` 신설
- [ ] `eval/run.py` — `_NORMALIZERS`에 `plate` 추가
- [ ] `eval/manifests/mock_pack/gt/gt_plate.json` 신설
- [ ] `eval/scorers/plate.py` — GT 분기 재구현 (F6 해소). **검증할 GT가 5건 있으므로 F6 교훈의 조건은 충족된다**

**판정 = `abstained` × GT `legibility` 교차표**

| | GT READABLE | GT UNREADABLE |
| --- | --- | --- |
| `abstained=false` | `exact_match`: `observation.value` == `true_text` | **`wrong_accept`** |
| `abstained=true` | 놓친 판독 | **`abstention_recall` 적중** |

- [ ] 실측 분모: `exact_match` **4/4** · `abstention_recall` **1/1** · `wrong_accept_rate` **0/1**
- [ ] **분자 0건 한계를 `coverage`에 적는다** — pack에 「확신에 차서 틀리게 읽은」 케이스가 없다. 이 수치는 안전하다는 증거가 아니다
- [ ] `not_scored` 2건(`infra_failure` · `relative_rebase`)도 사유와 함께 적는다

## F. 결과 envelope 누락 4건

- [ ] `predictions/`에 `contract_version` · `processed_duration_sec` 추가
- [ ] `results/`에 `scorer_version` · `prediction_ref`(경로 + sha256) 추가
- [ ] `contract_version` 기준으로 「버전이 다르면 비교 거부」(v4 §9-2 규칙 5)를 `score.py`에서 강제
- [ ] `processed_duration_sec` 값 = **이 실행이 실제로 예측을 만든 시나리오들의 timeline union 합**. 대상 아님으로 뺀 시나리오는 분모에도 안 들어간다
- [ ] 근거·상세: `research/version-fields-proposal.md` §3

## G. 비용 지표 — **결정: 연다**

- [ ] `eval/scorers/cost.py` 신설 + `score.py`에 `result["cost"]` 블록
- [ ] **집계 키는 `case_id`** — `run_ref` 아님(`usage-record/v1.2` §9-2). STALE attempt row(`RUN_NOT_PRODUCED` 2건)가 빠지지 않게
- [ ] **분모는 timeline union** — `happy_001` 전후방 2소스 합산 금지(1200s), `relative_rebase_001`은 **최신 rev 2**에서 gap `600~630s` 제외(1200s)
- [ ] 분자·분모를 **같은 시나리오 집합**으로 맞추고 그 집합을 `coverage`에 적는다
- [ ] 통화가 섞이면 환산하지 말고 **거부한다** — 환율은 `pricing_context`에 귀속되지 eval이 정할 값이 아니다
- [ ] `case_x001`이 **0원**이다. 평균만 내지 말고 case별로 남겨 분포가 보이게 한다

**실측 (26행 · 전 행 KRW)**

```
case_h001 938 · case_u001 756 · case_p001 728 · case_r001 630
case_e001 434 · case_rb001  84 · case_x001   0        합계 3570 KRW
run_ref_reason:  null 22 · DIRECT_NO_RUN 2 · RUN_NOT_PRODUCED 2
```

## H. `clip_id` 규약 + 문서 문구 2곳

- [ ] **`scenario_id = clip_id` 규약 유지** — 7개로 넓혀도 1:1이 안 깨진다(시나리오당 timeline 1개, `relative_rebase_001`은 같은 `tl_rb001`의 revision 2개). GT `meta.clip_id_convention`에 명문화
- [ ] B tier(`clip_id` 실재)와 mock tier가 같은 scorer를 타므로 **결과 파일만 보고 어느 쪽인지 읽히게** 한다
- [ ] `docs/modules/eval/experiment-guide.md:483` — `OVERCONFIDENT`가 런타임 실패 이름들과 한 표에 있다. 층위(런타임 5 + 사후 1) 한 줄 추가
- [ ] `docs/modules/eval/harness-v1-design.md:267`(F6) — 「`wrong_accept_rate` 분모에 abstain 항목 포함」을 **「정답이 `UNREADABLE`인 항목」**으로 정정. E의 교차표·ADR §4.10과 같은 정의

## I. `tests/eval`가 §13의 빈자리를 메운다

§13은 `metric_targets`가 **비어있는지만** 보고 라벨 내용은 검증하지 못한다. 그 자리를 내 테스트가 맡는다.

- [ ] 모든 `metric_targets[].ref`가 pack 안 객체로 해석될 것
- [ ] `legibility=READABLE`이면 `true_text` == 해당 `PlateReadout.observation.value`
- [ ] `legibility=UNREADABLE`이면 그 판독의 `abstained == true`
- [ ] `candidate_onset.onset_ms` == 해당 candidate의 `span.representative_ms`
- [ ] `scoring` 값이 `INCLUDED`/`EXCLUDED`/`BOUNDARY_EXCLUDED` 안에 있을 것
- [ ] 7개 시나리오 전부에 expected 파일이 있을 것

## J. 외부 입력 대기 — 완료 정의에서 제외

- [ ] `eval/manifests/b_youtube/clips.json`에 `source_url`·`license` 추가 — **`YT_0001` 원본 URL·라이선스 표기 필요**
- [ ] 자료조사 6개 문서의 `[링크 필요]` 채우기 — AI-Hub 71555 상세/이용조건/일반 이용정책/구축 설명서, 제조사 매뉴얼 5종
- [ ] `research/blackbox-storage-survey.md`는 **출처 0건이라 현재 인용 금지** 상태다

## K. v5 신규 검수 — 조치 없음 (확인 완료)

- [x] v5가 eval 라벨 값을 바꾸지 않았다 — onset 5건·참값·abstain 상태 전부 v4와 동일
- [x] `validate_mock_pack.py` 46 files · 7 scenarios PASS (validator +170줄 보강 포함)
- [x] `infra_failure_001`에 overlay 판독 2건이 추가됐으나 둘 다 `UNKNOWN`·value null → 라벨 `occurred_at: not_scored` 유지
- [x] `correction_rerun_001`의 `verification=AGREED`는 evidence 소유 미결(4차 공지 🔴 1건)이며 내 시각 라벨(13:13:00)에 영향 없음

---

## 2차 완료 정의

> 7개 시나리오 정답지가 `eval-expected/v2`로 존재하고 **공용 validator를 수정 없이** 통과하며, `pytest tests/eval`이 **0 failed**이고, candidate 매칭이 onset point error로 동작하며, **plate 교차표와 cost 블록이 실제 수치를 내고**, 결과 파일만으로 **「어느 계약 · 어느 지표 정의 · 어느 예측」**을 채점했는지 재현할 수 있으면 2차 완료로 본다.
> **완료 정의에서 제외:** J(외부 입력 대기).

## 순서

```
A 어휘  →  B expected 7개  →  C impl 7개 + GT 재생성  →  D point error
      →  E plate 경로  →  F envelope  →  G cost  →  H 규약·문서
                                    I(테스트)는 B·C·E와 함께 붙인다
```

C 끝에서 `pytest tests/eval` **0 failed**를 찍는다.

## 검증 명령

```bash
python data/mock/validate_mock_pack.py            # 46+ files / 7 scenarios PASS 유지
python -m pytest tests/eval -q                    # 목표: 0 failed
python -m eval.run --impl mock_pack:contracts --manifest mock_pack --stage candidate --run-id mock_e2e
python -m eval.run --impl mock_pack:contracts --manifest mock_pack --stage plate     --run-id mock_plate
python -m eval.score --prediction mock_e2e
python scripts/check_boundaries.py                # CI가 실제로 도는 검사
```

> Windows에서 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`을 앞에 붙인다.

## 옛 번호 대응

이슈·대화에서 쓰던 번호와의 대응이다. `#1-A`는 **해소**됐다(validator 교체 불필요).

| 옛 | 지금 |
| --- | --- |
| #1-A | §0 뒤집힌 전제 1 — 해소 |
| #1-B | A |
| #2 | B |
| #3 · #4 | C (합침) |
| #5 | D |
| #6 | E (열기로 결정) |
| #7 | F |
| #8 | G (열기로 결정) |
| #9 · #10 | H |
| #11 | J |
| #12 | K |
