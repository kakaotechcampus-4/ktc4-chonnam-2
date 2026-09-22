# case/decisions

조사·실험을 근거로 확정한 이 모듈 내부 결정을 둔다. 다른 모듈/제품 범위를 침범하는 결정은 여기서 단독 확정하지 않는다.

## 현재 결정

- `timeout-fallback.md — timeout 담당·결정 시점 (A-1)`
- `correction-log-reuse.md — correction 로그 재사용 전제·익명화 3줄 (C-4)`
- `budget-krw-normalization.md — 예산(KRW) vs 비용(USD) 통화 정규화, Mock 기본값 (P3-1, 이슈 #19)`
- `candidate-stale-revision-display.md — CaseView.candidates[].timeline_revision/stale_revision 필드 신설 (P1-10, 이슈 #18 위임)`
- `generic-warn-package-and-situation-response.md — situation_confirmation·unconfirmed_fields 신설, EVIDENCE/FINAL_PACKAGE WARN→READY 투영 (이슈 #25 A절·댓글)`
- `eval-round2-ground-truth-and-usage.md — plate_reread_001·unknown_abstain_partial_001 참값 라벨 확정, STALE attempt UsageRecord 컨벤션 (이슈 #22 B-3·B-4)`
- `orchestration-service-layer.md — service.py/ModuleAdapter Protocol 도입 + Mock→Real 교체(W5/W6) 진행 기록 (RealAdapter 실측 real 교체 범위, case.get_view() 진입점)`
- `intent-llm-eval-target-thresholds.md — intent LLM 평가 목표치(schema_compliance/field_accuracy/hallucination/missed rate) 딥리서치 기반 1차 설정 (2026-09-19 실측 완료, 3개 후보 전부 통과 — §4)`
- `intent-llm-model-selection.md — 자연어 단서 구조화 LLM 최종 채택 Gemini 3.8 Flash(2026-09-22 재검토로 GPT-5 Nano에서 변경, §10) — §1~§9는 첫 결정 기록으로 보존`
- `agent-framework-adoption-criteria.md — LangGraph/Google ADK 등 agent framework를 지금 도입하지 않는다는 결정 + 재검토 트리거 4개`
- `input-fingerprint-implementation-label-deferred.md — input_fingerprint의 implementation label 조합 로직을 지금 만들지 않는다는 결정 + 재검토 트리거 2개 (이슈 #77)`
- `intent-hint-robustness-policy.md — 도메인 밖 입력은 스키마 변경 없이 null/low로 처리, 모순 정보는 마지막 값+confidence low 채택 (PM 재검토, 2026-09-22)`
