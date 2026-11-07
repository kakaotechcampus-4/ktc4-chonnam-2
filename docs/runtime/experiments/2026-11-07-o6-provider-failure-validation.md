# O6 provider 실패 연결 검증 — 2026-11-07

로컬 fake provider로 일시 실패 후 성공, 재시도 횟수 소진, 시간 상한 소진의 Worker·Case 연결을 검증했다. 제품 정책을 변경하는 문서가 아니라 실행 근거다.

## 실행 식별과 증거 범위

| 항목 | 확인 결과 |
| --- | --- |
| 실행 브랜치 | `codex/o6-provider-failure-evidence` |
| 실행 HEAD / 기준 배포 SHA | `70f1c47cbc7c08fa848d057687f7130047f1126c` |
| 정확한 실행 소스 | 위 HEAD + 미커밋 시험 파일 2개. 아래 시험 bytes·patch hash로 구분한다. 제품 소스는 배포 SHA와 동일 |
| 제품 동일성 | src/apps/migrations·설정/의존성 파일의 Git diff 없음. 핵심 제품 파일 18개는 배포 blob과 bytes 동일도 확인 |
| 유효 정책 | Search max_retries=3, retry_base_sec=5.0, Case scope max_latency_sec=600.0. SDK 내부 retry=0 |
| 환경 | Windows Python 3.12.14, OpenAI SDK 2.54.0, pytest 8.4.2, SQLAlchemy 2.1.3, MySQL 8.4.13, Node 24.11.1, Vitest 5.0.0 |

운영 설정·설치 의존성·실제 provider의 동일성은 미검증이다. 실제 provider·AWS·운영 서버를 호출하지 않았다. 입력은 기존 fixture가 만드는 1초·64×48 합성 영상이며 실영상 전체 E2E가 아니다.

## 주입과 연결

기존 `worker_peer`와 `test_public_api_worker_search_t1_t2_across_processes`를 재사용했다.

- [process helper](../../../tests/e2e_runtime/production_processes.py): 기존 scenario의 max_retries=0 시험 설정을 유지한다. 새 provider_* 3종만 그 덮어쓰기를 생략해 기존 정책을 그대로 적용한다.
- fake는 실제 SDK에 주입한 httpx.MockTransport의 HTTP 503/200 응답이다. trust_env=False로 환경 proxy도 사용하지 않는다. 실제 provider 함수·Worker handler·Case 반영기를 성공/실패 stub으로 대체하지 않는다.
- deadline만 실제 factory가 만든 SearchService의 기존 monotonic 주입 지점을 사용한다. 두 번째 fake 503에서 해당 요청의 남은 timeout+0.001초만 시계에 더한다. retry sleep·Worker heartbeat/lease·DB 시계는 실제 시간을 따른다.
- [process test](../../../tests/e2e_runtime/test_production_search_process_mysql.py)는 호출 수·간격·남은 SDK timeout·HandlerResult·JobExecution·produced AnalysisRun·case_applied_at·Case processed_executions/settled_jobs·공개 CaseView를 함께 검사한다.
- API와 Worker는 별도 OS 프로세스다. API 프로세스 안의 HTTP 입구는 기존 FastAPI TestClient다. 별도 TCP HTTP 서버나 실제 브라우저 E2E는 아니다.

## 경로별 관측

호출 수는 COARSE_SEARCH transport 호출 수다. 세 경로 모두 JobExecution attempt=1이다. provider 내부 retry와 Worker redelivery를 구분한다.

