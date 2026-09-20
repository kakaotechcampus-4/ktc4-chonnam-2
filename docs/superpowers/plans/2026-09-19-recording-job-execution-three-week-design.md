# 정철원 3주 Recording·JobExecution 개발/고도화 설계

> 기준일: 2026-09-19  
> 상태: Brainstorming 승인 완료 · 구현 전  
> 대상: 정철원 (`recording`, `common/runtime`의 `JobExecution` 구현)  
> 범위: 약 3주의 집중 개발 기간과 11월 11일 최종 제출 전 후속 단계

## 1. 목적 및 배경

Canonical Contract, 7개 Mock Scenario, 공개 입출력을 연결한 1차 Mock E2E는 완료됐다. 다음 단계의 목적은 Mock 결과를 확장하는 것이 아니라 실제 Recording을 현재 public interface에 통과시켜 실제 Search·Readout과 연결하는 것이다.

프로젝트 전체 목표 흐름은 다음과 같다.

```text
실제 Recording
→ 실제 Search
→ 후보 선택
→ 실제 Readout
→ Evidence
→ CaseView
→ Web
```

이 문서는 위 전체 흐름을 다시 설계하지 않는다. 전체 흐름에서 정철원이 소유한 Recording과 `JobExecution` 구현을 월요일 최소 Baseline, 실제 데이터 관찰, W7 Risk Burn-down, W8 집중 개발 종료선까지 어떻게 완성할지를 정의한다.

대표 영상에는 사건·번호판·시각 Ground Truth가 없다. 사건 위치와 정답도 알려져 있지 않다. 따라서 월요일 Real E2E는 정확도 Benchmark가 아니라 **GT 없는 실제 배관 E2E**다. 실제 파일 접근, 계약 객체 생성, 실제 Search·Readout 호출, 실패·UNKNOWN·abstain 전달, 실제 CaseView의 Web 표시를 검증한다. Search Top-1은 정답이 아니라 명시적인 `UNVERIFIED` 후보로 사용한다.

## 2. 정철원 책임 범위 / 비책임 범위

### 2.1 책임 범위

| 영역 | 정철원 책임 |
| --- | --- |
| Source 등록 | 실제 원본 파일 등록, `SourceAsset`·`MediaStream` 생성 |
| Metadata | 실제 파일 크기·duration·stream 정보 probe |
| Timeline | 신뢰 가능한 anchor 또는 relative-only Timeline 생성·revision 보존 |
| Asset resolve | opaque ref를 내부 locator로 해석하는 registry |
| AnalysisSource | 원본 media를 실제 분석 입력으로 제공하는 최소 capability |
| IncidentClip | 선택된 Top-1 후보 1건의 실제 clip materialization |
| Frame | 원본 기준 canonical `FrameRef` 발급과 on-demand frame 접근 |
| Runtime | `JobExecution` 상태 전이·attempt·produced·failure·usage ref 구현 |
| Integration handoff | 동기 Python 공개 함수, consumer 예제, 실패 규칙 제공 |
| Observability | 실행별 JSON 리포트와 내부 상태 전이 로그 |
| Verification | contract/unit test, opt-in 실제 영상 smoke, CI media smoke, Recording Benchmark |

### 2.2 비책임 범위

| 영역 | 비책임 사유 |
| --- | --- |
| 전체 로컬 통합 실행기 조립 | 최종 Owner는 김준영·유소연 중 팀에서 확정 |
| Evidence·CaseView 정책 | 각 계약 Owner 책임 |
| Web 연결과 화면 정책 | web/통합 Owner 책임 |
| Search·OCR 정확도 | search/readout 책임. Recording은 실제 입력 경로를 보장 |
| Top-1의 정답성 | GT가 없으므로 `UNVERIFIED`로만 사용 |
| 월요일 정식 HTTP API·Worker | 동기 Python 공개 호출로 대체 가능 |
| 월요일 DB Queue·분산 Worker | `JobExecution` lifecycle과 교체 경계까지만 구현 |
| 월요일 `REPORT_VIDEO`·`PLATE_IMAGE` | 최종 신고용 파생 자산은 현재 E2E 완료 조건에서 제외 |
| 전체 위반 유형·모든 edge case | 대표 실제 배관 1건이 우선 |

## 3. 기본 개발 전략

**E2E 경로 우선 + 관측 결과에 따른 고도화 + 최소 Runtime 교체 경계 유지**를 기본 전략으로 한다.

1. 실제 데이터가 통과하는 가장 얇은 vertical slice를 먼저 만든다.
2. Canonical Contract와 현재 public interface는 유지한다.
3. 원본 경로, provider locator, 인증정보는 public Contract에 노출하지 않는다.
4. 실패를 Mock, 가짜 ref, 가짜 datetime, 원본 전체 영상 대체로 숨기지 않는다.
5. baseline을 측정한 뒤 실제 blocker와 품질 문제만 고도화 대상으로 승격한다.
6. in-memory/local adapter를 사용하더라도 registry·media adapter·store 경계를 분리해 후속 DB/Storage/Worker 교체 시 핵심 로직을 다시 작성하지 않는다.

