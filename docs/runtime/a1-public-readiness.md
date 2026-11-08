# A-1 서버 연결과 공개 운영 검수

## 제한적 외부 공개 운영 인계 — 2026-11-09 KST

**현재 상태: 운영자(사용자)의 공개 승인에 따라 공식 샘플 전용 A-1을 외부에 개방했다.**
공개 전환은 07:42:12 KST, 후속 서버 조회는 07:46:34 KST다.
이 절이 아래 구현·NO-GO·운영 미적용 snapshot보다 최신이며, 아래 기록은 당시 이력으로 보존한다.
추가 분석·Case 생성·provider 호출 없이 진입 화면과 GET 접근만 확인했다.

| 항목 | 실제 확인값 |
| --- | --- |
| 공개 진입 | **https://daesingo-ktc4.duckdns.org/?sample** — 기본 `/`의 기존 흐름과 구분 |
| 최종 source / schema revision | `91e41a15de0fe1c1879b76026ee454cb809be08f` |
| image digest | `sha256:24664217733dbd6da1781bfe193ee1ae102288510ca9d7ae14c7e68d0fac114c` |
| config / heads | `aws-a1-local-ocr-v4` / `case_0001`, `recording_0002`, `runtime_0008` |
| 공식 묶음 | `synthetic-v3-1min-full10`：10개, 합계 600,000ms, 244,829,133B. 임의 업로드 거부 유지 |
| manifest SHA256 | `e7f54761ffad29333155085c15161f37e5aff826cce7a1c66afe030287a0a9f5` |
| 분석 admission 한도 | `session_daily=1`, `ip_daily=10`, `case_repeats=2`, `session_concurrent=1`, `global_concurrent=1` |
| 무료 작업 별도 한도 | `local_work.case_jobs=12`, `ip_daily_jobs=40`, `global_concurrent=2` |
| TTL | session / Case 각 604,800초(7일), source 86,400초(24시간). 세션 권한·만료 검사 유지 |
| 실행 / 비용 보호 | Coarse 600초 유지. `elice_supported` 명시 모드. 체험별·일·누적 **원화 상한은 강제하지 않는다**. 무제한 지원·추가 청구 없음의 보장이 아니다. 기존 비용·예약·사용량 원장 보존 |
| gate | `accepting=true`, `jobs_stopped=false`, policy 일치. 일반 분석 수용 중단과 모든 신규 job 긴급 중단 기능 유지 |
| 서비스 / 자원 | API·MySQL healthy, Worker running, 재시작 0. RAM 여유 6,198,882,304B / reserve 961,544,192B. disk 여유 13,630,697,472B / reserve 10,737,418,240B |
| 작업 / 배포 상태 | 후속 조회 시 blocking jobs=0, 미정산·미관측 usage=0, dirty/operation.lock 없음 |
| 복구 | 같은 SHA의 guarded current 재기동 실제 PASS. 현재 schema rollback 허용은 **이 SHA 하나**. 구버전으로 세션 보호를 우회하지 않는다. 전체 DB/media backup restore는 **NOT_RUN** |

SSM 공개 전환 `84eb2fce-fdd3-4d12-9468-826bfa567d3a`와 후속 읽기 전용 조회
`cc476cae-932e-42d7-9ed5-28824ca2f197`는 모두 Success / exit 0이다.
Caddy의 운영자 IP 제한 두 줄만 제거하고 128MiB body 제한·no-store·loopback API 경로를 보존했다.
현재 Caddyfile SHA256은 `01dea60f0135ea97c483971bdb7a8273b4b8f88571a82debbac5c5920ca2ae39`다.
이전 allowlist 밖의 TLS loopback 검사에서 진입·샘플 목록·version·readiness가 모두 200이었다.
새 익명 Chrome context에서도 정상 TLS로 진입 200, 공식 묶음 표시, 선택 후 준비 버튼 활성화,
version 정확한 SHA 및 readiness 200을 확인했다. 준비 버튼은 누르지 않았고 페이지 요청은 GET뿐이다.
브라우저 인증자료는 저장하지 않았다. 기존 검수 브라우저는 이 확인 전에 연결이 종료된 상태여서
인증을 복사하지 않은 새 익명 context로 공개 진입만 확인했다.

### 알려진 문제: 삭제 최초 응답 유실

실제 검수에서 첫 삭제 요청 한 번은 Web의 15초 AbortSignal 이후 `web.network_error`로 표시됐다.
이는 삭제 실패 확정이 아니다. 서버 읽기 전용 대조에서 `DELETED`, 전용 원본·파생·분석·청크·임시 파일 삭제,
공식 원본 10개 및 비용·예약·사용량 원장 보존을 확인했다. 이어 같은 소유 세션에서 명시적으로 한 번
재확인한 멱등 DELETE는 **200 / DELETED / files=0**, UI는 **“삭제했어요.”**였다.
최초 1회 + 명시적 재확인 1회이며 중복 클릭이나 자동 반복이 아니다.
15초를 넘긴 정확한 서버 세부 구간은 **원인 미확정**이다. RAM 부족·Docker 장애·lock deadlock으로 단정하지 않는다.

