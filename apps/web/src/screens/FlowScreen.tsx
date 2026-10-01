import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { noticeMessage } from '../contracts/labels'
import { selectScreen } from '../state/selectScreen'
import { ProgressPanel } from '../components/ProgressPanel'

// Figma 02_Main_Flow · 02_Retry_Flow · 02_Fail_Flow. 세 프레임은 같은 틀이고
// 단계 상태(progress)와 알림(notices)만 다르다 — 둘 다 CaseView에서 온다.
// 진행 화면에는 버튼이 없어서 알림도 문구만 보여준다.
export function FlowScreen(props: { view: CaseView; fileName: string; situation: string }): JSX.Element {
  const screen = selectScreen(props.view)
  return (
    <div className="stack">
      <h1 className="page-title">올리면 진행</h1>
      <div className="panel panel-p tight run-summary">
        <b>{props.fileName}</b>
        <span className="kv-src">“{props.situation}”</span>
      </div>
      {props.view.notices.map((n) => (
        <div key={n.code} className={`flow-notice${n.blocking ? ' blocking' : ''}`}>
          {noticeMessage(n.message_key)}
        </div>
      ))}
      <ProgressPanel view={props.view} jobs={screen.jobs} />
    </div>
  )
}
