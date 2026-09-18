# intent-llm-model-comparison

**목적:** `research/llm-model-comparison-hint-extraction.md`가 남긴 미결 항목(§7) — 자연어 단서 구조화 호출에 GPT-5 Nano / Gemini 3.1 Flash-Lite / Claude Haiku 4.5 중 무엇을 쓸지 실측으로 결정하기 — 을 실행하는 실험 하네스와 고정 데이터셋.

**상태:** Elice ML API(카테캠 제공, 크레딧 12만 한도 — `search`와 공유) 경유로 세 모델을 다 부를 수 있다는 것까지 확인됐다. `ELICE_API_KEY`/`ELICE_BASE_URL` 값과 `gpt-5-nano`/`gemini-3.1-flash-lite` 모델 ID 문자열 확인만 남았다(아래 「Elice 연동」).

## 비용 — 12만 크레딧 예산 대비

Elice 모델 카드에서 확인한 단가(KRW/1M 토큰, `scripts/pricing.py`):

| 모델 | 입력 | 출력 |
| --- | --- | --- |
| GPT-5 Nano | 76 | 609 |
| Gemini 3.1 Flash-Lite | 380 | 2,283 |
| Claude Haiku 4.5 | 1,522 | 7,612 |

시드 7건 × 후보 3개 + judge 21건 기준으로 계산하면 **총 실행 비용은 ₩50 미만**(1 크레딧=₩1 가정 시 12만 크레딧의 0.05% 미만) — `search`와 예산을 나눠 써도 문제없는 수준이다. 10배 여유를 둬도 ₩500 이내.

## 채점 방식 — 1차 가설, 실측 전 잠정

**아래는 전부 실측 전 잠정 판단이다.** 아직 API 키/모델 ID가 확정 안 돼서 실제로 judge를 돌려본 적이 없다 — LLM-judge가 정말 믿을 만한지는 스팟체크(아래 「검증」)로 확인해야 나온다. 사람과 다르게 판정하는 비율이 높으면 규칙 기반 채점이나 사람 라벨링으로 되돌아갈 수 있다. 지금 이 판단을 `decisions/`로 올리지 않고 `experiments/`에 두는 이유가 이거다.

**2026-09-18 방향 전환:** LLM-judge를 채점 방식의 최종 답으로 보지 않는다. `decisions/intent-llm-eval-target-thresholds.md`의 딥리서치가 권고하고 지금 보기에도 정확도·비용 면에서 더 나은 방법은 **CorrectionRecord 기반 Field-level F1**이지만, 런칭 전이라 CorrectionRecord 실데이터가 없어서 지금 당장은 못 쓴다. 그래서 LLM-judge는 **이번 v1 모델 비교 한 번에만 쓰는 임시 방편**이고, 런칭 후 CorrectionRecord가 쌓이면 F1 기반으로 전환한다(아래 「다음 단계」).

**스키마 준수율만으로는 부족하다.** 세 후보(GPT-5 Nano / Gemini 3.1 Flash-Lite / Claude Haiku 4.5) 모두 Structured Outputs(JSON Schema strict mode)를 지원한다(`research/llm-model-comparison-hint-extraction.md` §5) — API가 스키마 위반 자체를 강제로 막아준다. 그러면 "스키마를 지켰는가"만 재면 세 모델 다 100%에 가깝게 나와서 모델 간 차이가 안 보일 수 있다. 그래서 이 실험은 스키마 준수율과 별개로, **추출 내용의 정확도**(원문에 있는 내용을 실제로 옳게 뽑았는지, 없는 내용을 지어내지 않았는지)를 측정 대상에 포함한다 — 이게 이 실험 설계 전체의 출발점이다.

**내용 정확도 채점 방법으로 LLM-judge를 선택한 이유.** 검토한 대안:

