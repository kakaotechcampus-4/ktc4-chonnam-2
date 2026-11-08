# #629 팀 리뷰 후속 — 일반 중단·긴급 중단·무료 결과 작업

기준 HEAD `b3ce9cde93c878f524aec0aa4073b092c08c90b9`. 아래는 로컬 미커밋 변경이며
기존 b3ce CI 성공을 수정본의 성공으로 쓰지 않는다. Coarse600초 유지,26분 E2E 제외.
운영 적용·게시·실제 유료 호출은 하지 않았다.

## P2 수정 결과 — 최신 판정 (2026-11-08 KST)

아래 이전 제출 점검의 P2 미해결 판정은 당시 기록이다. 이번에는 사용자 지시로 최소 수정까지 수행했다.
기존 완료 settle/관측 뒤 자동 export만 후보 aggregate에서 만들고, admission 거부 시 그 후보만 폐기한다.
Case processed_executions와 Runtime 완료 표식은 commit되므로 상한2의 기존 terminal2가 무한 재전달되지 않는다.
Worker direct/replay는 같은 port/SAVEPOINT를 사용하며 수락한 자동 job은 최종 admission에서 이중 차감하지 않는다.
Fine/clip/HINT의 필수 후속 차단은 그대로다. 기존 T1/산출물/비용/예약·기존 export input을 삭제하지 않는다.
실패·긴급 중단은 신규 무료 export를 발주하지 않지만 기존 완료 정산은 보존한다.

재개 후 사용자는 현재 export request로 기존 GENERATE_REPORT_VIDEO action을 명시 실행할 수 있다.
최초 자동 발주가 보류된 경우도 실행 중 export가 없고 현재 request가 있으면 버튼 근거가 있다.
새 명시 export(첫 발주/같은 입력 재시도)는 case_rev를 한 번 올려 payload identity를 구분한다.
동일 payload 재전송은 stale/발주0, 실패 후 새 revision 요청은 별도 admission이다. force_rerun은 바꾸지 않았다.
Case command·append-only 결정·T2 결정·CaseView notice의 공용 계약4문서를 실제로 갱신했다.

상한2/누계/긴급 중단3개를 실제 Case+SQL/공개 counter로 RED(LOCAL_CONCURRENT/LOCAL_LIMIT/JOBS_STOPPED)→GREEN으로
확인했다. 실제 command/PublicAPI.admit_result를 쓰는 명시 재시도 identity도 RED2(INPUT)→GREEN으로 확인했다.
완료2개·old input·예약10micros·보호된 시험 파일 hash 보존, 이전 terminal 반복 ALREADY_APPLIED,
동일 payload stale/추가enqueue0, 실패 후 두 번째 명시 재시도 및 mixed 필수 후속 차단을 검사했다.
SQLite의 clock/queue 부분은 fixture이고 evidence/Package도 시험값이다. 실제 영상/다운로드 HTTP 검증으로 확대하지 않는다.
관련 회귀 **202PASS**, Ruff·mypy Linux/Windows·경계 PASS. strict checker 새3개×7누락 층과 완전 보고서 단위22PASS.
독립 최종 소스 리뷰에서 잔존 P1/P2 미발견. reviewer의 실제 테스트/DB 실행은 없었다.

같은3개 실제 Case/Runtime T2/enqueue/표식을 쓰는 MySQL 시험을 추가해 canonical/strict/실제 보고서 변조 목록에
연결했다. 기존7개+새3개=10개. 실제 MySQL/canonical 전체/strict/실제 보고서 변조/새 CI는 NOT_RUN이다.
로컬 Available3742310400B/C free9989259264B였고, 이전 기동 감소 관측 약3.15GB+reserve1GiB를 확보하지 못해
Docker/MySQL을 시작하지 않았다. 기존 volume/보호 원본/운영 상태에 접근하지 않았다.
#616 최신59184b20 확인, Case/계약/시험 patch --check PASS. 실제 merge/합본 실행은 NOT_RUN이다.

