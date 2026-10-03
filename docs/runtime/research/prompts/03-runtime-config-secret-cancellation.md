# Research Prompt 03 — Runtime Config / Secret / Cancellation

> **추적 정보** — 이 블록은 조사 대상이 아니다. 결과 문서에서 근거를 Decision ID에 연결하는 데만 쓴다. 아래 문서명은 조사자가 열람할 수 없고 열람할 필요도 없다.
>
> - Source: 대신고 `decision-classification.md` §6 External Research Queue
> - Part A · R1 · RD-07a — Docker Compose env 주입 semantics
> - Part A · R2 · RD-07c — SSM Parameter Store → EC2 → Compose container 전달 패턴
> - Part B · R1 · RD-19b · RD-19c — Python Worker · 외부 HTTP 호출 · ffmpeg subprocess 중단 semantics
>
> 사용법: 이 파일 전체를 새 웹 리서치 대화에 그대로 붙여 넣는다. Part A와 Part B는 서로 다른 기술 영역이다.

---

다음 기술 조사를 수행하세요. 이 조사는 서로 독립된 두 Part로 이루어집니다.

- **Part A** — Docker Compose와 AWS SSM Parameter Store를 쓸 때 config · secret이 container 안 Python process까지 어떻게 전달되고 어디에 노출되는가
- **Part B** — Python Worker가 실행 중인 작업을 사용자 요청으로 중단할 때, 진행 중인 외부 HTTP 호출과 ffmpeg subprocess를 기술적으로 어디까지 · 어떤 semantics로 멈출 수 있는가

이 조사는 결정을 내리는 작업이 아닙니다. 아래 Decision의 **선택지 · 제약 · failure mode · 검증 항목을 현실화하는 근거**를 모으는 작업입니다. 최종 선택은 별도 단계에서 팀이 합니다.

**우선순위:** R1(Q-A1 · Part B 전체)이 R2(Q-A2)보다 먼저입니다. 조사 분량이 부족하면 R1 질문의 깊이를 우선하고, Q-A2는 패턴 비교 수준으로 줄여도 됩니다.

## 1. 공통 프로젝트 맥락

**대신고**는 블랙박스 영상을 받아 교통법규 위반 신고 자료 준비를 보조하는 서비스입니다. 사용자가 영상을 올리면 서버가 비동기로 영상 변환(ffmpeg), 외부 AI API 호출을 통한 후보 구간 탐색, 번호판 판독 등을 실행합니다. 6명 팀의 10주 MVP입니다.

현재 Runtime baseline(이미 정해짐):

- AWS EC2 1대(t3.medium · Ubuntu 24.04)
- Docker Compose로 `api` · `worker` · `mysql` 세 service를 따로 띄운다. api와 worker는 같은 image 계열이고 command만 다르다. 같은 image를 환경 사이에 재사용하고 환경 차이는 runtime에 주입한다
- FastAPI API process 1 · Worker process 1 · Worker concurrency 초기값 1
- 작업 queue는 MySQL 8.4 테이블(DB Queue)이다
- Python 3.12
- 배포: GitHub Actions가 OIDC로 AWS deploy role을 assume하고, SSM Run Command로 EC2에 명령을 보낸다. 장기 AWS Access Key · SSH key 저장 · 22번 port 개방은 쓰지 않는다

---

# Part A — Runtime config / secret

## A1. Part A 맥락

**현재 config loader(사실):** repository의 config loader는 실행 시점 working directory의 `.env` 파일만 읽어 dict로 돌려준다. **process environment(`os.environ`)는 읽지 않고, 그렇게 하도록 명시돼 있다.** 이 규칙은 한 모듈 담당자의 로컬 평가 실행 맥락에서 정해졌고, 배포 환경 주입 경로는 그 결정이 다루지 않았다. 따라서 지금 상태로는 Compose `environment:` / `env_file:`로 주입한 값이 코드에 도달하지 않는다.

loader를 어떻게 바꿀지는 팀 내부 결정입니다. 이 조사는 **Compose 쪽에서 값이 실제로 어떻게 전달되는가**의 semantics를 확정하는 근거를 모읍니다.

**이미 정해져 있어 다시 열지 않는 것:**

