# Runtime Ops Spec

**Status:** Working — operations spec  
**Owner:** common/runtime — 김준영  
**Deployment baseline:** EC2 1대 + Docker Compose + MySQL  
**AWS 환경 입력:** [`official-inputs/aws-environment.md`](./official-inputs/aws-environment.md) — 카테캠 제공 조건 · 2026-10-02 / 10-30 실환경 snapshot  
**Last synced:** 2026-10-30 — `develop` `f208d65f`(#479 · #478 포함)  
**Architecture SoT:** [`docs/architecture/module-architecture.md`](../architecture/module-architecture.md)  
**Logical Data Model:** [`docs/architecture/erd-draft.md`](../architecture/erd-draft.md)  
**Alignment ADR:** [ERD ↔ Runtime 정합화](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)

> 이 문서는 배포된 Runtime을 **어떻게 운영·관찰·복구·확장할지** 정한다. Final Contract와 Logical ERD가 정의한 논리 의미·관계를 바꾸지 않으며, JobExecution/UsageRecord persistence와 queue algorithm은 [`runtime-tech-spec.md`](./runtime-tech-spec.md)이 소유한다.

**2026-10-31 구현 갱신:** 승인값은 유지하며 [공개 배포·복구 Notes](rt14-public-deployment.md)에
rollback tip 독립·release-bound Web·pointer/state·Caddy/DDNS·외부 smoke와 현재 검증을 연결한다.
아래 2026-10-30 snapshot 표는 당시 이력이다. #483/#484/#488의 quality/import/secret gate는
현재 CI에 있으며 이번 변경에서 완화하지 않았다. 실제 AWS/public acceptance는 완료하지 않았다.

**2026-10-31 실행 갱신:** 첫 AWS 배포, 검증자 1명(`/32`)으로 제한한 public acceptance, 실영상 E2E 1회를
수행했다([실행 기록](experiments/2026-10-31-rt14-aws-real-e2e.md)). 같은 날 팀 계정에서 Elastic IP를
할당·연결할 수 있음을 확인해 공개 주소에 쓰기로 했고(§2-2, RD-14a), `AWS_ACCOUNT_ID`는 Secret으로
공급하도록 바꿨다(§2-1). 두 번째 deploy·rollback·restore rehearsal과 장기 공개 hardening은 남았다.

## 1. 문서 경계

### 이 문서가 소유한다

- 배포 topology
- 최종 제출 · 발표 기간의 운영 조건과 외부 체험 보호 요구
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
| RDS · ALB | 차단. 요청 시 검토 | capacity 자원이다. §18 조건이 생길 때만 요청한다 |
| Elastic IP | AWS 가이드는 「할당 불가 · 요청 시 검토」. **2026-10-31 팀 계정에서 할당 · 연결 가능 확인**(dry-run, 실제 1개 할당 · [`aws-environment.md`](./official-inputs/aws-environment.md) §11) | capacity 자원이 아니라 public endpoint **주소 안정성** 결정이다. RT-14 공개 주소에 1개를 쓴다(§2-2 · RD-14a) |
| S3 · ECR · CloudWatch · SSM Parameter Store | 사용 가능 | 10-30 SSO 권한으로 ECR · Log Group · SecureString 생성 → 삭제가 PASS. 사용 여부는 RD-12 · RD-13 결정이 정한다 |
| 서버 중지 · 시작 · 재부팅 · Security Group 편집 | 사용 가능 | 22번을 `0.0.0.0/0`으로 열면 보안 모니터링에 탐지된다 |

2026-10-30 host 상태: EC2는 10-02 이후 중지 상태였고, RT-14 스파이크를 위해 Docker Engine · Compose plugin을 설치했다(버전 · 설치 방식은 [`aws-environment.md`](./official-inputs/aws-environment.md) §10). 같은 날 다른 팀원도 이 instance를 쓰고 있었고, 마지막 관측 상태는 `running`이다(같은 문서 §10 「공유 EC2 사용 충돌」). 대신고 stack은 아직 배포되지 않았다. 같은 날 RT-14 준비 구현(#479)이 `develop`에 병합됐고, 그중 OIDC 인증과 ECR publish만 Actions에서 실제로 실행했다. EC2 쪽 배포는 실행하지 않았다(§2-1 「현재 구현 범위」).

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
- AWS 계정 ID는 repository **Secret `AWS_ACCOUNT_ID`** 로 공급한다(2026-10-31 변경, 이전: Variable). 계정 ID는 credential이 아니지만, 공개 repository에서 Variable은 step `env` 표시로 Actions log에 평문으로 남아 「계정 ID를 Actions log에 쓰지 않는다」([RT-14 실행 절차](./rt14-deployment.md) §2) 규칙과 충돌한다. Secret masking으로 이 규칙을 지킨다.
- AWS 인증이 필요한 job에만 `permissions: id-token: write`와 `contents: read`를 선언하고 `ap-northeast-2`의 배포 역할을 assume한다. 준비 구현은 credential action 대신 `deploy/aws.py`가 OIDC token → STS 교환을 직접 하고, 임시 자격증명을 `GITHUB_ENV` · output · artifact에 남기지 않는다([RT-14 실행 절차](./rt14-deployment.md) §5).
- 현재의 boundary/contract 등 **비-AWS CI에는 OIDC 권한을 추가하지 않는다.** 배포 workflow와 일반 PR CI를 분리한다.
- 배포 트리거는 `workflow_dispatch`다. 준비 구현의 두 workflow는 이 repository · repository ID · `develop` ref일 때만 job을 실행하고, 실제 원격 작업은 `RT14_EXECUTION_ENABLED` Variable이 `true`일 때만 돈다. fork PR에서는 OIDC token이 발급되지 않을 수 있으므로 `pull_request`를 실제 배포 경로로 사용하지 않는다.
- **production 승격 source는 `develop`이다.** `develop`에 포함되고 push CI를 통과한 revision만 배포할 수 있다. `develop` push 자체는 배포를 시작하지 않고, 사람이 `workflow_dispatch`로 승격한다. `main`은 멘토 리뷰 · 제출 snapshot 흐름이며 배포 source가 아니다. 준비 구현이 이 조건을 검사하는 정확한 방식은 [RT-14 배포 설계](./rt14-deployment-design.md) §4다.
- EC2 접속과 원격 명령 실행은 **SSM Session Manager / SSM Run Command**를 사용한다. GitHub Actions 배포를 위해 SSH private key를 저장하거나 보안그룹의 22번 포트를 인터넷에 개방하지 않는다.
- Object Storage를 도입해 S3 경유 배포를 선택하는 경우, GitHub Actions의 업로드 주체(`ktc-github-deploy`)와 EC2의 다운로드 주체(`ktc-ec2-ssm-role`)를 별도 권한 주체로 취급한다.
- 이 결정은 **S3 사용 자체를 확정하지 않는다.** Object Storage 범위는 §13의 실측 기반 결정 기준을 계속 따른다.

#### 실환경에서 확인된 제약 — 2026-10-02 · 10-30

관측 원문은 [`aws-environment.md`](./official-inputs/aws-environment.md) §8 · §9 · §10이다. 아래는 그 사실이 위 원칙에 주는 함의만 적는다. exact 배포 절차는 RD-12(RT-14, [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450))가 정한다.

- **OIDC provider와 `ktc-github-deploy`는 이미 provision돼 있다.** 별도 IAM 생성 없이 workflow 쪽만 필요하고, 그 준비 구현은 `develop`에 있다. 2026-10-30 GitHub OIDC → `ktc-github-deploy` 실제 인증을 확인했다(§2-1 「현재 구현 범위」).
- **deploy role trust의 `sub` 조건은 이 repository 전체(`:*`)다.** AWS가 branch · tag · PR · environment를 구분하지 않으므로, 어떤 ref가 배포 role을 얻을 수 있는지는 GitHub workflow의 trigger · 조건이 제한해야 한다. `pull_request`를 배포 경로로 쓰지 않는다는 위 원칙이 이 제한의 일부다.
- **SSM Run Command(`AWS-RunShellScript`)는 `/bin/sh`로 실행되고 마지막 명령의 exit code만 결과가 된다.** 중간 명령이 실패해도 `Success`가 될 수 있으므로, Run Command `Success`를 배포 성공으로 읽지 않는다. 배포 절차는 실패를 끝까지 전파해야 하고, 성공 판정은 §19의 health · smoke 검증이 한다.
- **IMDSv2 필수 + hop limit 1이다.** bridge network의 container는 EC2 instance role 자격증명에 닿지 않는다. Parameter Store 조회 같은 role 권한 작업은 host의 배포 script가 하고 container에는 결과 파일만 넘긴다(§4-1 경로와 같다).
- **두 role 모두 `PowerUserAccess`가 붙어 있지만 최종 권한 상한은 카테캠 SCP · guardrail이다.** 정책 이름으로 사용 가능 서비스를 추론하지 않고, role로 직접 하는 확인은 OIDC 검증 workflow와 첫 배포에서 한다.
- **EIP가 없으면 공인 IPv4는 EC2를 시작할 때마다 바뀐다.** 2026-10-31부터 공개 주소에 EIP를 연결했지만, 배포 · smoke는 여전히 고정 IP를 전제하지 않는다. public endpoint 조건은 §2-2.

#### 공유 EC2 전원 · host 변경 원칙

EC2 1대를 팀원 전체가 함께 쓴다([`aws-environment.md`](./official-inputs/aws-environment.md) §1). 2026-10-30 확인 자동화가 다른 팀원이 쓰던 instance를 두 번 중지했을 가능성이 있다(같은 문서 §10 「공유 EC2 사용 충돌」). 그래서 다음을 모든 자동화에 적용한다.

- **배포 · bootstrap · 스파이크 자동화는 EC2를 start · stop · reboot하지 않는다.** instance가 `running`이 아니면 자동화는 실패로 끝난다.
- **전원 변경은 사람이 한다.** 팀 공유 host의 사용 상황을 확인하고 알린 뒤에 한다.
- **「작업 전 전원 상태로 되돌리기」 자동화도 두지 않는다.** 시작과 종료 사이에 다른 사용자가 끼어들 수 있어서, 되돌리기가 남의 사용을 끊는다. 최종 전원 상태는 자동화가 소유하지 않는다.
- package 설치처럼 host 전체에 영향을 주는 변경도 같은 방식으로 사람이 알리고 한다. Docker daemon 설정 · 전역 prune 같은 세부 규칙은 [RT-14 배포 설계](./rt14-deployment-design.md) §7.3이다.

준비 구현(`deploy/aws.py`)은 EC2 전원 API를 호출하지 않는다. instance가 꺼져 있으면 SSM 명령이 전달되지 않아 실패로 끝난다.

#### 현재 구현 범위

2026-10-30 `develop` `7bab60bc` 기준, 이 절의 결정은 **준비 구현까지 반영**돼 있다(#479, [RT-14 실행 절차](./rt14-deployment.md) — IN_PROGRESS). RT-14 Decision Gate는 2026-10-30 [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450)에서 Runtime/Ops Owner가 승인했다. 승인값과 Gate 상태는 [RT-14 배포 설계](./rt14-deployment-design.md) §1이다.

`develop`에 있는 것 — #479 준비 구현이다. 이 중 OIDC 인증과 publish 경로는 2026-10-30 실제 Actions에서 확인했다. remote SSM deploy와 EC2 쪽 acceptance는 아직 실행하지 않았다:

- `.github/workflows/rt14-oidc.yml` — 인증 전용 수동 workflow. 기대 account · role만 비교하고 identity를 출력하지 않는다
- `.github/workflows/rt14-deploy.yml` — `publish` · `deploy` · `rollback`을 각각 별도 수동 실행. publish는 amd64 image build → media · OCR acceptance → ECR immutable tag push → digest 확인
- `deploy/aws.py`(OIDC · ECR · SSM 호출) · `deploy/ec2.py`(host controller) · `deploy/configure.py`(Parameter Store → 보호 파일) · `tests/deploy/`

AWS 실행 상태 — 2026-10-30, `develop` `7bab60bc`:

| 구분 | 항목 | 근거 |
| --- | --- | --- |
| 검증 완료 | GitHub OIDC → `ktc-github-deploy` 인증 | [`rt14-oidc` run](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/41027826938) success |
| 검증 완료 | deploy role의 ECR publish — build · media/OCR acceptance · 기존 repository `IMMUTABLE` 확인 · SHA tag push · digest 확인 | [`rt14-deployment` publish run](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/41030370406) success. `remote` job은 실행하지 않음 |
| 미검증 | EC2 instance role의 ECR pull | 첫 배포 |
| 미검증 | EC2 instance role의 Parameter Store 조회 · 복호화 | host 준비 · 첫 배포 |
| 미검증 | remote SSM deploy · rollback | 첫 배포 · rollback rehearsal |

위 publish image는 Gate 승인 전 `7bab60bc` 기준이라 release-bound Web artifact가 없다. 공개 배포에는 `NEEDS_CHANGE` 구현 변경 뒤 다시 publish한 image를 쓴다.

아직 하지 않은 것(AWS 설정 · 실행 기준):

- remote용 Secret · Variable 등록(publish에 쓰는 Variable과 `RT14_EXECUTION_ENABLED`는 위 실행 때 등록됨)
- host controller · 보호 디렉터리 준비
- deploy · rollback rehearsal
- Security Group / IAM / EC2 설정 변경
- Gate에서 `NEEDS_CHANGE`로 승인한 구현 변경(rollback tip gate · 외부 smoke · release-bound Web artifact 등, [RT-14 배포 설계](./rt14-deployment-design.md) §16)

남은 순서:

```text
1. ~~RT-14 Gate 승인(#450)~~ 2026-10-30 완료 · `NEEDS_CHANGE` 구현 변경 · remote용 Secret/Variable 등록
2. ~~rt14-oidc로 role 인증 확인~~ 2026-10-30 완료
3. host 준비(controller · 보호 디렉터리 · volume · config) — 별도 승인 작업
4. 구현 변경 뒤 publish → deploy → health · 8종 등록 · smoke 확인
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

- **Elastic IP는 필수 자원이 아니라 주소 안정성 결정이다.** CPU · RAM · DB 같은 capacity 자원(§18)과 다르다. AWS 가이드는 기본 차단 · 요청 대상이라고 안내하지만, 2026-10-31 팀 계정에서 할당 · 연결 권한을 확인했다([`aws-environment.md`](./official-inputs/aws-environment.md) §11). 공개 기간에는 팀원이 EC2를 다시 시작해도 주소 · DNS · 인증서가 그대로여야 하므로 RT-14는 EIP 1개를 공개 주소에 쓴다(RD-14a). EIP가 없으면 공인 IPv4는 시작할 때마다 바뀐다.
- 현재 Compose는 api를 `127.0.0.1:<port>`에만 publish한다. 2026-10-02 관측 시 Security Group inbound rule은 0개였다. 외부 공개는 이 두 경계를 함께 바꾸는 RD-14 결정이다.
- 무료 서브도메인 공급자(DuckDNS, is-a.dev 등)는 이 문서에서 하나로 고정하지 않는다. 필요한 DNS record, 발급 소요시간, 유지 정책을 그 시점에 확인해 선택한다. 공인 IPv4가 바뀔 수 있으므로 **record를 API로 갱신할 수 있는지**를 기준에 넣는다. RT-14는 DuckDNS를 쓰고, EIP를 연결한 뒤에도 API 갱신(updater)을 백업으로 둔다([RT-14 배포 설계](./rt14-deployment-design.md) §13.2).
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

**2026-10-30 갱신:** 최종 산출물 제출 요건(§2-3)으로 「외부 공개 demo URL 필요」 조건이 실제가 됐다. RD-14는 trigger 대기가 아니라 제출 마감(11/11) 전에 닫아야 하는 결정이다. 위 목록은 RD-14 구현 전까지 「아직 하지 않은 것」으로 남는다.

- 공개 모델은 [RT-14 배포 설계](./rt14-deployment-design.md) §13이다(2026-10-30 #450 Gate 승인). 로그인 · 회원가입 없는 공개 체험 서비스, Web + API same-origin, HTTPS, reverse proxy는 Caddy 1순위, Security Group은 public 80/443만 연다. Caddy는 app release와 분리된 host 인프라로 두고, Web 정적 산출물은 API와 같은 release revision에 묶는다(`Web revision == API revision`). 22 · 3306 · API 8000은 공개하지 않는다. 구현은 [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450)에서 이어진다.
- ~~EIP는 필수로 두지 않는다. 카테캠 도메인 가이드와 AWS 가이드의 안내가 달라 사용 가능 여부도 미확정이다.~~ **2026-10-31 갱신:** 팀 계정에서 할당 · 연결 권한을 확인했고(카테캠 도메인 가이드와 일치, [`aws-environment.md`](./official-inputs/aws-environment.md) §11) 공개 주소에 EIP를 쓴다(RD-14a).
- [RT-14 실행 절차](./rt14-deployment.md) §9의 준비 구현은 내부 loopback smoke만 제공한다. 공개 배포의 외부 smoke(DNS · TLS · Web · Web revision · same-origin API)는 RD-12h에 workflow의 SSM 성공 뒤 단계로 더한다.
- RT-14가 직접 닫는 것은 public endpoint · 공개 모델 · DNS/TLS/reverse proxy · Security Group · 외부 smoke까지다. abuse · privacy · capacity 보호는 §2-4의 경계를 따른다.

**2026-10-31 갱신:** 위 「하지 않는다」 목록 중 EIP 할당 · 연결, DNS record, Security Group 80/443, TLS 인증서, Caddy는 검증자 1명(`/32`)으로 제한한 public acceptance에서 수행했다([실행 기록](experiments/2026-10-31-rt14-aws-real-e2e.md)). OAuth는 로그인이 MVP 범위 밖이라 해당 없다. Caddy가 검증자 IP만 허용하는 동안 GitHub-hosted runner의 외부 smoke는 403을 받으므로, 외부 smoke는 검증자 PC에서 `deploy/public_smoke.py`로 실행했다. 공개 범위를 넓힐 때 workflow 외부 smoke 경로를 함께 정한다(§2-3).

### 2-3. 최종 제출 · 발표 기간 운영 조건

카테캠 「최종 산출물 제출 안내 & 심사 기준 공개」(2026-10-22 공지)가 배포 · 운영에 주는 요구다.

| 요구 | 운영 함의 | 2026-10-30 상태 |
| --- | --- | --- |
| 배포 서비스 URL — 접속해서 핵심 기능을 처음부터 끝까지 써 볼 수 있어야 한다 | 외부에서 닿는 endpoint(RD-14)와 실제 API · Worker · provider 경로, 심사자가 쓸 샘플 입력 | 외부 endpoint 없음. OIDC 인증 · publish만 실행했고 EC2 배포 전(§2-1) |
| 로그인이 필요하면 테스트 계정 · 샘플 데이터를 함께 적는다 | 현재 인증이 없고 `case_id`를 아는 것이 사실상 접근 조건이다([HTTP Contract](../architecture/contracts/contract-http-api.md) §3.6). 테스트 계정 대신 샘플 영상 · 사용 안내가 필요하다 | 샘플 입력 · 공개 범위 미정 |
| GitHub 저장소 — README(실행 · 배포 방법) · 테스트 코드 · CI/CD 설정 | README 배포 절은 실제로 실행한 배포 절차를 근거로 쓴다 | CI 있음(§19). 배포 workflow는 준비 구현이며 OIDC 인증 · publish만 실행 확인. README 배포 절 없음 |
| 멘토 심사 「배포 · 운영」 — URL 접속 · CI/CD · 환경 분리 | 환경 분리는 §4-1 「환경별 구분」으로 설명한다 | §4-1 |
| 제출 뒤 산출물 수정 불가 | 제출 시점 revision을 known-good으로 기록하고, 그 revision으로 발표까지 운영한다 | 제출 뒤 배포본 hotfix 허용 여부는 `확인 필요` |

운영 기간:

```text
2026-11-11(수) 17:00  제출 마감 — 이 시점 revision이 심사 대상
2026-11-16(월) 18:00  광주(전남대) 현장 발표회 — 시연 중 서비스 유지
2026-11-20            카테캠 AWS 제공 종료
```

원칙:

- **제출 · 심사 · 발표 기간 동안 URL이 실제로 쓸 수 있어야 한다.** 이것이 공지의 요구다. 공지에는 심사가 끝나는 시점이 없다(`확인 필요`).
- **팀 운영 목표는 같은 URL을 11/20까지 유지하는 것을 기본값으로 둔다.** 11/20은 공지 요구가 아니라 카테캠 AWS 제공 종료일이라는 외부 조건이다. EC2를 중지하면 공인 IPv4가 바뀌므로(§2-1) 주소를 유지하는 수단은 RD-14가 정한다(§2-2).
- **EC2는 팀원 공유다**([`aws-environment.md`](./official-inputs/aws-environment.md) §1). 제출 뒤에는 서비스 중인 instance의 중지 · 재시작 · host 전역 변경(package 설치 등)을 운영 창에서만 한다. 전원 자동화 금지는 §2-1 「공유 EC2 전원 · host 변경 원칙」이다.
- **공개 범위와 비용 상한은 RD-14(endpoint 구성)와 따로 정한다.** 인증 없이 업로드 · 분석이 가능하므로 공개 샘플 전용 / 제한 접근 / 실사용자 영상 허용 중 무엇인지와 provider 호출 상한을 공개 전에 정한다. 이 결정과 §2-4 보호는 공개 운영 hardening 후속 이슈에서 우선순위를 나누고, 공개 전에 §21 pre-deploy review를 실행한다. 카테캠 계정은 상업적 · 유료 서비스 운영이 금지다(같은 문서 §3).
- **외부 체험은 §2-4의 보호 범위 안에서만 받는다.**
- **제공 종료 전 데이터 처리.** 업로드 영상 · 파생물 · DB의 삭제 시점과 방법은 retention 미결(§14, #71)과 함께 정한다. 결정 전에는 「제공 종료와 함께 사라진다」고 가정하지 않는다.

### 2-4. 외부 체험 운영 보호 · 부하 시험

§2-3의 공개 URL은 팀 · 시연만 가정한 현재 용량 가정(Baseline B-P1 · B-W1 ~ B-W4)을 넘는 요청을 받을 수 있다. 목표는 처리량 보장이 아니라 **OOM · 데이터 손상 · 중복 비용 · 끝없는 대기 없이, 수락한 과업과 조회를 유지하고 초과 요청에는 빠른 안내를 주는 것**이다.

> **범위 경계.** 이 절은 공개 운영에 필요한 hardening backlog와 검증 기준을 정의한다. 모든 항목이 RT-14 배포 Gate의 선행 구현 조건은 아니다. RT-14를 막는 최소 조건과 공개 운영 전 추가 hardening은 별도 이슈에서 우선순위를 나눈다. RT-14가 직접 닫는 것은 public endpoint · 공개 모델 · DNS/TLS/reverse proxy · Security Group · 외부 smoke다(§2-2). global admission control · queue backlog guard · 동시 upload 제한 · asset streaming · rate limiting · provider 비용 상한 · 부하 시험 · privacy/retention hardening은 그 이슈에서 다룬다.

#### 요청 종류별 보호 경계

| 요청 | 현재 (`develop` `7bab60bc`) | 필요한 보호 |
| --- | --- | --- |
| 신규 분석 시작 | 서버 전체의 수락 상한이 없다. 실행은 Worker 1 · concurrency 1(B-W1 · B-W2)로 직렬화되므로 초과분은 queue에서 기다린다 | 수락 조건 · 전체 대기량 상한. 검사와 발주가 경쟁해 상한을 넘지 않게 서버에서 처리하고, 거절할 때 job · provider 비용이 생기지 않아야 한다 |
| 업로드 | 파일별 body 상한 · 수신 timeout(B-U1 ~ B-U4)은 있다. 동시 수신 수 · 전체 working set 상한은 없다 | 동시 수신 · 남은 disk 기준 거절. 받을 수 없는 파일을 끝까지 받은 뒤 거절하는 경로를 줄인다 |
| frame | API 동시 생성 2(B-F2), 초과 요청은 기다린다 | 현재 값 유지. 혼합 부하에서 대기 시간 관측 |
| asset 다운로드 | 응답이 파일 전체를 메모리로 읽는다(`src/daesingo/api/composition.py:175`). 동시 수 제한이 없다 | 동시 다운로드 수 제한 또는 streaming. 큰 파일 동시 다운로드의 RSS를 먼저 측정한다 |
| `GET /view` polling | 탭당 ≤ 0.5 rps · 동시 탭 ≤ 10 가정(B-P1) | 오류 시 backoff, 요청 유실 뒤 command 자동 재전송 금지 |
| provider 호출 | 자동 retry 상한은 있다. 사용자 반복(재탐색 · 다시 판독 · 다른 후보)에는 MVP에서 상한을 두지 않고 운영 관찰 뒤 다시 보기로 했다([#311](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/311) 결정 B). 서버 전체 · 일일 호출 상한도 없다 | 공개 URL은 #311의 재검토 조건이다. 서버 전체 신규 분석 상한(첫 행)으로 먼저 막고, 반복 상한이 필요한지는 UsageRecord · 반복 횟수로 판단한다. 금액을 믿을 수 없으면 횟수 상한부터 둔다 |

원칙:

- **초과 요청은 일찍 거절한다.** 과부하에서 일부 요청을 의도적으로 거절해 수락한 요청의 지연을 낮게 유지하는 load shedding 접근을 따른다([AWS Builders' Library](https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload)).
- **전역 connection 한도 하나로 끝내지 않는다.** Uvicorn `--limit-concurrency`는 한도를 넘는 새 요청에 바로 `503`을 주고 idle keep-alive 연결도 한도에 센다([Uvicorn 문서](https://uvicorn.dev/server-behavior/)). 요청 종류를 구분하지 못해 조회 · health까지 막을 수 있으므로 위 표처럼 종류별 경계를 둔다.
- **queue 대기가 Case 대기 예산을 넘으면 수락하지 않는다.** Case는 탐색 job을 `requested_at + 실행 예산 + 30초`까지만 기다린다([case 대기 timeout](../modules/case/decisions/case-wait-timeout.md)). queue가 길어지면 실행이 성공하기 전에 Case가 기다리기를 멈춘다. timeout을 늘려 숨기지 않는다.
- **IP 단위 제한만으로 공정성 · 비용 상한을 삼지 않는다.** 같은 네트워크의 여러 사용자가 한 공인 IP를 쓸 수 있다. 서버 전체 상한을 우선하고, 인증 없는 case 생성으로 반복 상한을 우회할 수 있는지 함께 본다.
- **Worker 증설로 해결하지 않는다.** §17 조건이 그대로다.
- **운영 통제 절차가 필요하다.** 신규 분석만 일시 중단하고 기존 결과 조회 · 다운로드는 유지하는 방법을 공개 전에 정한다.
- 새 HTTP status · 오류 코드 · 사용자 안내가 필요하면 HTTP Contract Owner와 Consumer(case · web)가 함께 정한다. 이 문서는 운영 요구만 정한다.

#### 부하 시험

[P2 Runtime Capacity Smoke](./experiments/elice-runtime-capacity-smoke-plan.md)(concurrency=1 baseline)를 먼저 하고, 그 위에 외부 체험 시나리오를 얹는다. 배포된 EC2에서 한다.

| 시나리오 | 확인할 것 |
| --- | --- |
| 단일 실제 과업 cold · warm | E2E 시간 · CPU/RSS · disk · provider 호출 · 결과 |
| 정상 혼합 — 조회 여러 탭 + 실제 분석 1 + 허용 업로드 | UI · health 응답, heartbeat lag · false STALE · DB pool · 조회 지연 |
| 몰림 — 조회 다수 + 분석 시작 시도 다수 | 수락 수가 상한을 지키고 초과는 빠르게 안내, 수락한 과업은 정상 종료, 부하 뒤 회복 |
| 큰 · 느린 입력 — 상한 근처 파일 · 느린 업로드 · 중도 끊김 | 거절 응답 · 자원 회수 · staging/temp 정리 · disk 고갈 방지 |
| 다운로드 경쟁 — 큰 asset 동시 · 느린 소비 · 끊김 | RSS peak · 연결 · DB 회수 · 진행 중 분석 영향 |
| 장애 · 재개 — Worker kill · provider 지연/429/실패 · 일시 DB 장애 | retry 상한 · 중복 정산 방지 · 사용자 출구 · 이후 정상 과업 복귀 |
| 짧은 지속 시험 — 혼합 부하 수십 분 | 자원 · 잔여 파일 누적 여부 · CPU credit 추세. 장기 무장애 보장이 아니다 |

수집값: 수락 · 거부 · 실패 수, 완료 과업 수, queue wait, UI · health 지연, CPU · RSS · host memory · disk, CPU credit, provider 호출 · UsageRecord, false STALE, cleanup 뒤 잔여. **예상한 거절과 예기치 않은 5xx를 나눠 센다.**

규율:

- 체험 규모 가정 · 운영 상한 · 통과 기준은 실측 뒤 정하고 **시험 전에 고정한다.** 실패 뒤 기준을 느슨하게 바꿔 통과로 만들지 않는다.
- 조회 · 거절 폭주는 fake provider와 통제된 미디어로 시작하고, 실제 provider 혼합은 소수로 확인한다. fake 결과로 provider quota · 실제 비용 · 실제 영상의 peak RAM을 주장하지 않는다.
- 표본이 작은 실제 영상 결과는 개별값 · 범위로 쓰고 p95를 대표 성능처럼 쓰지 않는다.
- **CPU credit.** EC2는 `unlimited` 모드다(§2). 24시간 평균 CPU가 baseline을 넘으면 초과분이 vCPU-hour당 추가 요금으로 청구된다([AWS 문서](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode-concepts.html)). 시험 중 `CPUSurplusCreditBalance` · `CPUSurplusCreditsCharged`를 함께 기록한다.
- RAM · disk · process RSS는 EC2 기본 metric에 없다(§8). OS · container 계측으로 남긴다. 이 시험을 위해 monitoring stack을 새로 설치하지 않는다(§22).
- **공유 host.** 부하 · 장애 주입은 다른 팀원의 사용 시간과 조율한 뒤에만 한다.
- 결과는 `experiments/`에 남기고, 반복 가능한 운영 결론만 이 문서와 Baseline으로 승격한다(§20).

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
- EC2 배포 준비 구현 — OIDC 인증 · ECR publish · SSM host controller · rollback 도구와 Worker 8종 등록 marker (RT-14 #479, §2-1). OIDC 인증 · ECR publish만 실제 실행했고 EC2 배포는 실행하지 않았다
- CI: MySQL gate · 배포 image media/OCR acceptance · boundary/contract · web (§19)

### 아직 없는 것

- EC2 실제 배포 — 승인한 구현 변경 · AWS 입력 등록 · 첫 publish/deploy · rollback rehearsal(RT-14, RD-12b ~ f. Gate는 2026-10-30 승인)
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

#### 환경별 구분

같은 Dockerfile · 같은 앱 설정 key를 쓰고, 환경마다 image 출처 · DB · 설정 파일 공급 · AWS 권한이 다르다. 이 표는 기존 결정을 한곳에서 보이게 한 것이며 새 결정이 아니다. 앱 설정 key 원문은 [로컬 Runtime 실행환경](./local-runtime-environment.md)이다.

| 구분 | local | CI | production(EC2) |
| --- | --- | --- | --- |
| image | 로컬 build(`compose.yaml`) | `python-tests`가 배포 image를 build해 media · OCR acceptance. push하지 않음 | `rt14-deploy` publish가 build · acceptance한 image를 ECR digest로 pull. EC2에서 build하지 않음(RD-12b 승인, acceptance 전) |
| DB | Compose `mysql` named volume | MySQL 8.4 service container · test 전용 DB | 소유 label을 확인한 external volume. 도구가 생성 · 삭제하지 않음 |
| 앱 설정 · secret | repo 밖 파일을 `DAESINGO_RUNTIME_ENV_FILE`로 지정 → `/run/secrets/runtime.env` read-only mount | 비밀값 없는 test 설정. 외부 AI 실제 호출 없음(§19) | Parameter Store SecureString → EC2 instance role → host 보호 파일(config ID별) → 같은 mount 경로(아래) |
| AWS 권한 | 개인 SSO(사람이 확인할 때만) | 없음 — 일반 CI에 OIDC 권한을 주지 않음 | Actions는 OIDC deploy role, host는 instance role. 장기 Access Key 없음(§2-1) |
| api 노출 | `127.0.0.1` | — | 준비 구현은 host loopback. 외부 공개는 RD-14 |
| revision | `local` | `local`(build arg를 넘기지 않음) | 40자 commit SHA · image digest · config ID로 기록(RD-12c 승인) |

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
- **배포 전 확인(차단 아님).** 카테캠 guardrail에서 EC2 instance role이 해당 경로에 `ssm:GetParametersByPath`(필요 시 `kms:Decrypt`)를 할 수 있는지 M6 전에 확인한다. 2026-10-30 SSO 권한으로 `SecureString`(기본 `aws/ssm` key) 생성 → `get-parameters-by-path --with-decryption` → 삭제가 PASS했고, EC2 instance role의 inline Deny에는 SSM이 없었다([`aws-environment.md`](./official-inputs/aws-environment.md) §10). SCP가 이 작업을 막지 않는다는 근거이며, **EC2 role로 직접 하는 조회는 첫 배포에서 확인한다.** 불가하면 Session Manager 등으로 host 파일을 수동 배치하고, container 쪽 계약은 그대로다.
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

2026-10-30 당시 관측 준비 상태:

- queue wait · oldest queued · execution duration · STALE · retry · cancel 지표는 RT-12(b)의 **DB 집계 query**와 structured log event catalog로 local · integration에서 볼 수 있다([`rt12b-observability.md`](./rt12b-observability.md)). 정기 기록 · 대시보드는 없다(RD-13b).
- 당시에는 배포된 stack이 없었다. 이후 실제 stack의 CloudWatch 상관 이벤트와 DB/자원 단회 표본은 [RT-14 Result §8](./experiments/2026-10-31-rt14-aws-real-e2e.md)에 있다. 전용 phase 계측·지속 관측·capacity 검증 완료를 뜻하지 않으며, 현재 가용 관측과 gap은 [P2 §7](./experiments/elice-runtime-capacity-smoke-plan.md#7-관측-방법과-instrumentation-gaps)을 따른다.
- AWS 쪽 수집 경로: EC2 instance role에 `CloudWatchAgentServerPolicy`가 붙어 있고 Log Group 생성 · retention 설정이 SSO 권한으로 가능했다. 그러나 CloudWatch Agent는 설치돼 있지 않고 Log Group도 없다([`aws-environment.md`](./official-inputs/aws-environment.md) §8 · §10). 위 「structured stdout → AWS log collection」 경로의 transport 선택은 RD-13a다. RT-14 Gate는 Docker `awslogs` driver + dual local cache를 승인했고(2026-10-30) 준비 구현이 그대로 render한다 — 별도 Agent는 필요 없다. 이 EC2에서 Docker daemon이 instance role로 임시 group에 로그를 보내는 것은 2026-10-30 스파이크로 확인했고([RT-14 배포 설계](./rt14-deployment-design.md) §17), 운영 group · retention과 실제 stack 로그 수신 확인이 남는다([RT-14 실행 절차](./rt14-deployment.md) §1 · §8).
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

50GB local disk를 장시간 원본의 영구 저장소로 설계하지 않는다. root filesystem은 약 48G로 보이고 Docker 설치 전 사용량은 2.6G였다(2026-10-30, [`aws-environment.md`](./official-inputs/aws-environment.md) §10). 디스크 확장 · 추가 볼륨은 직접 할 수 없고 카테캠 요청 경로만 있다(§2). 공지는 디스크 부족의 가장 흔한 원인으로 Docker build cache 누적을 들었다(같은 문서 §7).

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

> **구현 경계 (2026-11-02 `develop` `15b8b6a1` 대조):** local Compose에서 api · worker는 `/media` volume을 공유한다 — `source`(durable 원본), `staging`(upload), `api-temp` · `worker-temp`(Recording temp). production은 [RT-14 controller](./rt14-public-deployment.md)가 소유 external volume을 연결한다. prepared AnalysisSource 등은 Recording MySQL `LONGBLOB`이므로 **DB volume working set**이다. 초기 profile/byte/길이 baseline v1은 이미 확정됐으며 원문은 [Recording limits](../modules/recording/analysis-source-limits.md)와 [설정 명세 §3](../management/environment-and-deployment-config.md#3-recording-초기-배포-baseline-v1)다. 운영 최적값·장시간 지원과 DB/Search/Case 결합 측정은 #452/P2에 남는다. Search 자체 tempfile은 별도 `/tmp`/container layer도 쓰므로 `/media/worker-temp`만 관찰하지 않는다. image/OCR cache·logs·DB/media·backup도 같은 disk 예산에 포함한다. current/previous known-good/candidate 보존 예산은 RT-14 절차를 따른다.

Issue #95 R3에서는 동일 AnalysisSource의 process-local reuse가 materialization 비용을 크게 줄일 가능성이 확인됐다. 그러나 현재 확인된 것은 **성능 최적화 후보**이지 durability guarantee가 아니다.

현재 Worker는 invocation별 새 RecordingService를 만들며 instance-local reuse와 durable BLOB 읽기는 다르다.
새 job의 local-source preparation이 자동 persistent cache hit가 되는 것은 아니다.
반복 job/실행 내 reuse·restart 뒤 ref 읽기/재준비·temp 회수와 durable DB 증가를 구분하는
측정은 [갱신한 P2-B/C/D](./experiments/elice-runtime-capacity-smoke-plan.md#8-실험-순서와-각-선행조건)를 따른다.

초기 4분/48 MiB 설정은 [Product Spec](../product/product-spec.md)의 장시간·다중 영상 후보 탐색 약속을
축소한 최종 제품 한도가 아니다. P2-0a의 현재 구성 안전 거부와 0b의 baseline 관측에 더해,
[P2-0c](./experiments/elice-runtime-capacity-smoke-plan.md#p2-0c--isolated-capacity-probe--최소-20분-logical-timeline-판단)는
최소 20분 logical timeline 가능성/최초 병목을 판단하도록 격리 target의 근거 있는 experimental override를 허용한다.
유한한 guard·자원/비용·config 복귀를 유지하며 운영 packet/limit 변경이나 자동 승격은 하지 않는다.
목표 미충족 시 bounded/chunked processing·storage·Search/Case 결합 설계를 다시 열 수 있으나 방식을 확정하지 않는다.
제품 지원 범위 변경의 최종 승인자는 PM이고, P3는 처리 방식 미정의 30~60분 logical timeline Real E2E다.

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

이 목록의 현재 잔여 범위는 [P2 정합성 감사](./reviews/runtime-p2-plan-audit-2026-11-02.md)와
[P2 §0](./experiments/elice-runtime-capacity-smoke-plan.md#0-감사-결과와-이미-있는-evidence)에서 구분한다.
RT-14의 작은 실영상 단회 자원 표본은 이미 있으나 대표 working set·구간 분해·동시 부하 검증은 아니다.
Coarse/Fine의 현재 기본은 Argon이며 inline 경로와 Intent Flash를 구분한다.

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

이 절은 capacity 자원(사양 · disk · DB · load balancing · GPU)의 요청 조건이다. Elastic IP는 capacity가 아니라 public endpoint 주소 안정성 결정이므로 §2-2 · RD-14가 정한다(아래 「Elastic IP」는 그 경계를 남긴 것이다). 아래 자원은 모두 카테캠 계정에서 직접 만들거나 바꿀 수 없고 운영진 요청 후 검토된다([`aws-environment.md`](./official-inputs/aws-environment.md) §2 · §4). 요청에는 팀 · 필요 항목 · 이유 · 예상 사용 기간이 들어가므로, 이 절의 조건을 뒷받침하는 관측값을 함께 남긴다. 지원 가능한 상한(최대 사양 · GPU · EBS 상한 · 예산)은 아직 확인되지 않았다(같은 문서 §8). 제공 기간은 2026-11-20까지다.

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

capacity 조건으로 다루지 않는다. public endpoint 주소 안정성 결정으로 RD-14a에서 다룬다(§2-2). 2026-10-31 팀 계정에 할당 권한이 있음을 확인했고, RT-14 공개 주소에 1개를 쓴다. capacity baseline 자원으로 선점하지 않는다.

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

배포 workflow는 별도 파일로 두며 §2-1의 **OIDC + SSM** 기준을 따른다. 준비 구현은 이 원칙대로 인증 전용 `rt14-oidc.yml`과 배포용 `rt14-deploy.yml`을 나눴다. deploy role trust가 repository 전체를 허용하므로(§2-1) 배포 role을 얻는 ref 제한은 workflow 조건(repository · repository ID · `develop` ref · `RT14_EXECUTION_ENABLED`)이 맡는다. publish/deploy는 실행 시 `develop` tip의 push CI(`python-tests` · `boundary-check`) 최신 run 성공을 요구한다([RT-14 실행 절차](./rt14-deployment.md) §5). rollback은 tip CI와 독립적으로 대상 ancestry/push CI/digest 및 host exact tuple/schema를 검사한다. 실제 공개 배포 acceptance와 일반 CI를 구분한다.

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
→ host 내부 smoke
→ host current 기록
→ 외부 endpoint smoke test
→ production 배포 성공
```

원칙:

- 모든 배포는 최소 commit SHA로 revision을 식별한다.
- Registry 기반 image 배포를 선택하면 `latest`만 의존하지 않고 immutable tag 또는 digest로 어떤 image가 배포됐는지 재현 가능하게 한다.
- 새 revision 배포 전 직전 known-good revision을 식별할 수 있어야 한다.
- container가 실행 중이라는 사실만으로 성공 처리하지 않고 health/readiness와 실제 외부 경로의 최소 smoke test를 통과해야 한다.
- **host 내부 배포 검증을 통과한 release만 host `current`로 승격한다.** 공개 production 배포 완료는 그 뒤 외부 smoke까지 통과해야 한다. 두 상태의 정의는 [RT-14 배포 설계](./rt14-deployment-design.md) §6이다.
- 외부 smoke 실패는 배포 실패로 기록하지만 자동 rollback이나 host `current` 자동 복원을 하지 않는다. operator가 원인을 보고 명시적 rollback을 판단한다. 준비 구현도 자동 rollback을 하지 않는다(RD-12e 추천은 같은 문서 §9).
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
- [x] production restart policy — RD-13c 승인(2026-10-30): api · worker · mysql `unless-stopped` · migrate `no`. restart rehearsal은 RT-14 acceptance
- [x] local MySQL volume · logical backup/restore 도구 — RT-13(a) · RT-13(b)
- [ ] EC2 운영 backup 주기 · 보관 위치 · restore 절차(RD-12f · RD-12g) — deploy role은 `ec2:CreateVolume`이 거부돼 EBS snapshot에서 새 volume을 만드는 복원 경로가 막혀 있다([`aws-environment.md`](./official-inputs/aws-environment.md) §10)
- [ ] production log transport — RD-13a 승인(2026-10-30): service별 `awslogs` + dual local cache. 운영 Log Group 생성 · 실제 수신 acceptance가 남았다
- [x] log retention(운영 log) — RD-11a 승인(2026-10-30): host dual cache 20m × 5 · CloudWatch 30일. 영상 · 파생물 · UsageRecord retention은 아래 별도 항목
- [ ] health alert/restart threshold — `/health/live` · `/health/ready` 구현은 완료. RD-13c alert는 공개 운영 hardening 후속으로 넘겼다(2026-10-30 Gate)
- [ ] disk working-set guardrail
- [ ] Object Storage 사용 범위
- [ ] Managed asset retention
- [ ] UsageRecord retention
- [ ] provider RemoteCopy cleanup 운영
- [ ] P2 Runtime Capacity Smoke 수행 — #95 P0/P1 기반 concurrency=1 baseline, working set, cleanup, restart/reuse 관측
- [ ] capacity/scaling threshold — P2 결과 없이 숫자를 선결하지 않음
- [ ] P2 이후 필요 시 P3 30분~1시간 Runtime E2E 계획
- [ ] OIDC + SSM deployment workflow — 준비 구현은 `develop`에 있다(#479, §2-1). Gate는 2026-10-30 승인. OIDC 실제 인증 · publish는 같은 날 확인. 승인한 구현 변경 · remote용 Secret/Variable 등록 · 첫 배포가 남았다(RT-14, [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450))
- [ ] 배포 artifact 전달 방식 — RD-12b 승인(2026-10-30): Actions build once → 같은 image acceptance → ECR immutable SHA tag · digest. deploy role ECR push는 2026-10-30 확인(§2-1). EC2 instance role pull acceptance가 남았다
- [x] build-time / runtime configuration 주입 방식과 변수 ownership — §4-1 · Tech Spec §15.2 (RD-07)
- [ ] immutable release 식별 + known-good revision 기록 + rollback exact command — RD-12c · RD-12e 승인(2026-10-30). 후보 명령은 [RT-14 실행 절차](./rt14-deployment.md) §6 · §7. rollback tip gate 변경 · 최초 배포 recovery runbook · rehearsal이 남았다
- [ ] post-deploy health/readiness + external smoke test 연결 — Run Command `Success`만으로 성공 판정하지 않는다(§2-1). 준비 구현은 health · 8종 등록 · host 내부 read-only smoke까지다. 공개 배포의 외부 smoke(DNS · HTTPS · Web → API) 추가가 남았다([RT-14 배포 설계](./rt14-deployment-design.md) §10). 2026-10-31: 외부 smoke는 [공개 배포 Notes](rt14-public-deployment.md)로 구현됐고 검증자 PC에서 PASS했다. Caddy `/32` 제한 중 workflow 단계 smoke는 runner에서 403이라 공개 범위 확대 때 함께 정한다(§2-2)
- [ ] public endpoint / domain / TLS(RD-14) — **최종 제출 요건으로 트리거됨(§2-3).** 공개 모델(same-origin · HTTPS · Caddy host 인프라 · release-bound Web artifact · SG 80/443만 · ~~DDNS 우선 · EIP 비필수~~ EIP + DuckDNS, updater는 백업)은 [RT-14 배포 설계](./rt14-deployment-design.md) §13, 2026-10-30 Gate 승인 · 2026-10-31 RD-14a 갱신. 2026-10-31 검증자 1명(`/32`) 제한 public acceptance PASS([실행 기록](experiments/2026-10-31-rt14-aws-real-e2e.md)). 공개 범위 확대가 남았다
- [ ] 공개 범위(공개 샘플 전용 / 제한 접근 / 실사용자 영상 허용)와 샘플 입력 · 사용 안내 — §2-3. RD-14와 분리해 공개 운영 hardening 후속 이슈에서 정한다
- [ ] 제출 뒤 배포본 hotfix 허용 여부 — 공지에 없음, 카테캠 확인 필요
- [ ] 외부 체험 보호 상한 — 신규 분석 수락 · 동시 업로드 · 다운로드 메모리 · 운영 통제(신규 분석 일시 중단) 절차(§2-4). RT-14 Gate가 아니라 공개 운영 hardening 후속 이슈 범위
- [ ] 외부 체험 부하 시험 실행과 결과 기록 — P2 다음 단계, 기준은 시험 전에 고정(§2-4). 공개 운영 hardening 후속 이슈 범위
- [ ] 제출 → 발표(11/16) → AWS 종료(11/20) 운영 유지와 종료 시 데이터 삭제 — §2-3 · §14
- [x] 공유 EC2 전원 자동화 금지 — §2-1 「공유 EC2 전원 · host 변경 원칙」(2026-10-30 공유 사용 충돌 근거)
- [ ] README 배포 절 · 환경 분리 서술 — 실제 배포 실행 뒤(§2-3 · §4-1)
- [ ] 공개 전 pre-deploy security review 실행 — §21
- [ ] secret scan gate

Recording/Search benchmark와 실제 Runtime implementation이 생기기 전까지 수치를 임의 확정하지 않는다.

## References

- [Architecture v4](../architecture/module-architecture.md)
- [Logical ERD](../architecture/erd-draft.md)
- [카테캠 지원 AWS 환경](./official-inputs/aws-environment.md) — 제공 조건 · 2026-10-02 / 10-30 실환경 snapshot
- [로컬 Runtime/Ops·Recording 실행환경](./local-runtime-environment.md)
- [RT-13(a) Docker / Compose](./rt13a-docker-compose.md) · [RT-13(b) backup / restore](./rt13b-backup-restore.md)
- [RT-14 실행 절차](./rt14-deployment.md) · [RT-14 배포 설계 — Decision Gate](./rt14-deployment-design.md) · [Deployment Runbook](./deployment-runbook.md)
- [CI test partitions](./ci-test-partitions.md)
- [ERD ↔ Runtime 정합화 ADR](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)
- [Runtime Tech Spec](./runtime-tech-spec.md)
- [AnalysisSource / Derived Asset Contract](../architecture/contracts/contract-analysis-source-derived.md)
- [UsageRecord Contract](../architecture/contracts/contract-usage-record.md)
- [Recording architecture input](../modules/recording/research/architecture-input-memo.md)
- [Search architecture input](../modules/search/research/architecture-input-memo.md)
- [Runtime experiments router](./experiments/README.md)
- [Runtime Capacity Smoke Plan — P2 (Elice ML API)](./experiments/elice-runtime-capacity-smoke-plan.md)
- [Issue #95 — Elice ML API migration tracker](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95)
- [Issue #153 — provider usage · pricing · runtime config boundary review](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153)
- [Pre-deploy security review](../management/pre-deploy-security-review.md)
- Kakao Tech Campus AWS OIDC guide (2026-09-22 공지)
- Kakao Tech Campus 무료 도메인 발급 가이드 (2026-09-22 공지)
- Kakao Tech Campus 최종 산출물 제출 안내 & 심사 기준 공개 (2026-10-22 공지)
- [Case 대기 timeout](../modules/case/decisions/case-wait-timeout.md)
- [Issue #311 — 비용이 드는 사용자 반복의 상한](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/311)
- [AWS Builders' Library — Using load shedding to avoid overload](https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload)
- [Uvicorn — Server Behavior (resource limits)](https://uvicorn.dev/server-behavior/)
- [AWS — Unlimited mode concepts for burstable instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode-concepts.html)
- Kakao Tech Campus 「에이전틱 서비스 배포 & CI/CD」 특강 (2026-09-23) — 소규모 팀의 운영 복잡도, observability, 반복 가능한 배포·복구 관점의 설계 입력
