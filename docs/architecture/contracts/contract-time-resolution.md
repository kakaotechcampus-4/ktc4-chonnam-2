# Final Data Contract — TimeResolution v1

**Status:** `Final — Accepted`

**Architecture Contract:** v4 §5-1 ⑧

**Contract:** `TimeResolution`

**Contract Version:** `time-resolution/v1`

**Accepted:** `2026-09-04`

**Related ADR:** `adr/adr-time-resolution.md` (노션 표기 `ADR-07`)

**Contract Lead / Owner:** 김준영 (`evidence`)

**Runtime Producer:** `evidence`

**Direct Runtime Consumer:** `case` — 유소연

**Review / Projection Consumer:** `web` — 신유민 (`CaseView` 경유)

**Upstream:** `recording`, `readout`, case 소유 사용자 correction

**관련 Architecture:** 대신고 모듈 구조 설계 v4

> 이 페이지가 `TimeResolution`의 **Source of Truth**다. Draft는 선택지와 Consumer Review 이력을 보존하며 구현·Mock·후속 Evidence 계약은 이 Final Contract를 따른다.
> 

---

# 1. 계약 목적

`TimeResolution`은 `recording`·`readout`의 시간 Observation과 명시적 사용자 correction을 `evidence`가 비교하여, **제품이 사용할 사건 발생시각(`occurred_at`)과 그 선택 근거·검증·충돌·계산 provenance를 확정한 결과**다.

`recording`과 `readout`은 시각을 관찰하고, 최종 source 선택과 resolution은 `evidence`만 수행한다. `case`와 `web`은 source priority를 재계산하지 않는다.

---

# 2. 최종 Contract 구조

```
TimeResolution {
    contract_version: string

    resolution_ref: ContractRef
    supersedes_ref?: ContractRef

    status:
        OK
        | NEEDS_REVIEW
        | UNKNOWN

    resolved?: {
        value: offset-aware RFC3339 datetime

        source: {
            kind: namespaced string
            input_ref: ContractRef
        }

        verification:
            AGREED
            | VERIFIED
            | UNVERIFIED

        computation: {
            mode:
                DIRECT
                | BASE_PLUS_OFFSET
                | USER_OVERRIDE

            base_input_ref?: ContractRef
            source_offset_ms?: integer

            timezone: {
                zone_id: string
                utc_offset: string
                source:
                    SOURCE_EXPLICIT
                    | PRODUCT_CONTEXT
            }
        }

        user_corrected: boolean
    }

    considered: [
        {
            input_kind:
                OBSERVATION
                | USER_INPUT

            input_ref: ContractRef
            source: {
                kind: namespaced string
            }

            value: string | null
            observation_status?: string
            verification:
                AGREED
                | VERIFIED
                | UNVERIFIED
            used: boolean
            reason_code?: namespaced string
        }
    ]

    conflict: {
        exists: boolean
        between_refs: ContractRef[]
        requires_user_notice: boolean
    }

    provenance: {
        policy_ref: string
        selected_input_ref?: ContractRef
    }

    post_stamp: {
        needed: boolean
        reason_code: namespaced string
        requires_user_notice: boolean
    }
}

ContractRef {
    kind: string
    ref: string
}
```

`ContractRef`는 이 계약에서 별도 신규 Contract로 승격하지 않고 기존 opaque reference 규칙을 재사용한다.

---

# 3. 상태 / 검증 / 충돌의 의미

| 축 | 값 | 의미 |
| --- | --- | --- |
| `status` | `OK / NEEDS_REVIEW / UNKNOWN` | 최종 시각의 제품 사용 가능 상태 |
| `resolved.verification` | `AGREED / VERIFIED / UNVERIFIED` | 선택된 시각 근거가 어떤 방식으로 검증·합의됐는지 |
| `conflict.exists` | `boolean` | 서로 다른 시각 후보 사이에 충돌이 존재하는지 |

핵심 규칙:

- `CONFLICT`를 `status`나 `verification` enum에 넣지 않는다.
- `resolved`가 존재하면서 `conflict.exists=true`인 상태를 허용한다.
- Architecture 정책상 fallback을 선택했더라도 충돌 provenance를 숨기지 않는다.
- `UNKNOWN`은 사용할 사건 시각이 없다는 뜻이며 임의의 시각을 생성하지 않는다.

---

# 4. Timestamp 선택 정책

`evidence`는 Architecture v4의 Timestamp 정책을 적용한다.

1. 검증을 통과한 Video Overlay가 있으면 가장 강한 근거로 사용한다.
2. 검증된 Overlay가 없으면 Filename / File Metadata / 제조사 metadata 등의 후보를 비교한다.
3. Filename / metadata 계열이 충돌하면 MVP 기본 정책에 따라 Filename 기반 값을 사용할 수 있으나 `conflict.exists=true`와 사용자 안내 필요성을 함께 보존한다.
4. 사용자가 사건 시각을 명시적으로 수정한 경우 `USER_INPUT` provenance를 사용할 수 있다.
5. 신뢰 가능한 근거가 없으면 `UNKNOWN`으로 남긴다.

