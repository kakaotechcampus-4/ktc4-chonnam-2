# [Case] Architecture Input Memo

> **성격:** 모듈 구조 설계 v4(`docs/architecture/module-architecture.md`) 작성의 근거가 된 Owner 자료조사 메모다. **조사 결과이지 결정이 아니다.** v4에 반영되지 않은 제안은 제안 상태로 남아 있고, 결정은 v4와 이 모듈의 `decisions/`에서만 한다. 문서 안의 `v3 §N`·`테크스펙 §N` 인용은 작성 당시(v3) 번호다.

**Owner:** 유소연

**관련 모듈:** search, readout, evidence, recording, web, eval, 공통기반/운영(김준영)

**근거 자료:** 대신고_테크스펙_v1.pdf / 대신고_모듈_구조_설계_v3.pdf / 대신고 백엔드 Runtime·Ops 고도화 설계 v1(김준영) / 본 대화 내 자료조사 1~6번 + PM 추가 요청(intent 평가체계·Agent framework 기준·correction 사건단위·불변규칙 검증)

---

### 1. 현재 추천 결론

1. **결론:** 상태기계는 INTAKE→SEARCHING→CANDIDATE_REVIEW→EVIDENCE_REVIEW→READY 5-state, TIME_HINT_EDIT/TIMELINE_REBASE(major)로 역방향 전이 허용.**근거:** 부분재실행표의 "폐기/재실행" 열(v3 p.42-43), "화면이 규칙을 재계산하면 안 된다" 원칙.**Architecture 영향:** 있음 — CaseView.stage enum으로 공식화 필요.
2. **결론:** input_fingerprint = hash(AnalysisScope 정규화값 + list_impls()의 활성 구현 이름표). PLATE_REREAD(correction·need 공통)는 이 값의 캐시 조회 자체를 예외적으로 건너뜀.**근거:** 캐시 규칙 원문(양쪽 문서 N5), RT9(list_impls 존재 이유), 부분재실행표 "번호판 다시 읽어줘" 행.**Architecture 영향:** 있음 — Data Contract에서 이 예외 규칙을 공식화해야 함(현재 어느 문서에도 없음, **담당자 제안**).
3. **결론:** CaseView 필드 확정(stage/progress[]/hints/candidates[]/evidence/requirements/package/running_jobs[]/notices[]). progress[]는 SCOPE/COARSE/FINE 범위로 한정, 이후 단계는 requirements/running_jobs가 대체.**근거:** 테크스펙 p.28-29 예시 + 팀 논의로 확정.**Architecture 영향:** 있음.
4. **결론:** needs_map은 확인된 kind 2개(OVERLAY_TIME_OCR→readout.read_overlay_time, PLATE_REREAD→readout.read_plate 재호출)만 매핑 가능. 전체 kind enum은 미정.**근거:** EvidenceNeeds 예시(양쪽 문서), 두 kind 외 다른 값은 어디에도 없음(직접 확인).**Architecture 영향:** 있음 — evidence 쪽 확정 대기.
5. **결론:** case_rev/selection_rev는 "selection_rev 상승 시 case_rev도 항상 상승, 역은 아님" 관계로 확정.**근거:** N9(동시성 안전), selection_rev 무효화 규칙(v1 p.24).**Architecture 영향:** 없음(기존 필드 관계 명확화).
6. **결론(추가 검토 제안):** Agent framework(LangChain/LangGraph) 미도입 유지, 판단 로직은 순수 함수(rerun_policy/needs_map) 유지 추천.**근거:** 원칙7(v3 p.6-7), RT2(지휘자 단일화, p.52), 6인·10주 제약.**Architecture 영향:** 없음(현행 유지) — 단, PM의 "AI 활용도 평가기준" 우려는 Product 판단 필요(6번 참고).

---

### 2. 확인된 기술적 제약

| 제약 | 근거 | Architecture/Contract 영향 |
| --- | --- | --- |
| intent LLM 호출은 1회로 제한 | v3 p.6-7, p.24 | 멀티턴 확장 시 공개 인터페이스·실패경계 재설계 필요(자료조사4) |
| case는 프롬프트 내용/OCR파라미터/영상코덱/시각출처우선순위/증거값 복사를 알면 안 됨 | v3 p.24 ⑨ | 접합부 필드는 opaque해야 함(예: list_impls 라벨) |
| case/ 폴더 grep 규칙(130MB·기한·프롬프트·VIDEO_OVERLAY)이 ⑨의 4개 규칙 중 1개만 실질적으로 커버 | 직접 대조 확인(전체모듈오너 점검) | God Module 방지 장치 보강 필요 |
| AnalysisScope.hint는 vehicle/free_text 2필드뿐, target_event_types는 별도 top-level 필드 | v3 p.30 | "상황"→유형분류, "위치" 처리 경로 미정(아래 4번) |
| usage_ledger 원 스키마/조회함수 전무 | v1 p.19/v3 p.39 | 김준영 Ops 문서 UsageRecord로 대부분 해결됨(4-4 참고) |
| JobRecord.status 원문엔 SUCCEEDED/RUNNING만 예시 존재 | JobRecord 예시(양쪽) | Ops 문서가 QUEUED/RUNNING/SUCCEEDED/FAILED/STALE 5종 제안 — 확정 필요 |
| case_rev 불일치 시 결과 폐기 규칙은 확정, 원자적 구현 방식은 어느 문서에도 없음 | N9(v3 p.42), Ops §4-1/§7 | 구현 시 compare-and-swap 등 방식 결정 필요 |