기능 구현과 품질 고도화의 경계는 다음과 같다.

| 영역 | 기능 구현 완료 | 품질 고도화 |
| --- | --- | --- |
| Source 등록 | 실제 파일에서 canonical 객체 생성 | 중복 등록 탐지, 대규모 파일 최적화, container 확대 |
| Timeline | 실제 duration과 확인된 anchor로 생성 | 자동 anchor 판독·검증, stitching, drift 보정 |
| AnalysisSource | 원본 기반 실제 입력 제공 | proxy/profile, provider별 최적화, 재사용 |
| IncidentClip | 선택 후보 1건 실제 materialization | padding, codec, 경계 정밀도, 복수 파일 clip |
| FrameRef | 요청 위치의 canonical frame 반환 | batch extraction, cache, decode 성능 |
| JobExecution | 올바른 lifecycle과 산출물 참조 | persistence, retry, heartbeat·lease, 분산 Worker |
| Observability | 실행별 실패 단계와 시간을 기록 | 중앙 logging·metrics·alert |

## 4. 월요일 최소 Baseline

### 4.1 필수 범위

- 사건 구간이 단일 파일 안에 포함된 대표 영상을 우선 선택한다.
- 실제 원본 영상을 등록한다.
- `ffprobe` 등 실제 도구로 metadata와 stream을 조사한다.
- `SourceAsset`, `MediaStream`, `RecordingTimeline`을 생성한다.
- 파일명과 화면 overlay를 사람이 확인한 결과를 anchor 입력으로 받는다.
- 두 값이 일치하고 신뢰 가능할 때만 absolute anchor를 사용한다.
- 불일치·파싱 실패·신뢰 부족이면 `USABLE_RELATIVE_ONLY`로 fallback한다.
- 가짜 날짜나 추정 absolute datetime을 만들지 않는다.
- Search에 원본 media를 제공하는 최소 `AnalysisSource`를 생성한다.
- 실제 Search 결과가 0건이면 이를 기록하고 provider 제한을 만족하는 다른 실제 영상으로 재시도한다.
- 후보를 인위적으로 만들거나 Mock 후보로 대체하지 않는다.
- 후보가 있으면 Top-1을 `UNVERIFIED`로 선택한다.
- 선택 후보 1건에 대해서만 실제 `IncidentClip`을 생성한다.
- Plate와 Overlay Readout이 사용할 canonical `FrameRef`와 frame 접근을 제공한다.
- `COARSE_SEARCH`, `PLATE_READ`, `OVERLAY_TIME_READ` 실행을 `JobExecution` lifecycle에 연결한다.
- 실제 결과에서 생성된 CaseView가 Web에 표시될 수 있도록 integration Owner에게 공개 호출 경계를 전달한다.

### 4.2 월요일에 제외하는 범위

- Search용 저해상도·무음 proxy
- 후보 전체의 clip 생성
- 자동 overlay OCR을 통한 anchor 신뢰도 판정
- 대표 데이터가 요구하지 않는 multi-file Timeline stitching
- `REPORT_VIDEO`·`PLATE_IMAGE` export
- 정식 DB·Queue·Worker·HTTP 배선
- 정식 retention·자동 purge
- 성능 최적화와 전체 codec 지원

### 4.3 월요일 완료 증거

- 실제 파일을 사용한 Source/Timeline/AnalysisSource 계약 객체
- 실제 생성된 IncidentClip 1건
- 실제 추출된 frame과 canonical FrameRef
- contract validation 결과
- `JobExecution` 상태·산출물 참조
- 실행별 JSON 리포트
- integration Owner가 consumer 예제로 재현한 결과
- 전체 팀 기준으로 실제 CaseView가 브라우저에 표시된 결과

## 5. Recording 데이터 흐름

```text
[내부 설정의 실제 파일 경로]
        │
        ▼
원본 등록 ──→ SourceAsset + MediaStream[]
        │              │
        │              └─ opaque ref → 내부 locator registry
        ▼
metadata probe
        │
        ▼
anchor 입력 검증 ── 신뢰 가능 ──→ absolute RecordingTimeline
        │
        └─ 불일치/불확실 ──────→ USABLE_RELATIVE_ONLY Timeline
        │
        ▼
resolve_span
        │
        ▼
원본 기반 AnalysisSource ──→ 실제 Search
                                  │
                                  ▼
                         CandidateEvent Top-1
                           (UNVERIFIED 선택)
                                  │
                                  ▼
                         resolve_span + clamp
                                  │
                                  ▼
                       IncidentClip 실제 생성
                                  │
                                  ▼
                resolve_frame/read_frame on demand
                                  │
                                  ▼
                       실제 Plate/Overlay Readout
```

