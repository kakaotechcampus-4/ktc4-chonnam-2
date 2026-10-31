# RT-14 공개 배포·복구 구현 / 운영 절차

**IN_PROGRESS · Refs #450 · Related #287, #460, #452, #486 · 2026-10-31**

이 문서는 [Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522291826)
§3과 [후속 요청](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522296524)의
구현 절차다. 정책 SoT는 [승인 설계](rt14-deployment-design.md) §13.6·§16.1과
[Ops Spec](ops-spec.md)다. Gate를 다시 미결로 열지 않는다.

이번 작업은 코드·runbook·로컬 검증만 한다. AWS 조회/변경·배포·SG 개방·DDNS 등록·
공개 인증서 발급·workflow dispatch를 실행하지 않았다. 실행 변수는 변경하지 않으며
`RT14_EXECUTION_ENABLED=false` 유지가 작업 조건이다. **로컬 검증은 공개 배포 완료나
RT-14 종료의 증거가 아니다.**

## 1. 변경 구조와 승인 대응

| 승인 요구 | 구현 | 검증 |
| --- | --- | --- |
| rollback tip 독립 | `aws.main`은 publish/deploy만 tip CI 검사. remote의 target ancestry/push CI/ECR digest 유지 | `test_aws_deploy.py` pending/failed tip, 대상 검증/SSM 실패 |
| release-bound Web | Docker Web build stage, 같은 REVISION, version/전체 파일 manifest. runtime image에 함께 COPY | `test_web_artifact.py`, 실제 npm/Docker Web stage build |
| 검증한 image 게시 | publish가 단 한 번 build한 image의 Web/media/OCR를 검사하고 그 tag를 push | workflow exact image acceptance; 실제 ECR은 미실행 |
| pointer·state | host 내부 PASS → promotion intent → symlink replace → previous/current → state_promoted → dirty unlink/fsync | Linux 실제 파일 + 경계 fault injection |
| 최초 배포 복구 | §4. current 없는 populated volume/project의 자동 인수 금지 유지 | 초기 실패·빈 volume·retry 거부 회귀 |
| Caddy·DDNS·TLS | host Caddyfile, 별도 updater/service/timer; Compose는 기존 4개 service | 실제 loopback Caddy adapt/validate/TLS/route, 합성 DDNS |
| 외부 smoke | post-SSM deploy/rollback, 별도 smoke operation/CLI | DNS/TLS/status/revision 실패 회귀, loopback 합성 통합 |
| secret·기존 gate | 기존 reusable secret-scan dependency 유지. runtime secret은 보호 config만 | secret focused regression, 비노출 synthetic sentinel |
| job 호환·drain | §5 승인 checklist; controller에 자동 drain/restore 없음 | 기존 Worker focused regression, 실제 rehearsal는 pending |

### Build-time과 runtime

`REVISION`은 공개 가능한 source identity다. production에서는 40자 SHA를 넣고,
기존 local/일반 CI build는 `local` marker를 허용한다. host와 public smoke는 `local`을
배포 revision으로 받지 않는다. Web은 상대 API URL을 그대로 사용하며 별도 public
API key/endpoint env가 필요 없다. `API_PROXY_TARGET`은 Vite dev server 전용이다.
Docker context는 필요한 Web source·JSON fixture만 추가하며 `.env*`·credential·key
제외를 유지한다. provider/DB/DDNS/TLS secret을 build arg/env/bundle에 넣지 않는다.
개인 로컬 build에는 비공개 `VITE_*`를 공급하지 않는다. 배포 image build에는 그런
입력을 전달하지 않는다. 기존 공개 fixture의 개인정보 적합성은 별도 P0 검수다.

host는 pull한 exact image에서 `docker create`/`docker cp`로 Web을 임시 staging하고,
revision·전체 파일 SHA-256 manifest를 검사한다. `releases/<SHA>/web`은 읽기 전용으로
게시하고 previous/candidate 디렉터리를 자동 삭제하지 않는다. 기존 revision 경로를
새 bundle로 덮어쓰지 않는다. 파일 manifest는 image digest 신뢰의 대체물이 아니다.

## 2. 운영자 입력과 host ingress 준비

아래는 **향후 별도 운영 작업**이다. 실제 값은 비공개 운영 기록에서 공급한다.

