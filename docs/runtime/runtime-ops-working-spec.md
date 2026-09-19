**2026-09-19 · v2 정합화 2차 완료 (Working)**
> **이번 고도화 범위**
§1~§28을 현재 `module-architecture.md v4`, Final Data Contract, `develop` 실제 구현, recording/search research, GitHub Issue #41 합의 기준으로 다시 정합화했다.
특히 **JobRecord↔JobExecution 분리, STALE/retry, UsageRecord v1.2, CaseView 진행상태, 실제 CI/배포 구현 여부, recording profile 책임 경계**를 현재 상태에 맞췄다.
> **이 문서의 지위**
아직 Git의 최종 Runtime Tech Spec/Ops Spec으로 분리되기 전 **Working source**다. Architecture·Final Data Contract의 스키마를 다시 정의하지 않으며, 충돌 시 상위 SoT가 우선한다.
> **현재 우선순위**
`Product Policy → module-architecture.md v4 → Final Data Contract → module decisions → module research/experiments → 이 Runtime/Ops Working 문서 → 구현`
> **남은 미결**
정확한 retry/lease/heartbeat 수치, 실제 MySQL Queue 구현, api/worker composition root, CI repo-wide 확장, Real Recording Benchmark, canonical profile exact 값, Storage/Retention 수치다.
# 대신고 백엔드 Runtime · Ops 고도화 설계 v1
> **목적**
대신고의 7개 도메인 모듈 구조를 유지하면서, Architecture와 Final Data Contract가 정한 경계를 **실제로 실행·통합·테스트·배포할 수 있는 Runtime/Ops 구현 기준**으로 내린다.
대규모 상용 인프라를 미리 만드는 것이 목적이 아니라, 6인·약 10주 프로젝트에서 **문제가 생겼을 때 원인을 추적하고 필요한 부분만 확장할 수 있는 최소 운영 구조**를 정한다.
---
## 0. 결정 상태 읽는 법
<table header-row="true">
<tr>
<td>표시</td>
<td>의미</td>
</tr>
<tr>
<td>**`[상위 확정]`**</td>
<td>Product / Architecture v4에서 이미 확정. 이 문서가 다시 결정하지 않음</td>
</tr>
<tr>
<td>**`[Contract 확정]`**</td>
<td>Final Data Contract가 authoritative. 이 문서에는 구현에 필요한 의미만 요약</td>
</tr>
<tr>
<td>**`[Runtime 구현값]`**</td>
<td>retry 상한, backoff, lease/heartbeat 주기, DB 구조 등 계약이 의도적으로 열어 둔 구현 세부</td>
</tr>
<tr>
<td>**`[recording 실측/Benchmark]`**</td>
<td>실제 Recording 자료·코드·Benchmark로 닫아야 하는 값. 이미 확인된 실측과 아직 열린 수치를 구분해서 기록</td>
</tr>
<tr>
<td>**`[후속 조건부]`**</td>
<td>현재 만들지 않고 실제 병목·장애가 관측될 때 도입</td>
</tr>
</table>
---
# 1. 전체 결론
현재 Architecture 기준에서 `common/runtime`은 **여덟 번째 도메인 모듈이 아니라 실행 인프라**다. `case`가 작업의 이유와 발주 의도를 소유하고, Runtime은 그 의도를 실제 실행으로 옮긴다.
```plain text
Browser
   │
   ▼
FastAPI / API composition root
   │
   ▼
case
   └─ JobRecord (Job Intent)
      ├─ 무엇을 실행할지
      ├─ 어느 Case / revision의 요청인지
      └─ fingerprint / force_rerun
             │
             ▼
      common/runtime
      ├─ DB Queue / claim              ← 구현 세부
      ├─ JobExecution                  ← 실행 1회분 Contract
      ├─ retry / lease / heartbeat     ← Runtime 구현 세부
      └─ UsageRecord                   ← 호출 사용량·비용 원장
             │
             ▼
      Worker composition root
      ├─ recording public capability
      ├─ search public capability
      ├─ readout public capability
      └─ evidence 등 필요한 public capability
```
MySQL에는 제품 상태와 Runtime persistence가 함께 놓일 수 있지만, **JobRecord를 Queue row와 동일시하지 않는다.**
`JobRecord`는 `case`가 만든 **Intent 계약**, `JobExecution`은 `common/runtime`이 만든 **실행 lifecycle 계약**이다. Queue table/claim column을 어떤 물리 스키마로 둘지는 Runtime Tech Spec의 구현 세부다.
배포 관점의 baseline은 유지한다.
```plain text
논리적으로      도메인 모듈 7개 + common/runtime 실행 기반
물리적으로      FastAPI 1 + Worker 1
데이터베이스    MySQL 1
배포 단위       하나
```
**Redis / Celery / RabbitMQ / SQS / Kafka / Kubernetes는 baseline에 넣지 않는다.** 실제 DB contention, Worker 확장, scheduling 복잡도 등이 관측되면 후속 조건부로 재검토한다.
## 1-1. 카테캠 실제 AWS 제공 환경 `[상위 환경 제약]`
2026-08-31 카테캠 공지 기준 기본 배포 환경은 다음과 같다.
```plain text
Region      ap-northeast-2 (Seoul)
EC2         t3.medium / 2 vCPU / 4GB RAM
OS          Ubuntu 24.04 LTS
Disk        50GB SSD (encrypted)
기간        2026-08-31 ~ 2026-11-20
기본 서버   팀당 EC2 1대
```
MVP 기본 배포는:
```plain text
EC2 t3.medium 1대
└─ Docker Compose
   ├─ api
   ├─ worker
   └─ mysql
```
로 둔다.
**RDS / ALB / Elastic IP는 기본 제공으로 가정하지 않는다.** 실제 병목이나 운영 요구가 측정될 때 요청한다.
50GB 로컬 디스크는 **working storage / cache / DB / container 자원이 함께 경쟁하는 실행 공간**으로 본다. recording 조사에서 현재 샘플이 약 **6.79GB/h**임은 이미 확인됐지만, 이것만으로 전체 원본 업로드나 S3 사용 범위를 확정하지 않는다. 최종 Storage/Upload 전략은 Real Recording Benchmark의 upload/network/peak disk/processing 결과까지 보고 결정한다.
제공 EC2에는 GPU가 없으므로 자체 대형 VLM inference를 제품 배포 baseline으로 두지 않는다.
---
# 2. 기술 스택
## 2-1. 핵심 Stack
<table header-row="true">
<tr>
<td>영역</td>
<td>결정</td>
</tr>
<tr>
<td>Language</td>
<td>**Python 3.12** — 팀 표준 개발/CI 버전 `[Runtime 구현값]`</td>
</tr>
<tr>
<td>Backend</td>
<td>**FastAPI**</td>
</tr>
<tr>
<td>Architecture</td>
<td>**Modular Monolith** `[기존 확정]`</td>
</tr>
<tr>
<td>DB</td>
<td>**MySQL 8.4 LTS (InnoDB)부터 사용** `[이번에 결정]`</td>
</tr>
<tr>
<td>ORM / SQL</td>
<td>**SQLAlchemy 2.x**</td>
</tr>
<tr>
<td>Migration</td>
<td>**Alembic**</td>
</tr>
<tr>
<td>Runtime schema</td>
<td>**Pydantic**</td>
</tr>
<tr>
<td>Dependency / lock</td>
<td>**uv + ****`pyproject.toml`**** + ****`uv.lock`**</td>
</tr>
<tr>
<td>Local development</td>
<td>**uv + project-local ****`.venv`****  • ****`.python-version`****(3.12)**</td>
</tr>
<tr>
<td>Runtime config</td>
<td>**`.env.example`****로 변수 계약 공유 / ****`.env`****는 로컬 secret로 Git 제외**</td>
</tr>
<tr>
<td>Format / Lint</td>
<td>**Ruff**</td>
</tr>
<tr>
<td>Type check</td>
<td>**basedpyright** — 현재 repo 사용 근거. repo-wide 표준화는 후속</td>
</tr>
<tr>
<td>Test</td>
<td>**pytest**</td>
</tr>
<tr>
<td>Secret scan</td>
<td>**gitleaks** — 목표 gate. 현재 CI에는 아직 없음</td>
</tr>
<tr>
<td>CI</td>
<td>**GitHub Actions**</td>
</tr>
<tr>
<td>Deployment packaging</td>
<td>**Docker + Docker Compose** — 로컬 개발환경 표준과 분리</td>
</tr>
<tr>
<td>Video</td>
<td>**ffmpeg / ffprobe** `[기존 확정] `</td>
</tr>
</table>
기존 v3에서 Python 단일 언어, AWS, 모듈형 모놀리스, ffmpeg/ffprobe는 이미 확정되어 있다.
### Python 개발환경 기준 `[Runtime 구현값]`
멘토 리뷰와 1차 Mock Merge에서 모듈별 Python 버전·build 설정 불일치가 실제 통합 충돌로 확인됐으므로, **프로젝트 전체 개발/CI 기준 Python은 3.12로 통일**한다.
```plain text
지원 하한        pyproject.toml → requires-python >=3.12
팀 개발 표준     .python-version → 3.12
로컬 환경        uv가 생성/관리하는 project-local .venv
의존성 선언      root pyproject.toml
정확한 lock      uv.lock
CI               GitHub Actions setup-python 3.12
배포 이미지      Python 3.12 기준 Docker image
```
운영 원칙은 다음과 같다.
- **root ****`pyproject.toml`****을 Python 프로젝트 설정의 단일 Source of Truth로 사용**한다. 모듈별로 별도 root `pyproject.toml`이나 Python 버전을 선언하지 않는다.
- 새로운 Python dependency는 각 모듈 전용 환경파일이 아니라 **root ****`pyproject.toml`****에 추가**하고 `uv.lock`을 갱신한다.
- 로컬 표준 진입점은 `uv sync`이며, 실행은 `uv run ...`을 사용한다.
- CI는 `uv sync --locked` 후 테스트/계약/경계 검증을 수행해 lockfile과 다른 환경에서의 성공을 허용하지 않는다.
- `.venv`와 `.env`는 Git에 커밋하지 않는다. 공유가 필요한 환경변수 이름·형식은 `.env.example`에 둔다.
- Docker는 **배포·통합 재현 환경**이며, 일상 로컬 개발 자체를 Docker 안에서만 하도록 강제하지 않는다.
현재 develop에 남아 있는 `requires-python >=3.10`, GitHub Actions의 Python 3.11, 과거 모듈별 3.10/3.11/3.13 선언은 **구현 정합화 대상으로 제거·수정**한다. 팀 표준은 Python 3.12이며, 3.13 사용을 개별 개발자의 임의 기본값으로 두지 않는다.
### 왜 SQLite가 아니라 MySQL부터 쓰나? 그리고 왜 PostgreSQL 대신 MySQL인가?
v3의 기존 추천은 `SQLite → 필요하면 PostgreSQL`이었다.
하지만 운영 설계를 구체화하면서 **DB가 단순 저장소가 아니라 Job Queue의 역할까지 맡는다는 점**이 중요해졌다.
API/runtime과 Worker가 Runtime Queue·JobExecution row를 동시에 claim/update해야 하므로 SQLite에서 나중에 옮기기보다 처음부터 서버용 관계형 DB를 사용한다. `JobRecord` 자체는 append-only Intent이며 Queue row와 동일하지 않다.
이번에는 **MySQL 8.4 LTS + InnoDB**로 통일한다.
MySQL의 `SELECT ... FOR UPDATE SKIP LOCKED`는 다른 worker가 잡고 있는 행을 기다리지 않고 건너뛸 수 있으며, MySQL 공식 문서도 여러 session이 같은 **queue-like table**에 접근할 때 lock contention을 피하는 용도로 사용할 수 있다고 명시한다.[[1]](https://dev.mysql.com/doc/refman/8.4/en/select.html)
따라서 기존 PostgreSQL 선택의 핵심 이유였던 **DB 기반 Job Queue + row-level claim**은 MySQL에서도 그대로 성립한다.
또한 SQLAlchemy 2.x는 MySQL을 공식 dialect로 지원하고,[[2]](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) AWS RDS도 MySQL 8.4를 지원한다.[[3]](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MySQL.Concepts.VersionMgmt.html) 다만 **카테캠 제공 환경에서는 RDS 생성이 기본 차단**되어 있으므로 MVP 기본 배포는 EC2 내부 Docker Compose MySQL로 간다. RDS는 DB가 같은 EC2의 CPU/RAM/I/O와 실제로 경쟁하거나, DB 분리·관리형 백업/복구가 필요하다는 운영 근거가 생겼을 때 카테캠에 요청하는 `[후속 조건부]` 경로다. 이 경우에도 DB 제품은 MySQL을 유지하므로 애플리케이션의 DB 제품 변경은 필요 없다.
PostgreSQL도 기술적으로 충분히 가능한 선택이다. 다만 현재 대신고가 PostgreSQL 고유 기능에 의존하지 않고, **구현 담당자가 MySQL에 더 익숙하다는 팀 숙련도 이점**이 있다. 6인·약 10주 프로젝트에서는 새로운 DB를 학습·디버깅하는 비용보다 이미 익숙한 DB로 빠르게 구현하는 편이 유리하다고 판단한다.
즉,
```plain text
SQLite
→ 나중에 서버 DB migration
```
보다
```plain text
MySQL 8.4 LTS (InnoDB)
→ 처음부터 DB Queue까지 동일 환경
```
으로 간다.
이 변경으로 바뀌는 것은 **DB 제품 선택**이며, `JobRecord`/`JobExecution` 책임 분리, Worker claim, retry/lease/heartbeat, SQLAlchemy, Alembic 등 상위 운영 설계는 유지한다.
---
# 3. FastAPI가 긴 작업을 직접 처리하지 않는다
`search`, 장시간 media transform, OCR/readout 등은 HTTP 요청 수명 안에서 완료를 보장할 작업으로 두지 않는다.
현재 경계는 다음처럼 읽는다.
```plain text
HTTP 요청
→ 요청 검증
→ case가 JobRecord(Job Intent) 생성
→ API / composition root가 Runtime 실행 경계에 전달
→ 202 Accepted + 조회 가능한 job 식별자
→ 요청 종료

이후
Worker composition root
→ Runtime에서 실행 claim
→ JobExecution 생성/전이
→ 해당 도메인 public capability 호출
→ produced / usage ref 기록
```
따라서 대신고에서는 FastAPI `BackgroundTasks`를 긴 영상 처리용 Job Queue로 사용하지 않는다.
```plain text
FastAPI request lifecycle
≠
Long-running execution lifecycle
```
API와 Worker는 프로세스를 나누되 **별도 도메인 서비스나 마이크로서비스로 쪼개는 것은 아니다.** 같은 repository와 같은 Contract를 사용하는 modular monolith의 두 composition root로 본다.
---
# 4. Job Queue / Execution 설계
> **정합화 핵심:** v1 문서의 `JobRecord.status / attempt / lease / heartbeat / cost` 중심 설계는 현재 Final Contract와 맞지 않는다. **Intent와 Execution을 분리**한다.
## 4-1. 두 계약의 역할 `[Contract 확정]`
```plain text
case
└─ JobRecord (job-record/v1)
   └─ 작업을 왜/무엇을 발주했는가

common/runtime
└─ JobExecution (job-execution/v1.1)
   └─ 그 Job이 실제로 몇 번째 시도에서 어떻게 실행됐는가

common/runtime
└─ UsageRecord
   └─ 실제 capability/provider invocation 1건의 사용량·비용
```
Runtime 구현은 이 세 의미를 한 객체나 한 row로 다시 합치지 않는다.
---
## 4-2. JobRecord는 Queue 상태 객체가 아니다
`JobRecord`는 `case`가 append-only로 만드는 Job Intent다.
핵심 의미는:
```plain text
job_id
case_id / case_rev
kind
scope_ref
input_fingerprint
force_rerun
requested_at
```
이다.
**status, attempt, lease, heartbeat, retry timing, produced, failure, cost는 JobRecord 소유가 아니다.**
캐시/부분 재실행 정책과 `force_rerun`은 `case`가 소유한다.
---
## 4-3. 실행 lifecycle은 JobExecution이 소유한다 `[Contract 확정]`
현재 닫힌 status 값은:
```plain text
QUEUED
RUNNING
SUCCEEDED
FAILED
STALE
CANCELLED
```
이다.
허용되는 기본 흐름은:
```plain text
QUEUED → RUNNING → SUCCEEDED
                 → FAILED
                 → STALE
                 → CANCELLED

QUEUED → FAILED
QUEUED → CANCELLED
```
각 execution은 독립 `execution_id`를 가지며, 같은 `job_id`의 자동 인프라 재시도에서는 새 execution과 증가한 `attempt`가 생길 수 있다.
`produced[]`는 산출물의 opaque ContractRef만 기록하고, 그 산출물이 의미상 유효한지는 각 도메인과 `case`가 판단한다.
---
## 4-4. STALE과 오래된 Case 결과는 같은 개념이 아니다
v1 문서는 `case_rev`가 오래된 결과를 `STALE`로 설명했지만 현재 계약에서는 둘을 분리한다.
```plain text
JobExecution.STALE
= 실행 중 Worker가 더 이상 살아 있지 않다고 Runtime이 판정한 실행 상태

case_rev 불일치
= 실행 자체가 성공했더라도 현재 Case state에 produced를 반영하지 않는 case 정책
```
즉:
```plain text
SUCCEEDED + old case_rev
→ JobExecution을 STALE로 바꾸는 것이 아님
→ case가 결과 적용을 거부
```
으로 처리한다.
---
## 4-5. 사용자 재개/재실행과 인프라 retry를 구분한다
```plain text
사용자가 "이어서 찾기" / 재판독 / 재검색을 요청
→ 새 JobRecord
→ 새 job_id
```
반면:
```plain text
사용자 새 Intent 없이 STALE 등으로 자동 인프라 retry
→ 같은 job_id
→ 새 execution_id
→ attempt 증가
```
이다.
---
## 4-6. 이 문서가 이후 Tech Spec에서 정할 값 `[Runtime 구현값]`
Final `JobExecution` 계약은 다음을 일부러 정하지 않았다.
```plain text
실제 DB Queue 물리 스키마
claim transaction / locking
retry 상한
backoff 곡선 / jitter
available_at 계산
lease 길이
heartbeat 주기
STALE 판정 임계값
startup / periodic stale sweep
Worker polling 주기
```
이 값들은 **Contract 변경이 아니라 Runtime Tech Spec의 구현 선택**이다.
현재 1차 구현은 in-memory lifecycle과 fixture-backed adapter까지 존재하며, 실제 DB Queue·lease·heartbeat는 후속 통합 대상이다.
---
# 5. 중복 작업 방지 — Idempotency / Cache Reuse
> **핵심 경계:** 중복 실행을 막을지, 기존 성공 결과를 재사용할지는 `case`의 Job Intent 정책이다. Runtime은 그 결정을 대신하지 않고, 전달받은 Job을 실행한다.
현재 Final Contract가 고정하는 재사용 조건은 다음이다.
```plain text
같은 case_id
- 같은 kind
- 같은 input_fingerprint
- force_rerun = false
- 재사용 가능한 기존 SUCCEEDED 결과 존재
→ case가 기존 결과 재사용 가능
```
`FAILED` / `STALE` 실행은 cache hit로 보지 않는다. 사용자가 재판독·재검색·"이어서 찾기"를 요청하면 **새 JobRecord / 새 job_id**를 발주한다. `force_rerun=true`이면 fingerprint가 같아도 기존 성공 결과를 재사용하지 않는다.
## 5-1. `input_fingerprint`의 책임
Architecture/ADR에는 `AnalysisScope`의 정규화된 입력과 **활성 구현 식별값**을 함께 fingerprint에 반영하는 방향이 있다. 다만 Runtime/Ops가 다른 모듈의 model/prompt/version 내부를 직접 읽어서는 안 된다.
따라서 현재 경계는:
```plain text
case / 접합 계층
	├─ normalized domain input
	├─ target capability의 opaque impl identity
	└─ 재사용 의미에 영향을 주는 profile / contract input
		↓
input_fingerprint
```
으로 둔다.
`search`의 모델명·prompt version 등을 `case`가 직접 해석하지 않고, 대상 모듈이 **opaque 구현 식별값**을 제공하는 방향을 유지한다. 구현 변경이 결과 재사용을 무효화할 수준이면 그 식별값도 달라져야 한다.
**Hash algorithm 자체는 Data Contract가 아니다.** 기존 v1의 “SHA-256 고정”은 이 문서에서 전역 불변조건으로 두지 않는다. 실제 canonical serialization과 hash algorithm은 `case` Tech Spec/접합 구현에서 하나로 고정하고 fixture와 테스트로 재현성을 검증한다.
## 5-2. 현재 구현 상태
- `case`에는 `input_fingerprint`와 `force_rerun`을 받는 Job 발주 함수가 실제 구현돼 있다.
- Mock validator에는 cache decision 검사가 있다.
- **Runtime DB Queue가 이 fingerprint를 다시 계산하는 구현은 아직 없다.** 그래야 한다는 요구도 없다.
---
# 6. Retry 정책
> **Contract와 구현값을 분리한다.** `JobExecution`은 attempt 의미만 고정하고, retry 상한·backoff·`available_at`·jitter는 Runtime Tech Spec 구현값으로 남긴다.
## 6-1. 사용자 재실행과 자동 retry
```plain text
사용자 Intent 발생
→ 새 JobRecord
→ 새 job_id
Runtime의 자동 인프라 retry
→ 같은 job_id
→ 새 execution_id
→ attempt + 1
```
자동 retry가 기존 `JobExecution` row를 되살리거나 attempt를 in-place 수정하지 않는다.
## 6-2. Retry 대상 판단
모듈별 상세 `failure_kind` 값 공간은 각 모듈이 소유한다. Runtime은 이를 받아 **retryable / non-retryable** 실행 정책으로 해석한다.
초기 원칙은:
- timeout, 일시적 네트워크 실패, provider 일시 장애/rate limit처럼 **재호출로 회복 가능성이 있는 실패**만 retry 후보.
- 잘못된 입력, 지원하지 않는 media, 인증/설정 오류처럼 **같은 입력으로 즉시 반복해도 회복되지 않는 실패**는 자동 retry하지 않는다.
- 상세 HTTP code 목록을 이 공통 문서에서 닫지 않는다. provider adapter가 자기 failure taxonomy와 함께 관리한다.
## 6-3. Scheduling
Worker가 backoff 동안 `sleep()`으로 실행 슬롯을 붙잡는 구조는 쓰지 않는다.
```plain text
retry 필요
→ 현재 execution을 terminal 상태로 기록
→ 다음 실행 가능 시각(available_at)을 Runtime 내부 queue metadata로 저장
→ 시간이 된 뒤 새 JobExecution(attempt+1)을 claim
```
`available_at`은 **JobExecution Contract 필드가 아니라 DB Queue 구현 세부**다.
기존 v1의 `최대 3회 / 2s→4s→8s`는 근거가 닫힌 값이 아니므로 **고정값에서 해제한다.** 첫 DB Queue 구현 시 config로 두고, 실제 provider failure log와 사용자 latency를 보고 조정한다.
---
# 7. Worker가 죽었을 때도 복구 가능하게 한다
> **v1 정정:** lease가 만료된 `RUNNING` 실행을 같은 execution의 `QUEUED`로 되돌리지 않는다. 현재 Contract에서는 **기존 execution을 ****`STALE`****로 끝내고, retry가 필요하면 새 execution을 만든다.**
목표 상태:
```plain text
JobExecution attempt 1
RUNNING
	↓ Worker heartbeat/lease 만료
STALE   ← terminal
자동 retry 허용 시
	↓
JobExecution attempt 2
QUEUED → RUNNING → ...
```
## 7-1. lease / heartbeat
`heartbeat_at`, `lease_expires_at` 같은 값은 **Runtime DB 내부 metadata**이며 Final `JobExecution` Contract 필드가 아니다. Consumer가 이 값을 알아야 하지 않는다.
Runtime 구현은:
1. claim할 때 execution과 lease를 만든다.
2. 실행 중 lease/heartbeat를 갱신한다.
3. 만료된 RUNNING execution을 `STALE`로 판정한다.
4. retry 정책이 허용하면 **같은 job_id에 새 execution_id / 다음 attempt**를 QUEUE한다.
5. 더 이상 retry하지 않으면 마지막 `STALE` 실행을 그대로 보존한다. `case` projection에서는 STALE을 실패 상태로 표현할 수 있다.
## 7-2. Recovery 주체
기존 inline 논의에서 합의한 방향을 유지한다.
```plain text
Worker startup
→ stale lease sweep 1회
Worker polling loop
→ periodic stale sweep
```
현재 Worker 1 baseline에서는 별도 reaper process를 추가하지 않는다.
## 7-3. 현재 구현 상태
현재 `src/daesingo/common/job_execution.py`는 `STALE`을 포함한 **in-memory JobExecution lifecycle과 attempt 연속성**까지 구현돼 있다. 실제 MySQL claim / lease / heartbeat / sweep은 아직 구현되지 않았다.
---
# 8. 별도 DLQ는 만들지 않는다
MVP에서는 별도 Dead Letter Queue infrastructure를 만들지 않는다.
대신 실패 이력은:
```plain text
JobRecord          = 발주 Intent 보존
JobExecution       = FAILED / STALE / CANCELLED 실행 이력 보존
UsageRecord        = 실제 invocation이 시작됐다면 비용/사용량 이력 보존
```
으로 남는다.
기존 v1처럼 `JobRecord.failure_class / error_code / attempt`를 넣어 JobRecord 자체를 DLQ처럼 쓰지 않는다. 실행 실패 정보의 위치는 **JobExecution과 모듈별 failure artifact/log**다.
운영자가 실패 execution을 조회·재현할 수 있으면 현재 규모에서는 별도 queue product의 DLQ가 없어도 된다. 추후 SQS/RabbitMQ 등 실제 message queue를 도입하고 redrive 운영 필요성이 생기면 그때 DLQ를 함께 검토한다.
---
# 9. Circuit Breaker는 지금 구현하지 않는다
Circuit Breaker는 `[후속 조건부]`다.
현재 baseline은 Worker 1 + 제한된 외부 provider 호출 규모이며, 반복 장애가 서비스 전체를 밀어내는 현상이 아직 측정되지 않았다. 우선:
```plain text
retry policy
- terminal JobExecution
- provider failure logging / UsageRecord
- queue wait 관측
```
으로 운영한다.
다음 패턴이 실제 로그에서 반복될 때 도입을 검토한다.
```plain text
동일 provider 장기 장애
→ 여러 Job의 retry 반복
→ queue wait 증가
→ 정상 Job까지 지연
```
임계값과 half-open 정책을 지금 임의로 만들지 않는다.
---
# 10. 진행 상태와 조회
진행 상태의 authoritative 화면 계약은 `CaseView`다. Web은 `JobExecution`을 직접 읽지 않는다.
## 10-1. JobExecution → CaseView projection `[Contract 확정]`
```plain text
QUEUED     → PENDING
RUNNING    → RUNNING
SUCCEEDED  → DONE
FAILED     → FAILED
STALE      → FAILED
CANCELLED  → PARTIAL
```
같은 `job_id`에 여러 attempt가 있으면 **가장 큰 attempt의 JobExecution**이 대표 상태다. 같은 `kind`의 JobRecord가 여러 개면 가장 최근에 발주된 Job이 대표 상태다.
`progress[]`에는 모든 가능한 단계를 미리 채우지 않는다. **해당 scenario/파이프라인에서 실제 존재하는 단계만** 싣는다.
## 10-2. Polling
MVP UI는 WebSocket/SSE보다 **CaseView polling**을 baseline으로 둔다. 기존 2초는 초기 UX 구현값으로 사용할 수 있지만 Data Contract가 아니며 실제 UI 부하/체감에 따라 조정 가능하다.
거짓 percentage는 만들지 않는다.
```plain text
실제 count를 아는 작업 → 3 / 10 같은 실제 count
모르는 작업            → CaseView progress state / running_jobs로 표시
```
현재 `api` composition root는 README 골격만 있고 실제 endpoint는 아직 없으므로 polling endpoint와 주기는 **설계값이지 배포 완료 기능이 아니다.**
---
# 11. 부분 실패가 전체 작업을 죽이지 않는다
상위 원칙은 유지한다. 다만 “항상 가장 작은 Job으로 쪼갠다”보다 **이미 성공한 domain artifact를 불필요하게 무효화하지 않는다**가 더 정확하다.
예:
```plain text
Search Candidate 확보
→ IncidentClip 준비
→ Readout 실패
결과:
Search Candidate 유지
IncidentClip이 유효하면 유지
실패한 Readout만 재발주 가능
```
recording Contract도 AnalysisSource/RemoteCopy/IncidentClip/DerivedAsset 실패가 과거 Candidate/Evidence를 자동 삭제하지 않는 경계를 갖고 있다.
**재실행 범위를 결정하는 주체는 case**다. Runtime은 dependency graph를 추론하거나 “어디부터 다시 해야 하는지” 정책을 만들지 않고, 발주된 JobIntent를 실행할 뿐이다.
---
# 12. UsageRecord — 호출 단위 사용량·비용 원장
> **정합화:** 비용을 `JobRecord.cost`에 두지 않는다. 금액의 authoritative source는 `UsageRecord v1.2`다. `JobExecution`은 `usage_refs[]`로 연결만 한다.
확정 스키마 요약:
```plain text
usage_id
execution_ref        nullable
run_ref              \{kind, ref\} \| null
run_ref_reason       DIRECT_NO_RUN \| RUN_NOT_PRODUCED \| null
case_id              nullable
occurred_at
provider_label
operation
token_usage          \{input_tokens, output_tokens, total_tokens\} \| null
processed_duration_sec
latency_ms
pricing_context      \{pricing_id, unit\}
cost                 \{amount, currency\}
```
## 12-1. Row 생성 규칙 `[Contract 확정]`
```plain text
실제 capability/provider invocation 시작
→ 성공 / 실패 / STALE 여부와 무관하게 UsageRecord 생성
queue에서 기다리다 dispatch 전 CANCELLED/FAILED
→ UsageRecord 생성하지 않음
```
따라서 “attempt마다 무조건 1 row”가 아니다.
## 12-2. 집계 축
- **execution 단위:** `execution_ref`
- **logical run 단위:** `run_ref`
- **사건 전체 비용:** `case_id`
- `AnalysisRun.usage_refs[]` / `ReadoutRun.usage_refs[]`는 조회 편의용이고, 어긋나면 원장 `UsageRecord.run_ref`가 기준이다.
`run_ref=null`이면 이유를 반드시:
- `DIRECT_NO_RUN`
- `RUN_NOT_PRODUCED`
중 하나로 남긴다.
## 12-3. 가격과 보존
실행 시점 `cost`를 나중 가격으로 덮어쓰지 않는다. 재평가가 필요하면 `pricing_context`를 이용해 별도 계산한다.
현재 Contract/Mock Pack에는 UsageRecord가 존재하지만, **common/runtime의 실제 DB persistence adapter는 아직 없다.** 또한 `purge_case` 때 UsageRecord를 삭제할지와 ledger retention 기간은 Contract Pending이다.
---
# 13. Logging 설계
## 13-1. 목표 운영 로그
Runtime 운영 로그는 key-value structured log를 기본으로 한다.
```json
\{
	"timestamp": "...",
	"level": "INFO",
	"event": "job.execution.completed",
	"trace_id": "...",
	"case_id": "...",
	"job_id": "...",
	"execution_id": "...",
	"module": "search",
	"duration_ms": 81231
\}
```
핵심 correlation은 `case_id → job_id → execution_id`다. `trace_id`는 HTTP/worker 경계를 연결하는 운영 correlation id로 추가할 수 있다.
## 13-2. 실제 사용자 데이터가 들어가는 운영 단계의 금지 원칙
다음 원문은 운영 로그에 넣지 않는다.
```plain text
번호판 문자열
정확한 GPS / 상세 위치
원본 영상 / frame
사용자 파일의 불필요한 전체 경로
외부 AI request/response payload 전문
사용자 free_text 전문
API key / access token / secret
```
`UsageRecord`도 raw provider payload를 보존하지 않는 Contract다.
## 13-3. 현재 개발 단계 상태
`docs/management/pre-deploy-security-review.md`는 **Mock/합성 데이터 중심 개발 중에는 전역 masking logger를 별도 선행조건이나 리뷰 blocker로 두지 않는다.** logging/privacy 10·11·13·14번은 실제 사용자 데이터/외부 provider 연동 또는 배포 준비 시 재검토한다.
즉:
```plain text
운영 원칙 = 유지
현재 Mock 개발 gate = 아님
Pre-deploy = 반드시 재검토
```
이다. 현재 `common/README.md`에는 masked logger 책임이 선언돼 있지만 전역 logging 구현 완료로 보지는 않는다.
---
# 14. 테스트 전략
테스트는 숫자 하나의 coverage gate보다 **경계별 실패를 잡는 층**으로 관리한다.
<table header-row="true">
<tr>
<td>계층</td>
<td>검증 대상</td>
<td>현재 상태</td>
</tr>
<tr>
<td>Unit</td>
<td>pure/domain logic · 상태 전이 · validator</td>
<td>여러 모듈에 실제 pytest 존재</td>
</tr>
<tr>
<td>Contract / Boundary</td>
<td>Final Contract fixture · import boundary · enum/invariant</td>
<td>`check_boundaries.py`, `check_contract_fixtures.py`, Mock validator 존재</td>
</tr>
<tr>
<td>Integration</td>
<td>모듈 public capability 접합 · case orchestration</td>
<td>Mock/fixture 기반 통합이 진행 중</td>
</tr>
<tr>
<td>Runtime Integration</td>
<td>FastAPI + MySQL Queue + Worker + JobExecution</td>
<td>**아직 미구현** — api/worker가 골격 단계</td>
</tr>
<tr>
<td>Real E2E / Experiment</td>
<td>실제 media/provider · latency/cost/quality</td>
<td>CI 밖의 별도 실험으로 수행</td>
</tr>
</table>
외부 AI 실제 호출은 PR CI의 결정론적 gate로 넣지 않는다. 비용·rate limit·외부 장애 때문에 일반 테스트와 분리한다.
Real media가 필요한 테스트는 **실패와 skip을 구분하고**, 어떤 데이터가 없어 skip됐는지 기록한다.
Coverage report는 도입할 수 있지만 임의의 “90% 미만 merge 금지” 같은 숫자를 먼저 만들지 않는다. 핵심 contract/state transition의 미검증 경로를 찾는 보조지표로 쓴다.
---
# 15. Quality Toolchain — 실제 상태와 목표를 분리
현재 repository와 목표 상태를 섞어 쓰지 않는다.
<table header-row="true">
<tr>
<td>역할</td>
<td>현재 확인</td>
<td>목표</td>
</tr>
<tr>
<td>Package/Test config</td>
<td>root `pyproject.toml` 존재</td>
<td>Python 3.12 기준 단일 SoT</td>
</tr>
<tr>
<td>Lock</td>
<td>`uv.lock` 존재하지만 현재 `requires-python >=3.13`로 root와 불일치</td>
<td>3.12 기준 재생성 + `uv sync --locked`</td>
</tr>
<tr>
<td>Test</td>
<td>`pytest` 실제 사용</td>
<td>repo-wide gate 유지</td>
</tr>
<tr>
<td>Format/Lint</td>
<td>일부 모듈에서 Ruff 실제 사용</td>
<td>root 설정으로 통일</td>
</tr>
<tr>
<td>Type check</td>
<td>`search`는 `basedpyright` 사용, `uv.lock`에도 존재</td>
<td>**repo-wide type checker를 한 개로 수렴**</td>
</tr>
<tr>
<td>Runtime schema</td>
<td>Pydantic v2 실제 사용</td>
<td>유지</td>
</tr>
<tr>
<td>Secret scan</td>
<td>현재 CI gate에서 확인되지 않음</td>
<td>Pre-deploy/CI 단계에서 gitleaks 도입</td>
</tr>
</table>
기존 v1이 `mypy`를 이미 팀 표준처럼 적은 것은 현재 저장소와 맞지 않는다. **현재 실제 사용 근거는 basedpyright 쪽에 있으므로, 최소한 repo-wide 표준화 전까지 mypy를 확정 gate로 적지 않는다.**
또한 `pytest-cov`, `pre-commit`도 현재 repository의 확정 공통 도구로 확인되지 않았으므로 “이미 채택” 상태에서 내린다.
---
# 16. CI Quality Gate
> **현재 CI와 목표 CI를 구분한다.**
## 16-1. 현재 develop에서 실제 동작하는 팀 CI
현재 `.github/workflows/boundary-check.yml`은:
```plain text
pull_request → develop/main
push         → develop
workflow_dispatch
```
에서 실행되고, Python **3.11**로:
```plain text
python scripts/check_boundaries.py
python scripts/check_contract_fixtures.py
```
두 검사를 수행한다.
즉 기존 문서의:
```plain text
ruff + type check + pytest + integration + gitleaks 전부 CI에서 실행
```
은 **아직 구현된 사실이 아니다.**
## 16-2. 다음 CI 정합화 순서 `[Runtime 구현값]`
Python 환경 통일 작업과 같이:
1. `setup-python`을 3.12로 통일
2. root `pyproject.toml` / `uv.lock`을 3.12 기준으로 정합화
3. `uv sync --locked`
4. 기존 boundary + contract fixture 검사
5. repo-wide `pytest`
6. Mock validator
7. root에 설정이 수렴한 뒤 Ruff / 선택한 type checker
8. 실제 외부 배포 전 secret scan
순서로 올린다.
운영진 소유 workflow(`assign-mentor`, `notify-discord`, `convention-check` 등)와 팀 자체 quality workflow는 소유권을 섞지 않는다.
---
# 17. 배포 구조
배포 목표는 Architecture에 맞춰 유지한다.
```plain text
AWS EC2 t3.medium
2 vCPU / 4GB RAM / 50GB SSD
Ubuntu 24.04 LTS
└─ Docker Compose
	├─ api
	├─ worker
	└─ mysql
```
API와 Worker는 같은 repository/Contract를 사용하는 **두 composition root**다. 프로세스가 둘이라고 마이크로서비스가 되는 것은 아니다.
## 17-1. 현재 구현 상태
현재 `src/daesingo/api/README.md`와 `worker/README.md`에는 경계만 있고 **실제 composition root 코드는 아직 없다.** repository에서 runtime용 Docker Compose 배포 구성이 구현됐다고 볼 근거도 아직 확인되지 않는다.
따라서:
```plain text
Docker Compose 3-container
same image / different command
main merge → image build
manual demo deploy workflow
```
은 **목표 배포 설계**이지 현재 동작 중인 pipeline으로 표현하지 않는다.
정확한 module entrypoint/command는 api/worker 코드가 생길 때 그 코드에 맞춰 닫는다.
RDS/ALB/Elastic IP/추가 EC2는 기본 전제가 아니며 §24의 관측 조건이 생길 때 요청한다.
---
# 18. 모니터링은 최소한으로 시작한다
별도 Prometheus/Grafana/OpenTelemetry stack을 baseline으로 만들지 않는다.
배포 후 1차 관측은:
```plain text
structured stdout
→ AWS 로그 수집(CloudWatch 계열)
-
Runtime DB / UsageRecord 조회
```
정도로 시작한다.
최소 운영 질문은:
- queue에 얼마나 기다리고 있는가
- 가장 오래 기다린 Job은 무엇인가
- JobExecution 성공/실패/STALE/retry가 얼마나 생기는가
- 실행 latency가 얼마나 되는가
- 외부 invocation 비용/latency가 얼마인가
- Worker heartbeat/lease가 정상인가
- disk working set이 얼마나 차는가
이다.
이 중 queue/lease/worker heartbeat metric은 아직 DB Runtime 구현이 없으므로 **현재 측정 가능한 지표가 아니라 구현 후 제공해야 할 관측값**이다. Usage/case/eval의 Mock 값과 실제 운영 metric을 혼동하지 않는다.
---
# 19. Health Check
Health endpoint는 Runtime 구현 시 최소 두 층으로 둔다.
```plain text
/health/live
→ API process 자체가 요청을 받을 수 있는가
/health/ready
→ 현재 요청 처리에 필수인 dependency(DB 등)를 사용할 수 있는가
```
Worker는 public HTTP health endpoint를 반드시 만들 필요는 없다. Runtime DB의 worker heartbeat/lease 상태로 readiness를 관측할 수 있다.
단, **현재 api/worker는 README 골격 단계라 위 endpoint와 worker heartbeat는 아직 구현되지 않았다.** 이 절은 구현 acceptance criteria다.
`ready`에 외부 AI provider 전체의 실시간 성공 여부까지 넣어 배포를 불필요하게 내려버리지는 않는다. 외부 provider 상태는 Job failure/retry/monitoring에서 분리해 본다.
---
# 20. 파일 보관·삭제
Lifecycle 용어는 Final recording Contract에 맞춘다.
```plain text
External Source Reference   ← 사용자 원본. 서비스가 overwrite/delete하지 않음
Managed Source Copy         ← 서비스 관리 사본
AnalysisSource              ← 분석용 입력
RemoteCopy                  ← 외부 provider copy/ref
IncidentClip                ← 사건 구간 파생물
DerivedAsset                ← Report Video / Plate Image 등
```
## 20-1. `purge_case()` 경계 `[Contract 확정]`
- **External Source Reference:** reference만 제거. 사용자 기기의 원본 물리 삭제 금지.
- **Managed Source / AnalysisSource / IncidentClip / DerivedAsset:** 서비스가 관리하는 실제 자산이면 삭제 대상.
- **RemoteCopy:** provider delete를 지원하면 삭제 요청, 즉시 삭제를 보장할 수 없으면 expiry까지 남음을 `DeletionReport`에 기록.
- 외부 provider delete API 호출 자체는 `search/providers` 경계, RemoteCopy registry/lifecycle은 recording 경계다.
`DeletionReport`는 자산별로:
```plain text
DELETED
NOT_FOUND
PENDING_EXPIRY
FAILED
```
를 구분하고 전체 status를 `COMPLETE / PARTIAL / FAILED`로 남긴다.
## 20-2. 현재 구현 상태
recording의 in-memory/fixture 구현에는 사용자 external source를 삭제하지 않는 불변조건과 `purge_case`/DeletionReport가 이미 있다. 실제 filesystem/object storage/provider delete adapter는 후속 통합 대상이다.
## 20-3. Retention
정확한 retention 일수는 아직 확정하지 않는다. 코드에 임의 `7 days` 같은 숫자를 박지 않는다.
또한 **UsageRecord가 ****`purge_case`****와 함께 삭제되는지는 별도 Pending**이다. 비용 원장의 lifecycle을 video asset retention과 자동으로 동일시하지 않는다.
---
# 21. Recording / Search 실측 — 닫힌 경계와 남은 Benchmark
> **2026-09-19 재분류:** GitHub Issue #41의 search↔recording 합의까지 반영한다. 이제 “proxy profile 전체가 실측 대기”가 아니다. **책임 경계와 필요한 profile 방향은 닫혔고, 정확한 media 값·품질·운영 비용이 Benchmark 대기**다.
## 21-1. 현재 샘플에서 이미 실측된 Recording 사실
recording Architecture Input Memo 기준:
```plain text
약 60초 / 파일
약 113.25MB / 파일
현재 조건 환산 약 6.79GB / h
container: AVI

전방 H.264 1920×1080 / 30fps
후방 H.264 1280×720 / 30fps
audio 포함

creation_time 없는 샘플 존재
파일명 MDR_YYMMDD_HHMMSS.AVI 형태 관찰
화면 overlay timestamp 존재
GPS stream / metadata는 현재 샘플에서 미확인
```
이 값은 **현재 기종/샘플 실측값**이며 전체 블랙박스 일반값으로 승격하지 않는다.
## 21-2. Issue #41로 닫힌 profile 책임 경계 [합의 완료]
search와 recording이 다음 경계를 합의했다.
```plain text
recording
→ profile의 측정 가능한 media 속성을 보장
  - audio 유무
  - resolution / resolution class
  - FPS
  - codec / container
  - duration / timeline coverage
  - source lineage / provenance

search
→ 그 profile의 recall 충분성 / provider 적합성 / 비용 / latency를 실험으로 검증
```
따라서 **“저해상도·무음이면 recall 손해가 없다”를 recording 보장으로 쓰지 않는다.** recall은 search 실험 결과다.
또한:
- `profile_ref`는 non-null opaque identity다.
- profile은 `coarse/fine` 같은 실행 단계명이 아니라 **media 특성**을 나타낸다.
- 최소 방향은 **저해상도·무음 분석용**과 **원본 또는 판독 가능한 고화질용** 두 계열이다.
- 무음 profile을 만들면 실제 출력 media에 audio stream이 없다는 것은 recording이 보장한다.
- 같은 media 조건이면 coarse/fine이 같은 `AnalysisSource` / `RemoteCopy`를 재사용할 수 있다.
## 21-3. Issue #41 이후에도 정확한 값은 Pending
다음은 아직 canonical profile 값으로 닫지 않는다.
```plain text
정확한 width / height
정확한 FPS
bitrate / quality target
codec / container 최종 선택
coarse recall 허용 하한
fine을 proxy로 할지 원본/고화질 구간으로 할지
무음 처리의 실제 비용 절감폭
budget 기본값
```
`720p/15`, `540p/10`, `360p/5` 같은 기존 숫자는 **실험 후보**이며 기본값이 아니다.
최종 profile 값 목록은 Contract §11-1대로 recording·search·readout 3자 확인 대상이다. 특히 판독용 고화질 profile은 readout 확인이 필요하다.
## 21-4. H.265 → AnalysisSource 고정 → A~D 비교 순서 [합의 완료]
Issue #41에서 다음 실험 순서에 합의했다.
```plain text
1. H.265 direct/copy 호환성 확인
2. 직접 사용 불가 시 target codec transcode 가능성 확인
3. 실험용 AnalysisSource 조건을 하나로 고정
   - container
   - codec
   - width/height
   - FPS
   - audio 유무
   - bitrate/quality
   - 동일 source / 동일 timeline coverage
4. 같은 AnalysisSource로 A~D 분할 전략만 변경
5. recall / cost / latency 비교
```
H.265 direct가 실패해도 transcode한 고정 AnalysisSource를 만들 수 있으면 전체 실험이 막히는 것은 아니다.
## 21-5. Upload 전략에서 지금 제외할 수 있는 것
search research는 Gemini Files API의 **파일당 2GB 제약**을 기록하고 있고, 현재 recording 샘플은 약 **6.79GB/h**다.
따라서:
```plain text
1시간 분량을 하나의 거대한 원본 파일로 묶어
Files API에 그대로 direct upload
```
하는 경로는 baseline에서 제외할 수 있다.
하지만 현재 블랙박스는 실제로 짧은 파일들로 분할돼 있으므로:
```plain text
분할 원본 직접 활용
필요 구간만 사용
고정 transcode AnalysisSource
저해상도·무음 proxy
혼합 전략
```
중 무엇이 최종 baseline인지는 아직 Benchmark가 필요하다. **“원본 전체 direct 불가”와 “원본을 전혀 쓸 수 없음”은 같은 말이 아니다.**
## 21-6. 여전히 Real Recording Benchmark가 필요한 운영값
```plain text
upload / ingest 시간
transcode / proxy 생성 시간
peak disk
외부 전송 bytes
ffmpeg / decode 처리 시간
end-to-end latency
반복 실행 시 reuse 효과
동시 처리 시 CPU/RAM/I/O
```
이 값이 나와야:
- Object Storage 사용 범위
- local 50GB working set
- proxy 승격 여부
- 서버 사양 상향 여부
- 실제 동시 처리 수
를 숫자로 닫을 수 있다.
## 21-7. Retention은 별도 미결
provider copy의 expiry 정보와 서비스 관리 자산의 retention 정책은 같은 문제가 아니다. 정확한 retention 일수와 `purge_case()` 이후 비용 원장 보존은 아직 별도 정책/구현 결정이다.
---
# 22. 초기 Runtime 제안의 현재 처리 상태 `[History / Disposition]`
> 이 절은 현재 Spec을 다시 정의하지 않는다. v1 작성 당시 제안을 **현재 Architecture/Contract에서 어떻게 처리했는지** 추적하기 위한 history다.
<table header-row="true">
<tr>
<td>초기 제안</td>
<td>현재 처리</td>
</tr>
<tr>
<td>DB Queue</td>
<td>**Architecture baseline 유지** — 실제 MySQL queue 구현은 아직</td>
</tr>
<tr>
<td>Redis / SQS / Celery</td>
<td>**baseline 제외** — 필요성 관측 시 재검토</td>
</tr>
<tr>
<td>Worker pool</td>
<td>**Worker 1 baseline**</td>
</tr>
<tr>
<td>202 async response</td>
<td>**설계 채택** — api composition root 구현은 아직</td>
</tr>
<tr>
<td>Polling</td>
<td>**MVP baseline** — 주기는 구현값</td>
</tr>
<tr>
<td>Retry / backoff</td>
<td>**패턴 채택** — 상한/곡선/수치는 Runtime 구현값</td>
</tr>
<tr>
<td>lease / heartbeat recovery</td>
<td>**채택** — STALE + 새 execution 방식으로 정정</td>
</tr>
<tr>
<td>Circuit Breaker</td>
<td>**조건부 보류**</td>
</tr>
<tr>
<td>별도 DLQ</td>
<td>**미도입** — JobExecution 실패 이력으로 운영</td>
</tr>
<tr>
<td>비용 로그</td>
<td>**UsageRecord v1.2로 승격**</td>
</tr>
<tr>
<td>처리 로그</td>
<td>**Structured logging 목표 유지**, 전역 masking 구현은 Pre-deploy 재검토</td>
</tr>
<tr>
<td>정확도/성능</td>
<td>**eval / module experiment 영역**</td>
</tr>
<tr>
<td>Python schema</td>
<td>**Pydantic v2 실제 사용**</td>
</tr>
<tr>
<td>Test Double</td>
<td>**fixture/fake provider 방식 실제 사용**</td>
</tr>
<tr>
<td>GitHub Actions</td>
<td>**사용 중** — 현재 boundary/contract 검사 중심, 전체 gate는 후속</td>
</tr>
</table>
Biome/Vitest/tsc/Zod 같은 TypeScript 도구와 Python 도구의 1:1 대응표는 더 이상 Runtime Spec의 결정 근거로 쓰지 않는다. **필요한 품질 역할을 현재 repository의 실제 도구로 충족하는가**만 본다.
---
# 23. 현재 baseline에서 일부러 안 만드는 것
현 단계 baseline에는 다음을 넣지 않는다.
```plain text
Redis / Celery / RabbitMQ / SQS / Kafka
Kubernetes / Service Mesh / Event Bus
Microservices 분리
Auto Scaling
별도 DLQ infrastructure
실시간 WebSocket/SSE progress
복잡한 Circuit Breaker
Prometheus/Grafana/OpenTelemetry full stack
```
이 목록은 영구 금지가 아니라 **“현재 문제를 해결하는 데 증거가 없는 복잡도”**다.
추가 인프라를 넣기 전 질문은 항상:
```plain text
지금 실제로 어떤 실패/병목을 해결하는가?
현재 구조로 재현 가능한가?
추가 복잡도가 측정 가능한 이득을 주는가?
```
세 가지다.
---
# 24. 언제 한 단계 확장하는가
숫자를 임의로 선결하지 않고 **재현 가능한 운영 증거**가 생겼을 때 확장한다.
## DB Queue → 전용 Queue
다음 중 하나가 반복되면 재검토한다.
- Worker 다중화 때문에 DB claim contention이 실제 병목
- queue workload가 제품 DB latency를 악화
- scheduling/delay/redrive 요구가 MySQL 구현 복잡도를 크게 증가
- DB 장애와 queue 장애를 분리해야 할 운영 요구 발생
## Worker 1 → Worker Pool
```plain text
queue wait가 실제 사용자 latency 문제
-
provider rate limit / EC2 resource에 병렬 여유
```
가 함께 확인될 때.
## Circuit Breaker
동일 provider 장기 장애에서 retry가 queue 전체를 밀어내는 현상이 반복될 때.
## Observability stack
structured log + Runtime DB + UsageRecord + AWS 기본 지표만으로 원인 추적이 반복적으로 실패할 때.
## 카테캠 자원 요청 `[후속 조건부]`
**서버 사양 상향**
- 같은 workload에서 반복 OOM / swap thrashing / 지속 CPU saturation / queue wait가 재현될 때.
**디스크 확장**
- cleanup/retention/object storage 분리를 적용한 뒤에도 **실행 working set** 때문에 50GB가 부족할 때.
**RDS**
- MySQL과 ffmpeg/OCR/Worker가 같은 EC2의 CPU/RAM/I/O를 실제로 경쟁하거나, 관리형 backup/recovery 요구가 생길 때.
**Elastic IP**
- stop/start 이후에도 동일 IP를 유지해야 하는 도메인/데모 운영 요구가 실제로 있을 때.
**ALB**
- API를 2대 이상 운영하거나 health-based routing/load balancing이 실제로 필요할 때.
**GPU / 기타 서비스**
- 실험이 아니라 제품 runtime의 필수 경로가 됐고 현재 제공 자원으로 대체할 수 없을 때.
즉 **기술 이름이 아니라 관측된 실패가 확장 사유**다.
---
# 25. 저장소 골격 — 현재 실제 구조 기준
v1의 `app/` 중심 예시는 현재 repository와 다르므로 실제 경로에 맞춘다.
```plain text
repo/
├─ apps/
│  ├─ prototype/          # 흐름 prototype
│  └─ web/                # 실제 Web 구현
│
├─ src/daesingo/
│  ├─ recording/
│  ├─ search/
│  ├─ readout/
│  ├─ evidence/
│  ├─ case/
│  ├─ common/             # runtime 기반, 도메인 모듈 아님
│  ├─ api/                # composition root — 현재 README 골격
│  └─ worker/             # composition root — 현재 README 골격
│
├─ eval/
├─ tests/
├─ data/mock/
├─ scripts/
├─ docs/
├─ .github/workflows/
├─ pyproject.toml
└─ uv.lock
```
Runtime 구현이 진행되면 필요에 따라:
```plain text
migrations/
Dockerfile
compose.yaml 또는 docker-compose.yml
runtime config / storage adapter / DB adapter
```
를 추가한다. **아직 없는 경로를 현재 구현처럼 문서에 그리지 않는다.**
`common/`은 여덟 번째 도메인 모듈이 아니다. 공통 실행 인프라만 둔다.
```plain text
DB / Queue
JobExecution lifecycle
Usage ledger
logging
configuration
storage adapter
```
교통위반 판단, 검색 품질 정책, 판독 규칙, 부분 재실행의 이유는 각 Owner 모듈에 남긴다.
---
# 26. 이 설계의 핵심 운영 원칙
```plain text
1. HTTP 요청과 long-running execution lifecycle을 분리한다.
2. JobRecord는 case의 Intent, JobExecution은 runtime의 실행 이력이다.
3. cache/reuse 여부는 case가 결정하고 runtime이 임의로 중복 판정하지 않는다.
4. 자동 retry는 같은 job_id에 새 execution/attempt로 남긴다.
5. Worker 소멸은 기존 execution을 STALE로 보존하고 필요 시 새 attempt를 만든다.
6. 성공한 artifact는 하위 단계 실패 때문에 불필요하게 지우지 않는다.
7. 현재 case_rev와 맞지 않는 결과는 실행 성공 여부와 별개로 case가 반영하지 않는다.
8. 실제 외부 invocation이 시작되면 UsageRecord에 사용량/비용을 append-only로 남긴다.
9. 실제 provider 호출은 일반 PR CI의 결정론적 gate와 분리한다.
10. 인프라는 관측된 실패가 필요성을 증명한 뒤 확장한다.
```
이 원칙이 Redis냐 Celery냐보다 우선한다.
---
# 27. 참고 자료 — 학습 근거이며 SoT가 아님
이 절의 책은 Runtime 설계 판단을 이해하는 **학습/참고 근거**다. Architecture나 Final Data Contract보다 우선하지 않는다.
<table header-row="true">
<tr>
<td>대신고에서 연결해 볼 주제</td>
<td>책</td>
</tr>
<tr>
<td>로그와 개인정보</td>
<td>Ch4 \`4.2</td>
</tr>
<tr>
<td>Idempotency</td>
<td>Ch8 \`8.4</td>
</tr>
<tr>
<td>Async / Queue</td>
<td>Ch8 \`8.6</td>
</tr>
<tr>
<td>CI/CD</td>
<td>Ch12 \`12.5~12.6</td>
</tr>
</table>
현재 프로젝트에 대응시키면:
```plain text
Idempotency → JobRecord cache/reuse + input_fingerprint
Async        → JobRecord Intent / JobExecution 분리
Retry        → 새 execution/attempt
Trace        → case_id / job_id / execution_id
Test Double  → fixture-backed provider / Mock Pack
CI           → boundary/contract 검사부터 단계적으로 확장
```
이 절은 구현값을 새로 확정하는 데 사용하지 않는다.
---
# 28. 최종 결정 요약 — 2026-09-19
## A. Architecture / Contract로 이미 닫힌 것
```plain text
Modular Monolith
API 1 + Worker 1
MySQL 8.4 / DB Queue baseline
case = orchestrator
common/runtime = executor
JobRecord = Job Intent
JobExecution = 실행 1회분 / attempt
UsageRecord = invocation 단위 authoritative usage/cost ledger
202 async boundary
사용자 재실행 = 새 JobRecord / 새 job_id
자동 인프라 retry = 같은 job_id / 새 execution_id
STALE = worker 소멸 실행 상태
case_rev 불일치 = case가 결과 미반영
External Source는 서비스가 삭제하지 않음
profile_ref = opaque / non-null
```
## B. Runtime/Ops에서 정한 baseline — 구현은 일부 남음
```plain text
Python 팀 표준 3.12
uv 기반 root 환경으로 수렴
Worker 1
DB Queue claim
lease / heartbeat / stale sweep
retry scheduling
CaseView polling
structured operational logging
live / ready health
Docker Compose 단일 EC2 배포 목표
AWS 기본 observability부터 시작
```
**중요:** 이 목록은 “현재 전부 구현 완료”가 아니다.
## C. 현재 develop에서 실제 확인된 것
```plain text
여러 domain module의 실제 Python 구현 + pytest
JobExecution v1.1 in-memory lifecycle
recording fixture/in-memory public capability + purge_case
Mock Pack / contract validator / boundary checker
boundary-check GitHub Action
root pyproject.toml / uv.lock 존재
```
동시에:
```plain text
api composition root = README 골격
worker composition root = README 골격
실제 MySQL DB Queue / lease / heartbeat = 미구현
Runtime UsageRecord DB persistence = 미구현
배포 Docker Compose pipeline = 확인되지 않음
repo-wide pytest/Ruff/type/gitleaks CI = 아직 아님
```
## D. Issue #41로 닫힌 Recording/Search 경계
```plain text
recording = media 속성 보장
search = recall/provider 적합성 검증
저해상도·무음 분석용 profile 필요
고화질/판독용 profile 필요
H.265 확인 → AnalysisSource 조건 고정 → A~D 비교
```
## E. 아직 실측/합의로 닫아야 하는 것
```plain text
H.265 direct/copy 실제 호환성
canonical profile의 exact w×h / FPS / bitrate / codec
fine 입력이 proxy인지 고화질/원본 구간인지
A~D 최종 분할 전략
1시간 Real E2E upload/transcode/disk/network/latency
Object Storage 사용 범위
retention 일수
동시 처리 수와 실제 capacity
```
따라서 **Recording 실측이 끝날 때까지 Runtime 공통 기반 전체를 멈출 이유는 없다.** 다만 이제 “proxy 전체가 미결”이라고 쓰는 것도 맞지 않는다. **profile 책임 경계는 닫혔고, 실제 profile 값과 운영 수치가 남아 있다.**
# 29. 2026-09-19 고도화 근거 · 확인 범위
> **목적:** 이 문서를 어디까지 확인한 뒤 수정했는지 추적하기 위한 audit trail이다.
**Git 기준:** `kakaotechcampus-4/ktc4-chonnam-2`의 `develop` 브랜치. recording/search 조사·개발 자료와 GitHub Issue 논의를 함께 확인했다.
## 29-1. Architecture / Final Data Contract
- [`docs/architecture/module-architecture.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/architecture/module-architecture.md) — v4의 7개 모듈 + common/runtime 경계, `case = orchestrator`, `common/runtime = executor`, FastAPI 1 + Worker 1 + MySQL DB Queue, Upload 전략 A6 미결을 확인.
- [`contract-job-record-case-view.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/architecture/contracts/contract-job-record-case-view.md) — `JobRecord = Job Intent`, append-only, `case_rev`, fingerprint, `force_rerun`, 사용자 재실행 발주 규칙을 확인.
- [`contract-job-execution.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/architecture/contracts/contract-job-execution.md) — `JobExecution v1.1`, `CANCELLED`, STALE 의미, attempt/execution identity, 사용자 재개와 인프라 retry 구분, retry/lease/heartbeat가 구현 세부임을 확인.
- [`contract-usage-record.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/architecture/contracts/contract-usage-record.md) — UsageRecord가 외부 invocation 1건의 authoritative usage/cost ledger이고 실제 invocation이 시작된 경우에만 row를 남기는 현재 규칙을 확인.
- [`contract-analysis-source-derived.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/architecture/contracts/contract-analysis-source-derived.md) — `profile_ref` opaque/non-null, 최소 profile 방향, recording lifecycle/DeletionReport, exact profile·retention Pending을 확인.
## 29-2. Recording / Search research와 Issue #41
- [`docs/modules/recording/research/architecture-input-memo.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/recording/research/architecture-input-memo.md) — 약 60초/파일, 약 113.25MB/파일, 약 6.79GB/h, AVI 내부 전·후방 H.264 + audio, timestamp/GPS 조사 상태를 확인.
- [`docs/modules/recording/decisions/first-integration-tech-spec.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/recording/decisions/first-integration-tech-spec.md) — Canonical Contract + in-memory/fixture baseline, 실제 ffprobe/ffmpeg/storage/provider/DB Queue가 후속임을 확인.
- [`docs/modules/search/research/architecture-input-memo.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/modules/search/research/architecture-input-memo.md) — Files API 2GB 제약, proxy 추천 방향, H.265/A~D 실험 순서, Issue #41 합의가 §6 B-1에 반영된 상태를 확인.
- [GitHub Issue #41](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/41) — search↔recording이 **media 속성 보장 = recording / recall·provider 적합성 = search** 경계를 합의했고, **H.265 direct/copy 확인 → AnalysisSource 조건 고정 → A~D 비교** 순서를 합의했음을 확인. 이슈는 2026-09-14 completed로 종료됐다.
## 29-3. Develop 코드 / Runtime 현재 상태
- [`src/daesingo/common/job_execution.py`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/src/daesingo/common/job_execution.py) — JobExecution v1.1 model, 상태 전이, in-memory attempt 연속성, STALE/CANCELLED 구현을 확인.
- [`src/daesingo/common/README.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/src/daesingo/common/README.md) — common/runtime 책임 선언 확인. **`JobRecord lifecycle`**이라는 과거 표현은 현재 계약과 어긋나므로 후속 README 정합화 대상**이다.
- [`src/daesingo/recording/models.py`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/src/daesingo/recording/models.py) / [`service.py`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/src/daesingo/recording/service.py) — asset lifecycle, `profile_ref`, external source 삭제 금지, fixture/in-memory `purge_case` 확인.
- [`src/daesingo/api/README.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/src/daesingo/api/README.md) / [`worker/README.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/src/daesingo/worker/README.md) — composition root 책임은 문서화됐지만 **아직 실제 코드가 없음**을 확인.
- [Root README](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/README.md) — 2026-09-18 기준 module 구현/Mock 통합 진행, api/worker 골격 상태 확인.
- [`pyproject.toml`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/pyproject.toml) — 현재 `requires-python >=3.10`.
- [`uv.lock`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/uv.lock) — 현재 `requires-python >=3.13`, basedpyright/Ruff 포함 상태를 확인.
- [`.github/workflows/boundary-check.yml`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/.github/workflows/boundary-check.yml) — 현재 Python 3.11에서 `check_boundaries.py` + `check_contract_fixtures.py`만 실행하는 실제 CI 범위를 확인.
- [`docs/management/pre-deploy-security-review.md`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/develop/docs/management/pre-deploy-security-review.md) — Mock 개발 단계에는 logging/privacy 일부를 별도 blocker로 두지 않고 Pre-deploy에 다시 검토한다는 현재 정책을 확인.
## 29-4. 이번 고도화에서 근거가 없어 열어둔 것
- retry 상한 / backoff 곡선 / lease 길이 / heartbeat 주기 / STALE threshold.
- 실제 MySQL Queue schema / claim transaction / locking.
- H.265 direct/copy 실제 호환성.
- canonical profile exact width/height/FPS/bitrate/codec.
- fine이 proxy인지 원본/고화질 구간인지.
- A~D 최종 분할 전략.
- 1시간 Real E2E upload/transcode/peak disk/network/latency.
- Object Storage 사용 범위 / retention 일수 / 동시 처리 capacity.
- UsageRecord retention과 `purge_case` 연동.
§1~§28은 이번 회차에 현재 자료 기준으로 정합화했으며, 위 항목은 완성도를 위해 임의로 채우지 않았다.
## 29-6. 2026-09-19 Python 개발환경 통일 반영 내역
이번 수정은 멘토 PR 리뷰와 1차 Mock Merge에서 확인된 Python 환경 불일치를 Runtime/Ops 기준으로 닫기 위한 것이다.
- **Python 팀 표준을 3.12로 확정**: 로컬 개발과 CI의 기준 버전을 동일하게 둔다.
- **root ****`pyproject.toml`****을 단일 SoT로 명문화**: `requires-python >=3.12`를 기준으로 하고 모듈별 중복 버전/프로젝트 선언은 정리 대상으로 둔다.
- **uv 기반 개발환경 명문화**: `.python-version`(3.12), project-local `.venv`, `uv sync`, `uv run ...`, `uv.lock`을 표준으로 둔다.
- **CI 기준 명문화**: GitHub Actions `setup-python` 3.12 + `uv sync --locked`를 기준으로 한다.
- **Docker 역할 분리**: Docker + Docker Compose는 배포·통합 재현 환경이며, 로컬 개발 자체를 Docker-only로 강제하지 않는다.
- **환경변수 관리 기준 추가**: `.env.example`은 변수 계약을 공유하고 `.env`는 로컬 secret로 Git에서 제외한다.
- **저장소 공통 골격 갱신**: `.python-version`, `.env.example`, `pyproject.toml`, `uv.lock`의 역할을 명시했다.
### 구현 후 확인할 체크리스트
- [ ] root `pyproject.toml`의 `requires-python`을 `>=3.12`로 수정
- [ ] `.python-version`에 `3.12` 추가
- [ ] `uv.lock` 생성·커밋 및 `uv sync --locked` 재현 확인
- [ ] 모든 GitHub Actions의 `setup-python`을 3.12로 통일
- [ ] 저장소 전체의 과거 3.10/3.11/3.13 Python 버전 선언 제거·정정
- [ ] 모듈별 중복 root `pyproject.toml`/build 설정이 남지 않았는지 확인
- [ ] repo-wide type checker를 하나로 수렴하고 root 설정/CI에 연결
- [ ] 전체 pytest + contract fixture + boundary + mock validation 재실행
> 이 절은 **문서 정책 반영 내역**이다. 실제 Git 변경이 끝나기 전까지는 위 체크리스트를 구현 완료로 간주하지 않는다.
## 29-7. 2차 고도화에서 정정한 대표 v1 드리프트
- `JobRecord.status/attempt/lease/heartbeat/cost` 중심 모델 → **JobRecord Intent / JobExecution / UsageRecord 분리**.
- lease 만료 시 `RUNNING→QUEUED` 재사용 → **기존 execution STALE terminal + 새 execution/attempt**.
- `JobRecord`가 FAILED 보관소 역할 → **JobExecution 실패 이력**.
- UsageRecord 구 스키마와 `JobRecord.cost` 집계 → **UsageRecord v1.2 authoritative ledger**.
- 임의 progress stage/percent 중심 → **CaseView progress/running_jobs projection**.
- “pytest/Ruff/type/gitleaks가 모두 CI에서 돈다” → **현재 CI는 boundary + contract 검사만 실제 동작**.
- “Docker Compose 배포 pipeline이 이미 있다” → **배포 목표 구조이며 api/worker/compose는 아직 미구현**.
- “proxy profile 전체가 실측 대기” → **Issue #41로 책임 경계·필요 profile 방향은 닫힘, exact media 값/품질/운영 수치만 Pending**.
## 29-8. 다음 문서화 단계
이 페이지를 더 크게 키우기보다 Runtime 구현이 시작되는 시점에 Git 문서로 분리한다.
1. **Runtime Tech Spec** — DB Queue, claim, retry, lease/heartbeat, stale sweep, Usage persistence, health/logging.
2. **Ops Spec** — EC2/Docker Compose, 배포, monitoring, disk/storage guardrail, retention/cleanup.
3. **Recording Benchmark Reference** — H.265/profile/A~D/1시간 E2E 실측 결과.
4. Architecture/Final Contract 내용은 복제하지 않고 링크/요약만 둔다.

