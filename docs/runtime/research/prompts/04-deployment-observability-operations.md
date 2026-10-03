# Research Prompt 04 — Deployment / Observability / Operations

> **추적 정보** — 이 블록은 조사 대상이 아니다. 결과 문서에서 근거를 Decision ID에 연결하는 데만 쓴다. 아래 문서명은 조사자가 열람할 수 없고 열람할 필요도 없다.
>
> - Source: 대신고 `decision-classification.md` §6 External Research Queue
> - Part A · R2 · RD-12 — ECR pull vs host build · SSM Run Command 배포 · MySQL container volume backup / restore · migration 실행 순서
> - Part B · R2 · RD-13a · RD-11a — log transport · Docker log rotation · 보관 설정 위치
>
> 사용법: 이 파일 전체를 새 웹 리서치 대화에 그대로 붙여 넣는다.

---

다음 기술 조사를 수행하세요. 주제는 **EC2 1대 위의 Docker Compose 서비스(api · worker · mysql)를 배포 · 롤백 · 백업하는 운영 패턴, 그리고 container log를 수집 · 회전 · 보관하는 수단의 운영 차이**입니다.

이 조사는 결정을 내리는 작업이 아닙니다. 아래 Decision의 **선택지 · 제약 · failure mode · 검증 항목을 현실화하는 근거**를 모으는 작업입니다. 최종 선택은 별도 단계에서 팀이 합니다.

**이 조사는 새 topology를 추천하는 조사가 아닙니다.** Kubernetes · ECS · RDS · ALB · 추가 EC2로의 전환을 제안하지 말고, 아래 baseline 안에서의 선택지만 다루세요.

## 1. 프로젝트 맥락

**대신고**는 블랙박스 영상을 받아 교통법규 위반 신고 자료 준비를 보조하는 서비스입니다. 사용자가 영상을 올리면 서버가 비동기로 영상 변환(ffmpeg), 외부 AI API 호출을 통한 후보 구간 탐색, 번호판 판독 등을 실행합니다. 6명 팀의 10주 MVP입니다.

**현재 Runtime baseline(이미 정해짐):**

- **EC2 1대** — t3.medium(2 vCPU · OS 기준 약 3.7 GiB usable RAM) · Ubuntu 24.04 · gp3 50 GiB root EBS 1개
- **Docker Compose**로 세 service를 띄운다
  - `api` — FastAPI process 1
  - `worker` — Worker process 1 (concurrency 초기값 1)
  - `mysql` — MySQL 8.4 LTS. 작업 queue(DB Queue)와 실행 원장을 담는다. data는 container layer와 분리된 volume에 둔다
- api와 worker는 같은 dependency baseline의 image이고 command만 다르다
- RDS · ALB · Elastic IP · 추가 EC2는 가정하지 않는다
- Python 3.12

**배포 경로에서 이미 정해진 것:**

- GitHub Actions가 **OIDC**로 AWS deploy role을 assume한다. GitHub Actions용 장기 AWS Access Key는 없다.
- EC2 접근은 **SSM Session Manager / Run Command**로 한다. SSH key 저장 · 22번 port 개방은 하지 않는다.
- secret을 image에 넣지 않는다(bake 금지).
- **배포 성공의 정의:** 배포된 revision을 식별할 수 있고 + health/readiness 확인 + 외부 smoke 통과 + 직전 known-good revision을 식별할 수 있음.
- revision은 commit SHA로 식별한다. registry를 쓰면 `latest` tag에만 의존하지 않는다.
- **DB migration은 자동 rollback 대상으로 가정하지 않는다.**
- Blue-Green · Canary는 기본값이 아니다.

**AWS 계정 쪽 사실:**

- S3 · ECR · CloudWatch는 사용 가능한 서비스지만 **현재 ECR repository · CloudWatch Log Group은 없다.** 새로 만들려면 운영 측 확인이 필요할 수 있다.
- EC2 instance role에는 SSM managed-instance 권한과 CloudWatch Agent server용 권한이 준비돼 있다. **CloudWatch Agent는 서버에 설치돼 있지 않다.**
- 운영 측은 Docker build cache 누적을 disk 부족의 가장 흔한 원인으로 안내한다.
- 50 GiB disk를 MySQL data · Docker image/layer · 영상 temp · 파생 영상 · log · OS가 함께 쓴다.