**추가 사용자 지시: Elice 원화 단가/예약액 조사는 보류. P2 검증·CI 제출의 차단 사유가 아니다.**
지원받는 사용을 공급자의 무제한 보장으로 해석하지 않는다. 일2만원/누적10만원의 실제 코드 처리 방식은 별도
미결 결정이다. 기존 비용 보호/원장과 동시·반복·timeout·저장공간·긴급 중단 제한을 임의로 해제하지 않았다.
이하 가격 계산/요청 목록은 보류 전 조사 기록이며 새 조사·운영값 적용을 하지 않았다.
commit/push/댓글/운영 적용/provider 호출은 하지 않았다. 이전 CI는 이전 SHA 근거로 보존한다.

## 이전 제출 전 점검 snapshot — 위 P2 수정 결과보다 우선하지 않음

2026-11-08 KST, 같은46개 파일을 재점검했다. 분류는 제품13·Web7·migration1·시험21·gate1·문서3이다.
임시자료/보호 원본/빈 cleanup lock3개는 제출 목록에서 제외한다. 운영 설정·새 호출별 금액은 넣지 않았다.
이번 점검에서 제품 동작을 추가 확장하지 않았으며 Web의 과도한 자동 재생성 부정 문구2개와 해당 시험만 보완했다.

**P2 미해결: 완료 결과 반영과 추가 자동 export가 동시 상한으로 순환 대기할 수 있다.**
기존 report+plate batch2가 active이고 무료 동시 상한2인 동안 시각 정정을 저장하면 새 report는 보류된다.
기존 terminal의 Case reflection도 현재 정정값으로 새 export를 자동 발주한다. wrapper가 active2+신규1을
거부하면 기존 terminal T2도 rollback한다. refresh_active는 그 terminal의 case_applied_at=NULL을 busy로
보므로 재전달해도 active2가 해제되지 않는다. Case당 누계 소진도 같은 완료 반영 결합 위험이 있다.
이는 단순히 stop을 해제하면 진행되는 상태와 다르며, 상한 인상으로 제품 결함을 덮지 않는다.

동일한 실제 PublicStore/Wrapper를 쓰고 reflector만 시험용으로 대체한 제한된 SQLite 진단에서
3회 모두 LOCAL_CONCURRENT, 이전 terminal2 미반영, active job_count2, 저장된 T2 효과0을 확인했다.
실제 Case+MySQL 재현은 NOT_RUN이다. 이 진단을 실제 DB나 해결 검증으로 표현하지 않는다.
앞선 “잔존 P1/P2 미발견”은 이전 검토 범위의 기록이며 현재 판정은 **잔존 P2 있음/병합 차단**이다.

필요한 최소 후속은 T2의 완료 정산과 그 뒤 추가 자동 export 발주도 command처럼 분리하는 것이다.
완료 정산 뒤 snapshot을 잡고 무료 자동 export만 거부 시 복원하되 guarded 필수 후속의 차단은 유지한다.
기존 batch2/상한2/시각 정정/두 terminal 재전달, 기존 export input·SUPERSEDED 보존,
명시 job+자동 export의 거부 원자성 시험이 필요하다. 이번 제출 준비에서 이 제품 변경은 실행하지 않았다.

command의 현재 snapshot은 handler 뒤/자동 export 앞이므로 정정·case_rev·명시 job은 보존한다.
HTTP command와 CaseView 필드를 추가하지는 않지만 **성공한 정정과 자동 발주 보류를 분리하는 의미 변화**다.
Case command §5·§6 및 command-appended-job-records 결정에 분리 규칙을, CaseView B§7에
public.local_work_not_queued의 Runtime 생산·발동/해제·message key를 등재해야 한다.
Runtime 설명만으로 공용 계약 개정을 완료했다고 보지 않는다. 소연에게 전달할 정확한 개정 초안은 준비했으나
Case 소유 문서나 #616의 report_draft/v1.13을 이번46개에 임의로 이식하지 않았다.

