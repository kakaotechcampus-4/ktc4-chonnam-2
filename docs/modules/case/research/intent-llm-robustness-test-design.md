# Intent LLM 강건성(Robustness) 테스트 설계 — 도메인 밖 입력·일관성

> 작성일 2026-09-22 · 담당 유소연(`case`)
> 근거: 딥리서치 도구 결과(2026-09-22, `datasets/intent-hint-robustness-v1.jsonl`로 검증·정규화해 보존) + PM 재검토 피드백
> 관련: `experiments/intent-llm-model-comparison/README.md`(하네스) · `decisions/intent-llm-model-selection.md`(v1 모델 선정) · `decisions/intent-llm-eval-target-thresholds.md`(v1 목표치·표본 한계)

## 1. 배경 — 이 문서가 다루는 재검토 지점

PM이 GPT-5 Nano 모델 선정 결과를 재검토하며 두 가지를 지적했다. 이 둘은 서로 다른 문제라 구분한다.

1. **표본 크기(N) 문제** — `decisions/intent-llm-eval-target-thresholds.md` §1.1이 이미 자체 인정한 지점이다. locked v1은 카테고리당 1케이스(n=7)뿐이라 케이스 1개가 결과 퍼센트를 약 14%p씩 흔든다. 이건 "같은 카테고리를 더 많이(가능하면 실사용자 로그 기반으로)" 채우는 문제이고, **이 문서는 이 항목을 다루지 않는다** — README/`decisions/intent-llm-model-selection.md` §8에 이미 미결로 남아있다.
2. **모집단 대표성(커버리지) 문제 — 이 문서가 다루는 지점.** "화장실이 어디예요?" 같은 질문에 안전하게 반응하는지, 비슷한 의미의 질문에 항상 일관되게 반응하는지는 표본 개수를 늘린다고 해결되지 않는다. locked v1의 7개 카테고리(정상/일부누락/전부모호/상대시간/차량애매/위치애매/correction)는 전부 "사용자가 진짜로 사고를 설명하고 있다"는 전제 위에 있고, 그 전제 자체가 깨지는 입력은 한 종류도 없었다. 케이스를 100개로 늘려도 이 전제가 그대로면 여전히 이 질문엔 답을 못 한다.

## 2. 두 축

- **커버리지 축** — locked v1이 아예 갖고 있지 않은 입력 유형(카테고리)을 찾아 채운다.
- **일관성(invariance) 축** — 같은 카테고리 안에서 표현만 바꾼 변형을 3개씩 만들어, 모델이 매번 같은 방식으로 반응하는지 확인한다. 기존 judge 채점("정답과 비교해 맞았는가")과 성격이 다르다 — 이 축은 "정답을 하나로 못박기 어려운 상황에서도 최소한 결과가 흔들리지 않는가"를 본다.

## 3. 새 카테고리 9개(`intent-hint-robustness-v1.jsonl`, 27케이스 = 9카테고리 × 3변형)

| 카테고리 | 왜 필요한가 |
| --- | --- |
| 무관한 질문·잡담 | 사고 설명이라는 전제 자체가 깨졌을 때, 엉뚱한 질문에 답하려고 정보를 지어내지 않고 안전하게 null/low로 떨어지는지 확인 |
| 여러 사건 혼합 | 서로 다른 사건 2개 이상이 한 문장에 섞였을 때, 서로 다른 사건의 속성을 임의로 조합해 존재하지 않는 사건을 만들어내지 않는지 |
| 모순 정보 | 같은 슬롯을 한 문장 안에서 두 번 다르게 말했을 때, 임의로 값을 확정하면서 confidence까지 high로 과신하지 않는지(가장 위험한 실패 패턴) |
| 구조적 경계 입력 | 빈 문자열·의미 없는 문자열·극단적으로 긴 입력에서 파이프라인이 죽지 않고 동일하게 null/low로 안전 처리되는지 |
| 프롬프트 인젝션 | 시스템 지시사항을 캐내려는 시도, 또는 실제 사고 정보와 함께 "confidence를 강제로 high로 답해" 같은 직접 지시가 섞였을 때 지시를 따르지 않는지 |
| 비한국어·언어 혼합 | 서비스는 한국어 기준 설계지만 실사용자는 영어·혼용·다른 언어로도 입력할 수 있다 — 언어별 처리 방침은 미정이라도, 최소한 표현만 다른 세 변형이 서로 다르게 처리되면 안 된다는 것 |
| 욕설·유효신고 혼합 | 신고자가 화가 나서 욕설을 섞어도 실제 유효 정보를 놓치지 않고, 반대로 욕설 자체를 사고 정보로 착각하지 않는지 |
| `correction_target` 오염 시도 | 정정 발화에 무관한 새 정보를 슬쩍 끼워 넣었을 때, 정정 대상이 아닌 필드까지 덩달아 덮어써지지 않는지 |
| 새 사고를 정정으로 오인 방지 | `prior_hints`가 남아있는 상태에서 명시적 전환 신호("그건 됐고" 등)와 함께 완전히 새로운 사고를 말했을 때, 기존 필드 정정으로 착각해 두 사고를 섞지 않는지 |

