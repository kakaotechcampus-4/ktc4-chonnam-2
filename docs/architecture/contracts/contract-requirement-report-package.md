# Final Data Contract — RequirementReport + ReportPackage v1

**Status:** `Final — Accepted`

**Architecture Contract:** v4 §5-1 ⑩

**Contract:** `RequirementReport + ReportPackage`

**Contract Version:** `requirement-report/v1` / `report-package/v1`

**Accepted:** `2026-09-04`

**Related ADR:** `adr/adr-requirement-report-package.md` (노션 표기 `ADR-10`)

**Contract Lead / Owner:** 김준영 (`evidence`)

**Runtime Producer:** `evidence`

**Direct Runtime Consumer:** `case` — 유소연

**Review / Projection Consumer:** `web` — 신유민 (`CaseView` 경유)

**관련 Architecture:** 대신고 모듈 구조 설계 v4

> 이 페이지가 `RequirementReport + ReportPackage`의 **Source of Truth**다. Draft는 선택지와 Consumer Review 이력을 보존하며 구현·Mock·CaseView projection은 이 Final Contract를 따른다.
> 

---

# 1. 계약 목적과 경계

`RequirementReport`는 현재 `EvidenceRecord`와 신고 준비 자산에 **신고 규칙을 적용한 immutable 판정 결과**다. 각 Requirement를 `PASS / WARN / BLOCK / UNKNOWN`으로 구조화하고, Consumer가 규칙을 다시 계산하지 않도록 한다.

`ReportPackage`는 최종 신고요건 검사를 통과한 confirmed Evidence와 신고용 파생 자산을 **안전신문고 handoff에 필요한 구조화 입력값·신고문·자산·capability로 결정론적으로 묶은 ready-only immutable bundle**이다.

```
EvidenceRecord
    ↓
RequirementReport(scope=EVIDENCE)
    ↓ EVIDENCE_SUFFICIENT gate 파생
Report Video / Derived Asset 준비
    ↓
RequirementReport(scope=FINAL_PACKAGE)
    ↓ PASS/WARN만 허용
ReportPackage
    ↓ PACKAGE_READY gate 파생
CaseView → web → USER_REVIEWED → Handoff
```

핵심 분리:

- confirmed Evidence 값 → `EvidenceRecord`
- 신고 규칙 판정 → `RequirementReport`
- 신고용 파생물/입력 bundle → `ReportPackage`
- 사용자 검토·외부 handoff lifecycle → `case / CaseView`

---

# 2. Producer / Consumer

## Producer

- `evidence` — 김준영

## Runtime Consumer

- `case` — 유소연

## Review / Projection Consumer

- `web` — 신유민
- `web`은 `RequirementReport` / `ReportPackage`를 raw로 직접 소비하지 않고 `CaseView` safe projection만 소비한다.

## 주요 Upstream

- `EvidenceRecord`
- `TimeResolution`
- 신고용 Report Video / 이미지 등 derived asset metadata
- 신고문 template
- 신고 규정 / Package policy

---

# 3. `RequirementReport` 최종 구조

```
RequirementReport {
    contract_version: string

    requirement_report_ref: ContractRef
    supersedes_ref?: ContractRef

    scope:
        EVIDENCE
        | FINAL_PACKAGE

    basis: {
        evidence_record_ref: ContractRef
        asset_refs: ContractRef[]
        template_ref?: string
    }

    policy_ref: string
    evaluated_at: offset-aware RFC3339 datetime

    overall:
        PASS
        | WARN
        | BLOCK
        | UNKNOWN

    checks: RequirementCheck[]
}

RequirementCheck {
    code: namespaced string

    category:
        EVIDENCE
        | TIME
        | VEHICLE
        | LOCATION
        | ASSET
        | DEADLINE
        | REPORT_CONTENT

    outcome:
        PASS
        | WARN
        | BLOCK
        | UNKNOWN

    reason_code: namespaced string
    summary?: string

    subject_refs: ContractRef[]

    measurement?: {
        actual: number
        limit?: number
        unit: namespaced string
    }
}
```

---

# 4. `RequirementReport` 의미

## 4.1 동일 Contract를 두 scope에 재사용

```
scope=EVIDENCE
= Report Video / Package 생성 전에 confirmed Evidence가 다음 단계로 진행하기 충분한지 검사

scope=FINAL_PACKAGE
= 신고용 자산·신고문까지 준비된 뒤 최종 handoff bundle을 만들 수 있는지 검사
```

두 scope는 동일 check 구조를 사용하지만 서로 다른 gate다. 하나의 mutable Report를 단계별로 갱신하지 않고, **평가 시점마다 immutable RequirementReport를 생성**한다.

