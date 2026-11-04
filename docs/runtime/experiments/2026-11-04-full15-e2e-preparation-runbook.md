# 원본 15개 전체 E2E 준비·운영자 runbook

**상태: PR 준비·focused 163 PASS / Windows 전체 회귀는 §9의 실패 포함 / 해당 22개 Linux 재확인 PASS(§10) / 기존 EC2 전체 E2E NOT_RUN.** Refs #452 · #530 · #552 · #561. 기준 제품 HEAD `a962374079275e5d64a3d561f97bf2ec7e345dde`, 브랜치 `codex/issue452-ec2-long-recording`. 하네스 변경은 미커밋 content SHA-256으로 식별한다. 아래 운영 절차는 이번 세션에서 실행하지 않는다.

목표는 **기존 EC2에서 실제15개 전체 1584.173332초(26분 24.173332초)**를 Upload → Search/Case → 후보 확인·필요 시 수정 → Export → Package READY → 신고영상 다운로드까지 완주하는 것이다. 1200초 prefix나 여러 짧은 시험의 합, 별도 배포의 준비 성공은 대체 증거가 아니다. 180초 성능 최적화와 미검증4GiB 후보 보완은 범위 밖이다. 180초 내 완료는 이번 인수 조건이 아니지만, 현 Case 코드가 늦은 결과를 버리는 문제는 Case Owner 판단으로 별도 해결해야 한다.

## 1. 읽은 근거와 현재 차단 판정

