# 코딩 에이전트 전달용 — ADR-EVIDENCE-005(D2) 반영 구현 프롬프트

이 문서 전체를 저장소에 접근 가능한 코딩 에이전트 또는 담당자에게 전달한다. 기준 문서는 하나다.

- [ADR-EVIDENCE-005 — 판정 주체가 없는 사건 장면·전후 상황 rule을 `FINAL_PACKAGE`에서 제거한다 (D2)](../adr/adr-event-context-rules-removal.md)

이 프롬프트는 계획 작성이 아니라 **구현·테스트·Artifact 재실행·증빙 기록까지 수행하는 작업 지시**다.

발주자: 김준영(`evidence` Owner). 작성일: `2026-09-14`.

---

당신은 대신고 모노레포에서 김준영 담당 `evidence` 모듈을 구현하는 엔지니어다.

**ADR-EVIDENCE-005는 이미 `ACCEPTED`다. 이 작업은 그 결정을 정책 데이터·코드·테스트·Artifact·문서에 실제로 반영하는 일이다.** 결정을 다시 논의하거나 확정된 값에 대해 확인을 반복해서 요구하지 마라. 짧은 계획을 공유한 다음 구현·검증·결과 정리까지 진행하라.

ADR의 판정 규칙을 이 프롬프트에 복제하지 않았다. **원문은 항상 ADR의 해당 절이며, 아래 작업 항목은 "어느 절을 어디에 반영하는가"만 지정한다.** 이 프롬프트와 ADR이 달라 보이면 ADR이 이긴다.

**절 번호 표기.** 아래에서 그냥 `§`로 적은 것은 **ADR-EVIDENCE-005의 절**이다. 다른 ADR은 「ADR-002 §5.12」처럼 번호를 붙이고, 이 프롬프트 자신의 절은 「이 프롬프트 §10」처럼 명시한다.

## 1. 목표와 담당 범위

**한 문장:** `FINAL_PACKAGE` 무조건 rule 세 건을 제거한 새 catalog revision을 발행하고, 그 결과 H·U의 `ReportPackage`가 실제로 돌아오는 것을 증빙으로 남긴다.

- 제거 대상 세 rule과 근거는 §5.1·§4. **직접 열거하지 말고 ADR을 읽어라.**
- `policy/requirement-rules-v4`를 발행한다(§5.2). `v3`는 보존한다.
- 관찰 fact 입력 key를 정리한다(§5.5).
- H/U/P/R 네 공용 Scenario를 재실행하고 변화를 기록한다.

**범위 밖.**

- `recording`의 REPORT_VIDEO 생성 전략·span 정책(§5.6 D2-e). **`recording` Owner 소유다. 대신 확정하지 마라.**
- 통합 항목 I2(공용 fixture 재렌더)·I4(번호판·시각 관찰 전달). 둘 다 다른 Owner다.
- `package.evidence.situation_response`의 outcome 매핑 변경(§5.4 — **유지가 결정이다**).
- common/runtime, 다른 모듈 구현, 실제 AI/OCR·영상 생성, 외부 제출.

## 2. 시작할 때 확인할 것

1. 현재 브랜치·HEAD·작업 트리 상태와 `CLAUDE.md`·`docs/README.md`·`AGENTS.md`가 있으면 그 규칙을 확인한다.
2. 기존 미커밋 변경은 발주자의 작업물이다. 되돌리거나 고치지 말고 내 커밋에 섞지 않는다(「이 프롬프트 §10.2」).
3. **변경 전 기준선을 먼저 실행해 기록한다**(「이 프롬프트 §9」). 이 작업은 "결과가 바뀌는 것"이 목적이므로 전후 비교가 증빙의 핵심이다.
4. 담당 범위·순서·확인이 필요한 항목을 짧게 공유한 뒤 구현을 시작한다.

작성 시점 스냅샷 — 브랜치 `feature/evidence-location-nullable`, HEAD `39d3e0e`. ADR-005와 `reviews/14_…`를 포함한 문서 8개가 **미커밋 상태**다. **이것은 과거 스냅샷이다. 실행 시 현재 상태를 다시 확인하라.**

## 3. 읽을 자료와 우선순위

모든 경로는 저장소 루트 기준이다.

