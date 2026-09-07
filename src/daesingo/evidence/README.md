# `evidence` — 증거 확정 / 신고 정책 / Package

**Owner:** 김준영 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈4 · **문서 작업공간:** `docs/modules/evidence/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈4)

Observation → confirmed Evidence·Timestamp 최종 resolution·사용자 correction 적용·`EvidenceNeeds`·Visual Event → Report Type 매핑·신고 요건 검사(PASS/WARN/BLOCK)·신고문 Template·`ReportPackage`·handoff

## 이 폴더가 알면 안 되는 것 (§4-모듈4 「알면 안 되는 것」)

AI model/prompt / OCR library / ffmpeg / Worker lease·heartbeat / 사용자가 어느 화면에 있는지 / 외부 시스템에 직접 작업 발주. **순수 함수 모듈** — 다른 도메인 모듈을 호출하지 않는다

## 공개 함수

`daesingo.evidence`에서 JSON-compatible mapping 기반 공개 함수를 제공한다.

```text
resolve_time() → TimeResolution
build_evidence_record() → EvidenceRecord
build_evidence_needs() → EvidenceNeeds
evaluate_requirements() → RequirementReport
build_report_package() → ReportPackage | None
assemble() → 위 산출물 전체
```

세부 입력 envelope와 실패 방식은 `docs/modules/evidence/tech-spec.md`를 따른다.
다른 모듈은 **공개 함수만** 호출한다.

## 상태

**1차 Mock 통합 코드가 있다.** Happy/Partial 공용 fixture 경로만 완료됐으며 실제
AI/OCR·CorrectionRecord·자산 metadata 기반 검사는 아직 통합 대기다.
