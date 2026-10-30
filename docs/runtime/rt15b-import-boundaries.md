# RT-15(b) Runtime import boundaries

Status: IN_PROGRESS · Refs #301 · Related #287 · PR / merge SHA pending.

## Implementation plan

Goal: 기존 Architecture의 두 import 방향을 기존 CLI에서 검사한다.
Spec: [Implementation Plan RT-15 · §12](./runtime-implementation-plan.md),
[ownership §6](../management/ownership.md#6-소유권-충돌-방지--이건-내-것이-아니다-목록),
[Architecture §1 · 원칙 6 · §6](../architecture/module-architecture.md),
[Runtime Tech Spec §12 · §16](./runtime-tech-spec.md).

- [x] 시작 상태·SoT·기존 checker/workflow/테스트 조사.
- [x] 실제 CLI negative control을 먼저 실행해 기존 검출 누락 RED 보존.
- [x] 기존 문자열/Contract 검사를 보존하고 Python AST 검사만 확장.
- [x] 허용/금지/상대 import/기존 규칙 회귀, Contract fixture, RT-15(a) quality 검증.
- [x] 구현 이력을 받지 않은 fresh read-only reviewer의 코드 검토.
- [x] 같은 reviewer의 최종 문서 delta 재확인.
- [x] ownership §6·루트 README·Notes·Log·Owner 통지 초안, 소유 임시 자원 정리.

현재 checkout에서 직접 실행한다. 새 worktree/checkout/staging/commit/push/PR/외부
댓글·메시지/merge를 하지 않는다. 전체 pytest/MySQL/Docker build는 반복하지 않고
최종 regression/mysql/test는 향후 push 뒤 원격 CI 조건으로 남긴다. inventory,
strict/timeout/skip/xfail, 운영진 workflow/CODEOWNERS, RT14_EXECUTION_ENABLED,
provider/AWS/배포, Contract/public surface/domain 구현은 변경하지 않는다.

설계 선택: 문자열 grep 확장만으로는 주석·문자열 오탐과 alias/상대 import 누락이
생긴다. 외부 import 분석 도구 도입은 의존성·설정 범위가 늘어난다. 기존 checker의
`check_boundaries()`에 표준 라이브러리 AST 순회를 더하는 최소 확장을 선택한다.
기존 검사는 그대로 두며 새로운 전역 lint/type 정책이나 허용 예외를 추가하지 않는다.

Pre-flight: checker가 CLI 진입점이고 테스트는 그 파일을 작은 임시 root로 복사하여
실제 exit code/진단을 관찰한다. 기존 boundary workflow는 이 진입점을 이미 실행하고,
새 pytest는 기존 regression partition으로 수집된다. workflow 변경은 필요하지 않다.

## 시작 근거

- 2026-10-30 branch `codex/rt15b-import-boundaries`, HEAD
  `e3fec617dc75b2cf21141a110bd8e81e816970b8`; tree/index clean.
- 로컬 `origin/develop`과 `git ls-remote origin refs/heads/develop` 모두 같은 SHA,
  `git rev-list --left-right --count HEAD...origin/develop` = `0 0`.
  sandbox의 최초 ls-remote는 DNS 오류였으며 외부 read 재실행으로 확인했다.
- [PR #483](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/483):
  GitHub 직접 조회에서 merged=true, merge SHA가 현재 HEAD와 같다. RT-15(a)의
  quality extra/runner/job이 checkout에 있다. 과거 PR CI 결과는 이번 diff 검증이 아니다.
- [Issue #301](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/301):
  본문과 전체 댓글 직접 조회, 댓글 0개. import 표와 checker 동시 갱신·Owner 통지를
  요구하며 Decision gate는 없다. RT-15 전체는 IN_PROGRESS다.
- 파일 시스템의 루트/상위 및 적용 경로에서 AGENTS.md 파일을 찾지 못했다.
  사용자가 제공한 AGENTS.md 지침과 `CLAUDE.md`, `docs/README.md`를 적용했다.
  넓은 탐색에서 기존 `.pytest_cache` 접근 거부가 있었으며 그 cache는 검사 대상이 아니다.
- 변경 전 boundary 0 위반, Contract 구조 62 / JSON 26 / 의미 fixture 104 PASS.

## Implementation Notes

### 구현 결과

- `scripts/check_boundaries.py`: 기존 `check_boundaries()` 끝에서 두 방향 AST 검사를
  실행한다. 기본 전체/`--only=boundaries`가 같은 검사를 쓰며 `--only=contracts`는
  기존 Contract 검사만 실행한다. 새 dependency/CLI 옵션/workflow 변경은 없다.
- domain 7개의 실제 경로와 namespace는 ownership §6 표와 `DOMAIN_IMPORTS`를
  함께 정합화했다. `eval`은 root package다. `web`은 TypeScript 프로젝트이며
  `apps.web`은 그 경로를 Python namespace로 참조할 경우의 경계다. 없는
  `src/daesingo/eval`·`src/daesingo/web` 경로를 대신 검사하지 않는다.
- common 6개 기반 경로와 domain 7개 경로 아래 `.py`만 새 AST 대상으로 한다.
  현재 직접 집계: common 35파일(jobs16/usage7/db5/config1/logging2/storage4),
  domain 143파일(case23/recording29/search41/readout8/evidence13/eval29/web0).
  TypeScript import 해석기를 추가하지 않았다. web 기존 문자열 검사는 유지한다.
- 새 AST는 주석·문자열을 무시하고 정확한 namespace 또는 `namespace.`로 비교한다.
  `import api`, `daesingo.api_client`, `daesingo.readout.api`는 `daesingo.api`와 다르다.
  `from daesingo import worker as harmless`는 원래 `daesingo.worker`로 검사한다.
  여러 alias·하위 모듈·star의 명시 base·함수/try/TYPE_CHECKING 내부도 검사한다.
- 파일 containing package를 기준으로 상대 level을 계산한다. `__init__.py`도
  디렉터리 자체가 package이며, 파일 이름을 package에 더하지 않는다. 파싱/디코딩/읽기
  실패와 package root를 벗어난 상대 import는 진단을 남기고 실패한다.
- 검사 전후 현재 코드 위반 0건. domain 코드 이동/의존성 은닉/공개 surface 변경 없음.
  기존 문자열 목록·code 확장자·walk 제외 경로·Contract CHECKS는 보존했다.

### Plan 대비 변경 · 새 implementation detail

Plan의 두 방향과 검사 범위를 따른다. Python `ast.Import`/`ast.ImportFrom`를 읽고
alias의 바인딩 이름 대신 원래 모듈 경로로 비교한다. 상대 import는 파일의 containing
package와 level을 사용한다. import 대상 모듈을 실행하지 않는다.

해석 근거: Python 3.12 공식 [import system](https://docs.python.org/3.12/reference/import.html),
[AST Import/ImportFrom/alias](https://docs.python.org/3.12/library/ast.html),
표준 라이브러리 `importlib.util.resolve_name`(모듈을 로드하지 않는 상대 이름 계산).
2026-10-30 공식 문서를 직접 확인했고, 실제 CLI fixture로 해석 결과를 검증했다.

### Contract / Decision / Baseline 영향

Contract 변경: 없음. Decision 변경: 없음. Baseline 변경: 없음.
다른 Owner의 public surface·책임 변경: 없음. 기존 Architecture 검사의 추가다.

### Owner 확인 포인트

각 domain의 경로·Python namespace와 상대 import 해석, 정적 분석 한계를 확인한다.
Owner 통지는 아래 초안만 작성하며 게시하지 않는다. (c) secret scan과 RT-15 전체
완료·Owner acceptance는 이 변경으로 닫지 않는다.

### Verification

아래는 이번 작성자의 직접 실행이다. `.venv/Scripts/python.exe`의 Python 3.12.14,
pytest 8.4.2, mypy 2.4.1을 사용했다. 기존 환경을 재사용했고 새 venv/archive를 만들지
않았다. pytest에는 `-p no:cacheprovider`와 전용 basetemp를 사용했다.

| 실행 | 결과 / 의미 |
| --- | --- |
| 변경 전 `pytest tests/test_import_boundaries.py -q --tb=no` | **236 failed / 22 passed**, 43.15초. 금지 import 235개와 파싱 실패 1개를 기존 CLI가 놓쳤다. 15개 허용 fixture와 7개 기존 금지 문자열의 거부 검증은 PASS |
| 변경 전 상대 import 단일 fixture `-k 'relative_import and common/jobs' --tb=short` | **1 failed / 257 deselected**. CLI의 exit 0/PASS를 직접 관찰하고 보존. import 누락 때문에 실패하며 fixture 문법 오류 때문이 아님 |
| AST 확장 후 같은 258 fixture | **258 passed**, 48.72초. 금지 fixture는 CLI exit 1, 허용 fixture는 exit 0을 검증 |
| `python scripts/check_boundaries.py` 및 `--only=contracts` | 각각 PASS, 현재 저장소 위반 0건 |
| `python scripts/check_contract_fixtures.py` | 구조 **62** / JSON **26** / 의미 fixture **104** 검사 PASS |
| `python scripts/check_runtime_quality.py` | Runtime Ruff PASS; mypy Linux/win32 각각 **87 source files**, 오류 0 |
| `pytest tests/test_runtime_quality.py tests/test_ci_orchestration.py -q` | **55 passed**, 13.25초. 기존 quality negative controls와 required gate 회귀 |
| 추가 `ruff check --no-cache scripts/check_boundaries.py tests/test_import_boundaries.py` | **기존 Contract 코드 E741 1건**. HEAD 원본을 stdin으로 독립 검사해 같은 `l` 변수 진단 재현. 이번 추가부의 진단이 아니며 Runtime quality gate 대상 밖. 범위 밖 lint 정리는 하지 않음 |
| 추가 새 테스트 파일 단독 Ruff | PASS |

전체 pytest·MySQL·Docker build와 이 미커밋 diff의 원격 CI는 실행하지 않았다.
최종 조건은 향후 push 뒤 `boundary-check`와 `python-tests`의
quality/regression/mysql 및 required test 성공이다. 기존 inventory/strict/timeout/
skip/xfail gate는 변경하지 않는다. workflow 파일을 수정하지 않아 actionlint 재실행은
필요하지 않았다. PR #483의 CI는 선행 상태의 보존된 결과이며 이 diff의 결과가 아니다.

초기/최종 raw 요약은 ignored `.codex-scratch/rt15b/`에만 두고 PR 파일에서 제외한다.
중간 pytest root는 최종 정리한다. RED와 GREEN은 다른 실행이며 합산하지 않는다.

### Fresh read-only review

구현 이력을 상속하지 않는 reviewer에게 SoT와 현재 미커밋 diff를 전달했다.
reviewer는 소스·테스트·문서를 수정하지 않는 read-only 조건으로 검토했다.

| 구분 | reviewer 보고 |
| --- | --- |
| 직접 실행 | 현재 boundary CLI PASS, fixture **258 passed / 48.42초**, `git diff --check` PASS |
| 독립 adversarial 실행 | 12사례 기대 결과 12/12 일치: 금지6 거부, 허용/자체 모듈/비슷한 prefix4 통과, 문서에 명시한 동적·alias 한계2 통과 |
| 증거 열람 | SoT·기존 HEAD checker·미커밋 diff·현재 workflow 검토. 작성자 RED 및 quality 실행은 reviewer의 직접 재실행으로 주장하지 않음 |
| 실행 환경 오류 | reviewer 최초 pytest는 선택한 basetemp 부모 부재(WinError3)로 setup258ERROR. 부모 생성 후 새 basetemp 실행으로 위 PASS 확인. 제품 결함/작성자 RED와 구분 |
| 현재 결론 | actionable finding 없음. 소유 임시 probe/pytest 자원 정리 보고 |

같은 reviewer의 최종 문서 delta도 actionable finding 없음으로 확인됐다. 이번 delta는
문서/보존 로그 열람, 파일 수 common35/domain143/web0 직접 재집계,
`git diff --check` 새 실행 PASS다. 변경 없는 테스트 suite는 반복하지 않았으며 위
258PASS/독립12사례는 reviewer의 이전 직접 실행 증거로 구분했다.

## 변경 파일 · 종료 상태

| 파일 | 변경 |
| --- | --- |
| `scripts/check_boundaries.py` | 두 방향 AST 검사, 기존 CLI/규칙 보존 |
| `tests/test_import_boundaries.py` | 실제 CLI 검출·허용·상대 import·기존 문자열·파싱 회귀258개 |
| `docs/management/ownership.md` | §6 검사 표/namespace/한계·현행 실행 정합화, 초기 수동 점검 기록 보존 |
| `README.md` | 검사 범위 포인터와 focused 명령만 추가 |
| `docs/runtime/rt15b-import-boundaries.md` | 계획·Implementation Notes·검증·review·미발송 통지 초안 |
| `docs/runtime/runtime-implementation-log.md` | RT-15(b)·implementation detail 기록, 선행 #483 merge SHA 색인 반영; 기존 이력 보존 |

RT-15(b) 로컬 구현·focused 검증을 마쳤고 PR/merge/원격 CI는 pending이다.
RT-15 전체는 IN_PROGRESS이며 (c) secret scan을 후속으로 남긴다.
최종 branch/HEAD는 시작 상태와 동일하며 index는 비어 있다. 위 6개 파일만
미커밋·미스테이징 상태다. 전용 scratch 안의 pytest-red/pytest-red-detail/
pytest-green/pytest-quality-ci 임시 디렉터리는 절대 경로가 task root 안인지 검증한
뒤 제거했다. 기존 다른 scratch/venv/cache는 보존했다. 작은 RED/GREEN/quality 로그만
ignored scratch에 남기며 PR 대상이 아니다. staging/commit/push/PR/외부 댓글/merge는
수행하지 않았다. workflow/CODEOWNERS/제품 코드/DB/migration/RT14 실행 변수 변경 없음.
최종 boundary-only와 `git diff --check` PASS, staged diff 없음도 직접 확인했다.

### 남은 한계

정적 Python import문 검사이며 동적 import, 임의 alias 속성 접근, 다른 모듈을 통한
간접 re-export, 런타임 import hook/sys.path 변경은 전이 분석하지 않는다.
`from daesingo import *`의 노출 이름은 추론하지 않는다. 금지 namespace에서의
`from daesingo.worker import *`는 명시 base로 검출한다.
JavaScript/TypeScript의 모듈 해석을 Python AST로 보장하지 않는다.
기존 문자열 검사는 주석/문자열도 검사하는 기존 의미를 그대로 유지한다.

## Domain Owner 통지 초안 — 미발송

공통 전달 내용: “RT-15(b), Refs #301 / Related #287입니다. 기존 Architecture를
기계화하여 common 6개 기반 경로 → domain import와 domain → daesingo.api/worker
import를 검사합니다. 허용 예외·Contract/public surface 변경은 없습니다.
로컬 실행은 `python scripts/check_boundaries.py --only=boundaries`입니다.
경로/namespace 표와 한계는 ownership §6, 직접 검증·review 근거는 본 Notes에 있습니다.
현재 미커밋 상태이며 원격 CI·deferred acceptance 전입니다.”

| domain | 수신 Owner | domain별 덧붙일 초안 |
| --- | --- | --- |
| case | 유소연 @yuusoyeon | `src/daesingo/case`의 api/worker 역참조를 검사합니다. common의 `daesingo.case` import도 금지 검사하며 JobIntent/CaseView 의미는 변경하지 않았습니다. |
| recording | 정철원 @cheol1203 | `src/daesingo/recording`의 api/worker 역참조와 common의 `daesingo.recording` import를 검사합니다. 파일·capability·migration은 변경하지 않았습니다. |
| search | 서어진 @kong2488-star | `src/daesingo/search`의 api/worker 역참조와 common의 `daesingo.search` import를 검사합니다. provider/config/public annotation 변경은 없습니다. |
| readout | 신유민 @uminshin | `src/daesingo/readout`의 api/worker 역참조와 common의 `daesingo.readout` import를 검사합니다. 자체 `.api` 상대 import와 `daesingo.readout.api`는 Runtime api와 구분합니다. |
| evidence | 김준영 @flosure23 | `src/daesingo/evidence`의 api/worker 역참조와 common의 `daesingo.evidence` import를 검사합니다. 기존 ffmpeg/프롬프트/search/readout 문자열 금지를 유지합니다. Runtime/Ops deferred review도 부탁드립니다. |
| eval | 김대원 @kim1034 | 실제 root `eval/`의 api/worker 역참조와 common의 `eval` import를 검사합니다. 기존 case/evidence 문자열 금지를 유지하고 eval runner/scorer 책임은 변경하지 않았습니다. |
| web | 신유민 @uminshin | 실제 `apps/web/` 경로를 표에 포함했습니다. 현재 Python 파일은 0개이고 TypeScript import 해석은 새 AST의 보장 범위 밖입니다. 기존 web 문자열 검사를 유지하며 HTTP/public surface 변경은 없습니다. |

외부 댓글 게시·메시지 발송·Owner acceptance를 수행한 것으로 표시하지 않는다.
