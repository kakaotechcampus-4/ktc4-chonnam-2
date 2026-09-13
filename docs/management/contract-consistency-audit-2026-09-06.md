# 데이터 계약 정합성 검수 — 외부 감사 보고

검토일: 2026-09-06 · 기준 커밋: `81e5539fe1edd0c3bf4a0307db5f1addcd236758`

검토 대상은 2026-09-05 착수 결정부터 09-06 종결 선언까지의 **6단계 전체**다. `secret/`의 계획·호출 카드·회신 원본을 실제로 읽었다. 원본은 수정하지 않았으며, 이 보고서만 작성했다.

> **읽는 사람에게.** 이 보고서는 PM(김준영)이 수행한 데이터 계약 정합성 검수를 **외부 검토자에게 감사시킨 결과**다. 판정이 검수를 수행한 PM에게 비판적인 것은 의도된 것이며, 팀의 계약 품질을 낮추는 내용이 아니라 **접합부에서 무엇이 아직 합의되지 않았는지**를 드러낸 기록이다.
>
> 본문이 인용하는 `docs/management/secret/` 아래 파일(검수 계획 · 호출 카드 · 담당자 회신 원본)은 **PM 내부 문서이며 저장소에 커밋되지 않는다.** 경로는 감사의 근거를 밝히기 위해 남겨 뒀고, 링크가 열리지 않는 것이 정상이다.
>
> 이 보고서가 지적한 항목의 **현재 처리 상태**는 이 문서가 아니라 `architecture/contracts/adr/adr-consistency-followup-2026-09-06.md`가 갖는다. B04·B10은 복원됐고 B02·B11·B12의 무근거 확정은 철회됐으며, 접합부 BLOCK 8건은 `CALL-8`~`CALL-11`로 확인 중이다.

## 0. 요약

- **종합 판정: 재작업 필요.** 일부 이름·소유권 표기 보정과 담당자 회신 반영은 확인했지만, 「정답이 유일한 보정만 했다」·「파생이 결정론적이다」·「검수가 연 미해결 0건」은 현재 자료로 성립하지 않는다.
- **다음 일정 진행 가능 여부: 조건부.** 이미 정의된 정상 응답의 개별 fixture 작성은 가능하다. 그러나 **현재 계약만으로 `ownership.md` §7-④의 6개 통과 기준을 모두 만족했다고 판정하는 것은 불가**다. 특히 실제 코드로 돌릴 `evidence`에 필요한 자산 사실과 표시 상태의 입력 규칙이 없다.
- **지적 사항: BLOCK 12건 · WARN 7건 · NOTE 3건.** 중복 집계를 피하려고 관련 증상을 §2의 22개 항목으로 묶었다. 주장별 지적 수와 합산하지 않는다.
- 단계별 판정: **① 착수결정 — 조건부 / ② 검수설계 — 보완 필요 / ③ Pass 실행 — 전수·0건 주장 반증 / ④ 트랙1 — 일부 월권·완료 오기 / ⑤ v4 역반영 — 핵심 반영 확인, 과도한 종결 문장 포함 / ⑥ 트랙2 — 주요 회신 반영 확인, 추가 결정·연결 누락 존재.**

`python scripts/check_boundaries.py`는 종료 코드 0으로 PASS였다. 출력은 **boundary NOTE 7개 + coverage NOTE 5개 = 12개**였고, 경계 검사 대상 코드 파일 수는 **0개**였다. 이는 문서·코드의 의미적 정합성이나 실행 가능한 통합을 보증하지 않는다.

등급은 검수 계획 §3을 따른다. 추가로 요청된 감사 기준에 따라 **타 Owner의 결정을 트랙 1 조건 없이 확정한 C1 항목도 BLOCK**으로 다뤘다. 특히 B12는 직렬화 오류가 아니라 이 절차 기준에 따른 등급이다. PASS는 명시한 범위에서 반증을 찾지 못했다는 뜻이며, 과거 작업이 실제 그 순서로 실행됐다는 보증은 아니다.

## 1. 그룹별 판정

아래에서 파일명만 쓴 계약은 `docs/architecture/contracts/`, `adr-*.md`는 그 아래 `adr/`에 있다. `검수 계획`은 `docs/management/secret/데이터-계약-정합성-검수-계획.md`다. 회신 원본의 정확한 파일명은 §6에 적었다. 인용은 현재 파일의 절을 기준으로 한다.

| # | 주장 | 판정 | 근거 |
|---|---|---|---|
| P-1 | 착수 결정 D-1~D-4가 옳았다 | 지적 | `검수 계획:§0·§3`; `ownership.md:§7-③`; `622a869` 변경 목록. 번호 단일 소유·스크립트 도입은 타당하나 작성과 독립 검증의 분리가 없다 |
| P-2 | 검사 축 9개로 충분했다 | 반증 | `검수 계획:§5·§8-A`; `contract-job-execution.md:§4·§7`; `contract-recording-timeline-asset-span.md:§8.1`. 직렬화·필수/nullable·참조 연결·시간 좌표의 대조가 빠짐 |
| P-3 | §11 제외 범위가 정당하고 지켜졌다 | 지적 | `검수 계획:§11-3·§11-5`; `adr-consistency-2026-09.md:§2 C1-6·§6 R-7`. 미관 제외는 타당, 타 Owner 결정의 빠른 종결 금지는 위반 |
| P-4 | 정답지 우선순위를 일관되게 적용했다 | 반증 | `adr-consistency-2026-09.md:§6 R-6·R-7`; `product-spec.md:§7`; `contract-job-record-case-view.md:B§7`. 소유권 대신 비용·최신 확정 표기를 근거로 닫은 사례 존재 |
| Q-1 | Pass 1이 실제 전수였다 | 반증 | `검수 계획:§5 A·C·D·I`; `check_boundaries.py:check_headers/check_coverage/check_event_enum`. 계획한 검사와 구현이 다르고 현재 누락도 재현됨 |
| Q-2 | 축 E·G 위반 0건이다 | 지적 | `contract-observation.md:§11·§14`; `contract-evidence-record-needs.md:§2·§4`; `contract-job-record-case-view.md:B§7`. 책임 선언은 대체로 구분되나 case의 검토 필요 판정 입력이 닫히지 않음 |
| Q-3 | F-1~F-29 등급이 적절하다 | 반증 | `검수 계획:§8·§8-A·§8-B·§9`; `adr-consistency-2026-09.md:§6 R-6·R-7`. 표현 오류·실제 값 공간 변경·수락 증거가 혼용됨 |
| Q-4 | Pass 2·3이 산문 근거로 판정했다 | 지적 | `검수 계획:§6 각주·§8-B F-28`; `contract-recording-timeline-asset-span.md:§23`; `module-architecture.md:§5-3`. 경로 해석은 가능하지만 불변조건 전수 확인 주장은 성립하지 않음 |
| Q-5 | 놓친 충돌이 없다 | 반증 | 이 보고서 §3, 특히 `contract-job-execution.md:§7`, `contract-usage-record.md:§5`, `contract-analysis-scope.md:§5·§10` |
| C-1 | C1 13건 모두 트랙1 조건을 만족한다 | 반증 | `adr-consistency-2026-09.md:§2 C1-6·C1-13`; `검수 계획:§3`. 순서 조건과 수락 날짜의 임의 확정 |
| C-2 | 수락된 ADR 수정은 표기 보정 예외 안이다 | PASS(현재 내용) | `adr-visual-evidence.md:Status 아래 고지·§4`; `adr-analysis-scope.md:Status 아래 고지`; `adr/README.md:수락 ADR 보정 예외`. 과거 정확한 변경 횟수는 확인 불가 |
| C-3 | 세 계약의 Accepted 헤더를 채운 근거가 충분하다 | 지적 | `contract-analysis-scope.md:머리말·§11`; `adr-analysis-scope.md:결정일`; `adr-consistency-2026-09.md:§2 C1-13`. 종결 내용은 있지만 날짜까지 유일하게 정해지지는 않음 |
| C-4 | C1-5·C1-6은 역할 배정의 단순 역반영이다 | 반증 | `adr-job-record-case-view.md:A§5·§13`; `ownership.md:§5`; `adr-consistency-2026-09.md:§2 C1-6`. PM이 추가한 순서 조건은 회의 결정이 아니라고 직접 명시 |
| C-5 | C1 13건의 완료 기록과 파일이 일치한다 | 반증 | `adr-consistency-2026-09.md:§2 C1-4`; `contract-analysis-run-candidate-event.md:헤더`; `contract-visual-evidence.md:헤더`. Related ADR 표준 헤더 2건 누락 |
| C-6 | PM 신규 2건의 Final 처리와 신규 결정 목록이 충분하다 | 지적 | `ownership.md:§7-③`; `contract-job-execution.md:§6·§9·§10`; `contract-usage-record.md:§5·§8·§9`. 작성 권한은 있으나 「추가 필드뿐」이라는 설명은 사실과 다름 |
| C-7 | 미등재 타입에 주석만 달고 Owner 결정을 기다렸다 | PASS(최종 근거) | `adr-consistency-2026-09.md:§2 C1-12·§6 R-3·R-4`; `CALL-5 회신:⑷`; `CALL-6 회신:답변`; `module-architecture.md:§5-1` |
| V-1 | V-1~V-7이 계획대로 반영됐다 | 지적 | 이 보고서 §1-V. 핵심 이름·포인터는 있음. V-2는 실명 대신 역할명이고 일부 상태값은 기존 문장을 이용 |
| V-2 | 역반영 방향이 옳았다 | 지적 | `module-architecture.md:§5-1·§5-3·§12 RT8`; `adr-job-record-case-view.md:A§4·§7`. Job 분리는 타당, 「공백은 목을 막지 않는다」의 상위 문서 승격은 근거 부족 |
| V-3 | 규칙을 복제하지 않았다 | 반증 | `contract-job-record-case-view.md:B§7`; `contract-requirement-report-package.md:§5.2-1`; `contract-readout-run.md:§6`; `module-architecture.md:§5-3` |
| V-4 | 개정 이력이 실제 변경을 다 담는다 | 지적 | `module-architecture.md:개정 이력·§11-4`; `git show 81e5539 -- docs/architecture/module-architecture.md`. 09-06 USER_REVIEWED 항목 종결이 해당 날짜 이력에 없음 |
| R-1 | v1.1 기각의 12개 회귀 판정이 모두 옳다 | 지적 | `Final Data Contract v1.1 원본:머리말·A§7·B§5·§11·§12`; `adr-consistency-2026-09.md:§6 R-6·§7`. 통째 교체 방지는 타당하나 12건의 등급·삭제 의도·베이스 미기재 주장은 성립하지 않음 |
| R-2 | 회신 원문이 왜곡 없이 반영됐다 | 지적 | `CALL-1·5·6 회신`, `recording CALL-4 피드백`, `CorrectionRecord 원본`; `contract-readout-run.md:§5`; `contract-job-record-case-view.md:B§7`. 직접 답한 핵심은 반영, 후속 PM 결정과 연결 누락 존재 |
| R-3 | observability로 info_state 파생이 결정론적이다 | 반증 | `contract-job-record-case-view.md:B§7·§10`; `contract-evidence-record-needs.md:§3`; `contract-time-resolution.md:§2`. needs_review 원천과 사건시각 입력 변환이 없음 |
| R-4 | scope의 PM 확정·WARN 하향이 정당하다 | 반증 | `검수 계획:§3·§11-5`; `adr-consistency-2026-09.md:§6 R-7`; `ownership.md:§7-④`. 세 gate 표시 자체가 통과 기준이므로 단순 표기 문제가 아님 |
| R-5 | plate Accepted 조건이 충족됐다 | PASS(좁은 조건) / 지적(세트 완성) | `recording CALL-4 피드백:ref 제안`; `CALL-6 회신:기존 계약 승격 동의·결과 연결 조건`; `contract-plate-overlay-readout.md:§3·예시`. frame 예시는 교체됐으나 run 연결은 스키마에 없음 |
| R-6 | CorrectionRecord·ReadoutRun이 소비자 계약과 정합하다 | 지적 | `contract-correction-record.md:§5·§6·§8·§9`; `contract-time-resolution.md:§5·§13`; `contract-readout-run.md:§5·§6`; `failure-taxonomy.md:기록 규칙` |
| R-7 | 카드 설계와 원인 진단이 적절했다 | 지적 | `CALL-1:§2⑶·§5`; `CALL-4:§4`; `CALL-5:⑵`; `CALL-6:§4`; `CALL-7:발송하지 않음`; `adr-consistency-2026-09.md:§7` |
| Z-1 | 검수가 연 미해결 0건이다 | 반증 | `검수 계획:§0-B·§8·§9`; `adr-consistency-2026-09.md:§4(d)·§6 R-3·R-5·R-7`. 작성 약속·Draft·무회신을 완료와 합산 |
| Z-2 | 계약 14건은 Final 13·Draft 1이다 | PASS(수량) / 지적(완결성) | 14개 Status 직접 집계; `contract-correction-record.md:머리말·§9`; B01~B10. Final 표기는 소비 가능한 스키마의 증거가 아님 |
| Z-3 | 미결을 하나도 채우지 않았다 | 반증 | `adr-consistency-2026-09.md:§2 C1-13·§6 R-7`; `contract-job-execution.md:§10`; `contract-correction-record.md:§9`. 보존한 미결도 있으나 전체 무위반은 아님 |
| Z-4 | 다른 모듈의 문서를 고치지 않았다 | PASS(모듈 내부 파일) / 지적(권한 일반화) | `81e5539` 변경 목록. `docs/modules/**` 수정 없음. 공용 contracts에 있는 case 계약은 여전히 case Owner 소유 |
| Z-5 | recording 계약 공백이 Mock Pack을 막지 않는다 | 반증(무조건 주장) | `contract-requirement-report-package.md:§2·§4.5·§6·§8.1`; `contract-recording-timeline-asset-span.md:§8.1·§12`; `ownership.md:§7-④` |
| Z-6 | mock-pack-v1-refs가 충분히 안전하다 | 지적 | `mock-pack-v1-refs.md:머리말·§1·ref 규약`; `module-architecture.md:§5-3`; `contract-recording-timeline-asset-span.md:§6.2·§8.1`. 임시임은 명시했으나 계약 예시와 상위 보증이 혼재 |
| Z-7 | check_boundaries가 유효한 검사를 한다 | PASS(일부 검사) / 반증(포괄 보증) | 직접 실행·코드 0개 계수·메모리 반증 검사. 이 보고서 §3.6 |
| Z-8 | 목데이터 1차 통합이 지금 계약만으로 가능하다 | 반증(전체 통과) | `ownership.md:§7-④`의 6개 기준을 §4에서 개별 판정 |

