# intent-llm-model-comparison

**목적:** `research/llm-model-comparison-hint-extraction.md`가 남긴 미결 항목(§7) — 자연어 단서 구조화 호출에 GPT-5 Nano / Gemini 3.1 Flash-Lite / Claude Haiku 4.5 중 무엇을 쓸지 실측으로 결정하기 — 을 실행하는 실험 하네스와 고정 데이터셋.

**상태:** API 키 미확보(research 문서 §7 미결 1번) — 아래 코드는 구조만 갖춰져 있고 아직 실행할 수 없다. 데이터셋(§ 아래)은 키 없이도 확정 가능해서 먼저 작성했다.

## 채점 방식을 정한 이유

**스키마 준수율만으로는 부족하다.** 세 후보(GPT-5 Nano / Gemini 3.1 Flash-Lite / Claude Haiku 4.5) 모두 Structured Outputs(JSON Schema strict mode)를 지원한다(`research/llm-model-comparison-hint-extraction.md` §5) — API가 스키마 위반 자체를 강제로 막아준다. 그러면 "스키마를 지켰는가"만 재면 세 모델 다 100%에 가깝게 나와서 모델 간 차이가 안 보일 수 있다. 그래서 이 실험은 스키마 준수율과 별개로, **추출 내용의 정확도**(원문에 있는 내용을 실제로 옳게 뽑았는지, 없는 내용을 지어내지 않았는지)를 측정 대상에 포함한다 — 이게 이 실험 설계 전체의 출발점이다.

**내용 정확도 채점 방법으로 LLM-judge를 선택한 이유.** 검토한 대안:

- 필드별 규칙 기반 채점(정규식/키워드 매칭): 비용은 가장 낮지만, `time_hint`·`vehicle_hint`처럼 자유 텍스트 필드는 "정답 문자열"이 하나로 고정되지 않아(예: "어제 18시쯤"을 "18시쯤"이라고만 뽑아도 맞다고 봐야 하는지) 케이스마다 규칙을 정교하게 미리 써둬야 하는 부담이 큼.
- 사람이 직접 pass/fail 라벨링: 가장 정확하지만, 프롬프트나 모델을 바꿔 재실행할 때마다 3개 모델 × N개 케이스를 매번 다시 사람이 봐야 해서 반복 실험(재실행이 전제인 locked dataset 취지)에 안 맞음.
- **LLM-judge(채택)**: 자유 텍스트의 의미적 동치를 판단할 수 있으면서 재실행 비용이 낮음. 단점(judge 자체의 신뢰성)은 판정의 일부를 사람이 스팟체크하는 것으로 보완한다(아래 「검증」 절).

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
scripts/
  schema.py      # §3 추출 스키마 + 후보/judge 프롬프트 템플릿 (단일 정의 소스)
  dataset.py     # datasets/*.jsonl 로더
  candidates.py  # CandidateAdapter 인터페이스 + 3개 벤더 stub (실행 전 벤더 문서 확인 필요 — TODO 표시)
  runner.py      # dataset × candidates → predictions/*.jsonl (불변 저장)
  judge.py       # predictions × judge 모델 → 필드별 correct/partial/wrong 판정
  aggregate.py   # 스키마 준수율 · 필드 정확도율 · 비용/latency 집계 → results/summary.md
```

Prediction과 Judging을 분리해서, judge rubric이 바뀌어도 유료 API 호출(prediction)을 다시 하지 않아도 되게 한다.

**Judge 모델**: 비교 대상 3개 후보 중에서 고르지 않는다(자기 채점 편향 방지). 현재 팀이 이미 쓰는 모델 중 후보 3개에 없는 것을 쓴다 — 실행 시점에 `JUDGE_MODEL` 환경변수로 확정.

**검증**: judge 판정 중 일부(20% 권장)를 사람이 직접 스팟체크한다. 사람과 다르게 판정한 케이스가 나오면 데이터셋이 아니라 `schema.py`의 judge 프롬프트(rubric)를 고친다.

## 다음 단계 (미결)

- [ ] `research/llm-model-comparison-hint-extraction.md` §7과 동일 — API 키 최소 1개 확보
- [ ] `candidates.py`의 벤더별 TODO를 실제 API 스펙으로 채움 (실행 시점 최신 문서 확인 — 이 코드 작성 시점 기준 벤더 확정 문법을 검증하지 못했다)
- [ ] `JUDGE_MODEL` 확정
- [ ] 실측 실행 → `results/summary.md` → 결과를 바탕으로 `docs/modules/case/decisions/`에 확정 문서 작성
