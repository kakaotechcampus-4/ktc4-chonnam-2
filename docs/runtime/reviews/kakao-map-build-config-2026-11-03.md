# 카카오 지도 Web build 전달 검증 기록

2026-11-03 KST · 작성자 정철원(Runtime 구현·Recording) 작업의 검증 근거다. 운영 설정의 원문은 [환경·배포 설정 명세 §2.4](../../management/environment-and-deployment-config.md#24-web-선택적-build-설정)이며 설정표를 복제하지 않는다. 실제 배포 완료 기록이 아니다.

## 1. 확인한 상태와 범위

| 대상 | 확인 결과 |
| --- | --- |
| 지정 브랜치 | `codex/kakao-map-build-config` |
| 시작·검증 source HEAD | `bc8799e1477b77a55a3baa1bb54b196d2b89404c` |
| 시작 working tree·staging | 모두 깨끗함. 기존 변경 없음 |
| 원격 `develop` | `git ls-remote`로 위 source HEAD와 일치 확인 |
| [PR #541](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/541) | 최신 본문·전체 diff·댓글 조회 성공. OPEN·미병합. HEAD `408bede4de6087f1d3034c59f43880e5bbb44012`로 이전 확인과 동일. 원격 PR ref도 대조 |
| 원격 권한 | 조회 성공. `AUTH_REQUIRED` 아님 |
| 원본 consumer | `apps/web/src`에 지도 consumer 없음. 이번 브랜치에서 #541 기능 수정·merge/rebase하지 않음 |
| 제외 | 댓글의 자연어 위치 해석 확장, 현재 위치의 사건 위치 저장, 계약/한도/profile/Case 대기 정책, #549 capacity·CI timeout·재실행 변경 |

CLAUDE 라우터, docs·management·runtime README 규칙, 환경 설정 원문, Ops build/runtime 경계, RT-14 관련 계획·runbook을 필요한 범위로 읽었다. 루트 README의 실행 설정 포인터만 추가했다. Web Owner 문서·제품 정책은 바꾸지 않았다.

## 2. RED → GREEN과 전달 경로

`tests/deploy/test_web_build_config.py`의 두 control을 구현보다 먼저 실행했다.

| 단계 | 직접 실행 결과 |
| --- | --- |
| RED | 2 failed: Web stage의 선택 ARG 부재, publish step의 Repository Variable 공급 부재. 테스트 오타나 tool 부재가 아닌 기대한 배선 누락 |
| GREEN | 2 passed. stage 소비·runtime 비전달·publish 공급·기존 revision/manifest acceptance 보존 검사 |

이 두 검사는 배선에 대한 정적 회귀 control이다. 실제 Vite 전달 성공은 아래 Docker Web stage 실행과 artifact 검사로 별도 입증했다. workflow 자체의 GitHub runner 실행은 `NOT_RUN`이다.

## 3. 실제 Web stage build와 임시 통합

실행 전 Windows 메모리·C: 여유와 Docker/WSL 자원을 조회했다. Windows 여유 RAM은 약 4.7 GiB, C: 여유는 약 11.7 GiB, WSL MemAvailable은 약 6.7 GiB, Docker disk는 약 951 GiB 여유였다. 기존 실행 컨테이너는 0개, 기존 image 5개·volume 3개·cache 34개였다. 공유 자원을 재시작·prune·삭제하지 않았다. 전체 FFmpeg/Paddle image build는 실행하지 않았다.

작업 소유 `.codex-scratch/kakao-build-20261103/`에 tracked build 입력만 `git archive`로 복사했다. `.env*`는 포함하지 않았고 실제 키를 읽거나 공급하지 않았다.

- **원본 단독 사본**: source HEAD의 tracked Web·fixture 입력 + 이번 Dockerfile만 사용.
- **임시 통합 사본**: 위 원본에 고정 #541 HEAD의 Web 변경 5개(246줄 추가)만 patch로 적용. root README는 build 입력에 영향을 주지 않는 설명이므로 통합 patch에서 제외. `kakaoMap.ts`는 고정 HEAD의 blob과 byte 단위 일치 확인.
- 공통 ancestor: `102a49a1269588ecde234341b3b91027686848c7`. 적용한 Web patch SHA-256: `1a2d619642036f61ba017485efdb8eeb4ae4f0fb56628db7d5cd171ccc65dd78`.
- 네 번 모두 현재 Dockerfile의 `--target web-build --platform linux/amd64` 사용. digest 고정 Node 24 stage에서 locked `npm ci`, `tsc -b && vite build`(Vite 6.4.3), 기존 `docker/web_release.mjs`를 실제 실행했다.
- 키 없음은 ARG를 생략했다. 합성 control은 실서비스 키로 오인할 수 없는 문자열을 process env로만 공급하고 `--build-arg VITE_KAKAO_MAP_KEY`로 전달했다. 값 자체는 검증 기록에 출력하지 않는다.
- 각 결과를 네트워크 없는 비실행 컨테이너에서 `docker cp`로 추출하고 기존 `deploy.web_artifact.verify_web()`로 전체 파일 집합·파일별 SHA-256·version/manifest revision을 검증했다. JS를 실행하거나 외부 SDK를 요청하지 않았다.

| 사본·입력 | build | JS의 합성 control | 전체 manifest SHA-256 | revision·파일 검사 |
| --- | --- | --- | --- | --- |
| 원본·키 없음 | PASS | 없음 | `c36265bce7dcb964dd9ac3de1cadda144b7b899d6929ce75cd778d3d8fcad5e2` | PASS |
| 원본·합성 키 | PASS | 없음 | `c36265bce7dcb964dd9ac3de1cadda144b7b899d6929ce75cd778d3d8fcad5e2` | PASS |
| #541 임시 통합·키 없음 | PASS | 없음 | `9efac2863658befab09c773296c44be515a04963fd21cf88d77064190e1b5301` | PASS |
| #541 임시 통합·합성 키 | PASS | 포함 | `59e27ed44da817c5864b5834c0f57c20aa3f4c5e8193aff853b624c6d5e60a33` | PASS |

원본 단독에서는 consumer가 없어 동일한 Web bytes가 나왔다. 따라서 **원본 build-arg 전달만으로 지도 artifact 검증이 끝났다고 보지 않는다.** consumer가 있는 임시 통합 사본에서만 합성 키가 artifact에 반영됐음을 확인했다. 두 사본의 marker에는 비교 control로 같은 source HEAD를 사용했으며, 임시 통합 사본의 marker가 실제 병합 commit을 뜻하지 않는다.

아래 값은 **로컬 Web stage image ID**이며 registry 배포 digest가 아니다. 실제 ECR publish·production image acceptance 근거로 사용하지 않는다.

| 사본·입력 | 로컬 stage image ID |
| --- | --- |
| 원본·키 없음 | `sha256:a20771484c9f9ddb49bc31502056136d4259b164b70952b6f821b230803464de` |
| 원본·합성 키 | `sha256:dfe1aef760d6ec0ecfa312a5e69a389cf019c5d0fc2a2bcbee28e24a93230700` |
| #541 임시 통합·키 없음 | `sha256:b7e305c64c02b7b8cbb38091011f4f4ebcc603f8c740067da9a8a9965ed2b49d` |
| #541 임시 통합·합성 키 | `sha256:87498b368f486ddf01888364d7d387d0b6cb922071277092cc5ea0629a67efa4` |

Docker는 `VITE_KAKAO_MAP_KEY` 이름의 KEY 패턴에 `SecretsUsedInArgOrEnv` 경고를 냈다. 실제 secret을 통과시킨 것이 아니며 브라우저 공개 JavaScript 설정이라는 명세를 유지했다. 경고 검사나 기존 실패 gate를 끄지 않았다.

같은 임시 통합 stage에서 기존 `locationMap.test.tsx`만 네트워크 없이 실행해 **5 passed**를 확인했다. GPS 핀·버튼 전 권한 미요청·위치 실패·키 없음·SDK 실패를 mock으로 확인한 것이며 실제 지도 로드 증거가 아니다.

## 4. 회귀·정적 검사와 한계

| 검사 | 직접 실행 결과 |
| --- | --- |
| 배선 control | RED 2 failed → GREEN 2 passed |
| deploy 전체 focused + `tests/test_runtime_quality.py` | 첫 실행 193 passed·74 setup errors: sandbox 기본 Temp 디렉터리 생성 실패. 작업 소유 `--basetemp`로 재실행 시 246 passed·21 failed: 전부 기존 Linux 배포 symlink 테스트의 Windows `WinError 1314` |
| Linux 배포 symlink/artifact focused | `test_ec2_deploy.py`·`test_web_artifact.py`·`test_web_build_config.py`: **42 passed**, skip/xfail 0. 위 Windows 실패 21개 포함. Docker/AWS 경계는 기존 double이며 실제 host 배포가 아님 |
| Runtime quality | Ruff PASS, mypy Linux·win32 각각 87 source files 오류 0 |
| boundary·Contract | boundary 정합성 위반 0건. Contract 문서 구조 62·JSON 26·의미 fixture 104 검사 PASS |
| 변경 workflow actionlint | 공식 v1.7.12 Windows amd64 zip SHA-256 `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`를 공식 checksum과 대조. `-shellcheck= -pyflakes=`로 YAML·Actions expression PASS. shellcheck/pyflakes는 미실행 |
| diff | `git diff --check` PASS |

전체 로컬 pytest와 전체 mandatory MySQL은 실행하지 않았다. 기존 테스트를 삭제·skip·xfail 처리하거나 실패를 무시한 PASS로 바꾸지 않았다. Windows 오류와 Linux 결과는 구분한다.

Linux 검사 준비 중 고정 Python base image pull은 공유 image/cache 변경 가능성을 이유로 자동 승인 검토가 거부했다. pull을 실행하지 않았으며, 추가 image/cache 생성 없이 이미 있는 로컬 이미지의 Python만 읽기 전용·네트워크 차단 컨테이너에서 사용한다. 현재 저장소 테스트를 read-only mount하고 원래 image의 capacity 코드·설정은 실행하지 않는다.

## 5. 독립 리뷰·정리

구현 이력을 전달받지 않은 fresh 읽기 전용 reviewer에게 현재 diff·요구사항·검증 자료만 제공했다. 초기 리뷰는 기능상 결함 없음, P3 검증 기록 링크 대상 누락 1건이었다. 이 문서를 작성해 보완한 뒤 **같은 reviewer가 재확인해 이전 지적 해소·새 blocking 지적 없음, 요청된 build 배선 범위에서 수용 가능**으로 판정했다.

| reviewer 활동 | 확인 범위 |
| --- | --- |
| 직접 읽기 전용 실행 | 새 control 함수 2개·diff 검사 PASS. 추출 dist 4개의 기존 `verify_web()` 전체 파일/각 SHA/revision 검사 PASS. 합성 control이 임시 통합·합성 입력 JS에만 존재함을 확인. source/고정 PR patch SHA·현재/임시 Dockerfile 일치·결과 manifest hash와 build 로그 image ID 일치 확인 |
| 작성자 증거 검토 | 실제 Docker/npm/Vite build 로그를 확인했으나 Docker build 자체는 재실행하지 않음. Windows 267개 중 실패 21개가 모두 symlink `WinError 1314`임을 집계 확인. 작성자의 Linux 실행·실제 배포 검증을 reviewer 직접 실행으로 표현하지 않음 |
| 같은 reviewer 재확인 | 새 control 함수 2개·diff 검사·설정 명세와 검증 기록 로컬 링크를 직접 다시 확인해 PASS. 기록과 이전 독립 artifact 검사 일치 확인. 작성자 Docker 4건·Linux 42건·지도 mock 5건은 작성자 증거 검토로 구분. 실제 SDK·도메인·배포 NOT_RUN 경계 확인 |

reviewer 재확인 뒤 작업 소유 임시 원본/통합 사본·추출 dist 4개·성공 build 로그·테스트 temp·내려받은 도구를 정리했다. 생성한 고유 image 태그 4개는 각 기록의 image ID와 대조한 뒤 `docker image rm --no-prune`으로만 제거했다. 기존 image 5개와 DB volume 3개는 유지됐고 실행 컨테이너는 남지 않았다. 공유 cache는 prune하지 않았다. 최소 재현 script·source/hash JSON·Windows 오류 분류 JUnit·검증 요약은 작업 소유 ignored scratch에 남겼으며 이 문서에 공개 증거를 요약했다.

최종 지정 브랜치와 source HEAD는 시작 상태를 유지하고, 새 저장소 변경 7개는 미커밋·미스테이징 상태다. 원본 Web 소스·기존 scratch·보존 DB volume은 유지했다. 기존 공유 image/cache를 삭제·prune하지 않았다.

## 6. NOT_RUN과 실제 배포 전 남은 작업

| 대상 | 상태·이후 사용자 작업 |
| --- | --- |
| #541 병합·원본 통합 | `NOT_RUN`. Web Owner와 #541 및 이번 배선의 최종 develop 통합을 검토. 이번 임시 사본은 폐기 가능 검증용 |
| 실제 JavaScript 키·GitHub Variable 설정 | `NOT_RUN`. 사용자가 canonical §2.4 위치에 올바른 공개 키를 공급. runtime.env·REST 키로 대체하지 않음 |
| 카카오 콘솔·도메인 권한·실제 지도 | `NOT_RUN`. 키 소유 앱의 서비스 origin 제한·카카오맵 사용 설정과 실제 브라우저 로드를 별도로 확인 |
| AWS·ECR publish·SSM·deploy·workflow dispatch | `NOT_RUN`. 실제 배포 전 새 revision CI → 검증한 exact image publish/digest 확보 → 승인 tuple과 해당 image의 Web manifest·revision 대조 필요 |
| 같은 SHA의 키 교체·다중 variant 운영 | 현재 ECR immutable SHA tag·host revision 경로가 지원하지 않음. 새 revision으로 기존 절차를 따르거나 별도 release identity 결정을 받아야 함. 기존 검증을 완화하지 않음 |
| 실제 배포 검증 | `NOT_RUN`. 정확한 배포 digest·그 image에서 추출한 artifact 근거와 기존 health/Worker/media/OCR/smoke를 확인. source SHA 또는 합성 control 포함만으로 배포 지도 성공을 선언하지 않음 |

커밋·스테이징·push·PR/댓글·merge·실제 설정 변경은 하지 않는다.
