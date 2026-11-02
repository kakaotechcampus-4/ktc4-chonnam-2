# #537 Recording frame coverage 최소 재현

Owner: 정철원(Runtime·Recording). 기준은 `codex/issue452-timing-repro`,
`b34714fc08bb46751b6dbbc5c53ee64ec3f17a7c`다. 시작 working tree와 index는 비어 있었고,
원격 develop도 같은 HEAD였다. #527 변경은 가져오거나 수정하지 않았다.
[기존 실패 기록](../../../runtime/experiments/2026-11-02-local-capacity-probe.md)은 그대로 보존한다.

## 원인과 축소 근거

**확정 — 이번 재현 범위:** 선택 VIDEO의 연속된 가변 frame duration을 B-frame 재정렬과 함께
MP4로 인코딩하면 일부 decoded frame의 관측 duration이 바뀐다. strict coverage 검사가 이를 거부했다.
원본 손상, 요청 seam, time-base 반올림이나 마지막 frame duration 누락을 이번 실패의 원인으로
확정할 근거는 없었다. 별도 null 출력 DTS 진단의 옵션을 이번 제품 경로에 적용하지 않았다.

기존 비공개 manifest·ledger의 입력 순서 `input-01→02→03`, VIDEO index `0`, 명시 범위
`[0,240)`와 config hash `10255f8e64b12f1c87ec02e208f6ede83d114fea307b29238fd8e10132ada5a5`를 확인했다.
첫 구간은 input-01의 `[0,117.933333)`이다. #537의 실패 출력은 unwind 후 삭제되어
보존된 영상이 없었으므로, 기존 로그/assertion을 읽은 다음 실제 materializer로 이 첫 구간부터 재생성했다.
DB·provider는 사용하지 않았다. 도구 명령과 검증 결과만 관찰하는 adapter를 사용했다.

| 실행 | 요청 범위(초), 선택 frame | 수정 전 결과 |
| --- | --- | --- |
| 첫 span만 분리 | input-01 `[0,117.933333)`, 3218개 | 동일 `_FrameCoverageError`, 출력 **25,865,650 bytes**까지 일치 |
| 끝 경계만 축소 | `[0,17)`, 190개 | 같은 duration 불일치 |
| 시작 경계만 축소 | `[15.9,17)`, 31개 | 같은 종류의 불일치 |
| 끝 경계만 축소 | `[15.9,16.1)`, 4개 | frame index 1 duration 불일치 |
| 끝을 한 frame 더 축소 | `[15.9,16.05)`, 3개 | PASS, duration 모두 원본과 일치 |
| 4개 frame, `-bf 0`만 주입 | `[15.9,16.1)` | PASS, PTS·duration 정확히 일치 |

따라서 **확인한 최소 실패는 4개 frame**이다. 모든 가능한 원본 부분구간의 전역 최소를 탐색한 것은 아니다.
3개 frame 대조의 실제 coverage 끝은 `241/15초`이며 요청 끝 `16.05초`로 clamp하지 않았다.

원본 전체 PTS는 엄격 증가하고 coverage gap은 0개다. time base는 원본·출력 모두 `1/30000`이다.
원본 duration은 `3000 tick ×160 +1000 tick ×3058`, 출력은 `3000 tick ×162 +1000 tick ×3056`이다.
3218개 상대 PTS가 전부 일치하며, 출력 index 161·163의 duration만 `1000→3000 tick`으로 바뀐다.
출력의 전체 duration이 같다는 사실만으로 개별 coverage 일치를 보장하지 못한다.

최소 구간을 첫 선택 frame 기준으로 정규화하면 다음과 같다. 값은 모두 정수 tick이며 직접 관측했다.

| 표시 순서 | PTS | 원본 duration | 기존 출력 duration | `-bf 0` 출력 duration |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0 | 3000 | 3000 | 3000 |
| 1 | 3000 | 1000 | 3000 | 1000 |
| 2 | 4000 | 1000 | 1000 | 1000 |
| 3 | 5000 | 1000 | 1000 | 1000 |

