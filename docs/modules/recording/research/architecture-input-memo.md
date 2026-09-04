# [Recording] Architecture Input Memo

> **성격:** 모듈 구조 설계 v4(`docs/architecture/module-architecture.md`) 작성의 근거가 된 Owner 자료조사 메모다. **조사 결과이지 결정이 아니다.** v4에 반영되지 않은 제안은 제안 상태로 남아 있고, 결정은 v4와 이 모듈의 `decisions/`에서만 한다. 문서 안의 `v3 §N`·`테크스펙 §N` 인용은 작성 당시(v3) 번호다.

# `recording` Architecture Input Memo

**Owner:** 정철원

**관련 모듈:** `search`, `readout`, `evidence`, `case`, `eval`, 공통 Runtime/Ops, geocoder adapter

**근거 자료:** `전남대학교 2팀 서비스 기획안 제출 1.3`, `대신고 소프트웨어 모듈 구조 설계 v3`, `모듈 기반 역할 배정안 v1`, 현행 Technical Spec, Technical Spec Review Guide, `블랙박스 Recording 파트 자료조사 정리`, `대신고 백엔드 Runtime · Ops 고도화 설계 v1`

`recording`은 현재 Architecture에서 모든 모듈의 가장 아래 계층이며, 원본 `VideoAsset`, 전체 파일 시간축 `RecordingTimeline`, 시각 후보, 분석용 사본, 외부 사본, 파생영상 및 보관·삭제를 소유한다. 다른 모듈에 의존하지 않고 ffmpeg/ffprobe·파일시스템·저장소 같은 기술 기반에만 의존하는 구조다.

---

## 1. 현재 추천 결론

### 1) 블랙박스 파일과 시간축의 단일 소유권은 `recording`에 유지

> **결론:** 파일 사실, 전체 `RecordingTimeline`, 파일 경계 해석은 `recording`이 단독 소유하는 현재 구조를 유지하는 것이 적절하다.
> 
> 
> **근거:** 실제 샘플은 약 1분 단위 파일이며, 분할파일을 직접 활용할 경우 파일 경계·중복 처리가 필요하다.
> 
> **Architecture 영향:** 없음. 단, `resolve_span()` 계약은 더 명확히 해야 함.
> 

### 2) 시각은 하나를 조기에 확정하지 않고 후보와 출처를 보존

> **결론:** `recording`은 파일명·파일 metadata·제조사 metadata 등 파일에서 얻은 시각 후보를 보존하되 어느 값이 맞는지는 판정하지 않는다.
> 
> 
> **근거:** 현재 Architecture도 `TimeSourceCandidate[]`를 `recording`이 생산하고 최종 판정은 `evidence`에 맡긴다.  실제 샘플에서는 `creation_time`이 없고 파일명 시각 및 영상 overlay timestamp가 확인됐다.
> 
> **Architecture 영향:** 없음. Data Contract에서 source 종류 확장성 검토 필요.
> 

### 3) GPS는 optional이며 부재를 정상 상태로 표현

> **결론:** GPS를 필수 입력으로 두지 않는다. 파일·로그에 존재할 때만 `recording`이 좌표 관찰값을 제공한다.
> 
> 
> **근거:** 실제 샘플에서는 GPS stream/metadata가 확인되지 않았다.  기존 Architecture 역시 GPS 없음은 `UNKNOWN`이며 오류가 아니라고 정의한다.
> 
> **Architecture 영향:** 없음. GPS 관련 계약은 nullable/UNKNOWN을 반드시 지원해야 함.
> 

### 4) 사용자 원본은 immutable 외부 자산으로 취급

> **결론:** 사용자 기기에 있는 원본은 서비스가 수정·덮어쓰기·이동·rename·삭제하지 않고, 모든 가공 결과는 별도 사본에 생성하는 방향을 권장한다.
> 
> 
> **근거:** 조사 문서에서 사용자 원본 read-only와 `proxy/derived` 분리를 제안했고, SHA-256 동일성 검증도 수행했다.
> 
> **Architecture 영향:** 있음. `source`가 사용자 원본 reference인지 서버 관리 복사본인지 계약상 구분 필요.
> 

### 5) 업로드 전략과 Proxy profile은 아직 확정하지 않음

> **결론:** 전체 업로드/부분 업로드/proxy/로컬 처리/분할파일 활용 중 어느 하나를 Architecture에서 고정하지 않는다.
> 
> 
> **근거:** 현재 샘플은 약 6.79GB/h이며 ④ 로컬 처리 또는 ⑤ 분할파일 활용이 유력하다는 것은 담당자 가설일 뿐, 실제 전송시간·저장비용·API 비용이 아직 없다.
> 
> **Architecture 영향:** 있음. v4는 실행 위치가 바뀌어도 계약이 유지되는 형태여야 함.
> 