| scenario | 응답 / 호출 수 | 관측 호출 간격 | 최종 Job / AnalysisRun | Case 결과 |
| --- | --- | --- | --- | --- |
| provider_retry_success | 503 → 200 / **2회** | 5.094초 | SUCCEEDED / SUCCEEDED | T2 반영, 후보 1개, coarse DONE, 실패 notice 없음, EVIDENCE_REVIEW. 후속 Fine도 별도 HTTP 1회로 SUCCEEDED·T2 반영 |
| provider_retry_exhausted | 503 × 4 / **4회** | 5.062 / 10.063 / 20.062초, 실제 대기 | FAILED / SEARCH_PROVIDER_ERROR, AnalysisRun FAILED·PROVIDER_CALL_FAILED | T2 반영, 후보 없음, coarse FAILED, running_jobs 없음, SEARCHING, 실패 notice·RETRY_SEARCH |
| provider_deadline_exhausted | 503 × 2 / **2회**, 세 번째 호출 없음 | 5.063초 실제 대기 후 592.283초 시계 진행 | FAILED / SEARCH_DEADLINE_EXCEEDED, AnalysisRun FAILED·RUN_DEADLINE_EXCEEDED | 위와 동일한 실패 안내·사용자 retry 출구 |

남은 SDK timeout은 횟수 소진에서 599.563 → 592.516 → 582.453 → 562.391초, 시간 상한 모사에서 599.500 → 592.282초였다. **횟수 소진 실행이 600초도 소진했다는 뜻은 아니다. 시간 상한은 600초 설정을 유지한 시계 모사이며 실제 600초 wall 대기·실네트워크 timeout 측정이 아니다.**

두 실패의 공개 CaseView는 아래 notice를 반환했다.

```json
{"code":"search.candidate_search_failed","severity":"ERROR","blocking":true,"message_key":"notice.candidate_search_failed","actions":["RETRY_SEARCH"]}
```

실제 API에 RUN_NOTICE_ACTION/RETRY_SEARCH를 보내 두 경로 모두 HTTP 202와 다른 job_id의 COARSE_SEARCH를 받았다. DB는 기존 FAILED + 새 QUEUED였다. 새 Job은 실행하지 않았다. 새 CaseView는 중복 retry action을 숨긴다. 이 사용자 요청을 자동 provider retry 횟수에 더하지 않는다.

같은 CaseView와 실제 retry 응답을 소비한 별도 jsdom 시험은 실제 ApiFlow/createApi에서 SEARCH_FAILED 선택, “장면을 찾는 중에 문제가 생겼어요.”, 활성 “다시 찾기”·“처음으로” 버튼을 확인했다. 다시 찾기 POST는 실제 API가 수락한 payload와 일치하고, 기록된 202 응답을 적용하면 PROGRESS·“분석 중단”으로 이동한다. FailedScreen의 “처음으로” callback 1회도 확인했다. **location.assign에 의한 브라우저 이동·새 페이지 로드는 미검증이다.**

## 11 PASS의 정확한 범위

| 묶음 | 개수 | 실행 node / 경계 |
| --- | --- | --- |
| 기존 helper contract | 2 | test_worker_peer_forwards_composition_logger_and_stops_after_dispatch[False/True] |
| 기존 provider bounds | 3 | test_429_status_code_retries, test_5xx_status_code_retries, test_retry_stops_when_run_deadline_exhausted_between_attempts |
| 기존 Case notice | 1 | test_failed_search_view_shows_failure_not_no_result |
| 새 process 연결 | 3 | test_public_api_worker_search_t1_t2_across_processes[provider_retry_success/provider_retry_exhausted/provider_deadline_exhausted] |
| recorded-response jsdom | 2 | 위 두 실패 CaseView의 notice·실제 createApi payload·retry 응답 적용·home callback |

11개는 한 pytest 실행의 수가 아니다. helper/provider/Case 6개와 process 3개, jsdom 2개의 서로 다른 실행이다. baseline 6개와 보완 후 동일 6개를 중복 합산하지 않는다. process 3개 실행은 110.96초였고 기존 8개 scenario가 deselected였다.

### PR 준비 중 추가 회귀

공통 helper의 기존 process scenario **8 PASS / 실패·오류·skip 0**, 새 provider 3개 deselected. JUnit suite 시간 214.834초. 기존 11개와 구분한 추가 회귀다. 전체 E2E·Worker kill은 반복하지 않았다.

대상: `normal`, `partial`, `failed`, `fine_failed`, `hint`, `clip`, `clip_fractional`, `clip_multisource`.

