# case 설계 고도화 — W7 Quality/Risk Burn-down 기준 문서

**날짜:** 2026-09-19 · **작성:** 유소연 · **브랜치:** `docs/design-refinement`

**목적:** "모듈별 설계 고도화" 요청의 case 몫. **W7 Quality/Risk Burn-down 단계에서 실제 고도화를 진행할 때 그대로 쓰일 기준 문서**다 — 여기서 우선순위를 정해두면 W7에서 다시 처음부터 뭘 할지 고민하지 않는다.

W5/W6 Real E2E 공지와는 별개의 기존 요청이지만, 오늘(2026-09-18) 진행한 Real E2E 작업(`feature/case-mock-real-service-adapter`)에서 실제로 드러난 병목·실패 유형을 반영해서 우선순위를 조정했다 — 추측이 아니라 오늘 직접 실행해서 관찰한 것들이다.

⚠️ 아래 §1·§4가 참조하는 `real_e2e.py`/`w6-real-e2e-happy-001.md`/`orchestration-service-layer.md`는 이 브랜치(`docs/design-refinement`)엔 아직 없다 — `feature/case-mock-real-service-adapter`가 develop에 병합돼야 링크가 유효해진다(§4 참고).

## 0. 범위 정의 — case가 직접 할 것과 아닌 것을 먼저 나눈다

Real E2E에서 발견한 항목을 "case 작업 중에 나왔다"와 "case가 고쳐야 한다"를 섞지 않는다. 아래 §1의 항목은 전부 case가 주도할 수 있는 것(단독이거나, case 주도 + 타 모듈 조율)만 담는다. case 파트가 아닌 것은 §2에 별도로 분리해서 "case가 의존하고 있는 외부 블로커"로만 표시한다.

## 1. 우선순위 목록

### 1순위 — Candidate span → Recording 변환 로직 설계

**문제:** `real_e2e.py`는 recording fixture가 이미 알고 있는 `span_resolutions[0]`을 그대로 재사용해서 `recording.resolve_span()`을 부른다. search의 `CandidateSpan`을 recording의 `resolve_span(timeline_ref, requested_range)` 입력으로 바꾸는 진짜 변환 로직이 없다 — 그래서 fixture 밖의(새 영상의) candidate span은 이 경로를 아예 못 탄다.

**왜 1순위:** 4순위(B5, 시나리오 확장)의 선행 조건이다. 이게 없으면 `happy_001` 밖으로 못 넓힌다.

**조율 필요:** case가 오케스트레이션을 주도하지만, 정확히 어떤 값을 어떻게 넘길지는 search·recording Owner와 계약을 새로 합의해야 한다.

**참고:** `src/daesingo/case/real_e2e.py`, `docs/modules/case/decisions/orchestration-service-layer.md` §7

### 2순위 — situation_response / observation_facts 워크플로우

**문제:** 오늘 데모(`demo_happy_001.py`)에서 실제로 관찰됨 — `situation_response`/`observation_facts`가 없어서 `FINAL_PACKAGE` 판정이 `UNKNOWN`에 걸리고 `build_report_package()`가 `PackageNotReady`를 던진다. `package`가 항상 `null`이다.

**왜 2순위(1순위와 병렬 가능):** 최종 신고 패키지 생성의 핵심 결손 — 다른 걸 아무리 잘해도 이게 없으면 신고 패키지를 영원히 못 만든다.

**이미 있는 것:** `Candidate.situation_confirmation` 필드가 case 도메인에 이미 있다(`NOT_ASKED` 상태). 워크플로우 자체는 case 몫이 맞다.

**조율 필요:** 사용자에게 실제로 묻는 UI는 web 몫이라 case 혼자 못 끝낸다. evidence의 정책(확정 안 된 situation 처리)과도 연결.

**참고:** `docs/modules/case/experiments/w6-real-e2e-happy-001.md` "알려진 단순화 2"

### 3순위 — Intent LLM 통합

