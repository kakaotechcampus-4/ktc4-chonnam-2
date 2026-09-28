# 이슈 #137 `NOT_OBSERVED` 소비 누락 수정 발주 프롬프트

아래 작업을 현재 저장소에서 구현하고 검증해 주세요. 이 지시는 이슈 #137의 기존 계약
버그를 고쳐 Real E2E를 복구하기 위한 것입니다. 최신 와이어프레임의 자동 진행 방향을
부정하지 않지만, 아직 `core-user-flow.md`와 관련 계약이 정본화되지 않았으므로 그 Product
변경을 이번 구현에 함께 넣지 않습니다.

기준 검수 문서:

- `docs/modules/evidence/reviews/17_issue-137-not-observed-integration-review_2026-09-22.md`

## 1. 목표

현재 Search Fine은 정상적으로 다음 결과를 만들 수 있습니다.

```text
verification=NOT_OBSERVED
visual_event_type=null
```

그러나 Case가 이 결과를 분류하지 않고 IncidentClip·Readout·TimeResolution·Evidence로
보내고, Evidence가 null event를 `UNCERTAIN`에만 허용해 아래 예외로 Real E2E가 종료됩니다.

```text
ContractInputError: only an UNCERTAIN VisualEvidence may produce a null visual event
```

이번 작업의 목표는 다음과 같습니다.

1. Case가 `NOT_OBSERVED`를 Evidence 이전에 정상적인 non-accepted 결과로 소비합니다.
2. Evidence public boundary도 `NOT_OBSERVED`를 가짜 EvidenceRecord로 만들지 않는 안정적인
   non-assembly 결과로 방어합니다.
3. 원본 VisualEvidence, Fine execution, UsageRecord/provenance를 보존합니다.
4. 기존 `OBSERVED` happy path와 `UNCERTAIN + USER_UNSURE` generic WARN path를 회귀시키지
   않습니다.
5. synthetic 회귀를 먼저 통과시킨 뒤 negative와 positive Real E2E를 분리해 확인합니다.

## 2. 작업 시작 전 확인

- 원격을 fetch하고 작업 기준 브랜치·커밋·관련 PR 상태를 기록하세요.
- 현재 worktree의 사용자 변경을 확인하고 이번 작업과 무관한 파일을 수정하거나 되돌리지
  마세요.
- 다음 정본과 검수 문서를 먼저 읽고 실제 코드 경로와 어긋난 부분이 있으면 결과에
  명시하세요.
  - `docs/product/core-user-flow.md`
  - `docs/architecture/contracts/contract-visual-evidence.md`
  - `docs/architecture/contracts/contract-evidence-record-needs.md`
  - `docs/architecture/contracts/adr/adr-visual-evidence.md`
  - `docs/modules/evidence/reviews/17_issue-137-not-observed-integration-review_2026-09-22.md`
- Search enum과 `visual_event_type` 값 공간은 변경하지 마세요.
- 실제 유료 API를 호출하기 전에 synthetic fixture와 캡처된 응답으로 재현·검증하세요.

## 3. 유지해야 할 의미

| Fine 결과 | 이번 소비 의미 |
| --- | --- |
| `OBSERVED + non-null visual_event_type` | 현재 accepted downstream으로 계속 진행 |
| `UNCERTAIN + null` | 현재 계약의 사용자 확인 경로 유지 |
| `UNCERTAIN + null + USER_UNSURE` | 기존 generic EvidenceRecord/WARN 경로 유지 |
| `NOT_OBSERVED + null` | 정상 non-accepted, EvidenceRecord 조립 안 함 |
| `NOT_OBSERVED + non-null visual_event_type` | producer 계약 위반으로 차단 |

`NOT_OBSERVED`와 `UNCERTAIN`을 같은 fallback으로 합치지 마세요. `NOT_OBSERVED`에서
EvidenceRecord·RequirementReport·ReportPackage를 만들면 안 됩니다.

## 4. 구현 범위

### A. Case: `NOT_OBSERVED` 정상 분기

Fine 결과를 받은 직후, IncidentClip·Readout·TimeResolution·Evidence 조립보다 먼저
`verification`을 분류하세요.