“자동으로 다시 만들지 않아요”는 Worker 후속 발주까지 없다는 약속으로 읽힐 수 있어 제거했다.
이번 요청에서 영상 생성이 시작되지 않았다는 사실만 안내한다. 브라우저가 자동 POST하지 않는 검사는 유지한다.
수정 후 관련 Web2파일20PASS. 앞선 Web 전체373PASS/build PASS는 문구 수정 전 로컬 snapshot 기록이며
이번 수정 후 전체 반복은 NOT_RUN이다. 서버 제품 코드는 이전130PASS 이후 변경하지 않았다.

### 최신 PR 대조

원격 head는 아래 기존 표와 같다. 각각의 PR patch를 현재 작업 트리에 적용하지 않고 --check로만 대조했다.

| PR | 이번46개와 같은 파일 | 실제 check 결과/남은 접점 |
| --- | --- | --- |
| #616 | 없음 | Case 소스·Case 시험·e2e_runtime·공용 계약 subset check PASS. 전체는 Case decisions/README.md 문맥 불일치. #618 포함 조건/report_draft 의미와 위 보류 계약 통합 필요 |
| #606 | ApiFlow/labels2개 | 텍스트 patch check PASS. consent JPG는 patch 미제공이라 제외. 실제 consent/보관 문구 합본 시험은 NOT_RUN |
| #621 | ApiFlow/labels2개 | 텍스트 patch check PASS. onReviewed/CORRECTED와 새 notice를 모두 유지해야 함. 실제 합본은 NOT_RUN |
| #628 | 없음 | GitHub mergeable=false, 현재 vite.config.ts proxy 문맥에서 check 실패. 기존 /public proxy를 보존하며 build input을 결합해야 함. 이번46개가 새로 만든 충돌로 단정하지 않음 |

이것은 각각의 기계적 check이며 네 PR을 차례로 합친 결과나 통합 실행 성공이 아니다. checkout/merge는 하지 않았다.

### 호출별 예약액 산정 정산

소스 기본 모델은 Intent gemini-3.8-flash, Coarse/Fine gemini-4-argon이다. 운영 protected env의 현재 override는
이번에 조회하지 않았고 로컬 두 .env 위치도 없었다. 기본값을 현재 운영 설정처럼 단정하지 않는다.
요청 상한은 media40MiB/request56MiB이며 출력/사고 token cap은 보내지 않는다. reasoning_effort=low는
Coarse/Fine에만 전달하며 Intent는 생략한다. byte 제한·JSON schema·약2000토큰 잘림에 대한 과거 주석·
Coarse600초/client timeout은 과금 토큰 hard cap의 증거가 아니다. pricing placeholder/0.0도 무료라는 뜻이 아니다.