---

# 30. Git 문서 분리 계획

> 이 파일은 **현재 Runtime/Ops 설계를 빠짐없이 옮겨 놓은 이관 기준본**이다. 최종 Source of Truth로 장기간 유지하는 문서가 아니다. 이 브랜치에서 분리·정합 검토를 끝낸 뒤, 최종 PR에는 중복 SoT가 남지 않도록 이 working 파일을 제거하는 것을 기본안으로 한다.

## 30-1. 왜 바로 여러 파일로 쪼개지 않는가

현재 문서는 Architecture, Final Data Contract, Runtime 구현값, Ops 정책, Recording/Search 실측, 과거 설계 이력까지 한 문맥 안에서 연결되어 있다.

처음부터 문단 단위로 여러 파일에 흩어 놓으면 다음 문제가 생긴다.

- 어떤 문장이 상위 Contract의 요약인지 Runtime의 새 결정인지 구분하기 어렵다.
- 이동 과정에서 STALE/retry, UsageRecord, storage lifecycle처럼 서로 연결된 조건이 빠질 수 있다.
- 같은 결정이 README, Tech Spec, Ops Spec에 중복 복제되어 나중에 서로 다른 값으로 drift할 수 있다.
- 이관 전 문서와 이관 후 문서를 사람이 대조하기 어려워진다.