**관측 쪽에서 이미 정해진 것:**

- 1차 관측 수단의 방향: application은 structured log(key-value / JSON)를 stdout으로 낸다 → AWS log 수집 + Runtime DB query + 사용량 원장 + EC2 기본 지표.
- Prometheus · Grafana · OpenTelemetry full stack은 baseline이 아니다.
- 근거 없는 CPU · disk · alert threshold를 만들지 않는다. **alert threshold 숫자는 이번 조사에서 만들지 않는다** — 배포 환경이 생긴 뒤 실측 대상이다.

## 2. 이 조사가 근거를 제공할 Decision

| ID | 열린 질문 | 우선순위 |
| --- | --- | --- |
| RD-12b | artifact 전달 방식 — EC2에서 build / registry(ECR) pull / 기타 | R2 |
| RD-12c | image tag · digest convention과 known-good revision 기록 위치 | R2 |
| RD-12d | SSM Run Command로 실행할 배포 명령과 순서 | R2 |
| RD-12e | rollback exact 절차 | R2 |
| RD-12f | DB migration 실행 시점 · 순서와 restore 절차 | R2 |
| RD-12g | MySQL volume · backup baseline | R2 |
| RD-12h | post-deploy health/readiness + 외부 smoke 연결 | R2 |
| RD-13a | production log transport — CloudWatch Agent / Docker logging driver / 기타 | R2 |
| RD-11a | 운영 log 보관 기간과 rotation 방식 — **이번 조사는 「어디서 · 어떻게 설정하는가」만**. 보관 기간 값은 정하지 않는다 | R2 |

RD-12a(Dockerfile 구조 · Compose entrypoint)는 application 실행 단위 구현 뒤 정하는 항목이라 이 조사의 직접 대상이 아닙니다. 답이 RD-12a에 영향을 주면 그 점만 표시하세요.

## 3. 조사 질문

필요한 경우 인접 질문까지 확인하되, **위 Decision을 닫는 데 필요한 범위로 제한**하세요.

### Part A (R2 · RD-12) — Deployment

#### Q-A1 — ECR image pull vs EC2 host build

단일 EC2 + Docker Compose 기준으로 다음 축을 비교하세요.

1. **revision 식별** — 실행 중인 container가 어느 commit에서 왔는지 확인하는 방법(image tag · digest · label · build metadata).
2. **reproducibility** — 같은 commit을 다시 배포했을 때 같은 결과가 나오는가(base image · dependency 해석 시점 차이).
3. **rollback** — 직전 known-good으로 돌아가는 데 필요한 것(이전 image가 어디에 남아 있는가 · 다시 build해야 하는가).
4. **build resource consumption** — host build가 운영 중인 api · worker · mysql과 CPU · RAM · disk를 경쟁하는 방식, build cache 누적, burstable instance(T3)에서 build가 CPU credit에 주는 영향(instance의 credit 설정은 대신고 쪽 확인 대상).
5. **deployment duration** — 각 방식에서 시간이 걸리는 단계의 구조(수치를 baseline으로 만들지 말 것).
6. **artifact provenance** — image가 어디서 · 누가 · 어떤 입력으로 만들었는지 증명하는 수단(registry digest · build attestation · SBOM 등)이 각 방식에서 어디까지 가능한가.
7. **ECR 운영 요소** — EC2가 ECR에서 pull하기 위한 인증(instance role · credential helper · 로그인 토큰 수명), image tag immutability 설정, lifecycle policy, image 저장 비용 구조. GitHub Actions에서 OIDC role로 push하는 흐름.
8. S3를 경유해 image tarball을 전달하는 방식 등 다른 대표 방식이 있으면 같은 축으로 짧게 포함하세요.

#### Q-A2 — AWS SSM Run Command를 사용한 배포

