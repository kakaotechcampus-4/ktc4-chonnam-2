# AI·OCR 실험 환경 및 기록 가이드

## Experiment Note Template

> 서비스 기획안 1.3의 `#실험 채널` 형식을 문서 템플릿으로 옮겼다.

```text
[CASE]
real / synthetic
visual event type
positive / hard-negative
source duration

[INPUT]
user hint / ground-truth interval

[PIPELINE]
Coarse model/settings
Fine: Direct / Structured / +Reference

[RESULT]
Recall@K / timestamp error / FP-hour
Fine Recall / HN-FPR / Precision
Final Recall@3
latency / tokens / cost / Fine exposure

[FAILURE]
stage: COARSE / FINE / PLATE / OVERLAY_TIME
kind:  [search]  SEARCH · PRIMITIVE · TEMPORAL_ORDER · TARGET_ASSOCIATION · FINE_FN · COST
       [readout] PLATE_TARGET_ASSOCIATION · PLATE_DETECTION · PLATE_RECOGNITION · OVERLAY_VALIDATION
       [공통]    INFRA

[LEARNING]
다음 실험에서 바꿀 한 가지
```

`[FAILURE]`의 이름·stage 체계의 원본은 `modules/search/decisions/failure-taxonomy.md`(COARSE·FINE)와 `modules/readout/decisions/failure-taxonomy.md`(PLATE·OVERLAY_TIME)다. 위 템플릿의 이름은 그 사본이므로 어긋나면 그쪽이 이긴다. 1.3의 초기 분류(`SEARCH / PRIMITIVE / TEMPORAL / TARGET / FINE_FN / OTHER`)는 대체되었다.

실제 사용 시 contract version, 구현 이름표, manifest version 등 추가 필드가 필요하면 `module-architecture.md`와 eval Owner의 후속 설계를 따른다.

## 1. 목적

이 문서는 실험 양식을 강제하기 위한 템플릿이 아니다.

AI 영상 탐색과 OCR 실험에서 **어떤 조건으로 실행했는지, 무엇을 변경했는지, 왜 결과가 달라졌는지를 나중에도 추적할 수 있도록 공통적으로 기록할 항목을 정리**한다.

AI 시스템은 모델뿐 아니라 프롬프트, 입력 데이터, FPS, 해상도, 전처리 방식 등 여러 요소가 결과에 영향을 준다. 따라서 평가 점수만 남기면 변경 원인이나 실패 원인을 추적하기 어렵다.

실험 기록의 최소 목표는 다음 질문에 답할 수 있는 것이다.

> 어떤 데이터와 설정으로 실행했는가?
이전 실험과 무엇이 달라졌는가?
성능·비용·속도가 어떻게 변했는가?
어떤 사례에서 실패했고 어느 단계가 원인이었는가?
필요하면 같은 조건으로 다시 실행할 수 있는가?

평가의 목적 역시 단순히 점수를 만드는 것이 아니라 **변경이 실제 개선인지 개악인지 판단할 수 있는 반복 구조를 만드는 것**에 있다.

---

## 2. 실험 기본 정보

실험마다 최소한 아래 정보는 남긴다.

| 항목 | 예시 |
| --- | --- |
| 실험명 | `search_fps_compare_v1` |
| 실행자 / 실행일 |  |
| 실험 목적 | 1fps → 2fps 변경 효과 확인 |
| Baseline | 기존 설정 또는 Run |
| 변경 사항 | FPS만 1 → 2 |
| Git Commit | `a31f...` |
| MLflow Run | Run ID 또는 링크 |

### 왜 필요한가?

AI 실험에서는 한 번에 여러 설정을 바꾸면 **무엇 때문에 성능이 변했는지 알기 어렵다.**

가능하면 한 실험에서는 핵심 변수 하나를 중심으로 비교하고, 동시에 여러 항목을 바꿨다면 무엇을 변경했는지 명확하게 기록한다.

`Git Commit`은 해당 결과가 **어떤 코드 상태에서 나온 것인지** 다시 확인하기 위한 기준점이다.

---

## 3. 평가 데이터와 정답 데이터

성능 수치에는 반드시 **어떤 평가셋으로 측정했는지**가 따라야 한다.

| 항목 | 예시 |
| --- | --- |
| Dataset | `long_dashcam_eval` |
| Dataset Version | `v0.2` |
| 영상 수 / 총 길이 |  |
| Positive 수 |  |
| Hard-negative 수 |  |
| 사건 유형 구성 |  |
| 주간/야간/우천 등 구성 |  |
| Ground Truth Version | `gt_v0.2` |

### 왜 필요한가?

서로 다른 데이터셋에서 나온 `Recall@3 = 90%`와 `Recall@3 = 85%`는 직접 비교할 수 없다.

따라서 성능 결과는 항상