| 입력 | 공급·보관 |
| --- | --- |
| `RT14_PUBLIC_HOSTNAME` | 운영자가 소유/관리하는 bare DDNS hostname. repo Variable과 Caddy service 환경에 동일하게 공급 |
| `RT14_REVISION`, `RT14_CONFIG_ID` | 승인 SHA, immutable config ID. 기존 workflow Variable |
| `RT14_IMAGE`, `RT14_INSTANCE_ID` | 기존 workflow Secret. 전체 값/ARN/IP는 공개 기록 금지 |
| account/region/ECR repository | account는 Secret `AWS_ACCOUNT_ID`(2026-10-31 Variable에서 변경, Ops §2-1), region · ECR repository는 Variable. 실제 identity 대조 |
| policy·volume·MySQL digest/UID·Log Group | 기존 [준비 절차](rt14-deployment.md) §4. 운영자 선택·권한·소유권 확인 |
| runtime config·packet·메모리/disk/log buffer | Owner 승인 실측값. #452 profile/한도에 근거 없는 기본값 없음 |
| release approval | exact tuple, schema_parent, rollback_targets, backup_reference, §5 job compatibility 근거 |
| DDNS token | `/etc/daesingo-ddns/token`, root0400, 상위 root0700. 값은 argv/env/Git/log에 넣지 않음 |
| DDNS subdomain | `/etc/daesingo-ddns/public.env`의 `RT14_DDNS_SUBDOMAIN=<operator-subdomain>`; token과 분리 |
| Caddy 패키지 버전·TLS 상태 | 운영자가 검증/고정한 공식 패키지, 지속되는 Caddy data directory. 실제 계정·키 출력 금지 |

### Caddy 설치·갱신