마지막 두 카테고리는 경계가 미묘하게 겹친다 — `correction_target` 오염 시도는 "정정인데 정정 아닌 정보가 끼어든 경우", 새 사고 오인 방지는 "정정이 전혀 아닌데 정정으로 오인될 위험이 있는 경우"로 분리했다.

## 4. 검증 결과 — 원본 파일을 그대로 쓸 수 있는가

- 27개 전부 유효 JSON, 스키마 키(`id`/`scenario_tag`/`prior_hints`/`input_sentence`/`expected_notes`)가 locked v1과 일치 확인(round-trip 파싱 확인).
- **정규화 1건 적용.** 원본 파일의 `prior_hints`에는 `correction_target: null`이 매번 포함돼 있었는데, locked v1의 correction 케이스(`case-07-correction`)는 `prior_hints`에 `correction_target` 키 자체를 두지 않는다 — `correction_target`은 "이전부터 들고 다니는 상태값"이 아니라 "이번 발화가 뭘 고치는지"를 나타내는 **이번 턴의 출력**이라 prior state 취급이 맞지 않는다. `intent-hint-robustness-v1.jsonl`을 저장하며 이 키를 `prior_hints`에서 제거해 v1 컨벤션에 맞췄다(내용 값 자체는 바꾸지 않았다).
- **인용 정정.** 딥리서치 결과가 8번(`correction_target` 오염 시도)·9번(새 사고 오인 방지) 카테고리의 근거로 "이슈 #39"를 들었는데, 실제로 확인하니 이슈 #39는 evidence 모듈 4차 mock 검수 건이라 이 주제와 무관하다(오귀속 — 이전에 딥리서치 원문의 FinGround/MulitaMiner 수치가 미확인이었던 것과 같은 패턴이라, AI가 만든 인용은 항상 별도로 검증해야 한다는 걸 다시 확인함). 실제 근거는 `experiments/intent-llm-model-comparison/scripts/schema.py`의 `CANDIDATE_SYSTEM_PROMPT`에 이미 있다: "이번 발화에서 언급되지 않은 필드는 prior_hints 값을 복사하지 말고 null로 둔다(병합은 이 호출의 책임이 아니다)." 위 §3 표는 이 근거로 정정해서 적었다.

## 5. 이 카테고리들이 지금 하네스로 바로 테스트 가능한가

**가능하다.** `candidates.py`가 `prior_hints`를 그대로 프롬프트에 주입하는 구조라(`CANDIDATE_USER_TEMPLATE`의 `prior_hints: {prior_hints_json}`), `correction_target` 오염 시도·새 사고 오인 방지 카테고리는 실제 `CaseAggregate` 프로덕션 배선(아직 안 됨 — `decisions/intent-llm-model-selection.md` §8)과 무관하게 지금 하네스에서 곧바로 실행할 수 있다. locked v1의 `case-07-correction`도 이미 같은 방식으로 `prior_hints`를 하네스가 직접 합성해 공급했다. 즉 프로덕션 배선 미완료는 이 테스트를 막는 조건이 아니다.

## 6. 데이터셋 파일 명명 — 왜 `v2`가 아니라 별도 파일인가

`experiments/intent-llm-model-comparison/README.md`의 "Locked Dataset 정책"이 말하는 `intent-hint-eval-v2.jsonl`은 §1의 "표본 크기(N) 문제" 해결책 — **같은 7개 카테고리를 실사용자 로그 기반으로 더 많이** 채우는 다음 버전을 가리킨다. 이번 27케이스는 카테고리 자체가 다른 종류(강건성/안전성)라 그 v2와 성격이 다르다 — 같은 파일명 아래 섞으면 "표본을 늘렸다"와 "새 위험 유형을 찾았다"가 뭉개진다. 그래서 `intent-hint-robustness-v1.jsonl`이라는 별도 이름으로 두었다. 둘 다 언젠가 실측이 끝나면 사실상 "더 큰 locked set"으로 합쳐질 수 있지만, 지금 단계에서는 목적이 다른 두 갈래로 분리해 추적하는 게 맞다고 판단했다.

