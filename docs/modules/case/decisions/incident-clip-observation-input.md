# 관찰 job 입력 고정 · IncidentClip 준비 단위 · 발주 순서 (8-6 2단계 · RT-10(b))

> **상태: RT-10 Implementer(정철원) · Runtime/Ops Owner(김준영) 확인 완료 — web(신유민) label 확인 대기** · 작성 2026-10-23 · 갱신 2026-10-24 · 담당 유소연(`case`) · 근거 #297 [정철원 10-22 제안](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6338265847) · [김준영 10-22 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6340336360) · [서어진 10-23 Search 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6364998000) · [정철원 10-24 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6380237333) · [정철원 10-24 요청 정리](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6380318817) · [김준영 10-24 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6380794802) · `observation-storage.md` §1 · §6 미결 · 6.6순위 조건 2 · `reselect-observation-reuse.md` · `contract-case-command.md` 초기 선택(#168 결정 1)
> 어느 후보를 언제 관찰하고 무엇을 다시 발주하는지는 case 결정 범위다(Tech Spec §12 「Worker가 orchestration 결정을 새로 만듦」 금지). IncidentClip 본체의 durable 보관 · 복원 · 동일성은 recording(REC) 몫이고, handler 등록 · T1 처리 · 재시도는 Runtime 몫이다. 이 문서는 그 둘이 기대는 **case 쪽 입력과 순서**만 정한다.

## 1. 목표 · 범위

#297에서 case에 온 판단 요청 4개에 답한다.

1. job에 고정된 후보 · 세대 · `InputRef`를 조회하는 공개 경계
2. clip 준비가 끝난 뒤 Readout job 발주 순서
3. 재선택 · 재탐색 이후에도 기존 job 입력이 변하지 않는 연결 방식
4. `StoredObservationAdapter`의 IncidentClip 조립 경계

**범위 밖:** IncidentClip 본체 보관 · close/restart 복원 · 생성 후 T1 전 crash 처리(recording · Runtime) · T1 persistence retry · COMMIT 불명 복구(Runtime) · handler 내부 구현 · `EvidenceNeeds` 자동 재발주(`observation-storage.md` §1과 같음) · 6.6순위 조건 1(준비 중 재선택 금지) · `REPORT_VIDEO_EXPORT` · `PLATE_IMAGE_EXPORT` 입력.

## 2. 지금