### 1-P. 착수 결정·검수 설계의 재검증

**P-1.** D-1은 번호의 단일 원천을 v4 §5-1로 두므로 타당하다. 다만 실제 검사는 포인터가 *올바른 행*인지 확인하지 않는다. D-2의 선작성은 누락 계약을 Draft로 구체화하는 작업으로는 타당하다. 공백은 검수 결과로 남길 수 있으므로 「먼저 채워야 판정이 오염되지 않는다」가 필수 논리는 아니다. 같은 사람이 작성·수락·감사를 연속 수행하면서 스키마와 예시 불일치를 놓쳤다(B04·B05·B10). D-3은 문서 버전과 계약 버전을 구분하면 가능하다. ⑬ 추가·⑦ 확장은 기존 모듈 소유 데이터의 등재이므로 반드시 v5여야 한다는 근거는 없다. 대신 변경 절과 계약 성숙도를 정확히 기록해야 한다. D-4는 두 커밋의 stat과 workflow를 확인했고 운영진 소유 4개 파일 변경은 없었다.

**P-2.** 실제 계획은 A~I의 **9개 축**이다(프롬프트의 A~H는 목록과 다름). 축 이름의 수보다 검증 단위가 문제다. 본문·예시·불변조건·필수 칸을 같은 계약의 독립 표현으로 비교하는 절차, 계약 간 ref의 생성→소비 연결, immutable revision, null/실패/부분 성공 경로가 빠졌다. §8-A의 「enum 토큰 전부 대조」는 값 공간의 구문 확인이지 상태 전이·projection의 총함수성 검증이 아니다.

**P-3.** 내부 필드명 취향·정규화 미관·archive·연구 자료를 제외한 것은 타당하다. 그러나 serialized ref 모양과 반환값의 추적 가능성은 내부 설계 품질이 아니라 계약 접합부다. 이를 제외할 수 없다. ADR 본문 불수정 원칙은 공개 예외·고지가 생겼으므로 C1-1의 현재 조치는 별도로 평가한다. §11-5의 빠른 트랙1 종결 금지는 C1-6과 R-7에서 지켜지지 않았다.

**P-4.** Job Intent/Execution 분리와 위반유형 표기는 상위 경계·수락된 ADR로 방향을 설명할 수 있다. 반면 R-6은 `product-spec.md:§7`에 없는 「4종 유형 표시 불변 경계」를 인용하고, R-7은 case Owner의 필드 선택을 비용 비교로 대신했다. §2의 「새로운 Accepted이면 v4가 뒤처졌다」는 문장만으로 역반영하면 PM이 새로 붙인 Accepted가 다시 PM 수정의 근거가 되는 순환이 생긴다. 소유자의 결정 근거를 먼저 확인해야 한다.

### 1-Q. Pass 1~3 재검증

**Q-1.** 현재 14개 계약과 15개 ADR의 헤더를 열고, 계획 §5에 해당하는 번호·상태·Consumer·미결 문자열을 다시 수집했다. §3.6의 스크립트 재현 결과는 계획의 포인터 정확성·전체 enum·필수 헤더 검사를 구현하지 않음을 보여준다. 당시의 원시 grep 출력·커버리지 행렬·중간 파일은 없어 과거 실행 여부 자체는 확인 불가다. 현재 파일에 표준 헤더 누락과 옛 번호가 남아 있으므로 「전수 완료」 주장은 현재 결과로도 반증된다.

**Q-2.** 축 E의 web 직접 소비 금지는 `contract-evidence-record-needs.md:§2`, `contract-requirement-report-package.md:§2`, `contract-observation.md:§14`에서 확인했다. `eval`의 DTO 소비와 `case/evidence` 구현 import는 다른 행위이므로 Consumer에 eval이 적혔다고 곧바로 위반으로 보지 않았다. 축 G의 다섯 원천도 재검사했다: 번호판 확정=evidence(판독은 readout), 발생시각=evidence(후보는 recording/readout), 파일 경계=recording, 발주=case/실행=runtime, 사건 선택=case다. 선언상 이중 authoritative 원천은 발견하지 못했다. 다만 `needs_review`와 시각 표시 상태의 정책 입력이 미정이므로 이 선언이 실제 projection에서 지켜진다는 결론까지 낼 수 없다(B01).

**Q-3.** F-18의 위반유형 값 불일치, F-7의 출처·정보 상태 통로 부재는 BLOCK 판정이 타당하다. 반대로 F-19는 출처와 Need의 다른 값 공간이므로 이름 통일 대상이라고 단정할 이유가 없다. F-22는 실제 미수락과 헤더 누락을 한 BLOCK으로 묶었다. 이후 R-6에서는 Consumer 헤더 누락을 BLOCK으로 올리면서 closed enum·nullable의 후퇴는 WARN으로 내렸다. 그리고 R-7의 scope 선택은 통합 기준 ④에 영향을 주는데 WARN으로 내렸다. §1-Z의 F별 표에서 처리 결과까지 대조했다.

**Q-4.** recording의 「논리적으로 evidence」는 `case`가 전달하고 evidence가 값을 판정한다는 상위 문서와 양립한다. 데이터 소비와 직접 호출을 구분한 결론 자체는 가능하다. 그러나 계약에 직접 경유 경로를 명시하지 않은 부분을 v4에 추가한 사실이 과거 본문에 이미 경로가 모두 있었다는 증거는 아니다. 더욱이 `SpanResolution` 예시의 미설명 10초, `AnalysisScope`의 절대시각만 있는 입력, Candidate의 revision 누락은 본문·불변조건을 함께 읽어야 드러난다. Pass 2·3이 모든 접합부를 검증했다고 볼 수 없다.

**Q-5.** §3에 신규 발견을 기존 F/R 항목과 구분해 적었다. enum 이름의 중복 자체를 오류로 세지 않고 값 공간·필드 의미·변환 규칙을 대조했다. `Observation.ERROR`를 `RequirementReport.overall=ERROR`로 복제한 현행 규칙이나 `ABSTAIN`을 공통 상태로 승격한 규칙은 찾지 못했다. 발견한 실제 문제는 직렬화, 입력 부재, revision, 캐시 범위와 gate projection이다.

### 1-C. 트랙 1 보정 13건 개별 판정

조건 ①은 답의 유일성, ②는 의미·값 공간·경계 불변, ③은 PM 소유 영역이다. ③이 있다고 타 Owner의 소비 계약까지 자동으로 확정할 수 있다고 해석하지 않았다. 현재 반영 확인과 과거 변경 증명은 구분했다.

| C1-# | 내용 | 트랙1 조건 ①②③ 충족 | 파일 반영 확인 | 판정 |
|---|---|---|---|---|
| C1-1 | 위반유형 이름 보정·ADR 고지 | ①② 충족: v4와 제품의 백색 실선 범위로 한정. ③ 문서 일관성 | 두 계약의 현재 enum 및 두 ADR Status 아래 고지 확인 | PASS. 3곳/1곳의 실제 과거 수정 횟수는 preimage 없어 보류 |
| C1-2 | 번호 제거·v4 포인터 | ①②③ 충족 | 제목·헤더 포인터 반영. 본문에는 Contract④(AnalysisRun), plate ⑥-A/B 등이 남음 | 지적(W01): 완료 범위를 제목/헤더로 한정해야 함 |
| C1-3 | CaseView Core 표기 | ①②③ 충족 | 현재 제목, A/B절, Core 설명 있음 | PASS |
| C1-4 | 12건 헤더 통일 | 보정 자체 ①②③ 충족 | AnalysisRun·VisualEvidence에 `Related ADR:` 없음. 원격 결정 근거 링크는 존재 | 반증(W01): 「4개를 모든 계약에 맞춤」은 사실 아님 |
| C1-5 | Worker lifecycle 이름 역전 수정 | ADR로 ①② 충족 | ownership의 JobExecution 명칭·역할 반영 | PASS. 역할 이전이 아니라 이름 정정으로 읽을 근거 있음 |
| C1-6 | 정철원 구현 배정·순서 추가 | 배정은 ADR에 기록, 독립 회의록 미확인. **추가 순서는 ①② 불충족**, 타인 부하 | ownership §1-1·§3·§5·§6에 있음 | **BLOCK B11**. PM이 회의 확정이 아니라고 직접 명시한 순서를 트랙1로 닫음 |
| C1-7 | VisualEvidence Consumer 헤더 | 상위 경로를 기준으로 ①② 충족 | 현재 case Direct → evidence/readout projection | PASS(현재). 최초 미반영 후 정정 이력은 자체 서술만 존재 |
| C1-8 | JobExecution·UsageRecord 작성·수락 | **③ 작성 권한 있음**. 새 전이·원장 제약까지 ①②라고 할 수 없음 | 2계약·짝 ADR·Final 표기 존재 | 지적(W04, B04·B05·B10). 무조건 월권으로 보지 않지만 폐쇄 근거가 불충분 |
| C1-9 | PlateReadout case 경유 | 상위 경로+CALL-2(a)로 ①② 충족 | 헤더·책임 경계 반영 | PASS. 최종적으로는 Owner 확인을 받은 보정 |
| C1-10 | AnalysisScope eval fixture Producer | v4 §5-1로 ①② 충족 | 헤더는 수정, 본문 §2는 여전히 eval Consumer | 지적(W01) |
| C1-11 | JobRecord runtime Consumer 추가 | ADR의 Intent→Execution으로 ①② 충족 | A§2에 runtime·eval·간접 web 표기 | PASS |
| C1-12 | 미등재 2타입 확인 주석만 추가 | 미결 보존·문서 일관성 범위 충족 | 현재는 후속 Owner 회신을 근거로 ⑦·⑬ 등재 | PASS(최종 근거). 주석만 있던 중간 파일 상태는 확인 불가 |
| C1-13 | 세 계약 Status·Accepted 날짜 추가 | **Status의 종결 증거는 있음. 공통 날짜 09-04는 ① 불충족** | 세 헤더 모두 09-04. AnalysisScope ADR 결정일은 09-05 closure 보완 | **BLOCK B12(요청된 트랙1 절차 기준)**. Status 보정과 수락 일시 추정을 분리해야 함 |

**C-2 보충.** `adr-visual-evidence.md:§4·§12`는 대상 사건을 백색 실선 침범으로 읽을 수 있고, 현재 enum은 v4에 맞는다. `adr/README.md`의 표기 보정+고지 예외와 현재 고지는 맞는다. `adr-consistency-2026-09.md:§3`이 수락된 ADR을 건드린 비용을 적은 것도 확인했다. 다만 같은 커밋에 예외 규칙과 보정이 처음 등장하므로, 과거 소유자가 예외를 수락했다는 증거로 사용하지 않는다. 이 선례를 enum 집합·정책 수정까지 확장할 수 없다.

**C-3 보충.** AnalysisScope의 locked 스키마·Draft→Final 표, JobRecord/CaseView의 Consumer Review 종결표, recording의 Pair Review 최종표는 실제로 있다. 따라서 「세 계약에 종결 증거가 전혀 없다」는 반증은 실패했다. recording ADR에는 결정일 9/4도 있어 그 날짜의 추가 근거가 있다. 반면 C1-13이 세 건 모두의 날짜를 「나머지 6건과 같은 회차」로 채운 일반화는 성립하지 않는다. 특히 AnalysisScope의 9/5 closure와 9/4 Accepted가 서로 어떤 판본을 뜻하는지 원문 확인이 필요하다. plate의 명시적 후보 상태를 처음에는 남긴 차별 처리는 일관적이다.

