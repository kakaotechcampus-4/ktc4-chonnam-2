# EC2 Recording 격리 실행물 준비 계획

IN_PROGRESS · Refs #452 · Related #530, #553, #555 · RT-14 후속.

사용자가 제공한 상세 범위를 구현 기준으로 삼는다. 지정 checkout과 브랜치를 유지하고 작성자가 순차 구현한다. 독립 reviewer만 별도 fresh context로 읽기 전용 검토한다. commit·staging·원격 실행은 하지 않는다.

## 설계와 선택

Windows 감독기의 경로·image ID·무암호 DB를 복제하는 방법은 제외한다. 운영 Compose를 재사용하는 방법도 target 혼입 때문에 제외한다. 기존 유한 Docker 호출·소유권 정리·Recording 전용 경계·phase observer를 재사용하는 Linux 호스트 감독기를 추가한다. 제품 src는 변경하지 않는다.

제품 source는 HEAD의 명시 allowlist archive로 고정하고, 미커밋 하네스는 개별 content hash로 별도 식별한다. registry digest가 없는 로컬 이미지는 로컬 acceptance 전용으로 구분한다. EC2 실행에는 registry digest와 실제 import/의존성/도구 검증이 모두 필요하다. 실험 credential은 매 stage 생성하고 보호 파일로 전달한다.

## 구현 순서와 검증

1. 패키지 allowlist·archive 변조/탈출·revision·image identity controls를 RED→GREEN으로 구현한다.
2. Linux 자원 gate·운영 target 배제·단계 실패 차단·credential·명시 placement controls를 RED→GREEN으로 구현한다.
3. 새 Linux 감독기/entrypoint를 연결하고 로컬 실제 Linux에서 무미디어 acceptance를 한 번 실행한다. 자원이 모자라면 실패 근거를 남기고 NOT_RUN으로 기록한다.
4. 한국어 단계별 runbook·자원 산식·운영 snapshot/lock/원래 서비스 복귀 및 실패 복구 절차를 작성한다.
5. 독립 fresh 읽기 전용 reviewer 검토 후 수정하고 같은 reviewer에게 재확인받는다. 관련 focused 검사·diff·src 불변·미스테이징·기존 자원 보존을 확인한다.

## 검토 초점

운영 이름/DB/volume/network 혼입, source/harness/config/image 불일치, reserve 미달, cleanup 실패 후 서비스 복귀, secret/원본 공개, 감독/daemon 실패의 한계를 중점 검토한다. 대역 tests와 실제 Linux 연결 검증을 구분한다.

## 진행 기록

- 시작: 지정 branch, HEAD `ab614354132888d6ce2a29cd4d9d14e92f219f84`, tree/index 비어 있음. GitHub #555 merged SHA와 일치, head `23c00984` ancestry exit0.
- 판단: 사용자 지시대로 지정 checkout에서 작업하며 별도 worktree/branch/commit을 만들지 않는다. 전체 pytest/MySQL·기존 실영상 비교를 반복하지 않는다.
- 구현·검증: controls를 RED→GREEN으로 구현, 최종 focused83 PASS·lint PASS. 실제 Linux b 권한 실패/정리 성공을 보존하고 c 연결 성공 후 추가 안전 변경을 d의 새 frozen 조합에서 검증했다. d 무미디어 acceptance PASS·순수 Linux negative8 PASS·새 Docker 자원 잔여0.
- 검토: 독립 fresh reviewer의 P1 상위 메모리 scope·P2 입력 identity를 수정하고 같은 reviewer가 해소·추가 actionable 없음 재확인. 운영 서비스 중단/복귀는 로컬 controls·절차 검토이며 EC2 직접 실행은 아니다.
- 마무리: 공개10파일·제품 src 등 HEAD diff0·원본15개 size/mtime 일치·기존 보호 volume3개 유지. 실제 EC2 정보/registry digest/점검 승인은 runbook에 남긴 별도 선행 결정이다.
