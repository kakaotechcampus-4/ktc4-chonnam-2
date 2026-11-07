# Coarse 후보 썸네일 Runtime 연결 계획

목표: #583 E안에 따라 Fine/clip 결과와 독립적으로 Coarse 성공 후보의 Top-3 frame refs를 T1 전에 발급한다.
기준: `3108418c`, 브랜치 `codex/issue583-coarse-thumbnails`. Case 소비·selector는 미병합 #604 고정 HEAD `4bba4d44`에 의존한다.

## 경계

- 사용자 생성 브랜치에서 작업한다. Case·Search 계약/제품 코드를 복사하거나 임의 수정하지 않는다.
- 신규 kind, timeout·retry·Coarse 예산 상향, AWS/provider·배포·commit/push는 범위 밖이다.
- frame 거부 4종만 후보별 null. binding·DB·취소/lease·commit 실패는 전파한다.
- provider 성공 뒤 frame 실패를 같은 handler 안에서 provider 재호출로 처리하지 않는다. Worker stale 회수·사용자 재시도 전체의 과금 중복 방지를 새로 보장하는 변경은 아니다. T1 replay는 기존 durable receipt를 사용한다.
- 기존 clip 발급은 유지한다. #604와 합친 트리는 별도 격리 검증하며 본 작업 트리에 Case 변경을 섞지 않는다.

## 작업

- [x] 재현: 성공 Coarse 결과가 frame 발급기를 거쳐 produced payload에 실리는 RED. 실패/빈 결과·Fine에서는 frame 호출 없음.
- [x] 후보 발급: Case selector/position 주입, rank·중복·범위·timeline·Case/VIDEO 소유권 검사. source resolution과 frame 추출은 DB transaction 밖.
- [x] 실행 연결: production Recording context와 Coarse 후처리 연결. 성공 refs shape·허용 후보를 T1 전에 검사. 기존 유료 Search 호출은 한 번만.
- [x] 검증: 부분 frame 거부, checkpoint/오류·context cleanup, production 실영상 frame 및 #604 Case 반영 통합. 기존 Search/clip 회귀·quality·boundary.
- [x] 기록: 직접 실행 범위·dependency·미실행(MySQL/EC2/브라우저/실시간 측정)을 구분해 남긴다.

## 리뷰 중점

선택하지 않은 후보/타 scope frame, span 밖 대표 시각, provider 재호출, 취소 중 성공 payload, T2 프레임 재발급, 실패를 후보 없음으로 위장하는 경로를 검사한다.

결과 및 배포 전 미완료 조건은 [Runtime 검증 기록](../../runtime/experiments/2026-11-07-coarse-thumbnails-runtime-validation.md)을 참조한다.