**문제:** `CaseAggregate.intake()`가 여전히 구조화된 `hints`만 파라미터로 받는다. 원문 자연어를 구조화하는 실제 호출이 `domain.py`/`scope.py` 어디에도 없다.

**왜 3순위:** case의 헤드라인 책임(`tech-spec.md` §1)이자 실사용자 입력 경로의 시작점이지만, `docs/case-llm-model-comparison-20260916` 브랜치에 하네스·locked dataset·Elice 연동이 이미 준비돼 있어서 상대적으로 빨리 붙일 수 있다(API 키/모델 ID 확정이 유일한 외부 의존).

**서브 항목 (A4와 동시에 결정해야 함, 따로 뗄 수 없음):**
- **원 입력 텍스트 저장 여부/위치** — `CorrectionRecord`는 `previous_value → new_value`(수정 전/후 값)만 기록하고 사용자가 실제로 입력한 원문은 어디에도 안 남는다. "원 입력 → 최초 추출 → 수정 → 최종값"을 사건 단위로 재현하려면 A4를 만들 때 같이 결정해야 한다.
- **UsageRecord 구현 요청(common/runtime)** — LLM 호출 원본 로그(프롬프트·응답·모델명·비용·latency)를 남길 계약이 문서(`module-architecture.md`)엔 있지만 코드는 아직 없다(`common/job_execution.py` 확인함). case가 자체 로그를 새로 만들기보다 common/runtime에 `UsageRecord` 구현을 요청하고 case는 거기 맞춰 채우는 쪽을 제안한다.

**참고:** `docs/case-llm-model-comparison-20260916` 브랜치 전체, `research/llm-model-comparison-hint-extraction.md`

### 3.5순위 — Correction 로그 재사용 정책 미결 5건 종결

**상태:** Issue #74에 case 제안 초안을 코멘트로 게시 완료(2026-09-19). PM 승인 대기 중.

**내용:** 동의 문구/저장 위치, 익명화 수준의 Contract화, 보관기간, 철회 처리, 1단계(평가)/2단계(학습) 고지 분리 — 5건. 배포 전 self-review(`docs/management/pre-deploy-security-review.md`)가 이미 이 항목의 실제 구현 여부를 확인하도록 돼 있어서, 배포 직전에 처음 정하면 구현과 문구를 동시에 고쳐야 하는 위험이 있다.

**참고:** `docs/modules/case/decisions/correction-log-reuse.md`, Issue #74, Issue #71(영상 자산 lifecycle — 경계 분리됨)

### 4순위 — `real_e2e.py` 시나리오 확장 (1/7 → 7/7)

**문제:** 지금 recording→search→readout→evidence real 연결은 `scenario_happy_001` 하나로만 검증됐다. correction rerun(supersede 체인), plate reread, unknown/abstain, infra failure(재시도), relative rebase, empty — Mock이 이미 커버하는 6개 시나리오는 Real 경로로 하나도 안 됐다.

**왜 4순위:** 1순위(A3)가 풀려야 이어서 할 수 있다. 새 능력을 여는 게 아니라 기존 걸 더 넓게 검증하는 확장 작업.

**참고:** `src/daesingo/case/real_e2e.py`, `tests/case/test_real_e2e.py`

### 5순위 — asset_refs 선택 로직

**문제:** `real_e2e.py`의 `asset_refs`도 recording fixture 객체가 이미 아는 목록을 그대로 재사용한다 — "이 case에 어떤 asset_facts가 관련 있는지"를 스스로 판단하는 로직이 없다.

**왜 5순위:** 작고, 2순위(situation_response/observation_facts)가 먼저 풀려야 의미가 커진다 — 패키지 조립 자체가 막혀 있는 동안은 다듬어도 효과가 잘 안 보인다.

### 6순위 — HTTP 진입점 / transport

**문제:** `case.get_view(case_id, store=store)`는 만들었지만(오늘 완료) 이걸 실제로 네트워크에 노출하는 FastAPI 같은 transport 계층이 없다.

