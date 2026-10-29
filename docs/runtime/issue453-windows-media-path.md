# Windows media 경로 분리 — Issue #453

**IN_PROGRESS · Refs #453** — 미스테이징·미커밋 검토본. commit/push/PR 생성 없음.

## 기준

- 브랜치: `codex/issue453-windows-media-path`.
- 시작 HEAD, 로컬 `origin/develop`, 원격 `git ls-remote origin refs/heads/develop`:
  `f2943270974e4cb0939cac5b66bfbad270fe5dc1`. 시작 worktree/index clean.
- [Issue 본문](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/453)과
  [최신 Recording Owner 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/453#issuecomment-6493672032)을 직접 확인했다.
- Windows에서 Python 3.12.14, ffmpeg·ffprobe 9.0.1 essentials build를 사용했다.
  이슈의 ffmpeg 8.1 환경과 동일한 버전 검증은 아니다.

## 원인과 변경

`configured_cleanup()`의 handle 기반 canonical temp root가 `MediaRoot`를 통해
media tool 경로까지 전달됐다. Windows concat은 GUID namespace manifest의
상대 조각 경로를 열지 못했다. 실제 합성 입력 2개로 수정 전 실패를 확인했다.

| 경로 역할 | 구현 |
| --- | --- |
| cleanup·lease·보호 경로 비교 | 기존 canonical root 유지. Windows `VOLUME_NAME_GUID`, no-follow traversal 유지 |
| 구성 root | `CleanupScanner.configured_root`에 별도 보관. canonical target을 다시 구성 root로 대체하지 않음 |
| tool·임시 I/O root | 구성 root를 pin하고 Windows handle의 `VOLUME_NAME_DOS`로 일반 절대 경로 조회. POSIX는 기존 절대 경로 사용 |
| 동일성·수명 | configured/canonical/tool 경로 모두 pin하고 device/inode 비교. 생성 및 매 호출에서 검증하고 호출 종료까지 pin·기존 shared lease 유지 |

GUID 문자열로 드라이브를 추측하지 않는다. DOS handle 조회가 실패하거나 지원하지
않는 namespace이면 정적인 오류로 거부한다. 생성자에서 획득한 handle은 반환한다.
호출 전에 root가 junction/symlink로 바뀌면 producer 실행 전에 거부한다.

AnalysisSource의 연결을 `_materialize_many()` 메서드 경계로 이동해 기존
`materialize_chain()`의 조각 쓰기·manifest·probe·읽기·임시 정리 전체를 보호한다.
실행 사이에 aged 조각 파일을 cleanup이 삭제할 수 있던 lease 공백도 회귀로 고정했다.
인코딩·coverage·time-base 정책과 #425·#452의 동작은 변경하지 않았다.

## IncidentClip·export 조사

| 경로 | 확인 결과 |
| --- | --- |
| AnalysisSource | 수정 전 2개 연결 실패, 수정 후 성공. 단일 입력 유지 |
| IncidentClip | 같은 연결 엔진 사용. 수정 전 2개 연결 실패, 수정 후 성공. 기존 strict 처리 유지 |
| Report Video | 같은 temp root의 작업 디렉터리를 사용. 현재 ffmpeg build에서는 수정 전에도 stamp 성공. ordinary cwd 주입 후 stamp·무변환 copy 회귀 통과 |
| Plate Image | 이미지 pipe 입출력으로 temp 경로를 argv에 전달하지 않음. 실제 crop 회귀 통과 |

## RED → GREEN 및 직접 실행

- 최초 Worker 경로 테스트: **3 failed, 3 passed**. ordinary 경로 유지와 실제
  AnalysisSource/IncidentClip 2개 연결 실패. 단일 입력·export는 성공했다.
- 서로 다른 canonical/configured root 거부 테스트: **1 failed, 3 passed** → 통과.
- AnalysisSource 조각 쓰기 중 aged cleanup 테스트: **1 failed**(조각 삭제)
  → `_materialize_many()` 경계 도입 후 통과.
- 최종 focused: **21 passed**. 실제 Windows ffmpeg·ffprobe, 같은 `1/10000`
  time base·64×48 입력, 1개/2개 AnalysisSource·IncidentClip, frame 수·색상 순서,
  Report/Plate, alias·junction·identity 불일치·DOS 조회 실패·오류 개인정보 검사 포함.
- storage 전체: **154 passed**. 기존 cleanup·publish 보호·alias·junction·escape 포함.
- 관련 Recording·Worker·API cleanup: **308 passed, 5 skipped**.
  skip은 실제 원본/실험 설정 opt-in. FastAPI/Starlette 기존 deprecation warning 1건.
- CI orchestration 정책 테스트: **36 passed**. `.github/`와 orchestration 소스 변경 없음.
- WSL Ubuntu/Python 3.12.3: filesystem 모듈 직접 로드 검사 **3 passed**.
  일반 tool 경로·canonical identity·누락 suffix·이중 slash·parent traversal·symlink escape 확인.
- boundary 검사 통과. Contract fixture: 문서 구조 62, JSON 26, 의미 fixture 104 검사 통과.
- 넓은 sandbox 실행은 junction 접근 거부 등의 실패와 장시간 정체로 중단했다.
  해당 pytest 프로세스만 식별해 종료했으며 통과로 집계하지 않는다.
- 넓은 native 실행 1차: **950 passed, 122 skipped, 1 failed**.
  `test_live_root_lease_defers_scan_even_if_mtime_is_old[temp]`에서 성공한 삭제
  집계 직후 `Path.exists()`가 `PermissionError(WinError 5)`를 반환했다.
  변경본과 별도 HEAD archive에서 해당 테스트의 독립 재실행은 각각 통과했다.
  일시적인 OS 상태일 가능성은 있으나 원인은 확인하지 못했으며 실패 이력을 보존한다.
- **동일한 넓은 native 범위 재실행: 951 passed, 122 skipped, 1 warning**
  (130.36초). storage 전체·Recording 전체·관련 Worker·API cleanup·CI orchestration
  포함. skip은 MySQL 또는 실제 원본 opt-in이며 실패한 최초 실행과 구분한다.
- 최종 `git diff --check` 통과. workflow·CI orchestration 파일의 diff 없음.

## 실행 범위와 남은 위험

- Worker composition의 실제 `MediaRoot` → 실제 Recording capability → ffmpeg까지
  합성 입력을 실행했다. DB claim/transaction·provider·별도 Worker process 전체 E2E는 미실행이다.
- 실제 사용자 입력·22개 원본·ffmpeg 8.1 환경은 미실행이다.
- Linux 미디어 통합은 미실행이다. WSL에 pytest·pydantic·ffmpeg가 없어
  dependency 없는 filesystem 검사만 실행했다. 원격 CI는 실행하지 않았다.
- 전체 저장소 pytest는 미실행이다. 변경된 storage·Recording과 관련 소비자 회귀에
  검증을 집중하며 실제 MySQL·provider 의존 테스트는 별도 환경이 필요하다.
- DOS 이름 없는 볼륨/미지원 namespace는 fail-closed다. POSIX 외부 process의
  비협조적 namespace 교체는 기존 소유 root·lease 모델의 한계로 남는다.

## PR 제외 자료

합성 영상·pytest temp root·lock 파일·HEAD 비교용 archive는 작업 전용
`.codex-scratch/issue453-*` 및 저장소 밖 검증 폴더에서만 만들었다.
RAW 로그·JUnit XML·POSIX 확인용 runner·실행 ledger는 저장소 밖에 보존하며
PR 후보 파일에 포함하지 않는다. 사용자 원본·runtime 설정·credential은 추가하지 않았다.

## 변경 파일 전체

1. `src/daesingo/common/storage/_filesystem.py`
2. `src/daesingo/common/storage/cleanup.py`
3. `src/daesingo/common/storage/media.py`
4. `src/daesingo/recording/materialization.py`
5. `src/daesingo/recording/service.py`
6. `tests/common/storage/test_media.py`
7. `tests/worker/test_media_paths.py`
8. `docs/runtime/issue453-windows-media-path.md`

## 독립 리뷰와 종료 상태

구현 이력을 상속하지 않은 fresh read-only reviewer가 1차 검토와 동일 reviewer
재검토를 수행했다. 확인된 P1/P2/P3 수정 요청은 없었으며, 따라서 review-driven
제품 수정은 없었다. reviewer는 테스트를 직접 실행하지 않았고 이 문서의 직접 실행
결과를 독립 재현으로 주장하지 않는다. 기존 WinError 5 실패는 이번 diff의 결함으로
연결할 근거가 없다는 판정이며, 원인이 환경이라고 확정한 것은 아니다.

이번 작업의 pytest 임시 root 15개와 HEAD 비교 archive를 정리했다. 작업 소유
pytest process·미디어·lease 자원은 남기지 않았고, DB/provider/백그라운드 service를
별도 운영 프로세스로 시작하지 않았다. 테스트가 시작한 cleanup thread는 종료됐다.
실제 MySQL/provider 연결은 하지 않았다. RAW/JUnit/runner/ledger만 저장소 밖에 보존한다.
기존 다른 작업의 scratch 자원은 변경하지 않았다.

브랜치와 HEAD는 시작값 그대로이며 staging은 비어 있다. 수정·추가 파일 8개는
모두 미스테이징·미커밋 상태다. commit·push·PR 생성은 수행하지 않았다.