### 반드시 먼저 읽을 것

- [`adr/adr-event-context-rules-removal.md`](../adr/adr-event-context-rules-removal.md) — **이 작업의 기준.** §2(배경·관측 상태)·§5(결정 7건)·§9(검증표)·§12(발주 범위)
- [`reviews/14_instruction-conflict-analysis-and-doc-fixes_2026-09-14.md`](../reviews/14_instruction-conflict-analysis-and-doc-fixes_2026-09-14.md) — 이 결정에 이르게 된 분석. §1의 outcome 분포가 기대값의 근거다
- [`reviews/13_adr-002-003-implementation_2026-09-14.md`](../reviews/13_adr-002-003-implementation_2026-09-14.md) — 직전 구현 회차의 검수 기록
- `src/daesingo/evidence/` 전체와 `README.md`
- `tests/evidence/` 전체와 `tests/evidence/fixtures/adapter_inputs.json`
- [`first-completion-result.md`](../first-completion-result.md) — 갱신 대상 추적표

### 배경 (필요할 때)

- [`adr/adr-first-completion-owner-decisions.md`](../adr/adr-first-completion-owner-decisions.md) — K3 원문. §5.6·§5.12·§5.14·§5.15에 **D2 표시**가 붙어 있다. §5.9(`situation_response`)는 이번에 바꾸지 않는 것의 원문이다
- [`adr/adr-requirement-policy-engine.md`](../adr/adr-requirement-policy-engine.md) — 정책 엔진 구현 구조(ADR-004). 활성 catalog 선택점 원칙
- `docs/architecture/contracts/contract-requirement-report-package.md` §4.3(precedence)·§5.2(`PACKAGE_READY`)·§6(불변조건 6·7)

## 4. 현재 상태 — 반드시 알고 시작할 것

작성 시점에 실제로 확인한 값이다. **재실행해서 직접 확인하라.**

| 항목 | 현재 |
| --- | --- |
| 활성 catalog | `policy/requirement-rules-v3` (파일: `src/daesingo/evidence/requirement_rules_v3.json`) |
| `EVIDENCE` rule | always 4 / conditional 0 |
| `FINAL_PACKAGE` rule | **always 15 / conditional 1** → Report의 `checks[]`는 16개 |
| H baseline | `FINAL_PACKAGE` `UNKNOWN`, Package 0건. `UNKNOWN`은 **제거 대상 세 건뿐**, 나머지 13개 전부 `PASS` |
| U baseline | `FINAL_PACKAGE` `UNKNOWN`, Package 0건. `UNKNOWN`은 **세 건뿐**, 나머지는 `PASS` 10 · `WARN` 3 |
| P·R baseline | `FINAL_PACKAGE` 평가 자체가 없다(EVIDENCE scope 전용). **이번 변경으로 달라지면 안 된다** |
| `BLOCK` | 네 Scenario 어디에도 없다 |

**세 rule 제거 후 기대값은 산술적으로 확정돼 있다** — H는 `PASS` 13개만 남아 `overall=PASS`, U는 `PASS` 10 + `WARN` 3으로 `overall=WARN`. 둘 다 Package가 발행된다.

**결과가 이와 다르면 멈추고 원인을 찾아라.** 기대값에 맞추려고 다른 rule이나 입력을 손대지 마라.

### 제거 대상이 등장하는 파일 (전수 확인 결과)

| 파일 | 처리 |
| --- | --- |
| `src/daesingo/evidence/requirement_rules_v3.json` | **수정 금지.** v4를 새로 만든다 |
| `src/daesingo/evidence/requirement_rules_v2.json` | **수정 금지.** 과거 revision |
| `src/daesingo/evidence/requirements.py` | `_observation_check`의 `reason_roots`에서 세 code 제거 |
| `src/daesingo/evidence/mock_integration.py` | `known_differences` 문자열 중 세 rule을 언급하는 항목(작성 시점 `:454` 부근)이 **낡은 설명이 된다.** 그대로 두지 마라 |
| `tests/evidence/fixtures/adapter_inputs.json` | `final_rules` 기대값과 `requirement_observation_facts`에서 제거 |
| `tests/evidence/test_policy_decisions.py` | 기대값 갱신 |
| `tests/evidence/test_mock_integration.py` | 기대값 갱신 |
| `docs/modules/evidence/artifacts/first-completion/*.baseline.json` | 재실행으로 자동 갱신 |
| `docs/modules/evidence/adr/adr-first-completion-owner-decisions.md` | **수정 금지.** D2 표시가 이미 반영돼 있다 |
| `docs/modules/evidence/prompts/implementation-prompt-adr-002-k1-k4.md` | **수정 금지.** 발주 이력이다 |

