# 코딩 에이전트 전달용 — ADR-EVIDENCE-002(K1~K4)·003(D1) 반영 구현 프롬프트

이 문서 전체를 저장소에 접근 가능한 코딩 에이전트 작업에 전달한다. 기준 문서는 두 개다.

- [ADR-EVIDENCE-002 — 1차 완료 후 Owner 정책 결정 K1-K4](../adr/adr-first-completion-owner-decisions.md)
- [ADR-EVIDENCE-003 — 위치를 확보하지 못한 사건의 `ReportPackage` 발행(D1)](../adr/adr-location-absent-package.md)

이 프롬프트는 계획 작성이 아니라 **구현·테스트·Artifact 재실행·증빙 기록까지 수행하는 작업 지시**다.

발주자: 김준영(`evidence` Owner). 작성일: `2026-09-13`. 갱신: `2026-09-14`(ADR-003 D1 반영 항목 W10~W12 추가).

---

당신은 대신고 모노레포에서 김준영 담당 `evidence` 모듈을 구현하는 엔지니어다.

**ADR-EVIDENCE-002의 K1·K2·K3·K4와 ADR-EVIDENCE-003의 D1은 이미 `ACCEPTED`다. 이 작업은 그 결정을 코드·정책 데이터·계약·테스트·Artifact·문서에 실제로 반영하는 일이다.** 결정을 다시 논의하거나, 이미 확정된 값에 대해 사용자 확인을 반복해서 요구하지 마라. 짧은 계획과 확인 사항을 먼저 공유한 다음 구현·검증·결과 정리까지 진행하라.

ADR의 수치·매핑·판정표를 이 프롬프트에 복제하지 않았다. **판정 규칙의 원문은 항상 ADR의 해당 절이며, 아래 작업 항목은 "어느 절을 어디에 반영하는가"만 지정한다.** 이 프롬프트와 ADR이 달라 보이면 ADR이 이긴다. 다만 ADR이 Final Data Contract를 이기지는 않는다 — ADR과 Contract가 충돌하면 이 프롬프트 §7의 처리 방식을 따른다.

**절 번호 표기.** 아래에서 `§3.4`·`§5.12`처럼 그냥 `§`로 적은 것은 **ADR-EVIDENCE-002의 절**이다. ADR-003의 절은 「ADR-003 §5.5」처럼 ADR 번호를 붙여 적고, 이 프롬프트 자신의 절을 가리킬 때만 「이 프롬프트 §10」처럼 명시한다.

## 1. 목표와 담당 범위

구현 대상은 `evidence` 모듈 하나다.

- K1 첨부 용량·개수 policy를 versioned policy data와 `FINAL_PACKAGE` 여섯 rule로 구현한다.
- K2 신고기한 policy를 `deadline_policy_v1.json` 기반 deadline evaluator로 구현한다.
- K3 catalog를 실제 rule 선택 주체로 만들고, `evaluate_requirements()`의 호출 경계를 §5.13대로 바꾼다. 작업 중 활성 catalog는 `policy/requirement-rules-v2`로 시작해 **W12에서 `v3`로 바뀐다**.
- K4 `source-kind-registry`를 v2로 개정하고 비시각 correction provenance를 테스트로 고정한다.
- **D1**(ADR-003) 위치 없는 `ReportPackage` 발행을 계약 `report-package/v1.1`·신고문 정책 `safety-report-policy/v1.1`·catalog revision·구현에 반영한다(W10~W12).
- 위 변경이 H/U/P/R 네 공용 Scenario 재실행 결과에 어떻게 나타나는지 증빙으로 남긴다.

**범위 밖.** common/runtime 구현(Queue·Worker·lease·heartbeat·retry·취소·비용 장부·마스킹 로거·config/storage·CI/CD), `JobExecution`·`UsageRecord` 생산, 실제 AI/OCR 호출, ffmpeg 영상 생성, 안전신문고 자동 제출, 다른 모듈(`case`·`recording`·`readout`·`web`)의 구현. `evidence` 구현을 위해 공통 실행기나 상위 계층을 먼저 만들어야 한다는 방향으로 범위를 넓히지 마라.

## 2. 시작할 때 확인할 것

1. 현재 브랜치·HEAD·작업 트리 상태와 적용되는 `CLAUDE.md`, `docs/README.md`, `.agents`/`AGENTS.md`가 있으면 그 규칙을 확인한다.
2. 기존 미커밋 변경은 사용자의 작업물이다. 내용을 되돌리거나 고치지 말고, 커밋할 때 내 변경과 섞지 않는다(「이 프롬프트 §10.2」).
3. ADR 전문과 「이 프롬프트 §4」의 현재 구현 상태 표를 확인한 뒤, 이미 되어 있는 것을 다시 만들지 마라.
4. 기존 테스트와 공용 검증 3종의 **시작 상태**를 먼저 실행해 기록한다. 변경 후 결과와 비교할 기준선이 필요하다.
5. 담당 범위·구현 순서·예상 변경 경로·확인이 필요한 항목을 짧게 공유한 뒤 구현을 시작한다.

