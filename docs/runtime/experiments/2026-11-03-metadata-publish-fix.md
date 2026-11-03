# Prepared metadata publish 숫자 보존 수정 — 2026-11-03

최종 상태: **metadata 결함 수정·실제10초/100초 모듈 경계 PASS, 240초 byte cap typed 거부**.
실제100초의1ULP 원인을 확인하고 정확한 저장 표현을 수정했다. 검사·한도는 유지했다.
담당: 정철원(Runtime/Recording). provider·AWS·운영·20분 E2E 결과가 아니다.

## 시작·계약·기존 증거 보존

branch `codex/issue452-real-media-recheck`, HEAD `fb40402676f7712fb86e67c468fb1c50f327bfed`를 유지한다.
최초 index는 비어 있었고 이전 문서·harness·controls3파일의 미커밋 변경을 ignored snapshot/hash로 보존했다.
원래 [실패 기록](2026-11-03-real-media-recheck.md)은 수정하지 않았다.
사용자 AGENTS.md 지침, CLAUDE.md 라우터, docs 규칙, AnalysisSource/IncidentClip Final Contract와
청크 저장 구현 메모·이전 실제/합성 실패 evidence를 읽었다.

metadata 동등성 검사는 같은 opaque ref에 다른 값이 등록되어 canonical metadata·provenance가
덮어써지는 것을 막는다. public duration/range는 number이며 stream/provenance와 timeline revision도
함께 유지해야 한다. 비교 삭제나 허용오차로 통과시키면 이 경계를 깨므로 사용하지 않았다.

## 수정 전 실제100초 진단 — 합성 재현과 별도 실행

제품 코드를 바꾸기 전에 같은 input-02→03·명시 placement·0–100초·baseline profile로 한 번 재현했다.
원본은 ro이며 이 실행은 진단 목적이다. source/도구/요청·cap은 이전 실험과 동일하다.
현재 Windows RAM4,659,180KiB/C13,238,513,664B, Docker 컨테이너0을 직접 확인한 후 시작했다.
WSL available7,175,761,920B는 Windows 물리 RAM과 합산하지 않았다.
시작 원본15/15 SHA-256·size·mtime이 보호 manifest와 일치했다.

새 owner DB·volume·internal network를 만들었다. 기존 보존 volume3개는 사용하지 않았다.
기존 supervisor를 별도 owner/evidence 경로로 복사하고 같은 resource/stop/정리 경계를 유지했다.
시작 RAM3004MiB = runner1280+DB512+reserve700+보수적 collector/daemon512MiB,
C 시작6GiB/reserve4GiB·성장2GiB, DB data1GiB·cgroup440MiB soft,
runner cgroup1100MiB·temp512MiB soft, swap 추가 없음·CPU1.5/0.5·affinity2개다.
Recording 도구120초/Search150초/runner900초/host930초·정리60초 후보 예산을 유지했다.
각 실제 단계 직전 host/DB 상태와 예산을 다시 확인했다.

비민감 진단은 field path·타입·숫자·float hex만 남긴다. ID/파일명/임의 문자열 값은 redaction한다.
현재 준비 모델과 locking read payload를 관찰했으며, 반환값·비교·encode 옵션을 바꾸지 않았다.

| 실제100-a locking 비교 | 쓰기 전 | DB 조회 후 |
| --- | --- | --- |
| 차이 필드 | `timeline_range.end_sec` | 같은 필드1개 |
| 타입 | float | float |
| 값 | 100.00000033333333 | 100.00000033333332 |
| hex | `0x1.900000165e9f8p+6` | `0x1.900000165e9f7p+6` |

model_equal=false이고 `mysql_repository.py`의 기존 exact model 비교에서 ValueError였다.
이제 **실제 입력과 이전 합성1ULP 재현이 같은 현상임을 직접 확인했다**.
이전 세션이 이를 추론으로 남겼던 기록은 당시 계측 한계로 보존한다.
이전 문서의 ‘hex 최하위1bit’ 표현은 정확하지 않으며, 이번 기록에서 ‘인접 float의1ULP 차이’로 정정한다.
실제 media38,363,450B·concat/strict decode는 성공했지만 청크 저장·새 조회·Search는 NOT_REACHED였다.
수정 전 Recording 준비162.657초, cleanup/temp0, sampler 오류 없음이다.