`apps/`·`data/mock/`·`web`에는 세 rule code가 **없다.** Consumer 쪽 영향이 없음을 확인했으니 그쪽을 찾아 고치려 하지 마라.

## 5. 변경할 수 있는 범위

- `src/daesingo/evidence/` 코드와 정책 데이터, `tests/evidence/`, `docs/modules/evidence/`의 문서·Artifact를 작성·수정한다.
- 기존 공용 타입·유틸을 재사용한다. 새 패키지·포매터·추상화를 도입하지 마라.
- 다음은 **수정 금지**다.
  - `docs/architecture/contracts/`의 Final Contract 전부 — **이번 작업에는 계약 개정이 없다**
  - 공용 `data/mock/` 원본, 공용 validator(`data/mock/validate_mock_pack.py`, `scripts/check_*.py`)
  - 다른 Owner의 모듈 구현·문서 폴더
  - `.github/workflows/{assign-mentor,notify-discord,convention-check}.yml`·`.github/CODEOWNERS`
  - `docs/management/secret/`·`docs/management/submissions/`·`doc/` — 커밋 금지, `git add -f` 금지
  - `docs/archive/`
  - `requirement_rules_v2.json`·`requirement_rules_v3.json`
  - `prompts/` 전체와 `reviews/13_…`·`reviews/14_…`(시점 기록)
- **커밋은 「이 프롬프트 §10」에 따라 직접 수행한다.** 커밋 전 승인을 다시 요청하지 마라. push·PR·이슈·외부 메시지는 별도 지시 없이 수행하지 마라.

## 6. 작업 항목

각 항목은 「근거 → 할 일 → 완료 조건 → 하지 말 것」이다.

### W1 — `requirement_rules_v4.json` 발행

**근거:** §5.1 · §5.2

**할 일**

1. `requirement_rules_v3.json`을 복사해 `src/daesingo/evidence/requirement_rules_v4.json`을 만든다. `policy_ref`는 `policy/requirement-rules-v4`, `supersedes_policy_ref`는 `policy/requirement-rules-v3`, `decision_ref`는 ADR-005를 가리킨다.
2. `FINAL_PACKAGE`의 `always`에서 §5.1이 지정한 세 rule을 삭제한다.
3. **그 외 모든 내용을 그대로 계승한다** — `EVIDENCE` 4개, 나머지 무조건 12개, 조건부 selector 블록, `referenced_policies`, `asset_requirements`, `policy_configuration_errors`.
4. JSON 키 명명·들여쓰기·근거 필드 구성은 v3를 그대로 따른다.

**완료 조건**

- `FINAL_PACKAGE` always 12 / conditional 1. `EVIDENCE` always 4.
- 남은 12개의 `code`·`category`·`outcomes`가 v3와 문자 단위로 같다(세 개가 빠진 것 외의 차이가 없다).
- `referenced_policies.report_template`이 여전히 `safety-report-policy/v1.1`이다.

**하지 말 것**

- v2·v3 파일을 고치거나 지우지 마라.
- rule을 더 빼거나 더하지 마라. **정확히 세 개다.**
- 남은 rule의 `outcomes` 매핑을 조정하지 마라. 특히 `package.evidence.situation_response`의 `NOT_ASKED → UNKNOWN`은 **유지가 결정이다**(§5.4).
- 조건부 selector의 네 갈래(`package.time.overlay_visible`·`post_stamp_applied` 2건·`display_unresolved`)를 건드리지 마라.
- `EVIDENCE` scope를 건드리지 마라.

### W2 — 활성 catalog 선택점 갱신

**근거:** §5.2 · ADR-002 §5.13 · ADR-004

**할 일**

1. 활성 catalog를 v4로 바꾼다.
2. **선택점은 코드에서 한 곳뿐이어야 한다.** 파일이 셋이 되므로 호출자가 파일을 고르거나 파일명을 여기저기서 조립하는 구조를 만들지 마라.

