# 기존 EC2 20개 영상 20분 제품 E2E 결과

**단회 제품 E2E PASS — 입력 검증, 선택 후보 OBSERVED, Package READY, 신고영상 다운로드·재생까지 확인했다.** 운영자가 제공한 서버 조회 출력과 브라우저 확인에 근거한다. 기존 원본 15개·26분 검증은 별도이며 [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)를 완료 처리하지 않는다.

[#452 결과 공유 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6690002906)에 같은 결과와 제한을 남겼다.

## 근거와 실행 조건

기록일은 2026-11-07(KST)이다. 운영자가 웹에서 업로드·분석·상황 확인·다운로드를 수행하고, 같은 Case의 입력 대조와 최종 읽기 전용 조회 결과를 제공했다. 작성자는 해당 출력·화면과 수치를 대조했으며 이번 기록 작업에서 EC2에 접속하거나 재분석하지 않았다. Case 식별자·원본명·번호판·보호 경로는 공개 문서에 복제하지 않는다.

| 항목 | 확인 범위 |
| --- | --- |
| 배포 revision | 운영자가 앞선 배포 사후 확인에서 보고한 C′ `70f1c47cbc7c08fa848d057687f7130047f1126c` |
| image digest | 같은 사후 확인의 `sha256:18775ff7efe472cfb8faa0abe658dc4425db971149b625135efd514cc088a3c9` |
| config | `aws-e2e-20261106-full15-v1`. 최종 결과 조회 자체는 revision/config를 재조회하지 않았으므로 위 배포 결속과 구분한다 |
| 입력 | MP4 20개, **304,227,785B**, 총 **1,200.0초** |
| 입력 대조 | 서버 업로드 파일 SHA-256 20/20 일치, 로컬 파일명 정렬 순서 일치. DB 연결을 반납한 뒤 파일 hash 검사 |
| 실행 시작 시 입력 상태 | `SEARCHING`, Case revision 1, HINT_EXTRACT 성공·COARSE_SEARCH 실행 중 |
| Search 예산 | 배포 후보의 Coarse 600초 일시 예외. 150초 복귀 후 같은 입력의 성공을 검증한 결과가 아님 |

이 입력은 기존 15개·1,584.173332초·1,771,439,266B 원본과 다른 집합이다. 입력 종류·길이가 다른 성공으로 기존 목표 장면 미검출 기록을 대체하지 않는다.

## 최종 서버 결과

| 항목 | 운영자 제공 결과 |
| --- | --- |
| Case | `READY`, revision **4**, timeline **1,200,000ms** |
| 검색 상태 | `analysis_range_too_long=false`, `candidate_search_failed=false`, `search_input_unsupported=false` |
| 후보 | **3개**, rank 1 선택, 정밀 확인 **OBSERVED** |
| Package | 객체·package 참조·신고영상 참조 모두 존재 |
| 지원 동작 | `DOWNLOAD_ASSETS`, `COPY_FIELDS`, `OPEN_DESTINATION` |
| 결과 검사 | `RESULT_CHECK_EXIT=0` |
| 신고영상 다운로드·재생 | 운영자가 다운로드 후 재생이 정상이라고 확인 |

| Job | attempt | 실행 wall 초 | 최종 상태 | Case 반영 |
| --- | ---: | ---: | --- | --- |
| HINT_EXTRACT | 1 | 6 | SUCCEEDED | 1 |
| COARSE_SEARCH | 1 | 418 | SUCCEEDED | 1 |
| FINE_VERIFY | 1 | 318 | SUCCEEDED · OBSERVED | 1 |
| INCIDENT_CLIP_BUILD | 1 | 19 | SUCCEEDED · clip 참조 존재 | 1 |
| PLATE_READ | 1 | 49 | SUCCEEDED | 1 |
| OVERLAY_TIME_READ | 1 | 50 | SUCCEEDED | 1 |
| REPORT_VIDEO_EXPORT | 1 | 0 | SUCCEEDED | 1 |
| PLATE_IMAGE_EXPORT | 1 | 0 | SUCCEEDED | 1 |

8개 Job 모두 `failure_present=false`, `case_applied=1`이다. 시간은 `TIMESTAMPDIFF(SECOND, started_at, ended_at)` 정수 조회값으로, 0초는 무비용·무처리를 뜻하지 않는다. 병렬 실행·큐 대기·사용자 확인 시간이 분리되지 않았으므로 합산한 값을 전체 E2E 소요시간으로 쓰지 않는다. Coarse Job 418초를 Search 내부 준비 또는 provider latency로 해석하지 않는다.

| 후보 rank | 시작 ms | 대표 ms | 끝 ms | 선택 |
| --- | ---: | ---: | ---: | --- |
| 1 | 20,000 | 28,000 | 36,000 | 예 |
| 2 | 622,000 | 629,000 | 636,000 | 아니오 |
| 3 | 1,100,000 | 1,102,000 | 1,105,500 | 아니오 |

후반부 후보가 반환됐다는 사실과 전체 사건 재현율은 별개다. 선택한 장면의 사용자 확인과 OBSERVED 결과만 확보했으며, 요청한 모든 사건의 정답 목록 대조는 하지 않았다.

## 남은 제한과 후속 작업

- **후보 썸네일:** 3개 모두 `thumbnail_reference_present=false`. 이번 성공이 [#583](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/583)의 수정·배포 완료를 뜻하지 않는다.
- **화면 내 신고영상 미리보기:** 브라우저에 미리보기 불가가 표시됐다. 다운로드 파일의 재생 성공과 구분하며 원인은 미확정이다.
- **사용자 확인 필드:** `safety_report_type`, `location`, `violation_expression`이 미확인 상태다. Package READY는 실제 신고 제출 또는 법적 판단 완료가 아니다.
- **Search 관측:** provider 호출·재시도 횟수, input/output token, 응답 종료 사유, 실제 비용은 이번 최종 조회에 없다. Job attempt 1을 provider 호출 1회로 환산하지 않는다.
- **AWS 최소 안정성:** O1의 실행 구간별 자원·사용량 및 O6 필수 복구 경로는 이 단회 정상 E2E와 별도로 증거를 대조해야 한다. 백업 격리 복원을 Worker 장애 복구의 대체 근거로 쓰지 않는다.
- **26분 검증과 복귀 시점:** 이번 20분 성공은 기존 15개·26분 검증의 종료를 뜻하지 않는다. 26분 검증을 이어갈 때는 [PM이 승인한 600초 조건](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6650917486)으로 진행하며, 이번 성공만을 근거로 먼저 150초로 복귀시키지 않는다. 검증 종료를 정한 뒤 합의대로 150초 복귀 PR과 임시 업로드 한도 원복을 진행한다. 승인 기간·범위를 추가로 연장해야 하면 PM과 별도 조율한다. 운영자가 전달한 후속 안내에 따라 같은 문제가 재발하면 재현 입력·순서·revision/config·기대 장면·실제 결과를 이슈로 남기고 무작정 반복하지 않는다. 이번 기록에서 설정을 변경하지 않았다.

공개 업로드 허용 범위·동시 처리량·p95·장시간 안정성은 이 단회 성공으로 승인하지 않는다. 기존 [전체 15개 격리 준비 결과](2026-11-05-ec2-full15-coarse-preparation-result.md)는 provider 송신 직전 차단 실험이고, 이번 제품 E2E와 입력·측정 경계가 다르다.
