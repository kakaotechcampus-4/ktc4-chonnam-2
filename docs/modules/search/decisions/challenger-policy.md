# 챌린저 개방 정책 — Failure decides the challenger

> 결정일 2026-09-04 · 근거 `management/cross-cutting-decisions.md` A-2 · §3-(1)
> **담당:** 서어진(`search`) · **Consulted:** 김대원(`eval`) · **승인:** PM (주간 회의)
> 이 표는 원래 모듈 구조 설계 v3 §11-1-1이 소유했다. v4가 세부를 Owner의 결정으로 내리면서 여기로 옮겼다. `product-spec.md` §5 「보류」의 개방 조건과 `project-operating-plan.md` §3이 이 문서를 가리킨다.

## 원칙 2개

1. **베이스라인이 충분하면** model hunting보다 E2E 제품 완성에 집중한다.
2. **부족하더라도** "더 좋아 보이는 모델"을 무작정 비교하지 않고, **failure category가 지목하는 챌린저만** 연다.

## 매핑 — 실패 분류 → 열 수 있는 챌린저

| 실패 분류 | 열 수 있는 챌린저 | `product-spec.md` §5 보류 항목 |
| --- | --- | --- |
| `SEARCH_FAILURE` — 사건 자체를 찾지 못함 | VideoChat3 / SentrySearch / retrieval challenger | VideoChat3 · SentrySearch |
| `TEMPORAL_ORDER_FAILURE` — 전후 순서·시간 관계 판단 실패 | temporal verifier / TrafficRAG-inspired 확장 | TrafficRAG |
| `PRIMITIVE_FAILURE` — 차선·신호·차량 등 기본 시각 정보 인식 실패 | ADAS/CV perception 조사 | ADAS/CV Candidate Generator |
| `TARGET_ASSOCIATION` — 대상 차량 연결 실패 | tracking / lane-signal association / stronger VLM | — |
| `FINE_FALSE_NEGATIVE` — Coarse는 찾았는데 Fine이 제거 | Fine model / prompt / reference 개선 | TrafficRAG(고정 reference 먼저) |
| `COST` — 비용·지연이 감당 불가 | Local SLM / CV / self-host / fine-tuning 검토 | 자체 VLM fine-tuning / GPU VM |

실패 분류 이름의 원본은 `failure-taxonomy.md`(이 폴더)다. 여기 표의 이름이 그쪽과 달라지면 그쪽이 이긴다.

## 개방 절차

1. `eval`이 같은 정답지로 채점한 결과에서 실패 분류 통계가 특정 카테고리를 가리킨다.
2. `search` Owner가 **주간 회의에 안건으로 올린다** — 실패 분류 근거 + 열려는 챌린저 + 예상 비용.
3. PM이 승인한다. 안건으로 올리는 것이 곧 승인 경로다. 막기 위한 절차가 아니라 **다른 사람이 모르는 채로 기술 스택이 바뀌지 않게 하는 절차**다.
4. 개방 결정과 근거를 이 폴더에 1건 기록한다.

## 열지 않는 것

- 실패 분류가 가리키지 않는 챌린저.
- baseline 실측이 나오기 전의 챌린저 전부 (`ownership.md` §3 서어진 ③-6).
