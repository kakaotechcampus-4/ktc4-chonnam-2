import { useEffect, useState, type JSX } from 'react'
import { LOAD_ISSUES, SNAPSHOTS } from './contracts/fixtures'
import { CaseScreen } from './screens/CaseScreen'
import { ApiFlow } from './screens/ApiFlow'
import { OfficialSampleEntry } from './screens/OfficialSampleEntry'
import { DemoFlow } from './screens/DemoFlow'
import { rememberedCase } from './state/lastCase'
import { createPublicSamplesApi } from './api/publicSamples'

// 공개 입구는 기본 주소다. 배포의 API가 현재 등록 방식을 결정한다.
// `?case=<id>`는 같은 세션의 case를 이어 본다. 어느 진입도 A-1 서버 보호를 우회하지 못한다.
// `?demo`는 mock fixture 시연 흐름, `?cases`는 시연에서 보여 줄 경우(실패·결과 없음 등)를 고르는 상자를 연다.
// `?dev`는 스냅샷을 하나씩 넘겨 보는 증빙 화면이다.
// 주소에 case가 없으면 이 브라우저가 마지막으로 연 case로 이어간다 — 창을 닫았다 와도 분석 · 결과가 이어진다.
export function App(): JSX.Element {
  const params = new URLSearchParams(location.search)
  if (params.has('dev')) return <SnapshotViewer />
  if (params.has('demo') || params.has('cases')) return <DemoFlow casePicker={params.has('cases')} />
  const caseId = params.get('case')
  return <LiveEntry caseId={caseId ?? rememberedCase()} remembered={!caseId} />
}

function LiveEntry(props: { caseId: string | null; remembered: boolean }) {
  const [client] = useState(createPublicSamplesApi)
  const [mode, setMode] = useState<'loading' | 'internal' | 'server' | 'bundle' | 'error'>('loading')
  useEffect(() => {
    const url = new URL(location.href)
    if (url.searchParams.has('sample')) {
      url.searchParams.delete('sample')
      history.replaceState(history.state, '', url)
    }
    let active = true
    void client.intakeMode().then(result => {
      if (active) setMode(result.ok ? result.data.upload_enabled ? 'bundle' : 'server'
        : result.status === 404 ? 'internal' : 'error')
    })
    return () => { active = false }
  }, [client])
  if (mode === 'loading') return <main className="web-main"><p role="status">체험 설정을 확인하고 있어요.</p></main>
  if (mode === 'error') return <main className="web-main"><p role="alert">체험에 연결할 수 없어요. 잠시 뒤 새로고침해 주세요.</p></main>
  if (mode === 'internal') return <ApiFlow {...props} />
  return <OfficialSampleEntry {...props} client={client} upload={mode === 'bundle'} />
}

// `?dev` 스냅샷 보기 — 라우터·서버·로컬 상태 머신 없이 fixture 스냅샷만 넘겨 본다.
// 화면 전환은 「어느 스냅샷을 보는가」뿐이다.
function SnapshotViewer(): JSX.Element {
  const [current, setCurrent] = useState(0)
  const view = SNAPSHOTS[current].view

  return (
    <div>
      <div className="snapshot-bar">
        {SNAPSHOTS.map((s, i) => (
          <button
            key={`${s.scenarioId}-${s.index}`}
            type="button"
            className={`btn${i === current ? ' on' : ''}`}
            onClick={() => setCurrent(i)}
          >
            {s.scenarioId.replace('scenario_', '').replace('_001', '')} #{s.index}
          </button>
        ))}
      </div>

      <main className="web-main">
        <div className="web-meta">
          <span className="kv-val mono">{view.case_id}</span>
          <span className="kv-src mono">rev {view.case_rev}</span>
          <span className={LOAD_ISSUES.length === 0 ? 'load-ok' : 'load-bad'}>
            스냅샷 {SNAPSHOTS.length}건 파싱 {LOAD_ISSUES.length === 0 ? 'OK' : `문제 ${LOAD_ISSUES.length}건`}
          </span>
        </div>

        <CaseScreen view={view} showReason />

        {LOAD_ISSUES.length > 0 && (
          <div className="panel panel-p tight">
            <div className="sec-label">계약과 어긋난 값</div>
            {LOAD_ISSUES.map((issue, i) => (
              <div className="kv-src mono" key={i}>
                {issue.where} — {issue.problem}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