운영 재확인 순서:

1. 같은 브라우저·같은 세션을 유지한다. 쿠키 삭제·새 체험 생성·분석 재실행으로 확인하지 않는다.
2. 202 / DELETING이면 기존 **“삭제 다시 확인”**을 사용한다. 첫 응답 유실이면 운영자가 상태를 먼저 확인하고,
   기존 **“체험 데이터 삭제” → 확인**으로 한 번만 멱등 재확인한다. 200 / DELETED와 완료 안내로 판정한다.
   404만으로 물리 삭제·원장 보존까지 완료됐다고 판단하지 않는다.
3. timeout 반복·DELETING 지속·소유 상태 확인 불가 시 자동/맹목 반복을 중단한다. Runtime/Case 담당이 읽기 전용으로
   `public_case.state`, 저장된 삭제 계획·lease·활성 job·usage, 전용 파일/청크/임시 파일과 공식 원본·원장 보존을 대조한다.
   이번 시험의 고정 Case용 audit를 다른 Case에 그대로 적용하거나 대상 보호 assertion을 풀지 않는다.
4. 원본·원장·백업·증거를 보존한다. 임의 SQL/파일 삭제, lock 제거, timeout·한도 완화로 완료 처리하지 않는다.

기존 [ownership](../management/ownership.md) 기준의 인계 창구다. 새 담당 수락이나 팀 통지를 수행했다는 뜻은 아니다.

| 책임 경계 | 인계 담당 |
| --- | --- |
| 운영 중단·재개 판정 / common-runtime | 김준영(PM) |
| Case 삭제 상태·멱등 재확인·long-running 계약 | 유소연, Web 지원 신유민 |
| Web 15초 응답 유실 안내·완료 재확인 UX | 신유민 |
| 전용 저장물·청크·임시 파일 잔여 및 공식 원본 보존 | 정철원 |

### 중단 조건과 복구 경계

세션 간 Case/미디어/Range/다운로드 노출, 임의 업로드·비공식 입력 수용, policy/release/key 불일치,
원장 중복·정산 훼손, 공유/공식 원본 삭제 의심, 반복되는 삭제 결과 확인 불가가 발생하면 신규 job을 중단하고 증거를 보존한다.
API/Worker 비정상, dirty/lock 불명, 위 RAM/disk reserve 미달도 신규 수용 중단 조건이다.
한 번의 알려진 응답 유실 뒤 실제 DELETED·보존 증거·멱등 완료 응답이 확인된 경우와 구분한다.
진행 중인 팀원 작업을 임의 취소하거나 이미 시작된 provider 호출이 취소됐다고 가정하지 않는다.

기존 운영자 control을 사용한다(아래는 비상 시 명령이며 이번 공개 확인에서는 실행하지 않았다).

```sh
sudo docker compose --project-name daesingo-runtime -f /opt/daesingo/release-compose.json exec -T api \
  python -m daesingo.api.public_control stop --env-file /run/secrets/runtime.env
sudo docker compose --project-name daesingo-runtime -f /opt/daesingo/release-compose.json exec -T api \
  python -m daesingo.api.public_control status --env-file /run/secrets/runtime.env
# 세션 보호 노출 또는 stop 성공을 확인할 수 없을 때 ingress도 차단한다.
sudo systemctl stop caddy
```

`stop` 결과는 `accepting=false`, `jobs_stopped=true`로 확인한다. 기존 결과 조회/다운로드는 세션·만료 검사를 유지한다.
재개는 원인 해소·동일 identity·서비스·정책·보호 검사를 확인한 뒤 기존 `open` 절차로 판정하며 자동 재개하지 않는다.
Caddy의 개방 전 백업과 전환 영수증은 `/opt/daesingo/a1-public-go-20261109/`에 보호 보관했다.
백업 권한을 그대로 복사하는 `cp -p`나 과거 Caddyfile 무조건 덮어쓰기를 복구 명령으로 사용하지 않는다.
검증한 동일 SHA guarded current 경로를 재사용하고 구버전 rollback을 새로 승인하지 않는다.

남은 제한: 진입 화면에 과거 **“보관·삭제 기간과 반복 횟수 미확정 / 공개 준비 중”** 문구가 남아 있다(Web 후속).
실제 승인·적용값은 위 표이며 이번 공개에서 Web bundle을 바꾸지 않았다.
candidate video preview는 비활성 상태다. 실제 전체 DB/media 복원, overlay OCR 실제 재시도,
26분/대형 실패 재현·전체 capacity·메모리 peak 검증은 이번 공개 확인에서 **NOT_RUN**이다.
세션 격리·임의 업로드 거부·긴급 중단·실제 다운로드/재생·삭제 검수는 직전 동일 SHA의 증거를 재사용했다.
#452의 범위 초과·미지원 입력 실패 안내는 코드와 CI에서 확인했다. 배포본의 실제 API 응답·화면 안내·재시도 버튼 검수는 `NOT_RUN`이다. [#452 종료 기록](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)