**왜 6순위:** case 단독 결정 사안이 아니다 — `api/` 모듈(현재 껍데기만 있음) 또는 web 쪽 몫일 가능성이 높다. "만들기"보다 "누가 만들지부터 확인"이 먼저라 순서상 뒤로 미룬다(급하지 않다는 뜻은 아님).

**참고:** `src/daesingo/case/service.py`(`get_view`), `src/daesingo/case/store.py`(`CaseStore`), `docs/modules/case/experiments/w6-real-e2e-happy-001.md` 완료 증빙 표

### 7순위 — Orchestration 평가 지표

**문제:** 지금까지 이야기한 평가(intent-llm-model-comparison 등)는 전부 "LLM이 내용을 잘 뽑았는가"만 잰다. "Case가 올바르게 오케스트레이션했는가"는 따로 재는 게 없어서, 나중에 "LLM은 잘 답했는데 Case가 잘못 재실행했다"와 "Case는 맞는데 모델이 잘못 추출했다"를 구분할 수 없다.

**지표 후보 7개, 실현 가능성으로 3단 분류(`job_records`/`correction_records`/`InvalidTransition`을 다시 확인해서 나눔):**

| 분류 | 지표 | 비고 |
| --- | --- | --- |
| **바로 가능** | correction 후 필요한 단계만 재실행되는 비율 | `case.correction_records`(어떤 필드 고쳤는지) + `case.job_records`(그 뒤 뭘 재발주했는지) 대조 + 기존 부분 재실행 정책 표 기준 |
| **작은 계측 추가로 가능** | 잘못된 stage transition 0건 | `domain.py`에 `InvalidTransition` 예외가 이미 있음 — 지금은 그냥 죽기만 하고 카운트가 안 남는다. 잡아서 세기만 하면 됨 |
| **작은 계측 추가로 가능** | 불필요한 재실행률 | `job_records.force_rerun` 비율로 근사 시작 가능 |
| **새 인프라 필요** | 정상 workflow completion rate | 여러 case에 걸쳐 집계해야 하는데 `CaseStore`가 in-memory뿐이라 case가 끝나면 데이터가 사라짐(persistence 필요, A1 인접) |
| **새 인프라 필요** | 필요한 Job 발주 누락률 | "필요한"의 기준(정책)을 코드로 인코딩하는 추가 설계 필요 |
| **새 인프라 필요** | stale 결과 적용 오류 | `JobExecution`(A1, common/runtime) 필요 |
| **새 인프라 필요** | case당 latency/token/cost | `UsageRecord`(3순위 서브 항목과 동일 — common/runtime) 필요 |

**왜 7순위:** "바로 가능" 1건, "작은 계측" 2건은 사실 비용이 낮아서 더 앞에서 같이 해도 되지만, 나머지 4건이 A1/UsageRecord(둘 다 case 파트 아님)에 종속적이라 전체 항목으로는 뒤로 뒀다.

## 2. case가 의존하는 외부 블로커 (case 파트 아님, 참고용)

case가 직접 고칠 수 없고, 각 모듈 Owner의 작업을 기다리거나 그 결과를 그대로 쓰는 항목이다. 이 문서의 우선순위 대상이 아니다.

| 항목 | 소유 | 현재 상태 |
| --- | --- | --- |
| Worker/실행 인프라(`get_job_executions()` 등) | `common/runtime`(정철원 구현) | `worker/` 폴더가 비어있음. `service.py`의 `fetch_case_view_inputs()`가 이 메서드를 아예 안 부르므로 오늘 E2E 목표엔 영향 없었음 |
| search/readout 내부 실제 AI·OCR | 각 모듈 Owner | 여전히 `FixtureSearchService`/`FixtureOcrProvider` — 오늘 증명한 건 "파이프라인 배선이 안 끊긴다"이지 "AI 품질이 좋다"가 아님 |
| `time_source_candidates` 공개 함수 미노출 | `recording` | `RecordingFixture` pydantic 모델에 이 필드 자체가 없음. `real_e2e.py`가 raw fixture로 우회 중 |

## 3. 별도로 이미 결정 완료된 것