```
Dataset v0.2
Recall@3 = 87%
```

처럼 데이터 버전과 함께 관리한다.

정답 데이터(Ground Truth)는 최소한 다음 정보를 포함한다.

```
video_id
event_type
gt_start
gt_end
positive / hard-negative
```

책에서도 평가를 **데이터, 태스크, 스코어러**의 조합으로 보고 있기 때문에, 평가 코드뿐 아니라 어떤 데이터를 사용했는지가 고정되어야 비교가 가능하다.

---

## 4. Positive / Hard-negative

평가셋에는 실제 사건뿐 아니라 **위반처럼 보이지만 정상인 사례**도 포함한다.

예:

```
백색 실선에서 차로변경
→ Positive

백색 점선에서 정상 차로변경
→ Hard-negative
```

### 왜 필요한가?

Positive만 평가하면 모든 장면을 위반이라고 판단하는 모델도 높은 Recall을 얻을 수 있다.

따라서

- 실제 사건을 놓치지 않는지
- 정상 사례를 사건으로 잘못 판단하지 않는지

두 가지를 함께 확인해야 한다.

---

## 5. 영상 입력 및 전처리 설정

영상 분석에서는 모델뿐 아니라 **모델에게 어떤 형태의 영상을 보여줬는지**가 성능에 직접 영향을 준다.

| 항목 | 예시 |
| --- | --- |
| 원본 / Proxy | Proxy |
| Resolution | 480p |
| FPS | 1 |
| Chunk Length | 20 sec |
| Chunk Overlap | 5 sec |
| Frame Extraction | FFmpeg |
| 전처리 | resize 등 |
| FFmpeg Version | 자동 기록 권장 |

### FPS

FPS가 높아지면 더 많은 장면을 볼 수 있지만 처리량과 비용도 증가한다.

따라서

```
1fps → Recall 84%, 비용 100
2fps → Recall 90%, 비용 170
```

처럼 **품질과 비용의 trade-off**를 비교할 수 있어야 한다.

### Chunk / Overlap

긴 영상을 일정 길이로 나누어 처리할 경우 사건이 chunk 경계에서 잘릴 수 있다.

```
chunk = 20 sec
overlap = 5 sec
```

같은 설정도 검색 성능에 영향을 줄 수 있으므로 실험 조건으로 관리한다.

---

## 6. AI 영상 탐색 설정

Coarse와 Fine은 가능하면 별도로 기록한다.

### Coarse Search

```
model
model_version
prompt_version

fps
resolution
chunk
overlap

retrieval_top_k
candidate_merge_range
time_prior 사용 여부
```

### Fine Verification

```
model
model_version
prompt_version

clip_length
fps
resolution

fine_candidate_count
final_top_k
retry_count
```

### 왜 분리하는가?

최종 Top-3에서 사건을 놓쳤더라도 원인은 여러 가지일 수 있다.

```
Coarse에서 사건 자체를 놓침
        ↓
Fine이 볼 기회 없음

또는

Coarse에서는 사건을 찾음
        ↓
Fine에서 잘못 제거
```

두 경우는 개선 방법이 다르다.

따라서 **어느 단계까지 사건이 살아 있었는지**를 확인할 수 있어야 한다.

---

## 7. 모델·프롬프트 버전

최소한 아래는 기록한다.

```
model
model/version 또는 snapshot
prompt_version

temperature
top_p
max_tokens
seed
reasoning/thinking 설정
output schema version
```

지원하지 않거나 사용하지 않는 파라미터는 생략한다.

### Prompt Version을 별도로 두는 이유

프롬프트 역시 코드 변경처럼 결과에 영향을 줄 수 있다.

따라서 프롬프트 전체를 매 실험 기록에 복사하기보다는 Git에서 관리하고,

```
prompt_version: fine_v3
```

처럼 버전만 실험에 연결한다.

책에서도 프롬프트는 버전 관리하고 실행 로그에는 **프롬프트 버전 또는 해시를 남기는 방식**을 권장한다.

---

## 8. 번호판 OCR 설정

OCR은 가능하면 **Detection과 Recognition을 분리**해서 기록한다.

```
Plate Detector
Detector Version

OCR Model
OCR Model Version

Crop Size
Best Frame 사용 여부
Multi-frame 사용 여부
사용 Frame 수

Image Preprocessing
Confidence Threshold
Abstention Threshold
```

### 왜 분리하는가?

OCR 실패는 크게 두 종류다.

```
번호판 영역을 못 찾음
→ Detection Failure

번호판 영역은 맞게 찾았지만
문자를 잘못 읽음
→ Recognition Failure
```

두 문제를 하나의 `OCR 실패`로 묶으면 무엇을 개선해야 하는지 알기 어렵다.

### Best Frame / Multi-frame

