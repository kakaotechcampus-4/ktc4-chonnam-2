# `evidence` + `common/runtime` 1차 통합 구현 검토 보고서

- **검토일:** 2026-09-07
- **검토 대상:** 브랜치 `codex/feat-evidence-first-integration`의 **미커밋 작업 트리** (신규 15개 파일 + 수정 4개 파일)
- **검토 기준:** `docs/modules/evidence/first-integration-checklist.md` · Final Data Contract 7건 · `module-architecture.md` §3-2·3-5·3-6·3-7·§4-모듈4·§6-2 · `data/mock/` Seed v0
- **검토자:** 김준영 (Owner self-review 대행)
- **판정:** **CONDITIONAL — Merge 전 Blocker 2건 수정 필요.** 나머지는 회의 안건 또는 후속 과제.

> 이 문서는 검토만 한다. 코드를 고치지 않았다. 아래 §1의 2건은 체크리스트 §Merge 중단 기준에 직접 걸리므로 PR 전에 닫아야 한다.

---

## 0. 먼저: 보고된 검증 결과는 전부 재현됐다

에이전트가 보고한 수치를 직접 다시 돌렸고 **모두 사실이다.** 과장이나 미실행 주장은 없었다.

| 보고 내용 | 재현 결과 |
| --- | --- |
| Python smoke/contract test 17/17 PASS | `Ran 17 tests ... OK` — 일치 |
| Mock validator ERROR 0 / WARN 0 | `검사한 고유 JSON 파일 수: 45 / 오류 0 / 경고 0` — 일치 |
| 모듈 경계 검사 PASS | `PASS — 경계·계약 정합성 위반 0건` (evidence가 NOTE 목록에서 빠짐 = 실제로 검사됨) — 일치 |
| CLI Happy 5개 / Partial 4개 + Package 부재 | `report_package_generated: true` / `false` — 일치 |
| 신고문에서 `흰색 SUV` 제외 | `"백색 실선 침범 신고 (12가 3476)"` — 일치 |

**잘한 것으로 기록할 것 5가지**

1. **Contract 형식 JSON in/out 순수 함수.** 다른 모듈 import 0건, caller mutation 0건(`test_assembly_does_not_mutate_caller_input`). `evidence`가 "아무도 호출하지 않는 순수 함수 묶음"이라는 §4-모듈4 경계를 실제로 지켰다.
2. **`흰색 SUV` 문제를 값 생성 없이 처리했다.** `05_kim_junyoung_mock_review` §6이 남긴 계약 빈틈을, 임의 필드를 만들지 않고 template에서 생략하는 쪽으로 닫았다. 정확한 판단이다.
3. **`assemble()`이 clock/random ID를 읽지 않는다.** ID와 `evaluated_at`을 runtime이 주입하는 구조라 같은 입력 → 같은 출력이 보장된다. contract test가 성립하는 근본 이유다.
4. **Tech Spec §2·§9가 정직하다.** `PARTIAL_READY` 표현, Pending 7건 명시, "placeholder나 새 enum으로 대신하지 않는다"까지 — 미결을 미결로 남기라는 팀 규칙을 지켰다.
5. **cross-case/cross-candidate 혼입 차단**(`service.py:791-801`)과 **Requirement basis ↔ Package 일치 검사**(`service.py:699-706`)는 체크리스트에 없던 방어인데 실제로 필요한 것이다.

---

## 1. Blocker — PR 전에 닫아야 한다

### B-1. `TimeSourceCandidate.source_kind` enum이 Final 계약과 다르다 🔴

**위치:** `src/daesingo/evidence/service.py:81-87`

```python
source_names = {
    "FILENAME": "recording.filename_time",
    "FILE_METADATA": "recording.file_metadata_time",
    "MANUFACTURER_METADATA": "recording.manufacturer_metadata_time",   # ← 계약에 없는 값
}
```

`contract-recording-timeline-asset-span.md` §15의 **Final 최소 enum은 `FILENAME | FILE_METADATA | VENDOR_METADATA`** 다. `MANUFACTURER_METADATA`라는 값은 계약 어디에도 없다.

**재현:**

