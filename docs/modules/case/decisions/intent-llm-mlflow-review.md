# Intent LLM 평가 도구 — MLflow를 도입하지 않는다

> 결정일 2026-09-24 · 갱신 2026-10-14(git 진행 상황 반영) · 담당 유소연(`case`) · Consulted 없음
> 근거: 아래 §2 하네스 실적 · §6 참고 자료. 2026-10-25 로컬 검토 문서(`doc/`, gitignore 대상)에서 옮겼고 내용은 10-14 판 그대로다

**이 문서의 용도:** PM이 요청한 "LLM 평가용 도구로 MLflow를 조사해보라"에 대한 조사 결과와, 왜 도입하지 않기로 했는지를 설명한다. 범위는 case의 자연어 단서 구조화(intent LLM) 평가다 — eval 모듈의 성능 채점 체계는 다루지 않는다(§5).

---

## 1. 결론

**도입하지 않는다. 9/24 결론이 10/14 기준으로도 그대로다.** 9/24 이후 평가를 크게 더 돌렸지만(아래 §2) 전부 커스텀 하네스로 끝냈고, 그 과정에서 MLflow가 없어서 막힌 일이 없었다. 남은 기간도 짧아졌다.

달라진 점은 셋이다.
- MLflow 쪽 사실 하나를 바로잡는다 — 내장 judge가 "범용 4종"뿐이라고 적었는데, 지금은 더 많고 커스텀 judge(`make_judge`)도 공식 지원한다(§3). 결론은 바뀌지 않는다.
- 셋업 비용 근거를 바꾼다 — 「서버 구성이 필요해 무겁다」가 아니다. 로컬 SQLite로 서버 없이 쓸 수 있다. 실제 비용은 우리 모델 호출 방식(Elice 프록시)에 judge를 붙이는 작업이다(§2).
- 하네스 규모가 커졌다(100케이스 × 5회 × 설정 여러 개). 재검토 조건 하나에 가까워졌지만 넘지는 않았다(§4).

**미뤄도 잃는 것이 거의 없다 — 지금 하지 않아도 되는 이유.** 이 판단은 되돌리기 쉽다.
- 예측(모델 출력)과 판정(judge 결과)이 실험마다 JSON 원본으로 남아 있다 — 레포의 첫 실행분과, #146 이후 공유 드라이브 zip(§2).
- MLflow 3.x는 미리 만든 outputs를 넘기면 모델을 다시 부르지 않고 채점만 한다(§5, 1차 출처 §6-2). 그러니 재검토 조건(§4)이 생겼을 때 기존 원본을 그대로 들여올 수 있다.
- 그래서 지금 도입하든 필요해질 때 도입하든 이전 비용이 거의 같다. 지금 하면 그 비용을 쓸 일이 없을 수도 있는 시점에 먼저 쓰는 것뿐이다.
- 지금 방식(원본은 공용 저장소, 결과는 문서)은 멘토 리뷰 #146에서 정한 것이다(`experiments/intent-llm-model-comparison/README.md`). 즉 이 방식은 이미 리뷰를 거쳤다.

> 기준 버전: MLflow 3.17.1(PyPI, 2026-10-13). 아래 MLflow 기능 서술은 공식 문서로 확인한 것만 적었다(2026-10-14). 확인 방법은 §6.
> 옮길 때(2026-10-25) PyPI 최신은 3.17.2(2026-10-21) — 패치 릴리스라 위 기능 서술을 다시 확인하지는 않았다.

## 2. 인프라로서 — 필요 없었다 (9/24 이후 실제로 한 일로 확인)

MLflow(`mlflow.genai.evaluate()`)는 평가 실행 · metric 추적 · run 비교 UI · 데이터셋 · artifact 관리를 주는 실험 관리 인프라다. 9/24 이후 한 일은 모두 `docs/modules/case/experiments/intent-llm-model-comparison/scripts/`의 하네스(`runner.py` · `judge.py` · `aggregate.py` · `consistency_eval.py` · `judge_validation.py` · `pricing.py`)로 끝냈다.