**C-4·C-6 보충.** 독립 회의록은 현재 비archive 문서·첨부에서 찾지 못했다. ADR에 적힌 배정 자체를 거짓이라고 단정하지는 않는다. 그러나 추가 순서는 본문이 PM 판단이라고 인정하므로 별도 증거 없이도 판정 가능하다. 한편 `ownership.md:§7-③`은 핵심 3계약 외에는 생산자가 작성하고 소비자가 이의를 제기하는 절차를 허용한다. 그래서 소비자 정식 리뷰가 없다는 이유만으로 PM 소유 계약 둘의 작성·Final을 자동 월권으로 판정하지 않았다. 문제는 통보·수락 범위를 좁힌 신규 결정 목록이 불완전하고 실제 계약 접합 오류가 남아 있는데 이를 「비용」만으로 닫았다는 점이다.

### 1-V. v4 역반영 7건 개별 판정

| V-# | 계획이 적은 반영 내용 | v4 현재 문장 | 일치 |
|---|---|---|---|
| V-1 | §5-1⑫를 JobRecord/JobExecution/UsageRecord로 분해, Producer 분리 | §5-1⑫에 세 이름과 case/common/runtime 각각 명시 | 일치 |
| V-2 | 모듈5④⑤에 계약명·status 5값·CANCELLED 미포함·Owner/구현 담당 | ④의 기존 다이어그램에 5값, 추가 문장에 JobExecution·CANCELLED 제외·evidence/common Owner와 recording Owner 역할명. ⑤ 소유 표도 수정 | 의미 일치. 계획의 실명 표기와 문자 그대로 같지는 않음 |
| V-3 | RT8 force_rerun·SUCCEEDED 캐시·scope_ref 종결 | §12 RT8에 종결·계약/ADR 포인터와 해당 내용 | 일치. 캐시 tuple 누락은 계약 측 B10으로 별도 지적 |
| V-4 | §11-4 Job 분리 체크 | 해당 항목 체크 및 계약 포인터 | 일치 |
| V-5 | v4 CaseView 최소 구조 유지, 계약 부록 표기만 정리, enum 복제 안 함 | 모듈5⑥ 의미 수준 구조 유지. 계약 A/B절·Core 표기 | 일치 |
| V-6 | 보조 구조 TimeSourceCandidate/SpanResolution/TimeSourceCheck 이름만 등재 | §5-3에 세 이름·역할·필드는 recording 계약 소유라고 명시 | 일치. 후속 ref 규칙 상세 추가는 이 원래 V-6과 분리해서 봐야 함 |
| V-7 | 당시 ①~⑫ 유지, 계약 번호만 보정 | 후속 R-3·R-4 Owner 회신으로 ⑬ 추가 | 단계 차이로 설명 가능. V-7을 09-06 최종 총수라고 읽으면 오래된 기록 |

**V-2~V-4 보충.** 확정된 Job 분리를 계약에 맞춰 v4에 기록한 방향은 타당하다. 하지만 후속 §5-3의 「이 공백은 목데이터를 막지 않는다」는 소비자 입력을 전수 확인한 결과로 입증되지 않는다(B07). 이는 계약의 미완성을 상위 문서의 보증으로 바꾼 것이다. 또한 `CaseView:B§7`에 FINAL_PACKAGE 우선 규칙이 그대로 있어 「RequirementReport에만 두고 복제하지 않았다」는 R-7 설명과 다르다. v4의 09-06 개정 이력은 §11-4의 USER_REVIEWED 확인 종결을 누락한다. 버전 v4 유지 자체보다 실제 수정·미결 상태를 추적하기 어려워진 것이 문제다.

### 1-R. 회신 반영의 재검증

**R-1.** 원본 v1.1과 현재 계약을 직접 비교했다. 파일 전체를 덮어썼다면 이미 명시된 closed enum·fallback·nullable 표현 일부가 사라지는 것은 맞다. 그러나 「12건 모두 작성자의 베이스 착오이고 설계 의견이 아니다」는 자료로 증명되지 않는다. 다음 표의 '등급'은 **그 원본을 그대로 병합했을 때의 영향**을 말하며 §2 건수에 별도로 더하지 않는다.

| R-6이 나열한 12건 | 원본↔현재 대조 결과 | 감사 판정 |
|---|---|---|
| 캐시 SUCCEEDED 제한 | 원본 A§7은 기본 false도 추정/작성 필요, 현재 A§7·JobExecution §9-6은 SUCCEEDED 한정 | 회귀 방지 필요, BLOCK 성격. 다만 현행도 tuple 누락(B10) |
| JobRecord Consumer | 원본 헤더는 runtime/eval이 빠졌지만 A§3·§10은 실행을 common/runtime 소유로 명시 | **표기 누락은 확인, 직접 의존 변경이라는 BLOCK 증거는 부족. WARN 성격** |
| evidence 4필드 삭제 | 원본 B§5에는 네 필드가 없음, 현재 B§5에는 있음 | 차이는 사실. 삭제 의도·동등한 다른 UI 설계를 확인하지 않아 설계 결정의 정당성은 보류. 단순 기각 확정은 과도 |
| running_jobs label_key/status | 원본은 label_key 없음·status 매핑 작성 필요, 현재는 키/fallback·PENDING/RUNNING | 실제 wire·표시 계약 후퇴, BLOCK 성격 |
| progress.state | 원본 schema 자유 string·전체 enum 미결, 현재 4값 | **WARN으로만 보기 어려움**. 대기·실패를 다르게 내면 UI 분기 깨짐 |
| notices.severity | 원본 자유 string, 현재 INFO/WARN/ERROR | 단순 표기가 아니라 허용 값 범위. 소비자가 값으로 분기하므로 BLOCK 후보 |
| package 타입 | 원본 object/array 제안, 현재 문자열 map/string[] 등 구체화 | object 배열과 string 배열을 달리 만들 수 있어 BLOCK 후보. 원래 필드 수준 합의 증거는 별도 확인 필요 |
| manifest_summary.range | 원본 배열만, 현재 nullable | 정상 영상 0개의 명시적 경로를 잃음. **BLOCK 성격** |
| requested_at | 동일 필드·ISO8601, 원본은 필드명 제안 상태 | 값 자체의 차이보다 수락 표기 차이. WARN |
| 김준영 최종 승인 | 원본은 원칙 승인·필드 미서명, 현재 최종 스키마 승인 | **서로 다른 수락 기록**. 어느 것이 당시 사실인지는 독립 승인 원문 필요 |
| JobExecution 구현 담당 | 원본 common/runtime 소유는 유지, 정철원 기록 누락 | 역할 문서 기록 누락. WARN |
| 헤더·부록 표기 | 원본 예전 형식, 현재 표준화 | WARN. serialization 변경과 구분해야 함 |

원본 머리말은 **「v1: 2026-09-04 Accepted 기준」**을 명시한다. 따라서 `adr-consistency-2026-09.md:§7`과 `검수 계획:§9`의 「어느 판본을 베이스로 삼았는지 적지 않았다」는 문장은 사실과 다르다. 정확한 커밋·closure 세부 판본을 식별하지 못한다는 더 좁은 지적은 가능하다. §7은 개인 사본·비의도적 후퇴를 추측으로 표시했지만 §6 R-6과 계획 §9는 이를 사실로 단정한다. 팀 노션에 당시 최신본이 공개돼 있었다는 주장은 로컬 파일만으로 검증하지 못했다.

4필드 유지의 실질 목적(유형·신고유형·근거 표시 보존)은 제품 약속과 맞을 수 있다. 그러나 `product-spec.md:§7`은 정확한 네 필드나 「4종 유형 표시」를 고정하지 않는다. 특히 preview_ref의 정확한 직렬화는 제품의 유일한 답이 아니다. 따라서 임시로 기존 표시 기능을 보존하는 조치와 타 Owner의 스키마를 영구 확정하는 조치를 분리해야 한다. 원본 삭제가 정당했다고 단정할 자료도 없다.

**R-2.** 직접 답변의 반영은 다음과 같다.

| 원본 | 반영 확인 | 남은 차이/한계 |
|---|---|---|
| CALL-1 | A안, INFO_ 접두어, display별 info_state/source_label_key가 CaseView B§5~7에 있음 | 5단계 파생 알고리즘의 완결성은 답변이 증명하지 않음. observability·label_key와 scope는 PM 후속 추가 |
| CALL-5 | READY=PACKAGE_READY, readiness=overall, user_reviewed boolean, CorrectionRecord 분리 모두 있음 | 회신은 report 선택 우선순위·scope 신규 필드를 확정하지 않았음 |
| CorrectionRecord 원본 | 8개 kind·식별자·selection_rev·전후 값·수정 시각 보존. Draft·target_field/현재값/실패 수정 미결 보존 | 원본 §11을 가리키는 설명이 재편된 현행 문서에는 없는 §11처럼 읽힘(W01). 소비자 최종 리뷰 미진행은 사실 |
| CALL-6 | 별도 ReadoutRun·최소 7필드·실패 taxonomy 포인터·abstain 비실패 반영 | 결과→run 연결은 산문만 추가. 판독 결과 schema/JSON에는 run_id 없음(B03). eval 최종 확인도 첨부에 없음 |
| recording CALL-4 | opaque ID 방향, 위치·role 분리, 두 계약으로 작성, 기존 recording Accepted 동의, 운영 세부 미결 보존 | 원문은 최소 schema **제공 약속**과 opaque 방식 **제안**. 약속 이행이나 모든 field 계약 완료로 바꿔 읽을 수 없음 |

**R-3.** 5단계 규칙을 그대로 함수로 옮겨 분기 표본을 실행했다(§3.1). 입력 전체가 주어지면 순서 함수는 결정적이다. 그러나 필요한 입력 중 needs_review의 생산 규칙이 없고, 사건시각은 EvidenceValue조차 아니다. 따라서 EvidenceRecord만으로 화면 상태가 결정된다는 강한 주장은 반증된다. PM이 evidence 필드를 설계할 권한은 있지만 소비자 case의 입력·migration 합의를 자동으로 대신하지는 않는다.

**R-4.** scope가 있으면 무엇을 표시했는지 명시할 수 있다는 장점은 있다. 하지만 단일 객체·두 객체·별도 gate 값 등 복수 해법 중 하나를 선택했다는 것 자체가 「정답 유일」 조건과 다르다. web이 계산하지 않아도 잘못된 gate가 표시되면 통합 기준 ④를 위반한다. 보고서 선택은 evidence의 overall 계산과 달리 case의 현재 workflow·basis 선택 책임도 포함하므로, 규칙을 PM 소유 파일에 둔 것만으로 단독 소유가 되지 않는다. 게다가 실제로 CaseView에 규칙을 복제했다(W05).

**R-5.** 기존 판독 계약 승격에 대한 Owner 동의와 recording Owner의 opaque ref 방향은 원문에 있다. 현재 판독 예시의 frame_ref들은 fr_ 형식으로 바뀌었다. 따라서 *기존 plate 문서의 좁은 조건*에는 PASS를 줄 수 있다. 단, recording 원문이 「제안/제공하겠다」라고 한 것을 완성 schema라고 보지는 않는다. 신유민의 「전체 세트는 ReadoutRun과 결과 연결까지 추가되어야 완성」 조건은 B03으로 남는다. Accepted 문자열 하나로 전체 수락 조건이 해소됐다고 쓰면 안 된다.

**R-6.** CorrectionRecord의 correction_record ref, selection_rev 보존, EVENT_TIME_MANUAL과 TIME_HINT_EDIT 구분은 TimeResolution §5·§13의 추적 요구와 맞는다. 하지만 전후 값이 any이고 같은 필드의 현재값 규칙이 미결이어서 실제 시간 수정 fixture를 합의 없이 만들 수는 없다. ReadoutRun.operation으로 PLATE/OVERLAY_TIME stage를 추론할 수 있어 taxonomy의 stage 요구가 원천적으로 불가능한 것은 아니다. 다만 명시적 stage 매핑·소비자 수락은 없고 taxonomy 자체도 Owner 확정 전 초안이다. produced_by.run_ref는 공통 ContractRef 형태를 지켜야 한다. 단순 run 수가 있다고 Abstention Recall의 정답 라벨·분자가 자동으로 생기지는 않는다(N02).

**R-7.** 로컬에는 CALL-1·2·4·5·6·7 **6개 카드**와 공지문 1개가 있다. CALL-3은 카드 없이 닫았다고 계획 §9에 적혀 있어 누락 첨부라고 임의 판단하지 않았다. 카드별 점검은 다음과 같다.

| 카드 | 확인 결과 |
|---|---|
| CALL-1 | A/B 선택과 INFO_ 대안은 명시. 그러나 §2⑶ 「재료는 이미 EvidenceRecord에 다 있다」는 B01과 충돌. §5에 Owner 파일 수정과 새 ADR까지 배정하여 델타 답변/전체 문서 교체 범위가 흐려짐 |
| CALL-2 | 경로 축약인지 직접 의존인지 구분해 물었고 (a) 확인 있음. PM 추천이 곧 수락으로 처리되지는 않아 이 부분은 적절 |
| CALL-3 | 작성·발송 없음. 회의 확정이라는 ADR을 근거로 호출 생략. 추가 순서는 회의 근거가 아니므로 별개(B11) |
| CALL-4 | 세 대안과 잠정 ref에 제안 표시 있음. 미답 시 잠정 적용 규칙이 수락처럼 변하면 안 됨. 실제 Owner가 role/위치 인코딩을 반대한 점은 대안 검증의 필요성을 보여줌 |
| CALL-5 | ⑵를 WARN이라고 했으나 readiness 4/5와 overall은 소비 의미가 달라 BLOCK 성격. 「타입을 좁히면 끝」이라는 설명이 scope·이력 선택 문제를 놓침 |
| CALL-6 | 별도 Run 필요성은 근거 있음. 다만 A/B/C 세 선택 중 (c)는 통계를 포기하므로 상위 일정 변경 선택이다. 최소 예시만으로 eval 지표가 닫힌다는 인상은 과도 |
| CALL-7 | 새 카드 형식과 세 대안이 있음. 하지만 발송하지 않고 소유자의 선택을 PM이 확정. 형식 개선과 승인 절차 개선은 별개 |