- 필드별 규칙 기반 채점(정규식/키워드 매칭): 비용은 가장 낮지만, `time_hint`·`vehicle_hint`처럼 자유 텍스트 필드는 "정답 문자열"이 하나로 고정되지 않아(예: "어제 18시쯤"을 "18시쯤"이라고만 뽑아도 맞다고 봐야 하는지) 케이스마다 규칙을 정교하게 미리 써둬야 하는 부담이 큼.
- 사람이 직접 pass/fail 라벨링: 가장 정확하지만, 프롬프트나 모델을 바꿔 재실행할 때마다 3개 모델 × N개 케이스를 매번 다시 사람이 봐야 해서 반복 실험(재실행이 전제인 locked dataset 취지)에 안 맞음.
- **CorrectionRecord 기반 Field-level F1**: 정확도·비용 면에서 가장 이득이라고 판단한다(`decisions/intent-llm-eval-target-thresholds.md` §3.2·§5의 딥리서치 권고와 일치 — LLM-judge보다 결정론적이고 저렴함). **다만 지금은 못 쓴다** — case가 아직 런칭 전이라 실사용자가 고친 이력(`CorrectionRecord`)이 하나도 없다(같은 문서 §1 마지막 줄, UCR도 같은 이유로 production 이후로 미룸). 그래서 이번 v1 모델 비교에는 쓸 정답지가 없다.
- **LLM-judge(런칭 전 v1 비교용 임시 방편)**: 위 이유로 CorrectionRecord F1을 지금 못 쓰니, 이번 3개 모델 비교 한 번만 쓸 임시 채점 방식으로 LLM-judge를 둔다. 자유 텍스트의 의미적 동치를 판단할 수 있으면서 재실행 비용이 낮다는 게 근거다. 단점(judge 자체의 신뢰성)은 판정의 일부를 사람이 스팟체크하는 것으로 보완할 **계획**이지만, 그 스팟체크를 아직 안 해봤다. **런칭 후 CorrectionRecord가 쌓이면 LLM-judge는 걷어내고 Field-level F1로 전환한다** — 이번 하네스(`schema.py`/`judge.py`/`aggregate.py`)는 v1 모델 선정이 끝나면 그 역할을 다한 것으로 본다.

**"correct/partial/wrong" 하나로는 부족해서 hallucinated/missed로 더 쪼갰다.** 단순 정확도만 보면 "모델이 없는 내용을 지어냈다"와 "모델이 있는 내용을 놓쳤다"가 똑같이 "틀림"으로 뭉개진다. 이 둘은 원인도 다르고(전자는 과감함, 후자는 소극적 과묵) 신고 준비 맥락에서 위험도도 다르다(있지도 않은 차량 색상을 지어내는 쪽이 더 위험하다). 그래서 judge 판정을 `correct / partial / hallucinated / missed` 4종으로 나누고(`schema.py`), `aggregate.py`에서 다음을 모델별로 집계한다:

- `schema_compliance_rate` — 스키마 준수율
- `field_accuracy_rate` — 필드별 정확도(위 원래 채점 방식)
- `hallucination_rate` — 없는 정보를 지어낸 비율
- `missed_rate` — 있는 정보를 null로 놓친 비율(= null/UNKNOWN 처리가 안 된 비율)
- `per_scenario_accuracy` — 카테고리별 정확도. 데이터셋에 이미 있는 7개 태그를 그대로 써서 "애매한 표현 처리 정확도"(`전부_모호`·`차량_애매`·`위치_애매`)와 "correction 후 값 반영 정확도"(`잘못_입력_후_correction`)를 전체 평균에 묻히지 않고 따로 뽑는다.

## 이 데이터셋과 Mock Pack의 차이

`data/mock/case/scenario_happy_*.json`은 workflow/contract 검증용이고 `hints` 필드가 이미 구조화된 결과물이다(원문 문장이 없음). 이 폴더의 데이터셋은 **원문 문장 → LLM 추출 결과**를 실측하기 위한 것이라 목적이 다르다. `phase1-completion-checklist.md` 74번 항목이 명시한 "AI 실측은 1차 Mock 범위 밖"이 이 작업이다. 두 데이터는 서로 대체하지 않는다.

## Locked Dataset 정책

`datasets/intent-hint-eval-v1.jsonl`은 **고정(locked)** 세트다.

- 어떤 모델/프롬프트를 실측하든 이 파일을 그대로 재사용한다. 비교 대상이 바뀔 때마다 케이스를 새로 쓰면 이전 실측과 비교가 깨진다.
- 케이스를 추가/수정해야 하면 파일을 고치지 않고 `intent-hint-eval-v2.jsonl`을 새로 만든다. 이전 버전으로 만든 `predictions/`·`results/`는 그대로 보존한다.
- 버전 변경 사유는 이 README에 짧게 추가한다.

### 카테고리 (최소 고정 — v1은 카테고리당 1케이스)

| 카테고리 | 왜 필요한가 |
| --- | --- |
| 정상 단서 | 모든 필드가 명확한 기준선 케이스 |
| 일부 누락 | 언급 안 된 필드를 null로 두는지, 지어내지 않는지 확인 |
| 전부 모호 | `confidence: low`를 실제로 붙이는지 확인 |
| 상대시간 표현 | "30분 전"처럼 상대 시간을 절대 시각으로 함부로 변환하지 않고 원문 그대로 보존하는지 확인(시각 해석은 case/evidence의 후속 책임) |
| 차량 애매 | 애매한 설명을 확정적인 값으로 지어내지 않는지 확인 |
| 위치 애매 | 위와 동일하되 위치 필드 |
| 잘못 입력 후 correction | 1회 호출 제한 하에서 `correction_target`을 올바르게 잡는지, 언급 안 된 다른 필드까지 덩달아 채우지 않는지 확인 — `prior_hints`로 이전 상태를 프롬프트에 준다 |

