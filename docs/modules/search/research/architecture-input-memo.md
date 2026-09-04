# [search] Architecture Input Memo

> **성격:** 모듈 구조 설계 v4(`docs/architecture/module-architecture.md`) 작성의 근거가 된 Owner 자료조사 메모다. **조사 결과이지 결정이 아니다.** v4에 반영되지 않은 제안은 제안 상태로 남아 있고, 결정은 v4와 이 모듈의 `decisions/`에서만 한다. 문서 안의 `v3 §N`·`테크스펙 §N` 인용은 작성 당시(v3) 번호다.

# `search` Architecture Input Memo

**Owner:** 서어진 — `search`(사건 탐색)
**관련 모듈:** `recording`(정철원) · `case`(유소연) · `eval`(김대원) · `evidence`(김준영) · `readout`(신유민 — profile 태그 한 건만)
**근거 자료:** ①「비search 모듈 자료조사 — Gemini baseline 실측 착수용」(2026-08-27, ai.google.dev video-understanding/files/pricing/batch-api/caching + python-genai v1.33 교차확인) ②기존 자산 `eval.py`·`COST.md`·`labels.example.jsonl` ③SentrySearch 레포 코드 확인(github.com/ssrajadh/sentrysearch, main) ④기준 문서: 기획안 1.3 / 모듈 구조 v3 / Technical Spec v0.1(N1~N15)

**표기 규약**`[확인]` 공식문서·코드로 확인된 사실 · `[제안]` Owner의 현재 가설·설계 초안 · `[검토]` AI가 보기에 추가 검토가 필요한 지점(자료에 근거 없음)

---

## 1. 현재 추천 결론

**① 제품 런타임 baseline = Files API 업로드 + `media_resolution=low` + 무음 + Flash-Lite**

- **근거:** `[확인]` inline은 요청 전체 100MB 한도이고 base64가 ~33% 팽창하므로 1시간 영상은 불가. low 기준 1시간 ≈ 0.36M tok, Flash-Lite 0.036/시간**.
- **Architecture 영향: 있음** — 업로드 전략 5안 중 (a)전체·(b)필요파일 원본 업로드는 §2의 2GB 제약과 충돌. `recording`의 proxy 생성이 사실상 전제가 된다.

**② Batch API(50% 할인)는 제품 런타임에서 배제하고 `eval` 오프라인 채점 전용으로 못박는다**

- **근거:** `[확인]` 공식문서가 target 24h·보장 없음, "non-urgent tasks such as running evaluations"로 명시. N7(백그라운드 강제)은 24h를 허용한다는 뜻이 아니다.
- **Architecture 영향: 있음** — Efficiency 지표의 "source-video-hour당 원가"가 **제품 원가**와 **채점 원가** 두 값으로 갈린다. `AnalysisRun.cost`에 `is_batch` 플래그가 없으면 두 숫자가 섞인다.

**③ 1회 업로드 → `videoMetadata.startOffset/endOffset`만 바꿔 N회 질의 (coarse→fine 재업로드 없음)**

- **근거:** `[확인]` clipping 파라미터 존재(문자열 `"1250s"` 형식). `[검토]` 일부 SDK 버전 미지원 보고가 있어 실측 미완.
- **Architecture 영향: 있음** — 같은 case의 Coarse 1 + Fine K가 **하나의 `RemoteCopy`를 공유**한다. 업로드 참조의 캐싱 주체·수명·`JobRecord.input_fingerprint` 연동이 계약 대상이 된다.

**④ 오디오 스트립은 `search`가 아니라 `recording`이 profile로 수행한다**

- **근거:** `[확인]` API에 오디오 제외 옵션 없음(업로드 전 `ffmpeg -an` 뿐). 오디오는 해상도 무관 32 tok/s 고정 → low에서 비중 ~33%. `[확인]` 4종은 전부 순수 시각 이벤트이고 화면시각·속도는 overlay OCR(`readout`) 담당 → **정보 손실 0**.
- **Architecture 영향: 있음** — v3의 `prepare_analysis_source(time_range, profile)`는 유지되지만, **profile 태그 체계를 누가 정의하는가**가 빈칸이다(§4·§6-B).

**⑤ `AnalysisRun.cost`를 현행 3필드(`krw, tokens, latency_sec`)에서 요율 스냅샷 포함으로 확장**

- **근거:** `[확인]` 요율이 (a)200k 티어 (b)모달리티(video/audio 요율 다름) (c)배치 (d)캐시 (e)시점(3.x Flash 2027-01-01 인상) 5축으로 갈린다. 실행 시점 요율을 값으로 박아두지 않으면 요율표가 바뀐 뒤 과거 실행의 원가를 재계산할 수 없다.
- **Architecture 영향: 있음** — 계약 ④는 전원 합의 대상 3개 중 하나다. §4 참조.