## 7. 이번에 추가로 제안된 축 4개 — 다음 단계

딥리서치 도구가 위 9개 외에 추가로 제안한 축. 전부 "케이스를 더 만든다"보다 "다른 방식으로 잰다"에 가까워서, 이번 27케이스와 성격이 또 다르다. 실행은 각 항목의 조건이 갖춰진 뒤로 미룬다.

- [ ] **출력 계약(스키마) 준수** — 내용이 맞아도 형식이 깨질 수 있다(여분 키, 키 누락, `"null"` 문자열 vs 실제 null, JSON 파싱 실패). **사실 이건 새로 잴 게 아니라 이미 재고 있다** — `aggregate.py`의 `schema_compliance_rate`가 모든 케이스 실행에서 자동으로 이걸 집계한다(v1 실측 때도 21건 전부 `schema_valid=True` 확인됨). 이번 27케이스를 실측에 포함시키기만 하면 별도 구현 없이 이 축도 같이 커버된다.
- [ ] **필드 간 오염(cross-field leakage)** — §3의 `correction_target` 오염 시도·새 사고 오인 방지 두 카테고리가 이미 이 문제의 핵심 사례를 담고 있다. 완전히 새 축이라기보다 그 두 카테고리의 상위 개념으로 보는 게 맞고, 별도 케이스 추가는 지금 불필요해 보인다.
- [ ] **신뢰도 보정의 반대 방향(과소평가)** — 지금 새 카테고리는 전부 "애매한데 high로 과신하면 안 된다"만 본다. 반대로 "단서가 명확한데도 low로 깎는" 실패는 새 케이스보다 **회귀 테스트**로 다루는 게 맞다 — locked v1의 `case-01-normal`(정상 단서)이 매 실측마다 안정적으로 high가 나오는지를 실측 결과 비교 시 계속 확인하면 된다. 별도 데이터셋 항목 신설 불필요.
- [x] **정보 위치/순서 편향** — 같은 정보라도 문장 앞/뒤 위치에 따라 추출 여부가 달라지는지. **2026-09-22 추가** — `case-01-normal`과 정보 내용이 완전히 같고 절 순서만 바꾼 3개 변형(`case-17a/b/c`, 카테고리명 `정보_위치순서_편향`)을 만들어 `intent-hint-robustness-v2.jsonl`에 넣었다. 기대값은 매번 `case-01-normal`과 동일 — 뒤로 이동했다는 이유로 값을 놓치거나 confidence를 낮추면 오답.

## 8. 설계 중 나온 결정 사항 — 이 문서에 두지 않음

§7의 두 미결 항목(도메인 밖 입력의 스키마 표현, 모순 정보의 정답 정책)은 실제로 결정됐다. Research는 결정이 아니므로(`docs/README.md`) 결정 내용과 근거는 `decisions/intent-hint-robustness-policy.md`에 있다 — 여기서 다시 옮겨 적지 않는다. 언어 처리 방침만 여전히 미정으로 남는다(같은 문서 §2).

## 9. 다음 단계

- [x] `dataset.py`의 `load_dataset()`으로 27케이스 전부 무료 로드 확인(2026-09-22) — 파싱 에러 없음, `prior_hints`가 있는 6케이스(`case-15a/b/c`·`case-16a/b/c`, §3 마지막 두 카테고리 각 3개 — 8이 아니라 6이었다, 이전 기재 정정)도 정상 인식됨. `candidates.py`가 `prior_hints`를 그대로 프롬프트에 주입하는 구조라 실제 API 호출 전에 걸릴 게 없음을 확인.
- [x] **모델 선정 재검토 필요성 관련(PM 피드백 2)** — GPT-5 Nano의 100% field 정확도가 n=7 기반이라 근거가 얇다는 지적에 따라, 이번 27케이스 실측을 GPT-5 Nano 하나가 아니라 **3개 후보 모델 전부**에 대해 실행하기로 결정(2026-09-22) — robustness 검증과 모델 선정 재확인을 동시에 수행.
- [ ] `decisions/intent-hint-robustness-policy.md` §3의 남은 항목(모순 정보 `expected_notes` 구체화 등) 진행
- [ ] §7 "정보 위치/순서 편향" 케이스 추가 여부 결정
- [x] Elice 실측 실행(3개 모델 × 27케이스, 2026-09-22) → §10 참고. `predictions-robustness/`·`results/summary-robustness-v1.md`에 저장(기존 v1 `predictions/`·결과와 분리, §6 명명 원칙 그대로 적용)

