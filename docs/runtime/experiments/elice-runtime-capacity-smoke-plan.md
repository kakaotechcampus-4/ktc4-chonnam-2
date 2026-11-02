# Runtime Capacity Smoke Plan — P2 (Elice ML API)

**Status:** Planned — 현재 구현과 재정합화, P2 실험 미실행\
**Reviewed:** 2026-11-02 KST · fetched `develop` `15b8b6a1658652fa16ea86d490df9f6bbe24e5bc`\
**Owner:** common/runtime — 김준영 · Recording/Runtime 구현 정철원\
**Inputs:** #95 P0/P1/R3 · #452 · RT-01~RT-14 · [실행환경](../local-runtime-environment.md)\
**Router:** [Runtime Experiments](README.md) · **Policy:** [Tech](../runtime-tech-spec.md) / [Ops](../ops-spec.md)

**제품 정합성 재검토:** 2026-11-02 · [Product Spec](../../product/product-spec.md) 및 이번 PM 요청.
구현 감사 SHA는 위 snapshot으로 보존하며, Product Spec은 이후 `develop` `c39353ad`의 #531 변경까지 대조했다.

이 문서는 **계획**이다. [수정 전 정합성 감사](../reviews/runtime-p2-plan-audit-2026-11-02.md)를 먼저 수행했다.
AWS 실험·provider 호출·배포·rollback·fault injection·실제 22개 영상 실행이나 Runtime 코드 변경은 하지 않았다.
현재 develop 구현과 과거 AWS 배포 RC를 구분한다. 파일명은 inbound link 호환을 위해 유지한다.
Elice는 여전히 현재 Search의 실제 provider 경로이며, 과거 Flash 모델 전제를 뜻하지 않는다.

## 0. 감사 결과와 이미 있는 evidence

| 기존 항목 | 판정 | 현재 계획의 변화 |
| --- | --- | --- |
| P2-A cold normal | UPDATE / EVIDENCE EXISTS(기본 관통) | AWS 관통을 다시 증명하는 대신 대표 입력의 자원·구간별 시간 측정 |
| P2-B warm reuse | SPLIT / UPDATE | 같은 Worker의 별도 job 반복과 같은 RecordingService 안의 reuse를 구분 |
| P2-C failure/cleanup | KEEP(질문) / UPDATE / SPLIT | duration·bytes·Search 실패·crash 잔여와 temp 경로를 구분 |
| P2-D restart | UPDATE / EVIDENCE EXISTS(일부 내구성) | durable ref 읽기와 새 job 재준비를 분리. restore/release rollback은 RT-14로 REMOVE |
| P2-E concurrency | UPDATE | process당 execution=1 유지. 복수 Worker는 별도 target·gate 필요 |
| P2-F lifecycle | SPLIT / UPDATE | F1~F5별 target·계측 공백 명시. 미구현 전제 REMOVE |
| #452 결합 검증 | ADD | P2-0a 현 baseline 안전 거부 regression / P2-0b 현 baseline 안 characterization / P2-0c 격리 capacity probe. 20분 logical timeline 판단으로 연결 |

### 0.1 RT-14 evidence와 책임 경계

[10/31 Result](2026-10-31-rt14-aws-real-e2e.md)의 배포 RC는 `e50b2976`이며 위 감사 develop과 다르다.
같은 설정 이름이나 merged PR만으로 현재 배포된 코드·config 적용을 단정하지 않는다.
실험 시작 때 exact image/revision/config/schema를 다시 대조한다.