### 5.1 원본 등록과 registry

- 사용자 원본은 read-only로 취급한다.
- 원본을 overwrite, rename, move, delete하지 않는다.
- public 객체에는 local path를 넣지 않는다.
- 내부 asset registry가 opaque ref와 local locator를 연결한다.
- 월요일에는 memory 또는 로컬 실행 전용 저장 방식을 허용한다.
- 실행마다 새 opaque ref를 발급할 수 있다.
- 한 실행 안에서는 ref와 provenance가 일관되어야 한다.
- 동일 파일 ref 재사용·중복 제거 정책은 Benchmark 전 고도화 대상으로 둔다.

### 5.2 Timeline과 anchor

- 파일명과 overlay의 촬영 시각은 사람이 한 번 확인한다.
- 확인된 값은 명시적 설정 입력으로 전달한다.
- Recording은 입력 형식과 영상 범위 정합을 검증한다.
- 수동 입력이라는 provenance와 absolute/relative 선택 근거는 실행 리포트에 남긴다.
- 신뢰할 수 없으면 정상적으로 relative-only를 반환한다.

### 5.3 AnalysisSource

- `AnalysisSource`는 반드시 proxy일 필요가 없다.
- 월요일에는 원본 또는 원본 구간을 실제 분석 입력으로 연다.
- `profile_ref`는 non-null opaque ref로 유지한다.
- Search adapter가 실제 경로를 필요로 하면 내부 resolver를 통해 얻고, public Contract에는 노출하지 않는다.
- 정확한 원본/고화질 profile identity와 보장 속성은 Open Issue 1이 해소된 뒤 사용한다.

### 5.4 IncidentClip

- Top-1 후보 1건만 materialize한다.
- 요청 범위는 선택된 `CandidateEvent.span`을 그대로 사용한다.
- 임의 padding을 추가하지 않는다.
- Timeline 경계를 넘을 때만 유효 구간으로 clamp한다.
- `requested_range`와 실제 `timeline_range`를 구분해 보존한다.
- 빠른 stream copy보다 요청 경계와 호환성을 우선하는 재인코딩을 기본으로 한다.
- 실제 codec/container 설정은 입력과 Readout 환경 확인 후 Tech Spec 구현값으로 정하되, 실행 리포트에 기록한다.
- 생성 후 파일 존재·decode 가능성·실제 범위를 검증한 뒤에만 `AVAILABLE`과 ref를 반환한다.
- 사전 생성 실패는 기존 `INCIDENT_CLIP_BUILD_FAILED`로 기록하고 Readout Job을 발주하지 않는다.

### 5.5 FrameRef와 frame access

- Readout이 locator로 필요한 frame을 요청한다.
- Recording은 원본 `MediaStream` 기준 canonical frame을 선택한다.
- proxy 기준 FrameRef를 발급하지 않는다.
- 전체 프레임을 미리 추출하지 않고 요청된 frame만 on-demand 생성한다.
- 추출 결과는 실행 작업 디렉터리에 캐시할 수 있다.
- 같은 실행에서 같은 FrameRef는 같은 원본 위치를 재참조해야 한다.

### 5.6 Run workspace와 cleanup

- 실행마다 격리 작업 디렉터리를 사용한다.
- IncidentClip, frame cache, 실행 리포트를 한 실행 단위로 모은다.
- E2E 종료 전 자동 삭제하지 않는다.
- E2E 종료 후 명시적 cleanup으로 제거한다.
- 사용자 원본은 어떤 cleanup에서도 대상이 아니다.
- 정식 TTL·retention·managed storage lifecycle은 후속 범위다.

## 6. JobExecution 연결 방식

### 6.1 실행 모델

월요일에는 실제 Queue나 비동기 Worker 없이 로컬 통합 실행기에서 동기 호출해도 된다. 단, 각 실행은 Canonical `JobExecution` lifecycle을 따라야 한다.

```text
QUEUED → RUNNING → SUCCEEDED
                 → FAILED
```

`STALE`·`CANCELLED`·재시도 규칙은 기존 계약을 유지한다. 월요일 실제 경로에서 반드시 발생시킬 필요는 없지만 contract/unit test로 검증한다.

### 6.2 월요일 추적 대상

| Job kind | 실행 대상 | 성공 시 produced |
| --- | --- | --- |
| `COARSE_SEARCH` | 실제 Search 호출 | 실제 `analysis_run` ref |
| `PLATE_READ` | 실제 번호판 판독 호출 | 실제 `readout_run` ref 1건 |
| `OVERLAY_TIME_READ` | 실제 화면 시각 판독 호출 | 실제 `readout_run` ref 1건 |

