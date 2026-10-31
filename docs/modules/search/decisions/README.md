# search/decisions

조사·실험을 근거로 확정한 이 모듈 내부 결정을 둔다. 다른 모듈/제품 범위를 침범하는 결정은 여기서 단독 확정하지 않는다.

## 현재 결정

- [search-structure-2026-10-28.md](search-structure-2026-10-28.md) — Search 구조 확정: argon Coarse 0.5배속 → argon Fine 0.25배속 + `fine-gore-v1`, CV · AI Hub 후보 미포함. 성능 판정(E5)은 미결
- [decision-trace-2026-09-26.md](decision-trace-2026-09-26.md) — p4 종료, p3 기반 Search 전용 판단 근거 진단과 단계별 프롬프트 실험
- [fine-coarse-handoff-experiment-2026-09-28.md](fine-coarse-handoff-experiment-2026-09-28.md) — Coarse 관찰 Fine 인계·실선/중앙선 UNCERTAIN 지시를 진단 전용 profile로 분리 실험(운영 p3 불변)
- [search-argon-model-2026-10-27.md](search-argon-model-2026-10-27.md) — Search Coarse · Fine 모델 `gemini-4-argon` · argon tenant 경로 · Fine `fine-gore-v1` 문장. intent는 Flash 유지
- [gemini-3.8-proxy-baseline-2026-09-18.md](gemini-3.8-proxy-baseline-2026-09-18.md) — 프록시 경유 · `.env` 설정 방식. 모델 · 경로 항목은 2026-10-27 argon 결정으로 대체
- [challenger-policy.md](challenger-policy.md) — Failure decides the challenger 매핑·개방 절차 (A-2)
- [failure-taxonomy.md](failure-taxonomy.md) — search 실패 분류. 실행 실패(`JobExecution.failure_kind`)는 **확정**(2026-10-25, #297), 품질 분류는 **초안**
- [candidate-span-semantics-2026-09-10.md](candidate-span-semantics-2026-09-10.md) — CandidateEvent.span = coarse 후보 창(사건 구간 아님) 확정, 이슈 #22 B-2(김대원) 회신
- [fine-temporal-offset-base-2026-09-22.md](fine-temporal-offset-base-2026-09-22.md) — Fine at_offset_ms 기준 = 잘라낸 clip의 0초 확정, 이슈 #132(유소연) 회신

## 대체된 제안

- [search-final-structure-2026-10-01.md](search-final-structure-2026-10-01.md) — Flash 기준 최종 구조 제안. 구조는 2026-10-28 구조 확정으로 대체. 느린 영상 전송 채택 근거는 유효

## 접합 제안 (타 모듈 확인 대기)

- [monday-real-e2e-stream-boundary-2026-09-21.md](monday-real-e2e-stream-boundary-2026-09-21.md) — 월요일 Real E2E의 Search VIDEO stream ref 전달 경계. Case·Recording 접합과 입력 연결 방식은 확인 대기

종료된 p4 계획은 [p4 종료 기록](../experiments/p4-retired-2026-09-25/conditions.md)에 있다.
