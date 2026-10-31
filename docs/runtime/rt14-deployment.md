<a id="rt-14--ec2-deployment-preparation"></a>

# RT-14 — EC2 배포 준비

**IN_PROGRESS · Refs #450 · Related #287, #460, #452**

이 문서는 [deployment runbook](deployment-runbook.md)의 구현 명령을 제공한다.
배포/복구 명령은 **향후 승인된 운영 작업의 예시**다. 이번 구현에서 실행하지 않았다.
아래 candidate는 Owner 결정이나 production acceptance를 대신하지 않는다.
2026-10-30 Decision Gate 승인값과 이 준비 구현에 남은 변경은 [RT-14 배포 설계](rt14-deployment-design.md) §1 · §16이다.

## 2026-10-31 후속 운영 기준

승인 후 구현·현재 운영 명령·최초 실패 복구·pointer reconciliation·Caddy/DDNS/TLS·
외부 smoke는 [공개 배포·복구 Notes](rt14-public-deployment.md)를 우선 사용한다.
아래 §1~§10은 #479 당시의 구현·검증 이력을 보존한다. 당시의 「후보/미승인」,
「rollback tip CI 의존」, 「recovery 없음」은 현재 상태로 읽지 않는다.
승인된 Gate는 재개방하지 않으며 OIDC trust 축소 답변은 코드 구현 blocker가 아니다.

