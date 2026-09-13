# 김대원 (`eval`) 1차 완료 체크리스트

> **입력 버전:** Architecture v4 · Mock Pack `seed-v0`(`data/mock/manifest.json`) · `04_mock_validation_report.md` · `harness-v1-design.md`
> **상태:** Mock Pack이 `v1`으로 재생성되면 Scenario·Fixture 절을 갱신한다.

> ## 🔄 상태 갱신 (2026-09-13 · Mock Pack v5 기준)
>
> 아래 1차 체크리스트의 판정은 **Mock Pack `seed-v0` 시점 기준이며 그때는 전부 사실이었다.** 이후 Pack이 v2에서 재생성되면서 **파일 레이아웃과 식별자가 바뀌어 일부 항목의 증빙 경로가 무효가 됐다.** 무효가 된 줄에는 `[v5 무효]` 표시를 달았고, 판정 자체(`[x]`)는 당시 기록이므로 지우지 않는다.
>
> **현재 상태:** `pytest tests/eval` → **6 failed · 75 passed · 6 skipped**. 실패 6건은 전부 구 경로·구 식별자이고 하니스 본체는 통과한다. `data/mock/validate_mock_pack.py`는 46 files · 7 scenarios PASS.
>
> 해야 할 일은 **아래 「2차 — Mock Pack v5 반영 수정 체크리스트」**에 모았다. 1차 항목을 고쳐 쓰지 않고 2차에서 다시 판정한다.

---

## 회의에서 먼저 볼 핵심