블랙박스 영상에서는 같은 번호판도 프레임마다 화질이 다르기 때문에,

- 단일 Frame
- Best Frame
- Multi-frame

중 어떤 전략을 사용했는지도 OCR 성능의 실험 변수다.

---

## 9. 판단보류(Abstention)

불확실한 입력에 대해 반드시 값을 만들어내는 것이 좋은 시스템은 아니다.

예를 들어 번호판이 읽기 어려운 경우

```
12가3456
```

으로 잘못 확정하는 것보다

```
확인 필요
```

로 넘기는 것이 더 적절할 수 있다.

따라서 OCR 및 영상 판단에서는

- 맞게 확정하는 능력
- 불확실한 경우 판단을 보류하는 능력

을 함께 평가한다.

---

## 10. 실행 환경

재현성 확인을 위해 아래 정보는 남기는 것이 좋다.

```
OS
Python Version
Dependency Lock

Docker Image
CPU / GPU
CUDA

FFmpeg Version
PaddleOCR Version
AI SDK Version

실행 환경
Local / AWS / 기타
```

이 항목은 사람이 매번 작성하기보다 **실험 시작 시 자동 수집하도록 만드는 것을 권장**한다.

---

## 11. 품질뿐 아니라 비용과 지연시간도 기록

AI 시스템에서는 최고 성능 모델이 반드시 실제 제품에 가장 적합한 모델은 아니다.

예:

```
방법 A
Recall@3 = 87%
비용 = 100원
처리시간 = 2분

방법 B
Recall@3 = 89%
비용 = 500원
처리시간 = 12분
```

따라서 실험에서는 가능하면 다음을 함께 기록한다.

```
total_latency

coarse_latency
fine_latency
ocr_latency

API call count

input_tokens
output_tokens

total_cost
cost_per_video_hour

retry_count
fine_exposure_ratio
```

책에서도 AI 시스템을 평가할 때 품질뿐 아니라 **운영 지표와 비용 지표를 함께 추적해야 한다**고 설명한다.

---

## 12. 실패 사례와 Artifact

평가 결과는 숫자만 남기지 않는다.

예:

```
Recall@3 = 84%
```

가 나왔다면 중요한 것은 **실패한 16%가 어떤 사례인지**다.

가능하면 다음 결과물을 함께 보존한다.

```
Top-K Candidate JSON
Fine 결과

모델 Raw Output
Structured Output

실패 영상 Clip

OCR Best Frame
OCR Candidate Frames

Error Log
```

이런 실험 결과물을 `Artifact`라고 부른다.

목적은 나중에 실패 사례를 다시 열어보고 **왜 실패했는지 분석할 수 있도록 하는 것**이다.

---

## 13. 실패 유형(Failure Taxonomy)

실패는 단순히 `FAIL`로 기록하지 않고 가능하면 원인을 분류한다.

**이름의 원본은 `search`·`readout`의 `decisions/failure-taxonomy.md`다.** 아래 표는 이 가이드가 처음 제안한 후보 목록이며, Owner가 확정할 때 흡수·병합 대상으로 참고한다. 실험 기록에는 확정된 이름을 쓴다.

| Failure Type | 의미 |
| --- | --- |
| `SEARCH_MISS` | 사건 자체를 찾지 못함 |
| `RANKING_FAIL` | 후보에는 있지만 Top-K 밖 |
| `TEMPORAL_FAIL` | 사건 시간 구간 오류 |
| `TARGET_FAIL` | 다른 차량/대상 선택 |
| `EVENT_CLASS_FAIL` | 사건 유형 판단 오류 |
| `FINE_VERIFY_FAIL` | Coarse 성공 후 Fine에서 제거 |
| `OCR_DETECTION_FAIL` | 번호판 탐지 실패 |
| `OCR_RECOGNITION_FAIL` | 번호판 문자 인식 실패 |
| `OVERCONFIDENT` | 불확실하지만 확정값 반환 |
| `SYSTEM_FAIL` | timeout/API/파이프라인 오류 |
| `UNKNOWN` | 아직 원인 불명 |

### 왜 필요한가?

예를 들어 FAIL 100개를 분류했을 때

```
OCR Recognition 52
Search Miss     18
Fine Verify     12
기타            18
```

라면 다음 개선 우선순위를 정하기가 훨씬 쉬워진다.

이 분류는 처음부터 완벽하게 만들 필요가 없으며 **실제 실패 사례를 보면서 추가·수정한다.**

책에서도 평가의 시작을 범용 지표 선정이 아니라 **실제 출력의 에러 분석과 반복되는 실패 유형의 분류**로 두고 있다.

---

## 14. 자동 검증

사람이나 AI가 판단할 필요가 없는 것은 코드로 검사한다.

예:

