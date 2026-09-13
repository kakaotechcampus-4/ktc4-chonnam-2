# Tool Trajectory Review — 경로가 맞았는지 판정하는 절차

> **담당:** 유소연(`case`) · **Consulted:** 김준영(`evidence` — 규정 해석이 필요할 때만)
> **근거 결정:** `cross-cutting-decisions.md` C-3
> **판정자는 규칙을 해석하지 않는다.** `case`는 신고 요건 계산과 시각 출처 우선순위를 만지지 않는다. 판정자는 `evidence`가 내놓은 판정 값을 **확인만** 하고, 해석이 필요하면 `evidence` Owner에게 묻는다. 이 문장이 없으면 이 절차가 `case`의 소유권 규칙을 침범한다.

`pre-deploy-security-review.md`와 형제 문서다. 둘 다 한 모듈 안에서 닫히지 않는 cross-cutting review이고, 배포 전에 표 하나로 닫힌다.

## 1. 왜 결과 지표와 따로 보는가

AI 에이전트 제품 평가에는 서로 다른 두 질문이 있다.

- **결과가 맞았나(outcome)** — Top-3에 정답이 있나, 번호판이 맞나 → `eval`이 채점한다.
- **거쳐온 경로가 맞았나(trajectory)** — 정답을 **맞는 방법으로** 얻었나 → 이 문서.

에이전트는 틀린 경로로 맞는 답을 낼 수 있다.

| 틀린 경로 | 겉으로 보이는 결과 | 실제 상태 |
| --- | --- | --- |
| Fine 검증을 건너뛰고 Coarse만 보고 「신호위반」을 확정했는데 마침 맞았다 | 점수 100점 | 다음 영상에서는 틀린 유형이 나간다 |
| GPS가 없는데 주소를 생성했는데 우연히 맞았다 | 위치 정확 | 다음 사용자에게 틀린 주소가 나간다 |
| 사용자가 「조금 뒤」 하나를 눌렀는데 파이프라인 전체를 재실행했다 | 결과 동일 | 비용·시간이 몇 배 |

이 축이 비어 있으면 **결과 지표만 좋고 경로가 틀린 상태**를 데모 직전까지 아무도 못 잡는다.

`eval`이 이 판정을 맡을 수 없는 이유: `eval`은 `case`·`evidence`를 몰라야 한다(`module-architecture.md` §6-1). 「필요한 단계만 재실행했는가」는 `case`를 알아야 판정할 수 있다.

## 2. 판정 7줄

| # | 판정 항목 | 무엇을 보나 | 근거가 어디 있나 | 실패하면 무슨 뜻인가 |
| --- | --- | --- | --- | --- |
| ① | 필요한 단계만 재실행했는가 | 사용자 수정 1건에 발주된 Job 목록 | `case`의 부분 재실행 정책 표 (`module-architecture.md` §7-4 · `modules/case/decisions/`) ↔ 실제 `JobRecord` | 정책 표와 발주가 어긋남. 비용 누수 또는 stale 결과 |
| ② | Fine을 건너뛰고 법적 유형을 확정하지 않았는가 | 선택된 후보의 `VisualEvidence`가 존재하는가 | `search.verify_visual` 실행 기록(`AnalysisRun`) | Coarse 점수만으로 유형이 나갔다. 「AI가 법적 위반을 최종 확정하지 않는다」 위반 |
| ③ | 번호판에 target · detection · frame 근거가 연결됐고, 불확실하면 포기했는가 | `PlateReadout`의 association·detection·frame_results·abstained | `readout` 출력 | 근거 없는 번호판 문자열. 「값을 만들어내지 않는다」 위반 |
| ④ | GPS 없을 때 주소를 생성하지 않았는가 | GPS `UNKNOWN`인 case의 위치 값 출처 | `recording` GPS 관찰 → `EvidenceRecord.location` | 사용자 단서가 아닌 값이 위치에 들어갔다 |
| ⑤ | 시각의 출처(provenance)가 보존됐고 사후각인 표시가 있었는가 | `TimeResolution.considered[]`·`post_stamp`, Report Video의 provenance | `evidence` 출력 · `recording.export_report_video` | 어디서 온 시각인지 모른다. 사후각인 영상이 원본 화면 시각처럼 보인다 |
| ⑥ | Evidence Rule을 실제 통과했는가 | `RequirementReport`의 PASS/WARN/BLOCK이 Package 생성 전에 계산됐는가 | `evidence.check_requirements` → `PACKAGE_READY` 순서 | 요건 검사 없이 자료가 나갔다 |
| ⑦ | 원본 영상을 덮어쓰지 않았는가 | `ExternalSourceRef`의 체크섬·mtime 전후 비교 | `recording` 원본 무변형 검증 | 제품 불변 경계 「Source video를 덮어쓰지 않는다」 위반 |

②·③·④·⑤·⑥은 `evidence` 규칙과 얽힌다. **판정자는 각 값이 있는지·순서가 맞는지만 본다.** 값이 규칙상 맞는지는 `evidence`의 unit test가 본다.

## 3. 언제 판정하는가

| 회차 | 시점 | 이유 |
| --- | --- | --- |
| 1 | 목데이터 1차 통합 (`ownership.md` §7-④) | 실제 AI 없이 계약이 맞물리는지 보는 시점. 경로는 이때 처음 전체가 돈다 |
| 2 | 데모 직전 | 실제 구현으로 교체된 뒤 경로가 그대로인지 |

주간은 과하다. 위 두 번 외에는 `search`·`readout` 구현이 교체됐을 때 Owner 요청으로 추가한다.

**자동화하지 않는다.** 수동 확인. 나중에 여유가 생기면 ①·②는 `case`의 `JobRecord`로 자동 판정으로 옮길 수 있다(§5).

## 4. 판정 기록

| 회차 | 날짜 | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ | 판정 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | | | |
| 2 | | | | | | | | | | |

판정 어휘는 `pre-deploy-security-review.md`와 같다 — **PASS / WARN / BLOCK**. BLOCK은 ②·③·④·⑦(사용자에게 틀린 값이 나가거나 원본이 손상되는 것). ①·⑤·⑥은 WARN으로 기록하고 진행할 수 있다.

## 5. 나중에 자동화할 수 있는 것

- **①** — `JobRecord`에 `case_rev`·`kind`·`input_fingerprint`가 있으므로, 수정 1건 → 발주 Job 집합을 정책 표와 대조하는 테스트로 바꿀 수 있다.
- **②** — 선택된 후보마다 `VisualEvidence`가 있는지는 `case` 상태 전이 조건으로 강제할 수 있다.
- ③~⑦은 값의 존재 확인이라 unit test로 옮길 수 있으나, 「사후각인 표시가 사용자에게 보였는가」(⑤)는 사람이 봐야 한다.