**완료 조건**

- 「어느 catalog가 활성인가」를 읽으려면 한 군데만 보면 된다.
- 출력 `policy_ref`가 `policy/requirement-rules-v4`이고, 그 값이 **코드 상수가 아니라 로드한 catalog에서 온다.**

### W3 — 구현 정리

**근거:** §5.5

**할 일**

1. `requirements.py`의 `_observation_check` `reason_roots`에서 제거된 세 code 항목을 지운다.
2. `mock_integration.py`의 `known_differences` 중 세 rule을 언급하는 문자열을 실제 상태에 맞게 고친다. **관찰 fact 부재로 `UNKNOWN`이라는 설명은 더 이상 사실이 아니다.**
3. 관찰 fact 입력 key는 §5.5의 표대로 남은 것만 소비한다. 제거된 key가 입력으로 들어와도 그것을 읽는 rule이 없으므로 판정에 영향이 없어야 한다 — **그 key를 오류로 만들지 마라.**

**하지 말 것**

- 관찰 fact의 구조 검증(boolean·`subject_refs`·`PolicyConfigurationError`)을 남은 세 fact에서 약화시키지 마라.
- `plate_visible_in_report_video`·`time_overlay_visible`·`post_stamp_applied` 경로를 건드리지 마라.

### W4 — 테스트와 adapter fixture 갱신

**근거:** §9 · §12-4·5

**할 일**

1. `tests/evidence/fixtures/adapter_inputs.json` — `final_rules` 기대 목록에서 세 code를 빼고, `requirement_observation_facts`에서 세 key를 뺀다. 파일의 `note`도 의미에 맞게 갱신한다.
2. `tests/evidence/test_policy_decisions.py` — rule 수를 고정하는 테스트를 **16 → 13**(무조건 12 + 조건부 1)으로 고친다. **테스트 이름에 숫자가 박혀 있으면 이름도 함께 고친다.**
3. `tests/evidence/test_mock_integration.py` — 세 rule을 참조하는 기대값을 갱신한다.
4. **회귀 방지 테스트를 하나 추가한다** — 활성 catalog의 `FINAL_PACKAGE` 무조건 rule에 세 code가 **없음**을 데이터에서 확인하는 테스트. 다시 들어오면 깨지게 한다.

**하지 말 것**

- 테스트를 통과시키려고 공용 fixture를 고치지 마라.
- 기대값을 실행 결과에 맞춰 사후에 베끼지 마라. **§4의 기대값이 먼저이고 결과가 그것과 맞아야 한다.**

### W5 — Artifact 재실행과 변화 기록

**근거:** §9 · §12-6

**할 일**

1. `python -m daesingo.evidence.mock_integration`을 재실행해 `docs/modules/evidence/artifacts/first-completion/`의 baseline 4종과 `run-summary.json`을 갱신한다.
2. Scenario별로 무엇이 바뀌었는지 기록한다: 사라진 check 3개, 바뀐 `policy_ref`, 바뀐 `overall`, **새로 발행된 Package**.
3. 다섯 파일 어디에도 `policy/requirement-rules-v3`가 없음을 실제로 확인해 기록한다.

**완료 조건**

- H — `FINAL_PACKAGE` `overall=PASS`, `pkg_h001` 발행, `PACKAGE_READY` 성립
- U — `FINAL_PACKAGE` `overall=WARN`, `pkg_u001` 발행, `PACKAGE_READY` 성립
- P·R — `FINAL_PACKAGE` 평가 없음. **변화 없음**
- 세 rule code가 어떤 Report의 `checks[]`에도 없다

**반드시 정직하게 다룰 것**