## 4.2 Outcome 의미

| 값 | 의미 | 다음 단계 |
| --- | --- | --- |
| `PASS` | 조건 충족 | 진행 가능 |
| `WARN` | 진행 가능하지만 사용자 고지/확인이 필요 | 진행 가능 |
| `BLOCK` | 판정은 성립했고 현재 정책상 진행 불가 | 진행 불가 |
| `UNKNOWN` | 현재 정보로는 판정 자체가 성립하지 않음 | 진행 보류 |

`UNKNOWN`은 `BLOCK`과 동일 의미가 아니다.

예:

```
BLOCK
= Report Video를 확인했고 번호판이 식별 불가능함

UNKNOWN
= Report Video가 아직 없어 번호판 가시성을 판정할 수 없음
```

## 4.3 Overall aggregation

`overall`은 `checks[]`를 기반으로 Producer가 결정하며 Consumer가 재계산하지 않는다.

v1 precedence:

```
BLOCK > UNKNOWN > WARN > PASS
```

규칙:

- BLOCK check가 하나라도 있으면 `overall=BLOCK`
- BLOCK이 없고 UNKNOWN이 있으면 `overall=UNKNOWN`
- BLOCK/UNKNOWN이 없고 WARN이 있으면 `overall=WARN`
- 모든 check가 PASS일 때만 `overall=PASS`

## 4.4 Readiness 점수는 사용하지 않음

`4/5`, `80% ready` 같은 단순 readiness score를 Contract에 두지 않는다. 항목의 중요도와 gate 의미가 다르므로 `overall + checks[]`가 authoritative하다.

## 4.5 Numeric measurement

파일 크기·글자 수·기한 계산처럼 수치형 설명이 유용한 check는 optional `measurement`를 제공할 수 있다.

```
measurement.actual
measurement.limit?
measurement.unit
```

단, 한도 숫자를 Contract schema에 고정하지 않는다. 실제 규칙 수치는 `policy_ref`가 가리키는 rule data가 소유한다.

---

# 5. 파생 Gate 규칙

## 5.1 `EVIDENCE_SUFFICIENT`

`EVIDENCE_SUFFICIENT`는 별도 저장 field/state가 아니다.

```
RequirementReport.scope = EVIDENCE
AND overall ∈ {PASS, WARN}
→ EVIDENCE_SUFFICIENT = true

BLOCK | UNKNOWN
→ EVIDENCE_SUFFICIENT = false
```

이는 workflow에서 사용하는 **파생 gate 이름**이며 RequirementReport와 별도의 authoritative 상태를 만들지 않는다.

## 5.2 `PACKAGE_READY`

`PACKAGE_READY` 역시 별도 field/state가 아니다.

```
RequirementReport.scope = FINAL_PACKAGE
AND overall ∈ {PASS, WARN}
AND ReportPackage exists
→ PACKAGE_READY = true
```

`BLOCK / UNKNOWN`, Package 생성 실패, 필수 asset 부재이면 `ReportPackage`가 존재하지 않으므로 `PACKAGE_READY`가 성립하지 않는다.

## 5.2-1 `CaseView`로의 projection — 제안/확인 대기 (B02)

기존 PM 확정(R-7)을 철회한다. `CaseView`는 case 소유이며 현재 basis 선택·동일 scope 이력 선택·세 gate 표시·nullable은 case/evidence/web 합의가 필요하다. 이 절을 PM 소유 파일에 둔 것만으로 소비 계약을 확정하지 않는다.

**검토 대상인 기존 제안 (실행 규칙으로 확정되지 않음):** FINAL_PACKAGE report가 존재하면 우선하고, 없으면 EVIDENCE report, 둘 다 없으면 null을 싣는다. 이 제안은 과거 basis의 report를 선택하거나 EVIDENCE gate를 가릴 수 있어 그대로 통합 기준으로 사용하지 않는다. 대체 선택 규칙은 이번 보정에서 정하지 않는다.

§5.1·§5.2의 evidence/package gate 정의와 overall 값 공간은 유지한다. CaseView에 scope 필드를 둘지와 표시 방식은 Pending이다. 후속 기록: `adr/adr-consistency-followup-2026-09-06.md` §3 B02.

## 5.3 `USER_REVIEWED`

`USER_REVIEWED`는 `case` 소유 workflow state이며 `RequirementReport`나 `ReportPackage`에 저장하지 않는다.

---

# 6. RequirementReport lifecycle / invariants