```
resolve_time(None, [{"source_kind": "VENDOR_METADATA", ...}], ...)
→ EvidenceContractError: unsupported TimeSourceCandidate.source_kind: 'VENDOR_METADATA'
```

**왜 Blocker인가.** 체크리스트 §Merge 중단 기준 1번(**"Contract와 다른 필드명/enum 문자열을 쓴다"**)에 정확히 해당한다. 정철원의 `recording`이 제조사 metadata 시각 후보를 내면 `resolve_time()` 전체가 예외로 죽는다. Mock 두 시나리오는 `FILENAME`만 쓰므로 테스트 17개가 전부 통과하면서도 이 결함을 통과시킨다 — **테스트가 잡지 못하는 계약 위반**이라 더 위험하다.

---

### B-2. 시각 후보 충돌인데 `verification = AGREED`를 낸다 🔴

**위치:** `src/daesingo/evidence/service.py:217`

```python
"verification": "UNVERIFIED" if len(usable) == 1 else "AGREED",
```

**재현:** 값이 서로 다른 FILENAME/FILE_METADATA 후보 2건을 넣으면

```
status: NEEDS_REVIEW | conflict.exists: True | resolved.verification: AGREED
```

**무엇이 틀렸나.** `contract-time-resolution.md` §3에서 `verification`은 "선택된 시각 근거가 **어떤 방식으로 검증·합의됐는지**"다. `conflict.exists=true`와 `verification=AGREED`는 같은 객체 안에서 서로를 부정한다. 소비자(`case` → `CaseView.event_time_display.info_state`)가 이 값을 읽으면 **충돌 상태를 "출처 합의됨"으로 화면에 내보낸다.**

**본인의 Tech Spec도 반대로 적혀 있다.** `tech-spec.md` §5.1-3: *"단독 후보나 충돌 fallback은 `NEEDS_REVIEW`, **같은 값을 말하는 복수 후보는 `AGREED`**"* — 즉 AGREED는 "값이 일치할 때"만이라고 스스로 정의해놓고 코드는 개수만 센다.

**왜 Blocker인가.** `ownership.md` §7-④ 통과 기준 3번이 **"시각 출처를 충돌로 만들었을 때 `TimeResolution`이 CONFLICT를 보존하는가"** 다. 1차 통합 회의에서 유소연이 직접 확인할 항목이고, 지금 상태로는 conflict 플래그는 보존하지만 verification이 그것을 지워버린다.

> 참고: `conflict.between_refs`와 `requires_user_notice=true`는 올바르게 채워진다. 고칠 곳은 한 줄이다.

---

## 2. Required — Merge 전에 결정하거나 명시적으로 유예할 것

### R-1. "BLOCK이면 Package 미생성"이 **테스트로 증명되지 않았다**

**위치:** `src/daesingo/evidence/service.py:832` · `tests/test_evidence_integration.py:51`

```python
# assemble()
if refs.get("package_ref") is not None and assets.get("report_video_ref") is not None:
    report_package = build_report_package(...)
```

Partial 요청 fixture는 `refs.package_ref = null`, `assets.report_video_ref = null`이다. 따라서 `test_partial_scenario`의 `assertIsNone(outputs["report_package"])`는 **gate가 아니라 "입력에 ref가 없었다"를 증명한다.** BLOCK 판정 때문에 Package가 안 만들어졌다는 증거가 아니다.

게이트 자체는 동작한다(직접 호출로 확인: BLOCK report → `None` 반환). 하지만 체크리스트 §Merge 중단 기준 5번(`BLOCK/UNKNOWN인데 Package 생성`)과 §회의에서 볼 핵심 2번의 **핵심 증빙이 자동 검증에 없다.** Partial의 BLOCK report + 유효한 `package_ref`/`report_video_ref`로 `build_report_package()`를 호출해 `None`을 확인하는 테스트 1개를 추가해야 회의에서 "테스트로 보장된다"고 말할 수 있다.

### R-2. `RequirementReport`에 자산·가시성 check가 아예 없다

**위치:** `src/daesingo/evidence/service.py:542-621`

현재 rule set은 번호판 존재 / 사건시각 존재 / 위치 신뢰도 **3개뿐**이다. 그 결과:

- `scope=FINAL_PACKAGE` Report가 `basis.asset_refs`를 **필수로 요구하면서 그 자산에 대해 아무것도 판정하지 않는다.** 계약 §6-5는 refs 포함만 요구하니 문자로는 통과하지만, 의미상 "최종 handoff bundle을 만들 수 있는지 검사"(§4.1)를 하지 않은 FINAL_PACKAGE report다.
- `category`가 `EVIDENCE`/`ASSET`/`DEADLINE`/`REPORT_CONTENT`인 check가 0건이다.
- **§4-모듈4 ④의 4분할이 절반만 구현됐다.** "차량번호 문자열 확정"은 있는데 "Evidence 영상에서 번호판이 실제 식별 가능한가"가 없고, "occurred_at 확정"은 있는데 "영상에 시각 표시가 있는가"가 없다.

체크리스트는 이 둘에 대해 **"1차에서 후자를 판정할 근거가 없으면 `UNKNOWN`으로 낸다"** 고 적었다. 구현은 `UNKNOWN` check를 내는 대신 **check 자체를 생략**했다. 이 차이가 중요한 이유: `UNKNOWN` check가 있으면 `overall`이 `UNKNOWN`이 되어 Package gate가 닫힌다. 생략하면 `WARN`으로 Package가 나온다. **즉 "번호판이 영상에서 보이는지 아무도 확인하지 않은 신고 꾸러미"가 정상 산출물로 나온다.**

Tech Spec §2는 이 항목을 Pending으로 선언했으므로 "몰래 한 것"은 아니다. 다만 **체크리스트와 반대 방향의 결정**이므로 회의에서 명시적으로 승인받아야 한다. 두 선택지:

- (a) 체크리스트대로 `UNKNOWN` check를 낸다 → Happy 시나리오의 Package가 사라진다(회의 데모가 약해진다).
- (b) 지금처럼 생략하고 **"1차 Package는 자산 요건 미검사"** 를 회의록에 못박는다.

어느 쪽이든 지금처럼 조용히 다르게 두면 안 된다.

### R-3. 신고문이 **사용자 기억 단서를 사실처럼 서술**한다

**위치:** `src/daesingo/evidence/service.py:752-757`

실제 출력:

```
"description": "2026-08-24 18:31경 미금역 근처에서 차량(12가 3476)이 백색 실선 구간에서 진로를 변경했습니다."
"report_inputs.location": {"display_text": "미금역 근처", "search_keyword": "미금역"}
```

R2 보정의 취지는 **"위치는 주소가 아니라 사용자 기억 단서임을 유지"** 였다. `EvidenceRecord`에서는 그것을 지켰다(`location.user_hint`, `observability=INFERRED`). 그런데 그 값이 신고문에 들어갈 때는 **아무 단서 없이 사실 서술로 바뀐다.** 사용자가 그대로 안전신문고에 붙여넣는 문장이다.

`흰색 SUV`(confirmed Evidence에 없어서 생략)와 **같은 종류의 문제인데 처리가 정반대다.** 하나는 뺐고 하나는 사실처럼 넣었다. 일관성 결정이 필요하다.

### R-4. `search_keyword`가 confirmed 값을 무시하고 문자열을 잘라 만든다

**위치:** `src/daesingo/evidence/service.py:647-661`

```python
for suffix in (" 근처", " 인근", " 부근"):
    if keyword.endswith(suffix):
        keyword = keyword[: -len(suffix)].strip()
```

두 가지 문제:

1. **`EvidenceRecord.location.search_keyword`가 있어도 쓰지 않는다.** 계약 §5는 `search_keyword`를 "위치 검색용 보조 문자열"로 정의한 confirmed value인데, `_location_snapshot`은 `place_name → address → user_hint → search_keyword` 순으로 **display 후보만** 찾고 keyword는 언제나 display 문자열에서 파생한다.
   재현: `location = {address: "성남시 분당구 미금로 1", search_keyword: "미금역 사거리"}` →
   `{"display_text": "성남시 분당구 미금로 1", "search_keyword": "성남시 분당구 미금로 1"}` — **명시된 검색어를 버리고 주소 전문을 검색어로 쓴다.**