1. 팀에 host 변경과 배포 창을 알리고 기존 80/443/8000 listener·다른 서비스를 확인한다.
   [공식 설치 안내](https://caddyserver.com/docs/install)의 Ubuntu 패키지를 버전 고정해
   운영자가 설치한다. 이번 로컬 검증 binary는 Caddy 2.11.7(공식 SHA512 대조)이며
   운영 package를 자동 설치/업그레이드하는 스크립트는 제공하지 않는다.
   설치 뒤 package가 만든 `caddy` 사용자의 UID가 container 사용자 UID(MySQL image는 `999`)와
   겹치지 않는지 확인한다. 겹치면 인터넷에 노출된 Caddy가 그 container process에 signal을 보낼 수
   있다. 2026-10-31 점검에서 실제로 겹쳤고(파일 · `/proc` 접근은 차단 확인), 유지보수 때 UID를 바꾼다.
2. `deploy/ec2.py`, `web_artifact.py`, `configure.py`, 필요 시 `ddns.py`를 승인 source의
   SHA-256과 대조하여 root 소유 controller에 함께 설치한다. 기존 두 파일만 설치된
   host는 새 helper도 필요하다. controller는 배포 중 자동 교체하지 않는다.
3. `/opt/daesingo`·configs·approvals의 private 0700 계약은 유지한다. public-only
   `/opt/daesingo/releases`를 root0755로 만들고 `/srv/daesingo`에 **read-only bind mount**한다.
   mount source/target을 운영자가 확인하고 persistence(fstab 또는 mount unit)를 구성한다.
   Caddy는 `/srv/daesingo/current`만 읽고 configs·approvals에는 접근하지 못해야 한다.
   Caddy unit은 해당 mount 뒤에 시작하도록 `RequiresMountsFor=/srv/daesingo`를 둔다.
   private root를 world-readable로 바꾸거나 앱 secret을 public tree에 복사하지 않는다.
4. `deploy/Caddyfile`을 root 소유 설정으로 설치한다. service drop-in에서 non-secret
   hostname 환경을 공급한다. Caddy data directory(ACME 계정·개인키·인증서)는 package
   전용 사용자만 읽도록 보존하며 app release와 함께 삭제/rollback하지 않는다.
5. 운영자는 `caddy adapt`/`caddy validate` 결과를 비공개로 확인하고 `systemctl reload caddy`로
   갱신한다. 실패 시 기존 승인 설정 복원 후 validate/reload한다. 서비스 설치·갱신은
   controller의 책임이 아니며 Docker daemon을 재시작하지 않는다.
6. public DNS와 ACME 발급은 SG 개방 이후 실제 acceptance다. 자동 HTTPS는 Caddy가
   담당한다. 80은 인증/HTTPS redirect, 443은 HTTPS다. 22/3306/8000 공개 금지.
   **SG 개방 전에 §7 hardening P0를 충족한다.**

`handle @api`는 `/cases*`·`/health*`를 prefix stripping 없이 loopback API로 넘긴다.
static fallback은 별도 handle이며 SPA index fallback, response rewrite, proxy cache를
두지 않는다. marker/static/API는 `Cache-Control: no-store`다. Caddy request log는
활성화하지 않고 기본 logger output은 discard하여 민감 query/upstream 오류를 journal에
남기지 않는다. 그 대신 외부 smoke와 서비스 상태를 감시해야 한다.
기본 동작은 [handle](https://caddyserver.com/docs/caddyfile/directives/handle)과
[reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)를 따른다.

body-size/업로드 timeout을 새 기본값으로 제한하지 않는다. 실제 업로드 상한·idle 경계는
기존 API 계약/B-U1·B-U3·B-U4 및 #452와 대조하는 별도 acceptance 항목이다.
배포 중 API 정지 시 Caddy는 upstream 오류(로컬 검증 502)를 보낸다. Web이 응답한다고
정상 서비스로 판단하지 않는다. maintenance 화면·새 kill switch는 이번에 추가하지 않는다.

### DDNS 운영

운영자가 등록한 subdomain과 보호 token을 준비한 뒤 `daesingo-ddns.service`와 timer를
설치한다. boot 1분 뒤, 이후 5분 간격은 **구현자가 정한 갱신 주기**이며 가용성 SLA나
capacity 승인값이 아니다. public IP를 추측하지 않고 DuckDNS HTTPS 요청의 IPv4 자동
탐지를 이용한다([공식 API](https://www.duckdns.org/spec.jsp)). stale AAAA가 없어야 하며
IPv6 운영은 별도 검토한다. 실패는 nonzero와 고정 문구만 출력한다. token은 요청 메모리에만
있고 shell/CLI argv·log·artifact에는 쓰지 않는다. redirect와 환경 proxy도 사용하지 않는다.
token rotation은 보호 파일을 교체한 뒤 service를 명시적으로 실행하고 외부 smoke로 확인한다.
EC2 IP 변경 뒤 timer 성공만으로 DNS 전파/TLS 성공을 간주하지 않는다.

**2026-10-31부터 EIP를 연결했다(RD-14a, [승인 설계](rt14-deployment-design.md) §13.2).** updater는
EIP를 DuckDNS에 등록할 때 1회 실행하고, timer는 비활성으로 두어 백업으로 남긴다. EIP를 해제하거나
잃으면 timer를 켜고 외부 smoke로 확인한다.

## 3. Pointer·상태 불변식과 reconciliation

정상 상태: `releases/current -> <current.revision>/web`, version/manifest 정상,
current/previous exact 기록과 schema authority 보존, dirty 없음이다.

| 마지막 durable phase | 예상 상태 | 다음 동작 |
| --- | --- | --- |
| dirty 없음 | pointer=current, previous artifact 보존 | 정상 검증 후 새 작업 가능 |
| quiescing | pointer/기록은 before snapshot, writer 정지 여부 불명 | 작업 생존·컨테이너·DB 조사, 자동 retry 금지 |
| migration_pending | pointer/기록 이전 값, 부분 DDL 가능 | deploy/rollback 금지, migration Owner 조사 |
| migration_complete | pointer/기록 이전 값, candidate app이 떠 있을 수 있음 | exact known-good/schema 승인일 때만 명시적 rollback |
| promotion_pending | 내부 검증 PASS 기록, pointer는 이전/대상 둘 중 하나 | 두 operation 거부, operator 대조 |
| web_published | pointer 대상, previous/current는 일부 갱신 가능 | 두 operation 거부, operator 대조 |
| state_promoted | pointer/current 대상, previous 직전 current, dirty 남음 | 두 operation 거부, operator 대조 |

dirty에는 operation·대상 release와 `before_current`, `before_previous`, `web_before`가
남는다. controller는 일반 작업 진입 때 before snapshot과 실제 기록을 대조하며 승격
중단을 자동 완료하지 않는다. 실패한 candidate가 서비스 중일 수 있어 writer/ingress
상태를 사람이 확인해야 한다. dirty를 지웠어도 pointer/current 불일치면 거부한다.

**승격 중단의 operator 절차:**

1. SSM command·controller·migrate가 종료됐는지 확인한다. 살아 있는 lock을 해제하지 않는다.
   dirty/current/previous/schema/pointer와 release.json/manifest를 보호된 incident 기록에 복사한다.
2. dirty before snapshot으로 직전 current/previous를 식별한다. pointer가 이전/대상 이외의
   값이거나 schema migration_complete를 입증하지 못하면 중단한다. 기록을 추측해서 채우지 않는다.
3. 완료 방향이면 대상 exact image/config/실제 app revision, live/ready, Worker process/8종,
   DB smoke를 **다시 검증**한다. 모든 검증이 PASS일 때에만 운영자가 root Python 세션에서
   검토된 `publish_web`/`atomic_json`을 사용하여 target pointer, previous=before_current
   (동일 release 재승격이면 before_previous 유지), current=대상 release로 맞춘다.
   dirty의 journal 전용 필드를 release 기록으로 복사하지 않는다. schema authority는 변경하지 않는다.
4. code rollback 방향이면 현재 상태를 검증한 뒤 **before pointer/current/previous metadata**를
   같은 helper로 복원하고, dirty의 phase를 `migration_complete`로 맞추는 operator 조정을
   비공개 기록한다. 이 metadata 조정 자체는 앱 복구가 아니다. 원래 before snapshot을 보존하고
   승인 known-good exact tuple/schema/대상 secret·CI 검증을 거친 명시적 rollback을 수행한다.
5. 어느 방향이든 실제 상태와 기록이 일치하기 전 dirty/lock을 제거하지 않는다. 검증이 부족하면
   중단 상태를 유지한다. 자동 unlock/retry/reconcile 명령은 제공하지 않는다.
6. 완료 후 dirty 삭제와 parent directory fsync, lock 해제, 외부 smoke를 수행한다. 외부 smoke
   실패는 public ingress부터 조사하며 host revision을 자동 변경하지 않는다.

개별 JSON은 임시 파일 fsync → rename → 부모 fsync, pointer는 같은 디렉터리 symlink
replace → 부모 fsync다. Web staging 파일/디렉터리도 fsync 후 rename한다. **여러 파일을
하나로 묶은 atomic transaction은 아니다.** Linux 로컬 회귀는 syscall 성공/예외와 실제
파일 내용을 검증한다. 실제 EC2 filesystem·전원 차단·storage controller의 내구성은
검증하지 않았으며 AWS recovery rehearsal에서 확인한다. leftover `.new`·staging은
임의 덮어쓰기/전체 prune 없이 사건 기록과 대조한 뒤 소유 작업 것만 사람이 처리한다.

## 4. 최초 배포 실패 복구 — previous가 없음

첫 deploy에는 rollback 대상이 없다. `current` 없는 populated volume/project를 다음
deploy가 자동 인수하지 않는 기존 guard를 유지한다. 아래는 **operator 통제 절차**이며
자동 volume 삭제·초기화·DB 덮어쓰기·무조건 재시도를 제공하지 않는다.

| 실패 지점 | 조사·복구 |
| --- | --- |
| preflight | writer 변경 전. artifact/자원/설정 오류만 고친다. 실제 빈 소유 volume 조건을 다시 확인 |
| quiesce/MySQL/packet, migration 전 | MySQL 초기화로 이미 populated일 수 있다. project/container와 DB/media 내용을 조사; dirty만 제거하고 retry 금지 |
| migration 중/결과 불명 | dirty/schema migration_pending. 실제 heads/table/부분 DDL과 migrate 프로세스를 조사. rollback/자동 migration 재실행 금지 |
| migration 후 start 실패 | schema는 전진했을 수 있고 일부 container 실행 가능. config·volume·이미지 identity 조사, writer 통제 |
| 내부 health/smoke 실패 | known-good 없음. 새 Worker가 job 처리했을 가능성을 배제하지 말고 DB/job/media 확인 |
| pointer 전환/기록 승격 중 | §3 snapshot 대조. current 없음이 곧 초기 empty 상태라는 뜻은 아님. 검증된 대상 승격 완료 또는 보존 복구 판단 |
| 상태 승격 후 외부 smoke 실패 | host current 존재. 최초 bootstrap reset 대상으로 삼지 않고 DNS/TLS/Caddy/SG부터 조사 |

공통 순서:

1. SSM/process/lock 종료를 확인하고 모든 상태·logs를 비공개 보존한다. 다른 작업의 자원을 건드리지 않는다.
2. current/previous 부재, 실제 사용자 데이터·job·media 부재, 이번 시도의 소유 project/volume임을
   사람이 증명해 기록한다. 하나라도 불명확하면 bootstrap reset 경로를 쓰지 않는다.
3. 데이터가 있거나 불명확하면 보존한다. migration Owner와 forward repair 또는 RT-13(b)의
   **별도 빈 target에 검증된 restore**를 선택한다. 자동 adoption을 제공하지 않으므로 복구된
   환경의 onboarding은 별도 검토 대상이다. 기존 volume 위 overwrite나 schema downgrade 금지.
4. 데이터 없는 최초 bootstrap임이 증명되고 운영자가 명시적으로 승인한 경우만 실패한 시도의
   project container를 지정해 정리한다. volume 재생성이 필요하면 운영자가 정확한 이름/label/
   mount와 백업·보존 필요성을 다시 확인한 뒤 수행한다. 이 문서에 일괄 파괴 명령은 두지 않는다.
5. 빈 owned DB/media volume, 같은 project 잔여 container 없음, config/approval 유효,
   pointer/current/previous와 dirty/schema/lock의 실제 상태를 대조한다. 조사 결과를 보존한 뒤
   operator가 marker를 해소한다. marker 해소를 복구 성공으로 기록하지 않는다.
6. `initial_state=verified-empty-owned-volumes` 승인을 새로 대조하고 deploy → 내부 검증 →
   pointer/state → 외부 smoke를 다시 수행한다. 실제 재시도 성공 전까지 실패는 열린 상태다.

### Break-glass

GitHub/Actions 장애 시 SSM Session 직접 controller rollback은 operator의 비상 경로다.
기존 [명령 예시](rt14-deployment.md#7-실패취소rollback부분-ddl)는 일반 workflow gate를
대체하는 자동 경로가 아니다. 호스트는 exact current/previous tuple과 schema를 검사하지만
GitHub secret scan/target push CI/ancestry를 직접 검사하지 않는다. 따라서 운영자는
**동일 controller source와 대상 SHA의 secret scan·develop ancestry·push CI 성공 근거 및
ECR tag/digest 검증**을 비공개 기록으로 확보한 후에만 실행한다. 최신 확인이 불가능하고
사전 검증 증거도 없으면 이 runbook은 우회를 승인하지 않는다. 실행자·사유·근거·전후 상태를
남기고 같은 내부/외부 검증을 수행한다. secret 값을 Session 명령행에 넣지 않는다.

## 5. Release job 호환 승인 checklist

- [ ] 새 handler가 이전 release의 durable job payload/kind 의미를 처리한다.
- [ ] rollback 대상 handler가 새 release가 만든 payload를 처리한다.
- [ ] kind 삭제/이름 변경이 없거나 별도 호환/8종 등록 변경을 승인했다.
- [ ] migration 후 남은 job/case 행을 새 코드와 rollback 코드가 모두 해석한다.
- [ ] schema_parent/rollback_targets/backup_reference와 이 검토 근거를 승인 기록에 연결했다.

[승인 설계 §8.2](rt14-deployment-design.md#82-queue-처리--full-drain과-graceful-stop-비교)의
네 조건 중 하나라도 해당하면 기본 graceful stop 경로로 진행하지 않는다: 새 handler의
old payload 비호환, kind 삭제/변경, job/case table 기존 행 비호환, rollback handler의
new payload 비호환. 마지막 경우 해당 revision을 rollback_targets에서 제외하는 것이 먼저다.
그 결과 현재 release rollback 승인 조건을 만족하지 못하면 controller guard를 우회하지 말고
release를 미룬다. full drain이 필요하면 API ingress를 멈춘 뒤 미래 available_at을 포함한
QUEUED와 RUNNING **모두 0**을 별도 확인하고 Worker를 정지한다. 자동 drain·대기 상한을
새로 만들지 않으며 0이 안 되면 연기한다. graceful stop은 진행 job 완료를 보장하지 않는다.

## 6. 실제 acceptance 실행 순서 / rehearsal

아래는 실행하지 않은 checklist다. 변경한 image는 과거 `7bab60bc` image와 다르다.

- [ ] push 후 CI quality/boundary/Contract, 전체 regression/mysql/test, Docker media/OCR/process,
  secret scan이 **해당 SHA**에서 PASS. skip/cancel/failure를 성공으로 해석하지 않는다.
- [ ] 운영자 입력·팀 변경 창·backup·job 호환·controller hash·config 권한·소유 volume·로그/
  capacity·instance-role 실제 권한을 확인한다. OIDC trust 축소는 accepted risk로 별도 추적한다.
- [ ] 승인된 운영 실행 시에만 enable을 별도 변경하고 새 release image를 publish한다.
  동일 image의 Web/media/OCR acceptance와 ECR SHA tag/digest를 기록한다.
- [ ] 첫 내부 deploy: EC2 pull/decrypt/awslogs/packet/migrate/API·Worker8종/internal smoke,
  pointer/current/dirty를 대조한다. 처음에는 previous 없음도 기록한다.
- [ ] 공개 전 P0 충족, DDNS·Caddy·TLS·승인 SG80/443 준비. 공개 개방 시점을 운영자가 기록한다.
- [ ] deploy/rollback workflow는 SSM 성공 뒤 외부 smoke를 필수 실행한다. 공개 경로가 아직
  준비되지 않은 내부 rehearsal run은 외부 smoke 실패 상태로 남으며 배포 성공이라고 하지 않는다.
- [ ] 첫 실패 rehearsal: 각 §4 phase에서 데이터 보존과 operator 조사를 확인한다.
- [ ] 두 번째 정상 release: previous가 첫 exact tuple인지, Web도 보존됐는지 확인한다.
- [ ] rollback: tip CI pending/failed와 무관하게 target 검증·secret gate·schema guard 확인,
  migration 미실행, old Web/API/config 일치, 외부 smoke PASS.
- [ ] pointer/state 중단 rehearsal: §3 phase별로 다음 deploy/rollback 거부 및 operator 복구를 확인한다.
- [ ] 외부 smoke 재실행: `operation=smoke` 또는 `RT14_PUBLIC_HOSTNAME`/`RT14_REVISION` 환경을
  공급한 `python deploy/public_smoke.py`. AWS/OIDC·SSM 호출 없음. 실제 응답 body/hostname은 출력하지 않는다.
- [ ] 외부 smoke 실패 시 host revision 불변 확인, DNS/DDNS/TLS/SG/Caddy부터 조사한다.
- [ ] restart/STALE, 실제 stack 로그, 운영 크기 backup/restore/capacity와 Owner acceptance를 연결한다.

실제 실행 기록은 접근 제한된 운영 incident/release 기록에 남기고 공개 Issue에는 revision,
workflow run 링크, 단계별 PASS/FAIL/UNKNOWN와 비민감 요약만 옮긴다. secret/raw response/경로/
계정/전체 image URI를 붙이지 않는다. 이 위치는 이번 구현의 기록 방식이며 팀 알림 채널의
새 정책을 확정하지 않는다.

## 7. 공개 전 남은 조건

Ops §2-4와 [pre-deploy security review](../management/pre-deploy-security-review.md)의
abuse/admission/backlog·upload/asset 보호·provider 비용 guard·실영상 허용/외부 AI 고지·
privacy/retention·샘플/진입 URL 등 **hardening P0는 SG 개방 전에 별도 충족**한다.
이 구현은 개인정보 검수나 abuse 보호 완료를 뜻하지 않는다. #452 운영 profile·분석 한도·
메모리/disk/packet 예산과 실제 first/second deploy/rollback acceptance가 남는다.
GPS, #425 time base, #470 preview는 변경 범위 밖이다.

## 8. 검증 기록

실제 AWS acceptance 기록 → [2026-10-31 RT-14 AWS 배포·Real E2E](./experiments/2026-10-31-rt14-aws-real-e2e.md).

최종 로컬 결과와 fresh review는 이 절에 실행 후 기록한다. 실제 AWS acceptance와
과거 증거를 합산하지 않는다. 최초 시작은 HEAD/원격 develop `3819a5d`, 깨끗한
`codex/rt14-public-deployment`였고 #479/#483/#484/#488/#491 병합을 GitHub에서 확인했다.
Issue #450 본문/댓글 5개를 직접 읽었다. 최신 댓글의 instance-role pull/preflight 및
controller 설치는 **기존 작성자 보고를 읽은 증거**이며 이번 세션의 AWS 직접 실행이 아니다.

### 작성자 직접 로컬 검증

| 검사 | 결과·한계 |
| --- | --- |
| rollback RED→GREEN | tip pending/failure의 기존 거부 2건 RED → AWS 경계 33 PASS. 이후 target ancestry/CI pending/failure/cancel/skip/digest 거부를 추가 |
| artifact RED→GREEN | 없는 verifier 6건 RED → 6 PASS. cached bundle+manifest 동시 변경 허용을 추가 RED로 재현, image/manifest hash 결속으로 수정 |
| state RED→GREEN | pointer/promotion fault 6건 RED → GREEN. 기존 schema fixture에 누락된 previous Web을 보충한 중간 실패 2건도 보존 |
| 외부 smoke/DDNS | 없는 smoke 15건, updater 4건 RED → GREEN. 외부 서비스 호출은 대역 |
| Linux 최종 집중 | **106 PASS**: AWS/config/state/artifact/smoke/DDNS. 실제 symlink·JSON·fsync 코드, pointer 직후 자식 프로세스 `os._exit(23)`으로 dirty/lock 보존 확인 |
| Windows focused | **136 PASS**: deploy/secret/quality 도구 및 Worker entrypoint/production readout/composition. 전체 pytest/MySQL 재실행 아님 |
| 후속 Windows guard | **58 PASS**: AWS/public smoke/DDNS; 위 focused와 중복이므로 합산하지 않음 |
| Web tests | **224 PASS / 13 files**, 작업 전용 TEMP와 동시 worker 2. 기존 jsdom media API 경고는 남고 제품 테스트는 통과 |
| Web | 실제 `npm run build --workspace=daesingo-web` PASS, 40자 marker 생성 후 전체 manifest 검증 PASS |
| Docker Web | pinned Node stage 실제 build PASS. 기존 production base에 같은 stage를 COPY한 경계 image build + network-none manifest 검사 PASS |
| Docker 한계 | 최종 Dockerfile 전체 media/Paddle 재빌드는 하지 않음. 경계 image는 새 production acceptance image가 아니며 push하지 않음. 최종 exact production image acceptance는 push 후 CI/publish 조건 |
| Caddy | 공식 2.11.7 SHA512 검증. 실제 adapt/validate + loopback HTTPS/Web revision/same-origin 경로·404/503/502 PASS. 합성 DNS mapping·로컬 self-signed CA이며 public DNS/ACME acceptance 아님 |
| quality | Ruff PASS, mypy Linux/win32 각각 87 source files PASS |
| boundary/Contract | boundary PASS, 문서62/JSON26/semantic104 PASS |
| workflow/diff | actionlint(rt14-deploy/secret-scan), `git diff --check` PASS |
| 실행 변수 | GitHub CLI로 해당 Variable 한 개 읽기 확인: `false`. 변경·dispatch 없음 |

첫 로컬 Web build는 기존 node_modules의 Pretendard 누락으로 실패했다. 잠금파일 기준
`npm ci` 후 실제 build가 성공했다. Linux artifact 회귀 추가 중 파일 fsync와 staging directory
rename의 권한 문제를 확인하여 파일 fsync 뒤 chmod, rename 뒤 최상위 chmod 순서로 보완했다.
Windows 기본 pytest temp 권한 오류는 작업 전용 basetemp 재실행과 구분한다. Caddy checksum은
처음 SHA256으로 비교해 거부했으며 공식 파일의 SHA512를 확인한 뒤 일치 검사 후에만 실행했다.
이 실패들을 product/AWS 실패나 성공 증거로 바꾸어 기록하지 않는다.

### Fresh review

구현 이력을 상속하지 않는 `GPT-6.1 Sol / high` read-only subagent를 명시 호출했다.
원래 요청·Owner 승인/후속 댓글·설계·최종 diff와 새 파일을 제공했다. 1차 검토에서
actionable product defect는 없었다. reviewer 직접 실행은 Windows 65 PASS,
Linux state/artifact 38 PASS, 실제 loopback Caddy PASS, diff 검사다. 작성자 136/98
회귀·build·quality 근거 열람은 직접 실행으로 세지 않는다. AWS는 실행하지 않았다.
exact tuple 회귀가 잘못된 dirty journal에서 먼저 거부된다는 테스트 보완 의견을 반영해
정상 state에서 config/image mismatch를 각각 검사하도록 바꿨다. 같은 reviewer가 수정 delta를 다시 읽고 Linux 11 PASS(22 deselected)를 직접 실행했다.
config/digest exact 거부·8단계 실패의 old pointer 유지·실제 process exit 보존을 확인했고
잔여 actionable product finding은 없었다. 지적된 Log EOF 공백은 수정 후 diff 검사를 통과했다.

### 변경 파일 전체 목록

| 파일 | 내용 |
| --- | --- |
| `.dockerignore` | 필요한 Web source/fixture/helper만 context 허용 |
| `.github/workflows/rt14-deploy.yml` | exact Web acceptance, post-SSM/독립 smoke |
| `Dockerfile` | pinned Web build stage와 runtime 포함 |
| `README.md` | deploy 구성 사실·실행 링크 정합화 |
| `deploy/aws.py` | rollback tip gate 분리 |
| `deploy/ec2.py` | Web staging, journal, pointer/state/reconciliation |
| `deploy/web_artifact.py` | marker·전체 file manifest 검증 |
| `deploy/public_smoke.py` | DNS/TLS/Web/revision/API 읽기 검증 |
| `deploy/Caddyfile` | host HTTPS·same-origin static/proxy |
| `deploy/ddns.py` | 보호 token DDNS 갱신 |
| `deploy/daesingo-ddns.service` | host oneshot |
| `deploy/daesingo-ddns.timer` | boot/주기 갱신 |
| `docker/web_release.mjs` | source revision/manifest 생성 |
| `tests/deploy/test_aws_deploy.py` | rollback 독립성과 대상 거부 |
| `tests/deploy/test_ec2_deploy.py` | pointer/state fault·process exit·초기 복구 |
| `tests/deploy/test_web_artifact.py` | bundle/revision/hash 변조 거부 |
| `tests/deploy/test_public_smoke.py` | DNS/TLS/HTTP 실패·비노출 |
| `tests/deploy/test_ddns.py` | 합성 응답·비노출 |
| `tests/deploy/public_ingress_acceptance.py` | opt-in loopback Caddy rehearsal |
| `docs/runtime/rt14-public-deployment.md` | 이 Notes·runbook·증거·acceptance |
| `docs/runtime/rt14-deployment.md` | 과거 이력 보존·현재 절차 연결 |
| `docs/runtime/deployment-runbook.md` | 현재 공개/복구 체크리스트 연결 |
| `docs/runtime/ops-spec.md` | 승인 구현 연결·rollback gate 구분 |
| `docs/runtime/open-decision-register.md` | 승인 유지·실제 acceptance pending 연결 |
| `docs/runtime/runtime-implementation-log.md` | 이번 구현과 검증 이력 append |
| `docs/superpowers/plans/2026-10-31-rt14-public-deployment.md` | 작업 계획·ruling·검증 ledger |

기존 `deploy/configure.py`, secret-scan workflow, 운영진 workflow/CODEOWNERS,
regression/mysql/test·inventory/timeout/strict/skip 정책과 제품 Worker 코드는 변경하지 않았다.


추가 환경 실패: Web 기본 임시 변환파일 ENOENT(10 suite 실패/74 test 통과), PowerShell
래퍼 오류/OOM을 숨기지 않는다. 작업 전용 TEMP, npm.cmd, 동시 worker 2로 재실행해
13 suite/224 test PASS를 확인했다. 테스트 내용·timeout·skip 정책은 변경하지 않았다.
secret scanner는 sandbox controls17 실패/17 오류, 표준 권한 retry의 history 실행 실패가
있었다. 초기 snapshot은 findings0/exceptions2였으나 전체 성공으로 세지 않았다.
작업 전용 TEMP와 GOMAXPROCS=2 재실행에서 synthetic controls17 PASS를 확인했다.
최종 counts-only scan은 현재 파일2331/findings0/exceptions2, HEAD1535 commits/findings0/exceptions24,
A01 12회/A02 14회, status=clean으로 통과했다. target 조상 검증도 포함했다.
예외는 기존 RT-15의 두 항목이며 이번 작업에서 추가하거나 완화하지 않았다. 원문 탐지 보고서는 출력/게시하지 않았다.


최종 정리: 작업 전용 Docker image 두 개의 ID를 대조해 tag를 제거했다. 해당 경계 container는
`--rm` 종료했고 Caddy/합성 API 프로세스는 harness가 종료·wait했다. 공유 cache/base image와
다른 작업 scratch는 보존했다. 작업 전용 temp만 정리하며 작은 실패/성공 요약은 ignored
scratch에 남긴다. 26개 변경 파일은 미스테이징·미커밋 상태다.