## 무결성 보존

ignored 원시 결과의 핵심 관측과 재현 절차는 이 문서에 실었다. 아래 SHA-256은 로컬 원시 파일과 대응하는 무결성 식별값이며, hash만으로 내용을 독립 검증했다는 의미는 아니다. 새 실행은 UUID·PID·시각 때문에 같은 hash가 나오지 않는다.

원래 시험 2개와 ignored 증거 33개를 별도 snapshot에 bytes 그대로 보존하고 기존 manifest의 모든 entry를 다시 검증했다. 원본 manifest 자체의 SHA-256은 다음과 같다.

`51e3245dc72ba1b67413ceae4786ea65d06cfc5d622e036a9d1ba9e5f09446ba`

| 파일 | SHA-256 |
| --- | --- |
| `tests/e2e_runtime/production_processes.py` | `1786f318d51529142064b7d9ca92bd24ed4740784038e2932bb49a01663df3e9` |
| `tests/e2e_runtime/test_production_search_process_mysql.py` | `41cc859fae92130e7e6f746d9a0b94c9e33f15ef8fbf5363dff186247baa7176` |
| `test-harness.patch` | `ca066990af188981c98df20a72519f00b6817c76a3681e1ade34154a2dfaf767` |
| `verified.xml` | `014585dc99cdae3ad74992ac39f18a8c93a6a41efee22e52d7dc6251a575be11` |
| `helper-regression.xml` | `3ed3e94dabb466a43f1315f73854d176cdaba65118ca0a7fa4b3d6aa1860d01c` |
| `web-verified.xml` | `1a3d03625c63dab46b6c0f01ae28881c01082002b70c8303507cace3a2e1d87a` |
| `provider_retry_success.json` | `f3ea97e0dd47100b5deccfd6f228d954d8f083dcf189cc2a2768af1b76a113f5` |
| `provider_retry_exhausted.json` | `3deed612401cc40df05e527599737ee7d2da61f4910b395805335b3ee4f7896d` |
| `provider_deadline_exhausted.json` | `b7de39549e3a78d5e35235dcd9141d2083000d59c58bfa78b1de50e01bae9060` |
| `legacy8.xml` | `a2c91b93a84ddb9041e3d1e88cb33efa5e22f541043a6c649c30b9c2d52ca42a` |
| `legacy8-mysql.json` | `2d5b632cd1e284da7e9775397bfba4034812c00df2e54dc2978935679546fe2f` |
| `legacy8.log` | `543f93bf430c61348e8d212b7bc98e0cc14bb175b44d09599d469294936c21d6` |

## 재현: backend와 기존 8개 회귀

저장소 checkout과 Python 의존성, ffmpeg/ffprobe, 테스트 전용 MySQL 8.4가 필요하다. DAESINGO_MYSQL_URL은 **새 disposable 로컬 DB**를 지정하고 이름에 test를 포함해야 한다. harness는 시험별 schema를 생성·삭제한다. 운영·공유 DB를 사용하지 않는다. 정책·assertion을 바꾸지 않는다.

아래는 저장소 루트의 PowerShell 예시다. `$o6DbUrl`에는 준비한 로컬 테스트 DB URL을 넣는다. `.codex-scratch/o6-provider-repro`는 새 경로로 만들고 기존 증거를 덮어쓰지 않는다.