판독값을 확정하지 못한 abstain·UNKNOWN은 정상적인 domain 결과일 수 있다. public 함수가 정상 완료해 계약 결과를 생성했다면 값 부재만으로 `JobExecution=FAILED`로 바꾸지 않는다.

### 6.3 Clip 준비 실패 경계

- IncidentClip이 Readout 발주 전에 실패하면 capability failure다.
- `INCIDENT_CLIP_BUILD_FAILED`를 실행 리포트에 기록한다.
- 존재하지 않는 Readout Job의 `JobExecution=FAILED`를 만들지 않는다.
- 발주 후 입력이 사라지거나 frame 접근이 실패한 경우는 해당 Readout 실행 실패 규칙을 따른다.

### 6.4 저장과 전이 기록

- Canonical `JobExecution` 객체에는 현재 계약 필드만 유지한다.
- 디버깅용 상태 전이는 별도 내부 로그에 append-only로 기록한다.
- queue 대기와 실행 시간을 구분할 수 있도록 각 전이 시각을 남긴다.
- W8까지 `JobExecutionStore` interface를 분리한다.
- in-memory adapter를 유지하고 로컬 영속 adapter 또는 실행 결과 저장 방식을 제공한다.
- 실제 DB Queue, heartbeat, lease, worker 사망 감지는 배포 단계 후보로 남긴다.
- `STALE`·attempt 증가·`CANCELLED` 부분 산출물 규칙은 결정론적 테스트와 수동 시뮬레이션으로 검증한다.

## 7. 내부 아키텍처

| 구성요소 | 책임 | 후속 교체 대상 |
| --- | --- | --- |
| Contract models | Canonical 입력·출력 파싱과 불변조건 검증 | 안정적으로 유지 |
| Recording application service | 등록→Timeline→AnalysisSource→Clip→Frame 조정 | public interface 유지 |
| Asset registry | opaque ref와 내부 locator 연결 | memory/local → DB/storage |
| Media probe adapter | metadata·stream 조사 | ffprobe → 대체 probe 가능 |
| Media transform adapter | IncidentClip·frame 생성 | ffmpeg 설정/구현 교체 가능 |
| Timeline/anchor policy | absolute/relative 결정과 revision | 자동 anchor 검증으로 확장 |
| Run workspace | 산출물·cache·리포트 격리 | local → managed storage |
| JobExecution store | 상태 전이·attempt·produced 보존 | memory/local → DB Queue |
| Observability | 시간·실패·media 사실 기록 | 중앙 logging/metrics로 확장 |

구현 규칙:

1. public Contract와 내부 locator를 분리한다.
2. subprocess 실행과 계약 조립을 분리한다.
3. 외부 도구 오류를 Consumer에게 그대로 노출하지 않고 안정적인 capability failure로 변환한다.
4. 실제 bytes 생성과 검증이 끝난 뒤 canonical 객체를 발행한다.
5. 자산 lifecycle과 사용자 원본 lifecycle을 분리한다.
6. `JobExecution`은 산출물의 의미를 판단하지 않고 실행 상태와 참조만 기록한다.
7. 실행 리포트는 public Contract를 변경하지 않는 진단 산출물이다.

## 8. 실패 분류 및 Observability

### 8.1 실패·상태 분류

| 구간 | 구분할 상태·실패 | 필수 증거 |
| --- | --- | --- |
| 원본 등록 | 파일 없음, 접근 불가, 읽기 실패, 원본 변경 감지 | dataset ID, 크기, 수정 정보, availability |
| probe | container 인식 실패, stream 없음/불명, 일부 stream decode 실패 | 도구 종료 상태, stream별 결과, 소요시간 |
| anchor | 파일명 파싱 실패, overlay 불일치, 신뢰 부족 | 후보값, 비교 결과, 선택 근거 |
| Timeline | duration 불명, stream 길이 불일치, 범위 밖, gap | status, revision, missing range, 실제 범위 |
| AnalysisSource | 원본 열기 실패, provider 크기·codec 제한, profile 불일치 | source/profile ref, 실패 단계, 시간 |
| IncidentClip | span 해석 실패, clamp, 재인코딩 실패, 빈 출력 | 요청/실제 범위, 설정, 시간, 크기 |
| FrameRef | locator 오류, 범위 밖, decode 실패, 재현 실패 | locator, source offset, 시간, cache 여부 |
| JobExecution | 잘못된 전이, produced 누락, 실행 실패, 재시도 | 전이 시각, attempt, produced, failure, usage ref |
| 자원 | 작업공간 부족, subprocess timeout, 비정상 종료 | 공간 사용량, 실행시간, 종료 정보 |

### 8.2 판정 원칙

