# 이슈 #137 `NOT_OBSERVED` 접합부 검수

> 검수일: 2026-09-22  
> 원격 기준: `origin/develop` @ `1f4a829` (PR #136 병합 후)  
> 재현 경로: `origin/fix/case-search-stream-context-wiring` @ `d43dbae`, Draft PR #131  
> 이슈: [#137 evidence가 NOT_OBSERVED(visual_event_type=null) VisualEvidence를 처리 못 한다](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/137)  
> 추가 검수 입력: 사용자 제공 최신 와이어프레임 스크린샷 5장(2026-09-22, repo 미반입)  
> 판정: **REQUEST_CHANGES — 현재 Accepted Contract에서 유효한 negative Fine 결과가 Case → Evidence 경계에서 예외로 종료됨**

## 결론

이 문제는 Search가 잘못된 값을 만든 것이 아니다. `verification=NOT_OBSERVED`와
`visual_event_type=null`은 `visual-evidence/v1.0`이 명시적으로 허용하는 정상 Fine 결과다.
Fine이 실행됐고 영상을 볼 수 있었지만, 선택한 후보를 지지하는 필수 사실이 없거나 반증된
hard-negative를 뜻한다.

현재 Real E2E 경로는 Fine 결과를 분류하지 않고 항상 IncidentClip·Readout·TimeResolution·
Evidence 조립으로 넘긴다. Evidence의 `_event_values()`는 값 공간에는 `NOT_OBSERVED`를
넣어 두고도 실제 null 분기에서는 `UNCERTAIN`만 허용하므로, 그 잘못된 진입이
`ContractInputError: only an UNCERTAIN VisualEvidence may produce a null visual event`로
드러났다. 유효한 Fine 결과를 계약 위반처럼 처리하는 현재 동작은 수정 대상이다.

수정 방향은 `NOT_OBSERVED`를 `UNCERTAIN` fallback으로 합치는 것이 아니다.
`UNCERTAIN + USER_UNSURE`는 구체 유형을 확정하지 못했지만 사용자가 진행을 택한 기존 generic
신고 경로이고, `NOT_OBSERVED`는 해당 후보를 Fine이 기각한 결과다. 둘을 합치면 관찰되지
않은 위반으로 generic 신고문과 Package를 만들 수 있어 의미가 뒤집힌다.

이번 #137은 **현재 Accepted Contract와 현재 `core-user-flow.md`에서 이미 유효한
`NOT_OBSERVED` 소비 누락을 고쳐 Real E2E를 복구하는 것**까지를 주 범위로 한다. Case는 Fine
결과를 Evidence 이전에 분류해 `NOT_OBSERVED`를 정상적인 non-accepted 결과로 종료하고,
Evidence public boundary도 직접 잘못 호출되더라도 가짜 Record를 만들지 않는 안정적인
non-assembly 결과로 방어해야 한다.

> 이번 수정은 새 와이어프레임을 반려하는 결정이 아니다. 현재 정본 계약을 기준으로 Real
> E2E의 기존 계약 버그를 먼저 제거하고, 자동 후보 채택·순회 및 Package 확인 정책은 수정
> 중인 `core-user-flow.md`가 정본화된 후 별도 Product/Contract 변경으로 반영한다.

최신 와이어프레임은 기존 `core-user-flow.md`보다 자동화된 강한 Product 방향을 보여 준다.
그러나 아직 관련 정본 문서와 계약이 갱신되지 않았으므로, 자동 후보 순회·자동 채택·사용자
확인 없는 Package 정책을 #137의 구현 완료조건에 함께 넣지 않는다. Web 쪽에는 최신
와이어프레임 기준으로 `core-user-flow.md` 갱신 요청을 이미 전달한 상태로 본다. 정본 갱신
뒤 Product/Case/Evidence/Web이 함께 맞추는 후속 변경으로 분리한다.

## 이번 판정에서 유지하는 불변 결론

1. `verification=NOT_OBSERVED + visual_event_type=null`은 Search의 정상 Fine 결과다.
2. `NOT_OBSERVED`와 `UNCERTAIN`은 의미가 다르며 같은 fallback으로 합치지 않는다.
3. `NOT_OBSERVED`로 EvidenceRecord·RequirementReport·ReportPackage를 만들면 안 된다.
4. 원본 VisualEvidence, Fine 실행 결과, UsageRecord/provenance는 평가·진단용으로 보존한다.
5. Evidence public boundary도 방어적으로 `NOT_OBSERVED`를 정상적인 비조립 결과로 처리한다.
6. 현재 `ContractInputError: only an UNCERTAIN ...`는 유효한 Fine 결과를 계약 위반처럼
   다루므로 수정 대상이다.
7. Search enum과 `visual_event_type` 값 공간은 변경하지 않는다.
8. 기존 `UNCERTAIN + USER_UNSURE` generic WARN 경로는 그대로 유지한다.

## 이번 #137의 범위

### 포함

- Case가 Fine 결과를 받은 직후 `verification`을 분류한다.
- `OBSERVED`는 현재 accepted downstream으로 계속 보낸다.
- `UNCERTAIN`은 현재 계약의 사용자 확인 및 `USER_UNSURE` 경로를 유지한다.
- `NOT_OBSERVED`는 Evidence 이전에 정상적인 non-accepted 결과로 종료한다.
- `NOT_OBSERVED`에서 IncidentClip·Readout·TimeResolution·Evidence 조립을 시작하지 않는다.
- Evidence public boundary가 `NOT_OBSERVED`를 가짜 Record로 승격하지 않도록 방어한다.
- VisualEvidence, Fine 실행 결과, UsageRecord/provenance를 보존한다.
- 세 상태의 소비자 회귀 테스트와 negative/positive Real E2E 기준을 분리한다.
- 현재 Case가 이미 가진 stage/notice로 정상 종료를 표현할 수 있다면 그것을 재사용한다.
  정말 필요한 최소 변경 외에는 새 CaseView 필드나 enum을 추가하지 않는다.

### 명시적 비범위

다음은 잘못된 아이디어여서 제외하는 것이 아니다. 최신 와이어프레임을 반영한
`core-user-flow.md`가 정본화된 뒤 Product/Case/Evidence/Web이 함께 결정하고 반영할 후속
Product-flow 변경이다.

- Case가 ranking 순서대로 후보를 자동 순회하는 정책
- 첫 `NOT_OBSERVED`에서 다음 candidate를 자동 Fine하는 정책
- 가장 높은 `OBSERVED` candidate의 자동 채택
- `CANDIDATE_REVIEW`의 UI blocking 없는 자동 통과
- speculative readout 뒤 `selection_rev` 변경 시 stale 처리하는 정책
- 사용자가 다른 후보를 고를 때 기존 Evidence를 supersede하는 동작
- `AUTO_INFERRED` 같은 새 상태 또는 provenance 추가
- 사용자 사건 확인 없이 WARN Package를 발행하는 새 정책
- 최신 와이어프레임을 근거로 CaseView/Package Contract를 지금 바로 버전업하는 일
- 위 자동 흐름을 #137의 BLOCK 사유나 완료조건으로 두는 일

## 확인 근거

### 1. Producer 계약은 `NOT_OBSERVED`를 정상 결과로 정의한다

- `docs/architecture/contracts/contract-visual-evidence.md` §4-1은
  `NOT_OBSERVED`를 “Fine은 정상 실행됐으나 해당 사건을 지지하는 근거가 없음”으로
  정의하고 `visual_event_type`은 반드시 null이라고 정한다.
- 같은 문서 §12는 Evidence Consumer가 `NOT_OBSERVED`와 `UNCERTAIN`을 별도 입력 상태로
  처리해야 한다고 명시한다.
- `docs/architecture/contracts/adr/adr-visual-evidence.md`도 Evidence가
  `NOT_OBSERVED`를 정상 실행된 유효 관찰 결과로 보존해야 한다고 기록한다.
- Search 모델의 `VisualEvidence.check_verification()`도
  `NOT_OBSERVED | UNCERTAIN → visual_event_type=null`을 정상으로 검증한다.

따라서 이 입력을 upstream 계약 위반으로 분류하는 현재 Evidence 예외는 잘못된 경계다.

### 2. `NOT_OBSERVED`와 `UNCERTAIN`은 서로 다른 결과다

`contract-evidence-record-needs.md`는 EvidenceRecord가 관찰을 바탕으로 채택한 confirmed
value만 snapshot한다고 정한다. `event.visual_event_type.value=null` 예외는
`VisualEvidence.verification=UNCERTAIN`이고 사용자가 `USER_UNSURE`로 응답한 경우에만
명확화돼 있다.

`NOT_OBSERVED`를 이 null 예외에 넣으면 다음 문제가 생긴다.

- 영상에서 사건이 성립하지 않았다는 결과와 판단 불충분을 같은 값으로 만든다.
- 실제 사용자 응답이 없는데 `USER_UNSURE`를 자동 생성해야 하는 압력이 생긴다.
- `evidence.visual_event.present`가 WARN generic 경로로 평가될 수 있다.
- 이후 generic 신고문과 ReportPackage가 만들어져 hard-negative의 의미와 반대로 동작할
  수 있다.

따라서 `NOT_OBSERVED`는 EvidenceRecord 생성 이전의 정상 비채택 결과로 남겨야 한다.

### 3. 현재 누락 지점은 Case와 Evidence 두 곳이다

#### Evidence

`src/daesingo/evidence/assembly.py::_event_values()`는 먼저 세 enum을 모두 허용한 뒤,
`visual_event_type is None` 분기에서 다시 `verification == "UNCERTAIN"`만 요구한다.
조건이 서로 어긋나 `NOT_OBSERVED`는 선언상 허용되지만 실제로는 도달 불가능하다.

2026-09-22 로컬 synthetic 재현 결과:

```text
verification=NOT_OBSERVED, visual_event_type=null, situation_response=None
→ ContractInputError: only an UNCERTAIN VisualEvidence may produce a null visual event
```

#### Case Real E2E

Draft PR #131의 `build_evidence_for_real_video_candidate()`는 Fine 결과를 받은 뒤
verification을 분류하지 않고 IncidentClip, PaddleOCR, TimeResolution을 거쳐
`assemble_evidence()`를 반드시 호출한다. `RealVideoAdapter._build_evidence_bundle()`도
EvidenceBundle이 항상 존재한다고 가정한다.

Evidence의 예외 메시지만 바꿔서는 E2E가 복구되지 않는다. Case가 `NOT_OBSERVED`를 Evidence
이전에서 소비해 정상 종료해야 하고, Evidence는 잘못된 직접 호출에도 Record를 만들지 않는
방어 경계여야 한다.

### 4. 소비자 회귀 테스트가 비어 있었다

- Evidence 통합 테스트는 `OBSERVED`와 `UNCERTAIN + USER_UNSURE`를 검증한다.
- 공용 Mock 검수 문서는 `NOT_OBSERVED`가 미커버라고 명시한다.
- Search에는 `NOT_OBSERVED` fixture와 계약 테스트가 있지만, 그 결과가 Evidence/Case로
  넘어가는 소비자 회귀 테스트는 없다.

`NOT_OBSERVED` 소비 버그는 기존 3-state 계약의 coverage 누락이다. 최신 와이어프레임이
제시한 자동 진행 정책과 함께 고쳐야만 해결되는 문제는 아니다.

## Real E2E 성공 기준

이번 검수는 “하나의 영상이 반드시 `READY + Package`까지 가야 성공”이라고 정의하지 않는다.
실제 Fine 결과의 의미에 따라 두 정상 결과를 분리한다.

### A. Negative Real E2E

```text
Coarse/Fine 실제 실행
→ Fine = NOT_OBSERVED
→ 정상 분기
→ EvidenceRecord 생성 안 함
→ RequirementReport 생성 안 함
→ ReportPackage 생성 안 함
→ ContractInputError 없음
→ VisualEvidence / Fine execution / Usage 보존
```

이 결과도 정상적인 E2E 성공이다. Fine이 정상적으로 “이 후보는 아니다”라고 판단했는데
Evidence나 READY까지 억지로 진행시키는 것이 오히려 계약 위반이다. 현재 Case가 이 상태를
표현할 최소 분기가 필요하다면 구현하되, 새 자동 후보 순회 제품 정책까지 확장하지 않는다.

### B. Positive / Happy Real E2E

별도의 대표 영상 또는 `OBSERVED`가 나오는 실제 입력으로 다음을 검증한다.

```text
Fine = OBSERVED
→ 현재 accepted flow대로 IncidentClip
→ Readout
→ TimeResolution
→ Evidence
→ 현재 계약이 요구하는 사용자 확인
→ Requirement / Package
```

따라서 `NOT_OBSERVED` 대표 입력은 negative path, `OBSERVED` 대표 입력은 READY/Package happy
path를 검증한다. 실제 Gemini 호출은 synthetic 회귀가 끝난 뒤 필요한 대표 실행만 최소
횟수로 수행한다.

## 권고 구현안

### A. Case Owner — Fine 결과를 최소 분기로 소비한다

Case의 이번 책임은 아래로 제한한다.

```text
Fine 결과 수신
↓
verification 확인

OBSERVED
→ 기존 downstream 계속

UNCERTAIN
→ 기존 계약의 사용자 확인 / USER_UNSURE 경로 유지

NOT_OBSERVED
→ downstream Evidence 조립으로 보내지 않음
→ 정상적인 non-accepted 결과로 종료
→ VisualEvidence / Fine execution / Usage 보존
```

필수 조건:

- `NOT_OBSERVED`를 IncidentClip·Readout·TimeResolution·Evidence로 보내지 않는다.
- 예외나 실패가 아니라 정상적인 negative 결과로 반환하거나 기록한다.
- 현재 계약의 기존 stage/notice로 표현할 수 있으면 재사용한다.
- 새 CaseView 필드가 꼭 필요하지 않다면 추가하지 않는다.
- 새 enum이나 상태가 필요해 보이면 #137에서 임의로 확정하지 않고 후속 Product-flow 변경
  후보로 기록한다.
- 다음 candidate 선택·검증 정책은 구현하지 않는다. 정본화된 새 flow의 후속 작업이다.

### B. Evidence Owner — 안정적인 non-assembly 방어 경계를 제공한다

정상 제품 흐름에서는 Case가 먼저 분류한다. 그래도 public boundary는 직접 호출과 미래
consumer를 위해 세 상태를 명시적으로 방어해야 한다. tagged result 또는 작은 공개
classification/preflight 함수 등 현재 코드와 가장 작은 변경으로 맞춘다.

```text
OBSERVED      → assembly 가능
UNCERTAIN     → 기존 USER_UNSURE 규칙 유지
NOT_OBSERVED  → EvidenceRecord 조립 안 함, stable non-assembly result
```

필수 조건:

- Evidence가 candidate 선택이나 순회를 담당하지 않는다.
- `NOT_OBSERVED`는 오류나 Package 상태가 아니라 정상적인 비조립 결과다.
- `assemble_evidence()`를 직접 잘못 호출해도 가짜 EvidenceRecord가 생성되지 않는다.
- 예상 정상 흐름은 `ContractInputError` 없이 종료한다.
- 문자열 비교를 여러 호출부에 흩뿌리기보다 public boundary 한 곳에서 의미를 닫는다.
- 기존 `UNCERTAIN + USER_UNSURE` 규칙과 provenance는 변경하지 않는다.

구체 타입과 함수명은 구현자가 현재 코드 구조에 맞춰 선택할 수 있다. 단, 예외를 잡아
성공처럼 처리하거나 null EvidenceRecord를 만드는 방식은 허용하지 않는다.

### C. 계약·결정 문서 — 필요한 최소 명확화만 한다

코드 변경이 기존 계약 문구만으로 충분하다면 계약 버전을 올리지 않는다. 문구가 모호해
소비자 규칙을 보강해야 한다면 다음 최소 범위만 수정한다.

- `contract-visual-evidence.md`: Evidence Consumer가 `NOT_OBSERVED`를 정상 비채택 결과로
  소비하고 EvidenceRecord로 승격하지 않는다는 규칙
- `contract-evidence-record-needs.md`: `NOT_OBSERVED`는 null EvidenceRecord 예외가 아니며
  Record 생성 전에 종료한다는 명확화

자동 후보 순회·자동 채택·새 Package 정책을 이 계약 수정에 끼워 넣지 않는다.

## 필수 회귀 테스트

### Evidence 단위 테스트

| 입력 | 기대 |
| --- | --- |
| `OBSERVED + non-null type` | 기존 EvidenceRecord assembly 성공 |
| `UNCERTAIN + null`, 응답 전 | 기존 사용자 응답 대기, Record 미생성 |
| `UNCERTAIN + null + USER_UNSURE` | 기존 generic EvidenceRecord/WARN 경로 유지 |
| `NOT_OBSERVED + null` | stable non-assembly, Record 미생성, 예외 없음 |
| `NOT_OBSERVED + non-null type` | producer 계약 위반으로 차단 |

### Case synthetic 접합 테스트

- synthetic `NOT_OBSERVED` VisualEvidence를 유료 호출 없이 주입한다.
- `ContractInputError` 없이 정상 non-accepted 결과로 종료하는지 확인한다.
- IncidentClip·Readout·TimeResolution·Evidence assembly가 호출되지 않는지 spy/mock으로
  확인한다.
- EvidenceRecord·RequirementReport·ReportPackage가 생성되지 않는지 확인한다.
- 원본 VisualEvidence, Fine execution, UsageRecord/provenance가 보존되는지 확인한다.
- 다음 candidate 자동 순회가 테스트의 기대 동작에 포함되지 않게 한다.

### 기존 경로 회귀

- `OBSERVED` happy path가 기존 accepted flow와 결과를 유지한다.
- `UNCERTAIN + USER_UNSURE`가 기존 generic WARN 경로를 유지한다.
- Search의 `NOT_OBSERVED`/FrameRef 계약 테스트가 계속 통과한다.
- 기존 contract fixture와 module boundary 검사가 통과한다.

권장 검사:

```text
python -m unittest discover -s tests/evidence -p "test_*.py"
python -m pytest tests/search/test_contract_edges.py
python -m pytest tests/case -k "not_observed or real_video"
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
python -m ruff check src/daesingo/evidence tests/evidence src/daesingo/case tests/case
git diff --check
```

실제 Gemini 재호출은 synthetic 회귀가 모두 통과한 뒤 대표 negative와 positive 확인에 필요한
최소 횟수만 수행한다. 캡처된 실제 응답으로 같은 경계를 재현할 수 있으면 먼저 재생 테스트를
사용한다.

## 후속 Product Flow 정합화

### 와이어프레임에서 직접 확인한 Product 방향

2026-09-22 제공된 다섯 화면에서 다음 흐름을 직접 확인했다.

- 업로드와 사용자 사건 설명을 시작 입력으로 함께 받는다.
- 진행 화면은 `INTAKE → SEARCHING → CANDIDATE_REVIEW → EVIDENCE_REVIEW`를 표시하면서
  “나머지는 자동으로 진행됩니다”라고 안내한다.
- “가장 유력한 장면으로 진행합니다”를 기본 경로로 두고, “다른 장면이었나요? — 찾은 3개
  보기”를 보조 경로로 둔다.
- 시각·번호판을 자동으로 읽고, 번호판처럼 사람 판단이 필요한 항목에서만 멈춘다.
- 확인 후 `stage=READY · package 있음`인 신고자료 화면까지 간다.

이는 폐기할 자료가 아니라 최신 Product 방향을 보여 주는 강한 결정 입력이다. 동시에 현재
`core-user-flow.md`와 관련 Accepted Contract의 후보 선택·사용자 확인 규칙과 충돌한다.
Web 쪽에 요청한 `core-user-flow.md` 갱신이 정본화된 뒤 Product/Case/Evidence/Web이 함께
아래 사항을 결정하고 계약·구현·테스트를 맞춰야 한다.

1. 가장 높은 검증 후보를 자동 채택할지
2. `NOT_OBSERVED`이면 다음 후보를 자동 순회할지
3. `CANDIDATE_REVIEW`를 UI blocking 없이 자동 통과할지
4. 최초 사용자 설명을 특정 사건에 대한 사후 확인과 어떻게 구분할지
5. 사용자 사건 확인 없이 Package까지 허용할지
6. 허용한다면 `AUTO_INFERRED` 같은 provenance/state가 필요한지

사용자가 업로드 시 적은 “18시쯤, 흰색 SUV, 백색 실선 구간에서 차로 변경” 같은 문장은
현재 기준으로 검색 의도와 `AnalysisScope` 입력이다. 시스템이 나중에 찾은 특정 candidate를
본 뒤의 `situation_response=CONFIRMED`가 아니다. Product 정책이 바뀌더라도 최초 설명을
몰래 `CONFIRMED`로 변환해서는 안 된다.

이 후속 범위 분리는 “나중에 보자”는 보류가 아니다. #137의 원인은 현재 유효한 3-state
계약을 소비자가 빠뜨린 버그이고, 자동 진행은 정본 flow·표시 상태·선택 provenance·Package
확인 의미가 함께 바뀌는 Product/Contract 변경이다. 전자를 먼저 고쳐 negative Real E2E를
복구한 뒤, 갱신된 정본에 따라 후자를 별도 변경으로 추적하는 것이 책임과 검증 기준을
섞지 않는 순서다.

## 검수 판정표

| 축 | 판정 | 이유 |
| --- | --- | --- |
| Correctness | **BLOCK** | 계약상 유효한 `NOT_OBSERVED`가 예외로 종료되고 Real E2E를 막는다 |
| Readability | **WARN** | enum 허용 조건과 null 분기 조건이 서로 다른 허용 집합을 갖는다 |
| Architecture | **BLOCK** | Case가 `NOT_OBSERVED`를 분류하지 않고 downstream assembly로 밀어 넣으며 Evidence가 정상 negative 결과를 소비하지 못한다 |
| Security | **PASS** | 이번 이슈에서 비밀 노출·입력 주입·권한 문제는 확인되지 않았다 |
| Performance | **WARN** | `NOT_OBSERVED`인데도 IncidentClip/OCR/TimeResolution 등 불필요한 후속 작업으로 진입한다 |
| Test coverage | **BLOCK** | Producer 테스트는 있으나 Evidence/Case 소비자 회귀 테스트가 없다 |
| Product-flow alignment | **FOLLOW-UP** | 자동 순회·자동 채택·확인 없는 Package는 최신 와이어프레임을 반영한 정본 갱신 뒤 별도 정합화한다 |

자동 candidate traversal 미구현 자체는 이번 #137의 BLOCK 사유가 아니다.

## 완료 조건

- [ ] Case가 `NOT_OBSERVED`를 Evidence 이전에 정상 분기로 소비한다.
- [ ] `NOT_OBSERVED`에서 IncidentClip·Readout·TimeResolution·Evidence 조립을 불필요하게
      진행하지 않는다.
- [ ] `NOT_OBSERVED`가 `UNCERTAIN` generic 경로로 합쳐지지 않는다.
- [ ] EvidenceRecord·RequirementReport·ReportPackage가 생성되지 않는다.
- [ ] VisualEvidence·Fine execution·UsageRecord/provenance는 보존된다.
- [ ] Evidence public boundary도 `NOT_OBSERVED`를 가짜 Record로 승격시키지 않는다.
- [ ] synthetic negative E2E 테스트가 예외 없이 통과한다.
- [ ] 기존 `OBSERVED` happy path가 회귀하지 않는다.
- [ ] 기존 `UNCERTAIN + USER_UNSURE` path가 회귀하지 않는다.
- [ ] 실제 대표 `NOT_OBSERVED` 입력은 negative E2E 정상 종료를 확인한다.
- [ ] 실제 대표 `OBSERVED` 입력은 현재 accepted flow 기준 READY/Package까지 별도 확인한다.
- [ ] 최신 와이어프레임 기반 자동 진행 정책은 별도 후속 작업으로 명시한다.

자동 후보 순회·자동 최고 후보 채택·`AUTO_INFERRED`는 이 체크리스트의 완료조건이 아니다.

## 이번 검수가 증명하지 않는 것

- 실제 영상의 `NOT_OBSERVED` 판단이 정답이라는 정확도 평가는 하지 않았다.
- 사용자 제공 와이어프레임은 실제로 열어 확인했지만 repo에 보존된 canonical artifact는
  아니므로 Product/Contract 채택을 증명하지 않는다.
- 현재 Accepted Contract가 영구적인 최종 Product 답이라는 뜻이 아니다. 이 문서는 새
  정본이 채택되기 전 #137의 검증 기준만 고정한다.
- 자동 후보 순회·자동 채택·사용자 확인 없는 Package·`AUTO_INFERRED`의 채택 여부를
  확정하지 않았다.
- PR #131의 나머지 Real E2E 구현 전체를 승인한 것이 아니다.
- 원격 이슈 #137의 이후 상태나 별도 수정 PR의 병합을 이 문서가 증명하지 않는다.