계획 §7은 선택지를 2개까지라고 했지만 CALL-4·6·7은 3개다. 이것만으로 문제라고 할 필요는 없으나 「카드 설계 규칙을 그대로 지켰다」고 할 수는 없다. PM 추천 자체는 부당하지 않다. 문제는 추천을 받지 않은 항목도 최종 결정으로 바꾼 것, 그리고 회신 작성자의 의도를 추측에서 사실로 바꾼 것이다.

### 1-Z. 종결 상태의 전수 대조

**Z-1.** ADR §4(a)~(f)를 현재 계약·회신과 다시 대조했다. JobExecution/UsageRecord의 문서 부재는 파일 생성으로 해소됐지만 직렬화·캐시·연결은 남는다. 수락 헤더는 13Final/1Draft로 존재하지만 날짜·전체 세트 완성은 별개다. recording은 §4(d)가 **부분 종결**이라고 적은 점까지는 정직하다. 그러나 그 옆에 「Mock을 막지 않음/미해결 0건」이라고 결론 내린 것은 B06~B09 및 Draft 미결을 충분히 설명하지 못한다. 표시 상태와 READY 관련 회신은 반영됐지만 B01·B02가 남고, enum 이름 보정은 확인됐다. §4 표의 '해결'은 아래 F별 증거보다 강한 종결 표현이다.

| ADR §4 항목 | 발견·호출·반영 연결 | 현행 파일로 재판정 |
|---|---|---|
| (a) CaseView 출처·정보 상태 | F-7 → CALL-1 → R-1 | 필드 추가는 완료, 파생 완결은 B01 때문에 미종결 |
| (b) 판독 소비 경로 | F-9b/F-24 → CALL-2 → C1-9 | case 경유 확인·현행 헤더 반영. 종결 근거 있음 |
| (c) 수락 표기 4건 | F-22 → C1-13 + CALL-4/6 → R-5 | Status는 있음. B12 날짜와 B03 전체 세트 조건은 별도 확인 필요 |
| (d) recording 자산 계층 | F-21 → CALL-4 → R-5 | 작성 약속·ref 방향은 있음, 계약 2건 없음. 부분 종결까지만 인정 |
| (e) case 미결 4건 | F-25/F-26 → CALL-5 → R-2/R-3, 후속 R-7 | READY/readiness/user_reviewed 결정은 반영. CorrectionRecord는 Draft, scope의 후속 선택은 B02 |
| (f) ReadoutRun | F-27/F-29 → CALL-6 → R-4 | 새 계약 생성·⑦ 등재 완료. 결과/Usage 접합 B03/B05 남음 |

| 발견 번호 | 현재 대조 결과 |
|---|---|
| F-1 | 제목·헤더 번호 보정은 있음. 본문 옛 번호 남음(W01) |
| F-2 | recording 묶음이 번호 밀림 원인이라는 것은 추정. 최초 작성 경위를 독립 검증하지 못함 |
| F-3 | JobExecution 파일 생성됨. B04·B10 남음 |
| F-4 | UsageRecord 파일 생성됨. B05 남음 |
| F-5 | JobIntent의 의미가 JobRecord에 흡수되고 v4⑫가 구분함 |
| F-6 | Core 표기·A/B절 반영됨 |
| F-7 | 정보 상태·출처 필드 추가됨. B01 때문에 기능 종결 불가 |
| F-8 | TimeResolution §2·§4가 overlay/filename/metadata/user/unknown 의미를 나눔. UI projection 차이는 B01 |
| F-9a | VisualEvidence 헤더 현재 수정됨 |
| F-9b | CALL-2(a) 확인, plate 헤더 경유 표기 있음 |
| F-10 | v4 §5-3에 세 보조 구조 등재됨 |
| F-11 | 표준 헤더 2건 여전히 불완전(W01) |
| F-12 | ADR-003/ADR-08/ADR-부록/작성 필요 등 혼합 표기 남음. 통합 wire 문제는 아님 |
| F-13 | 일부 export 제목은 정리됐으나 중복 H1·aside·과거 filecite 잔재는 남음. 전부 정리됐다는 증거 없음 |
| F-14 | ownership lifecycle 이름 보정 확인. AnalysisRun §5의 runtime JobRecord 표기는 여전히 옛 이름(W01) |
| F-15 | 구현 배정은 ADR 근거, PM 추가 순서는 B11. 독립 회의록 미확인 |
| F-16 | v4 RT8·Job 분리 체크 종결. 입력 정규화 전부 확정으로 확대하면 안 됨 |
| F-17 | ownership §7-③ 실제 계약 묶음·Owner 표 갱신됨 |
| F-18 | 현재 baseline 4종 일치. 과거 변경 횟수는 preimage 없음 |
| F-19 | 출처 VIDEO_OVERLAY_OCR과 Need OVERLAY_TIME_OCR은 다른 값 공간. 이름 통일을 미해결 설계로 셀 필요 없음 |
| F-20 | stage READY와 EvidenceRecord의 상태 배제는 구분됨. 세 gate 표시 완결은 B02로 별도 |
| F-21 | 두 recording 계약 아직 없음. opaque 규약은 스키마·입력 사실을 대신하지 못함(B07) |
| F-22 | 3개 헤더 추가·plate 조건부 승격 근거 있음. 날짜 B12·세트 B03 남음 |
| F-23 | plate Contract Version 표기 있음 |
| F-24 | 세 헤더 보정됨. AnalysisScope 본문 Consumer는 미반영(W01) |
| F-25 | READY/readiness/user_reviewed 답은 반영. scope·gate 표현 B02 남음 |
| F-26 | CorrectionRecord Draft 생성. 소비자 리뷰·값 선택 규칙 미결이므로 완결 계약은 아님(N02) |
| F-27 | ReadoutRun 생성. 결과 연결 schema·Usage 참조가 남음(B03·B05) |
| F-28 | case 전달/evidence 판정 경로는 상위 문서와 양립. 호출 코드 검증은 하지 못함 |
| F-29 | 후속 Owner 회신으로 ⑦·⑬ 등재. CorrectionRecord의 등재와 Draft 상태는 양립 |

F-9a/F-9b 분기 때문에 표의 실제 행 수는 F-1~F-29라는 번호 개수와 다르다. 이를 새 결함 수로 세지 않았다. 카드별 결과는 §1-R, V-1~V-7은 §1-V, R-1~R-7 반영 정확도는 §1-R에서 교차 연결했다.

**Z-2·Z-3.** Status 실계수는 Final — Accepted 13, Draft — Consumer Review 대기 1이다. CorrectionRecord의 Draft 이유는 원문에 명시돼 있어 보존이 타당하다. 반면 제목은 Final이므로 W01이다. retry/timeout·보관·환율·업로드 전략 등 실제 보존한 미결도 확인했다. 그러나 scope와 세 수락 날짜를 임의 확정한 사례가 있어 「하나도 채우지 않았다」는 총괄 주장은 반증된다. 미작성 recording·CorrectionRecord 리뷰를 '검수 밖 산출물'로만 옮겨 놓고 통합 차단이 사라졌다고 하는 것도 충분하지 않다.

**Z-4.** `git show --stat 81e5539`와 이름 목록을 확인했다. `docs/modules/**`는 바뀌지 않았다. contracts/ADR, architecture, ownership과 mock refs가 변경 범위다. 공용 문서의 일관성 보정은 PM 범위로 볼 수 있지만, 경로가 modules 밖이라고 case Owner의 필드 결정권까지 PM으로 바뀌는 것은 아니다(B02·B11·B12).

**Z-5·Z-6.** 14개 계약의 SourceAsset/MediaStream/AnalysisSource/RemoteCopy/IncidentClip/DerivedAsset 및 ref 사용을 전수 검색하고 해당 문맥을 읽었다. 소비자가 외부 자산 객체의 필드를 직접 펼쳐 읽도록 정의한 확정 스키마는 찾지 못했다. 하지만 `RequirementReport:§2`는 derived asset metadata를 실제 입력으로 요구한다. typed dereference 문장이 없다는 것은 입력이 불필요하다는 증거가 아니다. mock refs는 계약 밖에 있고 폐기·필드 없음 경고도 있어 임시 ID 예시로 사용할 수 있다. 이 문서만으로 메타데이터 필드를 만들어서는 안 된다. coverage NOTE를 남긴 것은 타당하지만, v4 §5-3의 무조건적인 통합 가능 문장은 경고 효과를 약화한다.

**Z-7·Z-8.** 스크립트가 구현한 문자열 검사는 실제 실행됐다. 그러나 코드가 없는 7경로의 PASS와 뜻을 검사하지 않는 문서 검사의 PASS로 통합을 보증할 수 없다. 마지막 판단은 §4의 여섯 시나리오로 해야 하며 이번 검토에서는 실제 통합 실행·결과 파일·Trajectory 1회차 실적을 확인하지 못했다.

## 2. 발견한 문제

