# EC2 Recording 실행물 로컬 준비 검증

**IN_PROGRESS · Refs #452 · Related #530, #553, #555 · RT-14 후속.** 정철원(Runtime 구현·Recording Owner).
[운영자 단계별 명령](2026-11-03-ec2-recording-probe-runbook.md), [기존 실제 quota 대조 §9·§10](2026-11-03-recording-cpu-quota-probe.md), [준비 시간 분석](2026-11-03-recording-preparation-timing.md)을 연결한다. 이전 실패와 실측 원문을 덮어쓰지 않는다.

## 1. 시작과 근거

| 확인 | 직접 관측·조회 |
| --- | --- |
| branch·HEAD | `codex/issue452-ec2-recording-probe`, `ab614354132888d6ce2a29cd4d9d14e92f219f84` |
| 시작 working tree·index | 비어 있음. branch/HEAD 이동·merge/rebase·commit/push 없음 |
| #555 | GitHub 직접 조회: merged=true, merge SHA가 HEAD와 동일. head `23c0098499772dfa6aaa65311cf7d2da9e4dc050` ancestry exit0 |
| #452 | 최신 본문과 댓글19개 조회. 최신 댓글은 #555 결과 및 배포 머신 후속 구분. 과거 한 행 저장 설명을 현재 구현 설명으로 사용하지 않음 |
| 적용 지침 | 사용자 AGENTS·실제 CLAUDE 라우터·루트 README·docs 운영 규칙·실험 README·scripts README. 적용 경로에서 별도 AGENTS.md 발견 안 됨 |
| 읽은 경계 | 기존 supervisor/Linux bridge/observer/real-media/budget/capacity helper, §9·§10 결과, capacity G1~G6·§9, RT-14 배포/공개 배포/복구 acceptance의 lock·snapshot·원래 서비스 복귀 |

운영자 보고의 e50b2976/2CPU/3.7GiB·available1.6GiB/current/previous/schema·dirty/lock 부재는 이번 작성자의 직접 EC2 조회가 아니다. 지속 자원·credit·최근 배포·최신 청크/metadata 코드 성능을 보증하지 않는다.

## 2. 준비한 실행 경계

| 파일 | 역할 |
| --- | --- |
| `scripts/recording_ec2_package.py` | HEAD 제품·migration·lock의 명시 allowlist archive, 파일/manifest/archive SHA-256, 비정상 member·symlink·탈출/변조 거부. 보호 입력 계획만 별도로 생성 |
| `scripts/recording_ec2_host.py` | Linux MemAvailable/실제 disk gate, 운영 target 배제·snapshot/lock/승인, 유한 Docker 감독·owner 정리 재사용, stage별 새 인증 DB/network/data/work, acceptance→smoke→대표 단일 호출 |
| `scripts/recording_ec2_entry.py` | uid/import/의존성·binary identity, leaf/상위 cgroup·quota/affinity/memory scope, 기존 phase observer·Recording-only 실행과 credential URL 결속, 무미디어 DB/청크/metadata/rollback/sampler acceptance |
| 기존 real-media helper의 최소 확장 | 선택 사항인 명시 placement 파일이 주어진 경우 등록 결과와 exact 대조. 기존 호출의 동작은 유지 |
| `tests/runtime/test_recording_ec2_probe.py` | package·예산·운영 혼입·실패 단계 차단·credential·placement·상위 CPU·권한·원본 최소 집합·snapshot/승인 controls |

Windows ctypes·개인 source 경로·고정 로컬 image ID·과거 CODE_SHA는 Linux 실행물의 기본값으로 복제하지 않았다. 기존 observer/유한 transport/소유 정리/Recording strict·저장/fresh read 경계를 재사용했다. 제품 src는 변경하지 않는다. 실험 DB는 `probe`라는 새 빈 schema를 매 stage 새 data volume에 생성하며 운영 DB URL/runtime.env를 읽거나 복사하지 않는다.

## 3. identity·의존성과 남는 결속

제품 source revision은 준비 HEAD이며 product/migration/lock의 미커밋 byte 차이를 packaging에서 거부한다. 미커밋 하네스는 별도 content hash이며 검증된 commit SHA라고 표시하지 않는다. source tar·manifest·설정·실제 Python 배포판 name/version·ffmpeg/ffprobe hash를 결속한다. source import는 `/repo/src/…` exact 경로를 요구한다. 최종 commit 후 새 HEAD로 다시 package를 만들고 변경 조합을 재검토하는 절차는 runbook §3이다.

운영자 보고 revision e50b2976부터 준비 HEAD까지 pyproject.toml/uv.lock diff는0이고 Dockerfile 변경은 공개 Web build 인자다. 이는 기존 dependency image에 source를 mount하는 후보 근거다. 실제 호환성은 import·migration graph·binary/dependency identity·DB 연결 acceptance로 별도 검증한다.