따라서 **기준본 고정 → 책임별 분리 → 중복 제거 → 기준본 삭제** 순서로 간다.

## 30-2. 최종 권장 구조

최소 구조는 다음 세 문서로 시작한다.

```text
docs/runtime/
├─ README.md
├─ runtime-tech-spec.md
├─ ops-spec.md
└─ decisions/           # 실제 Runtime 결정이 생길 때만 추가
```

`common/runtime`은 여덟 번째 도메인 모듈이 아니므로 `docs/modules/common/`을 만들지 않는다.

### `docs/runtime/README.md`

역할은 **Runtime 문서의 입구와 경계 설명**이다.

담을 것:

- 문서 목적과 SoT 우선순위
- `case = orchestrator`, `common/runtime = executor`
- API / Worker composition root 관계
- 현재 구현 상태 요약
- Runtime Tech Spec / Ops Spec 링크
- 아직 열린 Runtime 결정 목록
- Architecture / Final Contract 링크

넣지 않을 것:

- JobExecution 전체 schema 복제
- retry 숫자 상세
- Docker Compose 전체 설정
- Recording 실측 표 전체

즉 README는 **“어디를 읽어야 하는가”**를 답하는 문서다.

### `docs/runtime/runtime-tech-spec.md`

역할은 **실행 인프라의 구현 계약**이다.

