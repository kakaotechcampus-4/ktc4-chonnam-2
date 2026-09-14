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
- `evaluate_requirements(...) -> RequirementReport`
- `build_report_package(...) -> ReportPackage`
- `render_report(...) -> dict`: `safety-report-policy/v1`의 결정론적 renderer. specific은 `CONFIRMED`/`CORRECTED`, generic은 `USER_UNSURE`를 명시해야 한다.
- `correction_heads(...) -> dict`: evidence가 소비하는 CorrectionRecord chain head 검증
- `validate_contract(contract) -> list[str]`: 다섯 출력 Contract의 최소 경계 검사

`evaluate_requirements`의 `rule_codes`와 가시성 fact는 채택된 policy 설정 또는 upstream 관찰을 명시적으로 주입하기 위한 Python 호출 인수다. 새 Runtime wire schema가 아니다. `PackageNotReady`는 ready-only Package가 발행되지 않았음을 나타내며 Contract에 새 status를 추가하지 않는다.

## 정책 데이터

- `deadline_policy_v1.json` — ADR-EVIDENCE-002 K2에서 채택한 2개 달력일 계산, 결과 매핑, 2026·2027 대한민국 공휴일 snapshot. 외부 공휴일 API를 사용하지 않는다.
- `requirement_rules_v2.json` — ADR-EVIDENCE-002 K3에서 채택한 적용 rule catalog. `EVIDENCE` 기본 4개, `FINAL_PACKAGE` 무조건 15개, 시각 표시 조건부 3개 중 1개 선택, 그리고 정상 Report를 발행하지 않는 구성 오류 목록을 가진다.

두 파일 모두 작성까지 완료됐으며 `evaluate_requirements` loader 연결은 아직 구현 전이다. 연결 시 `rule_codes` 인수가 사라지고 시각 표시 분기 selector용 `TimeResolution` 인수가 추가된다.

## 재현

저장소 루트의 PowerShell에서 실행한다.

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/evidence -p 'test_*.py'
python -m daesingo.evidence.mock_integration
```

두 번째 명령은 공용 H/U/P/R upstream JSON을 로딩하되 실제 baseline 순수 함수를 호출하고, 결과를 `docs/modules/evidence/artifacts/first-completion/`에 기록한다. 이 adapter와 그 Consumer reader는 테스트 도구이며 실제 `case` projection이 아니다.

## 상태

**1차 Mock 통합 baseline 구현.** production runtime, 외부 API 호출, 실제 영상 생성, `case`의 CaseView projection은 포함하지 않는다. 현재 검증 범위와 보류 항목은 [`first-completion-result.md`](../../../docs/modules/evidence/first-completion-result.md)를 따른다.