- relative-only fallback은 정상 상태이지 실패가 아니다.
- 후보·번호판·화면 시각을 찾지 못한 상태와 실행 실패를 구분한다.
- 계약 위반과 참조 단절은 즉시 수정 대상이다.
- 신규 machine-readable code를 임의로 만들지 않는다.
- 기존 canonical code를 우선 사용하고 새 값이 필요하면 소유 문서/registry에 먼저 등재한다.
- 원본 경로, 인증정보, provider 내부 locator는 공유·커밋되는 리포트에서 제외한다.

### 8.3 실행별 JSON 리포트

최소 기록 항목:

- run 식별자와 익명 dataset ID
- 입력 fingerprint와 도구 버전
- 원본 크기·재생시간·stream 기술 정보
- probe 시간
- Timeline status·revision·anchor 선택 근거
- AnalysisSource profile/ref와 접근 결과
- clip 요청 범위·실제 범위·설정·시간·크기
- frame locator·source offset·추출 시간·cache 여부
- JobExecution 전이와 produced/failure/usage refs
- 실패 단계와 내부 진단 요약
- 작업공간 사용량

## 9. CI / 테스트 전략

### 9.1 테스트 층

| 층 | 목적 | 입력 | 기본 실행 여부 |
| --- | --- | --- | --- |
| Unit | policy·모델·상태 전이 검증 | 작은 객체/fixture | 항상 |
| Contract | Canonical schema·불변조건·ref 검증 | 공용 fixture | 항상 |
| Adapter | probe/transform 오류 변환 검증 | 생성 media·통제된 실패 | 항상 |
| CI media smoke | 실제 media toolchain 회귀 검출 | CI가 실행 중 생성한 짧은 영상 | GitHub Actions |
| Real smoke | 실제 영상 한 건의 end-to-end Recording 검증 | Git 밖의 실제 영상 | opt-in |
| Benchmark | 개선 전후 품질·성능 비교 | 고정 실제 영상 세트 | 명시적 실행 |

### 9.2 GitHub Actions 필수 범위

GitHub Actions는 테스트 명령을 선언만 하지 않고 실제로 실행해야 한다.

- Python unit/contract test
- 기존 계약·Mock·boundary 검증
- 실행 중 테스트 영상 생성
- 실제 `ffprobe`
- Timeline 생성
- IncidentClip 재인코딩
- frame 추출
- 산출물 계약·참조 검증

대용량 실제 영상과 개인정보 포함 자료는 Git에 넣지 않는다. CI media smoke는 실제 media 처리 경로의 회귀를 찾지만 실제 도로 영상 품질을 대표하지 않는다.

### 9.3 Opt-in Real smoke

- 환경 설정으로 실제 영상 경로를 전달한다.
- 입력이 없으면 명시적으로 skip한다.
- CI 성공을 실제 데이터 E2E 성공으로 대체하지 않는다.
- 월요일 완료 증거에는 opt-in 실제 실행 결과가 별도로 필요하다.

## 10. Real Recording Benchmark

### 10.1 목적

사건 GT 없이도 Recording의 구조적 정확성, 재현성, 호환성, 처리시간과 자원 사용을 비교한다. Search 탐지율·번호판 정확도·시각 정확도를 Recording 성과로 주장하지 않는다.

### 10.2 데이터 관리

- 실제 영상은 Git 밖에 보관한다.
- Git에는 익명 dataset ID, fingerprint, 기술 metadata, 기대 검증값만 담은 manifest를 둔다.
- local path·개인정보·인증정보는 manifest에 넣지 않는다.
- 같은 fingerprint와 실행 조건으로 개선 전후를 비교한다.

### 10.3 입력 범주

- 정상 단일 파일
- absolute anchor를 신뢰할 수 없어 relative-only가 되는 파일
- 요청 구간이 Timeline 경계에 걸리는 입력
- probe 또는 decode가 실패하는 손상·비호환 입력
- multi-file 입력은 실제 필요와 데이터 가용성이 확인될 때 확장

### 10.4 비교 항목

- 계약·참조 검증 통과 여부
- 사용자 원본 불변 여부
- probe·Timeline 결과 재현성
- 요청 범위 대비 실제 clip 범위
- 동일 locator의 frame 재현성
- 단계별 처리시간
- 생성 파일 크기와 작업공간 사용량
- 성공·fallback·실패 분포
- failure와 실제 실패 단계의 일치

고정 성능 목표는 baseline 측정 전에 만들지 않는다. 월요일 실제 실행값을 baseline으로 저장한 뒤 동일 환경의 전후 차이와 회귀 기준을 정한다. 정확성을 훼손하는 성능 개선은 채택하지 않는다.

## 11. W7 Risk Burn-down

### 11.1 우선순위 규칙