로컬 상세 증거: `.codex-scratch/a1-public-go-20261109/PUBLIC_GO_RESULT.json`,
`browser-entry-proof.json`, `open2-result.private.json`, `post-open-result.private.json`.
공개 전환 당시에는 이 인계 문서를 로컬에만 준비했다. 이후 문서 전용 커밋으로 제출하며, 실행 코드나 배포 이미지를 변경하지 않는다.

## Elice 지원 모드 — 2026-11-08 정책 변경 (당시 운영 미적용 이력)

이 절은 아래 과거 snapshot과 후속 문서의 원화 예약 필수 문구보다 우선한다.
과거 문구는 기존 `krw` 모드의 계약으로 보존한다.

보호 policy의 `funding_mode`는 기본 `krw`이며 기존 양수 원화 상한·호출별 예약을 그대로 요구한다.
지원 서비스용 `elice_supported`를 명시하면 **체험별·KST 일일·공개 기간 누적 원화 상한을 강제하지 않는다**.
이는 지원이 무제한이거나 추가 청구가 없다는 확인이 아니다. 과거 승인된 일20,000원·누적100,000원을
이 모드에서 코드가 차단한다고 안내하면 안 된다. 원화 보호로 복귀하려면 실제 상한 근거를 갖춘 `krw` policy를
닫힌 상태에서 검증·활성화해야 하며, 기존 예약·비용·사용량 원장을 초기화하지 않는다.

지원 policy에는 비어 있지 않은 `support_ref`와 `supported_calls`의 정확한 operation/provider_label 쌍이 필요하다.
operation은 HINT_EXTRACT/SEARCH_COARSE/SEARCH_FINE, label은 실제 모델의 `elice:<model>`이다.
원화 상한·bounds는 함께 입력하지 않는다. 0원·가짜 단가·임의 예약액으로 채우지 않는다.
Worker는 실제 bootstrap의 Search/Intent 설정이 mlapi.run 및 해당 모델인지 매 호출 전에 확인한다.
이름표만 Elice인 다른 endpoint나 미등록 쌍, 필수 설정 누락은 호출을 거부한다.

기존 RUNNING claim/owner/lease/취소·CLOSED·긴급 중단·원본 binding·만료·공유 admission 검사는 우회하지 않는다.
새 지원 호출은 원화 예약 행을 만들지 않으며, Usage STARTED와 관측·토큰·실패·재시작 정산은 계속 기록한다.
기존 원화 예약의 identity/금액/정산은 보존한다. 과거 예약의 실제 관측액 초과 시 중단 경로도 유지한다.
입력·횟수·동시성·시간·재시도·저장공간·무료 작업 별도 제한은 변경하지 않는다.
현재 Search 설정에 명시적 output/thinking 토큰 hard cap이 없다는 사실을 상한 보장으로 바꾸지 않는다.
운영의 모델·상한·support_ref·승인된 반복/동시성은 최종 policy/설정/이미지에 결속해야 한다.

이 수정은 schema/image 게시·운영 적용·실제 provider 호출·공개 개방을 실행하지 않는다.
새 MySQL supported_funding(usage/cancel_db/cancel_signal/restart)은 canonical → strict JSON/JUnit → 실제 보고서 변조의
필수 목록에 포함하며 로컬 미실행을 기존 CI 성공으로 대체하지 않는다.

2026-11-08 리뷰 후속의 일반/긴급 중단, 무료 원장, 새 PM 승인과 남은 gate는
[팀 리뷰 후속](a1-review-followup.md)을 따른다. 아래 미확정·head7 검증 기록은 당시 snapshot으로 보존한다.

상태: **로컬 서버 연결 구현 / 운영 미적용 / 공개 NO-GO**.
최신 PM 결정으로 공식 샘플 사용 범위와 KST 일20,000원·누적100,000원은 승인됐다.
서버 설치·정책 적용은 미실행이며 호출별 예약액·반복/동시성·실제 보호 경로 검증은 남아 있다.
기존 배포 smoke·장시간 팀 E2E를 A-1 공개 검증으로 대신하지 않는다.
Coarse 실행 예산은 600초 그대로이며, 공개 입력 합계 600초와는 다른 한도다.
26분 E2E·#583 추가 변경은 이 작업에 포함하지 않는다.

## 기존 구현과 검증 snapshot — 최신 변경은 위 후속 문서 우선

