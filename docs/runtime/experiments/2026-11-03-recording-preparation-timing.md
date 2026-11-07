# Recording 준비 시간 재집계 — 2026-11-03

**IN_PROGRESS · Refs #452 · Related #530, #549, #552.** 정철원(Runtime/Recording).
기존 보호 로그의 분석 결과이며 새 실영상 실행 결과가 아니다.
**과거 285.2초와 이번 1219.275초 차이의 주원인, runner CPU 제한 기여도, 청크 변경의 인과효과는 미확정이다.**
이번 실행에서 시간이 어디에 쓰였는지는 아래처럼 분리할 수 있다. 운영 처리시간·허용 대기시간·Case timeout은 확정하거나 변경하지 않는다.
최소 20분 이상 실제 입력의 배포 E2E 완주는 여전히 NOT_RUN이다.

## 1. 조사 범위와 근거

시작 브랜치 `codex/issue452-preparation-timing`, HEAD `465671643d772847d8eac60ed083663ccbcf6bb7`.
working tree와 index는 비어 있었다. GitHub #552의 merged/merge SHA와 실제 HEAD가 같고,
head commit `d286f822`의 ancestry도 exit 0으로 확인했다. 브랜치·기존 변경을 이동하거나 덮어쓰지 않았다.
사용자 AGENTS 지침, 실제 `CLAUDE.md`, 루트 README, docs 운영 규칙과 실험 폴더 규칙을 적용했다.
적용 경로의 별도 AGENTS.md는 발견되지 않았다.