- secret을 repository · image · log에 남기지 않는다. build-time 값과 runtime 값을 구분한다.
- 같은 image를 재사용하고 환경 차이는 runtime에 주입한다.
- GitHub Actions용 장기 AWS Access Key는 없다.

**AWS 쪽 사실:**

- EC2 instance role에는 SSM managed-instance 기능 권한이 있다.
- 같은 AWS 계정에서 Parameter Store가 이미 다른 용도(운영자의 key pair 보관)로 쓰이고 있다.
- secret 대상 예: 외부 AI API key, MySQL 접속 credential.

## A2. 이 Part가 근거를 제공할 Decision

| ID | 열린 질문 | 우선순위 |
| --- | --- | --- |
| RD-07a | config 출처와 우선순위 — `.env` 파일 · process environment · 기타 출처의 관계 | R1 |
| RD-07c | 배포 환경 secret source(EC2 host 파일 · SSM Parameter Store · 기타)와 container 전달 방식 | R2 |

## A3. 조사 질문

필요한 경우 인접 질문까지 확인하되, **위 Decision을 닫는 데 필요한 범위로 제한**하세요.

### Q-A1 (R1 · RD-07a) — Docker Compose의 env 전달 semantics

현재 Docker Compose(Compose Specification · Docker Compose v2) 공식 문서 기준으로 확인하세요.

1. **값의 출처별 역할** — 다음 각각이 무엇에 쓰이는가: service `environment:`, service `env_file:`, project directory의 `.env`(variable interpolation용), Compose를 실행한 shell environment, Dockerfile `ENV`, `docker compose run -e` 등 CLI override.
2. **precedence** — 같은 이름의 변수가 여러 곳에 있을 때 container 안 process가 최종적으로 보는 값의 우선순위.
3. **interpolation과 container env 전달의 차이** — project `.env`가 `${VAR}` 치환에만 쓰이는지, container environment로 자동 전달되는지. `env_file:`로 지정한 파일 안에서 interpolation이 일어나는지.
4. **host `.env` 파일이 container 안에 자동으로 생기는가** — Compose가 project `.env` 파일을 container filesystem에 mount · 복사하는지. container 안 working directory에 `.env` 파일이 있으려면 무엇이 필요한가(bind mount · image에 포함 등)와 각 방식의 노출 경로.
5. **secret 노출 경로** — environment로 전달된 값이 보일 수 있는 곳: `docker inspect`, `docker compose config` 출력, `/proc/<pid>/environ`, child process 상속, crash dump · error report, log. build argument가 image history에 남는지.
6. **Compose `secrets:` 요소** — Swarm이 아닌 단일 host Compose에서 file 기반 secret이 container 안에 어떻게 노출되는가(경로 · 권한 · 갱신 시 동작). environment 전달과의 노출 차이.

### Q-A2 (R2 · RD-07c) — SSM Parameter Store → EC2 → Compose container

**특정 패턴을 선택하지 마세요.** 대표 패턴의 semantics와 trade-off를 조사합니다.

조사할 패턴(예시이며 더 있으면 포함):

1. 배포 시 host에서 fetch → shell environment로 넘겨 Compose interpolation / `environment:`로 전달
2. 배포 시 host에서 fetch → env file 생성 → `env_file:`로 전달
3. 배포 시 host에서 fetch → secret 파일 생성 → file mount(또는 Compose `secrets:`)로 전달
4. container 안 application이 시작 시 · 실행 중 직접 fetch(runtime fetch)

각 패턴에 대해:

- **누가 fetch하는가와 IAM** — GitHub Actions의 OIDC role이 가져와 SSM Run Command parameter로 넘기는 경우와, EC2 instance role이 host에서 가져오는 경우의 권한 범위 차이. 필요한 IAM action(`ssm:GetParameter*` · SecureString 복호화에 필요한 KMS 권한)과 path 기반 권한 제한.
- **container에서 instance role 사용** — container 안 application이 runtime fetch할 때 EC2 instance metadata(IMDSv2)에 접근하는 조건(hop limit 등)과 그 보안 의미.
- **노출 위험** — SSM Run Command의 command 문서 · 실행 이력 · output(콘솔 · S3 · CloudWatch로 보낼 때), host shell history, process listing, 생성한 파일의 권한 · 잔존, GitHub Actions log masking 범위.
- **secret rotation** — Parameter Store 값을 바꿨을 때 각 패턴에서 반영되려면 무엇이 필요한가(container 재시작 · 재생성 · 재배포). Parameter Store 자체의 버전 · 이력 기능.
- **실패 시 동작** — fetch 실패 · 권한 부족 · parameter 없음일 때 배포 또는 process 시작이 어떻게 실패하는가.
- Parameter Store Standard / Advanced tier, SecureString과 KMS key 선택이 이 용도에 주는 제약(비용 수치는 「확인일 기준 공식 가격」으로만 적기).
- Secrets Manager는 baseline 후보가 아닙니다. Parameter Store와의 차이가 위 패턴 비교에 꼭 필요할 때만 짧게 언급하세요.