| 순위 | 제거할 위험 |
| --- | --- |
| 1 | 계약·ref·provenance 무결성 위반 |
| 2 | 전체 E2E를 중단시키는 media/clip/frame 실패 |
| 3 | 정상처럼 보이는 잘못된 Timeline·clip·frame |
| 4 | Search·Readout 품질을 제한하는 호환성·경계 문제 |
| 5 | 반복 실행 시간·disk·중복 작업 문제 |
| 6 | 배포 편의와 구조 개선 |

### 11.2 조건부 승격

| 관찰 결과 | 승격할 고도화 |
| --- | --- |
| 원본 업로드 제한·시간·codec이 blocker | proxy/profile 최소 구현 |
| 대표 데이터가 파일 경계를 통과 | multi-file stitching |
| 반복 probe/clip/frame 비용이 큼 | cache·재사용 정책 |
| clip/frame 경계가 Readout을 방해 | 추출 정밀도·padding 실험 |
| 실패 원인 구분이 어려움 | observability·failure taxonomy |
| 실행 복구 문제가 나타남 | JobExecution persistence·retry |

관측되지 않은 고도화는 후보로만 유지한다. baseline 동결 전 성능 고도화를 시작하지 않는다.

## 12. Gate 기반 3주 구현 우선순위

| Gate | 결과 | 통과 증거 |
| --- | --- | --- |
| G0 입력·합의 | 대표 영상, 수동 anchor, profile 합의, media tool 환경 | fingerprint와 cross-owner 합의 기록 |
| G1 실제 Recording | 등록·probe·Timeline·AnalysisSource 실제 동작 | contract test와 실행 리포트 |
| G2 Readout 경계 | Top-1 IncidentClip·FrameRef 실제 생성 | clip/frame 재생·참조 검증 |
| G3 Runtime handoff | Search·Plate·Overlay 실행 lifecycle 연결 | 상태 전이·produced ref 검증 |
| G4 통합 재현 | 통합 Owner가 공개 예제로 사용 | 타 담당자 환경 재현 결과 |
| G5 Baseline 동결 | GT 없는 Real E2E 측정값 보존 | 재실행 가능한 bundle |
| G6 Risk burn-down | 가장 큰 실제 위험 개선 | 동일 Benchmark 전후 비교 |
| G7 안정화 | adapter 경계·실패 회귀·CI 정리 | GitHub Actions와 전체 회귀 통과 |

병행 원칙:

- CI 골격과 unit/contract test는 실제 adapter 구현과 병행할 수 있다.
- `JobExecutionStore` 경계는 media adapter와 병행할 수 있다.
- proxy·stitching·성능 고도화는 blocker 또는 baseline 증거 없이 착수하지 않는다.
- 배포 준비는 핵심 경계를 흔들지 않는다면 W8 이전에도 시작할 수 있다.

## 13. De-scope 규칙

### 13.1 제거하면 안 되는 것

- 원본 불변성과 내부 path 격리
- 실제 probe와 Timeline
- relative-only fallback
- 원본 기반 AnalysisSource
- Top-1 IncidentClip 1건
- canonical FrameRef와 frame 접근
- JobExecution lifecycle
- 계약·ref 검증
- 실행 리포트와 실패 기록
- CI media smoke
- integration consumer 예제

### 13.2 de-scope 순서

1. 최종 `REPORT_VIDEO`·`PLATE_IMAGE` export
2. 추가 위반 유형과 추가 실제 E2E Scenario
3. 자동 overlay anchor 판독
4. 대표 데이터가 요구하지 않는 multi-file stitching
5. 대체 가능한 영상이 있으면 proxy
6. 적극적인 cache·성능 최적화
7. 정식 retention·자동 purge
8. 실제 heartbeat·lease·분산 Worker
9. DB Queue와 배포용 storage adapter

### 13.3 blocker 승격 원칙

- 후순위 항목도 실제 E2E를 막는다는 증거가 생기면 최소 범위로 승격한다.
- 영상이 provider 크기·codec 제한에 걸리면 먼저 제한을 만족하는 다른 실제 영상을 선택한다.
- 사용할 수 있는 영상이 모두 제한에 걸릴 때만 최소 proxy를 blocker 대응으로 승격한다.
- stitching은 대표 데이터가 실제 파일 경계를 걸칠 때만 월요일 범위로 승격한다.
- 승격 시 원래의 전체 고도화 범위가 아니라 E2E blocker를 제거하는 최소 구현만 수행한다.

## 14. 단계별 Definition of Done

