# search 실패 분류 (Failure Taxonomy) — 초안

> **상태: 초안. Owner(서어진) 확정 전.** 2026-09-04 문서 정리에서 만들었다.
> 이 목록은 새로 정한 것이 아니다. 모듈 구조 설계 v3와 `modules/eval/experiment-guide.md` 템플릿에 흩어져 있던 이름을 **소유자 폴더 한 곳**으로 모은 것이다. v4는 「실패 taxonomy 기록」을 `search` 책임으로 두고 세부 이름은 Data Contract로 내렸다(`module-architecture.md` §4-모듈2 ②, §13-2).
> `eval`은 이 이름을 **복제하지 않고 가리킨다.** `experiment-guide.md` `[FAILURE]`, `initial-evaluation-plan.md` §6이 이 문서를 본다.

## stage

`COARSE` · `FINE`

## kind (search)

| 이름 | 의미 | 챌린저 매핑(`challenger-policy.md`) |
| --- | --- | --- |
| `SEARCH_FAILURE` | 사건 자체를 후보에 올리지 못함 | SEARCH_FAILURE 행 |
| `PRIMITIVE_FAILURE` | 차선·신호·차량 등 기본 시각 정보 인식 실패 | PRIMITIVE_FAILURE 행 |
| `TEMPORAL_ORDER_FAILURE` | 신호 → 정지선 → 통과 같은 전후 순서 판단 실패 | TEMPORAL_ORDER_FAILURE 행 |
| `TARGET_ASSOCIATION` | 다른 차량/대상을 사건 주체로 연결 | TARGET_ASSOCIATION 행 |
| `FINE_FALSE_NEGATIVE` | Coarse는 찾았는데 Fine이 제거 | FINE_FALSE_NEGATIVE 행 |
| `COST` | 비용·지연 상한 초과로 중단 | COST 행 |
| `INFRA` | timeout / API / 파이프라인 오류 (공통) | 챌린저 대상 아님 |

## Owner가 확정할 때 함께 볼 후보 이름

`experiment-guide.md` §13이 다른 이름 체계를 제안했다. 확정 시 흡수·병합 여부를 정한다.

```text
RANKING_FAIL       후보에는 있지만 Top-K 밖          → SEARCH_FAILURE의 하위로 둘지 별도로 둘지
EVENT_CLASS_FAIL   사건 유형 판단 오류               → Fine/Classification 실패. FINE_FALSE_NEGATIVE와 구분할지
OVERCONFIDENT      불확실하지만 확정값 반환          → search에서는 VisualEvidence.uncertainty 미기록. readout에도 같은 항목 필요
UNKNOWN            아직 원인 불명
```

## 기록 규칙

- `AnalysisRun`에 stage + kind로 기록한다. 이름만 적고 자유 텍스트로 대신하지 않는다.
- 이 분류 통계가 특정 카테고리를 가리킬 때만 챌린저를 연다(`challenger-policy.md`).
- 번호판·화면시각 실패는 여기 넣지 않는다 → `modules/readout/decisions/failure-taxonomy.md`.