```powershell
$env:DAESINGO_REQUIRE_MYSQL='1'
$env:DAESINGO_MYSQL_URL=$o6DbUrl
$env:PYTHONIOENCODING='utf-8'
New-Item -ItemType Directory -Path '.codex-scratch/o6-provider-repro'
.venv/Scripts/python.exe -B -X utf8 -m pytest tests/e2e_runtime/test_production_search_process_mysql.py -k provider_ -vv --tb=short -p no:cacheprovider --basetemp=.codex-scratch/o6-provider-repro/provider-tmp --junitxml=.codex-scratch/o6-provider-repro/provider.xml --mysql-report=.codex-scratch/o6-provider-repro/provider-mysql.json
.venv/Scripts/python.exe -B -X utf8 -m pytest tests/e2e_runtime/test_production_search_process_mysql.py -k 'not provider_' -vv --tb=short -p no:cacheprovider --basetemp=.codex-scratch/o6-provider-repro/legacy-tmp --junitxml=.codex-scratch/o6-provider-repro/legacy.xml --mysql-report=.codex-scratch/o6-provider-repro/legacy-mysql.json
.venv/Scripts/python.exe -B -X utf8 -m pytest tests/e2e_runtime/test_production_processes.py tests/search/test_provider_bounds.py::test_429_status_code_retries tests/search/test_provider_bounds.py::test_5xx_status_code_retries tests/search/test_provider_bounds.py::test_retry_stops_when_run_deadline_exhausted_between_attempts tests/case/test_candidate_search_failure.py::test_failed_search_view_shows_failure_not_no_result -q -p no:cacheprovider --basetemp=.codex-scratch/o6-provider-repro/related-tmp --junitxml=.codex-scratch/o6-provider-repro/related.xml
```

각 명령은 exit 0과 기대한 PASS/skip 0을 확인한다. 기대 개수는 각각 3·8·6이다. 관련 6개 시험 본문은 MySQL을 사용하지 않지만, 위 명령은 require mode의 MySQL 사전 점검으로 연결·schema 생성/삭제를 수행한다. 위 명령은 전체 suite·Worker kill을 선택하지 않는다.

## 재현: 같은 응답의 웹 소비 2개

기존 raw JSON을 받지 않아도 위 provider 시험이 각 tmp에 새 o6-evidence.json을 만든다. 다음으로 scenario 이름의 JSON을 복사한다.

```powershell
Get-ChildItem '.codex-scratch/o6-provider-repro/provider-tmp' -Recurse -Filter o6-evidence.json | ForEach-Object {
  $o6Record = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path '.codex-scratch/o6-provider-repro' ($o6Record.scenario + '.json'))
}
```

아래 두 파일을 새 재현 폴더에 저장한다. 기존 recorded-response jsdom 시험의 코드다. 이미 설치된 저장소 Node 의존성을 사용하며 실제 HTTP 대신 캡처 응답을 공급한다. 이 보조 시험은 ignored 실행 도구로, 일반 CI에 자동 포함된 회귀라고 주장하지 않는다.

`.codex-scratch/o6-provider-repro/captured-case-view.test.tsx`:

```tsx
// Recorded-response integration: same CaseViews produced by separate API/Worker
// processes. Real web routing, screen, action handling and HTTP client; no server.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { createApi } from '../../apps/web/src/api/client'
import { ApiFlow } from '../../apps/web/src/screens/ApiFlow'
import { FailedScreen } from '../../apps/web/src/screens/FailedScreen'
import { selectScreen } from '../../apps/web/src/state/selectScreen'

afterEach(cleanup)

for (const scenario of ['provider_retry_exhausted', 'provider_deadline_exhausted']) {
  it(`${scenario}: captured failure renders notice and retry creates progress with exact real API payload`, async () => {
    const evidence = JSON.parse(readFileSync(resolve(import.meta.dirname, `${scenario}.json`), 'utf8'))
    const view = evidence.coarse_case_view
    let current = view
    const posts: unknown[] = []
    const api = createApi({ fetch: async (url, init) => {
      const path = new URL(String(url), 'http://localhost').pathname
      if (init?.method === 'POST') {
        expect(path).toBe(`/cases/${view.case_id}/commands`)
        posts.push(JSON.parse(String(init.body)))
        expect(posts.at(-1)).toEqual(evidence.retry_request)
        current = evidence.retry_response.body.case_view
        return new Response(JSON.stringify(evidence.retry_response.body), { status: evidence.retry_response.status })
      }
      expect(path).toBe(`/cases/${view.case_id}/view`)
      return new Response(JSON.stringify(current), { status: 200 })
    } })
    history.replaceState(null, '', `/?case=${view.case_id}`)
    expect(selectScreen(view).kind).toBe('SEARCH_FAILED')
    const screen = render(<ApiFlow api={api} caseId={view.case_id} />)
    await screen.findByText('장면을 찾는 중에 문제가 생겼어요.')
    expect(screen.container.querySelector('.failed')).not.toBeNull()
    expect(screen.container.querySelector('.noresult')).toBeNull()
    expect(screen.container.querySelector('.flow')).toBeNull()
    const retry = screen.getByRole('button', { name: '다시 찾기', exact: true }) as HTMLButtonElement
    expect(retry.disabled).toBe(false)
    expect((screen.getByRole('button', { name: '처음으로', exact: true }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(retry)
    await screen.findByText('분석 중단')
    await waitFor(() => expect(posts).toEqual([evidence.retry_request]))
    expect(selectScreen(current).kind).toBe('PROGRESS')
    expect(screen.container.querySelector('.failed')).toBeNull()
    expect(screen.queryByRole('button', { name: '다시 찾기', exact: true })).toBeNull()
    // Isolate the existing screen's home callback; jsdom cannot navigate a page.
    cleanup()
    let exited = 0
    const home = render(<FailedScreen view={view} onAction={() => {}} canRun={() => true} onNewReport={() => exited++} />)
    fireEvent.click(home.getByRole('button', { name: '처음으로', exact: true }))
    expect(exited).toBe(1)
  })
}
```