---

### 3. 현재 Module Architecture에 미치는 영향

**그대로 유지 가능한 것**

- 지휘자 단일화(case만 발주), EvidenceNeeds 값-only 패턴(RT2)
- 순수 함수 기반 rerun_policy/needs_map — Agent framework 필요성 근거 없음(조사 결과)

**수정 검토가 필요한 것**

- **현재 구조:** case는 JobRecord를 "Job=추가만"(재시도마다 새 행)으로 해석해 running_jobs[]/notices[] 설계.**조사 결과:** 김준영 Ops 문서는 "같은 행이 QUEUED→RUNNING→SUCCEEDED/FAILED/STALE로 갱신"되는 모델 전제.**왜 검토 필요한가:** 두 모델이 정면으로 다르며 view 조립 로직이 어느 쪽이냐에 따라 완전히 달라짐.**영향받는 모듈:** case, 공통기반(김준영).
- **현재 구조:** CaseView.progress[]는 SCOPE/COARSE/FINE만.**조사 결과:** Ops 문서 §10 예시가 "영상준비중~신고영상생성중" 5단계로 케이스 전체 매크로 단계처럼 보임.**왜 검토 필요한가:** JobRecord 개별 진행률과 케이스 매크로 단계가 같은 개념인지 다른 레벨인지 불명확.**영향받는 모듈:** case, web.

**판단 불가**

- manifest_summary 계산 방식(view 조립 시 조회 vs 캐시) — 근거 없음
- candidates[].evidence("EvidenceRecord 그대로")의 정확한 범위 — evidence 필드 확정 대기
- intent 멀티턴 확장 여부 — PM 결정 대기

---

### 4. 접합부 / Data Contract에 영향을 주는 내용

| 상대 모듈 | 방향 | 필요/제공 정보 | 확인된 제약 | 계약 단계에서 결정할 것 |
| --- | --- | --- | --- | --- |
| search | case→search | AnalysisScope(time_ranges, target_event_types, hint) | hint는 2필드뿐, "상황"→유형분류 로직 위치 미정 | 분류를 case(intent)가 할지 search가 할지 |
| search | search→case | AnalysisRun+CandidateEvent[](list_impls 포함) | list_impls()가 여러 impl 나열 시 "현재 활성" 구분 필드 없음 | case가 fingerprint에 쓸 "활성 구현" 식별 방법 |
| readout | case→readout | target_hint(값 전달), span | PLATE_REREAD 시 캐시 우회 발주가 readout엔 안 알려도 되는지 미확정 | 캐시 우회 규칙의 구현 위치(case만 인지하면 되는지) |
| evidence | evidence→case | EvidenceNeeds(kind/why/would_fill/optional) | 확인된 kind 2개뿐, 전체 enum 없음 | kind 전체 목록 확정 시점 |
| evidence | evidence→case | EvidenceRecord("그대로" 노출) | "그대로"가 전체복사/부분인지 불명 | EvidenceRecord 필드 확정 후 노출 범위 |
| recording | case→recording | 사용자 발화의 "위치" 힌트 전달 | AnalysisScope엔 location 필드 없음, recording/geocoder의 user_hint로 가야 함(확인) | case→recording 전달 경로/함수 필요 여부 |
| web | case→web | CaseView 전체 | manifest_summary/notices는 v3 원안에 없던 신규 필드, checks[]는 evidence RequirementReport 스키마 재사용 확인 | manifest_summary 계산주체, notices 최종 스키마 |
| 공통기반(김준영) | case↔job_queue/usage | JobRecord 행모델, input_fingerprint 소스, 예산 사전조회 | 3번의 행모델 충돌, usage_ledger→UsageRecord로 대부분 해결 | 행모델 일치, case의 예산 사전조회 함수 |

---

### 5. 열린 결정

| 결정할 문제 | 가능한 방향 | 현재 추천 | 추천 근거 | 확인 대상 |
| --- | --- | --- | --- | --- |
| JobRecord 새 행 vs 같은 행 갱신 | (A)새행 (B)갱신 | B(Ops안) | 표준 job queue 패턴, heartbeat/lease와 자연스럽게 부합 | 김준영 |
| input_fingerprint의 모델명/promptver가 opaque 라벨인지 직접 값인지 | (A)list_impls 라벨만 (B)개별 필드 | 확인 필요 | 프롬프트 비노출 원칙과 직결 | search/readout, 김준영 |
| Agent framework 도입 | (A)미도입 (B)일부 LLM화 | A | 원칙7/RT2, 6인10주 제약 | PM, 기술멘토 |
| intent 멀티턴 확장 | (A)1회 유지 (B)멀티턴 | 확인 필요(PM 별도 조사요청) | 4필드 추출 정확도에 좌우 | PM |