### 6) 실제 샘플의 복수 미디어 스트림을 Data Model에서 재검토

> **결론:** `VideoAsset`을 곧바로 “영상 1개”와 동일시하면 안 된다.
> 
> 
> **근거:** 실제 AVI 하나에서 전방 H.264 1920×1080/30fps, 후방 H.264 1280×720/30fps, 오디오가 함께 확인됐다.
> 
> **Architecture 영향:** 있음. 현재 `video_asset.codec`, `duration_sec` 같은 단일 필드만으로 복수 stream을 충분히 표현할 수 있는지 검토 필요.
> 

---

## 2. 확인된 기술적 제약

| 제약 | 근거 | Architecture/Data Contract 영향 |
| --- | --- | --- |
| 현재 실측 기종은 AVI, 약 60초/파일, 약 113.25MB/파일 | 실제 샘플 실측 | 대용량 처리와 파일 경계가 기본 전제가 되어야 함 |
| 현재 조건 기준 약 6.79GB/h | 실측값 기반 계산 | 전체 업로드를 기본 가정하기 어려움 |
| AVI 하나에 전방·후방·오디오가 함께 존재 | 실제 ffprobe/재생 확인 | `VideoAsset`과 media stream 관계 검토 필요 |
| `creation_time`이 없는 샘플 존재 | ffprobe 실측 | `FILE_METADATA`를 항상 존재하는 값으로 계약하면 안 됨 |
| 파일명은 `MDR_YYMMDD_HHMMSS.AVI` 형태로 관찰됨 | 현재 기종 샘플; 제조사 공통 규칙은 아님 | filename parser는 제조사/패턴별 확장 가능해야 함 |
| 화면 overlay timestamp 존재 | 실제 샘플 | overlay 시간은 `readout`, 파일 시간은 `recording`이라는 현재 분리와 일치 |
| GPS는 현재 샘플에서 확인되지 않음 | ffprobe/SD카드 조사 | GPS 필드는 optional/UNKNOWN이어야 함 |
| 분할파일 직접 활용 시 경계·중복 처리 필요 | 조사 결과 | `resolve_span()`을 공통 경계 해석기로 유지할 필요 |
| 원본과 분석/파생본은 물리 분리 가능하며 SHA-256 검증 가능 | 실제 checksum 실험 | immutable source/reference와 파생자산 구분 필요 |
| proxy 해상도/FPS는 아직 성능 실측 전 | 720p/15, 540p/10, 360p/5는 실험 후보일 뿐 | `profile` 구조는 필요하나 기본값은 미결 |
| RemoteCopy/derived/proxy 보관기간은 현재 확정 불가 | Runtime/Ops도 보관 일수를 정책·업로드 방식 확정 후 정하도록 함 | `expires_at` 필드는 가능하나 기본 수치 고정 금지 |

---

## 3. 현재 Module Architecture에 미치는 영향

### 그대로 유지 가능한 것

`recording`이 `VideoAsset`, `RecordingTimeline`, `TimeSourceCandidate`, `AnalysisSource`, `RemoteCopy`, `DerivedVideo`와 삭제 수명주기를 소유하는 구조는 조사 결과와 맞는다.

`resolve_span()`을 파일 경계를 해석하는 유일한 창구로 두는 것도 실제 분할파일·경계 문제 때문에 오히려 필요성이 확인됐다.

GPS parser와 reverse geocoder를 분리하는 구조도 유지 가능하다. 좌표 파싱은 파일 사실이고 주소 변환은 외부 서비스 결과이므로 실패 경계가 다르다. 현재 조사에서는 parser adapter와 Kakao/Naver geocoder 후보가 제안되어 있다.

### 수정 검토가 필요한 것

**현재 구조:** `video_asset`에 `codec`, `duration_sec`, `bytes`, `checksum`, `has_gps` 등 파일 단위 값이 존재한다.

**조사 결과:** 실제 AVI 하나에 전방·후방 video stream과 audio stream이 함께 존재한다.

**왜 검토가 필요한가:** `codec`, 해상도, fps, stream role 등의 의미가 파일 단위인지 stream 단위인지 모호해질 수 있다.

**영향받는 모듈:** `recording`, `search`, `readout`, `eval`.

