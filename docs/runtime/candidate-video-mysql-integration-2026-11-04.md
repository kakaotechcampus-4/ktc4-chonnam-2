# 후보 영상 실제 MySQL 통합 검증 — 2026-11-04

[실제 통합 테스트 계획](../superpowers/plans/2026-11-03-candidate-video-real-test-plan.md)의 항목을 실제 MySQL로 실행한 결과다. [11/3 기록](candidate-video-integration-2026-11-03.md)은 메모리 저장소였고, 이 기록이 그 공백을 채운다. **배포 준비 완료를 뜻하지 않는다** — 아래 NOT_RUN을 보라.

## 환경

- 소스: PR #554 `dbf792eb`(develop `46567164` 이후 반영) + 이 기록의 테스트 커밋
- Windows 11 호스트 · Python 3.12(uv) · FFmpeg 9.0.1 · MySQL **8.4.13**(Docker, 이번 실행 전용 컨테이너) · Caddy 2.8.4(Docker) · Chromium 156(Playwright 1.64.1)
- 외부 AI는 기존 `worker_peer` 오프라인 HTTP 응답만 대체한다. MySQL · Case 저장소 · enqueue/claim · preview handler · Recording/FFmpeg · T1/T2 · API loader는 실제다.
- 계획은 Linux 호스트를 주 환경으로 둔다. 이번 실행은 Windows 호스트 + Linux MySQL 컨테이너이고, 정식 MySQL 게이트는 Linux CI에서 확인한다.

## 결과

새 테스트: `tests/worker/test_candidate_video_mysql.py`(20) · `tests/worker/test_candidate_video_process_mysql.py`(2). 실제 MySQL에서 22/22 통과했다. 시나리오 13개(`candidate_video` role)는 `scripts/check_mysql_test_report.py`의 필수 목록에 등록했다.

| ID | 결과 | 근거 |
| --- | --- | --- |
| DB-01 | PASS | 후보 0/1/2/3/5 → 카드 수 그대로, 영상 대상 0/1/2/3/3 |
| DB-02 | PASS | rank 2·3 요청마다 preview job 1개. 고정 입력의 후보 · 세대 · span · stream이 Case와 일치 |
| DB-03 | PASS | rank 4 · 5 · 알 수 없는 후보 요청은 거부되고 job 0개 |
| DB-04 | PASS | 준비 중 재요청, READY 뒤 재요청, T2 재전달 모두 job · 인코딩 증가 0 |
| DB-05 | PASS | rank 2 · 3을 함께 요청해도 둘 다 완료하고, clip_ref가 서로 다르다 |
| DB-06 | PASS | 새 연결에서 PREPARING → READY. produced 2개, 저장 MP4 ffprobe 성공 |
| DB-07 | PASS | `case_rev` · `running_jobs` · `video_preview`를 뺀 CaseView 전체가 요청 전과 같다 |
| DB-08 | PASS | 다른 후보 재선택으로 Fine이 대기 중일 때 preview 요청 202. preview 완료 뒤에도 Fine은 그대로 대기하다 정상 완료되고, 선택 후보의 clip build가 평소대로 발주된다. preview가 만든 후속 job 0 |
| DB-09 | PASS | 두 원본 파일 경계를 넘는 구간: resolution span 2개, provenance가 요청 구간과 일치, 전체 decode 성공 |
| RC-01 | PASS | API 프로세스를 종료하고 새 PID로 띄워도 같은 SHA-256, job · produced 수 그대로 |
| RC-02 | PASS | T1 전에 Worker 종료 → lease 만료 → 새 attempt가 1회 재인코딩(허용) → 재전달에서 추가 0. attempts `(1, STALE), (2, SUCCEEDED)`. 같은 흐름을 **별도 OS 프로세스 Worker를 인코딩 중 강제 종료**해서도 확인했다(새 PID가 READY로 마무리) |
| RC-03 | PASS | T1 rollback(deadlock 주입)과 COMMIT 응답 손실(`CommitResponseProxy`, 응답 1회 유실 확인) 모두 인코딩 1회 · produced 1개 · READY |
| RC-04 | PASS | T2 rollback · T2 중단 후 redelivery: 인코딩 1회, 반영 1회, READY |
| RC-06 | PASS | preview 대기 중 `EDIT_HINT`로 새 세대 발주(화면 출구 조건만 테스트에서 열었다). 이전 job은 디코드 전에 거부돼 FAILED, 이전 후보 · ref가 새 view에 없다. 새 Coarse 뒤 새 rank 2 preview는 READY |
| RC-07 | 부분 | 저장 chunk 소실 · 변조 → 404 `http.ref_unavailable`, 실제 연결 KILL · pool 고갈 → 503 `http.dependency_unavailable` 뒤 다음 요청 200, 원본 파일 소실 → 그 카드만 FAILED · 명시적 재요청 가능. 자동 재생성 0. **단 bytes가 손상돼도 view는 READY로 남는다**(아래 관찰) |
| RC-05 | PASS | 후보 2 생성 실패는 그 카드만 FAILED, 후보 3 READY, 후보 2 명시적 재요청은 새 job으로 READY. 신고자료 그대로 |
| HTTP-01 | PASS | 실제 TCP API 프로세스: `video/mp4` · `inline` · `private, no-store` · `Accept-Ranges: bytes` |
| HTTP-02 | PASS | 닫힌 · 열린 · 접미 · 넘치는 범위는 206, 범위 밖 · 역순은 416, 잘못된 형식 · multipart · If-Range는 전체 200. Caddy 경유에서도 같은 바이트 · 206 · 416 |
| HTTP-03 | PASS | 다른 Case · 알 수 없는 ref · 잘못된 case id는 404이고 경로 · traceback · 영상 바이트가 없다 |
| HTTP-04 | PASS | 반복 Range · 전송 중단 뒤 다시 재생 가능, GET으로 job · produced 증가 0 |
| UI-01 | PASS | 빌드한 Web을 Caddy로 서비스: 후보 3개는 카드 3 · 영상 보기 3, **후보 1개는 상황 응답 뒤 결과 화면 「동영상」 칸에서 재생 입구** |
| UI-02 | PASS | 영상 준비 중 → native 재생(currentTime 증가) → seek 완료. 후보 화면에 머문다 |
| UI-03 | PASS | 키보드(Enter)로 3번 요청. 3번 재생 시 2번 정지. 선택은 바뀌지 않음(전후 `(1, True)`) |
| UI-04 | PASS | 첫 생성 실패 → 그 카드만 「영상을 준비하지 못했어요.」, 3번 영상 보기 · 선택 버튼은 사용 가능 → 「다시 준비」로 재생. 브라우저 media 요청 1회 차단 → 「영상을 재생할 수 없어요.」 → 「다시 불러오기」로 재생(새 job 0). 콘솔 오류는 일부러 차단한 요청 1건뿐 |
| UI-05 | PASS | 새 탭에서 저장된 READY 영상 재생, preview job 수 그대로 |
| UI-06 | PASS | 375 · 768 · 1280px 가로 넘침 없음, 콘솔 오류 0 |