```text
Fine 결과 수신
↓
verification 확인

OBSERVED
→ 기존 downstream 계속

UNCERTAIN
→ 기존 사용자 확인 / USER_UNSURE 경로 유지

NOT_OBSERVED
→ downstream Evidence 조립으로 보내지 않음
→ 정상적인 non-accepted 결과로 종료
→ VisualEvidence / Fine execution / Usage 보존
```

요구사항:

- `NOT_OBSERVED`를 예외나 계약 실패로 보고하지 마세요.
- Case가 이미 가진 stage/result/notice로 표현할 수 있으면 재사용하세요.
- 꼭 필요하지 않으면 CaseView에 새 필드를 추가하지 마세요.
- 새 enum이나 상태가 필요해 보이면 임의로 확정하지 말고 후속 Product-flow TODO로
  보고하세요.
- `NOT_OBSERVED` 뒤 IncidentClip, OCR/readout, TimeResolution, Evidence assembly가 호출되지
  않아야 합니다.
- RequirementReport와 ReportPackage도 생성되지 않아야 합니다.

### B. Evidence: non-assembly 방어

Evidence는 candidate 선택 주체가 아닙니다. 다만 public boundary가 직접 호출되거나 다른
consumer가 잘못 연결돼도 `NOT_OBSERVED`를 가짜 Record로 승격시키지 않아야 합니다.

현재 코드 구조에 맞춰 아래 중 가장 작은 변경을 선택하세요.

- 작은 classification/preflight 함수
- 명시적인 tagged result
- 동등하게 안정적인 typed non-assembly result

필수 의미:

```text
OBSERVED
→ assembly 가능

UNCERTAIN
→ 기존 USER_UNSURE 규칙 유지

NOT_OBSERVED
→ EvidenceRecord 조립 안 함
→ 예외가 아닌 stable non-assembly result
```

요구사항:

- candidate 순회 또는 다음 candidate 선택 로직을 Evidence에 넣지 마세요.
- 문자열 비교를 여러 호출부에 흩뿌리지 말고 public boundary 한 곳에서 의미를 닫으세요.
- `assemble_evidence()`를 직접 잘못 호출해도 `NOT_OBSERVED`로 Record가 생성되지 않게
  방어하세요.
- 예상 정상 Case 경로는 `ContractInputError` 없이 종료해야 합니다.
- 기존 `UNCERTAIN + USER_UNSURE` provenance와 generic WARN 동작은 바꾸지 마세요.

### C. 보존·관찰 가능성

`NOT_OBSERVED`가 downstream 조립으로 가지 않더라도 다음 자료는 삭제하거나 성공값으로
덮어쓰지 마세요.

- 원본 VisualEvidence
- Fine 실행 결과와 실행 식별자
- UsageRecord 또는 동등한 비용/사용량 기록
- 기존 provenance와 입력 참조

보존 위치와 조회 방법을 테스트 또는 실행 결과에서 확인할 수 있게 하세요.

## 5. 명시적 비범위

아래 항목은 구현하지 마세요. 필요성이 발견되면 코드로 확장하지 말고 후속 Product-flow
TODO에 기록하세요.

- Case의 ranking 순 자동 후보 순회
- 첫 `NOT_OBSERVED` 뒤 다음 candidate 자동 Fine
- 가장 높은 `OBSERVED` candidate 자동 채택
- `CANDIDATE_REVIEW` 자동 통과
- speculative readout과 `selection_rev` stale 정책
- 사용자가 다른 후보를 골랐을 때 기존 Evidence supersede
- `AUTO_INFERRED` 같은 새 상태/provenance
- 사용자 사건 확인 없는 새 WARN Package 정책
- CaseView 대규모 변경
- 최신 와이어프레임 기준의 계약 즉시 버전업
- 최신 와이어프레임 전체 구현

이 비범위는 최신 와이어프레임을 폐기한다는 뜻이 아닙니다. Web 쪽에서 갱신 중인
`core-user-flow.md`가 정본화된 뒤 Product/Case/Evidence/Web이 함께 맞출 별도 변경입니다.

## 6. 테스트 요구사항

### A. Evidence 단위 테스트

최소 다음 입력을 검증하세요.