Consumer는 이 우선순위를 복제하거나 재계산하지 않는다.

---

# 5. 사용자 입력 / CorrectionRecord 규칙

사용자 입력을 `Observation<T>`로 재포장하지 않는다. `USER_INPUT`은 별도 provenance kind로 유지한다.

`considered[].input_kind=USER_INPUT`인 경우 `input_ref`는 **case가 이미 소유하는 `CorrectionRecord`를 직접 참조**한다.

```
input_kind = USER_INPUT
input_ref = {
    kind: correction_record
    ref: <CorrectionRecord ID>
}
```

규칙:

- 명시적으로 사건 발생시각을 정정한 `EVENT_TIME_MANUAL` correction은 TimeResolution의 USER_INPUT 근거가 될 수 있다.
- `TIME_HINT_EDIT`는 Search 범위를 조정하는 기억 단서이며, 그 자체를 최종 `occurred_at` 근거로 승격하지 않는다. 최종 시각으로 사용하려면 명시적 사건시각 correction 기록이 있어야 한다.
- USER_INPUT을 readout/recording Observation처럼 위장하지 않는다.
- `resolved.user_corrected=true`이면 선택 provenance에서 해당 `CorrectionRecord`까지 추적 가능해야 한다.

---

# 6. `considered[]` 규칙

`considered[]`는 원본 Observation 전체를 복제하지 않고 **evidence가 실제 판정에 사용한 최소 summary snapshot + reference**만 보존한다.

최소 의미:

- 어떤 입력이었는가 (`input_kind`, `input_ref`)
- 어떤 source인가
- 후보 값
- 검증 상태
- 선택에 사용됐는가 (`used`)
- 필요 시 선택/제외 이유

원본 Observation의 diagnostics, raw confidence, frame payload 등은 복제하지 않는다. 상세 근거는 `input_ref`가 가리키는 원본 Contract를 조회한다.

---

# 7. Timezone / 시간 형식 정책

`resolved.value`는 항상 **offset-aware RFC3339 datetime**으로 표현한다.

MVP의 제품 시간 context는 대한민국 안전신문고 신고 준비를 기준으로 **`Asia/Seoul` (`+09:00`)**로 고정한다.

Timezone provenance 규칙:

- 입력 Source가 timezone/UTC offset을 **명시적으로 제공**하면 `computation.timezone.source=SOURCE_EXPLICIT`로 보존한다.
- 입력 Source에 timezone 정보가 없으면 MVP 제품 context인 `Asia/Seoul (+09:00)`을 적용하고 `computation.timezone.source=PRODUCT_CONTEXT`로 기록한다.
- Source가 명시한 timezone/offset이 제품 context와 충돌한다고 판단되는 경우 이를 조용히 덮어쓰지 않는다. 해당 후보와 provenance를 보존하고 `NEEDS_REVIEW`/사용자 안내 경로로 전달한다.
- timezone/offset을 근거 없이 AI가 추정하지 않는다.

화면 표시 문자열은 `CaseView` / `web`의 projection 책임이다.

---

# 8. 계산 provenance

최종 시각 계산 방식은 다음을 구분한다.

```
DIRECT
= 선택된 입력의 절대 시각을 직접 사용

BASE_PLUS_OFFSET
= source 기준시각 + 영상/timeline offset으로 계산

USER_OVERRIDE
= 명시적 사용자 사건시각 correction을 사용
```

`BASE_PLUS_OFFSET`이면 `base_input_ref`와 `source_offset_ms`를 반드시 보존한다. Consumer는 이 값을 이용해 최종 시각을 다시 계산하지 않는다.

---

# 9. Confidence 규칙

`TimeResolution` 자체에는 numeric confidence를 생성하지 않는다.

다음으로 최종 신뢰 상태를 표현한다.

- source
- verification
- conflict
- considered provenance
- 사용자 correction 여부

Upstream Observation의 confidence를 복사·평균하여 `TimeResolution.confidence`를 만들지 않는다.

---

# 10. Immutability / Correction Lifecycle

1. 발행된 TimeResolution은 immutable result다.
2. 재계산 또는 사용자 correction 시 기존 Resolution을 overwrite하지 않는다.
3. 새 `resolution_ref`를 가진 TimeResolution을 생성한다.
4. 이전 결과를 대체하면 `supersedes_ref`로 연결한다.
5. `resolved.user_corrected`는 실제 사용자 correction이 최종값에 반영됐는지를 뜻하며 `USER_REVIEWED` workflow 상태와 동일하지 않다.