1. **팀 목데이터가 파이프라인을 끝까지 통과해 결과 JSON을 낸다** — `eval/results/mock_e2e.mp0.json`. 입력은 서어진의 `candidate_events.happy_001.json`이고, 계약의 `span`(690000~708000ms)을 초로 옮겨 IoU 매칭이 성립한다.
   - `[v5 무효]` 입력 경로는 `data/mock/search/scenario_happy_001.json`으로, `span`은 `300000~420000ms`(`representative_ms` 312480)로 바뀌었다. **IoU 매칭 자체가 폐기됐다** — 2026-09-10 계약 정정으로 coarse localization은 `abs(representative_ms − gt_onset_ms)` point error다(2차 #3).
2. **채점기가 오류를 잡는다는 증거를 보인다.** 두 fixture의 점수가 갈리는 것 자체가 지표 계산이 맞다는 근거다. 같은 점수가 나오면 채점기가 깨진 것이다.
3. **데이터가 없는 지표는 `0`이 아니라 `null` + 사유로 나온다.** 목데이터에는 negative clip이 없어 `fp_per_clip`이 `null`이고, 그 이유(`NO_NEGATIVE_CLIPS`)가 결과 파일에 적혀 있다.
4. **Runtime 흐름을 건드리지 않는다.** `eval`은 별도 Track이며 `case`·`evidence`·`web`을 import하지 않는다. 공개 Contract 파일만 읽는다.
5. **Consumer 검수 의견을 낸다.** 세 계약(`CandidateEvent`·`PlateReadout`·`UsageRecord`)에 대해 "이 fixture로 eval 개발을 시작할 수 있는가"에 답한다.

---

## 담당 범위

- **Owner:** 김대원
- **주 담당 Module:** `eval` (성능 채점기)
- **보조 담당 Module:** `web` 영상 화면(후보 카드·타임라인·번호판 확대) — **후반부 착수, 1차 완료 범위 밖**
- **Producer로 책임지는 것:** eval fixture(ground truth / prediction) · 정답지 · manifest 버전 · 지표 계산 · 결과 파일
- **Consumer로 사용하는 Contract:**
  - `AnalysisRun` · `CandidateEvent` · `VisualEvidence` (Producer 서어진)
  - `PlateReadout` · `OverlayTimeReadout` · `ReadoutRun` (Producer 신유민)
  - `JobExecution` · `UsageRecord` (Contract Owner 김준영)
  - `AnalysisScope` (Lead 유소연 — 검토 참여)
- **1차 통합에서 내 출력의 주요 Consumer:** 없음. `eval` 결과는 Runtime이 소비하지 않는다(단방향 채점). 사람이 읽는다.
- **1차 통합에서 내가 의존하는 주요 Producer:** 서어진(`search`) · 신유민(`readout`) · 유소연(Mock Pack 운영)

> `eval`은 Runtime 데이터 흐름 바깥에 있다. Merge 순서에서 별도 Track으로 잡는다.

---

## 1차 완료 정의

> `[v5 무효]` `data/mock/eval/prediction_*.json`과 `data/mock/expected/scenario_happy_001.expected.json`은 현재 존재하지 않는다. 정답지는 2차 #1에서 `expected/<scenario_id>.expected.json` 7개로 다시 쓴다.
>
> `scenario_happy_001` 기준으로 **팀 공용 Mock Pack 산출물(계약 `candidate_events`와 eval fixture `prediction_*.json`)과 정답지(`data/mock/expected/*.expected.json`)를 입력으로 받아**, 공개 Contract 필드만으로 채점을 수행하고, **결과 JSON을 파일로 생성**할 수 있으며, **데이터가 없어 낼 수 없는 지표는 `0`이 아니라 `null` + 사유로 표시**하고, `prediction_correct`와 `prediction_wrong`의 **점수 대비를 근거로 채점기 자체가 오류를 탐지한다는 것을 증명**할 수 있고, 세 소비 계약에 대한 **Consumer 검수 의견을 제출**했으면 1차 완료로 본다.

---

## 구현 체크리스트

### A. Input

- [x] 정답지(GT)와 manifest를 파일에서 로드할 수 있다.
- [x] 정답지 불변식을 검사해 위반 목록을 낸다(개수 일치·시간 순서·구간 범위·파일 존재·해시).
- [x] `data/mock/eval/prediction_*.json`을 **실제 파일 경로에서** 읽는다. — `[v5 무효]` 경로 소멸(2차 #2)
- [x] `data/mock/expected/scenario_happy_001.expected.json`을 정답지로 로드한다. — `[v5 무효]` 경로 소멸(2차 #1)
- [x] Mock fixture가 바뀌면 테스트가 깨진다 — Mock Pack이 v1로 재생성되면 여기서 드러난다.

### B. Core Flow

- [x] `python -m eval.run --impl <이름표>` 한 줄로 예측 산출물을 만든다.
- [x] `python -m eval.score --prediction <run_id>` 한 줄로 채점 결과를 만든다.
- [x] runner와 scorer가 분리되어 있고, 예측은 불변 산출물로 남는다.
- [x] **팀 목데이터가 파이프라인을 끝까지 통과한다** — `--impl mock_pack:contracts --manifest mock_pack`. 산출물 `eval/predictions/mock_e2e.json` · `eval/results/mock_e2e.mp0.json` 커밋됨. 입력은 서어진의 `candidate_events.happy_001.json`이다. — `[v5 무효]` 현재 이 impl은 구 경로를 읽어 실패한다(2차 #2)

### C. Output Contract (내가 생산하는 산출물)

- [x] 결과 JSON에 `run_id`·`impl`·`stage`·`manifest`·`gt_version`·`normalizer_version`·`code_commit`이 들어간다. — `[v5 보강 필요]` `contract_version`·`scorer_version`·`prediction_ref`·`processed_duration_sec` 누락(2차 #4)
- [x] 위반유형 4종별 점수를 따로 낸다.
- [x] Classification(A tier) 지표를 낸다 — 5×5 혼동행렬 포함.
- [x] **어떤 Scenario를 확인했는지가 증빙에 남는다** — 시나리오로 파라미터화해 pytest 출력의 테스트 이름에 박히고, 정답지가 없는 `scenario_partial_001`은 사유와 함께 skip으로 같은 화면에 보인다. — `[v5 무효]` 시나리오가 `scenario_unknown_abstain_partial_001`로 개명되고 `scenario_plate_reread_001`이 분리됐다(2차 #1·#2) 파이프라인 결과 파일에는 정답지 `meta.coverage.scenario_id`가 시나리오를 적는다.

### D. Failure / Uncertainty

- [x] 데이터가 없는 지표는 `null` + 사유 문자열이다. `0`으로 적지 않는다.
- [x] 정답은 있는데 예측이 못 맞힌 경우와, 애초에 잴 수 없는 경우를 구분한다.
- [x] Mock 예측에 구간이 없다는 사실이 코드에 기록돼 있다 — `from_mock_pack` 독스트링이 "IoU 기반 지표는 「측정했는데 0」처럼 보이지만 잰 적이 없는 값"이라고 경고한다. 애초에 채점하지 않으므로 잘못된 0이 나올 자리가 없다.
- [—] ~~`scenario_partial_001`의 ABSTAIN·UNKNOWN 채점~~ — **v1로 이월**(아래 제외 범위 참조)

### E. Integration

- [x] `eval`이 `case`·`evidence`·`web`을 import하지 않는다.
- [x] `search`·`readout`의 내부 코드(프롬프트·파서)를 import하지 않는다 — 공개 Contract 파일만 읽는다.
- [x] 외부 의존성 0개(표준 라이브러리만).
- [ ] 실제 구현이 나오면 `--impl`에 이름표만 등록해 교체할 수 있다. **원격에 `feature/search-stub`("fixture-backed stub for search public capabilities")이 이미 올라와 있어 이제 실물로 검증 가능하다** — 통합 후 착수, 1차 완료 범위 밖.

### F. Test / Evaluation

- [x] 채점기 단위 테스트가 있다.
- [x] **가짜 구현 2종의 점수 대비로 지표 계산을 검증한다.**
- [x] 정답지가 구현에 넘어가지 않는 것을 테스트가 검증한다.
- [x] 팀 Mock fixture를 읽는 회귀 테스트가 있다 — `test_mock_pack_contract.py`(7 통과 / 3 skip) · `test_mock_pack_pipeline.py`(5 통과).

### G. Operational

- [—] ~~`UsageRecord`의 `latency_ms`·`cost.amount`를 읽는다~~ — **v1 범위 밖**(아래 제외 범위).

---

## Contract별 완료 조건

### `CandidateEvent` (Consumer)

- [x] `candidate_id`·`rank`·`event_type_hint`·`span.{start_ms,end_ms}`를 읽어 옮긴다 — `normalize.from_candidate_events`.
- [x] **필드 이름·단위 차이를 한 곳에서 흡수한다** — `event_type_hint`→`event_type`, `ranking_score`→`score`, `start_ms`(밀리초)→`t_start_sec`(초).
- [x] `event_type_hint` 값이 baseline 4종 안에 있는지 테스트가 고정한다 — 벗어나면 혼동행렬에 자리가 없어 조용히 miss로 집계된다.
- [~] `uncertainties` 처리 규칙 — **PR #11 질문 3으로 서어진에게 물었다.** 혼자 정할 수 없어 답변 대기. 채점 구현은 v1.
- [x] Consumer 검수 의견 제출 — **PR #11 본문에 담당자별로 제출**(질문 1·2·3). 답변 대기.

### `PlateReadout` / `OverlayTimeReadout` (Consumer)

- [x] Consumer 검수 의견 제출 — **PR #11 질문 4.** `abstained=true`에 값이 남는 것이 계약상 정상임을 원문에서 확인하고, eval이 그 값을 확정으로 채점하지 않겠다는 해석을 함께 냈다. 신유민 확인 대기.
- [—] ~~`abstained` / `observation.status` 채점 규칙 구현~~ — **v1로 이월**

### `UsageRecord` (Consumer)

- [x] Consumer 검수 의견 제출 — **PR #11 「범위 밖」절에 명시**. 비용·Latency 계산은 v1 범위 밖이며 eval batch 비용을 runtime 비용과 섞지 않는다.
- [x] eval batch 비용을 runtime 비용과 같은 숫자로 보고하지 않는다 — 비용을 아예 계산하지 않으므로 섞일 자리가 없다.

### eval fixture (Producer — 내가 검수 담당)

- [x] `expected` 파일이 Mock Runtime Output이 아니라 사람이 라벨링한 정답지임이 문서에 명시돼 있다.
- [x] `prediction_correct`가 `expected`의 **5개 값 전부**와 일치하는지 코드로 확인했다.
- [x] `prediction_wrong`이 rank·`visual_event_type`·`plate_value` **정확히 세 곳에서만** 어긋나는지 코드로 확인했다 — Scenario Catalog의 주장과 파일이 일치한다.
- [x] **`scenario_partial_001`용 ground truth/prediction 부재를 보고했다** — **PR #11 질문 6.** `pytest` 출력에도 사유와 문서 번호가 함께 skip으로 남는다.

---

## Scenario별 완료 조건

| Scenario | 내 입력 | 내가 해야 할 처리 | 기대 출력 | 완료 기준 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | `prediction_correct.happy_001.json` + `expected` | 정규화 → 채점 | `results/*.json` | 4개 정답 항목 전부 적중, 낼 수 없는 지표는 `null`+사유 |
| `scenario_happy_001` | `prediction_wrong.happy_001.json` + `expected` | 정규화 → 채점 | `results/*.json` | rank·유형·plate 세 곳이 오답으로 잡힘 — **correct와 점수가 갈릴 것** |
| `scenario_partial_001` | `candidate_events` · `plate_readout` | 정답지 없이 가능한 것만 — enum 소속, ABSTAIN 가시성 | pytest PASS | 정답지가 필요한 3건은 **사유와 함께 skip**되어 출력에 남는다. 채점은 v1 이월 |

---

## 검수에서 나온 것 (Consumer 의견 초안)

`tests/eval/test_mock_pack_contract.py`를 붙이면서 실제로 확인된 것들이다. 추측이 아니라 파일을 읽은 결과다.

| # | 내용 | 누구와 | 상태 |
| --- | --- | --- | --- |
| 1 | `event_type_hint`가 baseline 4종 안에 있다 (`SOLID_LINE_LANE_CHANGE`). 다만 확인된 표본은 `happy_001` 1건뿐 — **값 공간 전체가 4종으로 닫혀 있는지는 계약 문서에서 확인 필요** | 서어진 | 확인 필요 |
| 2 | **`timeline_id` + 밀리초 offset ↔ `clip_id` 대응을 어느 계약도 정하지 않았다.** 계약은 timeline 기준으로, eval의 B tier 정답지는 clip 기준으로 위치를 말한다. 지금은 원문 식별자를 그대로 실어 보내며 지어내지 않았다. clip 단위 채점이 필요해지는 시점에 정해야 한다 | 서어진 + 정철원 | **열린 결정** |
| 3 | eval fixture(`prediction_*.json`)에 **구간이 없다** — `occurred_at` 타임스탬프뿐. 이 입력으로는 Recall@K·구간오차를 낼 수 없다(내면 "잰 적 없는 값을 0으로 적는" 것이 된다). **계약 산출물 `candidate_events`에는 `span`이 있어** 파이프라인은 그쪽을 읽어 해결했다. 다만 fixture가 실제 예측 형태를 대표하려면 `span`이 있어야 한다 | 유소연 | 보고 · 수정 PR 문의 |
| 4 | `scenario_partial_001`용 eval fixture가 없다 | 유소연 | v1로 이월 (§23 기록됨) |
| 5 | **`abstained=true`인데 `observation.value`에 값이 남아 있다**(`"12나 34?6"`). 계약상 정상 — `readout`은 번호판을 최종 확정하지 않고 관찰만 제공하며 확정/보류는 `evidence`가 판단한다. 따라서 **eval이 이 값을 확정 판독으로 채점하면 안 된다** — 정직하게 보류한 구현이 오답이 되고 무리해서 읽는 쪽이 유리해진다. 테스트로 고정해뒀다 | 신유민 | 확인됨 (채점 규칙은 v1) |
| 6 | `CandidateEvent.uncertainties`를 채점에서 어떻게 다룰지 미정 | 서어진 | v1 |

> 2번이 가장 중요하다. 지금은 Mock이 시나리오 1건이라 드러나지 않지만, 실제 영상으로 넘어가면 **"이 후보가 어느 클립의 몇 초인가"를 아무도 계산할 수 없다.**

---

## Merge 전 셀프 체크 증빙

- [x] CLI 실행 결과 — `python -m eval.run` / `python -m eval.score`
- [x] 정상 출력 JSON — `eval/results/demo_correct.g1.json`
- [x] 오답 출력 JSON — `eval/results/demo_wrong.g1.json` (대비가 보이는 쌍)
- [x] 테스트 실행 결과 — **84 통과 + 3 skip**
- [x] **팀 목데이터 파이프라인 결과** — `eval/results/mock_e2e.mp0.json` (커밋됨)
- [x] Consumer 검수 의견 전달 — **PR #11 본문**(https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/11). 담당자별로 묶어 6건. 회의에서 구두 보강 예정

> 화면 캡처·API·로그는 이 모듈에 해당 없음. 비용/Latency 측정 파일은 v1 범위 밖.

---

## Merge 전 확인 질문

1. `scenario_happy_001`의 `prediction_correct`를 넣으면 어떤 숫자가 나오고, `prediction_wrong`은 어디서 갈리는지 설명할 수 있는가?
2. 내가 읽는 필드가 정확히 무엇인지 — `event_type_hint`인가 `visual_event_type`인가 — 계약 문서를 짚어 말할 수 있는가?
3. `PlateReadout.abstained=true`를 오답으로 세고 있지 않은가?
4. 결과 파일의 `null` 하나하나에 왜 없는지가 적혀 있는가?
5. 내 코드가 `search`·`readout`·`case`의 내부 객체를 import하고 있지 않은가?
6. 실제 구현이 나오면 무엇만 바꾸면 채점되는지 한 줄로 말할 수 있는가?

---

## 접합부 확인

| 접합 상대 | 확인 Contract | 내 역할 | 상대 역할 | Merge에서 확인할 것 |
| --- | --- | --- | --- | --- |
| 서어진 (`search`) | `CandidateEvent` · `AnalysisRun` | Consumer | Producer | `rank` 의미 · `event_type_hint` 값 공간이 baseline 4종과 일치하는가 · `span` 단위(ms) |
| 신유민 (`readout`) | `PlateReadout` · `OverlayTimeReadout` | Consumer | Producer | ABSTAIN 표현 · `observation.status` 값 공간 |
| 김준영 (common) | `UsageRecord` · `JobExecution` | Consumer | Contract Owner | 비용 분모 정의 — eval batch와 runtime을 섞지 않는다 |
| 유소연 (Mock 운영) | eval fixture | 검수 담당 | Pack 생성 | partial 시나리오 fixture 부재 · 구간 정보 부재 |

---

## 부분 완료 / 통합 대기

| 항목 | 현재 어디까지 됨 | 무엇을 기다리는가 | 상대 담당 | Mock 대체 가능 |
| --- | --- | --- | --- | --- |
| 실제 `search` 채점 | 하니스 완성, `--impl` 자리 비어 있음 | search 가짜 구현 1개 | 서어진 | 가능 (자체 가짜 구현 2종으로 대체 중) |
| Plate 지표 | 스키마·자리만 있고 전부 `null` | C tier 원본(팀원 SD 영상) | 정철원 / 본인 | 불가 — A tier는 번호판이 마스킹돼 있음 |
| partial 시나리오 채점 | 불가 | partial용 GT/prediction fixture | 유소연 + 본인 | 불가 |
| Timestamp / 비용 지표 | 미착수 | — | — | v1 범위 밖(의도적) |

---

## 1차 완료에서 제외하는 것

- **`scenario_partial_001` 채점 전체** — `04_mock_validation_report.md` §23이 "Partial Success 채점 검증은 v1로 미뤄졌다"고 이미 기록했다. Seed Mock(v0)에 eval fixture 자체가 없고, W4 §17이 eval에 요구하는 것은 "공개 Contract/Mock 결과를 읽어 **기본 검증**"까지다. ABSTAIN·UNKNOWN이 Case를 깨지 않는지는 `case` 쪽 판정 항목이다.
- **Timestamp·Fine·E2E·Efficiency 지표** — 스펙 §1에서 v1 범위 밖으로 명시
- **Plate 실측 지표** — 정답지가 존재하지 않는다. 스키마와 `null` + 사유까지만
- **비용 / Latency 지표** — `UsageRecord` 검수 의견만 내고 계산은 하지 않는다
- **`web` 영상 화면(후보카드·타임라인·번호판 확대)** — 후반부 착수
- **챌린저 비교·성능 최적화**

---

## Merge 중단 기준

- `event_type_hint`의 값 공간이 baseline 4종(`SIGNAL`·`CENTER_LINE_CROSSING`·`SOLID_LINE_LANE_CHANGE`·`MOTORCYCLE_HELMET_NON_USE`)과 다르다
- 정답지가 구현에 전달되는 경로가 생겼다 — **채점 결과 전체가 무의미해진다**
- 데이터가 없는 지표가 `0`으로 보고된다
- ABSTAIN이 오답으로 집계된다
- `eval`이 `case`·`evidence`·`web` 또는 `search`·`readout` 내부 코드를 import한다
- eval batch 비용이 runtime 비용과 같은 숫자로 보고된다
- 두 가짜 구현이 같은 점수를 낸다

> 아래는 **중단 사유가 아니다**(후속 TODO): partial fixture 부재 · Plate가 전부 `null` · 비용 지표 부재.

---

## 검증 명령

```bash
# 정답지 불변식
python -c "from eval import manifests_io; print(manifests_io.check_invariants('b_youtube','candidate',verify_hashes=3))"

# 지표 검증 (가짜 구현 대비)
python -m eval.run   --impl fake:always_correct --manifest b_youtube --stage candidate --run-id demo_correct
python -m eval.run   --impl fake:always_wrong   --manifest b_youtube --stage candidate --run-id demo_wrong
python -m eval.score --prediction demo_correct
python -m eval.score --prediction demo_wrong

# 전체 테스트
python -m pytest tests/eval/ -v

# 팀 Mock fixture 접합 확인
python -m pytest tests/eval/test_mock_pack_contract.py -v
```

> Windows에서 한글 출력이 깨지면 `PYTHONIOENCODING=utf-8`을 앞에 붙인다.
> `verify_hashes`가 있는 테스트는 로컬 영상 파일이 필요하다. 없으면 skip된다.

---

## 2차 — Mock Pack v5 반영 수정 체크리스트

> **기준:** Mock Pack v5(develop `72e0e05`) · 계약 `analysis-run-candidate-event/v1.1`(2026-09-10 §4-1·Consumer—eval 정정) · `usage-record/v1.2` · `case-view/v1.3`
> **v5에서 eval 라벨 값은 하나도 바뀌지 않았다** — onset 5건·번호판 참값·abstain 상태 전부 v4와 동일하다(아래 #1 표가 그대로 유효). v5 변경분은 `infra_failure`(case·readout·common 보강)와 `correction_rerun`(`verification=AGREED`), validator +170줄이다.

### #1. `expected/` 7개 신설 + 기존 2개 폐기 — **착수 가능**

- [ ] `eval_fixture_correct_001.json`·`eval_fixture_wrong_001.json` 폐기 (ID 비교 모델. 역할은 `fake_always_correct`/`fake_always_wrong` 두 impl이 이미 수행)
- [ ] `data/mock/expected/<scenario_id>.expected.json` 7개 신설 — 스키마 `eval-expected/v2`, 값 복사 금지(`readout_ref`·`resolution_ref`·`timeline_ref` 참조만)
- [ ] plate 라벨은 **판독 단위 배열**(`plate_reread_001`은 INITIAL·REREAD 2건)

| 시나리오 | candidate(type · onset · rev) | plate | time |
| --- | --- | --- | --- |
| `happy_001` | `SOLID_LINE_LANE_CHANGE` · 312.48s · 1 | READABLE `12가3456` | `18:05:12` |
| `empty_001` | `targets: []` (음성 — `fp_per_clip` 분모) | 없음 | 없음 |
| `plate_reread_001` | `SIGNAL` · 612.00s · 1 | INITIAL UNREADABLE / REREAD READABLE, 참값 `17나2867` | `20:10:12` |
| `correction_rerun_001` | `MOTORCYCLE_HELMET_NON_USE` · 930.00s · 1 | READABLE `34나7890` | `13:13:00` (USER_OVERRIDE, offset 930s 유지) |
| `unknown_abstain_partial_001` | 615.00s · 1 · **`scoring: EXCLUDED`**(참값 유형 없음) | READABLE `88부1234` | `null` (시각 충돌 보존) |
| `infra_failure_001` | `targets: []` | `not_scored.plate = READOUT_INFRA_FAILURE` | `null` (overlay 2건 모두 `UNKNOWN`) |
| `relative_rebase_001` | `CENTER_LINE_CROSSING` · 512.00s · 1 | 없음 | `null` (`USABLE_RELATIVE_ONLY`) |

### #2. 접합부 재배선 — **착수 가능**

- [ ] `eval/runners/impls/mock_pack.py` — `search/candidate_events.<suffix>.json` → `search/scenario_<id>.json`의 `analysis_run_candidate_events[].candidates[]`
- [ ] `eval/runners/normalize.py` `from_mock_pack` — `data/mock/eval/prediction_*.json` 경로 소멸분 정리
- [ ] `eval/manifests/mock_pack/gt/gt_candidate.json` — span 690~708초 → onset 312.48초 기준으로 재생성, `derived_from` 경로 갱신
- [ ] `tests/eval/test_mock_pack_contract.py` — `scenario_partial_001` → `scenario_unknown_abstain_partial_001`, `<scenario>.expected.json` 경로
- [ ] 식별자 개명 반영 — `cand_h001`→`candidate_h001`, `run_h001_search`→`run_h001`, `PLATE_OCR`→`READOUT_PLATE`, `OVERLAY_OCR`→`READOUT_OVERLAY_TIME`
- [ ] **완료 판정:** `python -m pytest tests/eval -q` → 0 failed

### #3. 매칭 규칙 교체 (IoU → point error) — **착수 가능**

- [ ] `eval/scorers/candidate.py` — 1차 매처를 `abs(representative_ms − gt_onset_ms) <= tolerance`로 교체. span IoU는 보조 sanity(`start_ms <= gt_onset <= end_ms`)로만 남긴다
- [ ] `span_error_sec` → mock/실측 공통으로 onset 오차 의미로 정리하고 이름·정의를 결과 파일에 명시
- [ ] 근거: `contract-analysis-run-candidate-event.md` §4-1 · Consumer—`eval`(2026-09-10) · `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`
- [ ] **주의:** 규칙이 바뀌었으므로 #4의 `scorer_version`을 올리는 첫 계기다

### #4. 결과 envelope 누락 4건 — **착수 가능**

- [ ] `predictions/`에 `contract_version` · `processed_duration_sec` 추가
- [ ] `results/`에 `scorer_version` · `prediction_ref`(경로 + sha256) 추가
- [ ] `contract_version` 기준으로 「버전이 다르면 비교 거부」(v4 §9-2 규칙 5)를 코드에서 강제
- [ ] 근거·상세: `research/version-fields-proposal.md` §3

### #5. 내 문서 문구 2곳 — **착수 가능**

- [ ] `docs/modules/eval/experiment-guide.md:483` — `OVERCONFIDENT`가 런타임 실패 이름들과 한 표에 있다. 층위(런타임 5 + 사후 1) 한 줄 추가
- [ ] `docs/modules/eval/harness-v1-design.md:267`(F6) — 「`wrong_accept_rate` 분모에 abstain 항목 포함」이 `abstained=true`를 넣으라는 뜻으로 읽힌다. 「정답이 `UNREADABLE`인 항목」으로 정정(ADR §4.10 정의와 같은 뜻)

### #6. B tier manifest 출처 — **외부 입력 대기**

- [ ] `eval/manifests/b_youtube/clips.json`에 `source_url`·`license` 추가 (현재 없음. `eval-dataset-plan.md` §3-3·§6-2가 「최소한 이 둘은 남긴다」고 못 박은 값)
- [ ] 필요한 것: `YT_0001` 원본 URL과 라이선스 표기

### #7. 자료조사 출처 링크 — **외부 입력 대기**

- [ ] `research/aihub-71555-survey.md` §9 — AI-Hub 71555 상세/이용조건/일반 이용정책/구축 설명서
- [ ] `research/eval-dataset-plan.md` §9 — `YT_0001` URL·라이선스, 대체 공개 데이터셋 3종
- [ ] `research/blackbox-storage-survey.md` §4 — 제조사 매뉴얼 5종 (**출처 0건 상태라 현재 인용 금지**)
- [ ] `research/ground-truth-schema.md` §4 — 데이터셋 원본·라벨 명세·위반유형 근거

### #8. v5 신규 검수 — **확인 완료, 조치 없음**

- [x] v5가 eval 라벨 값을 바꾸지 않았다 — onset 5건·참값·abstain 상태 v4와 동일
- [x] `validate_mock_pack.py` 46 files · 7 scenarios PASS (validator +170줄 보강분 포함)
- [x] `infra_failure_001`에 overlay 판독 2건(`UNKNOWN`)이 추가됐지만 eval 라벨은 그대로 `time: null`
- [x] `correction_rerun_001`의 `verification=AGREED`는 evidence 소유 미결(4차 공지 🔴 1건)이고 eval 라벨(13:13:00)에는 영향 없음

### 2차 완료 정의

> 7개 시나리오 정답지가 `eval-expected/v2`로 존재하고, `pytest tests/eval`이 **0 failed**이며, candidate 매칭이 point error로 동작하고, 결과 파일만으로 「어느 계약·어느 지표 정의·어느 예측」을 채점했는지 재현할 수 있으면 2차 완료로 본다. #6·#7은 외부 입력 대기라 완료 정의에서 제외한다.

### 2차 검증 명령

```bash
python data/mock/validate_mock_pack.py            # 46 files / 7 scenarios PASS
python -m pytest tests/eval -q                    # 목표: 0 failed
python -m eval.run   --impl mock_pack:contracts --manifest mock_pack --stage candidate --run-id mock_e2e
python -m eval.score --prediction mock_e2e
```

---

## 회의에서 말할 한 줄 요약

> "`eval`은 공개 Contract 출력과 정답지를 입력으로 받아 4종별 점수와 Classification 지표를 계산하고, 결과를 파일로 남깁니다. **정답을 그대로 되돌려주는 구현과 일부러 틀리는 구현의 점수가 갈리는 것**으로 지표 계산이 맞다는 것을 검증했고, 데이터가 없어 못 내는 지표는 0이 아니라 사유와 함께 `null`로 나옵니다. `scenario_happy_001` 팀 fixture 채점과 partial 시나리오 fixture 부재가 남은 항목입니다."
