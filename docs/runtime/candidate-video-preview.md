# 후보 영상 미리보기 구현·검증

2026-11-02에 구현을 승인받았고, 아래 초기 구현과 검증은 2026-11-03의 로컬 기록이다. 당시 `codex/candidate-video-preview` 브랜치에서 검증했으며 그 작업에서는 커밋·푸시·PR 변경을 하지 않았다.

**AWS 공개 검수.** 2026-11-10 배포 `61d9b7ea`에서 후보 미리보기를 켰다. 후보 두 개를 각각 재생·탐색했고, 다른 세션의 일반 영상 URL과 Range 요청은 모두 `404`를 반환했다. 공개본은 한 번에 한 후보 영상의 재생을 지원한다. [최종 AWS 공개 배포](a1-public-readiness.md#2026-11-10-최종-aws-공개-배포)

## 동작

- 현재 세대 rank 1~3의 후보 구간을 첫 영상 요청 때 생성한다. 후보 0/1/2/3/5개를 검증했고 빈 카드·rank 4 보충은 없다.
- 영상 준비/재생과 후보 선택은 별도다. 미리보기 job은 Fine/OCR/export/선택 revision을 변경하지 않는다.
- 후보·세대·span에 묶인 진행 중/성공 요청을 재사용한다. 실패는 해당 카드에서만 재요청한다.
- 기존 Recording 생성 기능을 재사용하고, 저장 MP4를 현재 Case 및 원본 소유권 확인 뒤 inline/Range로 조회한다. 기존 다운로드와 thumb_ref 의미는 유지했다.
- native controls, 인라인 재생, 한 화면 한 영상, 준비·실패·브라우저 오류와 재시도 UI를 제공한다.
- CaseView v1.12 호환 확장 및 command/HTTP/디자인 명세를 함께 갱신했다.

## 확인한 결과

| 검사 | 결과 |
| --- | --- |
| 최종 기능·배포 등록 검사 | 68 passed |
| Web 전체 | 15 files / 254 passed |
| TypeScript·Vite production build | 성공 |
| Runtime ruff · mypy Linux/win32 | 성공 (89 files) |
| 모듈·계약 경계 · diff whitespace | 성공 |
| Python 신규 Worker LSP | 오류 없음 |
| 실제 브라우저 | rank 2/3 생성·재생, 1.8초 seek, 이전 영상 정지, 개별 오류/복구 확인 |
| 반응형 | 375/768/1280px, 가로 넘침 없음, 두 독립 시각 검토 PASS |
| live curl | Range 206/32 bytes, foreign ref 404 |
| 생성 재사용·선택 유지 | 후보 2/3 각각 1회, selected candidate 1 · selection_rev 1 유지 |

전체 Python suite 첫 실행은 13,792 passed / 26 failed / 1,229 skipped였다. 신규 handler 등록의 기대 목록 누락 1건은 수정하고 최종 focused 검사에 포함했다. 전체 suite의 재실행 성공을 주장하지 않는다.

남은 실패 중 아래 24건은 변경 전 HEAD 사본에서도 동일하게 재현됐다.

- `tests/common/db/integration/test_migration_gate.py::test_actual_report_rejects_each_missing_migration_check`: CI MySQL gate evidence 환경변수 없음.
- `tests/deploy/test_ec2_deploy.py`의 21개 symlink 시나리오: Windows symlink 권한(WinError 1314).
- `tests/recording/test_exports.py::test_report_preserves_clip_and_stamps_requested_value[True-2026-06-20T14:19:56+09:00]`, `tests/worker/test_media_paths.py::test_worker_media_real_report_and_plate_export`: 기존 FFmpeg 각인/export 경로 실패.

`tests/api/test_sources.py::test_receive_abort_sends_no_status_and_never_registers[disconnect]`는 첫 전체 실행과 첫 baseline 실행에서 실패했고 후속 baseline 실행에서는 통과했다. 업로드 연결 종료의 기존 간헐 실패로 기록하며 이 작업에서는 변경하지 않았다.

## 검증 한계·검토 결정

- MySQL 연결 설정이 없어 실제 MySQL 저장·재시작·원격 CI는 미검증이다. 실제 브라우저 QA는 메모리 저장소를 사용하며 Case command, Worker 입력/handler, Recording/FFmpeg, HTTP router, Web은 실제 구현을 통과했다.
- TypeScript LSP는 설치돼 있지 않아 추가 설치 없이 TypeScript compiler/build로 확인했다.
- 새 탐색 이후 이전 preview job을 강제로 취소하는 기능은 추가하지 않았다. 기존 작업은 끝날 수 있으나 이전 세대/span 결과와 ref는 새 카드에 투영/조회되지 않는다.
- Code review의 배포 registry 불일치는 기대 목록 수정과 focused RED→GREEN으로 해결했다. 두 visual review의 최종 결과는 PASS다.
- 실제 사용자 영상·live AI provider·배포는 실행하지 않았다. 신고용 결과 영상 미리보기 #519는 별도 범위다.

원시 로그·스크린샷·manual-qa.json·검토 보고서는 `.omo/evidence/candidate-video/` 및 `.omo/evidence/candidate-video-preview-*.md`에 로컬 보존했다.

## 2026-11-03 develop 통합 검증

2026-11-03 develop의 #525·#532를 보존하고 단일 후보 재생 입구를 추가했다. 변경·최종 결과·MySQL 제한은 [통합 검증 기록](candidate-video-integration-2026-11-03.md)을 따른다. 이전 수치와 합산하지 않는다.