작성 시점 스냅샷(`2026-09-14` 갱신) — 브랜치 `feature/evidence-location-nullable`, 작업 트리 깨끗함. ADR 3종·정책 데이터 2종(`deadline_policy_v1.json`·`requirement_rules_v2.json`)·공휴일 snapshot·`reviews/11`·`reviews/12`가 모두 커밋돼 있다. 직전 브랜치 `docs/evidence-first-completion-checklist`는 [PR #52](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/52)로 열려 있고 **아직 `develop`에 병합되지 않았다** — 이 브랜치는 그 위에 쌓여 있다. **이것은 과거 스냅샷이다. 실행 시 현재 상태를 다시 확인하라.**

## 3. 읽을 자료와 우선순위

모든 경로는 저장소 루트 기준이다.

### 반드시 먼저 읽을 것

- [`docs/modules/evidence/adr/adr-first-completion-owner-decisions.md`](../adr/adr-first-completion-owner-decisions.md) — 이 작업의 기준. §3(K1)·§4(K2)·§5(K3)·§6(K4)·§7(변경 규칙). §2·§5.6·§5.8·§5.11·§5.14에 D1 종결 표시가 붙어 있다
- [`docs/modules/evidence/adr/adr-location-absent-package.md`](../adr/adr-location-absent-package.md) — **W10~W12의 기준.** §5.2(직렬화 모양)·§5.3(계약)·§5.4(template)·§5.5(catalog 2건)·§5.6(사용자 고지 경계)·§8(이 ADR이 결정하지 않는 것)·§9(검증)
- [`docs/modules/evidence/reviews/10_first-completion_decisions_and_integration_2026-09-13.md`](../reviews/10_first-completion_decisions_and_integration_2026-09-13.md) — 이 ADR이 나온 맥락, D1, I1~I11 통합 항목
- [`docs/modules/evidence/reviews/12_u-package-location-nullability_issue-draft_2026-09-13.md`](../reviews/12_u-package-location-nullability_issue-draft_2026-09-13.md) — D1의 근거·두 Owner 답변·사실 확인 표. **결정 원문은 ADR-003이고 이 문서는 경위 기록이다**
- `src/daesingo/evidence/` 전체 코드와 `README.md`
- `tests/evidence/` 전체와 `tests/evidence/fixtures/adapter_inputs.json`
- [`docs/modules/evidence/first-completion-result.md`](../first-completion-result.md) — 갱신 대상 추적표

### 계약 원문 (판정 구조·불변조건의 authoritative 출처)

- `docs/architecture/contracts/contract-requirement-report-package.md` §3·§4.6·§6
- `docs/architecture/contracts/contract-evidence-record-needs.md` §3·§4.6·§4.7·§10
- `docs/architecture/contracts/contract-time-resolution.md`
- `docs/architecture/contracts/contract-correction-record.md` §5·§6
- `docs/architecture/contracts/contract-observation.md`

### 확정된 evidence 결정

- [`decisions/safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md)
- [`decisions/source-kind-registry.md`](../decisions/source-kind-registry.md) — K4에서 v2로 개정할 대상
- [`adr/adr-first-mock-integration-implementation.md`](../adr/adr-first-mock-integration-implementation.md)
- [`prompts/implementation-prompt-gpt-5.6-sol.md`](implementation-prompt-gpt-5.6-sol.md) — 1차 발주의 의미 경계(그 문서 §7)와 보고 형식(그 문서 §9)은 이번에도 유효하다. 다만 그 문서 §4의 **커밋 금지 조항은 이번 발주의 「이 프롬프트 §5·§10」이 대체한다**

### 보조

- `docs/mock/` 문서와 `data/mock/`의 실제 JSON — 입력 확인용
- `research/`의 PDF 3종과 공휴일 snapshot 문서 — ADR이 인용한 절의 근거 추적이 필요할 때만. **Research의 수치를 ADR과 다르게 해석해 정책으로 승격하지 마라.**
- `docs/archive/`는 현재 기준으로 사용하지 마라.

## 4. 현재 구현 상태 — 이미 있는 것과 없는 것

| 항목 | 상태 |
| --- | --- |
| `deadline_policy_v1.json` | **작성 완료**(커밋됨). 로더·계산기 미구현 |
| `requirement_rules_v2.json` | **작성 완료**(커밋됨). 로더·선택 로직 미구현. **D1 반영은 v2를 덮어쓰지 않고 새 revision으로 뺀다**(§7·ADR-003 §5.5) |
| `package.location.present` 매핑 | v2는 부재를 `UNKNOWN`으로 둔다. D1 종결로 **새 revision에서 `WARN`**이다(ADR-003 §5.5) |
| `report-package/v1` §7 `location` | 현재 필수. **v1.1에서 nullable**로 개정 대상(W10) |
| 장소 슬롯 없는 신고문 template | **없음.** `safety-report-policy/v1.1`에서 신설(W11) |
| K1 첨부 용량·개수 policy data | **없음.** 신설 대상 |
| `evaluate_requirements()` | `rule_codes`를 호출자가 주입. `policy_ref`는 v1 고정 |
| `package.asset.report_video.size` | 구현돼 있으나 `report_video_max_bytes` 미채택이라 `PolicyConfigurationError`. v2에서 K1 여섯 rule로 대체 대상 |
| `package.deadline.within_policy` | 무조건 `PolicyConfigurationError` |
| `package.evidence.situation_unconfirmed` | 구 이름·구 매핑으로 구현됨. `package.evidence.situation_response`로 교체 대상 |
| 사건 장면·전 상황·후 상황 세 rule | **미구현** |
| `package.location.present` rule | **미구현**(현재는 `build_report_package`의 `PackageNotReady("package.input.location_missing")`으로만 드러남). W12에서 제거 대상 |
| `package.time.display_unresolved` | **미구현**. 시각 표시 분기 selector도 미구현 |
| `source-kind-registry.md` | v1. K4 개정 전 |
| 비시각 correction provenance | `assembly.py`에 이미 K4와 같은 값으로 구현됨(ADR §6.11). 테스트만 없음 |

**이미 맞게 동작하는 코드를 재작성하지 마라.** K4는 registry 문서 추인과 테스트 추가이지 구현 변경이 아니다.

## 5. 변경할 수 있는 범위

- `src/daesingo/evidence/` 코드와 정책 데이터, `tests/evidence/`, `docs/modules/evidence/`의 문서·Artifact를 작성·수정한다.
- 기존 공용 타입·유틸이 있으면 재사용한다. 필요 이상의 전역 설정·의존성·추상화를 도입하지 마라. 표준 라이브러리로 충분한 계산에 새 패키지를 추가하지 마라.
- **예외 한 건 — `contract-requirement-report-package.md`.** ADR-003이 이 계약의 `v1 → v1.1` 개정을 확정했고 Contract Owner가 발주자(김준영)이므로 **W10의 범위 안에서만** 수정한다. 개정 범위는 ADR-003 §5.3이 지정한 §7·§8.2 두 곳과 version 표기뿐이다. 그 밖의 절, 다른 계약 파일은 그대로 수정 금지다. 「계약을 고칠 수 있다」로 일반화하지 마라.
- 다음은 **수정 금지**다.
  - `docs/architecture/contracts/`의 Final Contract(위 예외 제외), 공용 `data/mock/` 원본, 공용 validator(`data/mock/validate_mock_pack.py`, `scripts/check_*.py`)
  - 다른 Owner의 모듈 구현·문서 폴더
  - `.github/workflows/{assign-mentor,notify-discord,convention-check}.yml`과 `.github/CODEOWNERS`
  - `docs/management/secret/`·`docs/management/submissions/`·`doc/` — 커밋 금지, `git add -f` 금지
  - `docs/archive/`
- 테스트를 통과시키려고 공용 Fixture를 고치지 마라. 파생 입력이 필요하면 원본 경로·변경점·근거를 명시하고, 그 결과를 공용 Pack 원본 통과로 보고하지 마라.
- 새 공용 Scenario ID를 만들지 마라.
- **커밋은 「이 프롬프트 §10」의 전략에 따라 직접 수행한다.** 커밋 전 사용자 승인을 다시 요청하지 마라. 반면 push·PR 생성·이슈 작성·외부 메시지는 별도 지시 없이 수행하지 마라.

## 6. 작업 항목

각 항목은 「근거 조항 → 할 일 → 완료 조건 → 하지 말 것」이다. 판정 규칙 원문은 ADR에 있다.

### W1 — K1 첨부 용량·개수 policy data와 여섯 rule

**근거:** ADR §3.3(판정 대상)·§3.4(용량·단위)·§3.5(개수)·§3.6(판정 결과)·§3.7(내부 목표 없음)·§3.8(식별자·근거)

**할 일**

1. `policy/safety-report-attachment-size/v1`을 담는 versioned policy data 파일을 `src/daesingo/evidence/`에 신설한다. 파일명·구조는 `deadline_policy_v1.json`의 기존 관례에 맞춘다. 근거·확인일·증거 상태(개수 제한은 화면 캡처 미보존)를 데이터 안에 남긴다.
2. `package.asset.{image.each_size, video.each_size, total_size, image.count, video.count, total_count}` 여섯 rule을 구현한다.
3. 각 check에 `measurement.actual/limit/unit`을 출력한다. 단위 값은 **활성 catalog**가 지정한 것을 쓴다(W3 시점 `requirement_rules_v2.json`, W12 이후 `v3`).
4. 판정 대상 집합은 §3.3대로 "현재 Package에 첨부하려는 자산"이다. 동일 `asset_ref` 중복은 한 번만 센다. `ref` 접두어 추측으로 종류를 판단하지 말고 Contract의 role로 판단한다.
5. 기존 `package.asset.report_video.size`는 v2 catalog에서 사용하지 않는다. v1 Artifact에 남은 code와 값은 그대로 보존한다.

**완료 조건 (테스트)**

- 상한과 정확히 같은 값 `PASS`, 1 byte 초과 `BLOCK`
- `byte_size=null` 단건 `UNKNOWN`
- 일부 미측정인데 알려진 합만으로 이미 초과 → `BLOCK` / 확정 불가 → `UNKNOWN` 두 경우 분리
- 개수 rule 세 개가 각각 판정되고, 첨부 집합 확정 불가 시 `UNKNOWN`
- K1 상한 데이터가 없거나 형식이 깨졌을 때 정상 Report 미발행(§5.12)

**하지 말 것**

- `MiB` 해석, 표시용 MB 반올림값으로 판정
- 외부 상한보다 낮은 내부 목표치 도입(§3.7)
- `ReportPackage.assets`를 4개 첨부로 확장(§3.9 — 별도 Contract 논의 대상)
- 현재 첨부가 최대 2개라는 이유로 개수 rule을 생략

### W2 — K2 신고기한 evaluator

**근거:** ADR §4.3(대표시각)·§4.4(2개 달력일·경계)·§4.5(정적 달력)·§4.6(상태·outcome)·§4.7(WARN)·§4.8(달력 실패)·§4.9(식별자)

**할 일**

1. `deadline_policy_v1.json` 로더를 만들고 형식·coverage·날짜 정합(오름차순·중복 없음·`source_ids` 참조 무결성)을 로드 시점에 검증한다.
2. `package.deadline.within_policy`를 구현한다. `occurred_at`과 `RequirementReport.evaluated_at`을 `Asia/Seoul`로 변환해 비교한다.
3. 마감 경계는 §4.4대로 **exclusive upper bound**로 표현한다. `23:59:59.999`를 직접 만들지 마라.
4. `measurement`와 provenance에 채택한 `policy_ref`·`calendar_ref`가 드러나게 한다.
5. 주말은 코드로 계산하고 공휴일은 JSON 목록만 읽는다.

**완료 조건 (테스트 — §4.10)**

- 평일 위반, 금요일 위반, 연속 공휴일, 연말 경계
- 마감 직전 / 정확한 경계값 / 직후
- `OPEN`·`EXTENDED`·`EXCEEDED` → `PASS`/`PASS`/`WARN`
- `occurred_at` 부재·`UNKNOWN` → `UNKNOWN`, `NEEDS_REVIEW` → 잠정 계산 + `WARN`
- coverage 밖 연도·불완전 snapshot → `PolicyConfigurationError`, 정상 Report 미발행
- 기대 마감일은 **손으로 적은 날짜**로 검증한다. 구현 함수를 다시 호출해 expected를 만들지 마라.

**하지 말 것**

- Runtime 외부 공휴일 API 호출, 네트워크 접근
- 2028년 날짜 추정, 새 임시공휴일 자동 반영
- 달력 데이터 실패를 `UNKNOWN`으로 치환
- `EXCEEDED`를 `BLOCK`으로 처리하거나 "제출 불가" 문구 생성(§4.7의 사용하지 않는 표현 목록)
- `representative_ms` 부재 시 중앙값 fallback 생성

### W3 — K3 catalog 연결과 호출 경계 변경

**근거:** ADR §5.3~§5.13. 특히 §5.7(시각 표시 분기)·§5.8(content_length)·§5.9(situation_response)·§5.12(구성 오류)·§5.13(호출 경계)

> **D1과 겹치는 부분.** §5.4·§5.6·§5.8·§5.12에는 D1 종결 블록이 붙어 있다. W3에서는 v2를 그대로 연결하되 **위치 판정에 관한 테스트를 여기서 고정하지 마라.** 최종 형태는 W12가 정한다.

**할 일**

1. `requirement_rules_v2.json` 로더와 catalog entry 선택을 구현한다. **활성 catalog는 데이터 파일이고 코드에 박힌 상수가 아니다.** W3 시점의 활성 catalog는 v2지만 W12에서 새 revision으로 바뀌므로, `policy_ref` 문자열을 코드에 하드코딩하거나 테스트에 `v2`로 고정하지 마라. 출력 `policy_ref`는 로드한 catalog가 말하는 값이다.
1-1. **각 rule의 outcome 매핑을 코드에 박지 마라.** catalog JSON이 rule마다 `outcomes` 객체(예: `{"display_location_present": "PASS", "display_location_absent": "UNKNOWN"}`)를 갖고 있다. 구현은 「조건 판정 → 조건 key」까지만 하고 key→outcome 변환은 **데이터에서 읽는다.** 이렇게 해야 W12의 `UNKNOWN → WARN`이 데이터 한 줄 변경이 되고, 같은 rule을 두 번 고치지 않는다.
2. `evaluate_requirements()`에서 `rule_codes` 인수를 제거하고 `time_resolution` 인수를 추가한다(§5.13). 공개 함수 시그니처 변경이므로 `README.md`의 공개 함수 설명과 모든 호출부를 함께 고친다.
3. `EVIDENCE` 기본 4개, `FINAL_PACKAGE` 무조건 15개를 catalog에서 선택해 실행한다.
4. 시각 표시 분기는 `TimeResolution.status`와 `post_stamp.reason_code`로 **정확히 하나**를 고른다. `post_stamp.needed` 단독 분기 금지(§5.7).
5. 신규 rule을 구현한다: `package.event.violation_visible_in_report_video`, `package.event.pre_context_present`, `package.event.post_context_present`, `package.location.present`, `package.time.display_unresolved`.
6. `package.evidence.situation_unconfirmed` → `package.evidence.situation_response`로 교체하고 `NOT_ASKED`/필드 부재를 `UNKNOWN`으로 처리한다.
7. `package.report.content_length`는 렌더 입력이 부족할 때 예외 대신 `UNKNOWN`(`report.inputs_incomplete`)으로 둔다(§5.8).
8. §5.12의 구성 오류 전부를 `PolicyConfigurationError`로 처리하고 정상 `RequirementReport`를 발행하지 않는다. `overall=ERROR` 같은 값을 만들지 마라.

**완료 조건 (테스트)**

- 시각 표시 selector 네 경우 각각 정확히 하나의 rule이 선택됨
- selector 결과가 0개이거나 2개 이상일 때 정상 Report 미발행
- 미등재 `policy_ref`, 지원하지 않는 rule code, 빈 rule 목록, code 중복, 관찰 fact 구조 오류 각각에서 정상 Report 미발행
- `NOT_ASKED`가 `USER_UNSURE`로 자동 치환되지 않음
- 렌더 입력 부족이 예외가 아니라 `UNKNOWN`으로 나옴
- ~~`EVIDENCE` scope의 위치 부재가 `WARN`, `FINAL_PACKAGE`의 위치 부재가 `UNKNOWN`으로 **다르게** 판정됨~~ → **D1 종결로 폐기.** 두 scope 모두 `WARN`이다(§5.4의 D1 블록·ADR-003 §5.5). **「다르게 판정됨」을 테스트로 고정하지 마라** — W12에서 곧바로 뒤집히고, 그 변경이 회귀처럼 보이게 된다. 위치 판정 테스트는 W12에서 최종 형태로 한 번만 쓴다

**하지 말 것**

- `EvidenceRecord`에 `post_stamp`를 투영(Final Contract 변경이다)
- `category`에 `EVENT` 같은 새 값 신설(§5.6 — Contract §3의 7개만 사용)
- Scenario별 rule 생략 허용(§5.5)
- `pre_event_seconds` 같은 초 수를 정책 데이터로 저장(§5.6)
- `AssetFacts.duration`/`timeline_range`로 전후 상황을 추정 — 판정 입력은 실제 관찰 fact다

### W4 — K4 registry v2 개정과 provenance 테스트

**근거:** ADR §6.4~§6.10, §6.12

**할 일**

1. [`decisions/source-kind-registry.md`](../decisions/source-kind-registry.md)를 v2로 개정한다. 변경은 `case.user_correction` 한 행이다(§6.10). v1 표의 의미를 덮어쓰지 말고 v1 기준으로 만들어진 기존 Artifact가 재현 가능하도록 revision 구조로 기록한다.
2. 비시각 9개 semantic path의 `kind`·`source.ref`·`observability`·`label_key`·`user_corrected`·`needs_review`를 §6.6대로 검증하는 테스트를 추가한다. 현재 `test_correction_head_validates_type_chain_and_actual_application`은 `value`·`user_corrected`·`correction_refs`만 본다.
3. 정정에서 유도된 `safety_report_type`·`violation_expression`이 매핑 kind와 `INFERRED`를 유지하는지 테스트한다(§6.7).
4. 사용자가 유도값 자체를 직접 고친 경우 그 head가 매핑 결과를 대체하는지 테스트한다.
5. `occurred_at`이 `observability`·`source.ref`를 갖지 않는지 회귀 테스트한다(불변조건 15).
6. `label_key=null`이 `validate_contract`와 공용 validator에서 거부되지 않는지 확인한다.

**하지 말 것**

- 새 `source.kind`나 `label_key` 신설(§6.8 — UI 문구 확정 후 별도 revision)
- `occurred_at` 경로와 `case.user_location_hint` 변경(§6.9)
- head가 아닌 correction이나 `TIME_HINT_EDIT`을 provenance 근거로 승격(§6.5)

### W5 — adapter와 테스트 harness 재정렬

**근거:** ADR §5.5·§5.13

**할 일**

1. `tests/evidence/fixtures/adapter_inputs.json`의 `evidence_rules`/`final_rules`를 Runtime 입력에서 **"정책 엔진이 이 목록을 선택했는가"를 확인하는 기대값**으로 전환한다. 목록 내용도 v2가 실제로 선택하는 집합(`EVIDENCE` 4개, `FINAL_PACKAGE` 무조건 15개 + 시각 표시 1개)으로 갱신한다. 파일의 `note`도 그 의미로 갱신한다.
2. `mock_integration.py`가 `time_resolution`을 `evaluate_requirements()`에 전달하도록 고친다.
3. 관찰 fact 키 이름은 catalog의 `observation_fact` 값과 일치시킨다.

**하지 말 것**

- 사건 장면·전 상황·후 상황 관찰 fact를 **새로 지어내지 마라.** 실제 관찰 경로가 없으므로 네 Scenario 모두 이 세 rule은 `UNKNOWN`이 정상이다(§5.15).
- 기존 `mock_only` 표기를 지우거나 test-derived 입력을 공용 Fixture 값처럼 보이게 바꾸지 마라.

### W6 — Artifact 재실행과 변화 기록

**근거:** ADR §5.15 「Artifact 영향」

**할 일**

1. `python -m daesingo.evidence.mock_integration`을 재실행해 `docs/modules/evidence/artifacts/first-completion/`의 baseline 4종과 `run-summary.json`을 갱신한다.
2. 결과가 **v2 재실행 결과**임을 Artifact와 보고서에서 식별 가능하게 한다. v1 결과를 조용히 덮어썼다는 인상을 남기지 마라.
3. Scenario별로 무엇이 바뀌었는지 기록한다: 추가된 check, 바뀐 `policy_ref`, 바뀐 `overall`, 늘어난 `UNKNOWN`.

**반드시 정직하게 다룰 것**

v2에서는 사건 장면·전후 상황 세 rule이 관찰값 없이 `UNKNOWN`으로 들어오므로, **H의 `FINAL_PACKAGE` `overall`이 `UNKNOWN`이 되어 `pkg_h001`이 더 이상 발행되지 않을 수 있다.** 이 경우:

- 관찰 fact를 지어내 Package를 되살리지 마라.
- 실제 결과를 그대로 기록하고, Package가 성립하려면 어떤 관찰 입력이 실제로 필요한지(통합 항목 I4의 범위를 사건 장면·전후 상황까지 넓혀야 한다는 §5.15의 지적) 후속 목록에 남겨라.
- `build_report_package`의 조립·guard 경로 자체에 대한 회귀 검증은 test-derived 입력을 명시한 단위 테스트로 유지하라. 그 테스트 결과를 공용 Scenario의 Package 완료로 보고하지 마라.

관찰값이 없어 `UNKNOWN`이 늘어난 것을 회귀 실패로 표시하지 마라. 동시에, 그것을 "이전과 동일"로 표현하지도 마라.

**U는 다르다.** 위 경고는 관찰 fact가 없어서 생기는 `UNKNOWN`에 대한 것이고, U의 위치 부재는 관찰 부족이 아니라 **확정된 사실**이다. W12를 먼저 끝냈다면 U의 `overall`은 `WARN`이고 `pkg_u001`이 유지돼야 한다. 여기서 U의 Package가 사라졌다면 W12가 덜 반영된 것이니 「예상된 변경」으로 기록하지 말고 원인을 찾아라(§5.15의 D1 정정 블록).

### W7 — 문서 갱신

1. `src/daesingo/evidence/README.md` — 공개 함수 시그니처(`rule_codes` 제거·`time_resolution` 추가), 정책 데이터 목록(K1 파일과 새 catalog revision 추가), 재현 명령, 상태 문단.
2. [`first-completion-result.md`](../first-completion-result.md) — 추적표에 K1~K4와 D1 반영 결과를 반영한다. Q1 행(「U 정상 Package는 `package.input.location_missing`으로 보류」)이 D1 종결로 바뀐다. 기존 완료 조건을 축소하거나 체크박스를 일괄 완료 처리하지 마라.
3. **실행·검수 기록은 새 리뷰 보고서로 남긴다.** `docs/modules/evidence/reviews/13_adr-002-003-implementation_<YYYY-MM-DD>.md` 형태로 작성하고 `reviews/README.md` 목록에 추가한다. **번호 11·12는 이미 사용 중이다.**
4. **ADR 본문의 결정 내용을 고쳐 쓰지 마라.** ADR은 결정 기록이고 실행 증빙의 소유자가 아니다(`docs/README.md`·`prompts/README.md`의 폴더 역할 구분). 구현 중 ADR의 사실관계 오류를 발견하면 직접 고치지 말고 발견 사실과 근거를 보고에 남겨 김준영이 ADR §7(변경 규칙)로 처리하게 하라.
5. 이 프롬프트 파일과 `prompts/README.md`는 발주 이력이다. 수정하지 마라.

### W8 — 후속·통합 목록 갱신

구현하면서 확정된 후속 항목을 결과 문서와 리뷰 보고서에 남긴다. 최소한 다음은 상태를 갱신하거나 유지한다.

- **D1(Q1) U 위치 결론** — **종결됨**(ADR-003, 2026-09-14). 이 작업의 W10~W12가 그 반영이다. 남는 후속은 아래 셋이고 **`evidence` 범위가 아니다**: `CaseView`의 `report_field_states.location` 필수 존재 문구(`case`), 사용자 고지 code 등재(`case`), 공용 fixture 재렌더(I2). 대신 처리하지 마라.
- **④ 선택적 위치 질의 경로** — `DEFERRED`. C-1 사용자 검증 관찰 결과가 여는 조건이다(ADR-003 §5.7). 열지 마라.
- **`WARN` Package 최소 케이스가 `unknown_abstain_partial_001` 하나** — `scenario_blocked_001` 부재와 같은 자리. Mock 커버리지 후속으로 유지한다.
- **I4 범위 확장** — 관찰 전달 경로를 번호판·시각에서 사건 장면·전 상황·후 상황까지 넓혀야 한다(§5.15).
- **`ReportPackage.assets` 확장**(최대 4개 첨부) — Contract 변경 검토 필요(§3.5·§3.9).
- **대상별 `label_key` 신설** — UI 문구 확정 후 새 registry revision(§6.8).
- **`PLATE_IMAGE` 생성·크기 측정 경계** — [`reviews/11_plate-image-generation-and-size-handoff_issue-draft_2026-09-13.md`](../reviews/11_plate-image-generation-and-size-handoff_issue-draft_2026-09-13.md).
- **비시각 correction의 실제 Consumer 검증 부재** — 공용 Mock에 `occurred_at` 대상 correction 하나뿐이다. K4 검증은 evidence 단위 테스트 범위이며 I7·I8에서 실제 case correction과 CaseView projection으로 확인한다(§6.11).

### W10 — D1 계약 개정 `report-package/v1 → v1.1`

**근거:** ADR-003 §5.2·§5.3

**할 일**

1. `docs/architecture/contracts/contract-requirement-report-package.md` §7의 `report_inputs.location`을 nullable로 개정한다. 모양과 규범 문장은 ADR-003 §5.2가 소유한다 — 키 생략 금지, `null`은 확정된 부재, 빈 객체 금지.
2. §8.2의 최소 snapshot 항목이 「없으면 없다는 사실까지」 포함함을 명시한다.
3. contract version 표기를 `v1.1`로 올리고, 문서 머리말의 개정 이력에 근거(ADR-003·이슈 #48)를 남긴다.

**완료 조건**

- 계약 본문만 읽고도 `location: null`이 적법하며 그것이 「아직 오지 않은 값」이 아님을 알 수 있다.
- 개정 범위가 §7·§8.2·version 표기에 한정된다.

**하지 말 것**

- 다른 절을 정리·재배치하지 마라. 이 개정은 위치 의미 하나만 바꾼다.
- `location`에 `coord`를 추가하지 마라(ADR-003 §8).
- 다른 계약 파일을 건드리지 마라.

### W11 — 장소 슬롯 없는 신고문 template `safety-report-policy/v1 → v1.1`

**근거:** ADR-003 §5.4

**할 일**

1. `decisions/safety-report-policy-v1.md`를 덮어쓰지 말고 v1.1을 발행한다. `policy_ref`는 `safety-report-policy/v1.1`이다(W12의 `referenced_policies.report_template`이 이 값을 가리킨다). 장소 구절이 없는 변형을 **별도 `template_ref`로 등재**한다. 기존 2종은 그대로 둔다.
2. Renderer 불변조건 2의 입력 슬롯에서 `location.display_text`를 선택으로 내린다. 불변조건 5는 그대로다.
3. renderer가 위치 유무에 따라 template을 고르도록 구현한다. 장소 구절은 **지어내지 않고 뺀다.**

**완료 조건**

- 위치 없는 U가 렌더되고, 그 결과가 `template_ref`로 재현된다(불변조건 1·4).
- 값을 지어내지 않는다는 점이 테스트로 고정돼 있다.

**하지 말 것**

- 장소 자리에 「위치 미상」·「확인 필요」 같은 문구를 넣지 마라. 구절 자체를 뺀다.
- 기존 Package의 `template_ref`·`policy_ref`를 다시 쓰지 마라.

### W12 — D1 catalog revision과 구현

**근거:** ADR-003 §5.1·§5.5 · §5.6

**할 일**

1. `requirement_rules_v2.json`을 덮어쓰지 말고 **새 revision을 발행**한다(§7). 파일은 `src/daesingo/evidence/requirement_rules_v3.json`, `policy_ref`는 `policy/requirement-rules-v3`, `supersedes_policy_ref`는 `policy/requirement-rules-v2`로 둔다. `decision_ref`는 ADR-003을 가리킨다. **v2의 나머지 내용은 그대로 계승한다** — rule을 더하거나 빼지 않는다(15개 유지, §5.14).
   - `package.location.present` — 위치 부재를 `UNKNOWN`이 아니라 `WARN`으로
   - `package.report.content_length` — 필수 입력을 **선택된 template 기준**으로 읽는다. 장소 슬롯이 없는 template이면 위치는 필수 입력이 아니다
   - `referenced_policies.report_template` — `safety-report-policy/v1` → **`safety-report-policy/v1.1`**. W11이 하위 정책의 새 version을 내므로 §7의 「하위 정책이 새 version을 내면 K3도 그 version을 가리키는 새 revision이 필요하다」가 여기 걸린다. 이 한 줄을 빠뜨리면 catalog가 장소 없는 template이 없는 정책을 가리키게 된다
2. `requirements.py`에서 `PackageNotReady("package.input.location_missing")`을 제거한다. 위치 부재만으로 Package를 보류하지 않는다.
3. `validation.py`의 `location` 검사를 「키 필수 + `null` 허용」으로 바꾼다. 키가 없거나 빈 객체면 위반이다.
4. `_location_snapshot`이 대표값을 못 만들 때 `null`을 내도록 한다.
5. **§5.12의 갈래 분류를 지킨다.** 위치 부재는 「정책 엔진 오류」도 「업무상 `UNKNOWN`」도 아닌 **`WARN`**이다. §5.12의 `UNKNOWN` 목록에서 「Package 표시용 위치가 아직 없음」이 빠졌다(§5.12의 D1 블록).

**완료 조건**

- `validate_report_package(pkg_u001)`이 `[]`를 돌려준다.
- U의 `FINAL_PACKAGE` `overall`이 `WARN`이고 `PACKAGE_READY`가 성립한다.
- 두 rule 중 하나만 바꾸면 U가 `UNKNOWN`으로 떨어진다는 사실이 테스트로 드러난다.
- 출력 `policy_ref`가 `policy/requirement-rules-v3`이고, 그 값이 코드 상수가 아니라 로드한 catalog에서 온다.
- `EVIDENCE`·`FINAL_PACKAGE` 두 scope 모두 위치 부재를 `WARN`으로 판정한다(§5.4의 D1 블록). **위치 판정 테스트는 여기서 처음이자 마지막으로 쓴다.**

**하지 말 것**

- **두 rule 중 하나만 바꾸지 마라.** `content_length`를 그대로 두면 overall이 `UNKNOWN`이 되고 계약 §8.1로 Package가 다시 사라져 D1이 무효가 된다.
- `evidence.location.present`(EVIDENCE scope)는 이미 `WARN`이다. 건드리지 마라.
- 사용자 고지(notice)를 `evidence`에서 만들지 마라. code 이름·`message_key`·발동 조건은 `case` 소유다(ADR-003 §5.6·§8). `notices[].actions[]`를 확장하지 마라.
- 선택적 위치 질의(④)를 구현하지 마라. `DEFERRED`다(ADR-003 §5.7).
- 공용 `data/mock` fixture를 고치지 마라. `pkg_u001`의 `template_ref`·신고문 동기화는 통합 항목 I2(`case`)다.

### 실행 순서

W10·W11은 문서 개정이라 언제든 할 수 있다. W12는 **W3(catalog 연결)이 끝난 뒤** 그리고 **W6(Artifact 재실행) 전에** 수행한다.

**순서가 뒤바뀌면 틀린 증빙이 남는다.** §5.15의 D1 정정 블록이 그 이유를 적고 있다 — v2 그대로 재실행하면 U의 `package.location.present`와 `package.report.content_length`가 **둘 다 `UNKNOWN`**이 되어 `overall=UNKNOWN`, 계약 §8.1로 `pkg_u001`이 사라진다. 그 상태를 baseline으로 기록하면 「Package가 사라진 것이 정상 결과」라고 증빙에 남게 된다. D1 반영 후에는 U가 `WARN`이고 `PACKAGE_READY`가 성립한다.

권장 순서: **W1 → W2 → W3 → W10 → W11 → W12 → W4 → W5 → W6 → W7 → W8 → W9**

`requirement-rules-v2`는 아직 어떤 Artifact도 이 catalog로 생성된 적이 없다. 그래도 덮어쓰지 않는다 — ADR-002 §7의 규칙이다. 대신 **v2가 채택됐으나 첫 실행 전에 새 revision으로 대체됐다**는 사실을 W7의 문서와 W9의 ADR에 남겨라.

### W9 — 구현 ADR 작성 (마지막 순서)

**W1~W8과 W10~W12를 모두 끝내고 검증까지 통과한 다음** `docs/modules/evidence/adr/`에 새 구현 ADR을 작성한다. 파일명은 기존 관례를 따라 `adr-<주제>.md` 형태로 정하고, ID는 다음 번호(**`ADR-EVIDENCE-004`** — 003은 D1 결정이 이미 쓰고 있다)를 쓴다. `adr/README.md` 목록에 추가한다.

**이 ADR이 기록하는 것 — 정책이 아니라 구현 구조의 선택과 그 이유다.**

- K1·K2·K3 정책 데이터를 어떤 파일·구조로 두고 어떻게 로드·검증하는지, 그리고 그 구조를 고른 이유
- D1 반영에서 template 선택과 필수 입력 판정을 어떤 구조로 갈랐는지, 그리고 catalog revision을 v2 위에 어떻게 얹었는지
- `evaluate_requirements()`의 인수 변경을 어떤 형태로 흡수했는지(호출부 영향 포함)
- catalog 기반 rule 선택과 시각 표시 조건부 분기를 어떤 구조로 구현했는지
- 관찰 fact 입력의 표현 방식과, 그것이 Runtime wire schema가 아니라는 근거
- 정책 구성 오류(`PolicyConfigurationError`)와 업무 사실 부족(`UNKNOWN`)을 코드에서 어디로 갈랐는지
- 검토했지만 채택하지 않은 대안과 그 이유
- 이 구현이 **확정하지 않은 것**(D1 미결, 관찰 입력 부재, Contract 변경 검토 필요 항목)

**지켜야 할 경계**

- [`adr/README.md`](../adr/README.md)의 원칙 그대로다. Final Data Contract나 다른 모듈의 Owner 경계를 바꾸는 결정을 이 ADR에 담지 마라.
- **ADR-EVIDENCE-002·003의 결정을 다시 서술하거나 수정하지 마라.** 정책 원문은 002·003이 소유하고, 004는 "그 결정을 이렇게 구현했다"만 기록한다. 중복 서술 대신 절 번호를 가리켜라.
- 실행 로그·검사 결과·Scenario별 판정 변화는 ADR이 아니라 `reviews/13_...` 보고서가 소유한다(W7-3). ADR에는 구조 결정만 남긴다.
- 미결을 구현 편의로 확정하지 마라. 논의 전 항목은 `PENDING_DISCUSSION`으로 남긴다.
- 구현하면서 ADR-002·003의 사실관계 오류나 조항 간 충돌을 발견했다면, 그 ADR을 고치지 말고 004의 별도 절에 "발견한 불일치와 근거"로 남겨 김준영이 ADR §7(변경 규칙)로 처리하게 하라.

## 7. 모호함이 나왔을 때

| 분류 | 행동 |
| --- | --- |
| 내부 구현 선택(파일 분리·함수 이름·테스트 구조) | 기존 관례와 최소 변경 원칙으로 스스로 결정하고 계속한다 |
| ADR이 이미 확정한 값의 반영 | 근거 절을 남기고 구현한다. 재확인을 요청하지 않는다 |
| ADR 조항끼리 또는 ADR과 Contract가 충돌 | 양쪽 원문 조항과 실제 파일 경로를 기록하고, 종속된 부분만 보류한다 |
| 새 필드·enum·nullable·Owner 경계 결정이 필요 | `Contract 변경 검토 필요`로 분리한다. 김준영이 PM이라는 이유로 다른 Owner의 미결을 대신 확정하지 마라 |
| 상대 모듈의 실제 구현 부재 | 동일 Contract의 Mock으로 연결을 검증하고 실제 접합은 통합 대기로 기록한다 |

**입력이 없는데 결과를 만들어내지 마라.** 가시성 PASS, 기한 적합, 용량 적합, 위치·번호판·시각 확정은 실제 입력이나 명시된 Mock 근거가 있을 때만 성립한다. D1 한 건이나 관찰값 부재를 이유로 W1~W8의 나머지를 멈추지도 마라.

## 8. 반드시 지킬 의미 경계

1차 발주 프롬프트 §7의 경계는 이번에도 그대로 유효하다. 이번 작업에서 특히 위험한 것은 다음이다.

- **정책 구성 오류 ≠ 업무 사실 부족.** 전자는 정상 Report 미발행, 후자는 `UNKNOWN`이다(§5.12의 두 목록).
- **`UNKNOWN` ≠ `BLOCK`.** 둘 다 `PACKAGE_READY`를 성립시키지 않지만 의미가 다르다.
- **번호판 문자열 확정 ≠ 신고영상 가시성**, **발생시각 확정 ≠ 영상 내 시각 표시**(`contract-evidence-record-needs.md` §4.7).
- **`post_stamp`는 정책 결과이지 영상 생성 완료가 아니다.**
- **`EVIDENCE_SUFFICIENT`·`PACKAGE_READY`·`USER_REVIEWED`는 서로 다른 조건이다.** `EvidenceNeeds.items=[]`만으로 어느 gate도 통과 처리하지 마라.
- **사용자 정정·재판독으로 과거 snapshot을 덮어쓰지 마라.** 새 값은 supersede 연결로 남긴다.
- **ID는 opaque ref다.** 접두어로 종류를 추측하지 마라.
- `evidence`는 순수 함수 모듈이다. 다른 도메인 모듈을 호출하지 않고 Job을 발주하지 않는다.
- **위치 부재는 「확정된 사실」이지 「아직 오지 않은 값」이 아니다.** `location: null`과 키 부재를 같은 것으로 다루지 마라(ADR-003 §5.2).
- **값을 지어내지 않는 것과 슬롯을 비우는 것은 다르다.** 장소 구절은 문장에서 빼고, placeholder 주소·임의 좌표·역지오코딩은 넣지 않는다.
- **위치 없음을 사용자에게 말하는 주체는 `case`다.** `evidence`는 판정과 발행 여부만 정한다.

## 9. 실행·검증

저장소 루트의 PowerShell에서 실행한다. **변경 전과 변경 후를 모두 실행하고 비교하라.**

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/evidence -p 'test_*.py'
python -m daesingo.evidence.mock_integration
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
git diff --check
```

D1 반영(W10~W12) 후에는 다음도 함께 확인하고 결과를 기록한다(ADR-003 §9).

- `validate_report_package(pkg_u001)` → `[]`
- U의 `FINAL_PACKAGE` `overall`이 `WARN`이고 `PACKAGE_READY`가 성립한다
- 장소 없는 신고문이 `template_ref`로 재현되고, 장소 값이 지어내지지 않는다
- `python data/mock/validate_mock_pack.py`는 **보강하지 않은 상태 그대로** 돌린다. `report_inputs` 내부 모양 검사 추가는 통합 항목 I2 이후의 별도 작업이다

- 실제로 만들고 실행한 명령만 기록하라. 존재하지 않는 명령을 실행 가능하다고 적지 마라.
- 공용 validator PASS는 스키마·정책 의미·baseline·E2E·Owner 수락의 증거가 아니다. 알려진 불일치를 검사에서 제외해 놓고 전체 PASS로 표현하지 마라.
- 테스트는 public 경계의 결과를 관찰해야 한다. 구현 함수를 다시 호출해 expected를 만들거나 Fixture 복사만으로 계산 정확성을 증명하지 마라. 특히 K2의 날짜 계산과 K1의 경계값은 기대값을 직접 적어라.
- 리뷰 단계에서 적용 가능한 code review 스킬이 있으면 읽고 따른다. Contract 위반, 참조 오류, 상태 혼동, 입력·과거 결과 변형, 타 모듈 의존, 테스트가 주장하는 범위를 점검하고 내 범위의 문제를 고친 뒤 영향받는 검사를 다시 실행하라.

## 10. 커밋 전략

변경을 한 덩어리로 몰아넣지 말고 이력이 보기 좋게 나뉘어 있으면 된다. 커밋을 먼저 쪼개 놓고 구현하는 것이 아니라, **구현이 끝난 뒤 실제 diff를 읽고 그 diff에 맞는 커밋 단위로 나눈다.** 여기 적힌 것은 권장 기준이며, 완벽한 분할을 위해 시간을 쓰지 마라.

### 10.1 먼저 기존 컨벤션을 확인한다

전략을 세우기 전에 저장소의 현재 관례를 직접 확인하라. 아래는 작성 시점 관찰이며, **실행 시 다시 확인해 실제와 다르면 실제를 따른다.**

- **커밋 메시지:** `git log --oneline -30`으로 확인한다. 작성 시점 관례는 `type(scope): 한국어 요약` — 사용된 type은 `feat`·`fix`·`test`·`docs`·`mock`, scope는 모듈명(`evidence`). 제목은 한국어 명사형 요약이고 영어 혼용이나 마침표를 쓰지 않는다.
- **코드 컨벤션:** `src/daesingo/evidence/`의 기존 파일을 읽고 맞춘다. 작성 시점 관례는 `from __future__ import annotations`, 모듈 docstring 1줄, 내부 헬퍼 `_` 접두어, 타입 힌트 사용, 긴 한 줄을 허용하는 포매팅, 주석 최소화(계약·정책 근거가 필요한 곳에만). **새 포매터·린터·설정 파일을 도입하지 마라.** 저장소 루트에 채택된 lint/format 설정이 있으면 그것을 따르고, 없으면 주변 코드를 따른다.
- **테스트 컨벤션:** `tests/evidence/`의 기존 클래스·메서드 이름과 구조를 따른다. 새 테스트 프레임워크를 도입하지 마라(현재 `unittest`).
- **문서 컨벤션:** `docs/README.md`의 폴더 역할과 각 폴더 `README.md`의 목록 갱신 방식을 따른다.
- **JSON 정책 데이터:** `deadline_policy_v1.json`·`requirement_rules_v2.json`의 키 명명·들여쓰기·근거 필드 구성을 따른다.

### 10.2 diff를 읽고 커밋 단위를 설계한다

1. `git status`와 `git diff`(+ 신규 파일은 `git add -N` 후 `git diff`)로 **전체 변경을 실제로 읽는다.** 기억이 아니라 diff를 근거로 한다.
2. 이 브랜치에는 **작업 시작 전부터 있던 미커밋 변경**(「이 프롬프트 §2」의 스냅샷 참고)이 섞여 있다. 그것을 내 작업 커밋에 섞지 말고 별도 커밋으로 분리한다.
3. 권장 기준:
   - 정책 데이터 추가와 그것을 읽는 구현은 같은 커밋에 둔다(데이터만 있고 동작이 없는 중간 상태를 만들지 않는다).
   - K1 / K2 / K3 / K4는 서로 다른 결정이므로 섞지 않는다. K3의 catalog 연결이 K1·K2 rule 편입을 포함하므로 순서는 K1 → K2 → K3 → K4로 둔다.
   - 구현과 그 구현을 검증하는 테스트는 같은 커밋에 둔다.
   - 공개 함수 시그니처 변경(`rule_codes` 제거·`time_resolution` 추가)은 호출부·README 갱신까지 한 커밋으로 묶어 **어느 커밋에서도 저장소가 깨지지 않게** 한다.
   - Artifact 재실행 결과(baseline·run-summary)는 생성 코드 변경과 분리해 그 자체로 한 커밋으로 둔다. 재실행 산출물의 큰 diff가 코드 변경을 덮지 않게 한다.
   - 문서(결과 추적표·리뷰 보고서·registry v2·ADR-003)는 코드와 분리한다.
4. 각 커밋은 그 시점에 `python -m unittest discover -s tests/evidence -p 'test_*.py'`가 통과하는 상태를 목표로 한다. 중간 커밋에서 불가피하게 깨진다면 그 사실을 커밋 메시지 본문에 한 줄로 적는다.

### 10.3 커밋 메시지

- 제목은 저장소 관례(`type(scope): 요약`)를 따른다. 무엇을 했는지가 아니라 **무엇이 달라졌는지**를 적는다.
- 제목 한 줄로 충분하면 본문을 쓰지 않는다. 필요할 때만 짧게 덧붙인다(근거 절 번호, 의도적으로 바뀐 동작). 변경 파일 목록을 나열하지 마라 — diff가 이미 갖고 있다.
- 정책 결정 자체를 커밋 메시지에서 다시 설명하지 마라. 원문은 ADR이 소유한다.
- **커밋 메시지를 리뷰어에게 보내는 설명문으로 쓰지 마라.** 특정 사람을 향한 당부, 봐 달라는 요청, 변명은 적지 않는다.
- `git commit` 메시지 끝에 아래 한 줄을 붙인다. 다른 사람을 author나 co-author로 적지 마라.

  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  ```

### 10.4 커밋할 때 지킬 것

- **커밋은 승인을 다시 묻지 말고 직접 수행한다.** 분할이 마음에 안 들면 나중에 다시 정리하면 된다. 다만 이미 만든 커밋을 `reset --hard`·`rebase`·`push --force`로 되돌리지 마라 — 새 커밋으로 고친다.
- `git add -A`로 뭉뚱그리지 말고 경로를 지정해 stage한다. 의도하지 않은 파일이 들어가는 것을 막는다.
- `docs/management/secret/`·`docs/management/submissions/`·`doc/`·`tmp/`·`__pycache__`·`.ruff_cache`를 커밋하지 마라. `git add -f` 금지.
- `.github/workflows/{assign-mentor,notify-discord,convention-check}.yml`과 `.github/CODEOWNERS`를 커밋에 포함하지 마라.
- 커밋 전 `git diff --check`로 공백 오류를 제거한다.
- **push·PR 생성은 하지 마라.** 김준영이 직접 한다.

## 11. 남길 산출물

1. K1 정책 데이터 파일과 K1~K3 구현 코드.
2. 새 테스트와 실행 방법. W1~W4·W10~W12의 완료 조건이 각각 어느 테스트로 확인되는지 대응이 보여야 한다.
3. 갱신된 H/U/P/R baseline과 `run-summary.json`, v1 대비 변화 목록.
4. `reviews/13_adr-002-003-implementation_<date>.md` — 실행 증빙과 검수 기록.
5. 갱신된 `src/daesingo/evidence/README.md`·`first-completion-result.md`·`decisions/source-kind-registry.md`(v2).
6. **D1 산출물** — `contract-requirement-report-package.md` v1.1, `safety-report-policy` v1.1과 장소 없는 template, `requirement_rules_v3.json`. v2 파일은 지우지 않고 남긴다(채택됐으나 실행 전에 대체된 revision).
7. 후속·통합 대기 목록(W8) — 항목·담당자·영향 경로·완료에 필요한 구체적 조치.
8. `adr/adr-*.md`(ADR-EVIDENCE-004) — 구현 구조 결정과 채택하지 않은 대안(W9).
9. 「이 프롬프트 §10」에 따라 나눈 커밋들.

보고서의 상태 표기(`검증 완료` / `Mock 연결 검증 완료` / `통합 대기` / `Contract 변경 검토 필요` / `결정 대기`)는 회의·작업 관리용이며 Runtime Contract enum이 아니다.

## 12. 최종 보고

최종 답변에 다음을 포함한다.

1. K1·K2·K3·K4와 D1 각각의 반영 범위와 남은 부분. D1은 계약·정책·catalog·구현 네 층 모두가 반영됐는지 층별로 적는다.
2. 주요 코드·데이터·테스트·문서·Artifact 파일 링크.
3. **v2 적용 전후의 H/U/P/R 판정 변화.** 어떤 check가 추가됐고, 어떤 `overall`이 바뀌었고, Package 발행 여부가 바뀌었다면 그 이유.
4. 실행한 검사와 결과, 그리고 **그 검사로 증명하지 못한 것**.
5. 실제 baseline / upstream Mock / test-derived 입력 / Consumer Mock / 실제 Consumer 접합의 구분.
6. 미완료·통합 대기·Contract 변경 검토 필요 항목과 담당자.
7. 만든 커밋 목록(해시·제목).
8. Merge 회의에서 재현할 정확한 실행 명령과 1~2문장 요약.

"코드 작성 완료", "테스트 통과"만으로 종료하지 마라. **어떤 정책이 이제 실제로 강제되는지, 어떤 판정은 아직 관찰 입력이 없어 성립하지 않는지**를 증거로 설명하라.