---

# Part B — Cancellation

## B1. Part B 맥락

**제품 정책은 이미 정해졌습니다. 다시 결정하지 않습니다.**

- 사용자는 분석을 **확인 대화 없이 즉시 중단**할 수 있다.
- 이미 보존된 결과는 버리지 않는다.
- 현재 범위에서 중단된 탐색은 부분 후보를 남기지 않는다.
- **timeout은 사용자 중단이 아니다.** timeout 때는 진행 중 작업을 강제로 취소하지 않고, 상위 orchestrator가 기다리는 것만 멈춘다.

**실행 기록 규칙(이미 정해짐):**

- 실행 1회분(JobExecution)의 status에 `CANCELLED`가 있고, `QUEUED → CANCELLED` · `RUNNING → CANCELLED` 전이가 허용된다.
- 외부 AI provider 호출 원장(UsageRecord): **실제로 시작된 provider 호출은 1건당 1 row 기록 대상**이다. 실행 시작 전(dispatch 전)에 취소되면 row가 없다.
- Worker는 실행 중 heartbeat/lease를 DB에 주기적으로 갱신한다(구조는 미정).

**Worker 실행 방식(사실):**

- Worker는 Python process 1개이고 한 번에 작업 1개를 실행한다.
- **외부 AI API 호출:** OpenAI Python SDK의 **동기(sync) client**로 OpenAI-compatible HTTP API를 호출한다. 영상은 request body 안에 base64 data URL로 inline 전송한다. SDK 자체 재시도는 끄고(`max_retries=0`), 호출하는 adapter가 자체 재시도 loop와 attempt별 timeout을 둔다. 호출 하나가 오래 걸릴 수 있다.
- **ffmpeg / ffprobe:** `subprocess.run(..., timeout=...)`으로 실행한다.
- **주의:** 외부 AI provider의 모델 · 전송 방식은 다른 모듈에서 재선정 중이라, 위 SDK · inline 전송 방식이 바뀔 수 있다. 따라서 Q-B2는 OpenAI Python SDK에만 한정하지 말고 **Python의 sync / async HTTP client 일반**(SDK가 내부에서 쓰는 HTTP client 포함)의 중단 semantics로 답하고, SDK 고유 동작은 따로 표시하세요.
- 중단 요청이 Worker에 어떤 경로로 도달하는지(DB flag · 별도 신호 등)는 아직 열려 있습니다. 이 조사는 **Worker가 중단 요청을 알게 된 뒤** 무엇을 멈출 수 있는지를 다룹니다.

조사 질문은 하나입니다.

> **이미 정해진 사용자 중단 동작을, 기술적으로 어떤 semantics로 구현할 수 있는가?**

## B2. 이 Part가 근거를 제공할 Decision

| ID | 열린 질문 | 우선순위 |
| --- | --- | --- |
| RD-19b | QUEUED · RUNNING execution의 중단 semantics — 실행 중인 handler를 실제로 멈추는지와 언제 `CANCELLED`로 기록하는지 | R1 |
| RD-19c | 이미 시작된 provider 호출의 처리와 그 UsageRecord 기록(「시작된 호출마다 row」 원칙과 중단 시점의 관계) | R1 |

중단 command 표면과 전달 port(RD-19a)는 Owner 합의 대상이라 이 조사 범위가 아닙니다.

## B3. 조사 질문

필요한 경우 인접 질문까지 확인하되, **위 Decision을 닫는 데 필요한 범위로 제한**하세요.

### Q-B1 — Python Worker 자체