**현재 구조:** 공개 함수는 `read_file_facts()` 등 9개이며 `readout`은 구간·프레임을 요청하는 관계로 표현돼 있다.

**조사 결과:** 9개 공개 함수에는 “특정 프레임 1장”을 명시적으로 반환하는 함수가 없다. Review Guide도 이 점을 질문으로 남겼다.

**왜 검토가 필요한가:** `read_file_facts()`는 파일 metadata 성격이고 픽셀 프레임 전달과 책임이 다르다.

**영향받는 모듈:** `recording`, `readout`, `search`.

**현재 구조:** `source/`를 읽기전용으로 두고 `purge_case()`가 흩어진 파일을 정리한다.

**조사 결과:** 사용자 원본 자체와 서버가 만든 source copy는 삭제 권한이 다르다. Runtime/Ops도 “서버 source copy가 있다면 삭제”라고 구분한다.

**왜 검토가 필요한가:** 사용자 원본 reference를 `purge_case()`가 물리 삭제하는 구조는 원본 보호 계약과 충돌한다.

**영향받는 모듈:** `recording`, `case`, Runtime/Ops.

### 판단 불가

- 5개 업로드 전략 중 최종 방식.
- Proxy 해상도/FPS/bitrate/segment 길이.
- S3/Object Storage를 어느 범위까지 쓸지.
- `RemoteCopy`를 provider API로 즉시 삭제할 수 있는지 또는 expiry만 기다리는지.
- H.265 및 1시간 이상 실제 E2E에서 최초 병목이 upload/network/ffmpeg/disk/external API 중 어디인지.
- 정확한 retention 기간.

Runtime/Ops 문서 역시 이 항목들을 recording 실측 이후 닫도록 남겨두고 있다.

---

## 4. 접합부 / Data Contract에 영향을 주는 내용

| 상대 모듈 | 방향 | 필요한/제공하는 정보 | 조사에서 확인된 제약 | 계약 단계에서 결정할 것 |
| --- | --- | --- | --- | --- |
| `search` | `recording → search` | `AssetSpan`, `AnalysisSource`, asset/reference, 시간 범위 | 영상은 여러 파일과 stream으로 구성될 수 있고 1h≈6.79GB | 실제 파일 객체를 넘길지 reference만 넘길지, stream 선택 정보를 누가 결정하는지, proxy profile을 계약에 포함할지 |
| `readout` | `recording → readout` | 원본 품질 구간 또는 특정 프레임 접근 경로 | 번호판/overlay 판독에는 실제 frame 접근 필요. 현재 공개 함수에 명시적 frame API 없음 | `AssetSpan`만 넘길지 `FrameRef`/frame extraction contract가 필요한지 |
| `evidence` | `recording → evidence` | `TimeSourceCandidate[]`, GPS observation, asset/derived refs | `creation_time`은 없을 수 있고 시각 후보가 충돌할 수 있음. GPS도 없을 수 있음 | source enum 확장 방식, UNKNOWN 표현, 후보 provenance 필드, timestamp 최종 판정은 evidence에 유지할지 |
| `case` | `recording ↔ case` | Timeline reference, requested time range, deletion trigger | `recording`만 timeline을 수정해야 하고 사용자 원본 삭제 금지 | `rebase_timeline`을 누가 요청할 수 있는지, case 삭제 시 reference 삭제와 managed file 삭제 구분 |
| geocoder adapter | `recording → geocoder` | GPS `lat/lon` observation | GPS 없는 경우 정상. 주소 변환 실패해도 좌표는 유지돼야 함 | 좌표 상태와 geocoder 실패 상태를 별도로 표현할지, 주소 결과 provenance |
| `eval` | `recording → eval` | timeline/resolve 결과, 실제 media fixture 처리 결과 | mock만으로는 경계·codec·stream 구조를 평가하기 어려움 | 어떤 recording 값/fixture를 locked test에 보존할지 |
| Runtime/Ops | `recording ↔ Worker/Storage` | source/proxy/remote/derived reference, bytes, expiry, deletion result | 긴 ffmpeg/proxy 작업은 HTTP 동기 처리에 부적합; storage/upload 전략 미결 | 어떤 작업을 Job으로 정의할지, purge 부분 성공 결과를 어떻게 저장할지, 실제 bytes/latency 측정 위치 |

현재 전체 계약 목록에서도 `RecordingTimeline / AssetSpan / TimeSourceCandidate`는 `recording`이 생산하고 여러 모듈이 소비하는 핵심 계약으로 정의돼 있다.

---

## 5. 열린 결정