로컬 runner image에는 RepoDigests가 없었다. **로컬 image ID만 존재하는 검증 전용 패키지**를 생성했고 EC2용으로 표시하지 않았다. MySQL은 실제 로컬 RepoDigest가 있는8.4 이미지를 사용했다. EC2에서는 두 image의 registry digest·amd64·로컬 image ID의 대응을 다시 검사한다. 현재 EC2에서 사용할 runner digest는 이번 세션 **미확정**이며 원격 조회/pull/publish는 NOT_RUN이다. 최신 의존성 image가 반드시 필요하다는 근거도 아직 없다.

## 4. 작성자 직접 로컬 검증

| 실행 | 관측·범위 |
| --- | --- |
| 신규 controls RED | 최초 모듈 부재로8 FAIL. 기본 pytest temp/cache 권한 오류를 분리하고 전용 scratch basetemp·cache 비활성화로 재현 |
| 후속 RED→GREEN | 합성 container signature/운영 경로 겹침, runner 읽기 권한/최소 입력, 운영 snapshot 변화/승인 만료를 추가해 각각 실패 확인 후 구현 |
| 중간 focused | 신규14개와 관련 기존63개, 합계77 PASS. 대역/파일 controls이며 실제 EC2 검증이 아님 |
| 변경 lint | 신규3개·변경 helper·신규 tests의 Ruff PASS |
| package | 로컬 검증용 allowlist268파일. 입력/secret·전체 workspace를 넣지 않음. source unpack·hash 검증 직접 수행 |
| 입력 준비 | 기존 보호 manifest에서 두 파일의 전송 계획·최소 manifest·명시 placement 생성. 원본 내용 읽기/복사/전송 없음 |
| 최초 Linux 시도 b | source archive 검증 후 새 DB/volume/network 생성. runner connection JSON의 root0600 읽기 권한 때문에 FAIL_ENTRY/PermissionError. 수정 전 source·실패 원문 보존, cleanup=true·잔여0 |
| 수정본 Linux 시도 c | 별도 owner/새 패키지·DB/network/volume에서 **PASS_LINUX_ACCEPTANCE**, host 결과PASS·cleanup=true |

c의 실제 runner는 `cpu.max=200000 100000`, affinity/cpuset0~1, memory.max1,342,177,280B·swap.max0이었다. DB는 `cpu.max=50000 100000`, memory.max536,870,912B·swap.max0, effective cpuset0~17이었다. 이는 로컬 Docker Desktop Linux daemon의 실제 scope이며 EC2 CPU 조건이 아니다. Ubuntu WSL 호스트는 같은 daemon endpoint를 사용하고 C backing disk 여유도 별도 gate에 넣었다. EC2에서는 이 로컬 disk 매핑 옵션을 거부한다. Windows 물리 available4,193,562,624B도 초기 환경 확인에서 읽었으나 WSL 논리 RAM과 합산하지 않았다.

c의 무미디어 acceptance는 실제 credential 파일로 MySQL 연결, 빈 schema→Recording head`recording_0002`,600,032B 합성 container signature의3청크 저장/새 물리 연결 조회·hash, float hex까지metadata exact, 별도 publish rollback, 익명 temp4096B sampler 표본3개·실제 leaf·thread/temp 정리, phase2개PASS·hook 원복을 확인했다. **합성 signature는 실제 영상 인코딩/strict decode가 아니다.** 공유 image/cache·보호 volume3개를 보존하고 새 container/network/volume 잔여0을 확인했다.

운영 snapshot/만료 guard와 독립 검토 수정 후 최종 d 조합은 아래에서 별도로 검증했다. c의 성공을 이후 조합의 성공으로 확대하지 않았다.

## 5. 최종 검증·독립 검토

| 최종 작성자 직접 검증 | 결과·한계 |
| --- | --- |
| focused controls | 신규20+관련 기존63=**83 PASS**. archive 탈출/변조·예산·운영 target·이전 단계 실패·credential·placement·메모리 scope·승인 만료·fixture 교체·로컬 daemon 등. 실제 서버 실행을 대신하지 않음 |
| Linux 순수 negative controls | **8 PASS**. RAM 부족·유한 상위 memory scope·remote daemon·filesystem scope 변경·실제 symlink·symlink/중복 tar member·승인 fixture 변조를 거부. 이8개는 Docker/DB/미디어 호출0 |
| 최종 Linux d | 새 owner·새 frozen package에서 실제 **PASS_LINUX_ACCEPTANCE**, host PASS·cleanup=true. DB 시작 전 init의 상위 memory 검사와 DB poll·runner phase 관측을 실제 연결 |
| d 실제 검증 범위 | `recording_0002`·청크/새 물리 연결·metadata exact·rollback PASS, sampler3개·phase2개, 상위 메모리 표본5개·hook 원복. runner/DB actual quota/memory/swap는 c와 동일. 실제 외부 socket/HTTP 시도0·허용된 DB 연결2 |
| d scope 한계 | 로컬 Docker Desktop/WSL Linux이며 EC2가 아님. 유한 상위 memory.max/high는 수용하지 않고 거부. 실제 측정된 Linux host available의 최솟값6,600,171,520B. OS/daemon 정지에서 절대 wall 상한을 보증하지 않음 |
| d 정리 | cleanup9.277초(반올림), 오류0·잔여0. container0·기존 보호 volume3개·기본 network만 유지, image/cache 보존 |
| identity | d manifest·sidecar·archive SHA-256 검증, source268파일과 현재 파일 hash 모두 일치. 현재 제품/하네스가 실제 d 조합과 다르지 않음 |
| 최종 파일 검사 | 변경10파일·로컬 링크28개 누락0, 기존 원본명/원본 경로·이번 생성 credential의 알려진 문자열 일치0, 일본어 문자0·공백/newline·`git diff --check` PASS |
| 보존 | 원본15개는 내용 읽기/재해시 없이 기존 manifest 대비size/mtime15개 일치. src/migrations/lock/Dockerfile/Compose/deploy/workflow의 HEAD diff0. 이전 실패 source/로그를 보존 |