**⑥ 4종은 "스키마 하나 + 유형별 델타 넷"으로 구현하고, 공개 인터페이스는 `AnalysisScope.target_event_types` 목록 하나를 유지한다**

- **근거:** `[제안]` 시간순서형 3종(신호·중앙선·진로변경)과 객체속성형 1종(안전모)은 `VisualEvidence`의 **채우는 필드만** 다르다(안전모는 `temporal_order=[]`, primitives로 표현). 유형별 분기는 `search/routing` 내부 사정.
- **Architecture 영향: 없음** — v3의 "모듈은 늘리지 않고 primitive를 `종류+있음/없음+확신도`로 일반화" 결정이 실제 프롬프트 설계에서 성립함을 확인.

**⑦ 챌린저는 열지 않는다 — 조사만 완료**

- **근거:** `[확인]` SentrySearch 1시간 인덱싱 ~$2.84(임베딩 `gemini-embedding-2`만, rerank 미포함)로 우리 baseline의 **약 100배**. 그 비용은 "인덱스 1회 구축비"라 반복 검색에서 상각되는 구조인데 **우리는 영상당 1회 탐색**이라 상각이 일어나지 않는다. 겹침 청킹 실측값(30s 청크/5s 오버랩/step 25s)만 벡터DB 없이 차용 가능.
- **Architecture 영향: 없음** — `search/coarse/` 교체 인터페이스 1개 + 팩토리로 충분(플러그인 레지스트리는 과설계 목록).

---

## 2. 확인된 기술적 제약

| 제약 | 근거 | Architecture / Data Contract 영향 |
| --- | --- | --- |
| inline 입력은 요청 전체 **<100MB** (base64 ~33% 팽창) | `[확인]` files 문서 | 긴 영상은 Files API 강제. `search/providers/` 업로드 경로 단일화(N10과 정합) |
| Files API **파일당 2GB / 프로젝트 20GB** | `[확인]` files 문서 | **1시간 원본 4~8GB(COST.md §숨은비용)는 2GB 초과 → 원본 그대로 업로드 불가.** 업로드 전략 (a)(b)의 "원본 전송" 해석 재검토 필요 |
| 프로젝트 20GB 총량 한도 | `[확인]` | **동시 진행 case 수의 상한**이 provider 계정 단위로 걸린다. 초과 시 GCS 또는 한도 증가 요청 → 공통기반(작업 큐) 스케줄링 제약 |
| 업로드 파일 **48시간 자동 삭제** (`files.delete`/`files.list` 존재) | `[확인]` | `RemoteCopy.expires_at`의 상한. 만료 후 재실행 경로가 v3 부분 재실행 표에 없음(§3) |
| 컨텍스트 길이 상한: 1M 모델 기준 **default ~1시간 / low ~3시간** | `[확인]` (2M 모델 ~2시간은 현 라인업 존재 여부 불확실) | `AnalysisScope.time_ranges` 하나가 3시간을 넘으면 분할이 **선택이 아니라 강제** |
| 1시간 default = ~1.08M tok → **1M 컨텍스트 초과** | `[확인]` 토큰식 | **1시간 통스캔은 low에서만 가능.** default 통스캔은 구조적으로 불가 |
| 토큰화(1 FPS): default ~300 tok/s, low ~100 tok/s, **오디오 32 tok/s 고정** | `[확인]` (문서 내 258 vs 263, low 66 vs 70 불일치 → 보수적 값 사용) | 원가 예측의 분모. `video_duration_sec`·`media_resolution`·`fps_used`가 없으면 원가 재계산 불가 |
| `videoMetadata.fps` 기본 1.0, 범위 **(0, 24]** | `[확인]` | fps<1로 추가 절감 가능 → `AnalysisScope.budget`과 품질 사이의 노브가 하나 더 생김 |
| 지원 포맷은 **컨테이너 9종만 명시**(mp4/mov/webm/avi/mpeg/wmv/flv/mpg/3gpp), **코덱(H.264/H.265) 명시 없음** | `[확인]` 문서에 존재하지 않음(웹 검색으로도 미발견) | **N14("H.265 / 1시간 이상 E2E")의 근거가 아직 없다.** §3·§6-A |
| usage 필드명이 API 계열별로 다름 (`usage_metadata` vs `usage`) | `[확인]` SDK | `AnalysisRun.cost`는 **정규화된 우리 필드명**을 계약으로 두고 provider 필드는 어댑터에서 매핑해야 함 |
| Batch API: 전 모델 50% 할인, **target 24h·보장 없음** | `[확인]` batch-api | 제품 런타임 불가. `is_batch` 플래그 필요 |
| Context caching: read 단가 1/10~1/4 + **시간당 저장비** | `[확인]` caching | **파일 수명 48h ≠ 컨텍스트 캐시 수명** — 별개 개념임을 계약 문서에 명시 필요 |
| SentrySearch 임베딩 인덱싱 1시간 ~$2.84 (baseline의 ~100배) | `[확인]` README `## Cost` | 챌린저 조기 도입 근거 없음. 겹침 청킹값만 차용 |
| **자료 내부 원가 수치 불일치:** §2-5는 low 1시간 0.024 | `[확인] 불일치 자체` | 0.36M(오디오 포함) vs 0.238M(무음)으로 해석하면 정합하지만 **자료에 그렇게 쓰여 있지 않다.** 무음 A/B 실측 전까지 `budget` 기본값 확정 금지 |

