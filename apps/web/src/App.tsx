import { useState, type JSX } from 'react'
import { LOAD_ISSUES, SNAPSHOTS } from './contracts/fixtures'
import { CaseScreen } from './screens/CaseScreen'
import { ApiFlow } from './screens/ApiFlow'
import { OfficialSampleEntry } from './screens/OfficialSampleEntry'
import { DemoFlow } from './screens/DemoFlow'
import { rememberedCase } from './state/lastCase'

// 기본은 공식 샘플 전용 실제 HTTP 흐름이다. `?case=<id>`는 같은 세션의 case를 이어 본다.
// `?api`는 내부 전용 기존 업로드 UI이며 A-1 서버의 업로드/권한 차단을 우회하지 못한다.
// `?demo`는 mock fixture 시연 흐름, `?cases`는 시연에서 보여 줄 경우(실패·결과 없음 등)를 고르는 상자를 연다.
// `?dev`는 스냅샷을 하나씩 넘겨 보는 증빙 화면이다.
// 주소에 case가 없으면 이 브라우저가 마지막으로 연 case로 이어간다 — 창을 닫았다 와도 분석 · 결과가 이어진다.
export function App(): JSX.Element {
  const params = new URLSearchParams(location.search)
  if (params.has('dev')) return <SnapshotViewer />
  if (params.has('demo') || params.has('cases')) return <DemoFlow casePicker={params.has('cases')} />
  const caseId = params.get('case')
  if (params.has('api')) return caseId ? <ApiFlow caseId={caseId} /> : <ApiFlow caseId={rememberedCase()} remembered />
  return <OfficialSampleEntry caseId={caseId ?? rememberedCase()} remembered={!caseId} />
}

// 1차 범위에 라우터·서버·로컬 상태 머신이 없다. 화면 전환은 「어느 스냅샷을
// 보는가」뿐이다.
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