`.codex-scratch/o6-provider-repro/vitest.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    include: ['../../.codex-scratch/o6-provider-repro/captured-case-view.test.tsx'],
    environment: 'jsdom',
  },
})
```

apps/web에서 다음을 실행한다. 기대 결과는 2 PASS다.

```powershell
node ../../node_modules/vitest/vitest.mjs run --config ../../.codex-scratch/o6-provider-repro/vitest.config.ts --reporter=verbose
```

## 검토·정리·미검증

독립 코드 리뷰에서 수정이 필요한 결함은 확인하지 못했다. 새 provider 시험 이전의 기존 8개 분기와 HINT/readout/export helper 호출 경계를 정적으로 검토했다. readout/export 전체 process suite를 추가 실행한 것은 아니다.

최초 증거 수집 오류(JobRecord에 없는 status 참조) 실행 3 FAIL, sandbox의 웹 임시 asset ENOENT 수집 실패는 최종 PASS에 합산하지 않았다. 1 != 4 RED 실행은 기존 max_retries=0 공백을 검출했다. 수정 후 보고서만 위 결과로 쓴다. 직접 ruff는 기존 E701/E702 22건으로 실패하며 배포 원문과 source line/code/message 비교에서 신규 0건이다. 관련 없는 스타일은 수정하지 않았다.

원 검증에서는 fixture schema 0·기본 시험 DB table 0 확인 후 전용 MySQL 컨테이너·익명 볼륨을 제거하고 포트 닫힘·기록된 API/Worker/pytest PID 8개 잔존 없음을 확인했다. 생성 시험 tmp는 삭제하고 JSON·JUnit·로그·patch는 보존했다. PR 준비의 추가 회귀 정리 결과는 아래에 별도 기록한다.

미검증: 실제 provider·요금·실네트워크 timeout, 실제 600초 wall 대기, HTTP 429의 process 전체 연결, AWS·운영 서버·운영 설정, 실브라우저 이동, 사용자 retry로 새로 QUEUED된 Job 재실행, 모든 Job kind의 실패. HTTP 429는 관련 단위 시험에서만 확인했다. 전체 E2E·Worker kill은 반복하지 않았다.

staging·commit·push·PR 생성은 하지 않았다. 원래 시험 파일 2개는 hash를 유지한 미커밋 상태다.

### 추가 회귀 정리

전용 schema 잔여 0개, 기본 DB table 0개. 전용 컨테이너·익명 볼륨 제거, localhost 13379 닫힘을 확인했다. 해당 회귀의 생성 tmp도 증거 보고서를 보존한 후 정리했다. 기존 서비스·이미지는 정리 대상으로 삼지 않았다.