주요 대상:

- JobRecord Intent와 Runtime 경계
- DB Queue / claim
- JobExecution persistence
- idempotency와 cache/reuse 접합
- retry scheduling
- lease / heartbeat / STALE recovery
- startup / periodic stale sweep
- UsageRecord persistence
- Worker dispatch
- health endpoint의 기술 동작
- Runtime configuration
- DB transaction / locking
- 테스트 acceptance criteria

여기서 정하는 값은 Final Data Contract가 일부러 열어 둔 **Runtime 구현값**이다.

예:

```text
retry max
backoff / jitter
available_at
lease duration
heartbeat interval
STALE threshold
claim transaction
worker polling interval
```

단, JobExecution/UsageRecord의 schema 자체는 이 파일에서 다시 정의하지 않고 Final Contract를 링크한다.

### `docs/runtime/ops-spec.md`

역할은 **배포된 Runtime을 어떻게 운영할지**다.

주요 대상:

- EC2 / Docker Compose 배포 구조
- api / worker / mysql 프로세스 운영
- structured logging
- 개인정보/민감정보 logging guardrail
- monitoring / alert 기준
- health/readiness를 운영에서 사용하는 방식
- disk working set
- storage adapter / Object Storage 도입 기준
- cleanup / retention
- provider 장애 시 운영 절차
- capacity / scaling trigger
- 배포 전 security review
- CI/CD와 배포 검증

