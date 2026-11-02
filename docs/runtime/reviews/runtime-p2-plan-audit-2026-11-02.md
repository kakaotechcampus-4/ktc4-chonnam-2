# P2 Capacity Smoke 정합성 감사 — 2026-11-02

**Audited:** fetched `origin/develop` `15b8b6a1658652fa16ea86d490df9f6bbe24e5bc`\
**대상:** [기존 P2 계획](../experiments/elice-runtime-capacity-smoke-plan.md)\
**범위:** 코드·문서·GitHub 읽기 감사. 실험 결과나 정책 결정이 아니다.

이 감사와 사용자에게 전달한 분류를 먼저 정리한 뒤 P2 계획을 수정했다.
AWS/SSM·provider·배포·rollback·DB fault·실제 22개 입력 실행은 하지 않았다.
현재 코드와 배포된 artifact의 동일성을 원격으로 확인한 작업도 아니다.

최초 감사는 `54f6ecbb`에서 시작했다. 최종 원격 대조 중 #470이 병합돼 `15b8b6a1`까지
fast-forward하고 6파일 delta를 직접 읽었다. Case의 IncidentClip 결과 `preview_frame_ref` 저장/투영과
위치 해석 helper이며 handler frame 발급은 아직 미연결이다. T2에서 decode하지 않는 경계와
#452 typed notice·Runtime/Recording/Search/config 경로는 유지돼 감사 결론은 바뀌지 않았다.

## 1. 결론과 workflow 위치

기존 계획의 capacity 질문은 유효하지만 **현재 실행 가능한 계획으로 그대로 사용할 수 없다**.
Runtime은 workflow §8의 구현·관측을 거쳐 §9의 제한적 AWS Real E2E evidence를 확보했다.
RT-14(M6)는 IN_PROGRESS이며, P2(M7→M8)는 본격 측정 전이다.
§10의 결과 기록은 일부 존재하나 §11의 capacity/timing 최종 baseline 승격은 아직 아니다.
마일스톤을 하나의 순차 완료 표시로 축약하지 않는다.

가장 오래된 가정은 다음 다섯 가지다.

1. Queue/Worker/Compose가 구현 전이라는 가정.
2. Coarse/Fine도 과거 Flash 경로라는 가정. 현재 기본은 Argon, Intent만 Flash다.
3. process-local reuse를 job 간 warm cache와 동일시한 가정.
4. restart 시 준비된 모든 bytes/ref가 사라지는 것처럼 읽히는 가정.
5. 작은 20초 fixture와 존재하는 모든 metric만으로 phase attribution·장시간 입력·장애 실험까지 가능하다는 가정.

## 2. 기존 P2 항목별 판정

판정은 복수일 수 있다. DONE/EVIDENCE EXISTS는 해당 좁은 질문만 뜻한다.

| 기존 항목 | 현재 상태·근거 | 판정 | 수정 방향 |
| --- | --- | --- | --- |
| P2-A cold normal path | RT-14의 실제 5.533333초 입력에서 7 job·신고영상 다운로드 성공. Recording 단독 준비/요청 구성 peak는 미계측 | UPDATE / DONE·EVIDENCE EXISTS(관통) | 관통 자체를 다시 완료 조건으로 삼지 않고 대표 입력·정상 부하의 자원/시간 측정. cold의 범위를 새 execution/service로 명시 |
| P2-B warm reuse | `ProductionMediaFactory.__call__`은 invocation마다 새 RecordingService/SearchService. `_analysis_reuse`는 instance dict. 로컬 원본 preparation은 새 instance에서 다시 materialize | SPLIT / UPDATE | 동일 Worker의 별도 job 반복과 같은 service instance의 reuse micro-probe 분리. 후자는 module evidence이고 Runtime warm hit가 아님 |
| P2-C failure/cleanup | limits·typed failure·checkpoint 구현. Recording temp root와 Search `tempfile.mkdtemp()` 경로가 다름 | KEEP(질문) / UPDATE / SPLIT | 정상 종료·한도 거부·Search 실패·crash 잔여를 분리. `/media/worker-temp`만 측정하지 않음. 임의 ENOSPC/실 provider 장애 유도 제거 |
| P2-D restart/reuse | prepared content는 MySQL LONGBLOB, 원본은 shared media. RT-14 재부팅/DB·media 격리 restore 후속 evidence 존재 | UPDATE / DONE·EVIDENCE EXISTS(좁은 내구성) | ref 읽기와 새 job의 재준비 비용 분리. restore/release rollback 재실험은 REMOVE→RT-14 |
| P2-E concurrency | B-W2는 process당 1, env knob 없음. 배포 controller는 service당 container 1개 검사 | UPDATE | 단순 운영 `--scale worker=2` 지시 제거. 별도 target의 복수 Worker 실험 설계·DB/lease 동시성·provider 한도/비용·자원 예산 선행 |
| P2-F timing/failure | heartbeat/sweep/retry/cancel과 DB 집계·이벤트 구현. 정확한 T2 reason의 상시 로그/DB column은 없음 | KEEP(질문) / SPLIT / UPDATE | F1 정상 관측, F2 kill, F3 heartbeat DB stall, F4 late reflection, F5 cancel로 유지하되 가용 계측·target을 각각 명시 |
| 구현 전 조건문·과거 모델 고정 | API/Worker/MySQL/health/deploy 실제 구현 존재 | REMOVE / UPDATE | 역사적 입력은 링크로 보존, 현재 경로는 owning code로 재구성 |
| 20s/480p/H.264/MP4/audio off | #95 P1의 역사적 후보. RT-14 입력은 별도 5.533333초 비식별 사본 | UPDATE / SPLIT | minimal/representative/boundary/long regression fixture를 분리. 실제 확보·권한·manifest 확인 전 길이 grid를 확정하지 않음 |
| #452 남은 결합 검증 | 구현·Case/Web 연결·초기 baseline은 병합. 실제 22개와 Runtime phase별 측정은 미완료 | ADD | P2-0a duration rejection regression + P2-0b supported-range characterization. P2-A와 같은 실행 자료 재사용 |