1. **deploy sequence** — GitHub Actions(OIDC) → SSM `SendCommand` → EC2에서 Compose 명령을 실행하는 대표 흐름. 명령 문서(`AWS-RunShellScript` 등) 선택, 실행 user · working directory · 환경.
2. **command failure** — 명령 중간 실패 시 SSM이 보고하는 status, exit code 전달, timeout(실행 timeout · delivery timeout), GitHub Actions 쪽에서 완료를 기다리고 결과를 판정하는 방식.
3. **partial deployment** — 일부 service만 새 image로 바뀐 상태가 생기는 조건(예: api는 재생성됐는데 worker는 실패). `docker compose up`의 재생성 · 순서 동작.
4. **health check** — Compose `healthcheck` · `depends_on` 조건 · `docker compose up --wait` 등이 배포 판정에 쓰일 수 있는 범위와 한계. 외부 smoke와 container health의 차이.
5. **restart** — Compose `restart` policy의 종류와 host 재부팅 · Docker daemon 재시작 · container crash 때의 동작.
6. **rollback** — 이전 revision으로 되돌리는 명령 패턴, rollback도 실패할 때의 상태.
   - rollback 대상인 **직전 known-good revision을 어디에 기록하는가**의 대표 패턴(host의 파일 · SSM Parameter Store · GitHub Deployments / Releases · registry tag 등)과, 각 위치가 배포 실패 · host 재생성 때 남아 있는지
   - Compose 파일 자체(service 정의 변경)도 revision과 함께 되돌려야 하는 경우의 처리
7. **output · 노출** — SSM 명령 output을 어디에 남길 수 있고(콘솔 · S3 · CloudWatch) 그 output에 secret이 섞일 위험.

#### Q-A3 — MySQL container 운영

1. **persistent volume** — MySQL data directory를 named volume · bind mount에 둘 때의 차이, container 재생성 · image upgrade 시 data 유지 조건.
2. **backup** — logical dump(`mysqldump` · MySQL Shell dump utility 등)와 volume-level backup(파일 복사 · EBS snapshot)의 **개념 차이**: 일관성(InnoDB 실행 중 파일 복사의 위험) · lock 영향 · 복원 단위 · 복원 시간 구조 · 크기. backup 산출물을 같은 disk에 둘 때와 밖(S3 등)에 둘 때의 차이.
3. **restore** — 각 backup 방식의 restore 절차와 restore 검증 방법.
4. **MySQL 8.4 version upgrade** — container image의 MySQL minor · LTS 버전이 바뀔 때 data directory upgrade가 자동으로 일어나는지와 되돌릴 수 있는지.

#### Q-A4 — migration과 deploy 실행 순서

1. 새 application image 배포와 DB schema migration 중 무엇을 먼저 실행하는 패턴들이 있는가 — migration 먼저 / 배포 먼저 / expand-contract(병행 호환 단계를 두는 방식).
2. **backward compatibility** — 이전 version application이 새 schema에서, 새 version이 이전 schema에서 돌 수 있어야 하는 조건. api와 worker가 잠시 서로 다른 version으로 돌 수 있는 상황.
3. **failure 시 rollback** — MySQL DDL의 implicit commit과 MySQL 8.x atomic DDL의 보장 범위를 확인하고, 여러 단계로 된 migration이 중간에 실패했을 때 남을 수 있는 상태를 정리하세요. application rollback은 가능하지만 schema rollback은 자동으로 하지 않는다는 전제에서 가능한 복구 경로(backup restore · forward fix · down migration).
4. migration을 배포 sequence의 어느 단계에서 · 어떤 실행 단위(one-off container · 별도 service · application startup)로 돌리는지가 Q-A2의 partial deployment와 어떻게 맞물리는가.

### Part B (R2 · RD-13a · RD-11a) — Log transport / rotation / retention

**세 가지를 서로 다른 문제로 구분하세요.**

- **log transport** — log를 host 밖(CloudWatch Logs 등)으로 보내는 경로
- **log rotation** — host disk 위 log 파일이 무한히 커지지 않게 자르는 것
- **log retention** — 보낸 곳(또는 host)에서 log를 얼마나 남겨 두는가

비교할 수단(예시이며 더 있으면 포함):

1. CloudWatch Agent가 host의 log 파일(Docker container log 파일 포함)을 읽어 CloudWatch Logs로 전송
2. Docker `awslogs` logging driver로 container stdout/stderr를 직접 CloudWatch Logs로 전송
3. Docker `json-file`(또는 `local`) logging driver + rotation 설정으로 host에만 보관

각 수단에 대해:

1. **stdout/stderr collection** — container stdout/stderr가 어떤 경로로 수집되는가. host log(syslog · journald · Docker daemon log)와 container log의 구분.
2. **structured JSON** — 한 줄 JSON log가 수집 뒤에도 구조를 유지하는가(CloudWatch Logs Insights에서 필드로 조회 가능한가). multi-line(stack trace) 처리.
3. **log rotation** — 어디서 설정하는가(Docker daemon `daemon.json` 기본값 · Compose service `logging:` · logrotate). `json-file` 기본 설정에서 rotation이 켜져 있는가. `awslogs` 사용 시 host에 log 파일이 남는가(Docker의 dual logging 등).
4. **retention** — CloudWatch Log Group retention의 기본값과 설정 위치, host 쪽 보관과의 관계.
5. **disk growth** — 각 수단에서 host disk가 log로 커질 수 있는 경로.
6. **restart behavior** — container · Docker daemon · host 재시작, CloudWatch Agent 재시작 때 log 유실 · 중복 가능성.
7. **CloudWatch Logs delivery** — 전송 실패 · 네트워크 단절 때의 동작. `awslogs` driver의 blocking / non-blocking mode와 buffer가 application(stdout write)에 주는 영향.
8. **IAM** — 각 수단이 어떤 credential로 전송하는가(Docker daemon이 instance role을 쓰는지 · Agent가 쓰는지), 필요한 IAM action, Log Group 자동 생성 권한.
9. **failure visibility** — 수집 경로 자체가 실패했을 때 운영자가 그것을 어떻게 알 수 있는가. `docker logs`로 로컬 확인이 여전히 가능한가.
10. **configuration ownership** — 설정이 어디에 놓이는가(Compose 파일 · host `daemon.json` · Agent 설정 파일 · AWS 콘솔/IaC)와, 그 결과 배포 절차(Part A)가 무엇을 함께 관리해야 하는가.
11. **비용 구조** — CloudWatch Logs 수집 · 저장 · 조회 과금 단위(확인일 기준 공식 가격으로만 적고 대신고 사용량을 추정하지 말 것).

## 4. 범위 밖

다음은 조사하지 마세요.

- Kubernetes · ECS · RDS · ALB · 추가 EC2 등 새 topology 추천
- 공개 endpoint · domain · TLS · reverse proxy 구성
- scaling · Worker 수 증가 판단
- alert threshold · restart threshold 숫자
- log 보관 기간 값 자체(개인정보 · 비용 · 실측과 함께 정할 값)
- 개인정보 보관 · 파기 법령
- Prometheus · Grafana · OpenTelemetry stack 도입 추천

## 5. 조사 방법

자료 우선순위:

1. 기술 자체의 최신 공식 문서 (Docker · Docker Compose · MySQL 8.4)
2. 공식 AWS 문서 (ECR · Systems Manager Run Command · CloudWatch Logs · CloudWatch Agent · EC2 · EBS · IAM)
3. 신뢰할 수 있는 engineering / architecture 자료
4. 해당 OSS의 공식 GitHub issue · discussion · source
5. 커뮤니티 글은 보조 근거로만

- 현재 시점 기준 최신 정보를 확인하세요.
- **버전을 반드시 구분하세요.** 현재 Docker Engine · Docker Compose v2 · MySQL 8.4 · 현재 AWS SSM / CloudWatch 동작 기준입니다. Docker Compose v1 · MySQL 8.0 · 구버전 CloudWatch Logs agent 동작을 현재 동작처럼 쓰지 마세요.
- 공식 문서가 명시하지 않은 동작은 「문서에 명시 없음」으로 표시하고 추정하지 마세요.

## 6. 출력 원칙

**사실 · 해석 · 적용을 섞지 마세요.** 각 주장에 다음 중 하나를 표시하세요.

- **Verified fact** — 공식 문서 등이 직접 말하는 사실. 출처 필수
- **Interpretation** — 여러 근거를 종합한 해석. 근거 목록 필수
- **Daesingo implication** — 위 대신고 구조에 적용했을 때의 의미

**최종 선택을 하지 마세요.** 「따라서 ECR을 써야 한다」 「따라서 awslogs를 써야 한다」 「따라서 mysqldump로 매일 backup한다」 같은 결론을 쓰지 않습니다. 선택지와 trade-off까지만 정리합니다.

**외부 숫자를 대신고 baseline으로 쓰지 마세요.** 다른 서비스가 「log 보관 30일」 「backup 주기 N시간」 「max-size N MB」 「health check 간격 N초」를 쓴다면, 그 숫자는 **그 환경의 숫자이며 대신고에 직접 적용할 수 없다**고 구분해서 적으세요. 도구의 기본값은 Verified fact로 적되 「기본값」임을 표시하세요.

