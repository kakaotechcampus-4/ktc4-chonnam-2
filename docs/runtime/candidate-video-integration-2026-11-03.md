# 후보 영상과 develop 통합 검증 (2026-11-03)

초기 develop 통합은 `ba8e21ea57a400db1820594f5b50303bbf7df454`, PR 준비 시 다시 반영한 develop은 `465671643d772847d8eac60ed083663ccbcf6bb7`이다. #525의 Web 썸네일과 #532의 Case 후보 frame 저장·투영을 유지한다. 사용자 요청으로 PR을 준비하며 배포는 범위 밖이다. 원래 변경은 `.omo/evidence/candidate-video-integration/before.patch`, `untracked-before.tar`, 보존 stash에 남아 있다.

## 변경

- 카드의 기존 FrameSlot·이미지 오류 처리·준비 중/없음 문구를 유지한다. 영상 기능이 연결되면 같은 자리에 CandidateVideo를 사용하며, 선택 후보의 표지는 `thumb_ref ?? evidence.preview_ref`다. 표지가 실패해도 영상 요청은 가능하다.
- 단일 후보도 결과·상황 응답 대기·미관찰·실패 화면에서 영상을 요청하고 재생한다. 다른 후보 버튼은 실제 다른 후보가 있을 때만 보인다. 재생 요청은 재선택과 분리한다.
- 상황 응답 대기의 고정 480px 이미지 열은 기존 960px breakpoint 아래에서 한 열로 접힌다. 실제 375px 브라우저에서 관측한 가로 넘침을 수정했다.
- 최신 Recording의 chunk/metadata 및 임시 파일 transaction context를 보존했다. PR 준비 시 최신화에서는 병합된 #527의 실제 helper·selector·issuer와 영상 registry를 함께 조립한다.

## 초기 통합 실행 결과

| 검증 | 결과 |
| --- | --- |
| Web 전체 | 15 files, 269 passed |
| 후보 영상·#532 썸네일·API·Recording·registry 집중 테스트 | 93 passed |
| Case/Worker/API 관련 회귀 | 1547 passed, 636 skipped, 1 failed |
| 실패의 변경 없는 develop 재현 | `test_worker_media_real_report_and_plate_export`: 동일한 `export encoding failed` |
| Web TypeScript·production build | PASS |
| Runtime ruff·mypy linux/win32 | PASS, 89 files |
| 경계 검사·git diff 공백 검사 | PASS |
| MySQL strict 사전 점검 | `DAESINGO_REQUIRE_MYSQL=1 requires DAESINGO_MYSQL_URL` |

관련 회귀의 skip은 주로 MySQL opt-in이며 MySQL 성공으로 집계하지 않았다. 첫 관련 회귀 실행은 120초 도구 제한으로 중단됐다. 별도 추적 프로세스로 다시 실행한 최종 결과만 위 표에 집계했다.

## 실제 브라우저·TCP 증거

빌드된 Web을 실제 TCP FastAPI에서 제공하고 실제 Case command → preview handler → Recording/FFmpeg → 결과 반영 → 영상 HTTP를 실행했다. 저장소는 메모리이며 handler는 API와 같은 OS process의 별도 thread에서 실행했다. MySQL·독립 Worker process·재시작 내구성·Caddy 경유의 증거가 아니다. 외부 AI를 호출하지 않고 합성 영상과 현재 세대 후보를 seed했다. 결과/상황 응답 화면의 evidence/package는 canonical fixture를 화면 투영에 사용했다. 실제 신고자료 생성 완료를 검증한 것으로 해석하지 않는다.