[Elice 공식 요금표](https://elice.io/ko/cloud/pricing/ai-cloud)는 Serverless 사용량 과금과 Dedicated 시간 과금을
구분하지만 조회한 표에 이 두 Gemini의 endpoint 계약 단가는 없다. 다른 Gemini 모델의 Elice 모델 페이지를
이 endpoint의 과금 근거로 대체하지 않는다. 아래는 Google 직접 서비스의 **조건부 USD 참고 계산**이다.

| 모델 | 공식 가격/한도 근거 | 계산 결과: 수수료·세금·환율 제외 |
| --- | --- | --- |
| Argon | [Google 공지](https://cloud.google.com/blog/products/ai-machine-learning/gemini-4-argon-available-on-google-cloud): 2026-11-30까지 입력2/출력10 USD/1M. [개발자 가이드](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-4-argon): 입력+사고+출력 통합1048576 | 단일 통합 한도를 모두 비싼 출력으로 평가한 보수적 상계10.485760USD/시도,4시도41.943040USD. non-streaming 기본32768을 proxy에도 적용된 cap으로 사용하지 않음 |
| Flash3.8 | [Google 안내](https://ai.google.dev/gemini-api/docs/latest-model?authuser=0): 2026-12-31까지 입력0.75/출력3.75 USD/1M. [모델 명세](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash?authuser=3): 입력1048576/출력65536 | 두 한도를 각각 가득 평가하면1.032192USD/시도,4시도4.128768USD. 사고가 출력 한도/단가에 포함되는 endpoint 계약 대조 필요 |

직접 계산식은 Argon `1048576×10/1000000`, Flash `(1048576×0.75+65536×3.75)/1000000`이다.
Google direct 요금의 유효기간 이후에는 두 가격이 각각2배가 되는 공식 안내가 있으므로 고정값의 만료도 필요하다.
이 수치는 **현재 Elice 호출 예약액이나 공개 정책의 승인값이 아니다.** 실제 예약 KRW는 NOT_PROVEN이다.

SDK 자체 retry0, 제품 retry3이므로 provider의 한 _call 안에서는 최대4회 시도하며 매번 UsageSink.begin으로
별도 예약한다. 요청별4시도 상계를 예약1건으로 넣으면 매번4배로 중복 예약하므로 시도/요청 단위를 구분한다.
Worker STALE 재시도(코드 기본1)와 새 analysis run의 호출은 별도이며 전체 Case 호출 수를4회로 단정하지 않는다.
실패·timeout·미관측 비용을 임의 환급하지 않고 기존 원장으로 계속 차감한다.

운영 전 필요한 입력은 다음으로 좁힌다. 추가 유료 호출은 요구하지 않는다.

1. 실제 운영의 비밀값을 제외한 모델/설정 identity와 각 Elice endpoint의 Serverless/Dedicated 계약,
   모델 alias 대응·입력/출력/사고 과금 단위·프로모션 종료·통화·세금·추가 수수료 근거.
2. proxy가 실제 보장하는 입력·출력+사고 합계 hard cap과 지원 parameter. 현재 제품은 출력 cap을 전달하지 않으므로
   더 작은 예약액을 쓰려면 명시적 cap 연결·요청 검증이 추가로 필요하다. low/timeout/25%는 대체물이 아니다.
3. USD 청구면 승인 환율 상한·반올림·유효기간, KRW 청구면 해당 계약 단가. 캐시 할인·무료 credit은 안전 상한에서 제외.
4. operation/provider_label별 단일 시도 reserve와 evidence_ref 승인. KST일2만원/누적10만원만 확정이며
   Case5천원·횟수·동시성·25% 여유 권고는 전부 미승인이다. 기존 예약·지출 원장과 공개 기간 집계를 초기화하지 않는다.

### CI 제출 조건

로컬 Available3392491520B/C free10314670080B였다. 이전 Docker+MySQL 시작 감소 관측 약3.15GB와
reserve1GiB를 함께 확보하지 못해 시작하지 않았다. 전체 검사/Docker 재구축은 반복하지 않았다.
기존 workflow는 MySQL8.4, REQUIRE_MYSQL=1, 고정revision commit/tree 확인 후 canonical 전체→strict JSON/JUnit→
그 실제 보고서의 변조 검사를 순서대로 실행한다. 새7개는 local canonical1340 목록에 각각1회 있다.
새 제출 SHA의 실제 MySQL/canonical/strict/실제 보고서 변조/통합CI는 NOT_RUN이다.
기존 b3ce CI 성공·Windows symlink AUTH_REQUIRED 이력은 이전 기록으로 보존한다.
현재7개는 위 P2 회귀를 검증하지 않는다. Draft 자료는 준비하되 P2 수정/회귀와 Case 계약 등록 전 병합 준비 완료가 아니다.

## 원문과 원인

[소연 리뷰](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/629#issuecomment-6717384736)의 지적처럼
command 전 일괄 accepting/source 검사가 job 없는 검토까지 막았고, appended job 전부가 탐색 반복 원장을 썼다.
[유민 리뷰](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/629#issuecomment-6717489877)의 지적처럼
NO-GO 중 기본 `/`가 샘플 API를 조회했고 busy/origin/CLOSED 안내와 준비 전 보관·한도 안내가 부족했다.
원문과 PR별 고정 head/파일 목록은 보호된 로컬 검토 자료에 보존한다.

## command 이름 대신 실제 효과로 판정

| 실제 결과/handler | 처리 |
| --- | --- |
| 새 job 없음 | owner·세션·Case 만료를 확인하고 검토/저장 허용. 새 Case/세션 생성·샘플 등록을 열어 주는 것은 아님 |
| REPORT_VIDEO_EXPORT / PLATE_IMAGE_EXPORT / CANDIDATE_VIDEO_PREVIEW | 현재 handler는 로컬 Recording 작업으로 provider/UsageSink.begin을 호출하지 않음. 실제 job 수를 별도 무료 원장으로 제한 |
| HINT_EXTRACT / COARSE_SEARCH / FINE_VERIFY | 기존 분석 admission과 provider 시도 전 UsageSink 예약 적용 |
| INCIDENT_CLIP_BUILD | 자체는 로컬이지만 판독 후속이 있으므로 일괄 면제하지 않음 |
| PLATE_READ / OVERLAY_TIME_READ | 현재 ocr-local/보고 cost0이나 UsageSink 예약 경로를 사용. 유료라고 단정하지 않으며 이번 무예약 면제에는 넣지 않음 |
| 혼합/미등록 kind | 무료로 추측하지 않고 guarded 경로 유지. 실제 provider 호출은 승인 bound·예약 필수 |

| 상태 | 신규 분석 | 새 무료 결과 job | 조회·기존 파일 다운로드·job 없는 검토/저장 |
| --- | --- | --- | --- |
| open | 분석 한도·예산 검사 | 별도 승인 상한 검사 | owner/만료 검사 후 허용 |
| pause-analysis | public.stopped로 거부 | 별도 상한 안에서 허용 | 같은 조건으로 허용 |
| stop / 긴급 중단 | public.jobs_stopped로 거부 | public.jobs_stopped로 거부 | 같은 조건으로 허용 |
| 무료 상한 미설정 | 기존 분석 조건 | public.local_unconfigured로 거부 | 같은 조건으로 허용 |
| 정책·인증 입력 자체 미설정 | 거부 | 거부 | owner 확인도 성립하지 않으므로 우회 허용하지 않음 |

`pause-analysis`는 긴급 중단을 해제하지 않는다. `open`은 기존 보호 policy/catalog 검증 후에만 연다.
공개 HTTP 해제 endpoint나 브라우저 override는 없다. 이미 진행 중인 작업·발생한 요금을 강제로 취소하지 않는다.

## 정정 저장과 발주, 직접 반영과 재전달

Case command에 작은 `admit_auto_exports` port를 추가했다. 허용된 정정/검토 뒤 자동 export만 거부되면
정정은 저장하고 자동 export aggregate 효과만 복원한다. Runtime SAVEPOINT는 거부된 admission을 되돌린다.
명시적인 새 분석·새 export 요청의 거부는 기존처럼 transaction을 롤백한다.
성공 응답과 재조회에는 기존 notices로 `public.local_work_not_queued`를 투영한다.
“수정 내용 저장됨 / 이번 요청의 영상 미발주”를 구분하고 queued·READY로 꾸미지 않는다.
브라우저 자동 POST는 없지만 기존 Worker의 후속 발주 가능성까지 부정하지 않는다.
notice는 저장된 Case revision과 일치할 때만 보이며 local admission 성공 시 제거된다.

직접 T2와 startup/periodic redelivery는 **같은 PublicResultReflector**를 사용한다. HINT exhaustion의
COARSE 후속도 PublicExhaustionReceiver로 검사한다. 결과/실패 재전달 모두 첫 RR 읽기 전에 control lock을 잡는다. 새 child가 거부되면
Case T2·receipt·enqueue를 함께 rollback한다. 완료된 T1/produced/비용은 보존하며 job 없는 T2는 반영한다.
후속이 필요한 terminal은 case_applied_at=NULL로 남을 수 있다. 중단 해제·한도 설정 뒤 기존 redelivery로
진행해야 하며 이 상태를 완료/drain0으로 보고하지 않는다. 재전달의 control lock은 첫 RR 읽기보다 먼저 잡는다.

## schema·원장·복구

frozen runtime_0007은 보존한다. runtime_0008은 jobs_stopped,local_work_state,public_local_admission을 추가하고
accepting=False/jobs_stopped=True로 시작한다. 기존 예약·지출 원장은 초기화하지 않는다.
무료 한도는 job_count 합계다. 두 export batch는2개이며 동일 request/job 재전달은1회 차감한다.
Case 누계·IP/KST 일일 job 합계·무료 동시 job·기존 공유 admission/준비 상한을 모두 검사한다.
부모 분석과 자식 무료 작업의 공유 슬롯은 중복 청구하지 않는다. 당일 quota 영수증은 삭제 후에도 보존한다.
새 head8에 맞춘 기존 시험의 head/table 기대값을 명시적으로 갱신했고 assertion/timeout/skip 기준은 완화하지 않았다.

forward-only다. head/readiness만으로 b3ce/bb29/b915를 rollback 승인하지 않는다. 실제 image/host 복구 tuple은
미검증이다. 운영 전 새 통합 SHA의 CI/image/config/mount·보존 데이터 보호와 복구 경로를 확인해야 한다.
이번 작업은 운영 적용 승인이 아니다.

복구 준비는 새 통합 이미지와 head8을 유지하는 경로로 한정한다. 긴급 시 동일 이미지의 기존 운영자
`public_control stop --env-file <보호 env>`로 모든 신규 job을 닫고 owner/만료가 유효한 읽기는 유지한다.
일반 `pause-analysis`로 대체하거나 운영자의 기존 승인 없이 `open`을 실행하지 않는다.
이미 발생한 T1/산출물/예약·지출을 지우지 않고, 재기동 후 gate 상태·미반영 결과·outbox를 확인한다.
재개는 원인/상한/정책 tuple이 확인된 뒤 같은 보호 catalog 검증과 기존 redelivery 경로로 한다.
head8 rollback/downgrade를 시도하지 않는다. DB 복원이 필요하면 별도로 검증된 일관 백업을 빈 격리 target에
복원·대조하고 해당 데이터 시점과 공개 권한을 모두 지키는 source/image를 결속해야 한다.
head8의 실제 이미지·host 재기동/격리 복원은 이번에 NOT_RUN이며, 과거 head7의 로컬 guarded-current
검증으로 대신하지 않는다. bb29/b915는 세션 권한 우회 때문에 공개 rollback 대상으로 부적합하다.

## 이번 PM 승인과 미확정 값

2026-11-08 KST 이 chat에서 공식1min10개(600000ms/244829133B)의 공개 체험·외부AI분석·결과다운로드 사용을
승인받았다. 상위 README/manifest의 local-only 기록은 수정하지 않고 새 승인 기록으로 구분한다.
원천 라이선스 독립 감사까지 실행한 것으로 표현하지 않는다. 기존 PENDING과 원본은 보존하고 승인 ref가 있는
새 로컬 manifest를 준비했다. 서버 설치·등록은 NOT_RUN이다.

확정 예산은 **KST 일20000KRW/공개 운영 기간 누적100000KRW**다. policy 단위는 각각
20000000000/100000000000micros다. 기존 public_reservation의 지출·미확정 예약을 포함하며 집계 기간을 재설정하지 않는다.
이번에 운영 DB의 원장 합계나 이전 UsageRecord와의 결속을 조회하지 않았다. 공개 기간의 실제 기존 지출·예약이
예산 차감에 빠짐없이 포함되는지는 운영 적용 전 대조해야 한다. 원장 초기화나 임의 환급으로 맞추지 않는다.

아래는 **승인값이 아닌 권고안**이며 실제 image의 RAM/CPU peak·처리량 보장이 아니다.

| 미정 항목 | 권고 | 근거/한계 |
| --- | --- | --- |
| Case 예산 | 5000KRW | 승인 일 예산의1/4로 구획. 하루4건 성공이나 실제 비용을 보장하지 않음 |
| guarded 반복 | 최초1+case_repeats2 | 최초 Fine 뒤 Top-3의 다른 두 후보 확인 여지. 설명 변경/다시 찾기도 소비 |
| 세션 일일 Case | session_daily1 | 새 Case로 반복 상한 우회를 제한 |
| IP 일일 admission | ip_daily10 | 신규 세션·준비·분석의 기존 각 제한. proxy peer 공유 시 여러 사용자가 함께 차단될 수 있음 |
| 공유 session/global admission | 각각1 | 보수적인 단일 체험 슬롯. 같은 Case의 부모/자식 공유. 실제 Worker 수·자원 peak 재확인 필요 |
| 무료 Case 누계 | local_work.case_jobs12 | 최초 export2+Top-3 preview3+정정3회×export최대2=11개,1개 여유 |
| 무료 IP 일일 job | local_work.ip_daily_jobs40 | 유한한 공개 trial 제안. 부하 측정 후 승인 필요 |
| 무료 전역 동시 job | local_work.global_concurrent2 | export batch2개 허용. queued/running/미반영/미관측이 남으면 보수적으로 유지 |
| 호출별 예약액 | 숫자 확정 보류 | 실제 요금·환율·입출력 hard cap이 없어 검증 가능한 KRW 상한을 현재 도출할 수 없음 |

호출별 권고 산식은 `ceil((입력토큰상한×입력단가+출력·사고토큰상한×출력단가+proxy요금)×승인환율×1.25)`KRW다.
이 산식의 단가는 토큰당 USD로 정규화한다(USD/100만 토큰 요금이면1,000,000으로 나눔).
proxy 요금도 같은 통화로 맞추고 환율은 KRW/USD를 사용한다. 실제 과금 통화가 다르면 해당 단위로 다시 결속한다.
25%는 여유율 제안이며 미확인 단가나 토큰 상한의 대체물이 아니다. HTTP retry마다 별도 예약하고
미관측 비용은 임의 환급하지 않는다. Intent/Coarse/Fine별 산식과 evidence_ref 승인이 필요하다.
코드는 Search gemini-4-argon/Intent 기본 gemini-3.8-flash이며 pricing은 elice-unpriced-placeholder다.
요청에 output token hard cap이 지정되지 않는다. [Google 공식 요금표](https://cloud.google.com/model-garden/pricing?hl=ko)를
현재 Elice tenant의 실제 단가로 대체하지 않는다. 실제 단가·환율·input/output(사고 포함) hard cap·retry 경계
증명 전에는 그럴듯한 예약액으로 policy를 열지 않는다. 샘플과 일/누적 예산 승인은 이 미정값의 승인과 별개다.

## PR 통합과 Web

| PR / 조회 head / 상태 | 영향 |
| --- | --- |
| #616 /59184b20/open Draft | service/exports의 evidence 조립 후 자동 export 조건. 이번 command port는 함수를 그대로 호출하고 조건을 복제하지 않음. 기존 e2e MySQL2파일 변경과 다른 hunk, 실제 통합 CI 필요 |
| #606 /bf609d76/open | ApiFlow UploadScreen consent/failReason·labels·CSS. 이번 notice banner/오류 key는 별도 접점. labels 주변 삽입은 양쪽 유지 필요 |
| #621 /ec979594/open | ApiFlow 결과 props/client/caseView/labels. MARK_REVIEWED/CORRECTED 뒤 actual jobs에도 같은 admission 적용. #616/#618과 실제 초안→생성→다운로드 통합 필요 |
| #628 /5946b324/open | vite build input/선택형 게임. /public proxy와 역할이 다르며 이번에 vite/game 추가 수정 없음. 최종 합본 build 확인 필요 |

`/`·`?case`·`?api`는 기존 ApiFlow, 샘플은 `?sample`·`?sample&case=...`로 명시한다. 서버 보호는 유지한다.
busy409/origin403/분석중단503/긴급중단503/설정미완503/예산·횟수·무료상한429를 구분하고 Case 문구를 체험으로 바꿨다.
샘플 준비 전에10분 한도와 보관/반복 미확정 안내를 둔다. #606 파일선택 후 동의 모달을 샘플에 복제하지 않고
미승인24시간/7일 숫자도 붙이지 않는다. 실제 TTL·개인정보/외부AI 승인 문구는 #606 담당과 통합해야 한다.
AppHeader/오류·삭제 영역의 최종 배치는 대원 확인 대상으로 남긴다. 실제 merge·합본 외부 완주는 NOT_RUN이다.

## 검증과 남은 gate

로그는 `.codex-scratch/a1-review-followup-20261108/`에 보존한다. Web RED10→관련21PASS,
미발주 표시 RED1→관련8PASS, 서버 경계 RED9→9PASS를 확인했다. 후속 non-MySQL117PASS,
API 저장/notice·권한/원장 보존12PASS를 별도 확인했다. 묶음은 겹칠 수 있어 합산하지 않는다.
같은 새 SQLite fixture/callback에 고정 b3ce Worker 배선만 연결한 비교에서는 중단 guard4FAIL/2PASS,
수정 배선의 직접/재전달 공통 경계는6PASS다. 전체 base 제품/실제 MySQL 비교로 확대하지 않는다.

최종 소스의 non-MySQL/SQLite 관련 시험은 서로 겹치지 않는74+56=130PASS다.
Web 전체25파일373PASS, Web build PASS, Ruff/mypy Linux·Windows(106 source)/경계 검사 PASS다.
Web 재검증 첫 시도는 임시 변환 파일 ENOENT로19파일이 수집에 실패했다(45개 시험 PASS).
같은 시험을 접근 가능한 환경에서 다시 실행해373PASS를 확인했다. 로컬 서버 시험의 제한된 환경 첫 시도도
멈춰 중단했으며 접근 가능한 환경의 결과를 따로 보존했다. assertion·timeout·skip은 변경하지 않았다.

실제 MySQL7개(무료 경쟁3, 직접/재전달 중단·재개2, exhaustion pause/stop2)를 추가해
canonical/strict 독립 inventory·실제 보고서 변조 대상에 연결했다.
같은 canonical 선택 수집은1340개이며 새7개 각각1회다. unrelated Search collection4SKIP는 별도다.
checker의 새7개×7누락 층 단위49PASS(35+14)는 실제 canonical·실제 보고서 변조 성공을 대체하지 않는다.
독립 소스 리뷰에서 발견된 source 변수 shadow, T2·결과 재전달·exhaustion 발주 우회를 처리했고,
최종 재검토에서 잔존 P1/P2는 발견되지 않았다. reviewer는 실제 MySQL을 실행하지 않았다.
현재 실제 MySQL은 **NOT_RUN_RESOURCE**다. 초기 Available2.77GB, 후속3.62GB 모두 앞선
Docker/MySQL 기동 감소 관측 약3.15GB+reserve1GiB를 확보하지 못해 시작하지 않았다.
Docker 재구축/pull·기존 volume·운영 DB 접근은 없다. 이번 canonical 전체/strict/실제 보고서 변조/새 Linux CI는 NOT_RUN이다.
과거 b3ce Linux PASS와 로컬 Windows symlink AUTH_REQUIRED 기록은 보존한다.

공식 샘플/일·누적 예산은 승인됐지만 호출별 bound·그 밖의 한도·보호 mount·image/host 복구·Web 통합·
외부 두 세션의 실제 분석→다운로드/재생 완주가 남아 **공개·운영 적용 NO-GO**다.