1. **cooperative cancellation** — handler가 정해진 지점에서 취소 flag를 확인하는 방식(polling)의 일반 패턴과 한계: 확인 지점 사이의 긴 blocking 호출, 확인 주기와 반응 지연의 관계.
2. **thread 기반 중단의 한계** — Python에서 다른 thread를 강제로 멈출 수 없다는 제약, signal은 main thread에서만 처리된다는 제약 등 CPython 3.12 기준 사실.
3. **asyncio task cancellation** — `Task.cancel()` · `CancelledError` 전파 · `asyncio.timeout` · anyio cancel scope의 semantics. 동기 코드를 async로 감싸거나(`to_thread`) 그 반대일 때 cancellation이 실제로 어디까지 전달되는가.
4. **작업을 별도 process로 격리하는 패턴** — handler를 child process에서 실행하고 부모가 종료시키는 방식의 semantics와 비용(상태 전달 · DB connection · 메모리).
5. **graceful shutdown과의 구분** — `docker stop`(SIGTERM → grace period → SIGKILL), Compose `stop_grace_period`, PID 1로 실행되는 Python process의 signal 처리, `init: true`(tini 등)의 역할. 배포 · 재시작에 따른 종료와 사용자 중단이 같은 경로를 쓸 수 있는지 · 없는지의 기술적 차이.

### Q-B2 — 진행 중인 외부 HTTP API 호출

1. **동기 HTTP 요청의 중단 가능 범위** — OpenAI Python SDK(내부 HTTP client 포함)의 sync client에서, 다른 thread에서 client를 닫거나 요청을 끊는 것이 진행 중 요청을 실제로 중단시키는가. 공식 지원 방식이 있는가.
2. **async client의 경우** — async client 요청을 task cancellation으로 끊을 때의 동작.
3. **streaming response** — 응답을 stream으로 받는 경우 중간에 닫을 수 있는 범위.
4. **timeout과 cancellation의 차이** — connect · read · write · pool timeout의 의미, 전체 요청 timeout이 보장되는지. timeout은 「일정 시간 뒤 포기」이고 cancellation은 「외부 요청에 의해 즉시 포기」라는 차이가 구현에서 어떻게 드러나는가.
5. **connection close의 의미** — client가 connection을 닫았을 때 server(provider)가 그 요청 처리를 멈추는지는 일반적으로 보장되는가. HTTP/1.1 · HTTP/2에서 차이가 있는가.
6. **provider가 이미 요청을 받은 뒤** — request body 전송이 끝난 뒤 client가 끊으면 provider 측 처리 · 과금이 어떻게 되는지는 provider별로 다르다. 일반 원칙과, OpenAI 및 OpenAI-compatible API 문서가 이에 대해 무엇을 말하는지(말하지 않는지)를 구분해 정리하세요. 특정 provider의 실제 과금 정책은 이 조사로 확정하지 말고 「외부 확인 필요」로 남기세요.
7. **UsageRecord · billing 관점의 불확실성** — 중단 시점이 「요청 전송 전 / 전송 중 / 전송 완료 후 응답 대기 중 / 응답 수신 중」일 때 각각 「호출이 시작됐는가」 「사용량을 알 수 있는가」가 어떻게 달라지는가. 사용량을 알 수 없는 호출을 원장에 기록하는 일반 패턴(unknown · estimated 표시 등).
8. **idempotency** — 중단 후 같은 작업을 다시 실행할 때 provider 측 중복 처리를 막는 일반 수단(idempotency key 등)과, OpenAI-compatible API에서 그것이 보장되는지.

### Q-B3 — ffmpeg subprocess

1. **종료 신호별 동작** — ffmpeg에 SIGINT · SIGTERM · SIGKILL을 보내거나 stdin으로 `q`를 보낼 때의 동작 차이. 출력 파일이 정상적으로 닫히는지(container index · trailer 기록 여부), 손상된 partial file이 남는 조건.
2. **`subprocess.run(timeout=...)`의 실제 동작** — timeout 시 child에 어떤 신호를 보내는지, 대기 · 정리를 어떻게 하는지(Python 3.12 기준). ffmpeg가 또 다른 process를 만들 경우 그 손자 process는 어떻게 되는가.
3. **process group** — `start_new_session` · `process_group` 인자, `os.killpg`로 process tree 전체를 종료하는 패턴과 주의점.
4. **`subprocess.run` vs `Popen`** — 실행 중 외부 신호로 종료하려면 `Popen` 기반 관리가 필요한지, 그때 stdout/stderr pipe를 읽지 않으면 생기는 deadlock.
5. **zombie process** — container 안에서 zombie가 생기는 조건, PID 1 역할과 reaping, `init: true`의 효과.
6. **temp file · partial file cleanup** — Python `tempfile.TemporaryDirectory` 등의 정리가 정상 종료 · 예외 · SIGTERM · SIGKILL 각각에서 실행되는가. 비정상 종료 뒤 잔여 파일을 다음 시작 때 회수하는 일반 패턴.
7. **idempotency** — 중단된 변환을 다시 실행할 때 이전 partial output을 덮어쓰거나 무시하는 패턴(출력 경로 · 임시 이름 · rename).

