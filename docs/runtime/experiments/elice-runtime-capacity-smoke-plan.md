# Elice Runtime Capacity Smoke Plan

**Status:** Planned — 구현/실행 전 설계  
**Owner:** common/runtime — 김준영  
**Design input:** Issue #95 P0/P1/R3  
**Ops baseline:** [Runtime Ops Spec](../ops-spec.md)  
**Experiment router:** [Runtime Experiments](./README.md)

> 이 문서는 #95의 Search/Recording 실험을 다시 수행하거나 canonical media profile을 확정하는 문서가 아니다. 이미 확인된 module 사실을 실제 Runtime baseline에서 조합했을 때 **capacity, working set, cleanup, concurrency 가정이 유지되는지** 검증하기 위한 P2 계획이다.

## 1. 왜 필요한가

Issue #95 P0/P1/R3에서 다음 흐름은 실제 호출/로컬 실험으로 확인됐다.

```text
Recording AnalysisSource materialization
→ open_analysis_source()
→ Search가 binary media 획득
→ base64 data URL
→ JSON request
→ Elice ML API
```

또한 다음 운영 영향이 확인됐다.

- inline media 전송은 binary보다 더 큰 request body와 추가 process memory working set을 만들 수 있다.
- ffmpeg materialization은 CPU/RAM/time/temp disk를 사용한다.
- 동일 `source + span + profile`의 process-local reuse는 materialization 비용을 크게 줄일 가능성이 있다.
- Elice 경로는 provider-side reusable object를 기본 가정으로 둘 수 없다.

하지만 아직 baseline 배포 환경에서 아래 조합을 함께 실행하지 않았다.

```text
api
+ worker
+ mysql
+ ffmpeg
+ AnalysisSource bytes
+ base64 encode
+ JSON serialization
+ provider HTTP request
```

따라서 module benchmark만으로 `t3.medium / 4GB / 50GB / Worker 1` baseline이 충분하다고 결론 내리지 않는다.

## 2. 이 실험이 닫아야 하는 질문

P2가 끝나면 최소 다음을 설명할 수 있어야 한다.

1. Worker concurrency=1에서 대표 Real media path가 OOM/crash 없이 완료되는가.
2. ffmpeg materialization과 request construction 시 EC2/Worker peak CPU·RAM이 어느 정도인가.
3. api/mysql과 Worker가 같은 host에서 자원을 경쟁할 때 눈에 띄는 contention이 있는가.
4. temp media와 request working set이 정상·실패 후 회수되는가.
5. cold materialization 대비 warm local reuse의 이득과 steady-state disk 비용은 무엇인가.
6. Worker/process restart 후 재생성 비용은 어느 정도인가.
7. Worker concurrency 증가를 검토할 자원 여유가 있는가, 아니면 먼저 host/storage 구조를 바꿔야 하는가.

## 3. 이번 단계에서 결정하지 않는 것

P2 계획만으로 다음을 확정하지 않는다.

- canonical AnalysisSource profile
- 최종 clip length / overlap
- coarse/fine 최종 media quality
- Worker count > 1
- EC2 spec 상향
- Object Storage / shared cache 도입
- cache TTL / retention
- pricing SSOT / provider label / key naming
- 30분~1시간 P3의 exact 입력과 threshold

provider/usage/pricing/config ownership은 Issue #153의 Search 전수조사 결과를 기다린다.

## 4. 첫 시험 입력 후보

첫 smoke candidate:

```text
duration    20s
resolution  480p
codec       H.264
container   MP4
audio       off
```

이 값은 #95 P1에서 실제 Elice 호출과 비교적 작은 transport size가 확인되어 **첫 capacity fixture 후보**로 사용하는 것이다.

다음 의미는 아니다.

```text
20s / 480p
≠ canonical Search profile
≠ Runtime contract
≠ 운영 상수
```

Search/Recording이 이후 profile을 바꾸면 P2 입력도 그 결정에 맞춰 다시 실행할 수 있다.

## 5. 실행 환경

현재 baseline:

```text
EC2          t3.medium
CPU          2 vCPU
RAM          4GB
Disk         50GB SSD
OS           Ubuntu 24.04 LTS
Deployment   Docker Compose

services
- api
- worker
- mysql
```

실제 Compose/API/Worker가 아직 구현되지 않은 시점의 로컬 preflight는 측정 도구·경로 검증에만 사용할 수 있다.

**P2 완료 판정은 실제 baseline과 동등한 배포 환경에서 api/worker/mysql 조합을 포함해 실행한 결과**를 기준으로 한다.

## 6. 기준 실행 경로

목표 경로:

```text
JobRecord
→ Runtime dispatch / DB Queue
→ Worker claim
→ Recording AnalysisSource
→ Search capability
→ binary read
→ base64 encode
→ JSON serialize
→ Elice call
→ provider response normalize
→ Usage observation
→ domain result
→ cleanup
→ JobExecution terminal
```

Queue/Worker가 아직 구현 전이라면 preflight에서는 capability 경로만 검증할 수 있지만, 그 결과를 P2 완료로 취급하지 않는다.

## 7. 관측 항목

### Host

- EC2 CPU utilization
- available/used RAM
- swap 사용 여부
- disk 사용량 / temp working set
- disk I/O가 가능하면 함께 기록

### Process

가능한 범위에서:

