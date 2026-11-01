# Incident 720p 설정 적용·실영상 E2E 기록 — 2026-11-02

## 0. 요약과 증거 경계

**운영자 보고: EC2 Incident `720 / veryfast / CRF20` 적용, 변경 후 실영상 E2E 약 4분 44초.**
원하는 사건 포함과 기존 240p보다 훨씬 잘 보인다는 평가는 사용자 육안 확인이다.
Analysis profile·설정은 유지됐다. 최적 화질·OCR 정확도·전체 입력 품질·성능 또는 실제 신고 수용의 근거로 확대하지 않는다.

| 증거 | 제공·확인 주체 | 이번 문서 작업의 직접 실행 여부 |
| --- | --- | --- |
| EC2 5초 단독 측정·config 적용·서비스 상태 | 운영자 제공 실행 결과 | 재실행하지 않음 |
| 변경 후 E2E 시간·사건 포함·화질 평가 | 운영자 제공 시간·사용자 육안 확인 | E2E·육안 평가 재실행하지 않음 |
| 결과 파일 metadata·SHA-256 | 기존 대화의 직접 검사 인계 증거 + 이번 로컬 파일 재확인 | `ffprobe` metadata 조회·SHA-256 계산만 수행 |
| 결과 파일 전체 decode 통과 | 기존 대화의 직접 검사 인계 증거 | 이번 작업에서 재실행하지 않음 |

AWS 접속·provider 호출·encode·배포·dispatch·DB 작업은 수행하지 않았다.
실제 영상·개인 경로·Case 접근 식별정보·계정·image URI·credential은 싣지 않는다.

## 1. EC2의 5초 구간 단독 측정 (운영자 제공)

| 항목 | 보고된 관측 |
| --- | --- |
| 도구·입력 확인 | 동일 build FFmpeg/ffprobe 8.1, 원본 hash 일치 |
| Incident 후보 | `720 / veryfast / CRF20` |
| encode 경과 | 6.904초 |
| encoder peak RSS | 172,863,488 bytes |
| 출력 크기 | 6,212,369 bytes |
| 출력 영상 | 1280×720, 5초, 150 frames |
| 무결성·정리 | 전체 decode·원본 불변·임시 출력 정리 확인 |
| 측정 중·종료 후 상태 | 측정 중 Worker만 중단. 종료 후 Worker 상태 정상·API readiness 200 |

이 값은 해당 5초 구간의 단독 측정이다. 전체 E2E 시간이나 모든 입력의 자원 상한으로 일반화하지 않는다.
아래 §3의 7.5초 실영상 결과와 같은 출력으로 취급하지 않는다.

## 2. 실제 config 적용 (운영자 제공)

| 항목 | 적용 결과 |
| --- | --- |
| revision | `e50b2976ef4edc3a030cfc5b03a5206340dd917b` 유지 |
| 기존 config | `aws-e2e-20261031-v1` → previous |
| 신규 config | `aws-e2e-20261102-incident720-v1` → current |
| Incident 변경 | `240 / veryfast / CRF23` → `720 / veryfast / CRF20` |
| 유지 범위 | 이미지·revision·Analysis 설정·비밀번호 등 나머지 설정 |
| Analysis profile | `aws-e2e-v1` 유지; 480 / veryfast / CRF23, 50,331,648 bytes (48 MiB) / 240,000 ms (4분) 유지 |
| 배포 상태 | schema complete, dirty·operation lock 없음 |
| 서비스 상태 | API·Worker·MySQL 정상, Worker 상태 정상, readiness 200, Caddy active |

기존 backup artifact hash와 [과거 격리 복원 기록](2026-10-31-rt14-aws-real-e2e.md#rt14-recovery-execution-results)을
재확인한 결과다. **이번 배포 직전 새 DB 백업을 수행한 기록이 아니다.**
previous 기록은 rollback 대상 준비와 구분해 읽으며, **실제 rollback 실행을 보고한 증거는 없다.**
현재 적용값의 원문은 [환경·배포 설정 명세 §3](../../management/environment-and-deployment-config.md#3-recording-초기-배포-baseline-v1)이다.

## 3. 변경 후 실영상 E2E 결과

운영자가 지정한 로컬 결과 파일에 접근할 수 있어 metadata와 hash를 가볍게 재확인했다.
아래 값은 기존 인계 증거와 일치한다. 재인코딩이나 전체 decode는 수행하지 않았다.

| 항목 | 기존 인계 증거·이번 직접 재확인 |
| --- | --- |
| 영상 | 1280×720, H.264 |
| 길이·frame | 7.5초, 225 frames, 30fps |
| 파일 크기 | 8,333,019 bytes |
| SHA-256 | `F0688AB9A43A3E336D847824E4A1E6C23F63E82E6395DA5D3C5B0598890FAD95` |
| 전체 decode | 기존 인계 증거에서 통과, 이번 재실행 없음 |

| 운영자 확인 항목 | 보고된 결과 |
| --- | --- |
| 사건 포함 | 원하는 사건이 포함됨 (사용자 육안 확인) |
| 화질 | 기존 240p 출력보다 훨씬 잘 보임 (사용자 육안 확인) |
| 변경 후 E2E | 약 4분 44초 |
| 이전 E2E 정정값 | 약 4분 38초. 기존 약 4분 33초는 정정 전 수치 |
| 비교 조건 | 기존 출력 5초, 신규 출력 7.5초; 통제된 비교가 아님 |

정정된 두 E2E 시간의 단순 차이는 약 6초지만, **해상도 변경의 인과적 비용으로 해석할 수 없다.**
출력 길이가 다르고 단계별 시간을 통제하지 않았다. 사건 포함·화질 평가는 OCR 정확도나 전체 입력 품질 보장이 아니다.
§1의 5초 단독 encode 수치를 이 E2E 시간으로 대체하지 않는다.

## 4. 남은 조건과 이번 문서 검증 범위

- Analysis 4분·48 MiB 제한과 약 1시간 입력 지원 미확정 상태를 유지한다.
- 최적 encoding·화질, 대표/복잡한 전체 입력의 처리 성능·동시 실행 자원은 후속 측정 대상이다.
- 이번 config 적용을 실제 rollback rehearsal 완료로 계산하지 않는다. RT-14 전체 완료·최종 Package READY·장기 공개 gate·실제 신고 수용을 확정하지 않는다.
- 이번 직접 검증은 Git 상태, 관련 지침·문서 대조, 결과 파일 metadata·hash, 값·단위·근거 구분, 상대 링크·anchor, 과거 기록 보존, 추가 diff 비노출, `git diff --check`와 독립 읽기 전용 리뷰로 한정한다.
- 제품 코드·테스트·workflow·Analysis 설정·DB·AWS·실제 runtime.env는 변경하지 않는다. 전체 pytest·MySQL·Docker build를 반복하지 않으며 staging·commit·push·PR·외부 댓글·Notion 게시를 하지 않는다.