| 질문 | 현재 evidence / 남은 것 | P2와의 관계 |
| --- | --- | --- |
| AWS 실제 조립·public 경로 관통 | Result §2·6·8: OIDC/SSM·ECR·secret 공급·8종 registry, 실제 7 job·신고영상 다운로드 PASS | DONE/EVIDENCE EXISTS. 동일 단회 관통을 P2 필수 재실험으로 두지 않음 |
| capacity | 5.533333초 비식별 입력 1개·2초 sampling. Recording 단독 준비시간 미계측, 짧은 peak 누락 가능 | 대표/반복·분해 계측이 필요. 단회 RSS/CPU/temp를 상수·threshold·p95로 승격하지 않음 |
| UID/재부팅/알려진 secret 사본 정리 | Result §14의 운영자 제공 완료 보고 | 좁은 후속 완료. 장애 복구·모든 secret/보안 검수 완료가 아님 |
| DB·media backup/격리 restore | [Recovery §10](../rt14-recovery-acceptance.md#rt14-recovery-operator-results), Result §15: 운영자 보고상 단회 PASS, Case/asset·BLOB/media 비교 및 offline toolchain PASS | 이미 수행된 것을 TODO로 되돌리지 않음. 복원 DB의 정상 Worker claim/job/반영은 미검증 |
| 두 번째 deploy / rollback rehearsal | 현재 후속 기록에서 미완료 | Deployment/RT-14 소유. P2-D가 대체하지 않음 |
| public endpoint 최신 재확인 | 10/31 외부 검증자 PASS 뒤 운영 복귀 확인은 local HTTPS 403 | 외부 Web 200 재확인 미완료. 제한된 public P2 직전 확인 대상 |
| Recording profile/limits | #526·#528로 초기 배포 baseline v1 확정·문서 정합화. #460의 파일 값 9/9 대조는 process reload 증거 아님 | 운영 최적값·약 1시간 지원·전체 지원 범위 결합 검증은 남음 |
| off-host backup / RPO·RTO | 보관 정책·승인 목표/복구시간 보장은 미완료 | Ops/Recovery가 소유. 작은 restore PASS로 닫지 않음 |
| Package READY | PLATE_IMAGE_EXPORT·사건시각 drawtext·최종 package 생성/소비 미검증 | 입력 조건을 갖춘 별도 E2E. 작은 capacity 실험의 공통 선행조건은 아님 |
| 장기 공개 gate | 인증/IDOR·admission/비용·retention/동의·감시 등 남음 | 별도 hardening. 검증자 제한을 풀어 P2를 하지 않음 |

RT-14 전체는 **IN_PROGRESS**다. workflow §8 구현·관측에서 §9의 일부 Real E2E와 §10 기록까지 진행됐고,
P2의 M7→M8 capacity/timing 최종 검증·§11 승격은 남아 있다.
10/02 README/Tech 구현 snapshot, Register RD-09의 in-memory 설명, RT-14 초기 절의 pending 표현은
현재 구현의 부재로 읽지 않는다. 감사 문서가 이 시점 차이를 추적한다.

## 1. 목적

현재 승인된 Recording/Search 설정과 Runtime을 같은 배포 환경에 조합했을 때
**working set·시간·queue·실패 의미·cleanup·복구 관측**이 유지되는지 검증한다.
이를 [Product Spec §3~§5·§9](../../product/product-spec.md)의 **장시간·다중 블랙박스에서 사건 후보를 먼저 찾고
Coarse → Fine으로 필요한 장면을 정밀 검증한다는 제품 약속**에 연결한다.
이번 PM 방향은 우선 **최소 20분 logical timeline 지원 가능성**을 판단할 근거를 수집하는 것이다.
현재 20분 지원 확정이나 acceptance 완료를 뜻하지 않는다. capacity probe는 자원·시간·최초 병목을 측정하며,
Product Spec의 Top-3 탐색 성능·실용적인 비용/시간까지 입증하는 제품 acceptance는 Search/Eval/Case 검증과 함께 판단한다.

Analysis 48 MiB/4분은 **초기 배포 안전 baseline v1·실험 시작점·현재 configuration snapshot**이다.
PM 승인 최종 지원 길이·MVP 제품 요구사항·장시간 탐색 포기 결정이 아니다.
지원 범위·Must/Won't·불변 경계 변경의 최종 승인자는 Product Spec이 정한 **PM 김준영**이며,
모듈 Owner의 설정/구현 결정이나 Runtime 실험 결과가 이를 대신하지 않는다.

Product Spec §5의 `2시간 원본을 무조건 전체 서버 업로드` Won't는 전송·비용·privacy 때문에
범위축소/proxy/clip 전략이 필요하다는 뜻이다. 장시간 logical timeline 탐색을 포기하거나
반드시 하나의 거대한 AnalysisSource/BLOB으로 처리한다는 뜻이 아니다.
Spec §8의 `약 20분 → 약 3분`은 사용자 직접 작업시간 목표이며, 이번 **영상 timeline 최소 20분** 목표의 수치 근거로 전용하지 않는다.

Recording profile/limits의 원문은 [AnalysisSource limits](../../modules/recording/analysis-source-limits.md)와
[환경·배포 설정 명세 §3](../../management/environment-and-deployment-config.md#3-recording-초기-배포-baseline-v1)다.
Search provider/media/retry 의미와 Case 대기·notice는 각 Owner 문서를 따른다. 이 계획이 값을 새로 소유하지 않는다.

```text
P2-0a: current baseline regression ≠ final product support range
P2-0b: 현 baseline 안의 자원·시간·결합 특성
P2-0c: 격리 experimental override로 현 single-source 구조의 최초 병목 측정
→ Decision Gate: 최소 20분 logical timeline 가능성 / 필요한 후속 설계 판단
→ P3: 30~60분 logical timeline Real E2E, 처리 방식 미정
```

## 2. 닫을 질문

1. concurrency=1의 대표 단일/다중 원본에서 Recording·Search·OCR과 API/MySQL의 자원 경합은 무엇인가.
2. prepared BLOB·DB driver·Search 재인코딩·base64/JSON의 동시 working set과 실제 저장/전송 여유는 얼마인가.
3. 큐·Recording 준비·Search 준비·provider·T1/T2·Case-visible elapsed를 나누어 기존 대기 예산과 설명할 수 있는가.
4. #452 입력이 **현 baseline 한도 초과 시** 늦은 MySQL disconnect 대신 typed terminal failure·재시도 없는 notice로 끝나는가. 이 결과는 제품 지원 범위 결정과 분리한다.
5. 정상/실패 후 temp·자식 process·메모리가 회수되고, durable 원본/파생물 증가와 잔여 temp를 구분할 수 있는가.
6. 반복 job·process restart에서 무엇을 다시 준비하고 무엇을 ref로 복원하며 비용은 얼마인가.
7. 실제 정상 부하의 heartbeat gap·STALE·retry·cancel 관측으로 B-L*/B-R*/B-X1을 재검토할 수 있는가.
8. 복수 Worker 탐색이 필요하고 실행 가능한지 근거가 있는가. Worker 수/인프라 변경은 결과 뒤 Owner가 판단한다.
9. 격리 target에서 현 single-AnalysisSource/단일 Coarse request 구조의 최초 병목은 어디인가. 그 근거로 최소 20분 logical timeline 지원 가능성 또는 구조 재검토 필요성을 설명할 수 있는가.

## 3. 결정하지 않는 것

- Recording canonical/최적 profile·**운영** duration/byte 한도·제품 최종 지원 범위 변경, Incident 품질, Search recall/최종 media quality. P2-0c의 실험 전용 한도는 별도 기록한다.
- Case timeout/기산점 변경·chunking 구현·Web 접수 정책을 이 문서에서 확정하지 않는다. [기존 긴 범위 결정](../../modules/case/decisions/long-analysis-range.md)의 MVP 분할 제외는 현재 구현/Owner 결정 이력이며 PM의 장시간 제품 약속을 축소한 최종 정책이 아니다. 0c 결과가 제품 목표 미충족을 보이면 bounded/chunked processing 등을 포함한 cross-module 설계를 다시 연다.
- Worker count 확정·EC2/EBS 증설·Object Storage·RDS·전용 Queue·GPU 도입.
- retention/purge·off-host backup·RPO/RTO·공개 운영 승인·pricing/FX 정책.
- #452/#450 종료, RT-14 rollback/recovery·Package READY 완료 선언.

기존 숫자는 실험의 **입력 또는 기존 측정 목표**다. 새 CPU/RAM/disk/latency PASS threshold를 만들지 않는다.
단회 수치와 지원 길이 비례 추정은 운영 보장값이 아니다.

## 4. Fixture 종류와 선택

| 종류 | 후보·근거 | 선택/통제 |
| --- | --- | --- |
| minimal smoke | #95 P1의 20s/480p/H.264/MP4/audio off는 여전히 작은 후보 | 역사적 transport 후보이며 production encoding 설정이 아님. 실제 확보/권한/manifest 확인 후 선택 |
| RT-14 continuity | Result §8.1의 비식별 `aws-real-e2e-001`, 5.533333초 사본 | 기본 관통 증거는 재사용. 원본/사본을 혼동하거나 20초 후보와 동일시하지 않음. 무조건 재호출하지 않음 |
| representative | P2-0b용 **현 baseline 한도 안**의 주·야간, 움직임/노이즈/복잡도가 다른 영상, 단일/다중 원본 | 내용별 CRF byte 차이와 concat 비용을 비교. 같은 footage의 길이 변형만으로 대표성 주장 금지 |
| boundary | 현 duration 상한의 직전/동일/초과, bytes가 큰 유효 입력 | length=limit은 허용·초과만 거부라는 기존 의미. exact-byte synthetic 증거와 실영상 측정을 구분. byte 초과를 만들려고 DB packet을 낮추거나 운영 한도를 바꾸지 않음 |
| long regression | #452 실제 22개, 총 1,166.131초(약 19분 26초), 당시 H.264/1080p·같은 time base | **0a의 baseline v1에서만** 안전 거부가 기대값. 제품적으로 계속 거부하기로 정한 입력이 아님. SHA/길이/stream 순서·권한 확보 필요 |
| isolated long probe | 0c용 짧은 대표→긴 대표→약 10분급→약 20분급의 연속된 logical timeline | 확보 fixture·비용/자원 예산으로 단계 조정. single/multi 원본을 한 AnalysisSource/Coarse로 처리하는 현재 경로 유지. 19분 26초를 최소 20분 달성 표본으로 올림하지 않음 |

본 감사에서는 실제 22개나 새 대표 fixture를 확보·실행하지 않았다. Git에 있는 합성 fixture/test는 그 대체품이 아니다.
`1/2/3/4분` grid를 확정하지 않는다. 먼저 확보된 입력의 duration/bytes/복잡도·현재 상한을 대조해
0b는 짧은 대표→긴 대표→현 상한 인접, 0c는 별도 실험 한도/중단 계획에 따라 더 긴 timeline을 선택한다.
선정 이유·개수·반복 수·비용 한도를 실행 전에 기록한다. 최소 20분을 판정할 실제 입력이 없으면 그 목표는 미검증으로 남긴다.
4분 이하라도 bytes·coverage·Search/time 조건으로 실패할 수 있다. 하나의 영상으로 “N분까지 안전”을 결론 내리지 않는다.

## 5. 실행 환경과 현재 baseline

완료 근거는 실제 baseline과 동등한 **API + Worker + MySQL + media/provider 경로**를 포함한다.
로컬 mock/module probe·합성 CI는 각각의 경계 증거다. AWS 결과로 합산하지 않는다.

| 층 | 감사 시점 기준·실행 전 확인 |
| --- | --- |
| host | EC2 t3.medium/2 vCPU/약 4GiB/50GB root, Ubuntu 24.04. 실제 가용량·CPU credits/unlimited 비용·다른 작업/backup/image 공간은 재조회 대상 |
| local Compose | `compose.yaml`: api 1/worker 1/mysql + one-shot migrate, named media/DB volume, local log driver. Web/Caddy는 Compose service가 아님 |
| production | `deploy/ec2.py:production_compose`: exact image/digest, build/depends_on 제거, external DB/media volumes, awslogs non-blocking + local cache, policy restart, API loopback. Caddy host·release-bound Web·EIP/DDNS/TLS 별도 |
| Worker | B-W1/B-W2: process 1, execution 1. 실행별 Recording/Search 서비스와 UsageSink, heartbeat/sweep 별도 thread. 내부 concurrency env 없음 |
| tools | 현재 Dockerfile의 Python 3.12·동일 build FFmpeg/ffprobe 8.1·사전 탑재 Paddle/OCR·Linux amd64. RT-14보다 새 코드는 새 artifact 검증 필요 |
| Recording 입력 | 위 설정 SoT의 baseline v1: Analysis `aws-e2e-v1 / 480 / veryfast / CRF23`, `50331648 bytes / 240000 ms`(48 MiB/4분), Incident `240 / veryfast / CRF23`. **현재 배포 안전값 snapshot**이며 코드 기본값/최적값·PM 승인 최종 제품 한도 아님. 0c는 별도 experimental config를 사용 |
| lifecycle 입력 | [Baseline](../provisional-baseline-v0.1.md) B-Q*/B-L*/B-R*/B-D*/B-X1과 `common/config` 기본값 일치 확인. heartbeat 10s/lease 60s/sweep 15s, STALE retry 1회·첫 backoff 5s는 Provisional 입력. 실제 override와 시계 상태 기록 |
| config/secret | 보호 runtime 파일→bootstrap의 immutable snapshot. Worker는 `GEMINI_API_KEY` 소비. Search/eval alias와 다름. Parameter Store/보호 host 파일·immutable config/recreate 절차는 [실행환경](../local-runtime-environment.md)·[공개 배포 Notes](../rt14-public-deployment.md) 소유 |

48 MiB + 기존 policy margin < session packet이라는 배포 guard는 **SQL escaping/driver buffer·메타데이터 여유의 실증이 아니다**.
실제 DB packet은 SELECT로 확인하고 BLOB bytes만 보고 저장 가능을 판정하지 않는다.
runtime.env 파일 값 일치와 이미 실행 중인 process 적용도 구분한다.
host Caddy는 검증자 IP 제한·64 MiB body 제한이 있고 repo Caddyfile과 차이가 있다([설정 명세](../../management/environment-and-deployment-config.md)).
22개 원본의 개별 파일이 이 upload 제한에 걸리면 거부 regression이 Recording까지 도달하지 못한다.
운영 ingress 경계를 넓히지 말고 별도 experimental target의 검토된 ingest/기존 등록 사본 경로를 준비하거나 BLOCKED로 남긴다.

## 6. 현재 실행 경로와 reuse 경계

```text
API → Case command/JobRecord + Runtime enqueue [같은 transaction]
→ job_execution QUEUED → claim/lease [짧은 RC transaction, SKIP LOCKED]
→ Worker 실행별 heartbeat + DurableUsageSink
→ Recording ownership/scope/resolve/time-source 관찰 → duration guard
→ encode/누적 bytes/concat guard → AnalysisSource metadata+BLOB publish [짧은 transaction]
→ Search: stream 복사/probe → Coarse/Fine 재인코딩 → media cap
→ base64 data URL/JSON request cap → Elice HTTP [시도별 usage begin/finish]
→ Run/produced + JobExecution terminal T1 → usage reconciliation
→ Case reflection T2 [Case 저장+후속 JobRecord/enqueue+case_applied_at]
```

근거: `api/composition.py`, `common/jobs/{repository,worker_loop,reflection,redelivery}.py`,
`worker/{composition,production_media,search_handlers}.py`, `recording/{service,mysql_repository}.py`.
Usage 최종화 일부는 Search가 Run 확정 뒤 수행하며, T1 이후/주기 reconciliation이 잔여를 회수한다.
동일 terminal 재기록/T2 redelivery가 provider 재호출을 뜻하지 않는다. 자동 새 execution retry는 STALE만이다.

현재 `search/config.py` 기본 Coarse/Fine은 `gemini-4-argon`, Intent는 `gemini-3.8-flash`의 별도 tenant다.
Elice OpenAI-compatible `/v1/chat/completions`, inline base64는 유지된다. Files API/RemoteCopy reuse는 전제하지 않는다.
`search/media.py`는 AnalysisSource를 다시 준비한다(Coarse 360p·원본 2fps, Fine 360p·4fps, audio off·재생 길이 확장).
현재 Search media 40 MiB/request 56 MiB cap은 Search 코드 소유이며 Recording 48 MiB와 다른 단계다.
현재 Case는 전체 timeline을 하나의 Coarse scope/request로 발주하는 구현이며 chunked Coarse는 최종 합의/구현된 구조가 아니다.
`provider.py`는 요청 크기 확인 뒤 네트워크에 진입하고 SDK retry=0, Search `retry.py`의 429/5xx retry를
RunDeadline 안에서 수행한다. Recording preparation은 Search RunDeadline 시작 전이며 Case 대기에는 포함된다.
실행별 model/config version/fingerprint·Usage provider_label로 override 적용을 확인한다.

**reuse 세 층을 혼동하지 않는다.**

1. Case의 성공 결과 reuse는 새 Worker execution 자체를 생략할 수 있다. Case/JobRecord로 확인한다.
2. Recording `_analysis_reuse`는 **같은 service instance**의 dict다. 현재 production은 invocation마다 새 instance이므로 같은 Worker의 다음 job은 warm materialization hit가 아니다.
3. prepared media는 MySQL BLOB에 남아 ref로 다시 열 수 있다. 하지만 로컬 원본의 새 preparation은 자동 persistent cache lookup을 하지 않고 다시 encode/publish한다. durability와 deduplicated reuse는 별개다.

## 7. 관측 방법과 instrumentation gaps

### 7.1 지금 있는 Runtime 관측

`common/jobs/metrics.py:read_metrics`는 보존 행 **전체 snapshot**의 read-only query다.
실험 window/lineage별 표본은 보호된 SELECT/로그 추출로 따로 한정한다. 전역 before/after 차이만으로
다른 작업이 섞인 실험을 귀속시키지 않는다. timestamp는 DB UTC/causal 값이고 raw monotonic elapsed와 다르다.

| 논리 지표 | 현재 출처·해석 |
| --- | --- |
| `runtime.queue.wait_ms` | DB `started_at-queued_at`, Worker 같은 이름 log. attempt 1/2+ 분리; retry는 backoff 포함 |
| `runtime.execution.duration_ms` | DB `ended_at-started_at` kind/status별. **동명 독립 emitter 없음**. `runtime.execution.completed.duration_ms`는 Worker monotonic 구간이며 동일 정의가 아님 |
| heartbeat `lag_ms`/`attempt_ms` | 실제 log `duration_ms`. lag는 성공 간격-cadence, attempt는 전체 hard timeout 없음 |
| heartbeat `skipped_tick_count`/`consecutive_failures` | 실제 log의 **status 숫자**를 파싱. 실패 횟수는 STALE 조건 아님 |
| `runtime.stale.count` / `detect_latency_s` | retained DB fact + 실제 log. log의 `duration_ms/1000`으로 초 변환, null heartbeat는 누락 |
| `runtime.stale.false_count` | 원래 owner의 terminal 0-row 뒤 durable STALE 확인 때 count=1. fence로 terminal 시도 자체를 못 한 경우는 안 잡힘. 0건으로 false STALE 전체 부재를 증명하지 않음 |
| retry `auto_count` / `exhausted_count` | DB + sweep log, 실제 retry cap으로 해석. FAILED/한도 거부는 자동 retry 아님 |
| `runtime.retry.after_case_stopped_count` | commit된 attempt≥2의 `NOT_APPLIED(STOPPED_WAITING)`만. 다른 reason·ALREADY_APPLIED·rollback 제외 |
| cancel `observe_latency_ms` | heartbeat가 DB marker를 commit 후 in-process **신호 전달**한 지연. 첫 handler checkpoint 시각과 다름 |
| cancel `terminal_latency_ms` / `checkpoint_to_terminal_ms` | DB marker→terminal causal 차이 / log의 commit 보정 latency / 첫 checkpoint→T1 commit monotonic. DB 정상·장애 표본과 QUEUED/RUNNING 분리 |
| T2 outcome/reason | port는 APPLIED/ALREADY_APPLIED/NOT_APPLIED(STOPPED_WAITING·CANCELLED·SUPERSEDED). redelivery log에는 status만, 일반 T2의 전체 reason emitter 없음. `case_applied_at`은 NOT_APPLIED에도 기록되므로 APPLIED 증거가 아님 |
| DB·Usage | claim/DB error·retry log, usage_inflight/usage_record·produced. provider 시도별 token/latency·null cost 보존. 미가격은 0원 아님 |
| API/cleanup | api view/request/ready·asset 이벤트, `storage.cleanup.{staging,temp,orphan}.{count,bytes,failed_count}`. cleanup log는 execution context 없는 count-only |

실제 emitter와 의미의 근거는 [RT-12(b)](../rt12b-observability.md), `common/logging/catalog.py`,
`heartbeat.py`, `sweep.py`, `worker/composition.py`, `common/storage/cleanup.py`다.
metric 이름을 CloudWatch custom metric/dashboard의 존재로 읽지 않는다.

### 7.2 외부 표본과 아직 없는 구간 계측

| 관측 | 현재 가능 / 필요한 보완 | 제한 |
| --- | --- | --- |
| host CPU/RAM/swap/disk/I/O/CPU credits | 보호된 host/process/cgroup sampler·기본 AWS CPU/credit 관측 | RAM/disk/RSS는 기본 CloudWatch에 없음. sampling 간격·누락·collector overhead·RSS/cgroup 정의 기록 |
| API/Worker/MySQL·ffmpeg/ffprobe 자식 RSS/CPU | PID/starttime/container identity로 표본 | startup OCR HWM과 실행 중 peak 분리. 2초 sample max를 진짜 peak로 부르지 않음 |
| temp peak | Recording 명시 root + Search 실제 tempfile root(`/tmp` 등) + container writable layer + DB/media volume | Search temp는 `daesingo_media_*`, Recording scanner는 `recording-analysis/chain-*`만 소유. Search crash 잔여 회수 보장 없음 |
| Recording encode/phase | 기존 `recording.observability.capture_materialization()` opt-in | 기본 Worker에서 켜지지 않음. 단일 materialize phase만으로 전체 준비/concat/DB write 측정 불가 |
| Recording 전체 준비·span/concat elapsed·DB write | 실행 경계/concat/publish의 비민감 monotonic observer 또는 검토된 harness 필요 | 현재 전용 production metric 없음. bytes는 저장 metadata/content 길이, 실패 중간값은 추가 관측 필요 |
| Search preparation·request construction | stream 복사/probe/재인코딩/base64/JSON/SDK 전송의 bytes·elapsed observer 필요 | provider usage latency와 job 시작→usage 시각 차이로 세부 구간을 대신하지 않음. guard의 JSON bytes와 SDK 실제 wire bytes도 구분 |
| DB statement/driver overhead | 격리 DB·동일 driver의 bounded byte-count 관측/저장·읽기·rollback 비교 필요 | SQL/general log/echo로 원문 수집 금지. packet guard 통과는 실제 저장 여유의 증거 아님 |
| T2 exact outcome/reason·kill phase | commit 후 결과 수집·barrier harness 필요 | production phase 제어 endpoint 없음. 현재 marker/aggregate로 정확한 reason 복원 불가 시 UNKNOWN |
| Case-visible elapsed | client monotonic command→각 CaseView 최초 관측 + DB requested_at/settled reason | poll 지연·사람 대기 별도. server의 정확한 반영 시각과 혼동 금지 |

**최소 보완 목록:** Recording 전체/concat/publish, Search 준비/요청 구성, T2 commit outcome/reason,
정확한 kill barrier·bounded DB fault harness. 실제 수집 방식·권한·비노출·overhead를 검토해야 한다.
이번 작업에서는 구현하지 않는다. 가용 자원/DB/log만으로 subset 실행은 가능하나,
누락 구간은 N/A/UNKNOWN으로 남기며 P2-0b/F2~F4 전체 완료를 선언하지 않는다.
0c도 동일 phase/byte gap을 가진다. 추가로 experimental config/packet의 적용·복귀·연결별 값,
단계별 실제 duration/최초 차단 경계를 연결하는 manifest가 필요하다. 이 기록은 새 Runtime metric이나 실패 enum이 아니다.

## 8. 실험 순서와 각 선행조건

모든 실험은 §9 공통 gate를 먼저 통과한다. ID는 기존 A~F 참조를 유지하고 #452를 P2-0으로 추가한다.
번호가 병렬 실행 허가나 강제 일렬 의존성을 뜻하지 않는다. A와 0b는 같은 정상 실행 evidence를 공유한다.

### P2-0a — Known failure regression (#452)

**역할:** 현재 baseline v1에서 긴 입력이 encode/concat·BLOB write·Search/provider까지 늦게 진행한 뒤
실패하지 않고 빠르게 typed reject되는지 검증한다. **이 결과는 약 19분 입력을 제품 지원 범위 밖으로
확정하는 acceptance가 아니다.** current baseline regression ≠ final product support range.

**선행:** 실제 22개 보호 manifest·업로드/기존 등록 경로·권한 확보, baseline v1의 process 적용,
해당 Coarse execution을 분리한 provider/process/BLOB 관측. 처음에는 격리된 짧은 상한초과 synthetic으로
계측 경로만 점검할 수 있으나 실제 regression 완료와 구분한다. duration 제한을 풀지 않는다.

- 총 요청 길이가 상한을 넘는 위치에서 `AnalysisSourceLimits.check_range`로 거부되는지 확인한다.
- Analysis encode/concat ffmpeg가 시작되지 않고 Search capability/provider invocation·AnalysisRun/produced가 없는지 확인한다. 사전 source resolve/ffprobe/time 관찰은 가능하므로 모든 도구 호출 0을 요구하지 않는다.
- AnalysisSource prepared BLOB write가 없는지 확인한다. 업로드/등록/progress·T1·T2의 정상 DB 쓰기를 금지하지 않는다.
- 해당 execution의 `FAILED / RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`, 자동 retry 없음, Case notice `recording.analysis_range_too_long`·ERROR/blocking·`actions:[]`, Web SEARCH_FAILED·전용 문구를 확인한다.
- HINT_EXTRACT가 앞서 실행됐다면 별도 usage다. 전체 Case usage=0을 provider 미호출 판정으로 삼지 않는다. 비용 없는 거부 시험은 기존 준비 상태/격리 입력 경로를 명시하고 예상치 못한 다른 job 발주도 확인한다.
- 전용 DB의 연결 유지·해당 window `Aborted_clients` delta와 disconnect 오류, Worker/자식 RSS/temp 잔여·원본 SHA/size/mtime 불변을 확인한다. 공유 DB 전역 delta는 attribution 불명으로 남긴다.

**0a의 현재 구성 기대값:** 약 19분 입력에 빠른 typed rejection이 남는 것이다. 같은 입력의 향후 성공 가능성/지원 방식은 0c와 Decision Gate에서 따로 판단한다. Case waiting이 먼저 종료됐다면
notice 미반영과 T2 reason을 따로 기록하고 queue/준비 지연을 조사한다. 현재 구현만으로 deadline 이후에도 notice가 반드시 적용된다고 가정하지 않는다.
기본 로그만으로 ffmpeg/Search 호출·BLOB write 부재를 증명할 수 없으면 그 항목은 BLOCKED다.

### P2-A + P2-0b — concurrency=1 cold path / 현 baseline 안 characterization

0b의 범위는 baseline v1을 바꾸지 않은 정상/경계 경로이며, 제품 최종 지원 범위를 정의하지 않는다.

**A 선행:** 작은 허용 fixture·8종 registry·health와 bounded resource sampler/DB/log 수집.
**0b 추가 선행:** 대표/다중/상한 인접 fixture 선정, §7.2 phase/byte 계측, 동일 DB packet/driver·Search config 확인.
새 execution/service로 시작한다. OS page cache flush·host reboot를 cold 정의에 넣지 않는다.

minimal A로 수집을 확인한 뒤 짧은 대표→긴 대표→경계 인접 순으로 0b를 진행한다.
같은 실행에서 다음을 기록하고 중복 provider 호출로 별도 A/0b 표본을 만들지 않는다.

| 구간 | 관측 |
| --- | --- |
| source / Recording | source duration/bytes/선택 stream·span, span별·누적·최종 AnalysisSource bytes, materialization/encode/concat/전체 준비 elapsed |
| DB | publish/write elapsed, driver escaping/statement metadata bytes 및 buffer working set, session packet 여유, 저장→재조회 길이/hash·격리 rollback·연결 유지 |
| Search / transport | 준비 elapsed, 재인코딩 media bytes, base64 bytes, guard JSON/request construction elapsed·bytes, 가능하면 SDK wire bytes, provider latency/시도/usage |
| Runtime / Case | queue wait, started→terminal, T1→T2, Case requested→최초 결과/timeout notice 관측, settled reason. Recording 준비·Search 실행 시계를 분리 |
| resource / cleanup | Worker/API/MySQL RSS·ffmpeg/ffprobe RSS/CPU·cgroup·temp disk peak 표본, durable DB/media 증가, 종료 후 자식/파일/메모리 추세 |

현재 [Case 대기 결정](../../modules/case/decisions/case-wait-timeout.md)의 Coarse 150초 + 큐 여유 30초와 비교하되
P2가 이 값을 바꾸지 않는다. Recording 준비/Search 재인코딩/provider를 합쳤을 때 지원 안의 입력도
Case timeout이면 그대로 결과에 남겨 Case/Search/Recording Owner에게 전달한다.
byte limit 이하여도 driver/packet 오류가 나면 해당 **baseline 실행은 FAIL로 보존**한다.
운영 packet/limit을 올려 이 acceptance를 PASS로 덮어쓰지 않는다. 근거·복귀 계획이 있는
**격리 0c의 별도 experimental override는 허용**하며 다른 config/run으로 기록한다.
CRF 고복잡도에서 bytes 초과는 허용된 typed rejection일 수 있다. 이 경우 성공 시간 표본과 섞지 않는다.

### P2-0c — Isolated capacity probe / 최소 20분 logical timeline 판단

**목적:** 현 **single-AnalysisSource + 전체 timeline에 대한 단일 Coarse request** 구조를 유지한 채,
격리 experimental target의 안전 한도를 명시적으로 조절했을 때 **처음 막히는 경계**를 측정한다.
“20분을 반드시 성공시켜라”가 아니라 “20분 logical timeline 지원을 가로막는 최초 병목과 그 근거를 설명할 수 있는가”가 질문이다.
단일 AnalysisSource가 제품적으로 필수라고 결정하는 실험이 아니며, chunking/storage 코드를 구현하는 단계도 아니다.

**선행:** G1~G5 중 target에 해당하는 항목, 작은 A/0b의 sampler·phase/byte 계측과 안전 예산,
검토된 fixture/전송 권한·timeline/stream manifest, 운영과 분리된 DB/media/network/config·자원 예산,
유한한 단계별 한도·provider 시도/비용/시간·중단/cleanup·config 복귀 계획.
같은 작은 EC2에서 project 이름만 다르게 띄운 것은 자원 격리가 아니다. 이 준비 전에는 BLOCKED다.

#### Experimental override 경계

| 구분 | 허용 범위와 기록 |
| --- | --- |
| 운영 baseline | baseline v1·보호 config·운영 DB/packet·ingress는 그대로 둔다. 원래 실패를 성공으로 바꾸는 덮어쓰기 금지 |
| 실험 Recording | `MAX_DURATION_MS`/`MAX_BYTES`를 **유한한 experimental 값**으로 명시할 수 있다. encode/실행 중/DB write 전 guard와 typed code·notice·no automatic retry는 유지하고 disable/bypass하지 않음 |
| 실험 MySQL | session packet/driver/statement overhead·메모리 예산 근거가 있을 때 **전용 DB만** packet을 조절할 수 있다. 적용 전후 server/session 값·새 연결 적용·저장/재조회/rollback·연결 상태를 기록. packet만 올려 해결됐다고 결론 내리지 않음 |
| Search | 첫 probe는 현재 source materialization 512 MiB·Coarse 재인코딩·40 MiB media/56 MiB request cap을 유지하고 최초 거부를 기록. 이 값들은 현재 env knob가 아니므로 변경이 필요하면 Search Owner 후속 설계로 넘긴다. cap 하나를 키우는 것으로 전체 경로 해결을 선언하지 않음 |
| config 식별·복귀 | baseline/experimental 파일·config ID/내용 hash·profile 구성 식별을 분리하고 변경 이유·이전/실험 값·적용 순서를 보호 기록에 남긴다. 실험 입력 설정→process 적용 확인→측정→기존 실험 config로 복귀/시험 자원 정리 확인. 운영에는 자동 반영하지 않음 |

실험값은 §5의 운영 snapshot 표에 덮어쓰지 않는다. 단순 duration guard만 상향해 bytes가 먼저 막히는 실행도
유효한 병목 관측이다. 다음 비교를 하려면 원 실패를 보존한 별도 run에서 하나의 변경축과 근거·복귀를 명시한다.
임의의 무한 한도·packet 최대치·메모리 과할당으로 guard/배포 검증을 우회하지 않는다.
이 절은 향후 측정 계획이며 이번 PR 수정에서 실제 설정을 바꾸거나 실험을 실행하지 않는다.

#### 진행과 수집

1. 짧은 대표→더 긴 대표→약 10분급→약 20분급을 후보로 하되 fixture·관측 working set·비용 예산에 따라 단계를 정한다. 예산 근거가 없는 다음 길이로 진입하지 않는다.
2. logical timeline의 선택 범위·총 duration·span/원본 수를 확인한다. 20분 중 사건 주변 4분만 처리하고 20분 전체 탐색 성공으로 기록하지 않는다. 22개/19분 26초 원본은 별도 lineage로 재사용 가능하지만 최소 20분 달성의 대체 evidence는 아니다.
3. 아래 경계를 관측해 처음 걸린 guard/오류/자원·시간 제약을 분류한다. 앞단에서 멈추면 뒷단은 NOT_REACHED로 남긴다. 기존 cap 거부 자체도 결과이며 실제 DB disconnect/OOM을 유발해 ceiling을 찾지 않는다.

| 경계 | 필수 관측 |
| --- | --- |
| Recording | 요청 duration, span별/누적/final AnalysisSource bytes, encode/concat/전체 preparation elapsed, temp/RSS |
| DB | BLOB write/read elapsed·길이/hash, driver/statement metadata·escaping/buffer overhead, server/session `max_allowed_packet`와 여유, 연결 안정성·`Aborted_clients`·rollback |
| Search | Coarse 재인코딩 media bytes/elapsed, 현 40 MiB media cap·56 MiB request cap, base64/JSON/request construction bytes/elapsed, 실제 provider 시도/latency/usage |
| Runtime/Case | queue·Recording preparation·Search preparation·provider·T1/T2·Case-visible elapsed/timeout/반영 reason을 분리. 기존 Case waiting budget은 그대로 측정해 충돌 evidence로 남김 |
| resource/cleanup | Worker/API/MySQL/ffmpeg/ffprobe RSS/CPU·cgroup, 전체 temp/disk/DB 증가, 정상/거부 후 자식·파일·RAM 회수와 잔여 |

**중단/결과:** §9의 reserve·health·DB 연결·원본/비노출 경계를 유지한다. 한도 거부는 typed 결과로 보존하고,
예산 부족 시 결과 문서에 RESOURCE_BUDGET_STOP, 계측 불충분 시 UNKNOWN으로 남긴다. 이들은 실험 판정 라벨이며 새 Runtime failure code가 아니다. 관측 없이 “N분 ceiling”을 단정하지 않는다.
기본 계측으로 경계를 분리할 수 없으면 §7 gap이 해소될 때까지 전체 판정은 BLOCKED다.
통과한 가장 긴 표본·다음 차단 경계·config·내용 의존성·미도달 단계와 미실행 길이를 같이 기록한다.
단회 20분 통과도 생산 환경 지원/품질/대기시간 acceptance 완료나 운영값 자동 승격이 아니다.

**Decision Gate:** §10에서 0a/0b/0c 결과를 합쳐 현 구조 유지 가능성과 장시간 지원 설계 재개 필요성을 판단한다.

### P2-B — 반복 job과 reuse 비용

**선행:** A/0b의 관측 가능한 subset·Case가 새 job을 발주하는 유효 command/fixture 확인.
Case result reuse로 execution이 없으면 그것을 기록하고 encode warm hit로 세지 않는다.

- 같은 Worker에서 동일한 source/span/profile의 **별도 execution**을 비교한다. ref 생성·BLOB 증가·encode 횟수·elapsed/RSS/temp·DB 비용을 기록한다. 현재 기본 경로는 재준비이므로 빨라져도 OS/cache 효과와 구분한다.
- 같은 RecordingService instance를 두 번 호출하는 module micro-probe는 선택 비교다. instance dict hit의 이득만 설명하고 Runtime job 간 reuse 증거로 쓰지 않는다.
- durable ref 재열기는 P2-D와 연결한다. 반복 후 DB의 prepared asset 축적은 temp cleanup 실패가 아니다. 측정 중 purge/TTL을 새로 적용하지 않는다.

### P2-C — 실패 / cleanup

**선행:** A, 한정된 시험 자원/비민감 fixture. baseline 회귀는 baseline v1의 byte/duration 값으로 실행하고 0c override 표본과 분리한다. deterministic Search timeout/도구 실패는 격리 harness에서만 유도한다.
실제 provider를 일부러 timeout시키거나 운영 원본을 훼손하지 않는다.

duration 거부(0a)와 encode 중 누적 bytes·최종 concat bytes 거부, Search 준비 실패, Search/provider 실패를 분리한다.
실패 위치·typed/generic terminal·usage 유무·자동 retry 대상 여부·partial BLOB/produced 부재와 cleanup을 확인한다.
Recording의 약 50ms 출력 polling은 buffering/scheduling overshoot가 있고 RSS/disk hard quota가 아니다.
예외 정상 unwind와 SIGKILL 이후 잔여를 같은 cleanup PASS로 합치지 않는다.
Search는 finally `rmtree(ignore_errors=True)`이며 성공 로그만으로 실제 삭제를 보장하지 않으므로 파일 관측을 대조한다.
crash 잔여 관찰/회수는 F2와 연결하고, 임의 disk fill·ENOSPC·OOM 유도는 하지 않는다.

### P2-D — process restart / durable read / 재준비 경계

**선행:** A/B, 전용 target 또는 RT-14 복귀·현재 public 확인을 마친 점검 창, queue/미반영 terminal·사용자 작업 부재 확인.
운영 `down --volumes`, data restore, migration/rollback은 하지 않는다.

idle Worker의 graceful restart와 장애 kill(F2)을 분리한다. 동일 image/config/DB/media를 보존하고,
기존 Source/AnalysisSource/DerivedAsset ref의 metadata·bytes/hash를 새 process에서 읽을 수 있는지 확인한다.
그 뒤 유효한 새 job이 발주됐을 때 encode/publish가 다시 일어나는지·latency/DB 증가를 B와 비교한다.
기존 RT-14 재부팅/restore 자료는 ref 내구성 근거로 참조하고 복원 rehearsal을 반복하지 않는다.
restore된 DB에서 정상 Worker job이 필요하면 RT-14 후속으로 분리한다(Recovery의 egress/credential 격리 target에서 일반 Worker 시작 금지).

### P2-F1 — 정상 부하의 lifecycle timing

**선행:** A/0b와 동일 정상 표본에 heartbeat/sweep/queue·DB/log 관측 연결. 추가 provider run 없이 가능한 한 재사용한다.
정상 concurrency=1 반복에서 lag/attempt/skipped ticks·execution/queue·CPU credits와 자원 경합을 기록한다.
CPU credit 상태는 자연 관찰하며 고갈시키기 위한 host 부하를 만들지 않는다.
표본 수와 nearest-rank 집계를 함께 기록한다. 소표본 p99를 운영 대표치로 해석하지 않는다.
false STALE 이벤트 또는 살아 있는 실행의 lease loss 증거가 있으면 중단·조사한다.
`false_count=0`만으로 부재를 선언하지 않는다. RD-04 최종 튜닝은 F1/F2 근거와 Owner 판단이 필요하다.

### P2-F5 — cancellation observation

**선행:** 전용 시험 Case, DB 정상 표본, 유효 Case cancel command·heartbeat/cancel log 수집.
Recording preparation checkpoint와 Search capability 대기 중인 경우를 분리한다.
`cancel_requested_at → heartbeat signal → 첫 handler checkpoint → T1 terminal`을 가능한 범위에서 기록한다.
기존 B-X1(DB 정상 p95 ≤20초)은 측정 목표이며 hard bound가 아니다. 현재 `observe_latency_ms`는 signal 시점이므로
**그 값만으로 첫 handler checkpoint 목표 달성을 주장하지 않는다**. 정확한 구간이 없으면 계측 gap으로 남긴다.
provider in-flight 선점 중단을 기대하지 않는다. 관측/terminal latency·추가 usage·Case 즉시 중단 표시를 구분한다.
취소+STALE 뒤 자동 retry 억제는 별도 격리 경합 시나리오에서 확인한다.

### P2-F2 — Worker kill timeline

**선행:** 격리 target, 기존 concurrent claim/lease·T1/T2 integration evidence, exact container/PID/starttime,
주입 barrier/외부 observer·timeout·재기동/중단 책임·cleanup/비용 계획.
`tests/worker/test_redelivery_mysql.py` 등의 test-only barrier는 참고이며 production 주입 기능이 아니다.

| 지점 | 기대·측정 경계 |
| --- | --- |
| claim commit 후 / handler 초반 | durable RUNNING과 last heartbeat 확인 뒤 target Worker container만 SIGKILL. startup/periodic sweep과 retry 관찰 |
| Recording 준비 중 / provider 중 | ffmpeg 자식·temp 회수와 usage recovery 구분. 먼저 offline Recording 지점, 실제 paid HTTP 중 kill은 별도 비용/중복 invocation 허용 필요 |
| handler 반환 후 T1 전후 | 정확한 barrier가 없으면 BLOCKED. 임의 sleep/로그 polling을 정확한 경계 증거로 쓰지 않음 |
| T1 commit 뒤 T2 전후 | SUCCEEDED/FAILED terminal이면 T2 redelivery·Case/후속 enqueue idempotency 검증. 새 STALE retry를 기대하지 않음 |

graceful SIGTERM/Compose stop은 정상 drain 뒤 종료할 수 있어 kill 대체가 아니다.
SIGKILL 뒤 `unless-stopped`의 restart 동작을 가정하지 않고 exact target의 실제 restart 시각을 기록한다.
현재 단일 Worker가 죽으면 같은 process의 sweeper도 없으므로 **대체/재시작 Worker가 언제 시작했는지**가 recovery time의 일부다.
DB heartbeat/lease/ended_at·retry queued/available/started/terminal·T2 marker와 monotonic kill/restart 시각을 연결한다.
nominal lease+sweep+backoff를 복구시간 hard bound로 쓰지 않는다. 살아 있던 provider의 중복 비용/unknown usage도 보존한다.

### P2-F3 — DB stall / heartbeat gap

**선행:** 별도 DB/network/volume을 쓰는 격리 환경, heartbeat 전용 경로에 제한한 bounded fault harness·자동 해제/복귀 검증.
공유 EC2 운영 MySQL의 stop/pause/network 차단·전역 lock은 금지한다. API/다른 실행까지 막는 fault를 heartbeat-only라고 부르지 않는다.
현 production 진입점에는 heartbeat 전용 DB endpoint/fault knob가 없으므로 **harness 검토 전 BLOCKED**다.

기존 5/15/30/60초 주입 grid를 제거한다. 실제 timeout/lease·harness 해제 특성에서 구간을 골라 기록한다.
attempt/error/skipped tick·마지막 durable 성공 갱신·lease 만료·STALE·handler 생존·복구 후 terminal/retry를 관측한다.
heartbeat는 겹치지 않는 동기 호출이며 I/O timeout 합이 전체 attempt 상한은 아니다.
“N회 실패하면 STALE”가 아니라 저장된 lease 만료 조건을 그대로 사용한다.

### P2-F4 — late retry / T2 reason

**선행:** 격리 환경의 실제 attempt≥2 lineage, 현재 Case STOPPED_WAITING 정산 경로,
정확한 T2 commit outcome/reason 수집. 현재 Case timeout 구현은 이미 존재하므로 과거 “Case 미구현이면 0 정상” 조건은 제거한다.

APPLIED/ALREADY_APPLIED/NOT_APPLIED(STOPPED_WAITING·CANCELLED·SUPERSEDED)를 구분한다.
`after_case_stopped_count`는 attempt≥2 + NOT_APPLIED(STOPPED_WAITING)만 증가한다.
reflector 예외/T2 rollback은 반영 결과가 아니라 redelivery 대상이며 counter에 합산하지 않는다.
`case_applied_at`만으로 APPLIED나 reason을 추론하지 않는다. Case가 기다리기를 멈춘 뒤에도 Worker/usage는 계속될 수 있다.

### P2-E — 복수 Worker 탐색 (선행 실험 뒤 마지막)

**선행:** 0b/A~D·F1/F5에서 concurrency=1의 자원/cleanup/시간을 설명하고,
격리 F2~F4의 필요한 recovery·fencing·T2 의미를 확인한다. 동시 claim/sweep/lease integration 검증,
provider 동시 요청 한도·비용, API/MySQL/OCR/driver/temp 동시 peak 예산·중단 계획이 있어야 한다.

production controller는 service당 container 1개를 검증하므로 기존 배포에 `--scale worker=2`를 덧붙이지 않는다.
시험 전용 Compose/조립에서 **Worker process 2개 × execution 1개**를 후보로 설계하고 image/config/DB/media 공유·lease/cleanup을 대조한다.
현재 내부 concurrency config는 없다. 이를 열기 위한 Runtime 리팩터링은 이번 계획 범위 밖이다.
자원/queue/provider-bound 원인과 throughput·Case elapsed·retry·비용을 비교한다.
2 이상은 목표값이 아니며 결과가 있어도 운영 Worker count 변경은 별도 Owner 결정이다.

## 9. 공통 선행조건·안전·중단

| Gate | 확인할 입력·책임 | 적용 |
| --- | --- | --- |
| G1 identity/availability | 운영자: target project/서비스/container/image/revision/config/schema·8종·health, queue/미반영 terminal·다른 사용자·점검 작업·backup 충돌 | 모든 실행. 감사 develop과 배포 RC 차이가 실험 경로에 영향을 주면 그 차이를 먼저 해결/제한 표기 |
| G2 자원 예산 | Runtime/Ops: 실제 RAM/temp/DB/disk·images/log/backup·CPU credits, 실행당 예상 working set·collector overhead·중단/복귀 담당. 기존 승인 reserve의 적용 가능성 | 새로운 임의 수치 금지. 근거가 없으면 큰 입력/복수 stack 실행 불가 |
| G3 data/provider | fixture 소유자·Recording/Search: 개인정보/외부 전송·보관 권한·비식별화, manifest, provider 시도/비용 한도와 예상 followup job | 모든 media 실행. 22개 거부는 media provider 진입 차단 관측 필요. raw 원본/번호판/GPS를 공개 evidence에 넣지 않음 |
| G4 계측 | Runtime/Recording/Search: 표본 시계·window·필드·비노출·누락, §7의 실험별 필요 gap | gap이 있으면 subset/UNKNOWN으로 제한. 전체 완료 표기 금지 |
| G5 운영 보호/복구 | 운영자: 현재 public 경계 확인, 알려진 복귀 절차·backup 참조·서비스 영향·실행 창 | 활성 서비스 process 변경/고위험 시나리오는 RT-14 후속 evidence 뒤 재평가. 격리 target은 자체 복귀 조건 충족으로 독립 가능 |
| G6 experimental override (0c) | Runtime/Recording·DB 운영자: 변경축·유한한 값/packet 여유·자원/비용 근거·원 config 식별·적용/복귀 절차 | 0c 전용 target에만 적용. Search/Case의 기존 cap/대기 의미는 관측 입력으로 보존. 운영 지원 범위 승격과 분리 |

격리 target은 운영 project/DB/media/config·외부 공개 port와 분리한다. 같은 4GiB host에서 이름만 다른
두 번째 stack을 띄우면 자원 격리가 되지 않는다. Recovery target은 일반 Worker/provider 재생용이 아니므로 재사용하지 않는다.
권한이 없는 별도 host를 새로 만들거나 리소스를 증설하는 결정도 이 계획이 하지 않는다.

운영 Caddy/SG/IP 허용 범위·secret source·packet·limit·release tuple을 실험 편의를 위해 바꾸지 않는다.
이는 **운영 변경 금지**다. P2-0c의 별도 experimental target에서는 G6의 근거·복귀 계획에 따라
Recording duration/bytes·전용 MySQL packet을 조절할 수 있으며 guard/typed failure는 계속 유효하다.
SQL echo/general log, SDK debug/raw HTTP logging, `docker inspect`/env 전체 덤프, base64·media·credential 출력은 사용하지 않는다.
표본기는 경로/argv 대신 필요한 숫자·안전한 고정 phase만 수집한다.
disk exhaustion·swap/OOM·CPU credit 고갈을 목표로 부하를 만들지 않고 bounded 단계 관찰로 대체한다.

**즉시 중단:** 예상 밖 provider/후속 job·비용, 다른 사용자/운영 작업 유입, reserve 침범/예산 불명,
OOM/restart·지속 health 악화·DB disconnect/Aborted_clients 증가·false STALE/ownership loss,
원본 불변성 위반·민감정보 로그·계측 누락으로 안전 판정 불가.
stop은 신규 발주/부하를 멈추고 담당자에게 target 상태를 보존하는 것이다.
공유 host 강제 종료·DB kill·전체 Docker prune·운영 volume 삭제·자동 rollback/restore로 복귀하지 않는다.
fault 해제→소유 process/자식·queue/usage/T2·health·기존 release/config 보존 확인→시험 소유 자원만 명시 정리한다.
불명 상태는 UNKNOWN, 실패는 FAIL로 보존한다.

## 10. 완료와 Spec/Decision 승격

실험 ID·fixture/내용군·정상/거부/실패·측정 범위별로 PASS/FAIL/UNKNOWN/NOT_RUN을 기록한다.
P2 1차 readout에는 답한 질문과 닫지 못한 질문·blocker·Owner 후속을 함께 남긴다.
P2 전체 완료는 필수 질문의 검증 근거를 갖춘 뒤 판정하며, 계측 누락이나 미실행을 후속으로 옮겼다는 이유만으로 완료 처리하지 않는다.
subset을 실행한 사실을 capacity 전체 PASS로 쓰지 않는다. 임의 CPU/RAM 수치로 합격을 만들지 않는다.

| 결과 | 전달할 원문·Owner |
| --- | --- |
| Runtime working set·disk/DB contention·Worker 탐색 | Ops §11/§16~§18, RD-15. 구조 변경은 Owner 검토 뒤 ADR |
| heartbeat/lease/retry/cancel tuning | Provisional Baseline B-L*/B-R*/B-X1 change log + evidence, Tech Spec·RD-04. 최소 F1/F2 없이 최종값 선언 금지 |
| 실행 내/간 reuse·restart 비용 | Recording + Runtime, RD-09·Ops. durable storage를 process cache처럼 다시 설계하지 않음 |
| profile/limit·DB 전송 여유·준비시간 | Recording limits/환경 설정 원문 + #452. Runtime은 측정 영향만 링크 |
| 0c 최초 병목·최소 20분 logical timeline 가능성 | 아래 Decision Gate. baseline/experimental 증거 분리, 운영값 후보 검토와 제품 최종 승인 구분 |
| Search media/request/latency | Search Owner 문서. provider 계약/품질을 Runtime이 정하지 않음 |
| Case waiting·notice·late retry | Case timeout/long-analysis-range 결정 + #72/#452. 180초 변경은 Case 판단 |
| deploy/restore/off-host/RPO·RTO | RT-14/Recovery/Ops 후속. P2 결과로 자동 closure하지 않음 |

기존 정책의 재현 가능한 위반은 튜닝 전에 원인 조사한다. 반복 가능한 사실과 적용 범위가 확인된 것만
workflow §10→§11로 승격한다. 관측값·추정·Owner 결정·코드 기본값을 구분한다.

아직 Owner 확인이 필요한 것은 **실험 입력과 수집/운영 방식**이다. Recording은 대표/경계 fixture·phase 관측과
driver 여유 검증, Search는 요청 구성 관측·실제 provider 동시 한도/비용, Case는 대기/late-result 비교와
결과 환류를 확인한다. Runtime/Ops는 target·자원/복귀 예산·T2/fault harness와 cohort 수집을 정리한다.
기존 baseline v1·typed code·재시도 없는 notice는 유지한다. 0c는 초기 baseline을 지우거나
MVP 분할 제외 이력을 PM의 영구 제품 정책으로 승격하는 절차가 아니다.

### 10.1 Decision Gate — 제품 목표에 대한 환류

0a rejection PASS만으로 #452나 장시간 지원 문제를 해결 처리하지 않는다.
0b의 현재 구성 비용과 0c의 최초 병목을 합쳐 **최소 20분 logical timeline**에 대한 다음 판단을 남긴다.

| 근거 | 다음 판단·책임 |
| --- | --- |
| 현 single-source 구조에서 20분급 대표 입력이 안전한 자원·전송·시간 안에 처리될 가능성 확인 | Recording/Search/Case/Runtime이 운영 profile/limit·DB 여유·대기시간 **후보**를 재검토. 반복/품질·비용 검증과 필요한 승인 후 결정하며 실험값을 자동 production 승격하지 않음 |
| Recording/DB/Search 요청·Case 대기 등에서 제품 목표 미충족 | 최초 병목을 근거로 **장시간 지원 cross-module 설계를 다시 연다**. bounded/chunked processing, Recording 저장 구조/Object Storage, Search 요청 구조, Case 후보 merge/dedup·시간 좌표/파일 경계 처리 등을 후보로 비교. 채택 방식/구현은 미확정 |
| 20분 fixture·계측·안전 예산 부족 또는 뒤 단계 미도달 | 목표 미검증/UNKNOWN과 필요한 입력을 명시. 4분을 최종 제품 지원 길이로 고정하거나 무조건 chunking 필요라고 결론 내리지 않음 |

운영 설정의 기술적 검토는 각 Owner가 맡고, Must/Won't·불변 경계·제품 지원 범위 변경의
최종 승인은 [Product Spec 변경 절차](../../product/product-spec.md)에 따라 **PM 김준영**이 한다.
이 Gate는 정책/구현 결정을 위한 근거를 마련한다. 현 구조가 불충분하면 설계를 재개할 수 있으며,
장시간 지원 논의를 P3 이후로 미루는 gate가 아니다. chunking·storage·provider cap 하나만 바꾸면
해결된다는 결론도 전체 DB/Search/Case/자원·탐색 품질 검증 없이 내리지 않는다.

## 11. Evidence 기록 규칙

별도 날짜별 Result에 plan revision/실험 ID·미실행 항목을 연결한다. 이 계획에 실행 결과를 덮어쓰지 않는다.

- 실행 시각(KST/UTC)·source SHA/image digest·실제 배포 tuple/schema·도구/driver/model/config version·override·B-ID/profile 입력.
- 0a/0b의 baseline config와 0c experimental config/변경축·이전값·유한한 실험값·근거·적용/복귀 기록을 분리. 선택한 logical timeline 전체 duration/coverage와 최초 차단·NOT_REACHED 단계, 20분 목표의 검증/미검증 범위 보존.
- 안전한 fixture alias·선정 이유·길이/bytes/내용군·단일/다중·반복 수. 원본 hash/mtime·실제 식별자/위치·private manifest는 보호 저장.
- source→Recording→DB→Search→provider→T1/T2→Case-visible 경계별 bytes/elapsed, 각 시계·수집 간격·표본 수·누락/overhead.
- API/Worker/MySQL/ffmpeg/ffprobe RSS/cgroup/CPU, 모든 temp/DB/media/writable-layer peak 표본·종료 후 추세·자식/잔여 cleanup.
- job/execution/attempt lineage, queue/backoff·heartbeat/sweep·cancel·T2 outcome/reason·usage/추가비용·known limitations.
- 실패한 최초 시도·보조 측정 오류·재실행을 구분하고 후행 성공으로 소급하지 않음. 운영자 제공/에이전트 직접 관측/정적 대조를 구분.

개별 실험 lineage는 보호 기록에서만 `trace→case→job→execution(attempt)→usage/T1/T2`로 연결한다.
공개 Result는 alias/집계·비민감 판정만 싣고 raw SQL/BLOB/media/base64/secret/사용자 설명·번호판·정밀 위치를 게시하지 않는다.
집계는 cohort·nearest-rank·분모/누락을 명시한다. retention 전체 DB 분포나 하나의 표본으로 p95/운영 보장을 만들지 않는다.

## 12. 실행 readiness와 P3 진입

권장 순서: **G1~G4/수집 점검 → 0a(권한·fixture 확보 시) → minimal A → 대표 A/0b → G6·격리 0c → 제품/운영 Decision Gate**.
작은 정상 표본으로 B + F1/F5 → C → D → 격리 F2/F3/F4 → E도 이어가며, 0c가 모든 장애/복수 Worker 실험 완료를 기다릴 필요는 없다.
22개가 미확보면 그 regression은 남기고 독립적인 작은 A를 진행할 수 있다.
readiness는 구현/계획상의 분류이며 현재 AWS 가용 상태나 이번 작업의 실행 허가를 뜻하지 않는다.

### READY NOW

- G1~G4를 충족하는 이미 준비된 제한 시험 target에서 작은 A의 **기존 DB/log + bounded host/resource 관측 subset**, 같은 정상 표본의 F1, 새 job 발주가 확인된 B 반복 비용 관측. 새 Runtime 코드가 필요한 것은 아님.
- 기존 RT-14/CI/DB 로그의 읽기 전용 evidence 대조와 측정 경로 점검. 이는 새 P2 실행 PASS가 아님.

### READY AFTER RT-14 FOLLOW-UP

- public 경로를 포함하는 작은 A/0a는 RT-14 후속의 현재 외부 endpoint/운영 복귀 확인 뒤 G1~G4와 함께 재평가한다. 기존 local HTTPS 403은 외부 확인을 대체하지 않는다.
- 배포 RC와 현재 develop의 차이를 없앤 production-like 검증이 필요하면 RT-14의 artifact/CI/배포 절차에서 준비한다. 이 문서 작업에서 배포하지 않는다.
- 활성 EC2의 D/restart·고위험 부하는 별도 점검 창과 해당 위험에 필요한 복귀 evidence를 확인해야 한다. 두 번째 deploy/rollback·복원 DB 정상 Worker job은 RT-14의 독립 과제이며, 모든 P2를 막는 일괄 선행조건은 아니다. off-host/RPO·RTO/Package READY 정책 후속도 각 Owner가 계속 소유한다.

### BLOCKED

- 실제 22개 0a: 권한/manifest·등록 경로·baseline process 적용·무encode/무provider/무BLOB 증명 수집 미확보.
- 0b/A 전체 phase attribution: Recording 전체/concat/write·Search preparation/request·driver 여유 계측과 대표 fixture 선정 필요.
- 0c: 운영과 분리된 target·자원/비용 예산, experimental config/packet의 적용·복귀 근거, 단계별 장시간 fixture·최초 병목 계측 필요. 최소 20분 판정은 해당 duration의 실제 유효 timeline evidence가 있어야 함.
- F2의 정확한 T1/T2 kill, F3 heartbeat-only DB stall, F4 reason 검증: 격리/bounded harness·post-commit outcome 수집 필요.
- F5의 정확한 첫 checkpoint 지연은 해당 계측 없으면 목표 판정 불가. 기존 signal/terminal subset과 구분.
- E: 선행 concurrency=1 evidence·동시성 acceptance·별도 복수 Worker target·provider/자원 예산 확인 필요.

### DEFERRED

- **30분~1시간 logical timeline Real E2E(P3)**. 처리 방식은 P2 capacity 결과와 Recording/Search/Case 장시간 지원 설계 결정 뒤 정한다. single AnalysisSource·bounded/chunked processing·storage 구조 변경·기타 Owner 합의 방식 중 아직 확정한 것은 없다.
- 운영 scaling·Object Storage/RDS/Queue/GPU 도입·새 monitoring stack·장기 공개 hardening의 실제 적용. 다만 0c가 제품 목표 미충족을 보이면 필요한 장시간 지원 설계 **검토는 P2 Decision Gate에서 바로 재개**한다.

P3는 제품 약속인 장시간 탐색을 30~60분 logical timeline에서 확인하는 Real E2E다.
P2의 0a/0b/0c·DB/Search/Case timing·cleanup evidence와 잔여 failure mode를 정리하고,
제품 목표에 맞는 처리 방식·한도/대기·필요한 후보 merge/dedup·privacy/전송·실행/복구·자원/비용 조건을
Owner들과 검토한 뒤 별도 P3 계획을 작성한다. 실제 지원 범위 변경은 PM 승인 경계를 따른다.
4분 baseline 변경을 P3까지 금지하지 않는다. P2-0c experimental override와 향후 운영값 승인 절차를 분리한다.
긴 logical timeline의 사건 탐색과 거대한 단일 BLOB 성공은 서로 다른 질문이다.

## References

- [Product Spec — 장시간 탐색·Coarse/Fine·제품 변경 승인 경계](../../product/product-spec.md)
- [수정 전 감사와 owning code 인벤토리](../reviews/runtime-p2-plan-audit-2026-11-02.md)
- [#452 본문·전체 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452) · [#460](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/460) · [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450)
- [RT-14 Result](2026-10-31-rt14-aws-real-e2e.md) · [Recovery acceptance](../rt14-recovery-acceptance.md) · [공개 배포 Notes](../rt14-public-deployment.md)
- [Pre-implementation spike — Result, capacity 아님](pre-implementation-spike-2026-10-03.md)
- [Search Argon 결정](../../modules/search/decisions/search-argon-model-2026-10-27.md) · [UsageRecord Contract](../../architecture/contracts/contract-usage-record.md)
- [Provisional Baseline](../provisional-baseline-v0.1.md) · [Decision Register](../open-decision-register.md) · [Decision Classification](../decision-classification.md)