| # | 등급 | 위치 | 내용 | 왜 문제인가 | 제안 |
|---|---|---|---|---|---|
| B01 | BLOCK | `contract-job-record-case-view.md:B§6~7·§10`; `contract-evidence-record-needs.md:§3`; `core-user-flow.md:§13` | needs_review 생산 규칙이 없고 occurred_at은 EvidenceValue가 아닌데 공통 info_state 파생 입력으로 가정. 정상 예시의 filename 시각은 INFO_SOURCE_VERIFIED | 동일 Evidence 입력을 case 구현자가 다르게 검토 상태로 만들 수 있고 파일 시각의 확인 필요 화면과도 어긋남 | evidence/case가 각 display의 입력·우선순위·source key 전달·검토 필요 규칙을 함께 정하고 null/수정/충돌 fixture로 확인 |
| B02 | BLOCK | `adr-consistency-2026-09.md:§6 R-7`; `contract-requirement-report-package.md:§5.2-1·§6`; `contract-job-record-case-view.md:B§5~7`; `ownership.md:§7-④` | PM이 case의 scope를 단독 확정. 「FINAL_PACKAGE가 존재하면 우선」 규칙에 current basis/동일 scope 다건 선택이 없고 단일 projection에서 evidence gate가 가려짐 | 오래된 Package 판정을 현재 수정 후 상태에 표시하거나 evidence 충족/꾸러미 준비를 혼동. 통합 기준 ④에 직접 영향 | case Owner가 최신 basis별 report 선택과 세 gate 표시 계약을 결정하고 evidence/web 확인. 두 report·재검사·null 조합을 함께 검증 |
| B03 | BLOCK | `contract-readout-run.md:§5`; `contract-plate-overlay-readout.md:§4·§6·두 JSON 예시`; `contract-observation.md:§6 produced_by`; `CALL-6 회신:답변` | 결과가 run_id를 보존한다는 산문과 달리 PlateReadout/OverlayTimeReadout 필드 표·JSON에 run_id가 없음 | 스키마/예시대로 목을 만든 readout과 결과→run 역참조를 요구하는 case/eval이 접합되지 않음 | 결과 식별자·run 연결 위치와 Observation.run_ref의 ContractRef 모양을 판독 계약에도 명시하고 실패 0결과/정상 1결과 예시를 대조 |
| B04 | BLOCK | `contract-job-execution.md:§4·§5·§7`; `contract-observation.md:§3 ContractRef` | produced는 ContractRef[]인데 정상 JSON은 string[] | runtime 목이 문자열을 내면 case가 kind/ref를 읽을 수 없음 | 공용 ContractRef 규약을 가리키고 정상·실패 예시를 그 모양으로 통일 |
| B05 | BLOCK | `contract-usage-record.md:§5·§7`; `contract-readout-run.md:§4·§7` | UsageRecord.run_ref는 AnalysisRun.run_id만 정의. ReadoutRun은 usage_refs를 제공하고 실제 run identity가 있음 | readout 사용량에 rr_를 넣는 구현과 AnalysisRun만 허용하는 원장이 충돌. null이면 정의상 'Run 없는 호출'이어서 원장의 연결 의미를 잃음 | runtime/readout/eval이 run_ref의 허용 대상·양방향 연결을 합의. AnalysisRun·ReadoutRun·진짜 run 없는 호출 세 예시 검증 |
| B06 | BLOCK | `contract-recording-timeline-asset-span.md:§8.1·§9·§10·§23` | 요청 [50,130) 중 spans [50,60), missing [60,120)만 있어 [120,130) 10초가 설명되지 않음 | evidence가 근거 구간의 빠진 범위를 알 수 없고 PARTIAL fixture 소비 결과가 구현마다 달라짐 | Owner가 요청 범위 분할의 완전성·중복·범위 밖 입력과 FAILED 원인 표면을 확정하고 예시 검증 |
| B07 | BLOCK | `contract-requirement-report-package.md:§2·§4.5·§6·§8.1`; `contract-recording-timeline-asset-span.md:§12`; `adr-recording-timeline-asset-span.md:§13`; `ownership.md:§7-④` | opaque ref만으로 충분하다는 결론과 달리 실제 evidence에는 파생 자산 metadata가 필요. 준비 자산/FrameRef/Fine input/stream selector의 필요한 표면이 미작성 | 모든 모듈을 fake로 바꾼 화면 데모와 'evidence는 실제 순수 함수'인 통합을 혼동. final package의 크기·가시성·실재 자산 판정을 계산할 입력이 합의되지 않음 | 전체 저장소 구현 대신 해당 통합이 소비할 최소 자산 사실·lookup/주입 표면을 recording/evidence/search가 합의. opaque ID는 그대로 유지 가능 |
| B08 | BLOCK | `contract-analysis-scope.md:§5·§6·§10`; `contract-recording-timeline-asset-span.md:RecordingTimeline time_basis·timeline_status`; `module-architecture.md:§5-4` | recording은 절대 anchor 없는 relative-only timeline을 허용하지만 AnalysisScope.time_ranges는 timezone 포함 ISO8601만 허용 | 시각을 모르는 영상에서 search를 시작할 때 임의 날짜를 만들거나 스키마 밖 상대값을 넣게 됨 | case/search/recording이 상대 구간 입력 또는 명시적 adapter 계약을 결정. 임의 기준일로 미결을 메우지 말 것 |
| B09 | BLOCK | `contract-analysis-run-candidate-event.md:§4-1`; `contract-recording-timeline-asset-span.md:revision·§23`; `adr-recording-timeline-asset-span.md:§4 결정3` | Candidate.span은 timeline_id만 있고 사용 revision 연결이 없음. 같은 ID로 revision이 증가하는 recording 결정은 과거 사용 revision의 추적을 요구 | rebase 후 옛 후보가 어느 anchor/revision을 사용했는지 계약상 복원할 경로가 명시되지 않음. 픽셀 상대 위치가 같다는 것과 과거 시각 provenance 보존은 다름 | Candidate/Run/별도 연결 중 한 곳에서 사용 revision을 식별하도록 Owner 합의. 현재 화면의 새 anchor와 과거 provenance를 분리 검증 |
| B10 | BLOCK | `adr-job-record-case-view.md:A§7`; `contract-job-record-case-view.md:A§7·§10`; `contract-job-execution.md:§9-6` | ADR 캐시 키는 case_id+kind+fingerprint인데 현행 재사용 규칙은 fingerprint 동일+SUCCEEDED만 명시 | 같은 fingerprint의 다른 case/kind를 재사용해도 현행 축약 규칙을 만족. 잘못된 작업 결과를 reuse하는 두 구현이 가능 | 원래 캐시 namespace를 계약에 일관되게 연결하고 case/kind만 다른 반례로 확인. fingerprint에 몰래 포함됐다고 가정하지 말 것 |
| B11 | BLOCK | `adr-consistency-2026-09.md:§2 C1-6`; `ownership.md:§5`; `검수 계획:§3 트랙2·§11-5` | 'resolve_span 목 응답을 낸 다음'이라는 정철원 작업 순서를 PM이 추가하고 호출 없이 닫음 | 부하·역할 배정은 트랙2라는 자기 기준 위반. runtime 목 준비 일정에도 영향 | 회의에서 확정한 배정과 PM이 제안한 순서를 분리하고 담당자의 확인을 받기 전 종결하지 말 것 |
| B12 | BLOCK | `adr-consistency-2026-09.md:§2 C1-13`; `contract-analysis-scope.md:Accepted`; `adr-analysis-scope.md:결정일` | 세 계약의 수락일을 같은 회차라는 이유로 09-04로 확정. AnalysisScope ADR은 09-05 closure 보완 | 타 Owner의 수락 기록을 유일한 답 없이 채움. **사용자가 지정한 C1 월권 BLOCK 기준 적용**; 날짜 오기가 런타임을 깨뜨린다는 주장은 아님 | 각 판본별 실제 수락일을 원문으로 확인하고 Status와 날짜 판정을 나눌 것. 자료 없으면 날짜 확인 불가로 유지 |
| W01 | WARN | `adr-consistency-2026-09.md:§2 C1-2·C1-4`; 관련 계약 헤더·본문; `contract-correction-record.md:제목·머리말` | 헤더 통일 미완료, AnalysisScope eval Consumer 본문 잔존, 옛 계약 번호·절 포인터, Correction Draft/Final 제목 충돌 | 현재 규칙·근거 파일을 찾는 사람이 잘못된 행/절을 따라감 | 의미 변경 없이 실제 파일 기준으로 헤더·본문 포인터·제목·완료 주장을 정리 |
| W02 | WARN | `adr-consistency-2026-09.md:§6 R-6·§7`; `검수 계획:§9`; `Final Data Contract v1.1 원본:머리말` | 원본에 base v1/09-04 Accepted를 썼는데 '베이스 미기재'라고 서술. 작성자 의도를 추측/사실로 혼용. 12건 등급도 실제 영향과 불일치 | 회신자 결정을 검증하는 근거 기록이 왜곡됨 | 정확한 snapshot 미식별과 버전 무기재를 구분. 의도는 회신 전 보류하고 12건별 영향·승인 근거 재분류 |
| W03 | WARN | `검수 계획:§0-A·§0-B·§9`; `adr-consistency-2026-09.md:§4` | 완료/미답/발송 대기 표가 같은 최종 문서에 공존. NOTE가 5개뿐이라는 요약은 실제 12개와 다름. CALL-1~6 회신 완료에 무호출 CALL-3 포함 | 다음 담당자가 어느 작업·통보가 실제 남았는지 판단하기 어려움 | 과거 표에 기준 시점을 명시하고 최종 상태·미작성·검토 대기·미발송을 구분. B항목을 단순 장부 수정으로 닫지 말 것 |
| W04 | WARN | `contract-job-execution.md:§6·§9·§10`; `contract-usage-record.md:§5·§8·§9`; `adr-consistency-2026-09.md:§3` | 'PM이 새로 정한 것은 필드 추가뿐, 여기만 보면 됨'과 달리 허용 전이·attempt 규칙·RUNTIME_ 접두어·토큰 합산·run_ref 제한·가격표 관리도 규정 | 소비자에게 알린 리뷰 범위와 실제 변경 의미가 다름. '비용' 고지는 검토 범위 누락을 보완하지 못함 | 상위 문서에서 유도된 의미와 PM 신규 결정·미결을 모두 분류하고 소비자에게 실제 범위를 제시 |
| W05 | WARN | `contract-job-record-case-view.md:B§7`; `contract-requirement-report-package.md:§5.2-1`; `contract-readout-run.md:§6`; `module-architecture.md:§5-3`; `mock-pack-v1-refs.md` | '규칙 복제 안 함'이라고 하면서 report 선택 규칙, taxonomy 5값, ref 접두어/위치 규칙을 복수 현행 문서에 적음 | 지금 의미가 같아도 한쪽 수정 시 드리프트. R-7의 단독 소유 주장과도 모순 | 한 곳을 규칙 원천으로 두고 나머지는 포인터·비규범 예시로 구분 |
| W06 | WARN | `module-architecture.md:개정 이력·§11-4`; `검수 계획:§0 D-3·§10` | 09-06 USER_REVIEWED 체크 종결이 해당 날짜 이력에서 빠짐. 착수 당시 '네 곳만'과 최종 수정 범위도 다름 | v4를 유지하며 일부만 재독하라는 안내가 실제 범위를 온전히 전달하지 못함 | 최종 수정 절 목록과 날짜별 이력을 일치시킬 것 |
| W07 | WARN | `contract-recording-timeline-asset-span.md:§6.2·§8.1·§24`; `contract-plate-overlay-readout.md:두 JSON 예시`; `contract-job-record-case-view.md:B§8·§13` | sa_/ms_/clip_ 규약과 asset_A/stream_A_front/incident_clip_001 예시가 공존. thumb_ref의 frame:a09@178.6은 명시적 미결로 남음 | opaque를 약속해도 예시대로 role/위치를 해석하는 목이 생길 수 있음 | 임시 예시와 현행 규약을 명확히 구분하고 Owner 규약으로 통일. thumb_ref의 자산 종류는 추정하지 말 것 |
| N01 | NOTE | `check_boundaries.py:전체`; 로컬 실행 결과 | PASS, boundary 7NOTE+coverage 5NOTE, 검사 코드 0개. 제한된 문서 검사만 실행 | 구현 경계·실제 CI 통과·통합 실행은 보증하지 않음 | 결과에 검사 대상 수와 지원 범위를 함께 표시. 확대할 검사는 §3.6 참고 |
| N02 | NOTE | `contract-correction-record.md:§9`; `contract-readout-run.md:§2·§10`; `failure-taxonomy.md:초안·기록 규칙` | CorrectionRecord 리뷰와 값 선택 미결 보존은 적절. readout taxonomy/eval 확인 미완료. run 분모만으로 Abstention Recall 계산 가능하다는 근거 부족 | pending을 지킨 사실과 통합에 필요한 결정이 끝났다는 사실은 다름 | 원문 그대로 미결 유지하고 관련 fixture·평가 정답/집계 규칙 확인 뒤 각각 닫을 것 |
| N03 | NOTE | `81e5539`·`622a869` 변경 목록; `tool-trajectory-review.md:§4` | 계약 14건이 처음 추적된 커밋. modules 내부/운영진 보호 4파일 변경 없음. Trajectory 실적 표는 비어 있음 | git만으로 보정 전후·담당자 수락·통합 실행을 증명할 수 없음 | §5·§6의 자료 한계를 유지하고 완료 주장에 현재 파일 확인과 역사 증명을 구분 |

## 3. 검수가 놓친 충돌 (신규 발견)

이 절의 '신규'는 문서 전체에서 처음 언급된 개념이라는 뜻이 아니라 **F-1~F-29 및 R-1~R-7이 해당 접합 오류를 식별·판정하지 않았다는 뜻**이다. 기존 '계약이 없다/정보 상태가 없다'와 그 보정 이후 새로 생긴 정확한 실패를 구분했다.

| 새 발견 | 해당 문제 | 기존 검수와의 차이 |
|---|---|---|
| 상태 파생 입력이 계약상 완결되지 않음 | B01 | F-7/R-1은 info_state 필드 추가, R 후속은 observability 추가까지만 다룸. occurred_at 비동형 입력·needs_review 원천은 닫지 않음 |
| 이력 report 우선 선택이 오래된 판정을 노출 | B02 | R-7은 scope 부재를 다뤘지만 immutable 다건 report의 current basis 선택과 두 gate 표시 손실은 다루지 않음 |
| 결과→ReadoutRun 연결의 schema/JSON 누락 | B03 | F-27/R-4는 별도 계약 생성·산문 연결로 완료. 실제 결과 schema에서 연결 키가 없는 문제는 별도 |
| produced의 object/string 불일치 | B04 | F-3/C1-8은 계약 공백 해소. 정상 예시가 자기 타입을 위반한 것은 미지적 |
| UsageRecord가 ReadoutRun을 참조할 수 없음 | B05 | F-4와 F-27을 따로 닫고 양쪽의 연결을 대조하지 않음 |
| SpanResolution 예시의 미설명 10초 | B06 | F-21은 자산 계층 미작성. 이미 Final인 span 응답 자체의 결함은 미지적 |
| 상대 전용 timeline을 절대시각 scope에 넣을 수 없음 | B08 | enum·상태 이름 대조만으로는 입력 좌표계의 불일치를 잡지 못함 |
| Candidate에서 사용 timeline revision을 추적할 경로 부재 | B09 | 각각의 immutable 선언을 확인해도 ref 연결까지 대조하지 않으면 누락 |
| 캐시 namespace 일부가 현재 계약에서 사라짐 | B10 | 기존 검수는 force_rerun·SUCCEEDED 조건만 확인. case_id/kind tuple 대조를 놓침 |

### 3.1 정보 상태 5단계의 실행 결과와 입력 반례

`contract-job-record-case-view.md:B§7`을 순서 그대로 옮겼다. 정책을 추가하지 않았다.

```python
def info_state(value, user_corrected, needs_review, observability):
    if value is None:
        return "INFO_UNKNOWN"
    if user_corrected:
        return "INFO_USER_CONFIRMED"
    if needs_review:
        return "INFO_NEEDS_REVIEW"
    if observability == "OBSERVED":
        return "INFO_SOURCE_VERIFIED"
    return "INFO_AI_ESTIMATED"
```

| 입력 | 실제 결과 | 확인한 의미 |
|---|---|---|
| value=null, corrected=false, needs_review=true, OBSERVED | INFO_UNKNOWN | needs_review=true와 INFO_NEEDS_REVIEW는 동치가 아님 |
| value='v', corrected=true, needs_review=true, OBSERVED | INFO_USER_CONFIRMED | 사용자 수정 우선으로 정보 상태는 확정인데 검토 boolean은 true인 조합을 허용 |
| value='v', corrected=false, needs_review=false, OBSERVED | INFO_SOURCE_VERIFIED | 같은 evidence라도 review 입력이 달라지면 아래 행과 달라짐 |
| value='v', corrected=false, needs_review=true, OBSERVED | INFO_NEEDS_REVIEW | review 입력의 결정 주체·근거가 필요 |
| value='v', corrected=false, needs_review=false, INFERRED | INFO_AI_ESTIMATED | 나머지 분기 확인 |

