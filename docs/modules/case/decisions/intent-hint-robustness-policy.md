# Intent Hint 강건성 테스트 — 도메인 밖 입력 스키마·모순 정보 정책

> 결정일 2026-09-22 · 담당 유소연(`case`) · Consulted 없음(단독 결정 — 전례: `intent-llm-model-selection.md`·`intent-llm-eval-target-thresholds.md`도 동일)
> 근거: `research/intent-llm-robustness-test-design.md`(설계·미결 정리) · PM 재검토 피드백(2026-09-22)

## 1. 결정된 것

### 1.1 도메인 밖 입력에 대한 스키마 차원의 표현 — 지금은 스키마를 바꾸지 않는다

`IntentHintExtraction`에 `is_report_related` 같은 필드를 신설하지 않는다. "화장실이 어디예요?" 같은 도메인 밖 입력도 기존과 동일하게 "6개 필드 전부 null/low"로 처리한다("애매한 사고"와 "사고가 아예 아님"을 스키마상 구분하지 않음).

**이유:** 이 스키마는 아직 실제 프로덕션에 배선조차 안 됐다(`intent-llm-model-selection.md` §8 — `CaseAggregate.intake()`가 GPT-5 Nano를 호출하는 코드는 아직 없음). 실사용 연결이 없는 시점에 구분 필드부터 만드는 건 과설계다.

**재검토 트리거:** CaseView가 실제로 "이건 신고로 인식되지 않았어요" 같은 구분된 안내 문구를 보여줘야 하는 시점이 오면, 그때 필드 추가를 다시 검토한다.

### 1.2 모순 정보 카테고리의 정답 정책 — "마지막 값 채택 + confidence 무조건 low"

같은 슬롯(시간/차량/위치 등)을 한 문장 안에서 두 번 다르게 말한 경우, 마지막으로 말한 값을 채택하되 confidence는 무조건 low로 내린다. "전부 null" 대안은 채택하지 않는다.

**이유:** 이 실험 전체의 기조는 "모르면 null이되, 말한 걸 이유 없이 버리지는 않는다"이다(`research/llm-model-comparison-hint-extraction.md` §3 스키마의 nullable+escape hatch 설계와 같은 방향). 자기 정정("아니 19시요")은 실제 화법에서 마지막 값이 화자의 의도인 경우가 대부분이라 정보로서 가치가 있다. low로 표시해두면 downstream이 과신하지 않고 쓸 수 있다.

## 2. 결정하지 않은 것

**언어 처리 방침은 이번에도 정하지 않는다.** 비한국어 카테고리는 "정답값"을 하나로 못박지 않고 "표현만 다른 변형들이 서로 다르게 처리되면 안 된다(일관성)"만 1차 기준으로 둔다. 다국어 지원 여부/정책은 이 결정의 범위 밖이다.

## 3. 남은 것

- [ ] §1.2 정책을 `datasets/intent-hint-robustness-v1.jsonl`의 `case-10a/b/c`(모순 정보) `expected_notes`에 반영해 채점 기준을 구체화할지 결정
- [ ] 실측 실행 후 이 정책이 실제로 측정 가능한지(judge가 "마지막 값 채택" 여부를 판별할 수 있는지) 확인
