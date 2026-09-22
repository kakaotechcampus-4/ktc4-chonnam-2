# 자연어 단서 구조화 LLM — GPT-5 Nano 채택

> 결정일 2026-09-19(실측) · 담당 유소연(`case`) · Consulted 없음
> 근거: `experiments/intent-llm-model-comparison/results/summary.md`(judge_run_id `20260919T170342Z`) · `research/llm-model-comparison-hint-extraction.md` §5·§6·§9 · `decisions/intent-llm-eval-target-thresholds.md` §1

## 1. 결정된 것

**자연어 단서 구조화("사용자 자연어 단서를 구조화한다", `tech-spec.md` §1) 호출에 GPT-5 Nano를 쓴다.** Gemini 3.1 Flash-Lite / Claude Haiku 4.5는 채택하지 않는다.

## 2. 실측 결과 요약

`datasets/intent-hint-eval-v1.jsonl`(카테고리당 1케이스, 총 7케이스) 기준, Elice ML API 경유 실측(2026-09-19):

| model | schema 준수율 | field 정확도 | hallucination | missed | 평균 latency | 총 비용(KRW) |
| --- | --- | --- | --- | --- | --- | --- |
| **gpt-5-nano** | 100% | **100%** | **0%** | **0%** | 12,745ms | 8.34 |
| gemini-3.1-flash-lite | 100% | 93% | 2% | 0% | 2,676ms | 2.38 |
| claude-haiku-4-5 | 100% | 95% | 0% | 2% | 3,417ms | 34.21 |

필드별·카테고리별 전체 분해와 judge의 필드별 판정 근거(`reason`)는 `results/summary.md`와 그 안에 적힌 `predictions/<model>/<case_id>.judge.20260919T170342Z.json`에 있다 — 이 문서에 옮겨 적지 않는다.

## 3. 목표치 대조

`decisions/intent-llm-eval-target-thresholds.md` §1 목표치 대비, **3개 후보 전부 통과**했다(schema ≥99%/field ≥70~75%/hallucination ≤5%/missed ≤10%). 즉 이 목표치만으로는 세 후보를 가르지 못한다 — §1.1이 이미 경고한 대로 n=7(필드 단위 n=42)이 작아 퍼센트 차이(93%~100%)를 소수점 단위로 믿지 않는다. 그래서 최종 선택은 §4/§5의 정성적 근거로 갈랐다.

## 4. 왜 GPT-5 Nano인가 — 다른 두 후보를 제외한 이유

- **Gemini 3.1 Flash-Lite 제외 이유**: (1) `research/...` §5가 이미 지적한 **Preview 상태** — GA 전환 전까지 프로덕션에 커밋하기엔 이르다는 우려가 실측과 무관하게 그대로 남아있다. (2) 실측에서도 `vehicle_hint`(86%)·`confidence`(71%) 필드가 셋 중 가장 약했고, 애매 3종 `confidence:low` 인정률도 2/3로 유일하게 100% 미만이었다 — "애매하면 확정하지 않는다"는 이 기능의 핵심 안전장치를 가장 못 지켰다.
- **Claude Haiku 4.5 제외 이유**: (1) 셋 중 최고가(₩34.21, GPT-5 Nano의 약 4.1배) — 이 볼륨에서 절대액은 작지만 세 후보 품질이 비슷한 이상 비용 차이가 그대로 감점 요인이다. (2) "상대시간_표현" 카테고리에서 67%로 셋 중 가장 낮았다 — 이 카테고리는 스키마 설계 자체가 "상대 시간을 절대 시각으로 임의 변환하지 않고 원문 그대로 보존"을 목표로 두는 지점이라(README "카테고리" 표) 가벼운 실패가 아니다.
- **GPT-5 Nano를 고른 이유**: 필드 정확도 100%(측정된 모든 필드·모든 카테고리에서 만점), hallucination/missed 둘 다 0%, 애매 3종 `confidence:low` 인정률 3/3. `research/...` §6의 "실측 우선순위 1순위"(최저가권 + 종료 공지 없음) 추천과도 일치한다 — 추천이 실측으로 확인된 사례다.

## 5. Latency 트레이드오프 — 이 결정에서 가장 중요한 단서

GPT-5 Nano는 평균 12,745ms로 나머지 둘(2,676ms/3,417ms)보다 **3.7~4.8배 느리다.** `research/...` §5의 후보 비교표엔 애초에 latency 축이 없었다 — 이번 실측이 드러낸 조사 공백이다.

그럼에도 채택하는 이유: `module-architecture.md` §1-5 원칙("긴 작업은 HTTP 요청 안에서 끝내지 않는다. API는 작업을 발주하고 `202 Accepted`를 반환하며 Worker가 처리한다")과 `architecture-input-memo.md` §2("intent LLM 호출은 1회로 제한")를 같이 보면, 이 호출은 **한 요청 안에서 동기로 끝내야 하는 게 아니라 1회짜리 비동기 Job으로 발주될 대상**이다. 12초 남짓의 단일 호출은 이 아키텍처 전제 위에서는 병목이 아니다 — 사용자가 붙잡혀 기다리는 게 아니라 `CaseView`의 진행 상태(`progress[]`)로 표시되는 백그라운드 작업의 하나가 된다.

**단, 이 판단이 깨지는 조건은 §7 재검토 트리거에 명시한다.**

## 6. 이미 다른 문서가 정한 것 (여기서 다시 정하지 않는다)