운영자 제공 UID·재부팅·사본 정리 후속은 [실험 기록 §14](experiments/2026-10-31-rt14-aws-real-e2e.md#14-운영자-제공-후속-조치),
운영 크기 DB/media backup과 전용 빈 target 복원 준비는 [복구 acceptance 절차](rt14-recovery-acceptance.md)를 따른다.
약 4GiB 호스트의 dump 메모리/격리 예산과 heads를 확인하기 전에는 기존 smoke나 큰 dump를 실행하지 않는다.
이번 후속 준비에서는 AWS·서비스 정지·backup/restore를 실행하지 않았다.

## 1. 확인된 근거와 준비 범위

| 구분 | 근거 / 상태 |
| --- | --- |
| 저장소 시작 | `codex/rt14-deployment`, HEAD/fetched develop `4876e646171ba9f0195de52d11741f3c39fb51a0`; index/worktree clean |
| 선행 PR | #473, #474, #475, #476, #477 모두 merged; 현 코드의 FFmpeg 8.1 pair, production Paddle/cache, safe error_type, 실행환경, AnalysisSource 한도와 대조 |
| 캠퍼스 제공 | 첨부 AWS/OIDC/도메인/내부 운영 가이드 4개 직접 읽음. 기존 EC2 t3.medium, Ubuntu 24.04, 50GB encrypted root, 서울; SSO/MFA·SSM·OIDC 경로라는 **자료상 사실** |
| 실제 계정 | 이번 작업에서 접근/권한/role 연결/SSM/agent/ECR/S3/로그 리소스를 조회하지 않음 |
| 관측 | 2026-10-30 KST 사용자 브라우저 SSM 관측은 [AWS 입력 §9](official-inputs/aws-environment.md#9-2026-10-30-kst-사용자-관측)를 참조. 과거 10-02 조회와 별도 |
| 미결 | Register RD-12b~f/h, RD-13a/c/d, RD-11a와 실제 RD-07c 권한은 미확정. 입력을 요구하는 candidate 구현만 준비 |

최소 경로는 trusted develop CI → Linux amd64 공통 image → ECR immutable
revision tag와 digest → SSM 고정 host controller → MySQL → one-shot migrate →
API/Worker → health/8종 등록/read-only smoke → known-good이다. EC2에서 build하지 않는다.
S3로 대형 archive를 복사하지 않으며, application image가 자신의 Compose source를 포함한다.
host controller 자체는 별도로 검토·설치하고 배포 도중 자동 교체하지 않는다.

ECR은 큰 FFmpeg/Paddle 이미지를 서버에서 반복 build하지 않기 위한 **구현 후보**다.
CloudWatch `awslogs` + dual local cache 역시 RD-13a/11a의 승인 대기 후보다.
선택하면 추가 log agent가 필요하지 않으나 daemon instance-role 권한과 실제 수신 검증이 필요하다.
Owner가 다른 log transport를 선택하면 해당 adapter를 바꾸고 재검증한다.
restart는 `no` 또는 `unless-stopped`를 Owner가 명시해야 하며 기본 production 값은 없다.
health 실패를 Docker restart가 자동 복구하는 것으로 취급하지 않는다. alert/idle-heartbeat 정책도 미확정이다.

## 2. 실제 작업을 막는 입력

| 입력 / 결정 | 제공·검증 주체 | 막는 단계 |
| --- | --- | --- |
| RD-12/13/11 정책 승인 근거, 내부 smoke 허용, restart 선택 | Runtime/Ops Owner | host policy 검증 / 운영 acceptance |
| 계정·기존 deploy role·trust `aud`/실제 `sub`, region/guardrail | 개인 SSO로 인프라 담당과 확인 | OIDC / publish / SSM |
| 정확한 기존 EC2·instance-role 연결, SSM Online, Run Command 권한 | 인프라 담당·운영자 | SSM 원격 실행 |
| ECR repository URI·immutable tag 설정·수명 정책 | 인프라 담당 + Runtime/Ops | image publish/pull |
| 기존 MySQL 8.4 amd64 digest·mysql numeric UID, 소유 volume 이름/label | 운영자 | host preflight / 데이터 보존 |
| root-owned controller와 private 디렉터리·AWS CLI v2·Compose 사용 가능 | 운영자; 설치는 별도 승인 작업 | host preflight |
| SecureString 경로 3개와 실제 instance-role GetParametersByPath/KMS 권한, 또는 수동 보호 파일 | 인프라 담당 + 설정 소유자 | config 공급 |
| production runtime.env의 Search credential/model 쌍과 Recording 필수 그룹 | 각 모듈 Owner | deploy-config |
| Analysis profile/encoding, MAX_BYTES, MAX_DURATION_MS, DB packet 여유 | Recording + Runtime/Ops, 실제 22개 원본/측정 설정 제공자 | Worker 배포 acceptance / deploy-config·packet |
| CloudWatch group, retention 일수, buffer bytes, 수신/권한 | Runtime/Ops + 인프라 담당 | awslogs preflight / 로그 acceptance |
| 메모리·disk reserve bytes, 2개 known-good image+candidate·DB/media/log/backup working set | Runtime/Ops, EC2 실측 | capacity preflight / 운영 acceptance |
| revision별 config ID·schema 호환 rollback_targets·일관된 DB/media backup_reference | Runtime/Ops + migration 변경 Owner | migration/rollback 승인 |
| 공개 Web 경로·현재 인증/IDOR 검수·TLS 필요성 | PM + Web/API/Case Owner | 외부 사용자 공개만 |

기존 `ktc-github-deploy` 사용 가능성을 먼저 확인한다. `ktc-ec2-ssm-role`도 자료상
이름이며 실연결은 pending이다. 운영진 관리 IAM/trust를 수정하지 않는다. 별도 역할이
필요하면 아래 action/resource 및 사유를 제출하고 운영진 판단을 받는다.

확인된 GitHub repository는 `kakaotechcampus-4/ktc4-chonnam-2`, immutable ID는
`1340154683`, organization ID는 `287968646`이다(2026-10-30 GitHub 읽기 조회).
OIDC 실제 발급 subject/현재 trust는 조회하지 않았다. 첨부의 **타 팀 subject는 복사하지 않는다**.
기본 ref subject와 캠퍼스 immutable-ID 형식, environment 사용 시 subject 차이를
인프라 담당이 비공개로 대조해야 한다. 이 workflow에는 environment를 임의 추가하지 않았다.
workflow의 develop/ID 검사는 IAM trust를 대신하지 않는다. 다른 branch/PR이 역할을
얻을 수 있는 넓은 trust라면 enable 전에 운영진과 해결해야 한다.

`AWS_ACCOUNT_ID`는 가이드대로 Variable에 공급 가능하지만 값/등록 여부는 pending이다.
이메일/계정/전체 ARN/SSO URL/resource ID/IP/DNS/env/토큰은 Git·Issue·PR·Actions log에 쓰지 않는다.
배포 image URI와 instance ID는 아래 workflow에서 Secret으로 받아 공개 step 출력을 피한다.
로컬 운영자는 개인 SSO, Actions는 OIDC, host CLI와 Docker log daemon은 instance role이다.

## 3. IAM 확인에 필요한 최소 범위

이 표는 권한 요청 명세이며 현재 권한을 확인했다는 뜻이 아니다.

| 주체 | action | resource 경계 / 이유 |
| --- | --- | --- |
| Actions OIDC | `sts:AssumeRoleWithWebIdentity` | 기존 role의 신뢰 정책, 정확한 repo/ref/audience 확인 |
| Actions 검증 | `sts:GetCallerIdentity` | 기대 account와 정확한 assumed-role 비교만; JSON 출력 금지 |
| Actions ECR | `ecr:GetAuthorizationToken` | API 요구에 따른 `*`; 인증 token은 내부에서 password-stdin |
| Actions ECR | `ecr:DescribeRepositories`, `ecr:DescribeImages`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`, `ecr:BatchGetImage` | 승인된 repository만; immutable tag 및 digest publish/검증 |
| Actions SSM | `ssm:SendCommand` | AWS-RunShellScript 문서와 **지정된 기존 instance**만; tag fleet/broad instance 범위 금지 |
| Actions SSM | `ssm:GetCommandInvocation` | 해당 command 결과 조회(API가 지원하는 resource scope는 운영진과 대조); stdout/stderr 수집 안 함 |
| EC2 ECR | `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchCheckLayerAvailability` | token 외에는 지정 repository pull만 |
| EC2 config | `ssm:GetParametersByPath`, 필요한 `kms:Decrypt` | 승인 prefix만, recursive=false; CMK 사용 시 해당 key/context로 제한 |
| EC2 logging | `logs:DescribeLogGroups`, `logs:CreateLogStream`, `logs:PutLogEvents` | group 조회 API scope와 승인 group의 stream 범위; group 생성/retention 변경은 도구가 하지 않음 |

Actions에는 `ssm:GetParameter*`/KMS/env secret을 주지 않는다. EC2 프로세스는
SSO/Actions credential을 상속하지 않도록 AWS 설정 파일과 credential env를 비운다.
Docker daemon의 credential source/IMDS 접근은 실제 host에서 별도 검증한다.
공식 참고: [ECR push IAM](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html),
[SSM IAM 예시](https://docs.aws.amazon.com/systems-manager/latest/userguide/security_iam_id-based-policy-examples.html),
[GitHub AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

### 실제 담당자의 비공개 읽기 확인 순서

1. 개인 SSO/MFA로 AWS 콘솔에 로그인하고 서울 리전을 선택한다. EC2의 **기존 팀
   instance**를 식별한다. ID/IP/DNS나 콘솔 화면 전체를 공개 채널에 붙이지 않는다.
2. IAM → Roles → `ktc-github-deploy`의 Trust relationships, Permissions, Maximum session
   duration을 읽는다. `aud`, 실제 repo의 `sub` 형식과 develop 제한, 위 IAM action/resource,
   1시간 요청 수용 여부를 대조한다. 읽기 자체가 차단되면 운영진에게 대조를 요청한다.
   이 작업에서 trust/role을 편집하지 않는다.
3. EC2 → 해당 instance → Security의 IAM role 연결과 Systems Manager → Managed nodes의
   Online 상태를 확인한다. instance role의 ECR/config/log 권한과 guardrail은 인프라 담당에게
   확인한다. 10-02 snapshot이나 역할 이름만으로 현재 권한을 판정하지 않는다.
4. ECR → Repositories에서 승인된 repository와 immutable tag 설정, CloudWatch → Log groups에서
   group/retention을 읽는다. 없으면 생성하지 말고 담당자에게 필요한 범위·이유를 전달한다.
   Parameter Store는 승인 prefix의 이름/타입/암호화 metadata를 확인하고 값을 출력하지 않는다.
5. EC2 → Connect → Session Manager에서 아래 **읽기 전용** 항목을 확인한다. 원문 결과는
   내부 운영 기록에만 남긴다. 이 코드 작업에서는 아래 명령도 실행하지 않았다.

```sh
uname -m
free -h
df -h /
sudo docker version
sudo docker compose version
sudo docker system df
sudo docker ps --all
sudo ss -ltnp
```

그 뒤 Owner가 정책/용량/backup·schema/Recording 운영값을 승인하고 운영자가 아래 보호
파일·controller·리소스 입력을 준비한 후에만 manual 인증/publish/deploy 순서로 진행한다.

## 4. 보호된 host 준비와 config

아래는 **별도 운영 승인 이후**의 host 준비 계약이다. 이번에 패키지/서비스/파일을
EC2에 설치하거나 secret을 등록하지 않았다. `ubuntu`는 docker socket 접근이 거부된
관측이 있어 운영자는 SSM에서 필요한 `sudo`를 명시한다. socket 권한을 넓히지 않는다.

1. 승인된 revision의 `deploy/ec2.py`, `deploy/configure.py`를 개인 SSO/SSM으로 전달한다.
   GitHub의 승인 SHA와 로컬/host SHA-256을 비공개로 대조한다. 자동 `curl | sh` 없음.
   controller는 `/opt/daesingo/controller/`의 root 소유, 일반 사용자 쓰기 불가 파일이다.
   변경 때마다 동일 검토를 거친다. SSM RunShellScript의 실제 root 실행도 확인한다.
2. `/opt/daesingo`, `configs`, `approvals`를 root 소유 0700으로 준비한다.
   `policy.example.json`은 **의도적으로 실행 불가**다. 승인된 값을 host의
   `/opt/daesingo/policy.json`에 root 소유 0400으로 작성한다. null/빈 값/pending은 거부된다.
3. `project` 이름이 다른 서비스와 겹치지 않는지 확인한다. Docker가 비어 보였다는
   관측만으로 host의 다른 서비스를 없다고 가정하지 않는다. 8000 loopback 충돌도 확인한다.
4. DB/media external volume 두 개를 명시적으로 선택한다. 도구는 volume을 생성·삭제·
   초기화하지 않는다. `com.daesingo.owner=<policy.project>`,
   `com.daesingo.purpose=mysql|media` label 및 소유·데이터·mount를 확인한다.
   기존 unrelated volume에 임의 label을 붙여 소유권을 주장하지 않는다. 다른 project가
   잡은 volume, known-good 기록이 없는 기존 project는 자동 인수하지 않는다.
5. 기존 MySQL 8.4의 **확인한 amd64 registry digest**를 `mysql_image`에 적고 미리 준비한다.
   이 도구는 MySQL을 pull/upgrade하지 않는다. 실제 mysql UID를 확인해 `mysql_uid`에 적는다.

Parameter Store 선택 시 prefix 아래 **정확히 3개 SecureString**을 운영자가 준비한다.
`runtime-env`는 canonical guide의 runtime.env 전체 내용, `mysql-password`와
`mysql-root-password`는 각 password 한 개다. 앱 파일 내용은 shell eval/export하지 않는다.
`configure.py`는 EC2 instance role로 수집하고 별도 신규 config ID에 원자적으로 게시한다.
중복 ID/누락/빈 값/평문 String/예상 밖 parameter는 거부한다.

```sh
# EC2 SSM, 향후 승인 이후. 경로/ID만 argv에 둔다.
sudo /usr/bin/python3 /opt/daesingo/controller/configure.py --config-id '<new-config-id>'
```

권한이 없다면 Session Manager에서 동일 계약의 파일을 수동 배치하는 RD-07 fallback을
쓴다. 디렉터리는 root 0700, `runtime.env`는 UID10001 0400, MySQL 파일 두 개는 실제
mysql UID 0400이다. Docker daemon이 파일을 bind하고 컨테이너가 정확한 UID로 읽는다.
파일 symlink·쓰기 허용·빈 파일은 거부한다. 기존 config ID는 덮어쓰지 않는다.
암호화 at rest·로그 비노출과 별개로 Docker/root 권한자는 파일을 읽을 수 있다.

파일 키/secret 소비 서비스는 [canonical guide](local-runtime-environment.md)와
`.env.example`를 따른다. DB URL의 password는 app password와 일치해야 하며
`mysql/daesingo`, 사용자 `daesingo`만 허용한다. media/temp는 `/media`, `/media/api-temp`,
`/media/worker-temp`다. 새 config는 API/Worker **recreate**로 반영한다. restart로 대체하지 않는다.
기존 DB에서 MySQL password 파일을 바꾸는 것만으로 DB 사용자 password가 교체되지 않는다.
실제 credential rotation은 별도 DB 변경·일관성·rollback 계획이 필요하다.

## 5. CI publish와 SSM 실행

일반 regression/mysql/test CI와 required-check 의미는 유지한다. 두 새 workflow는
`workflow_dispatch`만 사용한다. OIDC 권한은 해당 job에만 있고 PR/fork에서 실행하지 않는다.
checkout v4.3.1을 공식 tag ref로 확인한 commit에 pin했다. credential action은 사용하지 않는다.
`deploy/aws.py`가 GitHub OIDC endpoint → 임시 0600 JWT 파일 → captured STS를 처리하고
파일을 제거한다. 임시 credential은 같은 프로세스와 자식 AWS CLI에만 전달하며
GITHUB_ENV/output/artifact에 저장하지 않는다. 기대 account/정확한 role만 비교해 판정한다.
자료상 1시간 session을 요청하고 job을 그 안으로 나눈다. 실제 role max/session 정책은 pending이다.

등록할 입력(실제 등록은 하지 않음):

| 위치 | 이름 | 내용 |
| --- | --- | --- |
| Variable | `AWS_ACCOUNT_ID` | 실계정과 대조한 값; 출력 수집 제한+마스킹 |
| Variable | `RT14_AWS_REGION` | 자료상 허용 region `ap-northeast-2`; 누락/다른 값은 거부 |
| Variable | `RT14_EXECUTION_ENABLED` | Owner/인프라 확인 완료 전 미설정; 승인 후 `true` |
| Variable | `RT14_ECR_REPOSITORY` | 승인된 기존 repository 이름 |
| Secret | `RT14_INSTANCE_ID` | 허용된 기존 EC2 정확한 ID |
| Secret | `RT14_IMAGE` | 승인한 ECR `repository@sha256:...` 전체 URI |
| Variable | `RT14_REVISION`, `RT14_CONFIG_ID` | 승인한 40자 commit와 immutable config ID |

순서는 authentication-only 수동 workflow → 별도 publish → 보호된 release 승인파일 준비 →
별도 deploy다. 이번에 dispatch하지 않았다. UI에서 branch는 develop을 선택한다.

publish는 amd64 image를 cache 사용 build하고 동일 image에서 media preflight,
offline OCR preflight, strict media acceptance를 실행한다. AWS 인증 후 immutable ECR에
commit tag로 push하고 digest를 확인한다. registry/credential CLI 출력은 공개하지 않는다.
ECR lifecycle은 current/previous known-good/candidate digest를 삭제하지 않도록 별도 검토한다.

도구는 실행 시 develop tip의 **push CI** python-tests/boundary-check 최신 run 성공을
요구한다. 배포 target에도 별도 push CI와 develop ancestor/identical 여부를 검증하고,
ECR tag→digest도 대조한다. 과거 PR CI만으로 새 변경이 검증됐다고 하지 않는다.
이 요구 때문에 병합 전 준비 검증과 병합 뒤 실제 dispatch 가능 여부는 다르다.

각 release에는 `approval.example.json` 형식으로 `/opt/daesingo/approvals/<revision>.json`
root0400을 둔다. exact image/revision/config, 현재 schema에서 안전한 rollback revision 목록,
일관된 backup 위치의 **비공개 reference**가 필요하다. 승인 문서 자체는 실제 백업 성공의
기계적 증명이 아니므로 운영자가 runbook 검증 evidence와 대조한다.
첫 배포는 previous known-good이 없다. 실제로 빈 소유 DB/media임을 확인한 별도
초기 상태 승인을 `initial_state=verified-empty-owned-volumes`로 명시해야 한다.
도구도 두 소유 volume의 실제 host Mountpoint가 비었는지 확인한다. 기존 populated
volume이나 controller 이력이 없는 project를 자동으로 인수하지 않는다. 그런 환경은
데이터·schema·backup·소유권을 별도 검토한 adoption 절차가 필요하며 이번 도구의 범위 밖이다.
두 번째 배포부터 `schema_parent`는 private `schema.json`의 실제 마지막 migration
revision과 같아야 한다. code rollback 뒤에도 이 schema parent는 되돌아가지 않는다.

SSM 입력은 고정 controller와 좁은 alphabet의 image/revision/config/operation뿐이다.
명령 접수 성공 뒤 remote 실행 결과가 필요하다. `Success` **그리고 정수 exit0**만 성공이다.
Pending/InProgress/Delayed/일시 응답누락은 bounded poll, failed/timeout/cancel/unknown은 실패다.
원문 stdout/stderr/SSM response URL은 runner에서 수집하지 않는다.
[공식 Run Command 상태](https://docs.aws.amazon.com/cli/latest/reference/ssm/get-command-invocation.html).

## 6. Host 순서와 성공 기준

```sh
# SSM이 실행하는 고정 명령의 동등 예시. 이번에 실행하지 않았다.
sudo /usr/bin/python3 /opt/daesingo/controller/ec2.py deploy \
  --image '<approved-ecr-uri@sha256:digest>' --revision '<40-hex-commit>' --config-id '<approved-config-id>'
```

1. root/x86_64/private policy/승인파일 검증. atomic mkdir `operation.lock`으로 deploy,
   rollback, config fetch 동시 실행을 막는다. Actions concurrency도 취소 없이 직렬화한다.
2. 불명확한 dirty migration이면 중단. protected file·external volume 소유·project 충돌,
   기존 MySQL exact image, available RAM/disk reserve, CloudWatch group/retention을 확인한다.
3. instance-role ECR 로그인은 임시 private Docker config에서 수행한다. app digest pull 후
   architecture/OCI revision을 검사한다. image 안 Compose를 추출해 build를 제거하고
   exact image·external volumes·보호 bind·awslogs·승인 restart로 render한다.
4. provider를 호출하지 않는 `deploy-config`: API/Worker RuntimeConfig, Search credential,
   Recording Analysis 6개와 Incident 3개를 검증한다. 비어 있는 운영 한도는 여기서 중단한다.
5. 기존 writer를 stop하고 MySQL만 기동/healthy를 기다린다. live app이 쓰는 상태에서
   migration하지 않는다. grace는 기존 30초로 모든 handler 완료 보장이 아니다.
6. app DB 연결의 실제 session packet과 `MAX_BYTES + packet_margin_bytes < packet`을
   확인한다. margin은 측정·승인값이고 코드에 기본값을 두지 않는다.
7. dirty와 별도 schema authority `schema.json`의 `migration_pending`을 fsync한 뒤
   migrate **단 한 번** 실행한다. nonzero/timeout은
   실패이며 API/Worker를 시작하지 않는다. forward-only이며 downgrade 없음.
8. 성공 뒤 schema authority와 dirty `migration_complete`; API/Worker를 `--no-deps --no-build --pull never`
   recreate한다. 이 우회는 controller가 단일 migration exit0을 직접 확인한 뒤에만 사용한다.
9. 각각 단일 running container·exact app image/revision·restart count0·OOM 아님,
   MySQL/API healthy와 ready, 실제 Worker PID1/starttime/revision/8종 marker를 확인한다.
   marker는 OCR 예열·실제 registry 조립 뒤 loop 직전에 쓰고 정상 종료 때 제거한다.
   stale PID/restart 파일이나 별도 OCR 조립 프로세스의 결과를 성공으로 쓰지 않는다.
10. API live/ready JSON과 임의의 미존재 Case GET view의 404를 확인한다. 이 read-only
    smoke는 DB-backed route를 지나며 case/job/media/provider를 생성하지 않는다.
11. 모든 검사 후에만 root0600 `previous.json`, `current.json`을 원자적으로 갱신하고
    dirty를 제거한다. compose source는 image digest로 재현, config ID는 그대로 보존한다.

marker는 **process/등록 증거**다. idle Worker heartbeat나 진행 중 handler 성공을 뜻하지 않는다.
실제 작업의 lease/heartbeat/STALE는 기존 Runtime DB query와 안전한 이벤트로 확인한다.
[RT-12 관측 Notes](rt12b-observability.md), Baseline lease/sweep를 사용하고 새 threshold를 만들지 않는다.
API healthy로 Worker/provider가 정상이라고 선언하지 않는다. 8종 등록은 실제 provider
분석→판독→export 성공, 장시간 메모리 용량 검증을 대신하지 않는다.

## 7. 실패·취소·rollback·부분 DDL

SSM timeout, Actions 취소/연결 단절은 원격 작업 중단을 보장하지 않는다. delivery60초,
remote 실행1200초, runner 결과 대기1500초의 **도구 timeout**은 SLA/측정값이 아니다.
각 child도 bounded이며 Docker CLI timeout 뒤 container 작업이 계속될 수 있다.
이 경우 UNKNOWN으로 기록하고 재dispatch하지 않는다. operator가 SSM command 상태,
host controller/Compose/migration process·container와 root private dirty/lock을 대조한다.
살아 있는 작업의 lock을 빼앗거나 container를 임의로 지우지 않는다.

| 마지막 상태 | 처리 |
| --- | --- |
| preflight 실패 | known-good 유지. pull된 candidate/image·검사 container 잔여를 소유 범위로 조사 |
| quiescing/MySQL/packet 실패 | writer 정지 가능. 자동 재시작 없음; DB/로그/credential 상태 조사 후 명시적 복구 |
| migration_pending 또는 결과 불명 | 새 deploy·rollback 모두 거부. MySQL 부분 DDL·Alembic heads/실제 table을 확인하고 migration Owner와 forward repair 또는 검증된 별도 restore |
| migration_complete 뒤 health/smoke 실패 | known-good 미갱신. 부분 새 app 실행 가능; 승인된 이전 image+config의 code rollback 여부 판단 |
| promotion 중 단절 | dirty와 current/previous를 함께 대조. 상태가 검증되기 전 임의 재시도 금지 |

```sh
# schema 호환 승인과 actual known-good exact record가 있는 경우에만 실행
sudo /usr/bin/python3 /opt/daesingo/controller/ec2.py rollback \
  --image '<known-good-ecr-uri@sha256:digest>' --revision '<known-good-commit>' --config-id '<known-good-config-id>'
```

rollback은 current/previous의 **exact tuple과 전체 기록**, 현재 적용 schema가 승인한
`rollback_targets`만 허용한다. config를 최신 파일로 바꾸지 않고 이전 config ID를 쓴다.
schema authority의 compatibility는 code rollback의 성공/실패와 무관하게 보존한다.
예를 들어 C schema가 B만 승인했다면 C→B code rollback 뒤에도 A로 돌아갈 수 없다.
동일 preflight → stop → MySQL/packet → recreate → health/8종/smoke를 반복하되
**migration을 실행하지 않는다**. DB/media volume 삭제·DB downgrade·자동 restore 없음.
처음 배포하거나 이전 digest/config가 삭제됐거나 schema가 호환되지 않으면 code rollback할 수 없다.

2026-10-30 설계 검토에서 확인한 현재 동작의 경계([RT-14 배포 설계](rt14-deployment-design.md) §9.3):

- workflow의 `rollback`도 dispatch한 develop tip의 push CI 성공을 요구한다. tip CI가 진행 중이거나
  실패한 동안에는 workflow rollback이 거부된다. 설계 변경안은 rollback에서 tip 검사를 빼고 대상 revision
  검사(develop 조상 · push CI · ECR digest)와 host exact tuple · schema 검사만 남기는 것이다. 위 controller
  명령의 SSM Session 직접 실행은 break-glass 경로로 남긴다.
- 최초 배포가 migration 뒤 실패하면 current가 없어 rollback 대상이 없다. dirty가 남아 deploy가
  거부되고, dirty를 치워도 preflight가 비어 있지 않은 volume을 거부한다. operator recovery 절차는 아직
  없고 첫 AWS deploy 전에 필요하다. 필요한 내용은 설계 §9.3이다. dirty 파일 삭제만으로는 복구가 아니다.

부분 DDL은 DB transaction rollback으로 되돌아갔다고 가정하지 않는다. 진행 작업이 없고
DB 실제 상태를 조사한 뒤 Owner가 forward repair/restore와 재개를 승인한 경우에만
private marker/lock을 별도로 보존·해제한다. 자동 unlock/retry 도구를 제공하지 않는다.
운영자가 단순히 marker를 지워 재실행하는 것은 복구 절차가 아니다.

## 8. Backup·restore와 자원 보존

[RT-13(b)](rt13b-backup-restore.md)의 `backup_compose.py`를 같은 project와 실제 생성한
`/opt/daesingo/release-compose.json`에 연결한다. 아래 명령은 도구가 있는 승인된
checkout에서 실행한다. private artifact 경로를 shell 변수로만 공급한다.

```sh
sudo python3 scripts/backup_compose.py backup --project '<approved-project>' \
  --compose-file /opt/daesingo/release-compose.json --directory '<private-backup-directory>'
```

기존 도구의 writer 정지·단일 DB·release heads·exclusive artifact 계약을 먼저 확인한다.
외부 writer/DDL도 중단해야 하며 deploy와 동시에 실행하지 않는다. RT-13(b)의 DB 내부
lock과 RT-14 host lock은 서로 다른 lock이므로 운영 창에서 중복 작업을 막아야 한다.
운영 DB 전체가 큰 경우 기존 도구는 SQL을 메모리에 모으므로 **4GB에서 바로 실행하지 않는다**.
측정·수용 가능한 snapshot 크기/메모리와 media 일관성 확보 전 backup acceptance는 pending이다.

논리 DB dump는 media volume backup이 아니다. 쓰기를 정지한 같은 시점의 media
snapshot/copy, SHA manifest, 소유/경로와 durable metadata 관계를 함께 보존하고
소유/암호화/오프호스트 저장/보관 기간/RPO/RTO를 Owner가 결정한다. 새 S3 bucket이나
lifecycle을 임의 생성하지 않는다. 복원은 기존 populated DB 위에 덮지 않고, 명시적으로
준비한 빈 별도 소유 target에서 DB dump와 media를 결합해 검증한다. 일부 import 실패 target은
격리한다. restore 성공·heads·파일 hash·health·실제 download 검증 전 서비스 재개 금지.
현재 도구만으로 자동 운영 restore 완료를 주장하지 않는다.

50GB disk·4GB RAM 계획은 실측 후 채울 예산표다. 비어 있으면 운영 준비 완료가 아니다.

| 예산 | 시작 계약 / 남은 측정 |
| --- | --- |
| build/cache | CI cache 사용, EC2 build 없음. FFmpeg/Paddle 공통 layer 재사용. shared cache 전체 prune 없음 |
| image | current + previous known-good 반드시 보존, candidate 하나의 peak도 예산에 포함. tag가 달라도 공유 layer 중복 계산을 피하고 `docker system df`/image size로 실측 |
| config/승인/상태 | current/previous config와 approval 보존. 오래된 것의 수동 정리는 실제 참조·rollback 창을 검증한 후 수행 |
| 로그 | B-O1의 20m×5 local cache를 service별 설정. 3개 steady service의 계산상 pre-compression 상한 약300MB, migrate/진단 container를 포함하면 추가 필요. 시간 retention과 다름 |
| 전송 | awslogs non-blocking buffer는 승인 bytes 필수. 전송 장애 시 손실 가능, 내구 queue/알람 보장 아님. 실제 CloudWatch retention/수신·지연 검증 필요 |
| DB/media/temp | 데이터 증가·동시 upload·Analysis 연결/encode overshoot·Worker temp·MySQL working set을 실측. prepared bytes limit은 RSS/disk hard quota 아님 |
| backup | 같은 disk dump+media copy의 peak, restore scratch와 오프호스트 사본까지 합산. 성공 대형 dump/RAW를 서버에 누적하지 않음 |
| reserve | `disk_reserve_bytes`, `memory_reserve_bytes`는 초기 안전 여유 입력. 단일 preflight 통과가 동시 API+Paddle+MySQL 용량 보장은 아님 |

삭제 기능은 구현하지 않았다. 정확한 volume/image/config의 소유·참조 범위와 보존 정책을
승인하기 전 정리하지 않는다. `system prune -a`, `volume prune`, `down -v` 금지.
현재/rollback image를 무조건 정리하지 않는다. 운영 관측 후 필요하면 캠퍼스 승인 경로로
사양/EBS/RDS/ALB/EIP 지원을 문의한다. 도메인 자료와 AWS 가이드의 EIP 허용 주장이
달라 실제 권한/담당 확인 전 미확정이다. EIP 무료·IPv4 비용 면제라고 쓰지 않는다.
DuckDNS/Caddy/TLS/OAuth를 확정하거나 구현하지 않았다.

driver/tag와 dual cache의 구현 형식은 [Docker awslogs 공식 문서](https://docs.docker.com/engine/logging/drivers/awslogs/)와
[dual logging 문서](https://docs.docker.com/engine/logging/dual-logging/)를 2026-10-30 확인했다.

## 9. 미결의 실제 영향

| 후속 | 실제 차단 / 잔여 위험 |
| --- | --- |
| #452 운영값·22개 원본/측정 profile | 운영 deploy-config/packet/Worker acceptance를 막음. CI/local 도구 검증은 진행 가능 |
| #452 Case 전용 notice | 큰 입력의 typed 실패가 일반 재시도 notice로 보일 수 있음; 사용자 경로 acceptance에 남음. RT-14에서 Case 정책 변경 안 함 |
| #445 orphan publish cleanup | crash 잔여 media의 장기 disk 증가 위험; 소유 scan/정리 검증과 운영 창 필요 |
| #71 retention·provider lifecycle | 장기 데이터 보관/삭제·외부 사본 lifecycle 미완료. deployment image 준비와 구분 |
| RD-14/auth/IDOR | 2026-10-22 최종 제출 요건으로 공개 trigger 발생. 공개 모델·외부 smoke는 [RT-14 배포 설계](rt14-deployment-design.md) §13 · §10.2(2026-10-30 Gate 승인, 구현 전). 이 준비 구현은 내부 loopback smoke만 제공 |
| AWS/용량/로그/rollback/restore 실제 증거 | mock/local 성공으로 닫지 않음. 실제 운영 승인 후 rehearsal 필요 |

<a id="10-implementation-notes"></a>

## 10. 구현 기록

직접 실행 검증·fresh reviewer·자원 정리·전체 변경 manifest는 구현 종료 시 이 절에
append한다. 과거 #473~#477 CI, 이번 로컬 Python/Linux Docker 검증, 미래 새 PR CI를
서로 다른 증거로 기록한다. DB schema/migration/Contract/mandatory MySQL 의미는 바꾸지 않는다.

### 2026-10-30 직접 검증과 review

| 증거 | 이번 결과 / 한계 |
| --- | --- |
| TDD | AWS/SSM 입력·판정16 RED→GREEN, host 전이14 RED→GREEN, runtime4 RED→GREEN. 후속 schema/bootstrap4·CLI 비노출2·cleanup1 회귀도 RED→GREEN |
| 작성자 최종 focused | `tests/deploy` + `tests/worker/test_entrypoint.py` + `test_production_readout.py` + `test_readout_composition.py`: **228 PASS**, 41.45초, Windows Python3.12.14 |
| 독립 reviewer | 구현 이력을 상속하지 않은 동일 read-only reviewer, 두 P1 수정과 최종 credential/region/cleanup delta 재검토; 별도 동일 focused **228 PASS**, 29.99초. 남은 actionable finding 없음 |
| 실제 Linux existing image | 기존 `daesingo-issue452:local` image에 새 src/adapter를 read-only mount, network none. 실제 production OCR 초기화·실제8종 registry·PID1/starttime/revision marker·제거·누락 config 거부 PASS |
| 위 image 검사의 한계 | **claim loop만 대역**. DB/queue/provider/service deployment 없음. 새 Dockerfile full build·image publish acceptance가 아님 |
| 잠금 | 독립 subprocess가 보유 lock 진입 거부(exit23), 해제 후 다음 프로세스 진입(exit0) 직접 PASS; 파일 잠금 강탈 없음 |
| Compose | 기존 source checker PASS; 실제 Compose로 local와 production candidate 모두 render PASS. 컨테이너 시작 없이 구조 검증 |
| boundary/Contract | boundary PASS; 문서62/JSON26/semantic104 모두 PASS. 최초 Windows cp949 출력 오류는 UTF-8 재실행과 구분 |
| workflow/shell | actionlint exit0; 신규 workflow 각 run block `bash -n` PASS. 기존 regression/mysql/test 파일·권한·required check 변경 없음 |
| privacy | 첨부4개에서 추출한 식별 후보와 추가된 텍스트의 일치0, 실제 숫자 계정 포함 literal ARN0. JWT/임시credential/CLI 오류/SSM query 비노출 focused 검사 PASS. 전수 secret scanner 보장은 아님 |
| diff / 상태 | `git diff --check` PASS; index empty, commit/push/PR/외부 댓글/Notion/dispatch/AWS 작업 없음 |

실패 이력도 보존한다. 최초 runtime patch가 media 함수에 잘못 들어간 NameError는
기존 media 회귀로 재현 후 위치를 수정했고 81 PASS로 확인했다. 첫 existing-image 검사는
검증 helper의 pytest import 때문에 실패했다. pytest 설치/이미지 변경 없이 fixture 함수만
읽도록 helper를 수정한 뒤 위 Linux 검사가 통과했다. 두 실패를 production 실패나
AWS 실패로 기록하지 않는다. 성공 증거와 초기 실패 log는 ignored task scratch에서 구분한다.

reviewer 최초 P1 두 건은 (1) code rollback이 이전 release의 compatibility 목록을
덮어쓰는 문제, (2) 처음 label만으로 populated volume을 인수할 수 있는 문제였다.
독립 schema authority와 최초 empty-volume 실검사를 추가했고 같은 reviewer가
회귀·구현·문서를 재확인했다. 이후 marker 제거 실패가 engine 정리를 건너뛰는 경계도
작성자가 RED→GREEN으로 고쳤고 같은 reviewer의 최종 recheck에 포함됐다.

과거 #473~#477의 CI는 선행 근거다. **이번 변경의 새 PR 원격 CI는 미실행**이며,
전체 로컬 pytest/전체 mandatory MySQL도 반복하지 않았다. 실제 OIDC subject/trust/role,
ECR publish/pull, EC2 SSM, protected config, migration, CloudWatch 수신, API+Paddle+MySQL
동시 용량·restart/STALE·code rollback rehearsal·DB/media restore acceptance는 모두 미검증이다.
Owner 결정·#452 운영값과 함께 실제 실행 전 조건으로 유지한다.

### 변경 manifest

아래 **26파일**이 제출 대상이며 모두 미스테이징이다. task scratch/RAW/JUnit/임시 env,
모델/credential/archive/image export는 제출 대상이 아니다.

| 파일 | 변경 |
| --- | --- |
| `.dockerignore` | Compose source의 image 포함 allowlist |
| `Dockerfile` | image 내 Compose source·OCI revision label |
| `README.md` | 새 deploy 경로 pointer |
| `.github/workflows/rt14-oidc.yml` | 별도 수동 인증 확인 |
| `.github/workflows/rt14-deploy.yml` | 별도 수동 publish/deploy/rollback |
| `deploy/aws.py` | OIDC·quality/digest·SSM 결과 판정 |
| `deploy/ec2.py` | root host 상태·scope·migration·health·rollback |
| `deploy/configure.py` | host instance-role SecureString fetch·보호 파일 |
| `deploy/policy.example.json` | 미완성 정책 입력 양식 |
| `deploy/approval.example.json` | release/schema/bootstrap 승인 양식 |
| `docker/runtime.py` | deploy-config/packet/worker-status/read-only smoke |
| `src/daesingo/worker/__main__.py` | opt-in 실제 registry marker·정리 |
| `src/daesingo/worker/deployment_status.py` | process identity·8종 snapshot |
| `tests/deploy/test_aws_deploy.py` | AWS/SSM/OIDC/ref/비노출 집중 검사 |
| `tests/deploy/test_ec2_deploy.py` | 실패 전이·잠금·schema/초기 데이터 보존 |
| `tests/deploy/test_deploy_config.py` | parameter·credential·CLI 경계 |
| `tests/deploy/test_deployment_runtime.py` | 필수 config·packet·실제 main marker·정리 |
| `docs/runtime/README.md` | RT-14 pointer |
| `docs/runtime/deployment-runbook.md` | 구현 명령·pending 경계 연결 |
| `docs/runtime/rt14-deployment.md` | 이 runbook·Notes·manifest |
| `docs/runtime/local-runtime-environment.md` | 새 opt-in 상태 확인과 기존 진단 구분 |
| `docs/runtime/official-inputs/aws-environment.md` | 사용자10-30 관측 append, EIP 불일치 |
| `docs/runtime/open-decision-register.md` | candidate 연결, OPEN 유지 |
| `docs/runtime/runtime-implementation-plan.md` | #450 준비 진행 상태 연결 |
| `docs/runtime/runtime-implementation-log.md` | 이번 구현·검증 append |
| `docs/superpowers/plans/2026-10-30-rt14-deployment.md` | 구현 계획·ruling·검증 경계 |

### 작업 자원 정리

새 image build/export, DB, named volume, network, media/backup을 생성하지 않았다.
offline 검사 전용 container는 `--rm` 종료 후 부재를 확인했고, 구조 검사 project의
volume/network도0을 확인했다. 기존 image4개는 시작과 같은 ID로 보존했고 shared cache를
prune하지 않았다. pytest task 임시 config/media와 성공 render/helper 사본은 task 범위에서
정리하며 초기 실패 log와 최종 작은 요약만 ignored scratch에 남긴다.
