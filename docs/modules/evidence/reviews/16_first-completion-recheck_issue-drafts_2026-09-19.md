# 1차 완료 체크리스트 재검토 — 처리 시점별 분류

> 상태: **초안 — 미게시.** 게시 여부와 분리 방식은 Owner가 정한다.
>
> 작성일: `2026-09-19` · 기준 체크아웃: `origin/develop` 동기화 후
>
> 계기: [`first-completion-checklist.md`](../first-completion-checklist.md)의 미표시 항목 재확인. 4건 중 3건은 6개 모듈 통합으로 증빙이 확보돼 표시했고, 나머지 1건과 그 과정에서 새로 드러난 항목을 정리한다.
>
> 이 문서는 **항목 본문과 분류만** 담는다. 확인 근거·실행 기록은 여기에 옮기지 않는다 — 각 항목을 실제로 올릴 때 그 시점의 증빙을 붙인다.

## 분류 기준

real E2E 작업을 기준선으로 놓고 세 갈래로 나눈다.

- **1부 — real E2E 착수 전에 닫는다.** 지금 상태 위에 다른 사람이 코드를 쌓으면 나중에 되돌리는 비용이 커지는 것들. 미루는 값이 매일 오른다.
- **2부 — real E2E와 함께, 또는 그 뒤에.** 작업이 끝난 뒤 체크리스트를 다시 확인하면 자연히 정리되는 것들.
- **3부 — 이슈 영역이 아니다.** 다른 PR에서 이미 진행 중이라 새로 올리지 않고, 나중에 됐는지만 확인한다.

