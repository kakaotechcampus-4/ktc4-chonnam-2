# 후보 영상 실제 MySQL 통합 검증 — 2026-11-04

[실제 통합 테스트 계획](../superpowers/plans/2026-11-03-candidate-video-real-test-plan.md)의 항목을 실제 MySQL로 실행한 결과다. [11/3 기록](candidate-video-integration-2026-11-03.md)은 메모리 저장소였고, 이 기록이 그 공백을 채운다. **실제 통합 전체 완료나 배포 준비 완료는 아니다** — 아래 NOT_RUN을 보라.

## 환경

- 소스: PR #554 `dbf792eb`(develop `46567164` 이후 반영) + 이 기록의 테스트 커밋
- Windows 11 호스트 · Python 3.12(uv) · FFmpeg 9.0.1 · MySQL **8.4.13**(Docker, 이번 실행 전용 컨테이너) · Caddy 2.8.4(Docker) · Chromium 156(Playwright 1.64.1)
- 외부 AI는 기존 `worker_peer` 오프라인 HTTP 응답만 대체한다. MySQL · Case 저장소 · enqueue/claim · preview handler · Recording/FFmpeg · T1/T2 · API loader는 실제다.
- 계획은 Linux 호스트를 주 환경으로 둔다. 이번 실행은 Windows 호스트 + Linux MySQL 컨테이너이고, 정식 MySQL 게이트는 Linux CI에서 확인한다.

## 결과

새 테스트: `tests/worker/test_candidate_video_mysql.py`(12) · `tests/worker/test_candidate_video_process_mysql.py`(1). 실제 MySQL에서 13/13 통과했다. 시나리오 7개(`candidate_video` role)는 `scripts/check_mysql_test_report.py`의 필수 목록에 등록했다.

| ID | 결과 | 근거 |
| --- | --- | --- |
| DB-01 | PASS | 후보 0/1/2/3/5 → 카드 수 그대로, 영상 대상 0/1/2/3/3 |
| DB-02 | PASS | rank 2·3 요청마다 preview job 1개. 고정 입력의 후보 · 세대 · span · stream이 Case와 일치 |
| DB-03 | PASS | rank 4 · 5 · 알 수 없는 후보 요청은 거부되고 job 0개 |
| DB-04 | PASS | 준비 중 재요청, READY 뒤 재요청, T2 재전달 모두 job · 인코딩 증가 0 |
| DB-05 | PASS | rank 2 · 3을 함께 요청해도 둘 다 완료하고, clip_ref가 서로 다르다 |
| DB-06 | PASS | 새 연결에서 PREPARING → READY. produced 2개, 저장 MP4 ffprobe 성공 |
| DB-07 | PASS | `case_rev` · `running_jobs` · `video_preview`를 뺀 CaseView 전체가 요청 전과 같다 |
| DB-08 | 부분 | preview 뒤 다른 kind의 job 상태와 수가 그대로다(Fine · OCR · export 추가 발주 0). Fine 진행 **중** 병행은 실행하지 않았다 |
| DB-09 | PASS | 두 원본 파일 경계를 넘는 구간: resolution span 2개, provenance가 요청 구간과 일치, 전체 decode 성공 |
| RC-01 | PASS | API 프로세스를 종료하고 새 PID로 띄워도 같은 SHA-256, job · produced 수 그대로 |
| RC-02 | PASS | T1 전에 Worker 종료 → lease 만료 → 새 attempt가 1회 재인코딩(허용) → 재전달에서 추가 0. attempts `(1, STALE), (2, SUCCEEDED)` |
| RC-03 | 부분 | T1 rollback(deadlock 주입): 인코딩 1회, READY. COMMIT 응답 손실(proxy)은 실행하지 않았다 |
| RC-04 | PASS | T2 rollback · T2 중단 후 redelivery: 인코딩 1회, 반영 1회, READY |
| RC-05 | PASS | 후보 2 생성 실패는 그 카드만 FAILED, 후보 3 READY, 후보 2 명시적 재요청은 새 job으로 READY. 신고자료 그대로 |
| HTTP-01 | PASS | 실제 TCP API 프로세스: `video/mp4` · `inline` · `private, no-store` · `Accept-Ranges: bytes` |
| HTTP-02 | PASS | 닫힌 · 열린 · 접미 · 넘치는 범위는 206, 범위 밖 · 역순은 416, 잘못된 형식 · multipart · If-Range는 전체 200. Caddy 경유에서도 같은 바이트 · 206 · 416 |
| HTTP-03 | PASS | 다른 Case · 알 수 없는 ref · 잘못된 case id는 404이고 경로 · traceback · 영상 바이트가 없다 |
| HTTP-04 | PASS | 반복 Range · 전송 중단 뒤 다시 재생 가능, GET으로 job · produced 증가 0 |
| UI-01 | PASS | 빌드한 Web을 Caddy로 서비스: 후보 3개는 카드 3 · 영상 보기 3, **후보 1개는 상황 응답 뒤 결과 화면 「동영상」 칸에서 재생 입구** |
| UI-02 | PASS | 영상 준비 중 → native 재생(currentTime 증가) → seek 완료. 후보 화면에 머문다 |
| UI-03 | PASS | 키보드(Enter)로 3번 요청. 3번 재생 시 2번 정지. 선택은 바뀌지 않음(전후 `(1, True)`) |
| UI-04 | NOT_RUN | 브라우저에서의 생성 실패 · 재시도. 같은 동작의 DB · Web 단위 검증(RC-05, `candidateVideo.test.tsx`)만 있다 |
| UI-05 | PASS | 새 탭에서 저장된 READY 영상 재생, preview job 수 그대로 |
| UI-06 | PASS | 375 · 768 · 1280px 가로 넘침 없음, 콘솔 오류 0 |

## 관찰

- Caddy의 `header Cache-Control "no-store"`가 API 값에 덧붙어 응답이 `no-store, private, no-store`가 된다. 캐시 금지 의미는 유지되므로 바꾸지 않았다.
- 합성 원본은 1초 · 64×48이라 미리보기는 0.2초다. 길이 · 화질 판단에는 쓰지 않는다.
- 이 브랜치의 Python 전체 회귀(api · case · worker · recording · readout · deploy)는 Windows에서 83 failed. 같은 83개가 깨끗한 develop에서도 실패한다(deploy 쉘 · FFmpeg export). 새 실패는 없다.

## NOT_RUN

- RC-03 COMMIT 응답 손실, RC-06 이전 세대 · span 변경 중 결과 도착, RC-07 원본 · clip bytes 소실 · DB 단절
- DB-08 Fine 진행 중 병행, UI-04 브라우저 실패 · 재시도
- API · Worker를 모두 독립 프로세스로 띄운 상태의 Worker 강제 종료(RC-02는 같은 프로세스 안의 종료 주입이다)
- 실제 블랙박스 영상 · live provider 전체 흐름, Linux 호스트 실행, 정식 MySQL 게이트(원격 CI에서 확인)

증거(스크린샷 · 로그)는 로컬 `.omo/evidence/candidate-video-real/run1/`에 있고 커밋하지 않는다. 브라우저 구동 스크립트도 이번 실행에만 썼다.