| 경계 | 구현 | 남은 확인 |
| --- | --- | --- |
| 공식 입력 | `official_samples`의 SHA/bytes/실제 영상 길이·합계 검증을 ID-only 등록에 연결. 등록 전 공유 preparation 한도, Case별 복사본과 등록·Case·binding 동일 transaction | 승인된 실제 샘플·이미지 FFmpeg 검증 |
| 임의 입력 | 공개 모드의 `/sources`를 body 수신 전에 403 거부. command는 서버 binding·Recording metadata·전체 길이 재확인 | 실제 외부 직접 API/프록시 검증 |
| 세션 | 서버 난수의 Secure/HttpOnly/SameSite=Strict `__Host-` cookie, 정확한 HTTPS Origin. Case 생성과 HMAC owner 동일 commit. 모든 Case method/media/Range 앞에서 owner 확인 | Case 담당 통합, 실제 브라우저 A/B |
| 반복·동시 | 프로세스 로컬 카운터 대신 MySQL control singleton current-read lock. session/IP 일일·Case 반복·session/전역 동시 admission과 enqueue 동일 transaction | 격리 MySQL8.4 동시성·장애 PASS. 실제 이미지/운영 한도 검증 |
| 비용 | 실제 Worker UsageSink.begin에서 현재 RUNNING claim/owner/lease/cancel 확인 후 invocation별 보수적 예약과 STARTED 동일 commit. API 차단만으로 대체하지 않음 | 실제 단가·최악 호출액·예산 승인 및 provider별 범위 |
| 긴급 중단 | DB accepting switch를 API와 매 attempt 직전에 확인. 이미 관측한 비용은 cancellation/중단 후에도 finish/finalize 보존 | 최종 이미지에서 운영자 stop/open/재개 검증 |
| 삭제 | owner DELETE/TTL → DELETING → 활성 job/미반영 결과/미확정 usage 확인 → 저장된 계획·공유 lease → 파일·청크·Case/produced 삭제 → DELETED. 실패하면 계획 유지·재시도 | 격리 MySQL 부분 실패·재시도 PASS. 이미지/실제 kill 복구 검증 |
| 임시 파일 | 양 서비스 공통 shared media의 `public-temp/a1-<DB token>` 사용. Recording·Search 변환에 같은 pinned temp context 전달 | 실제 컨테이너 mount/권한·크래시 잔여 검증 |
| 프록시 | Caddy의 API matcher에 `/public*` 추가 | live Caddy 변경·검증 NOT_RUN |

Runtime이 API adapter와 shared state를 소유한다. Case domain 및 Web 화면을 이 변경에서 수정하지 않는다.
`PublicAPI.ownership`은 같은 Connection에서 동작하는 교체 가능한 연결 경계다.
Case 담당은 기존 권한 구현을 연결할 경우 owner 확인·생성 atomicity·삭제·모든 media URL 범위를 유지한다.
localStorage Case ID는 권한이 아니다. 임의 X-Forwarded-For는 신뢰하지 않는다.
현재는 실제 ASGI peer를 HMAC 처리하므로 프록시 뒤 여러 사용자가 보수적으로 같은 IP 한도를 공유할 수 있다.

## 기본 설정과 승인 입력

`DAESINGO_RUNTIME_PUBLIC_MODE`의 기본값은 **a1**이다. 빠진 값이 일반 업로드/유료 분석 허용으로 이어지지 않는다.
기존 내부 전용 환경과 해당 회귀 fixture는 의도를 명시해 `internal`을 사용한다.
이 모드는 보호된 운영자 설정이며 공개 UI나 요청 header로 바꿀 수 없다.
공개 ingress를 열 때 API/Worker 모두 같은 a1 모드·정책·release identity를 사용해야 한다.

`DAESINGO_RUNTIME_PUBLIC_POLICY_FILE`은 보호된 로컬 파일이다. 누락·잘못된 값·SHA 불일치·
잘못된 소유/권한이면 분석을 거부한다. 신규 migration의 DB gate도 항상 CLOSED다.
승인값의 자동 기본값이나 과거 실험값 복사는 없다.

필수 policy 필드:

- approval_ref, release_revision(전체 source SHA), origin(정확한 HTTPS origin), session_key(32bytes 이상 비밀값).
- manifest_file/manifest_sha256/samples_root, max_input_bytes. manifest는 `official-samples/v1`이며 공개 목록에는 보호 경로/파일명/hash/권한 근거를 내리지 않는다.
- session_ttl_sec/case_ttl_sec(최대 7일), source_ttl_sec(최대 24시간).
- session_daily/ip_daily/case_repeats/session_concurrent/global_concurrent.
- case_budget_micros/daily_budget_micros/total_budget_micros: 양수 정수, **KRW의 1/1,000,000 단위**.
- bounds: operation/provider_label별 유일한 양수 reserve_micros와 evidence_ref. 실제 입력/출력/모델/가격/환율/자동 retry를 포함한 호출별 상한 근거를 release에 결속해야 한다. 코드의 fixed ceiling 설정만으로 실제 단가 상한이 입증됐다고 보지 않는다.

