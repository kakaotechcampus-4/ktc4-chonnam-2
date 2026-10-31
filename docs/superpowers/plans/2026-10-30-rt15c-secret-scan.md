<a id="rt-15c-secret-scan-implementation-plan"></a>

# RT-15(c) secret scan 구현 계획

> **에이전트 작업자 지침:** superpowers:executing-plans로 현재 세션에서 실행한다. 사용자 지시는 worktree 생성, checkout, staging, commit, push, PR 생성, 댓글, 배포를 금지한다.

**목표:** 발견 내용을 공개하지 않는 재현 가능한 오프라인 배포 전 secret 탐지.

**아키텍처:** Gitleaks 8.30.1 release archive, 실행 파일, upstream 규칙을 SHA-256으로 고정한다. 표준 라이브러리 Python wrapper는 child 출력을 포착하고 내장 rule ID와 개수만 내보내며 원본 발견 보고서는 절대 쓰지 않는다. Git 관리/현재 비무시 파일의 hardlink view와 전체 HEAD 조상을 별도로 스캔한다. 소스 복사나 baseline은 없다. 불완전한 이력, 지원하지 않는 파일, 무결성 오류, scanner 오류는 안전하게 거부한다.

**기술 스택:** Python >=3.12, Git, Gitleaks 8.30.1; Linux/Windows x64.

**명세:** Runtime Implementation Plan RT-15 및 §12; Ops Spec §7/§19/§21; 이 대화의 사용자 요청(비공개 및 로컬 전용 완료 제약).

<a id="global-constraints"></a>

## 전역 제약

- quality, 경계/Contract, regression, mysql, test 의미를 변경하지 않는다.
- provider 검증, AWS/OIDC 권한, 자격 증명 rotation, 이력 변경은 없다.
- 광범위한 저장소 허용 목록, inline suppression, baseline은 없다. upstream 전역 경로 제외를 제거하고 남은 내장 detector 한계를 문서화한다.
- root, side branch, merge resolution을 포함한 전체 HEAD 조상을 다루고 shallow/partial clone을 거부한다. scanner는 자동 fetch하지 않는다.
- 수동/재사용 workflow는 이 저장소 develop ref로 제한하며 배포 job이 여기에 의존한다. PR trigger로 fork 코드를 실행하지 않는다.
- 일반 PR gate 배치는 측정한 발견 내용/비용을 따르며 미결 발견 내용은 배포 전 단계를 차단한다.

<a id="review-focus"></a>

## 검토 초점

- 삭제된/side-branch/merge-resolution secret과 depth-1 clone.
- scanner 실패 대 발견 내용: 출력이나 의존성 누락은 통과할 수 없다.
- inline/config/ignore 우회와 정확한 예외 범위(최초에는 로컬 예외 없음).
- 자격 증명이 포함된 경로, 인접 코드, stdout/stderr, 보고서, artifact upload.
- 재사용 workflow 권한과 배포 전 의존성 전파.

<a id="tasks"></a>

## 작업

- [x] 1. runner 전에 실제 CLI 합성 대조를 작성한다. clean/detect/clean, dirty tracked/untracked, ignored scratch 대 tracked ignored 경로, 이력 삭제/merge/root, shallow, 도구 실패를 다룬다. RED를 관측한다.
- [x] 2. 고정 installer와 안전하게 거부하는 wrapper를 구현한다. checksum, 합성 대조, 개수 전용 보고서, 포착한 실패를 검증한다. 원시 출력 없이 실제 snapshot/history scan을 실행한다.
- [x] 3. 수동/재사용 develop 전용 CI와 배포 전 의존성을 추가한다. 기존 CI 의미를 보존한다. actionlint와 집중 테스트로 workflow를 검증한다.
- [x] 4. 측정값, 한계, #301 인수 조건 매핑, pending 원격 CI를 README, Implementation Notes, 추가 전용 Log에 갱신한다.
- [x] 5. 작성자 이력이 없는 새 읽기 전용 검토자를 사용하고 지적을 수정한 뒤 같은 검토자의 차이 확인을 받는다. 집중 경계/Contract/quality/diff 검사를 실행하고 작업 소유 임시 자원만 제거한다.

<a id="execution-ledger"></a>

## 실행 기록