1. `OBSERVED + non-null type` → 기존 assembly 성공
2. `UNCERTAIN + null`, 사용자 응답 전 → 기존 대기/미생성
3. `UNCERTAIN + null + USER_UNSURE` → 기존 generic WARN 경로
4. `NOT_OBSERVED + null` → stable non-assembly, Record 미생성, 예외 없음
5. `NOT_OBSERVED + non-null type` → 계약 위반 차단

### B. Case synthetic negative E2E

유료 호출 없이 synthetic `NOT_OBSERVED` VisualEvidence를 실제 소비 경로에 주입하세요.

반드시 검증할 것:

- `ContractInputError` 없이 정상 종료
- IncidentClip 미호출
- Readout/OCR 미호출
- TimeResolution 미호출
- Evidence assembly 미호출
- EvidenceRecord 미생성
- RequirementReport 미생성
- ReportPackage 미생성
- VisualEvidence 보존
- Fine execution 보존
- UsageRecord/provenance 보존

downstream 미호출은 결과 추정만으로 끝내지 말고 spy/mock/call count 등으로 증명하세요.

### C. 기존 경로 회귀

- `OBSERVED` fixture로 현재 accepted happy path가 유지되는지 확인하세요.
- `UNCERTAIN + USER_UNSURE` fixture로 기존 generic WARN path가 유지되는지 확인하세요.
- Search의 `NOT_OBSERVED`와 FrameRef 계약 테스트를 유지하세요.
- 기존 contract fixture 검사와 module boundary 검사를 실행하세요.
- 변경 파일에 lint/type/format 검사가 있다면 저장소 표준 명령으로 실행하세요.

테스트 명령은 저장소 현황에 맞게 조정하되, 최소 다음 후보를 확인하세요.

```text
python -m unittest discover -s tests/evidence -p "test_*.py"
python -m pytest tests/search/test_contract_edges.py
python -m pytest tests/case -k "not_observed or real_video"
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
python -m ruff check src/daesingo/evidence tests/evidence src/daesingo/case tests/case
git diff --check
```

존재하지 않는 명령을 성공했다고 쓰지 말고, 실제 실행 명령·exit code·통과 수·skip 수를
결과에 기록하세요.

## 7. Real E2E 검증

synthetic 회귀가 모두 통과한 뒤에만 실제 유료 API를 최소 횟수로 호출하세요. 같은 실제
응답을 안전하게 재생할 수 있다면 캡처된 응답으로 먼저 검증하고, 최종 대표 실행만 실제
호출하세요.

### A. Negative Real E2E

대표 `NOT_OBSERVED` 입력의 성공 기준은 Package 생성이 아닙니다.

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

이 상태를 정상 E2E 성공으로 보고하세요. `READY + Package`로 억지 진행시키지 마세요.

### B. Positive / Happy Real E2E

별도의 대표 영상 또는 `OBSERVED`가 나오는 실제 입력으로 확인하세요.

```text
Fine = OBSERVED
→ 현재 accepted flow대로 IncidentClip
→ Readout
→ TimeResolution
→ Evidence
→ 현재 계약이 요구하는 사용자 확인
→ Requirement / Package
```

실제 환경·비용·자격 증명·대표 입력 부재로 실행할 수 없다면 성공했다고 주장하지 마세요.
준비한 명령, 필요한 입력, 막힌 정확한 단계, 재실행 조건을 남겨 `NOT_RUN` 또는
`AUTH_REQUIRED`처럼 사실대로 보고하세요.

## 8. 문서 변경

필요한 최소 계약/결정 문서만 수정하세요.

- 기존 계약 문구로 구현 의미가 충분하면 불필요한 버전 상승을 하지 마세요.
- 소비 규칙이 모호하면 `NOT_OBSERVED`가 EvidenceRecord 이전에 종료되는 정상 비조립
  결과임을 최소 문구로 명확히 하세요.
- 자동 순회·자동 채택·사용자 확인 없는 Package 정책을 이번 문서 변경에 넣지 마세요.
- 최신 와이어프레임에서 드러난 결정 항목은 후속 Product-flow TODO로 분리하세요.

## 9. 완료 조건

