# RT-15(c) — pre-deploy secret scan

**IN_PROGRESS · Refs #301 · Related #287 · 미커밋/미스테이징 · 원격 CI pending**

## Implementation Notes

### 구현 결과

`scripts/check_secrets.py`는 설치와 검사를 분리한다. 설치만 공식 GitHub 릴리스에
접속하고 검사 중 provider 검증·AWS 호출·credential 유효성 확인은 하지 않는다.
현재 파일과 전체 HEAD 이력을 별도로 검사하며, 탐지 결과는 rule ID·건수만 공유한다.
경로·line·commit·author·match·주변 코드·URL을 보고서에 넣지 않는다.

| 파일 | 역할 |
| --- | --- |
| `scripts/check_secrets.py` | 고정 설치·무결성 재확인·대상 열거·scanner 출력 차단·실패 전파 |
| `scripts/secret_scan_exceptions.json` | A01/A02의 rule·위치 지문·도구 좌표·값/패턴 지문, 원문 없는 고정 예외 2개 |
| `scripts/secret_scan_controls.py` | 실제 고정 바이너리와 합성 저장소를 사용하는 필수 검증, Python 표준 라이브러리만 사용 |
| `tests/test_secret_scan.py` | 기존 offline regression 안의 무결성·오류·보고서 검증 단위 테스트 |
| `.github/workflows/secret-scan.yml` | develop 수동 실행/재사용 검사, 별도 권한·job |
| `.github/workflows/rt14-deploy.yml` | publish/remote의 secret-scan dependency |
| `README.md` | 로컬 공통 명령·CI 배치 포인터 |
| `docs/runtime/rt15c-secret-scan.md` | 설계·측정·한계·검증·리뷰, 이 문서 |
| `docs/runtime/runtime-implementation-log.md` | append-only 구현 이력과 최신 색인 |
| `docs/superpowers/plans/2026-10-30-rt15c-secret-scan.md` | 실행 계획·판단 기록 |

### Plan 대비 변경

Plan RT-15와 §12.3이 위임한 도구·배치 선택이다. 일반 PR gate는 보류하고 배포 전
필수 검사로 연결한다. Runtime 네 경로의 lint/type와 달리 secret 검사는 저장소의
Git 관리 파일·HEAD 이력을 대상으로 한다. credential은 문서/노트북에도 들어갈 수
있다는 기존 `.gitignore` 지침이 근거다. 다른 모듈의 제품 코드·공개 surface는 바꾸지 않는다.

### 새로 고정된 implementation detail

#### 도구 비교와 선택

2026-10-30 공식 자료를 확인했다. 성능 우열이나 탐지율을 비교 측정한 선택은 아니다.