이 다섯 결과 자체는 순서 규칙대로다. 오류는 **needs_review를 어디서 구하는지 계약에 없는데 전체 파생이 닫혔다고 주장하는 것**이다. `EvidenceValue` 필드는 value/source/support_refs/user_corrected이고 needs_review가 없다. `TimeResolution`에는 상태·검증·충돌이 있으나 이를 display별 needs_review로 변환하는 규칙이 없다.

더 직접적인 입력 불일치는 `contract-evidence-record-needs.md:§3`이다. `vehicle_number`는 EvidenceValue지만 `occurred_at`은 `{value, time_resolution_ref, resolution_status}`이고 source/user_corrected가 없다. `location`은 coord/address/place_name/search_keyword/user_hint의 여러 EvidenceValue를 가진다. 따라서 '해당 EvidenceValue 한 개'를 공통 입력으로 쓰려면 사건시각의 역참조·변환과 위치 대표값 선택을 먼저 계약화해야 한다. 여기서 case가 임의 선택하면 '정책 판단을 하지 않는다'는 원칙을 달리 구현할 수 있다.

`CaseView:B§10-8`은 user_reviewed(워크플로), user_edited(레코드), INFO_USER_CONFIRMED(필드)의 구분이다. needs_review와 info_state의 관계를 강제하는 불변조건이 아니다. 사용자 확인 뒤 UI가 needs_review만 보고 다시 묻는 구현과 info_state 우선으로 묻지 않는 구현이 둘 다 나올 수 있다. 순서 규칙의 예외를 boolean 소비 계약에도 명시해야 한다.

정상 JSON의 filename 시각은 needs_review=false/INFO_SOURCE_VERIFIED인데 `core-user-flow.md:§13 파일 기록을 이용해 계산한 경우`는 확인 필요를 요구한다. 단지 source를 OBSERVED로 분류하면 해결되는 문제가 아니다. 추가로 `EvidenceValue.source.label_key`는 전달용 필드인데 CaseView §6~7은 source.kind를 라벨 키로 옮긴다고 설명한다. 직접 전달인지 별도 매핑인지도 한 곳에서 정해야 한다.

### 3.2 단일 requirements projection의 정보 손실과 오래된 판정

다음은 현재 계약이 허용하는 입력을 사용한 문서 규칙 반례다. 실행 중인 제품을 관측했다는 뜻은 아니다.

```text
t1: EvidenceRecord ev1
    EVIDENCE report e1 = PASS
    FINAL_PACKAGE report p1 = PASS, ReportPackage pkg1
t2: 사용자 수정 -> EvidenceRecord ev2 (ev1 supersede)
    EVIDENCE report e2 = BLOCK
    ev2의 FINAL_PACKAGE report는 아직 없음
```

RequirementReport §6은 immutable·재검사 새 report·supersedes_ref·basis.evidence_record_ref를 허용한다. 반면 §5.2-1의 규칙을 문자 그대로 적용하면 **p1이 존재하므로 FINAL_PACKAGE/PASS를 싣는다**. current evidence basis로 필터하는 구현은 e2/BLOCK을 싣는다. 현재 규칙에는 두 구현 중 하나를 배제할 문장이 없다. '현재 케이스의 report'라고만 가정하면 부족하다. 동일 scope에도 이력이 여러 개라는 계약과 함께 선택 조건을 써야 한다.

이력과 무관하게 EVIDENCE=PASS, FINAL_PACKAGE=BLOCK인 현재 쌍에서도 단일 requirements는 FINAL_PACKAGE/BLOCK만 보여준다. `stage=EVIDENCE_REVIEW`는 EVIDENCE_SUFFICIENT=true 자체를 뜻하지 않는다. 따라서 web이 case/evidence 계약을 다시 읽거나 추론하지 않고 세 gate를 구분해 표시할 수 있다는 보장이 없다. 이는 '꾸러미 단계에서 값이 조금 잘못 보일 뿐'이 아니라 `ownership.md:§7-④`가 직접 요구한 접합 조건이다.

또한 CaseView schema·필수 표는 requirements를 object/scope 필수로 설명하지만 §5.2-1과 실패 예시는 requirements=null을 허용한다. null과 미생성·새 basis 재검사 대기를 포함해 **선택 대상과 nullable**을 함께 정리할 필요가 있다. 해결안을 감사자가 확정하지는 않는다.

### 3.3 참조의 생산·소비 모양을 연결해 확인한 결과

**JobExecution → case.** JSON을 파싱하니 §7 정상 예시의 produced 첫 원소 타입은 `str`였다.

```json
"produced": ["run_2026_0901_0007"]
```

§4·§5의 선언은 `ContractRef[]`이고 공통 Observation §3의 ContractRef는 `{kind, ref}`다. 단순 ID[]로 다룰 것인지, 공통 ref object로 다룰 것인지 실제 소비를 달리 만들기 때문에 B04다. 'opaque'는 소비자가 ID 내부를 해석하지 말라는 뜻이지 외부 object 모양을 생략해도 된다는 뜻이 아니다.

**판독 결과 → ReadoutRun.** `contract-plate-overlay-readout.md`의 두 실제 JSON block을 파싱했다. PlateReadout의 키는 readout_id/case_id/candidate_id/input_ref/target_association/observation/consensus/abstained/abstain_reason/best_frame/frame_results, OverlayTimeReadout의 키는 readout_id/case_id/candidate_id/input_ref/observation/validation/samples였다. **둘 다 run_id가 없다.** Observation 안에도 새 run 연결을 표현한 정상 예시가 없다. 새 readout-run §5의 산문 요구만 보고 Owner 조건이 전부 충족됐다고 할 수 없다.

**ReadoutRun → UsageRecord.** ReadoutRun 정상 예시는 rr_881→usage_5521을 갖는다. 하지만 UsageRecord.run_ref는 AnalysisRun.run_id 또는 Run 개념 없는 호출의 null만 설명한다. readout 사용량을 rr_881로 연결할지 null로 둘지 합의가 없다. UsageRecord의 로컬 OCR 예시도 null을 사용해 이 공백을 덮는다. 공용 원장의 Run 연결을 양쪽에서 같은 의미로 읽도록 정해야 한다.

판독의 nested observation이 공통 Observation envelope인지 domain 요약인지도 모호하다. `Observation:§10`은 모듈 경계를 넘는 semantic value에 envelope를 적용하지만 §14는 OverlayTimeReadout에 '적용 가능'이라고 적고, 판독 예시는 공통 produced_by/support_refs/source object를 그대로 갖지 않는다. 모든 best_frame을 Observation으로 감싸야 한다고 주장하는 것은 아니다. **semantic 관찰값의 정규화 위치와 결과-run 연결**을 B03의 확인 범위에 넣어야 한다.

### 3.4 시간 구간·revision·캐시 반례

**SpanResolution 예시를 직접 계산했다.** recording §8.1의 코드 fence(JSON 언어 표시가 없는 fence)를 JSON으로 읽고 spans와 missing_ranges의 합집합을 requested_range와 비교했다.

```text
requested_range = [50.0, 130.0)
usable spans    = [50.0, 60.0)
missing_ranges  = [60.0, 120.0)
설명되지 않은 범위 = [120.0, 130.0), 10.0초
```

§9의 PARTIAL은 'spans!=[] AND missing_ranges!=[]'이므로 이 예시는 그 조건을 통과한다. §23의 불변조건도 해당 10초를 검출하는 명시적 완전성 조건이 없다. 정상 asset_A/B가 무엇인지를 dereference하지 않아도 이미 오류가 나온다. FAILED는 failure reason이 필요하다고 하는데 invalid request 등에서 reason을 어느 필드에 담을지도 성공 예시만으로는 닫히지 않는다.

**상대 구간 반례.** recording은 working_anchor=null이어도 usable relative timeline을 허용한다. AnalysisScope는 timezone 포함 ISO8601 start/end를 필수로 요구한다. 상대 50~60초를 달력 시각으로 바꿀 근거가 없는 영상이 양 계약의 접합 반례다. Scope 외부에 Source를 주입하는 public API가 있을 수 있지만, 그것만으로 상대 범위를 ISO8601로 표현할 수 있는 것은 아니다. 이 변환 계약은 현재 14개 파일에서 확인되지 않았다.

**revision 반례.** Candidate.span의 canonical 값은 timeline_id/start_ms/end_ms/representative_ms이고 revision은 없다. recording의 동일 timeline_id rebase는 revision을 증가시키며 ADR §4 결정3은 Search가 사용 revision을 provenance로 추적해야 한다고 적는다. 새 anchor로 화면 시간을 다시 계산하는 것은 가능해도 이전 실행의 사용 revision을 복원할 계약상 링크는 별개다. Search 픽셀 결과를 전부 재실행하라는 제안이 아니다. 기존 결과를 보존하면서 과거 기준도 추적할 입력 연결이 필요하다는 지적이다.

**캐시 반례.** ADR A§7은 동일 `(case_id, kind, input_fingerprint, force_rerun=false)`에 한정한다. 현행 JobExecution §9-6의 조건으로는 다음 두 발주가 구분되지 않는다.

```text
기존: case=A, kind=SEARCH_COARSE, fingerprint=h, SUCCEEDED
신규: case=B, kind=SEARCH_COARSE, fingerprint=h, force_rerun=false
```

ADR 기준은 다른 case라 cache hit가 아니다. 현행 축약 문장만 구현하면 hit다. 같은 case의 다른 kind도 같은 종류의 반례다. ADR A§2의 fingerprint 설명은 AnalysisScope 정규화값+활성 구현 이름표이므로 case_id와 kind가 자동 포함된다고 가정할 수 없다. 데이터 유출이 실제 발생했다는 주장은 아니며, 재사용 조건의 계약 누락을 입증하는 반례다.

### 3.5 enum·소유권·제품 불변 경계 직접 대조

| 값 공간 | 현행 값/의미 | 재검증 결과 |
|---|---|---|
| Observation.status | OK / NEEDS_REVIEW / UNKNOWN / ERROR / NOT_APPLICABLE | 공통 관찰 상태. info_state와 같은 enum으로 합치는 현행 규칙 없음 |
| CaseView.info_state | INFO_AI_ESTIMATED / INFO_SOURCE_VERIFIED / INFO_USER_CONFIRMED / INFO_NEEDS_REVIEW / INFO_UNKNOWN | 값은 flow 5종과 대응. 생산 함수 입력이 부족(B01) |
| AnalysisRun·ReadoutRun.outcome | SUCCEEDED / PARTIAL / FAILED | 논리 실행 결과. runtime lifecycle과 구분됨 |
| RequirementReport.overall·checks.outcome | PASS / WARN / BLOCK / UNKNOWN | ERROR는 engine 실패 시 report 미생성. CaseView.readiness 값 공간은 일치하지만 어떤 report인지 문제(B02) |
| CaseView.progress.state | PENDING / RUNNING / DONE / FAILED | JobExecution 5값에서의 mapping은 문서끼리 일치 |
| JobExecution.status | QUEUED / RUNNING / SUCCEEDED / FAILED / STALE | CANCELLED 없음. domain PARTIAL의 결과를 runtime 성공/실패 어느 쪽으로 연결할지는 fixture에서 명시 필요 |
| PlateReadout.target_association.status | ASSOCIATED / LOW_CONFIDENCE / AMBIGUOUS / FAILED / NOT_PROVIDED | VisualEvidence의 MATCHED 등과 동일 enum으로 복사하는 계약이 아니다. readout이 자기 판독 대상의 association을 다시 기록한다. track_ref 부재만으로 판독을 막는 규칙은 없음 |
| SpanResolution.status | COMPLETE / PARTIAL / FAILED | 값 공간은 명시. 부분 범위의 완전성은 값 이름만으로 보증 안 됨(B06) |
| user_corrected / user_edited / user_reviewed / USER_REVIEWED | 필드 실제 correction 반영 / record 단위 수정 / 사용자 최종 검토 / workflow 개념 | 서로 다른 의미로 구분한 것은 타당. §10-8이 needs_review의 입력까지 정의한 것은 아님 |
| VIDEO_OVERLAY_OCR / OVERLAY_TIME_OCR | 출처 / Need 종류 | 다른 값 공간의 이름 차이 자체는 충돌 아님. 축 D의 '다른 개념에 같은 이름=무조건 BLOCK'도 과도 |

완료된 logical run의 PARTIAL은 usable 결과를 보존할 수 있는 반면 JobExecution §9-3은 SUCCEEDED만 produced를 유효하게 취급한다. 이를 'runtime는 SUCCEEDED, domain은 PARTIAL'로 연결하면 양립할 수 있다. 따라서 값 이름이 다르다는 이유로 별도 확정 충돌 건수를 만들지는 않았다. 다만 그 mapping을 통합 fixture 없이 저절로 일치한다고 볼 수도 없다.

