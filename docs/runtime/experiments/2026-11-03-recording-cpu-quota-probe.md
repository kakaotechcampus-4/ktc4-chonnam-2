# Recording CPU quota 대조 준비·자원 gate 중단 — 2026-11-03

**최신: 새 승인 g의 실제 smoke·A1/B/A2 모두 PASS, 출력 동일. 준비 wall132.800→114.251→131.314초이며 단회 대조의 해석/한계는 §10에 기록한다. §1~8은 최초 RAM 중단, §9는 이전 smoke setup 실패와 수정·무미디어 acceptance의 보존 이력이다.**
이전 시도의 실패/NOT_RUN 표기를 새 시도의 결과로 덮어쓰지 않는다.

**IN_PROGRESS · Refs #452 · Related #530, #552, #553.** 정철원(Runtime 구현·Recording Owner).

**실제 smoke·A1·B·A2는 모두 NOT_RUN이다.** 시작 Windows RAM gate가 실패해
DB·runner·network·volume을 생성하지 않았다. 최소 계측 부품과 합성 controls만 보완했다.
CPU quota 효과·성능 개선·통계적 유의성은 확인할 수 없다. #452 또는 배포 20분 E2E 완료가 아니다.

## 1. 시작 상태·필수 근거

지정 브랜치 `codex/issue452-cpu-quota-probe`, HEAD `7b2f6b8873cc1cdfc7c333ef0f8023143382ee66`.
시작 working tree·staging은 비어 있었다. `46567164`와 `264af65b`의 ancestry는 각각 exit 0이다.
GitHub 조회에서 [PR #553](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/553)의
merged/merge SHA와 원격 develop SHA가 HEAD와 일치했다. 지정 브랜치의 원격 검색 결과는 0개였으며
로컬 브랜치를 push하지 않았다. `git ls-remote`는 네트워크 오류, encoded branch 직접 API 조회는
도구의 URL 검증 오류로 실패했다. 이를 원격 branch SHA 확인 성공으로 기록하지 않는다.
merge/rebase·브랜치 이동·fetch에 의한 ref 변경은 하지 않았다.

사용자 AGENTS 지침과 실제 루트 README·CLAUDE 라우터·docs 운영 규칙·scripts README·Runtime 및
실험 README를 읽었다. 관련 저장소 경로에서 별도 AGENTS.md는 발견하지 못했다.

| 근거 | 이번 확인 범위 |
| --- | --- |
| [#452 본문·댓글 17개](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452) | 기존 실패의 정정, PM의 로컬 1219초 운영 채택·timeout 상향 금지, CPU 인과 대조 후속, PR #553 연결 |
| [준비 시간 분석](2026-11-03-recording-preparation-timing.md) §2~5 | 중첩 없는 기존 집계, runner throttling 부재, publish wrapper의 혼합 비용, 작은 대조 후보 |
| [Coarse 270p 결과](2026-11-03-coarse-270p-probe.md) | 기존 이미지·도구·입력·유한 예산·보호 자원·실패 증거 |
| [P2 계획](elice-runtime-capacity-smoke-plan.md) §9 | G2/G4/G6, reserve 유지·운영 분리·즉시 중단·소유 자원만 정리 |
| [기존 하네스](../../../scripts/recording_real_media_recheck.py)·[budget](../../../scripts/recording_probe_budget.py) | 실제 준비→publish→commit→rollback control→새 물리 연결 복원→detached strict decode와 기존 유한 예산 |
| 제품 호출 경로 | `service.py` → `materialization.py`·`multi_analysis.py`·`chain_clock.py` → `_publish_prepared` → `mysql_repository.py:add_prepared_media` |

기존 분석 원문과 실험 원문은 수정하지 않았다. 기존 encode+probe 83.83%는 현재 시간 소비 구간이며
과거 증가분의 원인별 비중이 아니다. DB throttling은 runner 증거가 아니고,
publish 61.132초에는 하네스 hash/metadata 검사도 포함된다.

## 2. 직접 자원 감사와 중단

2026-11-03 **17:53:46 KST**, 부하 생성 전 Windows API로 실제 가용 RAM과 C 물리 여유를 읽었다.
WSL 논리 RAM을 합산하지 않았다. 초기 sandbox의 CIM/Docker/WSL 접근은 실패했고,
읽기 전용 권한 확장 후 Windows API·Docker 상태를 확인했다. 자동 승인 검토 거절은 없었다.

| 항목 | 직접 관측 또는 기존 기준 | 판정 |
| --- | ---: | --- |
| Windows 가용 RAM | 3,074,957,312B | 기존 시작 예산보다 74,964,992B 부족 |
| 기존 시작 예산 | 3,149,922,304B = 3004MiB | runner1280 + DB512 + host reserve700 + collector/daemon512MiB 유지 |
| C 물리 여유 | 15,730,491,392B | 시작 6GiB 기준은 충족 |
| 전체 gate | `BUDGET_HOST_RAM_STOP` | 실제 입력 실험 진입 금지·재시도 없음 |
| Docker | Engine29.9.2·Linux·cgroup v2, 논리 CPU18·메모리8,072,269,824B | Windows RAM에 합산하지 않음 |
| 시작 자원 | 컨테이너0·기존 보호 volume3 | 새 실험 자원0 |
| WSL | 기본 Ubuntu·버전2라는 상태 조회 | 재시작·cache flush 없음 |

18:05:32 KST 종료 보존 감사에서는 가용 RAM3,858,186,240B·C 여유15,707,840,512B로
순간 자원이 달라졌고, 같은 예산 식의 순수 계산은 PASS였다. 이를 숨기거나 시작 gate 실패와
혼동하지 않는다. 이미 자원 중단으로 닫은 이번 실험을 재개·재시도하지 않았으며,
종료 감사는 보존 확인 용도다. 지속 가용량이나 계측/실행 gate 전체 통과를 보증하지 않는다.
runner/DB leaf·상위 cgroup quota와 cpuset·affinity0,1의 실제 사용 가능 여부는 새 컨테이너를
생성하지 않아 **미확인**이다. 호스트 논리 CPU18만으로 해당 affinity나 2core 여유를 확정하지 않는다.

## 3. 고정 후보·예산과 실행 여부

아래는 실행 설정 후보다. 각 arm의 실제 설정 적용 기록은 없다.

| 단계 | 입력·요청 후보 | runner quota 후보 | 실제 실행·적용 |
| --- | --- | --- | --- |
| smoke, 최대1회 | input-02 단독 logical0~10초 | 1.5core·affinity0,1 | NOT_RUN·RAM gate 중단 |
| A1 | input-01~02 기존 명시 placement 중 logical0~120초 | 1.5core·affinity0,1 | NOT_RUN·smoke 미실행 |
| B | A1과 동일 | 2.0core·affinity0,1 | NOT_RUN |
| A2 | A1과 동일 | 1.5core·affinity0,1 | NOT_RUN |

보호 manifest의 실제 파일을 읽어 원본15개 SHA-256·size·mtime을 확인했다. 기존 #552 보고의
input-01 placement는 `[0,117.933333)`, input-02는 `[117.933333,206.5)`, VIDEO index는 모두0이다.
기존 full-source probe 요약은 각각3218/2657frame, time base1/30000, strict PTS 증가·coverage gap0이다.
별도 기존 진단에서 input-01 duration1000/3000tick이 관측됐다. 따라서 0~120초는 VFR와 seam을
포함할 후보로 유지한다. 촬영의 물리적 연속성을 입증한 것은 아니다.
**새 120초 요청의 실제 선택 frame·coverage·PTS/duration·출력 bytes/hash·provenance 판정은 NOT_RUN**이다.
전체 source 요약이나 FPS×길이로 선택 frame 수를 대신 계산하지 않았다. 다른 영상으로 대체하지 않았다.

| 고정할 항목 | 유한 후보·연결 조건 |
| --- | --- |
| 코드 | 현재 제품 `src/**/*.py` path+content SHA-256(v1)은 `db59f30530b4aee1d36ea63b9bc9909762a81bb84355837d171f8f13d66ca998`로 #552와 동일. 제품 diff 없음 |
| 이미지·import | 기존 이미지 identity를 사용하되 새 실행 직전 검증. 하네스는 실제 Recording import가 `/repo/src/` 아래인지 요구. 이번 새 컨테이너 import 검사는 NOT_RUN |
| 도구 | #552의 FFmpeg/ffprobe8.1 binary hash를 기준으로 새 실행 전 일치 요구. 이번 binary 실행·재해싱은 NOT_RUN |
| profile | Analysis480·veryfast·CRF23·동시성1. Search·provider 실행 없음 |
| 출력·시간 | 명시 실험 config 후보96MiB·240000ms·runner900초, host930초·도구120초·별도 정리60초 |
| runner·DB | runner1280MiB hard/1100soft, DB512hard/440soft, swap 추가0, DB CPU0.5core·packet64MiB·청크256KiB |
| temp·DBdata | temp512MiB soft·DBdata1GiB soft. arm마다 새 전용 DB/network/volume과 같은 빈 schema·migration·seed 상태 검증 |
| 중첩 예산 | 기존 conservative 식 유지: N96MiB일 때 temp2N+64=256MiB, runner4N+240=624MiB, DB증가3N=288MiB, disk증가5N+64+64=608MiB. 실측 peak가 아닌 예산 후보 |
| disk·host | C 시작6GiB·reserve4GiB·누적증가2GiB, host 실행 중 reserve700MiB. 실제 DBdata·누적 증가를 매 단계 다시 차감 |

DB 초기 생성 전 감사의 `db_data=0`은 미생성 후보만 뜻한다. 실제 초기 DB 크기 검증을 대체하지 않는다.
CPU quota 이외에는 모든 제한·입력 mount·도구·계측·DB 초기 상태를 고정해야 한다.
cache flush·공유 Docker/WSL 재시작을 하지 않으므로 cache 온도·호스트 경합·순서 효과는 남는다.
A1/A2는 시간 흔들림 관찰용이며 통계적 유의성을 보장하지 않는다.

## 4. 최소 하네스 보완과 계측의 한계

[CPU 계측 모듈](../../../scripts/recording_cpu_quota_probe.py)은 Docker/DB/미디어를 스스로 실행하지 않는
부품이다. **실행 가능한 전체 Docker supervisor를 완성·검증했다고 주장하지 않는다.**
`run(args, cpu_observer=...)`의 observer 연결과 실제 leaf reader·상위 cgroup/host 수집,
원문 argv의 보호 journal, 소유 자원 생성/정리·실제 quota 적용 검증은 후속 Linux acceptance가 필요하다.
CLI `--recording-only` 자체가 CPU 대조의 모든 gate를 보증하지 않는다.

| 구현·control | 의미·경계 |
| --- | --- |
| runner/DB 각각 cpu.max·cpu.stat·cpuset reader | 실제 지원 필드를 보존. 필수6개 CPU 필드 누락·reset·scope identity/한도 변화는 실패. 없는 memory.peak/events는 null이며0으로 추정하지 않음 |
| phase monotonic wall·전후 snapshot·actor별 delta | parent ID로 중첩 관계 보존. 부모와 자식 wall/CPU를 합산하지 않음 |
| 자식 user/system CPU | Linux `RUSAGE_CHILDREN`의 회수된 자식 누적 차이. 지원 불가 시 null. 실행 중 자식·process별 정밀 CPU와 동일하지 않음 |
| collector 비용 | 전후 수집 wall·각 cgroup read 시각 기록. 경계 수집이며 별도 주기 표본기는 아님. 기존 RSS/temp sampler의200ms 목표·실제 간격·누락은 실측에서 별도 기록 필요 |
| argv 분류 | source/output frame probe·packet probe·encode·remux·concat·strict decode를 실제 옵션으로 분류. 공개 요약에는 경로·필터 문자열 없음. 기존 decode phase 라벨은 호환을 위해 유지하므로 tool_summary를 함께 읽음 |
| Recording 전용 경계 | 10초/120초 고정 후보만 허용. Search 준비/요청 건너뛰기. 저장·commit·rollback·새 물리 연결 복원·strict decode·provenance 검사는 유지 |
| quota·중단·정리 control | A1/B/A2 생성 옵션 중 quota만 변경, affinity고정. callback 실패/False/정리 실패면 다음 arm 차단. exact name/owner·미사용 확인 helper. 실제 Docker update·삭제 기능은 없음 |
| hook 원복 | 성공·제품 예외·collector 실패·중단 때 기존 phase 함수 복원 |

CPU delta의 관측 창에는 경계 collector 작업이 일부 포함될 수 있으며 wall 창과 완전히 같지 않다.
collector 비용을 CPU에서 임의 차감하지 않는다. `throttled_usec`는 절약 가능한 wall time이 아니다.
상위 cgroup quota·cpuset가 leaf보다 강하면 1.5/2.0core 설정만으로 유효 CPU 차이를 보장할 수 없다.
실제 RSS·memory.current/peak/events·temp/disk·DBdata·Aborted_clients·OOM/restart·I/O·호스트 경합은
이번 실측이 없어 모두 관측값이 없다. counter 합성값을 실제 CPU 시간으로 보고하지 않는다.

## 5. A1/B/A2 비교와 판단 가능한 범위

| 비교 항목 | A1 | B | A2 |
| --- | --- | --- | --- |
| source/output/packet probe·encode·remux/concat·strict decode·publish wall | NOT_RUN | NOT_RUN | NOT_RUN |
| runner/DB user/system/usage·periods/throttling delta | NOT_RUN | NOT_RUN | NOT_RUN |
| RSS·cgroup memory·temp/disk·DBdata·Aborted_clients·OOM/restart | NOT_RUN | NOT_RUN | NOT_RUN |
| bytes/hash·metadata exact·PTS/duration·frame 수·provenance | NOT_RUN | NOT_RUN | NOT_RUN |

CPU quota 영향량·배속·A1/A2 흔들림은 **확인할 수 없다**. 과거285.2초와1219.275초의 차이,
청크 저장 단독 추가 비용, 20분 입력 준비 시간, EC2 성능·CPU credit·사용자 허용 대기시간으로
일반화하지 않는다. quota에 따라 출력이 달라지는 경우도 이번에는 관측하지 못했다.
후속에서 차이가 발견되면 허용오차를 넓히지 말고 원인 조사로 남긴다.

## 6. 배포 머신 후속 측정의 최소 선행조건

먼저 동일한 두 실제 입력의 사용/전송 권한·read-only mount·전후 보호 hash/size/mtime,
기존 placement·VIDEO index·실제 선택 frame coverage를 확인해야 한다. 원본 전송은 별도 승인 사항이다.
실제 process revision/image/import·binary hash·Analysis profile을 로컬 대조와 맞추고,
운영과 분리된 새 target에서 reader/writer·`recording_0002`·metadata envelope·backup/rollback decoder
호환성을 확인한다. schema head만으로 rollback 호환성을 확정하지 않는다.

실제 Windows/Linux 물리 자원·상위/leaf quota·cpuset·host 경합·EC2 해당 시 CPU credit와 비용 조건을
확인한 뒤 유한 예산을 명시한다. 위 로컬 수치를 배포 host의 여유로 가정하지 않는다.
collector·quota 적용·원복·소유 자원 정리의 Linux acceptance를 먼저 수행하고, 별도 실행 창에서
smoke1회→120초 A1/B/A2만 진행한다. arm 하나 실패·계측 누락·자원 중단·정리 실패면 다음 arm 금지다.
성공해도 자동 반복·720/1200초 확대·Search/provider·운영 config/DB·AWS/SSM 접근을 허용하지 않는다.

## 7. PM 전달용 비민감 초안 — 게시하지 않음

> 작은 실제 입력으로 CPU quota만 바꾸는 대조를 준비했으나, 시작 실제 가용 RAM이 기존 안전 예산보다
> 74,964,992B 부족해 smoke와 A1/B/A2를 실행하지 않았습니다. reserve는 낮추지 않았습니다.
> 계측 누락·counter reset·중첩·분류·quota 전달·실패 후 차단·원복·정리 경계의 합성 controls를 보완했습니다.
> 이번에는 CPU 효과의 실제 수치가 없습니다. 과거285초와1219초 차이의 주원인·청크 순수 비용은
> 여전히 미확정이며, 로컬1219초를 운영 처리시간으로 채택하거나 Case timeout을 늘리지 않습니다.
> 실제 배포 머신의 revision·호환성·격리 자원·계측·점검 창을 확인한 뒤 작은 구간부터 별도 측정해야 합니다.
> #452와 배포20분 E2E는 계속 IN_PROGRESS입니다.

## 8. 검증·보존·정리

최초 controls는 계측 모듈과 Recording 전용 선택 부재로 실패했고, 구현 후 관련 합성 회귀90개가 통과했다.
boundary 최초 실행은 Windows stdout 인코딩으로 실패했으며 UTF-8 설정 후 재실행은 통과했다.
이 실패를 제품 경계 위반으로 해석하지 않는다.

| 최종 직접 검증 | 결과·범위 |
| --- | --- |
| focused | CPU quota controls33개 + real-media recheck·budget·capacity controls, 합계105 PASS. 실제 미디어/DB 성능 대조가 아님 |
| 변경 lint | 새 계측 모듈·기존 runner·새 controls의 ruff PASS |
| Runtime quality | 기존 quality 도구의 ruff와 Linux/Windows mypy 각각89개 source 검사 PASS. 제품 source 변경 없음 |
| boundary·Contract | 경계 위반0, 문서구조62·JSON26·의미fixture104 검사 모두 PASS |
| 링크·공개 검사 | 두 문서의 로컬 링크20개 존재. 공개5파일에서 알려진 원본명·개인 source 경로·주요 credential 패턴·일본어 문자 일치0, 줄끝 공백/마지막 newline·diff 검사 PASS. 모든 민감정보를 완전 탐지한다는 보장은 아님 |
| 시작/종료 보존 | 원본15개 SHA-256·size·mtime manifest 일치 및 전후 동일, 기존 보호 증거51개 bytes/hash 동일, 제품 source identity 동일 |
| 자원·정리 | 시작/종료 컨테이너0·보호 volume3개 목록 동일. 소유 DB/network/volume/PID 생성0이므로 삭제 대상0. 기존 실패 증거·공유 image/cache 변경 작업 없음 |
| Git | 지정 branch/HEAD 유지, 공개 변경5파일, staging 비어 있음. 미커밋·미스테이징 |

공개 변경 파일은 다음과 같다. Runtime Log는 운영/제품 구현 변경이 없어 수정하지 않았다.

- `scripts/recording_cpu_quota_probe.py`: 계측·분류·순서·정리 선행조건 부품.
- `scripts/recording_real_media_recheck.py`: Recording 전용 후보/성공 조건·선택적 observer·안전한 도구 요약.
- `tests/runtime/test_recording_cpu_quota_probe.py`: 합성 controls.
- `docs/runtime/experiments/2026-11-03-recording-cpu-quota-probe.md`: 이 결과·중단·PM 초안.
- `docs/runtime/experiments/README.md`: 실험 색인 연결.

구현 대화 이력을 전달하지 않은 fresh 읽기 전용 독립 reviewer가 설계·코드·실제 시작 감사·기존 보호
summary·산술·비노출·정리 경계를 검토했다. 첫 controls26개를 직접 실행했고, 정리 helper의 owner
누락/빈값을 허용하는 P2를 재현했다. 작성자는 이를 포함한 음성 controls를 먼저 실패시킨 뒤 수정했고,
미사용 여부의 미확인값도 거부하도록 보완했다. 실제 argv 저장을 구현했다고 읽힐 수 있는 docstring도 수정했다.
같은 reviewer는 수정된 controls33개와 diff 검사를 직접 재실행하고, source identity와 보호51개 hash를
직접 대조했다. 원본 재해시·GitHub 최신 상태는 작성자 감사/조회 증거 검토이며 reviewer 직접 실행과
구분한다. 전체 Runtime quality·boundary·Contract는 작성자 수행 결과에 따르며 reviewer가 원문 로그를
직접 대조한 항목이 아니다. reviewer는 작성자의 focused 최종105 PASS 로그를 별도로 열람했다.
같은 reviewer가 최종 문서·종료 보존 감사·최신 코드 hash·diff·빈 staging도 재확인했으며,
미해결 actionable 지적은 없다. reviewer의 Docker/DB/미디어/provider 실제 실행은0회다.

새 실영상 encode·새 DB 실험·Docker 자원 생성·전체 pytest/mandatory MySQL·Search/provider·외부 HTTP 송신·
AWS/SSM·운영 조회/설정·migration·배포·Case timeout 변경·commit/push/PR/댓글·외부 게시는 NOT_RUN이다.
GitHub의 필수 근거 읽기와 Docker/WSL 상태 조회는 수행했으며 외부 송신 금지는 실험의 media/제품 경로에 적용했다.
공개 문서에는 alias·집계만 사용하고 원본명·개인 경로·RAW·credential·GPS·번호판·Case 식별자를 넣지 않는다.
보호 감사·계획·검증 로그는 새 ignored scratch에만 보존한다.

## 9. 후속 Linux supervisor 연결 — 별도 시도

사용자 후속 승인으로 최초 중단 시도를 재개하지 않고 새 실험 ID들을 사용했다.
최초 보호 scratch68개 파일의 목록·hash는 그대로 보존한다. 기존 감사기를 재사용할 때 생긴 새 bytecode1개는
이번 산출물임을 확인해 새 시도 쪽으로 옮겼고, 이후 bytecode 생성을 끈 상태로 감사했다.

### 9.1 실제 연결과 acceptance 이력

| ID | 실행·검증 | 경계 |
| --- | --- | --- |
| `cpu-quota-linux-20261103-a` | 실제 SQL·ffprobe와 runner/DB observer 연결2phase PASS, 정리 오류0·잔여0 | 실제 입력 미실행. 독립 검토의 안전 보완 전 acceptance 증거로 보존 |
| `cpu-quota-linux-20261103-b` | Docker의 실제 소문자 부재 오류 표기를 인식하지 못해 setup에서 중단 | 안전하게 실패한 하네스 오류. 실제 runner/DB·미디어 실행 전이며 생성된 전용 network/volume 정리. 오류와 재현 control 보존 |
| `cpu-quota-linux-20261103-c` | 수정본 Linux controls45개·실제 SQL/도구·observer2phase·원복·정리 PASS | 이 ID에서만 승인된 실제 smoke1회와 A1/B/A2 순서의 별도 측정을 시작 |
| `cpu-quota-linux-20261103-d` | sampler leaf 수정 후 검증을 시도했으나 DB 준비 중 Docker timeout·정리 실패 | 실제 입력 미실행. 정리629.484초/잔여4를 원문 보존. 이후 exact owner 재확인·별도 정리2.515초/잔여0 |
| `cpu-quota-linux-20261103-e` | Linux47controls·실제Sampler3표본·SQL/도구·원복·정리 PASS | 무미디어 검증만 수행. 정리4.312초/오류0·잔여0. 실제 입력 재시도 없음 |
| `cpu-quota-linux-20261103-f` | 파일 기반 Docker 호출 수정본의 Linux48controls·실제Sampler3표본·SQL/도구·observer2phase·원복·정리 PASS | 무미디어 최종 검증만 수행. 정리5.141초/오류0·잔여0. 실제 입력 재시도 없음 |

새 [호스트 감독기](../../../scripts/recording_cpu_quota_supervisor.py)는 기존 감독기의 Docker 생성·시작·
유한 poll·실제 inspect·소유 자원 정리 방식을 재사용한다.
[Linux bridge](../../../scripts/recording_cpu_quota_linux.py)는 host cgroup namespace의 읽기 전용 cgroup2에서
실제 runner/DB leaf를 별도로 확인하고 phase observer를 실제 Recording 호출에 연결한다.
acceptance에서 실제 runner `150000 100000`, DB `50000 100000`, affinity0,1을 확인했다.
두 actor의 관측된 상위 cgroup2계층은 각각 `max 100000`·cpuset0-17이었다.
호스트의 다른 Windows 작업·물리 CPU 경합까지 제거했다는 뜻은 아니다.

| 보완 | 실제 연결·실패 차단 |
| --- | --- |
| 코드·입력·config 고정 | 제품 source·하네스6개·manifest/config hash를 acceptance에서 고정하고 각 stage 전후 대조. 실제 import와 고정 FFmpeg/ffprobe binary hash도 검사 |
| quota·cpuset·메모리 | inspect NanoCpus/Memory/MemorySwap와 실제 leaf cpu.max/cpuset/memory.max/swap.max를 각각 확인. 상위 identity/quota/cpuset를 phase 경계마다 재확인하고 변경 시 중단 |
| observer·argv | 실제 tool `_run`을 감싸 raw argv를 보호 journal에만 저장. 공개 출력은 고정 status/phase 수. runner/DB 각 counter·자식 rusage·collector 비용을 보존하고 hook 원복 검사 |
| 유한 감독 | 설정된 감독 목표는 DB 준비120초·init30초·runner900초/host 대기930초, setup포함 stage1080초·acceptance300초·정리 별도60초. Docker 실행 기본15초/DB 조회8초와 client 회수0.5초를 분리. d에서 실제 상한 위반이 있었으며 아래 수정/한계를 참조. poll은1초+호출 비용이고 실제 간격·비용 기록 |
| 자원 감시 | 기존3004MiB 시작 gate·host reserve700MiB·C reserve4GiB/누적증가2GiB 유지. runner1100/DB440MiB soft·OOM/events·DBdata·temp·Aborted_clients·restart와 정리 검사. WSL 메모리 합산0 |
| 단계 격리 | acceptance/smoke/각 arm마다 새 DB·빈 schema·내부 network·data/work volume. DB0.5core·512MiB·packet64MiB와 도구/입력 mount 고정. 공유 cache flush·Docker/WSL 재시작 없음 |
| 정리 확인 | 정확한 이름·명시 owner·정지 여부·volume/network 미사용을 삭제 직전에 재조회. daemon/권한 조회 오류는 자원 부재로 취급하지 않고 실패·잔여로 보존 |
| 출력 비교 | B/A2의 content hash/bytes·동일한 숫자/frames/placement/coverage/profile을 A1과 exact 비교. 새 DB의 생성 ref만 제외. 차이가 있으면 다음 arm을 차단하며 허용오차를 넓히지 않음 |

독립 reviewer의 실행 전 지적을 재현하는 controls를 먼저 실패시킨 뒤 수정했다.
Windows 합성 검사와 실제 Linux acceptance를 구분하며, 위 연결 완료 판정은 Linux 안의45개 controls와
실제 SQL·도구 호출·관측된 두 leaf·상위 제한·원복·정리 증거에 근거한다.

### 9.2 현재 자원 gate와 실제 측정

실행 직전 별도 감사(18:31:37 KST)에서 Windows 실제 가용 RAM **5,071,060,992B**,
C 물리 여유 **15,459,196,928B**로 기존 예산을 통과했다. 원본15개 hash·size·mtime을 다시 확인했다.
이는 최초 시도의 종료 RAM 표본을 재사용한 것이 아니다. 감독기는 각 stage의 실제 DB 초기 data 크기와
누적 disk 증가를 포함해 시작 gate를 다시 확인했다.

### 9.3 실제 smoke 중단과 sampler 수정

`c`의 smoke는 **FAIL_SETUP**이다. runner CPU1.5core·affinity0,1·메모리1280MiB·swap추가0,
DB0.5core·512MiB·packet64MiB와 read-only mount는 실제 inspect/leaf에서 확인했다.
그러나 기존 sampler가 host cgroup namespace에서 `/sys/fs/cgroup/memory.current`를 읽어
실제 runner leaf가 아닌 상위 값을 runner 사용량으로 처리했다.
첫 표본 **1,305,178,112B**가 soft cap을 넘으면서 abort marker가 만들어져 다음 단계가 차단됐다.
같은 실행의 관측된 runner leaf 초기 메모리는 **45,076,480B**다. 두 값은 동일 시각의 exact 대조가 아니며
초기 leaf 값으로 이후 peak를 추정하지 않는다. 기존 report의 peak **3,152,695,296B**도 상위 값이므로
runner peak·OOM·메모리 부족의 근거로 사용하지 않는다.

Recording events0·`recording/db_store/db_read=NOT_REACHED`, 자식0·temp0·cleanup 오류0·provider0이다.
소유 자원 정리7.843초·잔여0을 확인했다. 이 smoke 실행 시도1회를 소진한 것으로 처리하고
수정 후에도 실제 입력을 재시도하거나 A1/B/A2로 넘어가지 않았다. strict 검사를 약화하지 않았다.

하네스의 sampler와 최종 peak 조회는 `/proc/self/cgroup`에서 확인한 같은 실제 leaf를 읽도록 수정했다.
private namespace의 `0::/`와 host namespace의 실제 경로를 모두 controls로 검증했다.
`e`의 실제 Linux acceptance는 같은 Sampler thread를 시작해3표본·check·close·thread 종료를 확인하고,
`/work` 익명 파일4096B가 temp 집계에 포함되며 종료 후 temp0임을 확인했다.
이때 세 표본은 각각174,198,784B, 실제 leaf peak는174,297,088B였다.
이 값은 **합성 acceptance의 자원 관측**이며 실제 Recording 입력의 peak나 성능 수치가 아니다.

| 단계 | 실제 실행·설정 | phase wall·CPU/throttling·출력 정확성 |
| --- | --- | --- |
| smoke | input-02 0~10초 요청·CPU1.5 실제 적용 후 setup 실패1회 | 준비·저장·strict/provenance에 미도달. 유효한 Recording phase 비교 수치/출력 없음 |
| A1 | NOT_RUN·예정1.5core | smoke 실패로 차단. 모든 성능·정확성 비교 NOT_RUN |
| B | NOT_RUN·예정2.0core | 실제 quota2.0 적용·입력 실행 없음 |
| A2 | NOT_RUN·예정1.5core | 실제 입력 실행 없음 |

실제 A1/A2의 흔들림이나 CPU quota 효과는 **확인할 수 없다**. CPU 누적값·throttled time을
절약 가능한 wall로 환산하지 않는다. cache/호스트 경합·실행 순서 효과를 제거하지 않았으며
과거285초 차이 전체·EC2·20분 처리시간·사용자 대기시간으로 일반화하지 않는다.

### 9.4 Docker timeout 실패·수정의 정확한 범위

`d`에서는 Docker 호출 timeout과 정리629.484초/잔여4가 실제 발생해, 설정한 정리60초 목표를
충족하지 못했다. 조회 복구 후 이번 DB는 exit137·OOM 표시false·restart0이었지만 종료·지연의
정확한 원인은 확인할 수 없다. 기존 Docker/WSL 재시작·prune·다른 앱 강제 종료는 하지 않았다.
정확한 owner/name·정지·미사용을 재확인한 별도 정리는2.515초/잔여0으로 끝났으며 최초 실패를 덮어쓰지 않았다.

로컬 Python 구현 확인에서 `subprocess.run(capture_output=True, timeout=...)`의 Windows timeout 후
`communicate()`에는 별도 제한이 없는 경로가 있음을 확인했다. 이것이 d 지연의 원인이었다고
단정하지 않는다. 감독기의 Docker 호출은 파일 기반 stdout/stderr·100ms 단위 process wait·deadline·
kill 후 최대0.5초 wait로 바꿔 **무기한 pipe drain 경로를 제거**했다. stdout/stderr가 각각8MiB를 초과하면 실패시킨다.
호출 timeout의 실제 elapsed와 원래 예외/정리 예외 chain을 따로 보존하도록 보완했다.
실제10초 대기 자식을0.15초 제한으로 중단하는 control과 정상 capture를 검증했다.
OS/daemon이 멈추거나 실행 기회가 지연되는 상황에서 절대 wall 상한을 보증한다는 뜻은 아니다.
앞선 단회 acceptance 성공만으로 d 실패나 이 운영 한계를 닫지 않는다.

최종 transport 수정본은 `f`에서 별도 무미디어 Linux acceptance를 통과했다.
Linux48개 controls, 실제 observer2phase·sampler3표본·leaf 일치·thread 종료·temp0·hook 원복을 확인했다.
실제 leaf peak174,653,440B와 정리5.141초/오류0·잔여0을 보존한다. 이는 수정본의 단회 연결 검증이며
실제 Recording 성공·A1/B/A2 효과나 모든 외부 정지 상황의 시간 상한 보증이 아니다.

### 9.5 최종 검증·보존·Git·PM 전달 초안

최종 Windows focused4파일 **112 PASS**(6.47초), 변경 Python4파일 ruff PASS.
Linux 최종 acceptance의48개와 reviewer 직접48개는 각각 다른 실행이며 더해 하나의 테스트 수로 쓰지 않는다.
새 변경과 무관한 전체 pytest·mandatory MySQL·전체 Runtime quality/boundary/Contract 검사를 반복하지 않았다.
§8의 quality·boundary·Contract 결과는 최초 시도의 검증 이력이다.

19:09:29 KST 종료 감사에서 원본15개 SHA-256·size·mtime과 기존 보호 증거51개 bytes/hash,
제품 source identity가 시작 감사와 동일했다. 컨테이너0·기존 보호 volume3개를 확인했다.
최초 RAM 중단 원문, a~f 실패/성공 원문, c 실행 당시 하네스 사본과 c/d/e/f의 하네스6개·manifest/config
사본/hash를 보존했다. 공유 image/cache·Docker/WSL·다른 앱·운영 자원 정리 작업은 하지 않았다.
Docker resource 삭제는 이번에 만든 exact owner/name·정지/미사용을 확인한 대상에 한정했다.

공개 변경은 총8파일이며, 기존5파일에 아래3파일이 추가됐다.

- `scripts/recording_cpu_quota_supervisor.py`: 전용 자원 생성·현재 gate·유한 감독·중단·소유 정리 연결.
- `scripts/recording_cpu_quota_linux.py`: 실제 leaf/상위 제한·phase/argv·sampler·Recording bridge와 Linux acceptance.
- `tests/runtime/test_recording_cpu_quota_supervisor.py`: 연결·조회 실패·고정성·timeout·leaf·출력 exact 비교 controls.

기존 `recording_real_media_recheck.py`에는 실제 leaf current/peak 수정이 추가됐고, 이 문서와 실험 색인은
최초 시도와 후속 결과를 구분하도록 갱신했다. 제품 `src/`·strict 검증·Case timeout·운영 설정은 변경하지 않았다.
지정 브랜치 `codex/issue452-cpu-quota-probe`와 HEAD `7b2f6b8873cc1cdfc7c333ef0f8023143382ee66`을 유지하며
미커밋·미스테이징으로 남긴다.

같은 독립 reviewer가 수정 코드·실제 c 실패·d 정리 실패/복구·e/f acceptance·source 사본·보존 경계를
재검토했다. reviewer 직접 최신 합성48개·diff 검사는 통과했고, Docker/DB/미디어를 직접 실행하지 않았다.
실제 Linux48·Windows112·원본15개 재해시는 작성자 수행 증거 검토와 구분한다.
최종 비노출·링크·종료 보존·Git 검사 및 reviewer 최종 재확인은 별도 검증 기록에 남긴다.

최종 직접 검증에서 공개8파일·로컬 링크22개·실행 사본32개 exact hash·원본15개/보호51개 보존,
새 network/volume 잔여0·빈 staging·branch/HEAD 유지를 확인했다. 같은 reviewer도 최종 문서의
표현 수정을 포함해 위 보존/링크/비노출/소스 사본·Git 상태를 재확인했고 미해결 지적은 없다.
최초 RAM 실패 scratch68개와 c 기존 실패원문33개는 reviewer가 전후 hash를 직접 대조했다.
reviewer의 Docker/DB/미디어 실행은0회이며, OS/daemon 절대 wall 상한 비보장·d 원인 미확정·
실제 Recording/CPU 효과 미확인이라는 한계는 검토 완료와 별개로 유지한다.

> PM 전달 초안(게시하지 않음): Linux 감독기와 실제 runner/DB·sampler 연결을 보완하고 무미디어
> acceptance를 통과했습니다. 자원 gate는 충족됐으나 실제 smoke1회가 계측 경로 오류로 setup에서
> 중단됐고, 최대1회·실패 후 중단 원칙에 따라 A1/B/A2는 실행하지 않았습니다. 오류 수정의 Linux
> 연결 검증은 완료했지만 실제 Recording 성공과 CPU quota 효과는 미확인입니다. Docker timeout/정리
> 실패도 별도 보존했고 소유 자원 회수를 확인했습니다. 과거285초 차이 전체·EC2·20분 처리시간을
> 설명하는 결과가 아니며 운영값이나 Case timeout을 변경하지 않았습니다. #452는 IN_PROGRESS입니다.

## 10. 수정본 실제 Recording CPU 대조 — 새 승인·새 ID

새 사용자 승인에 따라 `cpu-quota-real-20261103-g`에서 실제 smoke 최대1회, 성공·계측·정리 확인 후
120초 A1→B→A2만 실행하는 별도 시도를 시작했다. 이전 c 실패를 재개하거나 성공으로 바꾸지 않았다.
f 무미디어 acceptance의 PASS·실제 Linux observer/sampler·원복 근거를 재사용하며 새 acceptance·controls를 반복하지 않았다.

### 10.1 실행 직전 확인과 고정성

브랜치 `codex/issue452-cpu-quota-probe`, HEAD `7b2f6b8873cc1cdfc7c333ef0f8023143382ee66`,
기존 공개 변경8파일과 빈 staging을 확인했다. 제품 source·하네스6개·manifest hash가 f identity와 exact 일치했다.
runner/MySQL image ID도 실제 로컬 inspect로 대조했다. 각 arm의 binary hash는 기존 고정값을 bridge에서 확인한다.
새 config는 f에서 **experiment_id만 변경**했고, bytes96MiB·duration240000ms·runner900초와 legacy budget을 유지했다.
새 승인 전용 실행기는 이 재사용 근거와 새 결과 marker를 별도 보호 파일에 기록하며, 새 acceptance 성공 marker를 만들지 않았다.

| 실행 직전 직접 확인 | 관측·판정 |
| --- | --- |
| Windows RAM, 19:16:45 KST | 4,804,366,336B, 기존3,149,922,304B 시작 예산 충족 |
| C 물리 여유 | 15,590,621,184B, 기존 시작6GiB·reserve4GiB·증가2GiB 유지 |
| Docker 현재 응답 | 컨테이너/volume/network 목록 조회 각각0.297/0.218/0.188초. timeout 없음 |
| 잔여 자원 | 컨테이너0·보호 volume3개. 이전 실험 prefix의 network/volume 잔여0 |
| 원본·실패 증거 | 원본15개 hash·size·mtime 재확인, 이전 RAM 중단 및 a~f 증거를 새 custody hash로 고정 |

과거 gate나 종료 표본으로 현재 승인을 대신하지 않았다. WSL 논리 RAM 합산·reserve 축소·공유 재시작·prune는 없다.
각 stage에서 실제 DB 초기 data·현재 RAM/disk·누적 증가와 전체 예산을 다시 확인한다.

### 10.2 실제 smoke

input-02 0~10초 smoke1회가 **PASS_RECORDING_ONLY**로 끝났다. 실제 준비·청크 저장·commit·rollback control,
새 물리 연결 조회·metadata exact·bytes/hash·detached strict decode·provenance 검사를 통과했다.
출력4,246,998B·10.0초, runner cgroup peak273,297,408B·temp 표본 최대4,246,998B다.
Aborted_clients0→0, temp/자식/cleanup 오류0, provider/외부 socket/HTTP 시도0이다.
smoke 소유 자원 정리는4.266초·오류0·잔여0으로 끝났다.

| smoke phase | wall 초 | runner usage 초 | DB usage 초 |
| --- | ---: | ---: | ---: |
| Recording 준비 | 40.613567 | 32.411720 | 1.615118 |
| publish 관측 wrapper | 1.886211 | 0.136936 | 0.243922 |
| commit | 0.369746 | 0.019604 | 0.012165 |
| rollback control | 2.231603 | 0.154484 | 0.244144 |
| 새 연결 조회 | 4.733644 | 0.275181 | 0.221420 |
| detached strict decode | 0.574324 | 0.788302 | 0.042553 |

publish는 준비에 포함된다. 각 행의 CPU는 그 관측 창의 누적 증가이며 wall에 더하지 않는다.
이 smoke와120초 대표 요청은 서로 다른 입력 범위이므로 같은 대조군으로 비교하지 않는다.
성공 후 대표 요청 A1→B→A2를 수행했으며 최종 비교·해석·정리는 아래와 같다.


### 10.3 A1/B/A2 실제 비교

세 arm 모두 **PASS_RECORDING_ONLY**다. runner 실제 cpu.max는 A1/A2 `150000 100000`,
B `200000 100000`, affinity는 모두0,1이다. DB는 모두 `50000 100000`,
runner/DB hard memory는1280/512MiB·swap추가0이며 같은 상위 quota max·cpuset0-17·읽기 전용
cgroup2를 확인했다. 코드·도구·profile·packet·동시성·입력/placement·계측 정책은 동일하다.

각 arm에 새 DB/data/work volume·내부 network·빈 schema를 사용했다. 관측된 초기 DB data bytes는
A1 **127,271,189**, B **127,271,222**, A2 **127,271,516**으로 소폭 달랐다.
논리적으로 새 빈 target을 맞춘 것이며 물리적 파일이 bitwise 동일한 초기 상태라고 주장하지 않는다.
최종 DB data 표본 차이도 아래에 그대로 기록한다.

첫 표는 `recording_prepare` 안의 실제 argv leaf와 publish 관측 wrapper를 중첩 없이 분할한 wall이다.
각 actor CPU snapshot 창도 서로 겹치지 않음을 별도로 확인했다. 미분류 잔여에는 Python·I/O·검증·
계측 경계 등이 섞일 수 있어 순수 제품 glue·DB·계측 전체 비용이라고 해석하지 않는다.
CPU 표는 관측 창의 실제 누적 delta이며 parent/child 또는 wall과 합산하지 않는다.
DB 값에는 해당 창의 background/collector 작업도 포함되며 runner 증거로 전용하지 않는다.

| 준비 안 구간 | A1 wall초 | B wall초 | A2 wall초 |
| --- | ---: | ---: | ---: |
| source frame probe(2회) | 53.252378 | 48.163912 | 53.132726 |
| encode(2회) | 39.006416 | 27.731994 | 36.208689 |
| output/remux/final frame probe(5회) | 16.622950 | 15.183311 | 18.115167 |
| packet probe(5회) | 0.267233 | 0.229792 | 0.274480 |
| stream-copy remux(2회) | 0.144673 | 0.137179 | 0.201850 |
| concat mux(1회) | 0.143207 | 0.186972 | 0.149817 |
| 준비 안 최종 strict decode(1회) | 4.321670 | 3.454641 | 4.095083 |
| publish 관측 wrapper(1회) | 5.267872 | 5.503843 | 5.471042 |
| 미분류 잔여 | 13.773825 | 13.659625 | 13.665326 |
| 준비 전체 | 132.800223 | 114.251268 | 131.314181 |

| 구간 | A1 CPU usage초(runner / DB) | B CPU usage초(runner / DB) | A2 CPU usage초(runner / DB) |
| --- | ---: | ---: | ---: |
| source frame probe(2회) | 45.875877 / 1.909421 | 44.113224 / 1.895311 | 47.961384 / 2.163173 |
| encode(2회) | 57.564640 / 1.582624 | 53.431247 / 1.275940 | 54.194175 / 1.654844 |
| output/remux/final frame probe(5회) | 17.430301 / 0.628605 | 15.909845 / 0.624809 | 19.136164 / 0.717849 |
| packet probe(5회) | 0.251137 / 0.002090 | 0.257598 / 0.002815 | 0.220984 / 0.001973 |
| stream-copy remux(2회) | 0.121161 / 0.001190 | 0.143001 / 0.000864 | 0.189755 / 0.118931 |
| concat mux(1회) | 0.141339 / 0.036664 | 0.205184 / 0.001140 | 0.152966 / 0.000952 |
| 준비 안 최종 strict decode(1회) | 6.437308 / 0.136941 | 5.783079 / 0.131599 | 6.059591 / 0.141650 |
| publish 관측 wrapper(1회) | 0.721273 / 1.172303 | 0.873877 / 1.146209 | 0.779477 / 1.192933 |

| 구간 | A1 throttled초(runner / DB) | B throttled초(runner / DB) | A2 throttled초(runner / DB) |
| --- | ---: | ---: | ---: |
| source frame probe(2회) | 0.000000 / 0.125857 | 0.000000 / 0.182922 | 0.000000 / 0.259281 |
| encode(2회) | 16.165741 / 0.338347 | 0.023794 / 0.442780 | 15.009452 / 0.864414 |
| output/remux/final frame probe(5회) | 0.000000 / 0.067457 | 0.000000 / 0.264006 | 0.000000 / 0.482572 |
| packet probe(5회) | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.000000 / 0.000000 |
| stream-copy remux(2회) | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.000000 / 0.063022 |
| concat mux(1회) | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.000000 / 0.000000 |
| 준비 안 최종 strict decode(1회) | 0.566548 / 0.000000 | 0.000931 / 0.000000 | 0.743957 / 0.000000 |
| publish 관측 wrapper(1회) | 0.000000 / 0.166314 | 0.000000 / 0.120605 | 0.000000 / 0.031881 |

| 준비 전체 actor | usage초 | user초 | system초 | nr_periods | nr_throttled | throttled초 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 runner | 130.743529 | 123.792133 | 6.951397 | 1328 | 417 | 16.732289 |
| A1 db | 5.952255 | 3.199661 | 2.752595 | 1050 | 19 | 0.740610 |
| B runner | 122.912986 | 116.774433 | 6.138553 | 1142 | 18 | 0.024725 |
| B db | 5.648388 | 3.075941 | 2.572447 | 974 | 20 | 1.010313 |
| A2 runner | 130.818720 | 124.440920 | 6.377800 | 1313 | 397 | 15.753409 |
| A2 db | 6.492045 | 3.684416 | 2.807629 | 1129 | 28 | 1.826639 |

| 자원(별도 표기 외 bytes) | A1 | B | A2 |
| --- | ---: | ---: | ---: |
| runner RSS 표본 최대 | 158,990,336 | 159,019,008 | 158,994,432 |
| runner cgroup peak | 210,993,152 | 211,079,168 | 211,165,184 |
| temp 표본 최대 | 69,073,643 | 69,073,643 | 69,073,643 |
| DB cgroup peak | 246,747,136 | 246,976,512 | 246,579,200 |
| DB data 표본 최대 | 207,208,725 | 211,403,062 | 207,209,052 |
| Windows 가용 RAM 표본 최소 | 3,996,020,736 | 3,966,803,968 | 4,094,914,560 |
| C 물리 여유 표본 최소 | 15,569,317,888 | 15,553,822,720 | 15,547,125,760 |
| runner 표본 수 | 772 | 736 | 807 |

| 준비 밖 구간 wall초 | A1 | B | A2 |
| --- | ---: | ---: | ---: |
| commit | 0.522329 | 0.619302 | 0.507431 |
| rollback control | 5.733596 | 6.246780 | 5.814449 |
| 새 연결 detached 조회 | 17.819787 | 22.087774 | 20.926436 |
| detached strict decode | 4.228256 | 3.177283 | 4.101951 |

준비 안 strict decode와 준비 밖 detached strict decode는 다른 호출이다.
publish는 준비에 포함되고 하네스 hash/metadata 검사를 포함하므로 순수 DB 저장 시간이나 청크 추가 비용이 아니다.
commit·rollback control·fresh read·detached decode를 위 준비 전체에 다시 더하지 않는다.
B의 fresh read는 A1/A2보다 느렸으므로 모든 단계나 전체 E2E가 개선됐다고 말할 수 없다.

### 10.4 출력·계측·정리의 검증

세 arm은 **34,536,629B·132청크·SHA-256 동일**, profile/metadata/placements/VIDEO index와 frame 요약도 동일하다.
새 DB의 생성 ref만 canonical alias로 대응시켰고 각 arm의 fresh metadata/float hex는 원본 모델과 exact 일치했다.
선택된 두 part는3218/63frame, 최종3281frame·time base1/30·PTS0부터3600·마지막 duration1tick이다.
실제 frame 끝은3601/30초이며 AnalysisSource 모델의 duration 표기는120.033333초다.
요청0~120초와 이 실제 frame coverage를 구분하며, 기존 frame 선택/strict coverage·PTS/duration·
provenance 검사를 유지했다. 허용오차를 늘리거나 frame/시각을 수정하지 않았다.
source 전체 probe의 두 파일 frame 수3218/2657을 실제 선택 frame 수로 바꿔 쓰지 않는다.

모든 arm에서 source 원본 검사·provenance·strict decode·commit/rollback·새 물리 연결 조회·
hash/length/metadata exact를 통과했다. Aborted_clients0→0, 종료 temp0·자식0·cleanup 오류0,
runner/DB OOM events0·OOMKilled false·restart0이다. provider·외부 socket·HTTP 시도도0이다.
각 CPU report의48개 phase가 PASS이고 필수 CPU counter 누락/reset/한도 변화는 없다.
user/system/usage·periods/throttling과 실제 자식 rusage를 보존했으며 필드를 추정으로 채우지 않았다.

runner RSS/temp는 표본 최대이며 진짜 순간 peak 보장이 아니다. cgroup peak는 해당 scope에 청구된 값으로,
호스트 전체 사용량이나 다른 scope의 page cache까지 포함하는 지표가 아니다.
기존 reserve·soft/hard cap·disk 증가 예산을 유지했다.

| 계측 관측 | A1 | B | A2 |
| --- | ---: | ---: | ---: |
| runner 표본 간격 중앙값초 | 0.216929 | 0.210575 | 0.211654 |
| runner 표본 간격 최대초 | 0.621097 | 0.344029 | 0.464599 |
| phase collect callback wall 합계초 | 0.123123 | 0.123929 | 0.110206 |
| 준비 창의 회수된 자식 user/system초 | 120.370830 / 4.584325 | 113.263891 / 4.038889 | 120.868738 / 4.080800 |

runner 목표 간격은200ms이며 관측 간격은 작업 비용/스케줄링에 따라 늘었다. sampler error는 없지만
긴 표본 간격의 순간 peak는 누락될 수 있다. collect callback 비용은 journal 쓰기·rusage·hook 등
**계측 전체 비용**이 아니다. 회수된 자식 CPU도 개별 process의 정확한 실행 창 분해나 wall이 아니다.
host poll은1초+Docker 호출 비용이며 Docker 호출 경과 합계를 준비 시간에서 차감하지 않았다.
CPU delta와 wall의 경계는 collector 전후 때문에 완전히 같지 않고 서로 다른 host/runner clock을 직접 빼지 않았다.

| 소유 자원 정리 | smoke | A1 | B | A2 |
| --- | ---: | ---: | ---: | ---: |
| 정리초 | 4.266 | 4.797 | 4.266 | 3.938 |
| 오류/잔여 수 | 0/0 | 0/0 | 0/0 | 0/0 |

19:30:28 KST 종료 감사에서 원본15개 hash·size·mtime, 보호 증거51개, 제품 source가 시작과 동일했다.
시작 전 고정한 이전 증거425파일의 bytes/hash도 보존했다. 컨테이너0·보호 volume3개,
이번/이전 실험 prefix의 새 network/volume/container 잔여0을 확인했다.
g Docker 호출1711건의 예외0·최대 경과1.875초를 관측했다. 이전 d timeout 원인을 해결했다고 일반화하지 않는다.

### 10.5 관측과 추론의 범위

**[관측]** B의 Recording 준비114.251268초는 A1 대비18.548955초·**13.97%**,
A2 대비17.062913초·**12.99%** 낮았다. A2는 A1보다1.486042초·**1.12%** 낮았다.
이는 준비 구간의 직접 계산이며 사용자 대기시간·전체 E2E 감소율이 아니다.
encode는39.006416→27.731994→36.208689초였고, runner encode throttled는
16.165741→0.023794→15.009452초로 함께 변했다.

**[추론]** 고정된 이 입력·코드·도구·affinity에서 1.5core quota가 encode 시간에 영향을 준다는 해석과
일관된 증거다. 그러나 관측된 준비 차이13~14% 전부를 순수 quota 인과효과로 확정하지 않는다.
source/output probe에서는 runner throttling이0인데도 wall/CPU가 달랐고, A1/A2의 encode·probe 변동은
전체 준비의1.12% 차이보다 크다. cache 온도·호스트 경합·클럭/실행 순서를 통제하거나 계측하지 않았다.
A→B→A 각1회이며 독립 반복·무작위화·통계적 유의성 검증이 아니다.

throttled_usec는 절약 가능한 wall time이 아니며 CPU usage를 wall에 더하거나 quota로 나눠
제한 없는 예상 시간을 만들지 않는다. DB throttling을 runner의 원인으로 쓰지 않는다.
과거285.2초와1219.275초 차이 전체, 청크 저장의 순수 비용, EC2·20분 준비 성능·Search 품질·
Case/Web/Package/다운로드 E2E를 설명하거나 완료한 결과가 아니다.
운영 처리시간·지원 범위·Case timeout을 변경하지 않는다.

### 10.6 검토·Git·PM 전달 초안

제품/하네스 코드는 수정하지 않았으므로 기존 f acceptance와 focused 검증을 재사용했고 새 controls·전체 pytest·
mandatory MySQL·Runtime quality/boundary/Contract를 반복하지 않았다.
이번에는 실제 네 단계 실행·원문 argv 분류·중첩/CPU delta 산술·출력 exact·현재/종료 gate·보존·정리·문서 검사를 수행했다.
공개 변경8파일을 유지하며 이번 후속의 공개 편집은 이 결과 문서와 실험 색인뿐이다.
지정 branch/HEAD·미커밋·미스테이징 상태를 유지한다.

같은 독립 reviewer가 f 재사용 근거·g 실제 원문·phase/CPU/argv 산술·출력·정리·이전425파일 보존과
해석을 읽기 전용으로 검토했다. reviewer의 직접 증거 재계산과 작성자의 실제 Docker/DB/미디어 실행을 구분한다.
reviewer는 최종 표·감소율·actor별 비중첩 counter 창·실제 argv 분류·모델/float hex·출력 동일성·
관측/추론의 한계를 직접 대조했고, 문서·색인 수정 후 같은 reviewer가 재확인해 미해결 지적은 없다.
공개8파일·링크22개·알려진 민감 문자열0·공백/newline·diff·지정 branch/HEAD·빈 staging도 재확인했다.
원본15개 재해시·Docker/DB/미디어·추가 controls는 작성자 수행 증거 검토이며 reviewer가 실행한 것이 아니다.

> PM 전달 초안(게시하지 않음): 수정본의 실제10초 smoke와120초 A1/B/A2가 모두 통과했고 출력은 동일했습니다.
> quota1.5→2.0→1.5에서 Recording 준비는132.800→114.251→131.314초였습니다.
> 이번 B는 A들보다 약13~14% 낮았고 encode throttling 감소가 함께 관측됐습니다.
> 이 입력의 encode에서 CPU 제한 영향이 있다는 해석과 일관되지만, 단회·cache/호스트/순서 한계로
> 관측 차이 전부를 순수 quota 효과로 확정하지 않습니다. 과거285초 차이 전체나 EC2·20분 성능을
> 설명한 결과가 아니며 운영 처리시간·Case timeout은 변경하지 않았습니다. #452와 배포20분 E2E는 미완료입니다.

