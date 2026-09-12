# [search] Gemini baseline 자료조사 (원자료)

> **성격:** Owner(서어진)가 `search` 모듈용으로 진행한 **기술 자료조사 원문**이다. 조사 결과이지 결정이 아니다. 이 문서를 요약·가공한 것이 같은 폴더의 [`architecture-input-memo.md`](./architecture-input-memo.md)이고, 결정은 v4(`docs/architecture/module-architecture.md`)와 이 모듈의 `decisions/`에서만 한다.
> **조사일:** 2026-08-27 (요율·API 사실은 이 시점 스냅샷).
> **Source of Truth:** 서비스 기획안 1.3 + 모듈 구조 설계 v3.
> **교차확인:** 팩트 항목(1·2·3)은 공식문서(ai.google.dev) + SDK 교차확인. 설계 항목(4·5·6)은 1.3/아키텍처 기반 초안.
> **기존 자산:** `eval.py`(coarse recall/지연/비용), `COST.md`(방법별 비용), `labels.example.jsonl`.
>
> 출처 링크 전체는 문서 맨 아래 [출처](#출처) 절에 모았다.

담당: 어진 (`search` 모듈).

> **문서 내 수치 불일치 주의:** 프레임당 토큰이 페이지별로 258 vs 263/sec, low 66 vs 70이 엇갈림.
> 원가 계산은 보수적으로 **default ~300 tok/s, low ~100 tok/s** 사용.

---

## 1. Gemini에 긴 영상을 넣는 방법

| 항목 | 사실 | eval.py 대조 |
| --- | --- | --- |
| 입력 방식 | inline(base64, 요청 전체 **<100MB**) vs **Files API 업로드(파일당 2GB, 프로젝트 20GB)** | ✅ 이미 Files API 사용 |
| 긴 영상 | 1~2시간은 **무조건 Files API** (inline은 base64 ~33% 팽창로 100MB 즉시 초과) | ✅ |
| **파일 수명** | **업로드 후 48시간 자동 삭제.** `files.delete(name)`로 수동 삭제, `files.list()` 조회 | ⚠️ `recording.RemoteCopy.만료시각`이 이 48h에 종속 — search가 알아야 함 |
| 지원 포맷 | mp4/mov/webm/avi/mpeg/wmv/flv/mpg/3gpp (9종). mp4·mov OK | — |
| 최대 길이 | 1M 컨텍스트: **default ~1시간 / low ~3시간**. 2M 모델은 ~2시간(현 라인업 존재 여부 불확실) | — |
| 오디오 | 포함 처리, 초당 32토큰 (Files API는 1Kbps 단일채널 저장) | — |

**출처:** [video-understanding](https://ai.google.dev/gemini-api/docs/video-understanding), [files](https://ai.google.dev/gemini-api/docs/files)

20GB이상이 필요하다면 Google Cloud Storage이나 한도 증가 요청이 필요하다.

## A. 코덱 (H.265 / HEVC)

### A-0. 확인된 사실

- Gemini 공식 문서는 **컨테이너 MIME 타입만 명시**한다 (`video/mp4`, `video/mov`, `video/webm`, `video/avi`, `video/mpeg`, `video/wmv`, `video/flv`, `video/mpg`, `video/3gpp`).
- **컨테이너 안의 코덱(H.264 / H.265 / MJPEG 등)에 대한 명시가 없다.** 웹 검색으로도 코덱 목록을 찾지 못했다 = 문서에 존재하지 않는다.
- 즉 `.mp4` 지원 ≠ `.mp4에 담긴 H.265` 지원. **이건 서로 다른 층위다.**

### A-1. 왜 지금 문제인가

| 걸리는 곳 | 내용 |
| --- | --- |
| **N14 (비기능 요구)** | 테크스펙이 **"H.265 / 1시간 이상 영상 E2E 동작"**을 요구사항으로 명시 |
| **최근 블랙박스 현황** | 저장 효율 때문에 HEVC 채택이 늘어남 → 실제 사용자 파일이 H.265일 가능성이 낮지 않음 |
| **§3 분할 전략** | SentrySearch 차용값이 `ffmpeg -c copy`(재인코딩 없이 자르기) 전제. **`-c copy`는 코덱을 그대로 둔다 → H.265 원본을 잘라도 결과물은 H.265** |

즉 Gemini가 HEVC를 못 받으면 **§3의 "재인코딩 없이 자른다"는 이점이 통째로 사라진다.**

### A-2. 실측 항목 (담당: 어진 / 샘플 제공: 정철원)

- [ ]  H.265(hevc) mp4 파일을 **그대로 Files API에 업로드 → generate_content 호출**이 성공하는가
- [ ]  실패한다면 어느 단계에서 실패하는가 — 업로드 거부 / 업로드는 되나 추론 실패 / 조용히 빈 응답
- [ ]  실패 시 에러 메시지에 코덱이 명시되는가 (실패 분류를 `INFRA`로 기록할 근거)
- [ ]  H.264 동일 내용 파일과 **토큰 수·지연·비용에 차이**가 있는가
- [ ]  블랙박스가 실제로 쓰는 컨테이너가 9종 목록 안에 다 들어가는가 (mkv / ts 등 목록 밖 포맷 사용 기종이 있는지 — 정철원 §1 실측과 연결)

### A-3. 결과별 분기

**Case 1 — HEVC 지원됨**

- `c copy` 전략 유지 가능. §3 비용 계산 그대로.
- 단, **오디오 제거(`an`)는 여전히 재먹싱이 필요**하다. `c copy -an`은 재인코딩 없이 가능하므로 문제 없음.

**Case 2 — HEVC 미지원**

- proxy 생성이 **재인코딩 필수**가 된다 → 다음이 전부 바뀐다.
    - [ ]  1시간 영상 트랜스코딩 **소요 시간**은? (사용자 대기 시간에 직접 추가됨 — N6/N7 백그라운드 정책과 연결)
    - [ ]  트랜스코딩 **CPU 비용**은? (§2 원가식에 없는 항목 — 현재 `source-video-hour당 원가`는 API 비용 중심)
    - [ ]  재인코딩 화질 손실이 **coarse 탐색 성능**에 영향을 주는가
- 재인코딩이 어차피 필요하다면 **저해상도·무음 proxy를 한 번에 만드는 것이 오히려 효율적**일 수 있다 → 업로드 전략 (c)안에 유리하게 작용.

### A-4. 파생 의문 — proxy와 원본의 용도 분리

재인코딩된 저화질 proxy는 **coarse 탐색 전용**이어야 한다. 다음이 아직 명확하지 않다.

- [ ]  Fine 검증도 proxy로 하는가, 원본 구간을 다시 뽑는가 (선 종류·신호색 판별에 화질이 영향)
- [ ]  `readout`(번호판·화면시각 OCR)은 **반드시 원본**이어야 한다고 보는데, 계약상 그 구분이 어디에 표시되는가
- [ ]  `recording.prepare_analysis_source(time_range, profile)`의 `profile` 태그 체계를 누가 정의하는가 (예: `coarse-low-noaudio` / `fine-native` / `readout-native`)

> **경계 주의:** profile 문자열은 `recording`이 해석하지만, **어떤 profile이 필요한지 아는 것은 `search`/`readout`**이다. 이 태그 체계는 두 모듈이 합의해야 하는 최소 계약이다.

---

## B. 영상 수명 (Files API 48시간)

### B-0. 확인된 사실

- Files API 업로드 파일은 **48시간 후 자동 삭제**된다.
- `files.delete(name)`로 수동 삭제, `files.list()`로 조회 가능.
- 파일당 2GB, 프로젝트당 20GB 한도.

### B-1. 의문점 1 — 소유권 방향이 뒤집혀 있다

리포트 표기:

> ⚠️ `recording.RemoteCopy.만료시각`이 이 48h에 종속 — **search가 알아야 함**

**모듈 구조상 반대다.**

- `RemoteCopy`는 **`recording` 소유** 계약이고, 만료 시각을 세팅하는 것도 `prepare_remote_copy(source_ref, provider_tag)`다.
- `search`가 provider의 파일 수명 정책을 아는 것은 **경계 침범**이다. `search`는 "분석용 소스 참조"를 받을 뿐 그게 어디에 얼마나 사는지 몰라야 한다.

**조치:** 이 항목은 "search가 알아야 함"이 아니라 **"recording에 전달할 제약"**으로 재분류한다.
→ 정철원에게: `RemoteCopy.expires_at ≤ upload_time + 48h`로 강제할 것.

### B-2. 의문점 2 — 만료 후 재업로드를 누가 트리거하는가 (미정의)

```
사용자가 후보를 받음
  → 이틀 뒤 접속해서 "다른 후보 보기" 또는 "조금 전으로 다시 찾기"
  → Files API 파일은 이미 자동 삭제됨
  → search 호출 실패
  → ??? 누가 재업로드를 발주하는가
```

- [ ]  실패를 `failure_kind = INFRA`로 잡고 `case`가 재발주하는 흐름이 맞는가
- [ ]  그렇다면 `case`가 "이건 재업로드가 필요한 실패"임을 어떻게 아는가 (INFRA는 너무 뭉뚱그려진 분류)
- [ ]  **부분 재실행 표에 이 케이스가 없다** — 사용자 입장에선 "어제는 즉시 나왔는데 오늘은 몇 분 걸림"이 된다. 재업로드 비용도 다시 발생
- [ ]  애초에 **case의 유효기간을 48h 이내로 제한**하는 선택지도 있다 (그 뒤에는 "다시 시작하기"만 제공). 이게 더 단순할 수 있음

> **담당:** 실패 분류 세분화는 어진(`search`), 재실행 정책은 유소연(`case`). **두 사람이 같이 정해야 하는 항목.**

### B-3. 의문점 3 — 우리 보관정책(N12)과의 정합성

- [ ]  우리 `RemoteCopy` TTL을 48h보다 **짧게** 잡을 것인가 (권장 — 우리가 먼저 지운다)
- [ ]  48h보다 길게 잡을 경우, `purge_case()`가 **이미 Google이 지운 파일**을 삭제 시도할 때의 동작은? → **에러가 아니라 정상(idempotent)으로 처리**해야 하며, `DeletionReport`에 "이미 없음"을 구분 기록할지 결정 필요
- [ ]  `files.list()`로 **고아 파일**(우리 DB에는 없는데 provider에 남은 것)을 주기적으로 점검할 것인가 — 개인정보 관점에서 필요할 수 있음

### B-4. 긍정적 측면 — 48h는 안전망이기도 하다

리포트가 경고(⚠️)로만 표기했는데, **개인정보 설계에서는 유리한 사실**이다.

- 우리가 삭제 로직을 실수로 빠뜨려도 **provider가 48h에 자동 파기**한다.
- N12(흩어진 4곳 동시 삭제)의 백스톱이 하나 생기는 셈.
- 보안 체크리스트의 "외부 AI API 전송 영상범위·보관" 항목에 **"provider 자동 파기 48h"를 근거로 기재 가능**.

→ 문서에 이 측면을 같이 적어두면 C-2(보안 coordinator) 안건에서 그대로 쓸 수 있다.

### B-5. 파생 의문 — 48h 내 재사용을 적극 활용할 것인가

- [ ]  같은 case에서 Coarse 1회 + Fine K회를 돌릴 때, **업로드 1회를 재사용**하는가 (§3의 "1회 업로드 → offset만 바꿔 재요청"과 연결)
- [ ]  그렇다면 업로드 참조를 어디에 캐싱하고, `JobRecord.input_fingerprint`와 어떻게 연동하는가
- [ ]  Context caching(§2-2)과는 별개 개념임을 문서에 명시할 것 — **파일 수명 48h ≠ 컨텍스트 캐시 수명**

---

## 2. 비용·지연 실측 설계1

### 2-1. 토큰화 (1 FPS 기본 샘플링)

| media_resolution | 프레임당 | 오디오 | 합계 |
| --- | --- | --- | --- |
| default | 258 tok/frame | 32 tok/s | **~300 tok/s** |
| low | 66 tok/frame | 32 tok/s | **~100 tok/s** |

- FPS 조절: `videoMetadata.fps`, 기본 1.0, 범위 **(0, 24]**. 긴 영상은 fps<1(예 0.2~0.5)로 추가 절감.
- Gemini 3 계열은 프레임당 값이 low=70일 수 있음(불확실).

**★ 오디오 제거 = low에서 ~1/3 절감.** 오디오는 해상도 무관 **32 tok/s 고정** → 비디오 토큰이 작을수록 비중↑:

| 해상도 | video | +audio | 오디오 비중 | 제거 시 |
| --- | --- | --- | --- | --- |
| **low** | 66/s | 98/s | **~33%** | 66/s (**약 1/3↓**) |
| default | 258/s | 290/s | ~11% | 258/s |

- 4종(신호·중앙선·진로변경·안전모)은 **전부 순수 시각 이벤트**라 오디오 불필요. 화면 시각·속도도 overlay OCR(`readout`) 담당 → **버려도 정보 손실 0.**
- 제거 방법: API에 옵션 없음 → **업로드 전 `ffmpeg -an`으로 무음 프록시.** `recording.prepare_analysis_source(profile="no-audio")`로 요청, 스트립은 `recording`이 수행(search↔recording 경계 유지).
- **실측 검증:** `prompt_tokens_details`의 AUDIO 모달리티가 무음 파일에서 0으로 떨어지는지 A/B로 확인 후 절감폭 확정.

### 2-2. 요금 (USD/1M, 2026-08-27) — >200k 티어는 Pro만 존재

> ⚠️ **표 일부 손상:** 이 표는 Notion→텍스트 반출 과정에서 3.7 Flash·2.5 Pro·3.1 Pro 행의 입력·출력 셀 일부가 깨졌다(`1.50)`, `2.50 | 15`, `4.00 | 18`). 아래는 반출된 그대로이며, **정확한 2026-08-27 스냅샷 값은 원본 Notion PDF에서 복구하거나 [pricing](https://ai.google.dev/gemini-api/docs/pricing) 페이지로 재확인해야 한다.** 2.5 Flash-Lite / 2.5 Flash 행은 온전하다.

| 모델 | 입력(≤200k / >200k) | 출력 |
| --- | --- | --- |
| 2.5 Flash-Lite | **$0.10** (video) | $0.40 |
| 2.5 Flash | $0.30 (video) | $2.50 |
| 3.7 Flash | 1.50) ⚠️ | $3.75 |
| 2.5 Pro | 2.50 ⚠️ | 15 ⚠️ |
| 3.1 Pro (preview) | 4.00 ⚠️ | 18 ⚠️ |

- **Batch API: 전 모델 입출력 50% 할인**(비동기, target 24h·보장 없음). 공식 문서가 "non-urgent tasks such as running evaluations"용으로 명시 → **제품 런타임 ✗(실시간 UX 불가), `eval` 오프라인 채점에서만 ✓.** (출처: [batch-api](https://ai.google.dev/gemini-api/docs/batch-api))
- **Context caching:** 긴 영상 반복 질의 시 캐시 read(일반 입력의 1/10~1/4) + 저장비(시간당). 짧은 시간 다회 질의면 이득, 오래 유지하면 저장비가 잠식.

### 2-3. 지연 측정 & usage 필드 (⚠️ 두 API 계열로 필드명 다름)

- 지연 = `time.perf_counter()` 요청→응답 wall-clock. 스트리밍이면 TTFT 별도.
- **구형 generateContent** → `usage_metadata`: `prompt_token_count`, `candidates_token_count`, `total_token_count`, `cached_content_token_count`, `thoughts_token_count`, `prompt_tokens_details`(모달리티별 VIDEO/AUDIO 분리)
- **신형 Interactions** → `usage`: `total_input_tokens`, `total_output_tokens`, `total_cached_tokens`, `total_tokens`
- 사전 산정: `client.models.count_tokens(...)`

### 2-4. `AnalysisRun.cost` 확정 필드 (★=원가 재계산 필수)

```
★ model_tag           요율 매칭 키 (예 "gemini-2.5-flash")
★ tokens_in           prompt_token_count / total_input_tokens
★ tokens_out          candidates_token_count / total_output_tokens
  total_tokens        검증용
  cached_tokens       캐시 절감 추적
  thoughts_tokens     thinking 비용 별도
  tokens_in_video     prompt_tokens_details의 VIDEO — 원가 귀속
  tokens_in_audio     오디오 요율 다름(Flash audio $1.00)
★ video_duration_sec  "시간당 원가" 정규화 분모
★ media_resolution    low/default (토큰 산정 근거)
  fps_used            커스텀 샘플링 기록
★ price_in_per_1m     실행 시점 입력 요율 스냅샷 (요율 변동·티어·시점 대비)
  price_out_per_1m    출력 요율 스냅샷
  is_batch            배치 50% 할인 플래그
★ price_usd           계산된 실제 청구액
★ latency_sec         wall-clock
  ttft_sec            스트리밍 첫 청크
  model_version       response.model_version
```

> **왜 스냅샷:** 요율이 (a)200k 티어 (b)모달리티 (c)배치 (d)캐시 (e)시점(3.x Flash는 2027-01-01 인상)으로 갈림. 실행 시점 요율을 값으로 박아두지 않으면 요율표 바뀐 뒤 과거 결과를 못 믿는다.

**eval.py 갱신점:** 현재 `prompt_token_count`만 기록 → 위 ★ 필드로 확장. `PRICE_PER_1M` 모델명 실호출 가능 여부 확인.

### 2-5. 1시간 영상 원가 (입력만, 실시간)

| 시나리오 | 모델 | 토큰 | 비용 |
| --- | --- | --- | --- |
| low ~0.36M | Flash-Lite | 0.36M | **~$0.036** ← 제품 런타임 |
| low + Batch | Flash-Lite | 0.36M | ~$0.018 (eval 채점 한정) |
| default ~1.08M | Flash | 1.08M | ~$0.32 |
| default ~1.08M | Pro | 1.08M | ~$2.7 |

→ **제품 런타임** coarse recall은 실시간이라 **low + Flash-Lite = $0.036/시간대** (배치 불가).
→ **eval 대량 채점**은 non-urgent라 **+ Batch로 절반($0.018)**. (default 1.08M은 1M 한도 경계라 low 권장)

**출처:** [pricing](https://ai.google.dev/gemini-api/docs/pricing), [tokens](https://ai.google.dev/gemini-api/docs/tokens), [caching](https://ai.google.dev/gemini-api/docs/caching), context7 python-genai v1.33

---

## 3. 구간 분할 전략 후보

**핵심 무기 — clipping:** `videoMetadata.startOffset`/`endOffset`(문자열 `"1250s"` 형식).
**1회 업로드 → 후보 구간별 offset만 바꿔 재요청(재업로드 불필요).** 단 일부 SDK 버전 미지원 보고 있음 → 실측 검증 필요.

| 전략 | 방법 | 트레이드오프 |
| --- | --- | --- |
| A. 통 스캔 | 1시간을 한 요청에 (현 eval.py) | 단순. low로 1M 한도 내. 단 긴 영상 recall 저하·offset 정밀도↓ 가능 |
| B. 고정 분할 | N분 청크로 잘라 각각 요청 | 청크당 컨텍스트 작아 recall↑. 요청 수↑=지연↑(Batch로 흡수) |
| C. 겹침 분할 | 청크 경계에 겹침(overlap) 구간 | **경계에 걸친 사건 놓침 방지**(1.3 TC6). 겹침만큼 토큰 중복 |
| ↳ 참조 | **SentrySearch 실측값: 30초 청크 / 5초 오버랩 / step 25초** | ffmpeg `-c copy`(재인코딩無)로 자름. 겹침 dedup은 인덱싱 아닌 검색시 코사인유사도만. 벡터DB 없이 이 값만 차용 가능 |
| D. 2패스 | low 통 스캔으로 후보 위치 → 후보 구간만 clipping 재분석 | 비용 최소. coarse→fine 구조와 동일 사상 |

> **실측 설계:** 같은 labels로 A~D를 돌려 **recall × 비용 × 지연**을 표로. 겹침 폭·청크 길이·병렬 개수가 노브.
> **제품 런타임 병렬은 asyncio(`client.aio`)** — Batch(24h)는 실시간 UX 불가라 제외. Batch는 eval 대량 채점 전용.
> 숨은 병목은 추론 아닌 **업로드**(1시간 ≈ 4~8GB, COST.md §숨은비용) → §11-2 업로드 전략과 직결.

---

## 4. 4종 프롬프트 구조 초안

4종은 **두 부류**다. 유형별 분기는 `search/routing` 내부 사정, 공개 인터페이스는 `AnalysisScope.target_event_types` 목록 하나(§RT6).

**4종 = 신호위반 / 중앙선 침범 / 진로변경 위반 / 안전모 미착용**

| 코드 | 한글 | 부류 |
| --- | --- | --- |
| `SIGNAL` | 신호위반 | 시간 순서형 |
| `CENTER_LINE_CROSSING` | 중앙선 침범 | 시간 순서형 |
| `LANE_CHANGE` | 진로변경 위반(백색 실선) | 시간 순서형 |
| `MOTORCYCLE_HELMET_NON_USE` | 이륜차 안전모 미착용 | **객체 속성형** |

| 부류 | 유형 | 관찰 핵심 | 프롬프트가 물을 것 |
| --- | --- | --- | --- |
| **시간 순서형** | 신호위반 / 중앙선침범 / 진로변경 | 시설·기하 + **차량 궤적의 전후 순서** | primitives(신호상태·정지선·선종류 등) + **temporal_order** |
| **객체 속성형** | 안전모 미착용 | **한 장면 안 객체 속성** | 이륜차→운전자→머리영역→안전모 present/absent |

### coarse (1차, recall 우선)

```
이 대시캠 영상에서 [target_event_types 설명]으로 의심되는 순간을 찾아라.
사용자 기억 단서: {cue}
가장 의심스러운 순서로 최대 {k}개 후보. 각 후보: start_sec, end_sec, event_type, 근거 한 줄.
확실치 않아도 근거가 조금이라도 있으면 후보로 올려라(recall 우선).
단, 아무 근거도 없는데 억지로 후보를 만들지는 마라 — 해당 사건이 없으면 빈 결과로 답하라(후보 0개는 정상이다).
안 보이는 번호판/위치/시각은 추측하지 마라. 법 조항·위반 확정은 하지 마라 — 무엇이 보이는지만.
```

### fine (2차, 구조화 관찰) — VisualEvidence 스키마 강제

```json
{
  "primitives": [{"kind":"WHITE_SOLID_LINE","present":true,"confidence":0.88}],  // 종류+유무+확신도로 일반화
  "target": {"described_as":"흰색 SUV","match_with_hint":true,"confidence":0.79,"track_ref":"..."},
  "temporal_order": [{"t":"...","fact":"..."}],   // 시간순서형만. 객체속성형은 비워도 됨
  "visual_event_type": "LANE_CHANGE",
  "uncertain": ["야간·역광으로 선 종류 일부 불확실"]
}
```

- **안전모는 temporal_order 대신 primitives(HELMET_ON_RIDER present/absent)로.** 스키마는 공유, 채우는 필드만 다름.
- 프롬프트 버전 필수 표기(`@c7`) → `AnalysisRun.impl.prompt_ver`.

### 4-A. 공통 규칙 (모든 유형·모든 프롬프트에 붙는 불변 블록)

```
너는 관찰자다. 보이는 것만 말하고, 안 보이는 것은 추측하지 마라.
- 번호판·정확한 위치·시각을 만들어내지 마라. 안 보이면 "안 보임"이다.
- **요청한 대상·항목·사건이 영상에 없으면 지어내지 말고 "없다"고 답하라.** 빈 결과(후보 0개, present=false)는 오답이 아니라 정상 결과다. 억지로 채우는 것이 가장 나쁜 답이다.
- "위반이다/도로교통법 몇 조" 같은 법적 판단은 절대 하지 마라. 무엇이 보이는지만 기술하라.
- 애매하면 confidence를 낮춰라. 없으면 present=false. 확정 대신 불확실을 표시하라.
- 출력은 지정된 JSON 스키마로만. 그 외 문장 금지.
```

### 4-B. 유형별 coarse 설명 (recall 우선 · 공통 골격의 `{event_description}`에 주입)

| 유형 | coarse `{event_description}` |
| --- | --- |
| **신호위반** | "정지신호(적색, 경우에 따라 황색) 상태에서 차량이 **정지선을 넘어 교차로에 진입/통과**하는 순간. 신호등 색과 정지선 통과가 함께 보이는 구간. (우회전 등은 확정 말고 후보로만)" |
| **중앙선 침범** | "차량이 도로 **중앙선(황색 실선 또는 황색 복선)을 넘어 반대방향 차로로 진입**하는 순간." |
| **진로변경 위반** | "**백색 실선**(진로변경 금지) 구간에서 차량이 옆 차로로 넘어가는 순간. **점선이 아니라 실선**일 때만 후보." |
| **안전모 미착용** | "**이륜차(오토바이·스쿠터)** 운전자 또는 동승자가 **안전모를 쓰지 않은** 장면. 시간 순서가 아니라 한 장면의 머리 상태." |

> coarse 공통 골격은 §4 위 `coarse (1차)` 박스 그대로. `[target_event_types 설명]` 자리에 위 문장을 넣고, 여러 유형이면 나열.

### 4-C. 유형별 fine 프롬프트 (2차 구조화 관찰 · 4-A 공통규칙 + 아래)

**신호위반 `SIGNAL`** (시간 순서형)

```
이 구간에서 신호위반 의심 차량 하나를 대상으로 아래를 관찰해 JSON으로 답하라.
primitives 후보: TRAFFIC_LIGHT_RED, TRAFFIC_LIGHT_YELLOW, TRAFFIC_LIGHT_GREEN,
                 STOP_LINE_VISIBLE, TARGET_CROSSED_STOP_LINE, TARGET_ENTERED_INTERSECTION
temporal_order: [신호등 색이 보인 시점] → [대상이 정지선에 접근] → [정지선 통과] → [교차로 진입] 순서로.
target: 위반 의심 차량을 described_as로 (색·차종). 사용자 단서와 일치하면 match_with_hint=true.
주의: 신호등 색과 "정지선 통과"가 같은 대상·같은 시간축에서 확인돼야 한다. 색만 보이고 통과가 안 보이면 통과 present=false.
```

**중앙선 침범 `CENTER_LINE_CROSSING`** (시간 순서형)

```
이 구간에서 중앙선 침범 의심 차량 하나를 대상으로 아래를 관찰해 JSON으로 답하라.
primitives 후보: CENTER_LINE_YELLOW_SOLID, CENTER_LINE_YELLOW_DOUBLE,
                 TARGET_CROSSED_CENTER_LINE, TARGET_IN_OPPOSITE_LANE
temporal_order: [대상이 자기 차로 주행] → [중앙선 접근] → [중앙선 넘음] → [반대방향 차로 진입] 순서로.
target: 대상 차량 described_as. 주의: 중앙선의 '황색' 여부와 '실선/복선'을 구분해 기술. 넘은 선이 백색이면 이 유형이 아니다.
```

**진로변경 위반 `LANE_CHANGE`** (시간 순서형)

```
이 구간에서 백색 실선 진로변경 의심 차량 하나를 대상으로 아래를 관찰해 JSON으로 답하라.
primitives 후보: WHITE_SOLID_LINE, WHITE_DASHED_LINE,
                 TARGET_CROSSED_SOLID_LINE, TARGET_ENTERED_ADJACENT_LANE
temporal_order: [대상이 원래 차로 주행] → [실선 접근] → [실선 넘음] → [인접 차로 진입 완료] 순서로.
target: 대상 차량 described_as (색·차종), 사용자 단서 일치 여부.
주의: 넘은 선이 '실선'인지 '점선'인지가 핵심. 점선이면 WHITE_DASHED_LINE=true로 기록(이 경우 위반 아님을 시사하나 판단은 하지 마라). 야간·역광으로 선 종류가 불확실하면 uncertain에 적어라.
```

**안전모 미착용 `MOTORCYCLE_HELMET_NON_USE`** (객체 속성형 — temporal_order 없음)

```
이 구간(또는 대표 프레임)에서 이륜차를 대상으로 아래를 관찰해 JSON으로 답하라.
primitives 후보: MOTORCYCLE_PRESENT, RIDER_VISIBLE, HELMET_ON_RIDER, PASSENGER_PRESENT, HELMET_ON_PASSENGER
temporal_order: 비워라(빈 배열). 이 유형은 시간 순서가 아니라 한 장면의 객체 상태다.
target: 이륜차를 described_as로.
주의: 운전자 머리 영역이 프레임에 안 잡히거나 흐리면 HELMET_ON_RIDER를 present로 확정하지 말고 confidence를 낮춰라.
이륜차 번호판은 후면·소형이라 잘 안 보이는 게 정상이다 — 안 보이면 안 보인다고만 하라.
```

> **4종 공통 fine 스키마는 §4 `fine` 박스 그대로** — primitives/target/temporal_order/visual_event_type/uncertain/legal_status(항상 null). 위는 각 유형에서 **채울 primitives 종류와 temporal 지침**만 다른 것. 스키마·골격은 하나, 델타만 넷.

---

## 5. 세 가지 프롬프트 방법 비교 실험

**무엇을 하는 실험인가:** 같은 영상들에 **묻는 방법(지시문)만 바꿔** 돌려보고, 어느 방법이 위반을 더 잘 찾는지 숫자로 비교한다. 모델도 영상도 그대로 두고 지시문만 바꾼다.

**세 방법 = "정보를 얼마나 정리해서 시키느냐"의 3단계**

| 단계 | 이름 | 어떻게 묻나 | 노리는 것 | 비용 |
| --- | --- | --- | --- | --- |
| 1 | **그냥 물어보기** | "이 영상에서 위반을 찾아줘"만. 판단을 전부 모델에 맡김 | 비교의 기준선 | 가장 쌈 |
| 2 | **쪼개서 물어보기** | "실선이 있었나 / 차가 넘었나 / 넘기 전후 순서가 맞나"처럼 관찰을 조각내서 답하게 | 근거가 남아 확인 쉽고, 대충 지어내는 것↓ | 지시문 약간↑ |
| 3 | **예시 보여주고 물어보기** | 2단계에 더해 "이건 위반 / 이건 비슷하지만 위반 아님" 예시 몇 개를 지시문에 넣음 | 헷갈리는 정상 장면을 위반이라 잘못 잡는 실수↓ | 지시문 많이↑ |

각 단계는 정보를 더 주는 대신 지시문이 길어져 비용(글자 수)이 늘어난다. 그래서 **"더 잘 찾게 된 이득"이 "늘어난 비용"만큼 값어치가 있는지** 같이 재야 한다.

**무엇을 비교해서 무엇을 아나**

- 1단계 → 2단계: 관찰을 쪼개게 하면 더 잘 찾나? 헛짚음이 주나?
- 2단계 → 3단계: 예시를 주면 헷갈리는 정상 장면을 덜 잘못 잡나? 그게 늘어난 비용값을 하나?

**무엇을 재나** (같은 영상들에 세 방법을 똑같이 적용)

- 놓치지 않고 찾아낸 비율 (실제 위반이 상위 후보에 들어왔는지)
- 헷갈리는 정상 장면을 위반이라 **잘못 잡은 비율**
- 1시간당 헛짚은 후보 개수
- 비용, 걸린 시간

**왜 꼭 같은 영상으로 비교하나:** 영상이 다르면 "방법이 좋아서"인지 "영상이 쉬워서"인지 구분이 안 된다. 같은 영상·같은 정답지에 방법만 바꿔야 공정하다. (실행 기록에는 방법 이름표 — `direct@v1`, `structured@v1`, `struct+ref@v1` — 만 다르게 남긴다, §9-3)

**주의 한 가지:** 3단계의 "예시 보여주기"는 무거운 검색(SentrySearch식 벡터DB)이 아니라 **고정된 예시 몇 개를 지시문에 그냥 넣는 것**이다. 1.3이 "무거운 검색은 나중, 예시 몇 개 넣는 것부터 재보라"고 한 게 이 뜻. 예시가 매번 같으니 캐싱으로 비용을 아낄 수 있고, 예시는 `eval/references/`에 고정해 재현성을 지킨다.

**이 실험의 의미:** **프롬프트만으로 어디까지 끌어올릴 수 있는지**를 먼저 잰다. 세 방법을 다 해봐도 부족하면 그때 §6 챌린저(다른 모델·검색)로 넘어간다.

---

## 6. 챌린저 — 조사만, 열지 않음 (Failure decides the challenger)

지금은 목록·발동조건만. **실패 분류가 필요성을 증명할 때만** 카드를 연다(§11 #12).

| 챌린저 | 여는 조건 (failure_kind 신호) | 성격 |
| --- | --- | --- |
| **VideoChat3** | `SEARCH` 지배적 — Gemini가 긴영상에서 후보를 아예 못 찾음(Recall@10 낮음) | 다른 탐색 VLM |
| **SentrySearch** | `SEARCH` + 특정 이벤트 유형 반복 누락 | **임베딩→ChromaDB 벡터검색 + VLM 재랭킹** (우리 baseline과 다른 계열) |
| **ADAS·CV / 전용검출** | `PRIMITIVE`·`TARGET_ASSOCIATION` — 선·궤적·대상판정 오류 지배적 | 결정적 CV 보강 |
| **자체 fine-tuning** | `PRIMITIVE`·`FINE_FN` 지속 + 데이터 축적됨 | 한국 도로/4종 특화 |
| **자체 GPU (Qwen2.5-VL 등)** | `COST` 지배적 + 고부하 지속(COST.md 방법B 조건) | 영상반출 금지 규정 시에도 |

> 지금 안 여는 이유: 챌린저 플러그인 레지스트리·상시 GPU는 §11-3 과설계 목록. `search/coarse/` 교체 인터페이스 1개 + 팩토리로 충분.

**SentrySearch 코드 확인 (2026-08-27, [github.com/ssrajadh/sentrysearch](https://github.com/ssrajadh/sentrysearch) main, 발동 시 참조):**

- 청킹: `chunker.py` — 30초 청크/5초 오버랩(step 25s), CLI `-chunk-duration`·`-overlap` 조절, ffmpeg `c copy`. 480p·5fps 다운스케일(payload 축소용), 정지화면 스킵.
- Gemini **2군데·다른 API**: ①임베딩 = `embed_content`, `gemini-embedding-2`(768d), 청크 mp4를 inline `Part.from_bytes` 그대로(File API 아님) → ChromaDB. ②재랭킹 = `generate_content`, `gemini-2.5-flash`, JSON스키마·temp0.
- 백엔드 3종: gemini(기본)/local Qwen3-VL/qwen-cloud DashScope.
- **차용 판단:** 겹침 청킹값(30/5/25s)은 벡터DB 없이 §3-C에 즉시 참조 가능. 임베딩+벡터검색 전체는 §11-3 과설계(ChromaDB 필요)라 recall 실측이 증명할 때만.
- **비용 (README `## Cost`):** 1시간 인덱싱 **~$2.84** (embedding-2, `3600 frame × $0.00079`, **임베딩만·rerank 미포함**). 우리 baseline(generate_content low Flash-Lite **~$0.024**)의 **약 100배**. 이유 ①임베딩 프레임단가가 generate_content 토큰환산의 ~120배 ②$2.84는 "인덱스 1회 구축비"라 반복검색 시 상각 — 우리는 영상당 1회 탐색이라 **통스캔이 유리**. (README의 3600프레임은 겹침 무시치 → 실제 ~4320프레임으로 20%↑ 가능. 로컬 Qwen 백엔드는 API비용 0)

---

## 부록. 4종 명칭 제안

| 현재 | 문제 | 제안 | 근거 |
| --- | --- | --- | --- |
| `SIGNAL` | 신호등? 방향지시등? 신호 상태? — 뭘 가리키는지 없음 | `RED_LIGHT_CROSSING` | 적신호에 정지선/교차로를 넘는 관찰 가능한 순간 |
| `CENTER_LINE_CROSSING` | 명확 — 이미 관찰형 | (유지) | — |
| `LANE_CHANGE` | 진로변경은 정상 주행과 구분 안 됨. 신고 대상은 "선을 넘는 끼어들기" | `LANE_LINE_CROSSING` | `CENTER_LINE_CROSSING`과 대칭. "어느 선을 넘었나"만 다름 |
| `MOTORCYCLE_HELMET_NON_USE` | 뜻은 명확하나 `NON_USE`가 어색 | `MOTORCYCLE_NO_HELMET` | 한 장면 객체 속성. 간결화 |

---

## 출처

조사 시점 2026-08-27 기준. 아래 링크는 자료조사에 직접 사용한 1차 출처다(유실 방지용 보존).

**Gemini API 공식문서 (ai.google.dev)**

- Video understanding — https://ai.google.dev/gemini-api/docs/video-understanding
- Files API — https://ai.google.dev/gemini-api/docs/files
- Pricing — https://ai.google.dev/gemini-api/docs/pricing
- Batch API — https://ai.google.dev/gemini-api/docs/batch-api
- Context caching — https://ai.google.dev/gemini-api/docs/caching
- Token counting — https://ai.google.dev/gemini-api/docs/tokens

**SDK / 레포**

- python-genai SDK v1.33 (context7 교차확인) — https://github.com/googleapis/python-genai
- SentrySearch (챌린저 조사 대상, main) — https://github.com/ssrajadh/sentrysearch

**내부 기준 문서 (레포 내)**

- 서비스 기획안 1.3, 모듈 구조 설계 v3 → 현행 v4는 `docs/architecture/module-architecture.md`
- 기존 자산: `eval.py`, `COST.md`, `labels.example.jsonl`
