<a id="issue-465--mp4-deployment-toolchain-implementation-notes"></a>

# Issue #465 — MP4 배포 도구 체인 구현 참고 사항

**IN_PROGRESS · Refs #465 · Related #460**

<a id="owner-decision-and-investigated-cause"></a>

## Owner 결정과 조사한 원인

[Issue #465](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/465)와
Owner 댓글은 정확히 일치하는 **ffmpeg 8.1 / ffprobe 8.1**을 선택한다.
`materialization.py`는 일반 MP4에 관측된 마지막 frame duration을 요구하며,
검증된 coverage는 기존 fallback/millisecond-MKV 경로에만 제공된다.
Ubuntu 6.1.1 도구는 공개
`RecordingService.prepare_analysis_source_from_resolution`의 **출력** 검증에서
`마지막 frame duration 근거가 없습니다
(duration/pkt_duration 누락)`을 재현한다.

Recording validator, duration/coverage 추론, encoder 인수, fallback 규칙 또는
#467 fixture는 변경하지 않는다. #467의 10fps/1/10-tick 입력은 CI 이식성
fixture이며 일반 MP4의 해법이 아니다. 이 회귀 테스트는 muxer 기본 timescale로
30fps H.264 MP4를 생성하고 1/10이 아님을 검증한다.

<a id="verified-supply-and-reproducible-build-inputs"></a>

## 검증한 공급원과 재현 가능한 빌드 입력

| 입력 | 신원 / 검증 |
| --- | --- |
| 공식 소스 | [ffmpeg-8.1.tar.xz](https://ffmpeg.org/releases/ffmpeg-8.1.tar.xz) |
| SHA-256 | `b072aed6871998cce9b36e7774033105ca29e33632be5b6347f3206898e0756a` — 다운로드 바이트에서 계산; Docker가 추출 전 `sha256sum -c -`로 검증 |
| 분리 서명 | [공식 .asc](https://ffmpeg.org/releases/ffmpeg-8.1.tar.xz.asc), GnuPG로 직접 검증: **Good signature** |
| 릴리스 키 | [공식 키](https://ffmpeg.org/ffmpeg-devel.asc), fingerprint `FCF986EA15E6E293A5644F10B4322F04D67658D8`; upstream MAINTAINERS / [공식 fingerprint 이력](https://ffmpeg.org/pipermail/ffmpeg-cvslog/2015-October/094859.html)과 일치. 로컬 GPG web-of-trust는 여전히 알 수 없으며, 로컬에서 인증된 신뢰를 주장하지 않음. |
| 독립 릴리스 신원 | [공식 mirror n8.1](https://github.com/FFmpeg/FFmpeg/releases/tag/n8.1), tag object `a65b3bfe9dacc3b20597ef199d0afdd8bc8128e2`, peeled commit `9047fa1b084f76b1b4d065af2d743df1b40dfb56`; 이미지 편집 전에 가져와 확인. 빌드는 유동적인 Git 브랜치가 아니라 서명된 릴리스 tarball 사용. |
| Python base | `python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337` — 실제 registry pull/inspect로 확보 |
| uv 빌드 입력 | `ghcr.io/astral-sh/uv:0.11.15@sha256:e590846f4776907b254ac0f44b5b380347af5d90d668138ca7938d1b0c2f98d3` — 실제 pull/inspect |
| Debian 패키지 | `20261027T000000Z`의 서명된 Debian 및 Debian-security snapshot(base의 apt source 주석에 기록된 날짜). 빌드 전에 snapshot 접근과 libx264-dev `2:0.164.3095+gitbaee400-3` 가용성 확인. 과거 만료 검사는 `apt-get update`에만 비활성화했으며 서명/hash 인증은 계속 활성화. |

같은 소스/설정 호출이 두 바이너리를 모두 생성한다. 자동 탐지는 비활성화하고
libx264, zlib 및 drawtext의 font library는 명시적으로 활성화한다. 별도 stage로
compiler, header, source/download 및 uv cache가 runtime에 들어가지 않게 한다.
Runtime에는 libx264-164/zlib1g와 기존 report-stamp capability의 font library
(FreeType, HarfBuzz, Fontconfig, FriBidi 및 DejaVu font), 그리고 이들의 runtime
패키지 의존성만 설치한다. FFmpeg library는 두 도구에 정적으로 링크한다.
ffplay는 빌드/복사하지 않는다. Base, source, Python lock 및 패키지 입력은
고정하지만 플랫폼/builder 간 최종 OCI digest의 비트 단위 동일성은 주장하지 않는다.

<a id="460-support--operator-handoff"></a>

## #460 지원 / 운영자 인계

지원 배포 조합: **이 이미지의 동일한 빌드에서 나온 정확히 ffmpeg 8.1 AND
ffprobe 8.1**. `>=8.1`, suffix, patch-release 또는 Windows 9.x 지원은 주장하지
않는다. Preflight는 PATH가 해석한 각 바이너리의 hash를 빌드가 생성한 manifest와
대조하고, 정확한 release token과 설정 일치를 확인한다. 도구가 없거나 변경됐거나
혼합됐거나 지원되지 않으면 API/worker는 exec할 수 없고 정적인
`media_toolchain_invalid` 진단만 출력한다. Migration과 readiness 예산은 바꾸지 않는다.

```sh
docker build --tag daesingo-issue465:local .
docker run --rm --network none daesingo-issue465:local ffmpeg -version
docker run --rm --network none daesingo-issue465:local ffprobe -version
docker run --rm --network none daesingo-issue465:local python /app/docker/runtime.py media-preflight
docker run --rm --network none \
  --mount type=bind,source="$PWD/tests/deploy/media_acceptance.py",target=/opt/media-acceptance.py,readonly \
  daesingo-issue465:local python /opt/media-acceptance.py
sudo python scripts/smoke_compose.py --evidence /tmp/issue465-compose.json
```

Preflight만으로는 media 인수가 아니다. helper는 등록, 상대 timeline/span 해석,
AnalysisSource 바이트, 명시적으로 관측한 출력 tail duration, 엄격한 coverage/decode,
IncidentClip/provenance 및 정리를 실행한다. 합성 MP4/AVI/MKV와 공개 API로 연결한
일반 MP4 소스 두 개를 다룬다. 회귀 CI job은 동일한 배포 이미지를 빌드/실행하며
인수 컨테이너에는 네트워크가 없다. Compose smoke는 API/worker에서 preflight를
실행하고, migration/readiness 후 기존 persistence/recovery 검사 전에 worker에서
실제 media 인수를 실행한다. 테스트 helper는 읽기 전용 mount이며 이미지 내용이
아니다. 일반 배포판 도구 CI smoke는 별도로 유지하며 MP4 제품 지원을 주장하지 않는다.

<a id="author-execution-evidence-2026-10-30-asiaseoul"></a>

## 작성자 실행 증거 (2026-10-30, Asia/Seoul)

| 조건 | 증거 / 현재 결과 |
| --- | --- |
| 시작 상태 | 브랜치 `codex/issue465-mp4-ffprobe-81`; HEAD/로컬 origin/develop/원격 develop 모두 `177505530cf6bc0f6575d846ae188a0868d4ae3e`; 작업 전 깨끗한 작업 트리와 빈 인덱스 |
| Linux 이전 도구 RED | Ubuntu ffmpeg/ffprobe `6.1.1-3ubuntu5`, 일반 30fps MP4: 공개 AnalysisSource가 출력의 엄격한 missing-tail 검사에서 실패. 동일 바이트 GREEN을 위해 불변 원본 테스트 입력 SHA-256 `5b2187d2557ff8a9cf4ba57b0d0a3f1d4c4b034ec897d50a4272f7b6d162da1f`를 저장소 밖에 보존. |
| Preflight TDD | 새 대조군 RED 14 failures, 이후 Windows unit 파일 **17 passed**; Docker 소스 고정 정책 RED 이후 deployment/runtime 파일 **72 passed** |
| Windows 보조 검증 | 로컬 **9.0.1**; 합성 MP4/AVI/MKV + MP4 chain AnalysisSource/IncidentClip PASS. 집중 deploy/workflow/Recording/worker **296 passed, 1 기존 opt-in skip**, 85.35s. 고정된 8.1 인수가 아님. |
| 구조 검사 | 경계 PASS; Contract 구조 62 / JSON 26 / 의미 fixture 104 PASS; Compose 소스 구조 정책 PASS; diff 공백 PASS. 첫 경계 호출은 Windows cp949 출력 인코딩 오류가 있었고 UTF-8 재실행은 통과. |
| Linux 고정 이미지 / 동일 바이트 GREEN | 빌드/인수 대기; 실제 결과는 아래에 추가하며 대기를 PASS로 해석하지 않음. |
| Docker config/build/startup/readiness/media | 실제 Compose smoke 대기. |
| Linux fallback / IncidentClip / #467 chain | 고정 이미지 집중 실행 대기. |
| 실제 MP4 두 유형 | 알려진 로컬 소스 폴더 / eval dataset 폴더에 없음(MP4 입력 미발견). 비공개 원본은 가져오거나 저장소에 복사하거나 출력하지 않음. 실제 입력이나 provider 첫 검색 성공을 주장하지 않음. |

Docker Desktop의 Windows Linux endpoint를 사용할 수 없었다. WSL Ubuntu의 기존
중단된 패키지 설정을 복구하고 Linux Docker 엔진을 사용했다. Windows mount에서
직접 빌드할 때 Docker sender xattr 권한 문제가 발생해, 추적되는 전달 파일을 담은
Linux native 임시 workspace를 대신 사용했다. 초기 archive 추출은 archive 완료와
경합해 실패했고, archive 완료 후 추출과 빌드를 다시 시작했다. 이 준비 실패들은
성공한 빌드 증거가 아니다.

<a id="remaining-gates-exclusions-and-review"></a>

## 남은 gate, 제외 항목 및 리뷰

DB/migration/inventory 변경은 없다. 전체 필수 MySQL은 의도적으로 다시 실행하지
않았다. 전체 회귀, 필수 MySQL 및 strict gate는 **사용자의 향후 push 이후 원격
CI**에서 계속 요구된다. 이 미커밋 세션에서는 원격 CI를 실행하지 않는다.
timeout, skip/xfail 또는 엄격한 검증 정책을 완화하지 않는다.

RAW/JUnit, scratch, 임시 source archive/checkout, 합성 MP4, GPG home,
credential, Docker cache export 및 비공개 원본은 PR에서 제외한다. 새 읽기 전용
reviewer 지적과 직접 실행한 명령/결과는 작성자 증거와 별도로 추가한다.
staging/commit/push/PR/Issue 변경은 하지 않는다.

<a id="acceptance-follow-up--author-investigation"></a>

## 인수 후속 기록 — 작성자 조사

첫 고정 이미지는 동일 바이트 합성 MP4, 일반 MP4/AVI/MKV 및 MP4-chain media
helper, runtime 도구/cache 감사와 실제 컨테이너 음성 대조군 여섯 개
(API/worker/preflight, 불일치 8.1/5.1.9 및 미지원 8.0/8.0)를 통과했다.
Linux 집중 테스트에서는 **294 PASS / 2 FAIL / 1 opt-in SKIP**이 나왔다.
테스트 전용 mount가 subprocess import path에서 pytest를 누락했고, library 자동
탐지 비활성화로 기존 #467 report export가 사용하는 `drawtext`가 제거됐다.
후자는 초기 빌드의 제품 회귀이며 허용된 한계가 아니다. 기존 export 테스트와
확장 deployment helper 모두 RED를 냈으며, 최종 빌드는 위 font library를
명시적으로 활성화한다. 수정 후 결과는 아래에 별도로 기록해야 한다.

Compose 2.40.3과 2.24.6은 모두 명시적 `create_host_path: false`를 빈 bind
객체로 렌더링하여, 리소스 생성 전에 기존 엄격한 구조 검사가 실패했다.
이는 compose-go의 [bool `omitempty` 필드](https://raw.githubusercontent.com/compose-spec/compose-go/v2.4.0/types/types.go)와
일치한다. 새 **5 RED → GREEN** 사례는 명시적 false를 갖춘 별도 유효 소스를
요구하고, 승인된 mount 대상의 빈 렌더링 bind 옵션만 복원하며, 소스 누락/true,
렌더링된 true 및 알 수 없는 대상을 거부한다. 소스 정책은 그대로이며 해석된
검증은 입력을 변경하지 않는다. 이후 deploy 폴더 전체가 **129 tests**를 통과했다.
실패한 Compose 시도 두 번은 모두 FAIL 증거로 남긴다.

고정 이미지 pytest launcher는 pytest의 테스트 의존성만 일회용 컨테이너로 복사하고
테스트 실행 전에 UID/GID 10001로 낮춘다. 이 의존성은 출하 이미지에 들어가지
않는다. Windows 집중 실행의 기존 skip은
`test_opt_in_tail_only_real_pair_analysis`로, 실제 소스와 명시적 placement가
필요하다. 새 skip은 도입하지 않았다.

<a id="delivery-file-manifest"></a>

## 전달 파일 manifest

- `.github/workflows/python-tests.yml`
- `Dockerfile`
- `docker/runtime.py`
- `scripts/check_compose.py`
- `scripts/smoke_compose.py`
- `tests/deploy/media_acceptance.py`
- `tests/deploy/test_compose.py`
- `tests/deploy/test_runtime.py`
- `docs/runtime/issue465-mp4-toolchain.md`
- `docs/runtime/rt13a-docker-compose.md`
- `docs/runtime/runtime-implementation-log.md`
- `docs/superpowers/plans/2026-10-30-issue465-media-toolchain.md`

<a id="final-pinned-image-author-verification"></a>

## 최종 고정 이미지 작성자 검증

필수 drawtext/font capability를 모두 포함한 최종 소스 빌드는 성공했다.
이미지 ID는 `sha256:70a81faf778ad7c1f694426ae285a1ce3ae0f72982224dc2710ce9c5812ef900`다.
이는 로컬 검증 이미지 신원이며 push한 운영 digest가 아니다.

- 동일 바이트 RED→GREEN: 원래 6.1로 생성한 MP4, SHA-256
  `5b2187d2557ff8a9cf4ba57b0d0a3f1d4c4b034ec897d50a4272f7b6d162da1f`가
  최종 Linux 8.1에서 공개 AnalysisSource / 엄격한 observed-tail coverage / decode
  및 IncidentClip을 통과했다. 실행 후 SHA-256도 동일했다.
- 최종 배포 helper: 일반 MP4, AVI, MKV 및 two-MP4 chain 모두 PASS이며,
  AnalysisSource, IncidentClip, report stamp 및 plate crop을 포함한다.
  컨테이너는 `--network none`과 기본 UID/GID 10001로 실행했다. 원래 고정 입력은
  합성 데이터다. helper의 `actual_source` JSON key는 외부에서 제공된 입력만
  의미하며 실제/비공개 소스 증거로 해석해서는 **안 된다**.
- 최종 Linux 집중 실행: **311 PASS, 1 기존 real-pair opt-in SKIP, 26.14s**.
  명시적 선택: `tests/deploy`, `tests/test_ci_orchestration.py`, Recording의
  `test_materialization_frame_duration.py`, `test_analysis_tail_policy.py`,
  `test_multi_span_analysis_source.py`, `test_multi_span_incident_clip.py`,
  `test_ci_media_smoke.py`, `test_exports.py`, Worker의 `test_media_paths.py`.
  AVI/MKV 검증 coverage, 양성/음성 fallback 정책, IncidentClip,
  #467 single/chain/manifest/error/privacy 및 report/plate 테스트를 포함한다.
- Runtime 감사 PASS: 두 도구의 `ldd`가 해석됐으며 runtime에 gcc/cc/make/curl/uv/nasm,
  source/build 디렉터리, uv cache, apt list 또는 다운로드한 `.deb` 파일이 남지
  않았다. 필요한 동적 의존성과 font 데이터는 남아 있다.
- 최종 실제 컨테이너 안전 차단 대조군 PASS: 통제한 불일치(8.1/5.1.9) 및
  미지원(8.0/8.0) 실행 파일의 manifest hash가 일치해도 모든 API/worker/preflight
  진입점이 계속 차단됐으며, assertion 여섯 개와 정적 오류만 확인했다.
  별도 unit 사례도 바이너리/hash 변경, 설정 차이, 도구/manifest 누락 및
  version suffix/patch/9.x 거부를 다룬다.
- 최종 Windows deployment/workflow 검사: **165 PASS, 17.84s**; 최종 Windows
  9.0.1 helper도 report/plate를 포함해 PASS. 소스 경계, Contract fixture 및
  공백 검사 PASS. README 사실 섹션을 변경 workflow/build와 비교했으며,
  수정해야 할 충돌 문장은 없었다.

이 기록 시점에 전체 Compose smoke는 여전히 대기 중이다. 별도 no-cache 빌드와
이후 migration/readiness/recovery 결과를 위 독립 이미지 인수 성공에서 추론하지 않는다.

<a id="resume-audit--environment-changed-during-interruption"></a>

## 재개 감사 — 중단 중 환경 변경

재개 시 브랜치/HEAD는 `codex/issue465-mp4-ffprobe-81` /
`177505530cf6bc0f6575d846ae188a0868d4ae3e`로 유지됐고, 전달 파일은 동일하게
unstaged 상태이며 인덱스는 비어 있었다. 로컬 `origin/develop`은 독립적으로
`1a784b9d1bad14197f8779387be8ef7e4618fa44`까지 진행됐으며 merge/rebase/reset은
수행하지 않았다. 이전 WSL `/tmp` workspace/report와 검증 이미지는 사용할 수
없었고, 재개 시 관측한 Docker 엔진은 29.9.2, Compose v5.6.1,
Linux x86_64였다. 위에서 이전에 직접 관측한 테스트 결과는 과거 실행 증거로
유지한다. 이전 Compose 실행은 command/view에 성공적으로 도달했지만 최종
보고서는 관측하지 못했으므로 전체 PASS/정리를 추론하지 않는다.

현재 전달 파일만 담은 Linux workspace에서 새로운 격리 Compose smoke를 실행
중이며 보고서는 무시된 Windows scratch에 보존한다. 새 리뷰에서는 deployment/workflow
**165 tests (10.47s)**, 경계, Contract fixture, Compose 소스 구조 및 diff 검사를
직접 통과했다. 최종 smoke 결과와 리뷰 판정은 관측 후 추가한다.

<a id="final-resumed-compose-acceptance-and-review-evidence"></a>

## 최종 재개 Compose 인수와 리뷰 증거

**IN_PROGRESS · Refs #465 · Related #460**

현재 소스의 격리 Compose smoke는 프로세스 exit **0**, 보고서 **PASS**,
정리 **PASS**로 완료됐다. 기록된 열 단계가 모두 통과했다.
`compose_config`, `clean_build`(cache 없음),
`migration_failure_blocks_startup`, `clean_up_migration_ready`,
`pinned_media_materialization`, `cross_container_media_identity`, `command_view`,
`kill_stale_attempt2`, `inspect_secrets_settings`, `recreate_persistence`.
정리 보고서의 `failures`와 `remaining` 배열은 비어 있다. 실행 후 독립 Docker
label/name 쿼리에서 프로젝트 container, volume, network 또는 tagged image가
없었다. 정리 전에 점검한 no-cache 이미지는
`sha256:66ee0bccda379f71bd2948e711d57c2b8a5ed265c8f9e6271d5c8f2722a98883`였다.
push하지 않았다. 원시 보고서는 무시된 scratch이며 전달 파일이 아니다.

<a id="issue-465-completion-condition-evidence"></a>

### Issue #465 완료 조건 증거

| Issue 조건 | 관측 결과 / 남은 경계 |
| --- | --- |
| MP4 첫 분석, 합성 및 실제 두 유형 | 동일 바이트 합성 MP4가 6.1.1에서 RED → 고정 8.1에서 엄격한 AnalysisSource GREEN. 최종 Compose worker media 경로 PASS. 실제 두 유형은 없었으며 실제/비공개 소스/provider 첫 검색 성공을 주장하지 않음. |
| AVI / MKV / fallback 회귀 | 작성자 고정 Linux 집중 311 PASS / 1 기존 actual-pair opt-in SKIP; fallback 성공/실패/엄격성, IncidentClip, #467 chain/error/privacy/export 포함. 최종 Compose MP4/AVI/MKV/chain + export PASS. |
| 지원 ffmpeg/ffprobe 규칙 기록 | 정확히 동일 빌드 8.1, 위 source/signature/hash/base/snapshot 증거 및 #460 운영자 명령; binary/hash/configuration/version 불일치 시 안전하게 차단. |
| CI 또는 Compose의 실제 MP4 회귀 | 둘 다 있음: 회귀 CI의 필수 deployed-image 단계 및 실제 Compose worker helper. 원격 workflow 실행은 사용자의 향후 push를 계속 기다림. |

<a id="fresh-read-only-review-separately-attributed"></a>

### 별도로 귀속한 새 읽기 전용 리뷰

첫 새 reviewer는 구현 대화를 상속하지 않았으며, Windows deploy/workflow
**165 PASS (17.29s)**, Windows helper PASS, 원래 고정 Linux
helper/preflight/runtime/hash 감사 PASS 및 좁은 Linux fallback/IncidentClip/#467
검사 **58 PASS (5.29s), skip 없음**을 직접 실행했다. 최종 증거 재확인은
중단됐으며, 이 결과들은 과거의 reviewer 직접 증거로 유지한다.

재개 후 새 읽기 전용 reviewer가 직접 실행한 내용:

- Windows 9.0.1 deploy/workflow **165 PASS (10.47s)** 및 보조 media 선택
  **146 PASS / 1 기존 actual-pair opt-in SKIP (84.69s)**.
  겹치지 않는 두 reviewer 선택의 합계는 **311 PASS / 1 기존 SKIP**이다.
- 위 현재 no-cache Linux 8.1 이미지: 독립 preflight **exit 0**과
  기본 UID, `--network none`, 일회용 컨테이너 helper **네 그룹 모두
  PASS (6.29s, exit 0)**, report/plate 작업 포함. mount한 helper의
  SHA-256 `dc0eac44516197234f3bad909381f32c96391a44a58a4a51ca2be96333d2afb1`은
  리뷰한 checkout과 정확히 일치했다.
- 경계, Contract fixture, 소스 Compose 구조 및 `git diff --check`
  PASS. 원래 Implementation Log의 바이트 prefix 보존, 인덱스 비어 있음.

새 reviewer는 처음에 사용할 수 없는 이전 image ID로 시도했다.
그 시도에서는 Linux 테스트가 실행되지 않았다. 이후 성공한 현재 이미지 실행은
별도 증거다. 두 reviewer 모두 작성자 리소스를 rebuild, stop, retag 또는 prune하지
않았다. 현재 코드 리뷰에서 조치할 P1/P2/P3는 없었으며, 최종
Notes/Log/report 일관성 재확인은 이 부록 뒤에 이어진다.

<a id="cleanup-exclusions-and-remaining-gates"></a>

### 정리, 제외 항목 및 남은 gate

이 작업을 위해 생성한 공식 tarball/signature/key 다운로드, 공개 소스 checkout 및
전송 archive는 검증 후 소유한 Windows scratch에서 제거했다. 최종 Compose 실행은
자신의 Docker container, volume, network 및 image를 제거했다. 공유 daemon의
다른 작업 image/anonymous volume/cache는 제거하지 않았으며, 전역 prune이나
cache export도 수행하지 않았다. 무시된 원시 보고서, 테스트 출력/임시 파일 및
작은 진단 launcher는 열두 파일 전달 manifest 밖에 남긴다. 저장소 파일이나
로그에 credential 또는 비공개 원본을 추가하지 않았다.

로컬 전체 pytest와 전체 필수 MySQL은 다시 실행하지 않았다. DB/migration/
inventory 변경이 없어 중복 작업이 필요하지 않다. 최종 전체 회귀, 필수 MySQL
및 strict gate는 **push 후 원격 CI 조건**으로 남는다. Windows 고정 8.1과
비 amd64 Linux는 별도로 검증하지 않았다. 원본이 없어 실제 두 유형 MP4 및
provider 첫 검색 인수는 미실행 상태다. timeout, skip/xfail 또는 엄격한 검증을
완화하지 않았다. HEAD는 변경하지 않았고, 전달 파일 열두 개 모두
unstaged/uncommitted 상태이며 commit, push, PR 또는 외부 Issue/Notion 변경은 없다.

동일 reviewer의 최종 Notes/Log/report 일관성 재확인: **조치할
P1/P2/P3 지적 없음**. reviewer는 보존된 열 단계 Compose PASS /
정리 PASS 보고서, 정확한 열두 파일 manifest, 변경 없는 HEAD, 빈 인덱스 및
원래 Log 바이트 prefix를 점검했다. 전체 Compose 실행은 작성자 증거이며,
현재 고정 Linux helper/preflight와 Windows 선택은 위에 표시한 reviewer 직접
증거다. 남은 소스 수정이나 미해결 리뷰 지적은 없다.

최종 리뷰 후 소유한 Linux 임시 workspace `/tmp/issue465-work`도
정확한 경로를 해석하고 확인한 뒤 제거했다. 최종 diff 검사는 깨끗하며,
HEAD와 빈 인덱스는 그대로다.