---

## 3. 현재 Module Architecture에 미치는 영향

### 그대로 유지 가능한 것

- **`search → recording` 단방향, `search`는 `readout`을 호출하지 않는다** — clipping 기반 coarse→fine이 전부 `search` 내부에서 닫힌다. 분리 비용이 실제로 0에 가깝다.
- **`AnalysisScope` 형식을 제품과 `eval`이 공유** — A/B 3종 실험이 지시문(impl 이름표)만 바꾸고 입력 형식은 동일하므로 성립한다.
- **`search`는 `eval`의 존재를 모른다** — Batch는 `eval` 측 실행 옵션이지 `search` 내부 분기가 아니다(`if 평가모드:` 불필요).
- **후보 0개는 정상 결과** — 프롬프트 공통 불변 블록에 "억지로 채우지 마라 / 빈 결과는 정상"을 명시(N1과 정합).
- **`VisualEvidence.legal_status` 항상 null** — 프롬프트 공통 블록의 "법적 판단 금지"가 이를 강제한다.
- **모듈을 늘리지 않는다** — 4종의 두 부류 차이는 스키마가 아니라 채우는 필드로 흡수된다.

### 수정 검토가 필요한 것

**(1) `AnalysisRun.cost` 필드 부족**

> **현재 구조:** `cost{krw, tokens, latency_sec}` 3필드.
**조사 결과:** 요율이 티어·모달리티·배치·캐시·시점 5축으로 갈리고 video/audio 토큰이 분리 집계된다. 요금은 USD인데 계약 필드는 KRW다.
**왜 검토가 필요한가:** 요율표가 바뀌면 과거 `AnalysisRun`의 원가를 재계산할 수 없다 = "10주 뒤 남는 실험 자산"이 깨진다. KRW 단일 값은 환율 스냅샷 없이 재현 불가.
**영향받는 모듈:** `eval`(Efficiency 지표·N15 재현성), `case`(`budget` 상한 비교 단위), 공통기반(사용량·비용 장부).
> 

**(2) profile 태그 체계의 소유자가 비어 있다**

> **현재 구조:** `prepare_analysis_source(time_range, profile)` — profile은 `recording`이 해석.
**조사 결과:** 어떤 profile이 필요한지 아는 쪽은 `search`(coarse는 저해상도·무음 가능)와 `readout`(번호판·화면시각은 원본 화질 필요)이다.
**왜 검토가 필요한가:** 태그 문자열이 합의되지 않으면 `recording`이 만든 사본을 `search`가 못 쓰거나, `readout`이 저화질 proxy로 번호판을 읽는 사고가 난다.
**영향받는 모듈:** `recording`, `readout`, (발주자로서) `case`.
> 

**(3) 48시간 만료 후 재실행 경로가 부분 재실행 표에 없다**

> **현재 구조:** 부분 재실행 표는 "사용자가 고친 것 → 다시 도는 것"만 다룬다.
**조사 결과:** 이틀 뒤 사용자가 "다른 후보 보기"를 누르면 provider 파일이 이미 자동 삭제돼 `search` 호출이 실패한다.
**왜 검토가 필요한가:** 사용자 체감이 "어제는 즉시, 오늘은 몇 분"으로 갈리고 재업로드 비용이 다시 발생한다. 실패를 `INFRA`로만 잡으면 `case`가 "재업로드가 필요한 실패"임을 알 수 없다.
**영향받는 모듈:** `case`(재실행 정책·JobRecord), `recording`(RemoteCopy 재생성), `search`(failure_kind 세분).
> 

**(4) `failure_kind = INFRA`가 너무 뭉뚱그려져 있다**

> **현재 구조:** 공통 `INFRA` 하나.
**조사 결과:** 최소 세 갈래가 구분돼야 한다 — ①원격 파일 만료/부재 ②코덱·포맷 거부 ③일시적 네트워크·쿼터. ①만 "재업로드하면 복구", ②는 "재시도해도 영원히 실패".
**왜 검토가 필요한가:** `case`의 재발주 판단과 챌린저 발동 조건("Failure decides the challenger")이 둘 다 이 분류에 의존한다. 뭉뚱그리면 taxonomy 통계가 오염된다.
**영향받는 모듈:** `case`, `eval`(failure 통계).
> 