---

### 6. 충돌 / 상대 담당자 확인 필요

**A. 기존 Architecture와 충돌**

- God Module 방지 grep 규칙이 ⑨의 4개 규칙 중 1개만 실질적으로 커버함(직접 대조 확인). CI 규칙 보강 검토 필요 — 김준영(공통기반) 확인 필요.

**B. 다른 모듈과 충돌 가능**

- JobRecord 행 모델(case의 "추가만" 해석 vs 김준영 Ops의 "행 갱신" 모델) — **김준영과 우선 조율, 안 닫히면 전체 논의**.
- input_fingerprint 개별 필드 출처 — search/readout 담당자 확인 필요.
- candidates[].evidence "그대로" 범위 — evidence(김준영) 필드 확정 필요.

**C. Product/정책 결정 필요**

- Agent framework 도입 여부, "AI 활용도" 평가기준 대응 — PM 판단 필요.
- 원본 업로드 전략(recording 실측 대기, case의 fingerprint/budget 값에 직접 영향) — PM+recording 담당(정철원).

---

### 7. 후속 Data Contract에서 반드시 다룰 질문

1. JobRecord는 재시도마다 새 행을 추가하는가, 같은 행의 status를 갱신하는가?
2. input_fingerprint의 "구현 이름표"는 case가 list_impls()의 어떤 값을 "현재 활성"으로 판단하는가?
3. PLATE_REREAD의 캐시 우회 규칙을 case의 jobs 컴포넌트가 구현하는가, 공통 job_queue 레벨에서 구현하는가?
4. AnalysisScope.hint의 "situation" 텍스트를 target_event_types로 분류하는 책임은 case(intent)인가, search(routing)인가?
5. 사용자 발화의 "위치" 정보는 AnalysisScope를 거치지 않고 어느 함수로 recording/geocoder에 전달되는가?
6. EvidenceNeeds.kind의 전체 enum은 몇 개이며 언제 확정되는가?
7. CaseView.candidates[].evidence("EvidenceRecord 그대로")는 전체 복사인가 부분 필드인가?
8. case_rev 불일치 검사를 원자적 연산으로 어떻게 구현하는가?
9. CorrectionRecord에 selection_rev/candidate_id를 추가해 "사건 단위" 이력 추적을 가능하게 할 것인가?
10. intent LLM 평가체계(hallucination/애매표현/correction 반영)를 eval 모듈에 넣을 것인가, case 자체 관리로 둘 것인가?

---

### 8. 아키텍처 반영 우선순위

🔴 **Architecture v4 전 반드시 결정**

- JobRecord 행 모델(새행 vs 갱신) — running_jobs/notices 설계 전체가 좌우됨
- CorrectionRecord의 "사건 단위" 구조 부재(selection_rev/candidate_id 없음) — 학습로그 자산 품질에 영향

🟡 **Data Contract 단계에서 결정**

- input_fingerprint 필드 출처/공식, PLATE_REREAD 캐시 우회 규칙 명문화
- EvidenceNeeds.kind 전체 목록, candidates[].evidence 범위
- CaseView 최종 스키마(manifest_summary, notices), AnalysisScope.hint situation 분류 책임, location 전달 경로

🟢 **모듈 내부 Tech Spec에서 결정**

- 상태기계 5-state·부분재실행표 세부, intent 프롬프트 구현/평가체계, 예산 사전조회 쿼리 구현

---

### 9. 원본 자료 Reference

- **대신고_테크스펙_v1.pdf** — §7 Runtime Flow, §9 부분재실행표, 데이터모델 §3-5(case 소유), 인터페이스 §1/§7, 요청사항 A-C, 담당자별 자료조사(p.34-36)
- **대신고_모듈_구조_설계_v3.pdf** — 모듈5(case) 전체 템플릿(p.23-27), §5 계약 정의(④⑧⑨/부록), §8 Background Job/Failure Flow, §12 Red Team(RT2/RT4/RT9), 용어대조표(p.58)
- **대신고 백엔드 Runtime·Ops 고도화 설계 v1(김준영)** — JobRecord/UsageRecord 스키마, 재시도·lease 복구, 배포 구조
- **본 대화 자료조사 1~6번** — 상태기계/부분재실행표/작업발주·case_rev·fingerprint/자연어단서/CaseView구조/needs_map 매핑, PM 신규 요청(intent 평가체계·orchestration 및 Agent framework 기준·correction 사건단위·불변규칙 검증)