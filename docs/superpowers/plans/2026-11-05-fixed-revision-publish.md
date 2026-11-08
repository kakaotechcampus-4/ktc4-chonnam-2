# 고정 revision publish 구현 계획

사용자가 준비한 `codex/rt14-publish-fixed-revision`, clean HEAD `8d6a0979ff68e3273587ec08397ce05d92f4c865`에서 작업한다. 기존 설계 조사와 사용자의 구현 지시를 따른다. commit·push·게시·AWS·dispatch·실제 Docker 작업은 하지 않는다.

## 범위와 identity

- 제어 workflow/publisher는 신뢰된 develop의 `GITHUB_SHA`다. 이를 바꾸지 않는다.
- `publish_revision`은 필수 전체40자 SHA다. 실제 commit/tree·제어 checkout·local ancestor·GitHub develop ancestor 및 제어/target의 기존 push CI를 검증한다.
- target secret-scan은 기존 scanner의 require-ancestor로 수행한다. deploy/rollback의 target·gate·controller 경로는 유지한다.
- Git archive를 이번 runner 전용 source 디렉터리에 추출하고 파일 manifest로 후속 변조를 거부한다. 제어 코드·untracked 파일을 build context에 섞지 않는다.
- build의 REVISION·Web marker·OCI label/env·immutable tag는 target SHA다. build 후 실제 image ID를 고정하고 기존 acceptance와 publish가 같은 ID를 사용한다.
- ECR IMMUTABLE을 유지하고 기존 target tag는 명시 거부한다. push 후 registry digest로 pull/identity를 대조한다. credential/전체 registry URI는 출력하지 않는다.

## 구현과 RED/GREEN

1. `tests/deploy/test_fixed_publish.py`: 전체 SHA/commit/tree/ancestor/CI, archive 안전성·source 변경, 이미지 label/env/platform/ID, immutable 기존 tag·digest 대조·비노출 반례를 먼저 작성하고 RED 확인.
2. `deploy/aws.py`: source 준비·image identity 두 offline stage 및 target-aware publish 추가. 기존 deploy/rollback/authenticate 함수의 의미를 유지한다.
3. `.github/workflows/rt14-deploy.yml`: publish 전용 입력, target secret-scan, full control history, source prepare, target build, image-ID acceptance 연결. 다른 배포 job은 변경하지 않는다.
4. 기존 Web build wiring 검사를 새 target source/ID 계약에 맞춘다. offline 배포/secret-scan/Web/Recording 회귀, lint·경계·YAML/Bash·diff를 실행한다. 실제 image/AWS 검증은 NOT_RUN.
5. 독립 reviewer가 실제 diff·제약·검증 범위를 읽고 확정 지적을 처리한다. 로컬 Draft PR 본문과 파일/hash·결과를 준비한다.

## packet 조사 — 이번 제품 diff 제외

`docker/runtime.py`, `deploy/ec2.py`, B/C Recording writer를 읽어 legacy의 전체 escaping command와 chunked의 분할 command 조건을 구분한다. 현재 MAX_BYTES+margin<packet 검사의 한계·C 최소 후속안·B/C 새 SHA/image 재고정 조건을 별도 기록한다. packet/Recording/controller·#583 제품 변경은 하지 않는다.

## 실행 기록

기능 부재와 acceptance 우회 반례의 RED를 확인하고 구현했다. 관련76개, 보강 후 offline 배포/secret-scan 회귀282개와 controller 부분 검사11개를 통과했다. 독립 P2는 interpreter/최적화 우회를 막아 재확인했다. 실제 고정 B/C Git archive는 파일2535/2539개 및 legacy/chunked 기본값을 확인했고, CI gate는 이 offline source 검사에서 대역임을 구분했다. 실제 image·AWS·Actions·secret scanner·publish는 NOT_RUN이다. 최종 근거는 `docs/runtime/rt14-fixed-revision-publish.md`, packet 제품 수정 없는 조사 결과는 `docs/runtime/rt14-packet-compatibility-review.md`를 따른다.
