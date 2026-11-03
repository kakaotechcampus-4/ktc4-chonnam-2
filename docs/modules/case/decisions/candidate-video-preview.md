# 후보 영상 미리보기

2026-11-02 사용자 승인. #532의 정지 이미지는 poster로 유지하고 후보 비교에서 영상을 재생한다.

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

검증: 후보 0/1/2/3/4+, stale/구간 없음, 동시 후보 요청, 중복·실패 후 재요청, generation/span 변경, T2 중복 전달, 선택 및 후속 job 불변, owned/foreign/ref unavailable, byte Range, 실제 브라우저 재생·seek·한 개만 재생.