제목의 Elice는 여전히 실제 provider 경로와 맞는다. inbound link를 `rg`로 조사했고
Ops·workflow·Baseline·Register·Classification·과거 review/official input이 참조한다.
파일명은 유지하고 제목을 Runtime 질문 중심으로 명확히 한다. 기존 참조의 §5(환경),
§8(실험 순서), §12(P3/다음 단계) 역할도 유지한다.

## 3. 현재 실행 경로와 코드 근거

```text
API Case command → Case 저장/JobRecord + Runtime enqueue (같은 transaction)
→ job_execution QUEUED → claim (RC / SKIP LOCKED / acknowledged commit)
→ execution별 heartbeat + UsageSink, Worker handler
→ Recording scope/ownership/provenance 확인 → duration guard
→ encode/span bytes/concat guard → prepared media MySQL 저장
→ Search가 stream 복사·probe·Coarse/Fine 재인코딩
→ inline media/base64/JSON cap → Elice HTTP (시도별 usage begin/finish)
→ Run/produced + terminal T1 → usage reconciliation
→ T2 Case reflection + 후속 JobRecord/enqueue + case_applied_at (같은 transaction)
```

초과 분기는 Search 진입 전 `FAILED / RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`다.
원본 등록·progress·JobExecution·Case 쓰기는 있으므로 “DB write 없음”은
**AnalysisSource BLOB publish 없음**으로 한정해야 한다.
전체 Case에는 앞선 HINT_EXTRACT usage가 있을 수 있으므로 provider 미호출도 해당 Coarse
execution 기준으로 증명해야 한다. duration guard 전에 resolve/time-source 관찰은 가능하다.

| 검토 경로 | 확인 내용 |
| --- | --- |
| `api/{bootstrap,composition,app,health}.py` | 파일 config·Case+enqueue/cancel transaction·live/ready. ready는 DB/저장소만 보며 Worker/provider 성공 검사가 아님 |
| `common/db/{engines,transactions,migrate}.py`, `common/jobs/{schema,repository}.py` | MySQL 8.4·PyMySQL/SQLAlchemy Core·RC/UTC·역할별 pool·claim receipt·terminal 조건부 갱신·모듈별 migration |
| `common/jobs/{worker_loop,heartbeat,sweep,retry_policy,cancel}.py` | process당 1 execution·별도 heartbeat/sweep·lease expiry·STALE만 자동 retry·취소 표식/협력 checkpoint |
| `common/usage/{sink,reconciliation,repository,schema}.py` | durable inflight/Final·attempt별 invocation·reconciliation, null cost는 0원 아님 |
| `common/jobs/{reflection,redelivery}.py`, `worker/{case_composition,case_reflector}.py`, `case/{reflection,domain,service}.py` | T1/T2 분리·Case 선잠금·execution idempotency·STOPPED_WAITING 구현·전용 notice |
| `worker/{__main__,composition_root,composition,production_media,search_composition,search_handlers}.py` | 8종 조립·실행별 서비스·Recording typed error의 좁은 매핑 |
| `recording/{factory,service,analysis_limits,materialization,mysql_repository,observability}.py` | 필수 설정 그룹·instance reuse·prepared BLOB·encode 전 duration/출력 bytes guard·opt-in phase 관측 |
| `search/{config,media,provider,retry,execution,intent}.py` | Argon/Flash 분리·Search 재인코딩·40/56 MiB cap·SDK retry=0 + Search in-call retry·RunDeadline |
| `common/storage/{media,cleanup}.py`, `search/media.py` | Recording 명시 temp root/lease·startup/age cleanup·등록 원본 보호. Search global temp는 별도 finally 정리, crash cleanup 보장 아님 |
| `compose.yaml`, `Dockerfile`, `docker/runtime.py`, `deploy/{ec2,configure,public_smoke}.py` | local/production Compose 차이·pinned FFmpeg 8.1/OCR·external volumes·health/8종 marker·packet guard·보호 config·public smoke |