1. 모든 Report는 `requirement_report_ref`를 가진다.
2. 생성 후 의미적으로 mutate하지 않는다.
3. 재검사 시 새 Report를 만들고 필요 시 `supersedes_ref`로 연결한다.
4. `basis.evidence_record_ref`는 반드시 존재한다.
5. `scope=FINAL_PACKAGE`이면 실제 판정에 사용한 신고용 자산 refs를 `basis.asset_refs`에 포함한다.
6. 정상 Report의 `checks[]`는 적용된 rule 결과를 가진다. 적용 rule이 하나도 없는 경우 policy/configuration 문제로 취급한다.
7. 같은 Report 안에서 `checks[].code`는 중복되지 않는다.
8. 모든 check는 `code`, `outcome`, `reason_code`를 가진다.
9. `evaluated_at`은 필수이며 time-dependent rule은 이 시점을 기준으로 계산한다.
10. Requirement engine 실행 자체가 실패하면 `overall=ERROR`를 만들지 않는다. 정상 RequirementReport가 생성되지 않은 것으로 처리한다.
11. Consumer는 measurement나 정책 수치로 outcome/overall을 재계산하지 않는다.
12. `USER_REVIEWED`, `SUBMITTED`, Job lifecycle을 이 Contract에 넣지 않는다.

---

# 7. `ReportPackage` 최종 구조

```
ReportPackage {
    contract_version: string

    package_ref: ContractRef
    supersedes_ref?: ContractRef

    evidence_record_ref: ContractRef
    requirement_report_ref: ContractRef

    created_at: offset-aware RFC3339 datetime

    report_inputs: {
        safety_report_type: string
        occurred_at: offset-aware RFC3339 datetime

        location: {
            display_text: string
            search_keyword?: string
        }

        vehicle_number: string
        violation_expression: string
    }

    report: {
        title: string
        description: string
        template_ref: string
    }

    assets: {
        report_video_ref: ContractRef
        plate_image_ref?: ContractRef
    }

    provenance: {
        source_refs: ContractRef[]
        derived_asset_refs: ContractRef[]
        policy_ref: string
    }

    handoff: {
        destination: SAFETY_REPORT
        supported_actions: [
            DOWNLOAD_ASSETS
            | COPY_FIELDS
            | OPEN_DESTINATION
        ]
    }
}
```

---

# 8. `ReportPackage` 의미

## 8.1 Ready-only object

`ReportPackage`에는 `BUILDING / INCOMPLETE / ERROR / READY` status를 두지 않는다.

Package는 다음 조건에서만 존재한다.

```
RequirementReport.scope = FINAL_PACKAGE
AND overall ∈ {PASS, WARN}
AND 필수 신고용 자산 존재
AND deterministic package assembly 성공
→ ReportPackage 생성
```

다음 상태에서는 Package가 없다.

- `overall=BLOCK`
- `overall=UNKNOWN`
- Report Video 생성 실패
- 필수 asset 부재
- Package assembly 실행 실패

준비중/실패 UI는 `CaseView`와 Job lifecycle이 표현한다.

## 8.2 Intentional handoff snapshot

`ReportPackage`는 `EvidenceRecord` 전체를 embed하지 않는다. 대신 실제 handoff에 필요한 확정값만 생성 시점 snapshot으로 복제한다.

최소 snapshot:

- safety report type
- occurred_at
- location display/search 정보
- vehicle number
- violation expression

이 중복은 실수가 아니라 **handoff 시점 재현성을 위한 의도된 snapshot**이다.

## 8.3 신고문은 deterministic template 기반

`report.title` / `report.description`은 confirmed Evidence와 고정 template를 이용해 결정론적으로 생성한다.

`report.template_ref`를 반드시 보존한다.

Package 단계에서 LLM 자유생성, 법적 추론, 새로운 Evidence 판단을 추가하지 않는다.

## 8.4 Source / Derived Asset 분리

`assets.report_video_ref`는 대신고가 생성한 신고용 파생영상이다. 사용자 원본 Source를 같은 자산으로 취급하지 않는다.

`plate_image_ref`는 확보된 경우에만 optional로 포함한다.

`provenance.source_refs`와 `derived_asset_refs`를 분리해 lineage를 보존한다.

---

# 9. Post-stamp / DerivedVideo 규칙

사후 Timestamp 각인은 `EvidenceNeeds`가 아니라 Package/DerivedVideo 준비 흐름의 책임이다.

```
TimeResolution.post_stamp
        ↓
case / package orchestration
        ↓
Report Video / DerivedVideo 생성
        ↓
RequirementReport(scope=FINAL_PACKAGE)
        ↓
ReportPackage
```