- api RSS
- worker RSS
- mysql RSS
- ffmpeg process peak RSS / CPU
- Worker request construction 전후 RSS

### Media / Transport

- source bytes
- materialized AnalysisSource bytes
- base64 bytes
- serialized request body bytes
- materialization elapsed time
- provider round-trip latency
- end-to-end execution latency

### Runtime

실제 Queue가 구현된 뒤:

- queue wait
- execution duration
- retry 여부
- Worker heartbeat/lease 상태
- JobExecution terminal status
- cleanup success/failure

Usage/cost는 관측하되 pricing 데이터의 SSOT 구조는 #153 결과 전에 P2가 정하지 않는다.

## 8. 실험 순서

### P2-A — concurrency=1 cold path

대표 입력을 새로 materialize해서 전체 경로를 한 번 관통한다.

목적:

- baseline working set 파악
- ffmpeg와 request construction peak 분리
- 정상 cleanup 확인

### P2-B — concurrency=1 warm reuse

동일 `source + span + profile`을 다시 요청한다.

비교:

- materialization 시간
- total latency
- disk steady state
- Worker RSS
- 재사용된 ref/asset의 일관성

### P2-C — failure / cleanup

안전한 실패 조건을 만들어 확인한다.

예:

- provider timeout
- materialization 실패
- 실행 중 취소/Worker 종료는 Runtime lifecycle 구현 뒤 별도 실행

관측:

- partial temp media 잔존
- request payload/raw media가 로그에 남는지
- terminal execution 상태
- retry 대상 여부
- disk/RAM 회수

### P2-D — restart / reuse boundary

Worker/process restart 전후 동일 입력을 비교한다.

목적:

- 현재 reuse가 process-local이라는 가정을 실제로 확인
- restart 후 duplicate materialization 비용 측정
- persistent/shared cache가 필요한지 판단할 근거 확보

### P2-E — concurrency 증가 탐색

**P2-A~D가 설명된 뒤에만** 검토한다.

concurrency=2 이상은 목표값이 아니라 탐색 조건이다. concurrency=1에서도 OOM/swap/지속 CPU saturation 또는 api/mysql contention이 보이면 먼저 원인을 줄이고 Worker 수를 늘리지 않는다.

## 9. 완료 기준

현재 단계에서 RAM/CPU percentage 같은 임의의 PASS 숫자를 만들지 않는다.

P2 1차 완료는 다음 질문에 측정 근거로 답할 수 있는 상태다.

- 현재 baseline을 유지할 수 있는가
- Worker concurrency=1을 유지해야 하는가
- EC2 spec 상향이 필요한가
- local disk guardrail을 더 좁혀야 하는가
- process-local reuse로 충분한가
- persistent/shared storage 실험이 필요한가
- P3 long-duration Runtime E2E를 어떤 조건으로 설계해야 하는가

결론이 “추가 측정 필요”여도 어떤 미확인 변수가 남았는지 특정할 수 있으면 결과 문서에 그대로 남긴다.

## 10. 결과가 바꿀 수 있는 결정

```text
P2 result
├─ baseline 여유 충분
│  └─ t3.medium + Worker 1 유지
│
├─ CPU/RAM contention
│  ├─ media path/profile 영향 재확인
│  └─ 필요 시 EC2 spec 상향 검토
│
├─ disk/reuse 문제가 병목
│  └─ persistent/shared storage 또는 Object Storage 실험 검토
│
├─ provider-bound + host 여유
│  └─ DB claim/lease concurrent-safe 확인 후 Worker pool 탐색
│
└─ 장시간 입력에서만 불확실성 큼
   └─ P3 30분~1시간 Runtime E2E plan 작성
```

P2 결과가 여러 구현과 향후 migration에 장기 영향을 주는 구조 결정을 만들면 `docs/runtime/decisions/` ADR로 승격한다.

예:

- baseline topology 변경
- persistent/shared AnalysisSource storage 도입
- Worker scaling model 변경

## 11. Evidence 기록 규칙

실제 실행 시 최소 다음을 결과에 남긴다.

```text
executed_at
commit_sha
environment / EC2 type
docker image/revision (해당 시)
input fixture identity
AnalysisSource profile identity
worker concurrency
host CPU/RAM/disk observations
process peak observations
materialized bytes
request body bytes
latency
queue/execution observations
cleanup result
known limitations
```

secret, raw media bytes, base64 payload 전문, 번호판 문자열, 정확한 위치 원문은 결과 문서에 남기지 않는다.

## 12. 다음 단계

P2 결과를 먼저 Runtime Ops/Tech 가정과 대조한다.

그 뒤 장시간 workload가 여전히 중요한 미확인 변수라면 별도의 P3 30분~1시간 Runtime E2E plan을 작성한다.

```text
#95 P0/P1
→ P2 Runtime Capacity Smoke
→ Tech/Ops 결정 갱신
→ 필요 시 ADR
→ 필요 시 P3 Long-duration Runtime E2E
```

## References

- [Issue #95 — Elice ML API migration tracker](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95)
- [Issue #153 — provider usage · pricing · runtime config boundary review](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153)
- [Runtime Ops Spec](../ops-spec.md)
- [Runtime Tech Spec](../runtime-tech-spec.md)
- [AnalysisSource / RemoteCopy Contract](../../architecture/contracts/contract-analysis-source-derived.md)
- [UsageRecord Contract](../../architecture/contracts/contract-usage-record.md)
