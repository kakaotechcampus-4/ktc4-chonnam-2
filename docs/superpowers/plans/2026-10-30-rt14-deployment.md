<a id="rt-14-deployment-preparation-implementation-plan"></a>

# RT-14 배포 준비 구현 계획

**상태:** IN_PROGRESS · Refs #450 · 관련 #287, #460, #452

**목표:** AWS에 접근하거나 변경하지 않고 검토 가능한 배포 도구를 준비한다.
**명세:** Issue #450, 사용자 요청 2026-10-30, Runtime Plan RT-14, Ops §2/4-1/19.
**아키텍처:** 신뢰할 수 있는 develop 전용 수동 workflow, CI 빌드 amd64 ECR digest,
명시적으로 설치된 root 소유 controller로의 SSM, 기존 Compose service,
외부 기존 volume, 보호된 버전 지정 config 파일. 호스트 빌드는 없다.

<a id="constraints-and-rulings"></a>

## 제약과 판단

- commit/staging/push/PR/comment/dispatch 또는 실제 AWS/service 작업은 없다.
- 기존 HEAD와 가져온 develop: `4876e646171ba9f0195de52d11741f3c39fb51a0`; 깨끗한 index/worktree.
- #473–#477은 병합됐으며 과거 CI는 이 변경의 검증이 아니다.
- RD-12b–e/h, RD-13a/c/d, RD-11a와 실제 RD-07c는 SoT에서 열린 상태다.
  도구는 후보 경로를 구현하며 명시적인 Owner 승인 호스트 정책을 요구한다.
  구현이나 config flag는 Owner 수락을 의미하지 않는다.
- 판단: ECR pull 후보는 사용자의 CI/registry 선호를 따르며 대규모 반복 EC2 빌드를
  피한다. S3 전달과 호스트 빌드는 여기서 필수 가치를 더하지 않는다.
- 판단: migration 실패 시 writer를 중지한 채 영속 dirty marker를 남긴다.
  자동 롤백, 재시도, 스키마 downgrade, volume 삭제는 없다.
- 판단: Compose 소스가 포함된 고정 application image에서 배포한다.
  host controller는 별도로 설치/검토하며 SSM으로 자동 갱신하지 않는다.
- 판단: 새 공개 endpoint/domain/OAuth는 없으며 내부 읽기 전용 smoke만 수행한다.
- 로깅/restart/retention과 disk 예산은 명시적으로 승인된 입력이어야 하며 운영
  기본값을 지어내면 안 된다. CloudWatch 자원은 사전 provision한다.

<a id="work"></a>

## 작업

- [x] 1. 테스트 우선: 불변 입력 검증, 고정 subprocess 진단,
  SSM pending/success/nonzero/missing/timeout/cancel, 정확한 account/role 검사.
- [x] 2. 안전한 OIDC/AWS orchestration과 별도 수동 workflow를 구현하고
  regression/mysql/test 및 모든 기존 필수 검사를 보존한다.
- [x] 3. 테스트 우선: host lock, 단일 migration, dirty marker, health 실패,
  known-good 원자적 승격, config를 고려한 롤백, volume 소유권 guard.
- [x] 4. host controller와 image/runtime 배포 preflight를 구현한다.
  실제 Worker process 등록 marker, live/ready, 읽기 전용 API smoke.
- [x] 5. 보호 입력, 최소 IAM action/resource, 정확한 명령, backup/media 일관성,
  부분 DDL 복구와 pending인 capacity/retention을 문서화한다.
- [x] 6. 집중 테스트, source/rendered Compose, 경계/fixture/actionlint/diff를 실행한다.
  필요한 경우에만 기존 image/cache를 사용하고 전체 로컬 pytest/전체 MySQL은 없다.
- [x] 7. 구현 이력이 없는 새 읽기 전용 검토자를 사용한다. 지적에 대한 회귀 테스트,
  같은 검토자의 재검사, notes/log 추가 후 unstaged로 둔다.

<a id="review-focus"></a>

## 검토 초점

신뢰하지 않는 dispatch ref와 OIDC subject, 예외/CLI 유출, SSM 전달 대 실행,
dirty 또는 불확실한 migration, 이전 config/schema 롤백, 경쟁 배포와 운영자 복구,
변경하지 않은 media/DB 소유권, 합성 대 실제 AWS/운영 증거.
비어 있는 Docker 목록에서 Runtime 메모리/disk 용량을 추론할 수 없다.