- **공용 fixture와의 차이가 남는다.** 디스크의 `pkg_h001`·`pkg_u001`은 아직 `contract-version: report-package/v1`이고, `pkg_u001`의 `template_ref`는 위치 있는 `tmpl/safety-report-generic-v1`이다. 재실행 결과는 `v1.1`과 위치 없는 template을 쓴다. **이것은 I2(`case`) 미완의 결과이지 회귀가 아니다.** `comparison.known_differences`에 그 의미로 남기고, **fixture를 고쳐 맞추지 마라.**
- **`plate_visible_in_report_video`가 무조건 rule에 남는 유일한 관찰 입력이 된다.** 현재 공용 입력에서 `mock_only: true`로 주입되고 있으므로, **실제 Runtime에서는 I4가 끝나기 전까지 이 rule이 `not_observed → UNKNOWN`이 되어 Package가 다시 막힌다**(§5.7). Package가 돌아온 것을 "Runtime 준비 완료"로 보고하지 마라. 이 의존성을 보고서에 명시하라.
- Package가 기대와 다른 이유로 돌아오거나 안 돌아오면 **원인을 찾아라.** 입력이나 다른 rule을 손대서 맞추지 마라.

### W6 — 문서 갱신

**근거:** §12-7·8

**할 일**

1. `src/daesingo/evidence/README.md` — 정책 데이터 목록에 v4를 추가하고 **어느 것이 활성인지 한 줄로 분명히 한다.** 파일이 셋이므로 목록만 보고 헷갈리면 안 된다. v2는 「채택 후 첫 실행 전 대체」, v3는 「실행된 뒤 D2로 대체」로 구분해 적는다. 공개 함수 시그니처가 바뀌지 않았다면 그 부분은 손대지 마라.
2. [`first-completion-result.md`](../first-completion-result.md) — 기준 정책 목록, 실행 결과 표(H·U 행), 「반영 대기 결정」 인용 블록, Q1·후속 표를 실제 결과로 갱신한다. **인용 블록은 반영이 끝났으므로 「반영 완료」로 바꾸거나 제거한다.**
3. **ADR 본문의 결정 내용을 고쳐 쓰지 마라.** ADR은 결정 기록이고 실행 증빙의 소유자가 아니다. 구현 중 ADR의 사실관계 오류를 발견하면 직접 고치지 말고 근거와 함께 보고에 남겨 김준영이 ADR-005 §10으로 처리하게 하라.

### W7 — 검수 보고서

**근거:** §12-9

**할 일**

`docs/modules/evidence/reviews/15_adr-005-implementation_<YYYY-MM-DD>.md`를 작성하고 `reviews/README.md` 목록에 추가한다. **번호 13·14는 이미 사용 중이다.**

담을 것:

1. §9 검증표의 9개 항목 각각에 대한 실제 결과
2. 전후 비교 — 사라진 check, 바뀐 `overall`, 새로 발행된 Package
3. 각 완료 조건이 어느 테스트로 확인되는지의 대응
4. **증명하지 못한 것** — 특히 `plate_visible`의 `mock_only` 의존성과 I2 fixture 차이
5. 후속·통합 대기 목록 갱신. **`recording` 미결(§5.6 D2-e)을 빠뜨리지 마라**

### 실행 순서

**W1 → W2 → W3 → W4 → W5 → W6 → W7.**

W5(재실행)는 W1~W4가 끝난 뒤에 한다. 순서가 뒤바뀌면 중간 상태를 baseline으로 기록하게 된다.

## 7. 모호함이 나왔을 때

| 분류 | 행동 |
| --- | --- |
| 내부 구현 선택(파일 분리·함수 이름·테스트 구조) | 기존 관례와 최소 변경 원칙으로 스스로 결정하고 계속한다 |
| ADR이 이미 확정한 값의 반영 | 근거 절을 남기고 구현한다. 재확인을 요청하지 않는다 |
| ADR과 Contract가 충돌 | 양쪽 원문 조항과 파일 경로를 기록하고 종속된 부분만 보류한다 |
| 새 필드·enum·Owner 경계 결정이 필요 | `Contract 변경 검토 필요`로 분리한다. 김준영이 PM이라는 이유로 다른 Owner의 미결을 대신 확정하지 마라 |
| 결과가 §4의 기대값과 다름 | **멈추고 원인을 보고한다.** 기대값에 맞추려고 입력·rule을 조정하지 마라 |

## 8. 반드시 지킬 의미 경계