| 결정할 문제 | 가능한 방향 | 현재 추천 | 추천 근거 | 누구와 확인해야 하는가 |
| --- | --- | --- | --- | --- |
| 원본 처리 방식 | 전체 / 필요한 파일 / proxy / 로컬 처리 / 분할파일 활용 | **미결 유지** | ④·⑤가 유력하나 비용·시간 수치 부족 | PM, `search`, Runtime/Ops |
| 복수 stream 표현 | `VideoAsset`에 포함 / 별도 stream 구조 | **별도 표현 필요성 검토** | 실제 AVI 한 파일에 전·후방+오디오 존재 | `search`, `readout`, PM/Architecture |
| 프레임 제공 계약 | `read_file_facts` 확장 / 별도 frame contract / consumer 직접 접근 | **별도 계약 검토** | file facts와 pixels 책임이 다름 | `readout`, `search` |
| GPS parser | NMEA/GPX/vendor adapter | **adapter 구조 제안** | 제조사별 포맷 상이 가능 | Architecture |
| reverse geocoder | Kakao / Naver 등 | **Kakao 우선 후보** | 현재 조사상 국내 주소·얇은 adapter와 적합 | PM/Architecture |
| retention 기본값 | 고정값 / 제품정책 데이터 | **현재 미결** | 업로드 전략과 개인정보 정책 의존 | PM, Runtime/Ops |
| RemoteCopy 삭제 | 즉시 API 삭제 / expiry | **provider 조사 후 결정** | provider 기능 의존 | `search` provider 담당, Runtime/Ops |
| gap reason | `MISSING_FILE`만 / 다중 reason | **확장 가능성 검토** | 녹화중단·손상·이벤트 분리 구분 가능성 | Architecture, `case` |

---

## 6. 충돌 / 상대 담당자 확인 필요

### A. 기존 Architecture와 충돌

**복수 stream vs 단일 `video_asset` 필드**

현재 데이터 모델은 `codec`, `duration_sec` 등을 단일값으로 둔다.  실제 파일은 복수 영상 stream을 포함한다. 따라서 “파일 1개 = 영상 stream 1개”라는 암묵적 가정이 있다면 수정 검토가 필요하다. `search`·`readout`과 함께 어떤 stream을 분석 대상으로 참조할지 확인해야 한다.

**`source` 삭제 의미**

Architecture의 “source를 purge한다”는 표현은 사용자 원본과 관리 복사본을 구분하지 않으면 read-only 계약과 충돌할 수 있다. 사용자 원본은 reference만 제거하고 서버 관리 copy만 삭제한다는 경계를 명시할 필요가 있다.

### B. 다른 모듈과 충돌 가능

**`readout`의 frame 접근**

Architecture 그림에서는 `readout → recording`에 “구간·프레임 요청”이 있으나 현재 공개 함수에는 frame 반환 경로가 명시되지 않았다.  `readout`이 어떤 단위의 참조를 필요로 하는지 계약 단계에서 공동 확인 필요.

**`search`의 proxy 요구사항**

Proxy profile은 사건 탐색 recall과 비용을 동시에 바꾸므로 `recording` 단독으로 확정할 수 없다. 현재 후보 값은 실험안이지 계약값이 아니다.

**`evidence`의 시각 source 범위**

`recording`은 파일 시각 후보만 생산하고 overlay OCR은 `readout`이 생산한다. `evidence`가 두 producer의 Observation을 동일 구조로 받을 수 있는지 확인 필요.

### C. Product/정책 결정 필요

- 사용자 파일/서버 사본의 실제 보관기간.
- Case 삭제 시 RemoteCopy를 어느 수준까지 “삭제 완료”로 표시할지.
- 사용자 원본을 서버에 복사하는 것이 기본인지 선택형인지.
- GPS가 없는 경우 사용자에게 어느 수준까지 위치 입력을 요구할지.
- 외부 AI로 전송 가능한 최대 영상 범위/개인정보 정책.

---

## 7. 후속 Data Contract에서 반드시 다룰 질문

