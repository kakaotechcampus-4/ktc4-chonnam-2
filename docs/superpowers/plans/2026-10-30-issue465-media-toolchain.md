<a id="issue-465-media-toolchain-implementation-plan"></a>

# Issue #465 미디어 도구 체인 구현 계획

> TDD로 현재 세션에서 실행하고 요청대로 모든 변경을 unstaged 및 미커밋 상태로 유지한다.

**상태:** IN_PROGRESS · Refs #465 · 관련 #460

**목표/명세:** Issue #465 및 Owner 댓글의 결정을 구현한다.
정확히 일치하는 FFmpeg/ffprobe 8.1, 변경하지 않은 Recording strict 검증,
실제 일반 MP4 구체화, #467 fixture 우회 없음.

**아키텍처:** 공식 8.1 소스를 별도 stage에서 빌드한다. 검증된 SHA-256, base image
식별자, Debian package snapshot을 고정한다. 도구 두 개, 필요한 runtime 의존성,
생성된 binary identity manifest만 복사한다. 컨테이너 API/worker 시작과 명시적
preflight는 지원하지 않거나 혼합되거나 변경된 binary를 안전하게 거부한다.
Compose smoke 및 CI로 배포 이미지의 공개 Recording API에 일반 30fps MP4를
실행하고 기존 범용 CI 테스트를 보존한다.

<a id="tasks-and-review-focus"></a>

## 작업과 검토 초점

- [x] Dockerfile 수정 전에 공식 소스 signature/checksum과 불변 image/package 입력을
  검증한다. Notes에 source provenance와 한계를 기록한다.
- [x] 지원하지 않는/혼합 버전, configuration/hash 불일치, 도구 누락, API/worker
  exec 방지에 대한 실패하는 배포 preflight 테스트를 추가한다.
  RED를 실행하고 `docker/runtime.py`에 구현한 뒤 GREEN을 실행한다.
- [x] 30fps/기본 MP4 timescale을 사용하는 실제 공개 Recording MP4 인수 helper를
  추가한다. 이전 Linux 도구로 RED를 실행하고 고정 이미지로 GREEN을 실행한다.
  출력 frame duration/coverage와 decode, IncidentClip, 정리를 검증한다.
- [x] `Dockerfile`의 apt ffmpeg를 고정 source stage로 바꾸고 runtime UID/config/
  health 예산을 보존한다. 필요에 따라 deployment policy 테스트를 확장한다.
- [x] 이미지 미디어 인수 검사를 `scripts/smoke_compose.py`와 CI에 통합한다.
  Docker config/build/startup/readiness/smoke, 집중 deploy/Recording/media,
  AVI/MKV/fallback, #467 chain, 경계/Contract/workflow/diff 검사를 실행한다.
- [x] 정확한 작성자/검토자 증거, #460 명령, 비공개 source 가용성, 정리, 제외 산출물을
  Implementation Notes와 Log에 추가한다.
- [x] 대화 이력이 없는 새 읽기 전용 검토자가 모든 변경을 검사하고 집중 검사를 실행해
  P1/P2/P3를 평가한다. TDD로 지적을 수정하고 같은 검토자에게 재검사를 요청한다.
  전체 회귀/MySQL strict gate는 원격 CI 조건으로 남는다.

<a id="constraints"></a>

## 제약

strict/coverage, timeout, skip/xfail, DB/migration/목록 정책 변경은 없다.
프레임 길이를 추론하지 않는다. 비공개 원본, 자격 증명, 다운로드 산출물,
cache export, raw/JUnit/scratch는 전달 범위에서 제외한다. commit/push/PR 또는 staging은 없다.

<a id="alternatives-considered-implementer-decision"></a>

## 검토한 대안 (구현자 결정)

고정 hash를 가진 공식 서명 소스를 사용한다. 검증 가능한 provenance와 동일 빌드
binary를 위해 선택했다. 제삼자 binary는 별도 산출물/의존성 검증이 필요하다.
기존 Debian package는 Owner의 정확한 8.1 규칙을 충족하지 않는다.
이 구현 상세에 추가 제품/Owner 선택은 필요 없다.