- **rule을 제거하는 것과 판정을 무르게 하는 것은 다르다.** 이번 작업은 전자다. 남은 12개의 outcome 매핑을 완화하지 마라.
- **`situation_response`가 evidence에 남는 유일한 사용자 확인 관문이 된다**(§5.4). `NOT_ASKED → UNKNOWN`을 절대 건드리지 마라. 이걸 풀면 사용자 확인 없이 신고자료가 나간다.
- **Package가 돌아오는 것이 목표가 아니라 결과다.** 목표는 판정 주체가 없는 rule을 걷어내는 것이다. Package를 되살리려고 다른 것을 조정하면 이 작업은 실패다.
- **`UNKNOWN` ≠ `BLOCK`.** 둘 다 `PACKAGE_READY`를 막지만 의미가 다르다.
- **입력이 없는데 결과를 만들어내지 마라.** 특히 `plate_visible`·`time_overlay_visible` 관찰 fact를 지어내지 마라.
- **`evidence`는 순수 함수 모듈이다.** 다른 도메인 모듈을 호출하지 않고 Job을 발주하지 않는다.
- **경찰민원24 요건은 실재한다.** rule을 뺀다고 요건이 없어진 것처럼 적지 마라. 확인 책임이 어디로 갔는지(§5.3) 문서에 남긴다.
- **`recording` 미결(D2-e)을 대신 확정하지 마라.** 등재만 하고 닫지 않는다.

## 9. 실행·검증

저장소 루트의 PowerShell에서 실행한다. **변경 전과 변경 후를 모두 실행하고 비교하라.**

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/evidence -p 'test_*.py'
python -m daesingo.evidence.mock_integration
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
python -m ruff check src/daesingo/evidence tests/evidence
python -m compileall -q src/daesingo/evidence tests/evidence
git diff --check
```

공용 validator 결과는 그 validator가 검사하는 fixture 정합성만 뜻한다. 실제 case projection, Runtime E2E, AI/OCR 정확도, 외부 신고 성공, Consumer Owner 수락은 증명하지 않는다. **보고에 그 구분을 유지하라.**

## 10. 커밋 전략

변경을 한 덩어리로 몰아넣지 말고 이력이 보기 좋게 나뉘어 있으면 된다. **구현이 끝난 뒤 실제 diff를 읽고 그 diff에 맞는 커밋 단위로 나눈다.** 완벽한 분할에 시간을 쓰지 마라.

### 10.1 먼저 기존 컨벤션을 확인한다

전략을 세우기 전에 저장소의 현재 관례를 직접 확인하라. 아래는 작성 시점 관찰이며, **실행 시 다시 확인해 실제와 다르면 실제를 따른다.**

- **커밋 메시지:** `git log --oneline -30`. 작성 시점 관례는 `type(scope): 한국어 요약` — type은 `feat`·`fix`·`test`·`docs`·`mock`, scope는 모듈명(`evidence`). 영어 혼용이나 마침표를 쓰지 않는다.
- **코드 컨벤션:** `src/daesingo/evidence/`의 기존 파일을 읽고 맞춘다. 새 포매터·린터·설정 파일을 도입하지 마라.
- **테스트 컨벤션:** `tests/evidence/`의 기존 클래스·메서드 이름과 구조를 따른다. 새 테스트 프레임워크를 도입하지 마라(현재 `unittest`).
- **JSON 정책 데이터:** `requirement_rules_v3.json`의 키 명명·들여쓰기·근거 필드 구성을 따른다.

### 10.2 diff를 읽고 커밋 단위를 설계한다

1. `git status`와 `git diff`(신규 파일은 `git add -N` 후)로 **전체 변경을 실제로 읽는다.** 기억이 아니라 diff를 근거로 한다.
2. 이 브랜치에는 **작업 시작 전부터 있던 미커밋 문서 변경**(ADR-005·리뷰 14 등)이 있을 수 있다. 그것을 내 작업 커밋에 섞지 말고 별도 커밋으로 분리한다.
3. 권장 기준:
   - v4 catalog 발행과 그것을 읽는 선택점 변경은 같은 커밋(데이터만 있고 동작이 없는 중간 상태를 만들지 않는다).
   - 구현 정리(`reason_roots`·`known_differences`)와 그것을 검증하는 테스트는 같은 커밋.
   - Artifact 재실행 산출물은 그 자체로 한 커밋. 큰 diff가 코드 변경을 덮지 않게 한다.
   - 문서(README·결과 추적표·리뷰 15)는 코드와 분리한다.
4. 각 커밋은 그 시점에 `python -m unittest discover -s tests/evidence -p 'test_*.py'`가 통과하는 상태를 목표로 한다. 불가피하게 깨진다면 커밋 메시지 본문에 한 줄로 적는다.

### 10.3 커밋 메시지

- 제목은 `type(scope): 요약`. 무엇을 했는지가 아니라 **무엇이 달라졌는지**를 적는다.
- 제목 한 줄로 충분하면 본문을 쓰지 않는다. 필요할 때만 짧게(근거 절 번호, 의도적으로 바뀐 동작). 변경 파일 목록을 나열하지 마라.
- 정책 결정 자체를 커밋 메시지에서 다시 설명하지 마라. 원문은 ADR-005가 소유한다.
- **커밋 메시지를 리뷰어에게 보내는 설명문으로 쓰지 마라.**
- 메시지 끝에 아래 한 줄을 붙인다. 다른 사람을 author나 co-author로 적지 마라.

  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  ```