2. 한국어 접미사 3개를 하드코딩한 문자열 수술은 Package assembly 안에 숨은 정책이다. "미금역 근처" 한 케이스에만 맞춘 것이고, `evidence`가 값을 만들지 않는다는 원칙과도 어긋난다.

### R-5. 공용 `validate_mock_pack.py`가 내 모듈 구현에 결합됐다

**위치:** `scripts/validate_mock_pack.py:354-389`

이 스크립트는 **팀 공용**이고 `04_mock_validation_report.md`가 인용하는 Mock Pack의 증빙이다. 여기에 `from daesingo.evidence import assemble`이 들어가면서 다음이 생겼다.

- 다른 Owner(정철원·서어진·신유민)가 자기 fixture를 검사하려고 이 스크립트를 돌렸는데 **내 evidence 코드 때문에 ERROR가 난다.** "fixture 정합성"과 "김준영 구현 회귀"가 한 출력에 섞인다.
- 4개 산출물을 fixture와 **완전 동등(`==`)** 비교한다. Mock PR(`c4fcbf0`)이 아직 머지 전이고 리뷰 중 수정될 수 있는데, fixture 값이 한 글자만 바뀌어도 공용 validator가 깨진다.
- `if "흰색 SUV" in report_text` — 한국어 리터럴 하나를 공용 스크립트의 영구 regression guard로 박았다. 나중에 PM이 "vehicle descriptor를 Evidence input에 정식 추가"를 선택하면 이 줄이 팀 전체를 막는다.
- `04_mock_validation_report.md` §검증 방법의 검사 목록 1~6은 **갱신되지 않았다.** 문서와 스크립트가 지금 서로 다른 말을 한다(§docs/README.md "문서 간 규칙 복제 금지"와 별개로, 인용 문서가 stale이 됐다).
- 새 블록이 파일 안에서 `# 4. known enum checks` **앞**에 삽입돼 섹션 번호가 6 → 4 순으로 뒤집혔다.

**권고:** 이 블록을 `tests/`(또는 `scripts/validate_evidence_impl.py` 같은 별도 스크립트)로 옮기고, 공용 validator는 fixture 검사에만 두는 것. 값 동등 비교는 내 테스트가 이미 하고 있어 중복이기도 하다.

---

## 3. Advisory — 지금 안 고쳐도 되지만 알고는 있어야 한다