| 근거 | 이번에 대조한 내용 |
| --- | --- |
| [#452 최신 본문](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)·댓글 15개 | 과거 직접 호출과 웹 실패의 구분, 입력·시간·revision. 과거의 한 행 저장 결정은 현재 구현 설명으로 전용하지 않음 |
| [PM 질문](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6598132602) / [Runtime 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6598204151) | 주원인·CPU·청크 영향·배포 측정, 로컬값의 운영 채택 및 timeout 상향 금지 |
| [#530](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/530)·댓글 / [P2 계획](elice-runtime-capacity-smoke-plan.md) | 0c·G2/G4/G6·Decision Gate, 최소 20분 목표와 실험/운영 구분 |
| [#549](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/549) / [기존 capacity 결과](2026-11-03-capacity-override.md) | 240/480초 준비 경계, 720초 Search cap 거부. 해당 PR 댓글 조회 결과 0개 |
| [#552](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/552)·리뷰/댓글 / [Coarse 결과](2026-11-03-coarse-270p-probe.md) | 720/1200초 직접 관측·유한 예산·실행 identity·품질 후속. 과거 실패 원문 보존 |
| [metadata 수정](2026-11-03-metadata-publish-fix.md) / [청크 구현 메모](../../modules/recording/chunked-prepared-media.md) | exact metadata 검사 이유, reader/envelope/rollback 비호환성 |
| 보호 증거 E1 | #552의 1200초 report·events journal·실행 당시 runner/supervisor/budget 사본·identity·실제 한도·자원 표본 |
| 보호 증거 E2 | 같은 #552의 720초 report·events journal·실행 사본·자원 표본. 동일 입력의 짧은 prefix이며 독립 대조군 아님 |
| 보호 증거 E3 | 기존 입력 manifest·input-01 timing 진단·실행 전후 source/input 감사·종료 자원 감사 |

보호 경로는 문서의 일반적인 “scratch 보존” 표기만으로 추정하지 않고 실제 파일을 찾아 확인했다.
이번 조사 전용 ignored 분석 디렉터리에 E1~E3의 실제 파일 대응·21개 파일 hash와 재집계 결과를 보존한다.
공개 문서는 alias·집계만 사용한다. 원본명·개인 경로·GPS·번호판·credential·Case 식별자·RAW는 포함하지 않는다.
과거 22개 실행의 상세 events/실행 하네스 원문은 이번 관련 보호 디렉터리 조사에서 확보하지 못했다.
과거 수치는 #452 본문에 보고된 증거이며, 이번에 과거 실행을 재집계하거나 원본 22개를 확보한 것이 아니다.

### 실행 당시 코드 대조

E1의 runner 사본과 현재 `scripts/recording_real_media_recheck.py` SHA-256은 모두
`c1f680d4f38f6f1a19d9f0f0b74754842bafade11f92483aadb906e4fa7ce5d3`이다.
E1 보고 revision은 `bf283652e0826df7c75ede44750311e8b1c3036c`이고,
실행 전·후 감사 및 이번 실제 `src/**/*.py` path+content SHA-256(v1)은 모두
`db59f30530b4aee1d36ea63b9bc9909762a81bb84355837d171f8f13d66ca998`이다.
따라서 아래 호출 의미는 현재 코드만으로 과거 동작을 가정한 것이 아니라 실행 사본·identity와 대조한 설명이다.
과거 #452의 `f313cf3a` 코드도 읽었지만 실제 과거 설정·도구 binary·계측기를 복원했다고 주장하지 않는다.

## 2. 비교 조건과 시간 경계

| 항목 | 과거 #452 | #552의 E1(1200초) | 비교 판정 |
| --- | --- | --- | --- |
| 입력 | 다른 MP4 22개, 총 1166.13초·약 1.72GiB(#452 보고) | 보호 MP4 input-01~13, 명시 placement 0~1228.799999초 중 요청 0~1200초 | 동일 입력 아님. 20분이라는 길이만으로 작업량 동등 가정 불가 |
| source video | H.264·1920×1080·30000/1001·time base 1/30000(#452 보고) | H.264·1920×1080·time base 1/30000. manifest avg_frame_rate는 input-01 48270/1769, 나머지 30/1 | 일부 속성만 같음. 과거 개별 frame 수·duration 분포 UNKNOWN |
| 실제 frame | 과거 총 frame 수 UNKNOWN | source 전체 13파일 probe 36,544frame, 선택 출력·최종 35,681frame | 마지막 파일 일부만 선택. FPS×길이로 frame 수 대체 금지 |
| 가변 duration | 원문만으로 VFR 여부 확정 불가 | input-01 진단에서 duration 1000/3000tick·strict PTS 증가. 개별 출력은 1/30000, remux/최종은 1/30 | exact-clock remux 경로가 실제 호출됨. 과거와 같은 작업 아님 |
| 출력 | 234,566,319B·854×480·1/30000 | 366,121,221B·1,397청크, Analysis 480/veryfast/CRF23, 최종 1200.033333초 | 과거 높이 외 preset/CRF의 실행값 UNKNOWN. 출력 크기는 내용·설정의 공동 결과 |
| OS·revision | Windows·Python3.12, 관찰 6141a5a9 / 직접 재현 기준 f313cf3a | Linux 컨테이너, 위 E1 revision/source identity | 코드·OS·도구 실행 환경 다름 |
| 도구 | ffmpeg/ffprobe 69회, 가장 긴 최종 show_frames 27.7초(#452 보고), binary/version UNKNOWN | FFmpeg/ffprobe 8.1, 아래 hash 고정. 준비 안 도구 95회 | 계측 경계까지 다름. 69↔95만으로 중복 비용이나 회귀 확정 불가 |
| CPU | 코어·quota·affinity·호스트 경합 UNKNOWN | runner 실제 inspect 1.5core·affinity 0,1. DB 생성 사본은 0.5core, DB cpuset 지정 없음 | runner 영향량은 A/B 부재. DB quota의 실제 inspect 필드는 보존 자료에서 미확인 |
| 메모리 | 실제 한도 UNKNOWN | runner Memory=MemorySwap=2,281,701,376B(2176MiB); DB 종료 감사는 둘 다 536,870,912B | swap 추가 0. DB cgroup/호스트·파일 cache를 혼동하지 않음 |
| DB | MySQL8.4·packet64MiB·저장 실패 | MySQL8.4.13·packet67,108,864B·256KiB 청크·정확 metadata envelope | 성공 저장을 과거 실패 저장과 성능 대조할 수 없음 |
| 시간 경계 | 개별 materialize 22개 합계 240.8초, concat까지 누적 285.2초, 저장 실패 +1.6초; resolve 1.8초 별도 보고 | `prepare_analysis_source_from_resolution` 반환까지 1219.275초, publish 포함·commit 제외 | 285.2↔1219.275는 서로 다른 포함 범위. 과거 resolve 포함 여부의 세부 타이머는 원문 부재로 재확인 불가 |
| 계측 | 세부 observer·sampling overhead UNKNOWN | 200ms 목표 sampler·journal·hash/metadata 검증·driver packet observer·host/DB collector | 계측 없는 동일 조건 대조가 없어 overhead 인과효과 UNKNOWN |

고정 image는 `sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`.
ffmpeg binary SHA-256은 `19e0073f42f3cc0c1880ac9a4a91fc6c42d511bec9497db03872cc527791c91a`,
ffprobe는 `ec4bde78f8b08c56109d68fffb16e9972ae7543ed62253fd90e699dda4a0f975`이다.
후속 대조에서는 이 identity를 고정하고 도구 버전만 같다는 것으로 대체하지 않는다.

직접 계산한 단순 비율은 1219.274873/285.2=4.275배다. publish 관측 구간을 제외해도
1158.142580초·4.061배지만, 이는 경계를 일부 맞춘 산술이며 성능 회귀 배수·CPU 효과가 아니다.
입력 길이 비율 1200/1166.13=1.029배도 영상 복잡도·frame duration·검증 경로 차이를 통제하지 않는다.

## 3. E1/E2 시간 재집계

E1 report events 124개와 journal phase_end 124개, E2는 각각 84개를 종료 순서·전체 event 값으로 대조했다.
각 event의 같은 runner monotonic 시작·종료로 containment를 확인하고 아래 최소 구간의 interval union을 계산했다.
선택 구간은 서로 겹치지 않았다. `chain_total`·`individual_materialize`·trace·그 안 도구 시간은 다시 더하지 않는다.
원문 double로 계산하고 표만 소수 셋째 자리로 반올림했다. E1 표시 행의 반올림 합계는 전체와 0.001초 다를 수 있다.

### 준비 1219.275초 안의 서로 겹치지 않는 구간

| 분류 | E1 호출 수 | E1 wall 초 | E1 준비 대비 | E2 720초 wall 초 |
| --- | ---: | ---: | ---: | ---: |
| source frame probe 도구 | 13 | 335.774 | 27.54% | 213.915 |
| 개별 encode 도구 | 13 | 484.410 | 39.73% | 292.695 |
| 개별 출력 frame probe 도구 | 13 | 64.792 | 5.31% | 39.493 |
| remux 전 packet probe 도구 | 13 | 0.661 | 0.05% | 0.351 |
| stream-copy remux 도구 | 13 | 2.589 | 0.21% | 2.359 |
| remux 출력 frame probe 도구 | 13 | 68.180 | 5.59% | 38.198 |
| remux 출력 packet 검증 도구 | 13 | 0.643 | 0.05% | 0.368 |
| concat mux 도구 | 1 | 0.935 | 0.08% | 0.760 |
| 최종 frame probe 도구 | 1 | 67.256 | 5.52% | 37.310 |
| 최종 packet 검증 도구 | 1 | 0.445 | 0.04% | 0.263 |
| 최종 strict decode 도구 | 1 | 52.742 | 4.33% | 28.879 |
| DB publish 관측 wrapper | 1 | 61.132 | 5.01% | 36.381 |
| 위 도구/publish 밖 잔여 | — | 79.715 | 6.54% | 55.113 |
| **Recording 준비 전체** | — | **1219.275** | **100%** | **746.085** |

도구 95회 = probe 67 + encode 13 + remux 13 + concat 1 + 최종 strict decode 1이다.
**하네스의 `recording_tool_decode` 14회는 실제 strict decode 14회가 아니다.**
사본의 분류기는 ffprobe/concat/`-vf` 이외를 decode로 표시한다.
`chain_clock.prepare_mixed_parts`의 13회 `-c:v copy` remux가 이 라벨에 들어간다.
순서(처음 packet probe 13회 → remux/frame/packet 각 13회 → concat/frame/packet/strict decode)와
실행 당시 source identity·40개 frame summary를 함께 대조했다. 사본에 실제 Recording argv 전체가 없으므로
이 분류는 호출 구조와 기록의 교차 확인이며 argv 원문을 새로 관측한 것은 아니다.

probe 합계는 **537.751초(44.10%)**, encode+probe는 **1022.161초(83.83%)**다.
이는 도구 호출·대기 경계의 wall time이며 순수 codec CPU 시간은 아니다.
현재 실행의 큰 시간 소비 구간은 확인했지만, 과거 증가분의 원인별 비중은 계산할 수 없다.
반복 frame probe/packet 검사는 frame coverage·remux 전후 clock·seam PTS/DTS/duration과 최종 정확성을 확인한다.
필요성을 조사하지 않고 불필요한 검증으로 판정하거나 생략 후보로 확정하지 않는다.

### trace의 Python 처리·I/O·잔여 경계

| 관측 경계 | E1 wall 초 | 의미·한계 |
| --- | ---: | --- |
| 개별 materialize 13개 합계 | 909.884 | source snapshot/probe·encode·출력 검증·read·원본 재검증을 포함. 위 표에 더하지 않음 |
| trace source_snapshot / source_verify 합계 | 11.281 / 11.547 | `_snapshot`의 stat/hash I/O 포함. 순수 Python CPU가 아님 |
| trace source_probe / output_probe | 336.450 / 65.058 | 안쪽 도구 335.774 / 64.792를 포함 |
| 위 두 wrapper에서 도구를 뺀 값 | 0.676 / 0.266 | JSON parsing·source `_frames`·하네스 summary/journal 등 혼합. 순수 metadata 비용으로 확정 불가 |
| trace frame_prepare / output_validate | 0.030 / 0.404 | 선택 frame·정확 PTS/형식/coverage 대조의 계측 구간 |
| trace bytes_read / bytes_validate | 0.232 / 0.000164 | 후자는 빈 bytes 검사 구간이며 MP4 box 검사는 그 밖에도 있음 |
| trace 내부의 9개 phase 밖 잔여 | 0.147 | trace 전체909.718초에서 9개 phase를 뺀 값. cleanup/모델/box 등 혼합. 외부 materialize wrapper909.884초와 구분 |
| chain 전체 | 1130.314 | 개별 materialize·원본 snapshot 전후·packet/clock 처리·remux/concat·최종 검증·파일 I/O 포함 |
| 준비 전체 − chain − publish | 27.828 | service의 timeline 재확인·원본 조회/입력 구성·모델·후처리 등 혼합, 세부 미계측 |

위 표는 중첩된 설명용 부분집합이다. 마지막 열의 미계측·I/O를 모두 metadata 또는 overhead로 이름 붙이지 않는다.
79.715초 잔여에는 알려진 snapshot/hash와 Python frame 처리, 파일 I/O, DB/service 조회, cleanup,
하네스 관찰 비용, scheduler 대기가 섞여 있다. 정확한 상호 비중과 계측의 추가 비용은 UNKNOWN이다.
snapshot은 원본 불변성 검사이고 packet/frame 비교는 정확성 검사다. 비용이 있다는 사실만으로 제거하지 않는다.

### 준비 밖 phase와 CPU 시간

| E1 경계 | 직접값 | 1219.275초와의 관계 |
| --- | ---: | --- |
| 입력 등록·timeline/resolve | 60.384초 | 준비 전. 원본 hash·probe/DB 등록 등을 포함 |
| db_commit | 3.006초 | 준비 후. commit뿐 아니라 청크 수·bytes/legacy content 조회와 추가 commit도 포함 |
| 정상 신규 ref rollback control | 63.843초 | 준비 후 별도 검증용 재저장/rollback, 준비에 포함하지 않음 |
| 새 물리 연결 조회 | 236.098초 | 준비 후 metadata·detached stream·hash/길이 검사 포함 |
| 추가 detached strict decode | 47.545초 | 준비 후 별도 decoder, 준비 안 52.742초와 구분 |
| Search source copy / reencode | 0.620 / 76.628초 | Search context 안 부분집합 |
| Search 준비 context | 82.182초 | request 1.234초·검사용 출력 inspection 포함. 준비 뒤이며 자체 하위 구간 합산 금지 |
| runner 표본 window | 1716.606초·7,568표본 | 전체 도구/검증 실행의 관측 window. API/Case 사용자 wall time 아님 |
| runner process CPU 최종 누적 표본 | 74.95초 | 위 window의 Python process user+system; 자식과 별도, 준비 구간 전용 아님 |
| ffmpeg / ffprobe CPU 표본 하한 | 978.67 / 477.53초 | PID별 관측 최대 누적값 합. 짧은 process·종료 말미 누락, Search/추가 검증도 포함 |
| DB CPU host 표본 window 차이 | 92.233313초 | 별도 collector 포함·host window 약1719.172초. runner clock과 직접 정렬하지 않음 |

CPU 누적값은 병렬 thread 실행량이며 wall time에 더하거나 1.5로 나눠 제한 없는 예상 시간을 만들지 않는다.
준비 안 도구 시간과 전체 window의 자식 CPU 시간을 직접 나눠 포화율을 산출하지 않는다.
E1의 Recording 366,121,221B·1397청크·준비1219.275·publish61.132·commit3.006은 기존 결과와 일치한다.
Search 270p/CRF28 준비 28,732,230B·SDK 송신 직전 PASS·실제 provider/외부 HTTP 0회도 원문과 일치하며 새 실행은 아니다.

## 4. PM 네 질문에 대한 답변

| 질문 | 확인된 사실 | 추론·현재 판단 | 추가 측정 필요 |
| --- | --- | --- | --- |
| 1. 285초↔1219초의 주원인 확정 가능? | E1은 encode484.410·probe537.751초가 크다. publish 제외1158.143초. 입력·코드·도구·OS·경계가 다름 | **확정 불가.** 현재 큰 시간 소비 구간은 encode/probe. CPU·입력 복잡도·VFR/clock 경로·코드/계측 차이가 원인 후보 | 같은 입력·revision·binary/profile·DB에서 변수 하나씩 대조. 과거 원본/하네스 없이는 과거 증가분 완전 분해 불가 |
| 2. CPU 제한 영향량과 throttling 기록? | runner 1.5core·0,1 실제 한도. runner sampler에는 cpu.stat 없음. DB collector에는 throttled_usec 있음 | **runner 영향량 UNKNOWN.** DB throttling 존재는 runner 병목의 증거가 아님. throttled time은 절약 가능한 wall 초가 아님 | runner와 DB 각각 cpu.max/stat·nr_periods/nr_throttled·usage를 같은 phase 전후 기록하고 CPU quota만 A/B |
| 3. 청크 저장 영향은? | publish61.132초=준비의5.014%. hash/metadata observer·제품 검사·SQL/driver/DB가 포함. 준비 밖 fresh read236.098초 | **순수 추가 비용 UNKNOWN.** 이 관측 publish 구간만으로 전체 준비 지연을 설명할 수 없음. 청크 변경 전체의 인과효과를5%로 제한한 것은 아님 | 같은 유효 payload·metadata·DB·transaction·driver guard 조건으로 이전/현 저장 구현 대조. 대용량 이전 구현 실패를 성공 latency와 비교 금지 |
| 4. 배포 Runtime에서는 어떤 순서로? | 현재 운영 revision·자원·reader/schema 상태는 이번 세션 미조회 | **운영 실측 NOT_RUN.** 먼저 상태/호환성·예산, 다음 작은 대표 구간의 Recording 분해, 마지막 승인된 전체 범위 | 아래 계획의 운영자 입력·전용 target·중단/정리·권한이 충족된 뒤 실행 |

### DB throttling이 남아 있는 정확한 범위

E1 `1200-a-host`의 첫/끝 DB 표본 1,275개 구간에서 `throttled_usec` 증가가
**10,337,299µs(10.337299초)**다. DB CPU 증가는92,233,313µs이며 host elapsed window는1719.172초다.
E2의 DB host 표본 760개에서는 각각4,461,412µs·52,210,723µs, window1029.110초다.
별도 E1 before/after health의 DB throttled 누적은39,422,228→48,582,059µs로 차이9.159831초이며,
그 DB monotonic window는1707.078초다. 서로 다른 관측 window이므로 수치 차이를 모순으로 해석하지 않는다.
DB cgroup은 두 실행 동안 재사용됐으므로 누적 최종값을 한 실행 증가량으로 쓰지 않는다.
runner의 nr_periods/nr_throttled/throttled_usec는 E1/E2 report·journal·sampler 사본에 없고,
host collector가 읽은 cpu.stat은 **DB 것**이다. 현재 cgroup을 조회해 이미 종료된 runner의 값을 복구할 수는 없다.

### publish 경계와 청크 해석

실행 사본의 `observed_publish`는 타이머 안에서 `model_dump`, 전체 content의 `hashlib.sha256`, 길이,
held reference를 기록하고 `repo._get`을 감싼 뒤 원래 `add_prepared_media`를 호출한다.
`_get` observer는 locking metadata 비교·추가 model validation·journal도 수행한다.
제품 함수 자체의 `prepared_content` 검증/hash, metadata/envelope·savepoint/locking read,
청크별 INSERT·mogrify command guard·manifest/case link 처리도 같은 타이머 안이다.
driver observer의 packet/command 계측 비용 역시 분리되지 않는다. commit은 밖이다.
따라서61.132초를 “DB가 순수하게 저장한 시간” 또는 “#544 때문에 추가된 시간”으로 쓰지 않는다.
청크 도입은 bytes 검증·읽기·전송 구조까지 바꾸므로 이 wrapper 하나가 전체 변경의 비용을 포괄하지 않는다.
반대로 fresh read·rollback·추가 detached decode를1219초에 다시 더해 청크 overhead라고 하는 것도 잘못이다.

driver observer의 `command_bytes` 기록은 준비 전체1511회, rollback control1413회,
fresh read1417회다. SQL 종류별 실행 시간이 없고 phase 이름도 publish 하위로 바뀌지 않으므로
1511회를 publish 전용 SQL 수로 쓰지 않는다. fresh read의 제품 경로는 청크1397개를 순차 bounded SELECT로
detached stream에 복원해 길이/hash/MP4를 검증하고, 하네스가 같은 stream의 길이/hash를 다시 확인한다.
이 검사는 저장 무결성과 transaction 밖 사용 가능성을 확인한다. 중복 hash의 정확한 추가 시간은 미계측이며,
fresh read236.098초를 모두 DB 서버 지연 또는 청크 도입 증가분으로 해석할 수 없다.

## 5. 후속 최소 측정안 — 계획이며 실행 아님

이 계획은 [P2-0c](elice-runtime-capacity-smoke-plan.md)의 기존 안전/승인 경계를 구체화한 것이다.
운영 변경·실영상 재인코딩·새 DB 실험·AWS/SSM 접근 권한은 이번 세션에 포함되지 않는다.

### 단계와 판별 목적

| 순서 | 대상·최소 범위 후보 | 고정/변경 변수 | 답할 수 있는 것·중단점 |
| --- | --- | --- | --- |
| 0 | 무미디어 controls·기존 로그 | interval union·부모/자식 제외·remux 라벨·phase별 CPU collector의 synthetic 입력 | 계측 정확성부터 확인. 누락/민감 출력/정리 실패면 실제 측정 진입 금지 |
| 1 | 로컬 input-02 단일 0~10초, 다음 input-01~02의 0~120초 후보 | 기존 E1 revision/source/image/binary/profile, 원본 전체 hash·index·span·정확 출력 coverage 고정 | 첫 구간은 작은 저장/경계 확인, 후자는 VFR+seam 경로 포함. 요청이 짧아도 source 전체 probe 비용이 있으므로 실제 입력 파일 범위도 고정 |
| 2 | 단계1의 같은 대표 요청 | runner quota1.5를 대조 후보2.0core로만 변경, affinity0,1·DB0.5·메모리/DB/temp/동시성/observer 유지 | **추정 후보**2.0core의 안전 여유가 있을 때만 A/B, 최소 A→B→A로 cache/호스트 흔들림 확인. 완전 무제한·affinity 확대 동시 변경 금지. 차이/분산을 기록하고 과거 22개 효과로 일반화 금지 |
| 3 | 같은 작은 유효 prepared payload의 저장만 | encode 제외, 이전/현 repository를 동일 packet64MiB·driver/metadata·transaction/동시성·관찰 경계로 대조 | 이전 구현이 성공하는 payload를 먼저 고름. 준비 경로 측정과 분리. 현 전체 guard 비용도 기록하고 제품 guard는 끄지 않음. 실패한 큰 legacy 저장을 반복해 ceiling 찾지 않음 |
| 4 | 실제 배포 머신에 운영자가 준비한 별도 격리 target, 단계1의 대표 구간 | 운영 상태를 확인한 뒤 **승인한 한 후보 revision**을 고정. 로컬 동 revision 대조를 별도로 맞춤 | 로컬 quota 비교와 별개 실험. 운영 API/Worker/DB와 경합·접속·volume 공유 없이 Recording 단독 phase 측정. 현 운영값을 로컬과 같다고 가정 금지 |
| 5 | 앞 단계가 안전하고 계측이 충분한 뒤 동일 계열 길이를 확대 | 긴 구간의 실제 유효 timeline·입력/예산을 매번 명시 | 처음부터1200초 반복하지 않음.20분 이상 실입력의 배포 Recording 관측 후에도 provider/Case/Web/Package/다운로드 E2E는 별도 승인·검증 |

대표0~120초는 E3 placement에서 input-01 전체와 input-02 일부를 포함하므로, input-01의 가변 duration과
seam/정확 clock 경로를 볼 수 있는 **후속 후보**다. 모든 영상 복잡도를 대표한다고 확정하지 않는다.
기존240초 출력79,323,248B보다 작은 결과가 보장되는 것도 아니다. CRF bytes는 직접 관측해야 한다.
청크 대조용 payload도 임의 바이트를 MP4라고 가정하지 않고 동일한 유효 미디어·모델을 사용한다.
구버전 metadata 표현을 그대로 읽을 수 없는 조합이면 호환성부터 해결하고 순수 청크 효과라 주장하지 않는다.

### 실행 전에 채워야 할 기록과 유한 예산

| 기록/조건 | 로컬 대표 대조 후보 | 배포 격리 측정의 필수 운영자 입력 |
| --- | --- | --- |
| 입력·권한 | E3의 alias/hash/size/mtime·VIDEO index0·명시 placement·선택 frame/PTS/duration·파일 범위 고정. 과거22개 미확보 명시 | 동일 입력의 접근/전송 권한·보호 목적지·원본 불변 감사. 전송은 별도 승인 |
| 코드·image·도구 | 위 E1 revision/source/image/도구 hash, runner/budget/observer 사본·설정 fingerprint 고정 | 실제 실행중 release/revision/image digest·실제 import source·ffmpeg/ffprobe binary hash. 파일상 설정과 process reload를 구분 |
| profile·호출 경계 | Analysis480/veryfast/CRF23. source probe/encode/frame/packet/remux/strict decode·hash/metadata·SQL execute/commit·reader를 개별 계측 | 운영 Analysis 실제 profile/limits·packet/driver 및 target 설정. 운영 설정 복사·변경 없이 격리 config manifest로 선언 |
| CPU·RAM | legacy 예산 후보: runner1280MiB hard/1100soft·swap추가0, DB512hard/440soft. 기본1.5/0.5core·affinity0,1. B후보2.0은 별도 자원 확인 후 | CPU 종류·논리/물리 수·quota/cpuset/상위 cgroup·경합·credit 사용 가능 여부, 실제 가용RAM/swap·동시 workload. 로컬 cap을 그대로 적용하지 않음 |
| temp·disk·DB | legacy temp512MiB·DBdata1GiB, C 시작6GiB/reserve4GiB/누적증가2GiB. host 시작3004MiB=1280+512+700+512. packet64MiB 유지 | 실제 filesystem free/temp mount·IO/DB 위치·가용 여유·백업/로그 증가, 운영 분리 DB/schema/volume·사용자, packet/DB버전·빈 target 확인. 숫자는 운영자 관측 후 확정 |
| 출력 cap·감독 | 대표 요청도 기존 legacy의96MiB/240000ms·runner900초/host930초·정리60초 후보 안에서 먼저 검토. 기존 budget preflight의4N+240MiB RAM·2N+Search후보 temp·3N DB·disk 식을 그대로 보수적으로 적용 | 유한 전체/도구/정리 시간과 cap을 target별 명시하기 전 실행 금지. 제한을 무조건 풀지 않음. 도구120초 유지, 실제 전체 입력 probe가 초과하면 typed 실패로 중단 |
| 관측 | phase 경계의 monotonic wall·wait4/rusage 자식 user/system, runner/DB cpu.max/stat·nr_periods/nr_throttled/throttled_usec 전후, RSS/cgroup memory.current/peak/events·temp/open-unlinked·disk/DB size·I/O·sampler 비용 | 같은 필드·시계 provenance·표본 간격/누락·collector overhead. host/runner monotonic epoch 직접 정렬 금지. phase ID로 연결하고 원문 보호 |

위 숫자는 기존 [budget 모듈](../../../scripts/recording_probe_budget.py)과
[96MiB 실험 예산](2026-11-03-capacity-override.md)의 **후속 후보 재사용**이며 이번 실행 승인·성능 보장이 아니다.
로컬 후보에서도 각 단계 전 현재 RAM/disk/DB 여유와 누적 사용을 다시 확인한다. Search/provider는 이 Recording 대조에서 실행하지 않는다.
DB는 각 arm의 동일 초기 데이터 상태를 전용 새 target으로 맞추고 cache flush·공유 서비스 restart 없이 warm/cold 상태·실행 순서를 기록한다.
payload·guard·버전 차이를 통제하지 못하면 그 차이를 명시하고 원인별 인과효과 대신 관측값으로 남긴다.

즉시 중단 조건은 기존 reserve/soft cap 침범·예산/계측 확인 불가·도구/전체 감독 시간 초과,
OOM/restart·DB disconnect/Aborted_clients 증가·누수/정리 실패·원본 변경·민감 로그·예상 밖 외부 호출·운영 작업 유입이다.
실패 원문을 보존하고 다음 arm으로 자동 재시도하지 않는다. 종료 시 소유 PID/컨테이너만 유한 감독으로 정지하고,
정확한 owner/name과 volume 미사용을 확인한 소유 자원만 정리한다. 기존 보호 volume3개·원본15개·공유 image/cache는 보존한다.
Docker/WSL 재시작·prune·다른 앱 강제 종료를 정리 수단으로 쓰지 않는다.

### 배포·DB·rollback 호환성의 별도 선행 점검

현재 운영 revision이 최신 청크 reader와 prepared metadata decoder를 포함하는지는 **미확인**이다.
운영자는 실제 process revision·`recording_0002` 적용 여부, legacy BLOB/chunk manifest/metadata envelope를 읽는
reader·writer 조합, backup/restore target·rollback code의 decoder 지원을 별도로 확인해야 한다.
schema head가 같아도 metadata envelope를 모르는 코드로 rollback할 수 있다는 뜻이 아니다.
이 점검을 운영 DB 조회·migration·배포·rollback 실행 승인으로 해석하지 않는다.

## 6. 확인된 병목·후보·판단 불가

| 분류 | 결론 |
| --- | --- |
| 확인된 시간 소비 구간 | 현재 E1 encode+probe1022.161초·83.83%. 최종 show_frames67.256초·strict decode52.742초 포함. concat mux 자체0.935초와 chain1130.314초를 구분 |
| 확인된 코드 경로 차이 | 과거 f313cf3a의 chain은 같은 clock part 직접 concat. E1은 가변 duration 때문에 exact-clock packet/remux 검증 경로 수행. remux 자체2.589초, remux frame probe68.180초 등 관측됨 |
| 원인 후보·추론 | runner quota/affinity·호스트 경합, 다른 입력의 내용/가변 duration·bytes, codec/binary/OS·검증/저장/계측 차이가 공동 기여할 가능성. 순위·기여도 확정 불가 |
| 현재 증거로 판단 불가 | 과거 증가분의 원인별 분해·runner throttling 양·CPU 무제한 배속·청크 순수 비용·전체 계측 overhead·배포20분 준비시간·사용자 허용 대기시간·품질/최종 E2E |

## 7. PM 전달 초안 — 게시하지 않음

> 기존 로그를 다시 집계했습니다. 이번1200초 준비1219.275초 안에서는 encode484.410초,
> source/output/packet probe537.751초가 합계83.83%를 차지합니다. concat mux 자체는0.935초이고,
> chain 전체1130.314초와는 다른 경계입니다. decode 라벨14회 중13회는 stream-copy remux로 확인했습니다.
>
> 과거285.2초와는 입력·VFR/clock 처리·코드·OS/도구·CPU·계측 및 publish 포함 범위가 달라,
> 차이의 주원인을 아직 확정할 수 없습니다. runner1.5core 제한은 실제 확인됐지만 runner throttling 기록과
> quota만 바꾼 대조가 없습니다. DB에는 throttling 기록이 있으나 runner 영향량이나 절약 가능한 wall 시간은 아닙니다.
>
> publish61.132초는 준비의5.014%이며 하네스 hash/metadata 검사와 제품·driver·DB 처리가 섞인 값입니다.
> 이를 청크 변경의 순수 추가 비용으로 보지 않습니다. 기존 실패 저장과 현재 성공 저장도 동일 조건 대조가 아닙니다.
>
> 다음은 작은 단일 구간과 VFR/seam 대표 구간부터 동일 입력·코드·도구·예산을 고정해 CPU quota 대조와
> 저장 단독 대조를 분리하는 것입니다. 배포 환경은 운영자가 실제 revision/reader/schema/rollback 호환성·자원·격리 조건을
> 먼저 확인한 뒤 별도 Recording 측정으로 진행할 계획입니다. 이번에는 이를 실행하지 않았습니다.
> 로컬1219초를 운영 처리시간·허용 대기시간으로 채택하지 않고 Case timeout도 변경하지 않습니다.
> 최소20분 이상 실제 입력의 배포 E2E는 계속 미완료입니다.

## 8. 이번 세션 검증·보존·NOT_RUN

공개 변경은 이 분석 문서와 [실험 색인](README.md)의 링크뿐이다. 제품 source·운영 설정·기존 계획/실험 결과는 변경하지 않는다.
조사 전용 분석기·집계 JSON·파일 대응/hash·검증 기록은 ignored 보호 scratch에만 둔다.
분석기는 기존 JSON/journal을 읽고 수치/고정 필드만 출력하며 ffmpeg/DB/Docker/network를 실행하지 않는다.
interval 중첩/분리/중복/빈 집합/부모 포함/역전 거부의 합성 controls6개와 E1/E2 event/journal·호출 패턴·비중/산술 검사를 수행했다.

| 이번 직접 검증 | 결과·범위 |
| --- | --- |
| 합성 controls·실제 로그 | controls6개 PASS. E1/E2 events와 journal124/84개 일치, leaf union+잔여가 각 준비 전체와 일치 |
| 숫자·링크·공개 검사 | 표의 도구/publish/잔여·probe 합계를 원문으로 대조. 새 문서9개와 실험 색인 포함 로컬 링크22개 누락0. 보호 manifest 원본명·개인 source 경로·생성 ref 문자열 일치0. 일본어 문자·주요 credential 패턴 일치0 |
| 공백·diff | `git diff --check` PASS. 이 명령이 포함하지 않는 미추적 새 본문은 별도 줄 끝 공백/마지막 newline 검사 PASS |
| 보존 | 조사 대상 기존 보호 파일21개 SHA-256 불변, 제품 전체 source path+content hash 불변, 원본15개 size/mtime 불변·manifest와 일치 |
| 정리·Git | 이번 미디어/DB/Docker 자원 생성·호출0, 별도 정리 대상 없음. 보호 volume3개·공유 image/cache에 접근/변경하지 않음. 지정 브랜치/HEAD 유지, 공개 변경2파일·index 비어 있음 |

구현 대화 이력을 전달하지 않은 독립 fresh 읽기 전용 reviewer가 문서·실행 사본·실제 로그와 제품 호출 코드를 검토했다.
reviewer는 controls6개·E1/E2 집계·driver 횟수를 직접 재현하고, 별도 sweep-line으로 E1의95개 도구+publish
96개 구간 union1139.559824649초·최대 중첩1을 재확인했다. 보호21개 hash·원본stat15개·알려진 민감문자열 누출0도 직접 확인했다.
첫 검토에서 actionable 지적은 없었다. trace와 외부 wrapper 경계를 명료화한 수정 및 driver/fresh read 설명을 검토받았고,
이 최종 검증 기록을 포함한 수정본을 **같은 reviewer가 재확인**했고 수치·링크22개·비노출/공백·보존·Git 상태가 유지됐다.
재확인에서 분석용 검증기의 설명이 보존 검사까지 수행한다고 넓게 적힌 P3 지적1건을 받아,
설명을 실제 숫자/링크/보호 문자열/공백 검사 범위로 고쳤다. 보존 검증은 별도 검사이며 위 결과와 구분한다.
수정 후 같은 reviewer가 P3 해소·미해결 지적 없음을 최종 재확인했다.
reviewer의 GitHub 최신 상태·과거 실행은 작성자 증거/한계 검토이며 독립 재조회·재실행이 아니다.
원본은 내용 읽기/재해싱 없이 manifest 대비 size/mtime15개를 확인했으며, 과거 hash 감사와 이번 검사를 구분한다.
실영상 encode·대규모 DB 실험·전체 pytest/MySQL·provider/유료 회귀·AWS/SSM/배포/workflow·운영 조회/서비스 정지·timeout/정책 변경은 NOT_RUN이다.
commit/push/PR/Issue 댓글·외부 게시는 하지 않는다. 분석을 미커밋·미스테이징으로 남긴다.
