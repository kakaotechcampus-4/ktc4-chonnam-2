# Search Coarse 270p·CRF28 격리 크기 실험 — 2026-11-03

담당 정철원(Runtime 구현·Recording). [#452 Search Owner 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6594486653)의 **1번 크기 재측정만** 수행한다. 운영값 확정·recall/오탐·실제 provider·Case 전체 흐름·배포 성공은 판단하지 않는다.

최종 직접 판정: **720초·1200초 모두 PASS_STOP_BEFORE_SEND**. Search 출력은 각각 **16,810,996B /28,732,230B**로 기존 media40MiB·request56MiB guard를 통과했다. 실제 provider 호출은0회다. 전체 제품 E2E·품질·운영 지원 범위 판정과 구분한다.

## 시작·근거·격리

지정 branch `codex/issue452-coarse-270p-probe`, HEAD `bf283652e0826df7c75ede44750311e8b1c3036c`. 시작 working tree/index는 비어 있었다. 원격 `refs/heads/develop`를 직접 조회해 같은 SHA를 확인했고 `origin/develop` ancestor 검사도 exit0이었다. 사용자 AGENTS 지침, CLAUDE 라우터, docs 규칙과 [P2-0c·G2/G4/G6·Decision Gate](elice-runtime-capacity-smoke-plan.md), [capacity override](2026-11-03-capacity-override.md), [metadata publish 수정](2026-11-03-metadata-publish-fix.md)을 읽었다. 별도 tracked AGENTS.md는 없다.

기존 실패 원문·보호 scratch·보호 volume3개는 보존한다. 기존 관련 scratch의 미디어 후보69개는 최대200,000B의 작은 controls이며720초215,411,995B 산출물은 없다. 현재 Docker 컨테이너0, 보존 volume3개만 있다. 따라서 같은 manifest/placement/VIDEO index를 사용해 Recording 준비 경로를 새로 실행한다. 기존360p Search 영상은 재생성하지 않는다.

15:06 KST 시작 감사에서 원본15개 SHA-256·size·mtime 모두 보호 manifest와 일치했다. Windows 가용 RAM5,610,659,840B, C 물리 여유17,754,906,624B는 직접 순간값이다. 기존 감사 helper의2100MiB 표시는 역사적 helper 필드이며 실제 실행 시작 gate는 아래3004MiB다. WSL RAM/가상 disk를 합산하지 않는다. 원본은 read-only mount하며 원본명·개인 경로·GPS·번호판·RAW는 새 ignored scratch에만 둔다.

## 실제 설정과 실험 배선

제품 `MediaPreparer._prepare_coarse`는 `fps=2.0,max_height=360`을 전달한다. 제품 `_run_ffmpeg_encode`의 실제 argv builder에는 **CRF와 preset이 명시되지 않는다**. Owner 표의 “현재CRF23”과 달리 이 경로에서23을 명시 전달했다고 말할 수 없다. FFmpeg/libx264 기본값 일반론과 과거 실제 argv를 구분한다.

실험 하네스의 명시적 flag에서만 Coarse hook을 적용한다. 제품 builder에270을 전달한 뒤 해당 encode argv에 `-crf 28`을 삽입한다. 기존 `fps=2,scale=-2:'min(270,ih)',setpts=(PTS-STARTPTS)*2,fps=1`, `libx264,-an,+faststart`, input/seek/deadline/guard/cleanup 의미를 보존한다. Fine은 기존4fps/360·seek를 유지한다. 다른 도구 호출에는 hook을 적용하지 않고 정상/encode실패/context중단 모두 원복한다. 운영 Search config·Analysis480/veryfast/CRF23·Case 계약/마감·packet64MiB·청크256KiB는 변경하지 않는다.

새 argv/격리/원복/invalid설정 controls는 RED9 FAIL→기존 포함GREEN53 PASS였다. 문자열 source 검사 대신 실제 제품 argv 생성 함수를 실행했다. 실제8.1 합성 출력·guard controls는 아래 실행 기록에 추가한다.

## 720초 실행 전 예산

| 항목 | 유한 값·근거 |
| --- | --- |
| Recording | 208MiB=218,103,808B /720000ms. 과거 직접215,411,995B 기준, 새 환경의 충분함 보장은 아님 |
| runner / DB | runner1280MiB hard/1100MiB soft, DB512MiB hard/440MiB soft, swap추가0, CPU1.5/0.5, affinity0,1 |
| Windows 시작 / reserve | 3004MiB=1280+512+700 host reserve+512 collector/daemon 예비. 실행 중700MiB reserve 유지 |
| temp / Search | temp512MiB soft. source512/media40/request56MiB·준비150초 유지. 거부 출력 후보64MiB는 cap 변경이 아닌 자원 추정 |
| 중첩 추정 | concat part/remux/final2N+64MiB=480MiB; 메모리4N+240MiB=1072MiB. 과거720 cgroup1,041,342,464B/temp483,401,674B와 대조 |
| DB/C | DB data1GiB soft. 새 DB 기준data+3N; C 시작6GiB/reserve4GiB/증가2GiB. DB3N+temp480MiB+log64MiB=1,224,736,768B 추정 |
| 시간·관측 | Recording 도구당120초, runner1800초/host1830초, 별도정리60초 후보. runner200ms 목표·host1초+Docker 호출시간. 호출 자체도 유한 timeout |

cache/JSON/frame객체/driver allocation과 짧은 peak는 계산만으로 보장하지 않는다. sampler·host·DB stop이 관측 실패도 FAIL로 남긴다. 전용 DB·internal network·공개port0·socket/HTTP fence·SDK sentinel을 사용한다.

## 직접 결과·후속

720초는 **PASS_STOP_BEFORE_SEND**다. 기존Recording215,411,995B와 SHA-256이 같고822청크·commit·새 물리 연결·metadata exact·길이/hash·detached strict decode·같은stream Search를 통과했다. 270p·CRF28 media16,810,996B/base6422,414,664B/guard JSON22,418,328B로 기존512/40/56MiB 및150초 준비 경계를 유지한 채 SDK sentinel1회에 도달했다. provider/HTTP/외부socket 시도0이다. Aborted_clients0→0, temp0·자식0·cleanup오류0, Coarse hook원복을 확인했다.

기존360p720초52,577,684B 거부와 비교하면 출력비율0.3197363, **약68.03% 감소(직접bytes로 계산)**다. 기존 실행은CRF를 명시하지 않았고 이번에는28을 명시했다. 이전실패/base64·request·SDK NOT_REACHED를 덮어쓰지 않는다. 영상크기 통과는 recall·오탐·실제provider 성공이 아니다. 실행 간 시간은cache·공유host·collector 등의 차이도 있어 설정 변경의 인과효과로 단정하지 않는다.

실제Coarse는480×270·audio0·1440frame·재생1440초, clock1/16384·PTS0→23576576+16384tick·증가/coverage PASS였다. 원본반환duration720.033333초와전체원본좌표0–720.033333,0.5배속 의미를 유지했다. 요청은0–720초이며frame선택의 기존 끝경계 규칙을 임의로 자르지 않았다. 독립 촬영 seam 연속성은UNKNOWN이다.

### 작은 실제 control·실패 보존

합성640×480/30fps·원본8초(음성 포함)를 고정FFmpeg8.1로 생성했다. 실제 Coarse argv의270·`-crf 28`과 encoder 보고`crf=28.0`을 확인했다. 출력360×270·audio0·1fps·16frame·16초, PTS0→245760+16384tick/clock1/16384, 증가·coverage PASS, 원본 좌표0–8초·playback_speed0.5였다. media76,007B다. Fine은360p/4fps·구간2–4초·0.25배속을 유지했다. media1B/request1B negative guard가 거부했고 후자의 SDK 진입0, 정상 sentinel1·provider0, hook원복·temp0을 확인했다.

최초 실제 control은 새 출력 계측 helper의`capture_stdout=True` 누락으로 FAIL이었다. 인코딩 뒤 ffprobe JSON을 받지 못한 하네스 오류이며 큰 실측은 시작하지 않았다. 원문 로그/컨테이너 상태는 보존했고 같은 원인의 control RED1→수정 후 Linux54 PASS·작은 실제 control PASS로 확인했다. 초기 실패를 후속 성공으로 지우지 않는다.

### 1200초 예산 후보 — 실행 전 준비, 아직 실행 아님

기존720초 직접값215,411,995B·cgroup1,041,342,464B·temp483,401,674B를1200/720배 하면 각각359,019,991.67B·1,735,570,773.33B·805,669,456.67B다. **모두 비례 추정이며1200초 실측이 아니다.** 기존256MiB 실험상한은 이 출력 추정보다 작고 제품DB 한계도 아니다.

| 항목 | 새 유한 후보·근거 |
| --- | --- |
| Recording | 384MiB=402,653,184B /1200000ms, run3000초. 알려진360MB 수준 추정에 여유를 둔 단일 후보; 충분함 미확정 |
| runner | 2176MiB hard /1900MiB soft /swap추가0. 4×384+240=1776MiB 메모리 후보보다 soft124MiB·hard400MiB 여유 |
| tool/runtime/cache | 메모리4N에 part/final bytes·파일cache 후보를 포함, 별도240MiB tool/probe/runtime 예비. Search source2N+64MiB 출력·base64/guard 할당은 다른 phase이며 concat과 합산하지 않음 |
| temp | 896MiB soft. detached+copy+출력 후보2×384+64=832MiB, 여유64MiB. source/원본 전체 복사 없음 |
| DB | hard512/soft440MiB 유지, data2GiB soft. 현재data+3×384MiB=현재data+1,207,959,552B와 비교. packet64MiB·256KiB 청크 유지 |
| Windows RAM | 시작3900MiB=2176+512+700host reserve+512collector/daemon 예비. 기존reserve를 줄이지 않음. WSL여유 합산0 |
| C 물리 disk | 시작8GiB/reserve4GiB/누적증가3GiB. DB3N+temp832+log64=2048MiB 후보, 기존720 증가도 누적3GiB 안에서 별도 차감 |
| 감독 | runner3000초/host3030초·정리60초 후보, 도구당120초/Search150초 유지. 기존720전체약978초의 비례 약1631초는 추정.13개 원본 순차probe/encode·concat/strict검증·DB왕복·Search·collector를 전체감독에 포함 |
| logical range | 보호manifest input-01→13 명시placement0–1228.799999초 중0–1200초 전체. nominal길이/시험합계로 대체하지 않고 실제 resolve·출력PTS·provenance를 검사 |

`recording_probe_budget.py`의 공유 유한 profile은 byte/duration/timeout 조합·메모리/temp/DB/disk/host reserve를 함께 검증한다. 기존 profile에서 byte만384MiB로 바꾸는 설정, 모르는 profile과 자원 부족은 거부한다. 새budget controls는 RED15→GREEN15다. 이 표를 준비한 뒤720실행 종료 후 하네스/Sampler/감독기 연결을 적용·검증했다. 이 표만으로1200실행을 허용하지 않는다.

### 1200초 실행 직전 결정

720초 직접관측window1025.632초·kernelpeak984,805,376B·temp447,634,986B였다. 이번720결과의1200/720비례값은 Recording359,019,991.67B·Search28,018,326.67B·전체1709.387초다. **추정으로만** 사용하고1200실측을 대신하지 않는다. 위384MiB/2176hard·1900soft/temp896MiB/DBdata2GiB/C증가3GiB/3000–3030초 조합을 유지한다.

720 실행 당시 harness 사본을 보존한 뒤 확장 profile을 연결했다. 기존 legacy의 256MiB 최대는 그대로이며 확장은 `coarse-1200-384m`의 byte/duration/timeout 정확한 조합에서만 허용한다. sampler도 동일 profile을 사용한다. 의도적 통합 RED1→전체 focused72 PASS, Linux 동일72 PASS(3.92초), 감독기 fake15 PASS다. reviewer가 지적한 budget 모듈 identity 누락은 host/runner hash 대조·소스 사본으로 보완했다. 실제 container hard limit도 Docker inspect로 대조한다.

직전 gate는 Windows 가용 RAM5,574,811,648B/C 물리 여유17,847,353,344B, DB data622,461,281B, work0에서 PASS였다. DB 현재+3N=1,830,420,833B<2GiB, temp 후보872,415,232B<896MiB, 메모리 후보1,862,270,976B<1900MiB, C 추가 후보2,147,483,648B<누적3GiB다. C 가시 여유가 시작보다 늘어 차감한 증가량은0B이며 그 반환을 보장하지 않는다. stage 직전에 같은 gate를 다시 적용한다. 조건을 충족하므로 새 실험 ID로 input-01→13·전체0–1200초를 직접 측정한다. provider 전송은 계속 차단한다.

stage 직전 재검사도 RAM5,592,952,832B/C17,846,153,216B에서 PASS였다. 실제 Docker `Memory=MemorySwap=2,281,701,376B`, CPU1.5/affinity0,1/pids128/read-only를 확인했다. 별도 읽기 전용 collector의 실제 MySQL8.4.13·session packet67,108,864B·Aborted_clients0·OOM false/자동 restart0도 기록했다. collector의 추가 조회는 runner의 network 횟수와 구분한다.

## 실행 identity·관측 범위

제품 source path+content SHA-256(v1)은 `db59f30530b4aee1d36ea63b9bc9909762a81bb84355837d171f8f13d66ca998`이다. #549 이후 현재 HEAD까지 Recording/Search source diff는0이다. 다른 Runtime/UI 변경을 포함하는 최신 develop을 그대로 사용했다. 실제 import가 `/repo/src/`인지 검사했고 이미지 내장 과거 source로 대체하지 않았다.

| 구분 | 식별 |
| --- | --- |
| 고정 runtime image | `sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f` |
| 실제 ffmpeg/ffprobe | 8.1, 각run binary hash를보호JSON에기록. 기존고정도구와대조 |
| 720 harness snapshot SHA-256 | `7f8f3cd132059576f37a6410749164e52f3341be7556c2b6613850812571e9c3` |
| 1200 harness snapshot SHA-256 | `c1f680d4f38f6f1a19d9f0f0b74754842bafade11f92483aadb906e4fa7ce5d3` |
| 입력 lineage | 기존보호manifest·input-01부터의순서·VIDEO index0·metadata duration을누적한명시placement재사용. 원본은read-only |
| 실험 ID | `p2-coarse270-720-a` / `p2-coarse270-1200-a` |
| 720 experimental JSON SHA-256 | `de3a57bb13fc79e6365b92769cc40fd133ffabfeba2aa1cc95c36c4b574f914e` |
| 1200 experimental JSON SHA-256 | `2fe2ec37f9f48e108904cb28229a93d69d66bca532a67db2c78c517ab93a3c85` |
| 실제 ffmpeg binary SHA-256 | `19e0073f42f3cc0c1880ac9a4a91fc6c42d511bec9497db03872cc527791c91a` |
| 실제 ffprobe binary SHA-256 | `ec4bde78f8b08c56109d68fffb16e9972ae7543ed62253fd90e699dda4a0f975` |

720은 확장 profile 연결 전의 사본이며1200은 연결 후 사본이다. source/runner/supervisor/budget/experimental JSON hash와 사본을 각각 보존한다. 1200 runner가 읽은 budget 모듈 hash를 host가 사전 기록한 hash와 대조한다.

Search production config fingerprint는 `890589142d3d02daed593c49c6a5813c9d6377ec6738dfd36dbfc99623be7821`로 유지한다. 이 fingerprint만으로 실험 override가 식별되는 것은 아니다. 별도 실험 ID·270/28 설정·실제 argv·encoder CRF 관측·harness snapshot으로 구분한다. Recording config SHA-256은720이 기존과 동일한 `03d12d55536619ec1b30a13340bdc5d5d2eb4f478f75476ef4eebaafa7acd7bb`, 1200이 `aa5db5a556a4b0ccd20498fe88e0d741c728565dd22d1d47f87f2aa5aa6340a8`다. 1200 budget 모듈 SHA-256 `d807eb6c75e47a955e40990e49a5c581b18a738c3cafe94aa40d342637a6571a`는 host 사본·runner 관측이 일치했다.

시간 phase는 중첩되므로 합산하지 않는다. runner200ms 목표의 실제 간격과 host1초+Docker 호출 시간을 함께 기록한다. Linux/Windows monotonic epoch를 직접 정렬하지 않는다. 표본 RSS/temp/CPU는 연속 peak나 driver별 allocation 전체가 아니다. PID별 tool CPU 관측 최댓값 합은 종료 말미·짧은 process 누락에 따른 하한이다. kernel `memory.peak`는 해당 cgroup 생애 값이며 공유 cache 전부의 host peak가 아니다. DB CPU는 내부 collector도 포함하고 DB kernel peak는 두 run 누적 생애 값이다. cache flush·다른 앱 종료·공유 Docker/WSL 재시작은 하지 않았다.

이번720 temp 직접값447,634,986B는 `2×215,411,995+16,810,996`과 같아 detached+Search copy+출력 중첩 모델과 일치한다. 이 한 표본의 일치를 일반적 peak 보장으로 확대하지 않는다.

## 직접 측정 표

아래 값은 각 run의 직접 관측이다. 1200초는 앞선 시험 길이의 합이나 비례 추정으로 채우지 않았다.

| 경계·크기·시각 | 기존360p 720초 | 이번270p·CRF28 720초 | 이번1200초 |
| --- | ---: | ---: | --- |
| 요청 범위 / 원본 수 | 0–720초 /8 | 0–720초 /8 | 0–1200초 /13 |
| Recording bytes /청크 | 215,411,995 /822 | 215,411,995 /822 | 366,121,221 /1397 |
| Recording 반환 duration | 720.033333초 | 720.033333초 | 1200.033333초 |
| Recording 최종 frame /clock /끝PTS+duration | 21281 /1/30 /21600+1 | 21281 /1/30 /21600+1 | 35681 /1/30 /36000+1 |
| metadata·길이·hash·provenance /detached strict decode | PASS | PASS | PASS |
| Search media | 52,577,684B·40MiB guard **FAIL** | **16,810,996B·PASS** | **28,732,230B·PASS** |
| base64 /guard JSON | NOT_REACHED | 22,414,664 /22,418,328B·PASS | 38,309,640 /38,313,305B·PASS |
| SDK sentinel /실제provider | NOT_REACHED /NOT_REACHED | 1 /0회 | 1 /0회 |

| 직접 시간(초, 중첩 합산 금지) | 기존360p 720초 | 이번270p·CRF28 720초 | 이번1200초 |
| --- | ---: | ---: | --- |
| 입력 등록 | 과거 보호 원문 참조 | 36.564 | 60.384 |
| Recording 준비(publish 포함) | 706.412 | 746.085 | 1219.275 |
| DB publish /commit | 27.143 /1.925 | 36.381 /1.904 | 61.132 /3.006 |
| 정상 신규ref rollback | 과거 보호 원문 참조 | 33.105 | 63.843 |
| 새 물리 연결 조회 /추가 detached decode | 107.560 /27.080 | 126.638 /28.692 | 236.098 /47.545 |
| Search source copy /encode | 0.451 /60.454 | 0.444 /44.056 | 0.620 /76.628 |
| base64 /guard dumps | NOT_REACHED | 0.070 /0.077 | 0.130 /0.115 |
| Search 준비 context(request 포함) | 61.061·guard 거부 | 47.430 | 82.182 |

| 자원·관측 | 이번720초 | 이번1200초 |
| --- | ---: | --- |
| runner RSS 표본 /ru_maxrss | 557,056,000B /543,712KiB | 884,338,688B /863,276KiB |
| runner cgroup 표본 /kernel peak | 984,805,376 /984,805,376B | 1,678,831,616 /1,678,831,616B |
| temp 표본(익명 open 파일 포함) | 447,634,986B | 760,974,672B |
| ffmpeg /ffprobe RSS 표본 | 109,232,128 /26,329,088B | 109,416,448 /26,128,384B |
| runner CPU 표본 최종 누적 | 46.20초 | 74.95초 |
| tool CPU 관측 하한(ffmpeg /ffprobe) | 582.62 /296.89초 | 978.67 /477.53초 |
| DB RSS /cgroup 표본 /data | 241,028KiB /305,745,920B /622,461,281B | 244,488KiB /275,783,680B /1,453,216,097B |
| DB cgroup CPU 표본 window 차이 | 52,210,723µs | 92,233,313µs |
| Windows 가용RAM /C free 최소 표본 | 4,617,490,432 /17,699,684,352B | 3,884,109,824 /15,782,158,336B |
| runner 표본 수 /최대 간격 /window | 4517 /0.663초 /1025.632초 | 7568 /0.924초 /1716.606초 |
| 실제 command /result packet 최대 | 524,467 /262,155B | 524,468 /262,155B |

packet 값은 PyMySQL command(+command byte)/result payload 길이다. TCP 전체 wire·SDK body 직렬화·provider latency는 측정하지 않았다. sentinel에서 송신 전 중단했으므로 SDK body/HTTP wire는 NOT_RUN이며 실제 탐색 응답·recall·오탐도 NOT_RUN이다. 육안 품질 비교는 수행하지 않았고 파일 크기를 탐색 품질 보장으로 사용하지 않는다.

1200초 resolve는13span·COMPLETE·missing range0이다. Recording 최종 PTS 증가·coverage discontinuity0·provenance PASS이며 요청 전체를 처리했다. 반환 format duration1200.033333과 timeline_range.end_sec1200.0333326666666은 서로 다른 실제 값이다. 새 조회에서도 각 값·타입·float hex가 원본 metadata와 정확히 같았다. 반올림·허용오차 확대·요청값 덮어쓰기로 통과시키지 않았다.

1200초 Coarse는480×270·video1/audio0·2400frame·재생2400초다. clock1/16384, PTS0→39305216+16384tick, 증가/coverage PASS, 원본 좌표0–1200.033333·playback_speed0.5를 유지했다. 실제 Coarse encode1회·CRF28.0이며 hook/subprocess 원복도 확인했다. 요청 구간 분할·후보 병합·Fine/Case 변경은 없다.

1200초 media는40MiB보다13,210,810B, guard JSON은56MiB보다20,406,951B 작았다. 앞서 계산한 Search 비례 추정28,018,326.67B보다 직접값은713,903.33B 컸다. Recording 직접값도359,019,991.67B 추정보다 컸다. 비례 추정을 직접 결과로 사용하지 않는다. temp 직접값760,974,672B=`2×366,121,221+28,732,230`으로 이번 run의 중첩 모델과 일치했다.

writer→fresh reader는720에서10→11,1200에서13→16이다. 조회 callback 뒤 checkout0·service 종료 후 동일 detached stream의 strict decode·64KiB bounded hash/길이 검증·Search copy hash 일치를 확인했다. 새 ref의 정상 rollback 후 writer 연결도 유지됐다. 실측 window의 provider/socket/HTTP0·SDK sentinel1, Aborted_clients0→0, temp0·자식0·sampler/cleanup 오류0이다. fence 자체의 초기 negative controls와 실측 window의 횟수를 구분한다.

DB kernel peak305,975,296B는 같은 DB의 누적 생애 값이다. 별도 DB temp collector는1200 실행 중간부터175표본/922.547초/최대간격7.485초를 수집했다. 실제 tmpdir는`/tmp`, `/tmp`·`/var/tmp`의 `du -sb` 최대는 각각4,096B(디렉터리 엔트리 포함)였다. 이 표본은 **subset**이며 시작 전 구간·unlink된 DB 익명 임시 파일·전체 temp peak는 UNKNOWN이다. DB data와 C 물리 여유 표본을 대체하지 않는다.

3900MiB는 실행 전 전체 cap을 확보하는 gate다. 실행 중에는 기존 Windows700MiB reserve와 runner/DB/temp soft stop을 적용했다. 두 run 모두 OOM·자동 restart·자원 중단은 없었다. 별도 collector 전후의 MySQL8.4.13/packet64MiB/Aborted_clients0도 일치했다.

## 검증·리뷰·정리

| 검증 | 직접 결과·범위 |
| --- | --- |
| 새 override controls | RED9 FAIL→GREEN. 실제 제품 argv builder·Fine seek/격리·encode실패/context중단 원복·invalid 설정 |
| stdout 계측 회귀 | 실제 작은 control FAIL 보존, RED1→GREEN. capture_stdout 누락 수정 |
| 확장 예산 controls | RED15→GREEN15. RAM/temp/DB/C·reserve·감독·한쪽 한도만 올리는 조합 거부 |
| 하네스/Sampler 통합 | 의도적 RED1→전체72 PASS(Windows3.77초/Linux3.92초). 다른 thread 격리·호출계약 drift 거부 포함 |
| 두 감독기 controls | 15 PASS(0.43초). owner/name·관측실패·start timeout·정리·실제 hard-limit 전달·budget identity |
| 관련 Search/Recording 회귀 | 102 PASS(16.03초). 배속/역변환·provider bounds/deadline·chunk·metadata·Analysis limits |
| Runtime quality | Ruff PASS, Linux/Windows mypy 각각89 source PASS |
| 변경 Python lint | harness/budget/두 test Ruff PASS |
| boundary /Contract | PASS /구조62·JSON26·의미104 모두 PASS |

전체 로컬 pytest·전체 mandatory MySQL은 반복하지 않았다. focused 단위 검사와 이번 실제 격리 DB/media 실측을 전체 acceptance suite로 표현하지 않는다.

구현 대화 이력을 전달하지 않은 fresh 읽기 전용 reviewer가 코드·argv·예산·계측·보호 증거를 검토했다. 1차 직접 controls는 의도적 통합 RED1을 제외한61 PASS/1 deselected와 감독기14 PASS였다. reviewer의 첫 시도는 개인 basetemp 부모 부재로14 fixture ERROR였고, 부모 생성 후 별도 실행으로 통과했다. 이 setup 오류를 제품 실패나 실측 실패로 분류하지 않는다.

reviewer 지적 중 budget 모듈 identity 누락을 사본·host/runner hash 대조로 보완했고, **같은 reviewer**가 통합 후 직접87 controls PASS(3.77초)로 재확인했다. 720 실영상/DB/FFmpeg·1200 preflight/실제 Docker 한도는 작성자 증거 열람·대조이며 reviewer가 재실측한 것이 아니다. 최종1200 결과·문서·정리도 같은 reviewer가 재확인했고 미해결 actionable 지적은 없었다. 원문7568표본의 수치·DB temp subset·metadata float hex·종료 감사·정리 증거를 다시 계산·대조했다. 현재 harness가1200 실행 사본과 동일해 앞87 controls는 반복하지 않았다. reviewer의 실제 미디어/DB/Docker/provider 재실행은0회다.

종료 work 감사는 files0/bytes0이었다. 소유 컨테이너10개의 State·OOM false·자동 RestartCount0을 보호 JSON에 보존했다. 실패한 작은 control1개의 exit1·로그도 보존했고 성공으로 덮지 않았다. 실행 중인 소유 runner가 없는지 확인한 뒤 DB를 정상 중단하고 exact-name/owner/volume 미사용 검사로 컨테이너10개·이번 data/work volume2개·internal network1개만 정리했다. 정리6.047초, owner 자원 재조회0이다. 전체 Docker 컨테이너0·network bridge/host/none·보호 volume3개 이름 유지도 별도 확인했다. 보호 volume을 mount/read/start/reuse/delete하지 않았다. 이번 시작의 보호 volume owner-label snapshot은 없어 label 전후 동등성은 UNKNOWN이며 현재 metadata만 보존했다.

16:04 KST 종료 감사에서 원본15/15 SHA-256·size·mtime, manifest hash·제품 source path+content hash·기존 runner hash가 시작과 같았다. 종료 순간 Windows 가용RAM5,371,940,864B/C 물리여유15,792,267,264B였다. 원본명·개인 경로·GPS·번호판·RAW·credential은 공개 결과에서 제외했고 ignored 보호 scratch에만 필요한 증거를 보존했다. 공유 Docker/WSL 재시작·prune·image/cache 변경·강제 앱 종료는 하지 않았다. 소유 volume 삭제가 C 물리 여유를 즉시 반환한다고 가정하지 않는다.

## Decision Gate·Owner 후속

같은 single-AnalysisSource·전체 단일 Coarse 요청 구조에서 **1200초 logical range의 로컬 준비·저장·재조회·Search 크기 guard까지 직접 통과**했다. 이번 가장 긴 직접 성공은1200초이며 이를 단회 local subset 밖의 처리량·동시 지원 수·일반적20분 제품 지원으로 확대하지 않는다. 실제 촬영 seam 연속성·일반적 성능·표본 사이 전체 peak·DB 익명 temp peak는 UNKNOWN이다.

다음 단계는 Search Owner가 비용 승인을 받아 기존 회귀 표본에서 현재 설정과 recall·오탐을 비교하는 것이다. 270p·CRF28의 운영 승격이나 cap 상향을 승인하지 않는다. 품질 미충족 시 다른 후보는 Owner 결정으로 남긴다.

배포 머신의 준비 시간/입력 길이 비율·PM의 허용 대기 시간·Case Owner의 마감 정책·실제 provider·Case/Web·Package READY·다운로드·AWS/배포 acceptance도 남아 있다. 이번 로컬 Recording 준비1219.275초가 기존 Case 대기식의180초보다 크지만 Case를 실행하지 않았으므로 실제 timeout 결과는 NOT_RUN이다. 계약이나 마감은 바꾸지 않았다.

NOT_RUN: 품질 회귀·실제 provider·SDK body/HTTP wire·Case 전체 흐름·배포/AWS·전체 pytest/mandatory MySQL. 과거360p720초의 media guard FAIL과 뒤 단계 NOT_REACHED, 과거1200 NOT_RUN은 그 실행 당시 결과로 보존한다. 이번 두 run의 성공으로 과거 실패를 지우지 않는다.

## 공개 변경 파일

- `scripts/recording_real_media_recheck.py` — Coarse 한정 override/실제 argv·출력 계측·공유 예산 연결.
- `scripts/recording_probe_budget.py` — 실험 전용 유한 profile·중첩 자원/감독/실행 전 검증.
- `tests/runtime/test_real_media_recheck.py` — override·원복·격리·stdout·Sampler 통합 controls.
- `tests/runtime/test_recording_probe_budget.py` — 예산 거부·coordinated profile controls.
- `docs/superpowers/plans/2026-11-03-coarse-270p-probe.md` — 승인된 범위의 실행 계획.
- `docs/runtime/experiments/2026-11-03-coarse-270p-probe.md` — 이 결과 원문.

제품 source·production 설정·원래 계획·과거 실패 원문은 변경하지 않았다. 새 변경은 미커밋·미스테이징으로 남긴다. commit/push/PR/댓글/merge·provider·운영 변경은 하지 않았다.
