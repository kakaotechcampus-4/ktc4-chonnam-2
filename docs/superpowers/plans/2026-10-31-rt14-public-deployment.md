<a id="rt-14-approved-public-deployment-implementation-plan"></a>

# RT-14 승인된 공개 배포 구현 계획

> superpowers:executing-plans와 test-driven-development로 현재 세션에서 구현한다.
> 사용자는 checkout/worktree 생성, staging, commit, push,
> dispatch, AWS 변경을 명시적으로 금지한다. 최종 검토: 새 GPT-6.1 Sol, high, 읽기 전용.

**목표:** #450 승인 §3 및 설계 §13.6/§16.1을 구현하고
`RT14_EXECUTION_ENABLED=false`를 유지한다. AWS/공개 인수 조건은 pending으로 남는다.

**권한 근거:** [Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522291826),
[후속 내용](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450#issuecomment-6522296524),
`docs/runtime/rt14-deployment-design.md`. Gate를 다시 열지 않는다.

**아키텍처:** 기존 운영 이미지의 Web build stage, revision marker와 content manifest,
불변 호스트 release 디렉터리, Compose와 별개인 host Caddy package,
영속 journal을 사용하는 원자적 symlink 게시.
Public smoke는 성공한 SSM 이후 및 독립적으로 사용하는 별도 읽기 전용 CLI다.

<a id="tasks"></a>

## 작업

- [x] 1. 롤백: pending/failed tip과 성공한 target, 거부되는 target CI/조상/digest를
  테스트하고 secret-scan 의존성을 보존한다. `deploy/aws.py`의 tip gate 선택만
  변경하며 테스트는 `tests/deploy/test_aws_deploy.py`에 둔다.
- [x] 2. 산출물: revision/manifest 불일치와 안전하지 않은 파일을 테스트하고
  `deploy/web_artifact.py`, `docker/web_release.mjs`, Docker build/context 변경을
  구현한다. 실제 Web을 로컬 빌드하고 정확한 출력을 검증하며 로컬 이미지 빌드를 유지한다.
- [x] 3. 상태: `tests/deploy/test_ec2_deploy.py`에 최초 실패, pointer/state 쓰기/
  unlink 중단, 롤백 결함 테스트를 추가한다. journal 스냅샷, pointer 검증/게시,
  안전하게 거부하는 reconciliation을 구현한다.
  자동 채택, restore, downgrade, volume 제거는 없다.
- [x] 4. Ingress: `deploy/public_smoke.py`, `deploy/Caddyfile`, 보호된 DDNS updater,
  host service 예시를 구현한다. DNS/TLS/HTTP/revision, redirect 없음,
  same-origin API 오류와 정제된 실패를 테스트한다. workflow의 post-SSM + smoke-only를 연결한다.
- [x] 5. 집중 deploy/secret/Worker, quality, 경계, Contract, actionlint,
  실제 로컬 Web build와 loopback Caddy routing/TLS를 실행한다. Docker 검사는
  변경한 산출물 경계로 제한한다. 전체 pytest/MySQL을 반복하지 않는다.
- [x] 6. 요구사항 matrix, 모든 파일, 증거, 미실행 인수 조건으로 recovery/public
  runbook, Notes, README, Log를 갱신한다. 새 검토와 차이 확인,
  최종 diff/staging 검사를 수행한다.

<a id="review-focus"></a>

## 검토 초점

target gate 실패/취소/skip을 성공으로 바꾸면 안 된다. dirty journal과 pointer
불일치를 조용히 채택하면 안 된다. 최초 bootstrap은 데이터를 보존한다. Web
manifest는 정확한 이미지에 결속한다. TLS/redirect/proxy fallback으로 smoke를
위장할 수 없어야 한다. 비공개 응답/예외/argv는 유출되지 않아야 한다.
테스트 대역은 AWS 증거가 아니다.

<a id="execution-ledger"></a>

## 실행 기록

- 시작: branch `codex/rt14-public-deployment`, HEAD와 GitHub develop
  `3819a5ddae6d1d446b79c7b1e644358b3680ba29`; 깨끗한 index/worktree.
  #479/#483/#484/#488/#491 병합. #450 본문과 댓글 다섯 개를 모두 읽었다.
- 판단: 사용자가 이미 설계와 현재 세션 구현을 승인했다. 계획 승인을 반복하거나
  skill이 요구하는 commit/worktree 작업을 하지 않는다.
- 판단: 이전 Notes에는 과거 pending 결정이 포함돼 있다. 명시적으로 날짜를 붙인
  대체 설명 및 운영 링크로 이력을 보존하며 승인을 권한 근거로 삼는다.

- 구현: rollback 2 RED -> 33 GREEN; bundle 6 RED -> 6 GREEN;
  pointer/fault 6 RED -> GREEN; smoke 15 RED -> GREEN; DDNS 4 RED -> GREEN.
- 판단: Caddy는 host package로 실행한다. 공개 전용 release의 읽기 전용 bind mount는
  보호된 /opt/daesingo 권한을 넓히지 않고 Caddy에 접근을 제공한다.
- 판단: staging 식별자는 manifest hash도 정확한 image digest에 결속한다.
  기존 revision 재사용으로 다시 쓰인 파일+manifest를 조용히 수락할 수 없다.
- 검증: Linux 최종 focused 106 PASS; Windows focused 136 PASS, guard delta
  58 PASS; Web 224 PASS (동시 worker 2개; 테스트 정책 변경 없음), 실제
  npm build, Docker Web stage 및 최종 COPY 경계, loopback Caddy PASS.
- quality/경계/Contract/actionlint/diff PASS; 요청대로 완전한 운영 이미지
  regression/mysql/test 인수 검사는 push 이후 CI로 연기한다.
- 새 검토자: GPT-6.1 Sol/high, fork none. 최초 제품 지적 없음.
  검토자 관측에 따라 tuple 테스트를 강화했으며 차이 확인은 pending이다.
- 환경 실패는 따로 유지한다. 기본 pytest temp 권한,
  최초 npm 의존성 누락, Web temp ENOENT, PowerShell OOM; scanner
  snapshot은 clean이나 history 실행 실패는 동시성을 제한한 재시도 대기 중이다.

- 최종: controls17 PASS; snapshot2331/history1535 findings0, 기존 예외만 있음.
  실제 GitHub RT14_EXECUTION_ENABLED는 false로 읽혔으며 변경하지 않았다.
- 같은 검토자의 차이 검토: 11 PASS, 남은 제품 지적 없음. EOF 공백 수정.
- 정확한 ID 검사 후 작업 소유 Docker image tag를 제거했으며 공유 cache/base는
  제거하지 않았다. 변경은 unstaged/미커밋으로 유지한다. 실제 AWS/공개 인수 검사는 pending이다.