**(5) 원본 리포트의 소유권 표기 하나가 뒤집혀 있었다 (자료 내 자체 수정)**

> **현재 구조:** `RemoteCopy`는 `recording` 소유, 만료 시각도 `recording`이 세팅.
**조사 결과:** 리포트 초안이 48h를 "`search`가 알아야 함"으로 적었으나, `search`가 provider의 파일 수명 정책을 아는 것은 경계 침범이다.
**왜 검토가 필요한가:** 이 항목은 "search가 알 것"이 아니라 **"`recording`에 전달할 제약"**으로 재분류돼야 한다 → `RemoteCopy.expires_at ≤ upload_time + 48h` 강제.
**영향받는 모듈:** `recording`. (v3 자체는 옳았고 리포트 표기를 고치는 방향)
> 

### 판단 불가 (자료 부족)

- **H.265/HEVC를 Gemini가 받는가** — 공식문서에 코덱 명시가 없다. 실측 전까지 N14 충족 여부를 말할 수 없다.
- **`videoMetadata.startOffset/endOffset`이 우리가 쓸 SDK 버전에서 동작하는가** — 미지원이면 결론 ③이 무너지고 fine마다 재업로드가 필요해진다.
- **구간 분할 전략 A(통스캔)/B(고정)/C(겹침)/D(2패스) 중 무엇이 이기는가** — 같은 labels로 recall×비용×지연을 재기 전에는 결정 불가.
- **Context caching이 우리 패턴(1 case에 coarse 1 + fine K, 수 분 내)에서 이득인가** — 저장비 잠식 지점 미측정.
- **무음 처리의 실제 절감폭** — `prompt_tokens_details`의 AUDIO 모달리티가 0으로 떨어지는지 A/B 미실시.

---

## 4. 접합부 / Data Contract에 영향을 주는 내용

| 상대 모듈 | 방향 | 필요한/제공하는 정보 | 조사에서 확인된 제약 | 계약 단계에서 결정할 것 |
| --- | --- | --- | --- | --- |
| `recording` | `recording → search` | 분석용 소스 참조(`AnalysisSource`/`RemoteCopy` ref), 그 소스의 **길이(sec)·해상도·오디오 유무·컨테이너/코덱**, 유효 만료시각 | 파일당 2GB·프로젝트 20GB·48h 자동삭제. 원본 4~8GB는 업로드 불가 | ①`search`가 파일 경로가 아니라 **ref만** 받는가(A4·N10 유지 시 ref여야) ②`video_duration_sec`을 누가 주는가(원가 정규화 분모 → **필수 필드**) ③만료시각을 `search`가 읽는가, 만료를 오직 실패로만 아는가 |
| `recording` | `search → recording`(요청) | `prepare_analysis_source(time_range, profile)`의 **profile 태그** | 오디오 제외는 업로드 전 ffmpeg만 가능. coarse는 저해상도·무음으로 충분 | ④profile 태그 문자열 집합을 누가 정의·소유하는가. 예: `coarse-low-noaudio` / `fine-native` / `readout-native` `[제안]`. 소비자가 둘(`search`·`readout`)이라 **3자 합의** 필요 |
| `recording` | `search → recording` | coarse 1회 + fine K회가 **같은 업로드를 재사용** | clipping이 되면 재업로드 불필요, 안 되면 K+1회 업로드 | ⑤업로드 재사용 참조를 어디에 보관하고 `JobRecord.input_fingerprint`와 어떻게 연동하는가 |
| `case` | `case → search` | `AnalysisScope{time_ranges[], target_event_types[], hint, budget, contract_version}` | `budget.max_cost_krw`는 KRW인데 요율은 USD. `time_ranges` 하나가 low 3시간(default 1시간)을 넘으면 단일 호출 불가 | ⑥budget을 KRW로 유지하려면 **환율 스냅샷을 누가 넣는가** ⑦`time_ranges` 길이 상한을 계약에 명시할 것인가 ⑧`hint.free_text`가 그대로 외부 API로 나간다 → **N13 방어선을 계약 수준에서 어떻게 강제하는가** `[검토]` |
| `case` | `search → case` | `AnalysisRun`(불변) + `CandidateEvent[]` + `VisualEvidence` | 후보 0개는 정상. 여러 후보를 배열로 보존해야 함(`[다른 후보 보기]`). `candidate.at_provenance`는 아직 확정 시각 아님 | ⑨`failure_kind`에 **재업로드로 복구 가능/불가** 축을 넣을 것인가(§3-4) ⑩부분 성공(fine K개 중 일부 실패)을 배열 내 개별 상태로 표현하는가, run 단위 상태로 표현하는가 |
| `case` / 공통기반 | `search → case` | 비용·지연·토큰 실측치 | 요율 5축 분기, USD/KRW, batch 여부, 캐시 토큰 | ⑪`cost` 확장 필드를 **계약에 넣을지 장부(공통기반)로 뺄지**. `[제안]` 계약에 넣는다 — `eval`이 `search` 공개 출력만으로 채점해야 하므로 |
| `eval` | `search → eval` | 제품과 **동일한** `AnalysisRun`, `impl{name, model_tag, prompt_ver}` | A/B 3종은 `direct@v1`/`structured@v1`/`struct+ref@v1` 이름표로만 구분. 참조 예시는 `eval/references/`에 고정 | ⑫`prompt_ver`이 프롬프트 텍스트 해시인가 수동 태그인가(N15 재현성 판정 기준) ⑬`price_in_per_1m` 스냅샷을 비교 거부 조건에 포함하는가 |
| `evidence` | (직접 없음, `case` 경유) | `VisualEvidence` | `legal_status`는 필드로 두되 항상 null | ⑭4종 event_type **enum 값 자체**가 `evidence`의 4종→신고유형 매핑표와 `eval` 정답지 양쪽의 키다(§6-C) |
| `readout` | (호출 없음) | profile 태그 체계만 공유 | 번호판·화면시각 OCR은 재인코딩 proxy로는 위험 | ⑮"이 소스는 관찰용 proxy이지 판독용 원본이 아니다"를 **데이터 형식 어디에** 표시하는가 |

