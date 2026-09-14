import { useState, type JSX } from 'react'
import { LOAD_ISSUES, SNAPSHOTS } from './contracts/fixtures'
import { selectScreen } from './state/selectScreen'
import { DevExtra } from './components/DevExtra'
import { NoticeList } from './components/NoticeList'
import { ProgressPanel } from './components/ProgressPanel'
import { CandidatesScreen } from './screens/CandidatesScreen'
import { EvidenceScreen } from './screens/EvidenceScreen'
import { HandoffScreen } from './screens/HandoffScreen'
import { NoResultScreen } from './screens/NoResultScreen'

// 1차 범위에 라우터·서버·로컬 상태 머신이 없다. 화면 전환은 「어느 스냅샷을
// 보는가」뿐이고, 화면 내용은 전부 그 CaseView 1건에서 파생된다.
export function App(): JSX.Element {
  const [current, setCurrent] = useState(0)
  const snapshot = SNAPSHOTS[current]
  const view = snapshot.view
  const screen = selectScreen(view)

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
          <span className="kv-src">{screen.reason}</span>
          <span className={LOAD_ISSUES.length === 0 ? 'load-ok' : 'load-bad'}>
            스냅샷 {SNAPSHOTS.length}건 파싱 {LOAD_ISSUES.length === 0 ? 'OK' : `문제 ${LOAD_ISSUES.length}건`}
          </span>
        </div>

        <NoticeList blocking={screen.blocking} info={screen.info} />

        {screen.kind === 'PROGRESS' && <ProgressPanel view={view} jobs={screen.jobs} />}
        {screen.kind === 'NO_RESULT' && <NoResultScreen view={view} />}
        {screen.kind === 'CANDIDATES' && <CandidatesScreen view={view} />}
        {screen.kind === 'EVIDENCE' && (
          <>
            <EvidenceScreen view={view} />
            <DevExtra label="증빙용 — 진행 상태(제품 화면에서는 별도 표시)">
              <ProgressPanel view={view} jobs={screen.jobs} />
            </DevExtra>
          </>
        )}
        {screen.kind === 'HANDOFF' && (
          <>
            <HandoffScreen view={view} />
            <DevExtra label="증빙용 — 확인한 내용(제품 화면에서는 이전 단계)">
              <EvidenceScreen view={view} />
            </DevExtra>
          </>
        )}

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