2026-11-04 GitHub 읽기 전용 조회로 [#452 본문·댓글21개](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452), [#530](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/530), [#552](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/552), [#561](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/561)의 본문·댓글·병합 metadata를 확인했다. #530·#552·#561은 merged다. 후속 재조회에서도댓글21개이며 최신 [#452 댓글6624832198](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452#issuecomment-6624832198)의 **기존EC2 전체완주** 목표와 대조했다. Search/Case Owner의새답변은이조회에서확인되지않았다. 최초/후속snapshot을각각scratch에보존한다.

| 조건 | 현재 제품 코드·계약 근거 (레포 루트 기준) | 전체 입력에 필요한 조건·판정 | 조치 종류·Owner |
| --- | --- | --- | --- |
| Web 업로드 | `apps/web/src/state/caseFlow.ts:132,151`, `api/client.ts:109–112`: 같은 Case에 파일별 순차 업로드, 요청당 file 하나, upload에서는 JSON 기본 15초 timer 비활성 | 15개 합계가 1GiB를 넘는 사실만으로 요청별 한도 위반을 판정하지 않는다. 최대 원본은 125108616B. multipart overhead 포함 각 요청과 실제 배포값 대조 필요 | 설정·실험. 병렬화/순서 변경은 Web 제품 변경 |
| API/Caddy | `common/config/__init__.py:100–102`: 기본 요청 1073741824B, idle60초, 수신1800초. `api/upload.py:64,255`: 실제 요청 bytes 검사. `deploy/Caddyfile:11`은 별도 size/timeout을 추가하지 않음 | repo 기본값은 현재 서버 설정의 증거가 아니다. 실제 ingress 경로·연결·staging 정리도 확인. `config:215`의 staging age≥수신 제한×2 유지 | 설정/운영 확인 필요 |
| Upload 성공 수 | `caseFlow.ts:108–119`: 실패 후 다음 파일 계속, 불명확한 응답은 file_count 증가로 정산 | 화면 진입만으로 15개 성공이라 하지 않는다. 요청별 결과, `file_count=15`, `ok_file_count=15`, Source↔익명 input 매핑 필요 | 실험 증거. 불명 응답 무조건 재업로드 금지 |
| Recording 길이/bytes | `.env.example:31–32`: baseline 48MiB/240000ms. `docs/modules/recording/analysis-source-limits.md`, `recording/factory.py`, `analysis_limits.py`: 길이 사전 검사, 누적·최종 bytes/DB 전 차단 | baseline이면 전체 길이 초과. 이번 하네스만 512MiB/1584174ms의 결속 profile 추가. 전체 출력 크기는 아직 모름 | 격리 설정 준비 완료. 운영승격은 Recording·Runtime/PM 판단 |
| materializer/청크/조회 | `recording/materialization.py`, `mysql_repository.py:204,291,319`, `chunked_media.py:8`: 256KiB 청크·escaping 후 command guard, 새 연결 detached stream. materializer와 일부 export는 전체 bytes 할당 유지 | 청크가 전체 메모리 상한을 없애지 않음. 15개 resolve COMPLETE, 15 VIDEO spans, strict/PTS/coverage/provenance·commit/rollback·새 연결 metadata/hash/length 검사 필요 | 기존 제품 경로 재사용. 실제 전체 Linux 실행 NOT_RUN |
| Search source/media/request | `search/config.py:47,50–51`: 512MiB / 40MiB / 56MiB. `search/media.py:264–283,382–390`, `provider.py:288–294,349–357`에서 송신 전 검사 | AnalysisSource와 재인코딩 media·base64 JSON은 다른 한도. 전체 입력이 통과할지는 미측정. cap을 자동으로 올리거나 guard를 끄지 않음 | 실험. cap 변경/분할은 Search Owner 판단·제품 변경 |
| 270p·CRF28 | `search/media.py:279–280,345–346,427–436`: 운영 Coarse/Fine360p. `recording_real_media_recheck.py`의 명시 실험 hook만270p·CRF28 | #552는 720/1200초 크기 준비·송신 직전 중단 성공. #452의 품질회귀 실행 계획은 있으나 조회한 댓글/현재 코드에서 채택 결과를 확인할 수 없음. 26분 크기·품질 성공 근거 아님 | Search Owner 품질 판정·운영 채택 **미해결**. 이번 mode는 실험만 |
| Case180초/late result | `case/analysis_start.py:34–35`, `domain.py:108,358–378`: 발주+150+30초, 만료시 STOPPED_WAITING. `reflection.py:87–107`: 먼저 만료 정산, 늦은 성공 NOT_APPLIED | 목표에서 180초를 제외해도 코드가 바뀌지 않음. 큐·Recording은 Case 시계에 포함되고 Search RunDeadline 밖. 늦은 Worker SUCCEEDED만으로 후보 확보 PASS 불가 | **제품 변경/Owner 결정 필요**. Case 유소연·PM 김준영, Web 신유민 consulted. 값/기산점/준비 신호/late 수용 중 선택은 미확정 |
| 사용자 진행 | `case/search_progress.py:8,22–41`, `SceneSearchStep.tsx:13–17`, `labels.flow.ts:64–72`, `caseFlow.ts:42,63–70` | PREPARING→SEARCHING→ORGANIZING. 백분율/ETA 아님. Search 시작 후120초 문구, Case 만료 후 진행 갱신 거부·running_jobs 비면 polling 정지 | Case 정책과 함께 Web UX 검토. UI timer만 늘려 우회하지 않음 |
| lease·retry | `common/config/__init__.py:82–89`, `jobs/heartbeat.py:168–172`, `worker_loop.py:104–107,158–162`, `retry_policy.py:8–14` | heartbeat10초/lease60초/sweep15초, stale retry1. lease는 전체 작업60초 제한이 아님. 일반 FAILED 자동 retry 아님. heartbeat·STALE·재전달 직접 관측 필요 | 설정/실험. 재시도 확대는 하지 않음 |
| provider deadline·시도 | `search/config.py:52–53`, `retry.py:45–79`, `provider.py:219–223,361–365,398–402` | 기본 Search150초 안에서429/5xx만 최대4시도, SDK retry0. Runtime 기본 최대2execution과 조합하면 **조건부 계산상 Coarse job 최대8시도** 가능. 실제 관측 호출수 아님 | 전체 Case의 Intent/Coarse/Fine/재요청 시도 상한은 별도 결정 필요 |
| 비용·시도 | `search/intent.py:40,108–138`, `search/retry.py:45–79`, `common/config/__init__.py:87`: Intent60초·Coarse150초·Fine70초, Search최대4시도/execution·STALE retry1·SDK retry0. scope1000원/max_cost_usd는 금액차단 아님 | 기존 시도제한과 유한 사용자 동작 수로 단회 호출 상한 계산 가능. 하네스는 실제provider0회/비용0. 유료 금액은 실제요율/허용금액·관측/중단 절차로 별도 확인하고 자동hard금액보장을 주장하지 않음 | **설정/운영 확인 필요**. §6의기존 제한 우선 적용. 범용 비용관리/새전역gate 구현은 이번 선행조건이 아님 |
| 배포 revision/schema/reader | `docs/modules/recording/chunked-prepared-media.md:73–106`, `prepared_metadata.py:37`, migration `0002_media_chunks.py:13` | 청크 reader와 metadata-envelope decoder는 별도 필수. 새 코드는 legacy 읽기, 구 코드는 새 청크/envelope 읽기 불가 가능. 같은 schema head로 호환 입증 불가. 현 서버 tuple은 이번 확인 불가 | 실제 두 revision의 양방향 fixture·durable job/case·reader 확인 필요 |
| rollback/데이터 | `deploy/ec2.py:123–139`, `rt14-public-deployment.md:220–228` | candidate.rollback_targets에 기존 current 필수, 실제 schema authority와 schema_parent 일치 필요. 비호환 current를 허위 승인해 우회하지 않음. forward-only migration·기존 BLOB 보존 | **실제운영값 확인 필요**. 기존EC2의 안전한revision 전환/rollback 경로를 확정. 격리probe는 준비검증일 뿐 최종목표를대체하지 않음. 운영 DB migration/rollback은 이번 NOT_RUN |
| Export/Package/download | `worker/export_handlers.py:33`, `case/service.py:174`, `contract-requirement-report-package.md:280,396,440`, `contract-http-api.md:493` | Export terminal/T2와 현재 selection의 FINAL_PACKAGE PASS/WARN·필수 ReportVideo·실제 ReportPackage·artifact 다운로드 필요. READY200/공개 smoke와 Package READY는 별개 | 실제 E2E NOT_RUN. 최종 파일 bytes/hash/decode·사건 범위/출처까지 대조 |

`src/daesingo/` 경로는 위 표에서 공통 접두사를 생략했다. Owner 계약·제품 지원 범위·Case 정책을 이 실험 문서가 재정의하지 않는다. `long-analysis-range.md`의 분할 제외 결정을 임의 변경하지 않으며 cap/품질이 막히면 #530 Decision Gate로 돌려보낸다.

## 2. 실제 15개 입력 대조

보호 manifest `.codex-scratch/capacity-input15-20261102/manifest.private.json`과 사용자 지정 원본 폴더를 직접 읽었다. 15개 **SHA-256·size·mtime·파일 집합·metadata·첫 VIDEO index0 전부 일치**했다. 합계1771439266B, metadata 길이1584.173332초. 전체 VIDEO는 H.264·1920×1080·time_base1/30000이다. input-01/15는 평균 frame rate가30/1이 아니므로 CFR로 가정하지 않는다. 로컬 ffprobe9.0.1 결과이며 배포8.1 materialization 성공 증거가 아니다.

원본명/경로/hash 상세는 공개 문서에 넣지 않고 `.codex-scratch/full15-local-20261104/input-audit/audit.private.json` 및 `input-plan/transfer-plan.private.json`에만 둔다. 실제 촬영 seam 연속성은 UNKNOWN이다. logical gap/overlap0은 명시 placement의 성질이며 촬영 연속성의 증명이 아니다.

| 익명 입력 | 길이(초) | logical 시작→끝(초) | hash/stat/VIDEO |
| --- | ---: | --- | --- |
| input-01 | 117.933333 | 0→117.933333 | PASS |
| input-02 | 88.566667 | 117.933333→206.500000 | PASS |
| input-03 | 107.233333 | 206.500000→313.733333 | PASS |
| input-04 | 99.633333 | 313.733333→413.366666 | PASS |
| input-05 | 98.066667 | 413.366666→511.433333 | PASS |
| input-06 | 82.133333 | 511.433333→593.566666 | PASS |
| input-07 | 88.466667 | 593.566666→682.033333 | PASS |
| input-08 | 83.100000 | 682.033333→765.133333 | PASS |
| input-09 | 88.366667 | 765.133333→853.500000 | PASS |
| input-10 | 111.000000 | 853.500000→964.500000 | PASS |
| input-11 | 88.733333 | 964.500000→1053.233333 | PASS |
| input-12 | 88.433333 | 1053.233333→1141.666666 | PASS |
| input-13 | 87.133333 | 1141.666666→1228.799999 | PASS |
| input-14 | 95.733333 | 1228.799999→1324.533332 | PASS |
| input-15 | 259.640000 | 1324.533332→1584.173332 | PASS |

하네스는 전체 소수초 끝점을 `Decimal(str(seconds))`로 비교하고 1200초/정수1584초 축소를 거부한다. **기존 계약에 따른 단위 차이:** `case/timeline_source.py:31–35`는 ms FLOOR, `analysis_start.py:80–81`는 그 end_ms를 사용한다. 제품scope는1584173ms로 하네스보다0.332ms 짧다(직접계산). 이는 `docs/modules/case/decisions/start-analysis.md:81`의 기존 정책이다. `materialization.py:232–249`는 정규화PTS가요청안에있는frame을선택하고frame번호로trim하며, 끝은요청시각이아닌실제마지막PTS+duration으로반환한다. `multi-span-analysis-source.md:31–34`도 바깥끝의frame coverage를허용한다. seam용≤1µs비교를요청끝과actual끝차이에적용하지않는다.

후속 읽기 전용관측에서 input15의첫PTS0, 마지막정규화PTS **259.60초**, 마지막관측duration **0.04초**, VIDEO/format duration **259.640000초**를확인했다. Case의local끝은 **259.639668초**, exact local끝은259.64초이므로둘다같은마지막frame을선택하며actual끝은259.64초다. 따라서 **이0.332ms 차이로마지막frame이제외되거나새strict실패가생긴다는근거는없고, 새RC blocker/새Owner정책요구로분류하지않는다.** ceil전환·strict완화·허용오차변경도하지않는다. first/tail probe와hash/stat불변은새source관측이며, 전체frame probe의20초timeout은보존했다. 로컬ffprobe9.0.1 source관측을EC2 8.1 encode/strict 성공으로대체하지않는다. 실제E2E에서는기존계약대로actualframe coverage와15개source연결을확인한다.

`UploadScreen.tsx:155,279`는 OS의 FileList 배열을 그대로 전달하고 별도 정렬하지 않는다. `case/timeline_source.py:59`는 등록된 sources 순서대로 누적하므로, 실제 브라우저 배열→15개 요청→Case sources→timeline ordered placements→실제 SpanResolution을 hash/ref로 연결해야 한다. Case는 VIDEO가 정확히 하나일 때만 그 ref를 고르며 index0을 가정하지 않는다(`case/domain.py:230`, `timeline_source.py:52`). 새 audit도 VIDEO가 정확히 하나이며 index0인 조건을 요구한다. 이번 실제15개는 그 조건을 만족한다.

## 3. 전체 입력용 유한 예산

`full15-512m`는 완료시간 예측이 아니라 **한 번의 격리 probe가 소비할 수 있는 중단 한도**다. 기존 [120초 EC2 결과](2026-11-04-ec2-recording-probe-result.md)의177.613151199초/34539938B/runner peak229806080B를26분에 비례 환산하지 않았다. 기존 [1200초270p 실측](2026-11-03-coarse-270p-probe.md)의366121221B도26분 크기의 보장값으로 쓰지 않는다.

| 예산 | full stage | 근거·집행·한계 |
| --- | --- | --- |
| 원본 | 15개1771439266B, 입력 readonly | 로컬 실측 합계. 원본 복제/전송은 이번 없음. 향후 복사본·패키지·evidence 공간은 실제 staging 이후 df에 반영 |
| 출력 N | 512MiB=536870912B | 기존 Search source cap과 같은 유한 종료선. CRF 최종 크기는 모름. 초과면 typed rejection이며 성공으로 분류하지 않음 |
| 길이 | 최대1584174ms | 실제 전체 길이×1000을 ceil한 config 검사값. **요청 끝은1584.173332초 그대로**, 1584.174초로 확장하지 않음 |
| runner RAM | hard3072MiB / soft2560MiB / swap0 | 기존 공유 식4N+240MiB=2288MiB 후보보다soft가 큼. bytes·probe·driver·page cache의 실제 peak 보장식 아님. leaf actual limit·current/peak·OOM events 확인, hard cgroup 최종 차단 |
| 임시 공간 | soft1280MiB | 기존 식2N+Search 후보64MiB=1088MiB. named+열린 unlinked file 계측, sampler0.2초. 순간 초과는 표본 사이 발생 가능 |
| DB | hard512MiB / soft440MiB, data soft2560MiB | 초기 실측 DBdata+3N(1536MiB)<2560MiB 필요. 64MiB packet 유지. data/temp/redo/driver 관측을 전체 peak 보장으로 확대하지 않음 |
| host RAM | 시작≥4096MiB+R | runner3072+DB512+collector512+R. R=max(실제 policy reserve,700MiB), 최소4796MiB=5028970496B. 실행 중에도 R 유지. 총 RAM8195911680B는 과거 운영자 보고이며 현재 MemAvailable 대체 아님 |
| host disk | D=max(policy,4GiB), 시작 free≥D+4GiB, 증가<4GiB | 기존 식5N+64+64=2688MiB 후보, 현재 증가+후보≤4096MiB. source/evidence/실제 DockerRootDir의 최소 free와 각 filesystem 증가 합. baseline은 staging 후, image/cache를 지워 여유 만들지 않음 |
| 실행시간 | runner3600초 / host wait3630초 | 한 시간의 단회 실험 ceiling 제안. 전체 변환시간 예측·SLA·Case timeout 아님. 준비가 끝나지 않으면 실패 보존 후 중단. 자동 연장/재시도 없음 |
| 나머지 시간 | DB readiness120초, 도구 호출당120초, cleanup 별도60초 | phase/host 감시 유지. 개별 Docker 호출15초 기본·capture8MiB/stream. CLI timeout이 daemon/OS hang 종료를 절대 보장하지 않음 |
| Search 준비 | source512/media40/request56MiB, deadline150초 | 유지. mode 선택 시 Coarse270p/CRF28만 실험, Fine 안 함. Search64MiB는 자원 산식의 후보 여유이며 media cap 상향이 아님 |
| provider | 실제0회·비용0, 자동 재실행0 | credential 미주입·internal network·HTTP/socket 차단·SDK sentinel. 최종 유료 E2E용 허용 금액/호출 제한은 아직 미확정이며 실행 gate를 열지 않음 |

점검 창도 유한하게 관리한다. **실험 제안:** drain 관측 최대300초, 전체 점검 승인 최대7200초, 그중 마지막300초는 복귀용으로 남긴다. 이는 제품 timeout/운영 SLA가 아니다. `maintenance-approved.private.json.not_after_unix`는 담당자가 정한 유한 종료시각이며 감독기가 실행 중 만료를 검사한다. 새 stage는 남은 승인시간이 그 stage의 runner/host·DB startup·정리와 복귀 여유를 수용할 때만 시작한다. 개별 Docker 호출 지연까지 포함한 전체 완료 보장은 없으며 부족하면 full을 시작하지 않고 복귀한다. drain이300초 안에0이 되지 않아도 강제취소·lease 조작 없이 이번 시도를 연기한다. Owner 결정이나 제품 배포를 기다리며 운영을 중단해 두지 않는다.

무미디어→10초→120초는 기존 legacy RAM/출력96MiB/길이240000ms/runner900초를 유지한다. full만 새 profile로 전환한다. 상위 유한 memory.max/high는 기존 adapter가 지원하지 않아 여유가 있어 보여도 거부한다. CPU quota/cpuset/credit·실제 image digest·도구 hash·dependency inventory·policy reserve는 운영자가 읽기 전용으로 확인해야 한다. 같은 장비라는 추정으로 값을 채우지 않는다.

## 4. 로컬 PowerShell 절차 — 이번 허용 범위

실행 위치는 `C:\ktc4-chonnam-2`. 새 evidence 폴더 이름을 사용한다. 기존 RED/FAIL·원본 manifest·4GiB 후보 백업은 덮어쓰지 않는다. pytest 기본 sandbox TEMP/cache 접근 오류가 있어 명시 basetemp와 cache 비활성화를 사용한다. 아래 원본 폴더 변수는 사용자 지정 실제 경로이며 공개 package에 넣지 않는다.

```powershell
Set-Location C:\ktc4-chonnam-2
git status --short --branch
git rev-parse HEAD
git diff --cached --stat
$FullOriginals = (Get-Content .codex-scratch/capacity-input15-20261102/manifest.private.json -Raw | ConvertFrom-Json).source_folder_private
.venv\Scripts\python.exe scripts/recording_full_input.py `
  --manifest .codex-scratch/capacity-input15-20261102/manifest.private.json `
  --source-root $FullOriginals --output $NewPrivateAuditDirectory
```

기대: 지정 branch/HEAD·빈 index, `PASS_INPUT_AUDIT`·15·1584.173332·1771439266. `$NewPrivateAuditDirectory`는 아직 없는 scratch 하위 경로를 운영자가 정한다. 실패시 출력/기존 증거를 보존하고 원본 수정·mtime 보정·manifest 재생성으로 통과시키지 않는다. `input-plan`에는 익명 manifest/placement와 **로컬 전용 비공개 전송계획**만 생성한다. 원본 자체를 복사하지 않는다.

```powershell
.venv\Scripts\python.exe -m pytest tests/runtime/test_recording_full_input.py `
  tests/runtime/test_recording_ec2_probe.py tests/runtime/test_recording_probe_budget.py `
  tests/runtime/test_real_media_recheck.py tests/runtime/test_recording_cpu_quota_probe.py `
  tests/runtime/test_recording_cpu_quota_supervisor.py tests/runtime/test_capacity_probe.py `
  -q -p no:cacheprovider --basetemp $NewControlsTempDirectory
.venv\Scripts\python.exe -X utf8 scripts/check_boundaries.py
.venv\Scripts\python.exe -X utf8 scripts/check_contract_fixtures.py
.venv\Scripts\python.exe -X utf8 scripts/check_runtime_quality.py
git diff --check
```

기대: controls 전부 PASS, 경계/계약/quality exit0, diff whitespace 오류 없음. 실패시 새 개별 log를 보존하고 원인을 수정한 뒤 같은 검사를 재실행한다. MySQL·실제 컨테이너·provider를 시작해 통과시키지 않는다. 이번 직접 실행 결과는 §8에 기록한다.

## 5. 운영자의 다음 작업 — 실행 순서

**여기부터 이번 NOT_RUN.** 이번 세션에는 AWS·전송·서비스중단·provider·배포 권한이 없다. 향후운영자는 읽기조사, provider0격리probe, 기존EC2제품E2E의조건을구분한다. provider0 probe에는exact target·frozen입력/패키지·유한자원·점검/복귀조건이필요하다. 제품E2E에는Case/Search정책·기존설정기반시도/허용비용·배포/rollback조건도필요하다. 새범용금액gate를구현해야만진행가능하다는뜻이아니다. 제품결정미결은승인된읽기조사/provider0준비를막지않는다. 실제확인값만사용하고revision/digest/schema/cost를예시값으로채우지않는다.

| 순서·위치 | 작업·명령/참조 | 기대 결과 | 실패 시 조치 |
| --- | --- | --- | --- |
| 1 로컬/담당자 | 본표의미결항목을Owner에게제시. 목표는기존EC2 전체완주로고정. 허용동작수·시도상한·허용비용과기존데이터보존/전환경로를순서9–10 전에확인 | 읽기조사·provider0준비·기존EC2제품E2E의책임자/조건을구분 | 독립준비계속. 격리성공을최종완주로대체하지않음 |
| 2 EC2 읽기 전용 | [기존 runbook](2026-11-03-ec2-recording-probe-runbook.md) §4의 현황 조사. 실제current/previous/config/schema/reader·CPU/cgroup/credit·reserve·disk/volume 보호 기록 | 과거`e50b2976` 등을 현재값으로 재사용하지 않음. reader/rollback 불일치 식별 | 값/controller guard를 고쳐 맞추지 않음. 제품 전환 보류 |
| 3 로컬 | 실제registry digest·runtime inventory·quota/cpus·operational_identity로 기존package config 작성. `probe_profile=full15-512m`, `full_probe_mode=recording_only` 또는 `coarse_270p_stop_before_send` 명시. 생성한15개판manifest/placements SHA-256을`input_identity`에 결속 | 미확인값 없음. probe 설정은 운영env와 별도. mode는package identity에 고정 | 빈칸/가짜digest로 config 작성 금지. mode 변경시 새package/owner 필요 |
| 4 로컬 | `python scripts/recording_ec2_package.py build --repo . --config $ProbeConfig --output $NewPackageDir`. manifest.sha256을 별도 승인 채널에 기록 | `PASS_PACKAGE`. HEAD제품+하네스content hash·full fixture hash 고정. 이번commit 금지. 향후commit 후 새HEAD로 재package | 제품/lock 미커밋 차이 거부. SHA만 바꾸지 않음 |
| 5 보호 전송/EC2 | 기존runbook §5의 보호 경로·unpack/hash·root0700/uid10001 적용. **승인한15개 모두** 익명input-01…15.mp4로 전송. fixture mount는manifest/placements 두 파일만 | 입력15개·fixture2개, hash/stat/VIDEO0 일치. transfer-plan은 로컬만, 원본readonly. mtime 정밀도 차이는hash/size 일치한 **전송 복사본만** 조정 가능 | 기존`inputs` subcommand는2개용이므로 이번에 쓰지 않음. 원본mtime/manifest 변경 금지 |
| 6 EC2 점검 창 | 기존runbook §6–7: atomic operation.lock·original exact snapshot·ingress/writer/deploy/backup 통제. API중단→미래queued/미반영terminal까지drain→Worker→MySQL exact ID중단. 이번profile용resource_gate 검사 | writer/job0·승인 유효·실제memory/disk/상위cgroup 충족 | 기존서비스 중단 실패시 다음 단계 금지·exact 복귀. reserve 축소/prune/보호volume 조작 금지 |
| 7 EC2 격리 | 아래acceptance→smoke→representative→full을 같은frozen 조합·새owner로 각1회 | 각status PASS·cleanup true. full은15개·전체endpoint·정확성·예산/통신 전부PASS | 한 단계 실패시 후속 금지·같은owner 재시도 금지. §7 복귀 |
| 8 EC2→로컬·즉시 운영 복귀 | phase별시간·output/driver bytes·CPU/memory/temp/disk·source refs/coverage·cleanup 보호 보관 후 **§7/기존runbook§10 exact 복귀·health·tuple 확인·lock 해제**. 공개용은수치/익명status만 추출 | probe 점검 창 종료·기존 서비스 복귀. full 실측을 처음 확보하되 provider0 준비를 제품E2E로 승격하지 않음 | FAIL/NOT_REACHED/NOT_RUN 유지. 축소scope로 대체 금지. 불명확한 복귀면unlock하지 않고 담당자 인계 |
| 9 Case/Search/PM | 실측·품질근거로Case대기/late-result정책·270p채택답변확인. provider는§6의기존제한/단회동작수·허용금액·추가실행절차확정. 실제upload순서/coverage확인 | Owner계약·제품코드·Web·운영config일치. 금액hard보장과운영예산을구분 | 180초성능목표·범용비용관리·4GiB후보로범위확대금지. 무제한retry/cap해제금지 |
| 10 배포 담당·새 작업 창 | probe종료뒤새승인/snapshot/lock으로시작. reader/metadata/durable job호환·DB/media backup_reference·schema_parent/rollback_targets확인후승인된RT-14 controller로 **기존EC2**에적용 | exact release/config/schema·rollback근거. 기존데이터/보호volume3개유지 | 비호환guard우회/데이터삭제/forward-only downgrade금지 |
| 11 실제 브라우저 | 같은Case에 원본15개를manifest순으로Upload, 15성공/stream/ref/timeline 확인→전체Search→후보 확인/필요시수정→Export→Package READY→실제report_video 다운로드 | 다음 절 전체 증거를 같은Case/selection/revision으로 연결. 20분prefix 불가 | Case중단/late결과 폐기도 실패기록. 임의재검색은 추가provider 예산을 소비하므로 중단 |
| 12 운영 복귀 | probe exact-owned 자원 중단/정리·기존서비스/tuple/lock 확인. 제품전환 실패는 승인된 호환exact rollback 경로만 | 원본불변·보호volume/image/cache 유지·서비스ready/worker 정상·잔여/dirty 없음 | 불명확한 채unlock/재시작 금지. 정리실패/잔여 인계 |

EC2의 유지 root shell에서 기존runbook의`OWNER`·`PROBE_HOME`·`PROBE_MANIFEST_SHA256`와lock/snapshot/approval을 준비한 뒤에만 실행한다. 기존문서의 예산표/“2개만 전송”은 본runbook full판으로 대체한다. 나머지 보호·복귀 조건은 완화하지 않는다. API/Worker/MySQL 중단 후 **무미디어 시작 전부터 full 자원**으로 아래 사전 검사를 실행한다. 기본 인자의legacy gate를 호출하지 않는다.

```sh
python3 -B - <<'PY'
import json, os, shutil
from pathlib import Path
from recording_ec2_host import resource_gate, memory_available
from recording_probe_budget import ProbeBudget, MIB
home = Path(os.environ['PROBE_HOME'])
policy = json.loads(Path('/opt/daesingo/policy.json').read_text())
config = json.loads((home/'source/manifest.json').read_text())['config']
paths = [home/'source', home/'evidence', home/'inputs', Path(config['docker_root'])]
free = min(shutil.disk_usage(p).free for p in paths)
value = resource_gate(policy, memory_available(), free, 0, 0,
    budget=ProbeBudget.from_profile('full15-512m'), output_cap=512*MIB)
print(json.dumps({'status': 'PASS_FULL_RESOURCE_PREFLIGHT', **value}))
PY
```

기대: `PASS_FULL_RESOURCE_PREFLIGHT`, 최소policy일 때start_required_bytes=5028970496. 이0 DBdata 인자는 DB 생성 전 검사에만 해당한다. stage는 새DB 초기화 뒤 실제data와전체증가를 다시 검사한다. 부족하면작은단계부터 시작하지 않고 §7 exact 복귀한다.

```sh
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage acceptance
```

기대: `status=PASS, cleanup=true`, entry `PASS_LINUX_ACCEPTANCE`. 같은 인자에fixture/inputs를 더해 아래를 **하나씩** 실행한다. 앞 단계PASS/cleanup 확인 전 다음 명령을 실행하지 않는다.

```sh
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage smoke \
  --fixture "$PROBE_HOME/fixture" --inputs "$PROBE_HOME/inputs"
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage representative \
  --fixture "$PROBE_HOME/fixture" --inputs "$PROBE_HOME/inputs"
python3 -B "$PROBE_HOME/source/scripts/recording_ec2_host.py" \
  --source "$PROBE_HOME/source" --evidence "$PROBE_HOME/evidence" \
  --owner "$OWNER" --manifest-sha256 "$PROBE_MANIFEST_SHA256" --stage full \
  --fixture "$PROBE_HOME/fixture" --inputs "$PROBE_HOME/inputs"
```

full entry 기대는mode에 따라`PASS_RECORDING_ONLY` 또는`PASS_STOP_BEFORE_SEND`. 후자는sdk_entry_count1·provider0·기존media/request guard 통과를 요구한다. 둘 다full_input_scope=`PASS_ALL_FIFTEEN_EXACT_ENDPOINT`, 15spans·전체source provenance·저장/rollback/새연결detached metadata/hash/length·strict decode·자식process0·temp0·Aborted_clients 불변이 필요하다. 최종full host result도`status=PASS, cleanup=true`여야 한다. 기록/짧은control PASS에서 실제full 성공을 추정하지 않는다.

## 6. 최종 E2E 증거와 유한 운영 예산의 미결 항목

범용 비용 관리 기능을 새로 만들지 않고 **기존 설정과 유한 사용자 동작 수**로 이번 단회 예산을 정한다. 실제 배포 revision/config에서 Search `max_retries=3`·SDK retry0·Runtime `stale_retry_max=1`이 맞는지 먼저 확인한다. Intent는60초, Coarse는150초, Fine은70초의 실행 시계를 갖고 각 job은 기본 최대2execution, execution당 최대4HTTP시도다. 일반 FAILED의 자동재시도가 아니라 STALE 재실행만 이배수에 포함된다. deadline을 금액보장으로 해석하지 않는다. Search retry 수는 현재 dotenv loader가 읽는 env 항목이 아니므로 존재하지 않는 env를 추가하지 않는다.

| 단회 동작 범위 | 기본 설정에서 직접 계산한 조건부 HTTP시도 상한 |
| --- | ---: |
| 최초 Intent1 + Coarse1 + 자동선택 Fine1 | 3jobs × 2execution × 4시도 = **24** |
| 최초 분석1회, 후보3개까지 Fine | (Intent1 + Coarse1 + Fine3) × 2 × 4 = **40** |
| **이번 실험 제안:** 최초 분석1회 + 필요시 설명수정/재검색 중 추가1회, 각 pass의후보3개까지 Fine | (Intent최대2 + Coarse최대2 + Fine최대6) × 2 × 4 = **80** |

위80은 관측 호출수나 사용자 승인값이 아니라 **필요시 수정까지 포함한 유한 운영안**이다. 실행 전에 운영자가 채택할 동작 수를 확정한다. 자동선택 Fine도3개에 포함하며 force-rerun·반복후보전환·추가 설명수정은 허용 수 밖에서 실행하지 않는다. 일반 값의 수동보정은 기존command를 사용하고, Search를 다시 발주하면 남은 pass/Fine 수에 포함한다. 빈 설명이면 Intent가 생략될 수 있지만 비용을 줄이기 위해 의도한 설명을 바꾸지는 않는다. 실제설정이나 다른provider 경로가 다르면 합산범위를 확인해 다시 계산한다. 기존 Runtime의 `DAESINGO_RUNTIME_STALE_RETRY_MAX=0` 선택도 가능하지만 이번 준비에서 운영값을 바꾸지 않는다.

비용은 PM/운영자가 실제 요율·사용량/청구 확인 경로와 허용금액을 실행 전에 정한다. Runtime `cost.amount=None`은 UNKNOWN이며 `max_cost_krw=1000`/`MAX_COST_USD`를 자동차단으로 표현하지 않는다. 허용 동작 소진·실패·비용/사용량 불명 시 **새 provider 호출을 추가하는 command·재실행을 중단**하고 담당자에게 인계한다. 추가 provider 호출이 없는 확인·Export·다운로드는 진행할 수 있다. 이미 전송된 요청의 잔여비용/취소한계도 기록한다. 금액의 자동 hard 보장이 필요하다면 기존 provider credit/quota 제한의 실제 존재·동작을 먼저 확인하고, 없으면 현재 보장할 수 없다고 보고한다. 이를 새 범용 비용관리 개발의 필수조건으로 확대하지 않는다.

| 단계 | 기록할 증거·중단 조건 |
| --- | --- |
| 전체 세션 | 실제release/config/schema·Case·owner·시작/종료시각. 총wall ceiling·채택한Intent/Coarse/Fine job수/시도상한·허용금액·추가실행횟수·중단담당을실행전에확정. 새금액gate 구현을요구하지않고기존설정/동작제한과자동hard금액보장을구분 |
| Upload/범위 | 15요청 결과·15정상 Source·manifest mapping·VIDEO0·timeline revision·actual placements·최종 scope. 암묵적 파일명시각/absolute timeline·gap/overlap·ms floor의 영향 확인 |
| Search/Case | 큐/Recording/prepare/provider/T2 시간을 분리. job/execution/run/usage refs·실제 attempts·token/cost·heartbeat/lease·late 적용 여부. 후보 없음/timeout을 성공으로 바꾸지 않음 |
| 후보/수정 | 실제 후보와 사용자가 확인한 사건 구간, 선택/수정 command와 case_rev·selection basis. 수정을 하지 않았다면 그 사실을 기록 |
| Export/READY | export terminal SUCCEEDED뿐 아니라 T2 반영·현재 selection의 derived_asset_ref·FINAL_PACKAGE PASS/WARN·필수 ReportVideo·ReportPackage 존재. BLOCK/UNKNOWN/과거 selection Package는 실패 |
| 다운로드 | 실제 artifact URL의200·media type/길이/attachment/private-no-store·브라우저 저장 완료·로컬 bytes/hash·strict decode/재생·사건 전후 구간/출처. 서버 metric만으로 client 수신 완료를 주장하지 않음 |
| 자원/종료 | host+runner+DB cgroup peak/CPU/throttled·disk/temp·provider 시도/금액·cleanup/원본 재대조·기존 서비스 복귀. 중첩phase 시간 합산/서로 다른 monotonic clock 차감 금지 |

이번 probe의provider0 예산과 최종 유료E2E의 미확정 예산을 구분한다. #452 품질 회귀 제안의2500원은 별도의15영상 회귀 예산이며 이26분 Case의 금액 상한으로 전용하지 않는다. `max_cost_krw=1000`도 현재 집행 증거가 아니므로 금액 보장으로 쓰지 않는다.

## 7. 실패 복구·보존

| 실패 | 실행 위치·복구 |
| --- | --- |
| 로컬 audit/control | 새 scratch evidence만 보존. 원본/manifest·기존 실패/백업은 변경하지 않는다. 환경 TEMP 오류는 새 basetemp로 해결 |
| package/입력/승인/자원 gate | 새 부하 시작 금지. 운영 중단 전이면 종료, 이미 중단했다면 exact 원래 서비스 복귀 절차로 이동 |
| DB/materialize/strict/Search cap/timeout | 해당owner 전용 실험만 종료. 실패phase·partial bytes·guard·실제 자원/통신을 기록. 자동 예산 확대/재요청 없음 |
| cleanup 실패/Docker timeout | creation-intents의exact owner/name·실제 Running/restart/mount/network 확인. CLI timeout을 부재/정지 증거로 취급하지 않음. 실행 중인 부하와 기존 서비스 동시 시작 금지 |
| 잔여 inert 자원 | 실험 runner/DB/init가 모두 정지·restart=no·운영과 연결 없음·reserve 보존을 입증하면 잔여를 기록하고 운영복귀 우선 가능. 새 실험은 금지 |
| 서비스 복귀 | [기존 runbook §10](2026-11-03-ec2-recording-probe-runbook.md#10-ec2--전용-정리기존-서비스-복귀실패-복구)의exact inspect→원래running 서비스만 MySQL→API→Worker start→120초 유한health/ready/worker-status/deploy-smoke→tuple/pointer/schema/mount/network 재대조. 새revision·migration·recreate를 섞지 않음 |
| lock 해제 | controller/실험 process 종료·복귀 성공·owner/evidence 일치 후 해당 marker만unlink·빈lock만rmdir. 세션 단절/불명/dirty면 담당자 인계, 자동trap unlock 금지 |

보호volume `issue452-capacity-db`, `issue452-chunks-restore-db`, `issue452-chunks-restore2-db`, 원본15개, 공유image/cache는 계속 보존한다. `prune`, 광역삭제, `down -v`, 보호volume의임의접속/복구, daemon/WSL 재시작을 이 작업의 복구 수단으로 사용하지 않는다. 4GiB 미검증 후보는 백업에서 가져와 되살리지 않는다.

## 8. 최초 로컬 검증 결과와 변경 목록

이 절은 최초 준비 세션의 증거다. 600초TIMEOUT의 후속 진단·현재 회귀 결과·범위 정정은 §9에 추가하며, 기존raw/FAIL/PASS 파일을 덮어쓰지 않는다.

| 검사 | 직접 결과·증거 경계 |
| --- | --- |
| 원본 대조 | **PASS**. 처음/마지막 두 번 각각15개 SHA-256/size/mtime/metadata·유일VIDEO0·전체파일집합 일치. 두 audit의files/placements/manifest hash도 동일 |
| focused controls | **PASS 160개**. 새full controls20개와 기존 EC2/budget/recheck/CPU/supervisor/capacity controls. `final-focused.txt`:160 passed in5.59s. 전체 컨테이너 실행 증거 아님 |
| RED→GREEN | 누락된 전체profile/선택/단계 등16실패→구현 후통과. 소수초Decimal/float 비교1실패→수정. 다중VIDEO1실패→수정. 과거RED파일 보존 |
| 로컬 package 구조 | **PASS**. HEAD제품+최종하네스269파일 build/unpack/verify·full module 포함 확인. `final-inert-package`는 실제운영config/image identity가 없는 **실행 불가 구조검증물**이며 운영 전송용이 아님 |
| boundary/계약 | **PASS**. boundary 위반0, 계약문서62/JSON26/의미fixture104 검사 실패0. 첫boundary는cp949 출력UnicodeEncodeError였고`-X utf8`로 재실행. 실패log도 보존 |
| quality/lint | **PASS**. Runtime Ruff 및Linux/Windows mypy 각각89source files 정상. 변경 하네스/새control Ruff PASS |
| 문서·Git·불변 | **PASS**. 표15행/Decimal누적·로컬링크·한글문서 검사, diff whitespace 없음·빈index·지정branch/HEAD. `src/migrations/deploy/compose.yaml/.env.example`와 기존#561 결과문서 diff0 |
| 비-MySQL 회귀 | **확인 필요:600초 TIMEOUT**. 전체비-MySQL partition 실행을 시도했지만 pytest 결과·JUnit을 확보하지 못했다. stdout0B, 원인UNKNOWN. 새`regression.txt`/`regression-timeout.private.json` 보존. PASS나테스트실패건수로 바꾸지 않음. focused 결과와 합산하지 않음 |
| 전체Linux/운영 | **NOT_RUN**. 실제26분 encode/DB/Search·AWS/SSM·전송·서비스중단·실제provider·배포·Case/Web/READY/download. Docker를 호출하지 않았으므로 보호volume의현재존재 직접조회도NOT_RUN이며 변경작업 없음 |

실행 로그·두 실제입력 audit·기존manifest hash·GitHub 읽기snapshot·구조검증package는 `.codex-scratch/full15-local-20261104/`에 보존한다. 첫pytest는 sandbox TEMP/cache 접근 오류가 있어 새basetemp와cache 비활성화로 재실행했다. 이를 제품실패로 해석하지 않는다. 미검증4GiB후보 backup·이전OOM/Docker/정리실패 기록은 그대로 보존했다.

비-MySQL 회귀 명령은 위focused 명령과 같은interpreter로 `-B -X utf8 -m pytest tests --ignore=tests/common/db/integration/test_migration_gate.py --ignore=tests/recording/test_ci_media_smoke.py -m "not mysql" -q -p no:cacheprovider --basetemp=<새 scratch> --junitxml=<새 scratch/regression.xml> --tb=short`를 실행하고, 부모subprocess에600초 timeout을 적용했다. timeout 후 시스템CIM 조회는sandbox에서 허용되지 않았고 로컬psutil도 없어 보조process 진단을 완료하지 못했다. 추가설치·시스템권한변경·daemon조작은 하지 않았다. 회귀완료와Linux sampler의실제연결 검증은 후속으로 남긴다.

| 변경 파일 전체(11개) | 역할 |
| --- | --- |
| `scripts/recording_full_input.py` (신규) | 15개 순서/집합/hash/stat/metadata·유일VIDEO0·정확끝점 검증, 보호계획 생성 |
| `scripts/recording_probe_budget.py` | full15 결속유한profile |
| `scripts/recording_real_media_recheck.py` | 전체15개 선택·정확endpoint·소수초coverage·무료Search observer 연결 |
| `scripts/recording_ec2_host.py` | full stage·전용예산·입력15개·actual abort marker 감시 |
| `scripts/recording_ec2_entry.py` | full scope·runner실제limit·기존정확성검증/무료Search sentinel 배선 |
| `scripts/recording_ec2_package.py` | 신규full module을기존allowlist package에 포함 |
| `scripts/recording_cpu_quota_supervisor.py` | DBdata감시가선택profile 상한을사용. legacy값은동일 |
| `tests/runtime/test_recording_full_input.py` (신규) | prefix/순서/변조/VIDEO/소수초/단계/예산/원본불변 controls20개 |
| `scripts/README.md` | 신규도구·전체준비runbook 안내 |
| `docs/superpowers/plans/2026-11-04-full15-local-preparation.md` (신규) | 범위·설계·구현/검토 기록 |
| `docs/runtime/experiments/2026-11-04-full15-e2e-preparation-runbook.md` (신규) | 조건표·Owner미결·예산·위치/명령/기대/복구·최종증거 |

**최종 목표는 기존 EC2의 실제15개 전체 Package READY·다운로드다.** 남은 주요답변은 Case대기/late 정책과 Search270p 품질채택이다. 실제배포 reader/rollback·전체크기/자원·Web업로드순서는 운영 실행조건으로 확인한다. 기존설정에기반한유한시도예산은 §6으로 구체화했고, 0.332ms는관측한마지막frame을제외하지않으므로별도새RC blocker가아니다. 실제26분전체E2E·Package READY·다운로드는 NOT_RUN이다. commit/staging/push/PR/외부댓글은 하지 않았다.

## 9. 후속 진단·검토 결과 — 기존 증거 보존

후속 증거는 `.codex-scratch/full15-followup-20261104/`에 새로 저장했다. 최초600초 실행·원본 manifest·기존120초EC2 결과·4GiB후보 백업을 덮어쓰지 않았다. 이번 후속에서 바꾼 공개 파일은 **본 runbook과 준비 계획 두 문서뿐**이다. 7개Python 실행파일은 기존 로컬검증package의269파일 hash와 모두 같고, 새실행물/새이미지를 만들지 않았다. 처음11개 변경의 전체목록은 §8을 유지한다.

### 9.1 600초 TIMEOUT 분류

| 질문 | 확인한 결과 |
| --- | --- |
| 실패 assertion이었나 | 최초실행은stdout0B/stack없음이므로 당시assertion을확정할수없다. 동일환경 첫테스트를좁힌재현에서는setup PASS 뒤 `TestClient.__enter__`에서멈췄고assertion 실패가아니었다 |
| 수집/느린 계산인가 | 비-MySQL14475개 수집은수정한진단기준12.77초에완료. 최소재현은CPU약1.7초 뒤30초동안socket대기. 정상적인긴계산이라는근거는없음 |
| 멈춘 자식인가 | 중첩Python시작/pytest import control은0.516초에정상종료. 멈춘재현의stack은별도provider/ffmpeg자식이아닌TestClient의AnyIO thread→Windows asyncio→`socket._fallback_socketpair`의`accept()`였다 |
| 환경 차이가있는가 | 표준라이브러리 `asyncio.run(asyncio.sleep(0))`만으로도sandbox에서8초대기재현. 같은첫API테스트는호스트문맥에서call0.186초로PASS. **[추론] 최초600초도같은첫테스트/환경의socketpair대기로설명하는것이관측과일치**하나당시stack이없어소급직접관측으로표현하지않음 |
| 자원 부족인가 | 호스트조회시총가시RAM16281024KiB/가용2904352KiB. 이는최초timeout시점값이아님. 재현stack에서allocation/OOM/CPU포화는확인되지않았고호스트문맥변경만으로통과. 자원부족을원인으로확정하지않음 |
| 잔존 프로세스인가 | 최초호스트조회에서Python전체0개·이전실행고유경로일치0개. 종료후에도이번고유경로와일치하는Python/ffprobe잔존0개. 다른작업은종료하지않음 |

API의합성server 종료control(`tests/api/test_process_safety.py:513`)은설정root로작업디렉터리를사용해0B `.runtime-cleanup-{orphan,staging,temp}.lock`3개를만들었다. 시작Git상태에는없었고생성시각은해당API실행중이었다. 모든테스트종료뒤정확한이름·0B·생성시각을확인하고, 세파일의read/write배타handle을모두획득한상태에서같은workspace의새scratch로 **이동 보존**했다. active handle이있으면이동하지않는조건이며다른운영lock/서비스는건드리지않았다. 최종Git변경목록은기존11개다.

진단과정의첫collection plugin에는`session.items()` 오타가있어수집종료hook 오류가났다. scratch 진단기만수정하고원본진단log를보존했으며, 수정판은14475개수집/exit0을확인했다. 제품/테스트소스의오류로분류하지않는다.

### 9.2 필요한 회귀 실행과 남은 실패

timeout을늘리지않고원인을좁힌뒤호스트문맥에서API와나머지partition을나눠실행했다. 각테스트진단상한30초·나머지partition전체상한600초를유지했고실제완료는572.84초였다. `-m "not mysql"`, 기존migration gate/전용media smoke 제외는canonical 정의와같다. 실제AWS·DB서비스·provider 호출을사용하는검증은실행하지않았다.

| 검사 | 직접 결과 |
| --- | --- |
| API partition | **239 PASS**, 248 deselected, 98.24초 |
| 나머지 partition | **14192 PASS / 22 FAIL / 26 SKIP**, 1003 deselected, 569.04초.26skip은22개선택node와typer미설치collection module4개를포함 |
| 전체 선택 대조 | **PASS**.14475개선택node를모두시작/정산, 누락0·중복0. API+나머지JUnit/progress와별도collection inventory를대조 |
| 합계 | **14431 PASS / 22 FAIL / 26 SKIP**. 전체회귀를PASS로보고하지않음 |
| 이번full 하네스관련7개test파일 | 같은회귀에서 **160 PASS**, 그중신규full controls20 PASS. 앞세션160PASS와중복합산하지않음 |
| 청크 실패단독/모듈 | 실패했던`test_detached_file_validates_manifest_and_cleans_failures[None]` 단독1 PASS, 인접청크모듈18 PASS. 원래회귀실패를지우지않음 |

21개실패는 `tests/deploy/test_ec2_deploy.py`의테스트용symlink생성에서 **WinError1314(권한없음)**이다. 하나를분리재현했고제품transition의성공/실패assertion에도달하기전실패했다. 이파일·deploy제품코드는이번변경에없다. 이미실행중인WSL환경도없어서비스를시작하거나Windows권한/정책을변경해통과시키지않았다. **symlink를지원하는기존검증환경에서해당21개를재실행할조건이남는다.** skip/가짜link로대체하지않았다.

나머지1개는 `tests/recording/test_chunked_media.py:79`의close직후파일부재assertion이다. 원래실행에서도stream.closed검사는통과했고, 사후8개관련임시폴더잔여는모두0개였다. product `detached_stream`과표준 `TemporaryFile`을합성파일로각200회비교해모든stream이닫혔고, product즉시잔여0/200·stdlib즉시잔여1/200(관측중사라짐)이었다. **[추론] Windows delete-pending/외부handle의일시적관측과일관**되지만원래실패시점의파일/handle을직접잡지못했으므로최종원인은확정하지않는다. 모듈재실행PASS만으로원래실패를PASS로덮지않으며제품cleanup/strict/테스트허용오차를바꾸지않는다.

재현명령의위치는레포루트이며asyncio/TestClient검사는sandbox가아닌일반호스트문맥이다. 예를들어 `.venv\Scripts\python.exe -B -X utf8 -u -m pytest tests/api/test_api_cleanup.py::test_api_lifespan_scans_once_and_closes_background_thread -vv -p no:cacheprovider --basetemp <새scratch> --junitxml <새report>`로첫테스트를확인한다. 실패시새log/stack을보존하고전체회귀를즉시반복하지않는다. 실제사용명령·진행node·시간/CPU·JUnit·실패목록은새scratch의`*-progress.private.jsonl`, `*-stack.private.txt`, `api-host.xml`, `nonapi-host.xml`, `failures.private.json`, `partition-coverage.private.json`에있다.

### 9.3 지금 수정할 것과 Owner 답변 구분

| 구분 | 이번 판단·다음 조건 |
| --- | --- |
| 지금 해결한 부분 | timeout을환경socketpair대기로좁히고회귀실행완료. runbook의목표대체/범용비용gate/0.332ms새blocker해석을수정. 이진단을이유로제품코드를바꿀근거는없음 |
| 재현확인 남음 | Windows symlink환경21개, 청크close직후관측1개. 실패이력을보존하고지원환경/같은assertion으로확인. 현재전체회귀는green아님 |
| Search Owner | 270p·CRF28 품질회귀결과·채택설정, 실제1584초전체의source/media/request cap·유한Searchdeadline을충족할준비방식. 1200초성공을전체로확대하지않음 |
| Case Owner | 긴준비동안180초에STOPPED_WAITING/late NOT_APPLIED되지않도록하는유한대기·완료반영정책. **180초성능최적화요청이아님**. 답변후필요한Case/Runtime/Web변경범위를확정 |
| 운영설정/준비 | 기존EC2actual revision/image/config/schema/양방향reader·rollback/데이터보존·자원·기존제한기반허용동작/금액확인. 새범용비용관리기능은요구하지않음 |
| 기존증거와새재검증 | #561의857423c…패키지120초PASS는그대로보존. 현재하네스/frozen package·운영config/image조합의EC2무미디어→10초→120초→전체검증은별도이며NOT_RUN. 운영자에게기존실측이없었던것처럼재측정하라고하지않되다른실행물의PASS로대체하지않음 |
| 0.332ms | 기존계약·실제마지막frame관측상제외frame없음. 새RC blocker/새정책대기대상으로삼지않음. 실제전체encode/strict/READY/download는여전히별도 |

기존EC2목표·0.332ms·유한호출예산문구는읽기전용독립검토후보완했다. 후속에서도AWS/전송/서비스중단/provider/배포/commit/push/게시를하지않았다.

### 9.4 원래 회귀에서 실패한 node 목록

```text
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[preflight]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[quiesce]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[mysql]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[packet]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[migrate]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[start]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[health]
tests/deploy/test_ec2_deploy.py::test_failures_do_not_promote_known_good[smoke]
tests/deploy/test_ec2_deploy.py::test_success_promotes_only_after_all_checks
tests/deploy/test_ec2_deploy.py::test_rollback_exact_record_and_schema_approval_no_migration
tests/deploy/test_ec2_deploy.py::test_rollback_unknown_config_or_digest_rejected[mutation0]
tests/deploy/test_ec2_deploy.py::test_rollback_unknown_config_or_digest_rejected[mutation1]
tests/deploy/test_ec2_deploy.py::test_rollback_cannot_replace_applied_schema_compatibility[False]
tests/deploy/test_ec2_deploy.py::test_rollback_cannot_replace_applied_schema_compatibility[True]
tests/deploy/test_ec2_deploy.py::test_promotion_interrupt_blocks_both_operations[pointer]
tests/deploy/test_ec2_deploy.py::test_promotion_interrupt_blocks_both_operations[previous]
tests/deploy/test_ec2_deploy.py::test_promotion_interrupt_blocks_both_operations[current]
tests/deploy/test_ec2_deploy.py::test_promotion_interrupt_blocks_both_operations[dirty]
tests/deploy/test_ec2_deploy.py::test_success_switches_web_and_rollback_together
tests/deploy/test_ec2_deploy.py::test_deleted_dirty_cannot_hide_pointer_mismatch
tests/deploy/test_ec2_deploy.py::test_process_exit_after_pointer_keeps_dirty_and_lock
tests/recording/test_chunked_media.py::test_detached_file_validates_manifest_and_cleans_failures[None]
```


## 10. PR 준비 — 실패 22개 Linux 재확인과 fresh review

이 절은 §8·§9 이후의 별도 실행이다. 과거 기록의 “새 실행물 없음”, “Linux 재확인 남음”, “서비스 시작 없음”은 당시 사실이며 현재 상태는 아래를 따른다. Windows 전체 회귀의 **14431 PASS / 22 FAIL / 26 SKIP**와 최초 600초 TIMEOUT은 보존한다. 이번에 전체 비-MySQL 회귀를 반복하지 않았고, Linux 22 PASS를 더해 원래 전체 회귀를 PASS로 바꾸지 않는다.

### 10.1 Linux 환경·유한 예산·직접 결과

설치된 Ubuntu WSL과 Docker Desktop의 기존 Linux 검증 환경을 시작했다. 운영 서비스 중단/재시작은 하지 않았다. 기존 캐시 이미지 `sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`(Python 3.12.16)를 `--pull=never`로 사용했다. 이미지 build/pull·패키지 네트워크 설치는 없다. 이미지에 pytest가 없어 Windows venv의 pytest 8.4.2 및 순수 Python 의존성을 새 scratch에 복사하고 파일별 hash를 남겨 read-only로 연결했다. 원본 영상·비공개 설정·DB·보호 volume은 연결하지 않았다.

| 항목 | 실제 제한·검증 |
| --- | --- |
| 사전 자원 gate | 기존 legacy 예산 사용: host available 시작 ≥3004MiB, C: free ≥6GiB·실행 중 reserve 4GiB. 부족하면 override 없이 종료 |
| runner | CPU 2·cpuset 0,1·RAM hard1280MiB/soft1100MiB·swap0·pids128·uid10001·rootfs read-only·cap-drop ALL·no-new-privileges·network none·포트 없음. 실제 inspect와 cgroup 대조 |
| 공간/시간 | 전용 work soft512MiB·tmpfs96MiB·로그1MiB×2·Docker capture8MiB/stream. runner180초/host210초/cleanup 별도60초. 전체 영상용 full 예산을 이 작은 검사에 적용하지 않음 |
| 정확한 22개 | §9.4 node 목록과 원래 실패 progress에서 추출한 목록을 순서까지 exact 대조. **22 PASS / 0 FAIL / 0 SKIP, 5.13초**. symlink21개와 detached cleanup1개 포함. 원래 테스트 파일·assertion·strict·skip 기준 변경 없음 |
| 자원 관측 | runner cgroup peak **79798272B**, work 최대51036B. OOMKilled false·restart0·OOM events0. 각 start/setup/call/teardown 경계와 종료 시 관측된 자식0개. 종료 후 sampler도 정지 |
| 정리/보존 | 해당 실행의 label/name이 일치하는 새 container2개와 work volume1개만 정리. 보호 volume3개 inspect 전후 동일. 공유 image/cache·다른 작업은 제거하지 않음. 환경 daemon은 남겨 둠 |
| 새 하네스 controls Linux | 리뷰 후 추가한 JSON 정상/cap rejection 및 로그 보존3개만 별도 실행: **3 PASS / 0 FAIL / 0 SKIP, 2.99초**, peak92639232B. 동일 제한·정리·보호 volume 보존 PASS |

격리 환경 준비 실패도 보존한다. 첫 runner는 exit1/OOM false였으나 init 로그 덮어쓰기로 runner 오류 로그를 잃어 직접 원인을 확정하지 못했다. 두 번째는 수집 전 `py` shim 누락, 세 번째는 read-only mount에서 공개 Recording mock fixture 디렉터리 누락으로 수집 실패했다. 로컬 `py.py`와 `data/mock/recording` read-only mount를 보완한 네 번째 실행에서 정확한 22개를 수집·실행했다. 이 준비 오류들을 제품 assertion 실패로 세지 않는다. 기존 실패 로그를 덮어쓰거나 삭제하지 않았다.

실행 위치는 Windows 레포 루트다. 이번 실제 감독 명령은 다음과 같고, 내부에서 위 Linux 컨테이너를 사용했다. 스크립트·node 선택·도구 hash·raw inspect·resource samples·JUnit은 **로컬 증거**이며 배포 package나 PR에 포함하지 않는다.

```powershell
.venv\Scripts\python.exe -B -X utf8 .codex-scratch/full15-pr-ready-20261104/run_linux22_attempt4.py
.venv\Scripts\python.exe -B -X utf8 .codex-scratch/full15-pr-ready-20261104/run_linux3.py
```

기대 출력은 각각 status PASS, passed22/3, failed0, skipped0, cleanup true, protected_volumes_unchanged true다. 이미 닫힌 시도는 재사용하지 않는다. 후속 진단이 필요하면 새 evidence 폴더·새 owner를 만들고 현재 자원 gate부터 확인한다. 실패 시 raw inspect/log/JUnit을 먼저 남기고 소유 label·정확한 이름을 확인한 이번 자원만 유한 정리한다. 보호 volume·공유 image/cache를 지우거나 다른 프로세스를 종료해 여유를 만들지 않는다. 증거 경로는 `full15-pr-ready-20261104/linux22-attempt4` 및 `linux-newcontrols`다.

### 10.2 원래 Windows cleanup 실패 조사와 한계

독립 검토자가 원래 progress·테스트·제품·실행 interpreter의 stdlib를 읽기 전용으로 대조했다. 직전 8개는 tail-policy 실패검증 mutation→retry→timeout, incident strict, packet DTS, multi-span False→True, chunk metadata lookup 순서였고 모두 call/teardown PASS다. 마지막 metadata lookup 후 문제의 `[None]`에서 stream read/seek/closed는 통과하고 `not any(p.exists() for p in tmp_path.iterdir())`만 실패했다. 단순 디렉터리 열거의 오래된 이름만으로 이 `exists()` 결과를 설명할 수 없다.

- `test_analysis_tail_policy.py:173–176,196–197,240–242`의 monkeypatch는 materializer 인스턴스 메서드에 한정된다. 직전8개에는 전역 tempfile/TemporaryFile/subprocess.run 교체가 없고 함수별 fixture는 undo한다. 원래 전체 세션의 객체 identity snapshot은 없어 공유 상태가 전부 정상이었다고 소급 확정하지 않는다.
- `[timeout]`은 같은 파일156행에서 호출 전에 합성 TimeoutExpired를 던져 해당 fallback ffmpeg를 시작하지 않는다. 실제 fixture ffmpeg는 `test_local_analysis_source.py:31–37`, `test_multi_span_analysis_source.py:17–21`의 동기 subprocess.run이다.
- 제품 `materialization.py:97–103`, `analysis_process.py:49–55`에는 동기 실행 또는 finally kill/wait/reader join/stderr close 경로가 있다. 실패 테스트 자체는 subprocess를 시작하지 않고 `chunked_media.py:58`에서 새 tmp_path에 TemporaryFile을 만든다. 앞선 ffmpeg가 이 나중 파일 handle을 소유했다는 근거는 없다.
- 원래 tracer는 PID/handle/file identity를 수집하지 않았다. 종료 후 task process0·사후 잔여0, 단독/모듈 PASS, 이번 Linux 경계별 자식0은 **원래 실패 시점의 자식/handle 부재 증명은 아니다**. Windows TemporaryFile의 O_TEMPORARY 경로와 별도 stdlib 일시 잔여 관측으로 delete-pending/외부 handle 가설은 가능하지만 **원인 미확정**으로 유지한다.

따라서 제품 cleanup 변경·assertion 완화·새 skip으로 처리할 근거는 확보하지 못했다. Linux의 해당 node는 원래 assertion 그대로 PASS했고, 원래 Windows 실패 이력은 그대로 남는다.

### 10.3 fresh review 지적 처리·현재 실행물

전체11개 변경을 구현 세션 이력을 주지 않은 독립 reviewer가 읽었다. 지적한 P2는 CPU journal이 연결된 Coarse 송신 직전 계측에서 전역 `json.dumps` 변경→journal append→같은 hook 재진입으로 RecursionError가 나는 하네스 결함이다. **두 control RED→GREEN**으로 확인하고 `provider.json` 참조만 임시 대체·finally 복원하도록 최소 수정했다. request bytes cap/SDK 진입 차단은 유지한다.

Linux 준비 중 별도로 확인한 supervisor init→runner 로그 덮어쓰기도 container 역할별 파일명으로 최소 수정했다. 보존 control에서 runner 로그가 init 값으로 바뀌는 assertion RED를 확인한 뒤 GREEN, 실제 Linux 새 controls 정리에서도 init/runner 로그가 별도 보존됐다. 이 하네스 진단 결함은 원래 Recording detached cleanup 실패의 원인으로 주장하지 않는다. 제품 src/deploy/계약/운영설정 변경은 없다.

| 직접 검사 | 최종 결과·기존 증거와의 구분 |
| --- | --- |
| 관련7개 test 파일 | **163 PASS, 7.29초**. 기존160 + 새 JSON2/로그1. 새 full controls23개. 이전160/전체회귀 결과와 중복 합산하지 않음 |
| 변경 Python8개 ruff | **PASS** |
| boundaries / contract fixtures | **PASS**, 경계 위반0 / 의미 검사104개 실패0. Owner 수락·E2E 증거 아님 |
| 원본 최종 대조 | **PASS_INPUT_AUDIT**, 실제15개 hash/size/mtime/metadata·기존 manifest 대조, 전체1584.173332초·1771439266B. 촬영 연속성 UNKNOWN 유지 |
| 새 로컬 package | **PASS_LOCAL_PACKAGE_INTEGRITY**,269파일 build/unpack/exact hash. manifest SHA-256 `7db25e3c338f2c08941901b37da50e9041102684ae15021dbe63b0a04ece27ac`. 실제운영 config/image identity 없는 실행 불가 구조검증물 |
| 기존 package | §8의269파일 package는 보존. 이번 두 하네스 수정 때문에 현재 실행물과 다르며 “최종 hash 일치”로 재사용하지 않음. #561의 기존120초 EC2 PASS도 원래 revision 근거로 보존 |
| 독립 최종 재확인 / Git | reviewer가 JSON·로그 수정/control·결과 문구를 다시 읽고 추가 actionable 결함 없음으로 보고. `git diff --check` PASS·index 비어 있음·11개 미staging. 해당 실행 container/volume 잔존0·작업 식별 process0, 다른 작업 종료 없음 |
| 실제 전체 E2E | **NOT_RUN**. AWS/SSM·외부전송·서비스중단·실제provider·제품배포·commit/push/게시 없음. 실제26분 encode·Package READY·다운로드 없음 |

새 package에 대한 acceptance→10초→120초→full의 운영 환경 재검증은 유지한다. 이미 확보한 이전 revision 실측을 지우거나 새 package의 실측으로 바꾸지 않는다. 리뷰 수정으로 provider 호출 예산·Case 시간계약·strict tolerance를 변경하지 않았다.

### 10.4 다음 운영자 실행 순서

1. 이 PR 준비 결과·새 실행물 identity를 검토한다. 원래 Windows 전체 회귀는 green이 아니며, Linux22 재확인은 별도 PASS로 정산한다. 필요 시 Windows cleanup 실패는 당시보다 상세한 handle/PID 계측으로 좁혀 조사하고 전체 회귀를 반복하지 않는다.
2. Search Owner에게 전체 source/media/request cap·270p CRF28 품질/채택·유한 deadline, Case Owner에게 180초 성능목표와 별개인 유한 대기/late 반영 정책 답변을 받는다. 기존 retry/STALE/SDK 제한·사용자 동작 수·실제 요율/허용금액으로 provider 예산을 확정한다. 범용 비용관리 구현을 추가하지 않는다.
3. §5의 읽기 전용 운영 조사로 기존 EC2의 actual revision/image/config/schema/reader·rollback·데이터/자원 조건을 확인한다. 미결 Owner 정책을 기다리며 운영을 중단하지 않는다.
4. 실제 확인값으로 새 frozen package/config/입력 identity를 만들고 §5·§7의 점검 승인·복귀 조건 아래 무미디어→10초→120초→15개 전체 provider0 probe를 실행한다. 새 package의 실제 Linux 계측·strict·청크 새 연결 조회/정리를 재검증한다. 실패는 보존하고 유한 중단/복귀한다.
5. 확정된 제품 정책과 배포/복귀 조건으로 기존 EC2에서 실제15개 Upload·성공수15→Search/Case→후보 확인/필요 시 수정→Export→Package READY→다운로드를 수행한다. 마지막 파일 bytes/hash/decode/coverage·출처를 확인해야 전체완주 PASS다. 20분 절단·다른 환경 준비·단계별 짧은 PASS로 대체하지 않는다.

§10의 모든 scratch는 로컬 비공개 증거다. PR에는 §8의11개 공개 변경만 제시하며 index는 비워 둔다.