예약은 실제 시도마다 유지하고 실패·응답 유실·재시작을 이유로 환급하지 않는다.
복구로 FINALIZED된 usage라도 실제 observed_at이 없으면 동시 admission을 유지하고 DELETE/TTL도 BUSY로 거부한다. job 종료/복구만으로 이전 HTTP의 반환을 추정하지 않는다.
KST 일일 한도는 당일 생성/정산 및 이전 미정산 예약을 모두 포함한다. 누적·Case 상한도 유지한다.
실제 관측 금액이 예약을 초과하거나 정산 통화/값이 맞지 않으면 관측은 보존하고 gate를 닫는다.
미승인 단가/operation/provider나 미확정 승인액은 호출 거부다. 일 2만원/누적 10만원을 승인값으로 사용하지 않는다.

## HTTP 연결 계약

| 요청 | 내용 |
| --- | --- |
| GET /public/samples | sample_id/label/example_hint/합계 duration_ms·byte_size/file_count만 표시 |
| POST /public/session | 승인 Origin에서 server cookie 발급·기존 유효 세션 재사용. 알 수 없는 client token은 서버 난수로 교체 |
| POST /cases | cookie owner와 Case 동일 commit |
| POST /cases/{id}/official-samples | JSON `{"sample_id":"..."}`만 수락. 정확한 기존 binding 재사용은 새 hash/probe/copy·quota 소비 없음 |
| POST /cases/{id}/commands | 기존 Case command 형식, owner/source/admission 검증과 실제 발주 동일 commit |
| GET /cases/{id}/view 및 media/Range | 같은 owner 검증. 미소유와 없는 Case 모두 비노출 404 |
| DELETE /cases/{id} | owner만 요청. 완료 200/DELETED, 진행·재시도 202/DELETING. 팀 job을 임의 취소하지 않음 |

오류는 기존 envelope와 고정 code를 사용한다. public.input=422, public.upload_disabled=403,
public.origin=403, public.limit/concurrent/budget=429(Retry-After 포함),
public.unconfigured/stopped/unpriced/claim_lost=503, 미소유는 http.not_found=404다.
본문 수신은 빈 조각 반복으로 연장할 수 없는 전체 15초 상한과 기존 JSON byte 한도를 적용한다.
429/503에서 새 command나 유료 호출을 자동 재전송하지 않는다.

## 삭제와 보존

정상 분석이 저장하는 time_observation·prepared metadata·청크·frame·파생 descriptor도 계획에 포함한다.
다른 Case의 공유 연결과 소유 불명 source graph는 보존한다. unknown graph, metadata 상한 초과,
파일 hash/identity 불일치, 미만료 provider remote reference는 삭제 완료로 처리하지 않는다.
계획은 metadata 최대 10,000행/행 64KiB/전체 16MiB로 유한하게 조사하며 BLOB을 읽지 않는다.
실제 파일 hash는 1MiB씩 처리한다. 미지원/한도 초과 데이터는 DELETING에 남겨 수동 판단한다.

Case/source TTL 중 **먼저 만료되는 시점에 Case와 전용 결과 전체를 만료 처리**하는 보수적 정책이다.
CleanupService가 시작 시 및 최대 60초 간격으로 시도한다. 활성 job·reader·usage·잠금·장애 때문에
물리 삭제가 지연될 수 있으므로 운영 검증 전 UI에 삭제 완료/정시 삭제를 보장하지 않는다.
부분 파일 삭제 후 DB 실패, 부분 marker, 마지막 marker 제거 후 빈 directory도 재시도 검증 대상이다.

공식 canonical 파일, 다른 Case의 공유 데이터, 설정·인증정보·migration·기존 백업·검증 증거는 대상이 아니다.
UsageRecord 및 예약 원장은 보존한다. 삭제가 당일 quota를 초기화하지 않도록 당일 HMAC/영수증을 유지하고,
다음 KST 일자에 삭제된 Case의 security receipt·만료 세션만 정리한다.
코드 rollback은 이미 삭제된 데이터를 복구하지 않는다.

## 운영자 중단/복구 경계 — 실행 전

최종 검증된 이미지 안에서 기존 보호 env 파일과 image의 DAESINGO_REVISION을 사용한다.
아래는 실행 예시이며 이 작업에서 운영 DB에 실행하지 않았다. 공개 HTTP 제어 endpoint는 만들지 않는다.

```sh
python -m daesingo.api.public_control status --env-file "$DAESINGO_ENV_FILE"
python -m daesingo.api.public_control stop --env-file "$DAESINGO_ENV_FILE"
# 승인·정책·전체 샘플 hash/probe 검증 후에만 명시적 재개:
python -m daesingo.api.public_control open --env-file "$DAESINGO_ENV_FILE"
```

stop은 유효 policy 파일이 없어도 보호 env의 DB에 gate를 닫을 수 있다.
이미 시작한 provider 요청의 소급 취소/요금 취소를 뜻하지 않는다. 관측·미확정 예약은 보존한다.

