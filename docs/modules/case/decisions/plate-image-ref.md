# 번호판 이미지 다운로드 주소 — `package.plate_image_ref`

> 2026-11-04(판본 2026-11-05) · 요청 [#569](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/569)(김대원, web) · CaseView 계약 `case-view/v1.11` · web 버튼 PR [#570](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/570)

## 1. 문제

- 11/3 PM 확인에서 번호판 이미지 별도 다운로드를 RC에 넣기로 했다(담당 web).
- 서버는 이미 번호판 이미지를 만든다. `PLATE_IMAGE_EXPORT`가 자동 발주되고, 만들어지면 evidence가 ReportPackage `assets.plate_image_ref`에 싣는다(`src/daesingo/evidence/requirements.py`). 내려받는 API `GET /cases/{case_id}/assets/{asset_ref}`도 `image/png`를 내려 준다.
- 하지만 CaseView `package`에는 영상 주소(`artifact_ref`)만 있었다. 그래서 web은 번호판 이미지를 받을 주소를 알 수 없었다.

## 2. 결정

1. **`package.plate_image_ref: string | null`을 추가한다.** 값은 `ReportPackage.assets.plate_image_ref.ref`를 그대로 옮긴 것이다. `artifact_ref`(`assets.report_video_ref.ref`)와 같은 방식이다.
2. **키가 없으면 `null`이다.** evidence는 PLATE_IMAGE asset이 `AVAILABLE`일 때만 이 키를 싣는다. 번호판을 못 읽었거나, 생성에 실패했거나, 아직 생성 중이면 키가 없다. case는 이 셋을 구분하지 않는다. 생성 실패는 이미 `recording.plate_image_export_failed` notice가 알린다.
3. **`package`가 non-null일 때 키는 항상 있다.** `package`가 `null`이면 이 값도 없다.
4. **버전은 `case-view/v1.11`로 올린다.** 이 계약은 필드를 추가할 때마다 minor를 올려 왔고(v1.3 · v1.7 · v1.9 · v1.10), 「버전 유지」는 필드 변경이 없을 때만 썼다. 같은 판본 안에 키가 있는 응답과 없는 응답이 섞이지 않게 한다. 호환 확장이라 web은 버전을 검사하지 않고, 키가 없는 v1.10 이하 응답은 `null`로 다룬다(#570). web 타입 파일(`apps/web/src/contracts/caseView.ts`, web 소유)에서 버전은 1행 주석에만 있어 런타임 · 타입 검사에 영향이 없다 — 주석은 web이 맞춘다. 처음(2026-11-04)에는 v1.10 유지로 적었다가 관례에 맞춰 고쳤다.

## 3. 범위 밖

- 다운로드 버튼과 파일 이름 — web 소유(#570). API는 `daesingo_asset.png`라는 이름으로 내려 준다.
- 번호판 이미지를 만드는 조건과 시점 — evidence · recording 소유.

## 4. 테스트

- `tests/case/test_package_plate_image_ref.py`: mock 두 시나리오에서 ref를 그대로 옮기는지, 키가 없으면 `null`인지 확인한다(`artifact_ref`는 영향이 없다).
- `tests/case/test_scenario_happy_smoke.py`: 정답 fixture와 대조한다.
- case mock fixture(`data/mock/case/scenario_happy_001.json` · `scenario_unknown_abstain_partial_001.json`)의 `package`에 같은 값을 넣었다.