Runtime Tech Spec이 “코드가 어떻게 실행되는가”라면 Ops Spec은 **“실행 중인 시스템을 어떻게 관찰·복구·확장하는가”**를 답한다.

## 30-3. Recording/Search 실측은 Runtime 문서가 소유하지 않는다

현재 §21의 내용은 중요하지만 최종 Runtime 문서 안에 실측 원본을 복제하지 않는다.

소유권은 그대로 유지한다.

```text
recording
→ media/profile/ffmpeg/storage 관련 실측

search
→ provider 호환성 / recall / cost / latency 실험

runtime
→ 그 결과가 실행/저장/배포 설계에 미치는 영향만 참조
```

예를 들어 Real Recording Benchmark가 작성되면 Runtime/Ops에서는:

```text
"1시간 peak disk가 X였으므로 local working set guardrail을 Y로 둔다"
```

처럼 **결정에 사용한 결과와 링크**만 남긴다.

Benchmark 원본은 `docs/modules/recording/` 또는 `docs/modules/search/`의 해당 Owner 영역에 둔다. 새 파일명은 실제 실험이 시작될 때 Owner 문서 구조에 맞춰 정하고, Runtime 때문에 미리 빈 benchmark 문서를 만들지 않는다.

## 30-4. 현재 단일 문서의 이동 지도