기존 최소 출력 packet의 decode 순서 `(PTS,DTS,duration)`은
`(0,-4000,3000), (5000,-1000,1000), (3000,0,3000), (4000,3000,1000)`이다.
표시 시각 `3000`인 packet은 다음 decode timestamp까지의 `3000 tick`을 duration으로 가지며,
표시 순서의 다음 PTS `4000`까지는 `1000 tick`이다.
FFmpeg n8.1의 [MP4 stts 작성](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/movenc.c#L2980)과
[인접 DTS 간격 계산](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/movenc.c#L1149)이 관측과 일치한다.
이 설명은 해당 build와 재현의 encoder/mux 결과에 한정하며 모든 VFR·B-frame 파일이 실패한다는 주장이 아니다.

## 수정과 정확성 경계

- 공용 materializer에서 **선택한 frame duration이 서로 다를 때만** `-bf 0`을 사용한다.
  trim·passthrough·encoder time base·track timescale·frame 수·PTS·duration·faststart 검사와
  기존 tolerance를 유지한다. source 전체가 VFR이어도 선택 구간이 일정 duration이면 기존 encoding을 쓴다.
- VFR/CFR의 같은 clock 연결을 양방향으로 추가 검사하니 서로 다른 decode 지연 때문에
  기존 단순 concat도 실패했다. VFR part를 포함한 chain은 기존 mixed-clock용 exact packet projection을
  재사용한다. 표시 PTS·개별 duration·frame 수를 보존하고 decode interval만 정확히 연결한다.
  원본 facts·Timeline·provenance를 바꾸지 않으며, 최종 frame/packet 검증과 strict decode를 유지한다.
  clock 약분이 format duration의 검사 폭을 늘리지 않도록 remux 전 clock과 최종 clock 중
  더 미세한 것을 비교 기준으로 유지한다.
- 고정 FPS, frame drop/duplicate, 끝 duration 합성, 입력 제외, tolerance 확대, 예외 성공 전환은 없다.
  B-frame 사용 여부는 파생 encoding 선택이다. 같은 CRF에서도 bytes와 압축 결과가 바뀔 수 있고
  byte cap은 계속 적용된다. 모든 VFR/clock 조합의 지원을 새로 보장하지 않는다.

## 실행 환경·자원·비공개 증거

동일 image ID `sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`,
실제 태그 `daesingo-issue452:local`을 재사용했다. FFmpeg·ffprobe 8.1과 현재 checkout의
`docker/runtime.py media-preflight` exit 0을 확인했다. 내장 코드를 HEAD로 간주하지 않고 현재 source를
read-only mount했다. 수정 전 source 경로+내용 hash는 기존 기록과 같은
`3d91fb6120bab2ce4e0ea650cd8ff98d9d4fa8a9b06858bc0af9920a694ce1a0`이다.
기존 runner hash는 `fadaf3bc986ce8341f5f819d9724d75466735a531393f91195d36d1dfbd75d44`다.
새 runner·source hash·실행 인자·관측 JSON·정상/실패 로그는 비공개 ledger로 구분했다.
최종 제품 source hash는 `ed044c3e35a325d4dbe136612b139579870256d05925885dbf169d598655350b`,
최소 진단 runner hash는 `41c1c79e40da030347ab3669eb769ed275aa01589d5b305f1370257e08b33378`다.
기존 #537에 병합된 최종 runner hash `95e35b71f300dd0695b7276fba7239a3daba25efc57e96604e381949d12b4a93`와
당시 baseline-exact 실행 runner hash가 다름도 구분했다. 이번에는 DB를 요구하는 그 runner를 재실행하지 않았다.

시작 RAM은 total `16,281,024 KiB`, free `2,018,900 KiB`, C free `2,598,785,024 bytes`였다.
이번 작은 DB-free 진단은 CPU 1.5/RAM 768 MiB/swap 추가 없음, tmpfs 96 MiB, 도구당 120초,
실영상 실행당 240초, 동시에 1개, network none으로 제한했다. 기존 대용량 probe의 자원 예산을 재사용하지 않았다.
첫 span은 standalone timeout으로 실행했고, 이후 감독은 시작 C 2 GiB/RAM 1000 MiB,
중단 C 1.8 GiB·disk 증가 64 MiB·RAM 700 MiB, 2초 표본을 적용했다.
focused test는 전체 600초 한도다. 표본·감지 지연이 있으며 hard disk quota나 실제 peak 측정은 아니다.
실행 종료 뒤 host RAM이 중단 기준 아래로 내려갔을 때 신규 실행의 시작 gate가 닫힌 것을 확인하고
추가 부하를 만들지 않았다. RAM 회복 후 같은 기준으로 재개했으며 Docker/WSL을 재시작하지 않았다.

이미지에 pytest가 없어 로컬의 기존 pytest 8.4.2와 의존 순수 Python 패키지만 read-only mount했다.
패키지 설치·네트워크 접근은 없고 이미지의 Linux runtime 의존성을 사용했다.
pytest 미설치/호환 모듈·temp 경로 준비 실패는 harness 실패로 보존하고 제품 RED로 세지 않았다.
기존 focused fixture 생성 중 7개 setup 오류는 별도 재현에서 PID 제한 도달
(`pids.events: max 2`, encoder `EAGAIN`)과 함께 발생했다. CPU affinity만 2개로 제한한 대조는
동일 fixture 10회 exit 0/`max 0`이었다. CPU quota·RAM·PID 제한과 제품 옵션은 유지했다.

최소 실패 MP4 SHA-256은 `38a10bf3c1f332660f886ca7d99495e64a3fb48b950ebdf07f70d2aaaf9f85b9`다.
이 영상과 최소 frame/packet JSON은 비공개 증거에만 남긴다. 공개 문서에 원본 파일명·개인 경로·영상은 없다.

## 검증과 잔여

직접 확인: 합성 최소 회귀는 수정 전 동일 coverage assertion에서 **1 FAIL → 1 PASS**다.
같은 clock VFR/CFR 연결은 **8 FAIL → 8 PASS**를 확인했다. 이후 reviewer의 format duration
허용폭 지적을 `0.4초` coverage에 format duration만 `0.45초`로 바꾸는 부정 대조로 재현해
**8 FAIL(거부하지 않음)**을 확인하고 검사 기준을 보완했다.

실제 원본은 진단 옵션 주입 없이 최소 4-frame 구간과 원래 첫 span 전체가 PASS다.
첫 span 전체는 `131.786616초`, `33,656,639 bytes`, 3218개 frame의 PTS·duration이
원본과 정확히 일치하고 temp 0/원본 hash 불변을 확인했다. 이 준비 시간은 로컬 단일 표본이며
기존 #537의 서로 다른 phase 계측 전체 시간과 성능 비교하지 않는다.

기존 100초 성공 chain은 #537의 대조 증거로 재사용했고 다시 실행하지 않았다.
최종 focused/reviewer 직접 실행 및 원본·자원 종료 결과는 아래에 기록한다.

| 검증 주체·범위 | 결과 |
| --- | --- |
| 작성자: 새 timing/negative controls | 최종 focused 안에 31개 포함, PASS |
| 작성자: focused 9개 파일 | **215 PASS**, 원본 opt-in 4개 deselected, 32.01초. skip/xfail 없음 |
| fresh reviewer: 코드·관련 계약·테스트 읽기 | duration 허용폭 P2 1건 지적·보완 diff 재검토 후 잔여 없음 |
| reviewer: 새 VFR + 기존 frame-duration 두 파일 직접 실행 | **80 PASS**, 8.58초. host/container exit 0, OOM 없음, 소유 container 정리 확인 |
| reviewer: 실제 원본·DB·provider 재현 | **NOT_RUN** |

작성자 focused 파일은 `test_vfr_materialization`, `test_materialization_frame_duration`,
`test_local_analysis_source`, `test_local_incident_clip`, `test_multi_span_analysis_source`,
`test_multi_span_incident_clip`, `test_mixed_timebase`, `test_source_inspection_reuse`,
`test_analysis_source_limits`다(`tests/recording/`, `-k 'not opt_in'`).
기존 208 PASS/7 fixture ERROR 실행과 이후 affinity 대조·215 PASS를 각각 보존했다.
reviewer는 구현 대화 이력을 받지 않은 새 context에서 시작했고 파일을 수정하지 않았다.
처음 sandbox Docker 접근 거부는 pytest 진입 전 실패이며 승인 범위의 재실행에서 실제 80개를 검증했다.

Runtime quality(Ruff + Linux/Windows mypy 각 87개 source), 변경 Python 파일 Ruff,
boundary, Contract fixture(구조 62/JSON 26/의미 104), `git diff --check`는 모두 PASS다.
boundary 최초 실행은 Windows CP949의 출력 인코딩 오류로 exit 1이었고,
제품/검사 코드를 바꾸지 않고 `python -X utf8`로 재실행해 exit 0을 확인했다.
MySQL·전체 pytest·전체 mandatory gate는 실행하지 않았다. 향후 push 후 원격 CI 조건으로 남긴다.

종료 시 원본 **15/15 SHA-256·size·mtime 불변**을 manifest와 대조했다.
이번 작업의 큰 실패 출력과 불필요한 3-frame 대조 사본 `25,933,894 bytes`만 정리했다.
최소 실패 영상 `72,757 bytes`와 frame/packet·실행별 실패/성공 기록, runner 버전은 비공개로 보존했다.
성공 중간물은 materializer cleanup 후 temp 0이며 대량 사본은 없다.
작업 소유 container는 **0개**, 새 network/volume은 만들지 않았다. 기존 실패 DB volume은
사용·재시작·삭제하지 않았고 존재를 확인했다. 공유 Docker/WSL 재시작·prune·cache 삭제는 없다.
종료 순간 C free `2,470,563,840 bytes`, RAM free `2,221,068 KiB`였다. 이후 가용량을 보장하지 않는다.

공개 변경은 `materialization.py`, `multi_analysis.py`, `test_vfr_materialization.py`, 이 문서의 4개다.
기존 #537 실패 문서는 수정하지 않았다. branch/HEAD는 시작값이고 index는 비어 있다.
미커밋·미스테이징 상태이며 commit·push·PR·외부 댓글·merge·배포는 하지 않았다.

20분 실험의 재개 가능성은 이번 coverage 수정만으로 확정하지 않는다. 현재 4분 정책,
별도 [DB packet·driver working set·감독/OOM 병목](../../../runtime/experiments/2026-11-02-local-capacity-probe.md)은
해결되지 않았다. 전체 240초 chain·20분·MySQL·Search/Case/Web·provider·운영 EC2 재실행은 범위 밖이다.
