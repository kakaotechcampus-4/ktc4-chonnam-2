# eval 2차 검수(#22) 대응 — 참값 라벨 2건, STALE attempt UsageRecord, expected/ 소유권

> 결정일 2026-09-10 · 근거 [이슈 #22](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/22) (김대원, eval) B-1~B-4
> **담당:** 유소연(mock pack v3 전체 owner) · **Consulted:** 없음(case 소유 사안 아니지만 mock pack 전체 owner로서 답함)

이슈 #22는 case 소유 계약이 아니라 eval이 mock pack 전반(주로 search·readout·common 소비분)을 채점 관점에서 재검수한 것이다. 4건(B-1~B-4) 중 case/mock-owner가 답해야 하는 것만 이 문서에서 처리한다.

## B-1. `data/mock/expected/` 재작성 — 액션 없음(eval 자기 소유 작업)

김대원 본인이 "제 몫이라 형태까지 여기에 올립니다"로 명시: 기존 `eval_fixture_correct_001.json`/`eval_fixture_wrong_001.json` 2개 폐기 → `data/mock/expected/<scenario_id>.expected.json` 7개 신설(스키마 `eval-expected/v2`, `readout_ref`/`resolution_ref`/`timeline_ref` 참조 방식)은 eval이 직접 작업한다.

**동의한 것:** `data/mock/expected/`는 `01_mock_dataset_overview.md`에 이미 "Eval 전용"으로 명시돼 있고, 이번 라운드부터 다른 모듈/mock-owner가 이 디렉터리를 손대지 않는다 — 두 벌의 정답지가 생기는 것을 막기 위함. 이 세션에서도 `data/mock/expected/`는 건드리지 않았다.

`correction_rerun_001` 라벨 판단 확인 요청(사용자 정정 13:15:30→13:13:00을 anchor 오류로 보고 timeline offset 930s는 유지, 절대시각만 정정된 것으로 라벨)은 **case 관점에서도 맞다** — `TimeResolution`의 `USER_OVERRIDE`는 절대시각 값을 교체하는 것이지 candidate의 timeline-relative offset을 재계산하는 것이 아니다(offset은 `AnalysisRun`/`CandidateEvent` 소유이고 `TimeResolution`이 건드리는 대상이 아니다). 이견 없음.

## B-2. `CandidateEvent.span` 폭 — 종결(2026-09-10, 서어진 회신 반영)

`span`이 (a) coarse 후보 창인지 (b) 사건 구간인지는 `CandidateEvent`/`AnalysisRun` 계약 소유자 서어진(`search`)의 답이 필요해 처음엔 case가 결정할 사안이 아니라고 보류했다. 서어진이 **(a) coarse 후보 창이 맞다**고 회신했다 — 원문·근거·fixture 증거는 `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`에 그대로 보존했다. `contract-analysis-run-candidate-event.md` §4-1·§7(eval Consumer 매칭 규칙)에 반영했고, `relative_rebase_001`의 span이 요청 scope와 동일해 오차가 정의상 0이던 문제도 서어진이 case에 넘긴 대로 `502000~527000ms`로 좁혀 해소했다.

## B-3. 참값 라벨 2건 — mock pack 저자로서 답함

두 라벨 모두 "AI가 확정 못 한 것이 옳았는가"를 재는 참값이고, 시나리오를 설계한 사람(mock pack 저자)만 답할 수 있다는 김대원의 진단이 맞다. mock pack v3 전체 owner로서 아래처럼 확정한다.

### `plate_reread_001`의 실제 번호판 문자열

`readout/scenario_plate_reread_001.json`의 두 프레임 판독은 `"17나2804"`(conf 0.41)·`"17나2891"`(conf 0.38)로 마지막 두 자리(0-idx position 5,6)만 불일치, consensus `"17나28??"`로 abstain했다.

**확정: 실제 번호판은 `17나2867`이다.** 두 프레임 추정 모두와 마지막 두 자리가 다르게 골랐다(`67` ∉ {`04`, `91`}) — "어느 쪽 프레임도 맞히지 못했고, 그래서 abstain이 정답이었다"는 이 시나리오의 설계 의도(FRAME_DISAGREEMENT → NEEDS_REVIEW)를 참값으로도 재확인하는 값이다. `legibility=UNREADABLE`은 김대원이 이미 잡은 대로 유지.

### `unknown_abstain_partial_001`의 참값 사건 유형

**확정: 참값 없음 — `scoring: EXCLUDED` + 사유로 둔다.** 이 시나리오는 이번 라운드에 `EvidenceRecord.event.visual_event_type.value=null`로 재구성한 바로 그 시나리오다(이슈 #25 A절, `generic-warn-package-and-situation-response.md`) — "AI가 사건 유형 자체를 확정하지 못했다"를 표현하는 것이 이 시나리오의 존재 이유이며, `situation_confirmation=UNKNOWN`(사용자도 "잘 모르겠어요")까지 같은 방향이다. 여기에 정답 이벤트 유형을 부여하면 "AI가 틀렸다"는 이야기가 되어 시나리오 설계와 정면으로 모순된다. 장면 자체가 애매하다는 것이 참값이다 — 오검출로도 세지 않는다.

두 값 모두 eval 쪽 카탈로그(`expected/scenario_plate_reread_001.expected.json`·`expected/scenario_unknown_abstain_partial_001.expected.json`)에 채워 넣을 수 있도록 이 문서를 인용해 회신한다. mock fixture(readout/evidence/case) 자체는 변경 불필요 — 김대원이 이미 "fixture 수정은 필요 없고 카탈로그 한 줄이면 된다"고 명시했다.

### (부가 질문 답) `plate_reread_001`의 "재판독 성공 후" 상태 추가 계획

김대원이 B-3 말미에 물은 것: `exec_p001_plate_reread`가 `QUEUED`·`produced=[]`라 재판독 후 판독값이 없는데, 다음 차수에 "재판독 성공 후" 상태를 넣을 계획인지.

**답(2026-09-10 갱신): 같은 세션 안에서 완료했다.** 처음 이 문서를 쓸 때는 "다음 라운드에 넣는다"고 답했지만, 같은 날 후속 작업으로 실제로 만들었다 — "재판독 대기 중" 스냅샷(`case_rev:3`, `running_jobs=[{job_p001_plate_reread, PENDING}]`)을 지우지 않고 그대로 둔 채, 완료 후 상태를 **새 `case_rev:4`**로 별도 추가하는 원래 계획 그대로 실행했다. `readout`에 성공한 재판독 `PlateReadout`(`readout_p001_plate_reread`, `abstained=false`, `consensus.text="17나2867"` — 위에서 확정한 참값과 정확히 일치)과 `ReadoutRun`, `common`에 `SUCCEEDED` `JobExecution`+`UsageRecord`, `evidence`에 `EvidenceRecord`(`ev_p001_v2`, `supersedes_ref=ev_p001`)·`EvidenceNeeds`(충족, `items=[]`)·`RequirementReport`(`req_p001_evidence_v2`, `UNKNOWN`→`PASS`)를 추가했다. 재판독 전/후 판독값(`readout_p001_plate` abstain vs `readout_p001_plate_reread` 확정) 비교, `review_needed`/`requirements_evidence.readiness` 전환(`UNKNOWN`→`PASS`) 모두 `case_rev:3`↔`case_rev:4` 두 스냅샷을 나란히 비교하면 eval이 검증할 수 있다. `04_mock_validation_report.md` §1 커버리지 갭에서 이 항목을 제거했다. 상세: `docs/mock/02_mock_scenario_catalog.md`의 `scenario_plate_reread_001` v3 추가 노트.

## B-4. STALE/실패 attempt의 `UsageRecord` 발행 — mock pack 컨벤션으로 확정, 계약 등재는 common/runtime 잔여

**질문:** 실패/STALE attempt에도 `UsageRecord`를 발행하는 게 규칙인가?

**mock pack v3에서 채택한 답: 그렇다.** `scenario_infra_failure_001`의 attempt 1(`exec_x001_plate_a1`, STALE)에 `usage_x001_plate_a1`(0 KRW, `run_ref: null`)을 이미 추가했다 — attempt 2(`exec_x001_plate_a2`, FAILED)의 `usage_x001_plate`와 함께 두 attempt 모두 원장에 남는다. 근거: 비용 분모(케이스당 총비용)에서 실패·재시도분이 조용히 빠지면 "재시도가 잦은 구현이 더 싸 보인다"는 김대원의 지적이 맞고, 유료 provider에서는 그대로 예산·efficiency 지표를 왜곡한다. `ocr-local`처럼 0원 provider라도 **row 자체는 남겨서** "이 attempt는 존재했고 비용은 0이었다"와 "이 attempt는 존재 자체가 원장에 없다"를 구별할 수 있게 했다.

**남은 것:** 이 규칙은 mock fixture 컨벤션으로는 확정했지만 `contract-usage-record.md`(Producer/Owner: 김준영, common/runtime)는 아직 이 점을 명문화하지 않았다 — 계약 소유자가 아닌 case가 남의 계약에 정규 규칙을 새로 써넣지 않는다. `CONTRACT_CONFLICTS.md`에 등재해 김준영의 계약 정식 반영을 요청한다.