- 후보 0/1/2/3/5개를 별도 QA 서버에 구성했다. 카드 수를 그대로 유지하고 5개에서는 요청 버튼이 3개였다.
- 단일 후보를 native controls에서 Space로 재생했다. duration 3초, currentTime 증가, 1.8초 seek, readyState 4를 확인했다. 선택 candidate_1 및 selection_rev 1은 그대로이고 생성은 1회였다.
- rank 2 재생 중 rank 3을 재생하면 rank 2가 정지했다. 각각 1회 생성됐다. media 404를 rank 2에 주입하고 다시 불러오기로 복구해도 생성 횟수와 선택은 변하지 않았다.
- 실제 HTTP Range `bytes=0-31`은 206, `Content-Range: bytes 0-31/342455`, body 32bytes였다.
- 단일 후보 네 화면 × 세 폭(375/768/1280px) 12장, 후보 5개 × 세 폭 3장, 오류 1장을 캡처했다. 정상 화면 15개 모두 가로 넘침이 없다. Classic scrollbar를 제외한 full-page PNG 폭은 viewport보다 15px 작다.
- 처음 상황 응답 375px에서는 scrollWidth 654였다. 임시 CSS 수정으로 360, 제거하면 654로 돌아갔다. 실제 CSS 수정·production build 후 최종 capture를 다시 만들었다.

로그·합성 영상 서버·JSON·PNG·파일 해시는 `.omo/evidence/candidate-video-integration/`에 있다. browser-qa.json의 `singleInitial`은 수정 전 진단이다. 최종 증거는 `singleFinal`과 `multipleFinal`이다.

## 남은 환경 검증

Docker Desktop 시작을 시도했으나 inference manager의 `dockerInference` socket 초기화 오류로 backend가 종료됐다. 로그는 `%LOCALAPPDATA%/Docker/log/host/com.docker.backend.exe.log`에 있다. 전역 설정·Docker 데이터·runtime socket은 변경하거나 삭제하지 않았다.

실제 MySQL, API/Worker 독립 process, T1/T2 장애·재시작, Caddy 경유 Range, live provider와 실제 사용자 영상은 NOT_RUN이다. 필수 항목은 `docs/superpowers/plans/2026-11-03-candidate-video-real-test-plan.md`에 남아 있다. 이번 증거만으로 실제 통합 전체 완료나 배포 준비 완료를 선언하지 않는다.

## PR 준비 시 최신화와 최종 실행

기준 develop은 `465671643d772847d8eac60ed083663ccbcf6bb7`이다. #527 프레임 발급과 새 영상 handler를 함께 조립하고, 최신 결과 화면 복사 피드백도 유지했다.

| 최종 검증 | 결과 |
| --- | --- |
| Web 전체 | 15 files, 270 passed |
| 영상·썸네일·production 조립·frame/clip 입력/handler·API 집중 회귀 | 210 passed |
| Case/Worker/API 관련 회귀 | 1603 passed, 656 skipped, 1 failed |
| 위 실패의 변경 없는 develop 재현 | 동일 report/plate export의 `export encoding failed` |
| production build·Runtime ruff/mypy·경계·공백 | PASS, mypy linux/win32 91 files |

시각 검토에서 375px 신고문과 이동 안내의 폭이 부족한 문제를 발견했다. 720px 아래에서 행·이동 안내를 한 열로, 복사 버튼을 본문 아래로 배치했다. 수정 전 본문 폭 27.5px/높이 2180px, 임시 수정 후 288px/183px, 수정 제거 시 원래 문제 재현을 확인했다. 최종 브라우저에서는 본문 폭 303px/높이 183px, 이동 안내 폭 287px이다.

최종 증거는 `pr-browser-qa.json`이다. 새 PID의 TCP 서버에서 후보 0/1/2/3/5개와 요청 버튼 0/1/2/3/3개, native 재생·seek·206 Range·영상 간 정지·404 복구·각 후보 1회 생성·선택 불변을 재확인했다. 총 16장을 다시 촬영했다. 문서 높이에 맞춰 viewport 높이를 확장해 375/768/1280px 폭을 정확히 유지하고 마지막 버튼이 capture에 온전히 들어오는지 확인했다. 초기 하단 잘림은 해소됐으며 초기 PNG 폭 설명은 최종 파일에 적용하지 않는다.

MySQL·독립 Worker process·재시작·Caddy·사용자 영상/live provider는 NOT_RUN이다. 이전 revision 또는 사용량 한도로 중단된 독립 리뷰를 최종 revision의 PASS로 재사용하지 않는다. PR에는 완료된 검증과 남은 항목을 구분한다.