**필드 성격 정리 `[제안]`**

- **필수:** `video_duration_sec`, `model_tag`, `tokens_in/out`, `price_in_per_1m`, `price_usd`, `latency_sec`, `media_resolution`
- **optional:** `cached_tokens`, `thoughts_tokens`, `ttft_sec`, `fps_used`, `tokens_in_audio`
- **immutable:** `AnalysisRun` 전체 — 다시 돌리면 새 기록(v3 유지)
- **배열 보존 필수:** `CandidateEvent[]`, `VisualEvidence.primitives[]`, `temporal_order[]`, `uncertain[]`
- **UNKNOWN/ABSTAIN 표현:** `primitives[].present=false` + 낮은 confidence, `uncertain[]`, 후보 0개(실패 아님)
- **downstream으로 넘겨야 하는 실패정보:** `failure_kind` + 재실행 가능성 신호(§3-4)

---

## 5. 열린 결정

| 결정할 문제 | 가능한 방향 | 현재 추천 | 추천 근거 | 누구와 확인 |
| --- | --- | --- | --- | --- |
| 1시간 원본이 Files API 2GB를 넘는다 | (a)원본 업로드 / (c)저해상도 사본 / (e)분할파일 직접 / GCS 경유 | **(c) 저해상도 무음 proxy** | 2GB·1M 컨텍스트·오디오 33%가 전부 같은 방향을 가리킴 | 정철원(업로드 5안 소유), 김준영(외부 전송 범위) |
| 구간 분할 전략 | A 통스캔 / B 고정분할 / C 겹침분할 / D 2패스 | **D를 유력 후보로 두되 A~D 실측 후 결정.** 겹침값은 30s/5s/step25s 차용 | 경계에 걸친 사건 누락(1.3 TC6) 방지 + 비용 최소. 단 recall 미측정 | 김대원(labels·채점), 유소연(latency 체감) |
| `AnalysisRun.cost` 단위 | KRW 단일 / USD + 스냅샷 / 둘 다 | **USD 원값 + 요율·환율 스냅샷 보관, KRW는 파생** | 요율표가 USD이고 재계산 가능성이 목적 | 유소연(budget 비교), 김준영(장부) |
| 48h 만료 후 사용자 재접속 | 재업로드 발주 / **case 유효기간을 48h 이내로 제한** / 만료 전 사전 갱신 | **보류 — 두 안 모두 정책 결정** | 기간 제한이 훨씬 단순하지만 UX 축소. 기술자 단독 결정 불가 | 유소연(`case` 재실행 정책), 김준영(N12) |
| `RemoteCopy` TTL | 48h보다 짧게 / 같게 / 길게 | **48h보다 짧게 — 우리가 먼저 지운다** | N12와 정합. provider 자동 파기는 백스톱으로만 | 정철원, 김준영 |
| 이미 지워진 provider 파일에 대한 `purge_case()` | 에러 / idempotent 정상 | **idempotent 정상 + `DeletionReport`에 "이미 없음" 구분 기록** | 삭제 실패로 오인되면 N12 검증이 무의미해짐 | 정철원 |
| 고아 파일 점검(`files.list()`) | 주기 점검 / 하지 않음 | **주기 점검** `[제안]` | 우리 DB엔 없는데 provider에 남은 영상은 개인정보 노출 | 김준영(C-2 보안 coordinator) |
| Context caching 도입 | 도입 / 보류 | **보류 — 실측 후** | 짧은 시간 다회 질의면 이득이나 저장비 잠식 지점 미측정 | (모듈 내부) |

