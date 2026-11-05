# 후보 영상 미리보기 — `candidates[].video_preview` · `CANDIDATE_VIDEO_PREVIEW`

> **상태: 결정 · 구현([PR #554](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/554))** · CaseView 계약 `case-view/v1.12`
>
> **결정 · 승인:** 2026-11-02 서어진(당시 case 인수 담당) 결정 · 2026-11-04 김준영(PM) 제품 흐름 승인([#554 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/554#issuecomment-6633990450)) — 「후보별 영상 미리보기 재생 및 단일 후보 진입 흐름 승인. 최종 머지는 남은 보완 및 검증 완료 후」
>
> **관련:** 정지 이미지(근거 장면 · 상위 3개 후보 썸네일)는 `evidence-preview-frame.md`(#446 · [PR #459](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/459), 상위 3개는 #523 §7). 이 문서는 그 위에 영상 재생을 더한다.

## 1. 문제

후보 비교 화면은 후보마다 정지 이미지 한 장(`thumb_ref`)만 보여 준다. 사용자는 그 구간에서 사건이 실제로 일어났는지 영상으로 보지 못한 채 후보를 고른다. 후보가 하나뿐인 결과, 상황 확인, 위반 미관찰, 실패 화면에서도 영상을 볼 길이 없다.

## 2. 결정

#532의 정지 이미지는 poster로 유지하고, 후보 비교에서 영상을 재생한다.

- 현재 후보 목록의 rank 1~3만 대상이다. 0/1/2개면 있는 만큼, 빈 카드와 4위 보충은 없다. stale·구간 없음은 카드에 재생 불가를 표시한다.
- 첫 재생은 `REQUEST_CANDIDATE_VIDEO_PREVIEW {candidate_id}` command다. 현재 세대·후보 span·원본 stream 선택을 고정해 `CANDIDATE_VIDEO_PREVIEW` job을 발주한다. 기다리는 요청과 성공 결과는 재사용한다. 실패는 사용자가 다시 요청할 수 있다.
- preview는 선택·selection revision·상황 응답·신고자료와 무관하다. Fine/OCR/export와 READY gate를 실행하지 않는다. 여러 후보의 미리보기 작업은 서로 supersede하지 않는다.
- 후보 구간은 Search가 준 span 그대로다. Recording의 `resolve_span`과 `build_incident_clip`을 쓰며 디코딩 중 DB connection을 보유하지 않는다. 자동 인프라 재실행의 T1 이전 재인코딩은 기존 Worker 정책을 따른다.
- `candidates[].video_preview`는 `{status, clip_ref}`다. status는 `NOT_REQUESTED | PREPARING | READY | FAILED | UNAVAILABLE`. rank 밖·stale·span 없음·세대 없음은 UNAVAILABLE. clip_ref는 READY에서만 문자열이다. 결과는 후보·현재 세대·span으로 묶고 세대 변경 후 이전 ref를 투영하지 않는다.
- 결과가 늦게 도착해도 preview 결과만 정산한다. 선택 후보의 후속 관찰에 섞지 않는다. 영상을 보기만 해서는 신고자료가 변하지 않는다.
- `GET /cases/{case_id}/candidate-videos/{clip_ref}`는 현재 CaseView의 READY preview에 속한 ref만 허용한다. Recording 공개 `open_incident_video`으로 저장된 MP4만 읽으며 재생성하지 않는다. 소유한 원본 lineage도 확인한다.
- HTTP는 `video/mp4`, `inline`, `private, no-store`, `Accept-Ranges: bytes`를 반환한다. 단일 closed/open/suffix byte range는 206, 불가능한 range는 416이다. 지원하지 않는 multipart/잘못된 문법의 Range는 무시하고 200으로 응답한다. transaction·저장 stream은 응답 전 닫는다. 기존 다운로드 API는 변경하지 않는다.
- Web은 native video controls·playsInline·preload=metadata를 사용한다. 자동 재생은 하지 않는다. 재생 준비 버튼과 「이 장면으로 다시 준비」는 분리한다. 한 영상이 재생되면 같은 비교 화면의 다른 영상은 멈춘다. 생성 실패·브라우저 재생 실패는 카드 안에 안내하고 다른 후보는 계속 쓸 수 있다.
- 후보 preview job도 running_jobs에 포함해 기존 polling을 사용하지만 신고자료 진행 화면 전환과 선택 제한에서는 제외한다.
- **READY는 「만들어 저장까지 끝났다」는 뜻이다. 「지금 읽을 수 있다」는 뜻이 아니다(2026-11-05 유소연, §2-1).**

### 2-1. 저장된 미리보기가 손상된 경우 (2026-11-05)

[서어진 실제 통합 검증](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/554#issuecomment-6629742662) RC-07에서 저장 chunk가 없어지거나 변조되면, 다운로드는 404 `http.ref_unavailable`인데 view는 READY로 남는다는 것을 찾았다. 다시 요청해도 READY라 새 job을 만들지 않는다.

**그대로 둔다.**

- `video_preview.status`는 preview job 결과(`SUCCEEDED` + `incident_clip_ref`)에서 투영하고, 저장소를 읽지 않는다. 신고용 영상(`package.artifact_ref`)과 번호판 이미지(`package.plate_image_ref`)도 같다 — ReportPackage에서 투영하고, 저장소가 손상되면 ref는 남고 `/assets`가 404 `ref_unavailable`이다.
- 저장된 clip이 없어지는 것은 사용자 흐름이 아니라 운영 사고다. 런타임 cleanup(`common/storage/cleanup.py`)은 업로드 staging과 recording 임시 파일만 지우고, MySQL chunk에 저장된 clip은 지우지 않는다.
- 손상되면 그 카드만 「영상을 재생할 수 없어요」가 된다. 신고자료 · 선택 · 다른 후보에는 영향이 없고, 자동으로 다시 만들지 않는다(RC-07에서 확인).
- 테스트 계획의 「가짜 READY 없음」은 「만들지 못했는데 READY인 경우는 없다」로 읽는다.

**고르지 않은 것**

| 안 | 고르지 않은 이유 |
| --- | --- |
| READY에서도 다시 요청을 받아 새 job을 만든다 | case는 재생 실패가 저장소 손상인지 일시 네트워크 · 브라우저 실패인지 구분할 수 없다. 재생 실패 때마다 다시 인코딩하게 된다. web 변경도 필요하다. |
| view를 만들 때 저장소를 확인한다 | web은 `GET /view`를 2초마다 부른다. CaseView는 job 결과만 투영한다는 원칙과도 맞지 않는다. |
| API가 읽기에 실패하면 case에 FAILED로 기록한다 | GET에 부작용이 생기고, case 행 잠금이 command · T2 반영과 부딪힌다. |

**재검토 조건:** 운영에서 손상이 실제로 보일 때, 또는 저장된 preview clip을 지우는 정책(만료 등)이 생길 때. 그때는 web이 `ref_unavailable`일 때만 「다시 준비」를 보이고 case가 READY에서도 다시 요청을 받는 안을 다시 본다.

## 3. 고른 이유

- **사용자가 사건 구간을 직접 보고 고른다.** 정지 이미지 한 장으로는 그 구간에 사건이 있는지 확인하기 어렵다. PM 승인 이유도 같다 — 「기존 대표 이미지 중심의 후보 확인 방식보다 사용자가 실제 사건 구간을 직접 확인하고 후보를 선택할 수 있다」.
- **보기와 고르기를 나눈다.** 재생은 선택 · 신고자료를 바꾸지 않으므로, 영상을 여러 번 봐도 Fine · 판독 · export가 다시 돌지 않는다. 후보를 바꾸는 길은 여전히 「이 장면으로 다시 준비」 하나다.
- **요청한 후보만 만든다.** 사용자가 「영상 보기」를 누른 후보만 만들고, 만든 것은 재사용한다.

## 4. 고르지 않은 것

| 안 | 고르지 않은 이유 |
| --- | --- |
| 썸네일만 둔다(지금까지) | 정지 이미지로는 사건 유무를 판단하기 어렵다(§3). 썸네일은 버리지 않고 poster로 남긴다 — `evidence-preview-frame.md` §7의 상위 3개 썸네일과 같은 것이다. |
| 신고용 clip(`INCIDENT_CLIP_BUILD`)을 재사용한다 | 신고용 clip은 선택 후보 하나에 대해 Fine 뒤에만 만들어진다(`incident-clip-observation-input.md`). 고르기 전에 여러 후보를 비교하는 데 쓸 수 없다. 신고용 영상(`REPORT_VIDEO_EXPORT`)은 상황 응답 뒤에 시각을 새겨 따로 만드는 다운로드 파일이라 더 늦다(`report-video-export.md`). |
| 후보 전체로 넓힌다 | 다른 후보 화면용 썸네일을 상위 3개로 정한 #523과 범위를 맞춘다. 4위 이하로 보충하지 않는 것도 썸네일과 같다. |

## 5. 리뷰 후속

[#554](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/554) 리뷰에서 나온 것이다. 정한 것 · 고친 것 · 남은 것을 항목마다 적는다.

- **미리보기가 쓰는 stream 기준(case) — 정함(2026-11-05 서어진).** 미리보기는 Coarse 후보 구간을 보여 주는 것이고, 다중 카메라를 지원한다고 주장하지 않는다. 지금 case 타임라인에서는 미리보기의 stream 목록이 곧 한 카메라 체인이다.
  - 원본 하나에 VIDEO가 2개 이상이면 `video_stream_ref`가 없고, 타임라인을 만들기 전에 막힌다(`timeline_source.py`, spec §3-1 한계 4).
  - 원본마다 placement 하나에 ref 하나를 둔다. `request_preview`는 그 ref 전부를 넘기므로 Recording resolver의 「placement마다 VIDEO ref 하나」를 늘 만족한다([정철원 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/554), 11/4).
  - 전방 · 후방을 별도 파일로 올리면 앞뒤로 이어 붙는다(spec §3-1 한계 1). Fine · 신고용 clip도 같은 타임라인이라 미리보기만의 한계가 아니다. 신고용 clip의 Fine provenance 대조는 Fine 이후에만 할 수 있고, 미리보기는 Fine 전이라 하지 않는다.
  - #510 Recording 정렬로 같은 시각에 여러 카메라가 놓이게 되면, Case가 고른 한 카메라 체인을 발주 입력 · 현재성 검사 · handler에 함께 넘기도록 다시 본다.
- **recording · API:**
  - `open_incident_video`의 `OSError` 500 — 고침(`4f343671`): 파일 부재 · 권한 오류도 경로를 숨긴 `UNAVAILABLE` → HTTP 404 `http.ref_unavailable`.
  - 세대가 바뀐 뒤 도착한 preview job — 고침(`68bd8886`): `FAILED / RUNTIME_PREVIEW_NOT_CURRENT`로 기록해 진짜 오류(`RUNTIME_HANDLER_ERROR`)와 구분한다. 같은 세대 안의 입력 불일치는 그대로 `RUNTIME_HANDLER_ERROR`다([서어진 실제 통합 검증](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/554#issuecomment-6629742662) 발견 2).
  - Range 요청마다 share lock 안에서 MP4 전체 적재 — 남음. 동시 Range와 같은 Case command · T2의 완료 · 잠금 해제, 오류 시 연결 반환을 실제 MySQL에서 확인해야 한다.

## 6. 검증

후보 0/1/2/3/4+, stale/구간 없음, 동시 후보 요청, 중복·실패 후 재요청, generation/span 변경, T2 중복 전달, 선택 및 후속 job 불변, owned/foreign/ref unavailable, byte Range, 실제 브라우저 재생·seek·한 개만 재생. 실제 MySQL · TCP API 프로세스 · Caddy · 실제 영상 검증은 `docs/runtime/candidate-video-mysql-integration-2026-11-04.md`.