이 변경은 runtime_0006 → **runtime_0007** forward-only schema를 추가한다. 신규 DB gate는 CLOSED다.
MySQL 8.4.13의 격리 schema에서 고정 bb29/b915가 만든 head6 → 현재 head7 전환 후
기존 job T1/T2·receipt·Case unknown key·Coarse600 보존과 두 old API의 live/ready200을 확인했다.
기존 API readiness는 DB SELECT1/storage를 확인하며 migration head를 검사하지 않는다.
반면 old migrator를 다시 실행하면 unknown head를 거부한다. 기동과 migration 재실행은 구분한다.

같은 head7 DB에서 **DB CLOSED여도 old API는 세션 없는 Case 읽기를 200으로 허용**했고,
현재 API는 404로 거부했다. 따라서 데이터 reader·readiness 통과를 A-1 공개 rollback 승인으로 쓰지 않는다.
기존 controller rollback은 migration을 실행하지 않고 최신 schema authority의 rollback_targets와
current/previous의 image·revision·config exact tuple을 검사한다. schema head만으로 old 기동 불가나
별도 중간 release 필수를 단정하지 않는다.

| 복구 상황 | 기존 기능으로 확인한 경로 | 실제 적용 전 필요한 증거 |
| --- | --- | --- |
| A-1 promotion 완료 뒤 프로세스 장애 | current의 같은 guarded exact tuple을 controller rollback으로 재기동. head7·gate·세션·비용/예약 원장 유지 | 실제 통합 SHA/image/config/approval, host 단계와 protected policy/sample mount 확인 |
| 초기 migration 완료 후 promotion 전 장애 | ingress 닫힘·drain을 독립 입증한 기존 current/previous로 controller rollback 가능 여부를 판정. old migrator 재실행·downgrade 금지 | bb29/b915의 공개 보호는 불충족. DB CLOSED만으로 대체 불가. Web뿐 아니라 직접 API·미디어 등 모든 공개 ingress 닫힘과 QUEUED/RUNNING/미반영 terminal/미관측 usage 부재가 입증되지 않으면 해당 target 승인 금지 |
| migration_pending 또는 promotion 중간 상태 | 기존 controller가 deploy/rollback을 거부. dirty·lock·schema/Web/state 증거를 보존하고 기존 reconcile 절차로 판정 | DB 완결성/부분 DDL과 pointer·record 대조. 임의 lock 삭제·stamp·허위 승인 금지 |
| 별도 수정 release로 전진 복구 | 같은 head7을 보존하는 새 guarded release를 기존 CI/publish/approval/controller로 적용 | schema_parent, 현재 revision 포함 rollback_targets, 실제 image 검증·최소 보호/복원 증거 |
| head6 데이터/schema로 복귀 | 별도 검증한 시점 일치 DB/media 복원 | 백업 이후 Case/비용·예약·권한 기록을 버리지 않는 복구 설계. 코드 rollback으로 삭제 데이터 복원 불가 |

실제 MySQL의 head7/권한/예약을 유지한 cold API 재기동과 기존 controller의 same-current rollback
state machine은 검증했다. host start/pull/Caddy/AWS는 test double이며 실제 이미지/운영 검증은 아니다.
운영 rollback tuple은 아직 승인하지 않았다. 공개 ingress를 닫는 실제 config와 외부 거부 검증도 NOT_RUN이다.
추가 중간 release는 지금 필수라고 판정하지 않으며, 위 조건을 충족하지 못할 때만 대안을 검토한다.

운영 적용 전 순서:

1. 통합 SHA push CI/canonical MySQL strict/실제 보고서 변조, image/Web/Caddy/config/policy/sample pin을 고정한다. 현재 preview 발주 OFF인 base 상태도 실제 이미지에서 판정하며 #583을 변경하지 않는다.
2. 승인 샘플/예산을 받고 팀 job·자원·dirty/lock을 재확인한다. retained data/원장/권한의 최소 보호·복원과 실제 복구 exact tuple을 검증해 controller approval에 결속한다.
3. 공개 ingress 닫힘·DB CLOSED 상태로 schema/이미지/설정을 적용하고, 두 외부 브라우저 및 다음 호출 중단·삭제까지 검수 후 명시적으로 연다.
4. 이상 시 ingress/다음 호출 gate부터 닫고 관측·원장·잠금 증거를 보존한다. drain 후 위 상태별 검증 경로로 복구한다. 활성 팀 job을 임의 취소하지 않는다.

실제 승인 샘플·예산·운영 복구 tuple이 없으므로 운영/공개 NO-GO다.
실제 유료 호출·publish·배포·운영 적용·외부 브라우저 완주는 NOT_RUN이다.

## 이전 단계 검증 기록과 미해결 회귀

