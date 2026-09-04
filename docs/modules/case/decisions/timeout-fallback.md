# Timeout / Long-running Job Fallback — 담당과 결정 시점

> 결정일 2026-09-04 · 근거 `management/cross-cutting-decisions.md` A-1
> **담당:** 유소연(`case`) · **Consulted:** 신유민(`web`)

## 결정된 것

- timeout 발생 여부와 작업 중단/계속 정책은 작업 lifecycle·orchestration 문제라 **`case`가 소유**한다.
- **timeout 수치는 baseline 실측 후에 정한다.** 지금 숫자를 박지 않는다. `search` Owner의 비용·지연 실측 결과가 나오면 이 문서에 값을 적는다.

## 이미 다른 문서가 정한 것 (여기서 다시 정하지 않는다)

- **timeout·중단 시 무엇을 보여줄지**는 `product/core-user-flow.md` §7(분석 중단 — 현재까지 후보 유지 + `이어서 찾기` + `조건 수정`)과 §22(결과 없음 — 출구 4개)가 정했다. 「직접 타임라인」 화면은 두지 않는다(§22).
- runtime의 lease·heartbeat·retry timing은 `common/runtime`이 소유한다(`module-architecture.md` §2 원칙 6). `case`가 정하는 것은 「얼마나 기다린 뒤 부분 결과로 전환하는가」와 「그때 어떤 Job을 취소/유지하는가」다.

## 남은 것

| 항목 | 상태 | 무엇으로 정하는가 |
| --- | --- | --- |
| Coarse 전체 timeout 값 | 미결 | `search` baseline 실측(영상 1시간당 지연) |
| Fine 후보당 timeout 값 | 미결 | 같음 |
| timeout 시 유지/취소하는 Job 집합 | 미결 | 부분 재실행 정책 표(`module-architecture.md` §7-4)와 함께 |