- 추출 스키마(`time_hint`/`vehicle_hint`/.../`reasoning`) — `research/llm-model-comparison-hint-extraction.md` §3.
- 이번 v1 비교에 LLM-judge를 쓴 이유와 그 한계(런칭 후 CorrectionRecord 기반 F1로 전환 예정) — `experiments/intent-llm-model-comparison/README.md` "채점 방식" 절.
- 평가 목표치 자체와 그 신뢰도 한계 — `decisions/intent-llm-eval-target-thresholds.md`.
- intent LLM 호출 1회 제한, case가 다른 모듈의 프롬프트/정책을 알면 안 된다는 경계 — `architecture-input-memo.md` §2 · `tech-spec.md` §1.

## 7. 재검토 트리거

아래 중 하나라도 실제로 생기면 다시 조사한다.

- [ ] intent 구조화 호출이 실제 구현에서 동기(사용자가 화면에서 기다리는 경로)로 붙게 된다 — §5의 latency 정당화가 성립하지 않게 되는 경우.
- [ ] Gemini 3.1 Flash-Lite가 GA로 전환된다 — §4의 제외 이유 중 하나(Preview 리스크)가 사라진다.
- [x] ~~v2 이상의 더 큰 locked dataset으로 재측정했을 때 이번 v1(n=7) 결과와 다른 순위가 나온다.~~ — **2026-09-22 충족.** 실사용자 로그 기반 v2는 아직이지만, `research/intent-llm-robustness-test-design.md`(9카테고리×3변형=27케이스, 강건성 관점)로 3개 모델을 재측정한 결과 v1의 100%/0% 우위가 재현되지 않았다(3개 모델 82~85%로 사실상 동률, hallucination 9~11%로 동반 상승, latency 격차는 오히려 확대). 스팟체크로 GPT-5 Nano의 실제 약점(새사고를 정정으로 오인, 3/3 hallucinated)도 확인됨(같은 문서 §10). 모델 재선정 여부는 별도 논의로 진행 — 이 트리거 충족 자체가 재선정 결론은 아니다.
- [x] ~~judge 판정 20% 스팟체크에서 LLM-judge가 사람과 크게 갈려, 이번 실측 자체의 신뢰도가 흔들린다~~ — 2026-09-20 완료, 안 흔들림(§9). 트리거 조건 미충족.
- [ ] `CorrectionRecord` 실데이터가 쌓여 Field-level F1로 채점 방식이 바뀐 뒤, 그 정답지로 다시 봤을 때 순위가 바뀐다.

## 8. 남은 것 — 이 결정이 안 끝낸 일

- **실제 프로덕션 배선은 이 결정의 범위 밖이다.** `CaseAggregate.intake()`가 아직 구조화된 `hints`만 받고, 원문 자연어를 GPT-5 Nano로 실제 호출하는 코드는 `domain.py`/`scope.py` 어디에도 없다 — 이건 별도 구현 작업(설계 고도화 우선순위 목록 3순위)이다.
- `research/...` §4 테스트 문장을 실사용자 로그로 교체(v2 dataset) — 미결. §9가 찾은 case-04류 위치 단서 판정 기준 공백도 v2에서 같이 메운다.
- Elice 쪽 `ELICE_API_KEY`/`ELICE_URL_*`/`JUDGE_MODEL_URL` 실제 값은 `.env`(gitignore 대상)에만 있고 이 문서·리포 어디에도 값 자체를 남기지 않는다.

## 9. judge 판정 스팟체크 결과 (2026-09-20)

126개 필드 판정(3모델 × 7케이스 × 6필드) 중 **5개(4%)만 `correct`가 아니었다** — 전부 `case-04-relative-time`/`case-05-vehicle-ambiguous` 두 케이스, claude-haiku-4-5/gemini-3.1-flash-lite 두 모델에만 있었다. **GPT-5 Nano는 5건과 전부 무관(126개 다 correct)** — 이 결정(§1)에 영향 없음.

5건을 사람이 직접 읽고 원인을 둘로 나눴다:

- **4건(case-04, location_hint/confidence)** — judge 판정 자체보다 **데이터셋 결함**이었다. `expected_notes`가 이 케이스의 `time_hint` 기준만 적어두고 원문의 "여기서"를 `location_hint`로 어떻게 다뤄야 하는지는 아예 안 정해뒀다 — judge가 그 자리에서 즉석 기준을 만들어 판정한 것. v2 데이터셋에서 이 공백을 메운다(§8).
- **1건(case-05, `vehicle_hint`)** — **진짜 judge 리스크**였다. claude·gemini 둘 다 `vehicle_hint="SUV"`로 완전히 같은 값을 냈는데 judge가 다르게 판정했다(claude: correct, gemini: partial) — gemini가 `confidence`를 잘못(`high`로) 매긴 여파가 무관한 `vehicle_hint` 판정에도 전이된 것으로 보인다. **조치:** `schema.py`의 `JUDGE_SYSTEM_PROMPT`에 "같은 필드가 같은 값이면 모델이 달라도 같은 verdict를 매긴다"는 규칙을 명시적으로 추가했다(이 커밋). 기존 `judge_run_id=20260919T170342Z` 결과는 그대로 두고(불변 저장 원칙, `judge.py` 참고) 덮어쓰지 않았다 — 이 rubric 수정은 다음 채점 run부터 적용된다.

**결론: 5/126(4%)이라는 이견율은 낮고, 유일한 진짜 judge 문제(case-05)도 이번 결정을 뒤집지 않는다 — §1의 GPT-5 Nano 채택은 이 스팟체크로 재확인됐다.**
