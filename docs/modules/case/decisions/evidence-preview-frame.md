# 근거 장면(`evidence.preview_ref`) — case가 선택 후보의 IncidentClip에서 FrameRef를 발급받아 채운다

> **상태: 결정 · 구현(handler 발급 연결 [PR #527](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/527), 2026-11-03) · 배포본 표시 확인 전** · 2026-10-29 · 상위 3개 썸네일 범위 확대 2026-11-02(#523, §7) · 썸네일 발급을 Coarse로 옮김 2026-11-07(#583, §7-8 · Case #604·Runtime #617 머지) · Owner 정책 검토 2026-11-04(§7-6 · 7) · 발급 위치 확정 2026-10-30(정철원, [PR #470](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/470)) · 결정 추적 [#446](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/446) Case 확인 요청 6 · Search 답(4 · 5번, 서어진 2026-10-29) · 관련 `contract-source-asset-media-stream.md` §5.3 · `adr-data-contract-call-closure-2026-09-08.md`(「thumbnail 이미지 전달 방식」 Pending)
>
> **후보 영상 재생**(상위 3개 썸네일을 poster로 쓰고 그 위에 영상을 더함)은 `candidate-video-preview.md`(#554).

## 1. 문제

결과 화면의 근거 장면 칸이 늘 비어 있다. case는 `evidence.preview_ref`에 선택 후보의 `thumb_ref`를 그대로 싣는데(`view.py`), Search가 후보 `thumbnail_ref`를 늘 `null`로 낸다(`search/coarse.py`).

Search는 썸네일을 채우지 않기로 답했다(#446 4번). 이유는 셋이다.

- `FrameRef`는 recording만 발급한다(`contract-source-asset-media-stream.md` §5.3).
- Coarse 후보 7~13개를 모두 디코딩하면 150초 상한이 빠듯해진다.
- 파일 경계 해석은 recording 몫이다.

`CandidateEvent.thumbnail_ref`는 지우지 않고 `null`로 둔다(Search 계약 변경 없음).

## 2. 결정

1. **근거 장면의 생산자는 case다.** case가 recording 공개 함수로 `FrameRef`를 받아 `evidence.preview_ref`를 채운다. Search도 동의했다(#446 6번 의견).
2. **선택 후보 하나만 만든다.** 화면에 그리는 것은 선택 후보의 근거 장면 하나다. 후보 전체를 만들지 않는다(Search가 지적한 비용과 같은 이유).
   - **2026-11-02 범위 확대(#523):** 다른 후보 화면 카드용으로 **상위 3개 후보 썸네일**(`candidates[].thumb_ref`)도 만든다. 근거 장면(`evidence.preview_ref`)은 그대로 선택 후보 하나다. 후보 전체는 여전히 만들지 않는다 — §7.
3. **발급 경로는 IncidentClip → `STREAM_POSITION`이다.** readout이 쓰는 것과 같은 공개 경로다(`readout/providers.py` `IncidentClipFrames.read_at`).
   1. `get_incident_clip(clip_ref)`
   2. 대표 시각이 든 `source_provenance.asset_spans[]` 하나를 고른다
   3. `resolve_frame({kind: STREAM_POSITION, media_stream_ref, source_offset_sec})`

   `TIMELINE_POSITION`(timeline + `at_sec`)은 **이미 발급된 frame만 찾고 새로 디코딩하지 않는다**(`recording/service.py` `resolve_frame` → `find_frames_at_timeline_position`). 그래서 후보 대표 시각을 그대로 넣으면 `FRAME_NOT_FOUND`다.
4. **시각은 1차로 `representative_ms`다.** Coarse 대표 시각은 0.5배속 360p 응답을 원본 시각으로 환산한 값이라 ±2초 오차가 있다(#439 채점 기준). 「사건 구간 근처 장면」으로 읽는다. Fine `temporal_facts[].at_offset_ms`가 더 정밀하지만 Fine 입력 clip 시작 시각을 원본으로 환산할 공개 값이 있는지 확인이 필요하다 — 확인되면 바꾼다.
5. **IncidentClip이 생긴 뒤에 만든다.** `INCIDENT_CLIP_BUILD` handler가 clip을 만든 뒤 T1 전에 한 번 발급해 produced 결과(`preview_frame_ref`)에 싣고, case는 T2 반영 때 그 저장값을 clip job 결과에 남긴다. T2 transaction · CaseView 조회(읽기)에서는 디코딩하지 않고, T2 재전달 때 빠진 frame을 다시 만들지 않는다. 그래서 근거 장면은 clip 준비 전에는 `null`이다. 어느 위치의 frame인지(후보 · 세대 · timeline revision · 대표 시각)는 case가 정한다 — handler는 case의 위치 해석 함수를 쓴다.
6. **하나로 정하지 못하면 `null`이다.** 대표 시각이 clip 밖이거나, 그 위치의 `asset_spans`가 0개 · 2개 이상이거나, `resolve_frame`이 거부하면 지어내지 않고 `null`로 둔다. 실패는 notice로 만들지 않는다 — 근거 장면은 「있으면」 보이는 값이다(`core-user-flow.md` 결과 화면 표).
7. **번호판 확인 화면의 「장면」 칸은 이 값이 아니다.** 그 칸은 `evidence.plate_preview_ref`(`PlateReadout.best_frame.frame_ref`)다(#47 · #446). 근거 장면은 위반 장면이고, 번호판이 읽힌 frame과 다를 수 있다.

## 3. 구현할 때 할 일

> (2026-11-08 현재: 아래 반영기 · 투영 · 테스트는 끝났다 — §4 · §7 참고.)

- 반영기: `INCIDENT_CLIP_BUILD` 반영(`reflection.py` `_apply_incident_clip_build`) 때 handler가 실은 근거 장면을 저장. 동기 real 경로(`real_e2e.py`)도 같은 위치 해석 함수를 쓴다.
- 투영: `view.py` `preview_ref`를 저장한 값으로 바꾼다. `candidates[].thumb_ref`와 `preview_ref`가 「항상 같다」는 CaseView 계약 B§ 정의 행(#47, 2026-09-28)을 고친다.
- 계약 · ADR: 「thumbnail 이미지 전달 방식」 Pending에 「생산자 case, 선택 후보만, IncidentClip 경유」를 반영한다.
- 테스트: 발급 성공 · clip 밖 · span 0 / 2개 이상 · `resolve_frame` 거부 → `null`, 재선택 시 이전 후보 값이 남지 않음.

## 4. case 쪽 구현 (2026-10-29, 2026-10-31 발급 위치 반영)

- `case/preview_frame.py` — 위치 해석 `preview_frame_position(clip, span, representative_ms)`(결정 3 · 4 · 6, `(media_stream_ref, source_offset_sec)` 또는 `None`), 투영용 `current_preview_frame_ref`(선택 후보 · 현재 세대의 가장 나중 성공 clip 값).
- `reflection.py` — 성공한 `INCIDENT_CLIP_BUILD` 반영 때 결과의 `preview_frame_ref`를 그 clip job의 `observation_outcomes[*].preview_frame_ref`에 남긴다. 값이 없거나 키가 없는 결과(이전 형식)는 `None`이고, 반영 중에 발급하지 않는다. 상태 필드는 새로 만들지 않았다.
- `view.py` — `preview_ref`는 저장한 값, 없으면 선택 후보 `thumb_ref`. Search 썸네일은 실제 경로에서 늘 `null`이라 fallback은 fixture에서만 값이 있다.
- 테스트 `tests/case/test_evidence_preview_frame.py` — 위치 해석(성공 · 파일 경계 span · clip 밖 · span 0 / 2개 · 다른 timeline · revision · 대표 시각 없음), 반영(저장값 투영 · `null` · 키 없음 · notice 없음 · 판독 후속 발주 유지), 재선택(A→B→A).
- **handler 쪽 발급은 #527(2026-11-03)로 연결됐다.** 위치 해석은 이 함수를 그대로 주입해 쓴다. 남은 것은 아래 5번이다.

## 5. 남은 확인

- ~~**handler 발급(Runtime · Recording, 정철원).**~~ → **연결됨([PR #527](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/527), 2026-11-03).** payload 필드는 `preview_frame_ref`, 키가 없는 이전 결과는 `null`로 읽는다. 검증은 ASGI TestClient까지다 — 실제 배포 브라우저에서 근거 장면 · 후보 썸네일이 보이는지는 #523에서 확인한다. 아래는 정한 당시 기록이다. 발급 위치는 ②로 정했다(2026-10-30) — `INCIDENT_CLIP_BUILD` handler가 입력 connection을 반환한 뒤 clip을 만들고, `preview_frame_position`으로 위치를 받아 recording `resolve_frame(STREAM_POSITION)`으로 발급해 `incident_clip_result` payload의 `preview_frame_ref`(발급 불가면 `null`)로 싣는다. 발급 불가 · 모호한 위치는 `null`로 두고 clip 성공 · 판독 발주는 유지하며, Runtime · DB · 취소 오류는 삼키지 않는다. payload 필드 이름과 reader 호환의 정확한 모양은 Runtime 후속 구현에서 함께 맞춘다. 다중 VIDEO clip(#486 Inline 1)과 같은 handler라 순서를 맞춘다. T2 안 발급(①)과 별도 job(③)은 고르지 않았다.
- Fine 시각을 원본 시각으로 환산할 공개 값(위 결정 4).

## 6. 고르지 않은 것

| 안 | 고르지 않은 이유 |
| --- | --- |
| Search가 Coarse 후보마다 `thumbnail_ref` 생산 | Search는 `FrameRef`를 발급할 수 없고, 후보 전체 디코딩은 Coarse 상한을 압박한다(#446 4번) |
| case가 모든 후보에 썸네일 발급 | Coarse 후보 전체(7~13개) 디코딩은 비용이 크다. 다른 후보 화면에 필요한 상위 3개만 만든다(§7). 「clip 없는 후보는 위치를 정할 공개 경로가 없다」는 이유는 #523에서 틀린 것으로 확인했다 — 후보 구간 `resolve_span`으로 정한다 |
| `TIMELINE_POSITION`으로 대표 시각 바로 조회 | 새로 발급하지 않아 `FRAME_NOT_FOUND`다(결정 3) |
| CaseView 조회 때 발급 | 읽기 경로에서 디코딩하면 조회마다 비용이 들고 결과를 저장할 곳이 없다(결정 5) |
| T2 반영 안에서 발급(`RecordingFacts` 확장) | T2는 DB transaction 안이다. 디코딩 · 저장 중 connection을 잡으면 Runtime의 「무거운 작업 중 connection 반환」 경계와 부딪힌다(정철원 2026-10-30) |

## 7. 상위 3개 후보 썸네일 (#523, 2026-11-02)

결정 추적 [#523](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/523). 발급 시점은 A안(정철원 2026-11-01) — 별도 job 없이 선택 후보 clip handler가 근거 장면과 함께 발급한다. Runtime 배선은 [PR #527](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/527).

1. **고르는 후보는 case가 정한다.** 현재 세대 rank 1~3, rank 순. 3개보다 적으면 있는 만큼만 고른다. 위치를 정할 수 없는 후보(rebase로 stale · span 없음 · 그 세대 Coarse 결과에 없음)는 빼고 **4위로 채우지 않는다**. 입력이 현재 세대가 아니면 고르지 않는다.
2. **위치는 후보 자기 구간에서 정한다.** 선택 후보 clip의 provenance에 다른 후보를 맞추지 않는다. 후보 구간의 `SpanResolution`에서 대표 시각이 든 원본 span이 정확히 하나일 때만 위치를 낸다 — 해석은 결정 3 · 4 · 6과 같다.
3. **결과 형태는 `incident_clip_result.payload.candidate_frame_refs`** — 후보 ID → `frame_ref` 문자열 또는 `null`(최대 3개). 키가 없는 이전 결과는 「썸네일 없음」이다. 반영 때 다시 발급하지 않는다(결정 5와 같다).
4. **투영은 현재 세대 성공 clip들의 값이다.** 다른 후보를 고르면 그 후보 clip이 다시 발급한다 — 나중 frame이 앞의 것을 덮고, 나중 `null`은 앞서 만든 frame을 지우지 않는다. 세대가 바뀌면 앞 세대 값은 쓰지 않는다. `thumb_ref`는 이 값이 우선이고 없으면 Search `thumbnail_ref`(실제 경로에서 늘 `null`)다.
5. **썸네일은 clip이 끝난 뒤에 나온다.** clip 실패 전에 썸네일이 먼저 보이는 것은 보장하지 않는다(A안의 한계). → §7-8에서 Coarse 발급으로 푼다.
6. **나중 `null`이 앞 frame을 지우지 않는 것은 맞다(Owner 검토 2026-11-04).** 썸네일 위치는 선택 후보 clip이 아니라 후보 자기 구간에서 정하고, 같은 세대 · 같은 timeline revision일 때만 낸다(결정 2, `_source_position`). 그래서 A를 골랐을 때 만든 frame과 B를 골랐을 때 만든 frame은 같은 위치다. 나중 `null`은 「그 장면이 틀렸다」가 아니라 「이번에 발급하지 못했다」이므로 앞의 것을 남긴다. 4위로 채우지 않는 것(1)도 그대로 둔다.
7. **stale이 된 후보의 썸네일은 이번 RC에서 가리지 않는다(Owner 결정 2026-11-04).** stale 후보에는 새로 발급하지 않지만(1), stale이 되기 전에 발급한 frame은 투영에 남는다 — `current_candidate_frame_refs`는 stale을 보지 않는다. 같은 카드의 `marker_ms`는 stale이면 `null`이라(`view.py`) 기준이 다르다.
   - 그대로 두는 이유: 그 frame은 그 후보 구간의 실제 원본 장면이라 틀린 그림이 아니다. 이번 RC는 촬영 순서 · 연속성이 확인된 입력으로 제한해(#510) 같은 세대 안에서 rebase가 사실상 일어나지 않는다. 제출(11/11) 직전에 투영 규칙을 바꾸지 않는다.
   - 고르지 않은 것: stale이면 `thumb_ref`도 `null`로 가리기 — `marker_ms`와 기준이 같아지지만 위 이유로 지금 바꿀 근거가 약하다. #510의 Recording 정렬로 `CaseTimelineSource`를 교체할 때 다시 본다.
   - 알고 가는 한계: stale 후보 카드에 rebase 전 장면이 보일 수 있다. 서어진 2026-11-02 #523 댓글 표의 「빠진 후보는 카드 자체가 없음」은 발급 기준 설명이다 — CaseView는 stale 후보도 카드로 낸다.

8. **썸네일은 Coarse handler가 T1 전에 발급한다(#583 E안, 2026-11-07).** A안은 첫 Fine이 `NOT_OBSERVED`거나 실패하면 clip이 발주되지 않아, 다른 후보 썸네일도 처음부터 만들어지지 않았다(멘토 리뷰 #563). PM이 P0 · RC 필수 수정으로 정했고(`docs/management/rc-scope-2026-11-05.md`), 정철원 · 유소연이 E를 골랐다(#583 댓글 2026-11-05 · 06).
   - **고르는 후보:** 그 Coarse 결과의 rank 1~3, rank 순(`coarse_thumbnail_candidate_ids`). 후보 목록이 아직 case에 반영되기 전이라 결과 `CandidateEvent`만 본다. span 다섯 값 중 하나라도 없으면 빼고 4위로 채우지 않는다(1과 같다). 위치는 후보 자기 구간에서 `candidate_frame_position`으로 정한다(2와 같다).
   - **결과 형태:** Coarse 결과 `candidate_frame_refs` — 후보 ID → `frame_ref` 또는 `null`(최대 3개). 키가 없거나 `null`이면 이전 형식 · 발급 없음이다. case가 고르지 않은 후보의 값 · 빈 문자열 · 다른 모양은 배선 오류(`ValueError`)로 반영하지 않는다(`coarse_frame_refs`).
   - **반영 · 투영:** Coarse 반영 때 후보 `thumb_ref`에 남긴다. Search `thumbnail_ref`보다 우선이고 `null`이면 Search 값이다. 늦은 결과 · 재전달은 반영 guard가 막으므로 현재 세대 후보에만 남는다. 다시 찾으면 후보 목록과 함께 바뀐다.
   - **A안 경로는 그대로 둔다.** clip이 낸 frame이 여전히 우선이고, clip의 `null`은 Coarse frame을 지우지 않는다(6과 같다). 같은 후보 · 같은 대표 시각이라 같은 장면이다. clip handler 쪽 발급을 걷어낼지는 Runtime이 정한다.
   - **근거 장면에도 닿는다.** `evidence.preview_ref`는 clip frame이 없으면 선택 후보 `thumb_ref`를 쓰므로(`view.py`), clip 전에도 Coarse frame이 보인다. 같은 대표 시각 frame이라 결정 1의 장면과 다르지 않다.
   - **Runtime 구현:** 성공 Coarse의 Top-3 발급을 T1 전에 연결했다. 네 가지 `FRAME_REFUSALS`만 후보별 `null`로 처리하고, 빈 후보 목록에는 발급을 호출하지 않는다. MySQL PR CI에서 첫 Fine `NOT_OBSERVED`/실패 뒤 ref 유지와 소유 프레임 HTTP 조회를 확인했다. 프레임 발급·저장 실패는 유료 Search 호출 재시도 경계 밖에서 처리한다. 대상 EC2·브라우저 검증은 PR 기준 `NOT_RUN`이다. [#617](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/617) · [PR CI](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/42356263220)
   - **남는 한계:** Coarse 자체가 실패하면 후보도 썸네일도 없다. 썸네일 3장의 추가 시간은 재지 않았다[확인 필요].

case 쪽 구현은 `case/preview_frame.py` `coarse_thumbnail_candidate_ids` · `coarse_frame_refs` · `thumbnail_candidate_ids` · `candidate_frame_position` · `current_candidate_frame_refs`, `reflection.py`(`candidate_frame_refs` 저장), `view.py`(`thumb_ref` 투영), `service.candidates_from_events`(`frame_refs`), 테스트 `tests/case/test_candidate_thumbnails.py` · `tests/case/test_coarse_candidate_thumbnails.py`(#583)다. clip handler 연결은 #527에서, 별도의 Coarse handler 연결은 #617에서 머지됐다.

남은 확인: 다른 후보 카드의 「미리보기 준비 중」은 web이 `running_jobs`가 있는지만으로 정해, 썸네일과 무관한 Fine · export가 돌 때도 준비 중이 될 수 있다(`docs/runtime/rt10b-preview-frames.md` #525 판정의 한계 표). case가 썸네일 발급 대기를 따로 알려야 하는지 정하지 않았다.