heartbeat/lease/sweep/retry 기본 숫자는 Baseline의 B-L*/B-R*와 현재 config가 일치한다.
숫자는 새로 결정하지 않는다. cooperative cancel의 Recording preparation 내부 checkpoint가
#477로 추가됐지만 Search in-flight HTTP 전체 선점 중단은 없다.

## 4. 이미 있는 evidence와 남은 RT-14 경계

| 항목 | 최신 근거에서 확인한 상태 | P2 처리 |
| --- | --- | --- |
| 실제 AWS 배포·secret 공급·internal/public smoke·8종 등록·7 job | [10/31 Result §2·6·8](../experiments/2026-10-31-rt14-aws-real-e2e.md). 배포 RC는 `e50b2976`, 감사 develop과 다름 | 관통 evidence 참조. 대표 capacity 완료로 확대하지 않음 |
| 자원 표본 | 같은 Result §8.4의 2초 sampling/단일 입력. startup HWM·sampling 누락 가능 | 단회 RSS/CPU/temp를 threshold·p95로 쓰지 않음 |
| 재부팅·UID·알려진 secret 사본 정리 | Result §14 운영자 보고 | 중복 TODO 제거, 실패 주입 acceptance로 확대하지 않음 |
| DB·PAX media 격리 복원·Case/asset 비교 | [Recovery §10](../rt14-recovery-acceptance.md#rt14-recovery-operator-results), Result §15 운영자 보고상 단회 PASS | 미실행으로 되돌리지 않음. 복원 DB 정상 Worker job은 아직 미검증 |
| 두 번째 deploy / rollback | 현재 후속 기록에도 미완료 | Deployment/RT-14. 파괴적 P2 운영 적용의 선행 안전 evidence와 독립 수행 과제 구분 |
| public endpoint 재확인 | 10/31 검증자 PASS 이후 운영 복귀 확인은 local HTTPS 403 | 현재 외부 200 재확인 미완료. 과거 PASS로 대체하지 않음 |
| Recording profile/limit | #460·#526·#528에서 초기 baseline v1 확정·문서 반영. 선택 파일 9/9 대조는 운영자 보고 | 초기값 재결정 불필요. process 적용/운영 최적값·지원 범위 결합 측정은 미완료 |
| off-host backup / RPO·RTO | 정책·승인값·실측 보장 미완료 | 별도 Ops/Recovery. P2가 정책을 만들지 않음 |
| Package READY / 장기 공개 gate | 계속 미완료 | 별도 입력 충족 E2E/hardening. 모든 제한적 P2의 일괄 blocker로 만들지 않음 |

Issue #450 본문/5개 댓글은 이후 Result보다 오래된 상태가 섞여 있다. Issue 체크박스만으로
실행을 부정하거나 완료를 선언하지 않았다. RT-14 Result/Recovery도 과거 절은 보존돼 있으므로
최신 후속 절을 우선하고, Recording baseline은 더 최신인 #526/#528을 따른다.

## 5. #452 편입 근거

Issue #452 본문과 전체 9개 댓글을 읽었다. 최초 웹/API 실패는 Windows temp 경로 #453이고,
일반 temp 경로에서 다음 단계인 224 MiB BLOB 저장 실패를 확인한 **두 층의 문제**다.
Case 180초 대기와 Recording 준비/Search RunDeadline의 기산점 차이도 별개다.

[PR #477](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/477),
[#454](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/454),
[#481](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/481),
[#492](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/492),
[#526](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/526)의 merge metadata를 확인하고
현재 factory/service/handler/Case/Web/config를 대조했다. merged라는 사실만으로 판단하지 않았다.
상세 구현·로컬/CI evidence는 [Recording limits](../../modules/recording/analysis-source-limits.md)가 소유한다.

남은 질문은 Runtime/DB/Search/Case 결합 자원·시간·실패 의미이므로 P2에 편입한다.
22개/약 19분 26초는 현재 4분 설정에서 **성공시킬 입력이 아니라 안전 거부 regression**이다.
7분 20초 Search 단독 성공이나 표본의 9~13분 추정을 전체 경로 지원 길이로 쓰지 않는다.
profile/limit SoT는 Recording 문서와 [설정 명세 §3](../../management/environment-and-deployment-config.md#3-recording-초기-배포-baseline-v1)이며
P2는 그 값을 입력받는다. #452 close, 클립 분할, timeout/길이 변경은 하지 않는다.

## 6. 최소 계측 공백과 blocker

| 공백 / 선행조건 | 현재 가능한 것 | 필요한 후속 |
| --- | --- | --- |
| Recording phase attribution | opt-in `capture_materialization()`의 단일 materialize phase | 기본 Worker 활성화 없음. 전체 준비/concat/DB write까지 같은 execution으로 잇는 비민감 observer/harness 검토. 현재 trace를 전체 준비로 오독 금지 |
| Search preparation·request 구성 | provider UsageRecord latency·job DB 시각 | stream/probe/재인코딩/base64/JSON/SDK HTTP bytes·elapsed 분리 observer 필요. byte 길이만, payload 보존 금지 |
| DB 여유 | 배포의 `maximum + margin < session packet` 검사 | SQL escaping·metadata·driver buffer까지 증명하지 않음. 격리 DB의 bounded 측정·저장/읽기/rollback·연결 유지 검증 필요 |
| T2 결과·reason | redelivery status log·STOPPED_WAITING retry counter·`case_applied_at` | marker는 NOT_APPLIED에도 생김. APPLIED 증거로 단독 사용 금지. 정확한 outcome/reason post-commit 수집 필요 |
| cancel 의미 | marker→heartbeat signal, checkpoint→T1 commit, marker→terminal 지표 | signal과 첫 handler checkpoint 구분. 정확한 marker→checkpoint가 필요하면 추가 관측. B-X1 이름만으로 보장하지 않음 |
| kill/stall 주입 | 테스트 전용 barrier·OS kill·DB harness 존재 | production image에는 phase 제어 API 없음. 별도 target의 exact container·재기동·bounded fault·복귀 계획 필요 |
| resource/fixture | host sampler·DB/log 파생 관측 가능 | AWS 현재 tuple/예산/보호 경계 재대조, 실제 fixture·22개 권한/manifest 확보. 기본 CloudWatch만으로 RSS/temp 계측 불가 |

계측이 없는 구간은 N/A/UNKNOWN으로 남기고 인접 두 timestamp의 차이를 단독 구간으로 이름 붙이지 않는다.
관측/코드 후속은 이번에 구현하지 않았다. 상세 실행 순서·중단 조건·readiness는 갱신한 P2 계획에 둔다.

## 7. 확인한 문서 범위

Runtime README, workflow, Tech/Ops Spec, Provisional Baseline, Implementation Plan/Log,
Open Decision Register, Decision Classification, local runtime guide를 현재 snapshot의 관련 절과 대조했다.
RT-14 deployment/design/public runbook/recovery/result, RT-13(a)/(b) 연결,
experiments router/P2/pre-implementation spike, Recording limits, 환경·배포 설정 명세,
Case long-analysis-range/timeout 결정, RT-12(b) observability와 owning code를 함께 검토했다.

README의 10/02 구현 전 snapshot, Register RD-09의 in-memory 설명, Ops의 10/30 미배포/운영값
미확정 표현은 역사적 상태와 현재 상태가 혼재한다. 이번에는 P2 진입·직접 참조에 필요한
링크/상태만 최소 수정하고 상위 문서 전체 재작성이나 Owner 결정 종료는 하지 않는다.

## 8. 이번 문서 작업의 검증

- 변경한 Markdown 7개(감사 신규 1개 포함)의 로컬 링크/anchor 205개를 확인했다. 누락 0개.
- `git diff --check`와 변경 경로 검사를 통과했다. 제품 코드·config·Contract·workflow 변경은 없다.
- 위 source·PR merge metadata·Issue 본문/댓글 대조는 정적 감사다. pytest/MySQL/Docker·AWS/provider·실영상 실행 검증으로 세지 않는다.
- 기존 작업 브랜치를 보존한 `codex/runtime-p2-plan-audit` worktree에서 문서만 수정했다. 감사 작성 시점에는 commit/push/PR·외부 댓글/Issue 상태 변경을 하지 않았다.