| 검사 | 결과 | 한계 |
| --- | --- | --- |
| 최종 public API/core/temp/retention/planner + 기존 MediaRoot | 76 PASS | 명시적 합성 sample·시험 microKRW; SQLite serialization은 InnoDB 증거가 아님 |
| 기존 API 회귀 + frozen migration DDL/닫힌 seed | 181 PASS | 자식 Python도 현재 작업트리로 결속. 실제 MySQL·Caddy·이미지 실행 아님 |
| 추가 storage/프로세스/배포 runtime/고정 revision 회귀 | 247 PASS | 현재 작업트리의 자식 소스 명시, timeout/assertion 유지 |
| 승인 policy 로드·0 승인액/호출 상한 거부 | 5 PASS | 최종76개에 포함. 실제 예산 승인값 아님 |
| 관련 Worker/Usage/Search/Recording 회귀 | 355 PASS / 기존 실제 영상 1 SKIP / MySQL 194 deselected | 해당 opt-in 입력 미제공. 대용량 upload 두 실패를 이 결과로 지우지 않음 |
| strict checker 및 독립 필수 inventory 검사 | 9499 PASS | checker 자체 검사. canonical MySQL/실제 보고서 변조 실행을 대신하지 않음 |
| Runtime Ruff + mypy Linux/Windows + 모듈 경계 | PASS | 103개 Runtime source type 검사 |
| 독립 review | core/temp/planner41 PASS, 추가47 PASS 및 최종 삭제/admission2 PASS. 검토 범위 미해결 P1/P2 미발견 | reviewer의 API asyncio·실제 MySQL NOT_RUN; 작성자 API는 별도 실행 |
| canonical 실제 MySQL·실제 보고서 변조 | NOT_RUN | 로컬 격리 URL 없음, Docker 재구축 안 함. 원격 기존 CI에 필수4종/5개 테스트 추가 |
| 배포 이미지·외부 공식 샘플/유료 전체 완주 | NOT_RUN | 실제 승인 샘플/예산·통합 Web·운영 복구 검증 필요 |

추가한 mandatory MySQL은 admission 동시성·미관측 복구/Worker 예산/API atomic rollback/실제 물리 삭제의4종5개 테스트다.
기존 strict JSON/JUnit checker, 독립 inventory와 실제 보고서 누락/변조 검사에 모두 포함했다.
누락 skip·기준 완화·timeout 상향으로 대신하지 않는다.

이전 관련 전체 회귀 **576 PASS / 2 FAIL / 기존 SKIP 1 / MySQL 248 deselected**는 유지한다.

| 미해결 실패 | 확보한 근거 | 재검증 조건 |
| --- | --- | --- |
| upload disconnect에서 idle 관측 | 변경 없이 단독 후속 1 PASS. 최초 원인 미확정 | 같은 transport/타이밍 조건과 안전한 오류 분류를 포함한 기존 회귀. 단독 PASS로 원인 해결 주장 안 함 |
| 1GiB 경계에서 예상413 대신503 | 당시 실제 2파일 동시 구간 최소2,147,483,648B. 후속 여유2,088,656,896B로 최소보다58,826,752B 부족. 원문 OSError 미확보 | 두 파일 최소값 외 실행 예비공간까지 확보한 환경에서 기존 assertion 그대로 실행. ENOSPC 단정 안 함 |

이전 단계 당시 대용량 후속은 NOT_RUN이었다. 11/8 자원 확보 후 전후 대조 결과는 아래 후속 절에 기록한다. 전체 회귀 GREEN으로 표시하지 않는다.
공식 MP4 위장 ffconcat, 시간 metadata 누락, 임시 marker 재시도, Windows 경로 identity 문제는
각 회귀로 확인하고 수정했다. 원본·보호 자료나 기존 volume을 삭제하지 않았다.

## 담당 연결 근거