| # | 내용 | 위치 | 비고 |
| --- | --- | --- | --- |
| A-1 | **테스트 이름이 검증 내용과 반대다.** `test_known_empty_gps_is_not_treated_as_unknown`은 이름과 달리 known-empty(`OK + []`)가 **예외를 던지는 것**을 정답으로 고정한다. `contract-observation.md` §5·§13은 "known-empty를 `UNKNOWN/ERROR`와 동일시하지 않는다"고 하고, 실제 동작은 `EvidenceContractError`로 **파이프라인 전체를 죽인다**. 좌표에 `[]`가 오는 게 비정상인 건 맞지만, optional 입력 하나 때문에 Evidence 조립 전체가 무너지는 건 §2 원칙 5(실패 경계를 값싸게)와 맞지 않는다. 최소한 이름은 바꿔야 한다. | `tests/test_evidence_integration.py:114` · `service.py:296` | |
| A-2 | **`VisualEvidence.verification != OBSERVED`이면 예외.** `NOT_OBSERVED`는 계약상 유효한 값이다(`04_mock_validation_report.md`가 "NOT_OBSERVED 예시 없음"을 v1 확장 대상으로 적어둔 것 = 값 공간에 존재). 관찰이 없었다는 사실이 Evidence 조립을 죽이는 대신 "event 미확정 + Need"로 흘러야 한다. Tech Spec §2에 없는 제약이므로 최소한 문서화 필요. | `service.py:272-273` | |
| A-3 | **같은 위치 규칙이 branch마다 다른 `code`를 낸다.** PASS/WARN은 `evidence.location.confidence`, UNKNOWN은 `evidence.location.present`. `case`가 check code로 notice를 매핑하면 한쪽을 놓친다. Mock fixture 2건을 그대로 재현하느라 생긴 결과인데, fixture는 서로 다른 시나리오였지 rule 설계가 아니었다. | `service.py:588-620` | |
| A-4 | **`EvidenceValue.source.ref: null`.** 계약 §3은 `ref: ContractRef`(optional 표기 없음)인데 policy_mapping 값은 `null`을 낸다. Mock fixture가 이미 그러므로 **구현이 새로 만든 문제는 아니다.** 다만 계약 Owner가 나이므로 `ref?`로 계약 문구를 정리하거나 실제 ref를 넣어야 한다. | `service.py:262` · 계약 §3 | 계약 정리 대상 |
| A-5 | **`location.source.gps` label_key를 새로 만들었다.** `label_key` 네임스페이스는 계약상 `evidence` 소유이므로 권한 안이지만, B01(CaseView 전달)이 Pending인 상태에서 키를 늘리는 것은 회의에서 공유해야 한다. | `service.py:307` | |
| A-6 | **CI가 새 테스트를 돌리지 않는다.** `.github/workflows/boundary-check.yml`은 `check_boundaries.py`만 실행한다. 17개 테스트는 아무 데서도 강제되지 않는다. 운영진 소유 4개 파일 밖이므로 job 추가는 허용된다(`ownership.md` §6). CI Python은 3.11, 로컬은 3.13 — 코드는 3.11 호환으로 보이나 실제로 돌려본 적은 없다. | `.github/workflows/` | PR에 포함 권장 |
| A-7 | **체크리스트 체크박스 122개가 전부 미체크다.** 셀프 체크 기준으로 쓰라고 만든 문서인데 어느 항목이 충족됐는지 표시가 없다. `PARTIAL_READY`를 주장하려면 이 표가 근거여야 한다. | `first-integration-checklist.md` | 회의 전 작업 |
| A-8 | **`aggregate_usage()`의 반환 shape이 `AnalysisRun.usage_summary`에 결합돼 있다.** `common/runtime` 헬퍼가 `search` 소유 계약의 필드 이름을 따라간다. 지금은 정합 검증용이라 유용하지만, `common`이 domain 계약 모양을 아는 형태다. | `runtime.py:135-182` | 낮음 |
| A-9 | **모든 작업이 미커밋 상태다.** 브랜치 `codex/feat-evidence-first-integration`은 존재하지만 커밋 0건, 전부 working tree에 있다. 리뷰·PR 전에 커밋이 필요하다. | — | |

---

## 4. 체크리스트 대비 이행 현황

| 체크리스트 절 | 판정 | 근거 |
| --- | --- | --- |
| A. Input (10항목) | **충족** | 5개 upstream을 Contract JSON으로 로드, opaque ref 통과, `CorrectionRecord` 미요구, 타 모듈 import 0건 |
| B. Core Flow (6항목) | **부분** | 5건 산출·gate 파생은 충족. Timestamp 우선순위는 경로 1(verified overlay)만 정상, fallback 경로에 B-2 결함 |
| C. Output Contract (11항목) | **부분** | `contract_version`·ref·RFC3339·enum·check code 유일성 충족. `source.ref: null`(A-4)만 잔여 |
| D. Failure / Uncertainty (12항목) | **부분** | ABSTAIN·GPS·필드 부재·precedence·WARN Package 충족. `BLOCK→미생성`은 테스트 미증명(R-1), known-empty는 반대로 구현(A-1) |
| E. State / Lifecycle (5항목) | **충족(경로 수준)** | `supersedes_ref` 경로 존재 + self-ref 방지, workflow 상태 미포함 |
| F. Integration (6항목) | **충족** | JSON 반환, 경계 grep 0건, `check_boundaries.py` PASS |
| G. Test / Evaluation (8항목) | **부분** | Happy/Partial/ABSTAIN/precedence/enum 오타 테스트 존재. WARN→생성 / BLOCK→미생성 쌍 중 후자 미증명(R-1) |
| H. Operational (7항목) | **충족** | JobExecution·UsageRecord invariant, 양방향 링크, 마스킹, `check_boundaries.py` FAIL 0 |
| `RequirementReport` 완료 조건 | **미충족 1항목** | "번호판 문자열 확정 ≠ 영상 내 식별 가능"을 다른 check로 두라는 항목 미이행(R-2) |
| Scenario 표 12행 | **11/12** | `scenario_partial_001` "Package 미생성" 행만 근거가 gate가 아님(R-1) |

