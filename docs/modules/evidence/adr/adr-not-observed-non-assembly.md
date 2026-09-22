# ADR-EVIDENCE-007: `NOT_OBSERVED` VisualEvidence는 `EvidenceRecord` 이전에 끝나는 정상 결과다

> 상태: **ACCEPTED**
>
> 결정일: `2026-09-22`
>
> Decider / Owner: 김준영 (`evidence` Owner · `evidence-record/v1.3` Contract Owner · PM)
>
> Consulted: 유소연 (`case` — Fine 결과 소비 분기) · 서어진 (`search` — `visual-evidence/v1.0` Producer) — [이슈 #137](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/137)
>
> 적용 범위: `evidence` public boundary, `case`의 Fine 결과 소비 경로, `contract-evidence-record-needs.md` 소비 규칙 명확화
>
> 근거 목록: [`reviews/17_issue-137-not-observed-integration-review_2026-09-22.md`](../reviews/17_issue-137-not-observed-integration-review_2026-09-22.md) · [`contract-visual-evidence.md`](../../../architecture/contracts/contract-visual-evidence.md) §4-1·§12 · [`adr-visual-evidence.md`](../../../architecture/contracts/adr/adr-visual-evidence.md)

## 1. 목적

`verification=NOT_OBSERVED`(그리고 계약상 반드시 따라오는 `visual_event_type=null`)인 Fine 결과를 **누가 어디서 끝내는지**를 확정한다. 지금은 이 값이 `case`에서 분류되지 않고 `evidence`까지 내려와 `ContractInputError`로 종료되며, Real E2E가 여기서 멈춘다.

## 2. 배경

### 2.1 유효한 결과가 계약 위반으로 처리되고 있었다

`contract-visual-evidence.md` §4-1은 `NOT_OBSERVED`를 「Fine은 정상 실행됐으나 해당 사건을 지지하는 근거가 없음」으로 정의하고 hard-negative / candidate rejection을 표현할 수 있는 **유효한 결과**라고 명시한다. §12는 Consumer `evidence`가 `NOT_OBSERVED`와 `UNCERTAIN`을 **별도 입력 상태**로 처리해야 한다고 정한다.

그런데 구현은 두 곳에서 그 규칙을 빠뜨렸다.

| 위치 | 당시 동작 |
| --- | --- |
| `evidence/assembly.py::_event_values()` | `verification` 값 공간에는 세 enum을 모두 허용해 놓고, `visual_event_type is None` 분기에서 다시 `UNCERTAIN`만 요구했다 — 두 조건의 허용 집합이 어긋나 `NOT_OBSERVED`는 선언상 허용이지만 도달 불가능했다 |
| `case/real_e2e.py` | Fine 결과를 분류하지 않고 IncidentClip·readout·TimeResolution을 거쳐 `assemble_evidence()`를 반드시 호출했다 |

2026-09-22 로컬 재현:

```text
verification=NOT_OBSERVED, visual_event_type=null, situation_response=None
→ ContractInputError: only an UNCERTAIN VisualEvidence may produce a null visual event
```

### 2.2 `NOT_OBSERVED`와 `UNCERTAIN`은 합칠 수 없다

`UNCERTAIN + USER_UNSURE`는 구체 사건 유형을 확정하지 못했지만 **사용자가 진행을 택한** 기존 generic 신고 경로다(`ADR-EVIDENCE-002` 계열, `scenario_unknown_abstain_partial_001`). `NOT_OBSERVED`는 Fine이 그 후보를 **기각한** 결과다.

둘을 같은 fallback으로 합치면 다음이 따라온다.

- 영상에서 사건이 성립하지 않았다는 결과와 판단이 불충분하다는 결과가 같은 값이 된다.
- 실제 사용자 응답이 없는데 `situation_response=USER_UNSURE`를 자동 생성해야 하는 압력이 생긴다.
- `evidence.visual_event.present`가 WARN generic 경로로 평가되어, 관찰되지 않은 위반에 대해 generic 신고문과 `ReportPackage`가 만들어질 수 있다.

## 3. 결정 상태

| ID | 항목 | 상태 |
| --- | --- | --- |
| D3 | `NOT_OBSERVED`는 `EvidenceRecord` 생성 이전에 종료되는 정상 비채택 결과다 | **ACCEPTED** |
| D3-a | 소비 결정을 `evidence` public boundary의 tagged result 한 곳에 닫는다 | **ACCEPTED** |
| D3-b | `assemble_evidence()` 직접 호출은 가짜 Record 대신 `VisualEventNotAssembled`로 막는다 | **ACCEPTED** |
| D3-c | `case`가 Fine 결과를 downstream 이전에 분류한다 | **ACCEPTED** |
| D3-d | VisualEvidence·Fine 실행·Usage provenance를 보존한다 | **ACCEPTED** |
| D3-e | 계약 문서는 소비 규칙 명확화만 하고 버전을 올리지 않는다 | **ACCEPTED** |
| D3-f | 자동 후보 순회·자동 채택·사용자 확인 없는 Package 정책 | **DEFERRED** — §7 |

## 4. 결정

### 4.1 D3 — 세 상태의 결말을 분리한다

| Fine 결과 | 결말 |
| --- | --- |
| `OBSERVED + non-null visual_event_type` | 기존 accepted downstream으로 조립 |
| `UNCERTAIN + null`, 사용자 응답 전 | 기존 대기 — Record 미생성 |
| `UNCERTAIN + null + USER_UNSURE` | 기존 generic EvidenceRecord/WARN 경로 유지 |
| `NOT_OBSERVED + null` | **정상 비조립 종료** — Record·RequirementReport·ReportPackage 없음, 예외 없음 |
| `NOT_OBSERVED + non-null visual_event_type` | producer 계약 위반으로 차단(`ContractInputError`) |

### 4.2 D3-a — 의미를 public boundary 한 곳에 닫는다

`verification` 문자열 비교를 호출부마다 흩뿌리면 같은 판단이 여러 곳에서 각자 표류한다. `daesingo.evidence.classify_visual_evidence()`가 VisualEvidence 하나를 받아 tagged 결과를 돌려주고, 소비자는 그 값만 본다.

```text
ASSEMBLE                  → EvidenceRecord 조립 가능
AWAIT_SITUATION_RESPONSE  → UNCERTAIN, 사용자 응답 대기(기존 규칙 그대로)
NOT_ASSEMBLED             → 정상 비조립 종료, reason_code=evidence.visual_event.not_observed
```

이 함수는 **분류만** 한다. 다음 후보를 고르는 일은 `evidence`의 책임이 아니므로 여기 없다.

### 4.3 D3-b — 직접 호출은 막되, 오류 종류를 구분한다

`assemble_evidence()`를 `NOT_OBSERVED`로 직접 호출하면 새 `VisualEventNotAssembled`(코드 `evidence.visual_event.not_observed`)로 멈춘다. `ContractInputError`를 쓰지 않는 이유는 **producer가 계약을 어긴 게 아니기 때문**이다 — 호출자가 분류를 건너뛴 것뿐이고, 같은 질문을 `classify_visual_evidence()`에 물으면 예외 없이 답이 나온다.

예외를 잡아 성공처럼 처리하거나 `value=null`인 빈 `EvidenceRecord`를 만드는 방식은 채택하지 않는다. 전자는 사유를 지우고, 후자는 §2.2의 generic 승격 문제를 그대로 되살린다.

### 4.4 D3-c — `case`가 downstream 이전에 분류한다

정상 제품 흐름에서 이 판단을 하는 곳은 `case`다. Fine 결과를 받자마자 분류하고, 조립 대상이 아니면 IncidentClip·readout·TimeResolution·evidence를 **시작하지 않는다**. `evidence` 쪽 방어(D3-b)는 잘못된 직접 호출과 미래 consumer를 위한 이중 경계이지 제품 경로의 주 분기가 아니다.

`case`에 새 stage나 `CaseView` 필드를 만들지 않는다. `stage=EVIDENCE_REVIEW` + `evidence_record=null`은 `case-view/v1.4`가 이미 표현하던 상태이고(`view.py`의 해당 분기는 `scenario_infra_failure_001`로 검증돼 있다), 조립 이후 단계는 낙관적 `PENDING` 대신 progress 목록에서 빠진다.

### 4.5 D3-d — 조립하지 않아도 관찰 결과는 남긴다

`adr-visual-evidence.md`는 `evidence`가 `NOT_OBSERVED`를 정상 실행된 유효한 관찰 결과로 **보존**해야 한다고 기록한다. Fine이 후보를 기각했다는 것 자체가 hard-negative FPR 평가와 런타임 진단의 입력이다. 따라서 비조립 결말에서도 원본 VisualEvidence, Fine `AnalysisRun`(`run_id`·`outcome`·`usage_refs`·`usage_summary`), 입력 참조를 그대로 들고 나온다.

### 4.6 D3-e — 계약은 명확화만 한다

`contract-visual-evidence.md` §12는 이미 「`NOT_OBSERVED`와 `UNCERTAIN`을 별도 입력 상태로 처리한다」를 정하고 있다. 이번 구현은 그 문구를 실행한 것이지 새 규칙을 만든 것이 아니므로 **다른 Owner의 계약을 고치지 않는다.**

`evidence`가 소유한 `contract-evidence-record-needs.md`에는 한 줄이 비어 있었다 — v1.3의 「`event.visual_event_type` null 허용」 절이 `UNCERTAIN` 예외만 적고 `NOT_OBSERVED`가 그 예외에 들어오지 않는다는 말을 하지 않았다. 그 문장만 추가한다. 값 공간·스키마가 그대로이므로 `evidence-record/v1.3`을 유지한다.

## 5. 대안과 기각 사유

| 대안 | 기각 사유 |
| --- | --- |
| `NOT_OBSERVED`를 `UNCERTAIN` fallback에 합친다 | §2.2 — 관찰되지 않은 사건에 generic 신고문·Package가 만들어진다 |
| `_event_values()`의 예외 메시지만 고친다 | Real E2E가 복구되지 않는다. `case`가 여전히 IncidentClip·OCR·TimeResolution을 먼저 돌린 뒤 실패한다 |
| `assemble_evidence()`가 `None`을 돌려주게 한다 | 반환 타입이 흐려지고 모든 호출부가 null 검사를 다시 하게 된다. 판단 지점이 분류 함수 한 곳으로 모이지 않는다 |
| `case`에 `NOT_OBSERVED` 전용 stage/notice를 새로 만든다 | `CaseView` 계약 변경이 필요하고, 이미 있는 「evidence 없는 `EVIDENCE_REVIEW`」 표현과 중복된다 |
| 첫 `NOT_OBSERVED`에서 다음 후보를 자동 Fine한다 | §7 — Product 정본이 아직 갱신 중이다 |

## 6. 결과

- 유효한 negative Fine 결과가 더 이상 `ContractInputError`로 종료되지 않는다.
- `NOT_OBSERVED`에서 IncidentClip·OCR·TimeResolution이 돌지 않아 불필요한 비용이 사라진다.
- `evidence` public boundary에 `classify_visual_evidence()`·`VisualEvidenceDisposition`·`VisualEventNotAssembled`가 추가된다. 기존 함수의 시그니처와 `OBSERVED`/`UNCERTAIN` 동작은 바뀌지 않는다.
- `case`의 `EvidenceBundle`은 조립 산출물이 `None`일 수 있고, 어느 결말에서든 `visual_evidence`·`fine_run`·`disposition`을 들고 있다.
- `RealAdapter.get_evidence_records()`는 조립이 없으면 빈 리스트를 돌려준다.

## 7. 이 ADR이 정하지 않는 것

아래는 잘못된 방향이어서 빼는 것이 아니다. 2026-09-22 최신 와이어프레임이 보여준 자동 진행 Product 방향은 `core-user-flow.md`가 정본화된 뒤 Product/Case/Evidence/Web이 **함께** 결정할 후속 변경이며, 이번 결정은 그때까지 Real E2E blocker를 먼저 제거하는 시간 순서의 결정이다.

- `case`가 ranking 순서로 후보를 자동 순회하는 정책
- 첫 `NOT_OBSERVED`에서 다음 candidate를 자동 Fine하는 정책
- 가장 높은 `OBSERVED` candidate의 자동 채택
- `CANDIDATE_REVIEW`의 UI blocking 없는 자동 통과
- 사용자가 다른 후보를 고를 때 기존 Evidence를 supersede하는 동작
- `AUTO_INFERRED` 같은 새 상태 또는 provenance
- 사용자 사건 확인 없이 WARN Package를 발행하는 새 정책

현재 Accepted Contract가 영구적인 Product 정답이라는 뜻이 아니다. 이 ADR은 새 정본이 채택되기 전까지의 소비 규칙만 고정한다.

## 8. 검증

- `tests/evidence/test_visual_evidence_disposition.py` — 세 상태 × 다섯 입력의 결말 고정, `NOT_OBSERVED + non-null type` 차단, `USER_UNSURE`를 붙여도 generic 경로로 합쳐지지 않음
- `tests/case/test_not_observed_consumption.py` — synthetic `NOT_OBSERVED` 주입, downstream 미호출을 call count로 증명, Record/Report/Package 미생성, VisualEvidence·Fine 실행·Usage 보존, `CaseView` 표현
- `tests/case/test_real_e2e.py` · `tests/evidence/` 기존 스위트 — `OBSERVED` happy path와 `UNCERTAIN + USER_UNSURE` 회귀
