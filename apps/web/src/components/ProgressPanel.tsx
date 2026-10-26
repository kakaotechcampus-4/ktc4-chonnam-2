import type { JSX, ReactNode } from 'react'
import type { CaseView, RunningJob } from '../contracts/caseView'
import { PROGRESS_LABELS, jobLabel, stepLabel } from '../contracts/labels'
import { Panel } from './Panel'

// 진행 화면은 읽기 전용이다(core-user-flow.md). 단계별 상태만 세로로 잇고
// ETA·퍼센트는 내지 않는다 — 계약에 없는 값이다.
// heading은 목록 제목 자리 — 진행 화면은 「진행 단계 · 전체 N단계」를 넣고, 나머지는 기존 제목이다.
export function ProgressPanel(props: { view: CaseView; jobs: RunningJob[]; heading?: ReactNode }): JSX.Element {
  return (
    <Panel>
      <div className="sec-label">{props.heading ?? '진행 상태'}</div>
      <ol className="timeline">
        {props.view.progress.map((p) => (
          <li key={p.step} className={`tl-${p.state.toLowerCase()}`}>
            <span className="tl-label">{stepLabel(p.step)}</span>
            <span className="kv-src">{PROGRESS_LABELS[p.state]}</span>
          </li>
        ))}
      </ol>
      {props.jobs.length > 0 && (
        <div className="kv-src" style={{ marginTop: 12 }}>
          {props.jobs
            .map((job) => `${jobLabel(job.label_key)} ${job.status === 'RUNNING' ? '진행 중' : '대기'}`)
            .join(' · ')}
        </div>
      )}
    </Panel>
  )
}
