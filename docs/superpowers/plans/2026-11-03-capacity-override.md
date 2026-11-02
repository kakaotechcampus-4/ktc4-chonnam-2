# P2-0c 격리 capacity 실행 계획

> 실행: `superpowers:executing-plans`로 현재 브랜치에서 직접 구현하고 마지막에 fresh 읽기 전용 reviewer 검토를 받는다. 사용자의 상세 실행 승인에 따라 추가 승인·commit 단계는 생략한다.

**목표:** 동일 240초에서 byte cap만 조정하고, 실제 경계와 자원 증거로 다음 길이를 판단한다.

**구조:** 기존 real-media harness에 명시적 실험 JSON을 주입한다. 제품 설정·저장 구조·Search/Case 계약은 유지한다. 별도 owner DB/network/volume에서만 실행하고 결과·raw는 분리한다.

**기술:** Python/pytest, 고정 FFmpeg 8.1 이미지, MySQL 8.4/packet64MiB.

**요구 근거:** 사용자 요청, [P2-0c·G2/G4/G6·Decision Gate](../../runtime/experiments/elice-runtime-capacity-smoke-plan.md), [이전 실제 결과](../../runtime/experiments/2026-11-03-metadata-publish-fix.md).

## 공통 제약

- 현 브랜치 유지, 미커밋·미스테이징. 원본/기존 scratch/보존 volume3개/공유 cache 불변.
- Analysis480/veryfast/CRF23. 첫 240초는 duration240000ms 유지, byte만96MiB 후보.
- Recording 도구120초·Search150초·source/media/request512/40/56MiB·Case 정책 유지.
- runner1280MiB/DB512MiB, soft1100/440MiB, temp512MiB/DB1GiB 유지.
- Windows 시작3004MiB=1280+512+700 reserve+512 collector/daemon, C 시작6GiB/reserve4GiB/증가2GiB. 각 단계의 실제 working set과 별도 대조.
- API key 없음, internal network/공개port0, socket/HTTP 차단·SDK sentinel. provider·배포·운영 금지.
- 시간 중첩 합산 금지. 미도달 NOT_REACHED, 미실행 NOT_RUN, 근거 부족 UNKNOWN.

## 검토 초점

1. 유한하지 않은 값/불리언/오탈자/unknown key/중복 key는 실행 전에 거부한다.
2. config 없이 긴 길이를 허용하거나 duration보다 긴 요청을 실행하지 않는다.
3. 새 허용값이 실제 Recording guard에 연결돼야 하며 baseline은 유지한다.
4. 임의 placement gap/overlap을 성공으로 오인하지 않고 원본의 실제 연속성과 logical coverage를 구분한다.
5. 측정/중단/정리 실패가 PASS를 덮지 않으며 provider guard 거부 뒤 SDK 진입0을 보존한다.

## 작업

- [x] 1. 실패 controls: config·길이·실제 guard·placement·송신 차단·자원 stop·cleanup. RED를 확인한 뒤 harness 최소 보완, GREEN 확인.
- [x] 2. 소유 감독기/원본 hash·size·mtime/host/도구 identity 사전검사. Linux controls 후 동일240초 한 번. 실행 전 유한 예산·선택 근거를 결과 문서와 보호 scratch에 기록.
- [x] 3. 통과하면 실측 bytes/peak/elapsed로 다음 길이 후보(480초, 이후 최대1200초)를 판단. guard/자원/도구 timeout 첫 병목에서 중단. 무조건 장시간 실행 금지. 실제720초 Search40MiB guard에서 중단, 1200초 NOT_RUN.
- [x] 4. focused·quality·boundary·Contract·diff, fresh reviewer 및 같은 reviewer 재확인. 날짜별 한국어 결과/정리/20분 미도달 여부 기록. 107 focused PASS, reviewer 직접51 PASS, owner 자원0·원본15개 불변.

판정: 96MiB는 충분함이 확인된 값이 아니다. 기존100초38,363,450B의240/100배는92,072,280B(추정)이며,96MiB=100,663,296B다. part와 최종 동시 bytes 약2N, concat 디스크 중첩을 보수적으로3N+40MiB=328MiB로 잡아 temp512MiB와 대조한다. 이는 실행 중 표본/soft stop의 대체가 아니다. 다음 길이는 이 상한만으로 자동 승인하지 않는다.
