# 카테캠 2단계 ML API 환경

**Status:** Input — 카테캠 2단계 운영 공지 요약 + 엘리스 공식 문서 확인  
**Source:** 카테캠 운영진 2단계 MLAPI 지원 공지(비공개) + 엘리스 AI Cloud 공식 문서 + 1단계 ML API 사용 가이드(과거 기준 참고)  
**Notice date:** 확인 필요  
**Captured:** 2026-10-02  
**Maintainer:** common/runtime — 김준영  
**Router:** [Official Inputs](./README.md)

> 카테캠 공지 원문과 내부 포털 URL은 공개 레포에 싣지 않는다. §1은 2단계 최신 운영 공지를 사실만 요약했고, §2–§4는 엘리스 공식 공개 문서를 기준으로 재서술했다. 1단계 가이드는 과거 사용 방식 확인에만 사용하며, **2단계와 충돌하는 모델 제한은 2단계 공지를 우선**한다.
>
> 이 문서는 외부 입력이며 결정이 아니다. 실제 provider/model 선택, retry/timeout, concurrency, 비용 guardrail 등 Runtime/Ops 결정은 별도 Spec/Decision에서 이 문서를 근거로 정한다.

## 1. 카테캠 2단계 지원 조건

| 항목 | 2단계 기준 |
| --- | --- |
| 적용 범위 | 2단계 팀 프로젝트 |
| 사용 가능 방식 | 모델 라이브러리에서 **Serverless**로 제공되는 모델만 사용 가능 |
| 모델 제한 | Serverless 모델 안에서는 별도 모델 제한 없음 |
| Dedicated | 사용 불가 |
| 팀 예산 | 팀당 **₩120,000 크레딧** |
| 사용량 합산 | 팀원들의 사용량 총합을 팀 예산과 비교 |
| 예산 초과 | 공지상 API Key가 자동 삭제됨 |
| 한도 초기화 | **매월 29일 자정 이후** 초기화 |
| 사용량 조회 | 현재 참가자가 직접 확인할 수 없음. 운영진이 별도 안내하며, 필요 시 문의하여 확인 |
| 모델 선택 기준 | 예산을 고려해 팀에 적합한 Serverless 모델을 선택 |

### 1.1 1단계 가이드와의 경계

1단계 클론코딩 가이드는 당시 사용할 모델을 openai/gpt-4.1-mini와 openai/text-embedding-3-small로 지정했고, 모델별 Base URL과 Serverless API Key를 사용하도록 안내했다.

이 제한은 **1단계 커리큘럼용 고정값**이다. 2단계 최신 공지는 Serverless 모델에 대해 모델 제한이 없다고 별도로 안내하므로, 1단계의 두 모델만 사용할 수 있다고 해석하지 않는다.

다만 다음 운영 원칙은 현재 공개 엘리스 문서와도 일치한다.

- API 호출에는 API Key 인증이 필요하다.
- Serverless와 Dedicated Key는 구분되어 관리된다.
- 모델 상세에서 실행 방식, 가격, API 사용 예시를 확인한다.
- Key와 endpoint/model 정보는 공개 저장소에 비밀값으로 남기지 않는다.

## 2. 엘리스 Serverless의 공식 동작

엘리스 공식 문서에서 Serverless는 별도 인스턴스 생성이나 서버 설정 없이 사전 준비된 endpoint를 호출하는 방식이다.

- 모델 라이브러리에서 **Serverless 지원 모델**을 선택한다.
- 모델 상세에서 API 호출 정보와 가격, 사용 예시를 확인한다.
- Serverless API Key를 포함해 호출한다.
- 과금은 호출/사용량 기반이며 모델 유형에 따라 단위가 다를 수 있다.
- 일반 엘리스 환경의 Serverless 이용 현황에서는 총 이용 금액, 기간별 호출량과 Token / Seconds(Audio) / Megapixels(Image) / Pages(Document) 등을 확인할 수 있다.

단, 마지막 항목은 **일반 엘리스 제품 기능**이다. 카테캠 2단계에서는 현재 참가자가 사용 내역을 직접 볼 수 없다는 과정 고유 공지가 있으므로, 팀 운영에서는 카테캠 제한을 우선한다.

또한 모델 라이브러리는 공개 모델뿐 아니라 **기관 전용 모델**도 가질 수 있다. 따라서 2단계에서 실제 선택 가능한 모델 집합은 문서에 고정 목록으로 복사하지 않고, 선택 시점에 카테캠 조직의 모델 라이브러리에서 Serverless 표시를 확인한다.

## 3. API Key와 호출 방식

### 3.1 인증

엘리스 ML API는 API Key 인증을 요구한다.

~~~http
Authorization: Bearer <Serverless API Key>
~~~

공식 API Key 문서 기준:

- Serverless / Dedicated Key를 각각 관리한다.
- 만료일을 설정할 수 있다.
- 새 Key 값은 발급 직후에만 확인할 수 있다.
- 삭제하면 즉시 해당 Key로 호출할 수 없다.
- 재발급 시 기존 Key는 즉시 무효화된다.
- GitHub 등 공개 저장소에 Key를 저장하지 않는다.

2단계는 Dedicated를 사용할 수 없으므로 프로젝트에서 필요한 Key 종류는 **Serverless**다.

### 3.2 Endpoint / API 호환성

Endpoint와 지원 API는 모델별 상세 정보를 기준으로 확인한다.

1단계 카테캠 가이드는 OpenAI SDK 호환 방식으로 base_url, api_key, model을 바꾸어 호출하도록 안내했다. 현재 엘리스의 일부 공개 Serverless 모델 상세도 /v1/chat/completions, 스트리밍, 도구 호출, 구조화 출력 등 OpenAI 호환 인터페이스를 제공한다.