| 현재 절 | 최종 처리 |
| --- | --- |
| §0, §1, §28 핵심 요약 | `docs/runtime/README.md`로 압축 |
| §3~§12 | `runtime-tech-spec.md` 중심 |
| §19 Health | 기술 동작은 Tech Spec, 운영 판정은 Ops Spec |
| §1-1 AWS 환경, §17~§20, §24 | `ops-spec.md` 중심 |
| §13 Logging | logging API/구조는 Tech Spec, 보존·마스킹·관측은 Ops Spec |
| §14 Test, §15 Toolchain, §16 CI | 우선 Ops Spec의 검증 절에 두되 repo-wide 개발문서가 생기면 이동 검토 |
| §2 Python 개발환경 | root `pyproject.toml`/workflow가 실행 가능한 SoT. prose는 중복 최소화 |
| §21 Recording/Search 실측 | Owner 문서 링크만 Runtime/Ops에 유지 |
| §22 과거 제안 처리 | 필요한 결정만 현재 문서에 흡수하고 표 자체는 최종 normative spec에서 제거 |
| §23 미도입 기술 | README 또는 Ops의 “Non-goals / Expansion trigger”로 압축 |
| §25 저장소 골격 | README에 현재 경계만 유지 |
| §26 운영 원칙 | README에 유지 |
| §27 책/학습 참고 | 최종 normative spec에서는 제거 가능 |
| §29 audit trail | PR description/Git history + 각 문서 References로 축소 |

