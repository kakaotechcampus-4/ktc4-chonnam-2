# 김대원 (`eval`) 1차 완료 체크리스트

> **입력 버전:** Architecture v4 · Mock Pack `seed-v0`(`data/mock/manifest.json`) · `04_mock_validation_report.md` · `harness-v1-design.md`
> **상태:** Mock Pack이 `v1`으로 재생성되면 Scenario·Fixture 절을 갱신한다.

---

## 회의에서 먼저 볼 핵심

1. **`scenario_happy_001`의 팀 fixture를 읽어 실제로 채점 결과 JSON을 낸다.** `prediction_correct`는 만점, `prediction_wrong`은 rank·`event_type_hint`·plate 세 곳에서 어긋난 점수가 나온다.
2. **채점기가 오류를 잡는다는 증거를 보인다.** 두 fixture의 점수가 갈리는 것 자체가 지표 계산이 맞다는 근거다. 같은 점수가 나오면 채점기가 깨진 것이다.
3. **데이터가 없는 지표는 `0`이 아니라 `null` + 사유로 나온다.** Mock 예측에 구간이 없으므로 구간 기반 지표는 `null`이고, 그 이유가 결과 파일에 적혀 있다.
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

> `scenario_happy_001` 기준으로 **팀 공용 Mock fixture(`data/mock/eval/prediction_*.json`)와 정답지(`data/mock/expected/*.expected.json`)를 입력으로 받아**, 공개 Contract 필드만으로 채점을 수행하고, **결과 JSON을 파일로 생성**할 수 있으며, **데이터가 없어 낼 수 없는 지표는 `0`이 아니라 `null` + 사유로 표시**하고, `prediction_correct`와 `prediction_wrong`의 **점수 대비를 근거로 채점기 자체가 오류를 탐지한다는 것을 증명**할 수 있고, 세 소비 계약에 대한 **Consumer 검수 의견을 제출**했으면 1차 완료로 본다.

---

## 구현 체크리스트

### A. Input

- [x] 정답지(GT)와 manifest를 파일에서 로드할 수 있다.
- [x] 정답지 불변식을 검사해 위반 목록을 낸다(개수 일치·시간 순서·구간 범위·파일 존재·해시).
- [x] `data/mock/eval/prediction_*.json`을 **실제 파일 경로에서** 읽는다.
- [x] `data/mock/expected/scenario_happy_001.expected.json`을 정답지로 로드한다.
- [x] Mock fixture가 바뀌면 테스트가 깨진다 — Mock Pack이 v1로 재생성되면 여기서 드러난다.

### B. Core Flow

- [x] `python -m eval.run --impl <이름표>` 한 줄로 예측 산출물을 만든다.
- [x] `python -m eval.score --prediction <run_id>` 한 줄로 채점 결과를 만든다.
- [x] runner와 scorer가 분리되어 있고, 예측은 불변 산출물로 남는다.
- [x] 팀 Mock fixture 접합 확인은 **채점 파이프라인이 아니라 테스트로** 한다. Mock은 성능 자료가 아니므로 결과 JSON을 남기지 않는다 — `tests/eval/test_mock_pack_contract.py`.

### C. Output Contract (내가 생산하는 산출물)

- [x] 결과 JSON에 `run_id`·`impl`·`stage`·`manifest`·`gt_version`·`normalizer_version`·`code_commit`이 들어간다.
- [x] 위반유형 4종별 점수를 따로 낸다.
- [x] Classification(A tier) 지표를 낸다 — 5×5 혼동행렬 포함.
- [x] **어떤 Scenario를 확인했는지가 증빙에 남는다** — 시나리오로 파라미터화해 pytest 출력의 테스트 이름에 박히고, 정답지가 없는 `scenario_partial_001`은 사유와 함께 skip으로 같은 화면에 보인다. (Mock은 채점하지 않으므로 결과 JSON은 없다 — 성능 자료가 아니다.)

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
- [x] 팀 Mock fixture를 읽는 회귀 테스트가 있다 — `tests/eval/test_mock_pack_contract.py` 5개.

### G. Operational

- [—] ~~`UsageRecord`의 `latency_ms`·`cost.amount`를 읽는다~~ — **v1 범위 밖**(아래 제외 범위).

---

## Contract별 완료 조건

### `CandidateEvent` (Consumer)