## 관찰

- Caddy의 `header Cache-Control "no-store"`가 API 값에 덧붙어 응답이 `no-store, private, no-store`가 된다. 캐시 금지 의미는 유지되므로 바꾸지 않았다.
- **저장 bytes 손상 뒤의 READY:** clip 내용이 소실 · 변조돼도 preview 상태는 Job 결과에서 투영되므로 READY로 남는다. 사용자는 「영상을 재생할 수 없어요」만 보고, 재요청은 READY라 새 job을 만들지 않는다. 운영 저장소 손상은 드물지만 계획의 「가짜 READY 없음」 기준에는 걸린다. case 쪽 판단이 필요하다. → 후속: READY 유지로 정함(`0aad403b`, `decisions/candidate-video-preview.md` §2-1).
- **세대가 바뀐 뒤 거부된 preview:** 실패 종류가 `RUNTIME_HANDLER_ERROR`라 진짜 오류와 로그에서 구분되지 않는다. 동작(디코드 전 거부, 화면 격리)은 맞다. → 후속: `RUNTIME_PREVIEW_NOT_CURRENT`로 구분(`68bd8886`).
- 합성 원본은 1초 · 64×48이라 미리보기는 0.2초다. 길이 · 화질 판단에는 쓰지 않는다.
- 이 브랜치의 Python 전체 회귀(api · case · worker · recording · readout · deploy)는 Windows에서 83 failed. 같은 83개가 깨끗한 develop에서도 실패한다(deploy 쉘 · FFmpeg export). 새 실패는 없다.

## 실제 영상 · 실제 AI 흐름 (Owner 승인, 상한 ₩500)

하네스 없이 운영 구성으로 1회씩 실행했다: 이번 실행 전용 DB에 migration → `python -m daesingo.api` 프로세스 → Worker `main()` 프로세스 → Caddy가 빌드한 Web과 `/cases*`를 함께 서비스 → 브라우저에서 업로드부터 진행. Search는 실제 `gemini-4-argon`(argon tenant)이다. Analysis는 baseline v1(480p · 4분), Incident는 현재 적용값(720p · CRF 20)이다.

**OCR만 대체했다.** 운영 PaddleOCR은 Docker 이미지의 모델 캐시(`/opt/daesingo/paddlex`)를 전제로 해서 이 PC에서는 Worker가 시작 단계에서 실패한다. 그래서 `main()`이 받는 `readout_provider_factory`로 테스트용 오프라인 판독기를 넣었다. 번호판 · 시각 값은 실제 판독 결과가 아니다.

| 영상 | 결과 | 확인한 것 |
| --- | --- | --- |
| `20260620_141927_EVT_1.avi`(실제 블랙박스, 신호위반) | 후보 1개, Fine OBSERVED → 결과 화면 | 결과 화면의 단일 후보 입구에서 미리보기 생성 · 재생(1280×720, 3.5초, 중간 탐색). 미리보기 뒤 후속 job 0 |
| `YT_0001_C09.mp4`(실선 차로변경) | 후보 2개, 1순위 NOT_OBSERVED → 위반 미관찰 화면 | 두 후보 미리보기 생성 · 재생(10초 · 5.5초, 720p), 1번 재생 시 2번 정지. 미리보기 2개는 Fine을 발주하지 않았다. 「이 장면으로 다시 준비」를 누른 뒤에야 Fine → clip → 판독이 이어지고 「신고자료를 준비하고 있어요」로 넘어갔다 |

- 실제 AI 비용: 입력 29,621 · 출력 2,112토큰 ≈ **₩114**(argon 단가). 미리보기는 AI를 호출하지 않는다.
- 두 실행 모두 브라우저 콘솔 오류 0.
- 미리보기 job은 6초 안팎에 끝났다(로컬 Windows, 짧은 영상). 긴 영상의 생성 시간은 재지 않았다.

## NOT_RUN

- 운영 PaddleOCR이 들어간 배포 이미지로의 실행(위 대체 참고), Linux 호스트 실행
- 5분 이상 실제 영상에서의 미리보기 생성 시간

증거(스크린샷 · 로그)는 로컬 `.omo/evidence/candidate-video-real/run1/`에 있고 커밋하지 않는다. 브라우저 구동 스크립트도 이번 실행에만 썼다.