## 30-5. 분리할 때의 중복 제거 규칙

### 1. Architecture를 복사하지 않는다

`module-architecture.md`가 이미 정한 다음 내용은 Runtime 문서에서 다시 규정하지 않는다.

- 7개 도메인 모듈
- case orchestrator
- common/runtime executor
- API 1 + Worker 1 baseline
- MySQL DB Queue 방향

Runtime 문서는 **그 결정을 어떻게 구현할지**만 쓴다.

### 2. Final Data Contract schema를 복사하지 않는다

다음은 링크가 authoritative다.

- JobRecord
- JobExecution
- UsageRecord
- AnalysisSource / RemoteCopy / DerivedAsset
- CaseView

Runtime 문서에 필요한 것은 “어떤 필드를 어떤 DB 동작에 사용한다”는 구현 설명이다.

### 3. Owner 실험값을 복사하지 않는다

Recording/Search 수치가 바뀌면 Runtime 문서까지 두 군데 수정하게 만들지 않는다.

Runtime/Ops에는:

- 어떤 실험 결과를 사용했는가
- 그 결과로 어떤 결정을 했는가

만 남긴다.

### 4. 동일한 설정값은 한 문서만 소유한다

예:

```text
lease duration             → Runtime Tech Spec
disk alarm threshold       → Ops Spec
Python version             → pyproject / CI executable config
profile exact FPS          → recording Owner
retryable provider error   → provider/failure taxonomy + Runtime mapping
```