Product Spec §7의 **8개 항목 모두**를 다음과 같이 대조했다. 필드가 없다는 이유만으로 사용자 행동·파일 보존이 보증된다고 판정하지 않았다.

| 제품 불변 경계 | 계약 대응/확인 | 한계 |
|---|---|---|
| 중요한 Evidence를 근거와 확인·수정 가능 | VisualEvidence §3·§6의 input/support ref, PlateReadout frame 근거, EvidenceRecord §3 provenance, CorrectionRecord | 화면으로 전달할 자료의 연결·projection B01/B03/B07 확인 필요 |
| 불확실한 번호판·시각·위치에 값 생성 금지·출처/상태 표시 | Observation §5, plate abstain, TimeResolution §3·§4, EvidenceRecord §4.2·§5 | 상태 표현은 존재. CaseView의 실제 표시 규칙은 B01 |
| 제출은 사용자 | ReportPackage §1·§7 handoff, CaseView user_reviewed | SUBMITTED enum 부재만으로 자동 제출이 없음을 증명할 수 없음. 실행 코드/행위 검증 미실시 |
| 자체 지도 UI 제외·최종 핀은 사용자 | EvidenceRecord §5 위치 단서, ReportPackage handoff | 계약이 자체 지도 구현을 요구하지 않음. UI 실행 확인은 범위 밖 |
| 얼굴 모자이크를 필수 Must로 확정하지 않음 | 계약 14개에서 필수 얼굴 모자이크를 선언한 규칙 발견 못함 | 필드 부재는 현재 규칙에 강제가 없다는 뜻까지 |
| Source video 덮어쓰기 금지 | recording §12·§23의 원본/파생 경계, ReportPackage의 파생 자산 | immutable 레코드만으로 실제 파일 무변형을 보증하지 못함. Trajectory ⑦ checksum/mtime 실측 필요 |
| 운전 중 조작 필수 아님·사후 자연어 단서 시작 | AnalysisScope hint, CaseView hints | 입력 경계는 지원. relative-only 영상 시각 입력은 B08 |
| 익명화·평가/학습 재사용 동의 구분 | CorrectionRecord §2·§8, correction-log-reuse.md의 두 단계·익명화 3줄 | 원본 CorrectionRecord에 원값이 있는 것은 위반 아님. 익명화 export·동의 저장/철회는 미결이며 실측 없음 |

### 3.6 경계 스크립트의 보장 범위를 반증한 검사

원본 파일을 수정하지 않고 `runpy`로 읽은 스크립트의 `read()` 반환값만 메모리에서 바꿔 검사했다. 이를 실제 저장소 수정이나 추가 테스트 파일로 남기지 않았다.

| 실행 | 결과 | 의미 |
|---|---|---|
| 원본 `python scripts/check_boundaries.py` | exit 0, PASS, NOTE 12개 | 현행 스크립트 기준 결과 재현 |
| 7개 BOUNDARIES 경로의 walk_code 대상 계수 | 총 0파일 | 경계 문자열 검사는 빈 입력에 대해 통과 |
| 계약 검사 원본 호출 | fail 0 | 현재 기준선 |
| VisualEvidence의 실제 SIGNAL 토큰 1곳을 SIGNAL_TYPO로 메모리 교체 | fail 0 | enum 검사는 허용 집합 전체 검증이 아니라 LANE_CHANGE 변형만 탐지 |
| AnalysisScope Architecture 포인터 ④를 ①로 메모리 교체 | fail 0 | 올바른 행인지 검사하지 않고 동그라미 숫자의 존재만 검사 |
| CorrectionRecord 파일 본문을 메모리에서 빈 문자열로 대체하고 **coverage 함수만** 실행 | coverage fail 0 | CIRCLED가 ①~⑫만 포함하여 v4⑬을 순회하지 않음. 전체 헤더 검사까지 통과했다는 뜻은 아님 |

추가로 직접 읽어 확인한 누락은 다음과 같다.

- `REQUIRED_HEADERS`는 Status/Architecture Contract/Contract Version **3개**다. 계획의 Accepted/Related ADR 검사가 아니다. 첫 1,500자만 확인한다.
- `check_no_renumber`는 번호가 있는 **제목 줄**만 실패시킨다. 본문 표·산문의 옛 Contract④/⑥-A/B는 남는다.
- `check_coverage`는 '언급+제목'을 본다. AnalysisSource는 recording 계약의 Storage/AnalysisSource 경계 제목 때문에 전용 스키마가 없어도 NOTE에서 빠진다. FrameRef는 v4 §5-1 타입 추출 대상이 아니어서 5NOTE가 누락 타입의 총수가 아니다.
- `check_adr_pairs`는 같은 slug의 파일 존재만 본다. ADR Status·본문·수락 조건과 계약 내용의 일치는 검사하지 않는다.
- `ownership.md:§6`에 적힌 금지 문자열은 BOUNDARIES 목록에 구현돼 있다. 하지만 주석/문자열도 잡는 substring 검사이고 alias/re-export/dynamic import 등 실제 의존 그래프는 분석하지 않는다. 지정 경로 밖의 코드는 대상이 아니다.
- JSON의 필수/nullable/enum/ContractRef 구조, 결과-run 연결, 요청 구간 coverage, 캐시 tuple, 최신 report 선택, 링크 존재는 검사하지 않는다.

따라서 문서 헤더 일부와 알려진 enum 오타의 재발 방지에는 유효하다. **전수 의미 검증이 유효하다는 의미의 PASS는 아니다.** 계획 §8-A는 7+5NOTE를 정확히 적었지만 §0-B의 '남은 NOTE는 5개뿐'과는 다르다.

## 4. 다음 일정 리스크

### 4.1 목데이터 1차 통합 통과 기준 6개

여기서 '조건부'는 실행 PASS가 아니라 **어떤 추가 합의·증거가 있으면 검증을 시작할 수 있는가**를 뜻한다. 현재 src 모듈 구현이나 완성된 통합 테스트를 실행한 것이 아니다.

| # | `ownership.md` §7-④ 기준 | 현재 계약으로 검증 가능한 것 | 막히거나 다르게 구현할 지점 | 판정·필요한 최소 조치 |
|---|---|---|---|---|
| ① | 사용자 수정 → 필요한 JobIntent만 재발주 | v4 §7-4가 번호판 수정/재판독/시간 단서/후보 교체 등 재실행·보존 경로를 구분. CorrectionRecord.kind 8종과 JobRecord 식별 필드는 존재 | CorrectionRecord.target_field/전후 값 타입/현재 수정 선택이 미결. 캐시 namespace B10, 실행 produced B04가 틀리면 발주는 맞아도 다른 결과를 재사용. 구체 invalidation matrix는 v4가 후속 계약/Tech Spec으로 남김 | **조건부.** case가 최소 수정 시나리오별 입력→발주 kind→보존 결과 fixture를 확정하고 runtime과 B04/B10을 맞춰야 함 |
| ② | 번호판 abstain에도 선택 사건·나머지 값 유지 | plate §3·§5는 abstain을 전체 실패와 구분. EvidenceRecord는 확정되지 않은 번호판을 부재/null로 둘 수 있음. case 소유 Selection과 다른 Evidence는 분리 | readout 결과-run 연결 B03, INFO_UNKNOWN/needs_review의 표시 충돌 B01. abstain을 Run FAILED로 만드는 구현과 정상적인 보류로 만드는 구현을 구분해야 함 | **조건부, 가장 먼저 fixture화 가능.** 선택 사건·시각·위치는 고정하고 번호판만 보류인 before/after를 대조. 여기에 Unknown 번호판의 실제 제출 허용 정책까지 확정됐다고 덧붙이지 말 것 |
| ③ | 시각 충돌 보존·non-blocking notice·Need→JobIntent | TimeResolution §4·§11은 resolved+conflict 공존, fallback provenance와 사용자 안내를 보존. EvidenceNeeds §8.5는 current revision의 nonoptional Need 자동 발주를 허용. notices에 blocking 필드 있음 | TimeResolution→event_time_display가 공통 EvidenceValue 형태가 아님(B01). USER_INPUT 값 형태는 Draft이며 현재 유효 correction 규칙 미결. notice/Need context와 현재 selection 연결 fixture 필요 | **조건부.** filename/metadata 충돌, 검증 overlay 없음, 사용자 사건시각 수정의 세 입력을 time_resolve와 CaseView까지 연결해 확인 |
| ④ | EVIDENCE_SUFFICIENT → PACKAGE_READY → USER_REVIEWED를 CaseView에서 구분 | READY=PACKAGE_READY와 user_reviewed 별도 boolean은 Owner 회신으로 명시. readiness도 overall 4값과 일치 | 단일 requirements가 EVIDENCE gate를 가리고 stale FINAL_PACKAGE를 선택할 수 있음(B02). 실제 evidence의 final 자산 metadata가 없음(B07) | **현재 계약만으로 통과 불가.** current basis별 두 gate와 사용자 검토를 함께 구분할 projection을 case/evidence/web이 합의하고 PASS/BLOCK 혼합·새 revision·Package 없음 케이스 검증 |
| ⑤ | eval이 fake search를 채점해 결과 파일 생성 | AnalysisScope fixture Producer=eval, AnalysisRun/CandidateEvent와 rank/span/usage_summary가 있음. 법적 판단 없이 후보 평가 입력을 만들 수 있음 | 본문 eval Consumer 오기는 W01. relative input B08과 timeline provenance B09는 해당 시나리오의 해석을 갈라 놓음. 계약만으로 eval 실행기·정답 manifest·결과 파일이 실제 존재했다고 할 수 없음 | **설계상 제한된 fixture는 가능, 실행 결과는 확인 불가.** absolute anchor가 있는 고정 입력부터 실제 fake search 호출·정답·결과 파일을 남길 것. 현재 감사의 PASS로 대체하지 말 것 |
| ⑥ | Tool Trajectory Review 1회차 실시 | `tool-trajectory-review.md`에 담당자·7개 판정·기록 표가 있음 | §4의 두 회차 표가 비어 있음. ⑦의 원본 checksum/mtime, ⑤의 실제 report provenance, ⑥의 gate→package 순서는 opaque ID 샘플만으로 확인할 수 없음 | **미실시/실적 확인 불가.** 통합 실행에서 나온 발주·판독·요건·파생 파일 증거로 유소연이 1회차 기록을 작성해야 함 |

통합 목적은 **실제 AI는 없지만 evidence는 실제 코드**다. 자산 정책 결과까지 하드코딩한 화면 Mock은 유용할 수 있으나 `ownership.md:§7-④`가 정한 동일한 검증은 아니다. 이에 따라 'ref만 맞추면 언제든 전체 통합 가능'이라는 주장은 받아들이지 않았다.

### 4.2 담당자별로 필요한 최소 합의

다음은 수정 지시를 실행한 것이 아니라 보고서상 제안이다. 내부 모델·OCR 알고리즘·저장소 운영 수치를 이번 감사가 대신 정하지 않는다.

| 담당 경계 | 먼저 합의할 최소 내용 | 종료를 판단할 증거 |
|---|---|---|
| case ↔ evidence ↔ web | display별 value/source/user_corrected/needs_review 입력, 시각·위치 adapter, report 현재 basis와 세 gate projection | null·추정·관찰·사용자 수정·충돌, evidence PASS/package BLOCK, 새 correction 후 옛 report의 fixture에서 같은 결과 |
| common/runtime ↔ case | produced ContractRef 모양, cache namespace, domain PARTIAL과 execution status 연결 | 다른 case/kind는 reuse하지 않고 같은 허용 입력만 reuse, PARTIAL 결과 보존 여부가 명시된 fixture |
| readout ↔ case/eval ↔ runtime | readout 결과→run_id, Observation.run_ref, UsageRecord의 ReadoutRun 연결 | 성공/abstain/결과 없는 실패 세 가지에 대해 run 수·결과 수·usage가 역추적됨 |
| recording ↔ search/evidence/case | 최소 파일/stream/frame/파생 자산 사실과 lookup 또는 입력 주입 표면, span coverage, relative 입력·사용 revision 연결 | opaque ID 안을 해석하지 않고 현재/과거 revision 및 final package 판정에 필요한 사실을 얻는 fixture |
| case ↔ evidence | CorrectionRecord의 통합에 필요한 kind별 전후 값, target_field와 현재값 선택 | 사건시각 수정이 correction_record까지 추적되고 TIME_HINT_EDIT가 최종시각으로 승격되지 않음 |
| PM ↔ 정철원·해당 Owner | C1-6의 추가 순서, C1-13의 실제 수락 시점, R-7의 case 스키마 결정 | 제안·통보·수락의 상태를 구분한 원문 또는 결정 기록 |

recording의 upload 전략·provider별 delete·proxy 수치·retention 일수 전체를 확정해야만 개별 fixture를 시작할 수 있다는 주장은 하지 않는다. 반대로 현재 evidence 함수가 실제로 읽어야 하는 자산 사실까지 'recording 내부 필드'로 제외할 수는 없다. **필요한 입력 표면을 최소화하는 것과 입력이 필요 없다고 선언하는 것은 다르다.**

## 5. 확인하지 못한 것

요청된 첨부를 secret이라는 이유로 생략한 항목은 없다. 아래는 자료가 실제로 없거나 독립 근거가 충분하지 않은 항목이다.