### Q-B4 — 기존 job · workflow 시스템의 cancel semantics (참고 사례)

RD-19b의 「언제 `CANCELLED`로 기록하는가」에 근거를 주기 위한 질문입니다. **이 시스템들의 도입을 추천하지 마세요.** semantics만 비교합니다.

1. 대표 job queue · workflow 시스템(예: Celery · RQ · Temporal 등 — 예시이며 다른 시스템도 가능)이 실행 중 작업 cancel을 어떻게 정의하는가 — 「취소 요청됨」과 「실제로 멈춤」을 별도 상태로 구분하는지, 실행 중 작업에 취소를 어떤 경로(heartbeat 응답 · 신호 · flag)로 전달하는지, 작업이 협조하지 않을 때 무엇을 보장하는지.
2. 취소 요청과 작업 완료가 경합할 때(취소 요청 직후 작업이 성공으로 끝남) 최종 상태를 어떻게 정하는가.
3. 각 시스템이 문서에서 명시한 한계(강제 종료 시 정리 보장 없음 등).

---

# 공통 — 범위 · 방법 · 출력 (Part A · B 모두)

## 2. 범위 밖

다음은 조사하지 마세요.

- 사용자 중단을 허용할지 · 중단 시 무엇을 보여줄지 같은 제품 정책
- 중단 command 표면 · case → Runtime 전달 경로
- retry 횟수 · backoff · lease · heartbeat 주기 같은 값
- 공개 endpoint · TLS · scaling
- Kubernetes · ECS 등 새 topology, HashiCorp Vault 등 별도 secret 인프라 추천

## 3. 조사 방법

자료 우선순위:

1. 기술 자체의 최신 공식 문서 (Docker · Docker Compose · Python 3.12 문서 · ffmpeg 문서)
2. 공식 AWS 문서 (Systems Manager Parameter Store · Run Command · IAM · EC2 instance metadata) · OpenAI Python SDK 문서
3. 신뢰할 수 있는 engineering / architecture 자료
4. 해당 OSS의 공식 GitHub issue · discussion · source (OpenAI Python SDK · httpx · CPython · ffmpeg)
5. 커뮤니티 글은 보조 근거로만

- 현재 시점 기준 최신 정보를 확인하세요.
- **버전을 반드시 구분하세요.** Docker Compose v1(`docker-compose`)과 v2(`docker compose`)의 env 동작이 다르면 차이를 적고 대신고 기준은 **현재 Compose v2**입니다. Python은 **3.12** 기준입니다. OpenAI Python SDK · httpx는 확인한 버전을 적으세요. 구버전 동작을 현재 동작처럼 쓰지 마세요.
- 공식 문서가 명시하지 않은 동작은 「문서에 명시 없음」으로 표시하고, source로 확인했다면 그 위치를 적으세요.

## 4. 출력 원칙

**사실 · 해석 · 적용을 섞지 마세요.** 각 주장에 다음 중 하나를 표시하세요.

- **Verified fact** — 공식 문서 · source가 직접 말하는 사실. 출처 필수
- **Interpretation** — 여러 근거를 종합한 해석. 근거 목록 필수
- **Daesingo implication** — 위 대신고 구조에 적용했을 때의 의미

**최종 선택을 하지 마세요.** 「따라서 env_file을 써야 한다」 「따라서 runtime fetch가 최선이다」 「따라서 cancellation은 이 방식으로 확정한다」 같은 결론을 쓰지 않습니다. 선택지와 trade-off까지만 정리합니다.

