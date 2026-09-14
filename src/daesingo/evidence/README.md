# `evidence` — 증거 확정 / 신고 정책 / Package

**Owner:** 김준영 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈4 · **문서 작업공간:** `docs/modules/evidence/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈4)

Observation → confirmed Evidence·Timestamp 최종 resolution·사용자 correction 적용·`EvidenceNeeds`·Visual Event → Report Type 매핑·신고 요건 검사(PASS/WARN/BLOCK)·신고문 Template·`ReportPackage`·handoff

## 이 폴더가 알면 안 되는 것 (§4-모듈4 「알면 안 되는 것」)

AI model/prompt / OCR library / ffmpeg / Worker lease·heartbeat / 사용자가 어느 화면에 있는지 / 외부 시스템에 직접 작업 발주. **순수 함수 모듈** — 다른 도메인 모듈을 호출하지 않는다

## 공개 함수

`daesingo.evidence`는 Final Contract 값을 받거나 반환하는 순수 함수 경계다. 인수는 Contract JSON을 역직렬화한 `dict`이며, `scenario_id`나 Mock 파일명은 공개 입력이 아니다.

- `resolve_time(...) -> TimeResolution`
- `assemble_evidence(...) -> EvidenceRecord`
- `calculate_evidence_needs(...) -> EvidenceNeeds | None`
- `evaluate_requirements(evidence_record, *, scope, report_id, evaluated_at, time_resolution, asset_facts=(), observation_facts=None, supersedes_id=None) -> RequirementReport`
- `build_report_package(...) -> ReportPackage`
- `render_report(...) -> dict`: `safety-report-policy/v1.1`의 결정론적 renderer. specific은 `CONFIRMED`/`CORRECTED`, generic은 `USER_UNSURE`를 명시해야 하며 위치가 없으면 장소 슬롯 없는 template을 고른다.
- `correction_heads(...) -> dict`: evidence가 소비하는 CorrectionRecord chain head 검증
- `validate_contract(contract) -> list[str]`: 다섯 출력 Contract의 최소 경계 검사

`evaluate_requirements`의 rule 목록은 호출자가 전달하지 않고 활성 catalog가 선택한다. `time_resolution`은 시각 표시 조건부 rule selector이며, `observation_facts`는 번호판·시각 표시·사후 각인의 upstream 관찰을 명시적으로 주입하는 Python 호출 인수다. 둘 다 새 Runtime wire schema가 아니다. `PackageNotReady`는 ready-only Package가 발행되지 않았음을 나타내며 Contract에 새 status를 추가하지 않는다.

## 정책 데이터

- `attachment_policy_v1.json` — K1의 decimal byte 용량 상한과 첨부 개수 상한, outcome 매핑.
- `deadline_policy_v1.json` — K2의 2개 달력일 계산, 결과 매핑, 2026·2027 대한민국 공휴일 snapshot. 외부 공휴일 API를 사용하지 않는다.
- `requirement_rules_v2.json` — K3에서 채택됐으나 D1 반영으로 첫 실행 전에 대체된 보존 revision. 수정하거나 활성화하지 않는다.
- `requirement_rules_v3.json` — D1 반영 후 실제 실행됐으나 ADR-EVIDENCE-005 D2로 대체된 보존 revision. 수정하거나 활성화하지 않는다.
- `requirement_rules_v4.json` — **활성 catalog.** `EVIDENCE` 기본 4개, `FINAL_PACKAGE` 무조건 12개와 시각 표시 조건부 3개 중 정확히 1개를 선택한다. 판정 주체가 없던 사건 장면·전후 상황 세 rule을 제거하고 나머지 outcome 매핑은 v3에서 그대로 계승한다.
- `safety_report_policy_v1_1.json` — 위치 유무에 따른 네 deterministic template과 신고유형 매핑.

활성 requirement catalog 선택점은 `policy_catalog.py`의 `_ACTIVE_REQUIREMENT_CATALOG_FILE` 한 곳이며 현재 `requirement_rules_v4.json`이다. 출력 `policy_ref`는 이 파일에서 읽는다.

loader는 각 정책의 식별자·필수 구조·공휴일 coverage·catalog rule 구성을 검증한다. 깨진 구성은 `PolicyConfigurationError`로 정상 `RequirementReport` 발행 전에 중단하고, 관찰 사실 부족은 check의 `UNKNOWN`으로 남긴다.

## 재현

저장소 루트의 PowerShell에서 실행한다.

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/evidence -p 'test_*.py'
python -m daesingo.evidence.mock_integration
```

두 번째 명령은 공용 H/U/P/R upstream JSON을 로딩하되 실제 baseline 순수 함수를 호출하고, 결과를 `docs/modules/evidence/artifacts/first-completion/`에 기록한다. 이 adapter와 그 Consumer reader는 테스트 도구이며 실제 `case` projection이 아니다.

## 상태

**ADR-EVIDENCE-002(K1~K4)·003(D1)·005(D2) 정책 엔진 반영 완료.** 공용 H/U Mock에서 각각 `PASS`·`WARN` FINAL_PACKAGE와 Package 발행을 확인했다. 다만 번호판·시각 관찰은 여전히 `mock_only` 입력이므로 실제 Runtime의 I4 배선, 실제 영상 생성, `case`의 CaseView projection과 외부 제출은 포함하지 않는다. 현재 검증 범위와 후속 항목은 [`first-completion-result.md`](../../../docs/modules/evidence/first-completion-result.md)를 따른다.