| 후보 | 확인한 특성 | 이번 선택 |
| --- | --- | --- |
| [Gitleaks 8.30.1](https://github.com/gitleaks/gitleaks/tree/v8.30.1) | Git/파일 패턴 검사, 고정 릴리스, custom report template | 선택. provider 검증 없이 같은 바이너리/규칙으로 로컬·CI 실행 |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog/blob/main/README.md) | Git 검사와 credential verification 제공, verification 제어 옵션 | 이번에는 provider 검증이 금지돼 이 장점을 쓰지 않는다 |
| [detect-secrets](https://github.com/Yelp/detect-secrets) | baseline/audit와 pre-commit 중심 흐름 | 실제 기존 secret을 baseline 예외로 숨기지 않는 독립 이력 검사가 이번 요구에 더 직접적 |

공식 [release metadata](https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v8.30.1)의
asset SHA-256을 확인하고 다운로드 archive를 대조한 뒤 실행 파일을 추출해 다시 고정했다.
자동 최신 업데이트는 없다. SHA 고정은 review된 바이트 재현/변조 검출이며 서명 검증이나
공급자 침해 부재를 증명하지 않는다. 버전 갱신에는 공식 digest 확인과 합성 controls 재실행이 필요하다.

| 대상 | SHA-256 |
| --- | --- |
| Windows x64 zip | `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e` |
| Windows 실행 파일 | `17157e2ee8b76fc8b1d8bee607a250e34b8a8023c8bc81822d4b5ee4d78fcb7c` |
| Linux x64 tar.gz | `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` |
| Linux 실행 파일 | `88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509` |
| [upstream rules](https://raw.githubusercontent.com/gitleaks/gitleaks/v8.30.1/config/gitleaks.toml) | `e163e53b9e7e8a8511e77271e2b323ed057759542a6d988258afe3a1fa329caf` |

Archive는 메모리에서 검증하고 정확한 실행 파일 하나만 읽어 설치한다. 임의 경로를
archive에서 풀거나 upstream installer script를 실행하지 않는다. scan 때 실행 파일과
규칙 digest를 재검사한다. 지원은 Python >=3.12, Git, Linux/Windows x64다.

#### 로컬/CI 공통 명령

```powershell
python scripts/check_secrets.py install --tool-dir .codex-scratch/rt15c/tool
python scripts/secret_scan_controls.py --tool-dir .codex-scratch/rt15c/tool
python scripts/check_secrets.py scan --repo . --tool-dir .codex-scratch/rt15c/tool
```

CI는 같은 명령에 tool-dir만 `$RUNNER_TEMP/rt15c-tool`로 지정한다. app dependency/venv/uv
설치 없이 실행한다. 일반 regression은 실제 바이너리를 필요로 하지 않는 단위 테스트만
추가 수집한다. `--scope snapshot`/`history`는 로컬 진단용이고 CI는 기본 `both`를 사용한다.

| exit | 의미 |
| --- | --- |
| 0 | 요청한 범위 검사가 실행됐고 탐지 없음 |
| 1 | 탐지 있음. 사용/배포 전 분류 필요 |
| 2 | 설치·무결성·Git 조회·불완전 이력·읽기·지원 파일·scanner·보고서 등의 실행 실패 |

Scanner 내부 findings exit42를 wrapper exit1로 변환한다. timeout/실행 오류·error diagnostic·
알 수 없는 rule·누락/형식 오류 보고서·exit/report 불일치는 exit2다. child 출력과 예외 원문은
전달하지 않는다. `continue-on-error`, baseline, 원본 artifact 업로드가 없다.

#### 검사 대상과 비용

| 범위 | 실제 대상 | 제외/한계 |
| --- | --- | --- |
| snapshot | `git ls-files --cached --others --exclude-standard -z`의 현재 regular file | untracked ignored 파일은 제외. tracked 파일은 ignore 여부와 무관하게 포함. 누락/비정규 파일·symlink·외부 경로/submodule은 실패 |
| history | HEAD에서 도달 가능한 전체 commit, root와 merge 부모 포함 | unrelated ref·reflog·dangling object·도달 불가 삭제 branch·LFS 외부 객체는 검사 보장 밖 |
| PR diff | 전용 incremental 모드 없음 | 배포 전 전체 검사에 포함되는 변경은 검사. 미병합 fork branch를 이번 workflow가 검사했다고 주장하지 않음 |

snapshot은 source와 같은 파일시스템에 임시 hardlink view를 만든다. source 내용 사본은
없고 scanner는 링크를 읽기만 한다. source 링크에 write/chmod를 하지 않는다. 이름/경로는
출력하지 않는다. 링크 생성·읽기·정리에 실패하면 검사를 성공으로 처리하지 않는다.
파일 목록은 임시 디렉터리 생성 전에 확정한다. 동시에 파일을 편집하지 않는 안정된
checkout에서 실행한다. CI는 고정 checkout, 로컬은 현재 미커밋 파일도 포함한다.

scratch/venv/cache/모델/미디어용 새 광범위 scanner allowlist는 없다. 기존 `.gitignore`의
`/.codex-scratch/`, `.venv/`, `__pycache__/`, `eval/datasets/*`, search video 경로 등은
**untracked 로컬 자원**의 대상 경계를 정한다. tracked로 들어오면 이 경계로 숨기지 않는다.
`.dockerignore`는 image build context이며 secret 검사 제외 설정으로 사용하지 않는다.

공식 규칙의 **global path exemptions는 모두 제거**한다(미디어 확장자·lock 파일·
gitleaks.toml 포함). detector 고유 regex/stopword allowlist와 entropy 기준은 남는다.
초기 구현에는 로컬 추가 allowlist·baseline·inline suppression이 없었다. 후속으로 아래 A01/A02의 정확한 지문 예외만 추가했고 baseline·inline suppression은 여전히 없다. 명시적 verified config,
빈 ignore 디렉터리, `--ignore-gitleaks-allow`, 환경변수 정리로 저장소 config/ignore와
상속 환경이 검사를 끄지 못하게 한다.

실제 binary/media·archive 내부·모델 내용은 scanner 지원 한계가 있다. archive depth0,
decode depth5다. ZIP 내부·압축/암호화·임의 encoding/난독화의 전수 탐지를 보장하지 않는다.
AWS/GitHub/provider key·private key·generic credential 등 고정 rule에 맞는 패턴을 검사한다.
공개 금지인 내부 식별정보·개인정보·임의 비밀번호/URL을 모두 찾거나 credential이 살아
있는지 판정하는 도구가 아니다. 별도 pre-deploy security review를 대체하지 않는다.

#### Git fetch / PR 보안

Scanner는 fetch하지 않는다. shallow는 history 검사 전에 거부하고 partial/promisor clone도
거부한다. replacement ref를 끄고 graft 이력도 거부한다. Git -diff 속성으로 텍스트를 숨기지
못하도록 --text/--no-renames를 사용한다. --no-ext-diff/--no-textconv/--no-show-signature로
외부 diff/변환/서명검증 프로그램 실행을 비활성화한다. CI checkout은
`fetch-depth: 0`, `fetch-tags: false`, `persist-credentials: false`다.
checkout v4의 depth0은 전체 branch/tag 이력을 가져오는 방식이므로 PR 두 commit만
받는 비용이 아니다([공식 checkout 설명](https://github.com/actions/checkout/tree/v4.3.1)).
시작 시 로컬 HEAD ancestry는 1,519 commits, pack 약 39 MiB(`git count-objects`의 39,942 KiB)였다.
이는 로컬 pack 측정이며 GitHub runner의 전송량/실행 시간은 아직 측정하지 않았다.
기존 로컬 fetch는 `git fetch --no-tags origin develop` 1회, HEAD 대비 ahead/behind 0/0이었다.

workflow trigger는 workflow_dispatch/workflow_call뿐이다. GitHub context의 repository·ID·
develop ref·workflow_dispatch event를 checkout 전에 검사하고 불일치하면 실패한다.
`pull_request_target`·입력 ref·PR head checkout·외부 action 설치 script는 없다.
일반 PR merge ref나 fork PR는 이 workflow를 시작하지 않는다. 수동/재사용 호출에서
그 context가 들어오면 checkout 전에 거부한다. 따라서 비신뢰 PR 코드를 실행하지 않으며,
미병합 PR를 스캔 완료로 표시하지 않는다. 합성 merge-only/side-history controls로 HEAD
ancestry 선택을 검증한다. 향후 PR 편입 시 trusted runner/config와 base/head fetch 설계를
별도로 검토해야 하며 depth1 merge commit 검사를 재사용하면 안 된다.

secret scan job의 권한은 contents:read뿐이다. RT-14 publish/remote가 `needs: [secret-scan]`으로
의존한다. 실패/취소/skip이면 기본 dependency 의미로 배포 job은 진행하지 않는다.
기존 RT14 실행 변수 조건·권한·배포 도구는 보존한다. deploy/rollback 때 require_target=true와
vars.RT14_REVISION을 별도 비밀값 없는 workflow input으로 전달한다. wrapper의
`--require-ancestor`는 40자리 소문자 hex를 요구하고 Git merge-base로 **검사 HEAD**에 포함되는지
확인한다. 빈 값/잘못된 값/미포함 target은 실패한다. 기존 `deploy/aws.py`의 live develop
ancestry 검증도 유지하지만 그것만으로 검사 후 develop 전진 경합을 방어했다고 주장하지 않는다.
AWS 권한을 가진 기존 job과 scanner job은 별도 runner다. secrets를 scanner에 전달하지 않는다.

#### 비노출 설계

초기 구현은 `--redact=100`과 별개로 custom template에 고정 marker와 **RuleID만** 출력했다. 현재 지문 예외는 아래 후속 설계처럼 값이 메모리에 있을 때 비교하고 익명 예외 ID도 출력한다.
기본 JSON/SARIF/CSV 보고서를 생성하지 않는다. stdout/stderr는 subprocess capture로 받으며,
검증된 rules 집합의 ID만 세어 출력한다. 파일 경로 자체가 민감할 가능성이 있어 모든
경로를 기본 비공개로 처리한다. 원문·주변 코드·credential URL·경로를 담은 결과 파일은 없다.
기본 로그 레벨은 error이고 그런 diagnostic이 있으면 내용을 노출하지 않고 exit2다.
Traceback이나 예외 문자열도 출력하지 않는다. 임시 파일에는 verified rules/template만 있다.

합성 token·주변 sentinel·token을 포함한 파일명으로 wrapper 출력과 실제 child stdout/stderr,
template 보고서의 비노출을 검증한다. scanner 자체 오류 진단도 capture 후 정해진 오류
코드로만 전파한다. 이를 실제 credential 비노출 확인과 혼동하지 않는다.

#### 실제 측정과 일반 PR gate 판단

| 작성자 직접 실행 | 결과 | 시간 |
| --- | --- | --- |
| 시작 HEAD 전체 history | generic-api-key 24 occurrences, exit1 | 69.38초 |
| 구현 중 snapshot 2,314파일 | generic-api-key 2 occurrences, exit1 | 12.98초 |
| --text/--no-renames 보강 뒤 history | 같은 1,519 commits, generic-api-key 24 occurrences, exit1 | 76.41초 |
| 최종 snapshot 2,315파일 | generic-api-key 2 occurrences, exit1 | 8.47초 |

**초기 구현 당시 기록(후속 분류·예외 결과는 아래 참조):** 두 범위의 중복 가능성이 있으므로 고유 credential 수로 합산하지 않는다. 원문을 열람해
분류하지 않았으며 실제 credential/fixture 오탐 여부·오탐률은 **확인할 수 없다**.
확인된 실제 오탐에 대한 새 예외는 0건이다. 탐지를 승인된 baseline으로 숨기지 않는다.

**일반 PR gate 편입 보류.** 미분류 탐지가 남아 있고 cold checkout/download 비용도 미측정이다.
약 82초의 Windows scan 측정은 합계 추정이며 CI 성능 수치가 아니다. 현 배포 전 gate는
미분류 탐지로 실패한다. 보안 담당자/Runtime-Ops Owner와 해당 credential 소유자가 비공개로
종류·영향 범위를 분류해야 한다. 실제 credential이면 담당자가 폐기·회전 여부를 판단하고
과거 노출 영향도 확인해야 한다. 이 작업은 credential 사용·회전·이력 재작성·AWS 변경을 하지 않는다.
그 뒤 확인된 fixture만 rule/정확한 위치 단위로 사유를 남겨 별도 검토할 수 있다.

### Contract / Decision / Baseline 영향

- Contract 변경: 없음.
- Accepted Decision 변경: 없음.
- Baseline 의미 변경: 없음.
- 제품 동작·도메인 의무·Runtime queue/DB/회귀 의미 변경: 없음.

### Owner 확인 포인트

Runtime/Ops Owner 김준영의 deferred review: 미분류 탐지의 비공개 분류, 배포 전 fail-closed
의존성, 향후 PR gate 재검토. 일반 pre-deploy privacy/HTTPS/retention/provider 검수는 남는다.
운영진 workflow 3개와 CODEOWNERS는 변경하지 않는다. 외부 통지·Issue close는 수행하지 않았다.

### Verification

초기 test-first 실행은 script 부재로 검출/clean controls가 실패했다. shallow clone control의
file URL/setup 오류도 섞여 있었고 수정했다. 이를 scanner 결함 RED와 구분한다.
초기 hardlink Windows sandbox 차단은 exit2로 처리됐다. 테스트 전용 실행을 sandbox 밖에서
실행해 실제 hardlink 동작을 검증했다. per-file stdin 대안은 약 0.704초/호출 초기화 비용과
filename 기반 rule 손실 때문에 채택하지 않았다.

작성자 최종 focused·합성 controls·boundary·Contract·quality·actionlint 및 fresh reviewer 결과는
아래 최종 기록을 따른다. 전체 local pytest/MySQL/Docker build는 반복하지 않는다.
이번 미커밋 diff의 Linux CI와 실제 배포 성공은 확인하지 않았다.

### #301 수락 조건 대조

| 항목 | 근거 | 남은 것 |
| --- | --- | --- |
| (a) Runtime lint/type 0 error | PR #483 merged, 선행 원격 CI PASS 기록·이번 로컬 quality PASS | 새 원격 CI |
| (b) 위반 fixture 검출·boundary/Contract | PR #484 merged, 선행 원격 CI PASS 기록·이번 로컬 boundary/Contract PASS | 새 원격 CI·domain Owner 통지/acceptance 상태는 (b) Notes 참조 |
| (c) pre-deploy secret scan·PR 배치 판단 | 고정 runner·별도 CI·배포 선행 연결·실측·A01/A02 정확한 지문 예외·일반 PR 편입 보류 | push 후 실제 Linux CI 성공 |

**RT-15/#301 전체는 IN_PROGRESS다.** 구현·합성 controls의 성공은 현재 저장소 clean 판정이나
원격 CI 성공이 아니다. Issue를 닫거나 완료 체크를 올리지 않는다. 선행 merged PR의 원격
결과를 이번 미커밋 diff의 결과로 대체하지 않는다.

## 최종 검증·fresh review 기록

| 작성자 직접 검증 | 결과 |
| --- | --- |
| 단위 + Runtime quality/CI orchestration/deploy AWS 경계 회귀 | 94 PASS, 23.80초 (외부 경계는 대역, 실제 AWS 호출 아님) |
| 최종 실제 바이너리 합성 controls | 16 PASS, 59.792초 |
| 최종 wrapper 단위 | 12 PASS, 0.59초 |
| 기존 import boundary CLI fixture | 258 PASS, 88.58초 |
| boundary CLI / Contract fixture | PASS / 구조62·JSON26·의미104 PASS |
| Runtime quality | Ruff PASS, mypy Linux/win32 각각87파일 오류0 |
| 새 script/test Ruff | PASS |
| 변경 workflow actionlint1.7.12 | PASS, shellcheck/pyflakes 비활성화 (실제 Actions 실행 아님) |
| installer Windows/Linux extraction | 공식 다운로드를 이미 hash 대조한 archive를 응답 대역으로 공급, 실제 install/extract/reverify 경로 두 플랫폼 PASS. Linux 실행 자체/CI는 미검증 |
| diff / index | diff check PASS, index 비어 있음 |

처음 boundary 실행은 Windows cp949가 기존 성공 메시지의 em dash를 출력하지 못해 exit1이었다.
PYTHONIOENCODING=utf-8로 재실행해 PASS를 확인했다. 제품/boundary 코드 수정은 없다.

Fresh reviewer는 구현 이력을 상속하지 않고 read-only로 검토했다. 단위12 PASS(0.59초),
당시 합성14controls PASS(65.989초)를 **직접 실행**했다. 초기 기본 TEMP setup 오류는 workspace
basetemp 재실행으로 해소됐으며 scanner 결함과 구분한다. 추가 합성 Git config 변형도 직접
검사했다. 실제 저장소의 탐지 건수는 작성자 증거 검토이며 reviewer가 원문/저장소를 재검사한
결과가 아니다.

reviewer는 P2 한 건을 재현했다: local log.showSignature/gpg.program 설정과 서명 commit이
있으면 history 조회가 외부 verifier를 실행할 수 있었다. 작성자도 무해한 marker 프로그램으로
RED를 재현했다(wrapper exit0 + marker 생성). --no-show-signature로 차단하고 cross-platform
nonexecution control을 추가했다. 배포 target의 검사 HEAD ancestry 결박도 별도 합성 RED→GREEN
(1control, 8.138초)으로 확인했다. 작성자 최종16controls는 59.792초에 모두 PASS였다.
같은 reviewer는 두 delta controls를 별도 직접 실행해 2 PASS(7.345초)를 확인했다.
reviewer의 기존14와 추가2는 별도 실행이며, 한 번의 전체16 실행으로 합산하지 않는다.
같은 reviewer의 코드/workflow delta 검토에서 P2 해결·남은 기능/보안 지적 없음이었다.
완료 기록의 남은 로컬 검사 표기 불일치도 수정했다.

최종 snapshot은 2,315파일/2 occurrences/8.47초, exit1이다. 마지막 history 실측은
--text/--no-renames 적용 후이며 최종 --no-show-signature 추가 뒤 전체 이력을 반복하지는
않았다. 서명검증 비실행은 위 합성 control과 reviewer 직접 실행으로 검증했다.
기존 미분류 탐지를 clean으로 바꾸지 않는다.

README는 저장소 update-readme 지침에 따라 실행 사실 절에 명령/CI 포인터만 추가했다.
레포 구성·기술 스택은 변경하지 않았다. 전체 변경 파일은 후속 예외 설정을 포함한 위10개 manifest이며 scratch/RAW/
credential/원본 보고서는 포함하지 않는다. 소유 scratch/tool/archive/합성 저장소 정리 결과는
최종 Log에 남긴다. staging/commit/push/PR/외부 댓글/merge·AWS/provider/배포·실행 변수
변경 없이 미커밋/미스테이징 상태로 보고한다.

동일 reviewer의 최종 문서 delta에서도 추가 지적 없음(문서 열람만, 재시험 아님).
검증 후 소유 `.codex-scratch/rt15c` 전체(tool/archive/합성 저장소)와 실패한 sandbox TEMP
한 경로를 절대 경로 대조 후 삭제했다. 다른 작업의 scratch는 정리하지 않았다.
scanner 임시 view 잔존0을 확인했다. 향후 실행은 위 install 명령부터 다시 시작한다.

## 2026-10-31 — A01/A02 정확한 예외와 비노출 보강

이 절이 현재 상태다. 위의 미분류·예외0·exit1 기록은 당시 이력으로 보존한다.
현재 파일 2회·HEAD 이력 24회는 고유한 두 항목의 반복이었다. 분류와 실제 before/after
검사는 작성자 증거이며, reviewer의 독립 합성 검증과 구분한다.

| ID | rule | 현재 / 이력 | 확인 근거 | 허용 범위 |
| --- | --- | --- | --- | --- |
| A01 | generic-api-key | 1 / 11 | AST상 문자열 credential이 아닌 정상 계측식 | rule·상대 위치 지문·도구 좌표·검출값 지문·전체 match 지문 모두 일치 |
| A02 | generic-api-key | 1 / 13 | 명시적 합성 리터럴과 비노출 회귀 fixture 사용 확인 | 같은 결합 조건, 합성값 변경 시 불일치 |

이 26회 탐지에서 실제 발급 credential 의심·판단 불가 항목은 확인되지 않았다.
외부 API로 유효성을 시험하지 않았다. 이 분류가 비노출 절차 위반을 없던 일로 만들지는 않는다.

### 예외 구현과 제한

`scripts/secret_scan_exceptions.json`에는 원문·경로·주변 코드 대신 다음만 고정한다.

- A01/A02 ID와 사유 코드, generic-api-key rule.
- 정규화한 저장소 상대 위치의 SHA-256.
- Gitleaks가 보고한 start/end line·column의 정확한 값.
- 검출값과 전체 Match의 SHA-256. 줄바꿈만 LF로 정규화한다.

설정 schema는 정확히 두 ID·필드 집합·rule·사유·좌표·64자리 지문을 검증한다.
빈/손상/알 수 없는 예외 설정은 실패다. wildcard·파일 전체 제외·전체 rule 비활성화·
commit별 탐지 결과 일괄 baseline은 없다. 현재의 확인된 두 항목으로만 구성했으며,
과거 24회를 모아 승인한 baseline이 아니다. 지문은 원문 직접 노출 방지용 식별값이며
비밀 저장용 암호화가 아니다. 원문이나 실제 탐지 위치는 이 문서에 재현하지 않는다.

현재 파일 검사는 임시 view에서 `dir .`로 실행해 host/scratch 절대 위치에 의존하지 않는다.
경로 구분자와 선행 `./`만 정규화한다. Git 이력은 기존 전체 HEAD ancestry를 그대로 검사한다.
스캔 자체에서 경로나 finding을 제외하지 않고, 고정 template 내부에서 위 조건을 모두
비교해 일치할 때만 `allowed:A01`/`allowed:A02`로 투영한다. 그 외에는 원래 rule ID를 반환한다.

원래 값에 대한 지문 비교가 필요하므로 scanner 내부는 `--redact=0`이다. redaction된 값의
지문을 비교하면 새 값도 같은 것으로 허용될 수 있어 사용하지 않는다. 원래 값은 scanner
메모리 안에서만 비교하고, 원문뿐 아니라 지문도 child stdout으로 보내지 않는다.
고정 `RT15C_COUNTS_V2` 보고서에는 rule ID 또는 두 익명 예외 marker만 있다.
JSON/SARIF 원본 보고서 모드나 보고서 업로드는 없다. scanner stderr에는 오류 경로가
있을 수 있으므로 캡처 후 한 글자도 전달하지 않고 exit2로 처리한다.

Gitleaks의 raw exit42는 예외만 있을 때도 발생한다. wrapper는 보고서 전체를 검증하고
처리되지 않은 finding이 있으면 exit1, 정확한 예외만 있으면 exit0, 오류/불완전 보고서면
exit2다. header·rule·예외 ID·raw exit와 record 유무가 불일치하면 성공하지 않는다.
파일/좌표/값/패턴 중 하나라도 바뀌면 예외가 아니며 새 탐지를 거부한다.

### 비노출 사고: 조사 도구와 제품 실행기 구분

사고 경로는 **임시 조사 helper의 원본 finding·문맥 객체 → 성공 JSON 직렬화 →
진단 프로세스 stdout → 도구 출력**이었다. 제품 counts-only 실행기가 이 원본을 출력한
사고는 아니다. 조사 성공 경로에 원본 직렬화가 남아 있었고, 실행 후 파일을 수정한 것을
진행 중인 프로세스에도 적용됐다고 간주한 채 출력을 읽었다. 오류 경로 차단만 확인하고
성공 경로의 출력 schema를 실행 전에 검증하지 않은 것이 원인이었다.

원문·주변 코드·경로가 실제로 도구 출력에 포함된 절차 위반이다. 탐지 항목이 정상 코드와
합성 fixture였다는 판단과 별개로 기록한다. 이미 발생한 출력을 제거했다고 주장하지 않는다.
원문을 재인용하거나 credential 폐기/회전·이력 재작성으로 처리하지 않았다.

차단·회귀 보강:

- 임시 원본 보고서/문맥 dump helper는 폐기한다. 예외 준비에는 원문 필드를 처음부터
  출력하지 않는 hash-only projection과 고정 단계/건수 진단만 사용했다. 원본 보고서
  파일·RAW 자료·해당 helper는 PR 대상이 아니다.
- 제품 CLI의 argparse 오류와 ScanError도 고정된 공개 오류 코드만 출력한다.
  예상치 못한 인자·exception 문자열·잘못된 report·child stdout/stderr를 재전달하지 않는다.
- controls는 테스트 내부의 stdout/stderr를 버퍼링하고 traceback·예외 문구·출력 버퍼를
  실패 보고서에 싣지 않는다. 실행 전 경로 해석·framework 초기화·성공 summary까지
  바깥 캡처 경계로 감싸고, 숫자 요약과 고정 오류 코드만 출력한다.
- 숫자가 아닌 성공 payload는 거부한다. module을 명시해 suite를 선택하고,
  빈 suite·skip·expected-failure·Python 최적화에 따른 assert 생략은 성공으로 처리하지 않는다.

추가 잠재 오류 출력 경로를 합성으로 발견해 보강한 것이며, 당시 원본 누출 사고의 원인을
제품 실행기로 바꿔 기록하지 않는다. 성공·오류·stderr·민감 파일명·credential 형태 URL·
인자·설정 및 framework 초기화·부적합 성공 payload의 sentinel 회귀가 이를 검증한다.
scanner 내부 캡처 버퍼와 사용자/CI에 공유되는 출력 경계도 구분한다.

### RED/GREEN과 재스캔

| 작성자 직접 실행 | 결과 |
| --- | --- |
| 예외 비활성화 통제 검사 | 현재 2·이력 24, 미처리 26, exit1, 77.84초 |
| 정확한 예외 적용 후 동일 범위 | 현재 0/예외2 · 1,519 commits 이력 0/예외24, exit0, 77.09초 |
| 익명별 처리 횟수 | A01 12회·A02 14회, 현재/이력 중복을 고유 credential 수로 합산하지 않음 |
| 실제 위치를 복제한 focused control | 1 method의 A01/A02 두 subtest PASS, 13.228초 |
| 같은 위치·같은 길이의 새 generic credential | A01/A02 각각 현재·이력에서 exit1. generic-api-key rule 자체의 검출 확인 |
| 초기 신규 단위 RED | 7 FAIL / 13 PASS (오류 출력 2경로와 미구현 기능 포함) |
| controls 인자/최적화 RED | 2 FAIL / 20 PASS |
| reviewer setup/runner RED | 2 FAIL / 22 PASS → 바깥 출력 캡처로 수정 |
| 부적합 성공 payload RED | 1 FAIL / 24 PASS → 숫자 요약 검증으로 수정 |
| 빈 suite/skip/expected-failure RED | 3 FAIL / 25 PASS → 필수 실행 검사로 수정 |
| 필수 실행 보강 후 단위 | 28 PASS, 3.77초 |
| 관련 focused 회귀 | 107 PASS, 44.22초. 이후 세 필수 실행 분기는 위 최종28에서 재검증 |

예외 비활성화 통제는 고정 rule-ID-only template으로 예외 비교만 끈 별도 negative control이다.
수정 전 코드 전체를 checkout하거나 원본 보고서를 재출력한 검사가 아니다. 기존 실행기의
수정 전 exit1 기록과 이 통제 재현, 수정 후 exit0을 구분한다.

최종 전체 controls·quality/boundary/Contract·workflow·diff 및 같은 reviewer의 결과는
아래 마감 기록으로 보완한다. 전체 pytest·MySQL·Docker build·원격 Actions·배포는 실행하지 않는다.

### 배포 gate와 PR 편입 판단

실제 새 generic credential은 계속 exit1이고 도구/보고서/설정 오류는 exit2다.
원래 workflow shell 두 분기는 exit0/1/2를 그대로 전파하며, publish/remote는
`needs: [secret-scan]` 성공에 의존한다. failure/cancel/skip override나 continue-on-error가 없다.
필수 controls 미실행도 성공으로 바꾸지 않는다. 일반 PR gate 보류가 이 배포 의존성을 없애지 않는다.
이는 로컬 실행·원래 shell 대역·정적 dependency 검증이며 원격 Actions 실행 성공 증거는 아니다.

초기관측된 고유 오탐 두 개는 확인·제한 처리했지만 일반 PR gate는 보류한다.
로컬 전체 스캔 약77초와 별개로 cold checkout/download·Linux CI 비용이 미측정이고,
fork/PR 편입에는 trusted runner/config와 base/head fetch 설계가 별도로 필요하다.
현재 수동/재사용 develop 배포 전 gate는 유지한다. RT-15/#301 전체는 원격 CI pending으로
IN_PROGRESS다. Issue close·commit·push·PR·외부 게시·AWS/provider·배포·실행 변수 변경은 하지 않는다.

### 같은 fresh reviewer delta

같은 reviewer는 실제 A01/A02 원문·탐지 경로·저장소 스캔을 열람/실행하지 않았다.
독립 합성 경로·값·지문으로 정확한 예외 허용, 새 값/Match/위치 지문 거부, 현재 view의
줄·열·경로 변경 거부, CRLF 정규화 허용과 child/wrapper 비노출을 직접 검증했다.
이력에서 단순 빈 줄 추가는 기존 secret 줄의 새 추가 diff가 아닐 수 있어, 이력 결과만으로
새 현재 좌표를 검사했다고 주장하지 않는다. 기본 both의 현재 검사는 이동 좌표를 거부한다.

reviewer는 scope1 예외-only 성공 뒤 history 오류도 직접 exit2/clean 문구 없음으로 확인했다.
추가 P2 두 건(controls 초기화/runner 출력 경계, 빈 suite 성공)을 지적했고 작성자가 RED를
재현해 수정한 뒤 같은 reviewer가 최종 단위28 PASS(3.66초)와 코드 delta를 재확인했다.
남은 기능·보안 지적 없음. 실제 분류·현재/이력 건수·재스캔은 위 작성자 증거이며 reviewer가
직접 실제 credential을 확인한 것으로 바꾸지 않는다. reviewer 소유 scratch는 정리됐다.


### 마감 검증 기록

- 마지막 코드의 전체 합성 controls: **17 PASS**, 실패/오류0. 빈 suite·skip·expected-failure 거부와
  명시적 module 선택·숫자 summary 검증을 포함한 상태에서 직접 실행했다.
- 최종 단위: **29 PASS(1.75초)**. 추가한 scope orchestration 회귀는 현재 예외-only 성공 뒤
  history 오류를 exit2로 유지하고 최종 clean 문구가 없음을 검증한다. 관련 focused107과
  겹치는 실행은 합산하지 않는다.
- boundary CLI PASS, import fixture **258 PASS(96.70초)**, Contract 구조62·JSON26·의미104 PASS.
  Runtime Ruff PASS, mypy Linux/win32 각각87파일 오류0. 새 scripts/test Ruff PASS.
- actionlint1.7.12로 변경 workflow2개 exit0 확인(shellcheck/pyflakes 제외).
  원래 workflow shell 두 분기6경우가 exit0/1/2를 그대로 전파했고, dependent job의
  failure/cancel/skip override·실패 무시가 없음을 재확인했다. 실제 배포/AWS 호출은 0이다.
- 같은 reviewer는 최종 단위28(3.66초)과 추가 orchestration1(0.31초)을 **별도 직접 실행**했다.
  한 번의 전체29 실행으로 표기하지 않는다. 최종 코드·문서 delta에 추가 지적 없음.
  실제 A01/A02 분류·실제 재스캔은 작성자 증거다. reviewer의 합성 템플릿/좌표/실패/비노출
  검증과 구분한다. reviewer 임시 자원은 정리했다.
- 이 Task의 전체 변경 manifest는 위10파일이다. 이번 후속 보완은 그 중 runner·controls·
  exception JSON·unit test·README·Notes·Log·plan의8파일이며 기존 workflow2개는 보존했다.
  현재/이력 마지막 결과와 소유 scratch 정리·index/diff 마감은 아래 실제 확인으로 덧붙인다.


### 최종 상태 확인

문서/테스트 마감 후 현재2,316파일 재스캔도 미처리0·정확한 예외2(A01/A02각1),
exit0·8.47초였다. 전체 HEAD1,519commits 검증은 미처리0·정확한 예외24·exit0 기록을 유지한다.
이후 소유 .codex-scratch/rt15c-exceptions의 tool·합성/회귀 임시 파일·hash-only 준비 자료와
helper를 절대 경로/reparse 확인 후 정리했다. scanner view잔존0, 다른 작업 scratch 보존.
최종10파일 공백 검사/diff PASS, index 비어 있음, branch/HEAD 시작 상태 동일.
이번 후속 보완도 commit·push·PR·외부 게시·실제 배포 없이 미커밋/미스테이징으로 남긴다.
