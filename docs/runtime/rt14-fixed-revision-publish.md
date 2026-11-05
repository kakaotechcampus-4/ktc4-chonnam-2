# 고정 revision publish — 제어 source와 build target 분리

## 현재 범위

`codex/rt14-publish-fixed-revision`, 기준 HEAD `8d6a0979ff68e3273587ec08397ce05d92f4c865`에서 구현했다. 이번 미커밋 변경의 제어 revision은 아직 고정되지 않았다. B=`ce0750d5a3317ad1c810783d67f8a05ba88bce08`, C 후보=`8d6a0979ff68e3273587ec08397ce05d92f4c865`는 build target이다. 제어 PR SHA와 애플리케이션 target SHA를 같은 것으로 부르지 않는다.

Draft PR 준비이며 실제 Actions·secret scanner·image build/acceptance·AWS·ECR·publish·서버 변경·배포는 **NOT_RUN**이다. 로컬 Docker 재구축·image 복제·staging·commit·push·외부 게시는 하지 않았다. #583·packet/Recording/controller·공개 운영 정책 구현은 변경하지 않았다. 이번 E2E의 Coarse 600초 및 종료 후150초 복귀 조건도 변경하지 않는다.

이 문서는 현재 publish 경로를 설명한다. [배포 설계](rt14-deployment-design.md)의 publish identity를 함께 정합화하며 deploy/rollback의 기존 계약은 유지한다.

## source와 gate

| identity | 고정 방식 |
| --- | --- |
| 제어 workflow/publisher | develop의 실제 dispatch `GITHUB_SHA`; 기존 repo/ID/ref/event와 최신 develop tip push CI 검사 유지 |
| publish target | 필수 전체40자 소문자 commit SHA `publish_revision`; 빈 값·branch·짧은 SHA·tag object는 거부, fallback 없음 |
| Git source | 실제 commit/root tree, 로컬 제어 HEAD 일치, target→control ancestor 검증. GitHub develop ancestry와 target 자체 push CI도 기존 `quality_gate`로 검사 |
| secret scan | publish에는 target SHA, deploy/rollback/smoke에는 기존 `RT14_REVISION`. require-ancestor를 항상 요구하고 전체 control 이력 검사 유지 |
| build context | `git archive target`만 runner temp의 신규 디렉터리에 추출. 제어 checkout·untracked 파일·credential을 복사하지 않음 |
| source 무결성 | Git tree의 파일 집합과 blob object ID를 추출 파일에 대조. 후속 source/manifest 동시 변경도 실제 Git tree와 달라 거부 |

제어/target CI는 source 준비 전에 검사하고 publish 직전에 다시 검사한다. PR CI·이전 성공 run으로 최신 push 실패/진행 중을 대체하지 않는다. source 준비·image identity 단계는 OIDC/AWS를 호출하지 않는다. 기존 `trusted_context`, `quality_gate`, `oidc`, `remote`, `ssm_payload`의 동작은 그대로다.

Git symlink/submodule 등 지원하지 않는 entry와 tar 경로 이탈·symlink/hardlink는 거부한다. archive의 export 변환 등으로 실제 파일이 Git blob과 달라도 실패한다. 그 경우 최신 source로 대체하지 않는다. 제어 source와 build source는 작업 디렉터리 변경/checkout으로 서로 덮어쓰지 않는다.

## build·acceptance·registry 결속

1. target archive에서 `--platform linux/amd64`, `REVISION=$PUBLISH_REVISION`으로 build한다. 공개 Web 키는 기존 Variable→build arg 배선만 사용한다. runtime secret은 build에 공급하지 않는다.
2. image inspect를 내부에서 capture해 Linux/amd64·전체 image ID·OCI revision·단일 `DAESINGO_REVISION`이 target과 일치하는지 검사한다. image ID만 GITHUB_OUTPUT과 보호된 runner state에 기록한다.
3. 기존 Web 전체 manifest/revision 검사·media-preflight·readout-preflight·strict media acceptance를 **고정 image ID**에서 실행한다. target ENTRYPOINT를 상속하지 않도록 `/app/.venv/bin/python`을 명시하고 `-I`, `PYTHONOPTIMIZE=0`으로 assertion 비활성화·Python 환경 우회를 막는다. 서비스의 실제 deploy entrypoint/env는 변경하지 않는다.
4. publish는 같은 source 상태와 image ID를 재대조한다. 기존 OIDC/identity 검증 뒤 ECR repository가 IMMUTABLE인지 확인한다. target tag를 BatchGetImage로 조회해 명시적 ImageNotFound인 경우에만 진행한다. 기존 tag·기타 오류/미확인은 거부한다.
5. alias가 아닌 검증된 image ID를 `:target_SHA`로 tag/push한다. registry의 target tag→digest를 조회하고 digest로 pull한 이미지가 같은 image ID·revision·platform인지 확인한 뒤 기존 `image_verified` digest marker를 출력한다. image ID와 registry manifest digest는 별개 값이다.