---

## 6. 충돌 / 상대 담당자 확인 필요

### A. 기존 Architecture와 충돌

**A-1. N14("H.265 / 1시간 이상 영상 E2E 동작")의 근거가 아직 없다**

- **무엇이:** Technical Spec v0.1이 H.265 E2E를 비기능 요구로 명시했으나, Gemini 공식문서는 **컨테이너 MIME만** 정의하고 코덱을 명시하지 않는다. `.mp4` 지원 ≠ `.mp4 안의 H.265` 지원 — 서로 다른 층위다.
- **왜:** 최근 블랙박스는 저장 효율 때문에 HEVC 채택이 늘어 실제 사용자 파일이 H.265일 가능성이 낮지 않다. 미지원이면 **분할 전략의 `ffmpeg -c copy`(재인코딩 없이 자르기) 전제가 통째로 무너진다**(`c copy`는 코덱을 그대로 두므로 H.265 원본을 잘라도 결과물은 H.265).
- **파생 영향(미지원 시):** ①1시간 트랜스코딩 소요시간이 사용자 대기에 직접 추가(N6/N7) ②트랜스코딩 CPU 비용이 현재 원가식에 **없는 항목**으로 추가(현 원가는 API 비용 중심) ③재인코딩 화질 손실이 coarse 탐색 성능에 영향. 단 어차피 재인코딩이 필요하다면 **저해상도·무음 proxy를 한 번에 만드는 편이 오히려 효율적** → 업로드 전략 (c)에 유리하게 작용.
- **실측 항목:** HEVC mp4를 그대로 업로드→`generate_content` 성공 여부 / 실패 시 단계(업로드 거부·추론 실패·조용한 빈 응답) / 에러에 코덱이 명시되는가(`INFRA` 분류 근거) / H.264 동일 내용 대비 토큰·지연·비용 차이 / 블랙박스 실제 컨테이너가 9종 안에 다 들어가는가(mkv·ts 기종 여부).
- **같이 볼 사람:** 정철원(H.265 샘플 제공·컨테이너 실측), 김준영(N14 문구 소유).

**A-2. 1시간 원본(4~8GB)은 Files API 파일당 2GB 한도를 넘는다**

- **무엇이:** 업로드 전략 5안 중 "원본을 그대로 보낸다"는 해석이 기술적으로 불가능하다.
- **왜:** 2GB는 provider 하드 제약이고 우회는 GCS 경유 또는 사전 분할·다운스케일뿐이다.
- **같이 볼 사람:** 정철원(전략 5안 결정 주체), 김준영(외부 전송 범위 정의).

**A-3. 부분 재실행 표에 "provider 파일 만료" 행이 없다** — §3-(3). 같이 볼 사람: 유소연.

### B. 다른 모듈과 충돌 가능

**B-1. profile 태그 체계 — `recording`이 해석하지만 정의에는 `search`+`readout`이 필요**

- `search` coarse는 저해상도·무음으로 충분하나 `readout`(번호판·화면시각)은 **반드시 원본 화질**이어야 한다고 본다 `[제안]`. 이 구분이 계약 어디에도 표시되지 않는다.
- 미해결 파생 질문: **fine 검증도 proxy로 하는가, 원본 구간을 다시 뽑는가** — 선 종류(실선/점선)·신호색 판별은 화질에 직접 영향받는다.
- 같이 볼 사람: 정철원, 신유민.

**B-2. `AnalysisScope.budget` 기본값을 `case`가 정하려면 원가 실측이 먼저다**

- 자료 내부에서 low 1시간 원가가 0.024로 엇갈린다(오디오 포함/무음 차이로 해석하면 정합하나 자료에 명시 없음). 무음 A/B 실측 전에는 기본값을 줄 수 없다.
- 같이 볼 사람: 유소연.

**B-3. 실패 분류 세분화(`search` 소유)와 재실행 정책(`case` 소유)은 한쪽만 정할 수 없다** — §3-(4). 같이 볼 사람: 유소연.

**B-4. 4종 enum 명칭 변경 제안이 `eval` 정답지와 `evidence` 매핑표의 키를 동시에 건드린다** — C-1.

### C. Product / 정책 결정 필요

**C-1. 4종 event_type 명칭 `[제안]`**

