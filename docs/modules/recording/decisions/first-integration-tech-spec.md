# recording 1차 Mock E2E Tech Spec

**Owner:** 정철원  
**상태:** Implemented — 1차 Mock E2E 기준
**기준 브랜치:** `feature/recording-first-integration`  
**기준 커밋:** `53d2722`  
**범위:** `recording` 공개 입출력과 정철원 담당 `JobExecution` 구현  

## 1. 목적

Architecture, Canonical Contract, Mock Pack v5와 정철원 1차 완료 체크리스트를 실행 가능한 코드로 연결한다.

이번 구현의 목표는 실제 영상 처리와 production 인프라 완성이 아니라 다음 조건을 만족하는 integration-ready baseline이다.

1. Consumer가 호출할 공개 Python entry가 존재한다.
2. 공개 경계는 Canonical Contract와 같은 JSON-compatible 입력과 출력을 사용한다.
3. 공용 fixture로 대표 시나리오를 재현한다.
4. Stub을 실제 adapter로 바꿔도 Consumer 호출 방식이 달라지지 않는다.
5. 최소 smoke/contract test가 공개 경계와 핵심 불변조건을 검증한다.

## 2. 기준 문서

우선순위는 다음과 같다.

1. `docs/product/product-spec.md` §5·§7
2. `docs/architecture/module-architecture.md` §1·§2·§4-모듈1·§5·§6
3. `docs/architecture/contracts/contract-source-asset-media-stream.md`
4. `docs/architecture/contracts/contract-recording-timeline-asset-span.md`
5. `docs/architecture/contracts/contract-analysis-source-derived.md`
6. `docs/architecture/contracts/contract-job-execution.md`
7. `docs/modules/recording/first-integration-checklist.md`
8. `data/mock/recording/` 및 `data/mock/common/`

문서가 충돌하면 상위 문서를 따르고 임의로 새 Contract를 만들지 않는다.

## 3. 구현 범위

### 3.1 `recording`

- SourceAsset와 MediaStream 등록·조회
- FrameRef 발급과 frame 조회
- AssetFacts 조회
- RecordingTimeline revision 등록·조회
- timeline-relative 구간을 AssetSpan으로 해소
- AnalysisSource 준비·열기
- RemoteCopy 조회·등록
- IncidentClip 생성
- DerivedAsset 등록·조회
- case 단위 관리 자산 삭제 결과 생성

### 3.2 `common/runtime`

- `JobExecution` 생성 및 상태 전이
- 동일 `job_id`의 attempt 증가
- terminal 상태와 `produced[]`·`usage_refs[]` 보존
- STALE·FAILED·CANCELLED 의미 구분

`JobExecution`의 Contract와 lifecycle 의미는 김준영이 소유한다. 정철원 구현은 해당 계약을 변경하지 않는다.

## 4. 1차에서 구현하지 않는 것

- 실제 ffprobe/ffmpeg 실행
- 실제 frame decode와 이미지 전송 형식
- 실제 S3/GCS 저장소
- 실제 Gemini/provider upload와 delete
- 실제 DB Queue, lease, heartbeat 동시성
- canonical profile 값 목록 확정
- `stream_selector` exact schema 확정
- retention 기간 확정
- `transform_ref` payload schema 확정
- `build_incident_clip` options schema 확정

위 기능은 in-memory repository와 fixture-backed Stub으로 대체한다. 대체 여부는 공개 결과가 아니라 adapter 구성에서 결정한다.

## 5. 기술 선택

### 5.1 언어와 패키징

- Python 3.12 (프로젝트 root 공통 기준)
- `src` layout 유지
- 단일 Python package: `daesingo`
- 테스트: `pytest`
- 공개 JSON 경계 검증: Pydantic v2
- lint/format 도구는 팀 공통 기준이 정해지기 전까지 새로 강제하지 않는다.

### 5.2 저장소

1차 구현은 in-memory repository를 사용한다.

- 테스트 한 번의 lifecycle 동안만 상태를 보존한다.
- ref로 객체를 조회한다.
- public service는 저장 방식에 의존하지 않는다.
- 이후 MySQL/storage adapter로 교체하더라도 public 함수 입력과 출력은 유지한다.

