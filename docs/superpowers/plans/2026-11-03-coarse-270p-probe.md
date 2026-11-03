# Search Coarse 270p·CRF28 격리 실험 계획

> 사용자 상세 실행 지시를 설계·승인 근거로 삼는다. `executing-plans`와 TDD로 직접 구현하고 fresh 읽기 전용 reviewer가 검토한다. 추가 승인·commit·staging은 하지 않는다.

**목표:** 같은 보호 manifest의 전체 720/1200초 logical range에서 실험 전용 Coarse 270p·CRF28 크기만 측정한다.

**구조:** 제품 encode 함수를 그대로 호출하되 하네스의 명시적 Coarse 진입 중에만 높이를 바꾸고 해당 encode의 subprocess argv에 CRF28을 삽입한다. Fine·다른 subprocess·운영 config는 유지한다. 성공/예외 모두 hook을 원복한다. 기존 보호 영상이 없으면 실제 Recording→commit→새 물리 연결→detached strict decode→같은 stream Search 경로로 준비한다.

**기술:** Python/pytest, 기존 고정 FFmpeg8.1·MySQL8.4 이미지, 소유 internal network/volume만 사용.

**근거:** [P2-0c 계획](../../runtime/experiments/elice-runtime-capacity-smoke-plan.md), [기존 실패·실측](../../runtime/experiments/2026-11-03-capacity-override.md), #452 Owner 댓글6594486653, 사용자 요청.

## 경계와 검토 초점

- 원본2fps·0.5배속·역변환·무음·downscale-only·전체 단일 요청, source512/media40/request56MiB·준비150초 유지.
- Analysis480/veryfast/CRF23·청크256KiB·packet64MiB·metadata exact·strict decode 유지.
- override 잘못된 값·숨은 Fine 적용·예외 뒤 hook 잔류·argv drift·guard 우회에 대한 실행 controls.
- 이전 실패 원문과 ignored scratch는 보존. 새 RAW·개인 정보는 새 ignored scratch만 사용.
- 1200초는 이전256MiB/1100MiB/512MiB로 안전하다고 가정하지 않는다. 출력 중첩·DB·Windows RAM/C·시간을 실행 전 계산하고 유한한 전체 예산을 맞춘다. 부족하면 NOT_RUN.
- provider/HTTP/AWS/배포/Case·운영 변경0. 크기 성공과 탐색 품질을 구분한다.

## 작업·검증

- [x] 1. 실제 argv·Fine 격리·원복·invalid config·실제 guard controls RED→GREEN. 작은 합성8.1 encode에서 출력 높이·frame/PTS·무음·배속·크기를 확인.
- [x] 2. 보호 원본15개 hash/size/mtime와 lineage·도구/source identity·재사용 가능성·Windows 자원 확인. 새720초 run을 감독·계측.
- [x] 3. 720초 결과로1200초 출력/메모리/temp/DB/C/감독 시간을 계산하고 실행 전 기록. 조건 충족 시 전체0–1200초 직접 측정, 아니면 NOT_RUN.
- [x] 4. focused controls·quality·boundary·Contract·diff, fresh reviewer와 지적 후 같은 reviewer 재확인. 소유 자원만 정리하고 한국어 결과 문서에 변경 파일·직접값·실패·한계·Owner 후속 기록.

인터페이스 사전검토: controls→override→실측은 같은 context manager/설정 검증 API를 사용한다. sampler/감독기는 같은 유한 resource profile을 소비해야 하며 한쪽만 올리는 설정은 거부한다. 예산 표는 실행 전 결과 문서에 추가한다.

최종: 720/1200초 모두 PASS_STOP_BEFORE_SEND. Search16,810,996B/28,732,230B, provider0. focused72·관련102·감독기15 PASS, fresh reviewer 직접87 PASS 및 최종 증거 재계산/동일 reviewer 확인 완료. 원본15개 불변·소유 잔여0, 공개6파일만 미커밋·미스테이징이다. 품질·Case·배포 후속은 결과 문서에 남긴다.