- [x] `candidate_id`·`rank`·`event_type_hint`·`span.{start_ms,end_ms}`를 읽어 옮긴다 — `normalize.from_candidate_events`.
- [x] **필드 이름·단위 차이를 한 곳에서 흡수한다** — `event_type_hint`→`event_type`, `ranking_score`→`score`, `start_ms`(밀리초)→`t_start_sec`(초).
- [x] `event_type_hint` 값이 baseline 4종 안에 있는지 테스트가 고정한다 — 벗어나면 혼동행렬에 자리가 없어 조용히 miss로 집계된다.
- [ ] `uncertainties`가 비어 있지 않은 경우를 채점에서 어떻게 다룰지 정한다.
- [ ] Consumer 검수 의견 제출 — 아래 「검수에서 나온 것」 참조.

### `PlateReadout` / `OverlayTimeReadout` (Consumer)

- [ ] Consumer 검수 의견 제출 — 특히 **ABSTAIN 표현이 채점 가능한 형태인가**. 채점 구현은 v1이지만, 계약 형태에 대한 의견은 지금 내야 한다(계약이 닫히고 나면 바꾸기 어렵다).
- [—] ~~`abstained` / `observation.status` 채점 규칙 구현~~ — **v1로 이월**

### `UsageRecord` (Consumer)

- [ ] Consumer 검수 의견만 제출한다. **비용·Latency 지표 계산은 v1 범위 밖.**
- [x] eval batch 비용을 runtime 비용과 같은 숫자로 보고하지 않는다 — 비용을 아예 계산하지 않으므로 섞일 자리가 없다.

### eval fixture (Producer — 내가 검수 담당)

- [x] `expected` 파일이 Mock Runtime Output이 아니라 사람이 라벨링한 정답지임이 문서에 명시돼 있다.
- [x] `prediction_correct`가 `expected`의 **5개 값 전부**와 일치하는지 코드로 확인했다.
- [x] `prediction_wrong`이 rank·`visual_event_type`·`plate_value` **정확히 세 곳에서만** 어긋나는지 코드로 확인했다 — Scenario Catalog의 주장과 파일이 일치한다.
- [ ] **`scenario_partial_001`용 ground truth/prediction이 없다** — 검수 결과로 보고한다(`04_mock_validation_report.md` §23에 이미 기록됨).

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
| 3 | eval fixture(`prediction_*.json`)에 **구간이 없다** — `occurred_at` 타임스탬프뿐. 그래서 이 입력으로는 Recall@K·구간오차를 낼 수 없다(내면 "잰 적 없는 값을 0으로 적는" 것이 된다) | 유소연 | 보고 |
| 4 | `scenario_partial_001`용 eval fixture가 없다 | 유소연 | v1로 이월 (§23 기록됨) |
| 5 | **`abstained=true`인데 `observation.value`에 값이 남아 있다**(`"12나 34?6"`). 계약상 정상 — `readout`은 번호판을 최종 확정하지 않고 관찰만 제공하며 확정/보류는 `evidence`가 판단한다. 따라서 **eval이 이 값을 확정 판독으로 채점하면 안 된다** — 정직하게 보류한 구현이 오답이 되고 무리해서 읽는 쪽이 유리해진다. 테스트로 고정해뒀다 | 신유민 | 확인됨 (채점 규칙은 v1) |
| 6 | `CandidateEvent.uncertainties`를 채점에서 어떻게 다룰지 미정 | 서어진 | v1 |

> 2번이 가장 중요하다. 지금은 Mock이 시나리오 1건이라 드러나지 않지만, 실제 영상으로 넘어가면 **"이 후보가 어느 클립의 몇 초인가"를 아무도 계산할 수 없다.**

---

## Merge 전 셀프 체크 증빙

- [x] CLI 실행 결과 — `python -m eval.run` / `python -m eval.score`
- [x] 정상 출력 JSON — `eval/results/demo_correct.g1.json`
- [x] 오답 출력 JSON — `eval/results/demo_wrong.g1.json` (대비가 보이는 쌍)
- [x] 테스트 실행 결과 — 72개 통과
- [x] **팀 Mock fixture 접합 확인** — `pytest tests/eval/test_mock_pack_contract.py -v` 5개 통과
- [ ] Consumer 검수 의견 전달 — 위 표를 서어진·신유민·유소연에게 공유

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

## 회의에서 말할 한 줄 요약

> "`eval`은 공개 Contract 출력과 정답지를 입력으로 받아 4종별 점수와 Classification 지표를 계산하고, 결과를 파일로 남깁니다. **정답을 그대로 되돌려주는 구현과 일부러 틀리는 구현의 점수가 갈리는 것**으로 지표 계산이 맞다는 것을 검증했고, 데이터가 없어 못 내는 지표는 0이 아니라 사유와 함께 `null`로 나옵니다. `scenario_happy_001` 팀 fixture 채점과 partial 시나리오 fixture 부재가 남은 항목입니다."
