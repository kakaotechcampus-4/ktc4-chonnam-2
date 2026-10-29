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
- `intent-llm-model-selection.md — 자연어 단서 구조화 LLM 최종 채택 Gemini 3.8 Flash(2026-09-22 재검토로 GPT-5 Nano에서 변경, §10) — §1~§9는 첫 결정 기록으로 보존. 2026-10-05 단일 점수(정확도 × 일관성)로 확정, §13. 2026-10-06 GPT-6 Luna · reasoning effort challenger 검증 — 기본값 유지, 비용 대안을 Luna `none`으로 교체, §14`
- `intent-llm-mlflow-review.md — intent LLM 평가에 MLflow를 도입하지 않는다(커스텀 하네스로 충분 · Elice 프록시 judge 연결 비용 · 내장 judge가 우리 판정을 대신 못 함), 원본 JSON이 남아 있어 미뤄도 이전 비용이 같다 + 재검토 조건 3개. eval 모듈 판단과는 별개 (2026-09-24, 10-14 갱신)`
- `agent-framework-adoption-criteria.md — LangGraph/Google ADK 등 agent framework를 지금 도입하지 않는다는 결정 + 재검토 트리거 4개`
- `input-fingerprint-implementation-label-deferred.md — input_fingerprint의 implementation label 조합 로직을 지금 만들지 않는다는 결정 + 재검토 트리거 2개 (이슈 #77)`
- `intent-hint-robustness-policy.md — 도메인 밖 입력은 스키마 변경 없이 null/low로 처리, 모순 정보는 마지막 값+confidence low 채택 (PM 재검토, 2026-09-22)`
- `reselect-observation-reuse.md — 다른 후보를 골랐다가 돌아오면(A→B→A) 같은 탐색 결과 안에서는 관찰(Fine·판독)을 재사용, 후보 목록이 바뀌면 버림 (W7 7순위, 2026-09-30)`
- `command-appended-job-records.md — command가 이번에 append한 JobRecord를 응답 body 밖으로 돌려준다(`execute_command()` → `CommandResult`), handle_command는 response만 (W7 8순위 8-7, 2026-10-05)`
- `empty-case-and-manifest.md — 빈 case 생성(`create_case()`, case가 `case_` + uuid4 발급) · adapter 없는 등록 · 업로드마다 `manifest_summary` 갱신(file/ok 수만, duration·range·failed는 계산 안 함, case_rev 유지, INTAKE 전용) (W7 8순위 8-12, 2026-10-05)`
- `case-store-mysql.md — CaseStore MySQL 영속화 1단계: 하이브리드 schema(cases + append-only 레코드 3종) · 호출자 transaction 참여 · FOR UPDATE/FOR SHARE · opt-in MySQL 테스트 (W7 8순위 8-6, 2026-10-05). adapter 제거는 2단계`
- `running-jobs-derivation.md — running_jobs를 case가 JobRecord 정산 기록(REFLECTED · STOPPED_WAITING · CANCELLED · SUPERSEDED, state JSON)으로 계산, 실행 기록 없으면 PENDING, 공개 함수의 running_jobs 인자 제거 (W7 8순위 8-11, 2026-10-06)`
- `start-analysis.md — 분석 시작(START_ANALYSIS): case당 타임라인 하나를 교체 가능한 port로 받고(임시로 등록 순서대로 이어 붙임), 탐지 유형 4개 전부 · 예산 150초/설정 1,000원 · 첫 fingerprint sha256 · 단서 구조화 대기 90초 (W7 8순위 8-1, 2026-10-07)`
- `jobexecution-read-port.md — JobExecution read port를 `CaseStore(executions=…)`로 주입, case가 자기 job_id로 조회해 running_jobs · Fine 실행 상태를 계산, 진입 함수의 job_executions · visual_verify_status 인자 제거 (W7 8순위 8-10, 2026-10-11)`
- `stop-analysis.md — 분석 중단(STOP_ANALYSIS): SEARCHING에서 기다리던 HINT_EXTRACT · COARSE_SEARCH만 CANCELLED로 정산하고 cancelled_job_ids로 돌려줌(Runtime cancel은 composition root), stage는 SEARCHING 유지 · coarse_search PARTIAL · case.analysis_stopped notice, 늦은 결과는 「기다리는 job만 받는다」 (W7 8순위 8-9, 2026-10-11)`
- `result-reflection.md — Worker T2 반영 진입점 reflect_execution(): case 행 잠금 → 처리한 execution_id(state JSON processed_executions)면 ALREADY_APPLIED → 기다리지 않는 job이면 NOT_APPLIED(정산 사유) → kind별 반영(HINT_EXTRACT · COARSE_SEARCH, 내용은 주입 ProducedReader), 반영기 없는 kind는 오류 (W7 8순위 8-8, 2026-10-11)`
- `observation-storage.md — 8-6 2단계: search · readout 결과는 common/runtime 결과 저장소(T1 같은 tx, 해석 없는 append-only — RT-10 Implementer 확인 대기), evidence는 get_view마다 재계산, ModuleAdapter는 남기고 무상태 StoredObservationAdapter를 CaseStore adapter_factory로 주입, 선택 관찰은 현재 후보 세대 · candidate_id로 거름(6.6순위 조건 2), T2 관찰 kind는 정산 + READY gate (W7 8순위 8-6, 2026-10-12)`
- `case-wait-timeout.md — case 대기 timeout: 타이머 없이 마감(발주 시각 + scope 실행 상한 + 30초)을 계산해 CaseView는 저장 없이 멈춤으로 보이고 command · T2가 STOPPED_WAITING으로 정산, 늦은 결과는 반영 안 함 · 실행 취소 안 함 · case.analysis_timed_out notice, 이번 판본은 COARSE_SEARCH만(단서 구조화 90초는 2026-10-27 hint-exhaustion.md로 닫음 — 두지 않음) (W7 8순위 8-9, 2026-10-13)`
- `real-e2e-scenarios.md — real 경로를 Mock 5개 시나리오로 확장(infra는 비동기 E2E 몫 · rebase는 범위 밖), 관련 asset은 선택 IncidentClip과 그 lineage로 고름(select_case_assets, 역할로는 안 거름), 재판독은 readout-native-hires, 대조는 case fixture 마지막 CaseView · 발견 사항 4건 (W7 4 · 5순위, 2026-10-12)`
- `report-video-export.md — 신고용 영상: 신고 상황 응답 뒤 case가 REPORT_VIDEO_EXPORT 자동 발주(배선은 recording export handler 뒤로 보류), case.report_video_not_generated는 응답 뒤 영상이 없는 동안 계속 붙이고 GENERATE_REPORT_VIDEO는 이전 발주가 있고 실행 중이 아닐 때만, 첫 발주를 버튼으로 받지 않음 (#351, 2026-10-13)`
- `hint-unclear-notice.md — 설명을 잘 이해하지 못했을 때(OK+confidence=low · ABSTAINED, FAILED 제외) 결과 화면에 search.hint_unclear(INFO · 비차단) notice, 판정은 반영 때 state JSON에 저장, EDIT_HINT는 입력형 판본 뒤 2단계 (#266, 2026-10-20)`
- `incident-clip-observation-input.md — (RT-10 · Runtime/Ops 확인 완료, web label 대기) 관찰 job 입력(후보 · 세대 · span · clip ref)을 발주 때 case state에 고정하고 CaseStore.observation_input으로 읽음(scope_ref는 JobRecord에 실음), IncidentClip 준비는 새 kind INCIDENT_CLIP_BUILD(Fine과 다른 실패 단위), Coarse 뒤 rank=1 자동 선택 → Fine → (NOT_OBSERVED 아니면) clip → 두 판독이 같은 clip, 현재 선택 · 세대일 때만 후속 발주, clip 실패 notice는 후속 (8-6 2단계 · RT-10(b) #297, 2026-10-23 · 10-24 갱신)`
- `reselect-while-preparing.md — 새 후보 준비 중 재선택 금지(6.6순위 조건 1): 「준비 중」 = 선택 후보 · 현재 세대로 입력이 고정된 관찰 job 중 case가 기다리는 것이 있음, check_reselect가 거부(not_allowed), 상황 응답 대기 · Fine 실패 · 이전 세대 · 입력 없는 job은 막지 않음, 재판독 중 버튼 처리는 web 확인 (2026-10-24)`
- `hint-exhaustion.md — 단서 구조화(HINT_EXTRACT) 소진 알림: 정산 사유 EXHAUSTED 추가, 빈 단서(hint_unclear 없음)로 첫 COARSE_SEARCH 발주, 이미 정산된 job은 NO_CHANGE(+사유) · 저장 안 함, 모르는 job · 다른 kind는 ValueError, 진입점 service.receive_hint_exhaustion(), 단서 구조화 case 대기 timeout은 두지 않음(소진 알림 + 사용자 중단) (#405, 2026-10-27)`
- `edit-hint.md — 설명 고쳐 다시 찾기: (A) 원문 다시 적기 + (가) 한 command EDIT_HINT{description} → SEARCHING 역행 · hints 비움 · case_rev +1 · HINT_EXTRACT 재발주(빈 설명이면 바로 COARSE_SEARCH, 예산 같음), 허용 조건은 현재 notice가 EDIT_HINT를 싣는가, 싣는 notice는 no_candidates · hint_unclear · analysis_stopped(탐색 근거 없을 때) · visual_event_not_observed(PM 승인), CorrectionRecord 없음 (#410, 2026-10-27)`
- `timeline-duration.md — 시간축 전체 길이(#184, case-view/v1.9): 최상위 timeline_duration_ms와 manifest_summary.duration_sec을 분석 시작이 받는 timeline port 값(CaseTimeline.duration_ms, ms 내림 #423) 그대로 싣는다, 첫 탐색 전에는 null · 0, state에 저장, rebase · range는 범위 밖 (2026-10-28)`
- `retry-search-while-waiting.md — 다시 찾기(#426): 결과 없음에서 RETRY_SEARCH면 SEARCHING으로 역행(안 하면 새 결과가 InvalidTransition으로 반영 안 됨), 탐색 job 대기 중에는 모든 notice에서 RETRY_SEARCH를 빼 command도 막힘, 대기 중 coarse_search는 FAILED가 아님 (2026-10-29)`
