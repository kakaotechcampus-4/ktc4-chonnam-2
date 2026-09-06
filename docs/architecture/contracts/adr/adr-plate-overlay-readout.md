# ADR: PlateReadout / OverlayTimeReadout Contract Decision

**Contract:** ⑥ `PlateReadout / OverlayTimeReadout`

**Contract Lead:** 신유민

**Runtime Producer:** `readout`

**Consumer:** `evidence`(김준영), `eval`(김대원)

**기준 문서:** Module Architecture v4, `PlateReadout / OverlayTimeReadout` Final Contract 후보

**상태:** Accepted 후보

---

# 1. Context

`readout`은 선택된 사건의 Source-derived `Incident Clip`에서 번호판과 화면 Timestamp를 읽는 모듈이다. 단, `readout`은 값을 최종 확정하지 않고 관찰값과 근거만 생산한다. 최종 번호판, 최종 발생 시각, 신고 가능 여부는 `evidence`가 판단한다.

Consumer Review에서는 다음 요구가 확인되었다.

- `abstain`은 Case/Search 실패가 아니라 번호판 확정 보류 상태로 표현해야 한다.
- OCR 문자열뿐 아니라 실제로 어느 차량을 대상으로 읽었는지 association 근거가 필요하다.
- 초기에는 `evidence`도 충분한 관찰 정보를 받아야 한다.
- `eval`은 기본 평가는 `best_frame + consensus` 중심으로 가능하되, 실패 진단에는 상세 frame/sample 정보가 필요할 수 있다.
- v4 정책상 Verified Overlay Timestamp를 우선하므로, 초기에는 선택된 사건마다 Overlay OCR을 실행하는 편이 안전하다.

---

# 2. Decision

다음 결정을 채택한다.

1. Plate `abstain`은 `Observation.status = NEEDS_REVIEW` + `abstained = true`로 표현한다.
2. `PlateReadout`에는 `target_association`을 포함해 실제 판독 대상과 association 근거를 남긴다.
3. 초기 v1에서는 `evidence`와 `eval` 모두 충분한 관찰 정보를 받을 수 있게 하고, 이후 비용이 확인되면 projection 범위를 줄인다.
4. `OverlayTimeReadout`은 초기에는 선택된 사건마다 실행한다.
5. overlay 존재 탐지 후 조건부 OCR은 추후 cost/latency 최적화안으로 남긴다.
6. 번호판 disagreement는 사람이 읽을 수 있는 masking text와 `disagree_positions[]`를 함께 제공한다.
7. `eval`에서는 abstain을 단순 정답 회피로 합치지 않고 별도 metric으로 분리한다.

---

# 3. Alternatives

## A. 단순 최종값 중심 Contract

`readout`이 번호판 문자열과 timestamp 값만 넘기는 방식이다.

**채택하지 않은 이유:**

confidence가 정답성과 약하게 연결되고, 잘못된 차량 번호판을 읽는 경우를 downstream에서 검토할 수 없다. `evidence`와 `eval` 모두 실패 원인을 진단하기 어렵다.

## B. Consumer별 최소 projection만 제공

`evidence`에는 요약만, `eval`에는 상세값만 제공하는 방식이다.

**채택하지 않은 이유:**

초기 v1에서는 Contract 안정성과 검증 가능성이 더 중요하다. 김준영/evidence Review에서도 초기에는 충분한 관찰 정보를 받는 방향을 선호했다. payload/storage 비용은 실제 측정 후 줄이는 편이 안전하다.

## C. Overlay OCR을 presence detection 이후 조건부 실행

Overlay가 있을 것 같은 경우에만 OCR을 실행하는 방식이다.

**지금 채택하지 않은 이유:**

v4는 Verified Overlay Timestamp 우선 정책이다. presence detection이 overlay를 놓치면 가장 강한 시간 근거를 잃는다. 따라서 초기에는 선택된 사건마다 Overlay OCR을 실행하고, C안은 cost/latency가 문제로 확인된 뒤 recall/false negative benchmark를 통과하면 적용한다.

---

# 4. Consequences

## 장점

- `readout = 관찰`, `evidence = 확정` 경계가 유지된다.
- 번호판 OCR 결과뿐 아니라 대상 차량 association까지 검토할 수 있어 잘못된 차량 판독 위험을 줄인다.
- `abstain`이 정상적인 보류 상태로 표현되어 전체 Search 재실행을 피할 수 있다.
- `eval`이 정답률, wrong accept, abstain, association 실패를 분리해 평가할 수 있다.
- Overlay Timestamp를 초기부터 안정적으로 수집해 v4의 Verified Overlay 우선 정책과 맞출 수 있다.

## Trade-off

- 초기 payload와 저장 정보량이 늘어난다.
- Overlay OCR을 선택 사건마다 실행하므로 cost/latency가 증가할 수 있다.
- `target_association`, `validation`, `samples` 등 필드 의미를 Mock과 구현에서 일관되게 유지해야 한다.

---

# 5. Follow-up

- Final Contract에서 `target_association` 상태와 근거 필드를 명시한다.
- `OverlayTimeReadout.validation`의 `format_ok`, `monotonic_ok`, `duration_match_ok`, `sample_count` 의미를 명시한다.
- Eval 지표에서 Exact Plate Accuracy, Wrong Accept Rate, Abstention Rate, Abstention Recall을 분리한다.
- C안으로 최적화할 경우 Overlay presence detection benchmark 기준을 별도 Tech Spec에서 정한다.