- **Agent framework(LangGraph/Google ADK) 도입 기준** — 지금은 도입하지 않기로 결정. 재검토 트리거 4개 명시. → `docs/modules/case/decisions/agent-framework-adoption-criteria.md`

## 4. 오늘 Real E2E 실행 근거

이 문서의 §1 우선순위는 다음 실행 결과를 근거로 한다(2026-09-18, `feature/case-mock-real-service-adapter`):

- `src/daesingo/case/real_e2e.py` — recording→search→readout→evidence real 연결 구현
- `docs/modules/case/experiments/w6-real-e2e-happy-001.md` — `scenario_happy_001` real E2E 실행 로그
- `docs/modules/case/decisions/orchestration-service-layer.md` §6·§7·§8 — search/evidence/`get_view()` real 교체 과정에서 확인한 것들

⚠️ **위 3개 파일은 이 문서를 쓰는 시점(`docs/design-refinement`)엔 아직 없다.** `feature/case-mock-real-service-adapter` 브랜치에만 있고 아직 develop에 병합 전이다 — 그 브랜치가 병합되면 이 참조가 유효해진다. 지금 이 링크를 따라가려면 `feature/case-mock-real-service-adapter`를 별도로 체크아웃해야 한다.

## 5. 완료 조건 — 이 문서의 각 항목을 "끝났다"고 부르는 기준

이번 고도화 작업은 다음 사이클을 한 단위로 삼는다:

```
조사 문서 → 선택안과 근거 → eval dataset → baseline 측정 → 개선안 구현 → 동일 dataset 재평가 → ADR
```

**"도입하지 않음"도 정상적인 완료 조건이다.** 사이클이 반드시 "구현"까지 가야 끝나는 게 아니다 — 조사 후 "지금 구조가 이미 충분하고, 바꾸면 오히려 재현성·테스트성이 나빠진다"는 결론도 완료다. `decisions/agent-framework-adoption-criteria.md`가 이미 이 패턴을 실제로 증명했다 — 조사 문서(§2 출처) → 선택안과 근거(§3 대조표) → ADR(재검토 트리거 포함, §4)까지 거쳤고, eval dataset/baseline 측정 단계는 "측정할 대상 자체가 없다"(agent framework를 실제로 붙여보지 않고도 판단 가능한 정성적 기준)는 이유로 정당하게 생략했다. case의 현재 구조는 이미 단순하고 deterministic한데, 여기서 괜히 Agent framework로 바꾸면 재현성·테스트성이 오히려 나빠질 수 있다는 게 바로 그 판단의 핵심 근거였다.

**어떤 항목에 전체 사이클이 필요한지, 어떤 항목은 생략 가능한지:**

| 항목 | 사이클 적용 범위 | 이유 |
| --- | --- | --- |
| 7순위(Orchestration 평가 지표) | 전체 사이클 | "개선"이 실제로 측정 가능한 수치 변화라 baseline/재평가가 의미 있다 |
| 3순위(Intent LLM 통합) | 전체 사이클(이미 진행 중) | `intent-llm-model-comparison` 실험이 이미 eval dataset(locked v1)·baseline 측정 단계를 밟고 있다 |
| 1·2·4·5·6순위(A3/D8/B5/B6/A2) | 축약 — 조사 문서/선택안/구현/테스트까지만 | 순수 배선·설계 작업이라 "eval dataset로 개선폭을 측정"할 대상 자체가 없다(정답/오답이 명확한 정합성 문제) — 테스트 통과 여부가 곧 검증이다 |
| 3.5순위(correction 로그 정책) | 사이클 밖 — 정책/승인 프로세스 | 성능 개선이 아니라 동의·법무 성격이라 이 사이클이 안 맞는다. Issue #74의 완료 조건 체크리스트를 그대로 따른다 |

새 항목이 이 문서에 추가될 때도 "성능/품질 개선 항목인지, 순수 배선 항목인지, 정책 항목인지"를 먼저 구분하고 맞는 사이클(또는 생략)을 적용한다.
