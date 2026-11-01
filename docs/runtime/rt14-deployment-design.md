# RT-14 배포 설계 — Decision Gate

**Status:** Decision Gate Approved — Runtime/Ops Owner 승인본(2026-10-30, [#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450)) · implementation · AWS acceptance pending\
**Owner:** common/runtime — 김준영 · **Implementer:** 정철원\
**작성 기준:** 2026-10-30 · `develop` `7bab60bc`(RT-14 준비 구현 #479 병합) · [Ops Spec](./ops-spec.md)(PR #480) · [AWS 환경 §9 · §10](./official-inputs/aws-environment.md)(PR #478) · 카테캠 최종 산출물 제출 안내(2026-10-22)\
**Gate:** RD-12b · 12c · 12d · 12e · 12f · 12h · RD-13a · 13c · 13d · RD-11a · RD-07c · RD-14

> **이 문서의 Decision Gate 추천은 Runtime/Ops Owner 승인 기준으로 확정한다.** 설계 선택은 닫혔고, 남은 것은 #479 준비 구현의 변경(§16)과 실환경 acceptance다. **RT-14 완료를 뜻하지 않는다.** 이후 변경은 구현 · acceptance 과정에서 새 증거가 생긴 경우에만 reopening한다. 앞선 초안 비교 · 스파이크 근거 · Gate 상태 · blocker 목록은 근거 기록으로 남긴다.
>
> 이 문서는 Gate별 **상태, 승인값, 근거, 그 값을 고른 이유, 재검토 조건**을 한곳에 모은 설계 기록이다. 기준은 #479의 실제 구현이다. **구현이 있다는 사실은 AWS acceptance가 끝났다는 뜻이 아니다.** 승인된 값은 「한 결정은 한 곳」 원칙에 따라 Ops Spec · Runbook · Provisional Baseline으로 옮기고 Register 상태를 갱신한다. 그 뒤 이 문서는 근거 기록으로만 남는다. 정하지 않은 것은 §15에 미결로 남긴다.
>
> 같은 날 앞선 초안(`4876e646` 기준)은 #479 전의 가정을 썼다. Worker revision `unknown`, image 안의 `deploy.sh`, host `known-good.json`, 모든 배포의 queue drain, 조건부 자동 rollback, RD-14 비공개 기본값이 그것이다. 이 판은 그 가정을 실제 구현과 최종 제출 요구에 비춰 다시 판단했다. 바뀐 결정은 각 절의 「앞선 초안과 다른 점」에 남긴다.

## 0. 읽는 법

추천값에는 Provisional Baseline §0.1과 같은 Evidence 표시를 붙인다.

| 표시 | 뜻 |
| --- | --- |
| `MEASURED` | 대신고 실측(2026-10-30 AWS 확인 · 스파이크 · CI 실행 기록 등) |
| `DERIVED` | 이미 닫힌 결정 · 코드 사실에서 따라 나옴 |
| `EXTERNAL` | 공식 문서 · [Research 04](./research/04-deployment-observability-operations-2026-10-03.md) |
| `CONSERVATIVE_DEFAULT` | 직접 근거가 부족해 안전한 MVP 초기값으로 둠 |

Gate 상태는 네 가지 중 하나로 표시한다.

| 상태 | 뜻 |
| --- | --- |
| `ACCEPT` | Owner가 지금 채택해도 되는 값이다. 구현이 그 값과 맞고, 이 Gate만을 위한 AWS 증거가 따로 필요하지 않다. 첫 배포 acceptance에서 함께 확인한다 |
| `IMPLEMENTED_PENDING_ACCEPTANCE` | 값과 구현은 맞다. 이 Gate 고유의 AWS · 운영 증거(권한 · 수신 · rehearsal)가 있어야 닫힌다 |
| `NEEDS_CHANGE` | **Owner가 방향은 승인했지만** #479 준비 구현이나 문서에 추가 변경이 필요하다. Decision이 미정이라는 뜻이 아니다 |
| `DEFER_TO_FOLLOWUP` | RT-14가 아니라 공개 운영 hardening 후속 범위다 |

`ACCEPT`도 승인 기록은 필요하다. host controller는 `policy.json`의 `decision_refs` 11칸(RD-12b ~ f · h, RD-13a · c · d, RD-11a, RD-07c)이 비어 있거나 `pending`을 담고 있으면 실행을 거부한다(`deploy/ec2.py` `validate_policy`). **Gate 승인은 곧 그 칸에 넣을 근거 링크다.** RD-14는 이 목록에 없다.

## 1. 요약 — Gate 상태

| Gate | 상태 | 승인값 | 남은 것 |
| --- | --- | --- | --- |
| RD-12b artifact | `IMPLEMENTED_PENDING_ACCEPTANCE` | Actions에서 amd64 image를 **한 번만 build** → 같은 image로 media · OCR acceptance → 기존 `IMMUTABLE` ECR에 commit SHA tag로 push → digest로 배포. EC2에서 build하지 않음 | ECR repository 준비 · deploy role push · EC2 role pull 실측 |
| RD-12c revision | `ACCEPT` | 40자 SHA tag + digest 참조 + host의 `current.json` · `previous.json`(image · revision · config ID 정확한 tuple) + schema authority `schema.json` + release 승인파일 | 첫 배포에서 digest · revision 대조 |
| RD-12d SSM 명령 | `IMPLEMENTED_PENDING_ACCEPTANCE` | `develop`에서 `workflow_dispatch`로 승격(§4) · Run Command에는 고정 controller `exec` 한 줄 · `Success` + exit 0만 성공 · bounded polling · 자동화는 EC2 전원을 다루지 않음 | OIDC 실제 인증 · SSM 실행. 실패 단계 출력(§16 권장) |
| RD-12f migration · maintenance | `IMPLEMENTED_PENDING_ACCEPTANCE` | **ingress 정지 + Worker graceful stop(§8 B안)**. full drain 없음. migration은 writer 정지 뒤 단 한 번, forward-only | EC2 MySQL 첫 migrate · 배포 경로에서 STALE 회복 확인 · full drain이 필요한 release 판단 기준을 승인 checklist에 넣기 |
| RD-12e rollback | `NEEDS_CHANGE` | **자동 rollback 없음 · operator가 명시적으로 rollback**(현재 구현 그대로) | rollback workflow의 develop tip CI 의존 제거(코드) · 최초 배포 실패 recovery runbook · 두 번째 정상 release 뒤 rollback rehearsal(§9.3) |
| RD-12h 배포 후 검증 | `NEEDS_CHANGE` | host 내부 6단계(구현됨) → host `current` 갱신 → SSM 성공 뒤 **workflow 단계의 외부 DNS · TLS · Web · Web revision marker · same-origin API smoke**(없음) | workflow post-SSM 외부 smoke와 재실행 경로 추가(§10.2) |
| RD-13a log transport | `IMPLEMENTED_PENDING_ACCEPTANCE` | service별 `awslogs`(non-blocking) + dual local cache 20m × 5. host 기본 log driver는 바꾸지 않음 | 운영 Log Group 생성 · buffer bytes 승인 · 실제 stack 로그 수신 |
| RD-11a log 보관 | `ACCEPT` | host: dual cache 20m × 5(B-O1과 같은 숫자) · CloudWatch: 30일 | group을 만들 때 retention 설정(RD-13a acceptance에 포함) |
| RD-13c restart | `ACCEPT` | api · worker · mysql `unless-stopped` · migrate `no`(구현 고정) · `docker.service` enable | restart rehearsal은 #450 acceptance |
| RD-13c alert | `DEFER_TO_FOLLOWUP` | RT-14 blocker로 두지 않는다. 공개 기간 최소 감시는 후속 이슈 P1 | — |
| RD-13d Worker 노출 | `ACCEPT` | 실제 Worker process의 8종 등록 marker + container 상태 + `awslogs` + Runtime DB 집계 query. 새 HTTP · idle heartbeat table 없음 | queue 상태 운영 조회 명령은 후속 이슈 P1 |
| RD-07c secret | `IMPLEMENTED_PENDING_ACCEPTANCE` | prefix 아래 SecureString 정확히 3개 → 운영자가 host에서 `configure.py` 실행(instance role) → config ID별 보호 파일 | EC2 role의 조회 · 복호화 실측 · `runtime-env` 값 크기 확인 |
| RD-14 public endpoint | `NEEDS_CHANGE` | 공개 체험 서비스 · same-origin · HTTPS · **Caddy는 app release와 분리된 host 인프라** · **Web 정적 산출물은 API와 같은 release에 묶음**(`Web revision == API revision`) · Web current pointer는 host 내부 검증 PASS 뒤 전환 · Security Group 80/443만 · ~~DDNS(DuckDNS 우선) · EIP 필수 아님~~ **EIP + DuckDNS, updater는 백업**(2026-10-31 RD-14a 갱신, §13.2) | Caddy 설치 · 운영, release-bound Web artifact와 revision marker · pointer 승격 · reconciliation(코드), DDNS · TLS · SG(§13.4) |

RD-13c는 restart와 alert의 상태가 달라 두 줄로 나눴다. RD-14 안의 항목별 상태는 §13.4다. OIDC trust `:*`는 Gate가 아니라 infra risk로 §4 · §16.2에서 다룬다.

## 2. 이미 닫혀 있어 다시 정하지 않는 것

| 닫힌 것 | SoT |
| --- | --- |
| EC2 1대 + Compose(api · worker · mysql) · RDS · ALB · 추가 EC2 미가정 | Ops §2 |
| Elastic IP는 capacity 자원이 아니라 주소 안정성 결정이고 필수가 아니다 | Ops §2 · §2-2 · §18 |
| GitHub OIDC → `ktc-github-deploy` · SSM Session Manager / Run Command · SSH key · 22번 포트 없음 · `AWS_ACCOUNT_ID`는 Secret(2026-10-31 Variable에서 변경) | Ops §2-1 |
| production 승격 source는 `develop`이고 `workflow_dispatch`로만 배포한다 | Ops §2-1 |
| 자동화는 공유 EC2를 start · stop · reboot하지 않고 전원을 되돌리지도 않는다 | Ops §2-1 「공유 EC2 전원 · host 변경 원칙」 |
| secret은 Parameter Store → EC2 role로 fetch → host 보호 파일 → `DAESINGO_ENV_FILE` · Actions는 secret을 다루지 않음 | Ops §4-1 (RD-07) |
| 배포 성공 = revision 식별 + health/readiness + smoke + 직전 known-good 식별 · `latest`에 의존하지 않음 · host 내부 검증을 통과한 release만 host `current`로 승격 · 공개 production 배포 완료는 외부 smoke까지 통과 · migration은 자동 rollback 대상이 아님 | Ops §19 · Runbook §1 · §5 |
| api · worker · migrate는 같은 image, command만 다름 · migration은 one-shot · app startup migration 금지 | RD-12a(M4) · Tech Spec §4.4 |
| MySQL logical backup/restore 도구 | RT-13(b) `scripts/backup_compose.py` |
| container local log 상한 20m × 5 | Baseline B-O1 |
| ready는 Worker · provider · queue를 보지 않음 | HTTP API Contract §5.7 · Tech Spec §14 |
| lease 60 s · STALE = lease 만료 · sweep 15 s · startup sweep · Worker stop grace 30 s | Baseline B-L2 ~ B-L5 · B-W5 |

## 3. 설계에 쓴 사실

### 3.1 AWS — 2026-10-30

원문은 [AWS 환경 §9 · §10](./official-inputs/aws-environment.md)이다. 설계에 쓰는 것만 옮긴다.

- EC2는 10-02 이후 중지 상태였다. disk는 48G 중 2.6G 사용, 메모리 3,832 MiB, swap 0, CPU credit `unlimited`, Elastic IP 없음(시작할 때마다 public IP가 바뀜).
- 같은 날 스파이크를 위해 **Docker Engine 29.9.2 · Compose plugin v5.6.1을 설치했다**(부록 A). 그 밖의 host 설정(`daemon.json` · Log Group · `/opt/daesingo`)은 하지 않았다. **마지막 관측 상태는 `running`이다**(§3.4).
- IMDSv2 필수 · hop limit 1. bridge network의 container는 instance role 자격증명에 닿지 않는다.
- EC2 role과 deploy role 모두 `PowerUserAccess`다(IAM 정책 조회).
- **SSO principal로** ECR · CloudWatch Logs · SecureString의 생성 → 사용 → 삭제가 모두 PASS였다. SCP가 이 작업들을 막지 않는다는 근거다. **deploy role의 ECR push, EC2 role의 ECR pull · Parameter Store 복호화는 해 보지 않았다.** EC2 role의 CloudWatch Logs 전송만 SP-2에서 실측했다(§17).
- deploy role은 `ec2:CreateVolume`이 거부된다. EBS snapshot에서 복원하는 경로는 쓸 수 없다.
- OIDC trust `sub` 조건은 이 repository 전체(`:*`)다. AWS 쪽에서 branch · PR을 구분하지 않는다.
- Run Command(`AWS-RunShellScript`)는 `/bin/sh`로 실행되고 **마지막 명령의 exit code만 결과**가 된다.
- EIP는 카테캠 도메인 가이드와 AWS 가이드의 안내가 다르다. 실제 사용 가능 여부는 미확정이다(§9). → 2026-10-31 할당 · 연결 권한 확인(AWS 환경 §11, §13.2)

### 3.2 #479 준비 구현 — `develop` `7bab60bc`

이 설계 작성 시점에는 AWS에서 실행한 적 없는 준비 구현이었다. 이후 2026-10-30 OIDC 인증과 publish(deploy role ECR push)는 실제 Actions에서 성공했고, remote SSM deploy와 EC2 쪽 acceptance는 아직 실행하지 않았다. 현재 실행 상태는 [Ops Spec](./ops-spec.md) §2-1 「현재 구현 범위」다. 실행 절차 원문은 [RT-14 실행 절차](./rt14-deployment.md)다.

| 사실 | 위치 | 설계 영향 |
| --- | --- | --- |
| 수동 workflow 두 개. 둘 다 `workflow_dispatch` · repository와 repository ID · `refs/heads/develop`일 때만 job이 돈다. 배포 workflow는 Variable `RT14_EXECUTION_ENABLED == 'true'`도 요구한다 | `.github/workflows/rt14-oidc.yml` · `rt14-deploy.yml` | §4 · RD-12d |
| OIDC token → STS 교환을 credential action 없이 직접 한다. 임시 자격증명을 `GITHUB_ENV` · output · artifact에 남기지 않고, 기대 account와 `ktc-github-deploy` assumed-role만 비교한다 | `deploy/aws.py` `oidc` · `verify_identity` | RD-12d |
| publish: `--platform linux/amd64` build(`REVISION=$GITHUB_SHA`) → 같은 image로 media-preflight · readout-preflight · media acceptance(`--network none`) → 기존 repository가 `IMMUTABLE`인지 확인 → SHA tag push → `describe-images`로 digest 확인 | `rt14-deploy.yml` publish · `aws.py` `publish` | RD-12b |
| deploy · rollback: quality gate(§4) → ECR tag와 digest 대조 → `AWS-RunShellScript`에 `exec /usr/bin/python3 /opt/daesingo/controller/ec2.py <operation> --image … --revision … --config-id …` **한 줄**. delivery 60 s · 실행 1,200 s · runner 대기 1,500 s. `Success` **그리고** 정수 exit 0만 성공. stdout/stderr는 runner로 가져오지 않고, Run Command의 CloudWatch 출력도 끈다 | `aws.py` `remote` · `ssm_payload` · `wait_command` | RD-12d |
| host controller는 image가 아니라 검토 뒤 root 소유로 설치한 `/opt/daesingo/controller/`에 있다. 배포 도중 자동 교체하지 않는다. image에는 `compose.yaml`만 들어 있고, controller가 그것을 꺼내 운영 값으로 render한다 | `deploy/ec2.py` `preflight` · `production_compose` · `Dockerfile` | 앞선 초안의 「image 안 `deploy.sh`」 폐기 |
| controller 상태 파일: `operation.lock`(mkdir) · `dirty.json`(phase journal) · `schema.json`(schema authority) · `current.json` · `previous.json`(root 0600) · `approvals/<revision>.json` · `policy.json`(root 0400) | `ec2.py` `transition` · `main` | RD-12c · 12e |
| deploy 순서: preflight → quiesce(`compose stop api worker migrate`) → mysql up → packet 확인 → migrate 1회 → api · worker `--force-recreate` → health → smoke → 승격 | `ec2.py` `transition` · `DockerHost` | RD-12f · 12h |
| **queue drain이 없다.** Worker는 SIGTERM 뒤 새 claim을 멈추고, 실행 중 handler는 다음 idle 지점까지 계속된다. grace는 30 s다 | `ec2.py` quiesce · `worker/__main__.py` `request_stop` · `compose.yaml` worker `stop_grace_period` · B-W5 | RD-12f |
| **자동 rollback이 없다.** 검증이 실패하면 `current.json`을 바꾸지 않고 `dirty.json`이 남는다. 다음 deploy는 `dirty.json`이 없어야 하므로, rollback이 성공하거나 운영자가 상태를 대조하기 전까지 막힌다 | `ec2.py` `transition` | RD-12e |
| deploy 승인파일은 `current` revision을 새 release의 `rollback_targets`에 담아야 한다. 즉 새 schema가 지금 코드와 호환된다는 승인이 배포 조건이다. rollback은 `schema.json`의 `rollback_targets`만 허용하고 migration을 돌리지 않는다. 승인파일에는 `backup_reference`도 필수다 | `ec2.py` `transition` · `main` | RD-12e · 12f |
| 최초 배포는 `initial_state=verified-empty-owned-volumes`와 실제로 빈 소유 volume을 요구한다. `current.json`이 없으면 같은 project의 기존 container도 거부한다 | `ec2.py` `preflight` · `validate_existing_project` | §9.3 최초 배포 실패 |
| 검증: api · worker · mysql 각 1개가 running · Restarting/OOM 아님 · RestartCount 0 · app image ID와 `DAESINGO_REVISION` 일치 · api와 mysql healthy → api `ready` → worker `worker-status`(PID 1 · starttime · revision · 8종). 120 s 안에서 재시도한다 → `deploy-smoke`(live · ready `{"status":"ok"}` · 무작위 case view 404) | `ec2.py` health · smoke · `docker/runtime.py` · `worker/deployment_status.py` | RD-12h · 13d |
| Worker revision은 image ENV `DAESINGO_REVISION`(build arg)에서 온다. 앞선 초안의 `unknown` 문제는 없다 | `Dockerfile` · `worker/__main__.py` | RD-12c |
| render 결과: build · `depends_on` 제거 · restart = policy 값(migrate는 `no`) · `awslogs`(create-group 끔 · non-blocking · buffer = policy 값 · cache 20m × 5) · api `127.0.0.1:8000:8000` · external volume 두 개. service 집합은 **정확히** api · worker · migrate · mysql이어야 한다 | `production_compose` | RD-13a · 13c · 14 |
| policy 필수값에 기본값이 없다: repository · project · volume 두 개 · `mysql@sha256` · `mysql_uid` · `parameter_path` · `restart_policy` · `log_group` · `log_retention_days` · `log_buffer_bytes` · `disk_reserve_bytes` · `memory_reserve_bytes` · `packet_margin_bytes` · `decision_refs` | `validate_policy` · `deploy/policy.example.json` | §15 |
| preflight는 Log Group이 있고 retention이 policy와 같은지만 확인한다. group을 만들지 않는다 | `preflight` | RD-13a · 11a |
| config는 배포와 별개다. 운영자가 SSM에서 `configure.py`를 실행해 prefix 아래 SecureString 정확히 3개(`runtime-env` · `mysql-password` · `mysql-root-password`)를 새 config ID로 게시한다 | `deploy/configure.py` | RD-07c |
| controller는 child 출력을 공개하지 않고, 실패하면 고정 문구 한 줄만 낸다. `aws.py`도 내부 실패 코드(`quality_gate_pending` 등)를 출력하지 않고 `rt14: operation_failed_or_unknown` 한 줄만 남긴다 | `ec2.py` `run` · `main` · `aws.py` `main` | §7.2 · §16 |
| EC2 전원 API를 부르지 않는다 | `aws.py` | §7.3 |

### 3.3 최종 제출 요구와 일정

- 카테캠 「최종 산출물 제출 안내 & 심사 기준 공개」(2026-10-22)는 **접속해서 핵심 기능을 처음부터 끝까지 써 볼 수 있는 배포 서비스 URL**을 요구한다(Ops §2-3).
- 11/11 17:00 제출 마감 → 11/16 광주 발표회 → 11/20 카테캠 AWS 제공 종료다. 공개 운영 기간은 1주가 넘는다.
- 공지 요구는 제출 · 심사 · 발표 기간에 URL을 쓸 수 있는 것이다. 11/20까지 같은 URL을 유지하는 것은 팀 운영 목표의 기본값이다(Ops §2-3).
- 그래서 앞선 초안의 「기본 비공개 · SSM port forwarding · public trigger는 PM 질문」은 폐기한다. trigger는 이미 발생했다(§13).

### 3.4 공유 host 사용 충돌 — 2026-10-30

EC2는 팀 공용이다. 확인 자동화가 EC2를 시작하고 끝날 때 중지했는데, 같은 시간대에 다른 팀 principal도 이 instance를 쓰고 있었다. **다른 팀원이 쓰던 instance를 자동화가 두 번 중지했을 가능성이 있고**, 그 사이에 host 전체 package 설치도 했다. 마지막 관측 상태는 `running`이다. 순서는 [AWS 환경 §10](./official-inputs/aws-environment.md) 「공유 EC2 사용 충돌」에 있다. 원인은 「시작한 쪽이 끝나면 끈다」는 가정이고, 운영 원칙은 Ops §2-1 「공유 EC2 전원 · host 변경 원칙」으로 승격했다. RT-14 세부 규칙은 §7.3이다.

## 4. 배포 source — `develop` 승격

**추천:** production 승격 source는 `develop`이다. 앞선 초안의 「배포 대상 branch 미결」을 닫는다. RD-12d의 일부로 승인한다.

- `develop`에 포함되고 검증된 revision만 배포한다.
- `develop` push는 배포 trigger가 아니다. 사람이 `workflow_dispatch`로 승격한다.
- `main`은 멘토 리뷰 · 제출 snapshot 흐름이다. 멘토 리뷰 자동화(`assign-mentor` · `convention-check`)는 `main` 대상 PR에서만 돈다. production은 `main`을 따르지 않는다.

현재 구현이 이 조건을 검사하는 방식은 다음과 같다(`deploy/aws.py` `trusted_context` · `quality_gate` · `remote`).

```text
dispatch 조건 (workflow if + trusted_context)
  event = workflow_dispatch · repository · repository ID 일치 · ref = refs/heads/develop
  배포 workflow는 Variable RT14_EXECUTION_ENABLED = true

모든 operation(publish · deploy · rollback) 공통 — quality_gate(env)
  GITHUB_SHA == GitHub API의 현재 develop tip                    (아니면 develop_moved)
  그 SHA에 대한 push event의 python-tests · boundary-check 최신 run이 completed · success

publish
  build 대상 = GITHUB_SHA (= dispatch 시점 develop tip). ECR tag = 그 SHA

deploy · rollback — quality_gate(env, revision=RT14_REVISION) 추가
  GitHub compare <RT14_REVISION>...develop 의 status ∈ {ahead, identical}
    → 대상이 develop tip이거나 그 조상
  대상 revision의 push CI 최신 run이 success
  ECR에서 tag=<RT14_REVISION>의 digest == Secret RT14_IMAGE의 digest
```

결과적으로 배포할 수 있는 revision은 **develop 이력에 있고, push CI가 성공했고, publish 때 develop tip이었던 commit**이다. PR CI만 통과한 commit이나 `main`에만 있는 merge commit은 거부된다.

§9.3의 변경이 반영되면 rollback은 위 공통 tip 검사에서 빠지고 대상 revision 검사만 받는다.

### 4.1 OIDC trust `:*` — infra risk, RT-14 hard blocker 아님

deploy role trust의 `sub` 조건은 이 repository 전체(`:*`)다(§3.1). AWS는 branch · tag · PR · environment를 구분하지 않는다.

**현재 보호 경계.** 공식 RT-14 workflow를 쓰는 한 다음이 모두 검사된다.

| 검사 | 위치 |
| --- | --- |
| event = `workflow_dispatch` | `trusted_context` · workflow `on` |
| repository 이름 · immutable repository ID | workflow `if` · `trusted_context` |
| ref = `refs/heads/develop` | workflow `if` · `trusted_context` |
| dispatch SHA = 현재 develop tip, 그 push CI 성공 | `quality_gate(env)` |
| 대상 revision이 develop tip이거나 조상, 대상 push CI 성공 | `quality_gate(env, revision)` |
| ECR tag와 digest 일치 | `remote` |
| `RT14_EXECUTION_ENABLED == 'true'` | 배포 workflow `if` · `main` |
| host의 승인파일 · exact tuple · schema `rollback_targets` | `ec2.py` |

**위험을 둘로 나눈다.**

- **실수로 잘못된 ref를 배포하는 위험** — 위 검사가 막는다. 공식 workflow를 다른 branch에서 dispatch하거나, PR · `main`에만 있는 commit · CI가 실패한 commit을 배포하려 하면 거부된다.
- **repository workflow 쓰기 권한에 대한 신뢰 위험** — 남는다. 위 검사는 공식 workflow 파일 안에 있다. repository에 workflow를 쓸 수 있는 collaborator가 다른 branch에 별도 workflow를 만들면 `id-token: write`로 같은 role을 assume할 수 있고, 그 workflow는 위 검사를 거치지 않는다. 그 role은 `PowerUserAccess`이고 지정 instance에 SSM 명령을 보낼 수 있다. 과소평가하지 않는다.

**추천 처리.**

- 운영진에게 묻는다: 「제공된 `ktc-github-deploy` role의 repository-wide OIDC trust를 branch 또는 GitHub Environment 기준으로 좁혀줄 수 있는가?」
- 쉽게 좁혀 주면 그에 맞춰 workflow를 조정한다.
- 카테캠 기본 제공 role이 repository-wide trust이고 수정이 어렵다면, **repository workflow 쓰기 권한을 신뢰 경계로 받아들이고 RT-14를 진행한다.** 조건은 공식 RT-14 workflow만 쓰고, 위 guard를 유지하고, repository 쓰기 권한자가 팀 안의 신뢰된 사용자이고, 운영진 제공 role을 임의로 수정하지 않는 것이다.
- 상태는 **accepted risk pending infra confirmation**이다. 답을 기다리느라 RT-14를 멈추지 않는다(§16.2).

**앞선 초안과 다른 점:** 배포 branch를 미결로 두었던 것을 `develop`으로 닫았다. 「대상 SHA의 python-tests success 확인」은 구현에서 **push event CI**로 좁혀졌다.

## 5. RD-12b — artifact 전달

**상태:** `IMPLEMENTED_PENDING_ACCEPTANCE`

**추천(구현과 같음):** build once → 그 artifact를 검증 → 같은 artifact를 push → 그 digest를 배포한다.

```text
dispatch(develop tip, push CI success 확인)
→ publish job: linux/amd64 image를 한 번만 build (REVISION=SHA)
→ 그 local image로 media preflight · offline OCR preflight · strict media acceptance
→ OIDC → 기존 IMMUTABLE repository에 SHA tag push → digest 확인
→ (별도 dispatch) EC2 controller가 그 digest를 instance role로 pull
```

| 항목 | 값 | Evidence |
| --- | --- | --- |
| ECR repository | 운영자가 미리 만든 1개(Variable `RT14_ECR_REPOSITORY`). api · worker · migrate가 같은 image를 쓴다. publish는 repository를 만들지 않고 `IMMUTABLE`이 아니면 실패한다 | DERIVED(RD-12a) · 구현 · HIGH |
| tag | 40자 commit SHA 하나. `latest` · `known-good` 같은 움직이는 tag 없음 | DERIVED(Ops §19) · EXTERNAL · HIGH |
| lifecycle | host `current` · `previous` · candidate digest를 지울 수 있는 count 기준 자동 삭제를 두지 않는다. 규칙은 첫 push에서 image 크기를 잰 뒤 정한다 | CONSERVATIVE · MEDIUM |

**이 선택을 고른 이유**

- image가 무겁다. FFmpeg 8.1을 source에서 compile하고 Paddle과 모델을 넣는다. t3.medium(2 vCPU · 3.8 GiB)에서 운영 stack 옆에서 build하면 CPU · 메모리 · disk를 직접 경쟁한다. credit이 `unlimited`라 성능 대신 비용이 든다.
- rollback할 artifact가 registry에 그대로 남는다. host build는 이전 image가 지워지면 다시 build해야 하고 byte 단위로 같다는 보장이 없다(Research 04 §1).
- **검증한 artifact와 배포하는 artifact가 같다.** publish job이 build한 image를 그대로 검증하고 push한다. 일반 CI(`python-tests`)가 검증한 image를 넘겨받지 않으므로 일반 CI와 배포 workflow의 분리(Ops §19)도 유지된다.

**count 기준 lifecycle을 두지 않는 이유:** release 기록은 host의 `current.json` · `previous.json`이고(§6), ECR lifecycle은 그 사실을 모른다. 실패한 release를 여러 번 push하면 count 기준 규칙이 rollback에 필요한 image를 지울 수 있다.

**acceptance:** repository 준비(`IMMUTABLE`) · deploy role의 push · EC2 role의 pull · image 크기와 pull 시간 기록.

**버린 선택지:** EC2 host build(자원 경쟁 · 재빌드), S3 tar(ECR보다 얻는 것이 없음).

**재검토 조건:** publish job이 시간 한도(55분)에 걸릴 때 · EC2 pull이 배포 시간 대부분을 차지할 때 · ECR 저장 비용이 눈에 띌 때.

## 6. RD-12c — revision 식별 · host release 기록

**상태:** `ACCEPT`

```text
source identity     = 40자 commit SHA                (Variable RT14_REVISION)
artifact identity   = ECR image digest (sha256:...)   (Secret RT14_IMAGE = repository@digest)
config identity     = config ID                       (Variable RT14_CONFIG_ID, 덮어쓰지 않음)
release 승인        = /opt/daesingo/approvals/<revision>.json (root 0400)
host current        = /opt/daesingo/current.json  (root 0600, 정확한 tuple)
host previous       = /opt/daesingo/previous.json (직전 host current)
schema authority    = /opt/daesingo/schema.json (code rollback과 별개로 보존)
```

**용어.** 이 문서는 두 상태를 구분한다.

| 용어 | 뜻 | 누가 기록하나 |
| --- | --- | --- |
| host `current` | **host 내부 배포 검증(§10.1)을 통과한, 지금 설치된 release.** `previous`는 그 직전 `current`다 | controller(`current.json` · `previous.json`) |
| production deployment success | host `current` 갱신 + SSM 명령 성공 + **외부 smoke(§10.2) 성공**. 공개 배포가 끝났다는 뜻 | 배포 workflow 결과 |

[RT-14 실행 절차](./rt14-deployment.md)와 #479 코드가 쓰는 「known-good」은 host `current` · `previous` 기록을 뜻한다. 외부 smoke까지 통과했다는 뜻이 아니다. 이 문서는 혼동을 피하려고 host `current`와 production deployment success라고 쓴다.

**이 선택을 고른 이유**

- digest로 배포하면 tag가 무엇을 가리키든 실제로 실행된 것이 하나로 정해진다. image 안 OCI label과 `DAESINGO_REVISION`이 revision을 다시 확인한다.
- release 기록을 host에 두는 이유는 두 가지다. 실제로 무엇이 실행 중인지 아는 곳이 host 하나이고, controller의 rollback 자체는 GitHub 없이 host 기록만으로 돈다(workflow 경유 rollback의 GitHub 의존은 §9.3).
- schema authority를 따로 두는 것은 #479 reviewer P1의 결과다. code rollback이 이전 release의 호환 목록으로 schema 기록을 덮어쓰지 않게 한다.
- ECR `known-good` tag는 `IMMUTABLE`에 예외 filter가 필요해 두지 않는다(Research 04 §6).

**부분 배포 탐지:** api · worker의 image ID와 `DAESINGO_REVISION`이 대상과 같아야 하고, mysql image는 policy digest와 같아야 한다. 하나라도 다르면 실패다.

**재검토 조건:** host를 다시 만들거나 교체할 때(기록이 사라짐) · 배포 주체가 늘어날 때.

**앞선 초안과 다른 점:** `known-good.json` 하나와 `releases.jsonl` 대신 current/previous · schema authority · 승인파일 구조가 됐다. 배포 시도 이력 파일은 없다. 시도 이력은 Actions run과 `dirty.json`뿐이다(§15).

## 7. RD-12d — SSM 배포 명령

**상태:** `IMPLEMENTED_PENDING_ACCEPTANCE`

### 7.1 구조

```text
GitHub Actions (workflow_dispatch, develop)
 1. trusted_context · quality_gate (§4)
 2. OIDC → ktc-github-deploy → identity 비교
 3. ECR tag → digest 대조
 4. ssm send-command: exec /usr/bin/python3 /opt/daesingo/controller/ec2.py <op> ... (한 줄)
 5. get-command-invocation을 3 s 간격으로 polling → Success + exit 0만 성공
 6. (공개 배포, 추가 필요) runner에서 외부 smoke → production deployment success (§10.2)
EC2
 controller: root · x86_64 · policy · 승인파일 검증 → operation.lock → transition (§8)
```

| 항목 | 값 | Evidence |
| --- | --- | --- |
| trigger | `workflow_dispatch`만. `push`로 자동 배포하지 않는다 | DERIVED · HIGH |
| 허용 ref | `develop`(§4) | DERIVED · HIGH |
| 동시 실행 | Actions `concurrency: rt14-team-ec2`(진행 중인 것을 취소하지 않음) + host `operation.lock` | 구현 · HIGH |
| timeout | delivery 60 s · 실행 1,200 s · runner 대기 1,500 s · job 30분(remote) / 55분(publish). 도구 timeout이지 측정값이 아니다 | 구현 · LOW |
| Run Command 출력 | 수집하지 않음(CloudWatch 출력 끔, runner는 status · code만) | 구현 · HIGH |

**이 선택을 고른 이유**

- Run Command는 `sh`로 돌고 마지막 exit code만 결과로 삼는다(§3.1). 명령을 controller `exec` 한 줄로 두면 결과가 곧 controller의 exit code다.
- `aws ssm wait command-executed`는 약 100초 뒤 끝나므로 쓰지 않고 직접 polling한다(Research 04 Review).
- controller를 image 밖에 고정 설치하면, 배포 대상 image가 배포 절차 자체를 바꿀 수 없다. 대신 controller의 버전은 digest로 식별되지 않는다. 설치 때 승인 SHA의 파일과 host 파일의 SHA-256을 대조하는 절차로 메운다([RT-14 실행 절차](./rt14-deployment.md) §4).
- `push` 자동 배포를 하지 않는 이유: OIDC trust가 모든 ref에 열려 있고, 6명이 같은 서버를 쓰며, 모든 배포가 api · worker를 멈춘다(§8). 배포 시점은 곧 maintenance window이므로 사람이 고르고 알린다.

**앞선 초안과 다른 점:** image 안 `deploy.sh`를 꺼내 실행하는 안을 버리고 구현의 고정 controller를 채택한다. Run Command 출력용 Log Group(`/daesingo/prod/deploy`)은 출력을 수집하지 않으므로 필요 없다. 실행 timeout은 구현값 1,200 s다.

### 7.2 실패를 알리는 방식

Actions에는 `rt14: operation_failed_or_unknown` 한 줄만, host에는 고정 문구 한 줄만 남는다. quality gate 거부인지 원격 실패인지도 Actions 로그로는 구분되지 않는다. secret과 식별값이 새지 않는 대신, 어디서 실패했는지는 운영자가 GitHub CI 상태와 SSM의 `dirty.json` phase · container 상태 · `awslogs`를 보고 재구성해야 한다. 고정 어휘의 실패 단계 이름만 출력하는 보완은 권장하되 blocker로 두지 않는다(§16).

### 7.3 공유 host 운영 제약 — RT-14 세부 규칙

상위 원칙은 Ops §2-1 「공유 EC2 전원 · host 변경 원칙」이다. 전원 자동화 금지 · 사람이 전원 변경 · 전원 상태 되돌리기 자동화 금지가 거기 있다. RT-14 구현과 운영은 다음을 더 지킨다.

- **host 전체 Docker 설정을 바꾸지 않는다.** `daemon.json`(기본 log driver 등)은 그대로 두고, RT-14 설정은 release compose의 service 단위로만 건다. 구현도 그렇게 render한다(§11). `daemon.json`을 바꾸려면 Docker를 재시작해야 하고, 그러면 다른 workload도 멈춘다.
- **자기가 만든 것만 다룬다.** `docker system prune` · `docker image prune -a` · `docker volume prune` · `down -v` 같은 host 전체 정리를 자동화에서 쓰지 않는다. 준비 구현에는 삭제 기능이 없다. compose는 고정 project 이름으로만 다룬다. AWS 환경 §7의 prune 안내는 단독 사용을 전제로 한 일반 팁이다.
- **배포 · host 변경 전에 팀에 알린다.** 배포는 api · worker를 멈춘다. 공개 기간에는 외부 사용자도 영향을 받는다(§13.7).
- **lock의 한계:** `operation.lock`은 controller끼리의 동시 실행만 막는다. 다른 SSM session, 다른 사람의 Docker 작업, EC2 전원 조작은 막지 못한다. 이 부분은 팀 알림 규칙으로 메운다.

## 8. RD-12f — migration · maintenance

**상태:** `IMPLEMENTED_PENDING_ACCEPTANCE`

### 8.1 현재 구현 순서

| 단계 | 동작 | 실패하면 |
| --- | --- | --- |
| preflight | 소유 volume · project · MySQL digest · disk/memory reserve · 보호 config · Log Group retention · ECR pull · image 검사 · compose render · `deploy-config` | known-good 유지. 아무것도 멈추지 않았다 |
| quiesce | `dirty.json`(quiescing)을 먼저 기록 → `compose stop api worker migrate` | writer가 멈춘 상태로 남는다. 자동 재시작 없음 |
| mysql · packet | MySQL만 기동 · healthy → session `max_allowed_packet`이 `MAX_BYTES + packet_margin_bytes`보다 큰지 확인 | 같음 |
| migrate | `dirty.json` · `schema.json`을 `migration_pending`으로 기록 → migrate **단 한 번** | 새 deploy · rollback 모두 거부. 부분 DDL을 조사하고 forward repair 또는 검증된 restore |
| start · health · smoke | `migration_complete` 기록 → api · worker recreate → 검증(§10) | host `current` 미갱신. 새 app이 떠 있을 수 있다. 명시적 rollback 판단(§9) |
| 승격 | `previous.json` ← 이전 current, `current.json` ← 이번 release, `dirty.json` 삭제 | 중간에 끊기면 dirty와 current/previous를 대조 |

### 8.2 queue 처리 — full drain과 graceful stop 비교

| 기준 | A. full drain — API 정지 → QUEUED · RUNNING 0 → Worker 정지 | B. ingress 정지 + Worker graceful stop — 현재 구현 |
| --- | --- | --- |
| maintenance 시간 | **상한이 없다.** Worker가 결과 반영 transaction 안에서 다음 job을 enqueue하므로(`common/jobs/reflection.py` `reflect_terminal` · `exhaustion.py`) 진행 중 pipeline은 사용자 입력을 기다리는 지점까지 이어진다. backoff 중인 QUEUED는 `available_at`이 미래다. 상한 숫자가 필요하지만 근거가 없다 | 남은 job 양과 무관하다. Worker grace(최대 30 s) + MySQL · packet · migrate + 검증(최대 120 s 재시도) |
| old/new job 호환 | 0에 닿으면 새 Worker가 이전 job을 넘겨받지 않는다 | 새 Worker가 start 직후 남은 QUEUED와 STALE 재시도를 claim한다. **새 handler가 이전 release가 만든 job을 처리할 수 있어야 한다** |
| durable payload 호환 | 0일 때는 필요 없다 | 필요하다. rollback까지 보면 양방향이다. rollback한 이전 Worker가 새 release가 만든 job을 처리한다 |
| schema migration | writer 정지 뒤 실행 — 같다 | 같다. 다만 QUEUED 행이 남은 채 migration이 도므로 job 관련 table 변경이 기존 행을 깨면 안 된다 |
| rollback | 「새 release가 이전 job을 처리하지 않았다」는 전제가 생긴다 | 그 전제가 없다. 그래서 자동 rollback의 근거가 되지 못하고, 명시적 rollback(§9)과 맞다 |
| Runtime retry/STALE | 쓰지 않는다 | 쓴다. grace 안에 끝나지 않은 실행은 강제 종료 → lease 만료(60 s) → sweep(15 s) → STALE → 자동 retry. 2026-10-29 Compose 실측에서 판독 중 Worker 강제 종료 → STALE → attempt 2 성공, 반영 1회, 죽은 attempt의 사용량 Final 회수를 확인했다(#450 Owner 메모). 비용은 attempt 1회 소모, 실행 중이던 provider 호출의 재비용, 사용자 대기 증가다 |
| 공개 서비스 | 배포 창 길이를 예고할 수 없다 | 배포 창이 짧고 예측할 수 있다 |

**추천: B(현재 구현)를 기본으로 채택한다.** 근거는 maintenance 시간을 예측할 수 있다는 것, drain 상한 숫자를 지어내지 않아도 된다는 것, 그리고 이미 실측된 STALE · retry 계약 위에 서 있다는 것이다. 대가는 release 사이 job 호환 요구다. 이 요구는 새 장치가 아니라 **release 승인 때 확인할 항목**으로 둔다. 구현의 승인파일은 이미 「지금 revision이 새 release의 `rollback_targets`에 있다」는 schema 호환 승인을 요구한다(§3.2). 그 승인에 job 호환 확인을 포함한다.

**full drain(A)이 필요한 조건.** release 승인 때 아래 중 하나라도 해당하면 B로 배포하지 않는다.

1. job payload 구조 · kind 의미 · handler의 입력 해석이 바뀌어, 새 handler가 이전 release의 payload를 처리할 수 없다.
2. kind를 없애거나 이름을 바꾼다. 8종 등록 marker가 정확히 8종을 요구하므로 이 경우 검증도 바뀐다.
3. migration이 job · case 관련 table을 기존 행과 호환되지 않게 바꾼다.
4. rollback 대상 release가 새 release가 만든 job을 처리할 수 없다. 이 경우는 그 revision을 `rollback_targets`에서 빼는 것이 먼저다.

controller에는 drain 단계가 없다. A가 필요한 release는 수동 사전 단계로 처리한다. SSM에서 api만 멈추고, QUEUED(`available_at`이 미래인 행 포함) + RUNNING이 0이 된 것을 확인한 뒤 deploy를 dispatch한다. 기존 `read_metrics`의 `oldest_queued_age_s`는 `available_at <= NOW`만 보므로 이 판정에 그대로 쓰지 않는다. 대기 상한 숫자는 두지 않는다. 0에 닿지 않으면 그 release를 미룬다. 공개 기간에는 이런 release를 피하는 것을 권장한다.

### 8.3 backup

- 승인파일의 `backup_reference`는 모든 deploy에 필수다. 그 backup이 실제로 성공했는지는 기계적으로 증명되지 않으므로 운영자가 runbook evidence와 대조한다([RT-14 실행 절차](./rt14-deployment.md) §5).
- migration heads가 바뀌는 release는 RT-13(b) logical backup을 먼저 만든다. EBS snapshot 복원은 `CreateVolume` 거부로 쓸 수 없어 logical dump가 유일한 DB 복구 수단이다.
- 기존 backup 도구는 SQL을 메모리에 모은다. DB가 커지면 4 GB host에서 바로 실행하지 않는다(같은 문서 §8).
- media volume은 rollback · logical backup 대상이 아니다.
- host `current` · `previous`로 돌아가는 데 필요한 pre-migration backup은 지우지 않는다. 그 밖의 보관 개수는 첫 dump 크기를 잰 뒤 정한다(§15).

**앞선 초안과 다른 점:** 「모든 배포에서 api 정지 → queue drain → 0 확인 → worker 정지」를 폐기했다. 그 안의 전제는 「drain이 자동 rollback의 안전 전제를 만든다」였는데, 자동 rollback을 두지 않으므로(§9) drain이 지키던 것이 없다. 「배포 때 writer를 먼저 모두 멈춘다」는 SP-1 결론(§17)은 구현에 그대로 있다.

## 9. RD-12e — rollback

**상태:** `NEEDS_CHANGE` — 방향은 현재 구현이 맞고, 운영 경로에 고칠 곳이 있다.

### 9.1 현재 구현

- 자동 rollback이 없다. host 내부 검증이 실패하면 host `current`로 승격하지 않고, `dirty.json`이 남고, workflow가 실패한다.
- rollback은 operator가 `rt14-deploy`의 `operation=rollback`으로 실행한다. 이때 Secret `RT14_IMAGE`와 Variable `RT14_REVISION` · `RT14_CONFIG_ID`를 rollback 대상 값으로 바꿔 둬야 한다.
- controller는 `current.json` 또는 `previous.json`과 **정확히 같은 tuple**, 그리고 `schema.json`의 `rollback_targets`에 있는 revision만 받는다. migration을 실행하지 않고, 이전 config ID를 쓰고, 같은 preflight → 정지 → MySQL · packet → recreate → 검증을 반복한다.
- DB downgrade · volume 삭제 · 자동 restore는 하지 않는다.

### 9.2 자동 rollback을 두지 않는 이유

자동 rollback의 이점은 운영자가 반응하기 전에 복구 시간이 줄어든다는 것이다. 안전하려면 네 전제가 필요하다.

1. 새 release가 사용자 데이터 · job을 아직 처리하지 않았다.
2. 이전 code가 현재 schema와 호환된다.
3. 이전 image · config가 host와 registry에 남아 있다.
4. 실패 원인이 새 release에 있다. DB · host · 외부 원인이면 rollback도 실패하고 변경만 두 번 일어난다.

2와 3은 구현이 검사한다. **1은 B안(§8.2)에서 성립하지 않는다.** 새 Worker는 start 직후 claim을 시작하므로 검증 실패 전에 이미 job을 처리했을 수 있다. 4는 기계가 판단할 수 없다. 반대로 배포는 사람이 dispatch하고 결과를 지켜보는 수동 승격이라 반응 시간 이득이 작다. 그래서 **명시적 controlled rollback을 기본안으로 한다.**

#450 acceptance가 요구하는 것은 「known-good revision으로 실제 rollback rehearsal 통과」다. 「배포 실패 시 자동 rollback」이 아니다.

```text
host 내부 검증 실패
→ host current 유지(승격 안 함) · dirty.json(phase) 남음 · workflow 실패
→ operator: SSM으로 dirty phase · container · awslogs 확인
→ 복구가 우선이면 rollback 실행(대상 = host current 기록의 정확한 tuple)
   → exact tuple · schema rollback_targets 검사 → migration 없이 recreate → 같은 내부 검증 → 외부 smoke
→ 원인을 고친 새 revision은 rollback이 끝나 dirty가 없어진 뒤 publish → deploy

외부 smoke 실패(§10.2) — deploy든 rollback이든, host current는 이미 내부 검증을 통과한 release다
→ workflow 실패 · host application revision을 자동으로 바꾸지 않는다
→ operator: 먼저 public ingress를 조사한다
   DNS · DDNS 갱신 · TLS 인증서 · Caddy · Web pointer/산출물 · Security Group · public route
→ ingress 원인이면 그쪽을 고치고 외부 smoke만 다시 실행한다(host 상태 변경 없음)
→ 다른 application revision이 필요하다고 operator가 판단할 때만 별도 deploy 또는 rollback을 고른다
```

rollback operation이 host 내부 검증을 통과해 `current`가 이전 revision으로 바뀌었는데 외부 smoke가 실패했다면, 그것은 대개 이전 revision의 문제가 아니라 public ingress 문제다. 「다시 rollback」으로 이어지지 않는다.

### 9.3 고쳐야 할 것

1. **rollback dispatch가 develop tip CI에 묶여 있다.** `aws.py` `main`은 rollback에도 `quality_gate(env)`를 요구한다. dispatch한 develop tip이 현재 tip이어야 하고 그 push CI가 성공이어야 한다. 그래서 새 merge 직후 CI가 도는 동안(#479 기준 mysql job만 886 s)이나 tip CI가 실패한 동안에는 workflow rollback이 거부된다. Actions에는 고정 실패 문구만 남아 거부 이유도 바로 보이지 않는다(§7.2). rollback은 이미 host 검증을 통과했던 release로 돌아가는 일이라 tip 상태와 무관해야 한다.

   **코드 변경안(`deploy/aws.py`):**
   - `main`: `quality_gate(env)` 호출을 `publish` · `deploy`에만 적용하고 `rollback`에서는 부르지 않는다. `trusted_context`(workflow_dispatch · repository · ID · `refs/heads/develop`)와 `RT14_EXECUTION_ENABLED` 검사는 rollback에도 그대로 둔다.
   - `remote`: rollback에서도 지금처럼 `quality_gate(env, revision=RT14_REVISION)`(대상이 develop tip이거나 조상 · 대상 push CI 성공)과 ECR tag → digest 일치를 검사한다.
   - host 쪽은 바꾸지 않는다. `ec2.py` `main` · `transition`이 `current` · `previous`와의 exact tuple과 `schema.json`의 `rollback_targets`를 계속 검사한다.
   - `tests/deploy/test_aws_deploy.py`에 「tip CI가 pending · 실패여도 rollback은 대상 검사만으로 진행」 · 「deploy · publish는 여전히 tip 검사」 회귀를 더한다.

   그래도 rollback 대상은 develop 이력 · push CI · ECR digest · host exact tuple · schema 호환의 다섯 겹 검사를 받는다. 빠지는 것은 「지금 develop tip이 초록인가」뿐이다.

   **break-glass:** GitHub · Actions를 쓸 수 없을 때는 SSM Session에서 controller rollback 명령([RT-14 실행 절차](./rt14-deployment.md) §7)을 직접 실행한다. controller는 host 기록만으로 검사하므로 이 경로도 exact tuple · schema 검사를 받는다. runbook에 비상 경로로 남긴다.
2. **최초 배포가 실패하면 도구로 다시 시도할 수 없다.** 최초 배포가 migration 뒤에 실패하면 `current.json`이 없어 rollback 대상이 없다. `dirty.json`이 남아 deploy가 거부되고, dirty를 치워도 preflight가 비어 있지 않은 volume과 host `current` 없는 기존 container를 거부한다(§3.2). **첫 AWS deploy 전에 operator가 통제하는 recovery 절차를 runbook에 둔다.** 자동 volume 삭제 기능은 만들지 않는다. runbook에 들어갈 내용은 다음과 같다.
   - SSM에서 controller process · SSM command 상태 · 같은 project의 container를 확인한다. 살아 있는 작업의 lock을 빼앗지 않는다.
   - `dirty.json` · `schema.json`의 phase를 확인한다. `migration_pending`이면 부분 DDL 가능성을 기록한다.
   - `current.json`이 없고 실제 사용자 데이터가 없는 최초 bootstrap임을 확인하고 기록한다. 하나라도 아니면 이 절차를 쓰지 않는다.
   - 실패한 시도의 container를 그 project 범위에서만 정리한다.
   - 소유 volume을 다시 만들어야 하면 사람이 명시적으로 한다. 이름 · label(`com.daesingo.owner` · `com.daesingo.purpose`)은 policy와 같게 둔다.
   - empty-owned-volume 상태를 다시 검증한다(controller preflight와 같은 기준).
   - dirty · schema · lock 상태를 위 확인 결과와 맞춘 뒤에 해소한다. **`dirty.json`을 지우는 것만으로는 recovery가 아니다.**
   - `initial_state=verified-empty-owned-volumes` 승인으로 다시 bootstrap · deploy한다.
3. **rollback rehearsal 1회**(#450 acceptance). host `current` · `previous`가 모두 생긴 뒤, 즉 두 번째 정상 release 뒤에 가능하다.

### 9.4 rollback 경계

- **MySQL image는 앱 release와 분리한다.** policy에 `mysql@sha256` digest를 고정하고 controller는 MySQL을 pull · upgrade하지 않는다. MySQL 변경은 backup을 포함한 별도 수동 작업이다. 같은 LTS 안의 downgrade만 in-place로 지원되기 때문이다(Research 04 Review High).
- **media volume은 rollback하지 않는다.**
- **schema가 바뀐 release 뒤의 code rollback**은 그 release 승인이 이전 revision을 `rollback_targets`에 넣었을 때만 가능하다. 아니면 forward repair 또는 빈 target에 restore하는 수동 절차다([RT-14 실행 절차](./rt14-deployment.md) §7 · §8).

**앞선 초안과 다른 점:** 「배포 검증 중 실패 · heads 같음이면 자동 rollback」을 폐기했다. 그 안의 안전 전제였던 queue drain과 비공개 endpoint가 둘 다 없어졌기 때문이다.

## 10. RD-12h — 배포 후 검증

**상태:** `NEEDS_CHANGE` — host 내부 검증은 구현됐고, 공개 배포의 외부 smoke(workflow post-SSM 단계)가 없다.

```text
SSM deploy
→ host 내부 검증(§10.1)
→ Web current pointer 전환(§13.6)
→ host current 갱신            ← 「host 내부 검증 통과」의 뜻
→ SSM command success
→ GitHub runner 외부 smoke(§10.2)
→ production deployment SUCCESS ← 공개 배포 완료의 뜻
```

### 10.1 내부 검증 — 구현됨

모두 host 안에서 controller가 돌린다. health 단계는 120 s 안에서 3 s 간격으로 재시도한다. 모두 통과해야 host `current` · `previous`를 갱신한다.

| # | 확인 | 구현 | 성공 조건 |
| --- | --- | --- | --- |
| 1 | expected revision · digest · container | `inspect_services` | api · worker · mysql 각 1개 running · Restarting/OOM 아님 · RestartCount 0 · app image ID = pull한 digest · `DAESINGO_REVISION` = 대상 · api와 mysql healthy. smoke 뒤 한 번 더 확인 |
| 2 | live | `deploy-smoke` | `/health/live` 200 `{"status":"ok"}` |
| 3 | ready | `runtime.py ready` · `deploy-smoke` | `/health/ready` 200 `{"status":"ok"}` |
| 4 | Worker process · revision | `worker-status` | marker의 PID = 1 · process starttime 일치 · revision = 대상 |
| 5 | 필수 8종 handler 등록 | `worker-status` | 등록 kind = `HINT_EXTRACT` · `COARSE_SEARCH` · `FINE_VERIFY` · `INCIDENT_CLIP_BUILD` · `PLATE_READ` · `OVERLAY_TIME_READ` · `REPORT_VIDEO_EXPORT` · `PLATE_IMAGE_EXPORT`와 정확히 같음. Recording profile · 분석 한도 · incident encoding이 없으면 Worker가 marker를 쓰기 전에 실패한다 |
| 6 | provider 없는 DB 경유 smoke | `deploy-smoke` | 무작위 case의 `GET /cases/<id>/view` 404. DB를 지나고 case · job · media · provider를 만들지 않는다 |

- `compose up --wait`의 성공만으로는 부족하다는 SP-1 결과(S5: healthcheck 없는 worker의 crash를 `--wait`가 못 잡음)는 RestartCount 0과 PID/starttime marker가 덮는다.
- marker는 **process · 등록 증거**다. idle heartbeat나 handler 성공을 뜻하지 않는다.
- smoke에서 provider를 부르지 않는 이유: 배포마다 ML API 크레딧을 쓰지 않고, provider 장애가 배포 실패로 번지지 않게 하기 위해서다(Ops §9).
- **실제 provider 영상 E2E는 매 배포마다 하지 않는다.** release 후보를 정할 때 수동으로 한다. 빈도는 §15 미결이다.

### 10.2 외부 검증 — 추가 필요

공개 배포(§13)에서는 SSM command가 성공한 뒤 **GitHub-hosted runner**에서 아래를 실행한다. deploy와 rollback 모두에 적용한다.

| # | 확인 | 성공 조건 |
| --- | --- | --- |
| 7a | DNS resolve | 공개 hostname이 resolve된다. 결과를 EC2 public IPv4와 대조할지는 구현이 정한다 |
| 7b | TLS hostname · 인증서 검증 | hostname에 맞는 유효한 인증서로 연결된다. 인증서 검증을 끄지 않는다 |
| 7c | 공개 Web GET | `GET https://<host>/` 200 |
| 7d | Web revision | `GET https://<host>/version.json`의 revision == 대상 `RT14_REVISION`(§13.6 marker) |
| 7e | 공개 same-origin API GET | `GET https://<host>/cases/<무작위>/view` 404. 6번과 같은 의미를 proxy 경유로 확인한다 |

외부 smoke가 증명하는 것은 public DNS + TLS + Caddy + Web 도달 + **Web revision** + same-origin API 경로다. 7c만으로는 이전 Web revision이 계속 서비스돼도 통과하므로 7d를 둔다. 7d가 `Web revision == API revision`(§13.6)을 외부 acceptance에서 확인한다. API revision 자체는 내부 검증 1번이 확인한다.

**왜 runner에서 하나.**

- 실제 EC2 외부 네트워크에서 DNS · TLS · public route를 본다. host가 자기 public DNS를 부르는 방식보다 「외부 사용자가 접근할 수 있다」에 가깝다.
- controller에 callback이나 2단계 승격 상태 기계를 새로 넣지 않아도 된다.

**실패하면.** workflow가 실패한다. **외부 smoke 실패 자체로 host application revision을 자동으로 바꾸지 않는다.** controller가 자동 rollback하거나 host `current`를 자동 복원하지 않는다. operator는 먼저 public ingress(DNS · DDNS · TLS · Caddy · Web pointer/산출물 · SG · route)를 조사하고, 다른 application revision이 필요하다고 판단할 때만 별도 deploy · rollback을 고른다(§9.2).

**재실행.** 외부 smoke는 host 상태를 바꾸지 않고 따로 다시 돌릴 수 있어야 한다. ingress를 고친 뒤 배포 없이 확인하기 위해서다. 수단(별도 operation · workflow)은 구현이 정한다. host `current`는 「host 내부 검증 통과」이고 production deployment success는 「외부 smoke까지 통과」라서(§6 용어), 외부 smoke가 실패해도 두 의미가 충돌하지 않는다.

host에서 public URL을 부르는 검사는 필요하면 보조로 둘 수 있지만 primary acceptance로 만들지 않는다. 정확한 형태(별도 workflow step인지 `deploy/aws.py`의 함수인지, 공개 hostname을 Variable로 받는지)는 RD-14 구현 PR이 정한다.

**앞선 초안과 다른 점:** 「Worker 시작 로그로 8종 확인」은 구현의 marker로, 「60 s RestartCount 관찰」은 120 s health 창과 smoke 뒤 재확인으로 바뀌었다. 외부 smoke는 「RD-14 기본값(비공개)에서는 host 내부로 대신」이었는데, 공개가 확정됐으므로 필수가 됐다. 같은 날 검토에서 「controller가 승격 전에 외부 smoke를 돌린다」는 안을 버리고 workflow post-SSM 단계로 바꿨다.

## 11. RD-13a · RD-11a — log 수집 · 보관

**상태:** RD-13a `IMPLEMENTED_PENDING_ACCEPTANCE` · RD-11a `ACCEPT`

| 항목 | 값 | Evidence |
| --- | --- | --- |
| driver | release compose의 api · worker · migrate · mysql에 `awslogs`. **host 기본 driver(`daemon.json`)는 바꾸지 않는다** | EXTERNAL · MEASURED(SP-2) · 구현 · HIGH |
| Log Group | policy `log_group` 하나. 운영자가 retention과 함께 미리 만든다. controller는 존재와 retention 일치만 확인하고 `awslogs-create-group`은 끈다. 이름 후보는 앞선 초안의 `/daesingo/prod/app` | 구현 · CONSERVATIVE · MEDIUM |
| stream tag | `<project>/<service>/{{.ID}}` | 구현 |
| 전달 방식 | `mode: non-blocking` · `max-buffer-size` = policy `log_buffer_bytes`(필수, 기본값 없음). 앞선 초안 후보는 4m(SP-2에서 사용, 근거 약함) | EXTERNAL · CONSERVATIVE · LOW |
| host 상한 | dual logging cache `cache-max-size: 20m` · `cache-max-file: 5`. B-O1과 같은 숫자다 | DERIVED(B-O1) · 구현 · MEDIUM |
| CloudWatch retention | **30일**(RD-11a) | CONSERVATIVE · MEDIUM |

**이 선택을 고른 이유**

- **host-only(`local`)를 버린 이유:** container를 다시 만들면 로그가 사라진다. 배포와 rollback이 container를 다시 만들기 때문에 실패한 revision의 로그가 필요할 때 없다. controller가 출력을 공개하지 않으므로(§7.2) 실패 조사는 더욱 이 로그에 기댄다.
- **CloudWatch Agent를 버린 이유:** 설치 · 설정 대상이 하나 더 생기고, Docker log 경로 수집이 까다롭다(Research 04 Review Med).
- `awslogs`는 host의 Docker daemon이 instance role로 보낸다. IMDS hop limit 1은 container에만 걸린다. SP-2에서 이 EC2로 실측했다(§17).
- **B-O1과 option 이름이 다르다.** B-O1은 `local` driver의 `max-size` · `max-file`이다. remote driver의 dual logging cache는 `cache-max-size` · `cache-max-file`이다. 숫자만 맞췄고, 구현도 `cache-*` 이름으로 render한다.
- `non-blocking`을 고른 이유: CloudWatch 네트워크 문제가 api 응답을 막으면 안 된다(Research 04 B-6). 대신 buffer가 넘치면 로그가 버려질 수 있다.
- **retention 30일의 근거:** 10-30부터 제공 종료(11-20)까지 3주다. 그 기간을 덮는 가장 작은 CloudWatch 허용값이 30일이다. 로그에는 민감 원문을 남기지 않는 것이 원칙이다(Ops §7).
- Logs Insights의 JSON 필드 조회는 Docker stream으로 한 번에 실측하지 못했다(§17). 첫 배포 로그로 다시 확인한다.

**acceptance:** 운영 group 생성(retention 포함) · EC2 role의 `logs:DescribeLogGroups` · `CreateLogStream` · `PutLogEvents` · 실제 stack 로그 수신.

**재검토 조건:** `non-blocking` buffer 초과로 로그 누락이 관측될 때 · CloudWatch 비용이 눈에 띌 때.

**앞선 초안과 다른 점:** Run Command 출력용 group을 없앴다(§7.1).

## 12. RD-13c · RD-13d · RD-07c

### 12.1 RD-13c restart — `ACCEPT`

| 항목 | 값 | Evidence |
| --- | --- | --- |
| restart policy | policy `restart_policy = unless-stopped`(api · worker · mysql에 적용). migrate는 구현이 `no`로 고정 | EXTERNAL · MEDIUM |
| boot | `docker.service` enable(부록 A로 적용됨) | EXTERNAL · HIGH |

- `unless-stopped`는 프로세스 crash와 host 재부팅에서 자동으로 돌아오고, 유지보수 · rollback 중 사람이 멈춘 것은 존중한다. 공개 기간에 팀원이 EC2를 다시 시작해도 stack이 돌아온다. 다만 public IP가 바뀌므로 DDNS 갱신이 함께 필요하다(§13).
- 구현에는 기본값이 없다. 승인값을 policy에 넣어야 controller가 돈다.
- **알고 받아들이는 한계:** Docker는 `unhealthy` container를 재시작하지 않는다. 죽은 프로세스만 복구되고 멈춘(hang) 프로세스는 복구되지 않는다.
- restart rehearsal(Worker 강제 종료 → 재시작 · STALE 회복)은 #450 acceptance다.

### 12.2 RD-13c alert — `DEFER_TO_FOLLOWUP`

- 1주 넘는 공개 기간에 아무도 모르게 서비스가 멈출 수 있다는 위험은 실재한다. 그러나 임계값의 근거와 받아서 대응할 당번이 없다(Ops §9). RT-14 blocker로 두지 않는다.
- 공개 기간 최소 감시(공개 URL의 주기적 외부 확인 · EC2 status check 정도)와 알림 채널 · 대응자는 후속 이슈 P1에서 정한다. 큰 monitoring stack은 만들지 않는다(Ops §22).

### 12.3 RD-13d Worker 상태 노출 — `ACCEPT`

| 신호 | 수단 | 보는 것 |
| --- | --- | --- |
| process · 등록 | `worker-status`(SSM에서 언제든 실행 가능. release compose가 `DAESINGO_DEPLOYMENT_CHECK=1`을 넣는다) | 실제 Worker process가 대상 revision으로 8종을 등록했는지 |
| 생존 | container 상태 · RestartCount | 죽었거나 재시작을 반복하는지 |
| 로그 | `awslogs` | 실패 event · heartbeat lag |
| 처리 상태 | Runtime DB 집계(`common/jobs/metrics.py` `read_metrics`) | `oldest_queued_age_s` · `stale.count` · queue wait. 대기열이 쌓이는데 RUNNING이 없으면 Worker가 일을 못 하고 있다 |

- 새 HTTP endpoint를 만들지 않는다. ready에 Worker를 묶지 않는다는 계약(HTTP API Contract §5.7)을 지킨다.
- Worker 전용 idle heartbeat table을 만들지 않는다. schema 변경 비용에 비해, 대기 중인 Worker를 보는 이득은 대기열 지표로 대부분 얻는다.
- `read_metrics`를 운영자가 바로 부를 명령은 아직 없다. 후속 이슈 P1(최소 감시)에서 다룬다.
- **재검토 조건:** 대기 중에 멈춘 Worker가 실제로 관측될 때.

**앞선 초안과 다른 점:** 「시작 로그 1줄」 대신 구현의 marker를 쓴다.

### 12.4 RD-07c secret — `IMPLEMENTED_PENDING_ACCEPTANCE`

경로는 Ops §4-1로 **이미 닫혔다.** 구현은 다음과 같다.

| 항목 | 값 | Evidence |
| --- | --- | --- |
| Parameter Store | policy `parameter_path` 아래 **SecureString 정확히 3개**: `runtime-env`(runtime.env 전체 내용) · `mysql-password` · `mysql-root-password`. 누락 · 빈 값 · 평문 String · 예상 밖 parameter는 거부 | 구현 · HIGH |
| 실행 | 배포와 별개로 운영자가 SSM에서 `configure.py --config-id <새 ID>`. EC2 instance role로 조회 | 구현 · HIGH |
| 보호 파일 | `/opt/daesingo/configs/<config-id>/` root 0700 · `runtime.env` UID 10001 0400 · MySQL 파일 두 개는 mysql UID 0400. 기존 config ID는 덮어쓰지 않는다 | 구현 · HIGH |
| 값을 쓰는 사람 | 운영자가 SSO로 직접 쓴다. Actions는 값을 읽거나 쓰지 않는다 | DERIVED(Ops §4-1) · HIGH |
| fallback | 권한이 없으면 같은 계약의 파일을 Session Manager로 수동 배치(RD-07) | DERIVED · HIGH |

**acceptance:** EC2 instance role의 `GetParametersByPath` · 복호화 실측. **`runtime-env` 값 크기** — 파일 전체를 parameter 하나에 넣는다. standard tier SecureString 값은 4 KB까지다(advanced tier는 8 KB, 유료). 주석이 포함된 `.env.example`이 4,315 bytes이므로, 실제 값 파일이 4 KB 안에 드는지 첫 등록 때 확인한다. 넘으면 tier 또는 parameter 구성을 다시 정한다.

**앞선 초안과 다른 점:** key별 parameter(`/daesingo/prod/runtime/<KEY>`) 대신 구현의 parameter 3개 구조를 채택한다.

## 13. RD-14 — public endpoint

**상태:** `NEEDS_CHANGE` — 공개 모델은 추천하고, 구현은 아직 없다.

### 13.1 결정 갱신

앞선 초안의 「기본 비공개 · SSM port forwarding · public trigger는 PM 질문」은 폐기한다. 최종 제출 요구로 trigger가 이미 발생했다(§3.3). Register의 RD-14는 「trigger 대기」에서 「제출 마감 전 결정」으로 바뀐다.

### 13.2 추천 운영 모델

| 항목 | 추천 |
| --- | --- |
| 공개 형태 | 최종 심사 기간 외부에서 접근할 수 있는 **공개 체험 서비스**. 로그인 · 회원가입은 이번 MVP 범위에 넣지 않는다 |
| origin | Web + API **same-origin**. `https://<host>/`는 Web 정적 산출물, `https://<host>/cases…` · `/health…`는 API |
| API 노출 | 8000을 직접 공개하지 않는다. api는 지금처럼 host `127.0.0.1:8000`에만 bind한다(`production_compose`) |
| TLS | HTTPS. 인증서는 reverse proxy가 자동 발급 · 갱신한다(Let's Encrypt) |
| reverse proxy | **Caddy 1순위**(Ops §2-2 선택 원칙). app release와 분리된 host 인프라로 둔다(§13.5) |
| Web 정적 산출물 | API와 **같은 release revision**에 묶는다. `Web revision == API revision`(§13.6) |
| Security Group inbound | public **80 · 443만**. 22는 열지 않고 SSM을 유지한다. 3306 · 8000 공개 금지 |
| 주소 | ~~EC2 기본 public IPv4 + 무료 DDNS subdomain. DuckDNS 우선 검토~~ **EIP + DuckDNS subdomain. DDNS updater는 백업**(2026-10-31 RD-14a 갱신) |
| 검증 | SSM 성공 뒤 workflow에서 외부 DNS · TLS · Web · same-origin API smoke(§10.2) |

```text
Internet
→ DDNS hostname
→ Caddy HTTPS (host 인프라)
   ├─ Web static artifact (현재 release의 web, version.json 포함)
   └─ /cases* · /health* → 127.0.0.1:8000
```

주소 구성 순서(2026-10-31 RD-14a 갱신):

1. EIP 1개를 할당해 EC2에 연결한다. 팀 계정에 권한이 있다(AWS 환경 §11)
2. 무료 DDNS subdomain(DuckDNS)의 A record를 EIP로 등록한다. 주소를 손으로 입력하지 않고 EC2에서 updater를 1회 실행한다
3. Caddy + Let's Encrypt. 인증서 발급은 SG 80/443을 연 뒤에 성공한다
4. DDNS updater · timer는 백업이다. EIP를 해제하거나 잃으면 timer를 켜서 바뀌는 IP를 따라간다

승인 당시(2026-10-30) 순서는 「EC2 기본 public IPv4 → DDNS → Caddy → IP가 바뀌면 DDNS 갱신 → EIP는 DDNS로 부족할 때만 요청」이었다.

### 13.3 이 모델을 고른 이유

- **제출 요건.** 심사자가 URL로 접속해 끝까지 써 봐야 한다. SSM port forwarding은 팀원만 쓸 수 있다.
- **same-origin.** Web의 API client는 상대 경로(`baseUrl` 기본값 `''`, `apps/web/src/api/client.ts`)로 `/cases…`를 부른다. 개발 서버도 `/cases`를 API로 넘겨 같은 origin처럼 쓴다(`apps/web/vite.config.ts`). production에서 proxy가 같은 역할을 하면 CORS 설정과 API URL env가 필요 없다. API 경로는 모두 `/cases` 아래와 `/health/*`다.
- **Caddy.** TLS 발급 · 갱신을 앱에서 분리하고, single EC2의 운영 표면을 작게 유지한다(Ops §2-2).
- **EIP + DuckDNS(2026-10-31 갱신).** 승인 당시에는 EIP가 요청 대상이라 승인 시점을 예측할 수 없었고 안내도 엇갈려(AWS 환경 §9) DDNS를 우선했다. 2026-10-31 dry-run과 실제 할당으로 팀 계정에 권한이 있음을 확인했다(AWS 환경 §11). 공개 기간에는 팀원이 EC2를 다시 시작해도 주소 · DNS · 인증서가 그대로여야 하고, DDNS만으로는 재시작 뒤 갱신 · DNS 전파까지 접속이 끊길 수 있어 EIP를 붙인다. DuckDNS는 즉시 발급되고 A record를 지원하며 HTTP API로 갱신할 수 있어 그대로 쓴다. 공급자를 영구 SoT로 고정하지는 않는다(Ops §2-2).
- **80을 여는 이유.** 인증서 발급 검증과 HTTP → HTTPS redirect에 쓴다.
- **22를 닫는 이유.** `0.0.0.0/0` 개방은 보안 모니터링에 탐지되고(AWS 환경 §3), SSM으로 충분하다.

### 13.4 RD-14 항목별 상태

| 항목 | 상태 |
| --- | --- |
| 공개 모델(공개 체험 · same-origin · 로그인 없음 · SG 80/443만 · 22 · 3306 · 8000 비공개) | 추천값. 지금 승인할 수 있다 |
| Caddy 배치 원칙(app release 밖 host 인프라, §13.5) | 추천값. host package인지 container인지는 구현 PR |
| Web artifact lifecycle(`Web revision == API revision`, §13.6) | `NEEDS_CHANGE` — image · controller 코드 변경이 필요하다 |
| DDNS · TLS · SG 구성(§13.7) | 구현 · 운영 작업 필요 → 2026-10-31 수행: EIP · DuckDNS · TLS · SG 80/443, Caddy는 검증자 `/32`만 허용([실행 기록](experiments/2026-10-31-rt14-aws-real-e2e.md)) |
| EIP 사용(RD-14a) | 2026-10-31 Owner 결정. 근거는 §13.3 |
| 외부 smoke | `NEEDS_CHANGE` — RD-12h workflow post-SSM 단계(§10.2) |

Caddy와 Web 산출물은 lifecycle이 다르다. **Caddy 프로세스와 인증서 상태는 release와 무관하게 오래 사는 인프라**이고, **Web 정적 산출물은 release마다 바뀌고 API와 함께 rollback되는 release 산출물**이다. 아래 두 절을 섞어 읽지 않는다.

### 13.5 Caddy — app release와 분리된 host 인프라

**추천:** Caddy는 application release와 분리된 host-level infrastructure component로 둔다. release compose에 넣지 않는다.

- TLS 인증서 · ACME 상태를 app 배포마다 흔들 필요가 없다.
- controller는 service가 정확히 api · worker · migrate · mysql일 때만 render한다(`production_compose`). Caddy를 넣으려면 controller를 바꿔야 한다.
- app rollback 때문에 Caddy까지 다시 배포할 필요가 없다.
- 같은 EC2에서 바뀌지 않는 public ingress 역할을 한다. host network로 `127.0.0.1:8000`에 닿는다.

host package인지 별도 container인지는 구현 PR이 정한다. 둘 다 host 전체 변경이므로 §7.3 알림 규칙을 따른다. **이 「release 밖 고정」은 Caddy 프로세스 · 설정 · 인증서 상태에 대한 것이다. Web 산출물을 Caddy 설치 때 고정 복사한다는 뜻이 아니다.**

### 13.6 Web 정적 산출물 — API와 같은 release에 묶음

**불변식:**

```text
Web revision == API revision
```

Caddy 설치 때 production Web을 고정 복사하거나, app release와 별개로 최신 Web만 계속 서비스하는 구조는 추천하지 않는다. Web은 상대 경로로 같은 origin의 API를 부르므로(§13.3), 두 revision이 갈라지면 화면과 API 계약이 어긋날 수 있다.

**우선 후보 구조:**

```text
같은 source SHA
   ↓
production app image / release artifact
   ├─ backend
   └─ web/dist
        ↓
deploy
        ↓
/opt/daesingo/releases/<SHA>/web
        ↓
current Web pointer
        ↓
Caddy static serving
```

rollback에서도 API revision rollback과 Web 정적 revision rollback이 함께 일어난다.

**정확한 구현 방식은 아직 정하지 않는다.** 후보는 다음과 같다.

- production image 안에 `web/dist`를 넣는다. controller가 image에서 `compose.yaml`을 꺼내듯 `web/dist`를 꺼내 release directory에 둔다. image digest 하나가 API와 Web을 함께 식별한다.
- 별도 immutable Web artifact를 같은 SHA 또는 hash로 관리한다.
- 위 어느 쪽이든 host에서는 release directory에 Web 산출물을 두고 current/previous pointer를 바꾼다.

어느 방식을 고르든 다음을 만족해야 한다.

- Web 산출물을 source SHA 또는 hash로 식별할 수 있다.
- host `current` · `previous` release와 함께 움직인다. 이전 release의 Web 산출물은 rollback 대상으로 남아 있는 동안 지우지 않는다.
- API rollback과 Web rollback이 분리되지 않는다. pointer 전환은 deploy · rollback과 같은 controller 작업 안에서 한다.
- Caddy의 인증서 상태와 Web release 상태는 분리된다.
- **machine-readable revision marker를 둔다.** 기본안은 `web/dist/version.json`에 source commit SHA를 담는 것이다(예: `{"revision": "<40자 SHA>"}`). field 이름은 구현자가 일관되게 정한다. 외부 smoke 7d가 이것을 읽는다(§10.2).

**Web current pointer 전환 시점.** api · worker `start` 단계에서 바로 바꾸지 않는다. 새 API가 unhealthy인데 Web만 새 revision으로 노출되는 상태를 만들지 않기 위해서다.

```text
Web artifact staging (releases/<SHA>/web 배치 · 식별값 확인)
→ new API / Worker start
→ host 내부 검증(§10.1)
   revision/digest · live/ready · Worker process · 8종 등록 · provider 없는 DB smoke
→ 내부 검증 PASS
→ Web current pointer 원자적 전환
→ host current.json / previous.json 승격
→ dirty 제거
```

- 내부 검증이 실패하면 Web pointer는 이전 release를 가리킨 채 남는다. 그 사이 새 API가 떠 있을 수 있는 것은 지금 구현과 같다(§8.1). rollback 때도 같은 순서로 Web pointer를 대상 release로 되돌린다.
- **Web pointer와 `current.json`은 하나의 파일시스템 atomic transaction이 아니다.** pointer 전환 뒤 `current.json`을 기록하기 전에 process가 죽을 수 있다. 그래서 승격 단계 동안 `dirty.json`을 남기고, 승격이 끝나야 지운다.
- 다음 deploy · rollback 전에 controller(또는 operator)는 **Web current pointer · `current.json` · `previous.json` · dirty phase**를 서로 대조해 reconciliation한다. 넷이 같은 release를 말하지 않으면 진행하지 않는다.
- **marker 삭제는 복구가 아니다.** `dirty.json`만 지워 다음 작업을 열지 않는다.

### 13.7 DDNS · 인증서 · 업로드 경로 · 배포 창

| 항목 | 제약 · 추천 |
| --- | --- |
| DDNS 갱신 | token은 secret이다. repository에 커밋하지 않고(Ops §2-2) Parameter Store 또는 host 보호 파일로 둔다. boot 때와 주기적으로 갱신한다. 주기는 구현이 정하고, 갱신 실패는 외부 smoke가 잡는다. 2026-10-31부터 EIP를 연결해 updater는 백업이다. timer는 비활성으로 두고 EIP가 없어지면 켠다 |
| 인증서 상태 | ACME 계정과 인증서를 proxy 재시작 뒤에도 남게 보관한다. 반복 발급이 발급 한도에 걸리지 않게 하기 위해서다 |
| 업로드 경로 | proxy의 request body 크기 · timeout이 업로드 상한(B-U1 1 GiB · B-U3 · B-U4)과 Analysis 한도(#452)를 깎거나 우회하지 않는지 확인한다 |
| 배포 창 | 배포 중 api가 멈춘 동안 proxy는 오류를 낸다. 공개 기간의 배포 창은 미리 알린다. 점검 안내 화면은 후속 P2다 |

### 13.8 Web production build caveat

Web Owner의 별도 승인을 Gate blocker로 두지 않는다. 구현 리뷰에서 아래만 확인한다.

- **SPA fallback:** Web에는 client router가 없다. 화면은 query string(`?api` · `?api&case=<id>` · `?dev`)으로 고른다(`apps/web/src/App.tsx`). 깊은 경로 fallback이 필요 없다.
- **base path:** root(`/`)에서 서빙하면 Vite 기본 `base`로 충분하다.
- **API URL · env:** 상대 경로이므로 same-origin이면 env가 필요 없다. Vite `server.proxy`는 개발 서버 전용이므로 production에서는 proxy가 `/cases*`를 api로 넘긴다.
- **진입 화면:** query 없이 열면 mock fixture 시연 흐름(`DemoFlow`)이고, 실제 API 흐름은 `?api`다. `?dev`는 snapshot viewer다. 제출 URL을 어느 진입으로 둘지는 후속 이슈 P0 「샘플 · 사용 안내」에서 Web Owner와 정한다.
- **bundle 내용:** `data/mock/case` · `data/real/case` fixture가 bundle에 들어간다(`apps/web/src/contracts/fixtures.ts`). 이미 공개 저장소에 있는 파일이지만 공개 서비스 security review 때 함께 본다.

## 14. RT-14 범위와 공개 운영 hardening 경계

| RT-14가 직접 닫는다 | 후속 이슈로 넘긴다 |
| --- | --- |
| public endpoint · 공개 모델(§13) | 신규 분석 global admission · backlog guard |
| DNS · TLS · Caddy 설치 · 운영(§13.5) | abuse 대비 rate limit 필요 여부 |
| Security Group 80/443 | upload 동시성 · 크기 · request 크기 재점검 |
| 외부 smoke(§10.2) | asset streaming · 동시 download 보호 |
| 배포 · rollback 도구와 rehearsal | provider 비용 · 호출량 guard |
| restart policy · 로그 전송 · 보관 | 실제 개인 영상 업로드 허용 정책 · 외부 AI 처리 고지 |
| Worker 등록 · 상태 관측 | retention · purge · provider retention |
| Web 정적 산출물 revision 관리(§13.6) | 샘플 영상 · 사용 안내 · 진입 URL |
| | 최소 monitoring · alert(RD-13c alert) |
| | 공개 kill switch · 신규 분석 일시 중단 |
| | 외부 체험 load · capacity smoke |

**순서 경계.** 외부 smoke를 위해 80/443을 여는 순간 서비스는 공개된다. 그래서 후속 이슈의 **P0는 RT-14 구현을 막지 않지만, Security Group 개방(공개 시작) 전에 닫는다.** P1 · P2는 공개 뒤 실측과 함께 진행할 수 있다. 근거는 Ops §2-3 · §2-4다. 후속 이슈(제목 후보 「[ops/security] 최종 심사 공개 서비스 pre-deploy hardening」)는 초안만 있고 아직 만들지 않았다.

## 15. 미결로 남기는 것

정하지 않고 남긴다. 채우지 않는다.

- **OIDC trust 범위:** 운영진이 branch · environment 기준으로 좁혀줄 수 있는지에 대한 답. RT-14를 막지 않는 accepted risk다(§4.1 · §16.2).
- **policy 숫자:** `disk_reserve_bytes`(앞선 초안 후보 10 GiB, CONSERVATIVE · LOW) · `memory_reserve_bytes` · `packet_margin_bytes`(#452 실측) · `log_buffer_bytes`(앞선 초안 후보 4m). image · dump 크기와 첫 배포 실측 뒤 정한다.
- **메모리 여유:** swap 0 · 3.8 GiB에서 api · worker(OCR · ffmpeg) · mysql이 동시에 최고 사용량에 닿을 때의 OOM. capacity(RD-15) 범위다.
- **ECR 저장 비용 · image 크기 · lifecycle 규칙:** 첫 push 때 잰다(§5).
- **backup 보관 개수:** 첫 dump 크기를 잰 뒤 정한다(§8.3).
- **실제 영상 E2E 빈도:** release 후보 때 수동으로 한다는 것만 정했다(§10.1).
- **배포 시도 이력 기록 위치:** Runbook §7의 기록 항목을 어디에 남길지. 도구는 host 상태 파일과 Actions run만 남긴다(§6).
- **팀 알림 채널 · 형식:** §7.3 규칙의 실행 수단. 팀 운영 결정이다.
- **심사 종료 시점 · 제출 뒤 hotfix 허용 여부:** 공지에 없다. 카테캠 확인 대상이다(Ops §2-3 · §23).
- **RD-14 구현 세부:** Caddy가 host package인지 container인지(§13.5) · Web 산출물 전달 형식(§13.6) · DDNS 갱신 주기(§13.7) · 외부 smoke의 구현 위치(§10.2).

## 16. 구현 변경 요청

| # | 변경 | Gate | RT-14 blocker | 형태 |
| --- | --- | --- | --- | --- |
| 1 | workflow post-SSM 외부 smoke(7a ~ 7e)와 smoke만 다시 실행하는 경로(§10.2) | RD-12h · 14 | 예 | 코드 |
| 2 | release-bound Web artifact · `version.json` marker · 내부 검증 뒤 pointer 승격 · reconciliation(§13.6) | RD-14 | 예 | 코드 |
| 3 | Caddy host 인프라 설치 · 설정, DDNS 갱신, SG 80/443(§13.5 · §13.7) | RD-14 | 예 | 운영 · 설정 |
| 4 | rollback에서 develop tip gate 제거(§9.3-1). SSM 직접 실행은 break-glass로 runbook에 남김 | RD-12e | 예 | 코드 · 문서 |
| 5 | 최초 배포 실패 recovery runbook(§9.3-2) | RD-12e | 예 — 첫 AWS deploy 전 | 문서 |
| 6 | release 승인 checklist에 job payload 호환 확인과 full drain 조건(§8.2) | RD-12f | 예 | 문서 |
| 7 | controller 실패 단계를 고정 어휘로 출력(§7.2) | RD-12d | 아니오 — 권장 | 코드 |
| 8 | 배포 시도 이력 기록 위치(§15) | RD-12c | 아니오 — 권장 | 문서 |

### 16.1 코드 변경 지점

| # | 파일 · 함수 | 변경 |
| --- | --- | --- |
| 1 | `.github/workflows/rt14-deploy.yml` `remote` job | `python3 deploy/aws.py "$OPERATION"` 성공 뒤 외부 smoke step(deploy · rollback 모두). 공개 hostname · 대상 revision 입력. smoke만 다시 돌리는 경로(별도 operation 등) |
| 1 | `deploy/aws.py`(선택) · `tests/deploy/test_aws_deploy.py` | smoke 판정을 함수로 두면 7a ~ 7e 판정 회귀: 인증서 검증 실패 · `version.json` revision 불일치(이전 Web) · API 경로 404가 아닌 응답이 모두 실패인지, 출력이 비노출 규칙을 지키는지 |
| 2 | Web build(`apps/web` build 설정 또는 build script) | build 산출물에 `version.json`(source SHA) 생성 |
| 2 | `Dockerfile` · `.dockerignore` | image에 `web/dist`를 넣는 후보(§13.6 첫째)를 고르면 Web build stage와 `web/dist` 포함. Web fixture가 `data/mock/case` · `data/real/case`를 읽으므로 build context allowlist도 함께 |
| 2 | `deploy/ec2.py` `DockerHost.preflight` | release의 Web 산출물을 `/opt/daesingo/releases/<SHA>/web`에 staging하고 식별값(SHA · hash · `version.json`) 확인 |
| 2 | `deploy/ec2.py` `transition` | 내부 검증(`health` · `smoke`) **뒤**, `current.json` · `previous.json` 승격 **전**에 Web current pointer를 원자적으로 전환. `start` 단계에서 바꾸지 않음. 승격이 끝날 때까지 `dirty.json` 유지. deploy · rollback 시작 전에 Web pointer · `current.json` · `previous.json` · dirty phase reconciliation. `previous` release의 Web 산출물 보존 |
| 2 | `tests/deploy/test_ec2_deploy.py` | 내부 검증 실패 시 Web pointer가 바뀌지 않음 · pointer 전환 뒤 `current.json` 기록 전 중단 시 dirty가 남고 다음 deploy · rollback이 reconciliation 전에 거부됨 · deploy · rollback 뒤 Web pointer와 API revision이 같음 |
| 4 | `deploy/aws.py` `main` | `quality_gate(env)`를 `publish` · `deploy`에만 적용. `rollback`은 `trusted_context` · `RT14_EXECUTION_ENABLED`만 공통으로 받음 |
| 4 | `deploy/aws.py` `remote` | 변경 없음. rollback에도 `quality_gate(env, revision)`과 ECR digest 검사 유지 |
| 4 | `tests/deploy/test_aws_deploy.py` | tip CI pending · 실패에서 rollback 진행, deploy · publish는 거부 |
| 7 | `deploy/ec2.py` `main` · `transition` | 실패한 stage 이름만 고정 어휘로 출력(권장) |

`production_compose`의 4-service 제약은 바꾸지 않는다. Caddy는 그 밖에 둔다(§13.5).

### 16.2 infra risk · 운영진 확인 — RT-14를 막지 않음

| 항목 | 상태 | 처리 |
| --- | --- | --- |
| OIDC trust `sub` = repository 전체(`:*`) | accepted risk pending infra confirmation | 운영진에게 branch · GitHub Environment 기준으로 좁힐 수 있는지 묻는다. 답을 기다리느라 RT-14를 멈추지 않는다. 공식 workflow · develop guard · tip/target CI guard · 신뢰된 repository 쓰기 권한자 · 운영진 role 무수정을 조건으로 진행한다(§4.1) |

### 16.3 EC2 배포 실행을 실제로 막는 것

1. #450 Owner Gate 승인과 `decision_refs` 기록
2. rollback develop-tip gate 수정(§16.1-4)
3. 최초 deploy failure recovery runbook(§9.3-2)
4. release job compatibility checklist(§8.2)
5. 실제 OIDC 인증 acceptance(`rt14-oidc`)
6. ECR push(deploy role) · EC2 pull(instance role) acceptance
7. EC2 role의 Parameter Store fetch · 복호화 acceptance(안 되면 수동 파일 fallback)
8. host policy · 소유 volume · config · Log Group 준비
9. Web artifact lifecycle + Caddy · DDNS · TLS · SG 구현(§13.5 ~ §13.7)
10. workflow 단계 외부 smoke(§10.2)
11. 두 번째 정상 release 뒤 rollback rehearsal

1 ~ 8은 첫 내부 배포를 막는다. 9 · 10은 공개 production 배포 완료를 막는다. 11은 #450 종료를 막는다. OIDC trust 확인은 이 목록에 넣지 않는다(§16.2).

## 17. 스파이크 기록 — 2026-10-30

### 17.1 원칙

[Pre-implementation Spike 2026-10-03](./experiments/pre-implementation-spike-2026-10-03.md)과 같은 기준을 쓴다. 결과에 따라 추천값이 바뀔 수 있고 싸게 확인할 수 있는 것만 스파이크로 한다. 추천을 바꾸지 않는 확인은 acceptance로 넘긴다.

### 17.2 이미 확인한 것

| 확인 | 결과 | 영향받은 결정 |
| --- | --- | --- |
| AWS 권한 생성 → 삭제 시도(**SSO principal**) | ECR · Logs · SecureString 모두 PASS. deploy role · EC2 role 경로는 아님(§3.1) | RD-12b · 13a · 07c |
| SSM Run Command 실패 전달 | `sh`로 실행, 마지막 exit code만 반영 · `set -e`면 Failed | RD-12d — 구현은 controller `exec` 한 줄로 해결 |
| CI image build(2026-10-30 develop) | build + acceptance 약 8분 | RD-12b |
| rollback이 schema 경계를 넘을 때 | migration runner의 `unknown_revision` · 구현의 `rollback_targets` 검사로 결정 — 스파이크 불필요 | RD-12e |

### 17.3 실행한 스파이크 — 팀 EC2

EC2를 켜서 Docker를 설치(부록 A)한 뒤 실행했다. 앱 image · secret · ECR은 쓰지 않고 `busybox:1.36` · `curlimages/curl:8.10.1`만 썼다. 끝난 뒤 테스트 container · image · 임시 Log Group(retention 1일)을 지웠다. **스파이크 script는 마지막에 EC2를 중지했고, 이 동작이 같은 시간대의 다른 팀원 사용과 충돌했다(§3.4).** 이후 자동화에서는 전원을 다루지 않는다(Ops §2-1).

**SP-1 — compose 교체 순서.** 운영 구성과 같은 의존 구조(db healthy → `migrate` 완료 → api(healthcheck) · worker, api · worker는 `unless-stopped`)를 busybox로 만들고 `docker compose up -d --wait --wait-timeout 40`으로 교체했다.

| 시나리오 | `up` exit | 끝난 뒤 상태 | 결론 · #479 구현과의 관계 |
| --- | --- | --- | --- |
| S0 정상 | 0 | api healthy · worker running · migrate exit 0 | — |
| S1 `migrate` exit 1 | **1** | **이전 api · worker는 지워지고 새 api · worker는 `created`** | migrate 실패 = 서비스 중단. 구현은 writer를 먼저 멈추고 migrate를 `run --rm`으로 따로 돌린 뒤 성공했을 때만 api · worker를 띄운다 |
| S2 S1 뒤 정상 배포 | 0 | 모두 새 REV로 정상 | — |
| S3 api unhealthy | **1** | 새 api(unhealthy) · 새 worker가 **떠 있음** | 부분 교체 상태. 구현은 승격하지 않고 명시적 rollback 판단(§9) |
| S4 S3 뒤 정상 배포 | 0 | 정상 | — |
| S5 worker exit 1 | **0** | worker `running` · **RestartCount 1** | healthcheck 없는 서비스의 crash를 `--wait`가 못 잡는다. 구현은 RestartCount 0과 PID/starttime marker로 잡는다(§10.1) |

**SP-2 — `awslogs`.** container를 `--log-driver awslogs --log-opt mode=non-blocking --log-opt max-buffer-size=4m`으로 띄우고 JSON 한 줄 로그 3개를 남긴 뒤 지우고 다시 띄웠다.

| 확인 | 결과 |
| --- | --- |
| daemon이 instance role로 전송(hop limit 1) | PASS — 두 stream 모두 CloudWatch에 도착 |
| dual logging의 `docker logs` | PASS — 3줄 모두 출력 |
| container를 지운 뒤 CloudWatch 로그 | PASS — 지운 container의 stream이 그대로 남음 |
| Logs Insights JSON 필드 | **별도 확인** — Docker stream의 message가 JSON 한 줄 그대로임을 `get-log-events`로 봤고, 같은 문자열을 `put-log-events`로 넣은 별도 group에서 `fields event, n, rev \| filter event = "sp2.test"`가 2건을 필드 단위로 돌려줬다. Docker stream 대상 query는 결과 파싱 오류로 필드 값을 확보하지 못했다. end-to-end 실측으로 세지 않는다 |
| bridge container의 IMDS token | 응답 없음(`000`) · host는 200 — hop limit 1이 container를 막는다 |

### 17.4 하지 않는 것

| 후보 | 하지 않는 이유 |
| --- | --- |
| OIDC 실제 인증 | `rt14-oidc` workflow 실행이 곧 확인이다. acceptance |
| ECR push · pull 시간, image 크기 | 측정값이다. 대안(host build)이 더 나빠 추천이 바뀌지 않는다. 첫 배포 때 기록 |
| backup · restore | RT-13(b)에서 검증됨. 운영 크기는 acceptance |
| EBS snapshot 복원 | `CreateVolume` 거부로 대상 아님 |

## 18. 다음 순서 제안

1. **(완료)** #479 준비 구현 — OIDC · publish · SSM controller · rollback 도구 · 8종 marker.
2. **Gate 승인**(#450) — 이 문서 §1. 승인 근거 링크를 `policy.json` `decision_refs`에 넣는다.
3. **rollback tip gate 수정과 문서 보완** — §16의 4 · 5 · 6(rollback 코드 변경 · break-glass 경로 · 최초 배포 recovery runbook · 승인 checklist).
4. **RD-14 구현 PR** — Caddy host 인프라 · release-bound Web artifact · DDNS · SG · workflow 외부 smoke(§16의 1 · 2 · 3).
5. **첫 실행(코드 아님)** — Variable/Secret 등록 → `rt14-oidc` → host 준비(controller · 보호 디렉터리 · volume · config · Log Group) → publish → deploy → 두 번째 배포 → rollback rehearsal. 전원 조작 없음, 실행 전 팀 알림(§7.3).
6. **공개 운영 hardening 후속 이슈** — P0를 SG 개방 전에 닫는다(§14).

## 부록 A. host bootstrap 1단계 — Docker 설치 script

2026-10-30 팀 EC2에 SSM Run Command로 적용한 그대로다. 인자 없이 실행하면 그 시점의 최신 버전을 골라 고정하고 출력한다. 다시 실행해도 같은 버전이면 설치를 건너뛴다. 이번 적용 결과는 다음과 같다.

```text
pinned docker-ce=5:29.9.2-1~ubuntu.24.04~noble
pinned docker-compose-plugin=5.6.1-1~ubuntu.24.04~noble
docker.service: enabled / active
default log driver: json-file      ← host 기본값. RT-14는 바꾸지 않는다(§7.3)
```

RT-14 host 준비에서는 위 두 버전을 인자로 넘겨 실행한다. host 전체 변경이므로 실행 전에 팀에 알린다. 이 script는 EC2 전원을 다루지 않는다.

```bash
#!/usr/bin/env bash
# Host bootstrap step 1: Docker Engine + Compose plugin from Docker's official apt repo.
# Idempotent. Pins exact package versions; with no args it resolves the newest and prints them.
# Usage: bash bootstrap-docker.sh [DOCKER_VERSION] [COMPOSE_VERSION]
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

DOCKER_VERSION="${1:-}"
COMPOSE_VERSION="${2:-}"
KEYRING=/etc/apt/keyrings/docker.asc
# Docker release signing key fingerprint (docs.docker.com/engine/install/ubuntu)
EXPECTED_FPR=9DC858229FC7DD38854AE2D88D81803C0EBFCD88

if [ ! -s "$KEYRING" ]; then
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg >/dev/null
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o "$KEYRING.tmp"
  actual=$(gpg --show-keys --with-colons "$KEYRING.tmp" | awk -F: '/^fpr/ {print $10; exit}')
  if [ "$actual" != "$EXPECTED_FPR" ]; then
    echo "bootstrap: docker key fingerprint mismatch" >&2
    rm -f "$KEYRING.tmp"
    exit 1
  fi
  mv "$KEYRING.tmp" "$KEYRING"
  chmod a+r "$KEYRING"
fi

codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
echo "deb [arch=$(dpkg --print-architecture) signed-by=$KEYRING] https://download.docker.com/linux/ubuntu $codename stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq

[ -n "$DOCKER_VERSION" ] || DOCKER_VERSION=$(apt-cache madison docker-ce | awk 'NR==1 {print $3}')
[ -n "$COMPOSE_VERSION" ] || COMPOSE_VERSION=$(apt-cache madison docker-compose-plugin | awk 'NR==1 {print $3}')

installed=$(dpkg-query -W -f='${Version}' docker-ce 2>/dev/null || true)
installed_compose=$(dpkg-query -W -f='${Version}' docker-compose-plugin 2>/dev/null || true)
if [ "$installed" != "$DOCKER_VERSION" ] || [ "$installed_compose" != "$COMPOSE_VERSION" ]; then
  apt-mark unhold docker-ce docker-ce-cli docker-compose-plugin >/dev/null 2>&1 || true
  apt-get install -y -qq --allow-downgrades \
    "docker-ce=$DOCKER_VERSION" "docker-ce-cli=$DOCKER_VERSION" \
    containerd.io docker-buildx-plugin "docker-compose-plugin=$COMPOSE_VERSION" >/dev/null
fi
apt-mark hold docker-ce docker-ce-cli docker-compose-plugin >/dev/null

systemctl enable --now docker.service containerd.service >/dev/null 2>&1

echo "pinned docker-ce=$DOCKER_VERSION"
echo "pinned docker-compose-plugin=$COMPOSE_VERSION"
docker version --format 'engine={{.Server.Version}} api={{.Server.APIVersion}}'
docker compose version
echo "docker.service: $(systemctl is-enabled docker.service) / $(systemctl is-active docker.service)"
echo "default log driver: $(docker info --format '{{.LoggingDriver}}')"
```

`containerd.io` · `docker-buildx-plugin`은 고정하지 않았다. engine과 compose만 배포 동작에 직접 영향을 준다고 보고 고정했다. 필요하면 같은 방식으로 추가한다.

## References

- [Ops Spec](./ops-spec.md) §2 · §2-1 · §2-2 · §2-3 · §2-4 · §4-1 · §8 · §9 · §18 · §19 · §23
- [RT-14 실행 절차](./rt14-deployment.md) · [Deployment Runbook](./deployment-runbook.md)
- [Open Decision Register](./open-decision-register.md) RD-07 · RD-11 · RD-12 · RD-13 · RD-14
- [Provisional Baseline v0.1](./provisional-baseline-v0.1.md) B-O1 · B-H3 · B-H4 · B-W5 · B-L2 ~ B-L5 · B-U1 ~ B-U4
- [Research 03](./research/03-runtime-config-secret-cancellation-2026-10-03.md) · [Research 04](./research/04-deployment-observability-operations-2026-10-03.md)
- [AWS 환경](./official-inputs/aws-environment.md) §2 · §3 · §8 · §9 · §10
- [RT-13(a)](./rt13a-docker-compose.md) · [RT-13(b)](./rt13b-backup-restore.md) · [Local Runtime Environment](./local-runtime-environment.md)
- 구현: `.github/workflows/rt14-oidc.yml` · `.github/workflows/rt14-deploy.yml` · `deploy/aws.py` · `deploy/ec2.py` · `deploy/configure.py` · `docker/runtime.py` · `src/daesingo/worker/deployment_status.py`
- Docker: [awslogs driver](https://docs.docker.com/engine/logging/drivers/awslogs/) · [dual logging](https://docs.docker.com/engine/logging/dual-logging/) · [restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/)
