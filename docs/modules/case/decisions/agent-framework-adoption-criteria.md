# Agent Framework(LangGraph/Google ADK 등) 도입 기준 — 지금은 도입 안 함

> 결정일 2026-09-18 · 담당 유소연(`case`) · 근거 아래 §2 WebSearch 조사(2026-09-18) + case 현재 구현(`domain.py`/`jobs.py`/`service.py`/`decisions/job-resume-identity-policy.md`)

## 1. 결정된 것

**case의 orchestration을 agent framework(LangGraph, Google ADK 등)로 바꾸지 않는다.** 지금의 손으로 짠 상태 기계(`CaseAggregate` 5-state + 7개 시나리오 분기)를 유지한다. "써보고 판단"이 아니라 **먼저 도입 기준을 정하고, 그 기준에 안 맞으면 안 쓴다**는 순서로 조사했다.

대신 §4에 **재검토 트리거**를 못 박는다 — 나중에 누군가 유행을 이유로 무작정 붙이는 걸 막기 위해서다.

## 2. 조사한 실제 기준 (출처 있음)

| 기준 | 출처 |
| --- | --- |
| 구조가 이미 알려진 워크플로우엔 동적 오케스트레이션이 비용·지연·예측불가능성만 더한다. 팀이 "모델이 결정해야 할 지점"을 하나도 못 짚으면 agent loop를 넣지 않는다 | [How to think about agent frameworks](https://www.langchain.com/blog/how-to-think-about-agent-frameworks) (LangChain 공식 블로그) |
| 단일 프롬프트, 도구 호출 1번, 단순 구조화 추출이면 LangGraph로 시작하지 않는다 | [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) (LangGraph 공식 문서) |
| LangGraph 도입 체크리스트: LLM 출력 기반 조건부 라우팅, 재시도, 중단 후 재개, human-in-the-loop 승인, 여러 LLM 호출 간 공유 상태가 필요하면 쓴다 | [LangGraph: The State Machine Behind Production AI Agents](https://nidly.substack.com/p/langgraph-the-state-machine-behind) |
| Google ADK는 eval·trace·observability가 실재한다(OTel 기반, Arize/Langfuse 등 연동) | [Tracing, Evaluation, and Observability for Google ADK](https://arize.com/blog/tracing-evaluation-and-observability-for-google-adk-how-to/) |

## 3. case 현재 상태와 대조

| 기준 | case 현재 상태 | 판단 |
| --- | --- | --- |
| 동적 tool 선택 | `jobs.py`가 명시적 함수 호출(`issue_plate_read` 등)만 한다 — LLM이 "다음에 뭘 부를지" 결정하는 지점 자체가 없다(intent LLM 1회 호출 제한 설계와도 방향이 맞다, `docs/modules/case/research/architecture-input-memo.md` §2) | 이득 없음 |
| Branching 증가 | 5-state + 7개 시나리오로 **이미 유한하게 정의됨**. LLM 출력이 아니라 도메인 상태(plate abstain 여부 등) 기반 분기다 | LangGraph 기준 미달 |
| 복잡한 재시도 | `JobRecord`/`JobExecution` 분리 + `decisions/job-resume-identity-policy.md`로 case 고유 재시도 규칙(새 job_id vs 같은 job_id+attempt)을 이미 손으로 구현·테스트 완료 | 이미 있음, 프레임워크로 바꿀 유인 적음 |
| Human-in-the-loop | correction/재확인 흐름이 이미 있지만 **버튼 클릭 기반**(`product/core-user-flow.md` "채팅 인터페이스는 만들지 않는다") — LangGraph의 interrupt 모델과 안 맞을 수 있다 | 이미 있음, 과설계 위험 |
| Trace/eval 편의 | 유일하게 그럴듯한 이득이지만, 이 프로젝트엔 이미 전용 `eval/` 모듈이 있고 "product runtime과 분리"가 원칙이다(`module-architecture.md` 모듈7 ⑥ "search/readout는 eval의 존재를 모른다", "eval-only branch 금지"). ADK 내장 트레이싱을 product 코드에 붙이면 이 경계를 건드릴 위험이 있다 | 오히려 `eval/`과 충돌 소지 |

**5개 기준 중 case에 뚜렷하게 이득인 게 하나도 없다.** 오히려 trace/eval 항목은 기존 아키텍처 원칙과 충돌 위험이 있다.

## 4. 재검토 트리거 (아래 중 하나라도 실제로 발생하면 다시 조사)

- [ ] LLM이 다음에 어떤 모듈/capability를 호출할지 **스스로 결정**해야 하는 지점이 실제로 생긴다(지금은 case가 코드로 전부 결정한다)
- [ ] 시나리오 분기가 지금 7개를 넘어 **조합적으로** 늘어나서 `domain.py`의 상태 기계로 손 관리가 안 되는 지점에 이른다
- [ ] `correction`/재확인 UX가 버튼 기반을 벗어나 **자유 대화형**으로 바뀐다(`core-user-flow.md`가 지금은 금지하고 있음 — 그 결정이 먼저 바뀌어야 함)
- [ ] `eval/` 모듈이 스스로 ADK/LangGraph 기반 트레이싱 도입을 결정하고, case가 거기 맞춰 계측을 노출해야 하는 상황이 생긴다(그때도 case가 단독 결정할 사안은 아님)

## 5. 다음 단계

- `docs/design-refinement`의 설계 고도화 문서에서는 이 문서를 참조만 하고 내용을 복제하지 않는다.
- 트리거가 실제로 발생하면 이 문서를 갱신하거나(재검토 후 유지 결정이면) 새 결정 문서로 대체한다(도입 결정이면).