| 현재 | 문제 | 제안 | 근거 |
| --- | --- | --- | --- |
| `SIGNAL` | 신호등인지 방향지시등인지 신호 상태인지 지시 없음 | `RED_LIGHT_CROSSING` | 적신호에 정지선/교차로를 넘는 **관찰 가능한 순간** |
| `CENTER_LINE_CROSSING` | 명확 — 이미 관찰형 | (유지) | — |
| `LANE_CHANGE` | 진로변경은 정상 주행과 구분되지 않음. 신고 대상은 "선을 넘는 끼어들기" | `LANE_LINE_CROSSING` | `CENTER_LINE_CROSSING`과 대칭. "어느 선을 넘었나"만 다름 |
| `MOTORCYCLE_HELMET_NON_USE` | 뜻은 명확하나 `NON_USE`가 어색 | `MOTORCYCLE_NO_HELMET` | 한 장면 객체 속성. 간결화 |
- **왜 PM 판단인가:** 이 enum은 `AnalysisScope`(전원 합의 계약)·`eval` 정답지 키·`evidence`의 4종→신고유형 매핑표에 동시에 박힌다. **자료조사가 끝난 지금 바꾸는 것이 가장 싸고, 계약 회의 이후에는 비싸진다.** 바꾸지 않기로 해도 그 결정을 기록해야 한다.
- **같이 볼 사람:** 김준영(PM·`evidence`), 김대원(`eval` 정답지).

**C-2. 사용자 자유입력 단서(`hint.free_text`)가 외부 API로 나간다** `[검토]`

- coarse 프롬프트가 사용자 기억 단서를 그대로 주입한다. 사용자가 번호판·이름·상대 정보를 자유입력에 쓸 수 있다. N13은 "`AnalysisScope`에 개인정보 금지"라고 하지만 **자유 텍스트를 어떻게 막을지는 정의되어 있지 않다.**
- 자료에서 확인된 사항이 아니라 AI가 제기하는 검토 항목이다. 같이 볼 사람: 김준영(C-2 보안 coordinator), 유소연(단서 해석 LLM 1회 소유).

**C-3. `raw_response_ref`(모델 원문 응답) 보관** `[검토]`

- 모델이 관찰 서술에 번호판 문자열·상세 위치를 포함할 수 있다. N11(로그 마스킹)은 로그를 대상으로 하는데 `raw_response_ref`는 계약 필드다. 보관 범위·마스킹 여부·TTL이 정의되지 않았다. 같이 볼 사람: 김준영.

**C-4. 48h는 경고이면서 동시에 안전망이다 — 보안 문서에 근거로 기재 가능**

- 우리가 삭제 로직을 빠뜨려도 provider가 48h에 자동 파기한다 → N12(흩어진 4곳 동시 삭제)의 백스톱이 하나 생긴다. 보안 체크리스트 "외부 AI API 전송 영상범위·보관" 항목에 **"provider 자동 파기 48h"를 근거로 기재 가능**. 미결 C-2 안건에서 그대로 쓸 수 있다.

---

## 7. 후속 Data Contract에서 반드시 다룰 질문

1. `AnalysisScope`가 실제 파일 경로를 갖는가, `recording`이 발급한 **소스 참조(ref)만** 갖는가? (A4/N10 "영상이 나가는 코드는 `search/providers/` 한 곳"을 유지하려면 ref여야 한다)
2. **profile 태그 문자열 집합을 누가 소유하고 어디에 정의하는가?** `recording`이 해석하지만 필요를 아는 쪽은 `search`·`readout`이다. "이 소스는 관찰용 proxy이지 판독용 원본이 아니다"를 데이터 형식 어디에 표시하는가?
3. `video_duration_sec`을 `recording`이 계약 필드로 주는가, `search`가 스스로 재는가? (원가 정규화의 분모이자 `AnalysisRun` 필수 필드)
4. `AnalysisRun.cost`는 **KRW 단일 값**을 유지하는가, **USD 원값 + 요율/환율 스냅샷**을 계약에 넣는가? 스냅샷을 `eval`의 "비교 거부" 조건에 포함하는가?
5. `failure_kind`에 **"재업로드하면 복구 가능"** 축을 넣는가, `INFRA` 하나로 두고 `case`가 별도 판단하는가?
6. `search`의 부분 성공(fine K개 중 일부 실패)을 **후보 배열 내 개별 상태**로 표현하는가, **run 단위 상태**로 표현하는가?
7. 하나의 `AnalysisScope.time_range`가 provider 컨텍스트 상한(low ~3시간)을 넘을 때 **계약이 상한을 명시**하는가, `search`가 내부에서 조용히 분할하는가? 분할했다는 사실이 `AnalysisRun`에 남는가?
8. 같은 case의 coarse 1회 + fine K회가 **하나의 업로드를 공유**한다는 사실을 `JobRecord.input_fingerprint`가 어떻게 표현하는가? (공유가 깨지면 업로드 비용이 K배)
9. `RemoteCopy.expires_at`을 `search`가 **읽을 수 있어야** 하는가, 만료를 오직 실패로만 알게 되는가? (전자는 사전 방어가 가능하지만 provider 정책 지식이 `search`로 새어든다)
10. 4종 event_type enum을 지금 개명하는가? 개명한다면 `AnalysisScope`·`eval` 정답지·`evidence` 매핑표 세 곳을 **같은 커밋에서** 바꿀 주체는 누구인가?

---

