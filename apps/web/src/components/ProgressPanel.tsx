import type { JSX } from 'react'
import type { CaseView, RunningJob } from '../contracts/caseView'
import { PROGRESS_LABELS, jobLabel, stepLabel } from '../contracts/labels'
import { Panel } from './Panel'

export function ProgressPanel(props: { view: CaseView; jobs: RunningJob[] }): JSX.Element {
  return (
    <Panel>
      <div className="sec-label">진행 상태</div>
      <div className="kv kv-rows">
        {props.view.progress.map((p) => (
          <div className="kv-row" key={p.step}>
            <span className="kv-k">{stepLabel(p.step)}</span>
            <span className="kv-v">
              <span className="kv-val">{PROGRESS_LABELS[p.state]}</span>
            </span>
          </div>
        ))}
      </div>
      {props.jobs.length > 0 && (
        <div>
          <div className="sec-label" style={{ marginTop: 14 }}>
            진행 중인 작업
          </div>
          <div className="kv kv-rows">
            {props.jobs.map((job) => (
              <div className="kv-row" key={job.job_id}>
                <span className="kv-k">{jobLabel(job.label_key)}</span>
                <span className="kv-v">
                  <span className="kv-val">{job.status === 'RUNNING' ? '진행 중' : '대기'}</span>
                  <span className="kv-src mono">{job.job_id}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}