| 부 | # | 항목 | 성격 | 주 담당 |
| --- | --- | --- | --- | --- |
| 1 | P1 | `real_e2e`가 `location_hint`·`gps_observation`을 넘기지 않는다 | 배선 누락 | 유소연(`case`) |
| 1 | P2 | baseline 비교에서 P/R의 차이 사유가 기록되지 않는다 | 구현 버그 | 김준영(`evidence`) |
| 1 | P3 | `evidence.location.present` 정본 결정 | **정본 결정 · 유일한 차단 항목** | 김준영 · 유소연 · 신유민(`web`) |
| 2 | P4 | real E2E에서 H의 Package가 발행되지 않는다 | 접합 미배선 | 유소연 · 정철원 · 신유민 |
| 2 | P5 | 공용 Package fixture가 `report-package/v1`에 멈춰 있다 | fixture 갱신(I2) | 유소연 |
| 3 | V1 | Python 버전·빌드 환경 통일 | **[PR #82](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/82) 진행 중 — 머지 후 확인만** | 김준영(팀 공용) |

권장 순서는 **P1 → P2 → P3**이다. P1과 P2가 P3을 논의할 재료를 만든다 — P1 없이는 「위치가 있는 정상 케이스」를 실제로 볼 수 없고, P2 없이는 P/R이 왜 다른지를 남에게 보여줄 근거가 없다.

재검토 전 후보였던 「기본 `pytest`가 case 테스트를 수집하지 않는다」는 `develop`에서 case 테스트가 `tests/case`로 이동하면서 **이미 해소돼 뺐다.**

---

# 1부 — real E2E 착수 전에 닫는다

## P1. `[case]` `real_e2e`가 `location_hint`·`gps_observation`을 넘기지 않는다

### 제안 제목

`[case] real_e2e.py가 assemble_evidence에 location_hint/gps_observation을 전달하지 않는다 — H의 EVIDENCE가 불필요하게 WARN으로 내려간다`

### 한 줄 요약

`assemble_evidence()`는 이미 `location_hint`와 `gps_observation` 파라미터를 받는다. 그런데 `src/daesingo/case/real_e2e.py`의 호출부는 **둘 다 전달하지 않는다.** 공용 case fixture에는 `hints.location` 값이 들어 있는데도 real 경로에서만 위치가 비어, EVIDENCE scope가 `evidence.location.present` 하나 때문에 내려간다.

### 배경

`gps_observation`은 호출부에 `None`으로 명시돼 있고 `location_hint`는 인자 자체가 빠져 있다. 모듈 docstring의 「알려진 단순화」는 `time_source_candidates`와 `situation_response`/`observation_facts`를 적어 두었지만 **위치는 그 목록에 없다** — 의도한 단순화가 아니라 누락으로 보인다.

이걸 먼저 고쳐야 하는 이유는 값 하나가 틀려서가 아니다. 지금 상태로 real E2E 결과를 팀이 보면 **「H는 원래 WARN」이라고 결론 내고 그 위에 notice·화면 상태·UX를 설계한다.** 되돌릴 때 evidence가 아니라 `case`·`web`이 비용을 치른다.

계약 변경이 필요 없다. 이미 있는 파라미터에 이미 있는 값을 넘기는 일이다.

### 제안

1. `real_e2e.py`가 case의 `hints.location`을 `location_hint`로 전달한다.
2. `gps_observation`도 `recording`이 내는 `Observation<Coordinate>`로 연결한다. 연결할 수 없다면 `None`으로 두되 **그 사유를 「알려진 단순화」 목록에 적는다.**
3. 위치가 채워진 뒤의 EVIDENCE scope 결과를 P3 논의의 입력으로 쓴다.

### 완료 조건

- real 경로에서 H의 `EvidenceRecord.location`이 채워진다.
- 여전히 비는 값이 있다면 그 사유가 코드 주석이 아니라 「알려진 단순화」 목록에 있다.

---

## P2. `[evidence]` baseline 비교에서 P/R의 차이 사유가 기록되지 않는다

### 제안 제목

`[evidence] first-completion baseline의 comparison.known_differences가 P/R에서 비어 있다 — 불일치는 기록하는데 이유가 없다`

### 한 줄 요약

네 baseline artifact는 공용 Fixture와의 대조 결과를 `comparison`에 남기는데, `scenario_plate_reread_001`과 `scenario_correction_rerun_001`은 requirement overall이 불일치로 기록되면서 `known_differences`가 빈 배열이다. **다르다는 사실만 남고 왜 다른지가 증빙에 없다.**

### 배경

`src/daesingo/evidence/mock_integration.py`의 비교 블록은 `known_differences`를 빈 배열로 시작한 뒤 `scenario_happy_001`과 `scenario_unknown_abstain_partial_001`일 때만 설명 문자열을 덧붙인다. P/R 분기가 아예 없다.

체크리스트는 「무엇으로 검증했는지 공개한다」와 「검증 범위 밖 항목을 PASS로 보고하지 않는다」를 Merge 중단 기준으로 둔다. 불일치를 침묵으로 남기는 것은 그 기준과 맞지 않는다. 실제로 이번 재검토에서 미표시로 남은 항목 1건의 직접 원인이 이 빈 배열이다 — 차이의 사유가 artifact에 없어 체크 근거로 쓸 수 없었다.

**P3보다 먼저 해야 한다.** P3은 다른 모듈 Owner의 합의가 필요한데, 지금은 「무엇이 왜 다른가」를 보여줄 문서가 없다.

### 제안

1. `known_differences`를 시나리오별 하드코딩이 아니라 **비교 결과에서 파생**시킨다. 최소한 불일치가 있는데 설명이 0건이면 그 자체를 오류로 드러낸다.
2. P/R의 실제 차이(EVIDENCE scope check 구성과 overall 등급 차이)를 사유 문자열로 남긴다.
3. 같은 방식으로 time status·package count 불일치도 설명 없이 통과하지 않게 한다.

### 완료 조건

- 네 baseline 중 어느 것이든 불일치가 있으면 대응하는 사유가 `known_differences`에 반드시 존재한다.
- 사유 없는 불일치를 만들면 테스트가 실패한다(회귀 검사 추가).

---

## P3. `[evidence/case/web]` `evidence.location.present` 정본 결정

### 제안 제목

`[evidence/case/web] D1 이후 EVIDENCE scope에 추가된 evidence.location.present를 공용 Mock이 반영하지 않았다 — 어느 쪽이 정본인가`

### 한 줄 요약

`policy/requirement-rules-v4`의 EVIDENCE scope는 위치 부재를 `WARN`으로 잡는 check를 포함한다. 그런데 공용 `data/mock/evidence/`의 P·R은 이 check가 없는 구성으로 최종 `PASS`를 기대하고, 공용 `CaseView`도 같은 값을 그대로 담고 있다. **같은 시나리오에 두 개의 정답이 있다.**

### 배경

D1(`ADR-EVIDENCE-003`, 이슈 #48)로 위치 부재를 `WARN`으로 처리하는 방향이 확정되면서 EVIDENCE scope에 위치 check가 들어왔다. 이후 공용 Fixture는 재렌더되지 않았다.

그 결과 체크리스트 `RequirementReport` 절의 「H PASS · U WARN · P UNKNOWN→PASS · R WARN→PASS」 줄이 현재 구현과 어긋난다. 구현을 따르면 P·R의 최종 등급은 `PASS`가 아니라 `WARN`이다. **체크리스트에 남은 마지막 미표시 1건이 여기에만 묶여 있다.**

공용 `CaseView`도 같은 값을 담고 있어서, 이 차이는 evidence 안에서 끝나지 않고 `case`의 표시 규칙과 `web`의 화면 상태까지 이어진다. 미루면 되돌릴 곳이 evidence 구현·공용 evidence fixture·공용 `CaseView`·web 네 곳으로 늘어나고, 그 셋은 evidence 소유가 아니다.

### 정해야 할 것

둘 중 하나를 고른다. 가운데는 없다.

1. **구현이 정본** — 위치 없는 사건의 EVIDENCE scope는 `WARN`이 맞다. 공용 evidence fixture와 공용 `CaseView`를 재렌더하고, 체크리스트 해당 줄을 정정한다.
2. **공용 Fixture가 정본** — 위치는 EVIDENCE scope의 판정 대상이 아니고 `FINAL_PACKAGE`에서만 본다. v4 catalog에서 EVIDENCE 쪽 위치 check를 뺀다.

제안은 1번이다. D1이 이미 「위치 부재를 숨기지 않고 WARN으로 드러낸다」를 택했고, EVIDENCE scope에서만 그 사실을 감추면 사용자가 위치 없는 상태를 늦게 알게 된다. 다만 **이 결정은 `case`·`web`의 표시 규칙을 바꾸므로 evidence 단독으로 정하지 않는다.**

P1을 먼저 처리하면 「위치가 있는 케이스」와 「없는 케이스」를 실제 결과로 나란히 놓고 논의할 수 있다.

### 완료 조건

- 채택안이 기록되고, evidence 구현·공용 evidence fixture·공용 `CaseView`·체크리스트 네 곳의 값이 한 방향으로 일치한다.
- 체크리스트의 마지막 미표시 항목이 해소된다.

---

# 2부 — real E2E와 함께, 또는 그 뒤에

## P4. `[case/evidence/recording/readout]` real E2E에서 H의 Package가 발행되지 않는다

### 제안 제목

`[case/evidence] real E2E에서 scenario_happy_001의 ReportPackage가 만들어지지 않는다 — situation_response와 관찰 fact 미배선`

### 한 줄 요약

`case`가 evidence 공개 함수를 실제로 호출하는 경로에서 H는 `CaseView`가 `READY`까지 가는데 **Package는 나오지 않는다.** `FINAL_PACKAGE`가 `UNKNOWN`이라 조립이 막힌다. Mock adapter 경로에서는 Package가 나오므로, 두 경로의 결과가 갈린다.

### 배경

막히는 check는 세 갈래이고 담당이 다르다. P1의 위치 배선은 여기서 제외했다 — 그건 1부로 뺐다.

| 막히는 check | 왜 `UNKNOWN`인가 | 누가 채워야 하나 |
| --- | --- | --- |
| `package.evidence.situation_response` | `case`에 사용자 응답(확인/정정/모르겠음)을 수집하는 경로가 아직 없어 `None`으로 넘어간다 | 유소연(`case` intake) |
| `package.vehicle.plate_visible_in_report_video` | 신고영상에서 번호판이 보이는지에 대한 관찰 fact가 전달되지 않는다(I4) | 신유민(`readout`) · 정철원(`recording`) |
| `package.time.overlay_visible` | 같은 이유로 시각 표시 관찰 fact가 없다(I4) | 신유민 · 정철원 |
| `package.report.content_length` | 앞의 값들이 없어 신고문 렌더 자체가 성립하지 않는다 | 위 항목의 파생 |

`evidence`는 이 상태를 **실패가 아니라 정보 부족으로** 다룬다 — `UNKNOWN`을 내고 Package를 만들지 않는다. 설계대로 동작하는 것이므로 evidence 쪽 수정 대상은 없다.

이 건이 2부인 이유는 **이것이 real E2E 작업 그 자체**이기 때문이다. 작업이 끝나면 체크리스트의 해당 항목을 다시 확인하는 것으로 정리된다.

다만 착수 전에 팀에 한 가지는 공유해야 한다 — **「real 경로에서 Package가 안 나오는 것은 evidence 버그가 아니다」**. 이 말을 안 하고 결과만 보이면 회의에서 evidence 결함으로 읽힌다.

### 제안

1. `situation_response` 수집 경로를 `case`가 먼저 연결한다 — 나머지 둘보다 의존이 적고 UI 없이도 값 주입이 가능하다.
2. I4 관찰 fact 두 건의 생산·전달 경계를 `readout`·`recording`·`case` 사이에서 확정한다. **`evidence`가 이 값을 추측해 채우지 않는다**는 경계는 유지한다.
3. 그때까지 대외 보고 문구에서 **baseline 경로와 real 경로를 항상 구분해 적는다.**

### 완료 조건

- real E2E에서 H의 `FINAL_PACKAGE`가 `PASS`/`WARN`에 도달하고 Package가 발행된다.
- 또는 도달하지 못하는 이유가 남은 담당·일정과 함께 기록된다.

---

## P5. `[mock]` 공용 Package fixture가 `report-package/v1`에 멈춰 있다

### 제안 제목

`[mock] 공용 evidence fixture의 ReportPackage가 report-package/v1·policy/package-assembly-v1을 쓴다 — Final은 v1.1이다`

### 한 줄 요약

`report-package` Final 계약은 `v1.1`이고 채택된 신고문 정책은 `safety-report-policy/v1.1`인데, 공용 `data/mock/evidence/`의 Package 두 건은 아직 `report-package/v1`과 `policy/package-assembly-v1`을 참조한다. 공용 검증 스크립트는 이 어긋남을 잡지 못한다.

### 배경

새로 발견된 문제가 아니라 [`first-completion-result.md`](../first-completion-result.md)가 **I2**로 이미 분류해 둔 fixture 재렌더 대기 건이다. 이번 재검토에서 아직 그대로임을 확인했다.

문제가 되는 지점은 값 자체보다 **검증이 이 drift를 통과시킨다**는 점이다. 계약 버전이 올라가도 fixture가 구버전 문자열을 그대로 들고 있으면 아무 검사도 실패하지 않는다. 같은 일이 다음 버전업에서 또 생긴다.

2부에 두는 이유는 두 가지다. real E2E가 Package를 못 만드는 동안은 v1.1 Package를 소비하는 쪽이 없어 급하지 않고, **P3과 같은 fixture를 건드리므로 P3 결정 전에 하면 두 번 재렌더하게 된다.**

### 제안

1. 공용 Package fixture를 `report-package/v1.1`과 `safety-report-policy/v1.1` 기준으로 재렌더한다. U는 장소 없는 template을 함께 반영한다. **P3과 한 번에 처리한다.**
2. `validate_mock_pack.py`에 **계약 버전 문자열이 해당 계약 문서의 현재 Contract Version과 일치하는지** 보는 검사를 추가한다. 이번 건에 한정하지 않고 fixture가 참조하는 모든 계약 버전에 적용한다.

### 완료 조건

- 공용 Package fixture의 계약·정책 참조가 Final과 일치한다.
- 계약 버전만 올리고 fixture를 두면 공용 검증이 실패한다.

---

# 3부 — 이슈 영역이 아니다 · 완료 확인만

여기 있는 항목은 **새 이슈로 올리지 않는다.** 다른 PR에서 이미 작업 중이라, 나중에 반영됐는지 확인하는 것으로 끝낸다.

## V1. Python 버전·빌드 환경 통일 — [PR #82](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/82)

> **상태: PR #82 `chore/python-3.12-uv-env` 진행 중(OPEN).** 아래는 머지 후 확인할 내용이며 이슈 제안이 아니다.

재검토 시점의 지적은 「루트 `pyproject.toml`이 `requires-python = ">=3.10"`인데 `src/daesingo/search`가 `typing.override`를 써서 실제 하한은 3.12」였다. [`04_mock_validation_report.md`](../../../mock/04_mock_validation_report.md) 12차 갱신 Issue Log가 이 항목을 「실제 `>=3.11` 필요」로 적어 둬서, **PR이 3.11로 맞추고 끝내지 않는지**가 걱정거리였다.

PR #82을 확인한 결과 그 우려는 해당하지 않는다. 팀 표준을 **3.12**로 잡았고, 재검토에서 지적한 세 갈래를 모두 덮는다.

| 재검토에서 지적한 것 | PR #82의 처리 |
| --- | --- |
| `requires-python`이 실제 하한보다 낮다 | `>=3.10` → **`>=3.12`**. `.python-version`도 `3.12`로 추가 |
| `pyproject.toml` 3-way 충돌의 수렴안이 없다 | root `pyproject.toml`을 Python 설정 SoT로 확정하고, 「모듈별 별도 Python 버전·root pyproject를 만들지 않는다」를 운영 기준으로 명문화 |
| CI에 테스트 실행 job이 없어 이 어긋남이 잡히지 않는다 | `boundary-check`를 Python 3.12 + `uv sync --locked` 기준으로 바꾸고 **전체 pytest**와 Mock Pack 검증을 job에 추가 |

그 밖에 로컬 개발환경이 uv + project-local `.venv`로, 테스트 의존성이 `[project.optional-dependencies].test` → `[dependency-groups].dev`로 옮겨진다.

### 머지 후 확인할 것

- [ ] PR #82이 머지됐고 `requires-python`이 `>=3.12`다.
- [ ] CI의 전체 pytest가 실제로 돌고 통과한다. 이 job이 생기면 앞으로 같은 종류의 어긋남이 자동으로 잡힌다.
- [ ] **체크리스트의 실행 명령을 uv 기준으로 갱신한다.** [`first-completion-checklist.md`](../first-completion-checklist.md) §검증 명령의 재확인 블록은 아직 `$env:PYTHONPATH='src'`와 `python -m pytest` 기준이다. 정본이 `uv run pytest`로 바뀌므로 evidence 쪽 문서도 맞춰야 한다 — **이 항목만 evidence가 직접 해야 할 후속이다.**
- [ ] `pip install -e .[test]`를 쓰던 안내가 남아 있지 않은지 본다. extras가 dependency group으로 옮겨져 그 명령은 더 이상 동작하지 않는다.

---

## 게시할 때 고려할 것

- **P2는 evidence 단독**이라 이슈 없이 바로 고쳐도 된다. 다만 P3의 근거로 쓰이므로 P3보다 먼저 처리한다.
- **P1은 `case` 소유 파일**이다. evidence가 직접 고치지 않고 유소연에게 넘긴다. 분량이 작아 이슈보다 직접 전달이 빠를 수 있다.
- **P3이 유일한 차단 항목**이다. 체크리스트의 마지막 미표시 1건이 여기에만 묶여 있고, 되돌릴 곳이 세 모듈에 걸쳐 있다.
- **P5는 P3과 같은 fixture를 건드린다.** 따로 올리면 같은 파일을 두 번 재렌더하게 되니 한 이슈로 합치거나 작업 순서를 묶는다.
- **P4는 evidence가 고칠 것이 없다.** 담당이 셋으로 갈리므로 이슈를 쪼개는 편이 낫다.
- **V1은 올리지 않는다.** [PR #82](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/82)이 세 갈래를 모두 덮고 있어, 머지된 뒤 확인 항목만 본다. 다만 **체크리스트 실행 명령의 uv 전환은 evidence가 직접 해야 하는 후속**이라 그 하나는 잊지 않는다.
