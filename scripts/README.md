# scripts

팀 공용 스크립트 자리.

## `check_boundaries.py` — 모듈 경계 · 계약 정합성 점검

```bash
python scripts/check_boundaries.py                  # 전체
python scripts/check_boundaries.py --only=contracts  # 계약만
python scripts/check_boundaries.py --only=boundaries # 모듈 경계만
```

**규칙을 여기서 정하지 않는다.** 아래는 현재 스크립트가 실제 구현한 검사 범위다. 전체 의미 검증과 다르다.

| 검사 | 명세 원문 |
| --- | --- |
| 모듈 경계 금지 문자열 | `docs/management/ownership.md` §6 |
| 헤더 3개(Status/Architecture Contract/Contract Version)의 첫 1,500자 내 존재 · 제목의 번호 · 타입 언급/제목 coverage | `docs/architecture/module-architecture.md` §5-1 |
| 위반유형 baseline enum | `docs/architecture/module-architecture.md` §3-5 |
| 보정 이력 | `docs/architecture/contracts/adr/adr-consistency-2026-09.md` |

`FAIL`은 위반이고 `NOTE`는 확인 대상이다. 골격 단계에서 코드가 없는 모듈은 `NOTE`로만 나온다.

`enum` 검사의 변형 목록(`LANE_CHANGE` → `SOLID_LINE_LANE_CHANGE` 등)은 실제로 드리프트가 발생한 값만 넣는다. 현재는 baseline 줄과 SOLID_LINE_LANE_CHANGE의 존재 및 LANE_CHANGE 변형을 검사한다. 다른 임의 enum 오타를 모두 검출하지 않는다.

**알려진 한계:** 포인터가 올바른 행인지, Accepted/Related ADR, JSON 직렬화·nullable·참조 연결·gate 의미는 검사하지 않는다. 번호/coverage 범위는 아직 ①~⑫이며 ⑬을 놓친다. AnalysisSource는 제목 언급 때문에 coverage NOTE에서 빠질 수 있다. 검사 대상 코드가 0개인 경로는 boundary NOTE를 출력한다. 현재 골격에서는 7개 boundary NOTE와 5개 coverage NOTE가 나오며, PASS를 E2E·Owner 수락 증거로 쓰지 않는다.

## `check_contract_fixtures.py` — 계약 예시·fixture 의미 검사 (2026-09-07)

```bash
python scripts/check_contract_fixtures.py
```

`check_boundaries.py`가 보지 않는 것을 본다 — 수정한 계약 12건의 ```json 예시 파싱, `CaseView` `info_state` 파생(B01), `RequirementReport` 선택 3단계(B02), 판독 결과→`ReadoutRun`→`UsageRecord`→`JobExecution` 연결(B03·B05), `SpanResolution` 완전성(B06), `CandidateEvent.span.timeline_revision`(B09), 수정 문서의 상대 링크와 옛 Pending 문구 잔존. 규칙은 각 함수 docstring이 가리키는 계약 절이 소유하고, fixture는 `docs/architecture/contracts/fixtures/call-closure-2026-09-07/`에 있다. 검증 조건과 결과의 의미는 `docs/architecture/contracts/adr/adr-data-contract-call-closure-2026-09-07.md` §7.

**2026-09-08 확장.** fixture 폴더 `fixtures/call-closure-2026-09-08/`와 검사 V8~V11이 추가됐다 — 재판독 발주(`kind=PLATE_READ`+`force_rerun=true`, V8) · `AnalysisRun.usage_refs[]` 파생값 vs 원장 `run_ref` 집계(V9) · `SpanResolution` `failure`·`OUT_OF_TIMELINE_RANGE`·위치 불특정 FAILED 예외(V10, `span-resolution/v1.1`에만 적용) · `AnalysisScope` `kind: ABSOLUTE | TIMELINE_RELATIVE`·혼합 금지·하위 호환(V11). Draft 자산 계약 2건은 JSON 파싱과 링크·짝 ADR 존재만 본다(의미 fixture는 Consumer Review 후). 검증 조건과 결과의 의미는 `docs/architecture/contracts/adr/adr-data-contract-call-closure-2026-09-08.md` §7.

**알려진 한계:** ADR에서 확정되지 않은 값(`MissingRange.source_ref` 규칙 · recording `failure.kind` 값 집합 · 자산 ref `kind` 표기 · stale 표시 필드명)은 fixture에 없거나 `EXAMPLE_*` 자리표시자다. 실패 run의 `JobExecution.status` 매핑도 Pending이라 검사하지 않는다. `span-resolution/v1` payload에는 `failure` 규칙을 적용하지 않는다(재해석 규칙 미정). 출력의 PASS는 「계약 규칙을 코드로 옮겼을 때 fixture가 만족한다」는 뜻이며 구현 통합·E2E·Owner 수락 증거가 아니다. CI에는 아직 붙이지 않았다.

## CI

`.github/workflows/boundary-check.yml`이 PR과 `develop` push에서 `check_boundaries.py`를 돌린다.

**운영진 소유 4개 파일은 건드리지 않는다** — `workflows/{assign-mentor,notify-discord,convention-check}.yml`과 `CODEOWNERS`. 그 밖의 `.github/` 추가는 CODEOWNERS 개정으로 허용됐다.
