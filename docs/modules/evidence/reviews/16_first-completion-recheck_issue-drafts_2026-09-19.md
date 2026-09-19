# 이슈 초안 모음 — 1차 완료 체크리스트 재검토에서 나온 5건

> 상태: **초안 — 미게시.** 게시 여부와 분리 방식은 Owner가 정한다.
>
> 작성일: `2026-09-19` · 기준 체크아웃: `origin/develop` 동기화 후
>
> 계기: [`first-completion-checklist.md`](../first-completion-checklist.md)의 미표시 항목 재확인. 4건 중 3건은 6개 모듈 통합으로 증빙이 확보돼 표시했고, 나머지 1건과 그 과정에서 새로 드러난 항목을 이슈안으로 정리한다.
>
> 이 문서는 **이슈 본문 초안만** 담는다. 확인 근거·실행 기록은 여기에 옮기지 않는다 — 각 이슈를 실제로 올릴 때 해당 시점의 증빙을 붙인다.

## 목록

| # | 제목 | 성격 | 주 담당 | 차단 여부 |
| --- | --- | --- | --- | --- |
| A | baseline 비교에서 P/R의 차이 사유가 기록되지 않는다 | 구현 버그 | 김준영(`evidence`) | 비차단 · 즉시 수정 가능 |
| B | `evidence.location.present` check를 공용 fixture가 반영하지 않았다 | 정본 결정 | 김준영 · 유소연(`case`) | **차단** — 체크리스트 1건이 여기 묶여 있다 |
| C | 공용 Package fixture가 `report-package/v1`에 멈춰 있다 | fixture 갱신(I2) | 유소연 | 비차단 |
| D | real E2E에서 H의 Package가 발행되지 않는다 | 접합 미배선 | 유소연 · 정철원 · 신유민 | 비차단 · 일정 영향 큼 |
| E | `requires-python`이 실제 하한보다 낮다 | 빌드·CI 설정 | 팀 공용 | 비차단 · 잠복 |

재검토 전 후보였던 「기본 `pytest`가 case 테스트를 수집하지 않는다」는 `develop`에서 case 테스트가 `tests/case`로 이동하면서 **이미 해소돼 이슈안에서 뺐다.**

---

## A. `[evidence]` baseline 비교에서 P/R의 차이 사유가 기록되지 않는다

### 제안 제목

`[evidence] first-completion baseline의 comparison.known_differences가 P/R에서 비어 있다 — 불일치는 기록하는데 이유가 없다`

### 한 줄 요약

네 baseline artifact는 공용 Fixture와의 대조 결과를 `comparison`에 남기는데, `scenario_plate_reread_001`과 `scenario_correction_rerun_001`은 `requirement_overalls_match=false`이면서 `known_differences`가 빈 배열이다. **다르다는 사실만 남고 왜 다른지가 증빙에 없다.**

### 배경

`src/daesingo/evidence/mock_integration.py`의 비교 블록은 `known_differences`를 빈 배열로 시작한 뒤 `scenario_happy_001`과 `scenario_unknown_abstain_partial_001`일 때만 설명 문자열을 덧붙인다. P/R 분기가 아예 없다.

체크리스트는 「무엇으로 검증했는지 공개한다」와 「검증 범위 밖 항목을 PASS로 보고하지 않는다」를 Merge 중단 기준으로 두고 있다. 불일치를 침묵으로 남기는 것은 그 기준과 맞지 않는다. 실제로 이번 재검토에서 미표시로 남은 항목 1건의 직접 원인이 이 빈 배열이다 — 차이의 사유가 artifact에 없어 체크 근거로 쓸 수 없었다.

### 제안

1. `known_differences`를 시나리오별 하드코딩이 아니라 **비교 결과에서 파생**시킨다. 최소한 `requirement_overalls_match=false`인데 설명이 0건이면 그 자체를 오류로 드러낸다.
2. P/R의 실제 차이(EVIDENCE scope check 구성과 overall 등급 차이)를 사유 문자열로 남긴다.
3. 같은 방식으로 `time_statuses_match`·package count 불일치도 설명 없이 통과하지 않게 한다.

### 완료 조건

- 네 baseline 중 어느 것이든 `*_match=false`이면 대응하는 사유가 `known_differences`에 반드시 존재한다.
- 사유 없는 불일치를 만들면 테스트가 실패한다(회귀 검사 추가).

---

## B. `[evidence/case]` `evidence.location.present` check를 공용 fixture가 반영하지 않았다

### 제안 제목

`[evidence/case] D1 이후 EVIDENCE scope에 추가된 evidence.location.present를 공용 Mock이 반영하지 않았다 — 어느 쪽이 정본인가`

### 한 줄 요약

`policy/requirement-rules-v4`의 EVIDENCE scope는 위치 부재를 `WARN`으로 잡는 check를 포함한다. 그런데 공용 `data/mock/evidence/`의 P·R은 이 check가 없는 구성으로 최종 `PASS`를 기대하고, 공용 `CaseView`도 같은 값을 그대로 담고 있다. **같은 시나리오에 두 개의 정답이 있다.**