## 30-6. 권장 커밋 순서

### Commit 1 — 이관 기준본

```text
docs(runtime): import runtime-ops working spec
```

현재 브랜치의 첫 단계다.

- 현재 설계를 한 파일에 보존
- source-platform 전용 표기 제거
- 분리 계획 기록
- 아직 기존 문서를 삭제하지 않음

### Commit 2 — Runtime Tech Spec 분리

```text
docs(runtime): split runtime execution tech spec
```

- §3~§12 중심으로 이동
- DB Queue / retry / lease / heartbeat의 미결값을 명확히 표시
- Contract schema 중복 제거
- 실제 구현 상태와 목표 상태 분리

### Commit 3 — Ops Spec 분리

```text
docs(runtime): split runtime operations spec
```

- deployment / logging / monitoring / storage / cleanup / capacity 이동
- Recording/Search benchmark는 링크로 치환
- CI와 pre-deploy guardrail 정리

### Commit 4 — README와 cross-link 정리

```text
docs(runtime): add runtime docs index and reconcile references
```

- README를 entry point로 만듦
- Architecture/Contract/Owner 문서 링크 점검
- 같은 규칙이 두 파일에 중복됐는지 검사
- 기존 `src/daesingo/common/README.md`의 오래된 `JobRecord lifecycle` 표현도 별도 범위로 정합화 가능

### Commit 5 — working 기준본 제거

```text
docs(runtime): remove migration working spec
```

분리된 문서와 기준본의 내용 대조가 끝났다면 `runtime-ops-working-spec.md`를 삭제한다.

**최종 develop에는 “working 원본 + split 문서”가 동시에 남지 않게 한다.** 이관 원본은 Git commit history에서 언제든 다시 볼 수 있다.

## 30-7. 분리 완료 판정 체크리스트

- [ ] README에서 Runtime 문서 전체 진입점이 보인다.
- [ ] Runtime Tech Spec과 Ops Spec의 책임이 겹치지 않는다.
- [ ] JobRecord / JobExecution / UsageRecord schema를 로컬 문서가 재정의하지 않는다.
- [ ] retry/lease/heartbeat 수치의 Owner가 Runtime Tech Spec 하나다.
- [ ] deployment/storage/monitoring 수치의 Owner가 Ops Spec 하나다.
- [ ] Recording/Search benchmark 원본은 각 모듈 Owner 위치에 남아 있다.
- [ ] 현재 구현값과 목표값이 문서에서 구분된다.
- [ ] source-platform 전용 링크/댓글/mention이 없다.
- [ ] `common/runtime`을 8번째 도메인으로 오해하게 하는 경로가 없다.
- [ ] working 기준본을 제거해 중복 SoT를 남기지 않는다.

## 30-8. 이번 브랜치에서 어디까지 할 것인가

현재 커밋에서는 **기준본 이관 + 분리 계획 확정까지만** 한다.

다음 작업은 이 문서의 내용을 기준으로 실제 `README.md`, `runtime-tech-spec.md`, `ops-spec.md`를 만드는 것이다. 분리 과정에서 새 기술 결정을 끼워 넣지 않고, 기존 결정을 이동·정규화한 뒤 **새로 결정해야 하는 Runtime 구현값은 별도 표시**한다.

이 방식이면 문서 분리가 곧 설계 변경으로 변질되는 것을 막을 수 있고, PR에서 “내용이 바뀐 것인지 단지 위치가 바뀐 것인지”도 리뷰하기 쉬워진다.