### 5.3 ID

- ID는 opaque 문자열로 취급한다.
- Consumer가 prefix를 파싱하지 않는다.
- Stub fixture에서는 공용 fixture의 ID를 그대로 사용한다.
- 새 ID 생성이 필요한 테스트에서는 위치·role·offset을 ID에 인코딩하지 않는다.

## 6. 코드 경계

예정 구조는 다음과 같다. 파일명은 구현 중 책임이 명확하지 않으면 조정할 수 있으나 module boundary는 유지한다.

```text
src/daesingo/
  recording/
    __init__.py
    models.py          # recording 소유 Contract 모델
    errors.py          # public failure 직렬화
    repository.py      # in-memory 저장 경계
    service.py         # public capabilities
    fixtures.py        # 공용 recording fixture loader
  common/
    __init__.py
    job_execution.py   # JobExecution 모델과 lifecycle 구현
tests/
  recording/
  common/
```

다른 모듈은 `recording.service`의 public capability와 `common.job_execution`의 공개 entry만 사용한다.

## 7. 공개 entry

### 7.1 자산과 frame

```python
register_source_asset(payload) -> SourceAsset
register_media_stream(payload) -> MediaStream
resolve_frame(locator) -> FrameRef | failure
read_frame(frame_ref) -> ReadableFrame | failure
lookup_asset_facts(asset_ref) -> AssetFacts | failure
```

`ReadableFrame`은 Contract가 이미지 전달 형식을 확정하지 않았으므로 1차 Stub 내부 결과다. Consumer에게 공개할 때는 `frame_ref`와 binary content 경계를 분리하고 새로운 canonical JSON 필드를 만들지 않는다.

### 7.2 timeline과 span

```python
register_timeline(payload) -> RecordingTimeline
get_timeline(timeline_id, revision) -> RecordingTimeline | failure
resolve_span(timeline_ref, requested_range) -> SpanResolution | failure
```

`register_timeline`은 1차 fixture 주입 entry다. 실제 `build_timeline()`은 media probing이 연결되는 후속 단계에서 같은 RecordingTimeline 출력을 생산한다.

### 7.3 분석·파생 자산

```python
prepare_analysis_source(span, profile_ref) -> AnalysisSource | failure
open_analysis_source(analysis_source_ref) -> OpenedAnalysisSource | failure
find_remote_copy(analysis_source_ref, provider) -> RemoteCopy | None
register_remote_copy(analysis_source_ref, provider, remote_info) -> RemoteCopy
build_incident_clip(span, options) -> IncidentClip | failure
register_derived_asset(payload) -> DerivedAsset
purge_case(case_id) -> DeletionReport
```

`prepare_analysis_source`, `open_analysis_source`, `build_incident_clip`, `purge_case`는 1차에서 fixture-backed Stub으로 동작한다. Contract에서 Pending인 profile 값과 options schema를 구현이 임의로 확정하지 않는다.

### 7.4 JobExecution

```python
start_execution(job_id, attempt, queued_at, started_at) -> JobExecution
finish_execution(execution_id, status, ended_at, produced, failure_kind, usage_refs) -> JobExecution
```

세부 API 모양은 구현 중 조정할 수 있지만 반환값은 항상 `job-execution/v1.1` JSON과 동일해야 한다.

## 8. Contract 모델링 원칙

- 외부 JSON 필드명과 enum은 Contract 표기를 그대로 사용한다.
- optional과 nullable을 구분한다.
- `MissingRange.source_ref`처럼 키가 항상 필요한 nullable 필드는 누락을 허용하지 않는다.
- `ContractRef`는 `{kind, ref}` 객체로 유지한다.
- 자산 계층 `kind`는 소문자 snake_case다.
- `AnalysisRun.input_ref.kind=ANALYSIS_SCOPE` 같은 타 계약 값에 전역 소문자 규칙을 적용하지 않는다.
- 초 단위와 밀리초 단위의 변환은 public 경계에서 명시적으로 수행한다.
- 완료된 결과와 과거 timeline revision을 mutate하지 않는다.