각 row의 `expected_notes`는 모델이 뱉어야 할 정확한 문자열이 아니라 judge가 채점할 때 참고하는 사람이 쓴 판정 기준이다(자유 텍스트 필드는 문자열 완전일치로 채점할 수 없음).

## 하네스 구조

```
requirements.txt  # openai SDK (Elice가 OpenAI 호환 인터페이스로 중계 — 공유 pyproject.toml엔 안 넣음)
scripts/
  schema.py      # §3 추출 스키마(Pydantic) + 후보/judge 프롬프트 템플릿 (단일 정의 소스)
  pricing.py     # Elice 크레딧 단가(KRW/1M 토큰) → 호출당 비용 추정
  dataset.py     # datasets/*.jsonl 로더
  candidates.py  # CandidateAdapter/JudgeAdapter — Elice(OpenAI SDK 호환) 호출
  runner.py      # dataset × candidates → predictions/*.jsonl (불변 저장)
  judge.py       # predictions × judge 모델 → 필드별 correct/partial/hallucinated/missed 판정
  aggregate.py   # 스키마 준수율 · 필드 정확도율 · hallucination/missed rate · 카테고리별 정확도 ·
                 # 애매 3종 confidence:low 인정 비율 · 비용/latency 집계 → results/summary.md
```

Prediction과 Judging을 분리해서, judge rubric이 바뀌어도 유료 API 호출(prediction)을 다시 하지 않아도 되게 한다.

**Judge 모델**: 비교 대상 3개 후보 중에서 고르지 않는다(자기 채점 편향 방지) — `judge.py`가 `JUDGE_MODEL`이 `MODEL_IDS` 안에 있으면 실행을 막는다.

**검증**: judge 판정 중 일부(20% 권장)를 사람이 직접 스팟체크한다. 사람과 다르게 판정한 케이스가 나오면 데이터셋이 아니라 `schema.py`의 judge 프롬프트(rubric)를 고친다.

## Elice 연동

세 모델 다 Elice가 **OpenAI SDK 호환 인터페이스**로 중계한다(`Authorization: Bearer <Serverless API Key>` + `client.chat.completions.parse(model=..., response_format=<PydanticModel>)`). `candidates.py`는 벤더별 분기 없이 `model_name`만 다른 하나의 클래스로 세 모델을 다 처리한다.

**실행 전 필요한 환경변수:**

| 변수 | 값 |
| --- | --- |
| `ELICE_API_KEY` | Elice ML API Serverless API 키 |
| `ELICE_BASE_URL` | Elice 모델 카드의 `<your-mlapi-endpoint>`를 실제 계정 엔드포인트로 교체한 값 |
| `JUDGE_MODEL` | 후보 3개(`gpt-5-nano`/`gemini-3.1-flash-lite`/`claude-haiku-4-5`) 밖의 Elice 모델 ID |

키는 채팅에 붙여넣지 않고 `.env`나 셸 환경변수로 설정한다.

## 다음 단계 (미결)

- [ ] `ELICE_BASE_URL` 실제 값 확보(계정별 엔드포인트) — API 키는 이미 발급 방식 확인됨
- [ ] `candidates.py`의 `MODEL_IDS`에서 `gpt-5-nano`/`gemini-3.1-flash-lite` 문자열을 각 모델 카드에서 직접 확인(현재는 `claude-haiku-4-5`와 같은 명명 규칙일 거라고 가정한 값)
- [ ] `response_format=<PydanticModel>` structured output이 Gemini/Claude 백엔드에도 그대로 강제되는지 실제 호출로 확인(`schema_valid` 계속 False면 이 가정이 깨진 것)
- [ ] `JUDGE_MODEL` 확정
- [ ] 실측 실행 → `results/summary.md`
- [ ] **채점 방식(LLM-judge) 자체를 재검토** — judge 판정 20% 스팟체크해서 사람과 얼마나 갈리는지 확인. 여기서 신뢰도가 낮게 나오면 모델 비교 결과를 믿기 전에 채점 방식부터 규칙 기반/사람 라벨링으로 바꾼다
- [ ] 위 두 가지가 끝나야 결과를 바탕으로 `docs/modules/case/decisions/`에 확정 문서 작성(모델 선택 + 이번 v1 한정으로 LLM-judge를 썼다는 것 둘 다)
- [ ] **(런칭 후) LLM-judge를 CorrectionRecord 기반 Field-level F1으로 전환.** `CorrectionRecord` 실데이터가 쌓이기 시작하면 착수 — 그 전까지는 착수 조건 자체가 안 갖춰진 상태라 미룬다. 전환되면 이 폴더의 `schema.py`/`judge.py`(judge 프롬프트·판정 로직)는 더 이상 안 쓰이고, `aggregate.py`의 정확도 계산만 정답지 소스를 CorrectionRecord로 바꿔 재사용할 수 있는지 검토한다.