- [ ] Case가 `NOT_OBSERVED`를 Evidence 이전에 정상 분기로 소비한다.
- [ ] `NOT_OBSERVED`에서 IncidentClip·Readout·TimeResolution·Evidence 조립을 진행하지
      않는다.
- [ ] `NOT_OBSERVED`가 `UNCERTAIN` generic 경로로 합쳐지지 않는다.
- [ ] EvidenceRecord·RequirementReport·ReportPackage가 생성되지 않는다.
- [ ] VisualEvidence·Fine execution·UsageRecord/provenance가 보존된다.
- [ ] Evidence public boundary가 `NOT_OBSERVED`를 가짜 Record로 승격시키지 않는다.
- [ ] synthetic negative E2E 테스트가 예외 없이 통과한다.
- [ ] 기존 `OBSERVED` happy path가 회귀하지 않는다.
- [ ] 기존 `UNCERTAIN + USER_UNSURE` path가 회귀하지 않는다.
- [ ] 실제 대표 `NOT_OBSERVED` 입력의 정상 non-package 종료를 확인하거나, 실행 불가 사유와
      재실행 절차를 남긴다.
- [ ] 실제 대표 `OBSERVED` 입력의 현재 accepted happy path를 별도 확인하거나, 실행 불가
      사유와 재실행 절차를 남긴다.
- [ ] 자동 진행 정책은 별도 후속 Product-flow TODO로 남긴다.

자동 후보 순회·자동 최고 후보 채택·`AUTO_INFERRED`는 이번 완료조건이 아닙니다.

## 10. 최종 산출물

다음 항목을 빠짐없이 제출하세요.

1. 변경 코드
2. synthetic 및 회귀 테스트
3. 필요한 최소 계약/결정 문서 수정
4. 실제 실행한 명령과 결과
5. negative Real E2E 결과 또는 실행 불가 증빙·재실행 절차
6. positive Real E2E 결과 또는 실행 불가 증빙·재실행 절차
7. 남은 후속 Product-flow TODO
8. 아래 내용을 포함한 PR 설명 초안

```markdown
## 문제

- 유효한 `NOT_OBSERVED + visual_event_type=null` Fine 결과가 Case에서 분류되지 않고
  Evidence로 전달되어 `ContractInputError`로 종료됐다.

## 변경

- Case에서 `NOT_OBSERVED`를 Evidence 이전의 정상 non-accepted 결과로 소비한다.
- Evidence public boundary에서 `NOT_OBSERVED`의 Record 생성을 방어한다.
- VisualEvidence/Fine execution/Usage provenance를 보존한다.

## 테스트

- synthetic `NOT_OBSERVED` negative E2E
- `OBSERVED` happy path 회귀
- `UNCERTAIN + USER_UNSURE` 회귀
- downstream 미호출 및 usage/provenance 보존
- contract fixture / boundary / lint 검사

## Real E2E

- Negative: `NOT_OBSERVED` 정상 non-package 종료 결과
- Positive: 별도 `OBSERVED` 입력의 현재 accepted READY/Package 결과
- 미실행 항목이 있으면 사유와 재실행 절차

## 비범위 / 후속

- 자동 후보 순회·자동 최고 후보 채택
- `CANDIDATE_REVIEW` 자동 통과
- `AUTO_INFERRED`
- 사용자 확인 없는 새 Package 정책
- 최신 와이어프레임 전체 구현
```

## 11. 보고 원칙

- 코드·테스트로 확인한 사실, 실제 Real E2E 관찰, 추론, 후속 제안을 구분하세요.
- synthetic 테스트 통과를 실제 Gemini E2E 성공이라고 표현하지 마세요.
- negative path의 non-package 종료를 실패로 오인하지 마세요.
- positive path를 실행하지 못했다면 READY/Package까지 확인했다고 쓰지 마세요.
- 최신 와이어프레임을 무시하거나 폐기했다고 표현하지 마세요.
- 현재 Accepted Contract를 영구적인 Product 정답이라고 표현하지 마세요.
- 이번 결정은 **Real E2E blocker를 먼저 제거한 뒤 Product 정본 변경을 따라 후속 정합화**하는
  시간 순서의 결정입니다.
