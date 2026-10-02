# 카테캠 2단계 ML API 환경

**Status:** Input — 카테캠 2단계 운영 공지 요약 + 엘리스 공식 문서 확인 + 조직 Model Library 관측\
**Source:** 카테캠 운영진 2단계 MLAPI 지원 공지(비공개) + 엘리스 AI Cloud 공식 문서 + 조직 Model Library 화면 + 1단계 ML API 사용 가이드(과거 기준 참고)\
**Notice date:** 확인 필요  
**Captured:** 2026-10-02  
**Maintainer:** common/runtime — 김준영  
**Router:** [Official Inputs](./README.md)

> 카테캠 공지 원문과 내부 포털 URL은 공개 레포에 싣지 않는다. §1은 2단계 최신 운영 공지를 사실만 요약했고, §2–§4는 엘리스 공식 공개 문서와 날짜를 명시한 조직 Model Library 관측을 구분해 재서술했다. 1단계 가이드는 과거 사용 방식 확인에만 사용하며, **2단계와 충돌하는 모델 제한은 2단계 공지를 우선**한다.
>
> 이 문서는 외부 입력이며 결정이 아니다. 실제 provider/model 선택, retry/timeout, concurrency, 비용 guardrail 등 Runtime/Ops 결정은 별도 Spec/Decision에서 이 문서를 근거로 정한다.
>
> 본문은 운영진 공지·플랫폼 공식 문서·Model Library 관측을 다룬다. 대신고의 실제 proxy 호출 실험은 **§7 Related internal evidence의 링크로만 연결**하며, 실측값을 이 문서의 공식 조건으로 합치지 않는다. Search 실험은 Search 원문, Runtime 교차 실험은 Runtime experiments, 계약·결정은 각 Contract/Spec/Decision이 소유한다.

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
- API Key는 공개 저장소에 남기지 않는다. endpoint/model 정보는 모델 상세를 기준으로 확인한다.

## 2. 엘리스 Serverless의 공식 동작

엘리스 공식 문서에서 Serverless는 별도 인스턴스 생성이나 서버 설정 없이 사전 준비된 endpoint를 호출하는 방식이다.

- 모델 라이브러리에서 **Serverless 지원 모델**을 선택한다.
- 모델 상세에서 API 호출 정보와 가격, 사용 예시를 확인한다.
- Serverless API Key를 포함해 호출한다.
- 과금은 호출/사용량 기반이며 모델 유형에 따라 단위가 다를 수 있다.
- 일반 엘리스 환경의 Serverless 이용 현황에서는 총 이용 금액, 기간별 호출량과 Token / Seconds(Audio) / Megapixels(Image) / Pages(Document) 등을 확인할 수 있다.

단, 마지막 항목은 **일반 엘리스 제품 기능**이다. 카테캠 2단계에서는 현재 참가자가 사용 내역을 직접 볼 수 없다는 과정 고유 공지가 있으므로, 팀 운영에서는 카테캠 제한을 우선한다.

또한 모델 라이브러리는 공개 모델뿐 아니라 **기관 전용 모델**도 가질 수 있다. 따라서 2단계에서 실제 선택 가능한 모델 집합은 문서에 고정 목록으로 복사하지 않고, 선택 시점에 카테캠 조직의 모델 라이브러리에서 Serverless 표시를 확인한다.

### 2.1 2026-10-02 조직 Model Library snapshot

카테캠 조직에서 **공개 + 추천 + Serverless** 필터로 조회한 결과는 21개였다. 이는 해당 날짜와 필터의 관측이며, 추천 제외 모델이나 기관 전용 모델까지 포함한 전체 목록 또는 영구적인 지원 목록이 아니다. **실제 사용 모델 집합은 선택 시점의 조직 Model Library에서 다시 확인한다.**