### 배경

D1(`ADR-EVIDENCE-003`, 이슈 #48)로 위치 부재를 `WARN`으로 처리하는 방향이 확정되면서 EVIDENCE scope에 위치 check가 들어왔다. 이후 공용 Fixture는 재렌더되지 않았다.

그 결과 체크리스트 `RequirementReport` 절의 「H PASS · U WARN · P UNKNOWN→PASS · R WARN→PASS」 줄이 현재 구현과 어긋난다. 구현을 따르면 P·R의 최종 등급은 `PASS`가 아니라 `WARN`이다. 이 한 줄 때문에 체크리스트 1건이 미표시로 남아 있다.

공용 `CaseView`도 같은 값을 담고 있어서, 이 차이는 evidence 안에서 끝나지 않고 `case`의 표시 규칙과 `web`의 화면 상태까지 이어진다.

### 정해야 할 것

둘 중 하나를 고른다. 가운데는 없다.

1. **구현이 정본** — 위치 없는 사건의 EVIDENCE scope는 `WARN`이 맞다. 공용 evidence fixture와 공용 `CaseView`를 재렌더하고, 체크리스트 해당 줄을 정정한다.
2. **공용 Fixture가 정본** — 위치는 EVIDENCE scope의 판정 대상이 아니고 `FINAL_PACKAGE`에서만 본다. v4 catalog에서 EVIDENCE 쪽 위치 check를 뺀다.

제안은 1번이다. D1이 이미 「위치 부재를 숨기지 않고 WARN으로 드러낸다」를 택했고, EVIDENCE scope에서만 그 사실을 감추면 사용자가 위치 없는 상태를 늦게 알게 된다. 다만 **이 결정은 `case`·`web`의 표시 규칙을 바꾸므로 evidence 단독으로 정하지 않는다.**

### 완료 조건

- 채택안이 기록되고, evidence 구현·공용 evidence fixture·공용 `CaseView`·체크리스트 네 곳의 값이 한 방향으로 일치한다.
- 체크리스트의 마지막 미표시 항목이 해소된다.

---

## C. `[mock]` 공용 Package fixture가 `report-package/v1`에 멈춰 있다

### 제안 제목

`[mock] 공용 evidence fixture의 ReportPackage가 report-package/v1·policy/package-assembly-v1을 쓴다 — Final은 v1.1이다`

### 한 줄 요약

`report-package` Final 계약은 `v1.1`이고 채택된 신고문 정책은 `safety-report-policy/v1.1`인데, 공용 `data/mock/evidence/`의 Package 두 건은 아직 `report-package/v1`과 `policy/package-assembly-v1`을 참조한다. 공용 검증 스크립트는 이 어긋남을 잡지 못한다.

### 배경

이 항목은 새로 발견된 문제가 아니라 [`first-completion-result.md`](../first-completion-result.md)가 **I2**로 이미 분류해 둔 fixture 재렌더 대기 건이다. 이번 재검토에서 아직 그대로임을 확인해 이슈로 올린다.

문제가 되는 지점은 값 자체보다 **검증이 이 drift를 통과시킨다**는 점이다. 계약 버전이 올라가도 fixture가 구버전 문자열을 그대로 들고 있으면 아무 검사도 실패하지 않는다. 같은 일이 다음 버전업에서 또 생긴다.

### 제안

1. 공용 Package fixture를 `report-package/v1.1`과 `safety-report-policy/v1.1` 기준으로 재렌더한다. U는 장소 없는 template을 함께 반영한다.
2. `validate_mock_pack.py`에 **계약 버전 문자열이 해당 계약 문서의 현재 Contract Version과 일치하는지** 보는 검사를 추가한다. 이번 건에 한정하지 않고 fixture가 참조하는 모든 계약 버전에 적용한다.

### 완료 조건

- 공용 Package fixture의 계약·정책 참조가 Final과 일치한다.
- 계약 버전만 올리고 fixture를 두면 공용 검증이 실패한다.

---

## D. `[case/evidence/recording/readout]` real E2E에서 H의 Package가 발행되지 않는다

### 제안 제목

`[case/evidence] real E2E에서 scenario_happy_001의 ReportPackage가 만들어지지 않는다 — situation_response와 관찰 fact 미배선`

### 한 줄 요약

`case`가 evidence 공개 함수를 실제로 호출하는 경로에서 H는 `CaseView`가 `READY`까지 가는데 **Package는 나오지 않는다.** `FINAL_PACKAGE`가 `UNKNOWN`이고 조립이 `package.requirement_not_ready`로 막힌다. Mock adapter 경로에서는 Package가 나오므로, 두 경로의 결과가 갈린다.

### 배경

막히는 check는 네 개다. 원인은 각각 다르고 담당도 다르다.

| 막히는 check | 왜 `UNKNOWN`인가 | 누가 채워야 하나 |
| --- | --- | --- |
| `package.evidence.situation_response` | `case`에 사용자 응답(확인/정정/모르겠음)을 수집하는 경로가 아직 없어 `None`으로 넘어간다 | 유소연(`case` intake) |
| `package.vehicle.plate_visible_in_report_video` | 신고영상에서 번호판이 보이는지에 대한 관찰 fact가 전달되지 않는다(I4) | 신유민(`readout`) · 정철원(`recording`) |
| `package.time.overlay_visible` | 같은 이유로 시각 표시 관찰 fact가 없다(I4) | 신유민 · 정철원 |
| `package.report.content_length` | 앞의 값들이 없어 신고문 렌더 자체가 성립하지 않는다 | 위 항목의 파생 |

`evidence`는 이 상태를 **실패가 아니라 정보 부족으로** 다루고 있다 — `UNKNOWN`을 내고 Package를 만들지 않는다. 설계대로 동작하는 것이므로 evidence 쪽 수정 대상은 없다.

이 건을 이슈로 올리는 이유는 버그라서가 아니라, **「1차 통합 완료」를 어느 경로 기준으로 말할지가 갈리기 때문**이다. baseline 경로만 보면 H/U 모두 Package가 나오지만 real 경로에서는 안 나온다. 회의에서 이 둘을 섞어 말하면 준비 상태를 실제보다 앞서 보고하게 된다.

### 제안

1. `situation_response` 수집 경로를 `case`가 먼저 연결한다 — 나머지 셋보다 의존이 적고 UI 없이도 값 주입이 가능하다.
2. I4 관찰 fact 두 건의 생산·전달 경계를 `readout`·`recording`·`case` 사이에서 확정한다. **`evidence`가 이 값을 추측해 채우지 않는다**는 경계는 유지한다.
3. 그때까지 대외 보고 문구에서 **baseline 경로와 real 경로를 항상 구분해 적는다.**

### 완료 조건

- real E2E에서 H의 `FINAL_PACKAGE`가 `PASS`/`WARN`에 도달하고 Package가 발행된다.
- 또는 도달하지 못하는 이유가 남은 담당·일정과 함께 기록된다.

---

## E. `[infra]` `requires-python`이 실제 하한보다 낮다

### 제안 제목

`[infra] pyproject의 requires-python=">=3.10"이 실제 하한과 다르다 — 최소 3.12가 필요하다`

### 한 줄 요약

루트 `pyproject.toml`은 `requires-python = ">=3.10"`인데, `src/daesingo/search`가 `typing.override`(3.12+)와 `typing.Self`·`typing.assert_never`(3.11+)를 쓴다. 선언대로 3.10이나 3.11에서 설치·실행하면 import 단계에서 깨진다.

### 배경

[`04_mock_validation_report.md`](../../../mock/04_mock_validation_report.md) 12차 갱신의 Issue Log가 이미 「`requires-python`이 `>=3.10`으로 남아있지만 실제 `>=3.11` 필요」로 적어 둔 항목이다. 다만 **실제 하한은 3.11이 아니라 3.12**다 — `typing.override`가 3.12에서 추가됐기 때문이다.

지금 이 어긋남이 드러나지 않는 이유는 CI가 테스트를 돌리지 않기 때문이다. `boundary-check` 워크플로는 Python 3.11을 쓰지만 검사 스크립트가 프로젝트 모듈을 import하지 않는 정적 검사라 통과한다. 새로 합류하는 사람이나 배포 환경이 선언을 믿고 3.10/3.11을 잡으면 그때 처음 깨진다.

이 항목은 `pyproject.toml` 3-way 충돌(recording/search/eval-harness가 각자 다른 빌드 백엔드와 Python 버전을 선언했던 건)의 잔재이기도 하다. 그 최종 수렴안은 아직 팀 논의로 남아 있다.

### 제안

1. `requires-python`을 실제 하한에 맞춘다. 3.12를 올릴지, `typing.override`를 걷어내고 3.11로 맞출지는 팀이 정한다.
2. 같은 자리에서 빌드 백엔드 수렴안도 함께 정리한다.
3. CI에 테스트 실행 job을 추가해 선언한 최소 버전에서 실제로 도는지 확인한다. 지금은 `boundary-check`만 돌아서 이런 종류의 어긋남이 잡히지 않는다.

### 완료 조건

- 선언한 최소 Python 버전에서 전체 테스트가 통과한다.
- 그 사실이 CI로 확인된다.

---

## 게시할 때 고려할 것

- **A는 evidence 단독**이라 이슈 없이 바로 고쳐도 된다. 다만 B의 근거로 쓰이므로 B보다 먼저 처리한다.
- **B가 유일한 차단 항목**이다. 체크리스트의 마지막 미표시 1건이 여기에만 묶여 있다.
- **C는 B와 같은 fixture를 건드린다.** 따로 올리면 같은 파일을 두 번 재렌더하게 되니 한 이슈로 합치거나 작업 순서를 묶는다.
- **D는 evidence가 고칠 것이 없다.** 담당이 셋으로 갈리므로 이슈를 쪼개는 편이 낫다.
- **E는 evidence 범위 밖**이다. 팀 공용 채널로 올린다.