---

# 11. Conflict / 사용자 안내

`evidence`는 충돌을 판정하지만 실제 화면 노출 lifecycle은 소유하지 않는다.

```
conflict.requires_user_notice
= Timestamp 후보 충돌을 사용자에게 안내해야 하는가
```

- 실제로 언제/어떻게 표시했는지는 `CaseView`/web이 관리한다.
- `shown_to_user` 같은 UI lifecycle 필드를 TimeResolution에 넣지 않는다.

---

# 12. 사후 Timestamp 각인

`post_stamp`는 **사후 Timestamp 각인이 필요한지와 그 이유**만 표현한다. 실제 Report Video export 완료 상태를 의미하지 않는다.

원칙:

- 원본 Source와 Source 기반 Incident Clip에는 대신고가 만든 Timestamp를 근거처럼 삽입하지 않는다.
- Evidence가 확정된 뒤 Report Video에만 사후 Timestamp를 표시할 수 있다.
- `post_stamp.needed=true`이고 최종 시각이 `USER_INPUT` 기반이면 `post_stamp.requires_user_notice=true`여야 한다.
- 이 안내는 **non-blocking**으로 CaseView notice에 projection한다.
- 사용자에게는 원본 화면 Timestamp가 아니라 **사용자 입력/확정 정보를 바탕으로 사후 표시된 시각**임을 알릴 수 있어야 한다.

---

# 13. Invariants

1. `status=OK`이면 `resolved`가 존재해야 한다.
2. `status=UNKNOWN`이면 `resolved`가 존재하지 않는다.
3. `status=NEEDS_REVIEW`에서는 fallback `resolved`가 존재할 수 있다.
4. `resolved`가 존재하면 `provenance.selected_input_ref`가 존재해야 한다.
5. `resolved.value`는 offset-aware RFC3339다.
6. `conflict.exists=false`이면 `conflict.between_refs`는 빈 배열이다.
7. `conflict.exists=true`와 `resolved` 존재는 동시에 허용한다.
8. `BASE_PLUS_OFFSET`이면 `base_input_ref`와 `source_offset_ms`가 존재한다.
9. USER_INPUT 기반 resolved는 case의 `CorrectionRecord`까지 추적 가능해야 한다.
10. TimeResolution에는 numeric final confidence를 두지 않는다.
11. 사후 각인 여부와 실제 Report Video 생성 완료 여부를 동일 상태로 사용하지 않는다.

---

# 14. 다른 Contract와의 경계

- `Observation<T>`: recording/readout이 관찰한 시간 후보의 공통 envelope. 사용자 입력은 Observation이 아니다.
- `CorrectionRecord`: 명시적 사용자 사건시각 수정의 authoritative provenance.
- `EvidenceRecord`: 확정 event time은 TimeResolution의 `resolution_ref`를 참조한다.
- `CaseView`: web에 필요한 시각 값·검토 필요·notice를 safe projection한다. raw provenance를 그대로 노출하지 않는다.
- `EvidenceNeeds`: 사건시각·번호판 등 **confirmed Evidence를 보강하기 위한 추가 관찰/판독 Need**만 표현한다. `post_stamp`/Report Video 생성은 EvidenceNeeds에 넣지 않는다.
- `ReportPackage / DerivedVideo export flow`: `post_stamp.needed`를 소비해 case가 신고용 파생영상 생성 Job을 발주한다. 실제 각인·export 완료 상태는 TimeResolution이 소유하지 않는다.

---

# 15. 금지사항

- `case`/`web`이 Timestamp source priority를 재계산하지 않는다.
- unverified metadata를 numeric confidence 하나로 확정하지 않는다.
- 신뢰 가능한 source가 없는데 AI가 시각을 생성하지 않는다.
- USER_INPUT을 recording/readout Observation으로 가장하지 않는다.
- 원본/Incident Clip에 사후 Timestamp를 먼저 찍고 이를 다시 OCR 근거로 사용하지 않는다.

## 정합성 보정 — EvidenceNeeds 경계 확정

`EvidenceRecord + EvidenceNeeds` Final 확정 과정에서 `EvidenceNeeds`의 v1 범위를 **confirmed Evidence 보강 작업**으로 한정했다.

- 허용 Need: `OVERLAY_TIME_OCR`, `PLATE_REREAD`
- 제외: `POST_STAMP`, `REPORT_VIDEO`, export workflow
- `TimeResolution.post_stamp`는 사후 각인 필요 여부와 provenance만 보존하고, 실제 Report Video 생성은 Package/DerivedVideo export 흐름에서 처리한다.

이 보정은 Timestamp 선택 정책이나 `post_stamp` 의미를 변경하지 않고, 후속 실행 책임의 소유권만 명확히 한다.