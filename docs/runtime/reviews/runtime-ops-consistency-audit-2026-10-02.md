# Runtime/Ops §0 현재 상태 정합성 검수 — 2026-10-02

**Status:** Review Evidence — not a Source of Truth

**Audited SHA:** `9c204ee3c14036860124d2ac5e5453ce93d80226`

**Date:** 2026-10-02

> 이 문서는 특정 develop snapshot에 대한 정합성 검수 결과다. 결정 자체의 Source of Truth가 아니며, 후속 수정에 따라 일부 finding은 해소될 수 있다. 현재 규칙은 각 Contract · ADR · Runtime Spec에서 읽는다. 검수 직후 처리 결과는 §11에 기록한다.

> audit only (검수 수행 당시). tracked file 수정·Issue·PR·commit 없음. 모든 line 번호는 위 Audited SHA 기준이다.

## 1. Audit metadata

| 항목 | 값 |
| --- | --- |
| audited_at | 2026-10-02 (KST, 작업 시작 시 `git fetch origin --prune` 직후) |
| repository | `kakaotechcampus-4/ktc4-chonnam-2` (local: `daesingo-monorepo`) |
| origin/develop SHA | `9c204ee3c14036860124d2ac5e5453ce93d80226` — Merge PR #222 (2026-10-02T22:10:06+09:00) |
| local branch | `docs/runtime-ops-261002` @ `35b3029` — develop의 조상(이미 병합됨, PR #229). clean |
| working tree | clean. 검수는 별도 detached worktree(`%TEMP%/audit-dev-9c204ee`)에서 read-only로 수행 |
| CI on 9c204ee | `python-tests` success · `boundary-check` success (gh run list) |
| 검수 경로 | `docs/runtime/**` 전부 · `docs/architecture/{module-architecture(라우팅 범위), erd-draft, contracts/README}` · Runtime 관련 Contract 4건 + ADR 4건 · `src/daesingo/{common,api,worker,case,search,recording,readout}` Runtime 접점 · `tests/` · `scripts/check_*.py` · `.github/` 전체 · root config(`pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`) · `apps/web` · `docs/modules/{case,search}/decisions` 관련분 · `docs/management/{ownership, cross-cutting-decisions}` 관련분 · 링크된 Issue/PR 25건 |

## 2. Executive summary

```text
STALE DOC:                12
CONTRACT / SPEC MISMATCH:  3
IMPLEMENTATION GAP:       10
OPEN DECISION:            17
```

가장 중요한 5개:

1. **B-01 (HIGH)** — `module-architecture.md` §8-2와 `src/daesingo/worker/README.md:6`은 「`case_rev` 불일치 → STALE」이라고 쓴다. JobExecution Contract·Runtime Spec은 「STALE = Worker 소멸, old `case_rev` SUCCEEDED는 SUCCEEDED 유지」다. 하필 Worker composition root의 README가 틀린 쪽을 담고 있다.
2. **B-02 (HIGH)** — Runtime Tech Spec §6.3은 backoff가 끝난 뒤 새 JobExecution을 만든다고 쓴다. 그러면 대표 execution(attempt 최댓값)이 그동안 STALE/FAILED가 되어, JobRecord/CaseView Contract A절 §10-6의 「재시도 중 FAILED로 깜빡이지 않는다」를 깬다. queue schema를 닫기 전에 정리해야 한다.
3. **A-04 · B-03 · A-11 (MEDIUM)** — Runtime 문서 4곳은 아직 「#153 조사 결과를 기다린다」고 쓰지만 #153은 2026-09-26에 합의됐다(Search rate 주입 유지 · `pricing_id` 지금 추가 · `ELICE_ML_API_KEY` rename). UsageRecord Contract §5는 여전히 「가격표는 common/runtime config 소유」다. 통화도 2026-09-08에 「KRW 정규화」로 결정됐는데 Contract §10과 #153 코멘트는 미결로 다룬다.
4. **C-01~C-03 (HIGH)** — MySQL persistence·Queue·lease/heartbeat·API/Worker composition root·health endpoint는 develop에 **하나도 없다**(문서의 「미구현」 목록은 정확하다). 현재 real 경로는 `case`의 adapter가 Search·Fine·Readout을 **동기 in-process로 직접 호출**하고, JobRecord는 메모리에만 쌓인다.
5. **D-03 · D-08 · D-10 (timing A)** — 구현 전에 닫아야 할 숨은 결정 셋: ① retry 책임 층위. Search가 이미 슬롯 안에서 `sleep` 재시도를 하고 그 대기를 case timeout 150s에 포함한다. ② HTTP API Contract가 없고 transport 담당이 `api` Owner와 web 사이에서 엇갈린다. ③ config 주입. `common/env.py`가 `.env` 파일만 읽고 process env를 무시한다.

## 3. Coverage

| 영역 | 실제로 확인한 것 |
| --- | --- |
| Runtime docs | `README` · `runtime-ops-workflow` · `runtime-tech-spec` · `ops-spec` · `deployment-runbook` · `official-inputs/{README,aws-environment,mlapi}` · `experiments/{README,elice-runtime-capacity-smoke-plan}` — **전문**. 상대 링크 전수 해석(깨진 링크 0) |
| Architecture | `module-architecture.md` §0 머리말·개정이력, §1, §2 원칙6·7, §4-모듈5(case), §5-12·§5-13, §6, §7-4, §8, §10, §11-6 (CLAUDE.md 라우팅 범위. 전문 아님) · `erd-draft.md` 머리말·도표·§5·§7 · `contracts/README` · `docs/README` 우선순위 |
| Contracts | `contract-job-execution` 전문 · `contract-usage-record` 전문 · `contract-job-record-case-view` A절 전문 + B절 Runtime 관련 행(grep) · `contract-analysis-source-derived` §4·§5·§8·§11 (grep 중심) |
| ADR | `adr-erd-runtime-alignment-2026-09-19` 전문 · `adr-job-execution` 전문 · `adr-job-record-case-view` (retry/STALE/status grep) · `adr-usage-record` 존재 확인 |
| Code | `common/*` 전문 · `api/`·`worker/` (README만 존재) · `case/{adapters(부분),command,jobs,domain(부분),store,service(부분)}` · `search/{ledger,usage,retry,config,execution,provider(부분)}` · `recording/{service(부분),materialization(부분),observability}` · `readout/api` 공개 함수 목록 · repository-wide keyword grep(§5 목록 전부) |
| Tests | `tests/` 트리, Runtime 관련 테스트(`tests/common/test_job_execution.py`, `tests/case/test_scenario_infra_failure_smoke.py`), skip marker |
| CI | `.github/workflows/*.yml` 5개 **step·command 전문** · CODEOWNERS · 최근 develop run 결과 · repo Variables/Secrets 이름 목록 |
| Docker/deploy | repository-wide `Dockerfile*`·`*compose*`·`Caddyfile`·`nginx*`·`*.sql`·migration·lint/secret-scan config 검색 (모두 0건) |
| Official Inputs | 두 문서 전문을 Ops/Tech/P2와 대조 (인터넷 재조사 없음) |
| Case boundary | JobRecord 발주, command 진입점, CaseStore, adapter sync real 경로, `timeout-fallback.md`, `job-resume-identity-policy.md`, `budget-krw-normalization.md`, `design-refinement-w7-baseline.md` §6, `contract-case-command.md` 머리말 |
| Recording/Search/Readout/Evidence | Runtime 접점만 (materialization 위치·reuse·purge, provider retry/timeout/usage/pricing/config, readout 1-call 불변조건, export capability 존재) |
| Issue/PR | #19 #33 #41 #46 #47 #72 #95 #106 #128 #153(본문+코멘트) #154 #155 #156 #157 #165 #168 #170 #182 #200 #219 #222 #229 #231 #237, open PR 목록 |

---

## 4. STALE DOC

### A-01 — Runtime 「현재 구현 상태 — 2026-09-19」 3곳이 develop보다 뒤처짐
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime
- **현재 주장:** `docs/runtime/README.md:75-84`, `runtime-tech-spec.md:520-531`, `ops-spec.md:164-172`. 확인된 구현을 「recording fixture/in-memory capability」·「boundary-check GitHub Action」 수준으로만 쓴다.
- **현재 증거:**
  - `.github/workflows/python-tests.yml:44-57`: 필수 media smoke + `pytest -q` 전체 회귀 (`5e61dfe`, 2026-09-28)
  - Python 3.12 표준화 (`10cfca4`, 2026-09-20)
  - recording 실제 ffmpeg materialization (`recording/materialization.py:188-200`) + 다중 원본 Timeline (PR #222)
  - Search real Elice 경로 (PR #128 · #219)
  - case 동기 real 경로 (`case/adapters.py:461`)
- **판단:** 「아직 구현되지 않은 Runtime」 목록(README:86-94, Tech:533-540, Ops:174-183)은 전수 확인 결과 **여전히 정확하다**. 뒤처진 쪽은 「확인된 구현」과 날짜다.
- **Impact:** Implementation Plan에서 CI·recording 실구현을 없는 것으로 보고 중복 발주할 위험.
- **Next:** 문서 위생 묶음. · **Confidence:** High

### A-02 — Ops §5 Python 불일치 표가 해소된 상태를 미해결로 기술
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime/Cross-cutting
- **현재 주장:** `ops-spec.md:237-255`. 「2026-09-19 현재」 pyproject `>=3.10` · uv.lock `>=3.13` · boundary CI 3.11. 체크박스 6개 모두 미완.
- **현재 증거:**
  - `pyproject.toml:10` `>=3.12`
  - `uv.lock:3` `>=3.12`
  - `.python-version` `3.12`
  - `boundary-check.yml:27` 3.12, `python-tests.yml:26` 3.12
  - `python-tests.yml:32` `uv sync --locked`
  - 커밋 `10cfca4` (2026-09-20)
- **판단:** 6개 중 5개는 완료. 남은 항목은 「repo-wide type checker」 하나(type checker 설정 파일·CI step 0건).
- **Next:** 문서 위생. · **Confidence:** High

### A-03 — Ops §19 「현재 실제 CI」가 boundary-check만 있다고 기술
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime
- **현재 주장:** `ops-spec.md:662-676`. CI는 `boundary-check.yml`(Python 3.11)뿐이라 「repo-wide pytest/Ruff/type/gitleaks까지 한다고 쓰지 않는다」. 목표 확장 순서 `ops-spec.md:678-687`.
- **현재 증거:**
  - `python-tests.yml` 존재: PR(develop/main)·push(develop)·dispatch / ubuntu-24.04 / uv 0.11.15 / `uv sync --locked --extra test --extra eval-gemini` / ffmpeg 설치·`-fps_mode`·`libx264` 검사 / recording media smoke 1건 (skip 금지 assert) / `pytest -q` (testpaths=`tests`, `pyproject.toml:49`)
  - `boundary-check.yml`은 3.12
  - Runtime 문서끼리도 어긋난다: `runtime-ops-workflow.md:416`은 python-tests가 이미 repo-wide pytest를 돈다고 정확히 쓴다.
- **실제 상태 (gate별):**

  | Gate | 상태 |
  | --- | --- |
  | Python 3.12 | 실제 존재 |
  | `uv sync --locked` | 실제 존재 |
  | boundary/contract fixture | 실제 존재 |
  | repo-wide pytest (offline) | 실제 존재 |
  | media smoke | 실제 존재 |
  | Ruff | 문서만 (CI·config 0) |
  | type checker | 문서만 |
  | secret scan | 문서만 |
  | MySQL integration | 없음 |
  | External/Real E2E | CI 밖 (의도대로) |
  | deploy/OIDC/SSM | 없음 |
  | web vitest/tsc | CI 없음 (Web scope, 참고) |

- **Next:** 문서 위생. · **Confidence:** High

### A-04 — 「#153 조사 결과를 기다린다」 표현이 합의 이후에도 남아 있음
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime/Search
- **현재 주장:**
  - `README.md:137-141` (Search 주도 전수조사 중)
  - `runtime-tech-spec.md:378-385` (#153 결과 후 공동 결정), `:482` (`GEMINI_API_KEY` 유지·migration은 #153 대기), `:562-563`
  - `experiments/elice-runtime-capacity-smoke-plan.md:72` · `:185`
- **현재 증거:**
  - Issue #153 코멘트 2026-09-26: Search 전수조사 완료 (kong2488-star) → Runtime Owner(flosure23) 응답. 합의 내용은 ① 공용 pricing catalog는 지금 만들지 않고 Search rate 주입 유지 ② `pricing_id`(+unit) 지금 추가 ③ `GEMINI_API_KEY → ELICE_ML_API_KEY` rename, alias는 Search config 내부 ④ Runtime은 Search가 확정한 usage/cost/pricing context로 Final UsageRecord를 append.
  - 후속 PR #155·#156·#157 MERGED.
  - Runtime 쪽 최신 문서 `official-inputs/mlapi.md:254`는 이미 합의를 반영해서, Runtime 문서끼리 서로 다르다.
  - #153 자체는 OPEN (마지막 갱신 09-27).
- **Impact:** 닫힌 경계(provider 의미=Search, 주입·원장=Runtime)를 Decision Register에 다시 올릴 위험.
- **Next:** 문서 위생. 단 pricing 표현은 B-03과 함께 처리. · **Confidence:** High

### A-05 — Architecture·Contract 본문에 Job Intent/Execution 분해 이전 문구 잔존
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Cross-cutting
- **현재 주장:**
  - `module-architecture.md:864`: 「`CANCELLED`는 제품 요구가 없어 status에 두지 않는다」
  - `:1290-1312` (§5-13): `JobRecord`가 `QUEUED→RUNNING→…` lifecycle을 갖고 runtime 필수 개념(attempt, available_at, lease, produced refs)이 JobRecord 아래에 있음
  - `:1366-1367` (§6-2): `result ref + usage → JobRecord / UsageRecord`
  - Contract 내부 잔존: `contract-job-record-case-view.md:100`·`:167` (「status 5값 고정」), `contract-job-execution.md:81` (`enum(5)`)
  - `docs/management/ownership.md:253` (status 5값)
- **현재 증거:**
  - `contract-job-execution.md:13`·`:92-114`: v1.1에서 `CANCELLED` 추가, 6값
  - `contract-job-record-case-view.md:79`·`:150`: JobRecord에 실행 상태 없음
  - 코드 `common/job_execution.py:13` 6값
  - Architecture 머리말 `:23`·`:57`이 enum·schema를 Final Contract에 위임
- **판단:** 의미 충돌이 아니라 상위 문서가 enum/schema를 Contract에 위임한 뒤 남은 잔재. STALE 의미 충돌(§8-2)은 B-01로 분리.
- **Next:** Architecture maintenance 묶음 (Owner: 문서 일관성 B-4). · **Confidence:** High

### A-06 — Architecture §10-2 Search baseline이 Elice 전환 이전 상태
- **Classification:** STALE DOC · **Severity:** LOW · **Scope:** Search/Cross-cutting
- **현재 주장:** `module-architecture.md:1705` 「Gemini Files API / Flash-Lite 계열」, `:1707` 「한 RemoteCopy를 coarse/fine에서 재사용」 (§10-2 「현재 baseline」).
- **현재 증거:**
  - #95 전환으로 Files API 제거·base64 inline (#153 본문)
  - `search/provider.py:92-93` data URL
  - `search/config.py:25` `gemini-3.8-flash`
  - Search 코드에 RemoteCopy 사용 0건 (grep)
- **Impact:** Object Storage·RemoteCopy 운영 가정을 잘못 세울 수 있음. 머리말 `:23`의 historical 지정은 §10-3·§11·§13만 해당하고 §10-2는 빠져 있다.
- **Confidence:** High

### A-07 — Ops §11 Local Disk Guardrail이 AnalysisSource를 disk 소비자로 가정하지만 실제 구현은 process memory
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime/Recording
- **현재 주장:** `ops-spec.md:435-447`. local disk 경쟁 목록에 AnalysisSource·IncidentClip을 넣고 「proxy/AnalysisSource byte」를 disk 관측 대상으로 둔다.
- **현재 증거:**
  - `recording/service.py:125-131`: `_local_analysis: dict[str, (AnalysisSource, bytes)]`, `_local_clips` — 준비된 bytes를 인스턴스 메모리에 보관
  - `materialization.py:188`: `TemporaryDirectory`는 encode 동안만 쓰임
  - `service.py:515-533`: reuse key는 `(timeline_id, revision, span, profile_ref)`이고 인스턴스 dict에 보관
  - `service.py:195-200`: `close()` 때만 해제
- **판단:** 현재 working set은 50GB disk가 아니라 Worker RSS(t3.medium usable 약 3.7GiB, `aws-environment.md:153`)에 쌓인다. P2 plan은 RSS도 관측하므로 실험 설계는 살아 있지만, guardrail 서술의 축이 다르다.
- **Next:** D-11의 근거로 넘김. · **Confidence:** Medium-High (등록 원본·repository 경로 전체는 미추적)

### A-08 — case A-1 timeout 잠정값·정책이 Runtime 문서에 연결되지 않음
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime/Case
- **현재 주장:** Runtime Tech/Ops/P2 plan에 timeout 정책 참조가 없다 (`timeout-fallback`·`max_latency`·A-1 grep 0건. `mlapi.md:248`이 #72를 실험 링크로만 언급).
- **현재 증거:** `docs/modules/case/decisions/timeout-fallback.md`
  - `:26`: Coarse 클립당 150s
  - `:29`: Fine 70s
  - 클립 Job 동시성 1
  - `:34`: 진행 중 Job은 강제 취소하지 않고 case가 기다리는 것만 멈춘다
  - `:42`: 「runtime 머신 재측정(common/runtime 배치 후)」에서 확정
  - 코드 `case/real_e2e.py:158-160`
- **Impact:**
  - lease duration·STALE threshold는 job wall(150s + provider 재시도 대기)을 넘어야 한다.
  - P2는 case가 기다리는 재측정 장소인데 계획에 없다.
  - 「강제 취소 안 함」은 CANCELLED 전이 사용처와 맞물린다.
- **Next:** D-04 입력. · **Confidence:** High

### A-09 — Ops §12-1·P2 plan이 Elice provider 사실을 모델 범위 없이 일반화
- **Classification:** STALE DOC · **Severity:** LOW · **Scope:** Runtime/Search
- **현재 주장:** `ops-spec.md:501` 「Elice ML API의 inline video 경로가 실제 호출에서 동작했다」, P2 plan §1 `:15-22`.
- **현재 증거:**
  - `official-inputs/mlapi.md:131` (video modality 지원 확인 ≠ MP4 전달 계약), `:238`·`:250` (Flash 관측을 Pro/GPT에 적용하지 않음)
  - PR #231·#237 (2026-10-02, 다른 모델·이미지 transport 실험)
  - 운영 config는 여전히 `gemini-3.8-flash` (`search/config.py:25`)
- **판단:** 현재 운영 경로 기준으로는 참이지만 「gemini-3.8-flash / OpenAI-compatible `/v1/chat/completions` 2026-09」 범위 표기가 없다. 모델이 바뀌면 base64 video working set 가정이 바뀐다.
- **Confidence:** Medium

### A-10 — Ops가 인용하는 공식 공지 3건이 Official Inputs에 없음
- **Classification:** STALE DOC · **Severity:** LOW · **Scope:** Runtime
- **현재 주장:**
  - `ops-spec.md:65`: 「2026-09-22 카테캠 AWS 공지」로 OIDC/SSM baseline 확정, role 이름 `ktc-github-deploy`·`ktc-ec2-ssm-role`
  - `ops-spec.md:818-820`: OIDC guide · 무료 도메인 · CI/CD 특강 인용
- **현재 증거:** `official-inputs/README.md:12-15`에는 `aws-environment`·`mlapi` 두 건만 있다. `aws-environment.md:30` Notice date 「확인 필요」. role 이름은 Official Inputs 어디에도 없다 (`aws-environment.md:175`는 「deploy role provision」만).
- **Impact:** workflow §1 「공식 입력은 official-inputs에 보존」과 어긋나고, OIDC/SSM 결정의 근거 추적이 Ops 산문에만 남는다.
- **Confidence:** High (공지 원문 접근 불가는 §9 참조)

### A-11 — 통화 정규화 결정이 Contract §10·Runtime 문서·#153에서 미결로 취급됨
- **Classification:** STALE DOC · **Severity:** MEDIUM · **Scope:** Runtime/Case/Search
- **현재 주장:**
  - `contract-usage-record.md:234`: 「KRW 고정 여부 정하지 않았다 → Consumer Review 항목」
  - #153 Runtime 코멘트 (2026-09-26): 「USD vs `max_cost_krw` 통화 접합은 별도 결정으로」
  - Runtime 문서에는 언급 없음
- **현재 증거:** `docs/modules/case/decisions/budget-krw-normalization.md:6-10` (결정일 2026-09-09, 이슈 #19 common/runtime 답변, #19 CLOSED)
  - budget 판정 원천 = UsageRecord
  - `UsageRecord.cost`는 **저장 전 KRW 정규화**, `currency="KRW"`
  - provider-native 통화·환율 provenance는 `pricing_id`가 가리키는 versioned artifact가 보존
- **판단:** 「무엇을 할지」는 닫혀 있다 (구현 미비는 C-05). 「FX 출처·artifact 위치」만 남은 미결이다 (D-07). Decision Register에 「통화 정책」 전체를 올리면 안 된다.
- **Confidence:** High

### A-12 — `apps/web/README.md`가 코드·package.json이 없다고 기술 (참고, Web scope)
- **Classification:** STALE DOC · **Severity:** LOW · **Scope:** Web
- **현재 증거:** `apps/web/package.json` 존재 (React 19·Vite 6·vitest), `src/` 화면·contract 모듈 존재.
- **Runtime 관련:** Web에는 HTTP 호출이 하나도 없다 (`fetch`/`axios`/`VITE_`/polling grep 0건). fixture 기반이라 Web↔backend endpoint 불일치는 아직 생길 수 없다. 대신 HTTP 계약 부재가 숨어 있다 (D-08).
- **Next:** Web Owner에게 알림만 (다른 모듈 문서). · **Confidence:** High

---

## 5. CONTRACT / SPEC MISMATCH

### B-01 — 「old `case_rev` → STALE」 vs 「STALE = Worker 소멸」
- **Classification:** CONTRACT / SPEC MISMATCH · **Severity:** HIGH · **Scope:** Runtime/Case
- **충돌하는 주장:**
  - `module-architecture.md:1551` (§8-2): 「case_rev mismatch이면 STALE로 처리하고 현재 CaseView를 덮지 않음」
  - `:1541`: 「application/runtime composition root가 JobRecord 생성·enqueue」
  - `src/daesingo/worker/README.md:6`: 「`case_rev`가 현재와 다르면 결과를 STALE로 처리」
- **반대 증거:**
  - `contract-job-execution.md:100` (STALE = 「worker가 살아 있지 않다고 판정됨」), `:171` (불변조건 8: case가 mismatched produced를 반영하지 않음)
  - `contract-job-record-case-view.md:59` (JobRecord Producer = case)
  - `runtime-tech-spec.md:239-247` (SUCCEEDED + old case_rev → SUCCEEDED 유지, case가 적용 거부), `:516` (integration test #8 「old case_rev SUCCEEDED가 STALE로 바뀌지 않음」)
  - `README.md:59`
  - Architecture 자기 본문 `:858-859` (§4-모듈5 ④: 「현재 case_rev와 맞는 결과만 반영」)
- **Authoritative:** JobExecution Contract. Architecture 머리말 `:23`·`:57`이 state 의미를 Final Contract에 위임하고, Architecture 안에서도 §4-모듈5 ④가 Contract와 같은 뜻이다.
- **Impact:** Worker 구현자는 `worker/README`부터 읽는다. 그대로 구현하면 Contract 불변조건과 Runtime acceptance #8을 위반하고, CaseView projection이 정상 결과를 FAILED로 보인다 (STALE→FAILED 매핑).
- **Next:** 별도 Issue 후보 (workflow §0 「구현 방향을 잘못 유도할 수 있는 정합성 문제」). · **Confidence:** High

### B-02 — Retry backoff 동안 대표 execution 상태 vs CaseView 「깜빡임 없음」 규칙
- **Classification:** CONTRACT / SPEC MISMATCH · **Severity:** HIGH · **Scope:** Runtime/Case/Web
- **Spec 주장:**
  - `runtime-tech-spec.md:215-221`: 「현재 execution terminal 기록 → available_at 계산 → claim 대상에서 대기 → **시간이 된 뒤 새 JobExecution 생성**」
  - `:251-261`: 「retry 허용 → attempt 2 QUEUED」 (생성 시점 불명)
- **Contract 주장:**
  - `contract-job-record-case-view.md:152` (A절 §10-6): 대표 execution = attempt 최댓값. 「attempt 1이 STALE로 판정된 순간에도 progress[]는 곧바로 FAILED로 깜빡이지 않고 attempt 2가 QUEUED/RUNNING인 동안 진행 중으로 보인다」
  - 매핑 `:460`: STALE→FAILED
- **판단:** Spec대로면 backoff 동안 attempt 최댓값이 STALE(또는 FAILED)이고, 대표 상태가 FAILED로 투영된다. 두 문장은 동시에 참일 수 없다. 해소하려면 다음 중 하나가 필요하다.
  - Runtime이 terminal 기록과 **같은 transaction에서** 다음 attempt를 QUEUED로 만들고, 대기는 queue metadata(`available_at`)로 처리
  - projection이 「재시도 예정」을 알게 하는 Contract 변경
  - 첫 방식이면 `JobExecution.queued_at`(Contract §10-2 「queue 대기 시간」)이 backoff를 포함하게 된다. eval latency 의미와 연결된다.
- **Authoritative:** JobRecord/CaseView Contract (상위).
- **Impact:** queue/execution 물리 schema와 claim query 모양이 바뀐다 → D-01·D-02 선결.
- **Confidence:** Medium-High (「곧바로 깜빡이지 않고」를 transient 금지로 읽었다)

### B-03 — 가격표 소유: UsageRecord Contract vs Runtime Spec / #153 합의 / 실제 코드
- **Classification:** CONTRACT / SPEC MISMATCH · **Severity:** MEDIUM · **Scope:** Runtime/Search/Eval
- **Contract 주장:** `contract-usage-record.md:112`: 「가격표 자체는 이 계약에 넣지 않는다 … 표는 `common/runtime` config가 소유한다」, `:235` (위치·개정 절차만 구현 세부).
- **반대 증거:**
  - `runtime-tech-spec.md:376`: 「Runtime config가 독점한다고 선결하지 않는다」
  - #153 합의 (2026-09-26): MVP는 Search가 rate를 주입받아 계산, 공용 catalog는 요구가 생기면 검토
  - Runtime Owner가 같은 코멘트에서 「Contract의 과거 문구는 Runtime이 후속 정합화」를 약속했으나 미수행
  - 코드: rate는 `search/config.py:43-44` (`DAESINGO_GEMINI_*_USD_PER_MILLION`, `.env`)
- **Authoritative:** SoT 순서상 아직 Final Contract. 다만 Contract Owner(common/runtime) 본인이 개정을 약속한 상태라, 실질적으로는 「Contract 개정 대기」다.
- **Impact:** 「가격표 SSOT」를 OPEN DECISION으로 다시 올리면 #153을 되돌린다. 「Contract가 이미 닫았다」고 보면 #153 합의와 코드를 무시한다. 둘 다 오류다.
- **Next:** Contract 문구 정합화 Issue. · **Confidence:** High

---

## 6. IMPLEMENTATION GAP

### C-01 — MySQL Runtime persistence 전무 (Queue · JobExecution · UsageRecord · lease/heartbeat/sweep)
- **Classification:** IMPLEMENTATION GAP · **Severity:** HIGH · **Scope:** Runtime
- **방향이 닫힌 곳:**
  - `module-architecture.md:184` (A3 확정: FastAPI 1 + Worker 1 + MySQL 8.4 DB Queue), `:1694-1695`
  - `contract-job-execution.md` §6·§9
  - `adr-erd-runtime-alignment` (물리 선택만 미결)
- **현재 상태:**
  - `pyproject.toml:12-15` 의존성은 pydantic·tzdata뿐 (DB driver/ORM 없음)
  - `*.sql`·migration·`SKIP LOCKED`·`FOR UPDATE`·`available_at`·`heartbeat`·`lease`(코드) grep 0건
  - JobExecution은 `common/job_execution.py:167-269` `InMemoryJobExecutionStore`만 있다 (상태 전이·attempt 연속성은 Contract와 일치)
- **질문별 답:**

  | 질문 | 답 |
  | --- | --- |
  | MySQL persistence | 없음 |
  | DB Queue | 없음 |
  | Queue row와 JobRecord 분리 | 구현 대상 자체가 없음 |
  | `SKIP LOCKED` | 문서 후보뿐 (`runtime-tech-spec.md:159`) |
  | JobExecution persistence | in-memory |
  | UsageRecord persistence | 없음 |
  | migration | 없음 |
  | lease/heartbeat/sweep storage | 없음 |
  | 이미 닫힌 physical schema | 없음 (ADR non-decision `:262-271`) |

- **Confidence:** High

### C-02 — API composition root · HTTP endpoint · `/health/live`·`/health/ready` 부재
- **Classification:** IMPLEMENTATION GAP · **Severity:** HIGH · **Scope:** Runtime
- **방향이 닫힌 곳:** `module-architecture.md:158` (202 Accepted), `:1692` (FastAPI 확정), `runtime-tech-spec.md:413-441`.
- **현재 상태:**
  - `src/daesingo/api/`는 `README.md`만 있다 (「아직 코드가 없다」 `:10`)
  - FastAPI/uvicorn 의존성 없음. 코드에서 FastAPI 문자열은 `case/service.py:358` 주석 1건
  - health endpoint grep 0건
- **Confidence:** High

### C-03 — Worker composition root 부재 · case → Runtime 발주 경로 없음 · real 경로는 동기 in-process 호출
- **Classification:** IMPLEMENTATION GAP · **Severity:** HIGH · **Scope:** Runtime/Case
- **방향이 닫힌 곳:** Architecture 원칙 6 (`:236-242`), §8-1 Background (`:1525-1532`, Coarse/Fine 외부 AI는 background), `runtime-tech-spec.md` §12.
- **현재 상태:**
  - `src/daesingo/worker/`는 README만 있다
  - `case/command.py:11-12`: `RUN_NOTICE_ACTION`은 JobRecord를 남길 뿐
  - `case/jobs.py:36-63`: `case.record_job()`으로 aggregate 메모리에 append
  - `case/store.py:1-6`: in-memory, 재시작 시 소실
  - `case/adapters.py:34-35`·`:474`: `get_job_executions`는 RealAdapter에서 `NotImplementedError`
  - `:461`: 「동기 real 경로에는 JobExecution이 없어 …」
  - `RealAdapter`/`RealVideoAdapter`가 `real_e2e` 체인(Search·Fine(유료)·Readout)을 CaseView 조립 중 직접 호출한다
- **판단:** 의도된 interim이다 (recording/JobExecution 3주 plan `docs/superpowers/plans/2026-09-19-…:56-57`). 다만 Runtime이 받을 「case → dispatch」 포트가 코드에 없다 → D-09.
- **Confidence:** High

### C-04 — Final UsageRecord Producer 부재. Search 내부 `UsageRecord`는 다른 구조
- **Classification:** IMPLEMENTATION GAP · **Severity:** MEDIUM · **Scope:** Runtime/Search
- **방향이 닫힌 곳:** `contract-usage-record.md` §4·§8 (Producer common/runtime, 호출 1건당 append, 시작된 invocation마다 row `:215`).
- **현재 상태:** `search/ledger.py:7-19`의 `UsageRecord` dataclass
  - `usage_id`·`execution_ref`·`run_ref`·`run_ref_reason`·`pricing_context` 없음
  - `cost_usd` (USD)
  - provider `"elice"` 하드코딩 (`:27`)
  - 재시도: `search/retry.py:47-76` `call_with_retry`가 실패 attempt를 기록 없이 재호출한다. 최종 성공 결과만 ledger에 남으므로, 「시작된 invocation마다 row」와 맞지 않는다
  - #153에서 합의된 `pricing_id`도 미구현 (src grep 0)
  - Final Contract와 이름이 같은 다른 타입이라 접합 시 혼동 위험
- **Confidence:** High (실패 attempt 미기록은 coarse/fine 호출 흐름 기준. 다른 경로는 미추적)

### C-05 — KRW 정규화(2026-09-09 결정) 미구현, budget 미집행
- **Classification:** IMPLEMENTATION GAP · **Severity:** MEDIUM · **Scope:** Search/Runtime/Case
- **결정:** `budget-krw-normalization.md:9` (A-11).
- **현재 상태:**
  - `search/coarse.py:88`: 「`max_cost_krw`는 KRW↔USD 환산이 미결이라 여기서 집행하지 않는다」
  - `:331-336`: 총비용 USD
  - `case/real_e2e.py:160`: `max_cost_krw=1000` 전달
- **Impact:** 팀 ₩120,000 크레딧 초과 시 Key가 자동 삭제된다 (`mlapi.md:26`). 현재 KRW budget guard가 동작하지 않는다 (USD `max_cost_usd`만 존재).
- **Confidence:** High

### C-06 — #153 합의 `GEMINI_API_KEY → ELICE_ML_API_KEY` rename 미구현
- **Classification:** IMPLEMENTATION GAP · **Severity:** LOW · **Scope:** Search
- **현재 상태:** `.env.example:5`; `search/cli.py:72,160,183`; `case/real_e2e.py:709`; `eval/gemini_preflight.py:42` 외 scripts 다수.
- **판단:** 합의상 alias는 Search 내부에 둔다. Runtime secret wiring 전에 처리해야 deployment secret 이름이 한 번에 정해진다.
- **Confidence:** High

### C-07 — `REPORT_VIDEO_EXPORT`·`PLATE_IMAGE_EXPORT` kind에 대응하는 public capability 없음
- **Classification:** IMPLEMENTATION GAP · **Severity:** MEDIUM · **Scope:** Recording/Runtime
- **방향이 닫힌 곳:** `contract-job-record-case-view.md:117-120` (두 kind 등재, DerivedAsset 생성 발주), `case/jobs.py:20-29`, `case/command.py:31-34` (발주 매핑 존재).
- **현재 상태:** `recording/service.py` 공개 메서드는 `register_derived_asset`/`get_derived_asset`뿐이다. export 함수는 repository 전체에서 0건이고, `jobs.py:27` 주석 「recording 구현 대기」, #47 OPEN.
- **Impact:** Tech Spec §16 「Job kind → public capability dispatch registration」을 6 kind 중 4개만 채울 수 있다.
- **Confidence:** High

### C-08 — Docker/Compose · deployment workflow · OIDC/SSM 미구현
- **Classification:** IMPLEMENTATION GAP · **Severity:** MEDIUM · **Scope:** Runtime
- **방향이 닫힌 곳:** `ops-spec.md:65-88` (OIDC + SSM baseline 확정), `:52-57` (api/worker/mysql Compose).
- **현재 상태:**
  - Dockerfile·compose·`.dockerignore`·Caddy/Nginx 0건
  - workflow 5개 중 배포·AWS 인증 0
  - repo Variables 0건 (`AWS_ACCOUNT_ID` 미등록, `gh variable list`)
  - 문서가 이미 「향후」로 명시하므로 STALE은 아니다. Runbook §8 미결 항목 중 develop에 들어온 것도 없다.
- **Confidence:** High

### C-09 — Structured logging · correlation(`trace_id`/`case_id`/`job_id`/`execution_id`) 부재
- **Classification:** IMPLEMENTATION GAP · **Severity:** MEDIUM · **Scope:** Runtime/Cross-cutting
- **방향:** `ops-spec.md:259-315` (key-value structured log 기본, 전파 원칙).
- **현재 상태:**
  - `src/`에 `logging` import 0건, `trace_id` 0건
  - `recording/observability.py`는 phase 시간·실패 code를 내부 sink로 모으는 관찰기다. 경로·명령·예외 원문을 수집하지 않아 privacy guardrail과는 부합하지만, 로그 파이프라인은 아니다
  - `print(` 사용 10개 파일 (CLI 중심)
- **Confidence:** High

### C-10 — Runtime 결정론 테스트 계층·경계 검사 미구현
- **Classification:** IMPLEMENTATION GAP · **Severity:** LOW · **Scope:** Runtime
- **방향:** `runtime-tech-spec.md:488-518` (§16: MySQL Runtime Integration 8건, import boundary, dispatch registration).
- **현재 상태:**
  - `scripts/check_boundaries.py:26-37` BOUNDARIES에 `common`·`api`·`worker` 규칙이 없다 (case/recording/search/readout/evidence/eval/web만). 현재 `common`은 pydantic만 import해 위반은 없음.
  - MySQL integration job 없음
  - dispatch registration 테스트 없음 (대상 Worker 부재)
- **Confidence:** High

---

## 7. OPEN DECISION candidates

> 답은 제안하지 않는다. 「현재 근거」는 결정이 닫히지 않았다는 증거와 연결점이다.

### D-01 — Queue / execution 물리 schema + claim transaction
- **미결:** table 분할, column, index, Queue row와 JobRecord 관계, `SELECT … FOR UPDATE SKIP LOCKED` exact query·transaction 경계.
- **근거:** `runtime-tech-spec.md:147`·`:159`·`:548`·`:552`, ADR non-decision `:262-266`.
- **연결:** B-02, D-02, D-05, C-01.
- **Owner 후보:** common/runtime (결정 김준영 · 구현 정철원, ADR `:72-77`) · **Consult:** case (JobRecord 저장 위치)
- **Timing:** A · **외부 조사:** 예 (MySQL 8.4 InnoDB lock semantics, workflow §4 예시 그대로) · **실험:** pre-implementation spike 가능 · **ADR 후보:** 예 (`runtime-db-schema` 후속 고려 `:262`)

### D-02 — 재시도 attempt 생성 시점과 `queued_at` 의미 (B-02 해소)
- **미결:** 다음 attempt를 terminal 기록 시점에 QUEUED로 만들지, `available_at` 도래 시점에 만들지. 그에 따른 projection 무결성과 queue-wait 지표 의미.
- **근거:** B-02.
- **Owner 후보:** common/runtime · **Consult:** case (유소연), web (신유민), eval (김대원, latency 집계)
- **Timing:** A · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR 후보:** Contract 명확화가 필요하면 예

### D-03 — Retry 책임 층위와 retryable mapping
- **미결:**
  - ① provider adapter의 in-call retry(Search `max_retries=3`, `retry_base_sec=5`, 슬롯 안 `sleep`: `search/config.py:37-38`, `retry.py:76`. case가 이 대기를 timeout 예산에 포함: `timeout-fallback.md:26` 「재시도 대기 최대 35초」)와 Runtime execution retry(`runtime-tech-spec.md:204-221`, 「sleep으로 슬롯을 붙잡지 않는다」)의 관계
  - ② FAILED(일시적 오류) execution도 자동 retry 대상인지, STALE만인지. Contract `:15`의 「자동 인프라 재시도(`STALE`)에 한정」 문구는 예시로도, 한정으로도 읽힌다
  - ③ `RUN_DEADLINE_EXCEEDED`(case timeout) 결과를 Runtime이 retry하면 case의 「이어서 찾기는 새 Job」 정책(`timeout-fallback.md:34-36`)과 겹치는지
  - ④ readout 1-call 불변조건(`contract-job-execution.md:172`)과의 조합
  - ⑤ in-call retry attempt별 UsageRecord (C-04)
- **Owner 후보:** common/runtime · **Consult:** search (서어진), case (유소연), readout (신유민)
- **Timing:** A (handler·failure taxonomy 모양). 수치는 B. · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR 후보:** 예 (여러 모듈 장기 영향)

### D-04 — Runtime provisional 값
- **미결:** retry max · backoff · jitter · lease duration · heartbeat interval·persistence · STALE threshold · sweep interval · polling interval.
- **근거:** `runtime-tech-spec.md:223-233`·`:277-285`·`:553-559`, Contract `:188-189` (구현 세부로 위임).
- **연결:** case 잠정 timeout 150s/70s (A-08)와 호환되어야 함.
- **Owner 후보:** common/runtime (구현 정철원) · **Consult:** case
- **Timing:** B (Provisional Baseline), 조정은 C (P2) · **외부 조사:** 아니오 · **실험:** 예 (P2) · **ADR 후보:** 아니오 (tuning)

### D-05 — `JobExecution.produced` 물리 저장 / `usage_refs` materialization
- **미결:** JSON vs `job_execution_products`, 별도 저장 vs `UsageRecord.execution_ref` projection.
- **근거:** ADR D5·D6 `:154-198`, `runtime-tech-spec.md:549-550`, ERD `:418`·`:420`.
- **Owner 후보:** common/runtime · **Consult:** eval (집계), case (produced 소비)
- **Timing:** A (D-01과 함께) · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR 후보:** D-01에 포함

### D-06 — UsageRecord append 시점 · in-flight 복구 · 중복 방지
- **미결:** 위 세 가지. adapter가 실패 invocation의 usage를 어떻게 노출하는지도 포함.
- **근거:** ADR D4 `:143-150`, `runtime-tech-spec.md:360`·`:551`, ERD `:490`.
- **Owner 후보:** common/runtime · **Consult:** search (usage 노출 모양), readout
- **Timing:** A · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR 후보:** 가능

### D-07 — `pricing_id` resolve 대상 · FX 출처 · `unit` 표기 (+ B-03 Contract 문구)
- **미결:** `pricing_id`가 가리키는 versioned pricing/FX artifact의 존재·위치. KRW 환산 출처 (`budget-krw-normalization.md` 「남은 것」: 「common/runtime 구현 시점에 결정」). `pricing_context.unit` 값. 원화 크레딧과 표시 가격의 정산 기준 (`mlapi.md:116-123`, 운영진 확인 필요).
- **닫힌 것 (재오픈 금지):** KRW 정규화 규칙(A-11), Search rate 주입 유지·`pricing_id` 추가(#153).
- **Owner 후보:** common/runtime + search · **Consult:** eval, case
- **Timing:** `pricing_id`/`unit` 전달 모양은 A (B baseline 가능). catalog 위치는 D. · **외부 조사:** 운영진 문의 (인터넷 조사 아님) · **실험:** 선정 모델 API smoke로 usage 관측 · **ADR 후보:** 가능

### D-08 — HTTP API Contract와 transport 담당
- **미결:** HTTP 경로·202 응답 모양·job 상태 조회·CaseView 조회·polling·업로드 endpoint·인증(A2 미결 `module-architecture.md:183`).
- **근거:**
  - HTTP API 계약 문서 0건
  - `contract-case-command.md:36`: transport는 범위 밖, Draft v0
  - `design-refinement-w7-baseline.md:83`: 「transport는 case 몫이 아니다 … 이번에는 신유민(web)이 진행」
  - `src/daesingo/api/README.md:3`: api Owner 김준영
  - #106 OPEN
- **Owner 후보:** api composition root Owner (김준영)와 web (신유민) 사이 확정 필요 · **Consult:** case (유소연)
- **Timing:** A (workflow §5 명시) · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR/Contract 후보:** 예

### D-09 — case → Runtime 발주 포트와 결과 반영 경로
- **미결:**
  - case가 append한 JobRecord가 Runtime queue에 도달하는 방식 (같은 transaction / composition root가 읽음 / 기타)
  - JobRecord·Case persistence 위치 (`case/store.py:1-6` in-memory)
  - 결과 반영 시점: 「늦게 도착한 결과는 candidate_id 일치 시만」(`timeout-fallback.md:35`), worker 배선 시 재선택 가드 (`design-refinement-w7-baseline.md` 6.6순위)
- **근거:** C-03, Architecture `:1345` (「case --JobIntent--> composition root」만 있고 기전 없음).
- **Owner 후보:** case (유소연) + common/runtime · **Consult:** —
- **Timing:** A · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR 후보:** 가능

### D-10 — Runtime configuration / secret 주입 방식
- **미결:** config shape(`runtime-tech-spec.md:560`). 주입 경로(파일 mount / process env / SSM Parameter 등, `deployment-runbook.md:179`, `ops-spec.md:795`).
- **제약 증거:**
  - `common/env.py:1`: 「설정의 유일한 출처는 이 파일이며 shell 환경변수는 쓰지 않는다」. `load_env_file()`이 `os.getcwd()/.env`만 읽는다 (`:12-13`). Search 결정 `gemini-3.8-proxy-baseline-2026-09-18.md:26`에서 유래
  - 따라서 Compose `environment:`/`env_file:`로 주입한 값은 현재 무시된다
  - 이미지 재사용·runtime 주입 원칙: `ops-spec.md:224-231`
  - 참고: `search/config.py:49` 기본 `base_url`에 tenant 경로가 하드코딩돼 있다 (secret은 아니지만 `mlapi.md:232`는 내부 endpoint URL을 문서에 싣지 않는 원칙)
- **Owner 후보:** common/runtime · **Consult:** search, eval
- **Timing:** A (Compose 전) · **외부 조사:** 아니오 (AWS SSM 사용 여부는 §1 입력) · **실험:** 아니오 · **ADR 후보:** 가능

### D-11 — Worker 안 domain service 수명과 AnalysisSource 저장·재사용 범위
- **미결:**
  - RecordingService 인스턴스 범위 (job별 / process별). 이것이 in-memory reuse 이득과 RSS 증가를 결정한다 (A-07)
  - process-local reuse 유지 여부
  - Object Storage·shared persistence 도입 조건
- **근거:** `ops-spec.md:459-469`·`:529-542`, workflow `:135` (공동 결정), Architecture A6 미결 `:187`.
- **Owner 후보:** recording (정철원) + common/runtime · **Consult:** search
- **Timing:** B (baseline 범위), C (P2-B/P2-D) · **외부 조사:** 나중에 (Object Storage) · **실험:** 예 · **ADR 후보:** 도입 시 예 (`experiments/README.md:332`)

### D-12 — Retention / purge (제품·정책 축과 Ops 구현 축이 섞여 있음)
- **미결:**
  - (a) **제품/정책:** Managed Source Copy·AnalysisSource·IncidentClip·DerivedAsset 보관 기간, RemoteCopy 삭제 정책, `purge_case`가 UsageRecord를 지우는지 (`contract-usage-record.md:236`, `contract-analysis-source-derived.md:617`, Architecture `:1723`)
  - (b) **Ops 구현:** log retention, temp cleanup 방식
- **관찰:** `ops-spec.md:554-564`는 7개 축을 한 목록에 두고, workflow는 retention을 「공동 결정」(`:136`)과 「제품/정책」(`:144-147`) 양쪽에 둔다.
- **Owner 후보:** (a) PM 김준영 (B-1) + recording (정철원), (b) common/runtime · **Consult:** case (C-4 학습 데이터 재사용, 유소연)
- **Timing:** (a) D 또는 pre-deploy 전, (b) B · **외부 조사:** 아니오 · **실험:** 아니오 · **ADR 후보:** (a) 예

### D-13 — 배포 파이프라인 세부
- **미결:** Dockerfile/Compose command · artifact 전달(S3/ECR) · immutable tag 규칙 · SSM Run Command · known-good revision 기록 · rollback command · migration/restore 절차 · MySQL volume/backup.
- **근거:** `ops-spec.md:780-796`, `deployment-runbook.md:175-184`.
- **Owner 후보:** common/runtime · **Consult:** —
- **Timing:** B (composition root 이후) · **외부 조사:** 일부 (ECR/S3 사용 패턴, §4 단계) · **실험:** 배포 smoke · **ADR 후보:** topology 변경 시

### D-14 — 운영 관측 수단
- **미결:** production log transport (CloudWatch Agent 미설치, `aws-environment.md:169`), log retention, health alert/restart threshold, queue/lease metric 방식.
- **근거:** `ops-spec.md:782-784`.
- **Owner 후보:** common/runtime
- **Timing:** B / C · **외부 조사:** 일부 · **실험:** 예 · **ADR 후보:** 아니오

### D-15 — Public endpoint · domain · TLS
- **미결:** EIP 요청 여부 (요청 필요 자원, `aws-environment.md:60`), DNS, reverse proxy (Caddy 후보), OAuth callback.
- **근거:** `ops-spec.md:113-162`·`:798`.
- **Owner 후보:** common/runtime · **Consult:** web, PM
- **Timing:** D (요구 발생 시) · **외부 조사:** 그때 · **실험:** 아니오 · **ADR 후보:** 아니오

### D-16 — Capacity / scaling
- **미결:** Worker concurrency, EC2 상향, disk guardrail, Object Storage, RDS, 전용 Queue, GPU.
- **근거:** `ops-spec.md:785-792`, P2 plan Planned (결과 없음).
- **Owner 후보:** common/runtime · **Consult:** recording, search
- **Timing:** C · **외부 조사:** §4 단계 · **실험:** 예 (P2 → P3) · **ADR 후보:** 결과에 따라

### D-17 — 선정 provider/model의 운영 한도 입력
- **미결:** timeout · RPM/TPM/concurrency · payload 상한 · codec · 실패 과금 · 예산 초과 시 Key 삭제 범위·복구.
- **근거:** `mlapi.md:200-215` 미확정 목록. Search config 값(`:37-38` retry, `provider.py` per-attempt 60s, inline 40/56 MiB)은 실험 근거의 Search 내부 값이고 provider 보장값이 아니다.
- **Owner 후보:** search (모델 선택) + common/runtime (adapter 운영 정책) · **Consult:** PM (운영진 문의)
- **Timing:** B (adapter baseline), C (smoke) · **외부 조사:** 운영진 문의 · **실험:** 선정 모델 API smoke · **ADR 후보:** 아니오

> CI gate 추가(Ruff · type checker · secret scan · MySQL integration job)는 Ops §19 목표 순서와 §23 「secret scan gate」로 열려 있다. 결정이라기보다 Implementation Plan의 CI 묶음이라 별도 항목으로 올리지 않았다. 필요하면 D-18로 추가한다.

---

## 8. Checked and consistent

| 경계 | 근거 |
| --- | --- |
| JobRecord = Intent, 실행 상태 필드 없음 | Contract A§3·§5 `:69-100` ↔ `case/jobs.py:50-63` ↔ ERD `:62-69` ↔ Tech §3.1 |
| 사용자 재실행 = 새 `job_id` (재개·재검색·재판독 포함) | Contract `:15`·`:290` ↔ `job-resume-identity-policy.md:11` ↔ `case/domain.py:299-304` ↔ ERD `:475` ↔ ADR D7 ↔ README `:57` ↔ Tech §6.1 |
| 자동 infra retry = same `job_id` + new `execution_id` + `attempt+1`, 기존 row 미부활 | Contract §9-1·2 ↔ ERD `:473-474` ↔ ADR D7 ↔ Tech `:111`·`:200`·`:251-261` ↔ `InMemoryJobExecutionStore.add_snapshot` `:190-198` |
| JobExecution 6 status·허용 전이·STALE `ended_at`/`failure_kind` nullable | Contract §6·§8 `:92-124` ↔ `common/job_execution.py:13`·`:40-67`·`:170-177` |
| JobExecution→CaseView 매핑 | Contract B §13 `:460` ↔ Tech §9 `:307-314` |
| 같은 kind 여러 Job 대표 규칙 (`requested_at` 최신, `case_rev` 정렬 금지) | Contract A§10-7 `:153-154` ↔ ADR D3 ↔ ERD `:488` ↔ Tech §9 `:316` |
| cache 재사용 조건 (같은 case·kind·fingerprint + `force_rerun=false` + SUCCEEDED) | Contract A§7 `:125` ↔ Tech §5 `:165-174` |
| UsageRecord 기록 대상 vs persistence 시점 분리 | Contract §8-14 `:215` ↔ ADR D4 ↔ ERD `:490` ↔ Tech §11.1 `:348-360` |
| Run `usage_refs`는 파생, `UsageRecord.run_ref`가 기준 | Contract §8-11·12 ↔ Tech §11.2 `:368` ↔ ERD `:419` |
| SoT 우선순위 | `docs/README.md:48-59` ↔ Runtime README `:9-16` ↔ Tech §1 `:41-47` ↔ ADR D1 — 동일 |
| case=orchestrator / runtime=executor, `case` timeout 소유 | Architecture 원칙 6 ↔ ownership ↔ `common/README.md` ↔ cross-cutting A-1 ↔ `timeout-fallback.md:15-16` |
| provider 호출은 `search/providers` 경계에서만 (A4) | `src/`에서 openai import는 `search/provider.py`뿐 |
| readout은 JobExecution/UsageRecord를 모르고 worker가 1회 호출 | `readout/api.py:21-26` ↔ Contract §9-9 ↔ JobRecord A§10-5 |
| AnalysisSource public 계약에 locator 비노출, RemoteCopy registry는 recording | Contract §4.2 `:145` ↔ recording 구현 (bytes는 내부 dict, ref만 반환) |
| AWS baseline: EIP/RDS/ALB/추가 EC2 미가정, SSM 접속, OIDC deploy role | Ops `:61`·§2-1·§18 ↔ `aws-environment.md` §2·§8 |
| Runtime 문서가 timeout/rate/codec 등 provider 값을 확정값으로 쓰지 않음 | Tech §6.4·§7.4, Ops §12-1 미확인 목록 ↔ `mlapi.md` §5 |
| Non-goals | Runtime README `:180-192` ↔ Ops §22 동일 |
| Runbook 미결 항목 | 전부 develop에 미구현 (선행 구현된 것 없음) |
| Runtime docs 상대 링크 | 전부 해석됨 |
| `common`의 의존 방향 | `common/*`은 pydantic만 import, domain import 없음 |

## 9. Unverified / limitations

- 카테캠 비공개 공지 원문 (AWS OIDC 2026-09-22 · 무료 도메인 · CI/CD 특강 · AWS 실습환경 · 2단계 MLAPI)에 접근하지 못했다. role 이름 `ktc-github-deploy`/`ktc-ec2-ssm-role`과 공지 날짜는 검증하지 못했다.
- 실제 AWS 상태는 조회하지 않았다. `aws-environment.md` §8 snapshot에 의존했다.
- external provider는 호출하지 않았다. 로컬 pytest도 실행하지 않았고 develop `9c204ee`의 GitHub Actions 결과(success)에 의존했다.
- `mlapi.md:62`가 참조하는 `.codex-scratch/elice-serverless-2026-10-02/` 원본 evidence는 열람하지 않았다.
- `module-architecture.md`는 CLAUDE.md 라우팅 범위만 읽었다 (§3, §4 타 모듈, §9, §12-13 미열람). `contract-job-record-case-view.md` B절은 Runtime 관련 행만 grep으로 읽었다. `contract-analysis-source-derived.md`는 §4·§5·§8·§11 위주로 읽었다. 그 밖의 Contract 11건과 ADR 15건은 Runtime 연관 키워드 외에는 열람하지 않았다.
- domain 모듈 알고리즘은 리뷰하지 않았다. `recording.purge_case`가 in-memory bytes(`_local_analysis`)까지 해제하는지는 추적하지 않았다.
- #153은 OPEN 상태다. 「합의」 판단은 두 Owner(Search·Runtime)의 2026-09-26 코멘트 내용에 근거했다.
- Git history는 판단에 필요한 커밋만 확인했다 (`10cfca4`, `5e61dfe`, common/api/worker 이력).
- `docs/archive/`는 규칙상 제외했다.

## 10. 다음 단계용 요약

### Decision Register로 넘길 후보

| ID | Decision | Owner | Consult | Timing | Current evidence | Research? | Experiment? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D-01 | Queue/execution 물리 schema + claim transaction | common/runtime (김준영 결정·정철원 구현) | case | A | Tech `:147,:159,:548,:552` · ADR non-decision `:262-266` · C-01 | 예 (MySQL 8.4 lock semantics) | spike 가능 |
| D-02 | 재시도 attempt 생성 시점 · `queued_at` 의미 | common/runtime | case · web · eval | A | B-02: Tech `:215-221` vs Contract A§10-6 `:152` | 아니오 | 아니오 |
| D-03 | Retry 책임 층위 · retryable mapping (FAILED/STALE/deadline) | common/runtime | search · case · readout | A (수치 B) | `search/retry.py:47-76` · `config.py:37-38` · `timeout-fallback.md:26,34` · Contract `:15` · Tech §6 | 아니오 | 아니오 |
| D-04 | retry/backoff/jitter · lease · heartbeat · STALE threshold · sweep · polling 값 | common/runtime | case | B → C | Tech §6.4·§7.4 · Contract `:188-189` · A-08 | 아니오 | 예 (P2) |
| D-05 | `produced` 저장 · `usage_refs` materialization | common/runtime | eval · case | A | ADR D5·D6 · ERD `:418,:420` | 아니오 | 아니오 |
| D-06 | UsageRecord append 시점 · in-flight 복구 · idempotency | common/runtime | search · readout | A | ADR D4 · Tech `:360` · C-04 | 아니오 | 아니오 |
| D-07 | `pricing_id` resolve 대상 · FX 출처 · `unit` (B-03 Contract 문구는 §11에서 해소 — 정책은 재오픈하지 않음) | common/runtime + search | eval · case | A (catalog 위치 D) | `budget-krw-normalization.md` 남은 것 · #153 합의 · Contract `:112,:235` | 운영진 문의 | 모델 smoke |
| D-08 | HTTP API Contract · transport 담당 | api Owner (김준영) ↔ web (신유민) 확정 필요 | case | A | `contract-case-command.md:36` · `design-refinement-w7-baseline.md:83` · `api/README.md:3` · #106 | 아니오 | 아니오 |
| D-09 | case → Runtime 발주 포트 · 결과 반영 경로 · JobRecord persistence | case + common/runtime | — | A | `case/command.py:11-12` · `store.py:1-6` · `adapters.py:461` · Architecture `:1345` | 아니오 | 아니오 |
| D-10 | Runtime config / secret 주입 방식 · config shape | common/runtime | search · eval | A | `common/env.py:1,12-13` · Search 결정 `:26` · Ops `:224-231` · Runbook `:179` | 아니오 | 아니오 |
| D-11 | Worker 내 service 수명 · AnalysisSource 저장·재사용 범위 | recording + common/runtime | search | B → C | A-07 · `recording/service.py:125-131,515-533` · Ops §11·§13 | 나중 (Object Storage) | 예 (P2-B/D) |
| D-12a | 자산·UsageRecord retention · purge 범위 (제품/정책) | PM 김준영 + recording | case (C-4) | D (pre-deploy 전) | Contract UsageRecord `:236` · AnalysisSource `:617` · Architecture `:1723` · Ops §14 | 아니오 | 아니오 |
| D-12b | log retention · temp cleanup (Ops) | common/runtime | — | B | Ops `:783` · §14 | 아니오 | 아니오 |
| D-13 | 배포 파이프라인 세부 (Docker/Compose · artifact · tag · SSM · rollback · migration · backup) | common/runtime | — | B | Ops `:780-796` · Runbook `:175-184` · C-08 | 일부 | 배포 smoke |
| D-14 | 운영 관측 (log transport · alert threshold · metric) | common/runtime | — | B / C | Ops `:782-784` · `aws-environment.md:169` | 일부 | 예 |
| D-15 | Public endpoint · domain · TLS | common/runtime | web · PM | D | Ops §2-2 · `aws-environment.md:60` | 그때 | 아니오 |
| D-16 | Capacity / scaling (concurrency · EC2 · disk · RDS · Queue · GPU) | common/runtime | recording · search | C | Ops `:785-792` · P2 Planned | §4 단계 | 예 (P2/P3) |
| D-17 | 선정 모델 운영 한도 입력 (timeout · RPM/TPM · payload · 과금 · Key 삭제) | search + common/runtime | PM (운영진 문의) | B → C | `mlapi.md:200-215` · Search config 내부 값 | 운영진 문의 | 모델 smoke |

### Decision Register에 올리지 말 것 (이미 닫힘)

| 항목 | 닫힌 근거 |
| --- | --- |
| 통화 정규화 규칙 (KRW 저장 전 정규화) | `budget-krw-normalization.md` (2026-09-09, #19) — 구현은 C-05 |
| provider 의미·config validation = Search / 주입·원장 = Runtime, Search rate 주입 유지, `pricing_id` 추가, `ELICE_ML_API_KEY` rename | #153 2026-09-26 합의 — 구현은 C-04, C-06 |
| 사용자 재실행 = 새 `job_id`, 자동 infra retry = same `job_id` + new `execution_id` + attempt 증가 | Contract · ADR D7 · PR #46 |
| 같은 kind 대표 job 규칙 | Contract A§10-7 · ADR D3 |
| OIDC + SSM 배포 인증·접속 방식 | Ops §2-1 — 구현은 C-08 |
| timeout 소유 = case, 잠정 수치 | cross-cutting A-1 · `timeout-fallback.md` — 확정은 재측정 대기 |
| FastAPI 1 + Worker 1 + MySQL 8.4 DB Queue | Architecture A3 · §10-1 |
| STALE = Worker 소멸 실행 상태, old `case_rev` SUCCEEDED는 SUCCEEDED 유지·case가 미반영 | JobExecution Contract §6 · §9-8 — B-01 문구는 §11에서 정합화 |

### 별도 Issue 후보 (workflow §0: 구현을 잘못 유도할 수 있는 정합성 문제)

> **후속(2026-10-02):** 아래 세 항목은 Issue를 만들지 않았다. B-01 · B-03(+A-04 · A-11)은 Final Contract / Accepted Decision 기준 문서 정합화로 처리했고, B-02는 결정하지 않은 채 §2 Decision Register 입력으로 넘긴다(§11).

- **B-01:** `worker/README.md:6` · Architecture §8-2의 「case_rev 불일치 → STALE」
- **B-02:** Tech §6.3 retry 생성 시점 vs CaseView A§10-6
- **B-03 + A-04 + A-11:** pricing·통화·#153 문구 정합 (Contract `usage-record` §5·§10, Runtime 4개 문서)

나머지 STALE DOC (A-01~A-03, A-05~A-10, A-12)은 문서 위생 묶음 대상.

---

## 11. 검수 후 처리 기록 (2026-10-02)

> 이 절만 검수 이후에 추가했다. §1~§10의 판단은 바꾸지 않았다. 처리 근거는 Audited SHA와 같은 `origin/develop` `9c204ee`에서 다시 확인했다. 처리 PR은 branch `docs/runtime-consistency-review-261002`다.

| Finding | 처리 | 근거 / 위치 |
| --- | --- | --- |
| A-01 | 수정 | Runtime README · Tech Spec §17 · Ops Spec §3의 구현 현황을 2026-10-02 기준으로 갱신. 미구현 목록은 유지·보강 |
| A-02 | 수정 | Ops Spec §5 — Python 3.12 정렬 완료로 표기(`10cfca4`). type checker는 미구현으로 남김 |
| A-03 | 수정 | Ops Spec §19 — `python-tests.yml` · `boundary-check.yml` 실제 step과 gate별 현재 상태. Ruff · type checker · secret scan · MySQL integration · deployment는 없음으로 유지 |
| A-04 | 수정 | Runtime README · Tech Spec §11.3 · §15.1 · §18 · P2 plan · experiments README · workflow §3.1 — #153 「대기」 표현을 2026-09-26 합의로 교체. 남은 미결(artifact 위치·schema · FX source · 정산 기준)은 분리 유지 |
| A-05 | 수정 | Architecture §4-모듈5 ④ · §5-13 · §6-2 · 개정 이력, `contract-job-execution.md` §5 `enum(6)`, `contract-job-record-case-view.md` A절 포인터, `ownership.md` recording ⑤ |
| A-06 | 수정 | Architecture §10-2 Search baseline을 #95 Elice 전환 이후 상태로 |
| A-07 | 수정(사실 주석) | Ops Spec §11 — 현재 AnalysisSource bytes가 process memory에 있다는 구현 사실만 추가. 저장 위치·수명은 미결 유지(D-11) |
| A-08 | 수정(포인터) | Tech Spec §7.4 — case timeout 정책 문서로의 입력 포인터만 추가. 값 복제·관계 결정 없음(D-04) |
| A-09 | 수정 | Ops Spec §12-1 · P2 plan §1 — 모델·경로 범위(`gemini-3.8-flash` · `/v1/chat/completions` · base64 inline) 명시 |
| A-10 | 보류 | 공지 원문을 확보하지 못해 Official Inputs 사본을 만들 수 없다. 원문 확보 후 처리 |
| A-11 | 수정 | `contract-usage-record.md` §10 통화 항목을 `budget-krw-normalization.md`(2026-09-09) 기준 종결로 표기. Tech Spec §11.3에 반영 |
| A-12 | 범위 밖 | Web README. Runtime §0 목적과 직접 관계없어 이번에 고치지 않음 |
| B-01 | Contract 기준 정합화 | Architecture §8-2 · `src/daesingo/worker/README.md`. 새 정책 없음. `contract-job-execution.md` · Tech Spec §7.1은 이미 일치 |
| B-02 | 미결정 유지 → §2 | Tech Spec §6.3에 Open Decision 표지만 추가하고 §18 · Runtime README 목록에 등재. 답은 적지 않음 |
| B-03 | #153 / KRW 결정 반영 | `contract-usage-record.md` §5 가격표 소유 문구 · §10 가격표 항목을 「위치 미정 · 현재 Search rate 주입」으로 표기 정합(버전 유지). `mlapi.md` §7.2 연결 문구 갱신 |
| C-01~C-10 | 변경 없음 | 구현 · Issue 생성 없음. Runtime Implementation Plan 단계 대상 |
| D-01~D-17 | 답 없음 | 아래 보정 외에는 §10 표 그대로 §2 입력 |

### Decision Register 후보 보정

- **제외 (이미 닫힘):** KRW 정규화 규칙 자체 · Search rate 주입 유지 · 공용 pricing catalog 미도입 · `pricing_id` 추가 · `ELICE_ML_API_KEY` rename과 alias 위치 · STALE 의미. §10 「올리지 말 것」 표와 같다.
- **유지:** D-02(B-02 retry attempt 생성 시점 · `queued_at` 의미)를 포함해 D-01~D-17 전부. D-07은 정책이 아니라 artifact 위치 · FX source · `unit` · 정산 기준으로만 남는다.