**작성 언어와 기준일.** 결과는 한국어로 쓰고, 기술 용어 · 설정 이름 · 원문 인용은 영어 그대로 둡니다. 결과 맨 위에 조사 기준일을 적으세요.

**제출 전 자기 점검.** 결과를 내기 전에 「~해야 한다」 「~가 최선이다」 「권장한다」처럼 선택을 확정하는 문장이 남아 있는지 확인하고, 있으면 조건과 trade-off를 설명하는 문장으로 바꾸세요. 출처가 없는 Verified fact가 있으면 Interpretation으로 내리거나 9절(Unresolved)로 옮기세요.

## 7. 결과 형식

다음 구조로 작성하세요. 3 · 4 · 5 · 6절 안에서는 **Part A(Deployment)와 Part B(Logging)를 소제목으로 나눠** 적으세요.

```markdown
# Research Result — Deployment / Observability / Operations

## 1. Executive Summary
- 조사 결과의 핵심 사실만 (Part A · Part B 각각)
- 최종 Decision 추천은 하지 않음

## 2. Questions Investigated
- Q-A1 ~ Q-A4 · Part B 질문별 실제 조사 범위

## 3. Verified Technical Facts
### Part A
| Fact | Version / Condition | Evidence |
### Part B
| Fact | Version / Condition | Evidence |

## 4. Options / Patterns
### Part A — artifact 전달 · 배포 sequence · backup · migration 순서
### Part B — log transport · rotation · retention 수단 (세 문제를 구분해서)
- 각 항목에 trade-off

## 5. Failure Modes / Operational Risks
### Part A
| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
### Part B
| Failure mode | 발생 조건 | 영향 | 완화 가능성 |

## 6. Daesingo-specific Implications
### Part A
### Part B
- 현재 대신고 구조에 직접 적용되는 제약
- 어떤 RD / sub-decision(RD-12b~h · RD-13a · RD-11a)에 영향을 주는지

## 7. What External Research Cannot Decide
- 대신고 내부 합의가 필요한 것
- 실험이 필요한 것 (예: 실제 build 시간 · log 양)
- External Input이 필요한 것 (예: AWS 자원 생성 승인)

## 8. Suggested Pre-implementation Checks
- 필요 시 작은 spike (예: OIDC → SSM Run Command 왕복, backup → restore 1회, logging driver 설정 확인)
- 실제 production baseline 숫자를 만들지는 않음

## 9. Unresolved / Unverified
- 확인하지 못한 사실
- 문서 간 불일치
- 추가 확인 필요사항

## 10. Sources
- URL
- 문서명
- 버전 / 게시일 또는 확인일
```

## 8. Research Completion Criteria

이 조사는 다음에 답할 수 있을 때 완료입니다.

**Part A**

- 단일 EC2 + Compose에서 ECR pull과 host build의 차이를 revision 식별 · reproducibility · rollback · build 자원 · 배포 시간 구조 · provenance 축으로 설명할 수 있는가?
- SSM Run Command 배포의 실패 · partial deployment · rollback 동작과 그 판정 방식을 설명할 수 있는가?
- MySQL container의 logical dump와 volume-level backup의 개념 차이와 restore 절차를 설명할 수 있는가?
- migration과 배포 순서 패턴별 backward compatibility 조건과 실패 시 복구 경로를 설명할 수 있는가?

**Part B**

- log transport · rotation · retention을 서로 다른 문제로 구분해, 비교 수단별로 각각 어디서 어떻게 처리되는지 설명할 수 있는가?
- 수단별 disk growth · 재시작 · 전송 실패 · IAM · 설정 소유 위치의 차이를 설명할 수 있는가?

**공통**

- 대표 failure mode를 설명할 수 있는가?
- 대신고에서 spike · 실측으로 확인해야 할 조건을 구분했는가?
- 외부 조사만으로 결정할 수 없는 부분(내부 합의 · 실험 · External Input)을 식별했는가?
- 각 결과가 RD-12b~h · RD-13a · RD-11a 중 어디에 영향을 주는지 연결했는가?
- 핵심 주장에 출처가 붙어 있는가?