## 9. 대표 실행 시나리오

### 9.1 우선 구현 — `scenario_happy_001`

1. recording fixture를 로드한다.
2. SourceAsset·MediaStream·FrameRef·RecordingTimeline을 repository에 등록한다.
3. timeline range를 `resolve_span()`으로 해소한다.
4. AnalysisSource와 IncidentClip을 조회 또는 Stub 생성한다.
5. DerivedAsset과 AssetFacts를 조회한다.
6. 반환 JSON을 공용 fixture와 Contract 수준에서 비교한다.

### 9.2 두 번째 — `scenario_relative_rebase_001`

- revision 1 `USABLE_RELATIVE_ONLY`를 정상 등록한다.
- revision 2 등록 후 revision 1이 변하지 않았음을 확인한다.
- gap 요청이 `PARTIAL`과 `TIMELINE_GAP`을 반환하는지 확인한다.

### 9.3 세 번째 — `scenario_infra_failure_001`

- 같은 job의 STALE attempt와 FAILED retry를 구분한다.
- CANCELLED와 SUCCEEDED execution을 별도 job으로 재현한다.
- recording FrameRef source offset과 readout clip offset의 접합은 contract test에서 확인한다.

## 10. 테스트 전략

### Smoke test

- package import 가능
- Happy fixture load 가능
- public service 생성 가능
- Happy Path 공개 호출이 JSON-compatible 출력을 반환

### Contract test

- Contract version과 필수 키
- enum과 nullable
- SourceAsset↔MediaStream 역참조
- FrameRef 재조회 동일성
- timeline revision 불변
- SpanResolution coverage와 MissingRange
- IncidentClip AssetSpan provenance
- JobExecution 상태·시각·produced·usage refs

### 회귀 검사

```powershell
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
$env:PYTHONUTF8='1'; python scripts/check_boundaries.py
pytest
```

## 11. 구현 및 커밋 순서

1. Python package·pytest·Pydantic 실행 기반
2. SourceAsset·MediaStream 모델과 Happy fixture loader
3. FrameRef·AssetFacts 공개 capability
4. RecordingTimeline repository와 `resolve_span()`
5. relative-only·rebase·PARTIAL/FAILED 처리
6. AnalysisSource·RemoteCopy
7. IncidentClip·DerivedAsset·DeletionReport Stub
8. JobExecution lifecycle
9. 7개 fixture contract test와 Consumer 사용 예시

각 단계는 독립적으로 검증한 뒤 별도 커밋한다. 커밋 전 변경 파일·검증 결과·한글 커밋 메시지를 Owner에게 제시하고 승인을 받는다.

## 12. 1차 완료 판정

다음 조건을 모두 만족하면 recording 1차 구현 완료로 본다.

- 공개 함수 또는 Worker entry가 실행된다.
- Canonical Contract JSON 입력과 출력이 검증된다.
- `scenario_happy_001`이 공개 entry를 통해 재현된다.
- `scenario_relative_rebase_001`과 `scenario_infra_failure_001`의 핵심 상태를 테스트한다.
- Consumer가 fixture adapter와 실제 service를 같은 호출 형태로 사용할 수 있다.
- smoke/contract test와 공용 검증 스크립트가 통과한다.

실제 ffmpeg, provider, DB Queue가 Stub이라는 이유만으로 미완료로 보지 않는다. 반대로 문서와 fixture만 있고 실행 가능한 공개 entry가 없으면 완료로 보지 않는다.

## 13. 구현 결과

- `RecordingService` 공개 capability와 in-memory repository를 구현했다.
- recording·common 7개 시나리오 fixture를 Canonical 모델로 검증한다.
- Happy Path, Empty, relative rebase/PARTIAL, infra failure 접합을 자동 테스트한다.
- `examples/recording_consumer.py`에서 저장소 내부를 참조하지 않는 Consumer 호출과 JSON 출력을 재현한다.
- 실제 ffmpeg/provider/storage/DB Queue는 §4의 제외 범위대로 후속 구현에 남긴다.