## 10. 실측 결과 (2026-09-22, judge_run_id `20260922T105457Z`)

3개 후보 모델 × 27케이스, 전부 `error=None`/`schema_valid=True`(candidate 81건 + judge 81건, 실패 0). 원본: `results/summary-robustness-v1.md`.

| model | field 정확도 | hallucination | missed | 평균 latency | 총 비용(KRW) |
| --- | --- | --- | --- | --- | --- |
| gpt-5-nano | 85% | 10% | 1% | 17,479ms | 41.20 |
| gemini-3.1-flash-lite | 85% | 9% | 0% | 1,865ms | 9.73 |
| claude-haiku-4-5 | 82% | 11% | 1% | 2,994ms | 134.63 |

**v1(n=7)의 "GPT-5 Nano 100%/hallucination 0%" 압도적 우위가 재현되지 않았다.** 세 모델이 82~85%로 사실상 동률이고 hallucination도 9~11%로 다 같이 높아졌다 — n=7에서 보인 격차가 표본이 작아 생긴 착시였다는 §1의 PM 지적이 이번 실측으로 뒷받침된다. latency 격차는 오히려 더 벌어졌다(GPT-5 Nano 17.5초, Gemini 대비 9.4배·Claude 대비 5.8배 — v1 때는 4.8배/3.7배). 비용도 GPT-5 Nano가 더 이상 최저가가 아니다(Gemini가 가장 저렴).

카테고리별로 특히 튄 두 지점을 사람이 직접 스팟체크했다(원본 판정 근거는 `predictions-robustness/<model>/<case_id>.judge.20260922T105457Z.json`):

- **GPT-5 Nano — `새사고_정정오인_방지` 61%(3케이스 전부 확인).** 사용자가 "또 다른 사고", "그건 됐고", "다른 건데요"처럼 새 사고임을 명시했는데도, 3건 모두 이를 기존 필드 정정으로 오인해 `correction_target`을 지어냈다(judge 판정: 3건 다 `hallucinated`, 근거 문장도 매번 구체적이고 일관됨 — 예: "'또 다른 사고'라며 명시적으로 전환했는데 모델이 이를 vehicle_hint의 정정으로 오인"). 같은 케이스(`case-16a`)를 Claude Haiku로 확인하니 같은 신호를 정확히 인식해 `correction_target: null`로 맞게 처리했다 — 대조가 뚜렷하다. **judge rubric 문제가 아니라 GPT-5 Nano의 실제 약점으로 확인됨.**
- **Claude Haiku — `여러_사건_혼합` 39%(3케이스 전부 확인).** 두 사건이 섞인 문장에서 값을 분리하거나 하나를 고르지 않고 두 값을 한 필드에 콤마로 나열하면서(예: `vehicle_hint: "흰색 SUV, 검은색 세단, 오토바이"`), confidence는 3건 모두 `high`로 유지했다 — 이 카테고리가 원래 경계하려던 "애매한데 과신" 실패 패턴 그 자체다. **동일하게 judge rubric 문제가 아니라 실제 약점으로 확인됨.**

**결론: 이번 실측은 `decisions/intent-llm-model-selection.md` §7의 재검토 트리거("더 큰 dataset으로 재측정했을 때 다른 순위가 나온다")를 충족한다.** 모델 재선정 여부는 이 문서(research)가 결정하지 않는다 — 별도 논의로 진행한다.

## 11. 4번째 후보 추가 — Gemini 3.8 Flash (2026-09-22)

모델 재선정 논의 중 "이 3개 후보로 한정해야 하나"라는 질문에서 나왔다. 웹에서 새 후보를 찾기보다, **search 모듈이 이미 Elice로 실사용 중인 모델**(`src/daesingo/search/config.py`의 `model: str = "gemini-3.8-flash"`, base_url `https://mlapi.run/a90d8545-.../v1`, `chat.completions.parse(response_format=...)` 패턴까지 case 하네스와 동일)을 그대로 재사용했다 — Gemini 3.1 Flash-Lite가 애초에 후순위였던 이유(Preview 상태, `research/llm-model-comparison-hint-extraction.md` §5)가 이 상위 버전에는 없다.

