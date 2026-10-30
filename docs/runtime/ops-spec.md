# Runtime Ops Spec

**Status:** Working — operations spec  
**Owner:** common/runtime — 김준영  
**Deployment baseline:** EC2 1대 + Docker Compose + MySQL  
**AWS 환경 입력:** [`official-inputs/aws-environment.md`](./official-inputs/aws-environment.md) — 카테캠 제공 조건 · 2026-10-02 / 10-30 실환경 snapshot  
**Last synced:** 2026-10-30 — `develop` `7bab60bc`  
**Architecture SoT:** [`docs/architecture/module-architecture.md`](../architecture/module-architecture.md)  
**Logical Data Model:** [`docs/architecture/erd-draft.md`](../architecture/erd-draft.md)  
**Alignment ADR:** [ERD ↔ Runtime 정합화](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)

> 이 문서는 배포된 Runtime을 **어떻게 운영·관찰·복구·확장할지** 정한다. Final Contract와 Logical ERD가 정의한 논리 의미·관계를 바꾸지 않으며, JobExecution/UsageRecord persistence와 queue algorithm은 [`runtime-tech-spec.md`](./runtime-tech-spec.md)이 소유한다.

## 1. 문서 경계

### 이 문서가 소유한다

- 배포 topology
- api / worker / mysql 운영 경계
- logging / privacy guardrail
- monitoring / alert 방향
- health/readiness의 운영 사용
- disk working set과 storage guardrail
- cleanup / retention 운영
- Object Storage 도입 기준
- capacity / scaling trigger
- CI/CD 및 pre-deploy validation
- 배포 검증 / release 식별 / rollback 운영
- build-time / runtime configuration 주입 경계
- 운영 장애 시 확장 기준

### 이 문서가 소유하지 않는다

- DB Queue claim/retry/lease algorithm — [Runtime Tech Spec](./runtime-tech-spec.md)
- JobExecution/UsageRecord schema — Final Data Contract
- cross-domain logical relationship / cardinality — [Logical ERD](../architecture/erd-draft.md)
- JSON vs 관계 테이블 같은 Runtime 물리 persistence — [Runtime Tech Spec](./runtime-tech-spec.md)
- Recording/Search benchmark 원본 — 각 module Owner
- 제품 workflow — Product / case
- Search/Readout 품질 threshold — 각 module/eval

## 2. 배포 Baseline

카테캠 현재 환경 제약 기준 baseline. 제공 조건 · 실측값의 원문은 [`aws-environment.md`](./official-inputs/aws-environment.md)이고 여기서는 운영 판단에 쓰는 값만 옮긴다.

```text
Region      ap-northeast-2 (서울 외 리전 불가)
EC2         t3.medium · CPU credit unlimited
CPU         2 vCPU
RAM         4GB (OS usable 약 3.7 GiB · swap 0 — 초기 관측값)
Disk        50GB gp3 · 암호화 (3,000 IOPS / 125 MiB/s)
OS          Ubuntu 24.04 LTS
제공 기간     2026-08-31 ~ 2026-11-20

EC2 1대
└─ Docker Compose
   ├─ migrate (one-shot)
   ├─ api
   ├─ worker
   └─ mysql
```

API와 Worker는 같은 image를 쓰는 modular monolith의 두 composition root다. migration은 api · worker 기동 전에 끝나는 one-shot service다([RT-13(a)](./rt13a-docker-compose.md)).

카테캠 계정의 자원 경계([`aws-environment.md`](./official-inputs/aws-environment.md) §2 · §4):

| 구분 | 상태 | 운영 함의 |
| --- | --- | --- |
| 추가 EC2 · 사양 변경 · 디스크 확장 · 추가 볼륨 | 차단. 사양 상향 · 디스크 확장은 카테캠 요청 시 검토 | capacity 대응은 §18 근거를 갖춰 요청 경로로만 한다. deploy role도 `ec2:CreateVolume` · `ec2:ModifyVolume`이 거부된다(10-30 확인) |
| RDS · ALB · Elastic IP | 차단. 요청 시 검토 | §18 조건이 생길 때만 요청한다 |
| S3 · ECR · CloudWatch · SSM Parameter Store | 사용 가능 | 10-30 SSO 권한으로 ECR · Log Group · SecureString 생성 → 삭제가 PASS. 사용 여부는 RD-12 · RD-13 결정이 정한다 |
| 서버 중지 · 시작 · 재부팅 · Security Group 편집 | 사용 가능 | 22번을 `0.0.0.0/0`으로 열면 보안 모니터링에 탐지된다 |