로컬 evidence의 `manifest.json` → `models.json` → `report.md` 순서로 확인한 수집 규모는 21개 모델, 391개 수집 화면, 881행 version history다. 모델별 endpoint, modality, context, 표시 가격 및 일부 parameter/reasoning/usage 설명을 확인했다. 원본은 `.codex-scratch/elice-serverless-2026-10-02/`에만 보존하며 Git에는 포함하지 않는다. **이번 Model Library 수집에서 실제 API inference 호출과 provider 원문 정책 별도 검증은 미수행**이므로 아래 내용은 화면 관측이며 실행 호환성·정책 보장이 아니다. 기존 프로젝트의 실제 호출 evidence는 §7에서 별도로 연결한다.

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

워크플로우 §1의 조사 항목을 2026-10-02 기준 공식 자료 및 §2.1의 조직 Model Library 관측과 대조했다.

여기서 미확정은 **외부 보장값 또는 선택 시점의 provider 계약이 닫히지 않았다**는 의미다. 기존 Search 경로의 성공 사례·실측이 없다는 의미는 아니며, 재확인 시 §7의 원문을 먼저 활용한다.

| 조사 항목 | 현재 확인 상태 | 근거 / 비고 |
| --- | --- | --- |
| 지원 API | **모델별 확인** | Model Library 상세에 API/예제 제공. 일부 Serverless 모델은 OpenAI 호환 API 제공 |
| media 전달 방식 | **모델별 확인** | 입력 modality와 전달 schema가 모델별로 다름. 공개 Gemini Serverless 예시 중에는 text/image/video/file/audio 입력을 지원하고 Files API 없이 일부 파일을 message 내 base64 data URL로 전달하는 모델도 있음 |
| 최대 입력 크기 | **전역값 확인 안 됨** | 일부 모델은 context window를 공개하지만, 공통 request byte/file-size 상한은 확인한 공식 문서에서 찾지 못함 |
| timeout | **확인 필요** | Serverless 전역 timeout 보장값을 확인한 공식 문서에서 찾지 못함 |
| rate limit / concurrency | **기관 정책 확인 필요** | 수집한 21개 모두 사이드바는 API Rate Limit: 무제한. 여러 모델 본문은 기관별 정책 및 담당자 문의를 안내하므로 RPM/TPM/concurrency 무제한 계약으로 해석하지 않음 |
| 지원 codec / container | **모델별 확인 필요** | 영상 입력 가능 여부와 codec/container 허용 범위를 전역 정책으로 확인하지 못함 |
| 비용 | **모델별 가격 + 팀 ₩120,000 상한** | Serverless는 사용량 기반 과금. 모델 상세에 가격 표시. 카테캠은 별도로 팀 크레딧 한도 적용 |
| retention / logging / delete | **모델별 payload 정책 확인 필요** | Claude Fable 5 개요에 보존 조건 명시(§4.3). 대부분 다른 모델은 수집 범위에서 명시값 없음. 호출/비용/사용량 추적은 payload 보관·삭제 정책과 구분 |

### 4.1 비용에서 아직 확인할 것

카테캠 공지는 팀 예산을 원화 ₩120,000 크레딧으로 제시한다. 이번 조직 Model Library 수집에서는 사이드바에 원화 가격이 표시되고 일부 개요에는 달러 가격 설명도 있었다. 표시 가격만으로 팀 크레딧의 환산·정산 기준을 확정하지 않는다.

현재 공지만으로는 다음을 확정할 수 없다.

- 원화 크레딧과 모델 표시 가격 사이의 환산 기준
- 환율 적용 시점
- VAT 포함 여부
- 소수점/반올림 방식
- 실패·재시도 요청의 과금 기준
- 예산 초과 시 자동 삭제되는 Key의 범위(특정 Key / 팀의 모든 Serverless Key)
- 초과 후 재발급 가능 여부와 복구 절차
- 매월 29일 자정의 기준 timezone

비용 추정이나 hard budget guardrail을 설계할 때는 위 항목을 운영진에 확인한다.

### 4.2 영상 입력에서 아직 확인할 것

대신고 Search/Fine처럼 영상을 provider에 전달하는 경로는 **모델 선택 전에는 전역 계약으로 확정하지 않는다.**

이번 수집 페이지에서 `video` input modality가 명시된 후보는 Gemini 3.8 Flash, Gemini 3.5 Flash Lite, Gemini 3.1 Pro, GLM 5.3 Flash다. 이는 후보 확인이며 모델 추천이나 선택 결정이 아니다. **video modality 지원 확인 ≠ 대신고 MP4 전달 계약 확인**이다. 이미지·파일 전달 예제를 실제 video payload schema로 대체 해석하지 않는다.