## 수정·RED/GREEN

SQLAlchemy의 JSON serializer는 모델 float를 JSON 숫자 literal로 전달한다.
기존 MySQL native JSON 저장/조회에서는 위 숫자가1ULP 달라졌다.
수정은 `analysis_source`/`incident_clip` 두 종류의 repository 내부 표현만 바꾼다.

- versioned envelope의 JSON 문자열 안에 원래 모델 JSON을 저장한다. MySQL은 inner 숫자를 재파싱하지 않는다.
- `_row`에서 두 kind만 encode하고 `_get`/`_models`에서 decode한다. metadata-only 등록도 포함한다.
- public 모델/ref fingerprint 입력과 exact model 비교는 그대로다. 소비자는 원래 number·값·타입을 받는다.
- legacy dictionary는 그대로 읽고 같은 ref replay 때 수정하지 않는다. 과거에 이미 달라진 값을 추측해 복원하지 않는다.
- version/type/key 형태·중복 key·non-JSON 숫자·overflow가 잘못된 envelope는 거부한다. 정상 모델과 손상값을 혼동하지 않는다.
- DDL/migration·media bytes·PTS/duration/coverage/provenance 검증·Recording/Search cap·Case timeout은 바꾸지 않았다.

| 검증 | 결과 |
| --- | --- |
| 실제 MySQL 정확 metadata 회귀2kind, 수정 전 | 2 FAIL, 기존 immutable 비교에서 RED |
| codec 경계 단위 | 구현 전19 FAIL → 후속 focused 안에서 PASS |
| 새 actual MySQL 회귀 | 최종8 PASS, 6.28초 |
| 새 codec+기존 chunked+새·기존 harness controls | 60 PASS, 4.73초 |
| durable/ownership/Analysis limit 관련 | 68 PASS, 14.95초 |
| 같은8.1 VFR/frame-duration/Analysis limit/multi-span4파일 | 131 PASS/원본 opt-in1 deselected, 14.12초 |
| 기존 chunked+새 exact MySQL focused | 27 PASS/commit ACK-loss1 deselected, 62.28초 |
| 독립 MySQL evidence inventory 관련 단위 | 313 PASS/나머지 deselected, 3.59초 |
| Runtime quality | Ruff + Linux/Windows mypy 각87 source PASS |
| boundary/Contract | PASS, 구조62/JSON26/의미104 |

새 MySQL 회귀는 별 물리 연결에서 정확한 값/hex·목록·AssetFacts·stream을 확인하고,
동일 replay 뒤1ULP·duration·stream·revision·provenance 변경을 모두 거부하며 행/청크/case link가
변하지 않는지 검사한다. metadata-only→content 연결과 legacy 원문 미갱신·outer corruption도 포함한다.
8개 MySQL check identity를 독립 inventory와 checker에 각각 추가했다.
68개 로컬 합성 fixture 회귀는 Windows9.0.1이고, 위131개와 모든 실제 입력 실행은 고정 이미지의8.1이다.
Windows 결과를8.1 실제 측정의 대체 증거로 사용하지 않았다.

최초 MySQL RED 시도는 pytest temp 경로 누락으로 setup에 실패했고 제품 RED가 아니다.
별도 시도에서 위2 FAIL을 확인했다. 최초 GREEN은6 PASS/2 FAIL이었다.
두 실패는 prepared AssetFacts를 지원하지 않는 lookup 경로로 직접 호출한 테스트 오류로,
실제 public 목록 경로로만 수정한 후8 PASS였다. 숫자 기대값이나 실패 검증을 완화하지 않았다.
진단 helper RED1 FAIL→23 controls PASS, Linux23 PASS도 각각 보존했다.