## 8. 아키텍처 반영 우선순위

### 🔴 Architecture v4 전에 반드시 결정

- **H.265 지원 여부 실측** — 결과에 따라 업로드 전략·proxy 필수 여부·원가식 항목(트랜스코딩 CPU)·N14 문구가 전부 갈린다. (실측 어진 / 샘플 철원)
- **1시간 원본 > 2GB → 원본 직업로드 불가**를 확정 반영. 업로드 전략 5안의 선택지가 줄어든다.
- **4종 event_type 명칭 확정 또는 "유지" 명시 기록** — 세 문서의 공통 키.
- **profile 태그 체계의 소유자 지정** — `recording`·`search`·`readout` 3자 최소 계약.
- **48h 만료 케이스의 처리 정책**(재업로드 vs case 유효기간 제한) — 부분 재실행 표에 행이 하나 늘어난다.

### 🟡 Data Contract 단계에서 결정

- `AnalysisRun.cost` 확장 필드 목록과 단위(USD/KRW·요율 스냅샷·`is_batch`).
- `failure_kind` 세분(특히 `INFRA` 분해)과 부분 성공 표현 방식.
- `AnalysisScope.time_ranges` 길이 상한 명시 여부, `budget` 기본값.
- `hint.free_text`에 대한 N13 방어 수단.
- `impl.prompt_ver`의 정의(해시 vs 수동 태그)와 N15 비교 거부 조건.
- 업로드 재사용 참조와 `input_fingerprint` 연동.

### 🟢 모듈 내부 Tech Spec에서 결정 (Owner가 이후)

- 구간 분할 전략 A~D 중 최종 선택과 청크 길이·겹침 폭·병렬 개수 튜닝.
- 4종 프롬프트 본문, 공통 불변 블록 문구, primitives 종류 목록.
- A/B 3종(`direct` / `structured` / `struct+ref`) 실험 실행 순서.
- `client.aio` 기반 병렬 호출 구현, 스트리밍 TTFT 측정 여부.
- Context caching 도입 여부.
- `eval.py`의 usage 필드 확장 구현, `PRICE_PER_1M` 모델명 실호출 가능 여부 확인.
- 챌린저 카드(VideoChat3 / SentrySearch / ADAS·CV / fine-tuning / 자체 GPU) — **failure_kind가 필요성을 증명할 때만** 개봉. 개봉 선언 주체는 미결 A-2.

---

## 9. 원본 자료 Reference

| 자료 | 링크/위치 | 무엇의 근거인가 |
| --- | --- | --- |
| Gemini Video understanding | ai.google.dev — video-understanding | 토큰화(258/66 tok/frame, 오디오 32 tok/s), fps 범위, 컨텍스트 길이 상한, 지원 컨테이너 9종, `videoMetadata.startOffset/endOffset` |
| Gemini Files API | ai.google.dev — files | inline 100MB, 파일당 2GB·프로젝트 20GB, **48h 자동 삭제**, `files.delete`/`files.list` |
| Gemini Pricing | ai.google.dev — pricing (2026-08-27 스냅샷) | 모델별 USD/1M 요율, 200k 티어, 3.x Flash 2027-01-01 인상 |
| Gemini Batch API | ai.google.dev — batch-api | 50% 할인, target 24h·보장 없음, "non-urgent such as running evaluations" |
| Gemini Context caching | ai.google.dev — caching | read 단가 1/10~1/4 + 시간당 저장비 |
| python-genai v1.33 (context7) | SDK | `usage_metadata` vs `usage` 필드명 차이, `count_tokens` |
| SentrySearch | github.com/ssrajadh/sentrysearch (main, 2026-08-27 확인) | `chunker.py` 30s/5s/step25s + `-c copy`, 480p·5fps 다운스케일, `embed_content`+ChromaDB, README `## Cost` 1시간 ~$2.84 |
| `eval.py` (기존 자산) | 팀 저장소 | 현재 Files API 사용 · `prompt_token_count`만 기록 → 확장 대상 |
| `COST.md` (기존 자산) | 팀 저장소 | 방법별 비용, **§숨은비용 1시간 ≈ 4~8GB** |
| `labels.example.jsonl` | 팀 저장소 | A~D 전략 비교 실험의 정답지 형식 |
| 기준 문서 | 기획안 1.3 / 모듈 구조 v3 / Technical Spec v0.1 | 모듈 책임·계약 ①~~⑨·N1~~N15·부분 재실행 표 |

---

**미해결 수치 표기:** 자료 내부에 프레임당 토큰(258 vs 263), low(66 vs 70), low 1시간 원가(0.024) 세 쌍의 불일치가 있다. 원가 계산은 보수적 값(default ~300 tok/s, low ~100 tok/s)을 사용했고, **무음 A/B 실측으로 확정하기 전까지 `budget` 기본값을 계약에 박지 않는다.**