선택 모델마다 최소 다음을 확인한다.

~~~text
video 입력 지원 여부
전달 방식 (inline/base64, URL, file upload 등)
허용 container / codec
한 요청 최대 파일 크기
최대 영상 길이 / sampling 정책
context/token 환산 방식
request timeout
concurrency / RPM / TPM
실패 시 과금 기준
provider 측 payload retention / logging / delete 정책
~~~

이번 수집만으로 실제 video payload schema, file-size/duration/sampling, codec/container, timeout 및 구체 운영 한도를 확정하지 못했다. 이 값들은 Runtime provider adapter, timeout/retry, memory overhead, capacity smoke의 직접 입력이며, **사용 모델 선정과 API smoke test 이후** adapter 계약을 확정한다.

### 4.3 Serverless 모델 조사에서 확인된 공통 경계

- **미기재 — 수집한 모델 페이지에서 명시적 값 없음**을 뜻한다. file-size, media duration/page/resolution, timeout, RPM/TPM, concurrency, codec/container, retention/logging/delete의 미기재를 **제한 없음** 또는 **지원하지 않음**으로 해석하지 않는다. context window의 토큰 수 역시 파일 byte 상한이 아니다.
- 사이드바의 **무제한**과 본문의 기관별 정책 안내는 구체 운영 한도를 닫지 못한다. RPM/TPM/concurrency는 담당자 문의 또는 실측 대상이다.
- **Claude Fable 5**의 KTC/Elice 개요에는 30일 데이터 보존이 필수이며 ZDR 조직에서는 사용할 수 없다는 조건이 명시되어 있다. 다른 모델이나 Elice Serverless 전체 정책으로 일반화하지 않는다. 대부분 다른 모델의 payload retention/logging/delete는 이번 수집 범위에서 명시값을 찾지 못했다.
- **cache TTL과 payload retention은 별개**다. 캐시 유효 시간이나 캐시 가격 설명으로 prompt/media 보존·삭제 정책을 추론하지 않는다.

### 4.4 Known documentation inconsistencies

Model Library의 개요·예제·API schema·가격 표시가 항상 완전히 일치하지는 않았다. 아래는 수집 화면 사이의 차이이며, 실제 동작이나 어느 표기가 맞는지 확정한 결과가 아니다.

| 대표 사례 | 관측된 차이 / Runtime 확인 대상 |
| --- | --- |
| Claude Fable 5.1 | cache read 비용 설명이 개요·사이드바·공통 설명 사이에서 일치하지 않음. 실제 과금 확인 필요 |
| Gemini image 계열 | 본문은 `POST /v1/files` 지원을 언급하지만 API spec path 목록에는 없는 사례. 업로드 호환성 확인 필요 |
| Helpy Table Vision | 본문은 OpenAI 호환 Chat Completions API를 안내하지만 API spec은 `/v1/render`. 실제 endpoint/schema 확인 필요 |
| Helpy Document Vision | 상태 조회 표는 `GET /jobs/{job_id}`, 예제는 `GET /v1/jobs/{job_id}`이며 인증 여부도 다름. path/auth 확인 필요 |

실제 채택 모델은 다음 순서로 Runtime contract를 확정한다.

1. 모델 상세의 표시 문서와 예제를 확인한다.
2. API schema의 path, 인증, parameter, 응답을 대조한다.
3. 선정 모델에 최소 API smoke call을 수행한다.
4. usage / error / timeout을 관찰하고 계약과 미확정 항목을 기록한다.

화면상의 지원 표기만으로 endpoint compatibility나 운영 한도가 검증됐다고 처리하지 않는다.

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

### Model Library 관측으로 확인된 것

- 2026-10-02 공개·추천·Serverless 필터 21개와 모델별 endpoint/modality/context/표시 가격 일부
- video modality 후보 및 일부 parameter/reasoning/usage 설명
- Claude Fable 5의 보존 정책 특이사항과 문서 화면 간 불일치 존재