| 단계 | Definition of Done |
| --- | --- |
| Capability 준비 | 실제 영상으로 SourceAsset·MediaStream·Timeline·AnalysisSource·IncidentClip·FrameRef가 생성되고 계약 검증을 통과 |
| 통합 handoff | 김준영 또는 유소연이 Recording 내부 구현을 몰라도 consumer 예제로 같은 흐름을 재현 |
| 월요일 Real E2E | GT 없는 실제 입력이 Web까지 도달하고 실행·fallback·실패가 기록됨 |
| Baseline 동결 | 설정·dataset fingerprint·도구 버전·측정값이 재현 가능한 리포트로 보존 |
| W7 고도화 | 가장 큰 실제 위험을 제거하고 동일 Benchmark에서 전후 차이를 확인 |
| W8 안정화 | 핵심 기능·고도화·비교 검증이 사실상 완료되고 CI가 자동 회귀를 검출 |
| 최종 제출 | 선택된 배포 환경 E2E, 운영 설정, 회귀 검증, 데모·발표 증거를 11월 11일 기준으로 확인 |

## 15. Cross-owner dependency / blocker

| 상대 | 정철원 제공 | 상대 제공 | blocker 조건 |
| --- | --- | --- | --- |
| Search / 서어진 | AnalysisSource·실제 media 접근 경계 | provider 연결, Candidate span·Timeline revision | 원본 접근 불가, 후보 span 계약 불일치 |
| Readout / 신유민 | IncidentClip·FrameRef·frame bytes | 실제 Plate·Overlay 호출, locator 요청 | clip/frame 소비 경로 부재 |
| Case·통합 / 유소연 또는 김준영 | capability·JobExecution·예제 | JobRecord, 호출 순서, 결과 반영, CaseView 연결 | 통합 Owner 미확정 또는 입력 미합의 |
| Evidence / 김준영 | provenance·asset facts 복원 가능한 ref | UNKNOWN·abstain 정상 소비 | 값 부재를 pipeline 실패로 처리 |
| Web / 신유민 | 직접 제공 없음 | 실제 CaseView 자동 로딩 | 정적 fixture만 표시 |
| CI | 도구 요구사항과 smoke test | Actions 환경의 ffmpeg/ffprobe 실행 | workflow에서 실제 test 미실행 |
| 데이터 준비 | 입력 검증·fingerprint | 실제 대표 영상과 수동 anchor 확인 | provider-compatible 영상 부재 |

## 16. W8 종료선

W8은 최종 제출 또는 배포 완료 시점이 아니다. 다음 집중 개발 종료선이다.

- 핵심 Recording capability가 실제 데이터에서 안정적으로 동작한다.
- JobExecution lifecycle과 저장소 교체 경계가 정리돼 있다.
- Real E2E에서 수집한 주요 blocker와 silent correctness 위험이 제거됐다.
- 동일 Real Recording Benchmark의 개선 전후 자료가 있다.
- GitHub Actions에서 실제 unit/contract/media smoke가 실행된다.
- 알려진 실패와 미지원 범위가 문서화돼 있다.
- 이후에는 대규모 기능 개발보다 배포·안정화·발표 준비 중심으로 이동할 수 있다.

배포 준비 또는 일부 배포 작업은 W8 이전에 시작할 수 있다. 실제 배포 시점은 이 문서에서 확정하지 않는다.

## 17. 11월 11일 최종 제출 단계

W8 이후부터 11월 11일 사이에는 프로젝트 일정과 배포 결정에 따라 다음을 별도 완료한다.

- 선택된 배포 환경 구성
- 배포 환경에서 실제 E2E 검증
- config·secret·storage 경계 검토
- 배포 환경의 ffmpeg/codec 의존성 검증
- 최종 안정화와 회귀 테스트
- 대표 실제 데이터 데모
- Benchmark 개선 전후 결과 정리
- 알려진 한계와 실패 대응 설명
- 실행·장애 진단·데모 절차 문서
- 최종 발표자료와 시연 준비

이 단계의 세부 일정과 배포 방식은 아직 미확정이다.

## 18. Open Issues / Blocking Dependencies

### OI-1. 원본/고화질 AnalysisSource profile 합의

**상태:** 미확정 · 월요일 전 차단 합의  
**참여:** 정철원(recording) · 서어진(search) · 신유민(readout)

최소 결정 항목:

- 의미: 원본 또는 판독 가능한 고화질 입력
- 월요일 실제 처리: 원본 media 사용
- video/audio 유지 여부
- 같은 조건의 AnalysisSource 재사용 기준
- opaque `profile_ref`와 registry entry
- Consumer가 ref 문자열을 파싱하지 않는다는 재확인

저해상도·무음 proxy의 해상도·fps·분할값은 이 합의에 포함하지 않는다. 정철원이 canonical identity를 단독으로 만들지 않는다.

### OI-2. 전체 로컬 통합 실행기 Owner 확정

**상태:** 미확정 · 통합 진행 전 확정 필요  
**후보:** 김준영 또는 유소연