### 10.4 커밋할 때 지킬 것

- **커밋은 승인을 다시 묻지 말고 직접 수행한다.** 이미 만든 커밋을 `reset --hard`·`rebase`·`push --force`로 되돌리지 마라 — 새 커밋으로 고친다.
- `git add -A`로 뭉뚱그리지 말고 경로를 지정해 stage한다.
- `docs/management/secret/`·`docs/management/submissions/`·`doc/`·`tmp/`·`__pycache__`·`.ruff_cache`를 커밋하지 마라. `git add -f` 금지.
- `.github/workflows/{assign-mentor,notify-discord,convention-check}.yml`·`.github/CODEOWNERS`를 포함하지 마라.
- 커밋 전 `git diff --check`로 공백 오류를 제거한다.
- **push·PR 생성은 하지 마라.** 김준영이 직접 한다.

## 11. 남길 산출물

1. `requirement_rules_v4.json`. v2·v3는 지우지 않고 남긴다.
2. 갱신된 구현 코드(`requirements.py`·`mock_integration.py`·catalog 선택점).
3. 갱신된 테스트와 **세 rule 재유입을 막는 회귀 테스트**.
4. 갱신된 H/U/P/R baseline 4종과 `run-summary.json`, 전후 변화 목록.
5. `reviews/15_adr-005-implementation_<date>.md`와 `reviews/README.md` 목록 갱신.
6. 갱신된 `src/daesingo/evidence/README.md`·`first-completion-result.md`.
7. 후속·통합 대기 목록 — **`recording` 미결(D2-e)과 `plate_visible`의 I4 의존성 포함.**
8. 「이 프롬프트 §10」에 따라 나눈 커밋들.

보고서의 상태 표기(`검증 완료` / `Mock 연결 검증 완료` / `통합 대기` / `Contract 변경 검토 필요`)는 작업 관리용이며 Runtime Contract enum이 아니다.

## 12. 최종 보고

최종 답변에 다음을 포함한다.

1. §9 검증표 9개 항목의 실제 결과. 하나라도 기대와 다르면 그 사실과 원인.
2. 주요 코드·데이터·테스트·문서·Artifact 파일 링크.
3. **v3 → v4 전후의 H/U/P/R 판정 변화.** 사라진 check, 바뀐 `overall`, Package 발행 여부와 그 이유.
4. 실행한 검사와 결과, 그리고 **그 검사로 증명하지 못한 것.**
5. **`plate_visible_in_report_video`의 `mock_only` 의존성** — Package가 돌아왔지만 실제 Runtime에서는 I4가 필요하다는 사실을 명시.
6. 공용 fixture와 baseline의 남은 차이(I2 범위)와 그것이 회귀가 아닌 이유.
7. 미완료·통합 대기·다른 Owner 소유 항목과 담당자.
8. 만든 커밋 목록(해시·제목).
9. 주간 회의 보고용 1~2문장 요약 — ADR-005 §11이 B-3 보고 대상으로 지정했다.

"코드 작성 완료", "테스트 통과"만으로 종료하지 마라. **어떤 판정이 이제 사라졌고, 그 요건의 확인 책임이 어디로 갔으며, 무엇이 아직 성립하지 않는지**를 증거로 설명하라.