**호환성 한계:** 새 코드는 legacy를 읽지만 이전 코드(#544 포함)는 envelope 행을 읽지 못한다.
schema revision이 같아도 code rollback 호환성을 보장하지 않는다. 운영 적용/rollback은 실행하지 않았다.
청크와 envelope 각각의 reader 조건, 현재 HEAD가 새 decoder를 포함하지 않는 점,
향후 검증된 commit SHA/image tuple 및 controller 승인 조건은
[구현 메모의 배포·rollback revision 조건](../../modules/recording/chunked-prepared-media.md#배포rollback에-사용할-revision-조건)을 따른다.
현재 미커밋 소스를 기존 HEAD의 배포/rollback 호환성 증거로 대체하지 않는다.

## 수정 후 실제 경계 검증

Analysis480/veryfast/CRF23·240000ms/50331648B, packet67,108,864B,
Search source/media/request512/40/56MiB·준비150초는 유지했다.
immutable image·FFmpeg/ffprobe8.1 binary identity와 source ro/import 위치를 확인했다.
원본·metadata-relative placement는 기존 manifest/기록을 따른다.
같은 전방 카메라/연속 주행은 사용자 설명이며 새 촬영 seam 검증은 아니다.

10-a는 Recording→청크 저장→commit→writer close/dispose→다른 물리 connection 조회→
동일 detached stream 길이/hash·strict decode→Search copy/reencode/guard→SDK sentinel을 통과했다.
writer209/reader210, callback 후 checkout0, metadata 차이0, 신규ref rollback·동일 writer 연결,
Aborted_clients0→0, temp/child/cleanup 오류0이다. 원래10.0 값과 hex도 새 연결에서 일치했다.
외부망·HTTP send·인증 SDK/provider는 차단했으며 guard PASS를 실제 HTTP/provider 성공으로 표현하지 않는다.



### 실제 실행별 직접 수치

시간은 monotonic seconds이며 중첩 phase를 합산하지 않는다. Recording 준비는 DB publish 시도를 포함한다.
다른 run/Windows·WSL의 monotonic epoch를 정밀 정렬한 측정이 아니다.

| 관측 | 수정 후10-a | 수정 후100-b | 240-a |
| --- | ---: | ---: | --- |
| 요청/선택 | input-02,0–10초/1span | input-02→03,0–100초/2span | 기존 input-01→02→03,0–240초/3span |
| 개별 encode | 6.336초 | 52.369 / 7.320초 | 42.739초 PASS / 25.355초 typed 거부 |
| 완료된 part bytes | 4,246,998 | 33,347,841 / 5,015,985 | 첫 part33,665,675 |
| chain 전체 / concat mux | 해당 없음 | 155.388 / 0.195초 | chain142.793초 거부, concat NOT_REACHED |
| 최종 media bytes | 4,246,998 | 38,363,450 | NOT_REACHED |
| Recording 준비 | 43.211초 PASS | 163.283초 PASS | 147.566초 TYPED_REJECTION |
| DB publish / commit | 0.895 / 0.185초 | 4.311 / 0.622초 | NOT_REACHED |
| 저장 청크 | 17행 | 147행 | 0행 |
| 실제 command 최대 | 524,466B | 524,467B | 1,921B — metadata 조회뿐 |
| 실제 row packet 최대 | 262,155B | 262,155B | 971B — metadata 조회뿐 |
| commit 후 별 물리 연결/hash·길이 | 1.746초 PASS | 7.790초 PASS | NOT_REACHED |
| 추가 detached strict decode | 0.783초 PASS | 6.296초 PASS | NOT_REACHED |
| Search source copy / reencode | 0.040 / 1.373초 | 0.105 / 12.994초 | NOT_REACHED |
| Search media / base64 / guard JSON | 904,589 / 1,206,120 / 1,209,783B | 8,482,166 / 11,309,556 / 11,313,220B | NOT_REACHED |
| SDK entry sentinel | 1회 | 1회 | NOT_REACHED |

100-b는 writer212/reader213, callback 후 checkout0, service 종료 후에도 stream 유효,
원래 media와 detached stream의 길이/SHA-256 일치, 같은 bounded64KiB stream의 Search source copy/hash 일치를 확인했다.
새 연결에서 duration_sec는 float100.0, 문제의 timeline_range.end_sec는
**float100.00000033333333 / hex0x1.900000165e9f8p+6**으로 생산 시점과 정확히 일치했다.
전체 metadata 모델도 동일했다. 신규ref prepared rollback·같은 writer 연결·Aborted_clients0→0을 통과했다.
10/100 모두 cleanup 오류·sampler 오류·live child·temp 잔여0이다.

수정 전100-a와 수정 후100-b는 최종 bytes와 SHA-256도 동일했다. 다른 것은 metadata의 저장 표현이다.
실행마다 새 등록/격리 schema를 사용하므로 원본 provenance ref 문자열이 run 사이에 같다고 주장하지 않는다.
각 run의 생산 모델과 재조회 provenance는 정확히 같았다.

Search playback duration은 각각20/200초다. 기존 Coarse2fps→playback1fps 전송 준비에 따른 값이며,
원본10/100초 metadata가 바뀐 것이 아니다. Search의 전체 proxy read/base64/guard 문자열·bytes 할당은 남는다.
base64/dumps 시간은10초0.030/0.023초,100초0.061/0.052초였다.
guard JSON은 실제 SDK schema/body·HTTP wire가 아니며 이 세 경계와 provider 성공은 NOT_RUN이다.

### 240초 진입·정확한 중단 경계

10/100 통과 후100-b runner kernel cgroup peak235,532,288B·temp sampled max85,209,066B,
남은 host RAM/disk·DB 여유를 대조했다. 같은1280MiB/512MiB cap을 쓰며 새 예산을 낮추지 않았다.
시간 후보300초(관측100초 준비163.283초와 과거 첫span131.787초를 참고한 보수적 추정),
hard supervisor930초/도구120초/정리60초를 보존한 유한1회로 결정했다. 선형 성능 보장은 아니다.

240-a 첫 VFR span은3218frame의 PTS·duration·coverage 검증을 통과했다.
두 번째 span의 남은 출력 예산은50,331,648−33,665,675 = **16,665,973B (계산)**였다.
typed 거부 시 캡처한 partial file은16,777,264B였고 합계50,442,939B로 기준보다111,291B 컸다.
이는 마지막 partial file 길이이며 연속 최대치나 완성된/검증된 재생 영상 크기가 아니다.
기존 실행 중 byte guard가 ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED로 중단하고 정리했다.
partial 크기는 실패 observer의 finally에서 측정했으며 원래 예외·명령·반환값은 유지했다.
그 계측의 RED1 FAIL→새·기존 harness controls24 PASS(3.14초)도 보존했다.

전체240초의 concat·최종 strict decode·metadata publish·DB 청크·Search는 **NOT_REACHED**다.
4분 영상 성공이나 새 ceiling으로 표현하지 않는다. 한도를 상향하거나 같은 거부를 반복하지 않았다.
240 writer의 rollback 후 물리 연결 동일성은 별도 계측하지 않아 UNKNOWN이다.
그 후 같은 소유 DB의 global Aborted_clients0과 prepared/chunk 행0은 독립 조회했다.

## 자원·리뷰·종료

다음은 bytes 단위 sampled maxima와 kernel cgroup peak를 구분한 값이다.

| 실행 | runner RSS 표본 | ffmpeg / ffprobe RSS 표본 | runner cgroup 표본 / kernel peak | temp 논리bytes 표본 |
| --- | ---: | ---: | ---: | ---: |
| 수정 전100-a | 163,385,344 | 107,958,272 / 26,042,368 | 310,824,960 / 310,824,960 | 76,727,379 |
| 수정 후10-a | 103,309,312 | 106,909,696 / 25,546,752 | 285,978,624 / 285,978,624 | 9,398,585 |
| 수정 후100-b | 164,573,184 | 107,413,504 / 25,980,928 | 235,532,288 / 235,532,288 | 85,209,066 |
| 240-a | 120,418,304 | 108,929,024 / 25,673,728 | 336,826,368 / 337,350,656 | 33,665,675 |

ru_maxrss는 각각159,220/100,724/160,588/117,344KiB로 별도 보존했다.
페이지 cache/샘플 간 peak·짧은 child 생존·driver별 allocation은 이 수치만으로 확정할 수 없다.
unlink된 open stream도 inode를 중복 제거해 temp에 포함했고 CPU 누적·DB RSS/HWM·cgroup/data와
host 표본은 ignored JSONL에 남겼다. DB cgroup peak는 수동 재개 전후 세대가 다르므로 RSS나 run 사이 처리량과 단순 비교하지 않는다.
감독기 host 표본 RAM 최소3,955,015,680B/C free최소13,147,766,784B,
DB cgroup 표본 최대302,350,336B/data최대228,114,170B였다. 물리 전체 peak 보장이 아니다.

실제 제품 진단 실패와 테스트 호출 오류 뒤 감독 정책으로 이번 소유 DB를 정상 stop했고,
각 원인 확인 후 TCP final-server readiness로 수동 재개2회였다. 자동 RestartCount0과 구분한다.
OOMKilled는 소유 컨테이너 모두 false, 공유 Docker/WSL 재시작이나 다른 작업 강제 종료는 없었다.
마지막 DB는 MySQL8.4.13/packet67,108,864B/Aborted_clients0이며 이 값이 재개 전 진단 run의
누락된 connection stability를 대체하지 않는다.

정리 전 별도 조회에서 (analysis_source,prepared_content,chunk,rollback-case-link) 행 수는
수정 전100-a (0,0,0,0), 수정 후10-a (1,1,17,0),100-b (1,1,147,0),240-a (0,0,0,0)이었다.
work-audit files0/bytes0을 확인했고 성공 중간 영상은 남기지 않았다.
필요한 최초/중간 실패 JSON·runner/source identity·RED/GREEN·작은 재현·표본만 ignored scratch에 보존했다.
이번 owner의 컨테이너15개·data/work volume·internal network는 exact-name/owner/idle 확인 후 정리했다.
일반 테스트 성공 temp도 작업 경계를 확인한 뒤 정리했다. 기존 보존 volume3개는 사용·변경·삭제하지 않았다.

종료03:13:48 KST 원본15/15 SHA-256·size·mtime 불변이다. 그 순간 Windows available5,160,562,688B,
C free13,145,149,440B였으며 이후 여유를 보장하지 않는다. 제품 source 변경은 의도한 repository와
새 codec뿐이고 기존 capacity runner·manifest·이전 실패 문서의 불변 여부도 최종 검사로 확인했다.

독립 fresh read-only reviewer는 실제100의 변경 필드/hex, 구현·legacy/손상/비정상 숫자 회귀,
10/100의 정확 복원·새 연결·Search sentinel과240 typed 결과를 파일로 대조했다.
직접 offline45 PASS(2.80초)를 실행했고 실제 영상/DB/Docker/provider는 재실행하지 않았다.
최종 evidence/문서·원본/자원 종료를 reviewer가 재확인했고 미해결 P1/P2는 없었다.
용어1곳을 지적받아1ULP 차이로 정정했으며 제품·검증 기준은 바꾸지 않았다.
전체 pytest·전체 mandatory MySQL·CI 재실행은 NOT_RUN이다.
commit/staging/push/PR/외부 게시·provider/AWS/배포/운영 migration·큰 backup/restore는 하지 않았다.

이번에 metadata publish 결함과 동일100초의 Recording→DB→Search 준비 경계는 해결·검증했다.
240초의 다음 최초 경계는 기존48MiB 출력 byte cap이다. 이 결과를 Case/Web·Package READY·
20분 E2E·지원 길이·성능 보장·운영값 승격으로 확대하지 않는다.