정철원은 Recording adapter와 `JobExecution` lifecycle, consumer 예제를 제공한다. 전체 모듈 호출 순서, Evidence/CaseView 연결, Web 전달을 조립하는 책임은 맡지 않는다. Owner가 늦게 확정되더라도 정철원의 범위가 전체 실행기 구현으로 자동 확대되지 않는다.

## 19. 최종 체크리스트

### G0 — 입력·합의

- [ ] 대표 실제 영상이 준비됐다.
- [ ] 영상 fingerprint와 비공개 locator를 기록했다.
- [ ] 파일명과 overlay 시각을 사람이 대조했다.
- [ ] absolute 또는 relative-only 선택 근거를 기록했다.
- [ ] 원본/고화질 AnalysisSource profile을 3자가 합의했다.
- [ ] 전체 로컬 통합 실행기 Owner가 확정됐다.
- [ ] ffmpeg/ffprobe 실행 환경을 확인했다.

### G1 — 실제 Recording

- [ ] 실제 파일 등록이 `SourceAsset`·`MediaStream[]`을 반환한다.
- [ ] metadata·stream probe가 실제 값을 반환한다.
- [ ] 신뢰할 수 없는 anchor가 `USABLE_RELATIVE_ONLY`로 fallback한다.
- [ ] public Contract에 local path가 노출되지 않는다.
- [ ] 내부 asset registry가 opaque ref를 해석한다.
- [ ] 원본 기반 AnalysisSource가 실제 Search에 열리는 입력을 제공한다.

### G2 — Clip·Frame

- [ ] Top-1 `UNVERIFIED` 후보 1건에서 IncidentClip을 생성한다.
- [ ] 요청 범위와 실제 범위를 구분해 기록한다.
- [ ] clip 생성 결과를 decode·범위 검증한 뒤 발행한다.
- [ ] clip 준비 실패 시 Readout Job을 발주하지 않는다.
- [ ] `resolve_frame`·`read_frame`이 원본 기준 FrameRef를 제공한다.
- [ ] on-demand frame cache가 사용자 원본과 분리돼 있다.

### G3 — JobExecution

- [ ] `COARSE_SEARCH`가 canonical lifecycle을 남긴다.
- [ ] `PLATE_READ`가 실행 1회당 ReadoutRun ref 1건을 남긴다.
- [ ] `OVERLAY_TIME_READ`가 실행 1회당 ReadoutRun ref 1건을 남긴다.
- [ ] abstain·UNKNOWN과 실행 실패를 구분한다.
- [ ] 상태 전이 시각이 내부 append-only 로그에 남는다.
- [ ] `STALE`·attempt·`CANCELLED` 규칙을 테스트한다.

### G4 — Handoff·Real E2E

- [ ] 동기 Python public API를 제공한다.
- [ ] consumer 예제에 정상·실패 경계를 포함한다.
- [ ] 통합 Owner가 내부 구현 없이 실제 입력으로 재현했다.
- [ ] 실제 Search 0건 시 다른 실제 영상으로 재시도하고 기록했다.
- [ ] Mock/가짜 후보/가짜 ref로 fallback하지 않았다.
- [ ] 전체 팀 기준 실제 CaseView가 Web에 표시됐다.

### G5 — Observability·Baseline

- [ ] 실행별 JSON 리포트를 생성한다.
- [ ] 도구 버전·입력 fingerprint·설정을 기록한다.
- [ ] probe·clip·frame·Job 단계별 시간을 기록한다.
- [ ] 실패 단계와 machine-readable failure가 일치한다.
- [ ] 원본 경로·인증정보가 공유 리포트에 없다.
- [ ] 월요일 baseline bundle을 동결했다.

### G6 — CI·Benchmark·고도화

- [ ] GitHub Actions가 실제 Python/계약 검증을 실행한다.
- [ ] CI가 짧은 영상을 생성해 probe→Timeline→clip→frame을 실행한다.
- [ ] Git 밖 Real Recording dataset manifest를 준비했다.
- [ ] 정상·relative-only·경계·손상/비호환 범주를 검증했다.
- [ ] 가장 큰 실제 위험을 근거로 고도화 항목을 선택했다.
- [ ] 동일 Benchmark의 개선 전후 결과를 저장했다.
- [ ] 성능 개선이 계약 정확성을 훼손하지 않음을 확인했다.

### G7 — W8 안정화

- [ ] `JobExecutionStore` 교체 경계가 고정됐다.
- [ ] in-memory/local 실행 결과 보존 방식이 검증됐다.
- [ ] 주요 실패 회귀 테스트가 추가됐다.
- [ ] CI 전체 검증이 통과한다.
- [ ] 미지원 범위와 후속 배포 작업이 문서화됐다.
- [ ] 이후 대규모 기능 개발 없이 배포·안정화·발표 준비 중심으로 전환할 수 있다.