2026-10-30 host 상태: EC2는 10-02 이후 중지 상태였고, RT-14 스파이크를 위해 Docker Engine · Compose plugin을 설치했다(버전 · 설치 방식은 [`aws-environment.md`](./official-inputs/aws-environment.md) §9). 대신고 stack은 아직 배포되지 않았다. 같은 날 RT-14 준비 구현(#479)이 `develop`에 병합됐지만 AWS에서 실행하지 않았다(§2-1 「현재 구현 범위」).

### 2-1. AWS 배포 인증 · 서버 접속 기준

2026-09-22 카테캠 AWS 공지에 따라 **배포 인증과 서버 접속 방식은 아래를 baseline으로 확정**한다.

```text
GitHub Actions
→ GitHub OIDC
→ AWS STS AssumeRole
→ ktc-github-deploy

배포 명령 / 서버 접속
→ AWS Systems Manager(SSM)
→ EC2 instance role
```

원칙:

- GitHub Actions에서 AWS에 접근할 때 **장기 Access Key를 만들거나 GitHub Secrets에 저장하지 않는다.**
- 카테캠에서 제공하는 배포 역할 **`ktc-github-deploy`** 를 사용한다. 별도 IAM 역할 생성은 기본 경로가 아니다.
- AWS 계정 ID는 repository **Variable `AWS_ACCOUNT_ID`** 로 공급한다. 계정 ID 자체를 Secret으로 취급하지 않는다.
- AWS 인증이 필요한 job에만 `permissions: id-token: write`와 `contents: read`를 선언하고 `ap-northeast-2`의 배포 역할을 assume한다. 준비 구현은 credential action 대신 `deploy/aws.py`가 OIDC token → STS 교환을 직접 하고, 임시 자격증명을 `GITHUB_ENV` · output · artifact에 남기지 않는다([RT-14 실행 절차](./rt14-deployment.md) §5).
- 현재의 boundary/contract 등 **비-AWS CI에는 OIDC 권한을 추가하지 않는다.** 배포 workflow와 일반 PR CI를 분리한다.
- 배포 트리거는 `workflow_dispatch`다. 준비 구현의 두 workflow는 이 repository · repository ID · `develop` ref일 때만 job을 실행하고, 실제 원격 작업은 `RT14_EXECUTION_ENABLED` Variable이 `true`일 때만 돈다. fork PR에서는 OIDC token이 발급되지 않을 수 있으므로 `pull_request`를 실제 배포 경로로 사용하지 않는다.
- EC2 접속과 원격 명령 실행은 **SSM Session Manager / SSM Run Command**를 사용한다. GitHub Actions 배포를 위해 SSH private key를 저장하거나 보안그룹의 22번 포트를 인터넷에 개방하지 않는다.
- Object Storage를 도입해 S3 경유 배포를 선택하는 경우, GitHub Actions의 업로드 주체(`ktc-github-deploy`)와 EC2의 다운로드 주체(`ktc-ec2-ssm-role`)를 별도 권한 주체로 취급한다.
- 이 결정은 **S3 사용 자체를 확정하지 않는다.** Object Storage 범위는 §13의 실측 기반 결정 기준을 계속 따른다.

#### 실환경에서 확인된 제약 — 2026-10-02 · 10-30

관측 원문은 [`aws-environment.md`](./official-inputs/aws-environment.md) §8 · §9다. 아래는 그 사실이 위 원칙에 주는 함의만 적는다. exact 배포 절차는 RD-12(RT-14, [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450))가 정한다.

- **OIDC provider와 `ktc-github-deploy`는 이미 provision돼 있다.** 별도 IAM 생성 없이 workflow 쪽만 필요하고, 그 준비 구현은 `develop`에 있다. role로 실제 인증한 적은 아직 없다.
- **deploy role trust의 `sub` 조건은 이 repository 전체(`:*`)다.** AWS가 branch · tag · PR · environment를 구분하지 않으므로, 어떤 ref가 배포 role을 얻을 수 있는지는 GitHub workflow의 trigger · 조건이 제한해야 한다. `pull_request`를 배포 경로로 쓰지 않는다는 위 원칙이 이 제한의 일부다.
- **SSM Run Command(`AWS-RunShellScript`)는 `/bin/sh`로 실행되고 마지막 명령의 exit code만 결과가 된다.** 중간 명령이 실패해도 `Success`가 될 수 있으므로, Run Command `Success`를 배포 성공으로 읽지 않는다. 배포 절차는 실패를 끝까지 전파해야 하고, 성공 판정은 §19의 health · smoke 검증이 한다.
- **IMDSv2 필수 + hop limit 1이다.** bridge network의 container는 EC2 instance role 자격증명에 닿지 않는다. Parameter Store 조회 같은 role 권한 작업은 host의 배포 script가 하고 container에는 결과 파일만 넘긴다(§4-1 경로와 같다).
- **두 role 모두 `PowerUserAccess`가 붙어 있지만 최종 권한 상한은 카테캠 SCP · guardrail이다.** 정책 이름으로 사용 가능 서비스를 추론하지 않고, role로 직접 하는 확인은 OIDC 검증 workflow와 첫 배포에서 한다.
- **공인 IPv4는 EC2를 시작할 때마다 바뀐다**(Elastic IP 없음). 배포 · smoke가 고정 IP를 전제하지 않는다. public endpoint 조건은 §2-2.

#### 현재 구현 범위

2026-10-30 `develop` `7bab60bc` 기준, 이 절의 결정은 **준비 구현까지 반영**돼 있다(#479, [RT-14 실행 절차](./rt14-deployment.md) — IN_PROGRESS). RT-14 Decision Gate는 [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450)에서 진행 중이다.

`develop`에 있는 것 — 실행한 적 없는 준비 구현이다:

- `.github/workflows/rt14-oidc.yml` — 인증 전용 수동 workflow. 기대 account · role만 비교하고 identity를 출력하지 않는다
- `.github/workflows/rt14-deploy.yml` — `publish` · `deploy` · `rollback`을 각각 별도 수동 실행. publish는 amd64 image build → media · OCR acceptance → ECR immutable tag push → digest 확인
- `deploy/aws.py`(OIDC · ECR · SSM 호출) · `deploy/ec2.py`(host controller) · `deploy/configure.py`(Parameter Store → 보호 파일) · `tests/deploy/`

아직 하지 않은 것(AWS 설정 · 실행 기준):

- `AWS_ACCOUNT_ID` · `RT14_*` Variable · Secret 등록, `RT14_EXECUTION_ENABLED` 활성화
- OIDC 인증 workflow 실제 실행, ECR repository · host controller · 보호 디렉터리 준비
- 첫 publish · deploy · rollback rehearsal
- Security Group / IAM / EC2 설정 변경
- RD-12b ~ f · h Gate 승인 — 준비 구현은 후보이며 승인을 대신하지 않는다

남은 순서:

```text
1. RT-14 Gate 승인(#450) · Variable/Secret 등록
2. rt14-oidc로 role 인증 확인
3. host 준비(controller · 보호 디렉터리 · volume · config) — 별도 승인 작업
4. publish → deploy → health · 8종 등록 · smoke 확인
5. rollback rehearsal · 실제 배포 환경에서 pre-deploy review 수행
```

### 2-2. Public endpoint · Domain · TLS 기준

2026-09-22 카테캠 무료 도메인 공지는 **도메인 발급 자체를 현재 baseline 의무로 만들지 않는다.** 현재 Architecture는 인증을 MVP 최소 수준으로 두고 인증 방식 세부를 별도 결정으로 남기므로, 소셜 로그인·도메인·TLS 구현을 이 문서만으로 앞당기지 않는다.

다만 다음 요구가 실제로 생기면 public endpoint 운영 조건으로 함께 결정한다.

```text
외부 공개 demo URL 또는 OAuth redirect URI 필요
→ 안정적인 public IP 필요 여부 확인
→ 필요 시 Elastic IP 연결
→ A/CNAME 등 DNS 연결
→ HTTPS 인증서 / reverse proxy 구성
→ OAuth를 채택한 경우 정확한 HTTPS callback URI 등록
```

원칙:

- **Elastic IP는 현재 필수 자원이 아니다.** EC2 stop/start 이후에도 유지되어야 하는 public endpoint가 실제 요구일 때 도입한다. Elastic IP는 카테캠 계정에서 기본 차단이므로 도입은 운영진 요청 경로를 거친다([`aws-environment.md`](./official-inputs/aws-environment.md) §2 · §4, RD-14a). 그 전까지 공인 IPv4는 시작할 때마다 바뀐다.
- 현재 Compose는 api를 `127.0.0.1:<port>`에만 publish한다. 2026-10-02 관측 시 Security Group inbound rule은 0개였다. 외부 공개는 이 두 경계를 함께 바꾸는 RD-14 결정이다.
- 무료 서브도메인 공급자(DuckDNS, is-a.dev 등)는 현재 하나로 고정하지 않는다. 필요한 DNS record, 발급 소요시간, 유지 정책을 그 시점에 확인해 선택한다.
- 도메인 자동 갱신에 token 같은 비밀값이 필요한 공급자를 선택하면 해당 값은 repository에 커밋하지 않고 secret으로 관리한다.
- 외부 공개 endpoint에서 실제 사용자 데이터나 인증정보가 오가는 경우 **HTTPS를 pre-deploy 조건으로 검토**한다.
- 80/443 Security Group 규칙, Let's Encrypt, Caddy/Nginx 등 reverse proxy/인증서 도구는 실제 deployment stack을 닫을 때 결정한다.
- Google/Kakao 등 소셜 로그인 도입 여부와 인증 방식 자체는 이 문서가 결정하지 않는다. `module-architecture.md` §1-7 A2의 별도 결정을 따른다.
- 단순 내부 개발/Real E2E 때문에 domain/EIP/OAuth 구현을 선행하지 않는다.

#### Reverse Proxy 선택 원칙

외부 공개 endpoint와 HTTPS가 실제 요구가 되면, single EC2 + Docker Compose baseline에서는 **Caddy를 첫 구현 후보로 검토**한다.

이 선택 기준은 특정 도구 선호가 아니라 현재 운영 조건에 있다.

- TLS 인증서 발급·갱신 책임을 애플리케이션에서 분리할 수 있어야 한다.
- 단일 서버에서 proxy 설정과 인증서 lifecycle을 관리하는 운영 표면을 작게 유지한다.
- `api`는 public 80/443을 직접 소유하지 않고 내부 application port에 집중한다.
- 고급 routing, 세밀한 traffic tuning, 다중 upstream/load balancing 요구가 실제로 커지면 Nginx/ALB 등 다른 선택지를 다시 비교한다.

따라서 현재 결정은 **Caddy 고정**이 아니라 “작은 운영 표면을 우선하고 요구가 커질 때 확장한다”는 선택 기준이다.

#### 현재 구현 범위

이번 공지 반영은 **운영 조건과 후속 결정 시점의 문서화만 수행**한다.

현재 단계에서는 다음을 하지 않는다.

- Elastic IP 할당/연결
- 무료 도메인 발급 또는 DNS record 생성
- Security Group 80/443 변경
- TLS 인증서 발급
- Caddy/Nginx 등 reverse proxy 도입
- Google/Kakao OAuth client·callback 등록

## 3. 현재 상태와 목표 상태

### 현재 develop에서 확인된 것 — 2026-10-30 (`7bab60bc` 기준)

Task별 상세와 검증 기록은 [Runtime Implementation Plan](./runtime-implementation-plan.md) §6 · [Implementation Log](./runtime-implementation-log.md)가 소유한다. 로컬 구성 절차는 [로컬 Runtime 실행환경](./local-runtime-environment.md)이다.

- Python 3.12 정렬 (§5)
- MySQL Runtime persistence · DB Queue — `job_execution` claim · lease/heartbeat fencing · STALE sweep · 자동 retry · 협력적 중단 (RT-03 ~ RT-06)
- usage ledger · Final UsageRecord persistence · reconciliation (RT-07)
- api composition root — FastAPI · case 생성/조회/command · `/health/live` · `/health/ready` · source upload · frame · DerivedAsset read (RT-08 · RT-11)
- worker composition root — Search · IncidentClip · Readout · export handler 등록, 기본 Worker에 production Readout(PaddleOCR) 연결 (RT-10 · #468)
- recording MySQL persistence · durable source publish (REC-1 · RT-11(a))
- staging · temp cleanup (RT-12(a)) · DB 집계 query와 structured log event catalog (RT-12(b))
- local Docker / Compose — 단일 image · migrate one-shot · api · worker · mysql · secret file mount · B-O1 log rotation (RT-13(a))
- local MySQL logical backup / restore 도구 (RT-13(b))
- EC2 배포 준비 구현 — OIDC 인증 · ECR publish · SSM host controller · rollback 도구와 Worker 8종 등록 marker (RT-14 #479, §2-1). AWS에서 실행하지 않았다
- CI: MySQL gate · 배포 image media/OCR acceptance · boundary/contract · web (§19)

### 아직 없는 것

- EC2 실제 배포 — Gate 승인 · AWS 입력 등록 · 첫 publish/deploy · rollback rehearsal(RT-14, RD-12b ~ f)
- 배포 후 검증의 실제 실행(RD-12h). 준비 구현의 smoke는 host 내부 loopback이고, 외부 경로 smoke는 RD-14에 달려 있다
- production log transport · log retention(RD-13a · RD-11a) — 준비 구현은 `awslogs` + dual local cache 후보만 있다. EC2에 Log Group 없음
- production restart policy · health alert(RD-13c) — 준비 구현은 `no` · `unless-stopped` 중 승인값만 받고 기본값을 두지 않는다. local Compose에는 `restart:` 없음
- Worker 상태 운영 노출(RD-13d) — 8종 등록 marker는 process · 등록 증거이며 idle heartbeat가 아니다
- 지표 정기 기록 · 대시보드(RD-13b) — 집계 query는 있으나 수동 실행이다
- public endpoint / domain / TLS(RD-14)
- Ruff · type checker · secret scan(RT-15)
- P2 Runtime Capacity Smoke — baseline EC2에서 working set · concurrency 실측

따라서 local runtime 절(§4 · §6 · §9 일부)은 현재 동작을 가리키고, **EC2 배포 · 운영 관측 · capacity 절은 아직 구현 목표와 운영 acceptance criteria**다.

## 4. Docker / Process 운영

목표 process:

```text
api
→ FastAPI request / case command / Runtime dispatch

worker
→ Runtime claim / domain public capability 실행

mysql
→ product state + Runtime persistence
```

원칙:

- API와 Worker가 서로 private implementation을 import해 orchestration loop를 만들지 않는다.
- Worker crash가 API process crash로 이어지지 않아야 한다.
- MySQL은 single EC2 baseline이지만 volume을 container ephemeral layer와 분리한다.
- api/worker image는 가능한 같은 dependency/runtime baseline을 사용하고 command만 분리한다.
- secret은 image나 repository에 bake하지 않는다.

local Dockerfile · Compose는 RT-13(a)에서 닫혔다 — 단일 image, `docker/runtime.py`의 `migrate` · `api` · `worker` · `ready` 진입점, api · worker · migrate 같은 numeric UID(`10001`), MySQL은 named volume. 구성 원문은 [`rt13a-docker-compose.md`](./rt13a-docker-compose.md)와 [로컬 Runtime 실행환경](./local-runtime-environment.md)이다. EC2에서의 image 전달 · restart policy는 RT-14 범위(RD-12b · RD-13c)로 남는다.

### 4-1. Build-time / Runtime Configuration 경계

배포 환경변수는 “secret인가 아닌가”뿐 아니라 **언제 주입되는 값인가**를 구분한다.

```text
Build-time
→ image/dependency/build 산출물 생성에 필요한 값

Runtime
→ 실행 환경에 따라 달라지는 DB/provider/endpoint/tuning 값
```

원칙:

- build image에 provider key, DB credential, access token 같은 secret을 bake하지 않는다.
- 가능한 한 동일 image를 환경별로 재사용하고 환경 차이는 runtime configuration으로 주입한다.
- Compose/Dockerfile에는 secret 값 자체보다 변수 이름과 주입 경계만 남긴다.
- `.env.example`을 둘 경우 non-secret key 이름과 안전한 예시만 제공한다.
- CI에 등록된 값이라도 build 단계에서 필요한 값인지 runtime 단계에서 필요한 값인지 구분한다.

Runtime secret source와 전달 경로는 확정이다(RD-07, [#249](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/249), 2026-10-04). 앱이 파일을 읽는 규칙(값은 파일에서만 · `DAESINGO_ENV_FILE`은 composition root만 해석 · startup fail-fast · key 이름만 로그)은 [Tech Spec](./runtime-tech-spec.md) §15.2가 소유한다.

```text
SSM Parameter Store SecureString
→ EC2 instance role로 fetch (EC2 쪽 배포 script)
→ host의 보호된 파일 (container UID 소유 · 최소 권한, 예: 0400 · 값을 stdout/log에 남기지 않음)
→ Compose secret / file mount → api · worker
→ DAESINGO_ENV_FILE = mount된 파일 경로
```

- **GitHub Actions는 secret 값을 조회하거나 전달하지 않는다.** OIDC로 deploy role을 얻어 SSM Run Command로 「배포 절차를 실행하라」만 지시한다. Run Command 입력에 평문 secret을 싣지 않는다. 역할은 `rt14-deploy.yml`(배포 orchestration) · host controller `deploy/configure.py`(Parameter Store fetch · 보호 파일 게시) · `deploy/ec2.py`(migration · Compose render · 실행 · 검증) · image 안 Compose 정의(secret file mount · 실행 구조)로 나뉜다. 준비 구현의 exact 단계는 [RT-14 실행 절차](./rt14-deployment.md) §4 · §6이고, 승인은 RD-12.
- Compose는 file source secret의 `uid` · `gid` · `mode`를 적용하지 않으므로 **host 파일 권한이 접근 제어**다.
- **rotation.** Parameter Store 재조회 → host 파일 갱신 → `docker compose up -d --force-recreate api worker`. `docker compose restart`를 rotation 보장 수단으로 쓰지 않는다.
- **배포 전 확인(차단 아님).** 카테캠 guardrail에서 EC2 instance role이 해당 경로에 `ssm:GetParametersByPath`(필요 시 `kms:Decrypt`)를 할 수 있는지 M6 전에 확인한다. 2026-10-30 SSO 권한으로 `SecureString`(기본 `aws/ssm` key) 생성 → `get-parameters-by-path --with-decryption` → 삭제가 PASS했고, EC2 instance role의 inline Deny에는 SSM이 없었다([`aws-environment.md`](./official-inputs/aws-environment.md) §9). SCP가 이 작업을 막지 않는다는 근거이며, **EC2 role로 직접 하는 조회는 첫 배포에서 확인한다.** 불가하면 Session Manager 등으로 host 파일을 수동 배치하고, container 쪽 계약은 그대로다.
- container는 IMDS를 통해 instance role 자격증명을 얻지 못한다(hop limit 1, §2-1). Parameter Store 조회는 위 경로대로 host 배포 script에서만 한다.
- secret을 process environment로 넣지 않으므로 `docker inspect` · `/proc/<pid>/environ` · ffmpeg 같은 자식 process에 값이 노출되지 않는다([spike S3](./experiments/pre-implementation-spike-2026-10-03.md)).

### 4-2. API ↔ Worker 공유 저장 경계

확정(RD-17, [#246](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/246), 2026-10-04). recording metadata schema · ref 복원 · FrameRef durability 구현은 recording이 소유한다.

- **bytes.** api와 worker는 같은 host의 **local filesystem mount 하나**를 공유한다. 그 안에 staging · source · derived 계열 경계를 둔다. api · worker는 같은 image 계열과 **같은 numeric UID**로 실행한다. baseline에 Object Storage를 두지 않는다(§13).
- **publish 순서 — 파일 먼저, row 나중.** upload bytes를 같은 mount의 staging에 쓰고 → `fsync` → 같은 mount의 final 위치로 publish → recording 등록 · metadata commit. staging에 container `/tmp`나 다른 volume을 쓰지 않는다 — 다른 mount에서 오는 rename은 `EXDEV`다([spike S3](./experiments/pre-implementation-spike-2026-10-03.md)). 정상 순서에서 crash가 남기는 것은 row 없는 orphan · staging 파일뿐이고 dangling DB ref가 아니다. orphan · staging · temp 정리 나이와 scan 주기는 [Provisional Baseline v0.1](./provisional-baseline-v0.1.md) §2.9(B-C1 ~ B-C4), upload 한도 · 수신 timeout은 같은 문서 §2.6이다.
- **metadata.** SourceAsset · MediaStream · local locator · case↔asset 연결처럼 process 사이에 공유해야 하는 recording metadata는 recording 소유 MySQL table에 둔다. Runtime은 recording schema를 소유하지 않는다.
- **persistent 범위 원칙.** ref가 process 경계나 process 수명을 넘어 다시 역참조되면 persistent다 — SourceAsset · MediaStream · locator · case↔asset 연결 · restart 뒤 다시 필요한 timeline · span resolution · IncidentClip · DerivedAsset, 그리고 **CaseView에 노출된 FrameRef**(`thumb_ref` · `preview_ref` · `plate_preview_ref`). FrameRef를 bytes로 저장할지 locator · timestamp를 저장해 재생성할지는 recording 구현 선택이다. Worker 안에서만 쓰고 다시 만들 수 있는 AnalysisSource bytes · frame inspection cache는 process-local로 둘 수 있다(RD-09).
- **restart.** ref는 등록 때 한 번 발급해 persist하고 restart 뒤에는 다시 등록하지 않고 복원한다. 같은 파일을 사용자가 새로 등록하면 새 logical asset이라는 현재 의미는 유지한다.
- Compose 표기 · host 경로 값은 RD-12a. local disk working set이 P2에서 안전하지 않거나 multi-host 요구가 생기면 §13 기준으로 Object Storage를 다시 본다.

## 5. Python / Dependency Runtime

팀 문서 기준 목표는 Python 3.12 + root `pyproject.toml` + `uv.lock`이다.

2026-09-19 당시 있던 불일치(pyproject `>=3.10` · uv.lock `>=3.13` · boundary CI 3.11)는 커밋 `10cfca4`(2026-09-20)에서 해소됐다. 2026-10-30 `develop` 기준 실제 값:

```text
root pyproject.toml   requires-python >=3.12
uv.lock               requires-python >=3.12
.python-version       3.12
Dockerfile            python:3.12-slim-bookworm (digest 고정) · uv 0.11.15 (digest 고정)
                      uv sync --locked --no-dev --extra eval-gemini --extra readout-paddle
python-tests CI       Python 3.12 · uv 0.11.15 · uv sync --locked
boundary-check CI     Python 3.12
```

media · OCR toolchain(FFmpeg 8.1 · PaddleOCR 버전 · 모델)의 고정값은 [로컬 Runtime 실행환경](./local-runtime-environment.md) §1이 정리한다.

구현 체크:

- [x] root `pyproject.toml`을 3.12 기준으로 정합
- [x] `.python-version` 정합
- [x] `uv.lock` 3.12 기준 재생성
- [x] `uv sync --locked` 재현 (`python-tests.yml`)
- [x] GitHub Actions Python 3.12 통일
- [ ] repo-wide type checker 한 개로 수렴 — type checker 설정과 CI step이 아직 없다

Python version의 executable SoT는 prose가 아니라 실제 config/workflow다.

## 6. Structured Logging

Runtime 운영 로그는 key-value structured log를 기본으로 한다. container local log rotation 상한과 application log level의 시작값은 [Provisional Baseline v0.1](./provisional-baseline-v0.1.md) §2.13(B-O1 · B-O2)이다 — log transport와 retention 기간은 그 값이 아니다(§23).

권장 correlation:

```text
trace_id
case_id
job_id
execution_id
module
event
duration_ms
status
```

예:

```json
{
  "level": "INFO",
  "event": "job.execution.completed",
  "trace_id": "tr_...",
  "case_id": "case_...",
  "job_id": "job_...",
  "execution_id": "exec_...",
  "module": "search",
  "duration_ms": 81231,
  "status": "SUCCEEDED"
}
```

### 6-1. Correlation Context 전파

비동기 실행 경로에서는 로그가 API process와 Worker process로 분리되므로 correlation ID를 한 process 안에서만 유지해서는 충분하지 않다.

목표 흐름:

```text
HTTP request
→ API / case
→ Runtime dispatch
→ queue
→ Worker
→ recording / search / readout / evidence
→ provider adapter
```

원칙:

- API 진입점에서 요청 correlation context를 만들거나 신뢰 가능한 기존 값을 수용한다.
- Runtime dispatch 이후 Worker에서도 같은 `trace_id`를 이어서 기록할 수 있어야 한다.
- `case_id`, `job_id`, `execution_id`가 생긴 시점부터는 같은 로그 event에 함께 남긴다.
- `trace_id`는 observability용 상관관계 값이며 business identity나 Final Contract의 authoritative key를 대체하지 않는다.
- provider가 안전한 metadata/correlation field를 지원하면 최소 식별자만 전달할 수 있고, 지원하지 않으면 local log에서 invocation과 execution의 관계를 남긴다.
- `trace_id`는 `job_execution` row의 Runtime 내부 column이다. API request context에서 dispatch 때 기록하고 retry attempt에도 같은 trace lineage를 잇는다. Contract 필드로 공개하지 않는다(RD-01i, [Tech Spec](./runtime-tech-spec.md) §4.2). Final Contract schema를 관측 편의를 위해 임의 확장하지 않는다.

## 7. Logging / Privacy Guardrail

실제 사용자 데이터가 들어가는 운영 단계에서는 다음 원문을 일반 운영 로그에 남기지 않는다.

- 번호판 문자열
- 정확한 GPS 좌표 / 상세 위치 원문
- 원본 영상 / frame bytes
- 불필요한 전체 filesystem path
- 외부 AI request/response payload 전문
- 사용자 free text 전문
- API key / access token / secret

`UsageRecord` 역시 raw provider payload를 보존하지 않는다.

현재 `docs/management/pre-deploy-security-review.md` 정책대로 Mock/합성 데이터 중심 개발 중에는 전역 masking logger를 별도 merge blocker로 보지 않는다.

하지만 실제 사용자 데이터/외부 provider/배포 단계 전에는 해당 security review를 다시 실행해야 한다.

## 8. Monitoring Baseline

초기에는 Prometheus/Grafana/OpenTelemetry full stack을 baseline으로 두지 않는다.

1차 관측 수단:

```text
structured stdout
→ AWS log collection

+
Runtime DB query
+
UsageRecord
+
EC2 기본 CPU/RAM/disk 지표
```

최소 운영 질문:

- queue wait이 얼마나 되는가
- oldest queued Job이 얼마나 오래됐는가
- SUCCEEDED / FAILED / STALE / CANCELLED 비율은 어떤가
- retry가 얼마나 발생하는가
- execution latency가 얼마나 되는가
- provider invocation 비용/latency가 얼마인가
- Worker heartbeat/lease가 정상인가
- local disk working set이 얼마나 되는가
- OOM/swap/CPU saturation이 반복되는가

2026-10-30 현재:

- queue wait · oldest queued · execution duration · STALE · retry · cancel 지표는 RT-12(b)의 **DB 집계 query**와 structured log event catalog로 local · integration에서 볼 수 있다([`rt12b-observability.md`](./rt12b-observability.md)). 정기 기록 · 대시보드는 없다(RD-13b).
- 배포된 stack이 없으므로 이 값은 아직 실제 운영 metric이 아니다.
- AWS 쪽 수집 경로: EC2 instance role에 `CloudWatchAgentServerPolicy`가 붙어 있고 Log Group 생성 · retention 설정이 SSO 권한으로 가능했다. 그러나 CloudWatch Agent는 설치돼 있지 않고 Log Group도 없다([`aws-environment.md`](./official-inputs/aws-environment.md) §8 · §9). 위 「structured stdout → AWS log collection」 경로의 transport 선택은 RD-13a다. RT-14 준비 구현은 Docker `awslogs` driver + dual local cache를 승인 대기 후보로 render한다 — 별도 Agent는 필요 없지만 daemon의 instance role 권한과 실제 수신 확인이 남는다([RT-14 실행 절차](./rt14-deployment.md) §1 · §8).
- EC2 기본 CloudWatch metric(CPU 등)은 콘솔에서 볼 수 있다. RAM · disk · process RSS는 Agent 없이 기본 metric에 없다.

### Monitoring Stack 확장 기준

Prometheus/Grafana/OpenTelemetry를 쓰지 않는 것이 목표가 아니라, **현재 관측 수단으로 해결되지 않는 반복 운영 문제가 생길 때 도입**한다.

예를 들어 다음 요구가 실제로 생기면 시계열 metric 수집/대시보드 도입을 검토한다.

- queue wait / oldest queued age를 지속적으로 추세 비교해야 함
- execution latency / failure / retry rate의 시간대별 변화가 필요함
- Worker heartbeat, provider latency, CPU/RAM/disk를 같은 운영 화면에서 상관 분석해야 함
- 수동 DB query와 로그 검색만으로 장애 감지/원인 축소가 반복적으로 늦어짐
- metric 기반 alert가 실제 운영 대응에 필요함

도구 도입 자체가 목적이 아니라 **관측·감지·원인 축소 시간을 줄이는가**를 기준으로 판단한다.

## 9. Health / Readiness 운영

Runtime Tech Spec의 endpoint 의미:

```text
/health/live
→ API process가 살아 있는가

/health/ready
→ 필수 Runtime dependency가 준비됐는가
```

운영 원칙:

- liveness failure는 process restart 후보
- readiness failure는 신규 traffic/처리 준비 불가 신호
- 외부 AI provider 하나의 장애를 API 전체 liveness failure로 취급하지 않음
- Worker는 Runtime DB의 heartbeat/lease 기반으로 별도 관측 가능

`/health/ready` probe 제한 시간은 [Provisional Baseline v0.1](./provisional-baseline-v0.1.md) §2.10(B-H1 ~ B-H3)이다. 실제 restart/alert threshold는 deployment 환경이 생긴 뒤 정한다(RD-13c).

현재 구현(2026-10-30): 두 endpoint는 api composition root에 있다(RT-08(a)). local Compose의 api healthcheck는 `docker/runtime.py ready`로 readiness를 확인하고, mysql은 `mysqladmin ping`을 쓴다. local Compose에 `restart:` 정책은 없다. Worker는 HTTP health가 없고 heartbeat는 Runtime DB와 log로만 보인다 — 운영 노출 방식은 RD-13d다. RT-14 준비 구현은 배포 검증에서 Worker의 실제 process · revision · 8종 handler 등록 marker(`worker/deployment_status.py`)를 확인한다. 이 marker는 idle heartbeat나 handler 성공을 뜻하지 않는다.

## 10. Storage Lifecycle

Final recording Contract의 lifecycle 용어를 따른다.

```text
External Source Reference
Managed Source Copy
AnalysisSource
RemoteCopy
IncidentClip
DerivedAsset
```

### External Source

사용자 원본은 서비스가 overwrite/delete하지 않는다.

`purge_case()`는 서비스 내부 reference를 제거할 수 있지만 사용자 기기/외부 source 자체를 물리 삭제하지 않는다.

### Managed / Derived Assets

서비스 관리 사본과 파생물은 retention/cleanup 대상이다.

### RemoteCopy

provider delete를 지원하면 삭제 요청할 수 있다. 즉시 삭제를 보장할 수 없으면 `DeletionReport`에 `PENDING_EXPIRY`를 남긴다.

provider delete API 호출의 구현 경계는 provider adapter가 소유한다.

## 11. Local Disk Guardrail

50GB local disk를 장시간 원본의 영구 저장소로 설계하지 않는다. root filesystem은 약 48G로 보이고 Docker 설치 전 사용량은 2.6G였다(2026-10-30, [`aws-environment.md`](./official-inputs/aws-environment.md) §9). 디스크 확장 · 추가 볼륨은 직접 할 수 없고 카테캠 요청 경로만 있다(§2). 공지는 디스크 부족의 가장 흔한 원인으로 Docker build cache 누적을 들었다(같은 문서 §7).

동시에 local disk는 다음이 경쟁한다.

```text
MySQL data
Docker image/layer
temp transform output
AnalysisSource
IncidentClip / DerivedAsset
logs
OS working space
```

따라서 “50GB가 있으니 영상 X시간 저장” 같은 단일 계산을 하지 않는다.

필요한 것은 Real Recording Benchmark를 통한 **실행 working set** 측정이다.

관측 대상:

- source ingest byte
- transform temp byte
- proxy/AnalysisSource byte
- peak simultaneous disk
- cleanup 이후 steady-state disk

> **현재 구현 사실 (2026-10-30 `develop` `7bab60bc` 기준):** local Compose에서 api · worker는 named volume `/media` 하나를 공유한다 — `source`(durable publish 원본), `staging`(API upload), `api-temp` · `worker-temp`(각 process의 미디어 작업 temp). Recording이 준비한 미디어 bytes(AnalysisSource 등)는 recording 소유 MySQL table의 `LONGBLOB` 행에 저장되므로 **MySQL data volume의 working set**에 들어간다. 이 저장의 지원 길이 · byte 한도 운영값은 Recording Owner 측정 뒤 확정할 미결이다([#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452), [로컬 Runtime 실행환경](./local-runtime-environment.md) §5 · §9). 그 밖에 Docker image(PaddleOCR 모델 cache 포함)와 container log(B-O1, container당 ~100 MB)가 같은 disk를 쓴다. EC2 배포에서는 rollback을 위해 current · previous known-good image를 지우지 않고 candidate image가 잠시 더해진다([RT-14 실행 절차](./rt14-deployment.md) §8 예산표). AnalysisSource 재사용 범위는 RD-09, process 사이 bytes · ref 경계는 §4-2(RD-17)다.

Issue #95 R3에서는 동일 AnalysisSource의 process-local reuse가 materialization 비용을 크게 줄일 가능성이 확인됐다. 그러나 현재 확인된 것은 **성능 최적화 후보**이지 durability guarantee가 아니다.

따라서 Runtime은 persistent/shared cache를 먼저 도입하지 않고 다음을 capacity 실험에서 함께 관측한다.

- cold materialization과 warm reuse의 시간·disk 차이
- Worker/process restart 후 재생성 비용
- 동일 입력 동시 요청의 duplicate materialization 가능성
- cleanup 이후 steady-state disk 회수
- reuse 이득이 local-only storage의 제약을 상쇄하는지

이 결과가 local-only storage로 부족하다는 근거를 만들 때 §13의 Object Storage 또는 shared persistence 후보를 검토한다.

## 12. Recording / Search Benchmark Dependency

Runtime/Ops가 Recording/Search benchmark 원본을 소유하지 않는다.

### recording Owner가 제공할 것

- media/profile/ffmpeg/storage 측정
- transform time
- peak disk
- AnalysisSource materialization 특성

### search Owner가 제공할 것

- provider compatibility
- recall
- token/cost/latency
- provider-specific media/input 제약
- coarse/fine strategy 실험

Issue #41로 이미 닫힌 경계:

```text
recording → measurable media property 보장
search    → recall/provider suitability 검증
```

### 12-1. Issue #95 P0/P1에서 Runtime이 받아들이는 사실

Issue #95의 Elice 전환 실험에서 Runtime 설계에 영향을 주는 사실은 다음 정도다. 범위는 2026-09 시점 운영 경로 — `gemini-3.8-flash` · OpenAI-compatible `/v1/chat/completions` · base64 data URL — 이며, 다른 모델·전송 방식에 그대로 일반화하지 않는다([`mlapi.md`](./official-inputs/mlapi.md)).

- Elice ML API의 inline video 경로가 위 모델·경로의 실제 호출에서 동작했다.
- Files API / provider-side reusable object를 Elice 기본 경로로 전제할 수 없으며, Search가 AnalysisSource stream을 provider 전송 형식으로 변환한다.
- binary media를 base64 data URL + JSON request로 만들기 때문에 transport 단계에서 request body와 process memory working set이 원본 binary보다 증가할 수 있다.
- AnalysisSource materialization에는 ffmpeg CPU/RAM/time/temp disk 비용이 존재한다.
- 동일 `source + span + profile`의 local reuse는 materialization 비용을 크게 줄일 가능성이 있다.
- 20초·480p H.264 MP4·audio off는 P1에서 다음 단계의 첫 시험 후보로 제안됐지만 **canonical profile이나 운영 상수가 아니다.**

반대로 아직 다음은 확인되지 않았다.

- baseline EC2에서 api + worker + mysql + ffmpeg + base64/JSON이 동시에 실행될 때 peak CPU/RAM/disk
- provider call 중 request construction이 Worker RSS에 미치는 실제 영향
- MySQL과 media transform의 CPU/I/O contention
- Worker concurrency를 1보다 늘릴 자원 여유
- restart/실패 후 temp media와 local reuse working set 회수
- 30분~1시간 입력을 제품 경로로 처리했을 때 queue/cost/latency/storage 특성

따라서 위 미확인값을 구현 상수로 채우지 않고 [`experiments/elice-runtime-capacity-smoke-plan.md`](./experiments/elice-runtime-capacity-smoke-plan.md)의 **P2 Runtime Capacity Smoke**로 검증한다.

```text
#95 P0/P1
→ Runtime capacity 질문 추출
→ P2: concurrency=1 baseline 측정
→ 결과로 EC2 / concurrency / storage 가설 갱신
→ 필요 시 P3 long-duration Runtime E2E 계획
```

P2는 Search/Recording의 품질·profile 결정을 대신하지 않는다. Runtime/Ops에는 **실험 결과가 실행/배포/저장 구조에 주는 영향만** 승격한다.

## 13. Object Storage 도입 기준

Object Storage를 baseline 의무로 두지 않는다.

다음이 확인되면 도입 범위를 결정한다.

- 50GB local working set이 안전하지 않음
- 여러 실행 간 재사용을 위해 local-only storage가 부족
- instance 교체/재배포 시 보존해야 할 managed asset 존재
- upload/download overhead보다 persistence 이점이 큼
- lifecycle/retention을 object store 정책으로 관리하는 편이 단순
- process-local AnalysisSource reuse가 restart/다중 Worker 환경에서 반복 materialization을 유발하고 P2/P3에서 그 비용이 실제 병목으로 확인됨

도입 시에도 domain Contract에 provider/storage locator를 노출하지 않고 storage adapter 뒤에 둔다. local reuse의 성능 이득만으로 Object Storage를 선결하지 않는다.

## 14. Retention / Cleanup

현재 exact retention 일수는 미결이다.

금지:

- 근거 없이 “7일”, “30일” 같은 숫자 선결
- video asset retention과 UsageRecord retention 자동 동일시
- 사용자 External Source까지 서비스 purge 대상처럼 취급

결정해야 할 축:

```text
Managed Source Copy retention
AnalysisSource retention
IncidentClip retention
DerivedAsset retention
RemoteCopy expiry/delete
UsageRecord retention
log retention
```

각 값은 개인정보/재현성/비용/사용자 flow를 함께 보고 결정한다.

## 15. Provider 장애 운영

Circuit Breaker는 현재 baseline이 아니다.

초기 대응:

```text
provider failure taxonomy
+ retry policy
+ terminal JobExecution
+ structured log
+ UsageRecord
+ queue wait 관측
```

다음 현상이 반복되면 Circuit Breaker를 검토한다.

```text
provider 장기 장애
→ retry 반복
→ queue 적체
→ 정상 작업도 지연
```

threshold를 미리 invent하지 않는다.

## 16. DB Queue → 전용 Queue 확장 기준

MySQL Queue를 유지하다 다음이 실제 문제로 반복되면 Redis/SQS/RabbitMQ 등 전용 queue를 검토한다.

- Worker 다중화로 claim contention
- queue workload가 제품 DB latency 악화
- scheduling/delay/redrive 요구가 DB 구현 복잡도를 크게 증가
- DB 장애와 queue 장애를 분리해야 함

도입 여부는 기술 선호가 아니라 관측된 failure mode로 결정한다.

## 17. Worker 1 → Worker Pool 확장 기준

다음 두 조건이 함께 필요하다.

```text
queue wait가 실제 UX 문제
+
provider rate limit / CPU/RAM/I/O에 병렬 여유
```

CPU-bound ffmpeg/OCR와 network-bound provider call을 구분해 병목을 측정한다.

Issue #95 후속에서는 [P2 Runtime Capacity Smoke](./experiments/elice-runtime-capacity-smoke-plan.md)의 **Worker concurrency=1**을 먼저 baseline으로 측정한다. concurrency=1에서 api/mysql과 자원 경합, request construction peak, cleanup을 설명할 수 있기 전에는 Worker 수 증가를 성능 개선책으로 선결하지 않는다.

Worker 수를 늘리기 전에 DB claim/lease가 concurrent-safe함을 integration test로 확인하고, P2 결과에서 병렬 여유가 관측되어야 한다.

## 18. 카테캠 자원 확장 기준

아래 자원은 모두 카테캠 계정에서 직접 만들거나 바꿀 수 없고 운영진 요청 후 검토된다([`aws-environment.md`](./official-inputs/aws-environment.md) §2 · §4). 요청에는 팀 · 필요 항목 · 이유 · 예상 사용 기간이 들어가므로, 이 절의 조건을 뒷받침하는 관측값을 함께 남긴다. 지원 가능한 상한(최대 사양 · GPU · EBS 상한 · 예산)은 아직 확인되지 않았다(같은 문서 §8). 제공 기간은 2026-11-20까지다.

### EC2 사양 상향

같은 workload에서 반복적으로:

- OOM
- swap thrashing
- 지속 CPU saturation
- Runtime queue wait 증가

가 재현될 때 요청한다.

### Disk 확장

cleanup/retention/Object Storage 분리를 적용한 뒤에도 **실행 working set** 때문에 50GB가 부족할 때.

단순 장기 영상 보관을 위해 EBS만 계속 늘리는 방향은 baseline이 아니다.

### RDS

- MySQL과 ffmpeg/OCR/Worker가 CPU/RAM/I/O를 지속 경쟁
- managed backup/recovery가 필요
- DB를 EC2 lifecycle에서 분리해야 함

일 때 검토한다.

### Elastic IP

외부 공개 demo/domain endpoint의 IP 안정성이 실제 요구일 때. §2-2의 public endpoint 조건이 생기기 전에는 baseline 자원으로 선점하지 않는다.

### ALB

API server 2대 이상 또는 load balancing/health routing이 필요할 때.

### GPU

자체 inference가 실험이 아니라 제품 Runtime 필수 경로가 됐고 CPU/provider 대안이 없을 때.

## 19. CI Quality Gate — 현재와 목표

### 현재 실제 CI — 2026-10-30 (`develop` `7bab60bc` 기준)

일반 CI 세 workflow의 trigger는 같다. 배포용 `rt14-*` 두 workflow는 수동 실행 전용이며 아래 「Deployment workflow 분리 원칙」에 따로 적는다. `web-tests`만 path filter(`apps/web/**` · `data/**` · `package*.json` · 자기 파일)가 있다.

```text
pull_request → develop/main
push         → develop
workflow_dispatch
```

`.github/workflows/python-tests.yml` — job 3개. 분할 근거는 [`ci-test-partitions.md`](./ci-test-partitions.md)다.

```text
regression   ubuntu-24.04 · Python 3.12 · uv 0.11.15
             uv sync --locked --extra test --extra eval-gemini   (PaddleOCR 제외)
             pytest collection partition 완전성 · 서로소 검사
             ffmpeg 설치 · -fps_mode / libx264 지원 검사
             Recording 합성 media smoke 1건 — skip 금지 assert
             배포 image docker build → media / OCR preflight · acceptance
               (readout startup 실패 3종 · MySQL 붙은 Readout process acceptance 포함)
             Non-MySQL regression

mysql        MySQL 8.4 service · DAESINGO_REQUIRE_MYSQL=1
             canonical MySQL suite 1회 · strict JSON/JUnit · 실제 report mutation

test         regression · mysql 결과를 모두 요구하는 집계 job (기존 check 이름 유지)
```

`.github/workflows/boundary-check.yml`:

```text
Python 3.12
python scripts/check_boundaries.py
python scripts/check_contract_fixtures.py
```

`.github/workflows/web-tests.yml`:

```text
Node 24 · npm ci
apps/web: tsc -b · npm run test:web
```

Gate별 현재 상태:

| Gate | 상태 |
| --- | --- |
| Python 3.12 | 있음 |
| `uv sync --locked` | 있음 (`python-tests`) |
| boundary / contract fixture | 있음 (`boundary-check`) |
| repo-wide pytest (offline) | 있음 (`python-tests` regression · mysql로 분할). Mock Pack fixture 검증은 module별 테스트로 돈다. 별도 Mock validator job은 없다 |
| Recording media smoke | 있음 (`python-tests` regression) |
| MySQL Runtime integration | 있음 (`python-tests` mysql) |
| 배포 image build · media/OCR acceptance | 있음 (`python-tests` regression). image를 registry에 push하지 않는다 |
| web 타입 검사 · 테스트 | 있음 (`web-tests`) |
| Ruff | 없음 (CI step · 설정 파일 없음) |
| Python type checker | 없음 |
| secret scan | 없음 |
| Compose smoke · backup/restore smoke | CI 밖. `scripts/smoke_compose.py` · `scripts/smoke_backup_restore.py`를 로컬에서 실행 |
| deployment workflow | 준비 구현 있음 (`rt14-oidc` · `rt14-deploy`, `workflow_dispatch` 전용). 실행 Variable 미등록 · 실행 기록 없음 (RT-14) |
| 배포 도구 단위 테스트 | 있음 (`tests/deploy/`, `python-tests` regression) |
| 외부 AI 실제 호출 | CI 밖 (의도) |

따라서 현재 CI가 Ruff/type/secret scan/배포까지 수행한다고 쓰지 않는다.

### 목표 확장 순서

1. ~~Python 3.12 정합~~ — 완료
2. ~~`uv sync --locked`~~ — 완료
3. ~~boundary / contract fixture~~ — 완료
4. ~~repo-wide pytest~~ — 완료
5. Mock validator — 현재는 pytest 안에서 부분 충족. 별도 gate 필요 여부는 미정
6. ~~MySQL Runtime integration~~ — 완료
7. root Ruff
8. 선택한 repo-wide type checker
9. pre-deploy secret scan

7 ~ 9는 RT-15가 Runtime 소유 경로부터 건다([Implementation Plan](./runtime-implementation-plan.md) §6 RT-15).

외부 AI 실제 호출은 일반 PR CI의 deterministic gate에서 분리한다.

### Deployment workflow 분리 원칙

현재 `.github/workflows/boundary-check.yml`(모듈 경계·계약 검사) · `python-tests.yml`(pytest · MySQL · 배포 image acceptance) · `web-tests.yml`(web)은 일반 PR CI로 유지하고 AWS 인증 권한을 추가하지 않는다. `python-tests`가 배포 image를 build해 검증하더라도 AWS에 접근하지 않는다.

배포 workflow는 별도 파일로 두며 §2-1의 **OIDC + SSM** 기준을 따른다. 준비 구현은 이 원칙대로 인증 전용 `rt14-oidc.yml`과 배포용 `rt14-deploy.yml`을 나눴다. deploy role trust가 repository 전체를 허용하므로(§2-1) 배포 role을 얻는 ref 제한은 workflow 조건(repository · repository ID · `develop` ref · `RT14_EXECUTION_ENABLED`)이 맡는다. 배포 도구는 실행 시 `develop` tip의 push CI(`python-tests` · `boundary-check`) 최신 run 성공을 요구한다([RT-14 실행 절차](./rt14-deployment.md) §5). 실행 기록이 아직 없으므로 현재 CI가 배포까지 수행한다고 간주하지 않는다.

### Release 식별 · 배포 검증 · Rollback 원칙

배포 성공은 “원격 명령이 종료됨”이 아니라 **어떤 revision이 올라갔는지 식별 가능하고, 실제 서비스 경로가 검증됐으며, 실패 시 직전 정상 revision으로 복구 가능함**을 의미한다.

배포 흐름의 목표:

```text
CI quality gate
→ deployable revision 식별
→ AWS OIDC 인증
→ SSM 배포 명령
→ container/process 상태 확인
→ /health/live
→ /health/ready
→ 외부 endpoint smoke test
→ 성공 revision 기록
```

원칙:

- 모든 배포는 최소 commit SHA로 revision을 식별한다.
- Registry 기반 image 배포를 선택하면 `latest`만 의존하지 않고 immutable tag 또는 digest로 어떤 image가 배포됐는지 재현 가능하게 한다.
- 새 revision 배포 전 직전 known-good revision을 식별할 수 있어야 한다.
- container가 실행 중이라는 사실만으로 성공 처리하지 않고 health/readiness와 실제 외부 경로의 최소 smoke test를 통과해야 한다.
- 배포 검증 실패 시 원인 분석보다 서비스 복구가 우선인 상황에서는 직전 known-good revision으로 rollback하고 같은 health/smoke test를 다시 수행한다.
- DB migration처럼 코드 rollback만으로 되돌릴 수 없는 변경은 backward compatibility 또는 별도 rollback/restore 계획 없이 자동 rollback 대상으로 간주하지 않는다.
- exact 명령과 체크 순서는 [`deployment-runbook.md`](./deployment-runbook.md)에 유지한다.

Blue-Green/Canary 같은 다중 환경 배포는 현재 single EC2 baseline의 기본값이 아니다. 단순 rollback으로 감당할 수 없는 downtime/traffic 전환 요구가 실제로 생기면 검토한다.

## 20. Test / Validation 운영

테스트 층:

| 계층 | 목적 |
| --- | --- |
| Unit | pure/domain/runtime state logic |
| Contract / Boundary | Final Contract + import boundary |
| Integration | module public capability 접합 |
| Runtime Integration | FastAPI + MySQL Queue + Worker |
| Real E2E | 실제 media/provider 성능·비용 |

Real E2E는 비용·rate limit·외부 장애 때문에 일반 PR CI와 분리한다.

Runtime cross-cutting capacity 실험 역시 일반 PR gate로 두지 않는다. #95 P2는 baseline deployment에서 CPU/RAM/disk/queue/recovery를 관측하기 위한 계획이며, 완료 결과가 생기면 `experiments/`에 남긴 뒤 반복 가능한 운영 결론만 이 문서로 승격한다.

coverage는 미검증 경로를 찾는 보조지표로 사용하며 근거 없는 특정 percentage gate를 먼저 두지 않는다.

## 21. Pre-deploy Review

실제 사용자 데이터/외부 provider/배포 전에는 최소 다음을 재검토한다.

- logging에 민감 원문이 남는가
- secret이 repo/image/log에 노출되는가
- 외부 공개 endpoint에서 사용자 데이터/인증정보를 다룬다면 HTTPS가 적용됐는가
- provider upload/delete/expiry가 문서와 일치하는가
- cleanup/retention이 실제 adapter에 구현됐는가
- health/readiness가 deployment에서 동작하는가
- disk peak가 baseline 환경을 넘지 않는가
- Runtime queue recovery가 실제 MySQL에서 검증됐는가
- UsageRecord와 실제 비용 발생이 정합하는가

상세 security checklist는 [`docs/management/pre-deploy-security-review.md`](../management/pre-deploy-security-review.md)를 따른다.

## 22. Non-goals

현재 baseline에서 일부러 만들지 않는다.

```text
Redis / Celery / RabbitMQ / SQS / Kafka
Kubernetes / Service Mesh / Event Bus
Microservices
Auto Scaling
별도 DLQ infrastructure
WebSocket/SSE progress
복잡한 Circuit Breaker
Prometheus/Grafana/OpenTelemetry full stack
```

영구 금지가 아니라 현재 증거가 없는 복잡도다.

## 23. Open Ops Decisions

- [x] local Dockerfile / Compose exact service command — RT-13(a), §4
- [ ] production restart policy — RD-13c
- [x] local MySQL volume · logical backup/restore 도구 — RT-13(a) · RT-13(b)
- [ ] EC2 운영 backup 주기 · 보관 위치 · restore 절차(RD-12f · RD-12g) — deploy role은 `ec2:CreateVolume`이 거부돼 EBS snapshot에서 새 volume을 만드는 복원 경로가 막혀 있다([`aws-environment.md`](./official-inputs/aws-environment.md) §9)
- [ ] production log transport — RD-13a (CloudWatch Agent 미설치 · Log Group 없음. 준비 구현의 후보는 `awslogs` + dual local cache)
- [ ] log retention
- [ ] health alert/restart threshold — `/health/live` · `/health/ready` 구현은 완료, 운영 threshold는 RD-13c
- [ ] disk working-set guardrail
- [ ] Object Storage 사용 범위
- [ ] Managed asset retention
- [ ] UsageRecord retention
- [ ] provider RemoteCopy cleanup 운영
- [ ] P2 Runtime Capacity Smoke 수행 — #95 P0/P1 기반 concurrency=1 baseline, working set, cleanup, restart/reuse 관측
- [ ] capacity/scaling threshold — P2 결과 없이 숫자를 선결하지 않음
- [ ] P2 이후 필요 시 P3 30분~1시간 Runtime E2E 계획
- [ ] OIDC + SSM deployment workflow — 준비 구현은 `develop`에 있다(#479, §2-1). Gate 승인 · Variable/Secret 등록 · OIDC 실제 인증 · 첫 배포가 남았다(RT-14, [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450))
- [ ] 배포 artifact 전달 방식 — 준비 구현의 후보는 CI build → ECR immutable tag · digest(RD-12b OPEN)
- [x] build-time / runtime configuration 주입 방식과 변수 ownership — §4-1 · Tech Spec §15.2 (RD-07)
- [ ] immutable release 식별 + known-good revision 기록 + rollback exact command — 준비 구현의 후보 명령은 [RT-14 실행 절차](./rt14-deployment.md) §6 · §7. 승인(RD-12c · RD-12e)과 rehearsal이 남았다
- [ ] post-deploy health/readiness + external smoke test 연결 — Run Command `Success`만으로 성공 판정하지 않는다(§2-1). 준비 구현은 health · 8종 등록 · host 내부 read-only smoke까지이고, 외부 경로 smoke는 RD-14 뒤다
- [ ] public endpoint / domain / TLS — 외부 공개 demo 또는 OAuth 요구 발생 시 EIP 필요 여부 → DNS → HTTPS/reverse proxy → callback 구성, single-EC2 첫 구현 후보는 §2-2 기준으로 Caddy 검토
- [ ] secret scan gate

Recording/Search benchmark와 실제 Runtime implementation이 생기기 전까지 수치를 임의 확정하지 않는다.

## References

- [Architecture v4](../architecture/module-architecture.md)
- [Logical ERD](../architecture/erd-draft.md)
- [카테캠 지원 AWS 환경](./official-inputs/aws-environment.md) — 제공 조건 · 2026-10-02 / 10-30 실환경 snapshot
- [로컬 Runtime/Ops·Recording 실행환경](./local-runtime-environment.md)
- [RT-13(a) Docker / Compose](./rt13a-docker-compose.md) · [RT-13(b) backup / restore](./rt13b-backup-restore.md)
- [RT-14 실행 절차](./rt14-deployment.md) · [Deployment Runbook](./deployment-runbook.md)
- [CI test partitions](./ci-test-partitions.md)
- [ERD ↔ Runtime 정합화 ADR](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)
- [Runtime Tech Spec](./runtime-tech-spec.md)
- [AnalysisSource / Derived Asset Contract](../architecture/contracts/contract-analysis-source-derived.md)
- [UsageRecord Contract](../architecture/contracts/contract-usage-record.md)
- [Recording architecture input](../modules/recording/research/architecture-input-memo.md)
- [Search architecture input](../modules/search/research/architecture-input-memo.md)
- [Runtime experiments router](./experiments/README.md)
- [Elice Runtime Capacity Smoke Plan](./experiments/elice-runtime-capacity-smoke-plan.md)
- [Issue #95 — Elice ML API migration tracker](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95)
- [Issue #153 — provider usage · pricing · runtime config boundary review](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153)
- [Pre-deploy security review](../management/pre-deploy-security-review.md)
- Kakao Tech Campus AWS OIDC guide (2026-09-22 공지)
- Kakao Tech Campus 무료 도메인 발급 가이드 (2026-09-22 공지)
- Kakao Tech Campus 「에이전틱 서비스 배포 & CI/CD」 특강 (2026-09-23) — 소규모 팀의 운영 복잡도, observability, 반복 가능한 배포·복구 관점의 설계 입력