| 무엇 | 지금 |
| --- | --- |
| 후보 수신 뒤 초기 선택 · Fine 발주 | 비동기 경로에 없다. `receive_candidates`가 `CANDIDATE_REVIEW`로 올리고 멈춘다(`result-reflection.md` 범위 밖으로 미뤄 둠). 데모만 `select_top_ranked` · `issue_fine_verify`를 직접 부른다 |
| 관찰 JobRecord에 담기는 입력 | `kind` · `input_fingerprint`뿐(`scope_ref`는 `null`). 어느 후보 · 어느 세대 · 어느 clip인지는 JobRecord에 없다 |
| 관찰 kind T2 | `PLATE_READ` · `OVERLAY_TIME_READ` · `FINE_VERIFY` 정산 + READY gate는 develop에 있다(#357). `StoredObservationAdapter`는 관찰 객체 고르기(§4-4)까지만 있다(#386) |
| IncidentClip 생성 | 동기 `real_e2e.observe_real_video_candidate`만. Fine → `classify_visual_evidence` → `NOT_ASSEMBLED`가 아니면 `resolve_span(candidate.span, media_stream_ref)` → `build_incident_clip` → 같은 `InputRef`로 `read_plate` · `read_overlay_time` |
| clip 본체 | `RecordingService` 메모리 — `close()`에서 사라진다(#297 정철원 확인) |

## 3. 흐름

```
[T2 COARSE_SEARCH] receive_candidates
   └─ 후보가 있고 stale가 아니면 rank=1 자동 선택 → FINE_VERIFY 발주(입력 고정 §4-1)

[T2 FINE_VERIFY] 정산(REFLECTED / FAILED)
   └─ SUCCEEDED · 입력의 후보 = 현재 선택 · 현재 세대
        ├─ verification == NOT_OBSERVED → 끝(clip · 판독 발주 없음)
        └─ 그 밖 → INCIDENT_CLIP_BUILD 발주(입력 고정, fine_job_id 포함)

[T2 INCIDENT_CLIP_BUILD] 정산
   └─ SUCCEEDED · 같은 조건 → PLATE_READ · OVERLAY_TIME_READ 발주(같은 incident_clip_ref를 입력에 고정)

[T2 PLATE_READ · OVERLAY_TIME_READ] 정산 + READY gate(observation-storage.md §4-5, #357)

[SELECT_OTHER_CANDIDATE] 같은 세대에 그 후보의 관찰이 있으면 재사용, 없으면 FINE_VERIFY부터 발주
```

## 4. 결정

1. **관찰 job의 입력은 발주할 때 case state에 고정하고, 공개 함수로 읽게 한다.**
   - `issue_job`이 관찰 kind(`FINE_VERIFY` · `INCIDENT_CLIP_BUILD` · `PLATE_READ` · `OVERLAY_TIME_READ`)를 발주할 때 `observation_inputs[job_id]`를 같은 case 저장(같은 tx)에 남긴다. append-only이고 고치지 않는다 — 재선택 · 재탐색이 와도 이미 발주한 job의 입력은 그대로다(질문 3).
   - 모양(case 내부 state, JobRecord 계약 밖):

     | 필드 | 뜻 | 쓰는 kind |
     | --- | --- | --- |
     | `candidate_id` | 관찰 대상 후보 | 전부 |
     | `generation_job_id` | 그 후보 목록을 들여온 `COARSE_SEARCH` job — 세대 표식(`observation-storage.md` §4-4와 같은 기준) | 전부 |
     | `span` | 후보 `span`(`timeline_id` · `timeline_revision` · `start_ms` · `end_ms`) snapshot. clip 구간은 이 Coarse `span`을 쓴다 — Fine `temporal_facts[].at_offset_ms`는 선택값이라 구간 근거로 보장되지 않는다(서어진 10-23 ③) | `FINE_VERIFY` · `INCIDENT_CLIP_BUILD` |
     | `max_latency_sec` | Fine 후보당 실행 상한(초, `timeout-fallback.md` 잠정값 표 70초). handler가 그대로 `verify_visual`에 넘기고, Coarse scope 상한으로 대신하지 않는다(#407 결정 (a), 2026-10-26 추가). clip 입력으로 옮기지 않는다 | `FINE_VERIFY` |
     | `fine_job_id` | clip 구간 · stream을 정한 Fine job | `INCIDENT_CLIP_BUILD` |
     | `incident_clip_ref` | 두 판독이 공유하는 clip | `PLATE_READ` · `OVERLAY_TIME_READ` |

   - **`scope_ref`는 `observation_inputs`에 넣지 않고 JobRecord `scope_ref`에 싣는다.** 관찰 kind를 발주할 때 그 세대 `COARSE_SEARCH` JobRecord의 `scope_ref`를 그대로 넣는다. JobRecord 계약의 「`scope_ref`가 존재하면 유효한 AnalysisScope.scope_id를 가리킴」(`contract-job-record-case-view.md` §3)을 그대로 지키므로 계약 변경이 아니고, 같은 값을 두 곳에 두지 않는다. handler는 자기 JobRecord에서 `scope_ref`를 읽고, scope 본문은 `CaseStore.get_case(case_id).analysis_scopes[scope_ref]`로 읽는다([#297 10-21 case 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6314898281) 2-(a)).
     - 그 결과 `issue_job`의 대체 규칙(같은 kind · `scope_ref`의 기다리던 job → `SUPERSEDED`)이 관찰 kind에서는 같은 scope 안으로 좁아진다. 이전 세대 scope의 기다리던 관찰 job은 대체되지 않고, 결과가 와도 §4-4대로 정산만 된다.
   - 공개 함수 `CaseStore.observation_input(case_id, job_id) -> dict`(질문 1). handler는 자기 JobRecord의 `job_id`로 부르고, case 내부 repository · schema를 읽지 않는다. 관찰 kind가 아니거나 입력이 없으면 `KeyError`.
   - `media_stream_ref`는 입력에 값으로 넣지 않는다. Fine 결과가 원본이라 `fine_job_id`로 그 produced를 읽는다(같은 값을 두 곳에 두지 않는다 — `observation-storage.md` §4-2와 같은 이유).
   - 재시도 · 재판독(`RUN_NOTICE_ACTION` · `PLATE_REREAD`)은 지금처럼 「가장 나중 같은 kind JobRecord의 입력」(`scope_ref` 포함)을 쓰므로, `observation_inputs`도 그 job의 것을 그대로 복사한다 — 같은 clip을 다시 읽는다.

2. **IncidentClip 준비는 새 kind `INCIDENT_CLIP_BUILD`로 둔다.** `FINE_VERIFY` handler 안에 넣지 않는다.
   - 김준영 10-22 답변대로 Fine 성공과 clip 준비는 다른 실패 · 재실행 단위다. 별도 job이면 clip만 실패했을 때 Fine(유료)을 다시 부르지 않고 새 `job_id`로 clip만 다시 낼 수 있고, `FINE_VERIFY`는 그 자체로 `SUCCEEDED`에 남는다.
   - JobRecord A§7 `kind`(열린 enum)와 A§12 `label_key` `job.incident_clip_build`에 등재한다 — `PLATE_IMAGE_EXPORT` · `HINT_EXTRACT`와 같은 등재라 `job-record/v1`을 유지한다. 이름 · label 문구는 web(신유민) 확인이 필요하다.
   - handler 등록 · capability(`recording.build_incident_clip`) 호출 · clip 본체 durable 보관은 Runtime · recording(정철원). case는 결과의 `incident_clip_ref`만 읽는다.

3. **clip 준비 여부는 Fine의 `VisualEvidence.verification`으로 가른다 — 동기 경로와 같다.**
   - `NOT_OBSERVED`(`classify_visual_evidence` → `NOT_ASSEMBLED`)이면 clip · 판독을 발주하지 않는다. 실패가 아니라 정상 결과다(김준영 10-22 ④).
   - `OBSERVED` · `UNCERTAIN`이면 발주한다. `UNCERTAIN`은 상황 응답을 기다리는 것이지 관찰을 멈추는 것이 아니다(`observe_real_video_candidate`와 같음).
   - Search `AnalysisRun.outcome=PARTIAL`이어도 `VisualEvidence`가 있으면 위 규칙을 따른다. Runtime은 이 판단을 하지 않는다(김준영 10-22 ③). `VisualEvidence` 없이 끝난 Fine은 Fine 실패로 본다(`search.visual_verify_failed`, 8-14).

4. **후속 발주는 「입력의 후보 = 현재 선택 후보 · 현재 세대」일 때만 한다(질문 2).**
   - 늦게 온 이전 후보 · 이전 세대의 Fine · clip 결과는 정산만 하고 다음 단계를 내지 않는다. 6.6순위 조건 2를 「투영하지 않음」(`observation-storage.md` §4-4)에 더해 「발주하지 않음」으로도 지킨다 — 비용이 드는 job이 버려질 후보에 나가지 않는다.
   - `PLATE_READ` · `OVERLAY_TIME_READ`는 clip `SUCCEEDED` 뒤 함께 발주하고, 둘 다 같은 `incident_clip_ref`를 입력에 갖는다. 각 handler는 자기 공개 함수를 한 번만 부른다(신유민 10-07 확인).

5. **초기 선택과 첫 Fine 발주는 `COARSE_SEARCH` T2에서 한다.** `rank=1` 자동 선택(`contract-case-command.md`, #168 결정 1)을 비동기 경로에도 그대로 적용한다. 후보가 0개이거나 첫 후보가 stale이면 선택 · 발주하지 않는다(`core-user-flow.md` 가장 유력한 후보). stage는 `CANDIDATE_REVIEW` → `EVIDENCE_REVIEW`로 지금 `select_candidate`가 하는 전이를 그대로 탄다.

6. **다른 후보 선택은 같은 세대 안 관찰을 재사용한다(`reselect-observation-reuse.md` (b)).** `SELECT_OTHER_CANDIDATE` 뒤 그 후보 · 현재 세대에 `SUCCEEDED` 관찰 job이 있으면 그 단계는 다시 내지 않고, 없는 첫 단계부터 발주한다(Fine이 없으면 Fine, Fine만 있으면 clip, clip까지 있으면 판독).
   - **(2026-10-26 구현 결정) 끝난 단계는 T2 때 case state에 남긴 기록으로 알아본다.** 관찰 job을 반영할 때 `observation_outcomes[job_id] = {status}`를 남기고, Fine은 `verification`, clip은 `incident_clip_ref`를 더한다 — 후속 발주(§4-3 · §4-4)가 이미 읽는 두 값뿐이고 결과 내용 전체는 복사하지 않는다(§4-5 「내용은 case state에 복사하지 않는다」를 지킨다). command는 이 기록만 보고 고르므로 command 경로에 reader가 필요 없다. 실패한 단계 · `VisualEvidence` 없이 끝난 Fine은 빠진 단계로 다시 내고, Fine이 `NOT_OBSERVED`면 아무것도 내지 않으며, 그 후보의 job을 아직 기다리면 내지 않는다. 판독은 빠진 kind만 같은 clip으로 낸다.

7. **`StoredObservationAdapter`는 clip을 판독 입력에서 얻는다(질문 4).** 선택된 `PLATE_READ` 결과(§4-4 필터)의 입력 `incident_clip_ref`가 그 후보의 clip이고, 관련 asset은 지금처럼 그 clip lineage로 고른다(`select_case_assets`, `real-e2e-scenarios.md`). AssetFact는 recording 공개 함수로 읽는다. 판독이 아직 없으면 clip도 없는 것으로 본다.

## 5. 알려진 한계

- clip 본체가 recording에 durable하게 남기 전에는(§1 범위 밖) `INCIDENT_CLIP_BUILD`와 판독이 다른 process에서 같은 clip을 열 수 없다. 첫 비동기 E2E는 recording 쪽 보관이 들어온 뒤 돈다.
- `observation_inputs`는 case state JSON에 쌓인다. case당 관찰 job이 몇십 개 수준이라 지금은 문제 삼지 않는다.

## 6. 미결 (채우지 않는다)

- clip 준비 실패(`INCIDENT_CLIP_BUILD` `FAILED`)의 notice code · action — CaseView 판본에서 web(신유민)과 정한다. **이번 case 구현(§9) 범위가 아니라 후속이다.** 그때까지 package는 준비되지 않고 진행 화면에 머문다. 다시 시도는 Runtime 자동 재시도가 아니라 case가 새 `job_id`로 발주하는 것이다(김준영 10-24 ②).
- `INCIDENT_CLIP_BUILD` handler가 Fine produced에서 `media_stream_ref`를 읽는 방법 — RT-10 Implementer. (구간은 입력 `span`, §4-1)
- clip 본체 보관 · 동일성 · 생성 후 T1 전 crash 처리 — recording · Runtime(정철원).

## 7. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| `FINE_VERIFY` handler 안에서 clip까지 만든다(#297 정철원 제안 1) | Fine 성공과 clip 실패가 한 execution에 묶인다. clip만 다시 하려면 Fine을 다시 부르거나 handler 안에 부분 재시도가 생긴다(김준영 10-22 ①②) |
| 판독 handler가 각자 clip을 만든다 | 두 판독이 서로 다른 clip ref를 갖고 같은 일을 두 번 한다(#297 정철원 확인) |
| case가 T2 안에서 `build_incident_clip`을 직접 부른다 | T2는 반영 · 발주만 하고 capability를 실행하지 않는다. 실패 · 재시도 단위도 없어진다 |
| JobRecord에 `candidate_id` · `incident_clip_ref` 필드를 더한다 | JobRecord ↔ CaseView 계약이 바뀌고 6.6순위 결정(「JobRecord 계약 변경 불필요」)을 뒤집는다(`observation-storage.md` §7과 같음) |
| handler가 실행 시점의 현재 선택 후보를 조회한다 | 대기 중 재선택 · 재탐색이 오면 과거 job이 다른 후보를 관찰한다(#297 정철원 확인) |
| `scope_ref`에 관찰 입력 ref를 싣는다 | `scope_ref`는 `AnalysisScope`를 가리키는 필드라 뜻이 바뀐다 |
| §4-6 재선택 때 command가 `ProducedReader`로 이전 Fine · clip 결과를 다시 읽는다 | command 경로에 reader를 꽂는 composition 변경(Runtime)이 필요하고, T2가 이미 읽은 값을 다시 읽는다 |
| §4-6 재사용을 Runtime JobRecord 캐시(같은 `input_fingerprint`의 `SUCCEEDED` 재사용, A절 §7)에 맡긴다 | case가 새 job을 발주하고 Runtime이 캐시로 끝내는 구조라 job · execution이 늘고, 캐시 구현(`input-fingerprint-implementation-label-deferred.md`)을 기다려야 한다. case가 발주하지 않는 쪽이 단순하다 |

## 8. 맞출 것

- ~~정철원(RT-10 · recording)~~ — 10-24 확인: `observation_input` 모양으로 handler 진행 가능, `INCIDENT_CLIP_BUILD`는 별도 handler로 등록. clip 본체 durable 보관 · 복원 · 동일성은 recording 별도 변경으로 맡는다.
- ~~김준영(Runtime/Ops)~~ — 10-24 승인: 새 kind · 독립 execution, Fine과 다른 terminal 경계, 자동 retry는 `STALE`만, `JOB_KINDS` ↔ registry 대응 검증에 포함, JobRecord · JobExecution 의미 변경 없음.
- **신유민(web):** `INCIDENT_CLIP_BUILD` 이름 · `job.incident_clip_build` label.

## 9. case 쪽 구현 (확인 뒤, TDD)

> **진행 (2026-10-24, 1단계):** kind 등재 · 관찰 입력 고정과 `CaseStore.observation_input` · 관찰 kind의 `scope_ref` · Fine → clip → 판독 후속 발주 · 같은 입력 재발주(`jobs.issue_same_input`)를 넣었다(`case/observation.py`). **남은 것:** Coarse T2 자동 선택 · 첫 Fine 발주 배선은 `StoredObservationAdapter`를 composition에 꽂는 단계와 함께 연다 — 선택된 case는 CaseView 조립에 adapter가 필요해, 먼저 열면 API · Worker가 `AdapterNotAttached`로 멈춘다(Runtime 비동기 E2E의 rank=1 후보). `SELECT_OTHER_CANDIDATE` 뒤 첫 빠진 단계부터 발주(§4-6)도 그때 붙인다.
>
> **진행 (2026-10-24, 2단계):** §4-7 `StoredObservationAdapter`를 넣었다(`observation-storage.md` §9). 남은 것은 composition 주입(Runtime) 뒤 Coarse T2 자동 선택 배선과 §4-6이다.
>
> **진행 (2026-10-26, 3단계):** §4-5 Coarse T2 자동 선택 · 첫 Fine 발주를 반영기에 넣었다(`reflection._apply_coarse_search`). composition 주입(RT-10(b) #407) 위에서 연다 — 발주한 Fine은 `appended_job_records`로 돌려주고 Worker reflector가 같은 transaction에서 enqueue한다. 남은 것은 §4-6.
>
> **진행 (2026-10-26, 4단계):** §4-6 `SELECT_OTHER_CANDIDATE` 뒤 첫 빠진 단계부터 발주(`observation.issue_missing_for_selected`, `command._select_other_candidate`)와 그 근거인 `observation_outcomes`(T2 반영 때 기록, case state 저장)를 넣었다. 발주한 job은 command `appended_job_records`로 돌려준다(`command-appended-job-records.md`).

- `JOB_KINDS`에 `INCIDENT_CLIP_BUILD` · `label_key` 매핑 · JobRecord 계약 A§7 · A§12 등재.
- `issue_job(..., observation_input=…)` · 관찰 kind 발주 때 세대의 `scope_ref` 싣기 · `CaseStore.observation_input`.
- `reflection`: `COARSE_SEARCH` 뒤 자동 선택 + Fine 발주, `FINE_VERIFY` · `INCIDENT_CLIP_BUILD` 뒤 후속 발주, `_APPLIERS`에 `INCIDENT_CLIP_BUILD`.
- `SELECT_OTHER_CANDIDATE` 뒤 첫 빠진 단계부터 발주.
- 테스트: 관찰 JobRecord `scope_ref` = 그 세대 `COARSE_SEARCH`의 `scope_ref`, 재선택 · 재탐색 뒤 기존 job 입력 불변, 이전 후보의 늦은 Fine · clip 결과가 후속을 내지 않음, `NOT_OBSERVED`면 clip 없음, 두 판독이 같은 clip ref, A→B→A 재사용.