- 시작: branch codex/rt15c-secret-scan, HEAD 6b116e4a1317dc8e5c13e34b05481107bc00ca21; tree/index는 깨끗했다. 가져온 origin/develop과 같았으며 도달 가능한 커밋 1,519개, nonshallow였다. PR #483/#484 병합, Issue #301 댓글은 비어 있었다.
- 판단: 사용자 명시적 구현 요청과 Plan §12.3 위임에 따라 현재 세션에서 진행한다. 추가 설계 승인이나 Git 변경은 없다.
- 판단: TruffleHog(provider 검증 불필요/금지), detect-secrets(baseline 중심 workflow에 별도 이력 열거 필요) 대신 Gitleaks를 선택한다. 공식 증거와 무결성 고정값은 Notes에 둔다.
- 대조: 최초 script-absent RED에는 clone 설정 오류 하나가 포함됐으며 file URL을 수정했다. 이 Windows 호스트에서 hardlink 대조는 sandbox escalation이 필요하며 없으면 안전하게 거부한다. 최종 표준 라이브러리 대조 14/14 PASS (41.910s).
- 판단: 측정된 시작 비용 0.704s/파일 및 파일 이름 의존 규칙 손실 때문에 파일별 stdin 대안을 기각하고 읽기 전용 hardlink를 유지한다. 소스 복사는 없다.
- 판단: 합성 Git -diff attribute가 과거 text secret을 숨겼다(RED). --text/--no-renames를 강제했다(GREEN). replacement ref를 비활성화하고 graft 및 부분 이력을 거부한다.
- 측정: 최초 snapshot2314/파일 findings2 in12.98s; history1519/occurrences24 in69.38s, 모두 generic-api-key이며 미분류. baseline이 없고 소스/경로를 노출하지 않았다. 일반 PR gate는 연기하고 분류 전까지 배포 전 검사는 실패한다. --text 이후 history 재검사는 진행 중이다.
- 집중94 PASS (23.80s); 독립 unit12 PASS. 경계/quality/actionlint 최종 검증과 새 읽기 전용 검토는 진행 중이다. 원격 CI/deploy는 의도적으로 실행하지 않았다.
- 최종 검증은 위 진행 항목을 대체한다. 경계/Contract PASS, import fixture258PASS88.58s, Runtime Ruff 및 mypy Linux/win32 각각87개 파일 clean, 새 scripts/test Ruff 및 actionlint1.7.12 PASS. 최종 unit12PASS0.59s, 작성자 전체16controls PASS59.792s.
- --text 이후 최종 history:1519commits/24occurrences76.41s, 최종 snapshot2315files/2occurrences8.47s, 모두 exit1. 자격 증명 분류나 clean 주장은 없다.
- 새 검토자가 원본14controls PASS65.989s + unit12PASS0.59s를 직접 실행했다. 로컬 Git signature verifier 실행 P2를 확인했고 작성자가 독립적으로 RED를 재현한 뒤 --no-show-signature로 수정했다. 같은 검토자가 직접 delta2controls PASS7.345s와 코드/workflow 재검사를 수행했으며 남은 기능/보안 지적은 없었다.
- 배포 대상 조상 binding은 별도로 RED→GREEN을 거쳤으며 live remote develop 조상에만 의존하지 않는다. Notes/log에 사소한 수정 사항을 기록했고 같은 검토자의 최종 문서 차이 확인을 요청했다. 작업 소유 scratch 정리는 pending이며 Git 변경이나 원격 실행은 승인되지 않았다.
- 완료: 같은 검토자의 최종 문서 차이 검토에는 지적이 없다. 절대 대상 확인 후 작업 소유 .codex-scratch/rt15c (도구/archive/합성 저장소) 및 실패한 sandbox TEMP 하나를 제거했다. scanner view는 남아 있지 않다. staging/commit/push/PR/배포는 수행하지 않았다. 실제 발견 내용과 원격 CI는 로컬 구현 완료 범위 밖에서 pending으로 남는다.


<a id="authorized-exceptionnon-disclosure-delta-plan"></a>

## 승인된 예외/비공개 차이 계획

- [x] 좁은 예외와 출력/오류 sentinel 대조를 테스트 우선으로 추가하고 RED를 관측한다.
- [x] A01/A02를 정확한 rule, 해시 경로, 좌표, 정확한 탐지 내용 fingerprint에 결속하며 다른 모든 발견/오류는 계속 차단한다. baseline이나 rule/path 비활성화는 없다.
- [x] 조사 전용 원시 출력 사고를 제품 runner 동작과 별도로 기록하고 안전하지 않은 진단 report mode를 막으며 합성 실패 출력을 검증한다.
- [x] 현재 파일과 전체 HEAD 조상을 스캔하고 같은 위치의 변경된 자격 증명도 여전히 실패하는지 검증한다. 집중/quality/경계/Contract/workflow/diff 검사를 실행한다.
- [x] 같은 새 검토자의 차이 검토, 문서/README/Log 갱신, 작업 소유 임시 자원 정리 후 unstaged/미커밋으로 둔다.

수정 전 A01/A02 기준값: current2/history24 -> 정확한 위치 항목 2개 (A01 current1/history11, A02 current1/history13), 둘 다 오탐으로 확인했으며 제품 runner는 계속 exit1이었다. 비공개 분류 과정의 임시 조사 helper가 원시 성공 payload를 출력했다. 이는 발견 내용에 발급된 자격 증명으로 의심되는 값이 없다는 점과 독립적인 출력 절차 위반이었다. 제품의 개수 전용 runner에서 나온 것이 아니다. 원시값, 코드, 탐지 경로는 여기에 재현하지 않는다.


승인된 차이 증거: 예외 비활성 대조 current2/history24 exit1/77.84s; 정확한 template 활성 current0+allowed2/history0+allowed24 exit0/77.09s (1519commits,2316files). 실제 검토 소스 clone2subtests PASS13.228s, 같은 폭의 generic-value 변이 current/history exit1. 최종 controls17PASS, unit29PASS1.75s; focused107PASS44.22s 및 최신 missing-execution/orchestration unit 차이. 경계/import258/Contract62+26+104/플랫폼별 Runtime quality87/actionlint/diff 검사가 통과했다. 같은 검토자 합성 검사 + 직접28 및 별도1 PASS, 남은 findings0. 제품 CLI/template에는 조사 원시 report dump 경로가 없었으며 오류 경계는 독립적으로 강화했다. 비공개 원본 finding/source 필드는 재현하지 않는다. 문서 이후 최종 snapshot/작업 소유 정리/index 검사는 pending이다.

최종 차이 완료: 문서 이후 snapshot0/unhandled+2precise exceptions/exit0/8.47s; fullHEAD1519 history0+24precise exceptions/exit0/77.09s. 절대 경로/reparse 검사 후 작업 소유 exception scratch/tools/helper/hash metadata를 제거했으며 views0이다. 전체10-file whitespace/diffPASS, index는 비어 있고 branch/HEAD는 변경하지 않았다. 검토자 최종 코드/문서 지적 없음, 직접28과 별도1을 정확히 귀속했다. 원격 CI/publish/deploy는 의도적으로 실행하지 않았으며 issue301은IN_PROGRESS로 유지한다.
