# 근거 장면(`evidence.preview_ref`) — case가 선택 후보의 IncidentClip에서 FrameRef를 발급받아 채운다

> **상태: 결정 · case 쪽 구현(handler 발급 미연결)** · 2026-10-29 · 발급 위치 확정 2026-10-30(정철원, [PR #470](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/470)) · 결정 추적 [#446](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/446) Case 확인 요청 6 · Search 답(4 · 5번, 서어진 2026-10-29) · 관련 `contract-source-asset-media-stream.md` §5.3 · `adr-data-contract-call-closure-2026-09-08.md`(「thumbnail 이미지 전달 방식」 Pending)

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

- 반영기: `INCIDENT_CLIP_BUILD` 반영(`reflection.py` `_apply_incident_clip_build`) 때 handler가 실은 근거 장면을 저장. 동기 real 경로(`real_e2e.py`)도 같은 위치 해석 함수를 쓴다.
- 투영: `view.py` `preview_ref`를 저장한 값으로 바꾼다. `candidates[].thumb_ref`와 `preview_ref`가 「항상 같다」는 CaseView 계약 B§ 정의 행(#47, 2026-09-28)을 고친다.
- 계약 · ADR: 「thumbnail 이미지 전달 방식」 Pending에 「생산자 case, 선택 후보만, IncidentClip 경유」를 반영한다.
- 테스트: 발급 성공 · clip 밖 · span 0 / 2개 이상 · `resolve_frame` 거부 → `null`, 재선택 시 이전 후보 값이 남지 않음.

## 4. case 쪽 구현 (2026-10-29, 2026-10-31 발급 위치 반영)

- `case/preview_frame.py` — 위치 해석 `preview_frame_position(clip, span, representative_ms)`(결정 3 · 4 · 6, `(media_stream_ref, source_offset_sec)` 또는 `None`), 투영용 `current_preview_frame_ref`(선택 후보 · 현재 세대의 가장 나중 성공 clip 값).
- `reflection.py` — 성공한 `INCIDENT_CLIP_BUILD` 반영 때 결과의 `preview_frame_ref`를 그 clip job의 `observation_outcomes[*].preview_frame_ref`에 남긴다. 값이 없거나 키가 없는 결과(이전 형식)는 `None`이고, 반영 중에 발급하지 않는다. 상태 필드는 새로 만들지 않았다.
- `view.py` — `preview_ref`는 저장한 값, 없으면 선택 후보 `thumb_ref`. Search 썸네일은 실제 경로에서 늘 `null`이라 fallback은 fixture에서만 값이 있다.
- 테스트 `tests/case/test_evidence_preview_frame.py` — 위치 해석(성공 · 파일 경계 span · clip 밖 · span 0 / 2개 · 다른 timeline · revision · 대표 시각 없음), 반영(저장값 투영 · `null` · 키 없음 · notice 없음 · 판독 후속 발주 유지), 재선택(A→B→A).
- **handler 쪽 발급은 아직 없다.** 그래서 지금 develop Worker에서 근거 장면은 그대로 `null`이다. 남은 것은 아래 5번이다.

## 5. 남은 확인

- **handler 발급(Runtime · Recording, 정철원).** 발급 위치는 ②로 정했다(2026-10-30) — `INCIDENT_CLIP_BUILD` handler가 입력 connection을 반환한 뒤 clip을 만들고, `preview_frame_position`으로 위치를 받아 recording `resolve_frame(STREAM_POSITION)`으로 발급해 `incident_clip_result` payload의 `preview_frame_ref`(발급 불가면 `null`)로 싣는다. 발급 불가 · 모호한 위치는 `null`로 두고 clip 성공 · 판독 발주는 유지하며, Runtime · DB · 취소 오류는 삼키지 않는다. payload 필드 이름과 reader 호환의 정확한 모양은 Runtime 후속 구현에서 함께 맞춘다. 다중 VIDEO clip(#486 Inline 1)과 같은 handler라 순서를 맞춘다. T2 안 발급(①)과 별도 job(③)은 고르지 않았다.
- Fine 시각을 원본 시각으로 환산할 공개 값(위 결정 4).

## 6. 고르지 않은 것

| 안 | 고르지 않은 이유 |
| --- | --- |
| Search가 Coarse 후보마다 `thumbnail_ref` 생산 | Search는 `FrameRef`를 발급할 수 없고, 후보 전체 디코딩은 Coarse 상한을 압박한다(#446 4번) |
| case가 모든 후보에 썸네일 발급 | 화면에 그리는 것은 선택 후보 하나다. clip이 없는 후보는 `STREAM_POSITION` 위치를 정할 공개 경로가 없다 |
| `TIMELINE_POSITION`으로 대표 시각 바로 조회 | 새로 발급하지 않아 `FRAME_NOT_FOUND`다(결정 3) |
| CaseView 조회 때 발급 | 읽기 경로에서 디코딩하면 조회마다 비용이 들고 결과를 저장할 곳이 없다(결정 5) |
| T2 반영 안에서 발급(`RecordingFacts` 확장) | T2는 DB transaction 안이다. 디코딩 · 저장 중 connection을 잡으면 Runtime의 「무거운 작업 중 connection 반환」 경계와 부딪힌다(정철원 2026-10-30) |