최종 d 패키지 manifest SHA-256은 `1939492fddf6ac8aa48c610ea94ff5dde6964c5b47cd366323a3414145c5a5aa`다. 로컬 검증 전용이며 EC2에 사용 가능한 runner registry digest로 해석하지 않는다. 생성 패키지·증거·입력 전송 계획은 ignored `.codex-scratch/ec2-recording-prep/`에 있으며 원본이 들어 있는 공개 archive는 만들지 않았다.

독립 fresh 읽기 전용 reviewer에게 요구 원문·코드·문서·증거를 전달했고 다음2건을 받았다.

| 지적 | 수정·같은 reviewer 재확인 |
| --- | --- |
| P1: 상위 메모리 한도와 leaf memory/swap 변화 누락 | DB 시작 전 init 검사, 유한 상위 max/high 거부, 상위 scope·한도·current/events/swap 수집과 DB poll 재검사, runner leaf memory/swap 변화 거부. 새 control RED→GREEN |
| P2: 단계 사이 입력/placement identity 교체 가능 | 승인한 최소 fixture hash를 package config에 결속하고 실영상 단계 전후 content/stat/hash·명시 placement를 대조. 새 control RED→GREEN |

같은 reviewer가 수정본의 실제 호출 연결·runbook을 재검토했고 **추가 actionable 지적을 발견하지 못했다**. reviewer는 신규20 controls와diff 검사, d manifest/sidecar/archive·현재 하네스 hash 차이0을 직접 재현했다. d 실제 Docker/DB 결과·네트워크/정리·scope 표본은 **작성자 실행 증거 검토**이며 reviewer가 실행한 것이 아니다. Linux negative8개 역시 작성자 직접 실행이며 reviewer는 스크립트를 읽었다. reviewer의 EC2/Docker/DB/실영상 실행은0이다. 최종 검증 기록의 문서 갱신도 같은 reviewer가 재확인했고, 직접 실행/증거 검토 구분·수치·Git·미검증 한계에 추가 지적이 없었다.

전체 공개 변경은 다음10파일이며, 지정 branch/HEAD 유지·index 비어 있음·미커밋/미스테이징이다.

| 구분 | 파일 |
| --- | --- |
| 신규 실행물 | `scripts/recording_ec2_package.py`, `scripts/recording_ec2_host.py`, `scripts/recording_ec2_entry.py` |
| 기존 경계 확장 | `scripts/recording_real_media_recheck.py` |
| 신규 controls | `tests/runtime/test_recording_ec2_probe.py` |
| 신규 문서 | 이 검증 기록, `docs/runtime/experiments/2026-11-03-ec2-recording-probe-runbook.md`, `docs/superpowers/plans/2026-11-03-ec2-recording-probe.md` |
| 색인 | `docs/runtime/experiments/README.md`, `scripts/README.md` |

## 6. NOT_RUN·보존·운영 전 결정

EC2 접속/전송·CPU credit 확인·서비스 중단·실제10초/120초 서버 측정·20분 성능·배포 E2E·provider/유료 회귀·publish/ECR·workflow dispatch·commit/push/PR/외부 게시는 NOT_RUN이다. 새 실영상120초·기존 A1/B/A2·전체 pytest·mandatory MySQL은 반복하지 않았다.

원본15개·이전 실패 증거·보호 volume3개·공유 image/cache를 보존한다. 새 Docker 자원은 각 stage의owner/name·미사용을 확인해 정리한다. 로컬 보호 패키지/credential/로그/실패 source·입력 전송 계획은 ignored scratch와 로컬 Linux0700 디렉터리에 보존한다. 이를 공개 artifact로 취급하지 않는다.

운영 전 필요한 결정은 실제 policy reserve·중단 후 MemAvailable, 비교 가능한 CPU/quota/상위 cgroup/credit, 후보 registry digest·호환 acceptance, ingress/job/writer/배포/backup 통제·유한 점검 창·복귀 담당, 승인된 보호 전송이다. API·Worker·MySQL 전체 일시 중단 제안은 실제 reserve와 관측 후 판단한다. 예산 미달 시 실행을 거부하며 운영 복귀에 migration/새 배포/config·pointer 변경을 끼워 넣지 않는다.