검사 내용은 기존 acceptance를 재사용한다. readout-preflight는 offline production engine 로딩이고 실제 전체 OCR/process acceptance나 운영 B→C→B를 새로 수행한 것은 아니다. 그런 검증이 필요한 배포 승인은 별도 exact image에 결속한다.

credential은 기존 temporary Docker config와 captured CLI/password-stdin 범위를 유지한다. 전체 registry URI·env·토큰·AWS 응답을 공개하지 않는다. BatchGetImage의 per-image ImageNotFound와 images/failures 응답은 [공식 API](https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_BatchGetImage.html)를 대조했다. 실제 role 권한/registry 상태는 조회하지 않았다.

이미 tag가 있거나 push 뒤 digest 검증이 실패하면 재게시/덮어쓰기로 복구하지 않는다. push 뒤 실패는 tag가 생성됐을 수 있으므로 운영자가 보호된 읽기 조회로 기존 digest·source·acceptance를 대조해야 한다. 같은 source라도 공개 Web build 입력을 바꾸어 다른 bytes로 재게시하지 않는다. 실제 target 코드가 추가 변경되면 새 SHA·push CI·image·digest를 다시 고정한다.

## 운영자 명령 — 이번에 미실행

제어 PR 승인·병합 및 제어/target push CI 성공 후, 기존 develop 신뢰 경로에서 실행한다. 같은 control SHA로 B/C를 각각 publish하면 Actions run의 head SHA는 **제어 SHA**이며 target은 별도 source marker로 대조한다.

```bash
REPO=kakaotechcampus-4/ktc4-chonnam-2
gh workflow run rt14-deploy.yml --repo "$REPO" --ref develop \
  -f operation=publish -f publish_revision=ce0750d5a3317ad1c810783d67f8a05ba88bce08
gh workflow run rt14-deploy.yml --repo "$REPO" --ref develop \
  -f operation=publish -f publish_revision=8d6a0979ff68e3273587ec08397ce05d92f4c865
```

각 run의 control SHA·target SHA/tree·image ID·Web 검사·acceptance·registry digest를 기록한다. 전체 image URI는 보호된 입력으로만 공급한다. publish 성공은 서비스 변경이나 배포 승인으로 취급하지 않는다. config/schema_parent/rollback_targets/backup-reference·실제 B/C 데이터 호환과 최신 크기 복구 근거가 별도로 필요하다. C 이후 e50 rollback은 승인하지 않는다.

## offline 검증과 한계

세부 실행 로그·JUnit·source 검사·파일 hash는 Windows `.codex-scratch/fixed-revision-publish/`에 보존한다. 초기 RED는 기능 부재를 확인했고, image ENTRYPOINT/optimization 지적은 별도 RED로 재현했다. 첫 GREEN의1 실패는 Windows 기본 temp 경로 cleanup 권한 문제여서 새 시험 temp를 workspace 안에 둔 뒤 재실행했다. assertion·skip·timeout·gate를 완화하지 않았다.

현재 확인: 관련76개 통과 후, 보강된 배포 offline/secret-scan 회귀282개와 Windows에서 가능한 controller 검사11개가 통과했다. controller의 나머지22개 실파일 상태전이 검사는 symlink 환경 제약 때문에 이번 로컬 실행 범위에서 제외했으며 통과로 표시하지 않는다. 실제 image/AWS/secret scanner/전체 controller 전이와 원격 CI는 NOT_RUN이다.

실제 Git objects/archive를 사용하는 source 준비도 실행했다. B2535개·C2539개 파일을 실제 Git blob에 대조했고 각각 writer 기본값 legacy/chunked를 확인했다. source 합계는 약127MB였으며 image 복제는 하지 않았다. 이 검사만 GitHub CI gate를 offline 대역으로 사용했으므로 CI 승인·실제 이미지 검증으로 보고하지 않는다. `real-source-checks.json`에 구분해 기록했다. 제품/packet/controller 파일과 기존 deploy/rollback 관련 함수의 동일성, YAML parse·Bash run step8개 문법·Ruff·경계 검사는 통과했다. Bash는 최초 Windows 권한 오류 뒤 로컬 문법 검사만 권한 제한 밖에서 재시도했으며 workflow 명령은 실행하지 않았다.

독립 reviewer의 P2(target ENTRYPOINT·PYTHONOPTIMIZE가 acceptance를 우회할 수 있음)를 고정 interpreter/격리 모드로 처리하고 재확인했다. 잔여 확정 P1/P2는 없었다. reviewer는 테스트·Docker·AWS를 실행하지 않았다. 이 결과는 실제 publish 성공이나 B/C 배포 준비 완료가 아니다.

packet의 현행 제약과 별도 최소 수정안은 [별도 조사](rt14-packet-compatibility-review.md)를 따른다. 이 publish PR의 source/이미지 결속만으로 C 후보의 packet 검사가 수정되지 않는다.
