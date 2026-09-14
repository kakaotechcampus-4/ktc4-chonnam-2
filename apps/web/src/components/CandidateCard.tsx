import type { JSX } from 'react'
import type { Candidate } from '../contracts/caseView'
import { SITUATION_LABELS, staleLabel } from '../contracts/labels'

// at_provenance는 아직 raw 문자열로만 내려온다. case-view/v1.4에서
// at_provenance_label_key가 신설되면 그 키로 문구를 고른다(PR #46 Q-3).
// 확정 전까지 raw 값을 문구로 번역하지 않는다 — 만들면 두 번 만든다.
export function CandidateCard(props: { candidate: Candidate }): JSX.Element {
  const c = props.candidate
  const stale = staleLabel(c.stale_revision_label_key)
  return (
    <div className={`panel panel-p tight${c.selected ? ' candidate-selected' : ''}`}>
      <div className="sec-label">
        {c.selected ? '선택된 장면' : '후보 장면'}
        {c.stale_revision && stale && <span className="badge badge-unknown sm">{stale}</span>}
      </div>
      <div className="kv-val mono">{c.at ?? '시각 미확정'}</div>
      <div className="kv-src">{c.observed}</div>
      <div className="kv kv-rows">
        <div className="kv-row">
          <span className="kv-k">상황 확인</span>
          <span className="kv-v">
            <span className="kv-val">{SITUATION_LABELS[c.situation_confirmation]}</span>
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-k">시각 출처</span>
          <span className="kv-v">
            <span className="kv-val mono">{c.at_provenance}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
