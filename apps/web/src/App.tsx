import { useState, type JSX } from 'react'
import type { Action } from './contracts/caseView'
import { describeIntent } from './contracts/actionIntent'
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
  // 발주 경로(case worker)가 아직 없다. 버튼이 아무 일도 안 하는 것처럼 보이지
  // 않게, 계약이 정한 「이 버튼이 무엇을 발주하는가」를 그대로 보여준다.
  // 실제 전송이 붙는 자리는 이 setState 하나다.
  const [lastAction, setLastAction] = useState<Action | null>(null)
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
            onClick={() => {
              setCurrent(i)
              setLastAction(null)
            }}
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

        <NoticeList blocking={screen.blocking} info={screen.info} onAction={setLastAction} />

        {lastAction && (
          <div className="panel panel-p tight action-intent">
            <div className="sec-label">눌린 액션 — 발주 경로 미연결</div>
            <div className="kv-val mono">{lastAction}</div>
            <div className="kv-src">{describeIntent(lastAction)}</div>
          </div>
        )}

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