반면 엘리스의 일반 ML API 문서는 BentoML 기반의 사용자 정의 API도 설명한다. 따라서 **모든 모델이 동일한 endpoint/path/요청 schema를 가진다고 전역 가정할 수는 없다.** 실제 선택 모델의 Model Library 상세와 예제 코드를 확인해야 한다.

## 4. Runtime 관점에서 확인된 제약과 미확인 항목

워크플로우 §1의 조사 항목을 2026-10-02 기준 공식 자료와 대조했다.

| 조사 항목 | 현재 확인 상태 | 근거 / 비고 |
| --- | --- | --- |
| 지원 API | **모델별 확인** | Model Library 상세에 API/예제 제공. 일부 Serverless 모델은 OpenAI 호환 API 제공 |
| media 전달 방식 | **모델별 확인** | 입력 modality와 전달 schema가 모델별로 다름. 공개 Gemini Serverless 예시 중에는 text/image/video/file/audio 입력을 지원하고 Files API 없이 일부 파일을 message 내 base64 data URL로 전달하는 모델도 있음 |
| 최대 입력 크기 | **전역값 확인 안 됨** | 일부 모델은 context window를 공개하지만, 공통 request byte/file-size 상한은 확인한 공식 문서에서 찾지 못함 |
| timeout | **확인 필요** | Serverless 전역 timeout 보장값을 확인한 공식 문서에서 찾지 못함 |
| rate limit / concurrency | **기관 정책 확인 필요** | 공개 Serverless 모델 상세는 속도 제한이 기관별 정책에 따르며 구체 값은 담당자 문의 대상으로 안내 |
| 지원 codec / container | **모델별 확인 필요** | 영상 입력 가능 여부와 codec/container 허용 범위를 전역 정책으로 확인하지 못함 |
| 비용 | **모델별 가격 + 팀 ₩120,000 상한** | Serverless는 사용량 기반 과금. 모델 상세에 가격 표시. 카테캠은 별도로 팀 크레딧 한도 적용 |
| retention / logging / delete | **payload 정책 확인 필요** | 공식 Key 문서는 사용자별 호출/비용/사용량 추적을 설명하지만, prompt/media payload 자체의 보관 기간·삭제 정책은 확인한 ML API 문서에서 찾지 못함 |

### 4.1 비용에서 아직 확인할 것

카테캠 공지는 팀 예산을 원화 ₩120,000 크레딧으로 제시하고, 엘리스 공개 Model Library의 일부 모델 가격은 달러 기준으로 표시한다.

현재 공지만으로는 다음을 확정할 수 없다.

- 원화 크레딧과 모델 표시 가격 사이의 환산 기준
- 환율 적용 시점
- VAT 포함 여부
- 소수점/반올림 방식
- 예산 초과 시 자동 삭제되는 Key의 범위(특정 Key / 팀의 모든 Serverless Key)
- 초과 후 재발급 가능 여부와 복구 절차
- 매월 29일 자정의 기준 timezone

비용 추정이나 hard budget guardrail을 설계할 때는 위 항목을 운영진에 확인한다.

### 4.2 영상 입력에서 아직 확인할 것

대신고 Search/Fine처럼 영상을 provider에 전달하는 경로는 **모델 선택 전에는 전역 계약으로 확정하지 않는다.**

선택 모델마다 최소 다음을 확인한다.

~~~text
video 입력 지원 여부
전달 방식 (inline/base64, URL, file upload 등)
허용 container / codec
한 요청 최대 파일 크기
최대 영상 길이 또는 sampling 정책
context/token 환산 방식
request timeout
동시 호출 / rate limit
실패 시 과금 기준
provider 측 payload 보관·삭제 정책
~~~

이 값들은 Runtime provider adapter, timeout/retry, memory overhead, capacity smoke의 직접 입력이 된다.

## 5. 이 문서로 닫히는 것 / 닫히지 않는 것

### 외부 제약으로 확정

~~~text
2단계에서는 Serverless 모델만 사용
Dedicated 사용 불가
Serverless 안에서는 별도 모델 제한 없음
팀 크레딧 한도 = ₩120,000
팀원 사용량 합산
한도 초과 시 공지상 API Key 자동 삭제
매월 29일 자정 이후 한도 초기화
현재 참가자 직접 사용량 조회 불가
~~~

### 아직 Runtime/Ops 결정 또는 추가 확인이 필요한 것

~~~text
실제 사용할 provider / model
모델별 Base URL / endpoint / request schema
video 전달 방식
timeout
retry/backoff
rate limit / concurrency
codec / container
provider usage SSOT
KRW 환산 정책
payload retention / logging / delete
예산 초과 시 복구 절차
~~~

## 6. 공식 참고 자료

- [Elice AI Cloud — Serverless 방식으로 모델 사용하기](https://help.elice.io/help/docs/elicecloud/ml-api/serverless)
- [Elice AI Cloud — 모델 라이브러리](https://help.elice.io/help/docs/elicecloud/ml-api/model-library)
- [Elice AI Cloud — API Key 관리하기](https://help.elice.io/help/docs/elicecloud/ml-api/api-key)
- [Elice AI Cloud — API 요청](https://help.elice.io/help/docs/elicecloud/ml-api/api)
- [Elice ML API 제품 소개](https://elice.io/ko/cloud/mlapi)
- [Elice 공개 Model Library 예시 — Gemini 3.6 Flash](https://elice.io/en/ax/model-library/76ff490d-7908-4a0c-a6fb-7b65be0b6d7a)

카테캠 2단계 과정 고유 조건(사용 가능 mode, 팀 크레딧, 초기화, 사용량 조회 제한)은 위 일반 제품 문서보다 **카테캠 운영 공지를 우선**한다.