---

## 5. PR 권고

에이전트가 낸 PR 산정을 검증했다. **대체로 맞으나 두 가지를 정정한다.**

| 항목 | 에이전트 보고 | 실측 | 비고 |
| --- | --- | --- | --- |
| 변경 경로 | 18개 | **19개** | 신규 15 + 수정 4. `first-integration-checklist.md`를 신규로 세면 19 |
| 라인 수 | +2,289 / -5 | 신규 2,218행 + diff +71/-5 | 신규 2,218행에 **체크리스트 문서(약 350행)가 포함**돼 있다. 순수 구현·테스트는 약 1,500행 |
| 선행 의존 | `c4fcbf0` | 맞다 | `codex/fix-mock-pack-seed-consistency` 미머지 |
| 커밋 분할 3개 | 타당 | 타당 | 아래 수정안 참조 |

**권고 순서**

1. **§1의 Blocker 2건 수정** (B-1 enum, B-2 verification) — 각각 한 줄~몇 줄.
2. **R-1 테스트 1개 추가** — BLOCK report에 유효한 package_ref를 주고 `None`을 확인.
3. **R-5 처리 결정** — `validate_mock_pack.py`의 구현 결합 블록을 별도 스크립트/테스트로 분리할지, 그대로 둘지. 그대로 둔다면 `04_mock_validation_report.md` §검증 방법을 같이 갱신해야 한다.
4. `codex/fix-mock-pack-seed-consistency` → `develop` 머지.
5. 현재 브랜치를 `develop` 기준으로 rebase 후 커밋.
6. PR 생성.

**커밋 분할 (에이전트 제안 3개 → 4개 권장)**

| # | 범위 | 파일 |
| --- | --- | --- |
| 1 | `docs`: Tech Spec + 체크리스트 | `docs/modules/evidence/{tech-spec,first-integration-checklist}.md` |
| 2 | `feat(common)`: runtime 계약 유틸 + 마스킹 | `src/daesingo/common/**`, `tests/test_common_runtime.py` |
| 3 | `feat(evidence)`: 파이프라인 + 공개 API | `src/daesingo/{__init__.py,evidence/**}`, `tests/fixtures/**`, `tests/test_evidence_integration.py`, `scripts/{evidence_fixture_support,run_evidence_fixture}.py` |
| 4 | `chore`: README 3건 + validator 결합 (R-5 결정 반영) | `*/README.md`, `scripts/validate_mock_pack.py` |

4번을 분리하면 R-5를 되돌리기 쉽고, 공용 스크립트 변경이 리뷰에서 눈에 띈다.

**PR 본문에 반드시 넣을 것**

- `PARTIAL_READY` 표기와 Tech Spec §9 링크 — "1차 통합 완료"로 읽히지 않게.
- 신고문에서 `흰색 SUV`가 빠진 이유 (계약 빈틈, 3안 중 미결).
- R-2 결정 결과 (자산·가시성 check 생략을 승인받았는지).
- Pending 접합 7건 (B01/B02/B03/B05/W04, CorrectionRecord, derived asset metadata) — 이 PR이 닫지 않는다는 명시.
- 리뷰어 지정: `case`(유소연) — Consumer 접합 · `readout`(신유민) — abstain/overlay 해석.

---

## 6. 회의 전 남은 작업 요약

- [ ] B-1 `VENDOR_METADATA` enum 교정
- [ ] B-2 conflict 시 `verification` 교정 (Tech Spec §5.1-3 문구와 일치시킬 것)
- [ ] R-1 BLOCK gate 테스트 추가
- [ ] R-2 자산·가시성 check 생략을 회의 안건으로 올리고 결정 기록
- [ ] R-3 신고문의 user_hint 취급 결정 (사실 서술 vs 단서 표기 vs 생략)
- [ ] R-4 `search_keyword` 파생 로직 처리 결정
- [ ] R-5 공용 validator 결합 분리 여부 + `04_mock_validation_report.md` 갱신
- [ ] A-6 CI에 test job 추가
- [ ] A-7 체크리스트 122개 항목 셀프 체크 표시
- [ ] A-9 커밋 후 PR
