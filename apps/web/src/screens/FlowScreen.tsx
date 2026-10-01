import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { selectScreen } from '../state/selectScreen'
import { ProgressPanel } from '../components/ProgressPanel'

// Figma 02_Main_Flow · 02_Retry_Flow · 02_Fail_Flow. 세 프레임은 같은 틀이고
// 단계 상태(progress)와 알림(notices)만 다르다 — 둘 다 CaseView에서 온다.
// 진행 화면에는 버튼도 알림 문구도 없다. 실패는 그 단계를 빨갛게만 칠하고,
// 무슨 일이 있었는지는 결과 화면에서 알린다.
export function FlowScreen(props: { view: CaseView; fileName: string; situation: string }): JSX.Element {
  const screen = selectScreen(props.view)
  return (
    <div className="stack">
      <h1 className="page-title">올리면 진행</h1>
      <div className="panel panel-p tight run-summary">
        <b>{props.fileName}</b>
        {props.situation && <span className="kv-src">“{props.situation}”</span>}
      </div>
      <ProgressPanel view={props.view} jobs={screen.jobs} />
    </div>
  )
}