1. `VideoAsset`은 컨테이너 파일 하나를 뜻하는가, 영상 stream 하나를 뜻하는가? 복수 stream이라면 stream index/role/codec/resolution/fps를 어떤 reference로 표현하는가?
2. `readout`이 프레임 1장을 얻을 때 `AssetSpan`만 받으면 충분한가, 별도의 `FrameRef` 또는 frame extraction API가 필요한가?
3. `TimeSourceCandidate.source`는 `FILE_METADATA`, `FILENAME`, vendor custom 등을 고정 enum으로 둘 것인가, 확장 가능한 source type으로 둘 것인가?
4. GPS가 없는 경우 `null`만 사용할 것인가, `Observation.status=UNKNOWN`처럼 “정보 없음”과 “파싱 실패”를 구분할 것인가?
5. `RecordingTimeline.gaps.reason`은 `MISSING_FILE` 외에 손상·녹화 중단 등의 원인을 표현해야 하는가?
6. 로컬 처리 전략을 선택해도 `resolve_span()`만 파일 경계를 해석하도록 어떻게 계약으로 강제할 것인가?
7. `ExternalSource`(사용자 원본)와 `ManagedSource`(서버 관리 복사본)를 서로 다른 reference/ownership으로 구분할 필요가 있는가?
8. `purge_case()`는 각 저장 위치의 삭제 성공/실패/expiry pending을 개별적으로 반환해야 하는가?
9. `AnalysisSource`가 proxy profile 및 source asset provenance를 반드시 포함해야 하는가?
10. recording 평가를 위해 codec, bytes, 처리 latency, proxy 생성시간, peak disk, 경계/gap 결과 중 무엇을 공통 실험 결과로 보존할 것인가?

---

## 8. 아키텍처 반영 우선순위

### 🔴 Architecture v4 전에 반드시 결정

- `VideoAsset`과 복수 media stream의 관계.
- 사용자 원본 reference와 서버 관리 source copy의 소유권/삭제 경계.
- `readout`의 frame 접근 경로가 recording 공개 계약에 필요한지.
- 로컬 처리 여부와 무관하게 `resolve_span()` 단일 책임을 유지할 수 있는 구조.

### 🟡 Data Contract 단계에서 결정

- `TimeSourceCandidate` source/provenance 구조.
- GPS `UNKNOWN` / parser `ERROR` 표현.
- `RecordingTimeline.gaps.reason`.
- `AssetSpan`에 필요한 asset/stream reference.
- `AnalysisSource`의 profile/provenance/expiry 필드.
- `DeletionReport`의 부분 성공·RemoteCopy pending 표현.
- recording 관련 평가용 bytes/latency/codec/contract-version 기록.

### 🟢 모듈 내부 Tech Spec에서 결정

- 실제 GPS parser 라이브러리(`pynmea2`, `gpxpy`, GPSBabel 등).
- Kakao/Naver geocoder 중 provider 세부 선택.
- ffmpeg command와 CRF/bitrate.
- SHA-256 계산 구현 방식.
- proxy 생성 내부 디렉터리/도구.
- retention scheduler의 구체적 구현.
- H.265 및 1시간 성능 최적화 방법.

---

## 9. 원본 자료 Reference

- **전남대학교 2팀 서비스 기획안 제출 1.3** — 제품 요구사항의 Source of Truth. 모듈 구조 v3도 1.3과 충돌 시 1.3을 우선한다고 명시한다.
- **대신고 — 소프트웨어 모듈 구조 설계 v3** — recording 소유권, 시간축·파일경계, source/proxy/derived, GPS/geocoder 경계의 근거.
- **대신고 — 모듈 기반 역할 배정안 v1** — Owner별 조사 → 모듈 고도화 → Data Contract 확정 순서를 정의.
- **현행 Technical Spec / 인터페이스 명세** — recording 공개 함수 9개와 계약 초안.
- **Technical Spec Review Guide** — frame 접근, time source, gap reason, resolve_span, expiry, RemoteCopy 삭제, H.265/대용량 E2E를 recording 검토 항목으로 지정.
- **블랙박스 Recording 파트 자료조사 정리** — 실제 AVI/H.264/용량/다중 stream/시각/GPS, 업로드 전략, proxy, checksum, GPS parser/geocoder 조사 근거.
- **대신고 백엔드 Runtime · Ops 고도화 설계 v1** — Worker/Job 기반 긴 작업 처리, source/proxy/RemoteCopy/derived 삭제 및 recording 실측 이후 닫아야 할 storage/upload 항목.

이 Memo 기준으로 PM/Architecture 단계에서 가장 먼저 봐야 할 것은 **① 복수 stream 데이터 모델, ② 원본 소유권/삭제 경계, ③ readout의 frame 접근 계약, ④ 업로드 위치가 바뀌어도 유지되는 `resolve_span()` 책임** 네 가지다. 나머지 GPS library나 ffmpeg 세부값은 이 네 가지보다 뒤에서 결정해도 전체 모듈 경계에는 큰 영향을 주지 않는다.