이는 외부 입력 확보이며 provider/model 채택이나 실제 API 동작 검증은 아니다.

### 아직 Runtime/Ops 결정 또는 추가 확인이 필요한 것

~~~text
실제 사용할 provider / model
모델별 Base URL / endpoint / request schema 및 실제 호환성
video payload 전달 방식 / file-size / duration / sampling
timeout
retry/backoff
RPM / TPM / concurrency
codec / container
실패·재시도 시 과금
팀 usage 확인 방법 / provider usage SSOT
₩120,000 크레딧의 환산·정산 기준
payload retention / logging / delete
예산 초과 시 복구 절차
~~~

미확정 외부 정책은 **운영진 문의**, 모델별 호환성과 과금 관측은 **선정 모델 API smoke**, 실제 부하·경로 검증은 **Runtime capacity / Real E2E**로 닫는다. 이 문서나 workflow에는 모델 선택 및 timeout/retry 숫자를 결정값으로 넣지 않는다.

## 6. 공식 참고 자료

- [Elice AI Cloud — Serverless 방식으로 모델 사용하기](https://help.elice.io/help/docs/elicecloud/ml-api/serverless)
- [Elice AI Cloud — 모델 라이브러리](https://help.elice.io/help/docs/elicecloud/ml-api/model-library)
- [Elice AI Cloud — API Key 관리하기](https://help.elice.io/help/docs/elicecloud/ml-api/api-key)
- [Elice AI Cloud — API 요청](https://help.elice.io/help/docs/elicecloud/ml-api/api)
- [Elice ML API 제품 소개](https://elice.io/ko/cloud/mlapi)
- [Elice 공개 Model Library 예시 — Gemini 3.6 Flash](https://elice.io/en/ax/model-library/76ff490d-7908-4a0c-a6fb-7b65be0b6d7a)

카테캠 2단계 과정 고유 조건(사용 가능 mode, 팀 크레딧, 초기화, 사용량 조회 제한)은 위 일반 제품 문서보다 **카테캠 운영 공지를 우선**한다.

## 7. Related internal evidence — 공식 외부 조건과 분리

아래는 대신고에서 수행한 migration·실험·후속 설계의 탐색 경로다. **실측 수치·실험 표·모델 추천은 재생산하지 않는다.** 특정 model, proxy path, date, calling mode, experiment scope의 관측이며 Elice Serverless 전체의 공식 보장이 아니다. 내부 endpoint URL이나 인증정보 대신 모델명과 API path로 범위를 식별한다.

### 7.1 Search migration / experiment / decision

- [Issue #95 — migration tracker와 D3, P0/P1 결과](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95), [PR #128 — Real E2E proxy 전환](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/128): 2026-09-20~21의 `gemini-3.8-flash` / KTC Elice OpenAI-compatible `/v1/chat/completions` 호출·media probe 범위. Files API/file_uri 재사용, provider offset/fps, thinking_budget 전제의 변경은 이 프로젝트 migration 기록에서 확인하며 플랫폼 전 모델의 제약으로 승격하지 않는다.

아래 Flash 실험은 해당 날짜의 `gemini-3.8-flash` / KTC Elice OpenAI-compatible `/v1/chat/completions` 경로 기준이다. 호출 mode와 표본은 각 원문을 따른다.

| 상세 원문 | 날짜 · 호출 mode · 실험 범위 / 재사용 목적 |
| --- | --- |
| [Video sampling probe](../../modules/search/experiments/gemini-proxy-video-sampling-2026-09-28.md) | 2026-09-28 · `type:file` base64 inline(streaming 여부 원문 미명시) · 단일 원본 구간의 로컬 fps/해상도와 요청 parameter 비교 |
| [Image frame probe](../../modules/search/experiments/gemini-image-frame-probe-2026-09-28.md) | 2026-09-28 · non-streaming `image_url` · 같은 원본 구간의 해상도/detail/장수 비교, video와의 token·payload tradeoff |
| [Slowdown token probe](../../modules/search/experiments/gemini-video-slowdown-token-probe-2026-09-29.md) | 2026-09-29 · non-streaming inline video · 단일 구간의 배속/재생 길이 비교. Search transport workaround이며 공식 sampling 기능이 아님 |
| [Inline request-size probe](../../modules/search/experiments/gemini-proxy-size-probe-2026-10-01.md) | 2026-10-01 · non-streaming inline video · 고정 길이·크기별 단회 호출. 성공 범위와 latency 관측이며 provider hard limit 확정이 아님 |
| [Reasoning-effort experiment](../../modules/search/experiments/gemini-reasoning-effort-2026-10-01.md) | 2026-10-01 · 운영 low non-streaming과 실험 medium/high streaming의 호출 차이 명시 · Coarse→Fine 표본 비교, 출력 절단·usage 관측 |
| [Search final structure](../../modules/search/decisions/search-final-structure-2026-10-01.md), [운영 경로 검증](../../modules/search/experiments/search-v3-production-verify-2026-10-01.md), [PR #219](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/219) | 2026-10-01 · `GeminiProvider` non-streaming · v3 transport·시각 환산의 채택 근거와 운영 경로 표본 검증. Search 선택이며 Runtime 공통 상수가 아님 |
| [지연 baseline](../../modules/search/experiments/latency-baseline-2026-09-28.md), [Issue #72](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/72), [PR #182](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/182) | 2026-09-28 · 운영 non-streaming inline · 로컬 Windows의 길이·동시 발주 실험. provider latency와 전처리 포함 wall을 분리하며 EC2 capacity/rate limit으로 일반화하지 않음 |

후속 [PR #231 — 모델별 경로 비교](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/231)와 [PR #237 — sol 이미지 Fine 조건 분리](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/237)는 2026-10-02 별도 모델 endpoint/transport의 실험이다. Flash probe의 이미지 처리·video 지원 관측을 Pro/GPT 경로에 그대로 적용하지 않는다. 세부 범위와 호출 mode는 각 PR의 Search experiment 원문으로 이동하며, 이 문서에서 최종 provider/model을 선택하지 않는다.

### 7.2 Runtime / UsageRecord / security로 이동

- [Issue #153 — usage·pricing·config ownership 조사와 후속 합의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153): provider 의미와 config validation은 Search adapter, config/secret 주입과 Final UsageRecord persistence는 Runtime 경계다. 가격표 숫자의 공용 SSOT는 별도 요구가 생길 때 공동 검토하며, 이 문서가 catalog 위치/schema를 정하지 않는다.
- [UsageRecord Contract](../../architecture/contracts/contract-usage-record.md), [Runtime Tech Spec](../runtime-tech-spec.md) §11·§15: Final 원장 계약과 실행 시 usage/cost/pricing context 보존·주입 경계. #95 D3와 이후 reasoning 실험은 시점·호출 mode별 usage shape 관측이 다르므로 reasoning-specific field를 stable provider contract로 가정하지 않는다. Final 계약은 유지하며 실제 adapter normalization은 선정 모델/호출 경로 smoke에서 재확인한다. 가격표 소유 표현의 기존 정합화 후속은 #153으로 연결하고 여기서 Final Contract를 개정하지 않는다.
- [PR #154 — Runtime input 승격 경계](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/154), [Runtime Experiments](../experiments/README.md), [P2 capacity smoke plan](../experiments/elice-runtime-capacity-smoke-plan.md), [Ops Spec](../ops-spec.md) §12·§16: inline request working set, ffmpeg/host 자원, cleanup/restart/reuse는 기존 P2에서 검증한다. Search probe 성공을 P2 완료나 Runtime baseline 보장으로 처리하지 않는다.
- [Pre-deploy security review](../../management/pre-deploy-security-review.md) §1·§3: `RemoteCopy` 미사용과 provider payload retention은 별개다. inline request logging/retention 확인은 기존 검수 경로를 따른다.

기존 모듈 실측을 먼저 읽고 **현재 선택 모델·endpoint·호출 mode와 달라진 부분**을 smoke로 재확인한 뒤, Runtime 교차 실험 결과가 실제 운영 선택을 바꿀 때만 Tech/Ops Spec 또는 Decision/ADR로 승격한다.
