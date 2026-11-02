# 환경·배포 설정 명세

**Refs #460 · #450 · 2026-11-01, `develop` `23a26987` 코드 기준**

서버를 띄우거나 Local E2E · AWS E2E · publish/deploy를 할 때 필요한 **설정 이름**과
그 값이 공개 가능한지, 실제 값이 어디에 있는지를 한 곳에서 찾기 위한 문서다.

- **실행 절차는 여기 없다.** 아래 §7의 기존 runbook으로 간다.
- **키별 의미·허용값·코드 기본값의 원문**은 [canonical guide](../runtime/local-runtime-environment.md)다. 이 문서는 그 표를 복제하지 않고 이름·필수 여부·값 분류만 모은다.
- 이 문서가 원문인 것은 [§3 Recording baseline v1·현재 적용값](#3-recording-초기-배포-baseline-v1)과, 흩어져 있던 이름·구조를 모은 인벤토리다.
- 실제 팀 환경의 값(account·instance·경로·hostname·허용 IP 등)과 Secret 보관 위치는 **팀 Notion 엔지니어링 위키의 「운영 비공개 정보」**에 있다.

## 1. 공개 구분 규칙

**이름은 공개, 값만 구분한다.** `AWS_ACCOUNT_ID`라는 이름은 Secret이 아니다. 실제 계정 번호가 비공개다.

| 구분 | 예 | 둘 곳 |
| --- | --- | --- |
| 이름 · 형식 · 필수 여부 · 코드 기본값 · 팀 baseline · 요구 구조 | `GEMINI_API_KEY`가 필요함, `RT14_IMAGE`는 Secret, Analysis height baseline `480`, ECR은 IMMUTABLE | **이 repo** |
| 현재 우리 팀 환경의 식별자 · 운영값 | account ID, instance ID, EIP, VPC/SG ID, ECR URI, Parameter Store 경로, Log Group 이름, 허용 IP, Secret 발급 계정·교체 담당 | **팀 Notion** |
| credential 값 | API key, DB password, DDNS token, private key, session credential, TLS 개인키 | **어디에도 복제하지 않는다.** 저장 위치(§6)만 기록 |

판단이 애매하면: 다른 팀이 같은 코드로 배포해도 같은 값이면 repo, 우리 계정·서버에서만 의미 있으면 Notion이다.
GitHub **Variable** 값은 공개 Actions 로그의 step `env`에 그대로 찍힌다. 로그에 나와도 되는 값만 Variable로 둔다.

## 2. Local / Local E2E

의미·기본값·검증 규칙: [canonical guide §2~§4](../runtime/local-runtime-environment.md#2-설정-파일과-secret-소비-경계).
복사용 템플릿: [`.env.example`](../../.env.example).

### 2.1 Compose 호스트 shell 선택자

앱 runtime 파일 안이 아니라 `docker compose`를 실행하는 shell에 둔다.

| 이름 | 필수 | 기본값 | 값 분류 |
| --- | --- | --- | --- |
| `DAESINGO_RUNTIME_ENV_FILE` | Compose 필수 | 없음 | 경로(개인/호스트 종속) |
| `DAESINGO_MYSQL_PASSWORD_FILE` | Compose 필수 | 없음 | 경로. 파일 내용은 credential |
| `DAESINGO_MYSQL_ROOT_PASSWORD_FILE` | Compose 필수 | 없음 | 경로. 파일 내용은 credential |
| `DAESINGO_REVISION` | 선택 | `local` | 공개(source SHA) |
| `DAESINGO_API_PORT` | 선택 | `8000` | 공개 |

앱 쪽 파일 선택자 `DAESINGO_ENV_FILE`은 shell 선택자가 아니라 API/Worker/migrate의 process env다(API/Worker 미지정 시 `cwd/.env`, migrate adapter는 필수, Compose는 `/run/secrets/runtime.env`로 지정). 앱은 선택된 파일만 읽고 shell의 같은 이름 값을 병합하지 않는다.

### 2.2 runtime 파일(`runtime.env`)에 넣는 키

| 그룹 | 이름 | 필수 | 소비 | 값 분류 |
| --- | --- | --- | --- | --- |
| Runtime | `DAESINGO_RUNTIME_DB_URL` | 필수 | API · Worker · migrate | **credential 포함** |
| Runtime | `DAESINGO_RUNTIME_MEDIA_ROOT` | 필수 | API · Worker | 공개(Compose `/media`) |
| Runtime | `DAESINGO_RUNTIME_API_TEMP_ROOT` | API 필수 | API | 공개(`/media/api-temp`) |
| Runtime | `DAESINGO_RUNTIME_WORKER_TEMP_ROOT` | Worker 필수 | Worker | 공개(`/media/worker-temp`) |
| Search | `GEMINI_API_KEY` | **Worker 필수** | Worker(Search · Intent) | **credential** |
| Search | `ELICE_ML_API_KEY` | 선택(eval · smoke 도구는 우선 사용) | eval · smoke CLI | **credential** |
| Recording Analysis | `DAESINGO_RECORDING_ANALYSIS_{PROFILE_REF,HEIGHT,PRESET,CRF,MAX_BYTES,MAX_DURATION_MS}` | 6개 함께. 전부 없으면 Coarse/Fine 미등록 | Worker | 공개, baseline §3 |
| Recording Incident | `DAESINGO_RECORDING_INCIDENT_{HEIGHT,PRESET,CRF}` | 3개 함께. 전부 없으면 `INCIDENT_CLIP_BUILD` 미등록 | Worker | 공개, baseline §3 |
| Recording | `DAESINGO_RECORDING_FILENAME_OFFSET` | 선택(근거 없으면 생략) | Worker | 공개 |
| Search override | `DAESINGO_GEMINI_{MODEL,BASE_URL,MEDIA_RESOLUTION}`, `DAESINGO_INTENT_{MODEL,BASE_URL}` | 선택(생략하면 코드 기본값) | Worker | 공개 |
| Search 가격 | `DAESINGO_GEMINI_{INPUT,OUTPUT}_USD_PER_MILLION`, `DAESINGO_GEMINI_MAX_COST_USD` | 선택(기본 `0.0` = 미설정) | Worker | 공개 |
| Runtime 선택 | `DAESINGO_RUNTIME_*` 32개(log level · DB pool/timeout · heartbeat · lease · upload · cleanup · readiness) | 선택 | API · Worker | 공개. 목록과 기본값은 [canonical guide §4](../runtime/local-runtime-environment.md#4-선택-runtime-키-전체-목록) |

- 선택 키는 빈 문자열로 두지 말고 줄을 생략한다. Coarse/Fine용 `DAESINGO_GEMINI_*`에 빈 값을 넣으면 기본값으로 돌아가지 않는다(Intent는 빈 값을 기본값으로 처리).
- Search Coarse/Fine은 `gemini-4-argon`, Intent는 `gemini-3.8-flash`가 코드 기본값이다([Search Owner 결정](../modules/search/decisions/search-argon-model-2026-10-27.md)). 예전 Flash override가 남아 있으면 Coarse/Fine도 Flash로 간다.
- **Case · Readout · Web 앱 env는 없다.** Readout 모델·cache는 image에 고정(`PADDLE_PDX_CACHE_HOME=/opt/daesingo/paddlex`, Dockerfile이 지정)이고 버전은 [canonical guide §1 · §6](../runtime/local-runtime-environment.md#1-지원-범위와-버전)에 있다. Web은 build/runtime env 없이 상대 API URL을 쓴다.

### 2.3 개발 · 테스트 · eval 전용

| 이름 | 쓰는 곳 | 값 분류 |
| --- | --- | --- |
| `DAESINGO_MYSQL_URL` | MySQL integration test, `migrations/case/env.py` dev 경로. 폐기 가능한 test DB만 | 테스트 DB credential(로컬) |
| `DAESINGO_REQUIRE_MYSQL` | CI `mysql` job · `tests.ci_orchestration`이 지정. 손으로 둘 필요 없음 | 공개 |
| `API_PROXY_TARGET` | `apps/web` Vite dev server의 `/cases` proxy. 기본 `http://localhost:8000` | 공개 |
| `DAESINGO_EVAL_DATA_ROOT`, `DAESINGO_EVAL_PRIVATE_ROOT` | `eval/` 선택 경로 | 개인 경로 |

실행: MySQL test는 [루트 README 실행 절](../../README.md#실행)과 [CI 실행 구조](../runtime/ci-test-partitions.md), eval은 [`eval/README.md`](../../eval/README.md).

## 3. Recording 초기 배포 baseline v1

### 3.1 과거 초기 배포·재현 기준

아래는 `aws-e2e-20261031-v1` 당시의 baseline v1이다. 현재 Incident 적용값은 §3.2를 따른다.

```env
DAESINGO_RECORDING_ANALYSIS_PROFILE_REF=aws-e2e-v1
DAESINGO_RECORDING_ANALYSIS_HEIGHT=480
DAESINGO_RECORDING_ANALYSIS_PRESET=veryfast
DAESINGO_RECORDING_ANALYSIS_CRF=23
DAESINGO_RECORDING_ANALYSIS_MAX_BYTES=50331648
DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS=240000

DAESINGO_RECORDING_INCIDENT_HEIGHT=240
DAESINGO_RECORDING_INCIDENT_PRESET=veryfast
DAESINGO_RECORDING_INCIDENT_CRF=23
```

- **과거 초기 배포 baseline v1**이다. 근거: [#460 Recording Owner 정리(2026-11-01)](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/460#issuecomment-6555755740), 당시 실행 근거는 [AWS E2E 기록 §4](../runtime/experiments/2026-10-31-rt14-aws-real-e2e.md#4-aws-real-e2e-temporary-acceptance-values). 과거 Incident 240p 기록은 보존한다.
- **최적 운영값 확정이 아니다.** 단회 E2E 재현 기준이며 판독 정확도 · 번호판 가독성 · 신고영상 품질을 최적으로 검증한 값이 아니다.
- Analysis 최대 분석 범위는 **4분**(`240000` ms), 최종 분석 영상은 48 MiB다. 4분을 넘는 요청은 거부된다.
- **약 1시간 영상 지원은 후속 실측·개선 대상**이다([#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)). 한도만 키워서 해결했다고 하지 않는다.
- **Analysis 설정을 바꾸면 `ANALYSIS_PROFILE_REF`도 새 식별자로 바꾸고** 변경 이유와 검증 근거를 남긴 뒤 이 절과 `.env.example`을 함께 갱신한다. Incident만 변경할 때 Analysis profile 식별자는 유지한다.
- 배포에서는 `MAX_BYTES + packet_margin_bytes < 실제 DB session max_allowed_packet`를 controller가 확인한다(현재 48 MiB + 8 MiB < 64 MiB).
- 한도의 정확한 의미: [AnalysisSource 한도](../modules/recording/analysis-source-limits.md).

### 3.2 현재 적용값 — Incident 720p (2026-11-02)

운영자 제공 적용 결과 기준으로 current config는 `aws-e2e-20261102-incident720-v1`,
previous는 `aws-e2e-20261031-v1`이다. Incident만 다음 값으로 바뀌었다.

```env
DAESINGO_RECORDING_INCIDENT_HEIGHT=720
DAESINGO_RECORDING_INCIDENT_PRESET=veryfast
DAESINGO_RECORDING_INCIDENT_CRF=20
```

Analysis 6개 값은 §3.1 그대로이며 `ANALYSIS_PROFILE_REF=aws-e2e-v1`을 유지한다.
이미지·revision·비밀번호 등 나머지 설정도 유지됐다는 운영자 보고다.
근거와 한계는 [Incident 720p 적용·실영상 E2E 기록](../runtime/experiments/2026-11-02-incident720-config-real-e2e.md)에 둔다.
이는 현재 적용 기준이며 최적 화질·OCR 정확도·모든 입력의 성능이나 실제 신고 수용을 보장하지 않는다.

## 4. AWS E2E / production

실행: [공개 배포·복구 Notes](../runtime/rt14-public-deployment.md)(현재 기준) → [RT-14 배포 준비](../runtime/rt14-deployment.md) §4~§7 → [deployment runbook](../runtime/deployment-runbook.md).

### 4.1 배포 단위를 정하는 식별자

| 개념 | 형식 | 의미 |
| --- | --- | --- |
| revision | 40자 commit SHA. `local`은 배포 불가 | image label `org.opencontainers.image.revision` · API `DAESINGO_REVISION` · Web marker가 모두 같아야 한다 |
| image identity | `<account>.dkr.ecr.ap-northeast-2.amazonaws.com/<repository>@sha256:<64 hex>` | publish가 revision을 ECR tag로 push한 뒤 digest로 고정. tag가 아니라 digest로 배포 |
| config ID | `[a-z0-9][a-z0-9-]{0,63}` | 보호 config 디렉터리 이름. **immutable** — 덮어쓰지 않고, 값이 바뀌면 새 ID를 만든다 |
| release tuple | (image, revision, config ID) | 승인 파일 · `current.json` · workflow 입력이 정확히 일치해야 한다 |

### 4.2 production `runtime.env`

키는 §2.2와 같다. 배포 controller의 `deploy-config`가 추가로 강제한다.

- `DAESINGO_RUNTIME_MEDIA_ROOT=/media`, `..._API_TEMP_ROOT=/media/api-temp`, `..._WORKER_TEMP_ROOT=/media/worker-temp` — 다른 값은 거부.
- DB URL은 host `mysql`, DB `daesingo`, user `daesingo`만 허용. password는 `mysql-password` 파일 내용과 같고 URL encoding한다.
- Recording Analysis 6개 · Incident 3개가 **모두** 있어야 한다(로컬과 달리 그룹 생략 불가). `GEMINI_API_KEY` 필수.
- Parameter Store standard tier 한도가 4 KB이므로 주석 없는 `KEY=VALUE`만 넣는다. `.env.example` 전체를 그대로 넣지 않는다.

### 4.3 보호 파일과 공급 경로

```text
Parameter Store (SecureString, policy.parameter_path 바로 아래, non-recursive)
  runtime-env           → configs/<config-id>/runtime.env           UID 10001,      0400
  mysql-password        → configs/<config-id>/mysql-password        mysql UID(999), 0400
  mysql-root-password   → configs/<config-id>/mysql-root-password   mysql UID(999), 0400
        ↑ deploy/configure.py --config-id <new-id> 가 instance role로 읽어 새 디렉터리에 원자적으로 생성
```

정확히 이 세 leaf만 있어야 한다(누락 · 평문 String · 예상 밖 parameter는 거부). 권한이 없으면 같은 계약으로 Session Manager에서 수동 배치한다([RT-14 배포 준비 §4](../runtime/rt14-deployment.md#4-보호된-host-준비와-config)).
MySQL password 파일 교체만으로 기존 DB 사용자의 password는 바뀌지 않는다.

### 4.4 host 구조 (`/opt/daesingo`)

```text
/opt/daesingo/                         root 0700
├─ policy.json                         root 0400   host 정책(§4.5)
├─ controller/                         root        ec2.py · configure.py · web_artifact.py · ddns.py (승인 SHA와 해시 대조 후 설치)
├─ configs/                            root 0700
│  └─ <config-id>/                     root 0700   §4.3 파일 3개
├─ approvals/                          root 0700
│  └─ <revision>.json                  root 0400   release 승인(§4.6)
├─ current.json / previous.json        0600        known-good 기록(controller가 씀)
├─ schema.json                         0600        DB schema authority(code rollback 뒤에도 유지)
├─ dirty.json / operation.lock                     작업 중 journal · 잠금. 남아 있으면 다음 작업 거부
├─ release-compose.json                0600        image 안 compose.yaml을 렌더한 결과
└─ releases/                           root 0755   <revision>/web, current → <revision>/web
                                                   /srv/daesingo 에 read-only bind mount(Caddy가 읽음)
```

controller 입력 검사(파일 mode가 정확히 0400/0700, symlink 금지, 소유 UID)는 `deploy/ec2.py`의 `protected()`가 원문이다.

### 4.5 `policy.json` 필드

예시 양식: [`deploy/policy.example.json`](../../deploy/policy.example.json)(의도적으로 실행 불가). 검사 원문: `deploy/ec2.py` `validate_policy()`, `parameter_path`만 `deploy/configure.py`.
**실제 값은 host 파일과 팀 Notion에만 둔다.**

| 필드 | 형식 / 검사 | 의미 |
| --- | --- | --- |
| `region` | `ap-northeast-2`만 | 코드에도 고정 |
| `repository` | `<12자리>.dkr.ecr.ap-northeast-2.amazonaws.com/<name>` | 배포 image는 이 prefix + `@sha256:`이어야 함 |
| `project` | `[a-z0-9][a-z0-9_-]{0,63}` | Compose project 이름. volume label owner 값 |
| `mysql_volume`, `media_volume` | 같은 형식, 서로 달라야 함 | 미리 만든 external volume 이름 |
| `mysql_image` | `mysql@sha256:<64 hex>` | 미리 pull한 MySQL 8.4 amd64. controller는 pull/upgrade하지 않음 |
| `mysql_uid` | 양의 정수 | MySQL image의 numeric UID(현재 이미지 `999`). password 파일 소유자 |
| `parameter_path` | `/[A-Za-z0-9/_-]+/`(끝 `/`) | §4.3 SecureString prefix |
| `log_group` | `/[A-Za-z0-9/_-]+` | 미리 만든 CloudWatch Log Group |
| `restart_policy` | `no` 또는 `unless-stopped` | API · Worker · MySQL restart(migrate는 항상 `no`) |
| `log_retention_days` | 양의 정수 | Log Group retention과 **같아야** preflight 통과 |
| `log_buffer_bytes` | 양의 정수 | awslogs non-blocking buffer |
| `disk_reserve_bytes`, `memory_reserve_bytes` | 양의 정수 | preflight 최소 여유 disk / MemAvailable |
| `packet_margin_bytes` | 양의 정수 | §3의 packet 검사 여유 |
| `decision_refs` | `RD-12b` `RD-12c` `RD-12d` `RD-12e` `RD-12f` `RD-12h` `RD-13a` `RD-13c` `RD-13d` `RD-11a` `RD-07c` 모두 비어 있지 않고 `pending` 아님 | 운영값의 결정 근거 참조 |

### 4.6 release 승인 파일 (`approvals/<revision>.json`)

양식: [`deploy/approval.example.json`](../../deploy/approval.example.json). 절차·의미: [RT-14 배포 준비 §5](../runtime/rt14-deployment.md#5-ci-publish와-ssm-실행), [공개 배포 Notes §5](../runtime/rt14-public-deployment.md#5-release-job-호환-승인-checklist).

| 필드 | controller가 강제하는 것 |
| --- | --- |
| `image`, `revision`, `config_id` | workflow 입력과 정확히 일치 |
| `rollback_targets` | 40자 SHA 목록. **`current.json`이 있으면 현재 revision이 반드시 포함**되어야 deploy 허용 |
| `schema_parent` | `schema.json`이 있으면 그 revision과 같아야 함(첫 배포는 빈 값) |
| `initial_state` | `current.json`이 없을 때만 필요: `verified-empty-owned-volumes`, 그리고 두 volume이 실제로 비어 있어야 함 |
| `backup_reference` | 비어 있으면 거부. 실제 backup 근거는 사람이 대조한다 |

이미 승격된 tuple을 그대로 다시 deploy하면 위 조건으로 거부된다(fail-closed). 재배포는 새 revision publish + 새 승인 파일로 한다.

### 4.7 Public ingress (Caddy · DDNS)

| 이름 / 파일 | 위치 | 값 분류 |
| --- | --- | --- |
| `RT14_PUBLIC_HOSTNAME` | GitHub Variable + host Caddy `EnvironmentFile` | 공개 DNS 이름(두 곳 값 동일) |
| `RT14_E2E_ALLOWED_IP` | host Caddy `EnvironmentFile`만 | **팀 Notion**(검증자 IP) |
| `/etc/caddy/Caddyfile` | root:caddy 0640 | 공개 구조 |
| Caddy `EnvironmentFile` | `/etc/caddy/rt14-public.env`, root:caddy 0640, drop-in `caddy.service.d/rt14-e2e.conf`가 지정 | 위 두 이름 |
| `RT14_DDNS_SUBDOMAIN` | `/etc/daesingo-ddns/public.env`(root 0400) | 공개 |
| DuckDNS token | `/etc/daesingo-ddns/token`(root 0400, 상위 0700) | **credential** |
| release Web mount | `srv-daesingo.mount`: `/opt/daesingo/releases` → `/srv/daesingo`, `bind,ro,nosuid,nodev,noexec` | 공개 구조 |

**host Caddyfile은 repo [`deploy/Caddyfile`](../../deploy/Caddyfile)과 다르다.** host에는 다음이 추가되어 있다.

```caddyfile
@outside not remote_ip {$RT14_E2E_ALLOWED_IP}
route {
	respond @outside "Restricted E2E" 403
	request_body {
		max_size 67108864
	}
	# 이하 handle @api / static handle은 repo와 같음
}
```

- 앱 인증이 없는 현재 상태에서 API를 허용 IP로만 여는 장치다. **repo 파일을 그대로 설치하면 인증 없는 API가 인터넷 전체에 열린다.**
- allowlist가 있는 동안 GitHub-hosted runner의 외부 smoke는 403이고, deploy/rollback/smoke job은 SSM 성공 뒤에도 FAIL로 끝난다. 외부 smoke는 허용 IP에서 `deploy/public_smoke.py`로 한다.
- 현재 EIP를 쓰므로 DDNS timer는 비활성 백업이다([공개 배포 Notes §2](../runtime/rt14-public-deployment.md#ddns-운영)).

### 4.8 AWS 리소스 요구사항

실제 이름 · ID · ARN은 팀 Notion. 요구 action/resource 범위의 원문은 [RT-14 배포 준비 §3](../runtime/rt14-deployment.md#3-iam-확인에-필요한-최소-범위).

| 요구사항 | 근거 |
| --- | --- |
| region `ap-northeast-2` 고정 | `deploy/aws.py`, `deploy/ec2.py` 상수 |
| GitHub Actions → AWS는 **OIDC**, role 이름 `ktc-github-deploy`, session 3600초 | `aws.py` `oidc()`. 장기 access key 없음 |
| ECR repository 1개, **tag IMMUTABLE** | `aws.py publish()`가 확인. tag = revision |
| EC2: Linux x86_64, Docker · Compose, host AWS CLI v2, `/usr/bin/python3` | `ec2.py` `main()` · preflight |
| EC2 → AWS는 **instance role**: ECR pull, `ssm:GetParametersByPath` + KMS decrypt, CloudWatch Logs 쓰기 | `ec2.py` preflight · `configure.py` · awslogs |
| **SSM** managed node Online, `AWS-RunShellScript`(root 실행)로 고정 controller 호출 | `aws.py ssm_payload()` |
| Parameter Store **SecureString 3종** | §4.3 |
| CloudWatch **Log Group 사전 생성**, retention = `log_retention_days` | controller는 group을 만들지 않음(`awslogs-create-group=false`) |
| Docker **local volume 2개**(MySQL · media): driver `local`, option 없음, label `com.daesingo.owner=<project>` · `com.daesingo.purpose=mysql\|media` | `ec2.py preflight()`. 첫 배포는 빈 volume |
| MySQL **8.4 amd64 image를 digest로 미리 pull** | `policy.mysql_image` |
| Security Group: TCP 80/443만 공개. 22 · 3306 · 8000은 공개 금지, API는 `127.0.0.1:8000` | [공개 배포 Notes §2](../runtime/rt14-public-deployment.md#caddy-설치갱신) |
| public ingress는 host **Caddy**(자동 HTTPS), 고정 IP는 EIP([RD-14a](../runtime/rt14-deployment-design.md)) | §4.7 |

IAM policy simulator로 권한을 볼 때는 조직 SCP의 region 조건 때문에 `aws:RequestedRegion=ap-northeast-2` context를 넣어야 실제와 같은 판정이 나온다.

## 5. GitHub Actions Secrets / Variables

원문: `.github/workflows/rt14-deploy.yml`, `rt14-oidc.yml`, `deploy/aws.py`, `deploy/public_smoke.py`.
모든 job은 `develop` ref · 이 repository ID · `RT14_EXECUTION_ENABLED == 'true'`일 때만 돈다(`rt14-oidc`는 gate 없음).

### Repository Secrets

| 이름 | 쓰는 operation | 역할 | 값 형태 | 설정/갱신 시점 |
| --- | --- | --- | --- | --- |
| `AWS_ACCOUNT_ID` | 전부(+`rt14-oidc`) | OIDC role ARN 조립 · caller account 대조 | 12자리 숫자 | 계정이 바뀔 때. 2026-10-31 Variable → Secret(공개 로그 노출 방지) |
| `RT14_IMAGE` | deploy · rollback | 배포할 exact image | §4.1 image identity | publish 성공 후 digest 확정 시. rollback이면 대상 known-good |
| `RT14_INSTANCE_ID` | deploy · rollback | SSM 대상 EC2 | `i-` + 17자리 hex | 대상 instance가 바뀔 때 |

### Repository Variables

| 이름 | 쓰는 operation | 역할 | 값 형태 | 설정/갱신 시점 |
| --- | --- | --- | --- | --- |
| `RT14_AWS_REGION` | 전부 | region 확인 | `ap-northeast-2`(다른 값 거부) | 고정 |
| `RT14_ECR_REPOSITORY` | publish | push 대상 repository 이름 | ECR 이름(`[a-z0-9]+([._/-][a-z0-9]+)*`) | repository가 바뀔 때 |
| `RT14_EXECUTION_ENABLED` | 전부 | 실행 gate | 정확히 `true`일 때만 실행 | 작업하는 팀원이 필요할 때 열고 닫음. 팀원만 쓰는 동안은 별도 승인 절차 없음(외부 공개 전환 때 다시 정함) |
| `RT14_REVISION` | deploy · rollback · smoke, secret-scan target | 배포 source revision | 40자 SHA | publish 성공 후 `RT14_IMAGE`와 함께 |
| `RT14_CONFIG_ID` | deploy · rollback | host 보호 config 선택 | §4.1 config ID | 새 config를 만든 뒤 |
| `RT14_PUBLIC_HOSTNAME` | deploy · rollback · smoke | 외부 smoke 대상 | bare hostname(scheme · path 없음) | DNS 이름이 바뀔 때. host Caddy 값과 같게 |

workflow 안에서는 `ECR_REPOSITORY`, `DEPLOY_IMAGE`, `DEPLOY_REVISION`, `DEPLOY_CONFIG_ID`, `DEPLOY_INSTANCE_ID`, `AWS_REGION`으로 이름이 바뀌어 `deploy/aws.py`에 전달된다.
`GH_TOKEN`(= `github.token`)과 OIDC token 요청 변수는 GitHub이 자동 공급한다.
`DISCORD_WEBHOOK`(repository Secret)과 organization Secret은 운영진 workflow용이며 배포 입력이 아니다.

## 6. 값은 어디에 있나

값은 적지 않는다. 위치만 적는다. 현재 팀 환경의 실제 경로 · ID · 발급 계정 · 교체 담당은 팀 Notion.

| 값 | 로컬 | AWS 배포 |
| --- | --- | --- |
| `GEMINI_API_KEY` | 개인 runtime 파일 | Parameter Store `<parameter_path>runtime-env` 안 → host `configs/<id>/runtime.env` |
| DB app password(= DB URL 안) | 개인 password 파일 + runtime 파일 | `mysql-password` SecureString + `runtime-env` 안 → host 두 파일 |
| DB root password | 개인 password 파일 | `mysql-root-password` SecureString → host 파일 |
| DuckDNS token | — | host `/etc/daesingo-ddns/token` |
| TLS 인증서 · ACME 계정 키 | — | host Caddy data directory(caddy 사용자 전용) |
| AWS account · instance · image URI | — | GitHub Secrets(값은 SSO로도 조회 가능) |
| policy 실제 값 | — | host `/opt/daesingo/policy.json` |
| 허용 IP · hostname | — | host `/etc/caddy/rt14-public.env` |

값이 바뀌면: Parameter Store 갱신 → 새 config ID로 `configure.py` → `RT14_CONFIG_ID` 갱신 → 새 승인 파일 → deploy. 기존 config ID는 고치지 않는다.

## 7. 실행 절차는 여기

| 하려는 일 | 문서 |
| --- | --- |
| 로컬 Compose · migration · API/Worker · readiness · handler 확인 | [canonical guide §7 · §8](../runtime/local-runtime-environment.md#7-준비migration실행readiness) |
| Docker Compose 구성 근거 | [RT-13(a)](../runtime/rt13a-docker-compose.md) |
| publish · deploy · rollback · 외부 smoke · 최초 실패 복구 | [공개 배포 Notes](../runtime/rt14-public-deployment.md) |
| host 준비 · 보호 config · 승인 파일 · IAM 범위 | [RT-14 배포 준비](../runtime/rt14-deployment.md) §3~§7 |
| 배포 전후 체크리스트 | [deployment runbook](../runtime/deployment-runbook.md) |
| backup · 격리 restore | [복구 acceptance](../runtime/rt14-recovery-acceptance.md), [RT-13(b)](../runtime/rt13b-backup-restore.md) |
| 실제 AWS 실행 기록 | [AWS E2E 기록](../runtime/experiments/2026-10-31-rt14-aws-real-e2e.md) |

## 8. 바꿀 때 같이 고칠 곳

- env 이름을 추가 · 삭제 · 변경: 코드 consumer → `.env.example` → canonical guide 해당 절 → 이 문서 §2 · §4.
- Recording 적용값: §3과 `.env.example`을 함께 갱신한다. Analysis 설정 변경 시에만 `ANALYSIS_PROFILE_REF`를 새 값으로 관리하고, Incident만 변경하면 유지한다.
- workflow Secret/Variable 이름: workflow → 이 문서 §5 → 팀 Notion의 실제 값 표.
- host 구조 · policy 필드 · Caddy 설정: `deploy/` 코드 또는 host 변경 → 이 문서 §4 → 필요하면 runbook.