규칙:

- `TimeResolution.post_stamp.needed=true`이면 신고용 Report Video 생성 과정에서 해당 정책을 적용한다.
- USER_INPUT 기반 사후 Timestamp는 기존 TimeResolution 정책대로 non-blocking notice provenance를 유지한다.
- 원본 Source 또는 Source-derived 관찰 근거에 대신고가 만든 Timestamp를 삽입하지 않는다.
- `POST_STAMP`, `REPORT_VIDEO`, `EXPORT`를 `EvidenceNeeds` v1 kind로 추가하지 않는다.

---

# 10. Handoff 경계

`ReportPackage`는 **가능한 handoff capability**만 제공한다.

```
DOWNLOAD_ASSETS
COPY_FIELDS
OPEN_DESTINATION
```

다음을 소유하지 않는다.

- 실제 안전신문고 로그인
- 휴대전화 인증
- 신고자 개인정보
- 개인정보 동의
- `USER_REVIEWED`
- handoff opened/submitted state
- 실제 제출 성공
- 경찰 처리 결과

실제 사용자 workflow는 `case / CaseView`가 관리한다.

---

# 11. 주요 금지사항

- web이 파일 크기/기한/필드 길이 등 policy rule을 다시 구현하지 않는다.
- `UNKNOWN`을 `BLOCK` 또는 실행 실패와 동일 의미로 쓰지 않는다.
- `EVIDENCE_SUFFICIENT`를 RequirementReport와 별도 authoritative boolean으로 저장하지 않는다.
- `PACKAGE_READY`를 ReportPackage와 별도 authoritative state로 저장하지 않는다.
- ReportPackage에 `USER_REVIEWED` / `SUBMITTED` lifecycle을 넣지 않는다.
- Reporter PII / 인증정보를 Package에 저장하지 않는다.
- 신고문을 LLM 자유생성 결과로 만들지 않는다.
- 원본 Source와 Report Video를 동일 asset으로 취급하지 않는다.

---

# 12. 다른 Contract와의 경계

- `EvidenceRecord`: confirmed values의 authoritative source. RequirementReport는 이를 재판정하지 않고 규칙을 적용한다.
- `EvidenceNeeds`: confirmed Evidence 보강을 위한 관찰/판독 need만 소유한다. post-stamp/export는 포함하지 않는다.
- `TimeResolution`: occurred_at와 post-stamp 필요 여부의 authoritative source.
- `JobRecord / JobExecution`: Report Video 생성 및 Package assembly의 실행 lifecycle을 소유한다.
- `CaseView`: Requirement/Package 상태와 warning/action을 web에 safe projection한다.

---

# 13. Mock / 구현 최소 케이스

## RequirementReport

- EVIDENCE / all PASS
- EVIDENCE / WARN
- EVIDENCE / BLOCK
- EVIDENCE / UNKNOWN
- FINAL_PACKAGE / PASS
- FINAL_PACKAGE / WARN
- FINAL_PACKAGE / BLOCK
- FINAL_PACKAGE / UNKNOWN
- numeric measurement가 있는 check
- supersedes 재평가 케이스

## ReportPackage

- 정상 PASS 기반 Package
- WARN + 사용자 notice가 있는 Package
- optional plate image 없음
- post-stamped Report Video 포함
- Evidence correction 후 새 Package + `supersedes_ref`
- BLOCK/UNKNOWN에서는 Package 미생성

---

# 14. 버전 / 변경 규칙

계약 의미가 바뀌는 다음 변경은 Contract version 증가 및 ADR 변경 대상이다.

- Requirement outcome 의미 변경
- overall precedence 변경
- `EVIDENCE_SUFFICIENT` / `PACKAGE_READY` gate 정의 변경
- scope 추가/변경
- ReportPackage 생성 gate 변경
- handoff snapshot 필수/선택 의미 변경
- Producer/Consumer ownership 변경
- Package에 외부 submission lifecycle을 포함하도록 경계 변경

구체적인 신고 제한 숫자, template 내용, policy rule 값 변경은 schema 의미가 그대로라면 `policy_ref` / `template_ref` 버전 변경으로 관리하며 Contract version 증가를 요구하지 않는다.

---

# 15. Contract 번호 정합성

Draft 문서는 `⑨`로 작성됐으나 현재 Module Architecture v4의 Core Contract index는 `RequirementReport + ReportPackage`를 **⑩**으로 정의한다.

Final Contract는 Architecture Source of Truth에 맞춰 **⑩**을 사용한다. 이는 문서 인덱스 정합성 수정이며 계약 의미 변경이 아니다.
