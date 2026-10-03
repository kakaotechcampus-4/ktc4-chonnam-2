# Research Result — Deployment / Observability / Operations

**Status:** Evidence — 외부 기술 조사 결과 · **Owner 검토 전**\
**Owner:** common/runtime — 김준영\
**Workflow step:** [`runtime-ops-workflow.md`](../runtime-ops-workflow.md) §4 Decision-driven 외부 기술 조사\
**Prompt:** [`prompts/04-deployment-observability-operations.md`](./prompts/04-deployment-observability-operations.md)\
**Decisions:** [RD-12](../open-decision-register.md#rd-12--deployment-pipeline-세부) (12b~12h) · [RD-13](../open-decision-register.md#rd-13--운영-관측-수단) (13a) · [RD-11](../open-decision-register.md#rd-11--ops-retention--cleanup) (11a)\
**조사 기준일:** 2026-10-03

> 이 문서는 Decision 근거이며 결정이 아니다. 내용은 Owner 검토를 거쳐 Spec · Contract · ADR로 옮겨질 때만 효력이 있다. 외부 자료의 숫자는 대신고 baseline이 아니다.

> 범위: EC2 1대 + Docker Compose (`api` · `worker` · `mysql`) baseline 내부의 배포·rollback·backup·logging 선택지 조사.\
> 아래 내용은 **Decision 추천이 아니라 선택지를 현실화하기 위한 근거**다. Kubernetes/ECS/RDS/ALB/추가 EC2 전환은 다루지 않았다.

## 1. Executive Summary

### Part A — Deployment

- **Verified fact:** ECR은 image를 registry에 보존하고 manifest digest로 식별할 수 있으며, tag immutability와 lifecycle policy를 지원한다. EC2는 instance role을 이용해 ECR 인증을 받을 수 있고 ECR authorization token은 12시간 유효하다. GitHub Actions는 OIDC JWT를 AWS의 임시 credential로 교환할 수 있다.\
  Evidence: https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html
- **Interpretation:** 따라서 `commit SHA tag + immutable digest`가 존재하는 registry-pull 방식은 rollback 시 “동일 commit을 다시 build”하는 과정과 분리된다. 반대로 EC2 host build는 이전 local image가 그대로 남아 있지 않으면 rebuild가 필요하며, mutable base image나 build 시점에 다시 해결되는 dependency가 있다면 같은 source commit만으로 byte-identical artifact를 보장하지 않는다. Docker도 mutable base tag가 이후 다른 digest를 가리킬 수 있음을 명시한다.\
  Evidence: https://docs.docker.com/build/building/best-practices/
- **Verified fact:** BuildKit cache는 host storage를 사용하며 prune/GC 대상이다. T3는 CPU credit model을 사용하고, Unlimited에서 baseline을 초과하면 surplus credit/추가 비용이 발생할 수 있으며 Standard에서는 credit 고갈 후 baseline으로 제한될 수 있다. 실제 T3 credit mode는 instance/account 설정에 따라 확인이 필요하다.\
  Evidence: https://docs.docker.com/build/cache/garbage-collection/
- **Daesingo implication:** 2 vCPU, 약 3.7 GiB usable RAM, 50 GiB 단일 root EBS에서는 host build가 `api`·`worker`·`mysql`과 CPU/RAM/disk/cache를 직접 경쟁한다. ECR pull도 image layer 저장·압축 해제와 network/disk를 사용하지만 image compilation/build cache는 EC2에서 발생하지 않는다. 이는 **RD-12b**의 trade-off다.
- **Verified fact:** SSM Run Command의 `AWS-RunShellScript`는 Linux 명령을 실행할 수 있고 `workingDirectory`, execution timeout 등을 가진다. Linux SSM Agent는 기본적으로 root 권한으로 명령을 실행한다. Run Command는 `Pending`, `InProgress`, `Success`, `Failed`, `DeliveryTimedOut`, `ExecutionTimedOut` 등의 상태를 반환한다.\
  Evidence: https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-command-ssm-plugin-reference.html
- **Verified fact:** shell command 전체가 성공했는지를 SSM이 자체적으로 transaction처럼 판정하는 것은 아니다. AWS 문서상 script의 **마지막 command exit code**가 Run Command 결과가 될 수 있어 앞 명령 실패가 후속 성공 명령에 가려질 수 있다.\
  Evidence: https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command-handle-exit-status.html
- **Interpretation:** SSM `Success`는 “배포 revision이 실제 서비스로 정상 동작한다”는 의미와 동일하지 않다. Compose container health/readiness와 외부 smoke가 별도 판정층으로 남는다. AWS도 `Success`가 실제 애플리케이션 목적 달성을 보증하지 않는 여러 경우를 문서화한다.\
  Evidence: https://docs.aws.amazon.com/systems-manager/latest/userguide/monitor-commands.html
- **Verified fact:** Compose `up`은 image/config가 변경된 service의 container를 recreate하며 mounted volume은 유지한다. `--wait`는 service가 `running` 또는 `healthy` 상태가 될 때까지 기다릴 수 있다. Compose는 multi-service recreate 전체에 대한 transactional rollback을 문서화하지 않는다.\
  Evidence: https://docs.docker.com/reference/cli/docker/compose/up/
- **Interpretation:** 따라서 `api` recreate 성공 → `worker` 또는 후속 health step 실패와 같은 **partial deployment**가 가능한 운영 상태로 취급되어야 한다. 이는 **RD-12d/e/h**와 연결된다.
- **Verified fact:** MySQL 8.4 atomic DDL은 지원되는 **개별 DDL statement**를 crash-safe하게 commit/rollback시키지만 transactional DDL을 제공하지 않으며 DDL은 implicit commit을 발생시킨다. 여러 DDL statement로 구성된 migration 전체가 atomic한 것은 아니다.\
  Evidence: https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html
- **Verified fact:** MySQL 8.4는 data dictionary upgrade가 필요한 경우 startup에서 자동 upgrade할 수 있다. 성공적으로 upgrade된 data directory에 대해 이전 8.4 patch나 8.3으로 server downgrade하는 것은 지원되지 않으며, 이전 버전으로 돌아갈 때의 공식 경로는 upgrade 전 backup 복원이다.\
  Evidence: https://dev.mysql.com/doc/refman/8.4/en/data-dictionary-schema.html
- **Daesingo implication:** application rollback과 DB rollback은 서로 다른 작업이다. 특히 MySQL image 자체를 upgrade하는 배포는 일반 `api/worker` image rollback과 같은 의미로 다룰 수 없다. **RD-12e/f/g**에 직접 연결된다.

### Part B — Logging

- **Verified fact:** Docker Engine의 default logging driver는 `json-file`이며, **기본값으로 log rotation이 켜져 있지 않다.** Docker는 disk exhaustion 방지를 위해 `local` driver를 별도 선택지로 설명한다.\
  Evidence: https://docs.docker.com/engine/logging/configure/
- **Verified fact:** `local` driver는 기본적으로 container당 약 100 MB의 log를 보존하는 rotation 구조(`20m × 5`, compression 기본 enabled)를 가진다. 이 숫자는 Docker 도구의 **기본값이지 대신고 retention baseline이 아니다.**\
  Evidence: https://docs.docker.com/engine/logging/drivers/local/
- **Verified fact:** Docker `awslogs` driver는 stdout/stderr를 CloudWatch Logs로 직접 전송한다. `non-blocking` mode에서는 memory ring buffer를 사용해 application log write가 logging backend에 직접 block되지 않게 하지만 buffer가 차면 새 log가 drop될 수 있다.\
  Evidence: https://docs.docker.com/engine/logging/drivers/awslogs/
- **Verified fact:** remote logging driver를 사용해도 Docker의 **dual logging** local cache 때문에 `docker logs`용 host-side cache가 존재할 수 있다. 기본 local cache에는 자체 rotation 한도가 있다. 따라서 “`awslogs`이면 host에 log가 전혀 없다”는 일반화는 맞지 않는다.\
  Evidence: https://docs.docker.com/engine/logging/dual-logging/
- **Verified fact:** unified CloudWatch Agent는 지정한 host files/journald 등을 읽어 CloudWatch Logs에 전달할 수 있으며 agent JSON config 및 Parameter Store 등으로 config를 관리할 수 있다. 변경된 config는 `fetch-config`와 agent restart/reload 절차의 대상이다.\
  Evidence: https://docs.aws.amazon.com/en_en/AmazonCloudWatch/latest/monitoring/create-cloudwatch-agent-configuration-file.html
- **Verified fact:** Docker는 `json-file` 및 `local` driver 내부 파일을 **Docker daemon만 접근하도록 설계된 파일**이라고 명시하며 외부 프로그램이 직접 조작하는 것을 경고한다.\
  Evidence: https://docs.docker.com/engine/logging/drivers/json-file/
- **Daesingo implication:** 따라서 “CloudWatch Agent가 Docker private log file을 직접 tail한다”는 구성은 기술적으로 경로를 지정할 수 있는 것과 Docker가 그 파일을 외부 consumer용 interface로 지원한다는 것이 동일하지 않다. 이 부분은 **RD-13a**에서 별도 failure/compatibility 검증 대상이다.
- **Verified fact:** CloudWatch Log Group을 생성하고 retention policy를 설정하지 않으면 log는 기본적으로 expire하지 않는다. retention은 Log Group 설정이며 Docker-side rotation과 독립적이다.\
  Evidence: https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html

---

## 2. Questions Investigated

### Q-A1 — ECR pull vs EC2 host build

조사 범위는 image revision 식별 방법, reproducibility, rollback artifact 보존 위치, EC2 build 자원 경쟁, T3 CPU credit, BuildKit cache, 배포 단계 구조, BuildKit provenance/SBOM, ECR 인증·tag immutability·lifecycle·비용, GitHub OIDC→ECR push, S3 image tar 전달 방식까지다.

### Q-A2 — SSM Run Command deployment

`AWS-RunShellScript`, 실행 권한/user와 working directory, timeout/status/exit code, Actions에서 command completion 판정, Compose recreate의 partial-state 가능성, healthcheck/`--wait`, restart policy, rollback revision 기록 위치, Compose file rollback, SSM output의 S3/CloudWatch 전송과 secret 노출을 조사했다.

### Q-A3 — MySQL container operation

named volume/bind mount 수명, `mysqldump`·MySQL Shell dump와 physical/EBS snapshot의 차이, online consistency, restore 단위, 동일 disk와 외부 저장소의 failure domain, restore verification, MySQL 8.4 data-directory upgrade/downgrade 제약을 조사했다.

### Q-A4 — Migration ordering

migration-first, deploy-first, expand-contract의 compatibility 조건, mixed api/worker version 상태, MySQL implicit commit/atomic DDL, multi-step migration failure, backup restore/forward fix/down migration, one-off container/separate migration service/application startup 실행 모델을 조사했다.

### Part B

다음 세 문제를 분리해 조사했다.

1. **Transport:** stdout/stderr를 CloudWatch까지 전달하는 주체.
2. **Rotation:** EC2 disk상의 log 파일/캐시 성장을 제한하는 주체.
3. **Retention:** CloudWatch 또는 host에서 과거 log를 얼마 동안 유지하는 정책.

비교 대상은 CloudWatch Agent file-tail, Docker `awslogs`, Docker `json-file`/`local` host-only이다.

---

## 3. Verified Technical Facts

### Part A

| Fact | Version / Condition | Evidence |
|---|---|---|
| Docker image는 digest로 content-addressable하게 참조할 수 있다. ECR `ImageDetail`은 image manifest의 `sha256` digest를 노출한다. | 현재 ECR / OCI-Docker image | https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_ImageDetail.html |
| Mutable base tag는 이후 다른 image를 가리킬 수 있다. digest pinning은 해당 base image identity를 고정한다. | Docker Build current docs | https://docs.docker.com/build/building/best-practices/ |
| BuildKit은 provenance/SBOM attestation을 생성할 수 있고 provenance에 VCS/source/material 정보를 넣을 수 있다. | BuildKit current | https://docs.docker.com/build/metadata/attestations/slsa-provenance |
| ECR authentication token은 12시간 유효하며 AWS IAM principal의 권한 범위를 따른다. Docker 자체에는 IAM authentication 기능이 없으므로 `get-login-password` 또는 ECR credential helper가 사용될 수 있다. | Amazon ECR private registry | https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html |
| ECR tag immutability를 설정하면 기존 immutable tag를 overwrite하려는 push가 `ImageTagAlreadyExistsException`으로 실패한다. | Current ECR | https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html |
| ECR lifecycle policy는 조건에 맞는 image를 expire할 수 있으며 실제 action은 조건 충족 후 수행된다. | Current ECR | https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle_policy_parameters.html |
| ECR 비용은 주로 repository storage와 일부 data transfer로 구성된다. 같은 Region의 ECR↔EC2 직접 전송은 $0/GB다. 공식 pricing 예시는 private image storage를 $0.10/GB-month로 제시하지만 region별 실제 가격 확인이 별도 필요하다. | 확인일 2026-10-03 | https://aws.amazon.com/ecr/pricing/ |
| GitHub Actions AWS OIDC에서는 workflow에 `id-token: write`가 필요하며 action이 GitHub JWT를 AWS credential로 교환한다. | Current GitHub Actions/AWS flow | https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws |
| BuildKit cache는 disk를 사용하며 GC/prune할 수 있다. | Current Docker BuildKit | https://docs.docker.com/build/cache/garbage-collection/ |
| T3는 CPU credit 기반이다. Unlimited/Standard 동작이 다르고 실제 credit specification은 API로 확인 가능하다. | EC2 T3 | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-standard-mode.html |
| `docker save`는 image와 tag를 tar archive로 만들 수 있고 `docker load`는 이를 복원한다. | Docker Engine current | https://docs.docker.com/reference/cli/docker/image/save/ |
| `AWS-RunShellScript`는 Linux shell command를 실행하며 working directory 및 timeout을 지정할 수 있다. | SSM Run Command current | https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-command-ssm-plugin-reference.html |
| Linux SSM Agent가 실행하는 명령은 기본적으로 root 권한으로 실행된다. | Linux managed node | https://docs.aws.amazon.com/en_en/systems-manager/latest/userguide/ssm-agent-restrict-root-level-commands.html |
| Run Command의 script exit status는 마지막 command의 exit status가 될 수 있다. | `aws:runShellScript` | https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command-handle-exit-status.html |
| Run Command에는 `DeliveryTimedOut`과 `ExecutionTimedOut`이 구분되어 있으며 `Success`/`Failed` 등 terminal status가 존재한다. | Current SSM | https://docs.aws.amazon.com/systems-manager/latest/userguide/monitor-commands.html |
| Run Command output은 S3 또는 CloudWatch Logs로 보낼 수 있다. 기본 SSM 결과 화면/API output은 24,000 characters까지만 반환한다. | Current SSM | https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-rc-setting-up-cwlogs.html |
| Run Command 실행 이력은 최대 30일 확인 가능하며 command에 plaintext secret을 넣지 말라고 AWS가 경고한다. | Current SSM | https://docs.aws.amazon.com/systems-manager/latest/userguide/running-commands.html |
| S3 command output write 권한은 EC2의 instance profile이 사용된다. | EC2 managed node | https://docs.aws.amazon.com/systems-manager/latest/userguide/running-commands-console.html |
| Compose `up`은 변경된 config/image의 container를 recreate하고 mounted volume은 보존한다. | Compose current | https://docs.docker.com/reference/cli/docker/compose/up/ |
| `docker compose up --wait`는 service가 `running` 또는 `healthy`가 되기를 기다린다. | 지원되는 Compose version | https://docs.docker.com/reference/cli/docker/compose/up/ |
| short-form `depends_on`은 dependency가 healthy할 때까지 기다리지 않는다. `condition: service_healthy`는 dependency healthcheck 통과를 기다릴 수 있다. | Compose current | https://docs.docker.com/reference/compose-file/services/ |
| restart policy는 `no`, `on-failure`, `always`, `unless-stopped`가 있으며 `on-failure`는 Docker daemon restart 자체 때문에 container를 재시작하지 않는다. | Docker Engine current | https://docs.docker.com/engine/containers/start-containers-automatically/ |
| Named volume은 container lifecycle 밖에 존재한다. `docker compose down`은 기본적으로 named volume을 제거하지 않고 `down -v`는 제거한다. | Docker/Compose current | https://docs.docker.com/engine/storage/volumes/ |
| Bind mount는 host path를 직접 container에 노출하며 host process가 내용을 수정할 수 있다. | Docker Engine | https://docs.docker.com/engine/storage/volumes/ |
| `mysqldump`는 SQL 기반 logical backup을 생성한다. | MySQL 8.4 | https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html |
| `mysqldump --single-transaction`은 InnoDB에 consistent snapshot을 사용할 수 있지만 dump 중 DDL 변경은 dump consistency/failure에 영향을 줄 수 있다. | InnoDB | https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html |
| MySQL Shell `dumpInstance`/`dumpSchemas`/`dumpTables`와 `loadDump`가 존재하며 parallel dump/load를 지원한다. 8.4 API의 `consistent` 기본값은 `true`. | MySQL Shell 8.4 | https://dev.mysql.com/doc/dev/mysqlsh-api-python/8.4/group__util.html |
| Physical backup은 raw database files에 가까운 형태이고 logical backup과 portability·restore 구조가 다르다. 실행 중인 DB 파일을 단순 복사하는 것은 consistency를 보장하지 않는다. | MySQL 8.4/InnoDB | https://dev.mysql.com/doc/refman/8.4/en/backup-types.html |
| EBS snapshot의 application consistency를 self-managed MySQL에서 보장하려면 I/O freeze/flush 같은 적절한 pre/post action이 필요하다. 실패 시 crash-consistent snapshot으로 fallback하는 구성도 존재한다. | Amazon EBS | https://docs.aws.amazon.com/ebs/latest/userguide/automate-app-consistent-backups.html |
| MySQL 8.4 atomic DDL은 개별 지원 DDL statement 단위다. DDL은 transactional group으로 묶이지 않고 implicit commit을 일으킨다. | MySQL 8.4 | https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html |
| MySQL online DDL도 metadata lock 대기나 disk/resource 문제 등으로 실패할 수 있다. | MySQL 8.4 | https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-limitations.html |
| MySQL data dictionary upgrade가 성공하면 이전 server binary로의 단순 downgrade는 일반적인 rollback 방식으로 지원되지 않는다. | MySQL 8.4 upgrade | https://dev.mysql.com/doc/refman/8.4/en/data-dictionary-schema.html |

### Part B

| Fact | Version / Condition | Evidence |
|---|---|---|
| Docker default logging driver는 `json-file`. 기본 config에는 automatic rotation이 없다. | Docker Engine current | https://docs.docker.com/engine/logging/configure/ |
| `json-file`은 stdout/stderr 각 entry를 `log`, `stream`, `time`을 가진 JSON record로 host에 저장한다. | Docker Engine | https://docs.docker.com/engine/logging/drivers/json-file/ |
| `local` driver는 stdout/stderr를 Docker 내부 file storage에 저장하며 rotation/compression을 기본 제공한다. 기본값은 `20m × 5`, compression enabled다. | Docker Engine current; 도구 기본값 | https://docs.docker.com/engine/logging/drivers/local/ |
| `json-file`과 `local` 내부 log 파일을 외부 tool로 직접 조작하지 말라고 Docker가 경고한다. | Docker Engine | https://docs.docker.com/engine/logging/drivers/json-file/ |
| Logging driver의 daemon-wide 기본값은 `/etc/docker/daemon.json`에서 설정할 수 있고 container별 설정도 가능하다. 기존 container는 daemon default 변경만으로 새 설정을 자동 적용하지 않는다. | Docker Engine | https://docs.docker.com/engine/logging/configure/ |
| `awslogs`는 stdout/stderr를 CloudWatch Logs로 전송한다. | Docker Engine awslogs | https://docs.docker.com/engine/logging/drivers/awslogs/ |
| `awslogs-create-group` 기본값은 false이며 존재하지 않는 group을 자동 생성하려면 추가 설정 및 `logs:CreateLogGroup` 권한이 필요하다. | Docker `awslogs` | https://docs.docker.com/engine/logging/drivers/awslogs/ |
| Docker daemon은 EC2 instance profile credential을 `awslogs` 인증에 사용할 수 있다. | EC2 + `awslogs` | https://docs.docker.com/engine/logging/drivers/awslogs/ |
| Remote logging driver와 함께 Docker dual logging cache가 활성화되면 `docker logs`용 local cache가 남는다. | 지원되는 remote driver | https://docs.docker.com/engine/logging/dual-logging/ |
| Logging delivery의 기본 mode는 `blocking`. `non-blocking` mode는 in-memory ring buffer를 사용하고 buffer가 가득 차면 log가 drop된다. | Docker Engine | https://docs.docker.com/engine/logging/configure/ |
| Unified CloudWatch Agent는 `logs_collected.files.collect_list.file_path`로 host file을 수집할 수 있다. | Current unified CWA | https://docs.aws.amazon.com/en_en/AmazonCloudWatch/latest/monitoring/create-cloudwatch-agent-configuration-file.html |
| CloudWatch Agent config는 host JSON 또는 Parameter Store 등을 사용 가능하고 변경 시 config fetch/restart가 필요하다. | Unified CWA | https://docs.aws.amazon.com/en_en/AmazonCloudWatch/latest/monitoring/create-cloudwatch-agent-configuration-file.html |
| `CloudWatchAgentServerPolicy` v3은 `PutLogEvents`, `PutRetentionPolicy`, `CreateLogStream`, `CreateLogGroup` 등을 포함한다. | AWS managed policy v3 | https://docs.aws.amazon.com/aws-managed-policy/latest/reference/CloudWatchAgentServerPolicy.html |
| CloudWatch Agent 상태는 command/SSM으로 확인할 수 있고 자체 operational log와 config-validation log를 가진다. | Unified CWA | https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/troubleshooting-CloudWatch-Agent.html |
| CloudWatch Logs Standard class는 JSON log field discovery를 지원한다. | CloudWatch Logs | https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_AnalyzeLogData-discoverable-fields.html |
| 새 Log Group은 retention을 지정하지 않으면 log가 expire하지 않는다. | CloudWatch Logs | https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html |
| Unified Agent config에서 `retention_in_days`를 설정할 수 있으며 이미 존재하는 group의 retention 변경에도 적용될 수 있다. | Unified CWA | https://docs.aws.amazon.com/en_en/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html |
| CloudWatch Agent가 만드는 **자기 자신의 agent log**에는 별도 built-in rotation이 존재한다. 이는 application log rotation 설정이 아니다. | Unified CWA | https://docs.aws.amazon.com/en_en/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html |

---

## 4. Options / Patterns

### Part A — artifact 전달 · 배포 sequence · backup · migration 순서

#### A-1. Artifact 전달 방식

| 축 | EC2 host build | ECR image pull | S3 image tarball |
|---|---|---|---|
| Revision identity | **Interpretation:** commit SHA를 source checkout과 image label/tag에 기록 가능. 다만 build artifact 자체가 host-local이다. | **Verified fact:** tag + registry digest 사용 가능. **Interpretation:** commit SHA tag와 digest를 함께 기록하면 human-readable revision과 exact artifact identity를 분리할 수 있다. | **Verified fact:** `docker save/load`가 image/tag를 전달. **Interpretation:** tar의 SHA256 및 metadata manifest를 별도로 보존하면 exact file identity를 만들 수 있다. |
| Reproducibility | **Interpretation:** source commit이 같더라도 mutable base/dependency resolve가 있으면 rebuild artifact가 달라질 수 있다. | CI에서 한 번 만든 artifact를 그대로 pull 가능. Rebuild가 아닌 기존 digest 재사용 가능. | 저장된 tar를 그대로 재사용하면 동일 artifact. tar가 삭제되면 rebuild 문제로 돌아감. |
| Rollback artifact | local old image가 prune되지 않았다면 재사용 가능. 없으면 rebuild 필요. | lifecycle policy가 image를 삭제하지 않은 동안 이전 digest를 다시 pull 가능. | 이전 tar가 S3에 남아 있어야 함. |
| EC2 build resources | Build CPU/RAM/cache/layer I/O가 production host에서 발생. | host에서는 pull/decompression/layer storage가 발생하지만 compile/build cache는 CI side. | download + tar temporary space + `docker load` layer storage. |
| Deployment duration 구조 | checkout/download source → base/dependency resolve → build → recreate | CI build/push는 deploy 전 단계 → EC2 authenticate/pull → recreate | CI build → save/compress → S3 upload → host download → load → recreate |
| Provenance | BuildKit attestation 생성 자체는 가능. local image store/export 방식에 따라 attestation 보존 방식 확인 필요. | registry에 provenance/SBOM attestation을 artifact와 함께 둘 수 있음. | tar 외부에 checksum/SBOM/provenance를 같이 관리하는 별도 convention이 필요할 수 있음. |
| Infra prerequisites | ECR repo 불필요. Git/source와 build dependencies 필요. | ECR repository + CI push IAM + EC2 pull IAM. | S3 bucket/prefix + CI write + EC2 read IAM. |
| Storage management | BuildKit cache + multiple local images가 50 GiB를 점유. | local pulled images도 누적되며 ECR에는 별도 registry storage가 생김. | S3 object + downloaded tar + loaded Docker layer가 일시적으로 중복 disk를 사용할 수 있음. |

**ECR-specific Verified facts**

GitHub Actions에서 `id-token: write` → AWS deploy role assume → ECR authentication → image build/push 흐름을 구성할 수 있다. EC2 side에서는 instance role 기반 ECR authentication/credential helper 또는 login token을 사용할 수 있다. Tag immutability와 lifecycle policy는 서로 별개 설정이다.

**Daesingo implication — RD-12b/c:**\
ECR 사용 여부와 별개로 최소 두 identity가 구분된다.

- source revision: Git commit SHA
- deployed artifact identity: Docker image digest 또는 이에 준하는 immutable artifact checksum

둘을 동일시할 수 있는지는 build inputs가 어느 정도 pin되어 있는지에 달려 있다.

---

#### A-2. SSM Run Command deploy sequence

다음은 **대표 흐름**이지 최종 sequence 선택안이 아니다.

```text
GitHub Actions
  └─ OIDC → AWS deploy role
       ├─ artifact 준비(build/push 또는 기존 artifact 확인)
       └─ ssm:SendCommand
            ↓
EC2 / SSM Agent
  └─ AWS-RunShellScript
       ├─ working directory/revision 준비
       ├─ artifact pull/load/build
       ├─ (선택된 순서에 따라 migration)
       ├─ docker compose up ...
       └─ local health/readiness check
            ↓
GitHub Actions
  ├─ command terminal status + ResponseCode 확인
  ├─ deployed revision 확인
  └─ 외부 smoke
       ↓
성공 판정 후 known-good metadata 갱신
```

**Verified fact:** `SendCommand`는 asynchronous command ID를 돌려주며 invocation status/response code를 조회할 수 있다. AWS CLI waiter 또는 polling으로 terminal state를 확인할 수 있다. SSM은 eventual consistency 특성도 문서화한다.\
Evidence: https://docs.aws.amazon.com/cli/latest/reference/ssm/get-command-invocation.html

**Interpretation:** shell script 내부에서는 앞 명령의 non-zero status가 반드시 최종 command failure로 전파되도록 구성할 필요가 있다. 예를 들어 fail-fast shell convention이나 각 단계의 explicit return-code check가 여기에 해당한다. 이는 AWS가 앞 command failure를 자동 aggregate해 준다는 의미가 아니다.

#### Partial deployment

**Verified fact:** `docker compose up`은 변경된 service를 recreate한다. Compose 문서에는 “전체 project를 하나의 transaction으로 recreate하고 실패 시 기존 project로 자동 복원한다”는 보장이 없다.

**Interpretation:** 다음 상태가 운영상 가능하다.

```text
api = new revision
worker = old revision or stopped
mysql = unchanged
deployment command = failed
```

또는 image pull은 끝났지만 container health가 실패하는 상태가 가능하다.

따라서 **RD-12e rollback**은 단순히 “SSM command 재실행”보다 어떤 service가 어느 revision인지 재확인하는 과정까지 포함할 여지가 있다.

---

#### A-3. Health/readiness와 external smoke

**Verified fact:** Compose healthcheck는 container 안에서 명령을 실행해 Docker의 `healthy/unhealthy` state를 만든다. `depends_on: condition: service_healthy` 및 `compose up --wait`는 이 상태를 사용할 수 있다.

**Interpretation:** 세 레이어는 서로 다른 질문에 답한다.

| Layer | 확인 가능한 것 | 확인하지 못하는 대표 예 |
|---|---|---|
| container running | process/container가 살아 있음 | DB/query/API 기능 정상 |
| Compose healthcheck/readiness | 정의된 local check 통과 | 외부 client 경로, 배포 orchestration 밖의 network 문제 |
| external smoke | 실제 외부 접근 경로의 핵심 요청/응답 | 전체 business workflow의 모든 failure |

따라서 대신고가 이미 정의한 “health/readiness + external smoke”는 중복 검사가 아니라 다른 failure boundary를 본다는 해석이 가능하다. **RD-12h**와 연결된다.

---

#### A-4. Restart policy

| Policy | Container process crash | Docker daemon restart | 수동 stop 이후 daemon restart |
|---|---|---|---|
| `no` | 자동 restart 없음 | 없음 | 없음 |
| `on-failure` | non-zero exit이면 restart | daemon restart만으로는 restart되지 않음 | 해당하지 않음 |
| `always` | restart | restart | daemon restart 시 다시 시작 가능 |
| `unless-stopped` | restart | restart | 명시적으로 stop돼 있었다면 시작하지 않음 |

**Interpretation:** restart policy는 crash recovery policy이지 application readiness나 deploy success 판정 수단은 아니다.

---

#### A-5. Known-good revision 기록 위치

| 위치 | Deploy 실패 후 | EC2/root disk 상실 후 | 특성 |
|---|---|---|---|
| Host file | 보통 남을 수 있음 | 같이 소실 가능 | 가장 단순하지만 host-local |
| SSM Parameter Store | host와 독립 | 남음 | parameter version도 존재. AWS-side state |
| GitHub Deployment status | host와 독립 | 남음 | deployment를 source `ref`/SHA와 연결하고 status 기록 가능 |
| ECR `known-good` 같은 tag | ECR에 남음 | 남음 | mutable tag라면 그 tag 자체는 historical identity가 아님. digest를 함께 보존할 수 있음. lifecycle expiry와도 관계됨 |
| GitHub Release/tag | host와 독립 | 남음 | source release identity에는 적합하지만 deployment success 자체는 별도 convention 필요 |

**Interpretation:** “known-good”은 *commit이 존재함*과 *실제 production 검증을 통과함*을 구분하는 상태다. 어느 저장소가 이 authoritative status를 가지는지는 외부 조사로 결정되지 않는다. **RD-12c/e** 내부 합의 항목이다.

#### Compose file rollback

**Interpretation:** service command, volume, env wiring, logging driver 등이 Compose revision 사이에서 변경됐다면 image만 이전 digest로 바꿔도 이전 runtime definition으로 돌아간 것이 아니다. 따라서 source-controlled Compose definition을 revision과 함께 되돌리는 pattern과 image-only rollback pattern은 구별된다.

`docker compose restart`는 Compose config 변경을 반영하는 명령이 아니다.

---

#### A-6. MySQL persistent storage

| 형태 | Verified fact | Operational interpretation |
|---|---|---|
| Named volume | container 삭제/recreate와 독립적인 Docker-managed volume. 일반 `compose down`으로는 제거되지 않음. | Docker가 lifecycle/path를 관리. 단, 이 EC2에서는 결국 같은 50 GiB EBS failure domain 안에 있음. |
| Bind mount | 특정 host path를 직접 mount. host process도 해당 files를 볼/변경할 수 있음. | backup tooling에서 path가 명시적이지만 ownership/permissions/host-side accidental modification도 함께 관리됨. |

둘 모두 **container writable layer와 분리된다는 것**과 **EC2/root EBS 장애와 분리된다는 것**은 다르다.

---

#### A-7. Backup 방식

| 축 | Logical dump | Cold/physical copy | EBS snapshot |
|---|---|---|---|
| 예 | `mysqldump`, MySQL Shell dump | MySQL 정지 후 data directory 보존 | EBS block snapshot |
| Consistency | `--single-transaction`/Shell consistent dump로 InnoDB point-in-time consistency 구성 가능. concurrent DDL 제약 존재. | 실행 중 단순 file copy는 consistency 위험. DB quiesce/stop/backup mechanism 필요. | 아무 조치 없는 snapshot은 application-consistent가 보장되지 않음. MySQL용 flush/freeze pre-script가 공식 지원 pattern. |
| Granularity | schema/table/database 단위 가능 | data directory 중심 | volume 단위 |
| Portability | 상대적으로 높음 | MySQL/version/platform 종속성 큼 | EBS/volume 구조에 종속 |
| Restore 구조 | SQL replay 또는 `util.loadDump()` | data files 복원 후 compatible server 기동 | snapshot→EBS volume 생성→필요 데이터 복구 |
| Performance 형태 | SQL decode/insert/index rebuild 비용 | raw files라 restore가 상대적으로 직접적 | block-volume restore |
| Backup size | SQL/dump representation; compression 가능 | raw DB files | first snapshot 이후 incremental storage |
| Same-disk 위험 | dump를 50 GiB root에만 놓으면 DB와 같은 failure domain | 동일 | snapshot은 AWS-side에 source volume과 독립적으로 보존 |
| Validation | dump load가 실제 가능해야 함 | server startup + integrity/application check | restored volume에서 MySQL/application validation |

**Daesingo implication — RD-12g:** logical backup file을 `/backup` 같은 같은 root EBS 디렉터리에 생성하는 것과 그 파일을 S3 등 host 밖으로 복사해 둔 것은 failure domain이 다르다. “backup command가 성공했다”와 “EC2 disk loss에서 복원 가능하다”는 같은 보장이 아니다.

---

#### A-8. Restore pattern

##### Logical dump

**Verified fact:** `mysqldump` SQL output은 mysql client로 reload할 수 있고 MySQL Shell dump는 `util.loadDump()`를 사용한다.

**Interpretation:** restore 검증에는 단순 import exit code 외에도 다음과 같은 단계가 구분될 수 있다.

```text
backup artifact readable
→ compatible MySQL starts
→ schema objects exist
→ representative DB invariants/query succeed
→ api/worker can read required runtime state
```

어떤 domain invariant를 검증할지는 대신고 내부 결정이다.

##### EBS snapshot

**Verified fact:** EBS snapshot은 source volume과 별도로 유지되고 snapshot에서 새 EBS volume을 생성할 수 있다. Application-consistent MySQL snapshot에는 적절한 pre/post scripts가 필요하다.

**Daesingo implication:** baseline은 root EBS 1개이므로 snapshot은 MySQL만이 아니라 OS/Docker/video/log 등 같은 block device 전체를 포함한다. “MySQL data만 어느 directory로 꺼내 복원할지” 혹은 “root volume 단위로 복원할지”는 restore spike에서 실제 절차 확인이 필요하다.

---

#### A-9. Migration ordering

##### Pattern 1 — Migration first

```text
old app
   ↓
new schema migration
   ↓
new app
```

**Interpretation:** migration 직후부터 new app 전환이 끝날 때까지 **old api/worker가 new schema에서 정상 동작**할 수 있어야 한다. Column/table drop/rename처럼 old code가 즉시 깨지는 migration은 이 조건과 충돌한다.

##### Pattern 2 — Deploy first

```text
new app
   ↓
new schema migration
```

**Interpretation:** new application이 migration 완료 전까지 **old schema에서도 동작**할 수 있어야 한다. 새 column/table을 startup 직후 반드시 필요로 하는 code는 이 조건과 충돌한다.

##### Pattern 3 — Expand → application transition → contract

```text
additive schema
      ↓
old + new app 모두 호환
      ↓
new app 전환
      ↓
이전 code 제거 확인
      ↓
old schema element contract/drop
```

**Interpretation:** mixed-version period를 허용하는 대신 migration 단계가 늘어난다. 이 pattern은 Compose가 transactional all-at-once rollout을 보장하지 않는 현실과 compatibility를 명시적으로 연결하는 방식이다.

##### MySQL failure semantics

예를 들어 migration이 다음 세 statement라면:

```sql
ALTER TABLE ...;   -- success
CREATE INDEX ...;  -- success
ALTER TABLE ...;   -- failure
```

**Verified fact:** 앞 두 DDL의 commit을 세 번째 failure와 함께 하나의 transaction으로 되돌리는 보장은 없다. Atomic DDL은 각 지원 statement 안에서의 atomicity다.

따라서 **Interpretation:** migration runner가 실패했더라도 DB는 “old schema 그대로”가 아니라 migration version 사이의 상태일 수 있다.

---

#### A-10. Migration 실행 단위

| 방식 | Verified/Interpretation | Partial-deploy 관계 |
|---|---|---|
| `docker compose run --rm <service> migration-command` | **Verified fact:** Compose는 service config를 재사용해 one-off command를 실행하는 `run --rm`을 지원하며 문서 예시에도 DB upgrade 작업이 등장한다. | application startup과 migration exit code를 별도 단계로 판정 가능 |
| dedicated `migration` service | **Interpretation:** Compose dependency와 one-shot service를 연결할 수 있음. | Compose config 자체에 migration lifecycle 포함 |
| application startup migration | **Interpretation:** process start와 schema mutation이 결합됨. api/worker가 동시에 migration logic을 가진 경우 serialization/idempotency가 별도로 필요 | restart policy나 container recreate가 migration invocation이 되는 효과가 생김 |

**RD-12f / RD-12a 영향:** 어느 execution unit을 채택하는지에 따라 Dockerfile/entrypoint와 Compose definition도 영향을 받을 수 있으므로 RD-12a 인접 항목이다.

---

### Part B — log transport · rotation · retention

#### B-1. 세 문제의 분리

```text
application stdout/stderr
        │
        ├── transport ──→ CloudWatch Logs
        │
        └── host-side logging/cache
                         │
                         └── rotation

CloudWatch Log Group
        │
        └── retention policy
```

`transport`, `rotation`, `retention`은 서로 대체 관계가 아니다.

---

#### B-2. 세 가지 대표 구성 비교

| 항목 | CloudWatch Agent file-tail | Docker `awslogs` | `json-file` / `local` host-only |
|---|---|---|---|
| stdout/stderr path | Docker driver가 먼저 host file에 기록 → Agent가 file 읽음 | Docker logging driver → CloudWatch Logs 직접 | Docker → host storage |
| Host/system log도 수집 | Agent가 `/var/log/...`, journald 등을 별도로 수집 가능 | container stdout/stderr가 주 대상 | 별도 수집 없음 |
| Structured JSON | 원본 application file이라면 JSON 유지 가능. Docker `json-file` 자체를 tail하면 Docker outer JSON 안 `log` field에 application JSON이 들어감 | application의 1-line JSON message가 CloudWatch event가 됨 | local `docker logs`에서는 원문 확인 가능 |
| Rotation owner | source file을 누가 만드는지에 따라 Docker/logrotate 등 별도 | remote driver 자체 + dual logging cache 여부 | `json-file`: explicit Docker rotation 필요. `local`: built-in rotation |
| CloudWatch retention | Log Group | Log Group | 해당 없음 |
| Host disk | source file + Agent own logs | Docker dual cache 및 image/daemon logs 등 가능 | 명시적으로 사용 |
| Network interruption | Agent가 전송을 재시도하는 collector layer | logging driver delivery path에 직접 영향 | remote transport 자체 없음 |
| IAM | Agent process → instance role | Docker daemon → instance role | CloudWatch IAM 불필요 |
| Failure visibility | Agent status/agent log | Docker daemon/logging driver errors | Docker daemon/`docker logs` |
| Config ownership | Agent config + AWS Log Group + source log rotation config | Compose `logging:` 또는 daemon config + AWS Log Group | Compose/daemon config |
| `docker logs` | source driver에 따라 가능 | dual logging cache가 enabled이면 가능 | 가능 |
| Deployment coupling | Agent 설치/config가 host configuration으로 존재 | Compose service config와 함께 versioning 가능 | Compose 또는 daemon-wide host config |

#### Structured JSON nuance

**Verified fact:** CloudWatch Logs Insights는 JSON event의 fields를 자동 발견할 수 있다.

**Interpretation:**

- `awslogs`로 application이 `{"event":"job_done","job_id":"..."}`를 한 줄에 출력하면 CloudWatch message 자체가 application JSON이라 field discovery가 단순하다.
- Docker `json-file` file을 CloudWatch Agent가 직접 tail하면 on-disk representation은 대략 Docker의 `{"log":"...","stream":"stdout","time":"..."}` envelope다. application JSON은 `log` string 내부에 들어갈 수 있으므로 Logs Insights에서 nested content를 추가 parsing해야 할 수 있다.
- 이 차이는 JSON이 “손실된다”는 뜻은 아니고 **CloudWatch event의 envelope 구조가 달라진다**는 의미다. 실제 query shape는 spike 대상이다.

---

#### B-3. Multi-line

**Verified fact:** `awslogs`는 multiline pattern/datetime parsing 설정을 제공하지만 Docker 문서는 multiline regex processing이 logging performance에 영향을 줄 수 있다고 경고한다.

Unified CloudWatch Agent도 multi-line start pattern 설정을 지원한다.

**Daesingo implication:** structured logging baseline이 one-event-per-line JSON이면 exception stack trace를 JSON field의 escaped newline로 넣을지 여러 physical line으로 내보낼지가 log pipeline behavior를 바꾼다. 이는 application logging format과 **RD-13a**의 접점이다.

---

#### B-4. Rotation

##### `json-file`

**Verified fact:** Docker default이며 default automatic rotation이 없다.

Docker daemon 또는 Compose service logging options에서 `max-size`/`max-file`을 설정할 수 있다.

**Daesingo implication — RD-11a:** 별도 rotation 설정 없이 default `json-file`을 두는 것은 50 GiB disk에서 log growth path 하나를 무제한 상태로 남긴다. 이것은 retention 기간을 몇 일로 할지와 별개 사실이다.

##### `local`

**Verified fact:** automatic rotation/compression을 기본 제공하며 기본 `20m × 5`로 약 100 MB/container를 보존한다.

이 값은 **Docker default**일 뿐 대신고가 채택할 log budget 또는 retention 값이 아니다.

##### External `logrotate`

Docker는 `json-file`/`local` internal log files를 daemon 전용으로 취급하고 외부 tool 직접 access/manipulation을 경고한다.

**Interpretation:** Docker-owned internal log에 일반 OS `logrotate`를 직접 적용하는 방식과 Docker logging driver 자체의 rotation option은 동일 수준의 supported interface로 볼 수 없다.

---

#### B-5. Remote `awslogs`와 host disk

**Verified fact:** Docker remote logging driver는 `docker logs` compatibility를 위해 local dual logging cache를 사용할 수 있다. Docker 문서의 기본 cache 설정은 local driver를 사용하며 제한된 여러 파일로 rotate된다.

따라서:

> **Interpretation:** `awslogs` = “container stdout이 host disk를 0 byte 사용”은 성립하지 않는다.

다만 `json-file`에 rotation 없이 모든 로그를 host에 쌓는 것과는 growth behavior가 다르다.

---

#### B-6. Blocking vs non-blocking delivery

**Verified fact:** Docker logging delivery의 default mode는 `blocking`. `non-blocking`은 per-container in-memory ring buffer를 사용하며 buffer가 가득 차면 이후 message가 drop된다.

따라서 trade-off는 다음과 같다.

```text
blocking
CloudWatch/log driver 지연
        ↓
stdout/stderr write backpressure 가능
        ↓
application 영향 가능

non-blocking
CloudWatch/log driver 지연
        ↓
memory buffer
        ↓ full
log drop 가능
```

**Interpretation:** application availability와 log completeness 중 어느 failure mode를 허용할지가 설정 의미의 핵심이며, buffer 크기 수치는 실제 log량 측정 없이 대신고 baseline으로 만들 수 없다.

---

#### B-7. Restart / outage semantics

##### `awslogs`

Docker daemon이 전송 주체다. CloudWatch/network 문제에서 blocking/non-blocking mode에 따라 application 영향 또는 drop 특성이 달라진다. `docker logs`는 dual logging cache availability에 영향을 받는다.

##### CloudWatch Agent

**Verified fact:** current unified Agent는 상태 조회와 자체 error log를 제공한다.

**Unverified boundary:** 현재 unified Agent 공식 사용자 문서에서 임의의 Docker log rotation, agent crash, network outage 조합에 대해 **exactly-once/no-loss/no-duplicate를 보장하는 문구는 확인하지 못했다.** 이 보장은 전제하지 않는 편이 근거에 맞다.

##### Host-only

Remote network outage 때문에 log transport가 실패하는 경로 자체는 없지만, host/root EBS 장애가 곧 log 상실 failure domain이다.

---

#### B-8. IAM

##### CloudWatch Agent

현재 `CloudWatchAgentServerPolicy` v3에는 다음 CloudWatch Logs actions가 포함된다.

`logs:PutLogEvents`, `logs:PutRetentionPolicy`, `logs:DescribeLogStreams`, `logs:DescribeLogGroups`, `logs:CreateLogStream`, `logs:CreateLogGroup`.

**Daesingo implication:** 주어진 baseline상 이 managed policy가 instance role에 이미 있으므로 Agent transport에 필요한 기본 AWS-side permission의 상당 부분은 존재한다. 하지만 Agent software 설치/config 자체는 아직 없다.

##### `awslogs`

Docker daemon이 instance profile credentials를 사용할 수 있다. Log Group 자동 생성까지 driver에 맡길 경우 `CreateLogGroup` permission이 필요하다.

**Daesingo implication:** 실제 instance role이 `awslogs`가 사용할 CloudWatch Logs permissions도 가지고 있는지는 policy attachment/effective permission 확인 대상이다. `CloudWatchAgentServerPolicy`가 이미 attached돼 있다는 사실만 보면 위 actions는 포함되어 있다.

---

#### B-9. Retention

**Verified fact:** 새 CloudWatch Log Group에 retention policy가 없으면 logs는 expire하지 않는다.

Retention은 다음 위치 중 하나에서 관리될 수 있다.

- CloudWatch Log Group/IaC/API `PutRetentionPolicy`
- Unified CloudWatch Agent의 `retention_in_days`
- 별도 provisioning script

Agent config에서 retention을 지정하면 Agent IAM에 `logs:PutRetentionPolicy`가 필요하다.

**Interpretation:** retention setting을 Agent에게 소유시키는지 AWS resource provisioning이 소유하는지는 configuration ownership 문제다. 보관 **기간 값 자체**는 이번 조사 범위 밖이다.

---

#### B-10. CloudWatch Logs 비용 구조

**Verified fact:** CloudWatch Logs 비용은 사용 형태에 따라 log ingestion, archived storage, Logs Insights data scanned 등의 dimension을 가진다. 공식 pricing page는 Region별 가격이 다름을 명시한다. 확인일의 US East (N. Virginia) 예에서는 Standard log ingestion에 **$0.50/GB**가 사용된다. 이는 서울 Region baseline 가격이 아니다.

현재 공식 pricing 예시에는 archived log storage에 GB-month 단위가 사용된다. Logs Insights도 query가 scan한 data 양을 기준으로 과금되는 구조다.

**Unresolved:** 이번 조사에서 AWS의 동적 pricing 표로부터 **2026-10-03 Asia Pacific (Seoul)의 ingestion/storage/Logs Insights 세 항목 정확한 단가를 신뢰성 있게 추출하지 못했다.** 따라서 US region 숫자를 서울 대신고 비용으로 환산하지 않았다.

ECR 역시 저장된 private image 용량 기준 비용이 있으며 같은 Region EC2↔ECR 직접 data transfer는 무료다.

---

## 5. Failure Modes / Operational Risks

### Part A

| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
|---|---|---|---|
| Same commit rebuild ≠ same artifact | mutable base/dependency resolution | rollback artifact가 과거와 달라질 수 있음 | immutable image digest, dependency/base pinning, retained artifact로 identity 강화 가능 |
| Host build resource contention | production EC2에서 build | api/worker/mysql CPU·RAM·I/O 경쟁 | build timing/cache/resource 실측 또는 off-host prebuilt artifact와 비교 가능 |
| Build cache disk exhaustion | BuildKit/image cache 누적 | 50 GiB root pressure, DB/video/log에도 영향 | cache size 확인·GC/prune 정책 검증 |
| T3 CPU credit depletion/surplus | build가 baseline 초과 CPU 지속 사용 | Standard이면 throttling, Unlimited이면 surplus 비용 가능 | actual credit mode와 metrics 확인 |
| ECR rollback image expired | lifecycle policy가 old image 삭제 | known-good digest를 pull 못 함 | lifecycle policy와 rollback retention convention 연동 가능 |
| SSM false-success script | 중간 명령 실패 후 마지막 명령이 0 | Actions가 성공으로 판단 | script exit propagation 검증 |
| SSM timeout | delivery 또는 command execution timeout | 배포 중단, 일부 step 완료 가능 | 두 timeout을 분리해 관측하고 post-state 확인 |
| Partial Compose deployment | service 일부 recreate 후 후속 실패 | api/worker mixed revision | 실제 container image/digest를 재조회한 뒤 rollback/forward recovery |
| Health passes but service unavailable externally | healthcheck 범위가 좁음 | deploy success 오판 | external smoke를 별도 gate로 둘 수 있음 |
| `depends_on` misunderstanding | short form만 사용 | mysql 시작 직후 아직 ready 전 application 실행 가능 | health condition semantics 확인 |
| Known-good host file loss | EC2/root EBS loss | rollback pointer 소실 | AWS/GitHub 같은 host-external metadata location 선택 가능 |
| Compose definition not rolled back | image만 이전 digest로 변경 | old image + new runtime config 조합 | runtime definition revision까지 rollback 범위에 포함 여부 결정 |
| Named volume accidentally deleted | `down -v`, 수동 volume delete | MySQL data loss | destructive command boundary/backup 검증 |
| Inconsistent file backup | running MySQL data dir 단순 copy | unusable/inconsistent backup | logical consistent dump 또는 DB-aware quiesce/physical backup |
| Crash-consistent EBS snapshot only | MySQL I/O freeze/flush 없이 snapshot | application-level consistency 미보장 | application-consistent snapshot spike |
| Backup shares root disk | dump만 같은 50 GiB에 저장 | disk loss와 backup 동시 상실, capacity pressure | host-external copy와 비교 |
| Backup exists but restore fails | backup artifact만 생성하고 restore 미검증 | 실제 incident 때 복구 불가 | isolated restore rehearsal |
| Migration partially applied | multi-statement DDL 중 후속 실패 | schema intermediate state | forward fix, explicit down path, backup restore 등의 복구경로 사전 정의 |
| Old app incompatible with new schema | migration-first + destructive change | mixed version 동안 old process failure | backward-compatible migration 단계 |
| New app incompatible with old schema | deploy-first | migration 전 new process failure | new app compatibility/feature gate |
| MySQL image downgrade attempted | data dictionary upgrade 완료 | 이전 image가 data dir를 못 열 수 있음 | pre-upgrade backup restore 또는 supported upgrade path |
| Rollback also fails | old artifact missing/config mismatch/schema incompatible | 서비스 복구 지연 | known-good artifact + config + schema compatibility를 서로 독립 확인 |

### Part B

| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
|---|---|---|---|
| Unbounded `json-file` | default rotation 그대로 | root disk 소진 | Docker-native rotation 또는 다른 driver option 비교 |
| “CloudWatch이니 local disk 없음” 가정 | `awslogs` + dual logging cache | 예상 외 host disk 사용 | actual driver/cache config inspect |
| Logging backend stalls app | blocking driver + CloudWatch/network delay | stdout write/application 지연 | blocking/non-blocking trade-off 검증 |
| Logs dropped | non-blocking ring buffer full | observability gap | log rate/buffer behavior spike |
| Log Group missing | `awslogs-create-group=false` + group 없음 | container logging initialization/start failure 가능 | provisioning ownership 결정 |
| Agent stopped/misconfigured | config/path/IAM/network 문제 | CloudWatch 수집 중단 | Agent status + local agent logs |
| External tail of Docker private log | Agent/logrotate가 Docker-managed files 직접 취급 | unsupported interference 가능성 | Docker warning 고려, spike/alternative path 비교 |
| Nested JSON query inconvenience | Agent가 Docker `json-file` envelope를 전송 | application fields가 top-level로 바로 discovery되지 않을 수 있음 | Logs Insights parse test |
| Multiline split incorrectly | stack trace physical lines + pattern mismatch | 한 event가 여러 records로 분리 | one-line JSON 또는 multiline rules 검증 |
| CloudWatch retention unset | Log Group 기본 상태 | remote logs indefinite retention | retention policy owner를 별도 결정 |
| CloudWatch unavailable | remote transport path outage | mode에 따라 block/drop/delay | failure injection/spike |
| Host-only logging + host loss | EBS/instance failure | operational logs 소실 | remote transport 선택지와 trade-off |
| Agent config drift | host config가 deploy artifact와 별도 관리 | 재생성/수정 후 behavior 달라짐 | config source/version ownership 결정 |
| Daemon-wide config drift | `/etc/docker/daemon.json` 수동 변경 | container별 behavior 불일치 | host config revisioning 여부 결정 |
| Existing container keeps old logging config | daemon default 변경 후 recreate 안 함 | 기대와 실제 driver mismatch | recreate/inspect로 확인 |

---

## 6. Daesingo-specific Implications

### Part A

#### RD-12b — Artifact 전달

**Daesingo implication:** 비교의 핵심은 단순 “build 속도”보다 다음 네 failure boundary다.

```text
artifact identity
host resource competition
rollback artifact survival
artifact storage ownership
```

Host build에서는 BuildKit cache와 build peak가 이미 50 GiB/2-vCPU host에 들어온다. ECR에서는 ECR repository 생성 승인이 추가 external input이다. S3 tar 방식은 registry 없이 immutable artifact를 외부 보관할 수 있으나 tar/checksum/lifecycle convention이 별도로 필요하다.

#### RD-12c — Tag/digest/known-good

`commit SHA`, image digest, “production validation 성공”은 서로 다른 정보다.

```text
commit SHA          = source identity
image digest        = exact built artifact identity
known-good status   = 실제 deploy + health + smoke 결과
```

어느 system을 authoritative record로 삼을지는 내부 합의 대상이다.

#### RD-12d — SSM commands

SSM의 대표 operational boundary는:

```text
Actions credential success
≠ SendCommand accepted
≠ shell script successful
≠ Compose health successful
≠ external smoke successful
```

각 단계가 별도 실패 지점이다.

#### RD-12e — Rollback

Application rollback은 최소 다음 세 축이 있다.

1. 이전 image/artifact.
2. 이전 Compose/runtime definition.
3. 현재 DB schema와 old application의 compatibility.

DB schema 자체는 이미 baseline상 자동 rollback 대상이 아니므로 **application rollback이 항상 완전한 runtime rollback을 뜻하지 않는다.**

#### RD-12f — Migration

`api`와 `worker`가 잠시 다른 revision일 가능성을 배제하지 않는다면 migration ordering은 mixed-version compatibility 문제와 직접 연결된다.

MySQL atomic DDL을 이유로 multi-statement migration 전체 rollback을 전제할 수 없다.

#### RD-12g — Backup

50 GiB root EBS 1개에서는 named volume도, bind mount도, 같은 disk의 dump file도 **같은 physical failure/capacity domain**이다.

logical dump의 “DB-level 복원”과 EBS snapshot의 “volume-level 복원”은 서로 다른 목표다.

#### RD-12h — Health

`Compose --wait`는 useful deploy signal이지만 external smoke와 동일하지 않다. 대신고의 성공 정의에 이미 양쪽이 포함돼 있으므로 구현에서는 두 판정 결과를 별도로 기록할 수 있다.

### Part B

#### RD-13a — Log transport

세 선택지의 가장 큰 구조 차이는 collector ownership이다.

```text
CloudWatch Agent
application → Docker file → host collector → CloudWatch

awslogs
application → Docker daemon → CloudWatch

host-only
application → Docker daemon → host
```

현재 대신고 instance role에는 CloudWatch Agent 권한이 있지만 Agent executable/config는 아직 없으므로 Agent 방식에는 **host installation/configuration lifecycle**이 추가된다.

`awslogs` 방식은 Compose service의 logging config와 AWS Log Group provisioning이 연결된다.

#### RD-11a — Rotation/retention

두 설정은 동일 파일에 있지 않을 수 있다.

```text
host rotation:
  Docker daemon.json / Compose logging options

CloudWatch retention:
  Log Group / PutRetentionPolicy / Agent config

Agent's own internal log rotation:
  CloudWatch Agent 자체 built-in
```

따라서 “CloudWatch retention을 설정했으니 50 GiB local disk growth도 제한된다”는 결론은 성립하지 않는다.

---

## 7. What External Research Cannot Decide

### 내부 합의가 필요한 것

- RD-12b: host build / ECR / S3 tar 중 어느 artifact path를 채택할지.
- RD-12c: commit tag와 digest naming convention, authoritative known-good 기록 위치.
- RD-12d: 실제 deploy script의 단계와 누가 상태를 write하는지.
- RD-12e: rollback 범위가 image만인지 Compose revision까지인지.
- RD-12f: migration-first/deploy-first/expand-contract 중 각 migration별 compatibility discipline.
- RD-12g: logical dump, EBS snapshot 등을 어떤 복구 목표에 연결할지.
- RD-12h: health/readiness endpoint와 external smoke가 검증할 business operation.
- RD-13a: Agent/`awslogs`/host-only 중 transport ownership.
- RD-11a: log retention 값, host-side log budget.

### 실측이 필요한 것

- EC2 host Docker build 시 CPU/RAM peak.
- build 시간과 ECR pull 시간.
- BuildKit/image cache 증가량.
- 현재 T3 CPU credit mode와 build 중 credit 변화.
- image size.
- 평시/peak application JSON log byte rate.
- `awslogs` blocking 시 network failure가 실제 application latency에 주는 영향.
- non-blocking mode에서 필요한 buffer와 drop 발생 조건.
- MySQL dump 시간·dump size·restore 시간.
- EBS snapshot에서 실제 MySQL restore 절차.
- Compose `--wait` 및 실제 healthcheck 동작.
- mixed api/worker revision에서 schema compatibility.
- Docker `json-file`→Agent→CloudWatch를 쓸 경우 Logs Insights JSON query shape.

### External Input이 필요한 것

- ECR repository 신규 생성 가능 여부.
- CloudWatch Log Group 신규 생성 및 naming/retention ownership.
- 현재 EC2 instance role의 최종 effective IAM permissions.
- 필요 시 S3 backup prefix/bucket write policy.
- AWS 운영 측에서 허용되는 EBS snapshot 관리 방식.

---

## 8. Suggested Pre-implementation Checks

Decision을 대신하지 않고 사실을 확인하기 위한 작은 spike 기준으로 정리하면 다음과 같다.

| Spike | 확인하는 RD | 관찰값 |
|---|---|---|
| GitHub OIDC → `SendCommand` → harmless command → Actions terminal 판정 | RD-12d | command ID, status, response code, timeout/failure propagation |
| Shell step 2에서 의도적으로 실패 후 step 3 성공 | RD-12d | 전체 Run Command가 실제로 실패 처리되는지 |
| api/worker 중 하나를 의도적으로 unhealthy하게 한 `compose up --wait` | RD-12d/h | Compose exit code와 partial container state |
| 현재 image digest/SHA를 container에서 조회 | RD-12c | runtime에서 revision을 단일 command로 확인 가능한지 |
| known-good artifact로 실제 rollback 1회 | RD-12e | image + Compose + schema까지 필요한 단계 |
| `mysqldump` 또는 Shell dump → 신규 empty MySQL에 restore | RD-12g | backup size, dump/load success, domain query |
| EBS/MySQL application-consistent snapshot restore rehearsal | RD-12g | root-volume baseline에서 실제 restore sequence |
| migration 두 번째 DDL을 의도적으로 실패 | RD-12f | schema intermediate state와 migration runner behavior |
| actual MySQL patch image upgrade rehearsal | RD-12e/f/g | data-directory upgrade log와 rollback boundary |
| 현재 `docker info`/`docker inspect` logging config 기록 | RD-13a/11a | default driver, service-specific options, dual cache |
| one-line JSON → `awslogs` → Logs Insights | RD-13a | field discovery/query shape |
| one-line JSON → `json-file` → Agent → Logs Insights | RD-13a | Docker envelope/nested JSON query shape |
| logging destination network failure test | RD-13a | blocking latency / non-blocking drop visibility |
| bounded log generation | RD-11a | actual rotation files 및 disk behavior |

여기서 나온 size/time/rate는 구현 환경 실측값이며, 외부 문서의 예시 숫자를 대신고 baseline으로 가져오는 것이 아니다.

---

## 9. Unresolved / Unverified

1. **Docker Compose 실제 설치 version:** 현재 docs의 `--wait` 등 사용 가능 여부는 EC2에 설치할 exact Compose release로 확인할 필요가 있다. 특히 최신 Compose에 추가된 일부 lifecycle 기능을 “Compose v2 어디서나 존재”한다고 전제하지 않았다.
2. **T3 credit mode:** `t3.medium`이라는 instance type만으로 현재 instance가 Standard인지 Unlimited인지 확정할 수 없다. AWS API/instance setting 확인이 필요하다.
3. **Unified CloudWatch Agent의 exact delivery guarantee:** arbitrary file rotation + agent restart + network outage 조합에 대한 exactly-once/no-loss/no-duplicate 보장을 current unified-Agent 공식 문서에서 확인하지 못했다. 따라서 그러한 보장을 Verified fact로 적지 않았다.
4. **Docker internal JSON file 직접 tail:** CloudWatch Agent는 arbitrary file을 tail할 수 있지만 Docker는 `json-file` 내부 file의 external access를 경고한다. 이 조합을 AWS와 Docker가 end-to-end 공식 integration으로 보증한다는 문서는 확인하지 못했다.
5. **Seoul CloudWatch Logs 정확한 현재 단가:** AWS 공식 pricing page의 Region별 dynamic table에서 2026-10-03 `ap-northeast-2`의 ingestion/storage/Logs Insights 정확한 세 단가를 이번 조사 결과에 안정적으로 추출하지 못했다. N. Virginia 공식 예시 가격은 서울 가격으로 사용하지 않았다.
6. **MySQL storage engine:** `--single-transaction` 및 Shell consistent dump의 강한 consistency 설명은 InnoDB table 전제다. 대신고 schema 전체가 InnoDB인지 구현 시 확인이 필요하다.
7. **MySQL exact patch pin:** `mysql:8.4`처럼 floating LTS tag를 쓸지 `8.4.x` exact patch를 쓸지는 주어진 정보에 없다. 이 선택은 data-directory upgrade/rollback 검증과 직접 연결된다.
8. **EBS snapshot 복원 단위:** root EBS 1개 구조에서 entire root volume rollback과 MySQL data extraction 중 실제 운영 절차는 external docs만으로 대신고에 맞게 확정되지 않는다.

---

## 10. Sources

모두 **2026-10-03 확인**, 별도 표기가 없는 경우 현재 공식 온라인 문서다.

### Docker / Compose

- Docker — Configure logging drivers\
  https://docs.docker.com/engine/logging/configure/
- Docker — JSON File logging driver\
  https://docs.docker.com/engine/logging/drivers/json-file/
- Docker — Local file logging driver\
  https://docs.docker.com/engine/logging/drivers/local/
- Docker — AWS CloudWatch Logs logging driver\
  https://docs.docker.com/engine/logging/drivers/awslogs/
- Docker — Dual logging\
  https://docs.docker.com/engine/logging/dual-logging/
- Docker — Start containers automatically\
  https://docs.docker.com/engine/containers/start-containers-automatically/
- Docker Compose — docker compose up\
  https://docs.docker.com/reference/cli/docker/compose/up/
- Docker Compose — Services\
  https://docs.docker.com/reference/compose-file/services/
- Docker — Volumes\
  https://docs.docker.com/engine/storage/volumes/
- Docker — Bind mounts\
  https://docs.docker.com/engine/storage/bind-mounts/
- Docker — Build attestations\
  https://docs.docker.com/build/metadata/attestations/
- Docker — Build cache garbage collection\
  https://docs.docker.com/build/cache/garbage-collection/

### AWS ECR / GitHub OIDC

- Amazon ECR — Registry authentication\
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html
- Amazon ECR — Preventing image tags from being overwritten\
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html
- Amazon ECR — Lifecycle Policies\
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html
- Amazon ECR Pricing\
  https://aws.amazon.com/ecr/pricing/
- GitHub Docs — Configuring OIDC in AWS\
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws

### AWS Systems Manager / EC2 / EBS

- AWS Systems Manager — Run Command\
  https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html
- AWS Systems Manager — Running commands on managed nodes\
  https://docs.aws.amazon.com/systems-manager/latest/userguide/running-commands.html
- AWS Systems Manager — CloudWatch Logs for Run Command\
  https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-rc-setting-up-cwlogs.html
- Amazon EBS — Application-consistent snapshots with Data Lifecycle Manager\
  https://docs.aws.amazon.com/ebs/latest/userguide/automate-app-consistent-backups.html
- Amazon EBS — How pre/post scripts work\
  https://docs.aws.amazon.com/ebs/latest/userguide/script-flow.html

### MySQL 8.4

- MySQL 8.4 Reference Manual — mysqldump\
  https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html
- MySQL 8.4 Reference Manual — Using mysqldump for Backups\
  https://dev.mysql.com/doc/refman/8.4/en/using-mysqldump.html
- MySQL Shell 8.4 — Utilities\
  https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-shell-utilities.html
- MySQL 8.4 Reference Manual — Atomic Data Definition Statement Support\
  https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html
- MySQL 8.4 Reference Manual — Statements That Cause an Implicit Commit\
  https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html
- MySQL 8.4 Reference Manual — InnoDB Online DDL Operations\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html

### CloudWatch

- CloudWatch Agent — Configuration file details\
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html
- CloudWatch Agent — Create configuration file\
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/create-cloudwatch-agent-configuration-file.html
- CloudWatch Agent — Troubleshooting\
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/troubleshooting-CloudWatch-Agent.html
- AWS managed policy — CloudWatchAgentServerPolicy\
  https://docs.aws.amazon.com/aws-managed-policy/latest/reference/CloudWatchAgentServerPolicy.html
- CloudWatch Logs — CreateLogGroup\
  https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html
- Amazon CloudWatch Pricing\
  https://aws.amazon.com/cloudwatch/pricing/

---

**Completion check:** RD-12b~h, RD-13a, RD-11a에 필요한 artifact identity/reproducibility/rollback, SSM failure와 partial deployment, MySQL backup·restore·upgrade, migration compatibility/DDL failure, 그리고 logging의 transport·rotation·retention·disk·restart·IAM·configuration ownership까지 근거를 연결했다. 최종 artifact path, rollback source-of-truth, backup 조합, migration 순서, logging transport 및 retention 값은 확정하지 않았다.