```
JSON Schema가 유효한가

candidate_start < candidate_end 인가

후보 구간이 영상 길이를 벗어나지 않는가

confidence 범위가 정상인가

timestamp source가 허용 enum인가

존재하는 video_id인가
```

이런 검사는 가능하면 `pytest`로 매 변경마다 실행한다. CI 추가는 가능하지만(`management/ownership.md` §6) 아직 붙이지 않았으므로 **당장은 로컬에서 돌린다**.

책에서도 **코드로 결정론적으로 검사할 수 있는 것은 LLM 평가에 맡기지 않는 것**을 원칙으로 둔다.

---

## 15. 초기 12개 테스트 케이스의 역할

현재 정의한 12개 테스트 케이스는 전체 모델 성능을 대표하는 대규모 평가셋이라기보다 **기본 기능 및 회귀(Regression) 확인용 세트**로 본다.

즉 모델·프롬프트·파이프라인을 변경했을 때

> 기존에 통과하던 기본 사례가 새 변경으로 깨지지 않았는가?

를 빠르게 확인하기 위한 용도다.

본격적인 Recall@K, FP/hour, OCR 정확도 등의 성능 평가는 별도의 고정된 실제 평가 데이터셋에서 진행한다.

---

## 16. MLflow / Git / Notion 역할

세 곳에 같은 내용을 중복해서 작성하지 않는다.

| 도구 | 역할 |
| --- | --- |
| **Git** | Code / Prompt / Config / 평가 코드 |
| **MLflow** | Run / Parameter / Metric / Artifact |
| **Notion** | 실험 목적 / 결과 해석 / 실패 원인 / 다음 결정 |

집계 결과 JSON은 MLflow와 별개로 `eval/results/`에 git으로도 남긴다 — 결과는 파일 기반으로 버전 추적 가능해야 한다(`architecture/module-architecture.md` §4-모듈7 ⑥ · §10-2 「Eval result: JSON + git」).

예를 들어 Notion에는 다음 정도만 남겨도 충분하다.

```
실험 목적

Baseline
변경 사항

MLflow Run

핵심 결과

주요 실패 사례

결론

다음 실험
```

세부 파라미터와 Raw Result는 MLflow와 Git에서 확인한다.

---

## 17. Trace는 파이프라인 연결 이후 적용

실험 단위의 비교는 MLflow로 할 수 있지만, **개별 사건이 어느 단계에서 실패했는지**를 확인하려면 Trace가 필요하다.

예:

```
Case #127

Coarse Search
→ GT 사건 후보 #14 발견

Candidate Merge
→ 정상

Fine Verification
→ 후보 #14 제거

Final Top-3
→ GT 없음
```

이렇게 보면 최종 실패 원인이 Search 전체가 아니라 `Fine Verification`임을 알 수 있다.

책에서도 AI 시스템의 처리 과정을 **세션 → 트레이스 → 스팬**으로 나누고 각 단계의 입출력·시간·상태를 기록하는 구조를 설명한다.

초기부터 별도 Observability 플랫폼을 반드시 구축할 필요는 없고, 실제 파이프라인이 연결되는 시점부터 적용하면 된다.

---

## 18. 우선 적용 범위

10주 프로젝트에서 모든 실험 인프라를 한 번에 구축할 필요는 없다.

우선순위는 다음 정도로 둔다.

### 먼저 적용

```
1. Git 기반 Code / Prompt / Config Versioning

2. 고정 평가 Dataset + Ground Truth Versioning

3. MLflow Experiment Tracking

4. 실패 사례 및 Failure Taxonomy

5. 초기 12개 Regression Test

6. pytest 기반 결정론적 검사
```

### 파이프라인 연결 후

```
7. Trace / Observability

8. Eval Viewer
```

Eval Viewer는 평가 데이터가 많아져 사람이 영상·후보·OCR 결과를 여러 화면에서 확인하는 것이 병목이 될 때 추가한다.

책에서도 평가 도구 자체를 먼저 구축하기보다는 **실제 데이터를 보고 실패 유형을 파악한 뒤 평가 인프라를 만드는 순서**를 강조한다.

---

## 실험 기록 원칙

실험을 끝낸 뒤 최소한 다음에는 답할 수 있어야 한다.

> **무엇을 검증한 실험인가?Baseline에서 무엇을 변경했는가?어떤 평가 데이터로 실행했는가?어떤 코드·모델·프롬프트·영상 설정이었는가?품질·비용·속도가 어떻게 변했는가?주요 실패 유형은 무엇이었는가?결과를 바탕으로 다음에 무엇을 할 것인가?**

핵심은 모든 값을 문서에 많이 적는 것이 아니라,

> **“무엇을 바꿨더니 어떤 결과가 나왔고, 왜 그렇게 됐는지 설명할 수 있는 상태”를 유지하는 것**

이다.