`candidates.py`의 `MODEL_IDS`·`_MODEL_BASE_URL_ENV`에 추가하고(`.env`에 `ELICE_URL_GEMINI_3_8_FLASH` 추가), v1+robustness-v1 34케이스 전체에 실측(judge_run_id `20260922T120348Z`, candidate 34건+judge 34건 전부 `error=None`):

| | v1(7케이스) | robustness-v1(27케이스) |
| --- | --- | --- |
| field 정확도 | **100%** | **91%**(4개 모델 중 최고) |
| hallucination | 0% | **6%**(최저) |
| missed | 0% | 1% |
| latency | 3,298ms | 4,354ms |
| `새사고_정정오인_방지` | — | **100%**(4개 모델 중 최고 — GPT-5 Nano가 61%로 최저였던 카테고리) |
| `correction_target_오염_시도` | — | 61% |

원본: `results/summary-gemini-3.8-flash-v1.md`·`results/summary-gemini-3.8-flash-robustness.md`. **비용은 아직 `-`(None)** — `pricing.py`의 `KRW_PER_1M_TOKENS`에 이 모델 단가가 없다(구글 공식 요율 $0.75/$3.75는 찾았지만, Elice가 기존 3개 모델에 매긴 단가가 공식 요율보다 유의미하게 높았던 전례가 있어 그대로 못 쓴다 — Elice 모델 카드에서 직접 확인 필요, §12 참고).

4개 모델 중 거의 전 지표에서 가장 균형 잡힌 결과라, 모델 재선정 논의의 유력 후보가 됐다. **다만 최종 결론은 §12의 데이터셋 확장(50케이스 이상) 이후로 미룬다** — 지금 34케이스로도 이미 순위가 여러 번 뒤집힌 전례(§10)가 있어, 표본을 더 늘리기 전에 결론을 확정하지 않는다.

## 12. 데이터셋 50케이스 이상으로 확장 — 진행 중 (2026-09-22)

표본 크기(§1-1) 문제를 실제로 닫기 위해 케이스 수를 50 이상으로 늘리기로 했다. 두 갈래를 동시에 진행한다.

**A. 강건성 쪽 자체 확장(지금 진행 중)**
- `intent-hint-robustness-v2.jsonl` 신설(30케이스 = 기존 9카테고리×3 + `정보_위치순서_편향` 신규 1카테고리×3, §7 참고). **아직 실측 전 — locked 정책상(README "Locked Dataset 정책") 첫 실측 전까지는 계속 다듬어도 되는 상태.**
- 기존 9개 카테고리에 변형 2개씩(18개) 추가 요청을 딥리서치 도구에 다시 보냈다(대화 기록 참고, 이 문서엔 프롬프트 원문을 중복 보관하지 않음). 결과가 오면 `intent-hint-robustness-v2.jsonl`에 합쳐 30+18=48케이스가 되고, v1의 7케이스와 합치면 **55케이스**로 50을 넘긴다.
- 확장 완료 후 4개 모델(GPT-5 Nano/Gemini 3.1 Flash-Lite/Claude Haiku 4.5/Gemini 3.8 Flash) 전체 재실측 예정.

**B. 실사용자 로그 기반 확장(원래 v1의 표본 문제, §1-1) — 기반만 마련, 실행은 별도**
`decisions/intent-llm-model-selection.md` §8과 이 문서 §1이 계속 미결로 남겨둔 항목이다. case가 런칭 전이라 진짜 로그가 없어서, 대체 수단으로 **소규모 인간 대상 설문**(팀 밖 지인 포함, "블랙박스 신고 상황을 한 문장으로 써달라"는 요청)을 진행하기로 했다 — AI나 case 담당자 본인이 아닌 실제 다른 사람이 쓴 자유 문장을 얻는 게 핵심이라, 완전한 "로그"는 아니어도 지금 데이터셋의 "같은 저자가 쓴 예시문이라 표현이 비슷하다"는 약점을 메운다. 설문 문항 초안과 수집된 응답을 locked dataset으로 편입하는 절차는 `research/intent-hint-real-text-collection-plan.md`에 준비해뒀다(**아직 설문을 실제로 돌리지는 않았음** — 초안만 준비된 상태, 실행 여부는 별도 결정).