| 항목 | 확인 불가 — 필요한 자료 | 현재 판단에 미친 영향 |
|---|---|---|
| C1-1의 과거 정확한 수정 3곳/1곳, C1-7 최초 누락 후 보완 등 | 계약·ADR의 보정 전 snapshot 또는 당시 export. 81e5539 이전 git에는 이 파일들이 없음 | 현재 내용·고지는 확인, 정확한 과거 변경 횟수/순서는 확정하지 않음 |
| Pass 1~3이 주장한 당시 전수 실행 | 당시 파일 집합·hash, grep 원출력, enum/coverage 대조표 | 현재 검사를 재실행했으나 과거 실행 로그를 대신하지 않음 |
| 2026-09-04 백엔드 회의의 실제 참석자·확정 범위 | 독립 회의록·녹취·담당자 답변. 현재 ADR 재서술만 발견 | 정철원 배정을 거짓이라 단정하지 않음. PM 추가 순서는 본문 자체로 구분됨 |
| C1-13의 세 Accepted 날짜·판본 | 각 원본의 수락 일시와 버전, 특히 AnalysisScope 09-04와 09-05 closure의 관계 | Status 종결 근거와 수락일을 분리. 날짜 공통 추정을 승인하지 않음 |
| Final v1.1 작성자의 삭제/재오픈 의도 | ADR §7이 기다린다는 작성자 확인 회신 | 정당한 설계 결정을 버린 것이 '없다'거나 '있다'고 확정하지 않음. 12건 일괄 베이스 착오 판정은 보류 |
| 노션의 당시 canonical 접근 가능성·PM closure 고지 여부 | 당시 노션 페이지 이력/권한·발송 기록 | 로컬 공지 초안과 실제 발송/열람을 동일시하지 않음 |
| JobExecution·UsageRecord 소비자가 알고 이의 없었던 기간 | 통보된 실제 문서 버전·발송/수신 또는 소비자 확인 | 생산자 작성 권한은 확인했지만 무응답을 수락으로 증명하지 않음 |
| CALL-2의 독립 수신 원문 | 현재 카드·공지에 답변이 기록돼 있으나 별도 피드백 export는 없음 | (a) 기록을 근거로 현행 경로 확인. 독립 발송·수신 실적을 증명하지 않음 |
| recording 계약 2건의 실제 schema | `contract-source-asset-media-stream.md`, `contract-analysis-source-derived.md` | 의도적 미작성으로 구분. broken file을 우연한 삭제로 판정하지 않음 |
| Fine input exact schema·stream_selector 입력 | respective Owner의 public capability 계약. visual/recording ADR §13도 이를 후속 항목으로 남김 | output-only fixture 가능성과 완전한 호출 통합을 구분 |
| CorrectionRecord 정식 Consumer Review | evidence 리뷰 및 합의된 값/선택 규칙 | Draft가 정당하며 그 사실을 미해결 0건으로 덮지 않음 |
| readout taxonomy/eval 수락·Abstention Recall 산출 | Owner 확정 taxonomy, eval 집계·정답 라벨/실제 결과 | run 분모 존재만으로 지표 완성 주장하지 않음 |
| Mock Pack·통합 실행·Trajectory 1회차 | 실제 fixture 묶음/실행 명령/결과 파일/판정 기록 | 이번 보고서는 계약 감사이며 실행 PASS를 만들지 않음 |
| 원본 영상 실제 무변형·제출 사용자 수행 | 파일 checksum/mtime 전후, 실제 handoff 실행 기록 | 계약의 금지 선언까지만 확인 |
| GitHub Actions 서버의 이번 커밋 결과 | 원격 workflow run | workflow 내용·로컬 실행만 확인. CI 서버 PASS로 표현하지 않음 |

CALL-3 파일은 찾지 못했지만 계획이 **호출 없이 종결**했다고 설명하므로 재첨부를 요구할 빠진 카드로 세지 않았다. CALL-7은 존재하되 발송하지 않았다고 명시돼 있다. '카드 7장 모두와 회신'이 있는 상태라는 전제 자체를 정정해야 한다.

## 6. 검토 범위

### 6.1 읽은 문서

**규칙·판정 기록 — 전문**

- `CLAUDE.md`, `docs/README.md`
- `docs/architecture/contracts/README.md`, `docs/architecture/contracts/adr/README.md`
- `docs/architecture/contracts/adr/adr-consistency-2026-09.md`
- `docs/management/secret/데이터-계약-정합성-검수-계획.md` — 착수 결정·9축·Pass 결과·F-1~29·카드·V-1~7·제외 범위 포함
- `docs/architecture/mock-pack-v1-refs.md`

**상위 정답지 — 지정 절 중심**

- `docs/product/product-spec.md`: §5 Must/Won't, §6 유형 범위, §7 불변 경계
- `docs/product/core-user-flow.md`: §3-1, §9, §12~§14, §19, §23. 확정 문장과 `[프로토타입]` 가정은 구분했다
- `docs/architecture/module-architecture.md`: 개정 이력, §2, §3(3-5·3-6 포함), §5-1~§5-4, §4-모듈3③, §4-모듈5④⑤⑥, §11-1·§11-4, §12 RT8·RT9. 통합 기준이 직접 가리키는 **§7-4 부분 재실행 표**는 좁게 추가 확인했다. 문서 전체를 읽지 않았다
- `docs/management/ownership.md`: §1-1, §5, §6, §7-③·④. C1-5·C1-6 확인을 위해 §3의 해당 역할 문장 및 커밋 diff도 확인

**계약 14건 — 모든 헤더 및 본문**

1. `contract-job-record-case-view.md`
2. `contract-correction-record.md`
3. `contract-readout-run.md`
4. `contract-job-execution.md`
5. `contract-usage-record.md`
6. `contract-evidence-record-needs.md`
7. `contract-requirement-report-package.md`
8. `contract-plate-overlay-readout.md`
9. `contract-visual-evidence.md`
10. `contract-analysis-scope.md`
11. `contract-observation.md`
12. `contract-time-resolution.md`
13. `contract-analysis-run-candidate-event.md`
14. `contract-recording-timeline-asset-span.md`

**ADR 15건 — 전부 헤더 확인, 본문은 아래 범위**

전문: `adr-consistency-2026-09.md`, `adr-job-record-case-view.md`, `adr-analysis-scope.md`, `adr-observation.md`, `adr-plate-overlay-readout.md`, `adr-time-resolution.md`, `adr-requirement-report-package.md`, `adr-job-execution.md`, `adr-usage-record.md`, `adr-correction-record.md`, `adr-readout-run.md`.

긴 ADR은 헤더·목차·관련 결정 및 불변조건을 중심으로 읽었다. `adr-visual-evidence.md`는 Status 고지, 최종 결정·Consumer 반영·핵심 계약·invariants·변경 규칙·미해결; `adr-analysis-run-candidate-event.md`는 canonical span 결정, review 근거, invariants 및 관련 접합 설명; `adr-recording-timeline-asset-span.md`는 timeline/revision·SpanResolution·storage/AnalysisSource 결정, invariants, 미해결; `adr-evidence-record-needs.md`는 헤더와 결정·review·상태/원천 책임의 관련 문맥을 확인했다. 이 네 ADR의 긴 대안·진단 설명을 전부 정독했다고 주장하지 않는다.

**호출 카드 — 현존 6개 전문 + 공지문**

- `docs/management/secret/calls/CALL-1-CaseView-정보상태-출처-필드.md`
- `docs/management/secret/calls/CALL-2-PlateReadout-소비-경로.md`
- `docs/management/secret/calls/CALL-4-recording-자산계층-계약-공백.md`
- `docs/management/secret/calls/CALL-5-case-소유-계약-미결-4건.md`
- `docs/management/secret/calls/CALL-6-ReadoutRun-계약-없음.md`
- `docs/management/secret/calls/CALL-7-CaseView-requirements-scope.md`
- `docs/management/secret/calls/_공지-및-호출-문구.md`

**담당자 회신 — 현존 6개 전문**

아래는 모두 `docs/management/secret/CALL 관련 피드백/`에 있다.

- `Final Data Contract v1 1 — 부록-A JobRecord + 부록-B C 3d27ae78fc6a801c9bb8c3ef68dcae3a.md`
- `CorrectionRecord - Data Contract 3d27ae78fc6a80948a75f49f0a8d0819.md`
- `CALL-1 CaseView 3d27ae78fc6a80628345f6f6faf37901.md`
- `CALL-5 case 소유 계약 3d27ae78fc6a8096b71dfc5e93a48b44.md`
- `CALL-6 — ReadoutRun 계약이 없어서 readout 실패 통계를 집계할 수 없 3d27ae78fc6a80159579d6fe0217ad22.md`
- `정철원 — recording CALL-4 피드백 3d27ae78fc6a8020ab15f45635ae15b7.md`

**관련 결정·검사 구현**

- `docs/management/cross-cutting-decisions.md`
- `docs/management/tool-trajectory-review.md`
- `docs/modules/readout/decisions/failure-taxonomy.md`
- `docs/modules/case/decisions/correction-log-reuse.md`
- `scripts/check_boundaries.py` 전체 및 `scripts/README.md`의 검사 안내
- `.github/workflows/boundary-check.yml` 전체

### 6.2 실행·재검증 기록

```text
git status --short
git rev-parse HEAD
git log --oneline -5
git show --stat 622a869
git show --stat 81e5539
git show 81e5539 -- docs/architecture/module-architecture.md docs/management/ownership.md
python scripts/check_boundaries.py
```

추가로 `rg`·파일 목록 및 읽기 전용 Python을 이용해 다음을 수행했다.

- 14계약/15ADR 파일 수 및 Status 집계, 헤더 4요소 누락 확인
- 계약 14건의 Producer/Consumer/Owner, circled 번호·미결·enum·자산 타입/ref·needs_review 출현 검색과 해당 문맥 대조
- 계약의 JSON 예시 파싱, JobExecution.produced 원소 타입, 두 판독 결과의 run_id 존재 확인
- recording §8.1의 JSON을 파싱하고 usable/missing 구간의 합집합으로 미설명 10초 계산
- CaseView의 5단계 상태 규칙을 그대로 함수화해 분기 표본 실행
- 스크립트가 순회하는 코드 파일 수 계수 및 §3.6의 **메모리에서만 바꾼 3개 반증 검사**
- 비archive 파일에서 회의록·관련 배정 근거 위치 검색, 호출 카드/회신 실물 수 확인

검사 예시의 잘못된 enum mutation은 실제로 **SIGNAL 토큰 1곳이 바뀐 것을 확인**한 결과를 보고했다. 파일에 존재하지 않는 문자열을 치환한 결과는 증거로 사용하지 않았다. coverage의 CorrectionRecord 제거 반례는 coverage 함수만의 결과이며 전체 검사 결과로 확대하지 않았다.

`git log --oneline -5`에서 확인한 커밋은 `81e5539`, `622a869`, `5cf4d75`, `4f643b6`, `cffc2fe`다. 622a869는 검사 스크립트·workflow 도입, 81e5539는 이번 문서 작업의 최종 추적 상태다.

### 6.3 git 이력의 제약과 읽지 않은 범위

**계약 14건과 ADR 15건은 81e5539에서 처음 추적됐다.** 따라서 `git diff`로 계약의 PM 보정 전 판본을 복원할 수 없다. '변경이 파일에 현재 있다'는 검증에는 현행 파일을, '담당자가 무엇을 답했다'에는 secret 원본을, '과거 무엇을 어떻게 고쳤다'에는 검수 계획/ADR의 주장과 확인 가능한 상위 문서 diff를 사용했다. 주장 기록만으로 그 주장 자체를 입증하지 않았다.

`docs/archive/`는 현재 기준으로 사용하지 않았으며 본문을 근거로 읽지 않았다. `docs/design/`, modules 연구자료, 배포/인증 구현, 실제 AI 성능, 외부 제출 서비스 동작은 이번 계약 감사 범위 밖이다. 외부 노션 링크의 현재 페이지나 과거 접근 권한은 조회하지 않았고 로컬 원본과 구분했다. 데이터 계약이 인용하는 과거 v1/v3 문서의 역사적 사실도 archive를 열어 보충하지 않았다.

이 보고서의 반례는 **현재 계약으로 서로 다른 구현이 가능한 이유**를 제시한다. 코드가 없는 상태에서 실제 제품이 오류를 일으켰다거나 성능·개인정보 사고가 발생했다고 주장하지 않는다. 종결을 위해서는 해당 Owner의 결정과 그 결정을 사용한 최소 통합 fixture의 실행 증거가 필요하다.

작성 후 확인: 보고서의 필수 §0~§6, 주장 35개, C1 13개, V 7개, 지적 ID 22개 및 표 열 수를 점검했다. 감사 시작 시 수집한 원본 132개 hash와 종료 시 파일을 대조했으며, 새로 추가한 것은 이 보고서 1개다. 기존 파일 중 달라진 것은 작업 중 사용자가 범위를 갱신한 `외부검수-프롬프트.md`뿐이고, 검수 대상 계약·ADR·상위 문서·스크립트는 변경되지 않았다. `git status --short`는 비어 있으며 보고서는 기존 secret gitignore 규칙 아래에 있다.