확인 시 [Web #606](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/606)은 open(bf609d76),
[Case #616](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/616)은 Draft/open(59184b20),
[Web #621](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/621)은 open(ec979594)이다.
#606의 동의/보관 UI, #616/#621의 초안·결과 변경은 해당 PR을 재사용하고 이 변경에 일괄 이식하지 않는다.
위 PR에서 세션 권한 구현은 확인하지 못했다. Runtime 연결 경계를 제공하고 Case 담당의 통합 리뷰를 받는다.
유민은 이 API의 샘플 선택·cookie·고정 오류/삭제 대기 상태를 연결하고,
샘플 담당은 공개/외부 AI 전송/재배포 권한과 hash/길이/보호 manifest를 확정해야 한다.

추가 회귀의 최초244 PASS/3 FAIL도 보존한다. Worker fake engine2개는 새 필수 tagging 조회에 맞춰 SQLite fixture로 보완했다. 기존 종료 검사1개는 최초·단독에서5초 timeout이었다. 로컬 venv 자식이 원래 저장소를 읽는 것을 확인한 뒤 현재 source 경로를 명시하자 후속3개 및 전체247개가 같은 assertion/5초 제한으로 통과했다. 최초 timeout의 정확한 원인은 미확정이며 이 결과로 기존 upload 실패2건을 해결했다고 주장하지 않는다.

## 2026-11-08 실제 MySQL 통합 후속

로컬 기존 cached MySQL8.4.13 이미지의 전용 격리 container/schema를 사용했다. 새 이미지 build/pull·
기존 volume mount·운영 DB/provider 접근은 하지 않았다. Windows의 기존 MySQL8.0 서비스는 사용/변경하지 않았다.
DB memory1GiB/데이터 tmpfs640MiB, 잠금 의존성 Python3.12/uv0.11.15와 hash 결속 RAM source에서 검사한다.
RAM/tmpfs 크기와 자원 polling은 유한한 trial 중단 한도이며 서비스 전체의 peak 안전 보장이 아니다.

- 실제 MySQL focused19 PASS + 예약/취소 단위4 PASS. 동일 DB의 동시 admission/반복·실제 API Case 생성 quota·두 Worker 예산 race,
  enqueue 원자성, 미관측 복구 slot 보존, paid 경계 취소, 관측 후 취소·새 Worker 재시작 후 비용/예약 보존,
  실재 frame/download/Range 요청의 다른 session 거부, 삭제 hash/DB 부분 실패 재시도, 완료 재시도 및 head7 복구 포함.
- 실제 DB에서 singleton CHECK(id=1)와 AUTO_INCREMENT가 충돌한 MySQL3818을 재현했다. frozen/live DDL 모두 autoincrement=False로 수정했다.
- paid 경계 취소가 FAILED/persistence 오류로 바뀌는 실제 Worker 실패를 재현하고 CANCELLED로 전파했다. 실제 HTTP 대신 명시적 시험 handler만 사용했다.
- 독립 리뷰 P2(완료 DELETE 응답 유실 후 재시도404)는 실제 DB RED→GREEN. 유효 owner의 DELETE만 DELETED 허용,
  일반 read·다른 session·만료 권한 거부 유지. 정적 재리뷰에서 추가 P1/P2 미발견.
- 관련 최종 회귀9741 PASS / MySQL210 deselected, Runtime Ruff와 mypy Linux/Windows 각103 source PASS, 모듈/계약 경계0 PASS.
- canonical 전체는 기존 `tests.ci_orchestration mysql`을 그대로 실행했다. 1333개 선택 후 host Windows 가용625,332,224~642,871,296B로
  예비1GiB를 충족하지 못해 **INCOMPLETE_RESOURCE**로 중단했다. SIGINT가 종료로 이어지지 않아 명령/evidence identity를 재확인한
  소유 pytest에 SIGTERM을 보냈다. 뒤의 strict JSON/JUnit·실제 보고서 변조 단계는 **NOT_RUN**이다. 부분 로그를 전체 gate 통과로 쓰지 않는다.
  앞선 별도 실행은 리뷰 수정 반영으로 중단했고 이 역시 최종 증거가 아니다.
- 보고서/로그23개 3,401,668B를 Windows 보존본으로 이동하고 개별 길이/SHA256을 대조했다. 소유 RAM tmpfs와 전용 DB container/network만 정리했다.
  소유 Docker Desktop은 container0 확인 후 정상 종료했고 기존 volume/image·Windows MySQL80·원본·보호 증거는 보존한다.
- 동일 test hash로 base5004의 disconnect FAIL(idle) / 현재 PASS. 기존 소스에서도 재현되므로 신규 A-1 회귀 근거는 없지만
  최초 실패의 정확한 scheduling/I/O 원인은 미확정이다. assertion/.04초 제한을 변경하지 않았다.
- 1GiB 기존 경계는 처음 C 여유1,566,425,088B라 실행하지 않았다. 소유 Docker/RAM 자원 반환 후 C 여유4,062,965,760B로
  두 파일 최소2,147,483,648B + 예비1,073,741,824B를 충족해 원래 두 parameter를 실행했다.
  동일 test hash의 base5004 **2 PASS** / 현재 **2 PASS**. 최초503 원인은 여전히 미확정이며 ENOSPC로 확정하지 않는다.
  이번 자원 충족 후속에서는 재현되지 않았고 A-1 신규 회귀 근거는 없다. 기존 assertion/skip/timeout을 완화하지 않았다.

기존 위 표의 76/181/247/355/9499 및 NOT_RUN은 이전 단계 기록이다. 이번 실제 DB 결과와 혼합해 합산하지 않는다.

### PR와 공개 적용 판정

Draft PR 자료는 준비할 수 있지만 **병합 gate 완료/운영·공개 준비 완료는 아니다**.
남은 필수 검증은 자원 확보 환경에서 원래 canonical 전체→strict→실제 보고서 변조다. 기존1GiB 경계는 전후 각2 PASS로 후속을 마쳤다.
실제 배포 image·host recovery/closed ingress·retained DB/media backup/restore·외부 브라우저·유료 호출은 NOT_RUN이다.
공식 샘플/실제 예산 미승인은 운영 분석 거부 상태로 유지한다. 과거 장시간 E2E나 기존 배포 성공으로 이를 대체하지 않는다.
