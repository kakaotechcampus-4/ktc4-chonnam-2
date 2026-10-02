# case Orchestration 지표 — 1차 측정 (2026-09-30) · 4차까지 (2026-10-02)

> W7 고도화 7순위(`design-refinement-w7-baseline.md`). 러너 `scripts/measure_case_orchestration.py`.
> 이 문서는 설정 · 요약 결과 · 판단 근거만 담는다. 세션별 raw 결과는 git에 올리지 않았다(PR #146 멘토 피드백 — 실험 산출물은 git 밖).

## 무엇을 재는가

LLM·OCR 평가는 「AI가 내용을 잘 뽑았는가」만 잰다. 이 지표는 **case가 일을 제대로 시켰는가**를 따로 잰다 — 결과가 틀렸을 때 AI 잘못인지 orchestration 잘못인지 가르기 위해서다.

| 지표 | 한 번의 판정 | 기준 |
| --- | --- | --- |
| ① 필요한 단계만 재실행 | 사용자 행동 1개 직후 실제로 호출된 단계 ⊆ 허용 단계 | `doc-research/부분 재실행 정책 표 초안 v1` |
| ② 잘못된 전이 0건 | 매 단계 뒤 불변식 | 아래 표 |
| ③ 불필요한 재실행 | 같은 단계가 같은 입력(같은 선택 context)으로 다시 호출된 횟수 | — |

「단계」는 JobRecord가 아니라 **함수 호출**로 센다(coarse_search · fine_verify · incident_clip · plate_ocr · overlay_ocr · assemble). #175가 고친 버그가 JobRecord 없이 함수 호출로 재실행된 것이었기 때문이다.

**② 불변식**

| # | 불변식 | 근거 |
| --- | --- | --- |
| I1 | `READY` ⇒ ReportPackage 존재 | #167 |
| I2 | `EVIDENCE_REVIEW` ⇒ 선택 후보 정확히 1개 | — |
| I3 | CaseView `evidence ≠ null` ⇒ 현재 선택 candidate·`selection_rev`의 것 | #191 |
| I4 | 허용된 stage 전이만 (직접 대입 경로 포함, 스냅샷으로 검사) | — |
| I5 | 거부된 행동 뒤 상태 불변 | #166 |
| I6 | `case_rev`: 사용자 요청마다 +1, 거부·무변경은 불변 | CaseView 계약 §3-E · correction-record §8-7 |
| I7 | `READY` ⇒ blocking notice 없음 | #212 리뷰 |

## 설정

- **경로:** fixture 기반 `RealAdapter`(`happy_001`) — 유료 호출 없음, 결정론적. evidence 체인은 happy만 돈다(다른 mock 시나리오는 recording real 서비스가 timeline을 모른다). 그래서 관찰 상태는 happy 바탕에 주입한다.
- **관찰 상태 4종:** 정상 조립 · 음성(Fine `NOT_OBSERVED`) · 번호판 판독 실행 실패(4a) · 판독은 됐지만 못 읽음(1·3)
- **사용자 행동 8종:** 번호판 직접 수정 · 신고 유형 변경 · 발생시각 직접 입력 · 무변경 입력 · 최종 검토 · 시간 단서 수정(→ 재탐색 · 자동 선택) · 없는 후보 재선택 · 현재 후보 재선택 (2차 측정에서 **다른 후보 선택**을 더해 9종 — 아래 「2차 측정」)
- **순서:** 길이 1~3의 모든 순서 = 8 + 8² + 8³ = 584 → × 관찰 4 = **2,336 세션**. 손으로 고르지 않고 조합에서 나온 수다.
- 반복 정정은 매번 다른 값을 넣는다(러너가 무변경 입력을 스스로 만들지 않게). 이전 값은 그 시점 evidence에 보이는 값이다.

## 결과

| | #175 이전 (`7714efaa`) | develop (`ae7cebe2`) | develop + 무변경 정정 수정 |
| --- | --- | --- | --- |
| 판정한 행동 | 4,753 | 4,923 | **5,934** |
| ① 위반 | **4,040** | 0 | **0** |
| ② 불변식 위반 | **3,774건** | 209건 | **0건** |
| ③ 불필요한 재실행 / 전체 호출 | **13,350 / 41,314** | 0 / 19,938 | **0 / 20,642** |
| 크래시 세션 | 951 | 837 | **370** |

실행 시간: 2,336 세션에 86~408초.

### 2차 측정 — 「다른 후보 선택」 축 추가

mock search fixture가 전부 후보 1개라 1차에는 거부되는 재선택만 돌았다. 러너 안에서 rank1을 복사한 rank2(`candidate_id`만 다르고 span 동일)를 search 결과에 넣고, Fine fixture의 `VisualEvidence.candidate_id`를 선택된 후보로 맞췄다(제품 코드 무수정). 행동에 `OTHER_CANDIDATE`(허용 단계: 1차 탐색을 뺀 전부 — 정책 표 2행, `case_rev` +1)를 더해 9 + 9² + 9³ = 819 → × 관찰 4 = **3,276 세션**.

| | 축 추가 · 수정 전 | 축 추가 · `RealAdapter` 수정 후 |
| --- | --- | --- |
| 판정한 행동 | 8,476 | 8,476 |
| ① 위반 | **994** (전부 `OTHER_CANDIDATE → coarse_search`) | **0** |
| ② 불변식 위반 | 0건 | 0건 |
| ③ 불필요한 재실행 / 전체 호출 | 0 / 32,940 | 0 / **27,676** |
| 크래시 세션 | 470 | 470 |

실행 시간: 3,276 세션에 184~278초. 크래시 470건은 모두 1차와 같은 번호판 직접 입력 계약 문제(아래 표)다.

- **찾은 것:** fixture 기반 `RealAdapter`는 evidence를 조립할 때마다(새 선택 context마다) 선택된 CandidateEvent를 찾으려고 `search.search_candidates(scope)`를 **다시 불렀다**. fixture에서는 조회지만 실제 search 서비스에서는 영상 전체 Coarse 재실행이다. `RealVideoAdapter`는 이미 `candidate_id`별로 캐시해 문제가 없었다 — 같은 원칙이라고 적혀 있었지만 `RealAdapter`만 달랐다.
- **수정:** `RealAdapter.get_candidate_events()`가 받은 CandidateEvent를 캐시하고 조립은 거기서 찾는다. 호출 5,264회가 빠졌다(첫 선택·재선택·재탐색 뒤 조립마다 한 번씩).
- **③이 못 잡은 이유:** ③은 같은 입력의 관찰 단계 중복만 세고 `coarse_search`는 뺀다(재탐색은 시간 단서가 바뀌면 필요하다). 이 버그는 ①(행동별 허용 단계)로만 보였다. 1차 측정도 첫 선택 뒤 조립의 재호출은 setup 단계라 판정하지 않았다.
- 이전 후보의 정정이 새 후보로 따라가는지(#173 E-1)·`multiple correction heads`(#188)는 「정정 → 다른 후보 → 같은 필드 정정」 조합을 포함해 크래시·위반 0이다.

### 3차 측정 — A→B→A 관찰 재사용 (`decisions/reselect-observation-reuse.md`)

2차까지 ③의 관찰 입력 키는 (선택 후보, `selection_rev`)라, 다른 후보를 골랐다가 돌아올 때(A→B→A) Fine·판독을 다시 도는 것을 위반으로 세지 않았다. 정책 표 2행 「2차 확인(필요시)」을 「같은 탐색 결과에서 그 후보의 관찰이 아직 없을 때」로 정하고(위 결정 문서), ③의 관찰 키를 (선택 후보, 탐색 결과 세대)로 바꿨다. 세대는 1차 탐색 호출 수로 센다. 조립 키는 그대로(선택 context·정정마다 다시 조립해야 한다).

| | 키 변경 · 수정 전 | 후보별 관찰 캐시 수정 후 |
| --- | --- | --- |
| ① 위반 | 0 | 0 |
| ② 불변식 위반 | 0 | 0 |
| ③ 불필요한 재실행 / 전체 호출 | **322** / 27,676 | **0** / 27,354 |
| 그중 Fine(실영상에서 유료) | 1,988회 중 100회 | 1,888회 |
| 크래시 세션 | 470 | 470 |

- 322 = Fine 100 + IncidentClip·번호판·시각 판독 각 74. Fine이 더 많은 것은 음성(`NOT_ASSEMBLED`) 세션이 Fine 뒤 관찰을 하지 않기 때문이다.
- 수정: `CaseAggregate.candidate_generation`(후보 목록 교체·역행 때만 오름, CaseView 비노출)을 두고, 두 adapter가 같은 세대 안에서 후보별로 관찰을 보관한다. 재탐색 뒤에는 같은 `candidate_id`라도 다시 관찰한다(정책 표 1행 — 기존 테스트 그대로 통과).

### 4차 측정 — 상황 응답 · 응답 대기 · 후보 0개 · 탐색 실패 · READY (2026-10-02)

#177·#203·#209가 머지돼 「측정하지 않은 칸」 넷을 열었다.

- **관찰 상태 +3 (7종):** 응답 대기(Fine `UNCERTAIN`) · 후보 0개(탐색 `SUCCEEDED` + 0건) · 탐색 실패(`FAILED`)
- **행동 +2 (11종):** 상황 응답 `CONFIRMED` · `USER_UNSURE`. 순서 길이 1~3 = 11 + 11² + 11³ = 1,463 × 관찰 7 = **10,241 세션**.
- **command 경로:** command 대상 행동(다른 후보 · 상황 응답 · 최종 검토)은 web이 실제로 부를 `handle_command`(#216)로 보낸다 — 성공 뒤 `READY` 재확인까지 같은 경로다. 정정(입력형)은 command 판본이 없어 domain을 그대로 부른다.
- **READY에 가려면:** real 경로 FINAL은 최종 신고영상 관찰(I4, `observation_facts`)이 없어 늘 `UNKNOWN`이다(ADR-EVIDENCE-008 §6.2 — producer가 없고 case 몫이 아니다). evidence mock 하니스가 쓰는 happy 값(`tests/evidence/fixtures/adapter_inputs.json`)을 **러너 안에서만** 넣었다(제품 코드 무수정). 그 결과 616 세션이 `READY`에 갔고(정상 조립 324 · 응답 대기 292), `READY`에서 판정한 행동이 561개다. **#202를 이 러너로 처음 검증했다.**
- **거부 기대값:** 「거부돼야 하는가」를 행동 직전 case로 판단하고, 기대 밖 거부(「허용돼야 하는데 거부」)와 모든 거부 뒤 상태 불변을 함께 본다. 값 정정은 `EVIDENCE_REVIEW`·`READY`에서만, 시간 단서 정정은 `CANDIDATE_REVIEW`·`EVIDENCE_REVIEW`·`READY`에서만 받는다(`doc-research/상태 기계 설계 초안 v1` §3·§4).

| | develop (`4d07d8cf`) | 이 PR |
| --- | --- | --- |
| 판정한 행동 | 28,207 | 28,207 |
| ① 위반 | 0 | 0 |
| ② 불변식 위반 | **4,122건** | **0건** |
| ③ 불필요한 재실행 / 전체 호출 | 0 / 61,824 | 0 / 61,874 |
| 크래시 세션 | 767 | 767 |

실행 시간: 10,241 세션에 368~690초.

develop의 ② 4,122건:

| 건수 | 무엇 | 처리 |
| --- | --- | --- |
| 3,088 (I5) | 후보 선택 전(후보 0개·탐색 실패) 값 정정이 거부되지 않고 기록 — `selection_rev`도 반영할 evidence도 없는 기록 | 상태 기계 설계 초안 §4대로 `EVIDENCE_REVIEW`·`READY`에서만 받는다 |
| 386 (I5) + 386 (I6) | 탐색 실패로 `SEARCHING`에 머문 case의 시간 단서 정정 — 역행은 거부되는데 정정 기록·`hints`·`case_rev`가 먼저 남음 | `check_regress_to_searching()`으로 먼저 검사(#166과 같은 원칙) |
| 144 (I1) | `READY`에서 시각 정정·상황 응답 변경으로 재조립하자 Package가 사라졌는데 `READY`로 남음 — CaseView 계약 §10-9 위반. #202는 오르는 쪽만 막았다 | 다시 조립되는 변경이 오면 `EVIDENCE_REVIEW`로 내리고, command 성공 뒤 재확인이 gate가 성립할 때만 다시 올린다. `user_reviewed`는 유지(계약 B절 · #173) |
| 118 (I6) | `READY`에서 받은 상황 응답의 `case_rev` — 위 규칙에서는 내렸다 다시 올라 +2가 기대값이다(case-command 계약 §5에 추가) | 위와 같은 수정 |

- ③ 전체 호출 +50은 `READY`에서 내려간 뒤 재조립이 한 번씩 더 도는 몫이다(조립만 — 관찰 재호출 0).
- 크래시 767은 수정 전후 같다 — 아래 「이번에 새로 찾은 것」 마지막 두 줄.

### 지표가 실제로 잡는가 (baseline)

baseline 커밋에서 **이미 고쳐진 버그 3건을 모두 검출**했다. 지표가 0을 낼 때 그 0을 믿을 근거다.

| 검출 | 무엇 | 고친 PR |
| --- | --- | --- |
| ①·③ | 번호판·신고 유형·시각 하나만 고쳐도 coarse·fine·incident·plate·overlay 전부 재호출 | #175 |
| ② I5·I6 | 거부된 재선택이 통과하거나, 거부됐는데 `case_rev`·CorrectionRecord가 남음 | #189 |
| 크래시 145건 | 같은 필드를 두 번 고치면 `multiple correction heads` — **길이 2 이상에서만 보인다** | #188 |

### 이번에 새로 찾은 것

| 무엇 | 처리 |
| --- | --- |
| 값이 바뀌지 않은 정정도 기록 → evidence가 거부 → 기록은 되돌리지 않으므로(§8-9) **그 case는 이후 CaseView를 못 만든다** (크래시 511 · I6 209) | 이 PR에서 수정 — 수정 후 0 |
| 번호판 값이 없을 때(판독 실패·못 읽음·일부 판독) 직접 입력이 correction-record §6 `vehicle_number: string`에 막힘 (크래시 370) | 계약 문제 — PR #212에 제기 |
| 선택 전(후보 0개) CaseView가 real 진입점에서 크래시 | PR #209에 수정 포함 |
| `RealAdapter`가 evidence 조립 때 1차 탐색을 다시 호출(① 994) — 2차 측정 | 이 PR에서 수정 — 수정 후 0 |
| A→B→A로 돌아올 때 관찰을 다시 돔(③ 322, 그중 Fine 100) — 3차 측정 | 결정 문서 + 수정 — 수정 후 0 |
| 선택 전 값 정정 · 탐색 실패 뒤 시간 단서 정정의 흔적 · `READY`인데 Package 없음(② 4,122) — 4차 측정 | 이 PR에서 수정 — 수정 후 0 (위 4차 표) |
| 번호판 직접 입력 크래시가 관찰 상태 둘(판독 실패·못 읽음)에서 706으로 — 4차 측정 | 위 PR #212 줄과 같은 원인 |
| 응답 대기(evidence 없음) 중 값 정정 → 「잘 모르겠어요」 응답 뒤 evidence가 그 정정을 거부(`invalid previous_value`·`datetime must be a string`·`correction chain values are discontinuous`) → 기록은 되돌리지 않으므로 **그 case는 이후 CaseView를 못 만든다** (크래시 61) — 4차 측정 | 미결 — 화면에 값이 없어 이전 값이 `null`로 기록된다. correction-record §8-6(형식이 틀린 입력은 기록하지 않는다)을 case가 지키려면 evidence의 값 검사를 공개 함수로 받아야 한다(규칙 복제 금지) — PR #212에 제기. web은 이 상태에서 값 칸을 그리지 않아 실사용 경로는 아직 없다 |

## 측정하지 않은 칸

| 칸 | 이유 |
| --- | --- |
| 번호판 재판독 · 구간 조정 · rebase | real 경로에 흐름 없음 |
| `RUN_NOTICE_ACTION`(재시도 발주) | 동기 경로에서는 JobRecord만 남고 실행이 없다 — worker 배선 뒤 |
| 상황 응답 `CORRECTED` | case-command v0이 받지 않는다(입력형 판본) |
| `READY`의 값 정정이 command로 오는 경로 | 입력형 command 판본 전 — 지금은 domain에서 내리기만 하고, 다시 오르는 것은 다음 command 때다 |

## 한계

- fixture 기반이라 **case 로직의 커버리지**만 본다. 실제 영상마다 달라지는 AI 결과의 다양성은 search·readout 평가 몫이다.
- recording 조회(`resolve_span`·`prepare_analysis_source`·`lookup_asset_facts`)와 시간 source는 따로 세지 않는다. fixture 경로에서 모두 관찰 함수 안에서 IncidentClip과 함께만 불리고(실측: `lookup_asset_facts`는 행동 8,476개 중 IncidentClip 없이 불린 경우 0, 항상 asset 수 3배), 시간 source는 raw 파일 읽기다. 조회만 다시 도는 경로(예: `SPAN_ADJUST`)가 생기면 asset ref를 키에 넣어 센다.
- 크래시가 나면 그 세션의 이후 행동은 판정하지 못한다. 남은 크래시 767건(번호판 직접 입력 706 · 응답 대기 중 정정 61, 4차 기준)이 풀리면 판정 수가 더 늘어난다.
- `READY`는 러너가 넣은 `observation_facts`(happy 값 하나)로만 간다. 최종 관찰 사실이 실제로 달라지는 경우(번호판이 신고영상에 안 보임 등)는 보지 않는다.
- 「다른 후보 선택」은 합성 rank2로 잰다 — span·관찰 내용이 rank1과 같아 **선택 context가 바뀌는 것**만 본다. 후보마다 관찰 결과가 달라지는 경우는 보지 않는다.
- 축(관찰 상태·행동)을 빠뜨리면 그 축은 보이지 않는다. 축이 늘어나면(위 「측정하지 않은 칸」) 다시 돌린다.
