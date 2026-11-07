# 기존 EC2 20개 영상 20분 제품 E2E 결과

**단회 제품 E2E PASS — 입력 검증, 선택 후보 OBSERVED, Package READY, 신고영상 다운로드·재생까지 확인했다.** 운영자가 제공한 서버 조회 출력과 브라우저 확인에 근거한다. 현재 결과 정리 범위는 이 20개·20분 실행이다. 기존 원본 15개·26분 검증은 미완료 상태로 보류하고 추후 별도 이슈로 다룬다. 이 문서에서 새 이슈를 생성하거나 [#452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452) 전체를 완료 처리하지 않는다.

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

## O1 후속 조회와 보존된 호스트 관측

운영자가 같은 Case의 기존 DB 행과 sysstat 기록을 읽어 제공했다. 새 E2E·provider 호출·서비스 변경 없이 기존 실행 근거를 보완한 결과다. 아래 정밀 Job 시간은 앞 절의 최초 정수 초 조회와 구분한다.

| Job | queue 대기 초 | 실행 wall 초 |
| --- | ---: | ---: |
| HINT_EXTRACT | 0.4944 | 6.8470 |
| COARSE_SEARCH | 0.0099 | 418.7618 |
| FINE_VERIFY | 0.0105 | 318.4969 |
| INCIDENT_CLIP_BUILD | 0.0103 | 19.1131 |
| PLATE_READ | 0.0143 | 49.9113 |
| OVERLAY_TIME_READ | 50.0356 | 50.6853 |
| REPORT_VIDEO_EXPORT | 0.9327 | 0.3169 |
| PLATE_IMAGE_EXPORT | 2.8340 | 0.6086 |

최초 queue는 UTC 2026-11-06 16:07:34.659304, 마지막 terminal은 16:23:05.100522다. KST 11월7일 01:07:34~01:23:05이며, **930.4412초** 관측창에는 사용자 확인·idle도 포함되므로 순수 처리시간으로 쓰지 않는다.

| 관측 시각 UTC | CPU 평균 구간 | user+system | iowait / steal / idle | 메모리 available / used |
| --- | --- | ---: | --- | --- |
| 16:10:14 | 16:00:03~16:10:14 (611초) | 36.22% | 1.86 / 0.61 / 61.32% | 5,649,216KiB / 24.22% |
| 16:20:14 | 16:10:14~16:20:14 (600초) | 79.39% | 0.19 / 0.24 / 20.19% | 5,722,912KiB / 23.30% |
| 16:30:14 | 16:20:14~16:30:14 (600초) | 22.12% | 0.11 / 0.24 / 77.53% | 5,660,772KiB / 24.08% |

sadf 12.6.1의 UTC 출력으로 날짜·구간을 대조했다. CPU는 약10분 구간 평균이며, **두 번째 CPU 구간만 Case 실행 안에 온전히 포함**된다. 첫 구간은 실행 전, 마지막 구간은 실행 후 시간을 포함하므로 비례 배분해 전체 실행 평균을 만들지 않는다. 메모리는 **16:10:14·16:20:14 두 시점**이 실행 중이며, 해당 표본의 available은 **약5.39~5.46GiB**, used 비율은 **23.30~24.22%**다. 16:30:14 메모리는 실행 후 참고값이다. sysstat의 kB 명칭은 실제 KiB이며 [공식 FAQ](https://sysstat.github.io/faq.html)에 따라 환산했다.

모든 자원 값은 **호스트 전체**다. Worker RSS/cgroup 사용량이나 다른 팀 작업의 기여도를 분리하지 않았다. **79.39%는 user+system 구간 평균이지 순간 CPU peak가 아니며**, 메모리 두 표본의 범위도 전체 실행의 최소·최대 보장이 아니다. 이 기록으로 실행 중 OOM/restart 없음·디스크 peak·동시 처리 capacity·p95를 판정하지 않는다. 이번 최소 O1 근거는 시간·queue·사용량과 같은 시간대의 호스트 표본이며, 더 촘촘한 관측을 했다고 표현하지 않는다.

| Usage operation | input / output token | 기록된 latency |
| --- | --- | ---: |
| HINT_EXTRACT | 519 / 483 | 6.729초 |
| CANDIDATE_SEARCH | 176,144 / 377 | 54.510초 |
| VISUAL_VERIFY | 8,598 / 723 | 12.936초 |
| READOUT_PLATE | null / null | 50.000초 |
| READOUT_OVERLAY_TIME | null / null | 51.000초 |

tracker 5행은 모두 FINALIZED/SUCCEEDED, failure_kind null이다. Usage 행 수·Job attempt를 실제 HTTP 시도 수로 환산하지 않는다. Coarse/Fine의 Job wall과 기록된 latency 차이를 Recording 단독 준비시간으로 확정하지 않는다. 유료 Hint/Coarse/Fine의 ledger amount는 **null**로 비용 미확인이며 0원으로 계산하지 않는다. local Readout 두 항목은 기록상0이지만 실제 provider 청구서를 대조한 결과가 아니다. 원시 응답 종료 사유·SDK 내부 시도 수·전체 사건 정답 대조는 별도 미확인이다.

## 남은 제한과 후속 작업

- **후보 썸네일 관측 범위 정정:** 3개 모두 `thumbnail_reference_present=false`라는 값은 DB Case state의 `candidates[]`에서 `thumb_ref` 키를 조회한 결과다. 키 부재와 명시적 `null`은 구분되지 않았다. 공개 `/view` 조회는 Package 필드에 한정됐으므로 CaseView의 썸네일 표시 여부는 확인되지 않았다. #583의 배포 검증은 대상 revision에서 별도로 수행한다. [#452 후속 정정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6703034138) · [#583](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/583)
- **화면 내 신고영상 미리보기:** 브라우저에 미리보기 불가가 표시됐다. 다운로드 파일의 재생 성공과 구분하며 원인은 미확정이다.
- **사용자 확인 필드:** `safety_report_type`, `location`, `violation_expression`이 미확인 상태다. Package READY는 실제 신고 제출 또는 법적 판단 완료가 아니다.
- **Search 관측:** 후속 조회에서 token·latency를 확보했다. provider 호출·재시도 횟수, 응답 종료 사유, 실제 비용은 미확인이다. Job attempt 1을 provider 호출 1회로 환산하지 않는다.
- **AWS 최소 안정성:** O1은 위 호스트 표본의 범위로 정리한다. O6는 [별도 provider 실패 연결 검증](2026-11-07-o6-provider-failure-validation.md)과 [배포 C′의 Worker 복구 CI](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/42046404269)를 구분해 사용한다. 정상 E2E·백업 격리 복원을 Worker 장애 복구의 대체 근거로 쓰거나 로컬 fake 결과를 실제 AWS 장애 주입 PASS로 표현하지 않는다.
- **26분 검증 보류와 임시 설정:** 운영자는 26분 재검증을 나중으로 미루고 추후 별도 이슈로 추적하기로 했다. 현재 선행조건이 아니며 기존 미완료 기록은 보존한다. 운영자가 전달한 **11월6일 회의 후속 방침은 Coarse 600초 유지·필요 시 재검토**다([#452 갱신](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6694582845)). 앞선 [150초 복귀 조건](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6650917486)은 당시 결정 이력으로 보존하며 현재 복귀 예정으로 표시하지 않는다. 이 방침은 Coarse 상한에 관한 것으로 업로드 한도 등 다른 설정의 유지·변경을 일괄 승인하지 않는다. 이번 문서 변경에서 운영 설정·코드·배포를 변경하지 않았다.

공개 업로드 허용 범위·동시 처리량·p95·장시간 안정성은 이 단회 성공으로 승인하지 않는다. 기존 [전체 15개 격리 준비 결과](2026-11-05-ec2-full15-coarse-preparation-result.md)는 provider 송신 직전 차단 실험이고, 이번 제품 E2E와 입력·측정 경계가 다르다.
