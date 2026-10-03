# Research Result — Runtime Config / Secret / Cancellation

**Status:** Evidence — 외부 기술 조사 결과 · **보조 검토 완료 2026-10-03 · Owner 확인 전** — 정정 사항은 [Review notes](#review-notes-2026-10-03)가 본문보다 우선\
**Owner:** common/runtime — 김준영\
**Workflow step:** [`runtime-ops-workflow.md`](../runtime-ops-workflow.md) §4 Decision-driven 외부 기술 조사\
**Prompt:** [`prompts/03-runtime-config-secret-cancellation.md`](./prompts/03-runtime-config-secret-cancellation.md)\
**Decisions:** [RD-07](../open-decision-register.md#rd-07--runtime-configuration--secret-주입) (07a · 07c) · [RD-19](../open-decision-register.md#rd-19--사용자-중단cancellation-전달-경로와-실행-중단-semantics) (19b · 19c)\
**조사 기준일:** 2026-10-03

> 이 문서는 Decision 근거이며 결정이 아니다. 내용은 Owner 검토를 거쳐 Spec · Contract · ADR로 옮겨질 때만 효력이 있다. 외부 자료의 숫자는 대신고 baseline이 아니다.

## Review notes (2026-10-03)

> 이 절이 본문보다 우선한다. 본문은 조사 원문 그대로 두었다. 검토는 Claude Code 보조 검토이며 Owner 최종 확인 전이다. **★** = 검토 뒤 원문(공식 문서 · repo)을 다시 열어 재확인한 항목, 표시 없음 = 검토 단계에서 인용 출처와 대조한 항목.

**판정:** Part A(RD-07a · 07c)는 경미한 보완 후, Part B(RD-19b · 19c)는 아래 High 2건을 반영한 뒤 Decision 근거로 쓸 수 있다. 출처 대조 약 40건 — 부분 일치 4 · 인용 출처에 없음 1 · **반대 1**(SDK 최신 버전, 영향 적음), 나머지 일치. Temporal 인용 URL은 실재하고 인용 문구도 원문과 같다. 최종 선택 문장 · 외부 숫자의 baseline화는 없다.

### 정정 · 보완

| Sev | 본문 위치 | 정정 | 근거 |
| --- | --- | --- | --- |
| High | §4 Part B 「UsageRecord 시점」 | 「호출 row를 먼저 만들고 outcome을 **갱신**」하는 일반 원장 패턴은 **UsageRecord row 자체에는 적용할 수 없다** — row는 append-only다(§8-1). UsageRecord 밖의 별도 in-flight 추적 구조라면 RD-01e · 01f에서 열려 있는 선택지다. 사용량 미확정은 `token_usage=null`(§8-3)로 일부 표현할 수 있다 ★ | [`contract-usage-record.md`](../../architecture/contracts/contract-usage-record.md) §8-1 · §8-3 |
| High | §1 · §3 · §9 Part B SDK / transport 전제 | 본문은 openai v3.x + HTTPX2를 전제로 쓰고 HTTPX 0.28은 비교 근거로만 둔다. **대신고 현재 pin은 openai 2.54.0 + httpx 0.28.1**이다(`pyproject.toml`의 `eval-gemini` extra는 `openai>=1.40,<3.0`). 중단 semantics는 HTTPX 0.28 쪽이 적용 대상이고, §8 spike도 이 pin 기준으로 한다. 덧붙여 「최신 release v3.20.0」은 틀렸다 — 3.24.0(2026-10-02)까지 나와 있다 ★ | `uv.lock` · PyPI openai |
| Med | §6 RD-19b `CANCELLED` 「의미」 후보 | `CANCELLED`의 의미는 Contract §6에서 닫혔다: 「사용자가 진행 중인 분석을 중단해 **종료됨**」, status는 닫힌 enum 6값이다(Already fixed). 열린 것은 의미가 아니라 **기록 시점**이다. 「요청 수락」을 표시하려면 status 밖의 별도 표식이 필요하다는 제약으로 읽는다 ★ | [`contract-job-execution.md`](../../architecture/contracts/contract-job-execution.md) §6 |
| Med | §1 · §6 「timeout과 cancellation」 | repo 사실: 두 timeout은 이미 다른 층이다. 제품 timeout은 case가 Job을 기다리는 시간(`timeout-fallback.md`)이고, ffmpeg/ffprobe의 `subprocess.run(timeout=…)`은 recording 내부 안전 한도로 `TEMPORARY_FAILURE`로 변환된다. 「분리될 필요가 있다」는 지시형이 아니라 이 사실로 읽는다 | [`timeout-fallback.md`](../../modules/case/decisions/timeout-fallback.md) · `recording/materialization.py` · `frames.py` · `probe.py` |
| Med | Part A 노출 경로(Q-A1.5 · Q-A2) | 누락: **child process env 상속** — 현재 `subprocess.run`은 `env=`를 넘기지 않으므로 secret을 process env로 주입하면 ffmpeg까지 API key를 물려받는다. crash dump · error report, host shell history, process listing(argv)도 빠졌다. IMDS hop limit을 2로 열면 그 host의 어느 container든 instance role 자격 증명을 얻을 수 있다는 의미도 implication으로 추가한다 | `recording/materialization.py` |
| Med | §6 RQ 사례 | RQ는 「요청 / 실제 정지」를 분리하는 사례가 아니다. 상태(queued / running)별로 기능이 나뉘고, `send_stop_job_command`는 실행 중 job을 **즉시** 멈추며 결과는 `stopped`(FailedJobRegistry)다 → Q-B1.4(process 격리)의 근거로 읽는다 | [RQ jobs](https://python-rq.org/docs/jobs/) · [RQ workers](https://python-rq.org/docs/workers/) |
| Med | §1 「cooperative cancellation은 checkpoint 사이에서만 반응」 | 출처 없는 Verified fact → Interpretation | — |
| Med | §9-8 SIGTERM cleanup · Q-B1.5 PID 1 | 미결로 남겼으나 공식 문서로 닫힌다 → 아래 「보완 확인」 | — |
| Med | Q-B4.2 취소 · 완료 경합 | 다루지 않았다 → 아래 「보완 확인」 | — |
| Low | 여러 곳 | Compose `secrets` file source의 `uid`/`gid`/`mode`는 「제약」이 아니라 원문대로 **silently ignored**(host 파일 권한을 따름) · ffmpeg stdin `q`는 현재 코드가 `-nostdin` + `stdin=DEVNULL`이라 막힌 경로 · ffmpeg는 signal 3회 초과 시 hard exit, signal 종료 시 exit 255, SIGQUIT · SIGXCPU도 같은 handler · OpenAI client는 `_idempotency_header=None`이라 idempotency header를 보내지 않음 · 「protocol 수준 보장 없음」은 Interpretation · 취소 요청이 「DB flag」로 온다는 전제는 RD-19a 범위라 경로를 특정하지 않고 읽음 · AnyIO 기본 `abandon_on_cancel=False`면 thread가 끝날 때까지 돌아오지 않음 · GitHub `add-mask` 「출력 전에 등록」은 인용 페이지에 없음 · §10 출처 누락(compose config, Parameter Store advanced tier, Run Command CloudWatch output) | 각 공식 문서 · source |

### 보완 확인 (검토 단계 추가)

- **PID 1과 SIGTERM (Q-B1.5 · §9-8)** ★
  - Verified fact — PID namespace의 init(PID 1)에는 **handler를 설치한 signal만** 전달된다. ancestor namespace에서 보낸 SIGKILL · SIGSTOP만 예외로 강제 전달된다. ([pid_namespaces(7)](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html))
  - Verified fact — Python이 시작 시 설치하는 handler는 SIGPIPE(무시)와 SIGINT(→ `KeyboardInterrupt`)뿐이다. handler는 main thread에서만 실행되고 설정할 수 있다. ([signal (3.12)](https://docs.python.org/3.12/library/signal.html))
  - Interpretation — Python이 container의 PID 1이고 SIGTERM handler가 없으면 `docker stop`의 SIGTERM은 전달되지 않고 grace period 뒤 SIGKILL로 끝난다. `init: true` 등으로 init이 PID 1이면 Python은 SIGTERM의 OS 기본 동작(종료)을 받는다. **어느 쪽이든 handler가 없으면 `finally` · `TemporaryDirectory` 정리는 실행되지 않는다.**
- **취소 · 완료 경합 (Q-B4.2)** ★
  - Verified fact — Celery: revoke를 받으면 아직 시작하지 않은 task는 건너뛰지만, 실행 중 task는 `terminate` 없이는 멈추지 않는다. 그런데 result backend는 **즉시 `REVOKED`로 갱신**된다 → 기록 상태와 실제 실행이 어긋날 수 있는, 「요청 시점 기록」 사례다. ([Celery workers guide](https://docs.celeryq.dev/en/stable/userguide/workers.html))
  - Verified fact — Temporal: Activity는 heartbeat를 해야 취소를 받는다. ([Activity execution](https://docs.temporal.io/activity-execution))
  - 두 문서 모두 **취소 요청 뒤 성공으로 끝난 경우의 최종 상태를 명시하지 않는다.** → 경합 시 우선순위는 외부 사례로 정할 수 없고 RD-19b 내부 합의 대상이다.

### Decision 입력으로 옮길 때

- §7 RD-19c 「retry attempt마다 row인가, logical call마다 row인가」는 먼저 UsageRecord Contract §8-14(「실제 capability/provider invocation이 시작된 호출에만 row」)와 대조한다 — 이미 좁혀져 있을 수 있다.
- §8 Part A 2번(loader 도달 확인)에는 선택지 하나가 더 있다: `common/env.py`의 `load_env_file(path)`는 경로를 받으므로, `/run/secrets` 아래 KEY=VALUE 파일은 현재 loader로도 읽을 수 있다(선택이 아니라 사실).

---

> 이 문서는 RD-07a · RD-07c · RD-19b · RD-19c의 선택지를 현실화하기 위한 외부 기술 조사 결과이다.\
> 최종 config source, secret 전달 경로, cancellation 구현 방식은 선택하지 않는다.

---

## 1. Executive Summary

### Part A — Runtime config / secret

- **Verified fact — Compose의 interpolation과 container environment 주입은 서로 다른 단계다.** Project `.env`, `--env-file`, Compose 실행 shell은 우선 Compose YAML의 `${VAR}`를 해석하는 source다. 반면 container process environment는 service `environment:`, service `env_file:`, CLI `docker compose run -e`, image `ENV` 등에 의해 만들어진다. Project `.env` 값이 그 자체로 container environment에 자동 복사되는 것은 아니다.
- **Verified fact — service `env_file:`은 파일 자체를 mount하는 기능이 아니다.** 해당 파일의 key/value를 container environment로 전달한다. `environment:`가 같은 이름을 갖고 있으면 `env_file:`보다 우선한다. 일반 `env_file`의 unquoted/double-quoted value에는 Compose interpolation이 적용되며, Compose 2.30+의 `format: raw`는 이 해석을 끌 수 있다.
- **Interpretation — 따라서 현재 대신고 loader가 cwd의 `.env` 파일만 읽고 `os.environ`을 보지 않는다면**, Compose `environment:`/`env_file:`에 값을 주입하는 것만으로는 현재 loader가 그 값을 소비하지 않는다. 별도로 container filesystem에 `.env`가 존재하거나 loader source 규칙이 바뀌어야 한다.
- **Verified fact — environment secret은 container configuration/process environment의 일부가 된다.** Linux에서는 `/proc/<pid>/environ`을 적절한 권한이 있는 주체가 읽을 수 있고, Docker는 container의 상세 configuration을 `docker inspect`로 노출한다. Docker도 secret 값에는 environment보다 Compose `secrets` 사용을 별도 기능으로 제공하고 있다.
- **Verified fact — Compose `secrets`는 standalone Linux Compose에서도 `/run/secrets/<name>` 파일로 bind-mount된다.** service별 명시적 grant가 필요하다. long syntax 기본 mode는 `0444`이며 file source의 `uid`/`gid`/`mode` remap에는 Compose 구현상 제약이 있다.
- **Verified fact — SSM Parameter Store의 `SecureString` 복호화에는 Parameter Store read 권한과 KMS 권한을 별도로 고려해야 한다.** decrypted `SecureString`을 읽는 principal은 `kms:Decrypt`가 필요하다. `GetParametersByPath`는 상위 path 접근으로 하위 값을 가져올 수 있으므로 path 정책도 함께 검토 대상이다.
- **Verified fact — Run Command command input에 plaintext secret을 넣는 것은 별도 노출면을 만든다.** AWS는 plaintext password/config/secret을 Run Command command에 넣지 말라고 명시하며 Systems Manager API activity와 command history의 audit 경로를 설명한다. SSM Document의 일반 parameter reference는 `SecureString`을 직접 지원하지 않아, AWS 공식 예제도 managed node에서 `aws ssm get-parameters --with-decryption`을 실행하는 패턴을 별도로 보여준다.
- **Verified fact — 이미 실행 중인 container의 environment는 Parameter Store 값이 바뀌었다고 자동 갱신되지 않는다.** `docker compose restart`는 Compose environment 변경을 반영하지 않는다. 새로운 값을 environment로 전달하는 패턴에서는 새 값을 다시 fetch한 뒤 container가 새 configuration으로 생성/re-created되는 단계가 별도로 존재한다.

### Part B — Cancellation

- **Verified fact — Python thread에는 일반적인 강제 중단 API가 없다.** CPython 3.12 `threading.Thread`는 running thread를 destroy/stop/suspend/interrupt할 수 없다. Python signal handler는 main interpreter의 main thread에서 실행되며 inter-thread cancellation mechanism으로 사용할 수 없다.
- **Verified fact — cooperative cancellation은 cancellation checkpoint 사이에서만 반응한다.** handler가 flag를 polling하는 구조라면 긴 sync HTTP call이나 blocking subprocess wait 동안에는 flag를 다시 읽지 못한다.
- **Verified fact — `asyncio.Task.cancel()`도 “즉시 강제 종료”가 아니다.** 다음 cancellation opportunity에서 `CancelledError`를 주입하며 coroutine이 이를 정리하거나 심지어 suppress할 수도 있다. `asyncio.timeout()`은 내부적으로 현재 task를 cancel하므로, “상위 대기만 끝내고 실제 작업은 계속한다”는 timeout semantics와는 다른 동작이다.
- **Verified fact — thread로 넘긴 sync code는 async wrapper가 취소되어도 자동으로 죽지 않는다.** AnyIO는 이를 명시적으로 문서화하여 `abandon_on_cancel=True`일 경우 기다리는 task만 빠져나가고 worker thread는 계속 실행한다고 설명한다.
- **Interpretation — 현재 sync HTTP 호출을 같은 Worker thread 안에서 직접 수행하는 구조에서는**, cancellation flag를 Worker가 이미 알아도 HTTP client가 반환하기 전에는 Python handler가 다음 cancellation checkpoint에 도달하지 못할 수 있다.
- **Verified fact — current OpenAI Python SDK v3.20.0은 HTTPX2 기반이다.** HTTPX2 migration 자체는 v3.0.0에서 이루어졌다. 현재 source에는 sync client 전체를 `close()`하는 API와 response stream의 `close()`/`aclose()`가 있지만, “다른 thread가 특정 진행 중 sync request 하나를 안전하게 cancel한다”는 public contract는 확인되지 않았다.
- **Interpretation — 따라서 sync client의 `close()`를 cross-thread request cancellation primitive로 간주할 근거는 부족하다.** 실제 socket interruption 여부는 SDK/transport version을 고정한 spike 대상이다.
- **Verified fact — HTTP connection을 client가 끊는 것과 provider가 계산을 중단하는 것은 동일한 보장이 아니다.** HTTP/1.1에서는 incomplete request가 될 수 있으나 server는 이미 완성된 request를 처리하고 있을 수 있다. HTTP/2 `CANCEL`은 stream이 더 필요 없음을 뜻하지만, application processing이 전혀 시작되지 않았음을 명시적으로 보장하는 것은 `REFUSED_STREAM`이다.
- **Verified fact — ffmpeg의 current source는 `SIGINT`와 `SIGTERM`을 graceful termination path에 넣고 있으며 `q`도 main transcode loop를 빠져나가게 한다.** 이후 output마다 trailer를 쓰는 code path가 실행된다. 이것은 정상적인 trailer 작성 “시도”이며 모든 format의 partial output 유효성을 보장한다는 뜻은 아니다.
- **Verified fact — Python 3.12의 `subprocess.run(..., timeout=...)`은 timeout이 나면 child를 kill하고 wait한다.** POSIX에서 `Popen.kill()`은 `SIGKILL`이다. 따라서 이 timeout path는 ffmpeg의 SIGTERM/SIGINT graceful path와 다르다.
- **Daesingo implication — 현재 “timeout은 실행 중 작업을 취소하지 않고 상위 orchestrator가 기다리는 것만 멈춘다”는 제품 semantics와 `subprocess.run(timeout=...)`의 강제 child kill semantics는 동일하지 않다.** 현재 코드의 timeout이 어느 종류를 의미하는지 RD-19b에서 분리될 필요가 있다.
- **Verified fact — 기존 job 시스템도 cancel request와 actual stop을 분리한다.** Temporal Activity는 cancellation을 다음 heartbeat에서 알며 heartbeat가 없으면 completion/timeout까지 실행될 수 있다. RQ는 queued job `cancel()`과 running job `stop`을 별도 operation으로 둔다. Celery의 revoke도 기본적으로 이미 실행 중인 task를 종료하지 않고, `terminate=True`는 worker child process를 죽이는 별도·위험한 수단으로 문서화한다.

---

## 2. Questions Investigated

| Question | 실제 조사 범위 |
|---|---|
| **Q-A1 · R1** | Compose v2의 interpolation source, container env precedence, `environment`, `env_file`, project `.env`, shell, CLI override, image `ENV`; `.env` filesystem 존재 여부; env/file secret 노출면; Compose `secrets` |
| **Q-A2 · R2** | Parameter Store를 GitHub runner/EC2 host/container가 fetch하는 차이; SSM/KMS IAM; Run Command 노출; IMDSv2 container access; rotation·failure semantics; Standard/Advanced tier |
| **Q-B1 · R1** | Python 3.12 cooperative polling, thread, signal, asyncio/AnyIO, process isolation, Docker shutdown |
| **Q-B2 · R1** | generic sync/async HTTP cancellation, OpenAI Python SDK current behavior, streaming close, timeout vs cancellation, HTTP/1.1·HTTP/2 disconnect semantics, usage uncertainty, idempotency |
| **Q-B3 · R1** | ffmpeg `q`/SIGINT/SIGTERM/SIGKILL, `run`/`Popen`, process group, pipe deadlock, zombies, temp/partial files |
| **Q-B4 · R1** | Temporal · RQ · Celery에서 cancel requested와 actual termination을 분리하는 방식 및 한계 |

---

## 3. Verified Technical Facts

### Part A

| Fact | Version / Condition | Evidence |
|---|---|---|
| **Verified fact.** Compose interpolation source precedence는 shell → `--env-file` → default project `.env` 순이다. | Current Docker Compose v2 docs | Docker Docs — Variable interpolation |
| **Verified fact.** Container environment precedence의 최상위에는 `docker compose run -e`가 있고, 그 아래 Compose `environment`/`env_file`, 마지막 fallback에 image `ENV`가 있다. | Current Compose docs | Docker Docs — Environment variables precedence |
| **Verified fact.** Shell variable이나 project `.env`는 interpolation source이며, container environment로 들어가려면 Compose model이 그 값을 `environment` 등의 container setting에 연결해야 한다. | Compose v2 | Docker Docs — Variable interpolation |
| **Verified fact.** service `environment:`는 container environment를 설정하고 같은 variable의 `env_file:` 값을 override한다. | Compose v2 | Docker Compose file reference |
| **Verified fact.** service `env_file:`은 key/value를 container에 전달한다. 여러 파일이면 뒤 파일 값이 우선한다. | Compose v2 | Docker Compose file reference |
| **Verified fact.** 일반 `env_file`의 unquoted/double-quoted 값에는 interpolation이 적용된다. `format: raw`는 Compose 2.30+ 기능이다. | Compose ≥2.30 for `raw` | Docker Compose file reference |
| **Interpretation.** Project `.env`가 container filesystem으로 자동 mount/copy된다는 Compose semantics는 없다. `.env`를 cwd에서 `open()`하려면 image에 존재하거나, volume/bind mount 등 별도 filesystem 전달이 있어야 한다. | Compose model과 mount/env semantics의 결합 해석 | Docker Compose docs |
| **Verified fact.** `docker compose config`는 interpolation이 끝난 resolved Compose model을 출력하며 `config --environment`로 interpolation environment도 볼 수 있다. | Compose v2 | Docker Docs |
| **Verified fact.** Docker `ARG`와 Dockerfile `ENV`는 build secret 전달 수단으로 적합하지 않다고 Docker가 명시한다. `ARG`는 image history/provenance에 남을 수 있고 `ENV`는 생성된 container에 지속된다. | Current BuildKit/Docker docs | Docker Docs — Build variables |
| **Verified fact.** Linux `/proc/<pid>/environ`은 process의 initial environment를 제공하며 접근은 ptrace permission check의 영향을 받는다. | Linux man-pages 6.19 | `proc_pid_environ(5)` |
| **Verified fact.** Compose `secrets`는 Linux container에서 `/run/secrets/<secret_name>`의 file bind mount로 전달된다. | Current Compose | Docker Docs — Secrets in Compose |
| **Verified fact.** Compose secret long syntax 기본 mode는 `0444`; file-backed source는 bind mount 구현 때문에 `uid`/`gid`/`mode` remap에 제한이 있다. | Current Compose spec | Docker Compose file reference |
| **Verified fact.** `docker compose restart`는 변경된 environment를 container에 반영하지 않는다. | Current Compose CLI | Docker Docs — compose restart |
| **Verified fact.** Parameter Store `SecureString` decrypted value를 가져오는 principal에는 해당 KMS key에 대한 `kms:Decrypt`가 필요하다. | Current AWS docs | AWS Systems Manager Docs |
| **Verified fact.** `GetParametersByPath` 권한은 ancestor path를 통해 descendant를 읽을 수 있는 정책 함정이 있다. | Current AWS docs | AWS Systems Manager Docs |
| **Verified fact.** SSM Document의 일반 Parameter Store reference에서는 `SecureString`을 직접 reference할 수 없다. AWS는 Run Command script 안에서 AWS CLI로 `SecureString`을 fetch/decrypt하는 예를 별도로 제공한다. | Current SSM docs | AWS Systems Manager Docs |
| **Verified fact.** Run Command input에 plaintext secret을 넣으면 Systems Manager API audit/history 경로가 노출면이 된다. Command history는 최대 30일 제공된다. | Current AWS SSM | AWS Systems Manager Docs |
| **Verified fact.** Run Command stdout/stderr를 CloudWatch Logs로 보내도록 설정하면 execution output이 CloudWatch에 전송된다. | Current AWS SSM | AWS Systems Manager Docs |
| **Verified fact.** Container가 EC2 IMDSv2에 접근할 때 추가 network hop 때문에 hop limit `1`이 문제를 일으킬 수 있다. Metadata hop limit 범위는 1–64이다. | EC2/IMDSv2 | AWS EC2 Docs |
| **Verified fact.** Parameter Store는 value update마다 새 version을 만들고 최대 100 versions를 유지한다. | Current Parameter Store | AWS Systems Manager Docs |
| **Verified fact.** Standard/Advanced는 각각 10,000/100,000 parameters per account-region, 최대 value 4 KB/8 KB이고 Advanced에 parameter policy/cross-account 기능이 추가된다. | Current AWS docs | AWS Systems Manager Docs |
| **Verified fact.** 2026-10-03 공식 가격 페이지 기준 Standard storage는 추가 요금 없음, Advanced는 월 parameter당 USD 0.05이며 시간 단위 prorate; Advanced API interaction은 10,000건당 USD 0.05이다. Standard의 기본 throughput API는 추가 요금이 없고 higher throughput은 별도 과금된다. | **가격 확인일 2026-10-03** | AWS Systems Manager Pricing |
| **Verified fact.** GitHub Actions masking은 완전한 유출 방지 보장이 아니다. 변환/encoding된 value는 별도로 mask하지 않으면 자동 redaction이 실패할 수 있다. `add-mask`는 값이 출력되기 전에 등록되어야 한다. | Current GitHub Actions | GitHub Actions Docs |

### Part B

| Fact | Version / Condition | Evidence |
|---|---|---|
| **Verified fact.** Python thread는 외부에서 destroy/stop/suspend/resume/interrupt할 수 없다. | CPython 3.12.15 | Python 3.12 `threading` docs |
| **Verified fact.** Python signal handler는 main interpreter의 main thread에서 실행되며 main thread만 새로운 Python signal handler를 설정할 수 있다. | Python 3.12 | Python 3.12 `signal` docs |
| **Verified fact.** `Task.cancel()`은 다음 opportunity에 `CancelledError`를 throw하도록 요청하며 실제 cancellation을 절대적으로 보장하지 않는다. | asyncio 3.12 | Python 3.12 `asyncio` docs |
| **Verified fact.** `asyncio.timeout()`은 현재 task를 cancel한 뒤 `CancelledError`를 `TimeoutError`로 변환한다. | asyncio 3.12 | Python 3.12 `asyncio` docs |
| **Verified fact.** `asyncio.wait(..., timeout=...)`은 timeout 때 pending task 자체를 cancel하지 않는다. | asyncio 3.12 | Python 3.12 `asyncio` docs |
| **Verified fact.** AnyIO `CancelScope.cancel()`은 scope를 cancel 상태로 만들지만 `to_thread.run_sync()`의 thread는 host task cancellation과 별개로 계속 실행될 수 있다. | AnyIO 4.15.1 | AnyIO docs |
| **Verified fact.** `multiprocessing.Process.terminate()`은 POSIX에서 SIGTERM이며 `finally`/exit handler 실행을 보장하지 않는다. Descendant는 함께 종료되지 않는다. | Python 3.12 | Python 3.12 `multiprocessing` docs |
| **Verified fact.** 강제 process termination 중 pipe/queue가 손상되거나 lock/semaphore를 잡고 있으면 다른 process가 deadlock될 수 있다. | Python 3.12 | Python 3.12 `multiprocessing` docs |
| **Verified fact.** Docker/Compose stop은 기본적으로 SIGTERM 후 grace period를 거쳐 SIGKILL로 escalate한다. Compose의 documented default grace period는 10초다. 이는 도구 기본값이지 대신고 baseline 값이 아니다. | Current Compose | Docker Compose docs |
| **Verified fact.** `init: true`는 container 안에 init process를 두어 signal forwarding 및 child reaping 역할을 한다. | Current Compose | Docker Compose docs |
| **Verified fact.** OpenAI Python SDK의 2026-10-03 최신 release는 v3.20.0이며 default sync/async HTTP layer는 HTTPX2이다. Migration은 v3.0.0에서 이루어졌다. | openai-python v3.x | OpenAI Python release/source |
| **Verified fact.** Current OpenAI sync client `close()`는 underlying HTTP client를 닫는다. Current streaming abstraction도 response `close()`/`aclose()`를 노출하고 미완주 stream을 정리한다. | Current SDK source | `openai-python` source |
| **Interpretation.** Current public SDK 문서/source에서 진행 중인 **특정 sync request를 다른 thread가 cancel하는 공식 request-level primitive**는 확인되지 않았다. Client-wide `close()`의 concurrent abort 동작을 request cancellation contract로 간주할 근거도 확인되지 않았다. | OpenAI SDK current source/API 조사 | `openai-python` source |
| **Verified fact.** HTTPX 0.28 계열 documentation의 timeout은 connect/read/write/pool로 구분되며 read/write는 chunk 단위 inactivity 개념이다. 이는 generic HTTPX 참고 사실이며 현재 OpenAI SDK의 HTTPX2 구현 자체를 증명하는 근거는 아니다. | HTTPX stable reference | HTTPX Docs |
| **Verified fact.** Current OpenAI SDK는 timeout과 granular timeout configuration을 문서화한다. | openai-python v3.x | OpenAI Python docs/source |
| **Verified fact.** HTTP/1.1에서 request body가 다 도착하기 전에 connection이 끊기면 server는 incomplete request로 취급한다. 그러나 이미 완성된 request가 application processing에 전달된 뒤 client disconnect가 그 처리를 취소한다는 protocol-level 보장은 없다. | RFC 9112 | RFC 9112 |
| **Verified fact.** HTTP/2 `CANCEL`은 stream이 더 이상 필요 없다는 의미다. `REFUSED_STREAM`만 “application processing 전 거부”를 명시적으로 뜻한다. | RFC 9113 | RFC 9113 |
| **Verified fact.** OpenAI Chat Completions streaming의 `include_usage`는 마지막 추가 chunk에 total usage를 보내며 stream이 끊기면 이 final usage chunk를 못 받을 수 있다. | OpenAI API | OpenAI API reference |
| **Verified fact.** OpenAI API는 `X-Client-Request-Id`를 제공하면 timeout/network failure 이후 support가 “request를 받았는지/언제 받았는지” 조사할 수 있다고 문서화한다. 이것은 idempotency guarantee가 아니다. | OpenAI API | OpenAI API reference |
| **Verified fact.** Python 3.12 `subprocess.run(timeout=...)`은 timeout 발생 시 child를 kill하고 wait한 뒤 `TimeoutExpired`를 다시 발생시킨다. | Python 3.12 | Python 3.12 `subprocess` docs |
| **Verified fact.** 반대로 `Popen.communicate(timeout=...)` 자체는 timeout 시 child를 kill하지 않는다. Caller가 kill/cleanup을 수행하는 예제가 공식 문서에 있다. | Python 3.12 | Python 3.12 `subprocess` docs |
| **Verified fact.** `stdout=PIPE`/`stderr=PIPE`를 두고 적절히 drain하지 않으면 child가 pipe buffer에서 block하여 deadlock할 수 있다. | Python 3.12 | Python 3.12 `subprocess` docs |
| **Verified fact.** `start_new_session=True`는 POSIX child에서 `setsid()`를 수행하고 `process_group`은 `setpgid()`를 사용한다. `os.killpg()`는 process group 전체에 signal을 보낸다. | Python 3.12 | Python 3.12 `subprocess`/`os` docs |
| **Verified fact.** Current ffmpeg source는 SIGINT/SIGTERM을 same termination handler로 처리하고 transcode loop를 빠져나온 뒤 output trailer를 쓰는 path를 가진다. `q` 입력 역시 같은 loop에서 exit 조건으로 사용된다. | FFmpeg current trunk, checked 2026-10-03 | FFmpeg source |
| **Verified fact.** `TemporaryDirectory`는 정상 context exit/destruction/interpreter cleanup path에서 cleanup을 수행한다. | Python 3.12 | Python 3.12 `tempfile` docs |
| **Interpretation.** SIGKILL이나 abrupt container termination은 Python cleanup code가 실행될 기회를 주지 않으므로 temporary/partial output의 잔존을 별도로 고려해야 한다. | Python process + signal semantics 종합 | Python docs |

---

## 4. Options / Patterns

### Part A — config 출처 · secret 전달 패턴

#### A-1. Compose `environment:` / interpolation

**Interpretation**

흐름:

`source → Compose interpolation → service.environment → container process environment → application`

Source는 shell, project `.env`, `--env-file` 등이 될 수 있다.

**Trade-off**

- 별도 file-reading logic 없이 일반 process environment로 전달 가능하다.
- secret은 process environment라는 비교적 넓은 surface에 들어간다.
- resolved Compose config, Docker container configuration, `/proc` 등 운영권한을 가진 주체에게 노출될 가능성을 고려해야 한다.
- 이미 실행 중인 container의 environment는 rotation으로 변경되지 않는다.
- 현재 대신고 loader가 `os.environ`을 읽지 않는 상태에서는 application까지 연결되지 않는다.

#### A-2. Compose service `env_file:`

**Interpretation**

흐름:

`host env file → Compose parse → container environment → application`

**Trade-off**

- Compose YAML 자체와 값을 분리할 수 있다.
- host file을 plaintext로 생성하면 host filesystem에 새로운 secret-at-rest surface가 생긴다.
- file 자체가 container에 mount되는 것은 아니며 최종적으로 process environment가 된다.
- normal parsing과 `format: raw`의 차이를 고려해야 한다.
- rotation 후 host file만 고쳐도 이미 실행 중인 process environment는 변하지 않는다.

#### A-3. Host secret file → bind mount / Compose `secrets`

**Interpretation**

흐름:

`Parameter Store → EC2 host plaintext file → /run/secrets/... → application file read`

**Trade-off**

- secret이 일반 application environment 전체에 포함되지는 않는다.
- 대신 host filesystem file과 container mount라는 surface가 생긴다.
- service별 secret grant와 filesystem permissions로 접근 범위를 나눌 수 있다.
- application이 startup 한 번만 읽는지 매번 읽는지에 따라 rotation 반영 semantics가 달라진다.
- bind-mounted source file을 atomic replace/overwrite했을 때 running container에서 정확히 어떤 방식으로 새 content가 관찰되는지는 Compose secret rotation contract로 명시돼 있지 않아 spike 대상이다.

#### A-4. EC2 host가 Parameter Store fetch → shell env → Compose

**Interpretation**

권한 주체는 EC2 instance role이다.

**Trade-off**

- GitHub runner가 plaintext secret 자체를 보지 않아도 된다.
- GitHub deploy role에는 Run Command를 보낼 권한만, EC2 instance role에는 SSM/KMS read 권한을 두는 식의 권한 분리가 가능하다.
- host command의 process environment 및 이후 container environment라는 노출면은 남는다.
- shell command가 값을 `echo`, `set -x`, error output 등으로 내보내면 Run Command output/S3/CloudWatch 경로로 전파될 수 있다.

#### A-5. EC2 host가 Parameter Store fetch → env file

**Interpretation**

권한 주체는 EC2 instance role이다.

**Trade-off**

- secret 전달과 Compose invocation을 file로 decouple할 수 있다.
- file mode, parent directory access, deletion, failed deployment 뒤 잔존이 별도 운영 대상이 된다.
- 이후 `env_file:`로 넣으면 최종 container surface는 environment이다.

#### A-6. EC2 host가 Parameter Store fetch → secret file

**Interpretation**

A-3과 동일한 container-side semantics에 SSM fetch가 붙는다.

**Trade-off**

- environment-wide exposure 대신 file exposure를 갖는다.
- host file lifecycle과 rotation semantics가 추가된다.
- fetch가 실패한 상태에서 과거 file을 그대로 재사용하는지, deployment를 실패시키는지는 script semantics에 달려 있다.

#### A-7. Container application이 Parameter Store runtime fetch

**Interpretation**

흐름:

`application → AWS SDK → IMDSv2 temporary instance credentials → SSM/KMS`

**Trade-off**

- plaintext host env file/secret file을 만들지 않는 구성이 가능하다.
- 반대로 application runtime 자체가 `ssm:GetParameter*`와 `kms:Decrypt` 권한을 행사할 수 있는 주체가 된다.
- container에서 IMDS 접근 가능 여부와 hop limit 설정이 실제 dependency가 된다.
- Parameter Store/network/IAM failure가 application startup 또는 runtime failure domain으로 들어온다.
- rotation 반영 시점은 startup fetch, per-use fetch, cache refresh 등 application semantics에 달려 있다.

#### A-8. GitHub Actions가 fetch → plaintext를 Run Command parameter로 전달

**Interpretation**

권한 주체는 GitHub Actions OIDC deploy role이다.

**Trade-off**

- EC2 instance role에 secret read permission을 추가하지 않는 구성이 가능하다.
- 반대로 plaintext secret이 GitHub runner와 Run Command request boundary를 통과한다.
- AWS가 Run Command command input에 plaintext secret을 넣지 말라고 명시하고 있으므로, 이 패턴은 CloudTrail/command history라는 추가 audit exposure를 가진다.
- GitHub masking은 log 노출 완화 수단이지 secret이 runner/API request를 통과하지 않았다는 의미는 아니다.

---

### Part B — 중단 대상별 구현 패턴

| 대상 | Pattern | 실제 stop 범위 | Trade-off |
|---|---|---|---|
| Python handler | cancellation flag polling | 다음 polling point에서 cooperative stop | blocking 구간만큼 반응 지연 |
| Python async handler | `Task.cancel()` / cancel scope | 다음 async cancellation point | coroutine cleanup 가능; sync blocking code에는 직접 전달되지 않음 |
| sync code in thread | flag + thread 내부 check | check를 수행하는 code만 cooperative stop | thread 자체 강제 stop 불가 |
| handler child process | parent → SIGTERM/SIGKILL | child process 격리 단위 | IPC/DB/resource 경계 추가; force kill cleanup 보장 없음 |
| sync HTTP | client/library 반환, timeout 또는 library-specific abort | caller thread가 unblock되는 범위 | generic safe request-level cancel primitive 없음 |
| async HTTP | owning task cancellation | client-side await/stream 중단 가능 | remote provider calculation stop은 별도 문제 |
| streaming HTTP | response `close`/`aclose` | response consumption/connection resource 중단 | server processing/billing stop 보장 아님 |
| ffmpeg | stdin `q` | ffmpeg graceful stop path | stdin pipe 관리 필요 |
| ffmpeg | SIGINT/SIGTERM | ffmpeg graceful signal path | 종료까지 finite time 필요; trailer success 보장 아님 |
| ffmpeg | SIGKILL | process 즉시 강제 종료 | cleanup/trailer 불가, partial file 위험 |
| ffmpeg tree | process group + `killpg` | 같은 process group에 남아 있는 processes | group/session을 벗어난 descendant까지 보장하지 않음 |
| whole Worker container | Docker stop | worker lifecycle 전체 | 사용자 특정 JobExecution cancel과 scope가 다름 |

#### Sync HTTP call

**Interpretation**

현재처럼 Worker main execution path에서 sync request 하나가 blocking 중인 경우 cancellation flag가 DB에 생겨도 **그 thread가 Python으로 돌아오기 전까지 flag polling은 진행되지 않는다.**

Possible mechanisms는 다음처럼 서로 다른 의미를 갖는다.

- request library 자체의 공식 cancellation primitive
- connection/response close
- transport timeout
- entire client close
- HTTP 수행을 별도 thread/process에 격리
- async request로 바꾸고 owning task를 cancel

이 중 **connection close는 client-side wait를 끝내는 것**과 **provider-side inference를 취소하는 것**을 동일하게 보장하지 않는다.

#### Async HTTP call

**Interpretation**

Async request가 network await 중이라면 owning `Task` cancellation은 sync thread polling보다 직접적인 cancellation path를 제공할 수 있다.

하지만 다음 세 단계는 별도다.

`Python task cancelled`\
→ `HTTP transport/stream closed`\
→ `provider computation stopped`

첫 단계에서 세 번째 단계까지의 전파는 HTTP protocol이나 Python `Task.cancel()`만으로 보장되지 않는다.

#### UsageRecord 시점

**Interpretation**

| 중단 시점 | provider call “시작” 관찰 | usage 확인 가능성 |
|---|---|---|
| adapter dispatch 전 | 시작되지 않음 | 없음 |
| request transmission 시작 후, body 완료 전 | client 기준 dispatch됨; provider는 partial request만 봤을 수도 있음 | 대체로 exact usage 알 수 없음 |
| request body 전송 완료, response 대기 | provider가 request를 받은 가능성이 높음 | response/provider ledger가 없으면 불명확 |
| response 수신 중 | provider call 시작은 명확 | non-stream final response 전에는 exact usage가 없을 수 있음 |
| streaming 중 disconnect | call 시작 및 partial response 존재 가능 | final usage chunk를 받지 못하면 exact total usage가 없을 수 있음 |

OpenAI API의 `X-Client-Request-Id`는 timeout/network ambiguity에서 provider receipt 조사에 도움을 주지만 “중복 실행 방지” 기능은 아니다.

**Interpretation — 일반 원장 패턴**

시작된 호출 row를 먼저 만들고 이후 outcome을 `completed`, `cancelled-client-side`, `transport-error`, `usage-unknown` 등으로 갱신하는 구조는 “시작된 호출마다 row” 원칙과 양립할 수 있다. `usage=null/unknown`과 `usage=estimated`를 구분하는 것도 가능한 표현 방식이다.

이는 RD-19c의 schema 선택을 확정하는 결론이 아니라, 외부 API가 항상 exact usage를 반환하지 않는다는 제약에서 나온 선택지다.

#### Idempotency

**Interpretation**

“OpenAI-compatible”라는 표현 자체는 idempotency semantics를 보장하지 않는다.

Current OpenAI Python SDK 내부에는 retry 관련 idempotency-key helper가 존재하지만, 모든 ordinary OpenAI-compatible request에 적용되는 보편적인 application-level idempotency contract로 문서화되어 있지는 않다.

따라서 ambiguous disconnect 후 retry가 provider 측 중복 processing을 막는지는 **사용 endpoint/provider별 External Input**에 해당한다.

#### ffmpeg `run` vs `Popen`

**Interpretation**

`subprocess.run()`은 호출이 반환되기 전 `Popen` handle을 application cancellation controller가 지속적으로 보유하는 구조가 아니다. 반면 `Popen`은 PID/process group/stdin을 보유한 채 poll/send_signal/terminate/kill/communicate를 조합할 수 있다.

이는 `Popen`이 최종 선택이라는 뜻이 아니라, **“실행 중 외부 cancel signal을 받고 child를 단계적으로 종료한다”는 기능을 표현할 수 있는 control surface가 `run`보다 넓다**는 차이다.

---

## 5. Failure Modes / Operational Risks

### Part A

| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
|---|---|---|---|
| Project `.env`와 service `env_file` 혼동 | interpolation file을 container file로 간주 | application loader가 값을 못 찾음 | Compose integration spike로 구분 가능 |
| `.env`가 shell 값에 의해 override | 동일 variable이 shell과 `.env`에 존재 | 예상과 다른 resolved config | `docker compose config --environment`로 관찰 가능 |
| `environment`가 `env_file` override | 같은 key 중복 | env file 수정이 효과 없음 | resolved config 확인 가능 |
| Secret이 `docker compose config`에 materialize | secret을 `${VAR}`로 Compose model에 interpolation | operator terminal/log에 노출 가능 | command output 취급 정책으로 완화 가능 |
| Container env 노출 | secret을 process environment로 전달 | inspect/proc/debug surface 증가 | file-based 전달과 trade-off 가능 |
| Host plaintext file 잔존 | fetch 후 env/secret file 생성, cleanup 실패 | EC2 disk에 secret 잔존 | restrictive permissions/cleanup/startup audit 가능 |
| Run Command history/API exposure | GitHub runner가 plaintext secret을 command input에 넣음 | CloudTrail/history reader가 value 관찰 가능 | fetch location 변경 등 선택지 존재 |
| Run Command output leak | script가 secret을 stdout/stderr로 출력 | console/S3/CloudWatch 전파 | script/log hygiene로 완화 가능 |
| GitHub masking 실패 | transformed/encoded/generated value 출력 | Actions log leak | explicit masking; 그래도 완전 보장 아님 |
| SSM read AccessDenied | wrong role/path/KMS policy | deploy/startup/runtime fetch 실패 | preflight IAM test 가능 |
| `GetParametersByPath` policy gap | parent path read가 허용됨 | 의도보다 넓은 parameter access | IAM path test 가능 |
| KMS access gap | SSM allow지만 `kms:Decrypt` 없음 | SecureString decrypt 실패 | permission simulation/spike 가능 |
| IMDS unreachable from container | IMDSv2 + hop/network setting 불일치 | runtime fetch credential 획득 실패 | container integration test 가능 |
| Rotation not reflected | SSM update 후 running container만 restart | old environment 계속 사용 | recreate/read semantics 검증 가능 |
| Old secret file retained after failed fetch | fetch 실패를 script가 fatal 처리하지 않음 | 이전 credential을 계속 사용하는 ambiguity | script failure contract로 구분 가능 |
| Compose secret source rotation ambiguity | running bind mount source를 교체 | 새 값 관찰 시점 불명확 | 실제 filesystem update 방식으로 spike 필요 |

### Part B

| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
|---|---|---|---|
| Cancel flag observed late | 긴 sync HTTP/CPU/subprocess blocking | 사용자 cancel 요청 후 계속 RUNNING | cancellation checkpoint 구조 또는 isolation 선택지 |
| Thread cancellation 착각 | async wrapper만 cancel | underlying sync thread 계속 동작 | thread/process boundary 관찰 가능 |
| `asyncio.timeout`이 실제 handler cancel | wait-only timeout에 timeout context 사용 | 정해진 timeout 정책과 불일치 | waiting task와 work task 분리 가능 |
| Sync HTTP `client.close()` race | 다른 thread에서 shared client close | 동작이 transport/version-dependent | SDK-version-specific spike |
| Client disconnected, provider still running | request가 이미 provider에 전달 | cost/side effect 발생 가능 | provider contract 확인 필요 |
| Ambiguous HTTP retry | disconnect 후 같은 call 재실행 | provider 중복 processing 가능 | provider idempotency 확인 필요 |
| UsageRecord exact usage 없음 | network failure/stream interruption | 호출 row는 있으나 usage 미확정 | unknown/estimated state 표현 가능 |
| `subprocess.run(timeout)` kills ffmpeg | run timeout 만료 | graceful trailer path 우회 | timeout 종류 분리 가능 |
| SIGKILL partial output | forced escalation | invalid/incomplete output 잔존 가능 | temp-name/validation 패턴 가능 |
| Child만 kill되고 descendant 잔존 | subprocess가 process tree 생성 | orphan workload | process group/isolation 선택지 |
| Pipe deadlock | stdout/stderr PIPE를 drain하지 않음 | cancellation/finish 모두 지연 | `communicate` 또는 drain 구조 |
| Zombie | child exit 후 parent가 wait/reap 안 함 | process table entry 잔존 | `Popen.wait/communicate`, init 역할 |
| Parent hard kill | container/worker SIGKILL | `finally`, temp cleanup 미실행 | next-start scavenging 가능 |
| Process terminate 중 DB/queue corruption | force kill at critical section | transaction/IPC ambiguity | isolation boundary·transaction design 필요 |
| Cancel/completion race | cancel request와 handler completion 동시 | final status 경쟁 | DB state transition rule 필요 |
| Provider 완료와 local cancel race | response 도착 직전 cancel | provider cost/result 존재하지만 execution CANCELLED 가능 | RD-19b/19c 내부 상태 규칙 필요 |

---

## 6. Daesingo-specific Implications

### Part A

#### RD-07a — config 출처와 우선순위

**Daesingo implication**

현재 loader 규칙은 다음과 같은 deployment mismatch를 만든다.

`Compose environment → os.environ`\
≠\
`현재 loader → cwd/.env only`

따라서 RD-07a는 단순히 “Compose에서 무엇을 쓸지”만의 문제가 아니라 **application config loader가 어떤 sources를 읽으며 source collision 때 무엇이 이기는지**를 함께 정의하는 문제다.

외부 조사로 현실화된 선택 축은 다음과 같다.

1. process environment를 loader source에 포함하는지
2. cwd `.env`를 production source로 유지하는지
3. 두 source가 동시에 존재할 때 precedence
4. empty/unset value semantics
5. config와 secret에 동일 source rule을 적용하는지

Compose 자체의 precedence와 **application loader의 precedence는 별개의 층**이다.

#### RD-07c — secret source / 전달 방식

**Daesingo implication**

현재 deployment path가

`GitHub Actions OIDC → SSM Run Command → EC2 → Compose`

이므로 secret을 누가 decrypt하는가에 따라 IAM boundary가 크게 달라진다.

- GitHub role fetch: deploy role에 SSM/KMS read가 들어가고 secret이 runner를 통과
- EC2 host fetch: instance role에 SSM/KMS read가 들어가고 runner에는 plaintext를 전달하지 않을 수 있음
- container runtime fetch: application container가 instance-role capability를 사용할 수 있어야 함

세 경우는 기능적으로 동일한 “SSM 사용”이 아니다.

또한 `SecureString`을 GitHub에서 decrypt한 뒤 command argument로 넘기는 것과, **Run Command 안에서 EC2 role로 `get-parameter --with-decryption`하는 것**은 AWS audit exposure가 다르다.

Parameter Store rotation 자체는 새 version을 만들지만, container process가 새 secret을 즉시 본다는 의미는 아니다.

---

### Part B

#### RD-19b — QUEUED · RUNNING cancellation semantics

**Daesingo implication — QUEUED**

Worker가 아직 dispatch하지 않은 JobExecution은 외부 HTTP call/subprocess가 없으므로 실제 running work를 중단하는 문제는 없다. 기존 정책의 `QUEUED → CANCELLED`와 기술적으로 충돌하는 외부 제약은 발견되지 않았다.

**Daesingo implication — RUNNING**

RUNNING 이후는 하나의 “cancel” primitive로 표현되지 않는다.

현재 handler의 진행 지점에 따라:

`Python step`\
→ cooperative check 가능

`sync provider HTTP call`\
→ main thread가 반환할 때까지 polling 불가

`ffmpeg subprocess.run`\
→ 현재 code 구조에서는 external Popen control surface가 없음

`DB operation`\
→ transaction boundary와 race를 고려

로 나뉜다.

따라서 “cancellation request를 Worker가 알았다”와 “현재 실행 중인 primitive가 실제로 멈췄다”는 서로 다른 event다.

**Daesingo implication — status timing**

외부 시스템 사례도 이 둘을 분리한다.

- Temporal: cancel request → heartbeat에서 전달 → Activity cancellation
- RQ: queued `CANCELED`와 running `stop` 별도
- Celery: revoke와 forced terminate 별도

따라서 RD-19b에서 `CANCELLED`가 의미할 수 있는 후보는 최소한 다음 두 계열이다.

- cancellation request를 accepted한 상태
- handler/resource가 실제 종료된 terminal 상태

어느 의미로 고정할지는 외부 조사로 결정할 수 없다.

#### Timeout과 cancellation

**Daesingo implication**

정해진 대신고 정책:

> timeout은 사용자 취소가 아니며 진행 중 work를 강제로 취소하지 않고 상위 orchestrator의 wait만 끝낸다.

Python primitive의 실제 semantics:

- `asyncio.timeout()` → underlying Task cancellation을 사용
- `subprocess.run(timeout=...)` → child kill
- `asyncio.wait(..., timeout=...)` → pending task를 cancel하지 않고 반환 가능

따라서 코드에서 이름이 모두 `timeout`이라고 해도 동작이 서로 다르다.

현재 ffmpeg/ffprobe의 `subprocess.run(..., timeout=...)`이 제품에서 말하는 “wait-only timeout”과 동일한 timeout이라면 정책과 primitive semantics가 충돌한다. 별도의 subprocess safety timeout이라면 서로 다른 timeout category로 볼 수 있다.

#### RD-19c — provider call / UsageRecord

**Daesingo implication**

현재 정책은:

> 실제로 시작된 provider 호출은 call당 UsageRecord 1 row.

하지만 network layer에서는 “시작” 경계가 한 점으로 자동 제공되지 않는다.

가능한 관찰점은:

`adapter attempt created`\
→ `transport send entered`\
→ `request body transmission`\
→ `provider received full request`\
→ `provider accepted/assigned request id`\
→ `response received`

이다.

특히 현재 영상이 inline base64 body이므로 request body가 작지 않을 수 있고, **전송 도중 cancellation**과 **전송 완료 후 response wait 중 cancellation**의 불확실성이 다르다.

UsageRecord는 외부 research 관점에서 최소한 다음 상황을 표현할 수 있어야 한다는 제약이 생긴다.

- call은 dispatch됐지만 exact usage를 얻지 못함
- request가 provider에 도달했는지 local side에서 확정하지 못함
- response 일부는 받았지만 final usage metadata를 못 받음
- provider는 이미 처리했지만 client는 result를 버림

어떤 columns/status로 표현할지는 RD-19c 내부 결정이다.

#### ffmpeg cancellation

**Daesingo implication**

Current FFmpeg source 기준으로:

`q / SIGINT / SIGTERM`\
→ transcode loop break\
→ scheduler stop\
→ trailer write attempt

반면

`SIGKILL`\
→ handler/code cleanup 실행 불가

이다.

따라서 “ffmpeg를 중단한다”도 graceful request와 hard kill로 나뉜다.

또한 `subprocess.run(timeout)`이 POSIX `SIGKILL` 경로를 밟는다는 사실 때문에 현재 timeout implementation에서 생성된 partial output과 사용자 cancellation 결과를 동일하게 가정할 수 없다.

#### Partial file / idempotency

**Daesingo implication**

중단된 transform의 일반적인 file lifecycle 선택지는 다음 형태를 가진다.

`unique temp output`\
→ transform\
→ validate/complete\
→ final path로 atomic rename

취소/강제 종료로 temp가 남으면 다음 Worker startup이나 job retry에서 stale temporary path를 식별·회수하는 패턴이 가능하다.

이는 대신고의 final file layout을 확정하는 결론이 아니라 **hard kill에서는 Python cleanup을 신뢰할 수 없다는 제약에 대한 일반 패턴**이다.

---

## 7. What External Research Cannot Decide

### 내부 합의가 필요한 것

- **RD-07a**
  - production loader가 `os.environ`을 읽는지
  - `.env`를 어떤 환경에서 source로 인정하는지
  - `.env`와 environment가 충돌할 때 application-level precedence
  - missing / empty / invalid config의 fail-fast rule

- **RD-07c**
  - GitHub deploy role / EC2 instance role / container 중 누가 Parameter Store를 fetch할지
  - config와 secret을 environment/file/runtime fetch 중 어떤 boundary로 나눌지
  - host plaintext file이 생기는 패턴을 허용할지와 lifecycle
  - rotation 후 recreate/restart/re-read 동작

- **RD-19b**
  - `CANCELLED`를 cancellation request acceptance 시점에 기록할지 실제 handler stop 이후에 기록할지
  - cancel와 success가 동시에 발생할 때 어느 terminal transition이 승리하는지
  - graceful cancellation 이후 force escalation을 둘지
  - subprocess safety timeout과 orchestrator wait timeout을 별개 개념으로 둘지

- **RD-19c**
  - “provider call started”의 operational boundary
  - exact usage를 못 얻은 UsageRecord 표현
  - cancelled locally but provider potentially completed인 attempt 표현
  - retry attempt마다 row를 갖는지 logical call마다 row를 갖는지

### 실제 실험이 필요한 것

- 대신고에 실제 설치될 Docker Compose v2 version에서 env/interpolation matrix
- Compose secret backing file update 방식별 running container 관찰
- 현재 OpenAI SDK/실제 provider adapter의 sync in-flight close semantics
- async cancellation 때 사용 transport가 connection에 어떤 signal을 보내는지
- packaged ffmpeg version에서 signal별 output integrity
- ffmpeg가 대신고 command line에서 실제 descendant process를 만드는 경우가 있는지
- hard-kill 뒤 temp/media residue 회수 동작
- cancel-vs-complete DB transition race

### External Input이 필요한 것

- 실제 선택 provider가 client disconnect 이후 inference를 중단하는지
- disconnect된 request에 대한 provider별 billing
- provider별 idempotency/deduplication key 지원
- provider별 interrupted response의 usage 조회 API 존재 여부
- OpenAI-compatible proxy가 upstream request cancellation을 전달하는지
- proxy가 request body를 완전히 buffer한 뒤 upstream에 보내는지 streaming proxy하는지

---

## 8. Suggested Pre-implementation Checks

다음은 production baseline 값을 정하기 위한 실험이 아니라 **semantics 확인용 small spike**다.

### Part A

1. **Compose source matrix**
   - 동일 key에 Dockerfile `ENV`, `env_file`, `environment`, project `.env`, shell, CLI override를 각각 넣음
   - container에서 `printenv`
   - `docker compose config`
   - `docker compose config --environment`
   결과를 비교

2. **현재 loader reachability**
   - container environment에만 value 존재
   - cwd `.env`에만 value 존재
   - 둘 다 존재
   세 경우를 현재 loader와 변경 후보 loader에서 확인

3. **Filesystem check**
   - project host `.env`만 존재시 container cwd에 `.env`가 생기지 않는지 확인
   - `env_file:` 사용 후 container 안 해당 source file 자체가 존재하는지 확인

4. **Exposure check**
   - test-only dummy secret을 `environment:`에 주입
   - `docker inspect`
   - `/proc/<pid>/environ`
   - `docker compose config`
   에서 어느 권한으로 관찰되는지 기록

5. **Compose secret check**
   - `/run/secrets/<name>` path
   - owner/mode
   - api와 worker 중 grant하지 않은 service의 visibility
   확인

6. **Rotation check**
   - Parameter Store dummy value v1 → v2
   - `docker compose restart`
   - recreate
   - source file in-place write
   - source file atomic replacement
   각각에서 application이 보는 값을 기록

7. **SSM IAM check**
   - 정확한 parameter path만 허용한 test role
   - `GetParameter`
   - `GetParameters`
   - `GetParametersByPath` parent path
   - `kms:Decrypt`
   조합별 allow/deny 확인

8. **Run Command leakage check**
   - 실제 secret 대신 dummy marker 사용
   - command history / CloudTrail / stdout / CloudWatch 경로 중 marker가 어디에 남는지 확인

9. **Container IMDS check**
   - api/worker container에서 AWS credential provider chain이 instance profile credential을 얻는지
   - 현재 hop-limit과 IMDSv2-only setting을 기록

### Part B

1. **Cooperative cancel latency anatomy**
   - Python step
   - DB query
   - sync HTTP wait
   - ffmpeg wait
   각 state에서 cancel flag가 실제로 다시 확인되는 boundary만 기록

2. **Sync HTTP mock server**
   - request upload 중 pause
   - request 완전 수신 뒤 response delay
   - streaming response 중 pause
   세 지점을 만들고 다른 thread의 `client.close()`, socket/response close 등을 시험
   - caller unblock 여부
   - server가 처리 계속하는지
   - connection reuse 영향
   기록

3. **Async HTTP mock server**
   - 동일 세 지점에서 owning `Task.cancel()`
   - `CancelledError`
   - connection close
   - server-side work continuation
   을 별도로 기록

4. **OpenAI-compatible proxy**
   - 실제 adapter와 동일 transport/version에서 request ID를 남기고 cancel 실험
   - 결과는 “provider billing baseline”으로 사용하지 않고 semantics evidence로만 저장

5. **ffmpeg signal matrix**
   - 정상 완료
   - stdin `q`
   - SIGINT
   - SIGTERM
   - SIGKILL
   - 현재 `subprocess.run(timeout)`
   별로 exit code, process residue, file 존재, ffprobe 가능 여부를 확인

6. **Process-group spike**
   - `Popen(start_new_session=True)`
   - child가 test descendant를 생성
   - child-only signal과 `killpg` 결과 비교

7. **Pipe pressure test**
   - 많은 stderr를 출력하는 child로 PIPE 미소비/`communicate` 차이 확인

8. **Crash cleanup test**
   - `TemporaryDirectory`
   - graceful exception
   - SIGTERM
   - SIGKILL
   별 residue 확인
   - Worker restart 때 stale directory 탐지 가능성 확인

9. **Cancel/completion race**
   - handler commit 직전/직후 cancel을 넣어 JobExecution final status와 UsageRecord consistency 확인

---

## 9. Unresolved / Unverified

1. **Compose secret live rotation**
   - file-backed Compose secret source를 running container에서 교체했을 때 어떤 file-replacement 방식까지 즉시 반영되는지를 Compose가 rotation contract로 명시한 공식 문서는 확인하지 못했다.
   - bind mount implementation fact까지만 Verified다.

2. **`docker inspect`의 실제 운영 노출 범위**
   - `docker inspect`가 container configuration 전체를 출력한다는 것은 Verified다.
   - 어떤 daemon authorization model/운영계정에서 `Config.Env`를 읽을 수 있는지는 대신고 EC2의 Docker access model에 따라 달라진다.

3. **OpenAI Python sync in-flight request cancellation**
   - current SDK가 `client.close()`를 제공한다는 것은 Verified다.
   - 다른 thread가 이를 호출하면 특정 진행 중 request가 즉시/안전하게 abort된다는 documented guarantee는 확인하지 못했다.
   - SDK/HTTPX2 version-specific spike가 필요하다.

4. **HTTPX2의 cancellation 세부 transport semantics**
   - current OpenAI SDK가 HTTPX2를 사용한다는 것은 확인했다.
   - HTTPX 0.28의 timeout 문서는 비교 근거로 사용했으며 HTTPX2가 모든 세부 semantics를 동일하게 유지한다고 가정하지 않았다.

5. **Provider-side disconnect cancellation**
   - ordinary OpenAI REST request에서 client disconnect가 inference를 중단하거나 billing을 중단한다는 일반 보장은 공식 문서에서 확인하지 못했다.
   - Realtime 등 별도 API의 explicit cancel 기능을 ordinary HTTP semantics에 일반화하지 않았다.

6. **Provider idempotency**
   - “OpenAI-compatible” API 전체에 공통인 request idempotency guarantee는 확인되지 않았다.
   - 실제 provider/endpoint별 확인이 필요하다.

7. **ffmpeg version**
   - signal/trailer code path는 2026-10-03 current FFmpeg trunk source로 검증했다.
   - 대신고 EC2 image에 실제 설치되는 ffmpeg package version의 source가 동일하다고 가정하지 않는다.

8. **SIGTERM과 Python `TemporaryDirectory` cleanup**
   - context normal exit에서 cleanup되는 것은 Verified다.
   - SIGTERM 시 Python application이 custom handler 없이 종료될 경우 context cleanup/finally가 보장된다고 간주하지 않았다.
   - actual Worker signal handling과 함께 확인해야 한다.

9. **Cancel-vs-completion final-state race**
   - Celery/RQ/Temporal 모두 cancellation의 전달·강제종료 semantics가 서로 다르다.
   - 대신고의 DB terminal transition winner를 외부 사례에서 그대로 가져올 수 없다.

---

## 10. Sources

### Docker / Compose

- https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/ — Docker, **Environment variables precedence in Docker Compose**, 확인 2026-10-03.
- https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/ — Docker, **Variable interpolation**, 확인 2026-10-03.
- https://docs.docker.com/reference/compose-file/services/ — Docker, **Compose services reference**, 확인 2026-10-03.
- https://docs.docker.com/compose/how-tos/use-secrets/ — Docker, **Manage secrets securely in Docker Compose**, 확인 2026-10-03.
- https://docs.docker.com/build/building/variables/ — Docker, **Build variables**, 확인 2026-10-03.
- https://docs.docker.com/reference/cli/docker/compose/restart/ — Docker, **docker compose restart**, 확인 2026-10-03.

### AWS / GitHub

- https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-restrict-parameter-access.html — AWS, **Restricting access to Parameter Store parameters and paths**, 확인 2026-10-03.
- https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-restrict-decryption.html — AWS, **Restricting decryption of SecureString values**, 확인 2026-10-03.
- https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-paramstore-versions.html — AWS, **Parameter Store versions**, 확인 2026-10-03.
- https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html — AWS, **Parameter Store overview**, 확인 2026-10-03.
- https://aws.amazon.com/systems-manager/pricing/ — AWS, **Systems Manager pricing**, 가격 확인일 2026-10-03.
- https://docs.aws.amazon.com/systems-manager/latest/userguide/running-commands.html — AWS, **Running commands on managed nodes**, 확인 2026-10-03.
- https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-param-runcommand.html — AWS, **Parameter Store with Run Command**, 확인 2026-10-03.
- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-options.html — AWS, **Instance metadata options**, 확인 2026-10-03.
- https://docs.github.com/en/actions/reference/security/secure-use — GitHub, **Secure use reference**, 확인 2026-10-03.

### Python / AnyIO

- https://docs.python.org/3.12/library/threading.html — Python 3.12, **threading**.
- https://docs.python.org/3.12/library/signal.html — Python 3.12, **signal**.
- https://docs.python.org/3.12/library/asyncio-task.html — Python 3.12, **asyncio tasks**.
- https://anyio.readthedocs.io/en/stable/api.html — AnyIO, **API reference**, 확인 2026-10-03.
- https://docs.python.org/3.12/library/subprocess.html — Python 3.12, **subprocess**.
- https://docs.python.org/3.12/library/multiprocessing.html — Python 3.12, **multiprocessing**.
- https://docs.python.org/3.12/library/tempfile.html — Python 3.12, **tempfile**.

### HTTP / OpenAI

- https://github.com/openai/openai-python/releases — OpenAI Python SDK releases, 최신 확인 2026-10-03.
- https://github.com/openai/openai-python/blob/main/httpx2.md — OpenAI Python SDK, **HTTPX2 migration guide**, 확인 2026-10-03.
- https://github.com/openai/openai-python/blob/main/src/openai/_base_client.py — OpenAI Python SDK, **base client source**, 확인 2026-10-03.
- https://github.com/openai/openai-python/blob/main/src/openai/_streaming.py — OpenAI Python SDK, **streaming source**, 확인 2026-10-03.
- https://developers.openai.com/api/reference/overview — OpenAI API, **API overview / request IDs**, 확인 2026-10-03.
- https://platform.openai.com/docs/api-reference/chat/object — OpenAI API, **Chat Completions reference**, 확인 2026-10-03.
- https://www.python-httpx.org/advanced/timeouts/ — HTTPX, **Timeouts**, 확인 2026-10-03.
- https://www.rfc-editor.org/rfc/rfc9112.html — IETF, **RFC 9112 — HTTP/1.1**.
- https://www.rfc-editor.org/rfc/rfc9113.html — IETF, **RFC 9113 — HTTP/2**.

### FFmpeg / job-system reference cases

- https://www.ffmpeg.org/doxygen/trunk/ffmpeg_8c_source.html — FFmpeg current source, **fftools/ffmpeg.c**, 확인 2026-10-03.
- https://ffmpeg.org/faq.html — FFmpeg, **FAQ**, 확인 2026-10-03.
- https://docs.celeryq.dev/en/latest/userguide/workers.html — Celery 5.6.x, **Workers Guide**, 확인 2026-10-03.
- https://python-rq.org/docs/jobs/ — RQ, **Jobs**, 확인 2026-10-03.
- https://docs.temporal.io/nexus/standalone-activity — Temporal, **Activity cancellation behavior**, 확인 2026-10-03.