**외부 숫자를 대신고 baseline으로 쓰지 마세요.** 다른 서비스가 「grace period N초」 「cancel polling 주기 N초」 「timeout N초」를 쓴다면, 그 숫자는 **그 환경의 숫자이며 대신고에 직접 적용할 수 없다**고 구분해서 적으세요. 도구의 기본값은 Verified fact로 적되 「기본값」임을 표시하세요.

**작성 언어와 기준일.** 결과는 한국어로 쓰고, 기술 용어 · 설정 이름 · 원문 인용은 영어 그대로 둡니다. 결과 맨 위에 조사 기준일을 적으세요.

**제출 전 자기 점검.** 결과를 내기 전에 「~해야 한다」 「~가 최선이다」 「권장한다」처럼 선택을 확정하는 문장이 남아 있는지 확인하고, 있으면 조건과 trade-off를 설명하는 문장으로 바꾸세요. 출처가 없는 Verified fact가 있으면 Interpretation으로 내리거나 9절(Unresolved)로 옮기세요.

## 5. 결과 형식

다음 구조로 작성하세요. 3 · 4 · 5 · 6절 안에서는 **Part A와 Part B를 소제목으로 나눠** 적으세요.

```markdown
# Research Result — Runtime Config / Secret / Cancellation

## 1. Executive Summary
- 조사 결과의 핵심 사실만 (Part A · Part B 각각)
- 최종 Decision 추천은 하지 않음

## 2. Questions Investigated
- Q-A1 · Q-A2 · Q-B1 ~ Q-B4 질문별 실제 조사 범위

## 3. Verified Technical Facts
### Part A
| Fact | Version / Condition | Evidence |
### Part B
| Fact | Version / Condition | Evidence |

## 4. Options / Patterns
### Part A — config 출처 · secret 전달 패턴
### Part B — 중단 대상별 구현 패턴
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
- 어떤 RD / sub-decision(RD-07a · 07c · 19b · 19c)에 영향을 주는지

## 7. What External Research Cannot Decide
- 대신고 내부 합의가 필요한 것
- 실험이 필요한 것
- External Input이 필요한 것 (예: 특정 provider의 중단 · 과금 정책)

## 8. Suggested Pre-implementation Checks
- 필요 시 작은 spike / integration test (예: Compose 주입 값이 container 안 process에 도달하는지, ffmpeg 중단 후 잔여 process · 파일 확인)
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

## 6. Research Completion Criteria

이 조사는 다음에 답할 수 있을 때 완료입니다.

**Part A**

- Compose의 `environment` · `env_file` · project `.env` · shell environment · Dockerfile `ENV` · CLI override의 역할과 precedence를 현재 공식 문서 기준으로 설명할 수 있는가?
- interpolation과 container environment 전달의 차이, host `.env`가 container 안에 자동으로 생기는지를 설명할 수 있는가?
- secret이 노출될 수 있는 경로(`docker inspect` · `docker compose config` · `/proc` · log · image history 등)를 패턴별로 구분할 수 있는가?
- SSM Parameter Store 값을 container에 전달하는 대표 패턴별 IAM · 노출 · rotation · 실패 동작 trade-off를 설명할 수 있는가?

**Part B**

- Python Worker · 동기 HTTP 호출 · ffmpeg subprocess 각각을 「즉시 멈출 수 있는 것 / 협조적으로만 멈출 수 있는 것 / 멈출 수 없는 것」으로 구분할 수 있는가?
- timeout과 cancellation, connection close와 provider 측 처리 중단의 차이를 설명할 수 있는가?
- 중단 시점별로 provider 호출의 「시작 여부」와 「사용량 확인 가능 여부」가 어떻게 달라지는지 설명할 수 있는가?
- partial file · temp file · zombie process · child process의 대표 failure mode와 정리 패턴을 설명할 수 있는가?
- 「취소 요청됨」과 「실제로 멈춤」을 구분하는 기존 시스템의 semantics와, 취소 · 완료 경합 처리 방식을 비교할 수 있는가?

**공통**

- 대신고에서 spike로 확인해야 할 조건을 구분했는가?
- 외부 조사만으로 결정할 수 없는 부분(내부 합의 · 실험 · External Input)을 식별했는가?
- 각 결과가 RD-07a · RD-07c · RD-19b · RD-19c 중 어디에 영향을 주는지 연결했는가?
- 핵심 주장에 출처가 붙어 있는가?