| 9/24 이후 한 일 | 규모 | MLflow가 필요했나 |
| --- | --- | --- |
| judge 신뢰도 검증(멘토 Q1, 10/04) — 표본 80개 AI 재판정 + 갈린 10개 사람 판정, kappa 0.63 | 80 | 아니요 — `judge_validation.py` |
| judge 판정 기준 보강 · 재판정(Sonnet 보강 · Opus 5) | 1,152 판정 재확인 | 아니요 — 기준(프롬프트) 수정 + 재채점 |
| 단일 점수(정확도 × 일관성) · 5회 반복 확정(멘토 Q2, 10/05) | robustness-v3 100케이스 × 5회 × 2모델 | 아니요 — `consistency_eval.py` |
| challenger 검증 — GPT-6 Luna · reasoning effort(#281, 10/06) | 6개 설정 | 아니요 — 하네스에 `model@effort` 옵션 추가 |

- 집계는 손으로 하지 않는다 — 스크립트가 낸다. 결과 해석은 `results/*.md`와 결정 문서(`intent-llm-model-selection.md` §12~14)에 남겼다.
- **원본 관리는 멘토 리뷰 #146으로 정해졌다.** 모델 출력 · judge 판정 JSON은 레포에 두지 않고 실험마다 zip으로 팀 공유 드라이브에 두며, 결과 문서 첫머리 「원본」 줄에 파일 이름을 적는다(`experiments/intent-llm-model-comparison/README.md`, 같은 폴더 `.gitignore`). MLflow artifact store가 맡을 자리를 이 규칙이 채우고 있다.
**셋업 비용 — 무엇이 가볍고 무엇이 무거운가**
- **저장소는 가볍다(9/24 판 근거 정정).** 트래킹 서버가 필요하지 않다. `mlflow.set_tracking_uri("sqlite:///…")` 한 줄이면 로컬 SQLite 파일에 기록하고, 파일이 없으면 MLflow가 만든다. 그래서 「트래킹 서버/스토어 구성이 비용」이라는 9/24 서술은 근거로 쓰지 않는다.
- **judge 연결이 무겁다.** 우리 후보 · judge 모델은 Anthropic · Google API를 직접 부르지 않는다. Elice 프록시를 모델마다 다른 OpenAI 호환 `base_url`로 부른다(`scripts/candidates.py` — 후보는 모델별 환경변수, judge는 `JUDGE_MODEL_URL`).
  - MLflow의 직접 provider 방식(`anthropic:/…` · `gemini:/…`)은 각 사의 공식 API 키를 전제한다. 그래서 그대로는 붙지 않는다.
  - 붙이는 방법은 두 가지다. ① AI Gateway에 OpenAI provider endpoint를 모델마다 만들고 `openai_api_base`를 지정한 뒤 `gateway:/<endpoint>`로 부른다(Gateway 설정 · 실행이 추가된다). ② custom scorer 안에서 지금처럼 직접 호출한다(이러면 judge 호출 코드는 그대로 우리가 들고 간다).
- **기존 결과 이전.** 원본 JSON은 #146 규칙대로 레포가 아니라 공유 드라이브 zip에 있어, 옮기려면 받아서 변환해야 한다.

**판단:** 얻는 건 여전히 run 비교 UI와 결과 조회 정도다. 위 judge 연결 작업을 할 시간이 9/24보다 더 없다. 모델은 10/05에 Gemini 3.8 Flash로 확정됐고, 남은 평가는 재검토 트리거(`intent-llm-model-selection.md` §11 · §13 · §14)가 걸릴 때뿐이다. 이 문단은 측정이 아니라 판단이다 — 셋업에 몇 시간이 드는지는 재지 않았다.

## 3. judge 대체 수단으로서 — 지금도 안 맞는다

**사실 정정(2026-10-14):** 9/24 판에는 MLflow 내장 judge를 "correctness/safety/hallucination/groundedness 4종"이라고 적었다. 현재 MLflow 문서에는 Correctness · Guidelines · RelevanceToQuery · RetrievalGroundedness · Safety 외에 tool call · 다중 턴용 judge도 있고, `make_judge()`로 지시문 · 기대 출력을 넣은 커스텀 judge를 만드는 방식을 권장한다. 버전마다 목록이 달라 정확한 수는 설치 버전에서 확인해야 한다.

그래도 결론은 같다.
- **내장 judge는 우리 판정을 대신하지 못한다.** 우리가 채점하는 것은 "정정 문장에 끼어든 별개 사건 정보를 현재 사건 필드로 덮어썼는가"처럼 그 케이스의 `prior_hints`(이전 값)와 `expected_notes`(도메인 규칙)를 알아야 하는 판정이다.
- **9/24 이후 실제로 이것이 확인됐다.** judge 검증에서 찾은 오류(정정 케이스에서 언급되지 않은 필드의 올바른 null을 틀렸다고 판정 — 1,152개 중 11건)는 판정 기준에 이 프로젝트 전용 규칙을 예시와 함께 넣어서 고쳤다(`intent-llm-model-selection.md` §12). 범용 judge로는 이 규칙을 표현할 수 없고, `Guidelines`나 `make_judge`를 써도 결국 같은 규칙을 직접 써야 한다.
- **`make_judge`로 옮기는 모양.** 지시문에 쓸 수 있는 템플릿 변수는 예약된 것(`{{ inputs }}` · `{{ outputs }}` · `{{ expectations }}` · `{{ trace }}`, 최신 문서에는 `{{ conversation }}`도)뿐이다. 그래서 `prior_hints` · `expected_notes` 같은 케이스별 맥락은 `inputs`나 `expectations` 안에 넣어 넘겨야 한다. `{{ trace }}`를 쓰면 다른 변수와 함께 쓸 수 없다.
- **반대 근거(공정하게 적는다).** `make_judge`는 `feedback_value_type`으로 판정값 타입을 고정할 수 있다 — 예: `correct/partial/hallucinated/missed` 네 값만 나오게. 지금 하네스가 직접 하는 출력 형식 검증 일부를 MLflow에 맡길 수 있다는 뜻이다.
- 그래도 결론은 같다. MLflow를 쓰더라도 「커스텀 judge(`JUDGE_SYSTEM_PROMPT`)를 `make_judge` 틀에 옮겨 담는」 용도이지, 판정 규칙을 직접 쓰는 일을 줄여 주지 않는다.

## 4. 재검토 조건 — 10/14 점검

| 조건(9/24) | 10/14 상태 |
| --- | --- |
| 이 하네스를 프로젝트 이후 다른 프로젝트에서 재사용 | 해당 없음 |
| 프로젝트 타임라인이 길어져 셋업 비용을 회수할 시간이 생김 | 해당 없음 — 남은 기간이 더 짧다 |
| 평가 규모가 48~55케이스보다 크게 늘어 손으로 집계하기 부담 | **가까워짐, 넘지 않음** — 100케이스 × 5회 × 설정 6개까지 늘었지만 집계는 스크립트가 하고 부담이 없었다 |

실사용 문장 세트로 다시 재야 하는 시점(`intent-llm-model-selection.md` §13 재검토 트리거)이 오면, 그때 규모와 남은 기간을 보고 다시 판단한다. 도입하게 되면 기존 JSON 원본을 미리 만든 outputs로 들여와 다시 채점하면 된다(§1 「미뤄도 잃는 것이 거의 없다」).

## 5. 팀 문서와의 관계

- eval 모듈의 `docs/modules/eval/experiment-guide.md` §16은 MLflow를 Run · Parameter · Metric · Artifact 기록 도구로 둔다(2026-09-04 작성). 반면 같은 모듈의 `eval/README.md`는 결과를 JSON + git으로 남기고 「MLflow는 보조」라고 적고, `docs/modules/eval/research/architecture-input-memo.md`는 「1 run = 1 결과 전제라 재채점 구조와 충돌해 채택하지 않았다」고 적는다.
- 이 문서의 결론은 **case의 intent LLM 평가에만** 해당한다. eval 모듈의 문서 간 어긋남은 eval Owner(김대원)가 정리할 일이다.
- **참고 사실(2026-10-14 확인):** 조사 메모의 「1 run = 1 결과라 재채점과 충돌」은 MLflow 3.x GenAI 평가에는 맞지 않는다. `mlflow.genai.evaluate()`에 미리 만든 outputs나 저장된 trace를 넘기고 `predict_fn`을 생략하면, 모델을 다시 부르지 않고 채점만 한다. 공식 문서도 trace를 한 번 만들어 여러 평가에 재사용하라고 권한다. 그래서 이 문서는 재채점을 MLflow 미도입 근거로 쓰지 않는다. eval 쪽 판단에 이 사실을 쓸지는 eval Owner가 정한다.

## 6. 참고 자료

확인일은 모두 2026-10-14다. 각 출처가 이 문서의 어느 서술을 뒷받침하는지 적었다.

### 6-1. 레포 문서 · 코드 (`develop` 기준)

| 출처 | 뒷받침하는 서술 |
| --- | --- |
| [`intent-llm-model-selection.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/decisions/intent-llm-model-selection.md) §12 · §13 · §14 | §2 9/24 이후 한 일(judge 검증 · 단일 점수 확정 · Luna 검증), §3 judge 오류 11건과 판정 기준 보강, §4 재검토 트리거 |
| [`intent-llm-eval-target-thresholds.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/decisions/intent-llm-eval-target-thresholds.md) §1.0 | §2 단일 점수(정확도 × 일관성) 기준 |
| [`experiments/intent-llm-model-comparison/README.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/experiments/intent-llm-model-comparison/README.md) · 같은 폴더 [`.gitignore`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/experiments/intent-llm-model-comparison/.gitignore) | §2 원본 보관 규칙(멘토 리뷰 #146 — 공유 드라이브 zip, 결과 문서 「원본」 줄) |
| [`scripts/`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/experiments/intent-llm-model-comparison/scripts) (`runner.py` · `judge.py` · `aggregate.py` · `consistency_eval.py` · `judge_validation.py` · `pricing.py`) | §2 모든 평가를 커스텀 하네스로 했다 |
| [`scripts/candidates.py`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/experiments/intent-llm-model-comparison/scripts/candidates.py) 10~14행 | §2 Elice 프록시 · 모델별 OpenAI 호환 `base_url` · `JUDGE_MODEL_URL` |
| [`results/`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/case/experiments/intent-llm-model-comparison/results) (`judge-validation-robustness-v2.md` · `consistency-robustness-v3.md` · `luna-reasoning-effort-v3.md`) | §2 표의 규모 · 수치 |
| [`docs/modules/eval/experiment-guide.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/eval/experiment-guide.md) §16 · [`eval/README.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/eval/README.md) 17행 · [`docs/modules/eval/research/architecture-input-memo.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/eval/research/architecture-input-memo.md) 32행 | §5 eval 문서 간 MLflow 입장 차이 |

### 6-2. MLflow 1차 출처 (기준 버전 3.17.1)

| 출처 | 뒷받침하는 서술 |
| --- | --- |
| [PyPI — mlflow](https://pypi.org/project/mlflow/) · [GitHub releases](https://github.com/mlflow/mlflow/releases) | §1 최신 버전 3.17.1(2026-10-13) |
| [Tracking Experiments with Local Database](https://mlflow.org/docs/latest/ml/tracking/tutorials/local-database/) · [Backend Stores](https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/) · [Tracking Server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/) | §2 SQLite 로컬 저장 · 파일 자동 생성 · 서버 불필요 |
| [Supported judge models](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/custom-judges/supported-models/) | §2 직접 provider 형식(`anthropic:/` · `gemini:/`)과 각 사 API 키 전제 |
| [AI Gateway Configuration](https://mlflow.org/docs/latest/genai/governance/ai-gateway/configuration/) · [LLM-based Scorers](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/) | §2 OpenAI provider endpoint의 `openai_api_base` · `gateway:/` judge 호출 |
| [LLM Judges and Scorers](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/) · [Built-in LLM Judges](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/predefined/) | §3 내장 judge 목록 정정 |
| [Custom Judges](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/custom-judges/) · [Template-based LLM Scorers](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/make-judge/) · [make_judge (3.4.0)](https://mlflow.org/docs/3.4.0/genai/eval-monitor/scorers/llm-judge/make-judge/) | §3 `make_judge` 권장 · 예약 템플릿 변수(3.4.0은 4개, 최신은 `conversation` 추가) · `trace` 단독 사용 |
| [TypeSafe Judge Models](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/custom-judges/typesafe) | §3 반대 근거 `feedback_value_type` |
| [Evaluating (Production) Traces](https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/traces/) · [Migrating from Legacy LLM Evaluation](https://mlflow.org/docs/latest/genai/eval-monitor/legacy-llm-evaluation/) · [Databricks — Evaluate GenAI during development](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/concepts/eval-harness) | §5 저장된 outputs · trace 재채점(`predict_fn` 생략), trace 재사용 권장 |

### 6-3. 딥리서치 리포트 검증에 쓴 출처

| 출처 | 확인한 것 |
| --- | --- |
| [mlflow/mlflow Issue #22983](https://github.com/mlflow/mlflow/issues/22983) | `generate_rationale_first`는 내부 클래스 인자로 stack trace에만 나온다 — `make_judge`의 문서화된 옵션이 아니다 |
| [mlflow/mlflow Discussion #22671](https://github.com/mlflow/mlflow/discussions/22671) | 로컬 · 자체 endpoint를 judge로 쓰는 방법은 Gateway나 custom scorer다 — 리포트의 「20분 연동」은 이 작업을 빼고 셌다 |
| [OpenAI — Deprecations](https://developers.openai.com/api/docs/deprecations) | 리포트의 OpenAI Evals 종료 일정(2026-10-31 읽기 전용, 11-30 종료)은 맞다. MLflow 판단과 무관해 본문에는 넣지 않았다 |

### 6-4. 딥리서치 리포트 (담당자 보관, 레포에 없음)

- **2026-09-24 리포트** — MLflow 한계 항목. 인용된 수치 · 논문 ID는 원문 재확인 필요.
- **2026-10-14 리포트**(이 문서의 사유 검증용) — 결론(미도입 유지), 재채점 지원, 템플릿 변수는 위 1차 출처로 확인해 반영했다. 아래는 확인되지 않거나 틀려서 **반영하지 않았다**:
  - `generate_rationale_first=True`로 판정 근거를 저장한다 — 문서화된 옵션이 아니다(Issue #22983).
  - 내장 judge 목록 — 레거시 `mlflow.metrics`와 GenAI judge가 섞여 있고 `Guidelines`가 빠졌다(Built-in LLM Judges).
  - judge 연결 「20분」, `endpoints:/gemini-…` 예시 — 우리 Elice 프록시 구조를 반영하지 않았고 형식도 맞지 않는다(Supported judge models).
  - 셋업 · 이전 「2~4시간」, 도구별 도입 시간 — 출처 없는 추정이다.
  - 도입 전환 임계(500케이스 · 20~30회 · 주 10회 · 「2개 이상이면 전환」) — 출처가 없다.
  - 재시도 · 비동기 · 파싱 보일러플레이트가 준다 — 확인하지 못했다.
  - judge가 환경변수 `OPENAI_API_BASE`를 읽는다 — 문서에서 확인하지 못했다(리포트 주장은 아니지만 검증 중 나온 가능성이라 함께 적는다).
